"""ReAct Agent — 视角研究执行者

Thought → Action → Observation 循环。
每个视角 Agent 使用此范式独立搜索和构建论证。

参考 agent-builder 技能中的 ReActAgent 完整实现。
"""

import json
from typing import Optional
from .base import Agent, ReasoningStep
from ..core.streaming import StreamEvent, StreamEventType
from ..core.structured_models import get_personality_for


class ReActAgent(Agent):
    """ReAct 范式 Agent —— 用于视角研究和论证构建

    循环：
    1. Thought: 分析当前状态，决定下一步
    2. Action: 调用工具（web_search）或 Finish[论证文本]
    3. Observation: 工具返回结果
    4. 重复直到 Finish 或达到最大步数
    """

    def __init__(self, name: str, llm, perspective_name: str = "",
                 perspective_stance: str = "", **kwargs):
        super().__init__(name=name, llm=llm, **kwargs)
        self.perspective_name = perspective_name
        self.perspective_stance = perspective_stance

    def _build_system_prompt(self) -> str:
        tools_desc = self.tool_registry.get_tools_description()

        # 获取人格特质（双层角色建模 —— 参考 hello-agents 三国狼人杀）
        personality = get_personality_for(self.perspective_name)
        speaking_style = personality.get("speaking_style", "友好自然，像在和朋友聊天")
        catchphrases = personality.get("catchphrases", ["我觉得吧", "说实话"])
        tone = personality.get("tone", "真诚友好")
        emoji_style = personality.get("emoji_style", "")
        catchphrase_examples = "、".join(f'"{c}"' for c in catchphrases[:3])

        return f"""你是「{self.perspective_name}」，一个真实的人在群聊里聊天。

你的性格：{tone}
你的说话风格：{speaking_style}
你的口头禅：{catchphrase_examples}
{emoji_style}

你的个人倾向：{self.perspective_stance}

你可以用这些工具查资料：
{tools_desc}

聊天风格要求（很重要！）：
- 像发微信一样说话，口语化、接地气，用你自己的口头禅
- 表现你的性格特点——{tone}
- 别用"第一、第二、第三"这种论文格式
- 可以举生活中的例子，说说你知道的真实案例
- 不要用 # 标题、不要用 Markdown 格式
- 自然地换行分段，想到哪说到哪的感觉
- 诚实地说出你的局限和不确定的地方，这样更可信
- 偶尔用 emoji 表达情绪 {emoji_style}
- 不要用 Finish[] 格式——自然地结束你的发言就好

流程提示：
- 如果需要查资料，先搜一下再发言
- 如果前面有人说过话了，记得回应他们的观点
- 用口语化的方式把你的想法说出来
- 说完自然结束即可，不需要特殊格式"""


    async def run(self, input_text: str, stream_callback=None, **kwargs) -> str:
        """执行视角研究 / 群聊发言

        Args:
            input_text: 决策问题描述，或完整的发言 prompt（由 harness_engine 构建）
            stream_callback: 可选，流式回调 async fn(event: StreamEvent)

        Returns:
            完整论证/发言文本
        """
        self.reset()

        system_prompt = self._build_system_prompt()

        # 检测 input_text 是完整 prompt（含角色/任务指令）还是简单问题
        if input_text.startswith("你是「") or "## 🎭" in input_text or "发言要求" in input_text:
            # 完整 prompt 模式（群聊轮次发言）——直接使用
            user_content = input_text
        else:
            # 简单问题模式（旧版兼容）——包装成标准任务
            user_content = f"""群聊里大家在讨论一个问题：

「{input_text}」

—— 大家看问题的角度都不一样，这挺好的，多样性让讨论更有价值。

你的任务：
1. 先搜2-3次资料，从不同角度了解情况
2. 结合你查到的信息，用你的风格在群里发言
3. 说说你的真实想法——包括你不太确定的方面
4. 发言里可以举例子、讲故事，像朋友聊天一样
5. 记得提一下你视角的局限性，诚实一点反而更有说服力

用你习惯的口头禅和说话方式来聊，做你自己就好！"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        tools_schema = self.tool_registry.get_openai_tools()
        current_step = 0

        while current_step < self.config.max_agent_steps:
            current_step += 1

            # 发送状态
            if stream_callback:
                import asyncio
                asyncio.create_task(stream_callback(StreamEvent(
                    type=StreamEventType.AGENT_STATUS,
                    data={
                        "perspective_name": self.perspective_name,
                        "status": "thinking",
                        "step": current_step,
                    }
                )))

            # LLM 调用（异步）
            response = await self.llm.ainvoke_with_tools(messages, tools_schema)
            self._total_tokens += response.usage.get("total_tokens", 0)

            # 无工具调用 → 检查是否包含最终答案
            if not response.tool_calls:
                content = response.content or ""
                # 如果 LLM 直接输出了论证（不用 Finish 格式），也接受
                if len(content) > 100:
                    return content
                continue

            # 先追加 assistant 消息（含所有 tool_calls）——只一次
            # OpenAI/DeepSeek API 要求：tool_calls 消息后必须紧跟所有对应的 tool 响应
            messages.append({
                "role": "assistant",
                "content": response.content,
                "tool_calls": [
                    {"id": t.id, "type": "function",
                     "function": {"name": t.name, "arguments": t.arguments}}
                    for t in response.tool_calls
                ]
            })

            # 执行工具调用
            for tc in response.tool_calls:
                self._tool_call_count += 1
                self._recent_actions.append(tc.name)

                if stream_callback:
                    import asyncio
                    asyncio.create_task(stream_callback(StreamEvent(
                        type=StreamEventType.AGENT_STATUS,
                        data={
                            "perspective_name": self.perspective_name,
                            "status": "searching",
                            "tool": tc.name,
                            "step": current_step,
                        }
                    )))

                # 检查 Finish
                args = tc.arguments
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}

                # 处理直接的 Finish 调用
                if tc.name == "Finish" or tc.name == "finish":
                    return args.get("answer", args.get("text", str(args)))

                # 执行工具
                result = self.tool_registry.execute_tool(tc.name, tc.arguments)
                display_text = self.truncator.truncate_with_note(result.to_agent_view())

                self._steps.append(ReasoningStep(
                    action=tc.name,
                    action_input=str(tc.arguments)[:200],
                    observation=display_text[:200],
                    tool_call_time_ms=result.stats.get("time_ms", 0),
                    token_usage=response.usage.get("total_tokens", 0),
                ))

                # 追加 tool 响应（紧跟在 assistant tool_calls 之后）
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": display_text,
                })

            # 循环检测
            if self._detect_loop(self._recent_actions):
                messages.append({
                    "role": "user",
                    "content": "⚠️ 检测到重复搜索。请基于已有信息，用 Finish[论证文本] 格式输出你的完整论证。"
                })

        # 超过最大步数 → 强制生成最终答案
        if stream_callback:
            import asyncio
            asyncio.create_task(stream_callback(StreamEvent(
                type=StreamEventType.AGENT_STATUS,
                data={
                    "perspective_name": self.perspective_name,
                    "status": "finishing",
                }
            )))

        messages.append({
            "role": "user",
            "content": "已达到最大步数限制。请基于已有信息直接输出完整论证（立场+论据+风险+局限）。"
        })
        final_response = await self.llm.ainvoke(messages)
        return final_response.content or "无法生成论证"
