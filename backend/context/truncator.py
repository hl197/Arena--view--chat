"""Observation 截断器

参考 HelloAgents 的 ObservationTruncator：
支持 head / tail / head_tail 三种截断方向。
"""


class ObservationTruncator:
    """工具输出截断器"""

    def __init__(self, max_lines: int = 2000, max_bytes: int = 51200,
                 direction: str = "head"):
        self.max_lines = max_lines
        self.max_bytes = max_bytes
        self.direction = direction

    def truncate(self, text: str) -> tuple[str, bool]:
        """截断文本——返回 (截断后文本, 是否截断)"""
        truncated = False

        # 1. 按行截断
        lines = text.split("\n")
        if len(lines) > self.max_lines:
            truncated = True
            if self.direction == "head":
                text = "\n".join(lines[:self.max_lines])
            elif self.direction == "tail":
                text = "\n".join(lines[-self.max_lines:])
            else:  # head_tail
                half = self.max_lines // 2
                text = "\n".join(lines[:half]) + "\n...\n" + "\n".join(lines[-half:])

        # 2. 按字节截断
        data = text.encode("utf-8")
        if len(data) > self.max_bytes:
            truncated = True
            if self.direction == "head":
                text = data[:self.max_bytes].decode("utf-8", errors="ignore")
            elif self.direction == "tail":
                text = data[-self.max_bytes:].decode("utf-8", errors="ignore")
            else:
                half = self.max_bytes // 2
                text = (data[:half].decode("utf-8", errors="ignore") +
                        "\n...\n" +
                        data[-half:].decode("utf-8", errors="ignore"))

        return text, truncated

    def truncate_with_note(self, text: str) -> str:
        """截断并附加说明"""
        result, was_truncated = self.truncate(text)
        if was_truncated:
            original = len(text.encode("utf-8"))
            result += f"\n\n[输出已截断：原始 {original} 字节，显示 {len(result.encode('utf-8'))} 字节]"
        return result
