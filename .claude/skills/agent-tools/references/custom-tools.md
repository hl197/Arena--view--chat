# 自定义工具开发参考

## 1. 计算器工具（AST 安全求值）

```python
import ast
import operator
import math

class CalculatorTool:
    """安全的数学计算器——使用 AST 白名单，不执行任意代码"""
    name = "calculator"
    description = "安全地计算数学表达式。支持 +-*/、**、sqrt、sin、cos、pi、abs"

    # AST 节点 → Python 操作符 白名单映射
    ALLOWED_OPS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    ALLOWED_FUNCS = {
        'sqrt': math.sqrt, 'pow': math.pow,
        'sin': math.sin, 'cos': math.cos, 'tan': math.tan,
        'log': math.log, 'log10': math.log10, 'log2': math.log2,
        'exp': math.exp, 'abs': abs, 'round': round,
        'pi': math.pi, 'e': math.e,
    }

    def run(self, params: dict) -> str:
        expression = params.get("expression") or params.get("query", "")
        if not expression:
            return "错误: 请提供要计算的表达式"

        try:
            result = self._safe_eval(expression)
            return f"{expression} = {result}"
        except ZeroDivisionError:
            return "错误: 除数不能为零"
        except (SyntaxError, ValueError, TypeError) as e:
            return f"表达式错误: {e}"

    def _safe_eval(self, expr: str) -> float:
        tree = ast.parse(expr.strip(), mode='eval')
        return self._eval_node(tree.body)

    def _eval_node(self, node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.BinOp):
            op = self.ALLOWED_OPS.get(type(node.op))
            if not op:
                raise ValueError(f"不支持的操作符: {type(node.op).__name__}")
            return op(self._eval_node(node.left), self._eval_node(node.right))
        if isinstance(node, ast.UnaryOp):
            op = self.ALLOWED_OPS.get(type(node.op))
            if not op:
                raise ValueError(f"不支持的一元操作符")
            return op(self._eval_node(node.operand))
        if isinstance(node, ast.Call):
            if node.func.id not in self.ALLOWED_FUNCS:
                raise ValueError(f"不支持的函数: {node.func.id}")
            args = [self._eval_node(a) for a in node.args]
            return self.ALLOWED_FUNCS[node.func.id](*args)
        raise ValueError(f"不支持的表达式类型: {type(node).__name__}")
```

## 2. 搜索工具（多源 Fallback）

```python
import os
import requests
from typing import Optional

class RobustSearchTool:
    """多搜索引擎 + 自动 Fallback"""
    name = "web_search"
    description = "搜索互联网信息。当需要查找最新资料、事实核查、技术文档时使用。"

    def __init__(self):
        self.sources = []  # [(name, search_fn, priority)]
        self._init_sources()

    def _init_sources(self):
        """自动检测可用的搜索 API，按优先级排列"""
        if os.getenv("TAVILY_API_KEY"):
            self.sources.append(("tavily", self._search_tavily, 1))
        if os.getenv("SERPAPI_API_KEY"):
            self.sources.append(("serpapi", self._search_serpapi, 2))
        if os.getenv("BRAVE_API_KEY"):
            self.sources.append(("brave", self._search_brave, 3))
        if os.getenv("GOOGLE_API_KEY") and os.getenv("GOOGLE_CSE_ID"):
            self.sources.append(("google", self._search_google, 4))
        if not self.sources:
            print("⚠️ 无搜索 API 可用，使用内置搜索")
            self.sources.append(("builtin", self._search_builtin, 99))

        self.sources.sort(key=lambda x: x[2])  # 按优先级排序

    def run(self, params: dict) -> str:
        query = params.get("query", "")
        limit = int(params.get("limit", 5))

        if not query:
            return "错误: 请提供搜索关键词"

        errors = []
        for source_name, search_fn, _ in self.sources:
            try:
                results = search_fn(query, limit)
                if results:
                    return self._format_results(results, source_name)
            except Exception as e:
                errors.append(f"{source_name}: {e}")
                continue

        return f"搜索失败。各引擎错误:\n" + "\n".join(errors)

    def _format_results(self, results: list, source: str) -> str:
        lines = [f"🔍 搜索结果 (via {source}):"]
        for i, r in enumerate(results, 1):
            lines.append(
                f"{i}. **{r.get('title', '无标题')}**\n"
                f"   {r.get('snippet', r.get('content', ''))[:200]}\n"
                f"   📎 {r.get('url', r.get('link', ''))}"
            )
        return "\n\n".join(lines)

    def _search_builtin(self, query: str, limit: int) -> list:
        """内置搜索——用于没有外部 API 时的降级方案"""
        # 这里可以接本地搜索索引或简单的规则匹配
        return [{"title": "无搜索结果", "snippet": "请配置搜索 API Key", "url": ""}]
```

