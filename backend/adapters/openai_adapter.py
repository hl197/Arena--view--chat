"""OpenAI 兼容适配器

兼容所有 OpenAI 格式接口：
- OpenAI / DeepSeek / Groq / Together / Ollama / vLLM / 自定义端点
"""

import time
import json
from typing import Iterator, Optional
from .base import BaseLLMAdapter
from .llm_response import LLMResponse, LLMToolResponse, ToolCall


class OpenAIAdapter(BaseLLMAdapter):
    """OpenAI 兼容适配器——支持所有 OpenAI 格式 API"""

    def __init__(self, api_key: str, base_url: Optional[str] = None,
                 timeout: int = 60, model: str = ""):
        super().__init__(api_key=api_key, base_url=base_url, timeout=timeout, model=model)
        try:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=timeout,
            )
        except ImportError:
            raise ImportError("请安装 openai: pip install openai")

    def invoke(self, messages: list[dict], **kwargs) -> LLMResponse:
        start = time.time()

        # 过滤 tool_calls 消息（纯文本调用时不需要）
        clean_messages = self._clean_messages(messages, include_tool_calls=False)

        response = self._client.chat.completions.create(
            model=self.model,
            messages=clean_messages,
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens"),
        )

        elapsed_ms = int((time.time() - start) * 1000)
        choice = response.choices[0]
        content = choice.message.content or ""

        usage = {}
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        return LLMResponse(
            content=content,
            model=response.model,
            usage=usage,
            latency_ms=elapsed_ms,
        )

    def stream_invoke(self, messages: list[dict], **kwargs) -> Iterator[str]:
        clean_messages = self._clean_messages(messages, include_tool_calls=False)

        response = self._client.chat.completions.create(
            model=self.model,
            messages=clean_messages,
            temperature=kwargs.get("temperature", 0.7),
            stream=True,
        )

        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def invoke_with_tools(self, messages: list[dict], tools: list[dict],
                          tool_choice: str = "auto", **kwargs) -> LLMToolResponse:
        start = time.time()

        clean_messages = self._clean_messages(messages, include_tool_calls=True)

        response = self._client.chat.completions.create(
            model=self.model,
            messages=clean_messages,
            tools=tools,
            tool_choice=tool_choice,
            temperature=kwargs.get("temperature", 0),
        )

        elapsed_ms = int((time.time() - start) * 1000)
        choice = response.choices[0]
        msg = choice.message

        tool_calls = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=tc.function.arguments,
                ))

        usage = {}
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        return LLMToolResponse(
            content=msg.content,
            tool_calls=tool_calls,
            model=response.model,
            usage=usage,
            latency_ms=elapsed_ms,
        )

    def _clean_messages(self, messages: list[dict], include_tool_calls: bool = False) -> list[dict]:
        """清理消息——移除不兼容的字段"""
        clean = []
        for msg in messages:
            new_msg = {"role": msg["role"], "content": msg.get("content")}
            if msg["role"] == "tool" and "tool_call_id" in msg:
                new_msg["tool_call_id"] = msg["tool_call_id"]
            if msg["role"] == "assistant" and "tool_calls" in msg and include_tool_calls:
                new_msg["tool_calls"] = msg["tool_calls"]
            clean.append(new_msg)
        return clean
