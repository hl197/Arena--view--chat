# Tool 系统设计参考

## ToolRegistry 完整实现

```python
import re
from typing import Any, Callable

class ToolRegistry:
    """工具注册表 —— Agent 所有工具的统一入口"""

    def __init__(self):
        self._tools: dict[str, Any] = {}
        self._functions: dict[str, dict] = {}
        self._call_history: list[dict] = []

    # —— 注册 ——

    def register_tool(self, tool):
        """注册工具实例（Tool 子类）"""
        name = getattr(tool, 'name', tool.__class__.__name__)
        if name in self._tools:
            raise ValueError(f"工具 '{name}' 已注册，请先 unregister")
        self._tools[name] = tool

    def register_function(self, name: str, description: str, func: Callable):
        """注册普通函数为工具——适合快速包装已有函数"""
        self._functions[name] = {
            "name": name,
            "description": description,
            "func": func
        }

    def unregister(self, name: str):
        """移除工具"""
        self._tools.pop(name, None)
        self._functions.pop(name, None)

    # —— 执行 ——

    def execute_tool(self, name: str, input_data: str | dict) -> str:
        """统一的工具执行入口"""
        start_time = time.time()

        # 解析参数
        if isinstance(input_data, str):
            params = self._parse_params(input_data)
        else:
            params = input_data

        # 查找并执行
        result = None
        if name in self._tools:
            result = self._tools[name].run(params)
        elif name in self._functions:
            result = self._functions[name]["func"](**params)
        else:
            result = self._suggest_similar(name)

        # 记录调用历史
        self._call_history.append({
            "name": name, "params": params,
            "duration_ms": (time.time() - start_time) * 1000,
            "success": result is not None and "错误" not in str(result)[:50]
        })

        return str(result) if result is not None else f"工具 '{name}' 执行出错"

    # —— 描述生成 ——

    def get_tools_description(self) -> str:
        """生成给 LLM 看的工具列表——影响工具调用的准确性"""
        lines = []
        for name, tool in self._tools.items():
            desc = getattr(tool, 'description', '无描述')
            lines.append(f"- {name}: {desc}")
        for name, fn in self._functions.items():
            lines.append(f"- {name}: {fn['description']}")
        return "\n".join(lines)

    def get_tools_schema(self) -> list[dict]:
        """生成 OpenAI Function Calling 格式的工具描述"""
        schemas = []
        for name, tool in self._tools.items():
            if hasattr(tool, 'get_schema'):
                schemas.append(tool.get_schema())
        return schemas

    # —— 查询 ——

    def list_tools(self) -> list[str]:
        return list(self._tools.keys()) + list(self._functions.keys())

    def get_tool(self, name: str):
        return self._tools.get(name) or self._functions.get(name)

    def _suggest_similar(self, name: str) -> str:
        """当工具名不存在时，建议最相似的工具"""
        all_names = self.list_tools()
        if not all_names:
            return f"工具 '{name}' 不存在，且无任何已注册工具"

        # 简单的相似度匹配
        from difflib import get_close_matches
        suggestions = get_close_matches(name, all_names, n=3, cutoff=0.4)
        if suggestions:
            return f"工具 '{name}' 不存在。您是否想用: {', '.join(suggestions)}?"
        return f"工具 '{name}' 不存在。可用工具: {', '.join(all_names)}"

    # —— 参数解析 ——

    def _parse_params(self, raw: str) -> dict:
        """解析工具参数——支持多种输入格式

        格式1: key=value, key2=value2
        格式2: key=value,key2=value2
        格式3: 纯文本（作为 'query' 参数）
        """
        params = {}
        if "=" in raw:
            for part in raw.split(","):
                part = part.strip()
                if "=" in part:
                    key, value = part.split("=", 1)
                    params[key.strip()] = value.strip()
        else:
            # 纯文本 → 默认作为 query 参数
            params["query"] = raw.strip()
        return params

    # —— 历史与统计 ——

    def get_call_stats(self) -> dict:
        """工具调用统计——帮助优化工具设计"""
        stats = {}
        for call in self._call_history:
            name = call["name"]
            if name not in stats:
                stats[name] = {"count": 0, "success": 0, "total_duration_ms": 0}
            stats[name]["count"] += 1
            stats[name]["success"] += 1 if call["success"] else 0
            stats[name]["total_duration_ms"] += call["duration_ms"]
        return stats
```

## Action 分发模式

```python
class SearchTool(Tool):
    """多 Action 工具——通过 action 字段分发到不同操作"""

    name = "search"
    description = (
        "通用搜索工具。action=web 网络搜索, "
        "action=code 代码搜索, action=doc 文档搜索"
    )

    def run(self, params: dict) -> str:
        action = params.get("action", "web")
        query = params.get("query", "")
        limit = int(params.get("limit", 5))

        dispatcher = {
            "web": self._web_search,
            "code": self._code_search,
            "doc": self._doc_search,
        }

        handler = dispatcher.get(action)
        if handler:
            return handler(query, limit)
        return f"不支持的操作: {action}，可用: {list(dispatcher.keys())}"

    def _web_search(self, query: str, limit: int) -> str: ...
    def _code_search(self, query: str, limit: int) -> str: ...
    def _doc_search(self, query: str, limit: int) -> str: ...
```

## 工具名称与描述规范

```python
# ❌ 不好的工具描述
BAD_EXAMPLES = [
    ("search", "搜索东西"),
    ("calc", "做计算"),
    ("tool1", "工具1"),
]

# ✅ 好的工具描述
GOOD_EXAMPLES = [
    ("web_search", "在互联网上搜索指定关键词，返回标题、摘要和链接列表"),
    ("calculator", "安全计算数学表达式，支持四则运算、幂运算、三角函数"),
    ("memory_search", "在 Agent 记忆中检索相关的历史对话和知识"),
]

# 描述编写规则
DESCRIPTION_RULES = """
1. 说明工具功能（做什么）
2. 说明何时使用（触发条件）
3. 说明参数格式（怎么传参）
4. 说明返回值格式（拿到什么）
5. 控制在 50-150 字（太长 LLM 记不住，太短信息不足）
"""
```
