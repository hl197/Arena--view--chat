"""ToolFilter 工具过滤器测试"""

import pytest
from backend.tools.tool_filter import (
    ToolFilter,
    ReadOnlyFilter,
    FullAccessFilter,
    CustomFilter,
)


class TestReadOnlyFilter:
    """只读过滤器测试"""

    def test_allows_readonly_tools(self):
        f = ReadOnlyFilter()
        result = f.filter(["web_search", "news_search", "calculator"])
        assert result == ["web_search", "news_search", "calculator"]

    def test_blocks_write_tools(self):
        f = ReadOnlyFilter()
        result = f.filter(["db_write", "email_send", "file_delete"])
        assert result == []

    def test_mixed_tools(self):
        f = ReadOnlyFilter()
        result = f.filter(["web_search", "db_write", "calculator", "email_send"])
        assert "web_search" in result
        assert "calculator" in result
        assert "db_write" not in result
        assert "email_send" not in result

    def test_unknown_tools_blocked(self):
        """不在白名单中的工具被过滤"""
        f = ReadOnlyFilter()
        result = f.filter(["unknown_tool"])
        assert result == []

    def test_empty_input(self):
        f = ReadOnlyFilter()
        assert f.filter([]) == []


class TestFullAccessFilter:
    """全权限过滤器测试"""

    def test_allows_normal_tools(self):
        f = FullAccessFilter()
        result = f.filter(["web_search", "calculator", "custom_tool"])
        assert result == ["web_search", "calculator", "custom_tool"]

    def test_blocks_sensitive_tools(self):
        f = FullAccessFilter()
        result = f.filter(["email_send", "db_write", "file_delete"])
        assert result == []

    def test_mixed_tools(self):
        f = FullAccessFilter()
        result = f.filter(["web_search", "db_write", "custom_tool", "email_send"])
        assert "web_search" in result
        assert "custom_tool" in result
        assert "db_write" not in result
        assert "email_send" not in result

    def test_empty_input(self):
        f = FullAccessFilter()
        assert f.filter([]) == []


class TestCustomFilter:
    """自定义过滤器测试"""

    def test_allow_only(self):
        f = CustomFilter(allow=["tool_a", "tool_b"])
        result = f.filter(["tool_a", "tool_b", "tool_c"])
        assert result == ["tool_a", "tool_b"]

    def test_block_list(self):
        f = CustomFilter(block=["dangerous_tool"])
        result = f.filter(["safe_tool", "dangerous_tool", "neutral"])
        assert "dangerous_tool" not in result
        assert "safe_tool" in result
        assert "neutral" in result

    def test_allow_takes_priority(self):
        """allow 优先级高于 block"""
        f = CustomFilter(allow=["a"], block=["a"])
        result = f.filter(["a", "b"])
        assert result == ["a"]  # allow 生效

    def test_empty_input(self):
        f = CustomFilter(allow=["a"])
        assert f.filter([]) == []

    def test_default_empty(self):
        f = CustomFilter()
        result = f.filter(["any_tool"])
        assert result == ["any_tool"]  # 无限制
