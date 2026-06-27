"""工具错误码

参考 HelloAgents 的 ToolErrorCode 设计，定义 15 种标准错误码。
"""

from enum import Enum


class ToolErrorCode(str, Enum):
    """工具执行错误码"""
    # 参数错误
    INVALID_PARAM = "INVALID_PARAM"           # 参数格式/类型错误
    MISSING_PARAM = "MISSING_PARAM"           # 缺少必需参数

    # 资源错误
    NOT_FOUND = "NOT_FOUND"                   # 目标资源不存在
    PERMISSION_DENIED = "PERMISSION_DENIED"   # 权限不足

    # 执行错误
    EXECUTION_ERROR = "EXECUTION_ERROR"       # 工具执行失败
    TIMEOUT = "TIMEOUT"                       # 工具执行超时
    RATE_LIMITED = "RATE_LIMITED"             # API 速率限制

    # 外部服务错误
    EXTERNAL_API_ERROR = "EXTERNAL_API_ERROR"  # 外部 API 返回错误
    NETWORK_ERROR = "NETWORK_ERROR"            # 网络不可达

    # 系统错误
    TOOL_NOT_REGISTERED = "TOOL_NOT_REGISTERED"  # 工具未注册
    CIRCUIT_OPEN = "CIRCUIT_OPEN"                # 熔断器开启
    INTERNAL_ERROR = "INTERNAL_ERROR"            # 内部未知错误

    # 内容错误
    CONTENT_TOO_LARGE = "CONTENT_TOO_LARGE"    # 输入/输出超过限制
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"  # 不支持的内容格式

    # 安全错误
    UNSAFE_CONTENT = "UNSAFE_CONTENT"          # 检测到不安全内容
