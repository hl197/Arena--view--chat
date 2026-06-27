"""TokenCounter 三级降级计数测试"""

import pytest
from backend.context.token_counter import TokenCounter


class TestTokenCounterFallback:
    """无 tiktoken 时的 char/4 估算"""

    def test_empty_string(self):
        tc = TokenCounter()
        assert tc.count("") == 0

    def test_short_text(self):
        tc = TokenCounter()
        # char/4: 8 chars → 2 tokens
        assert tc.count("12345678") == 2

    def test_long_text(self):
        tc = TokenCounter()
        # char/4: 40 chars → 10 tokens
        assert tc.count("a" * 40) == 10

    def test_chinese_text(self):
        """中文字符计数"""
        tc = TokenCounter()
        # 中文字符也算一个 char
        result = tc.count("你好世界")
        assert result == 1  # 4 chars / 4 = 1


class TestTokenCounterMessages:
    """消息列表计数测试"""

    def test_simple_messages(self):
        tc = TokenCounter()
        messages = [
            {"role": "system", "content": "你是助手"},
            {"role": "user", "content": "你好"},
        ]
        count = tc.count_messages(messages)
        # "你是助手" (4) + "你好" (2) = 6 chars → 1 or 2 tokens
        assert count > 0

    def test_empty_messages(self):
        tc = TokenCounter()
        assert tc.count_messages([]) == 0

    def test_message_missing_content(self):
        tc = TokenCounter()
        messages = [{"role": "system"}]  # 无 content
        assert tc.count_messages(messages) == 0

    def test_multipart_content(self):
        """多模态消息（content 为 list 的情况）"""
        tc = TokenCounter()
        messages = [
            {"role": "user", "content": [
                {"type": "text", "text": "hello"},
                {"type": "image_url", "image_url": {"url": "..."}},
            ]},
        ]
        count = tc.count_messages(messages)
        # "hello" = 5 chars → 1 token
        assert count > 0

    def test_multipart_no_text(self):
        tc = TokenCounter()
        messages = [
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": "..."}},
            ]},
        ]
        assert tc.count_messages(messages) == 0


class TestTokenCounterWithModel:
    """指定模型测试"""

    def test_different_model(self):
        tc = TokenCounter(model="gpt-3.5-turbo")
        # 无 tiktoken 时应降级到 char/4
        assert tc.count("test text here") > 0
