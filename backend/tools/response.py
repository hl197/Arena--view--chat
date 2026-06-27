"""工具响应协议

参考 HelloAgents 的 ToolResponse 三态协议：
- SUCCESS: 工具执行成功
- PARTIAL: 部分成功（有数据但有警告）
- ERROR: 执行失败
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any
from .errors import ToolErrorCode


class ToolStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    ERROR = "error"


@dataclass
class ToolResponse:
    """工具执行统一响应"""
    status: ToolStatus
    text: str = ""                    # 人类可读的输出
    data: Optional[Any] = None        # 结构化数据
    error_code: Optional[ToolErrorCode] = None
    error_message: str = ""
    stats: dict = field(default_factory=dict)  # {"time_ms": 123, "tokens": 456}

    @classmethod
    def success(cls, text: str = "", data: Any = None, stats: dict = None) -> "ToolResponse":
        return cls(status=ToolStatus.SUCCESS, text=text, data=data, stats=stats or {})

    @classmethod
    def partial(cls, text: str = "", data: Any = None, warning: str = "", stats: dict = None) -> "ToolResponse":
        return cls(status=ToolStatus.PARTIAL, text=text, data=data, error_message=warning, stats=stats or {})

    @classmethod
    def error(cls, code: ToolErrorCode, message: str = "", text: str = "", stats: dict = None) -> "ToolResponse":
        return cls(status=ToolStatus.ERROR, text=text, error_code=code, error_message=message, stats=stats or {})

    @property
    def is_success(self) -> bool:
        return self.status == ToolStatus.SUCCESS

    @property
    def is_error(self) -> bool:
        return self.status == ToolStatus.ERROR

    def to_agent_view(self) -> str:
        """转为 Agent 可见的文本"""
        if self.status == ToolStatus.SUCCESS:
            return self.text
        elif self.status == ToolStatus.PARTIAL:
            return f"⚠️ 部分成功: {self.text}\n警告: {self.error_message}"
        else:
            return f"❌ 错误 [{self.error_code.value if self.error_code else 'UNKNOWN'}]: {self.error_message}\n{self.text}"
