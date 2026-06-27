"""ToolRegistry 工具注册表测试（含 FinishTool）"""

import pytest
from backend.tools.registry import ToolRegistry
from backend.tools.base import Tool, ToolParameter
from backend.tools.response import ToolResponse, ToolStatus
from backend.tools.errors import ToolErrorCode
from backend.tools.builtin.finish_tool import FinishTool


# === 测试用工具 ===
class MockSearchTool(Tool):
    def __init__(self):
        super().__init__(name="mock_search", description="模拟搜索")
    def get_parameters(self) -> list[ToolParameter]:
        return [ToolParameter(name="query", type="string", description="搜索词")]
    def run(self, parameters: dict) -> ToolResponse:
        return ToolResponse.success(text=f"搜索 '{parameters.get('query', '')}' 完成")


class MockFailingTool(Tool):
    def __init__(self):
        super().__init__(name="mock_bad", description="会失败")
    def get_parameters(self) -> list[ToolParameter]:
        return [ToolParameter(name="input", type="string", description="输入")]
    def run(self, parameters: dict) -> ToolResponse:
        return ToolResponse.error(code=ToolErrorCode.EXECUTION_ERROR, message="模拟失败")


class TestToolRegistryBasic:
    """基本注册/注销/查找测试"""

    def test_register_tool(self):
        reg = ToolRegistry(circuit_enabled=False)
        reg.register_tool(MockSearchTool())
        assert "mock_search" in reg.list_tools()

    def test_register_duplicate_raises(self):
        reg = ToolRegistry(circuit_enabled=False)
        reg.register_tool(MockSearchTool())
        with pytest.raises(ValueError, match="已注册"):
            reg.register_tool(MockSearchTool())

    def test_unregister_tool(self):
        reg = ToolRegistry(circuit_enabled=False)
        reg.register_tool(MockSearchTool())
        reg.unregister_tool("mock_search")
        assert "mock_search" not in reg.list_tools()

    def test_get_tool(self):
        reg = ToolRegistry(circuit_enabled=False)
        tool = MockSearchTool()
        reg.register_tool(tool)
        assert reg.get_tool("mock_search") is tool

    def test_get_tool_not_found(self):
        reg = ToolRegistry(circuit_enabled=False)
        assert reg.get_tool("nonexistent") is None

    def test_list_tools_empty(self):
        reg = ToolRegistry(circuit_enabled=False)
        assert reg.list_tools() == []


class TestToolRegistryExecution:
    """工具执行测试"""

    def test_execute_success(self):
        reg = ToolRegistry(circuit_enabled=False)
        reg.register_tool(MockSearchTool())
        result = reg.execute_tool("mock_search", '{"query":"房价走势"}')
        assert result.status == ToolStatus.SUCCESS
        assert "房价走势" in result.text

    def test_execute_not_found(self):
        reg = ToolRegistry(circuit_enabled=False)
        result = reg.execute_tool("nonexistent", "{}")
        assert result.status == ToolStatus.ERROR
        assert result.error_code == ToolErrorCode.TOOL_NOT_REGISTERED

    def test_execute_plain_text_input(self):
        """非 JSON 输入 → 当作 query 参数"""
        reg = ToolRegistry(circuit_enabled=False)
        reg.register_tool(MockSearchTool())
        result = reg.execute_tool("mock_search", "直接搜索文本")
        assert result.status == ToolStatus.SUCCESS

    def test_execute_error_tool(self):
        reg = ToolRegistry(circuit_enabled=False)
        reg.register_tool(MockFailingTool())
        result = reg.execute_tool("mock_bad", '{"input":"test"}')
        assert result.status == ToolStatus.ERROR
        assert result.error_code == ToolErrorCode.EXECUTION_ERROR

    def test_execute_with_circuit(self):
        """集成熔断器的工具执行"""
        reg = ToolRegistry(circuit_enabled=True)
        reg.register_tool(MockFailingTool())

        # 连续失败直到熔断
        for _ in range(4):
            result = reg.execute_tool("mock_bad", '{"input":"test"}')

        # 最终应该是熔断状态
        # 注意：第4次可能熔断
        circuit_status = reg.get_circuit_status()
        assert "mock_bad" in circuit_status


class TestToolRegistryStats:
    """调用统计测试"""

    def test_call_stats_empty(self):
        reg = ToolRegistry(circuit_enabled=False)
        assert reg.get_call_stats() == {}

    def test_call_stats_accumulate(self):
        reg = ToolRegistry(circuit_enabled=False)
        reg.register_tool(MockSearchTool())
        reg.execute_tool("mock_search", '{"query":"test1"}')
        reg.execute_tool("mock_search", '{"query":"test2"}')

        stats = reg.get_call_stats()
        assert "mock_search" in stats
        assert stats["mock_search"]["count"] == 2

    def test_call_stats_tracks_success(self):
        reg = ToolRegistry(circuit_enabled=False)
        reg.register_tool(MockSearchTool())
        reg.execute_tool("mock_search", '{"query":"test"}')

        stats = reg.get_call_stats()
        assert stats["mock_search"]["success"] == 1


class TestToolRegistryDescription:
    """工具描述生成测试"""

    def test_empty_registry(self):
        reg = ToolRegistry(circuit_enabled=False)
        assert reg.get_tools_description() == "无可用工具"

    def test_with_tools(self):
        reg = ToolRegistry(circuit_enabled=False)
        reg.register_tool(MockSearchTool())
        desc = reg.get_tools_description()
        assert "mock_search" in desc
        assert "模拟搜索" in desc

    def test_openai_schema_format(self):
        reg = ToolRegistry(circuit_enabled=False)
        reg.register_tool(MockSearchTool())
        schemas = reg.get_openai_tools()
        assert len(schemas) == 1
        assert schemas[0]["type"] == "function"
        assert schemas[0]["function"]["name"] == "mock_search"


class TestFinishTool:
    """Finish 工具测试"""

    def test_finish_tool(self):
        tool = FinishTool()
        assert tool.name == "finish"
        result = tool.run({"answer": "这是最终论证"})
        assert result.status == ToolStatus.SUCCESS
        assert result.text == "这是最终论证"
        assert result.data == {"terminated": True}

    def test_finish_tool_schema(self):
        tool = FinishTool()
        schema = tool.to_openai_schema()
        assert schema["function"]["name"] == "finish"
        assert "answer" in schema["function"]["parameters"]["properties"]

    def test_finish_in_registry(self):
        reg = ToolRegistry(circuit_enabled=False)
        reg.register_tool(FinishTool())
        result = reg.execute_tool("finish", '{"answer":"论证完整"}')
        assert result.status == ToolStatus.SUCCESS
        assert result.text == "论证完整"
