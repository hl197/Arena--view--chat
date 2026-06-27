"""ArenaView 异常体系测试"""

import pytest
from backend.core.exceptions import (
    ArenaException,
    LLMException,
    AdapterException,
    RateLimitException,
    AgentException,
    AgentTimeoutException,
    AgentLoopException,
    ToolException,
    CircuitOpenException,
    ConfigException,
    QuotaExceededException,
    DebateException,
)


class TestExceptionHierarchy:
    """异常层次结构测试"""

    def test_arena_exception_base(self):
        """所有异常都是 ArenaException 的子类"""
        assert issubclass(LLMException, ArenaException)
        assert issubclass(AgentException, ArenaException)
        assert issubclass(ToolException, ArenaException)
        assert issubclass(ConfigException, ArenaException)
        assert issubclass(DebateException, ArenaException)
        assert issubclass(QuotaExceededException, ArenaException)

    def test_adapter_exception_chain(self):
        """适配器异常继承链"""
        assert issubclass(AdapterException, LLMException)
        assert issubclass(AdapterException, ArenaException)

    def test_rate_limit_chain(self):
        """速率限制异常继承链"""
        assert issubclass(RateLimitException, LLMException)

    def test_agent_exception_chain(self):
        """Agent 异常继承链"""
        assert issubclass(AgentTimeoutException, AgentException)
        assert issubclass(AgentLoopException, AgentException)

    def test_tool_exception_chain(self):
        """工具异常继承链"""
        assert issubclass(CircuitOpenException, ToolException)

    def test_is_exception(self):
        """所有异常都是 Exception 的子类"""
        assert issubclass(ArenaException, Exception)


class TestExceptionMessages:
    """异常消息测试"""

    def test_arena_exception_message(self):
        e = ArenaException("基础异常")
        assert str(e) == "基础异常"

    def test_llm_exception_message(self):
        e = LLMException("LLM 调用失败")
        assert str(e) == "LLM 调用失败"

    def test_adapter_exception_message(self):
        e = AdapterException("Gemini 适配器错误")
        assert str(e) == "Gemini 适配器错误"

    def test_agent_timeout_message(self):
        e = AgentTimeoutException("Agent 执行超时")
        assert str(e) == "Agent 执行超时"

    def test_debate_exception_message(self):
        e = DebateException("辩论流程错误")
        assert str(e) == "辩论流程错误"

    def test_quota_exceeded_message(self):
        e = QuotaExceededException("今日辩论次数已达上限")
        assert str(e) == "今日辩论次数已达上限"

    def test_can_catch_by_base_class(self):
        """可以用基类捕获子类异常"""
        try:
            raise AgentTimeoutException("超时")
        except AgentException as e:
            assert isinstance(e, AgentTimeoutException)
        except Exception:
            pytest.fail("应该被 AgentException 捕获")

    def test_can_catch_by_arena_exception(self):
        """任何 ArenaView 异常都可以被 ArenaException 捕获"""
        try:
            raise QuotaExceededException("额度不足")
        except ArenaException:
            pass
        except Exception:
            pytest.fail("应该被 ArenaException 捕获")
