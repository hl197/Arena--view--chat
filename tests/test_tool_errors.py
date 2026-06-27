"""ToolErrorCode 枚举测试"""

import pytest
from backend.tools.errors import ToolErrorCode


class TestToolErrorCode:
    """错误码枚举完整性测试"""

    def test_all_codes_defined(self):
        """15 个标准错误码全部定义"""
        codes = set(e.value for e in ToolErrorCode)

        # 参数错误
        assert "INVALID_PARAM" in codes
        assert "MISSING_PARAM" in codes

        # 资源错误
        assert "NOT_FOUND" in codes
        assert "PERMISSION_DENIED" in codes

        # 执行错误
        assert "EXECUTION_ERROR" in codes
        assert "TIMEOUT" in codes
        assert "RATE_LIMITED" in codes

        # 外部服务错误
        assert "EXTERNAL_API_ERROR" in codes
        assert "NETWORK_ERROR" in codes

        # 系统错误
        assert "TOOL_NOT_REGISTERED" in codes
        assert "CIRCUIT_OPEN" in codes
        assert "INTERNAL_ERROR" in codes

        # 内容错误
        assert "CONTENT_TOO_LARGE" in codes
        assert "UNSUPPORTED_FORMAT" in codes

        # 安全错误
        assert "UNSAFE_CONTENT" in codes

    def test_total_count(self):
        """确认有 15 个错误码"""
        assert len(list(ToolErrorCode)) == 15

    def test_is_string_enum(self):
        """确认是字符串枚举"""
        assert isinstance(ToolErrorCode.NETWORK_ERROR.value, str)
        assert ToolErrorCode.TIMEOUT.value == "TIMEOUT"

    def test_equality(self):
        """确认枚举值比较"""
        assert ToolErrorCode.INVALID_PARAM == ToolErrorCode("INVALID_PARAM")
        assert ToolErrorCode.NOT_FOUND != ToolErrorCode.TIMEOUT
