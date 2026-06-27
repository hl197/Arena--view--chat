# MCP 协议集成参考

## MCPClient 完整模式

```python
from hello_agents.protocols import MCPClient
from contextlib import asynccontextmanager

class MCPManager:
    """管理与多个 MCP Server 的连接"""

    def __init__(self):
        self.clients: dict[str, MCPClient] = {}
        self.tools_cache: dict[str, list] = {}  # server_name → tools

    async def connect(self, name: str, command: list[str]) -> dict:
        """连接到 MCP Server 并发现其工具"""
        client = MCPClient(command)
        await client.__aenter__()
        self.clients[name] = client

        # 发现可用工具
        tools = await client.list_tools()
        self.tools_cache[name] = tools

        return {
            "server": name,
            "tool_count": len(tools),
            "tools": [t.name for t in tools]
        }

    async def call(self, server_name: str, tool_name: str, params: dict) -> str:
        """调用指定 MCP Server 的工具"""
        if server_name not in self.clients:
            return f"MCP Server '{server_name}' 未连接"
        client = self.clients[server_name]
        result = await client.call_tool(tool_name, params)
        return result

    async def health_check(self) -> dict:
        """检查所有 Server 是否存活"""
        status = {}
        for name, client in self.clients.items():
            try:
                await client.list_tools()  # 轻量级探测
                status[name] = "healthy"
            except Exception as e:
                status[name] = f"unhealthy: {e}"
        return status

    async def reconnect(self, name: str) -> bool:
        """重连异常断开的 Server"""
        if name in self.clients:
            try:
                await self.clients[name].__aexit__(None, None, None)
            except Exception:
                pass
        # 需要保存原始 command 才能重连
        # 建议在实际使用中保存 server_configs
        return False

    async def shutdown(self):
        """关闭所有 MCP 连接"""
        for client in self.clients.values():
            await client.__aexit__(None, None, None)
        self.clients.clear()
        self.tools_cache.clear()
```

## MCPTool 包装模式

```python
from hello_agents.tools import MCPTool

class ManagedMCPTool:
    """增强版 MCPTool —— 带命名空间和自动重连"""

    def __init__(self, name: str, server_command: list[str],
                 namespace: str = "", auto_reconnect: bool = True):
        self.name = name
        self.namespace = namespace
        self.full_name = f"{namespace}_{name}" if namespace else name
        self.server_command = server_command
        self.auto_reconnect = auto_reconnect
        self._mcp_tool = MCPTool(name=name, server_command=server_command)

    def get_tool_names(self) -> list[str]:
        """获取 MCP Server 暴露的所有工具名（加命名空间前缀）"""
        raw_names = self._mcp_tool.list_tool_names()  # 假设有此方法
        if self.namespace:
            return [f"{self.namespace}_{n}" for n in raw_names]
        return raw_names

    def resolve_call(self, namespaced_name: str) -> str:
        """去掉命名空间前缀，返回原始工具名"""
        if self.namespace and namespaced_name.startswith(f"{self.namespace}_"):
            return namespaced_name[len(self.namespace) + 1:]
        return namespaced_name
```

## 多 MCP Server 共存

```python
# 关键配置——每个 Server 独立的 MCPTool
MCP_SERVERS = {
    "filesystem": {
        "command": ["npx", "-y", "@modelcontextprotocol/server-filesystem", "."],
        "description": "读写本地文件系统"
    },
    "github": {
        "command": ["npx", "-y", "@modelcontextprotocol/server-github"],
        "description": "搜索和管理 GitHub 仓库"
    },
    "postgres": {
        "command": ["npx", "-y", "@modelcontextprotocol/server-postgres"],
        "description": "查询 PostgreSQL 数据库"
    },
    "amap": {
        "command": ["uvx", "amap-mcp-server"],
        "description": "高德地图——POI搜索、路线规划、天气"
    },
    "custom": {
        "command": ["python", "my_custom_mcp_server.py"],
        "description": "自定义 MCP Server"
    }
}

async def setup_all_mcp_tools(agent) -> dict:
    """为 Agent 注册所有 MCP Server——含错误处理"""
    manager = MCPManager()
    registered = {}

    for name, config in MCP_SERVERS.items():
        try:
            # 创建并连接
            tool = MCPTool(name=name, server_command=config["command"])
            await manager.connect(name, config["command"])

            # 注册到 Agent
            agent.add_tool(tool)
            registered[name] = "success"
            print(f"✅ MCP Server '{name}' 注册成功")

        except Exception as e:
            registered[name] = f"failed: {e}"
            print(f"❌ MCP Server '{name}' 注册失败: {e}")

    return registered
```

## MCP 工具调用的 Agent 端处理

```python
class MCPAwareAgent:
    """感知 MCP 工具的 Agent——自动发现和调用"""

    def __init__(self, name: str, llm, mcp_manager: MCPManager):
        self.name = name
        self.llm = llm
        self.mcp_manager = mcp_manager
        self.tool_registry = ToolRegistry()

    async def discover_and_register(self):
        """启动时自动发现所有 MCP 工具并注册"""
        for server_name, client in self.mcp_manager.clients.items():
            tools = await client.list_tools()
            for tool_info in tools:
                # 为每个 MCP 工具创建代理
                proxy = MCPProxyTool(
                    name=f"{server_name}_{tool_info.name}",
                    server_name=server_name,
                    tool_name=tool_info.name,
                    description=tool_info.description,
                    mcp_manager=self.mcp_manager
                )
                self.tool_registry.register_tool(proxy)

    def _build_mcp_aware_prompt(self) -> str:
        """构建包含 MCP 工具信息的系统提示词"""
        tools_desc = []
        for name, tool in self.tool_registry._tools.items():
            server = getattr(tool, 'server_name', 'local')
            tools_desc.append(f"- {name} [via {server}]: {tool.description}")
        return "\n".join(tools_desc)
```

## 自定义 MCP Server 开发

```python
# my_mcp_server.py —— 自定义 MCP Server 示例
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationCapabilities
import mcp.server.stdio
import mcp.types as types

server = Server("my-custom-server")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """定义 Server 提供的工具列表"""
    return [
        types.Tool(
            name="get_weather",
            description="获取指定城市的天气信息",
            inputSchema={
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名称"}
                },
                "required": ["city"]
            }
        ),
        types.Tool(
            name="translate",
            description="翻译文本",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "target_lang": {"type": "string", "default": "英文"}
                },
                "required": ["text"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """处理工具调用请求"""
    if name == "get_weather":
        city = arguments.get("city", "北京")
        # 实际应用中调用天气 API
        result = f"{city}今天晴，22-30°C"
        return [types.TextContent(type="text", text=result)]

    elif name == "translate":
        text = arguments.get("text", "")
        target = arguments.get("target_lang", "英文")
        # 实际应用中调用翻译 API
        result = f"翻译({target}): {text}"
        return [types.TextContent(type="text", text=result)]

    raise ValueError(f"未知工具: {name}")

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream,
            InitializationCapabilities(
                sampling={}, experimental={}, roots={}
            )
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```
