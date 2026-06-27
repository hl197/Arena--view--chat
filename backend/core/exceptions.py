"""ArenaView 异常体系"""


class ArenaException(Exception):
    """ArenaView 基础异常"""
    pass


class LLMException(ArenaException):
    """LLM 调用相关异常"""
    pass


class AdapterException(LLMException):
    """适配器异常（Provider 特有错误）"""
    pass


class RateLimitException(LLMException):
    """速率限制异常"""
    pass


class AgentException(ArenaException):
    """Agent 执行相关异常"""
    pass


class AgentTimeoutException(AgentException):
    """Agent 执行超时"""
    pass


class AgentLoopException(AgentException):
    """Agent 陷入循环"""
    pass


class ToolException(ArenaException):
    """工具执行相关异常"""
    pass


class CircuitOpenException(ToolException):
    """熔断器开启——工具暂时不可用"""
    pass


class ConfigException(ArenaException):
    """配置相关异常"""
    pass


class QuotaExceededException(ArenaException):
    """额度耗尽异常"""
    pass


class DebateException(ArenaException):
    """辩论流程异常"""
    pass
