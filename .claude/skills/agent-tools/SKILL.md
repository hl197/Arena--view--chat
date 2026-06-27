---
name: agent-tools
description: 在 HarnessAgent 项目中设计 Agent 的工具系统和通信协议。Use when: (1) 为 Agent 创建或注册工具, (2) 集成 MCP Server 到 Agent, (3) 设计 ToolRegistry 工具注册表, (4) 实现工具调用解析和执行, (5) 开发自定义工具(搜索/计算/文件等), (6) 设计 A2A Agent 间通信协议, (7) 多工具协同和 Fallback 策略。
---

# Agent Tools — 工具系统与协议设计

## 概述

本技能覆盖 Agent 工具系统的完整设计：从单一工具的接口规范，到 ToolRegistry 注册表管理，到 MCP 协议集成外部服务，再到 A2A 协议实现 Agent 间通信。Tool 是 Agent 的"手"——本技能确保它能可靠地执行各种操作。

## 工具系统架构

```
用户请求 → Agent(LLM推理) → 解析工具调用
                                ↓
                          ToolRegistry
                         /    |     \
                   内置Tool  MCPTool  A2AClient
                      ↓        ↓         ↓
                   本地函数  MCP Server  远程Agent
```

## 快速决策：工具协议选择

| 被调用方 | 协议 | 何时使用 |
|---------|------|---------|
| 本地函数/类 | **内置 Tool** | 系统内部功能：计算、文件、数据库 |
| 外部服务/API | **MCP** | 社区或第三方 MCP Server：搜索、地图、GitHub |
| 其他 Agent | **A2A** | Agent 间任务委派、协商、技能调用 |

**判断原则**: 被调用方是"被动工具"用 MCP/Tool，是"自主 Agent"用 A2A。

## Tool 接口设计

### 统一接口规范

所有工具必须实现 `run(params: dict) -> str` 接口：

```python
class Tool:
    """工具基类——所有工具的抽象父类"""

    name: str          # 唯一标识，如 "calculator", "search"
    description: str   # 给 LLM 看的功能描述，影响工具调用准确性

    def run(self, params: dict) -> str:
        """执行工具操作

        Args:
            params: 包含 'action' 字段的操作类型 + 操作参数
                   例如 {"action": "search", "query": "AI Agent", "limit": 5}

        Returns:
            字符串格式的执行结果（给 LLM 阅读）
        """
        raise NotImplementedError

    def get_schema(self) -> dict:
        """返回工具的 JSON Schema 描述——用于 Function Calling"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {...},
                "required": [...]
            }
        }
```

### Action 分发模式

```python
class MyTool(Tool):
    def run(self, params: dict) -> str:
        action = params.get("action")

        if action == "search":
            return self._search(
                query=params.get("query", ""),
                limit=params.get("limit", 5)
            )
        elif action == "add":
            return self._add(
                content=params.get("content"),
                category=params.get("category", "general")
            )
        elif action == "stats":
            return self._get_stats()
        else:
            return f"未知操作: {action}，支持: search, add, stats"
```

### 工具描述编写规范

工具描述直接决定 LLM 能否正确调用：

```python
# ❌ 糟糕的描述——LLM 不知道什么时候用
description = "一个搜索工具"

# ✅ 好的描述——LLM 清楚知道何时调用、如何调用
description = (
    "搜索知识库中的文档。当用户询问技术问题、需要查找文档内容、"
    "或需要了解项目相关信息时使用。参数: query(搜索关键词), limit(返回条数,默认5)"
)
```

## ToolRegistry 设计

### 核心实现

```python
class ToolRegistry:
    """工具注册表——统一管理 Agent 的所有工具"""

    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._functions: dict[str, dict] = {}  # 函数式注册的工具

    def register_tool(self, tool: Tool):
        """注册工具实例"""
        if tool.name in self._tools:
            raise ValueError(f"工具 '{tool.name}' 已存在")
        self._tools[tool.name] = tool

    def register_function(self, name: str, description: str, func: callable):
        """注册普通函数为工具——快速包装已有函数"""
        self._functions[name] = {
            "name": name,
            "description": description,
            "func": func
        }

    def execute_tool(self, name: str, params: str | dict) -> str:
        """执行工具调用——自动解析参数格式"""
        # 解析参数（支持字符串和字典两种输入）
        if isinstance(params, str):
            params = self._parse_params(params)

        # 先从实例工具查找
        if name in self._tools:
            return self._tools[name].run(params)

        # 再从函数工具查找
        if name in self._functions:
            return self._functions[name]["func"](**params)

        return f"工具 '{name}' 未找到。可用工具: {self.list_tools()}"

    def get_tools_description(self) -> str:
        """生成给 LLM 的工具描述文本"""
        lines = []
        for name, tool in self._tools.items():
            lines.append(f"- {name}: {tool.description}")
        for name, fn in self._functions.items():
            lines.append(f"- {name}: {fn['description']}")
        return "\n".join(lines)

    def list_tools(self) -> list[str]:
        """列出所有已注册工具名称"""
        return list(self._tools.keys()) + list(self._functions.keys())

    def _parse_params(self, raw: str) -> dict:
        """解析字符串参数为字典
        支持: key=value, key=value 或 key=value,key=value 格式
        """
        params = {}
        for part in raw.split(","):
            part = part.strip()
            if "=" in part:
                key, value = part.split("=", 1)
                params[key.strip()] = value.strip()
        return params
```

