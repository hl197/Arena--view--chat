"""Token 计数器

参考 HelloAgents 的三层降级：
1. tiktoken（精确）
2. cl100k_base（通用）
3. char/4（粗略估算）
"""


class TokenCounter:
    """Token 计数器——三级降级"""

    def __init__(self, model: str = "gpt-4"):
        self.model = model
        self._encoder = self._get_encoder()

    def _get_encoder(self):
        """获取编码器——三级降级"""
        # 1. tiktoken
        try:
            import tiktoken
            return tiktoken.encoding_for_model(self.model)
        except (ImportError, KeyError):
            pass

        # 2. cl100k_base
        try:
            import tiktoken
            return tiktoken.get_encoding("cl100k_base")
        except (ImportError, KeyError):
            pass

        # 3. 无编码器——用 char/4 估算
        return None

    def count(self, text: str) -> int:
        """计算文本的 Token 数"""
        if self._encoder:
            return len(self._encoder.encode(text))
        return len(text) // 4

    def count_messages(self, messages: list[dict]) -> int:
        """计算消息列表的 Token 数"""
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total += self.count(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and "text" in part:
                        total += self.count(part["text"])
        return total
