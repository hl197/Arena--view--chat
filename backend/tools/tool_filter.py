"""工具过滤器

用于子 Agent 和权限控制场景。
"""


class ToolFilter:
    """工具过滤器基类"""

    def filter(self, tool_names: list[str]) -> list[str]:
        """返回允许的工具名称列表"""
        raise NotImplementedError


class ReadOnlyFilter(ToolFilter):
    """只读工具过滤器——仅允许搜索/读取类工具"""
    READONLY_TOOLS = {"web_search", "news_search", "calculator"}

    def filter(self, tool_names: list[str]) -> list[str]:
        return [t for t in tool_names if t in self.READONLY_TOOLS]


class FullAccessFilter(ToolFilter):
    """全权限——排除敏感工具"""
    BLOCKED_TOOLS = {"email_send", "db_write", "file_delete"}

    def filter(self, tool_names: list[str]) -> list[str]:
        return [t for t in tool_names if t not in self.BLOCKED_TOOLS]


class CustomFilter(ToolFilter):
    """自定义过滤器"""

    def __init__(self, allow: list[str] = None, block: list[str] = None):
        self._allow = set(allow or [])
        self._block = set(block or [])

    def filter(self, tool_names: list[str]) -> list[str]:
        if self._allow:
            return [t for t in tool_names if t in self._allow]
        return [t for t in tool_names if t not in self._block]