### 命名空间管理（多工具源共存）

```python
class HarnessToolManager:
    """HarnessAgent 的工具管理器——处理多来源工具命名冲突"""

    def __init__(self):
        self.registry = ToolRegistry()
        self._namespaces: dict[str, str] = {}  # tool_name → source

    def register_from_mcp(self, mcp_tool: MCPTool, namespace: str):
        """从 MCP Server 注册工具，加命名空间前缀"""
        for tool_info in mcp_tool.list_tools():
            full_name = f"{namespace}_{tool_info.name}"
            self._namespaces[full_name] = namespace
            # 创建代理工具，内部路由到 MCPTool
            proxy = MCPProxyTool(name=full_name, mcp_tool=mcp_tool,
                                 remote_name=tool_info.name)
            self.registry.register_tool(proxy)

    def register_builtin(self, tool: Tool):
        """注册内置工具（无命名空间）"""
        self.registry.register_tool(tool)

    def unload_namespace(self, namespace: str):
        """动态卸载某个 MCP Server 的所有工具"""
        to_remove = [n for n, ns in self._namespaces.items() if ns == namespace]
        for name in to_remove:
            del self.registry._tools[name]
            del self._namespaces[name]
```

## MCP 协议集成

### MCPClient 模式

```python
from hello_agents.protocols import MCPClient

# 连接社区 MCP Server
async def connect_git_mcp():
    client = MCPClient(["npx", "-y", "@modelcontextprotocol/server-github"])
    async with client:
        tools = await client.list_tools()
        # tools = [{"name": "search_repos", "description": "...", "inputSchema": {...}}, ...]
        result = await client.call_tool("search_repos", {"query": "AI agent"})
        return result
```

### MCPTool 包装模式

```python
from hello_agents.tools import MCPTool

# 将 MCP Server 包装为 Agent 可用的 Tool
fs_tool = MCPTool(
    name="filesystem",           # Agent 看到的工具名（必须唯一）
    description="读写本地文件系统",
    server_command=["npx", "-y", "@modelcontextprotocol/server-filesystem", "."]
)

# 多个 MCP Server 共存——关键在于唯一的 name
gh_tool = MCPTool(name="github", server_command=["npx", "-y", "@modelcontextprotocol/server-github"])
amap_tool = MCPTool(name="amap", server_command=["uvx", "amap-mcp-server"])
custom_tool = MCPTool(name="my_service", server_command=["python", "my_mcp_server.py"])

for tool in [gh_tool, amap_tool, custom_tool, fs_tool]:
    agent.add_tool(tool)
```

### MCP Server 生命周期管理

```python
class MCPLifecycleManager:
    """管理 MCP Server 的启动、健康检查、重连、关闭"""

    def __init__(self):
        self.servers: dict[str, MCPClient] = {}
        self.health_status: dict[str, bool] = {}

    async def start_server(self, name: str, command: list[str]) -> MCPClient:
        client = MCPClient(command)
        await client.__aenter__()
        self.servers[name] = client
        return client

    async def health_check(self) -> dict[str, bool]:
        """定期检查所有 MCP Server 是否存活"""
        for name, client in self.servers.items():
            try:
                await client.list_tools()  # 轻量级探测
                self.health_status[name] = True
            except Exception:
                self.health_status[name] = False
        return self.health_status

    async def restart(self, name: str) -> MCPClient:
        """重启失败的 MCP Server"""
        if name in self.servers:
            await self.servers[name].__aexit__(None, None, None)
        # 重新启动（需要保存原始 command）
        ...

    async def shutdown_all(self):
        for client in self.servers.values():
            await client.__aexit__(None, None, None)
```

## 自定义工具开发

### 计算器工具（AST 安全求值）

