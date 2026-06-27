"""Google Gemini 适配器

使用 google-genai 新版 SDK（非废弃的 google.generativeai）。
Gemini 2.0 Flash 提供免费额度：15 RPM / 1500 RPD / 100万 token/天。

关键差异：
- 角色映射：assistant → "model"
- 工具声明使用 genai_types
- system_instruction 独立设置
"""

import time
from typing import Iterator, Optional
from .base import BaseLLMAdapter
from .llm_response import LLMResponse, LLMToolResponse, ToolCall


class GeminiAdapter(BaseLLMAdapter):
    """Google Gemini 适配器（免费默认）"""

    def __init__(self, api_key: str, timeout: int = 60, model: str = "gemini-2.0-flash"):
        super().__init__(api_key=api_key, timeout=timeout, model=model)
        try:
            from google import genai
            self._genai = genai
            self._client = genai.Client(api_key=api_key)
        except ImportError:
            raise ImportError(
                "请安装 google-genai: pip install google-genai\n"
                "Gemini 免费 API Key 获取: https://aistudio.google.com/apikey"
            )

    # === 消息格式转换 ===
    def _convert_messages(self, messages: list[dict]) -> tuple[str, list[dict]]:
        """将 OpenAI 格式转为 Gemini 格式

        Returns: (system_instruction, contents_list)
        """
        system_instruction = ""
        contents = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                system_instruction = content
            elif role == "assistant":
                # 检查是否包含 tool_calls
                tool_calls = msg.get("tool_calls")
                if tool_calls:
                    parts = []
                    if content:
                        parts.append({"text": content})
                    for tc in tool_calls:
                        import json
                        parts.append({
                            "function_call": {
                                "name": tc["function"]["name"],
                                "args": json.loads(tc["function"]["arguments"])
                                if isinstance(tc["function"]["arguments"], str)
                                else tc["function"]["arguments"]
                            }
                        })
                    contents.append({"role": "model", "parts": parts})
                else:
                    contents.append({"role": "model", "parts": [{"text": content}]})
            elif role == "tool":
                # 工具结果
                tool_call_id = msg.get("tool_call_id", "")
                contents.append({
                    "role": "tool",
                    "parts": [{
                        "function_response": {
                            "name": tool_call_id.split("_")[0] if "_" in tool_call_id else "",
                            "response": {"result": content}
                        }
                    }]
                })
            else:  # user
                contents.append({"role": "user", "parts": [{"text": content}]})

        return system_instruction, contents

    def _convert_tools(self, tools: list[dict]) -> list:
        """将 OpenAI Function Calling 工具格式转为 Gemini 格式"""
        from google.genai import types as genai_types

        gemini_tools = []
        for tool_def in tools:
            func = tool_def.get("function", tool_def)
            gemini_tools.append(
                genai_types.FunctionDeclaration(
                    name=func["name"],
                    description=func.get("description", ""),
                    parameters=func.get("parameters", {})
                )
            )
        return [genai_types.Tool(function_declarations=gemini_tools)]

    # === 核心方法 ===
    def invoke(self, messages: list[dict], **kwargs) -> LLMResponse:
        start = time.time()
        system_instruction, contents = self._convert_messages(messages)

        config_kwargs = {}
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction
        if "temperature" in kwargs:
            config_kwargs["temperature"] = kwargs["temperature"]

        response = self._client.models.generate_content(
            model=self.model,
            contents=contents,
            config=self._genai.types.GenerateContentConfig(**config_kwargs) if config_kwargs else None,
        )

        elapsed_ms = int((time.time() - start) * 1000)
        text = response.text or ""

        return LLMResponse(
            content=text,
            model=self.model,
            usage={
                "prompt_tokens": response.usage_metadata.prompt_token_count if hasattr(response, 'usage_metadata') and response.usage_metadata else 0,
                "completion_tokens": response.usage_metadata.candidates_token_count if hasattr(response, 'usage_metadata') and response.usage_metadata else 0,
                "total_tokens": response.usage_metadata.total_token_count if hasattr(response, 'usage_metadata') and response.usage_metadata else 0,
            },
            latency_ms=elapsed_ms,
        )

    def stream_invoke(self, messages: list[dict], **kwargs) -> Iterator[str]:
        system_instruction, contents = self._convert_messages(messages)

        config_kwargs = {}
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction

        response = self._client.models.generate_content_stream(
            model=self.model,
            contents=contents,
            config=self._genai.types.GenerateContentConfig(**config_kwargs) if config_kwargs else None,
        )

        for chunk in response:
            if chunk.text:
                yield chunk.text

    def invoke_with_tools(self, messages: list[dict], tools: list[dict],
                          tool_choice: str = "auto", **kwargs) -> LLMToolResponse:
        start = time.time()
        system_instruction, contents = self._convert_messages(messages)
        gemini_tools = self._convert_tools(tools)

        config_kwargs = {"tools": gemini_tools}
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction

        from google.genai import types as genai_types
        if tool_choice == "required" or tool_choice == "any":
            config_kwargs["tool_config"] = genai_types.ToolConfig(
                function_calling_config=genai_types.FunctionCallingConfig(mode="ANY")
            )

        response = self._client.models.generate_content(
            model=self.model,
            contents=contents,
            config=genai_types.GenerateContentConfig(**config_kwargs),
        )

        elapsed_ms = int((time.time() - start) * 1000)

        # 解析工具调用
        tool_calls = []
        text_content = ""

        if response.candidates:
            candidate = response.candidates[0]
            if candidate.content and candidate.content.parts:
                for part in candidate.content.parts:
                    if part.function_call:
                        import json
                        tool_calls.append(ToolCall(
                            id=f"call_{part.function_call.name}",
                            name=part.function_call.name,
                            arguments=json.dumps(part.function_call.args, ensure_ascii=False)
                        ))
                    elif part.text:
                        text_content += part.text

        return LLMToolResponse(
            content=text_content if text_content else None,
            tool_calls=tool_calls,
            model=self.model,
            usage={
                "total_tokens": response.usage_metadata.total_token_count if hasattr(response, 'usage_metadata') and response.usage_metadata else 0,
            },
            latency_ms=elapsed_ms,
        )
