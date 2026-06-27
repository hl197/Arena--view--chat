"""Finish 工具 — Agent 终止信号

ReAct Agent 通过调用此工具来标记论证完成。
注册到 ToolRegistry 后，LLM 通过 Function Calling 调用它。
"""

from ..base import Tool, ToolParameter
from ..response import ToolResponse


class FinishTool(Tool):
    """Finish 工具 — Agent 用此工具结束执行并返回最终答案"""

    def __init__(self):
        super().__init__(
            name="finish",
            description="当你已经完成研究、构建了完整的结构化论证后，调用此工具来提交最终答案。"
                        "调用后 Agent 执行结束。"
        )

    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="answer",
                type="string",
                description="你的完整论证文本，包含：立场陈述、核心论据（每点有数据支撑）、风险评估、该立场的局限性",
                required=True,
            ),
        ]

    def run(self, parameters: dict) -> ToolResponse:
        return ToolResponse.success(
            text=parameters.get("answer", ""),
            data={"terminated": True},
        )
