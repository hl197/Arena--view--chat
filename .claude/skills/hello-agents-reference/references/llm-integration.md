# LLM 集成层参考

## 架构设计

```
HelloAgentsLLM (统一接口)
  → create_adapter(base_url) 自动选择适配器
     ├── OpenAIAdapter     (默认，兼容所有 OpenAI 格式接口)
     ├── AnthropicAdapter  (Claude: system 独立、tool_use 格式转换)
     └── GeminiAdapter     (Google: genai 新版包)
  → 统一返回 LLMResponse / LLMToolResponse
```

## HelloAgentsLLM 统一接口

```python
class HelloAgentsLLM:
    """支持任何 OpenAI 兼容接口的 LLM 客户端"""
    def __init__(self, model=None, api_key=None, base_url=None,
                 temperature=0.7, max_tokens=None, timeout=None, **kwargs):
        # 参数优先级：传入参数 > 环境变量
        self.model = model or os.getenv("LLM_MODEL_ID")
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        self.base_url = base_url or os.getenv("LLM_BASE_URL")
        # 自动选择适配器
        self._adapter = create_adapter(api_key, base_url, timeout, model)

    # === 同步调用 ===
    def think(self, messages, temperature=None) -> Iterator[str]:
        """流式调用（实时打印）"""
    def invoke(self, messages, **kwargs) -> LLMResponse:
        """非流式调用，返回完整响应对象"""
    def invoke_with_tools(self, messages, tools, tool_choice="auto", **kwargs) -> LLMToolResponse:
        """Function Calling 调用"""
    def stream_invoke(self, messages, **kwargs) -> Iterator[str]:
        """流式调用别名"""

    # === 异步调用 ===
    async def ainvoke(self, messages, **kwargs) -> LLMResponse:
        """线程池包装同步 invoke"""
    async def astream_invoke(self, messages, **kwargs) -> AsyncIterator[str]:
        """真正的异步流式（使用 adapter 的异步实现）"""
    async def ainvoke_with_tools(self, messages, tools, **kwargs) -> LLMToolResponse:
        """线程池包装同步 invoke_with_tools"""
```

## 响应数据结构

```python
@dataclass
class LLMResponse:
    content: str
    model: str
    usage: Dict[str, int]      # {"prompt_tokens":100, "completion_tokens":50, "total_tokens":150}
    latency_ms: int = 0
    reasoning_content: Optional[str] = None  # Thinking model 推理过程

@dataclass
class LLMToolResponse:
    content: Optional[str]     # 文本内容（可能为 None）
    tool_calls: List[ToolCall] # 工具调用列表
    model: str
    usage: Dict[str, int]
    latency_ms: int = 0

@dataclass
class ToolCall:
    id: str        # "call_xxx"
    name: str      # "Read"
    arguments: str # '{"path": "config.py"}'  (JSON 字符串)

@dataclass
class StreamStats:
    model: str
    usage: Dict[str, int]
    latency_ms: int
    reasoning_content: Optional[str] = None
```

## 适配器架构

```python
class BaseLLMAdapter(ABC):
    def __init__(self, api_key, base_url, timeout, model): ...
    @abstractmethod
    def create_client(self) -> Any: ...
    def create_async_client(self) -> Any: ...
    @abstractmethod
    def invoke(self, messages, **kwargs) -> LLMResponse: ...
    @abstractmethod
    def stream_invoke(self, messages, **kwargs) -> Iterator[str]: ...
    @abstractmethod
    def invoke_with_tools(self, messages, tools, **kwargs) -> LLMToolResponse: ...
    # 异步流式默认实现：队列+线程池包装同步方法
    async def astream_invoke(self, messages, **kwargs) -> AsyncIterator[str]: ...
```

### OpenAIAdapter（默认）

兼容所有 OpenAI 格式接口：OpenAI / DeepSeek / Qwen / Kimi / 智谱 / Ollama / vLLM

```python
class OpenAIAdapter(BaseLLMAdapter):
    def create_client(self):
        return OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=self.timeout)

    def create_async_client(self):
        return AsyncOpenAI(api_key=self.api_key, base_url=self.base_url, timeout=self.timeout)

    def invoke_with_tools(self, messages, tools, tool_choice, **kwargs):
        response = self._client.chat.completions.create(
            model=self.model, messages=messages, tools=tools,
            tool_choice=tool_choice, **kwargs)
        # 解析 message.tool_calls → List[ToolCall]
```

### AnthropicAdapter

处理 Claude 特有格式：
- system 参数独立（不在 messages 中）
- 工具调用转为 `{type: "tool_use", id, name, input}`
- 工具结果转为 `{role: "user", content: [{type: "tool_result", tool_use_id, content}]}`

### GeminiAdapter

使用新版 `google-genai`（替代废弃的 `google.generativeai`）：
- 角色映射：assistant → "model"，user → "user"
- 工具声明：`genai_types.FunctionDeclaration` → `genai_types.Tool`
- 工具配置：`genai_types.ToolConfig` + `FunctionCallingConfig(mode="ANY"/"NONE")`

## 适配器自动选择

```python
def create_adapter(api_key, base_url, timeout, model) -> BaseLLMAdapter:
    if base_url:
        if "anthropic.com" in base_url.lower():
            return AnthropicAdapter(api_key, base_url, timeout, model)
        if "googleapis.com" in base_url.lower() or "generativelanguage" in base_url.lower():
            return GeminiAdapter(api_key, base_url, timeout, model)
    return OpenAIAdapter(api_key, base_url, timeout, model)  # 默认
```

## Function Calling 架构优势

旧方案（Prompt 工程）vs 新方案（Function Calling）：

| 维度 | Prompt 工程 | Function Calling |
|------|-----------|------------------|
| 解析成功率 | ~85% | 99%+ |
| Token 消耗 | 500 (prompt开销) | 300 (节省40%) |
| 格式灵活性 | 依赖正则 | LLM 原生结构化输出 |
| 多工具调用 | 需手动解析 | 原生支持并行调用 |

## 异步流式实现策略

```python
# BaseLLMAdapter 默认实现：队列 + 线程池
async def astream_invoke(self, messages, **kwargs):
    queue = asyncio.Queue()
    def _stream_to_queue():
        for chunk in self.stream_invoke(messages, **kwargs):
            asyncio.run_coroutine_threadsafe(queue.put(chunk), loop)
        asyncio.run_coroutine_threadsafe(queue.put(None), loop)  # 结束信号
    loop.run_in_executor(None, _stream_to_queue)
    while True:
        chunk = await queue.get()
        if chunk is None: break
        yield chunk

# OpenAIAdapter 覆盖为真正的异步
async def astream_invoke(self, messages, **kwargs):
    response = await self._async_client.chat.completions.create(
        model=self.model, messages=messages, stream=True, **kwargs)
    async for chunk in response:
        # 提取 content + reasoning_content + usage
        yield content
```

## 异常体系

```python
class HelloAgentsException(Exception): pass   # 基类
class LLMException(HelloAgentsException): pass # LLM 相关
class AgentException(HelloAgentsException): pass # Agent 相关
class ConfigException(HelloAgentsException): pass # 配置相关
class ToolException(HelloAgentsException): pass  # 工具相关
```
