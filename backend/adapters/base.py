"""LLM 适配器抽象基类

参考 HelloAgents 的 BaseLLMAdapter 设计。
"""

from abc import ABC, abstractmethod
from typing import Iterator, AsyncIterator, Optional
from .llm_response import LLMResponse, LLMToolResponse


class BaseLLMAdapter(ABC):
    """LLM 适配器抽象基类

    所有 Provider 适配器必须实现以下方法：
    - invoke: 非流式调用
    - stream_invoke: 流式调用
    - invoke_with_tools: Function Calling 调用
    """

    def __init__(self, api_key: str, base_url: Optional[str] = None,
                 timeout: int = 60, model: str = ""):
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.model = model
        self._client = None

    @abstractmethod
    def invoke(self, messages: list[dict], **kwargs) -> LLMResponse:
        """非流式调用——返回完整响应"""
        ...

    @abstractmethod
    def stream_invoke(self, messages: list[dict], **kwargs) -> Iterator[str]:
        """流式调用——逐块返回文本"""
        ...

    @abstractmethod
    def invoke_with_tools(self, messages: list[dict], tools: list[dict],
                          tool_choice: str = "auto", **kwargs) -> LLMToolResponse:
        """Function Calling 调用"""
        ...

    async def ainvoke(self, messages: list[dict], **kwargs) -> LLMResponse:
        """异步非流式——默认线程池包装"""
        import asyncio
        return await asyncio.to_thread(self.invoke, messages, **kwargs)

    async def astream_invoke(self, messages: list[dict], **kwargs) -> AsyncIterator[str]:
        """异步流式——默认队列+线程池包装"""
        import asyncio
        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def _stream_to_queue():
            try:
                for chunk in self.stream_invoke(messages, **kwargs):
                    asyncio.run_coroutine_threadsafe(queue.put(chunk), loop)
            finally:
                asyncio.run_coroutine_threadsafe(queue.put(None), loop)

        loop.run_in_executor(None, _stream_to_queue)

        while True:
            chunk = await queue.get()
            if chunk is None:
                break
            yield chunk

    async def ainvoke_with_tools(self, messages: list[dict], tools: list[dict],
                                 tool_choice: str = "auto", **kwargs) -> LLMToolResponse:
        """异步 Function Calling——默认线程池包装"""
        import asyncio
        return await asyncio.to_thread(self.invoke_with_tools, messages, tools, tool_choice, **kwargs)


def create_adapter(provider: str, api_key: str, base_url: Optional[str] = None,
                   model: str = "", timeout: int = 60) -> BaseLLMAdapter:
    """工厂函数——根据 Provider 自动选择适配器

    Args:
        provider: "gemini" | "openai" | "deepseek" | "groq" | "custom"
        api_key: API 密钥
        base_url: 自定义端点（custom Provider 必需）
        model: 模型名称
        timeout: 超时秒数
    """
    provider_lower = provider.lower()

    if provider_lower == "gemini":
        from .gemini_adapter import GeminiAdapter
        return GeminiAdapter(api_key=api_key, timeout=timeout, model=model)
    else:
        # 所有 OpenAI 兼容接口：openai / deepseek / groq / together / custom
        from .openai_adapter import OpenAIAdapter
        resolved_url = base_url
        if provider_lower == "deepseek" and not resolved_url:
            resolved_url = "https://api.deepseek.com/v1"
        elif provider_lower == "groq" and not resolved_url:
            resolved_url = "https://api.groq.com/openai/v1"
        elif provider_lower == "openai" and not resolved_url:
            resolved_url = "https://api.openai.com/v1"
        return OpenAIAdapter(api_key=api_key, base_url=resolved_url, timeout=timeout, model=model)
