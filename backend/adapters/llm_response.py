"""LLM 响应数据结构"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LLMResponse:
    """LLM 非流式调用响应"""
    content: str
    model: str = ""
    usage: dict = field(default_factory=dict)  # {"prompt_tokens": N, "completion_tokens": N, "total_tokens": N}
    latency_ms: int = 0
    reasoning_content: Optional[str] = None  # thinking model 推理过程


@dataclass
class ToolCall:
    """LLM 返回的工具调用"""
    id: str          # "call_xxx"
    name: str        # "web_search"
    arguments: str   # '{"query": "房价走势"}' (JSON 字符串)


@dataclass
class LLMToolResponse:
    """LLM Function Calling 响应"""
    content: Optional[str] = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    model: str = ""
    usage: dict = field(default_factory=dict)
    latency_ms: int = 0


@dataclass
class StreamStats:
    """流式调用统计"""
    model: str = ""
    usage: dict = field(default_factory=dict)
    latency_ms: int = 0
    reasoning_content: Optional[str] = None