```python
import ast
import operator
import math

class CalculatorTool(Tool):
    name = "calculator"
    description = "安全地计算数学表达式，支持 +-*/、sqrt、pow、sin、cos、pi"

    def run(self, params: dict) -> str:
        expression = params.get("expression", params.get("query", ""))
        try:
            result = self._safe_eval(expression)
            return f"计算结果: {result}"
        except Exception as e:
            return f"计算失败: {e}"

    def _safe_eval(self, expr: str) -> float:
        """使用 AST 安全求值——不执行任意代码"""
        allowed_ops = {
            ast.Add: operator.add, ast.Sub: operator.sub,
            ast.Mult: operator.mul, ast.Div: operator.truediv,
            ast.Pow: operator.pow, ast.USub: operator.neg,
        }
        allowed_funcs = {
            'sqrt': math.sqrt, 'pow': math.pow,
            'sin': math.sin, 'cos': math.cos,
            'pi': math.pi, 'abs': abs
        }

        def _eval(node):
            if isinstance(node, ast.Expression):
                return _eval(node.body)
            if isinstance(node, ast.BinOp):
                return allowed_ops[type(node.op)](_eval(node.left), _eval(node.right))
            if isinstance(node, ast.UnaryOp):
                return allowed_ops[type(node.op)](_eval(node.operand))
            if isinstance(node, ast.Call):
                if node.func.id not in allowed_funcs:
                    raise ValueError(f"不允许的函数: {node.func.id}")
                args = [_eval(a) for a in node.args]
                return allowed_funcs[node.func.id](*args)
            if isinstance(node, ast.Constant):
                return node.value
            raise ValueError(f"不支持的节点: {type(node)}")

        return _eval(ast.parse(expr, mode='eval'))
```

### 搜索工具（多源 Fallback）

```python
class RobustSearchTool(Tool):
    """多搜索引擎 + 自动切换"""

    name = "web_search"
    description = "搜索互联网信息。当需要查找最新资料、事实核查时使用。"

    def __init__(self):
        self.sources = []
        self._init_sources()

    def _init_sources(self):
        """自动检测可用的搜索 API"""
        import os
        if os.getenv("TAVILY_API_KEY"):
            self.sources.append(("tavily", self._search_tavily))
        if os.getenv("SERPAPI_API_KEY"):
            self.sources.append(("serpapi", self._search_serpapi))
        if os.getenv("BRAVE_API_KEY"):
            self.sources.append(("brave", self._search_brave))
        if not self.sources:
            self.sources.append(("builtin", self._search_builtin))

    def run(self, params: dict) -> str:
        query = params.get("query", "")
        limit = int(params.get("limit", 5))

        for source_name, search_fn in self.sources:
            try:
                results = search_fn(query, limit)
                if results:
                    return self._format_results(results, source_name)
            except Exception as e:
                continue  # 自动尝试下一个源

        return "所有搜索源均不可用，请稍后重试。"

    def _format_results(self, results: list, source: str) -> str:
        lines = [f"搜索完成 (via {source}):"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r['title']}\n   {r['snippet']}\n   {r.get('url', '')}")
        return "\n".join(lines)
```

## 工具调用解析

### 从 LLM 输出提取工具调用

```python
class ToolCallParser:
    """解析 LLM 输出中的工具调用——支持多种格式"""

    # 格式1: ReAct 风格
    REACT_PATTERN = re.compile(r'(\w+)\[(.*?)\]')

    # 格式2: 标记风格
    MARKER_PATTERN = re.compile(r'\[TOOL_CALL:([^:]+):([^\]]*)\]')

    # 格式3: Function Call JSON (OpenAI 原生)
    JSON_PATTERN = re.compile(r'```json\s*(.*?)\s*```', re.DOTALL)

    def parse(self, text: str) -> list[dict]:
        """按优先级尝试多种解析方式"""
        # 优先尝试标记格式（最可靠）
        calls = self._parse_marker(text)
        if calls:
            return calls

        # 其次尝试 ReAct 格式
        calls = self._parse_react(text)
        if calls:
            return calls

        # 最后尝试 JSON function call
        return self._parse_json(text)

    def _parse_marker(self, text: str) -> list[dict]:
        matches = self.MARKER_PATTERN.findall(text)
        return [{'tool_name': m[0].strip(), 'parameters': m[1].strip(), 'format': 'marker'}
                for m in matches]

    def _parse_react(self, text: str) -> list[dict]:
        matches = self.REACT_PATTERN.findall(text)
        return [{'tool_name': m[0], 'parameters': m[1], 'format': 'react'}
                for m in matches if m[0] != 'Finish']

    def _parse_json(self, text: str) -> list[dict]:
        json_matches = self.JSON_PATTERN.findall(text)
        calls = []
        for json_str in json_matches:
            try:
                data = json.loads(json_str)
                if isinstance(data, dict) and 'tool' in data:
                    calls.append({'tool_name': data['tool'],
                                  'parameters': data.get('params', {}),
                                  'format': 'json'})
            except json.JSONDecodeError:
                continue
        return calls
```

