"""ObservationTruncator 截断器测试"""

import pytest
from backend.context.truncator import ObservationTruncator


class TestObservationTruncatorHead:
    """head 方向截断测试"""

    def test_no_truncation_needed(self):
        t = ObservationTruncator(max_lines=10, direction="head")
        text, was_truncated = t.truncate("line1\nline2\nline3")
        assert was_truncated is False
        assert text == "line1\nline2\nline3"

    def test_line_truncation(self):
        t = ObservationTruncator(max_lines=3, direction="head")
        text = "\n".join(f"line{i}" for i in range(10))
        result, was_truncated = t.truncate(text)
        assert was_truncated is True
        assert len(result.split("\n")) == 3
        assert "line0" in result
        assert "line2" in result
        assert "line9" not in result

    def test_byte_truncation(self):
        """字节数超限时截断"""
        t = ObservationTruncator(max_lines=1000, max_bytes=20, direction="head")
        text = "A" * 100  # 100 bytes
        result, was_truncated = t.truncate(text)
        assert was_truncated is True
        assert len(result.encode("utf-8")) <= 20

    def test_single_line(self):
        t = ObservationTruncator(max_lines=5, direction="head")
        text, was_truncated = t.truncate("just one line")
        assert was_truncated is False
        assert text == "just one line"


class TestObservationTruncatorTail:
    """tail 方向截断测试"""

    def test_line_tail_truncation(self):
        t = ObservationTruncator(max_lines=3, direction="tail")
        text = "\n".join(f"line{i}" for i in range(10))
        result, was_truncated = t.truncate(text)
        assert was_truncated is True
        lines = result.split("\n")
        assert len(lines) == 3
        assert "line7" in result
        assert "line9" in result
        assert "line0" not in result

    def test_byte_tail_truncation(self):
        t = ObservationTruncator(max_lines=1000, max_bytes=10, direction="tail")
        text = "0123456789ABCDEF"  # 16 bytes
        result, was_truncated = t.truncate(text)
        assert was_truncated is True
        # tail 保留最后 10 字节
        assert len(result.encode("utf-8")) <= 10


class TestObservationTruncatorHeadTail:
    """head_tail 方向截断测试"""

    def test_line_head_tail(self):
        t = ObservationTruncator(max_lines=4, direction="head_tail")
        lines = [f"line{i}" for i in range(20)]
        text = "\n".join(lines)
        result, was_truncated = t.truncate(text)
        assert was_truncated is True
        assert "..." in result  # 分隔符
        assert "line0" in result  # 头部
        assert "line19" in result  # 尾部

    def test_byte_head_tail(self):
        t = ObservationTruncator(max_bytes=30, direction="head_tail")
        text = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"  # 36 bytes
        result, was_truncated = t.truncate(text)
        assert was_truncated is True
        assert "..." in result


class TestTruncateWithNote:
    """truncate_with_note 测试"""

    def test_truncated_adds_note(self):
        t = ObservationTruncator(max_lines=2, direction="head")
        text = "\n".join(f"line{i}" for i in range(10))
        result = t.truncate_with_note(text)
        assert "已截断" in result

    def test_not_truncated_no_note(self):
        t = ObservationTruncator(max_lines=100, direction="head")
        result = t.truncate_with_note("short text")
        assert "已截断" not in result

    def test_custom_max_lines(self):
        t = ObservationTruncator(max_lines=1)
        text = "a\nb\nc"
        result = t.truncate_with_note(text)
        assert "已截断" in result
