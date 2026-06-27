"""ToolResponse 三态协议测试"""

import pytest
from backend.tools.response import ToolResponse, ToolStatus
from backend.tools.errors import ToolErrorCode


class TestToolResponseSuccess:
    """SUCCESS 状态测试"""

    def test_success_factory(self):
        r = ToolResponse.success(text="搜索完成", data={"results": 5})
        assert r.status == ToolStatus.SUCCESS
        assert r.text == "搜索完成"
        assert r.data == {"results": 5}
        assert r.error_code is None
        assert r.error_message == ""

    def test_success_defaults(self):
        r = ToolResponse.success()
        assert r.text == ""
        assert r.data is None
        assert r.stats == {}

    def test_success_is_success(self):
        r = ToolResponse.success("ok")
        assert r.is_success is True
        assert r.is_error is False

    def test_success_to_agent_view(self):
        r = ToolResponse.success(text="找到 3 条结果")
        assert r.to_agent_view() == "找到 3 条结果"

    def test_success_with_stats(self):
        r = ToolResponse.success(text="done", stats={"time_ms": 42})
        assert r.stats["time_ms"] == 42


class TestToolResponsePartial:
    """PARTIAL 状态测试"""

    def test_partial_factory(self):
        r = ToolResponse.partial(
            text="部分结果",
            data={"found": 3, "total": 10},
            warning="搜索结果不完整"
        )
        assert r.status == ToolStatus.PARTIAL
        assert r.text == "部分结果"
        assert r.error_message == "搜索结果不完整"

    def test_partial_is_success(self):
        r = ToolResponse.partial("partial")
        assert r.is_success is False
        assert r.is_error is False

    def test_partial_to_agent_view(self):
        r = ToolResponse.partial(text="部分数据", warning="超时截断")
        view = r.to_agent_view()
        assert "⚠️ 部分成功" in view
        assert "超时截断" in view
        assert "部分数据" in view


class TestToolResponseError:
    """ERROR 状态测试"""

    def test_error_factory(self):
        r = ToolResponse.error(
            code=ToolErrorCode.NETWORK_ERROR,
            message="连接超时",
            text="请稍后重试"
        )
        assert r.status == ToolStatus.ERROR
        assert r.error_code == ToolErrorCode.NETWORK_ERROR
        assert r.error_message == "连接超时"
        assert r.text == "请稍后重试"

    def test_error_is_error(self):
        r = ToolResponse.error(code=ToolErrorCode.TIMEOUT, message="超时")
        assert r.is_error is True
        assert r.is_success is False

    def test_error_to_agent_view(self):
        r = ToolResponse.error(
            code=ToolErrorCode.CIRCUIT_OPEN,
            message="工具已熔断",
            text="debug info"
        )
        view = r.to_agent_view()
        assert "❌ 错误" in view
        assert "CIRCUIT_OPEN" in view
        assert "工具已熔断" in view

    def test_error_defaults(self):
        r = ToolResponse.error(code=ToolErrorCode.INTERNAL_ERROR)
        assert r.text == ""
        assert r.error_message == ""