## A2A 协议（Agent-to-Agent）

### A2AServer — 暴露技能

```python
from hello_agents.protocols.a2a.implementation import A2AServer

# 创建 Agent Server
agent_server = A2AServer(
    name="code-reviewer",
    description="专业的代码审查 Agent，支持多语言代码审查",
    version="1.0.0",
    capabilities={
        "review": ["security", "performance", "style", "architecture"],
        "languages": ["python", "javascript", "typescript", "java"]
    }
)

# 注册技能——其他 Agent 可通过 skill 名称远程调用
@agent_server.skill("review")
def review_code(query: str) -> str:
    """审查代码并给出改进建议"""
    # 解析 query 中的代码和语言信息
    # 执行审查逻辑
    return json.dumps({
        "issues": [...],
        "score": 85,
        "suggestions": [...]
    })

@agent_server.skill("explain")
def explain_code(query: str) -> str:
    """解释代码逻辑"""
    return "这段代码实现了..."

@agent_server.skill("info")
def get_info(query: str) -> str:
    """返回 Agent 的能力信息"""
    return json.dumps({
        "name": agent_server.name,
        "version": agent_server.version,
        "skills": list(agent_server.skills.keys()),
        "capabilities": agent_server.capabilities
    })
```

### A2AClient — 调用远程 Agent

```python
from hello_agents.protocols import A2AClient

class AgentConnector:
    """管理与远程 Agent 的连接和调用"""

    def __init__(self, base_url: str):
        self.client = A2AClient(base_url)
        self.cached_capabilities = None

    def discover_capabilities(self) -> dict:
        """发现远程 Agent 的能力"""
        result = self.client.execute_skill("info", "capabilities")
        self.cached_capabilities = json.loads(result)
        return self.cached_capabilities

    def execute(self, skill_name: str, input_data: str,
                timeout: int = 30) -> str:
        """调用远程 Agent 的指定技能"""
        try:
            return self.client.execute_skill(skill_name, input_data)
        except TimeoutError:
            return f"调用 {skill_name} 超时（{timeout}s）"
        except ConnectionError:
            return f"无法连接到远程 Agent"

    def negotiate(self, task: str, deadline: int) -> dict:
        """Agent 间协商——支持提案/反提案"""
        proposal = {"task": task, "deadline": deadline}
        response = self.client.execute_skill("negotiate", json.dumps(proposal))
        return json.loads(response)
```

## 错误处理与可靠性

### 工具执行防护

```python
def safe_execute(self, tool_name: str, params: dict,
                  timeout: int = 30, fallback: str = None) -> str:
    """带超时和兜底的工具执行"""
    import signal

    try:
        result = self.registry.execute_tool(tool_name, params)
        if result is None:
            return f"工具 '{tool_name}' 返回了空结果"
        return str(result)
    except TimeoutError:
        if fallback:
            return self.registry.execute_tool(fallback, params)
        return f"工具 '{tool_name}' 执行超时（{timeout}s）"
    except Exception as e:
        if fallback:
            try:
                return self.registry.execute_tool(fallback, params)
            except Exception:
                pass
        return f"工具 '{tool_name}' 执行失败: {e}"
```

### 工具重试策略

```python
@dataclass
class RetryPolicy:
    max_retries: int = 3
    backoff_seconds: float = 1.0
    backoff_multiplier: float = 2.0
    retryable_errors: tuple = (ConnectionError, TimeoutError)

def execute_with_retry(self, tool_name: str, params: dict,
                        policy: RetryPolicy = RetryPolicy()) -> str:
    """带重试的工具执行"""
    last_error = None
    delay = policy.backoff_seconds

    for attempt in range(policy.max_retries + 1):
        try:
            return self.registry.execute_tool(tool_name, params)
        except policy.retryable_errors as e:
            last_error = e
            if attempt < policy.max_retries:
                time.sleep(delay)
                delay *= policy.backoff_multiplier
        except Exception as e:
            return f"不可重试的错误: {e}"

    return f"重试 {policy.max_retries} 次后仍失败: {last_error}"
```

## 参考资源

| 文件 | 内容 | 何时查阅 |
|------|------|---------|
| [tool-design.md](references/tool-design.md) | ToolRegistry 完整实现、Action 分发、命名空间管理 | 设计工具注册表时 |
| [mcp-integration.md](references/mcp-integration.md) | MCPClient/MCPTool、A2A 协议、Server 生命周期 | 集成外部协议时 |
| [custom-tools.md](references/custom-tools.md) | 计算器/搜索/文件工具开发、多源 Fallback、重试策略 | 开发自定义工具时 |

> 📌 本技能覆盖 Hello Agent 教程 Ch4,7,10。Agent 核心范式见 agent-builder 技能，记忆系统见 agent-memory 技能。
