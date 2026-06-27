"""ArenaLLM — 统一 LLM 接口

提供多模型路由和自动降级：
1. 用户配置的 LLM（高级用户自填 Key，如 Gemini/GPT-4o 等）
2. 默认 DeepSeek（低成本，约 ¥1/百万 token）
3. 自动降级到默认适配器
"""

import os
from typing import Iterator, Optional
from .base import BaseLLMAdapter, create_adapter
from .llm_response import LLMResponse, LLMToolResponse
from ..core.exceptions import AdapterException


class ArenaLLM:
    """多模型统一 LLM 接口

    默认使用 DeepSeek（低成本），用户可配置自己的 API Key
    切换到任意支持的 Provider（Gemini/OpenAI/Groq 等）。

    使用方式:
        # 默认 DeepSeek
        llm = ArenaLLM()

        # 用户自填 Key 切换到 Gemini
        llm = ArenaLLM(user_provider="gemini", user_api_key="xxx", user_model="gemini-2.0-flash")
    """

    def __init__(
        self,
        user_provider: Optional[str] = None,
        user_api_key: Optional[str] = None,
        user_model: Optional[str] = None,
        user_base_url: Optional[str] = None,
    ):
        # 默认适配器（DeepSeek 低成本，用户也可通过界面切换到 Gemini/OpenAI 等）
        self.default_provider = "deepseek"
        self.default_model = "deepseek-chat"
        self.default_api_key = os.getenv("DEEPSEEK_API_KEY")

        if not self.default_api_key:
            raise AdapterException(
                "未配置 DEEPSEEK_API_KEY 环境变量。\n"
                "获取: https://platform.deepseek.com/api_keys\n"
                "设置方式: export DEEPSEEK_API_KEY=your-key"
            )

        self._default_adapter: Optional[BaseLLMAdapter] = None
        self._user_adapter: Optional[BaseLLMAdapter] = None

        # 用户适配器
        if user_api_key and user_provider:
            self._user_adapter = create_adapter(
                provider=user_provider,
                api_key=user_api_key,
                base_url=user_base_url,
                model=user_model or "",
            )

    @property
    def default_adapter(self) -> BaseLLMAdapter:
        if self._default_adapter is None:
            self._default_adapter = create_adapter(
                provider=self.default_provider,
                api_key=self.default_api_key,
                model=self.default_model,
            )
        return self._default_adapter

    @property
    def has_user_llm(self) -> bool:
        return self._user_adapter is not None

    def _get_adapter(self) -> BaseLLMAdapter:
        """优先用户适配器，降级默认"""
        if self._user_adapter:
            return self._user_adapter
        return self.default_adapter

    # === 公共接口 ===
    def invoke(self, messages: list[dict], **kwargs) -> LLMResponse:
        """非流式调用——优先用户适配器，降级默认"""
        if self._user_adapter:
            try:
                return self._user_adapter.invoke(messages, **kwargs)
            except Exception:
                pass  # 降级
        return self.default_adapter.invoke(messages, **kwargs)

    def think(self, messages: list[dict], **kwargs) -> Iterator[str]:
        """流式调用"""
        try:
            adapter = self._get_adapter()
            yield from adapter.stream_invoke(messages, **kwargs)
        except Exception:
            # 降级到默认
            yield from self.default_adapter.stream_invoke(messages, **kwargs)

    def invoke_with_tools(self, messages: list[dict], tools: list[dict],
                          tool_choice: str = "auto", **kwargs) -> LLMToolResponse:
        try:
            adapter = self._get_adapter()
            return adapter.invoke_with_tools(messages, tools, tool_choice, **kwargs)
        except Exception:
            return self.default_adapter.invoke_with_tools(messages, tools, tool_choice, **kwargs)

    # === 异步接口 ===
    async def ainvoke(self, messages: list[dict], **kwargs) -> LLMResponse:
        try:
            adapter = self._get_adapter()
            return await adapter.ainvoke(messages, **kwargs)
        except Exception:
            return await self.default_adapter.ainvoke(messages, **kwargs)

    async def athink(self, messages: list[dict], **kwargs):
        try:
            adapter = self._get_adapter()
            async for chunk in adapter.astream_invoke(messages, **kwargs):
                yield chunk
        except Exception:
            async for chunk in self.default_adapter.astream_invoke(messages, **kwargs):
                yield chunk

    async def ainvoke_with_tools(self, messages: list[dict], tools: list[dict],
                                 tool_choice: str = "auto", **kwargs) -> LLMToolResponse:
        try:
            adapter = self._get_adapter()
            return await adapter.ainvoke_with_tools(messages, tools, tool_choice, **kwargs)
        except Exception:
            return await self.default_adapter.ainvoke_with_tools(messages, tools, tool_choice, **kwargs)
