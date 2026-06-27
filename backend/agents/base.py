"""Agent 抽象基类

参考 HelloAgents 的 Agent 基类，集成 8 项横切能力：
- HistoryManager（对话历史）
- TokenCounter（Token 计数）
- ObservationTruncator（工具输出截断）
- CircuitBreaker（工具熔断）
- DebateMemory（辩论记忆）
- TraceLogger（可观测性）
- Token 预算监控
- 循环检测

子类只需实现 run() 方法。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Any
from ..core.config import ArenaConfig
from ..core.exceptions import AgentException, AgentTimeoutException, AgentLoopException
from ..adapters.unified_llm import ArenaLLM
from ..adapters.llm_response import LLMResponse, LLMToolResponse
from ..tools.registry import ToolRegistry
from ..tools.response import ToolResponse, ToolStatus
from ..tools.errors import ToolErrorCode
from ..context.history import HistoryManager
from ..context.token_counter import TokenCounter
from ..context.truncator import ObservationTruncator


@dataclass
class ReasoningStep:
    """每个推理步的结构化记录"""
    thought: str = ""
    action: str = ""
    action_input: str = ""
    observation: str = ""
    next_step: str = ""  # "continue" | "finish" | "error"
    token_usage: int = 0
    tool_call_time_ms: int = 0


class Agent(ABC):
    """Agent 抽象基类——集成横切能力

    子类必须实现:
        run(input_text: str) -> str

    子类可选覆盖:
        _build_system_prompt() -> str
        _parse_output(response: str) -> dict
        _detect_loop(recent_actions: list) -> bool
    """

    def __init__(
        self,
        name: str,
        llm: ArenaLLM,
        system_prompt: str = "",
        tool_registry: Optional[ToolRegistry] = None,
        config: Optional[ArenaConfig] = None,
    ):
        self.name = name
        self.llm = llm
        self.system_prompt = system_prompt
        self.tool_registry = tool_registry or ToolRegistry()
        self.config = config or ArenaConfig()

        # 上下文工程
        self.history_manager = HistoryManager(
            min_retain_rounds=self.config.min_retain_rounds,
            compression_threshold=self.config.compression_threshold,
        )
        self.token_counter = TokenCounter()
        self.truncator = ObservationTruncator(
            max_lines=self.config.tool_output_max_lines,
        )

        # 执行追踪
        self._steps: list[ReasoningStep] = []
        self._recent_actions: list[str] = []
        self._total_tokens: int = 0
        self._tool_call_count: int = 0

    # === 子类必须实现 ===
    @abstractmethod
    async def run(self, input_text: str, **kwargs) -> str:
        """核心运行方法——子类必须实现"""
        ...

    # === 工具方法 ===
    def add_tool(self, tool):
        """动态添加工具"""
        self.tool_registry.register_tool(tool)

    def _build_system_prompt(self) -> str:
        """构建系统提示词——子类覆盖定制"""
        return self.system_prompt

    def _build_messages(self, user_input: str) -> list[dict]:
        """构建发送给 LLM 的消息列表"""
        messages = [{"role": "system", "content": self._build_system_prompt()}]
        messages.extend(self.history_manager.get_messages())
        messages.append({"role": "user", "content": user_input})
        return messages

    # === 工具调用解析 ===
    def _parse_tool_calls(self, response: LLMToolResponse) -> list[dict]:
        """从 LLMToolResponse 中提取工具调用"""
        if not response.tool_calls:
            return []
        return [
            {"name": tc.name, "arguments": tc.arguments, "id": tc.id}
            for tc in response.tool_calls
        ]

    # === 工具执行循环 ===
    async def _run_with_tools(self, messages: list[dict], max_iterations: int = None) -> str:
        """执行工具调用循环直到 Agent 输出最终答案"""
        if max_iterations is None:
            max_iterations = self.config.max_agent_steps

        tools_schema = self.tool_registry.get_openai_tools()

        for iteration in range(max_iterations):
            # 循环检测
            if self._detect_loop(self._recent_actions):
                messages.append({
                    "role": "user",
                    "content": "⚠️ 检测到重复操作。请换一种方法，或基于已有信息直接给出结论。"
                })

            # LLM 调用（异步，释放事件循环）
            response = await self.llm.ainvoke_with_tools(messages, tools_schema)
            self._total_tokens += response.usage.get("total_tokens", 0)

            # 无工具调用 → 最终答案
            if not response.tool_calls:
                return response.content or ""

            # 执行工具调用
            tool_results = []
            for tc in response.tool_calls:
                self._tool_call_count += 1
                self._recent_actions.append(tc.name)

                result = self.tool_registry.execute_tool(tc.name, tc.arguments)

                # 截断过长的工具输出
                display_text = self.truncator.truncate_with_note(result.to_agent_view())

                tool_results.append({
                    "tool_call_id": tc.id,
                    "role": "tool",
                    "content": display_text,
                })

                # 记录步骤
                self._steps.append(ReasoningStep(
                    action=tc.name,
                    action_input=tc.arguments,
                    observation=display_text[:200],
                    tool_call_time_ms=result.stats.get("time_ms", 0),
                    token_usage=response.usage.get("total_tokens", 0),
                ))

            # 将 assistant 消息和 tool 结果注入对话
            assistant_msg = {
                "role": "assistant",
                "content": response.content,
                "tool_calls": [
                    {"id": tc.id, "type": "function",
                     "function": {"name": tc.name, "arguments": tc.arguments}}
                    for tc in response.tool_calls
                ]
            }
            messages.append(assistant_msg)
            for tr in tool_results:
                messages.append(tr)

        # 超过最大迭代
        messages.append({
            "role": "user",
            "content": "已达到最大工具调用次数。请基于已有信息直接给出最终答案。"
        })
        final_response = await self.llm.ainvoke(messages)
        return final_response.content or ""

    # === 循环检测 ===
    def _detect_loop(self, recent_actions: list[str], threshold: int = 3) -> bool:
        """检测 Agent 是否陷入重复调用循环"""
        if len(recent_actions) < threshold:
            return False
        last_n = recent_actions[-threshold:]
        return len(set(last_n)) == 1  # 全部相同 = 死循环

    # === Token 预算 ===
    @property
    def total_tokens(self) -> int:
        return self._total_tokens

    @property
    def tool_call_count(self) -> int:
        return self._tool_call_count

    @property
    def steps(self) -> list[ReasoningStep]:
        return list(self._steps)

    def reset(self):
        """重置状态"""
        self.history_manager.clear()
        self._steps.clear()
        self._recent_actions.clear()
        self._total_tokens = 0
        self._tool_call_count = 0