## 3. 文件系统工具

```python
import os
import json
from pathlib import Path

class FileSystemTool:
    """安全的文件系统操作——限制在指定工作目录内"""
    name = "filesystem"
    description = "读写文件。action=read/write/list/exists。限制在工作目录内。"

    def __init__(self, workspace: str = "."):
        self.workspace = Path(workspace).resolve()

    def run(self, params: dict) -> str:
        action = params.get("action", "read")
        path = params.get("path", "")

        # 安全检查——防止路径穿越
        full_path = (self.workspace / path).resolve()
        if not str(full_path).startswith(str(self.workspace)):
            return f"安全限制: 无法访问工作目录外的文件 ({path})"

        if action == "read":
            return self._read(full_path)
        elif action == "write":
            return self._write(full_path, params.get("content", ""))
        elif action == "list":
            return self._list(full_path)
        elif action == "exists":
            return str(full_path.exists())
        elif action == "delete":
            return self._delete(full_path)
        elif action == "mkdir":
            return self._mkdir(full_path)
        else:
            return f"不支持的操作: {action}"

    def _read(self, path: Path) -> str:
        if not path.exists():
            return f"文件不存在: {path}"
        if path.stat().st_size > 1_000_000:  # 1MB 限制
            return f"文件太大 ({path.stat().st_size} bytes)"
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return f"无法读取（可能不是文本文件）: {path}"

    def _write(self, path: Path, content: str) -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"已写入: {path} ({len(content)} 字符)"

    def _list(self, path: Path) -> str:
        if not path.exists():
            return f"目录不存在: {path}"
        items = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name))
        lines = []
        for item in items[:50]:  # 限制50项
            icon = "📁" if item.is_dir() else "📄"
            size = item.stat().st_size if item.is_file() else 0
            lines.append(f"{icon} {item.name} ({self._format_size(size)})")
        return "\n".join(lines) if lines else "(空目录)"

    def _delete(self, path: Path) -> str:
        if not path.exists():
            return f"文件不存在: {path}"
        path.unlink()
        return f"已删除: {path}"

    def _mkdir(self, path: Path) -> str:
        path.mkdir(parents=True, exist_ok=True)
        return f"已创建目录: {path}"

    def _format_size(self, size: int) -> str:
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"
```

## 4. 工具重试与超时

```python
import signal
import time
from functools import wraps

class TimeoutError(Exception):
    pass

def with_timeout(seconds: int):
    """工具执行超时装饰器（Unix only——Windows 需另处理）"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            def handler(signum, frame):
                raise TimeoutError(f"执行超时 ({seconds}s)")
            old_handler = signal.signal(signal.SIGALRM, handler)
            signal.alarm(seconds)
            try:
                return func(*args, **kwargs)
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
        return wrapper
    return decorator

class RetryableTool:
    """支持重试的工具基类"""

    def __init__(self, retry_policy: dict = None):
        self.retry_policy = retry_policy or {
            "max_retries": 3,
            "backoff_seconds": 1.0,
            "backoff_multiplier": 2.0,
        }

    def execute_with_retry(self, tool_name: str, params: dict) -> str:
        policy = self.retry_policy
        delay = policy["backoff_seconds"]
        last_error = None

        for attempt in range(policy["max_retries"] + 1):
            try:
                result = self.registry.execute_tool(tool_name, params)
                if "错误" not in str(result)[:50]:
                    return result
                # 工具返回了错误——可能也需要重试
                last_error = result
            except (ConnectionError, TimeoutError, OSError) as e:
                last_error = str(e)

            if attempt < policy["max_retries"]:
                print(f"⏳ 第{attempt+1}次重试，等待 {delay:.1f}s...")
                time.sleep(delay)
                delay *= policy["backoff_multiplier"]

        return f"重试 {policy['max_retries']} 次后仍失败: {last_error}"
```

## 5. 工具测试模式

```python
def test_calculator_tool():
    """计算器工具的标准测试"""
    tool = CalculatorTool()

    # 基础运算
    assert "4" in tool.run({"expression": "2 + 2"})
    assert "0" in tool.run({"expression": "2 - 2"})

    # 边界情况
    assert "错误" in tool.run({"expression": ""})
    assert "错误" in tool.run({"expression": "__import__('os')"})  # 安全

    # 复杂表达式
    result = tool.run({"expression": "sqrt(16) + pow(2, 3)"})
    assert "12" in result

    print("✅ CalculatorTool 测试通过")

def test_search_tool():
    """搜索工具的集成测试"""
    tool = RobustSearchTool()
    result = tool.run({"query": "Python agent framework"})
    assert len(result) > 0
    print("✅ SearchTool 测试通过")
```
