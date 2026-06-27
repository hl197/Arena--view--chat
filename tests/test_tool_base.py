"""Tool 抽象基类和 ToolParameter 测试"""

import pytest
from backend.tools.base import Tool, ToolParameter
from backend.tools.response import ToolResponse, ToolStatus
from backend.tools.errors import ToolErrorCode


# === 测试用的具体工具 ===
class EchoTool(Tool):
    """简单回显工具"""
    def __init__(self):
        super().__init__(name="echo", description="回显输入")
    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="text", type="string", description="要回显的文本"),
            ToolParameter(name="times", type="integer", description="重复次数", required=False, default=1),
        ]
    def run(self, parameters: dict) -> ToolResponse:
        return ToolResponse.success(text=parameters.get("text", ""))


class FailingTool(Tool):
    """会抛出异常的工具"""
    def __init__(self):
        super().__init__(name="failer", description="always fails")
    def run(self, parameters: dict) -> ToolResponse:
        raise RuntimeError("此工具总是失败")


class TestToolParameter:
    """工具参数数据类测试"""

    def test_required_param(self):
        p = ToolParameter(name="query", type="string", description="搜索查询")
        assert p.name == "query"
        assert p.type == "string"
        assert p.required is True
        assert p.default is None
        assert p.enum == []

    def test_optional_param(self):
        p = ToolParameter(name="limit", type="integer", description="限制条数",
                          required=False, default=10)
        assert p.required is False
        assert p.default == 10

    def test_enum_param(self):
        p = ToolParameter(name="sort", type="string", description="排序方式",
                          enum=["asc", "desc"])
        assert p.enum == ["asc", "desc"]


class TestToolBase:
    """Tool 基类测试"""

    def test_basic_attributes(self):
        tool = EchoTool()
        assert tool.name == "echo"
        assert tool.description == "回显输入"

    def test_get_parameters(self):
        tool = EchoTool()
        params = tool.get_parameters()
        assert len(params) == 2
        assert params[0].name == "text"
        assert params[1].name == "times"

    def test_run_returns_response(self):
        tool = EchoTool()
        result = tool.run({"text": "hello"})
        assert result.text == "hello"
        assert result.status == ToolStatus.SUCCESS

    def test_run_with_timing_adds_stats(self):
        tool = EchoTool()
        result = tool.run_with_timing({"text": "hello"})
        assert "time_ms" in result.stats
        assert isinstance(result.stats["time_ms"], int)
        assert result.stats["time_ms"] >= 0

    def test_run_with_timing_catches_exceptions(self):
        """run_with_timing 捕获异常并返回 ERROR 响应"""
        tool = FailingTool()
        result = tool.run_with_timing({})
        assert result.status == ToolStatus.ERROR
        assert result.error_code == ToolErrorCode.EXECUTION_ERROR
        assert "此工具总是失败" in result.error_message

    def test_arun_default_impl(self):
        """默认异步实现等同于同步"""
        import asyncio
        tool = EchoTool()
        result = asyncio.run(tool.arun({"text": "async"}))
        assert result.text == "async"


class TestToolOpenAISchema:
    """to_openai_schema() 测试"""

    def test_basic_schema(self):
        tool = EchoTool()
        schema = tool.to_openai_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "echo"
        assert schema["function"]["description"] == "回显输入"

    def test_schema_parameters(self):
        tool = EchoTool()
        schema = tool.to_openai_schema()
        params = schema["function"]["parameters"]
        assert params["type"] == "object"
        assert "text" in params["properties"]
        assert "times" in params["properties"]
        assert params["properties"]["text"]["type"] == "string"
        assert params["properties"]["times"]["type"] == "integer"

    def test_schema_required(self):
        tool = EchoTool()
        schema = tool.to_openai_schema()
        required = schema["function"]["parameters"]["required"]
        assert "text" in required  # required=True
        assert "times" not in required  # required=False

    def test_schema_no_params(self):
        """无参数工具"""
        class NoParamTool(Tool):
            def __init__(self):
                super().__init__(name="noop", description="no operation")
            def run(self, parameters: dict) -> ToolResponse:
                return ToolResponse.success("ok")

        tool = NoParamTool()
        schema = tool.to_openai_schema()
        assert schema["function"]["parameters"]["properties"] == {}
        assert schema["function"]["parameters"]["required"] == []

    def test_schema_enum(self):
        """带枚举的工具"""
        class SortTool(Tool):
            def __init__(self):
                super().__init__(name="sort", description="sort data")
            def get_parameters(self) -> list[ToolParameter]:
                return [ToolParameter(name="order", type="string", description="方向", enum=["asc", "desc"])]
            def run(self, p): return ToolResponse.success("sorted")

        tool = SortTool()
        schema = tool.to_openai_schema()
        assert schema["function"]["parameters"]["properties"]["order"]["enum"] == ["asc", "desc"]
