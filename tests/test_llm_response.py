"""LLM 响应数据结构测试"""

import pytest
from backend.adapters.llm_response import (
    LLMResponse,
    LLMToolResponse,
    ToolCall,
    StreamStats,
)


class TestLLMResponse:
    """非流式调用响应测试"""

    def test_create_basic(self):
        r = LLMResponse(content="你好")
        assert r.content == "你好"
        assert r.model == ""
        assert r.usage == {}
        assert r.latency_ms == 0

    def test_create_full(self):
        r = LLMResponse(
            content="回答内容",
            model="gemini-2.0-flash",
            usage={"total_tokens": 150, "prompt_tokens": 50, "completion_tokens": 100},
            latency_ms=320,
        )
        assert r.model == "gemini-2.0-flash"
        assert r.usage["total_tokens"] == 150
        assert r.latency_ms == 320

    def test_reasoning_content(self):
        """thinking model 推理过程支持"""
        r = LLMResponse(content="答案", reasoning_content="让我想想...")
        assert r.reasoning_content == "让我想想..."

    def test_default_reasoning_none(self):
        r = LLMResponse(content="test")
        assert r.reasoning_content is None


class TestLLMToolResponse:
    """Function Calling 响应测试"""

    def test_create_empty(self):
        r = LLMToolResponse()
        assert r.content is None
        assert r.tool_calls == []

    def test_create_with_tool_calls(self):
        tc1 = ToolCall(id="call_1", name="web_search", arguments='{"query":"房价"}')
        tc2 = ToolCall(id="call_2", name="finish", arguments='{"answer":"结论"}')
        r = LLMToolResponse(
            content=None,
            tool_calls=[tc1, tc2],
            model="deepseek-chat",
            usage={"total_tokens": 300},
            latency_ms=500,
        )
        assert len(r.tool_calls) == 2
        assert r.tool_calls[0].name == "web_search"
        assert r.model == "deepseek-chat"
        assert r.latency_ms == 500


class TestToolCall:
    """工具调用数据类测试"""

    def test_create(self):
        tc = ToolCall(id="call_abc123", name="web_search", arguments='{"query":"test"}')
        assert tc.id == "call_abc123"
        assert tc.name == "web_search"
        assert tc.arguments == '{"query":"test"}'

    def test_empty_args(self):
        tc = ToolCall(id="call_x", name="finish", arguments="{}")
        assert tc.arguments == "{}"


class TestStreamStats:
    """流式调用统计测试"""

    def test_defaults(self):
        s = StreamStats()
        assert s.model == ""
        assert s.usage == {}
        assert s.latency_ms == 0

    def test_with_reasoning(self):
        s = StreamStats(reasoning_content="推理中...")
        assert s.reasoning_content == "推理中..."
