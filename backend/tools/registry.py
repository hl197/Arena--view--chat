"""工具注册表

管理工具的注册、查找、执行，集成熔断器和调用历史。
"""

import time
from typing import Optional
from .base import Tool
from .response import ToolResponse
from .errors import ToolErrorCode
from .circuit_breaker import CircuitBreaker


class ToolRegistry:
    """工具注册表——工具注册、查找、执行

    集成能力：
    - 重名检测
    - 熔断器（可选）
    - 调用历史统计
    """

    def __init__(self, circuit_enabled: bool = True):
        self._tools: dict[str, Tool] = {}
        self._circuits: dict[str, CircuitBreaker] = {}
        self._circuit_enabled = circuit_enabled
        self._call_history: list[dict] = []

    def register_tool(self, tool: Tool):
        """注册工具——检测重名"""
        if tool.name in self._tools:
            raise ValueError(f"工具 '{tool.name}' 已注册。请先 unregister 或使用不同名称。")
        self._tools[tool.name] = tool
        if self._circuit_enabled:
            self._circuits[tool.name] = CircuitBreaker()

    def unregister_tool(self, name: str):
        """移除工具"""
        if name in self._tools:
            del self._tools[name]

    def get_tool(self, name: str) -> Optional[Tool]:
        """获取工具"""
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        """列出所有工具名称"""
        return list(self._tools.keys())

    def get_tools_description(self) -> str:
        """生成工具描述文本（用于 Prompt 注入）"""
        if not self._tools:
            return "无可用工具"

        lines = []
        for name, tool in self._tools.items():
            params = tool.get_parameters()
            param_desc = ", ".join(
                f"{p.name}: {p.type}" + ("?" if not p.required else "")
                for p in params
            )
            lines.append(f"- {name}({param_desc}): {tool.description}")
        return "\n".join(lines)

    def get_openai_tools(self) -> list[dict]:
        """生成 OpenAI Function Calling 格式的工具列表"""
        return [tool.to_openai_schema() for tool in self._tools.values()]

    def execute_tool(self, name: str, input_text: str) -> ToolResponse:
        """执行工具——集成熔断器+调用历史

        Args:
            name: 工具名称
            input_text: 参数（JSON 字符串或纯文本）
        """
        start_time = time.time()

        tool = self._tools.get(name)
        if not tool:
            # 相似建议
            from difflib import get_close_matches
            suggestions = get_close_matches(name, list(self._tools.keys()), n=3, cutoff=0.4)
            hint = f"。您是否想用: {', '.join(suggestions)}？" if suggestions else ""
            return ToolResponse.error(
                code=ToolErrorCode.TOOL_NOT_REGISTERED,
                message=f"工具 '{name}' 未注册。可用: {', '.join(self._tools.keys())}{hint}"
            )

        # 熔断器检查
        if self._circuit_enabled and name in self._circuits:
            circuit = self._circuits[name]
            if not circuit.before_call():
                return ToolResponse.error(
                    code=ToolErrorCode.CIRCUIT_OPEN,
                    message=f"工具 '{name}' 已熔断，请稍后重试。"
                )

        # 解析参数
        import json
        try:
            if isinstance(input_text, str):
                if input_text.strip().startswith("{"):
                    parameters = json.loads(input_text)
                else:
                    parameters = {"query": input_text}
            elif isinstance(input_text, dict):
                parameters = input_text
            else:
                parameters = {"input": str(input_text)}
        except json.JSONDecodeError:
            parameters = {"query": input_text}

        result = tool.run_with_timing(parameters)

        # 更新熔断器
        if self._circuit_enabled and name in self._circuits:
            if result.is_error and result.error_code != ToolErrorCode.TOOL_NOT_REGISTERED:
                self._circuits[name].on_failure()
            else:
                self._circuits[name].on_success()

        # 记录调用历史
        self._call_history.append({
            "name": name,
            "params_keys": list(parameters.keys()),
            "time_ms": int((time.time() - start_time) * 1000),
            "status": result.status.value,
            "error_code": result.error_code.value if result.error_code else None,
        })

        return result

    async def aexecute_tool(self, name: str, input_text: str) -> ToolResponse:
        """异步执行工具"""
        tool = self._tools.get(name)
        if not tool:
            return ToolResponse.error(
                code=ToolErrorCode.TOOL_NOT_REGISTERED,
                message=f"工具 '{name}' 未注册"
            )

        import json
        try:
            if isinstance(input_text, str) and input_text.strip().startswith("{"):
                parameters = json.loads(input_text)
            elif isinstance(input_text, dict):
                parameters = input_text
            else:
                parameters = {"query": str(input_text)}
        except json.JSONDecodeError:
            parameters = {"query": str(input_text)}

        return await tool.arun(parameters)

    def get_call_stats(self) -> dict[str, dict]:
        """工具调用统计"""
        stats: dict[str, dict] = {}
        for call in self._call_history:
            name = call["name"]
            if name not in stats:
                stats[name] = {"count": 0, "success": 0, "total_time_ms": 0}
            stats[name]["count"] += 1
            if call["status"] == "success":
                stats[name]["success"] += 1
            stats[name]["total_time_ms"] += call["time_ms"]
        return stats

    def get_circuit_status(self) -> dict[str, str]:
        """获取所有工具的熔断器状态"""
        return {name: circuit.state.value for name, circuit in self._circuits.items()}
