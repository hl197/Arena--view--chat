"""工具抽象基类"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Any
import time
from .response import ToolResponse
from .errors import ToolErrorCode


@dataclass
class ToolParameter:
    """工具参数定义"""
    name: str
    type: str          # "string" | "integer" | "number" | "boolean" | "array" | "object"
    description: str
    required: bool = True
    default: Any = None
    enum: list[str] = field(default_factory=list)


class Tool(ABC):
    """工具抽象基类

    所有工具继承此类，实现 run() 方法。
    框架自动调用 run_with_timing() 添加时间统计。
    """

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    def run(self, parameters: dict) -> ToolResponse:
        """执行工具——子类必须实现"""
        ...

    async def arun(self, parameters: dict) -> ToolResponse:
        """异步执行工具——默认包装同步 run()，IO 密集型工具应覆盖"""
        return self.run(parameters)

    def get_parameters(self) -> list[ToolParameter]:
        """返回工具参数定义——子类覆盖"""
        return []

    def run_with_timing(self, parameters: dict) -> ToolResponse:
        """带计时的工具执行"""
        start = time.time()
        try:
            result = self.run(parameters)
        except Exception as e:
            result = ToolResponse.error(
                code=ToolErrorCode.EXECUTION_ERROR,
                message=str(e)
            )
        elapsed_ms = int((time.time() - start) * 1000)
        result.stats["time_ms"] = elapsed_ms
        return result

    def to_openai_schema(self) -> dict:
        """转为 OpenAI Function Calling 格式"""
        params = self.get_parameters()
        properties = {}
        required = []

        for p in params:
            prop = {"type": p.type, "description": p.description}
            if p.enum:
                prop["enum"] = p.enum
            properties[p.name] = prop
            if p.required:
                required.append(p.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                }
            }
        }
