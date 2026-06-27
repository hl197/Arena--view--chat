"""HistoryManager 对话历史管理测试"""

import pytest
from backend.context.history import HistoryManager


class TestHistoryManagerBasic:
    """基本操作测试"""

    def test_initially_empty(self):
        hm = HistoryManager()
        assert hm.get_history() == []
        assert hm.get_messages() == []

    def test_append_message(self):
        hm = HistoryManager()
        hm.append({"role": "user", "content": "你好"})
        assert len(hm.get_history()) == 1

    def test_append_multiple(self):
        hm = HistoryManager()
        hm.append({"role": "user", "content": "问题1"})
        hm.append({"role": "assistant", "content": "回答1"})
        hm.append({"role": "user", "content": "问题2"})
        assert len(hm.get_history()) == 3

    def test_clear(self):
        hm = HistoryManager()
        hm.append({"role": "user", "content": "test"})
        hm.clear()
        assert hm.get_history() == []
        assert hm.get_messages() == []

    def test_get_history_returns_copy(self):
        """get_history 返回副本，修改不影响内部状态"""
        hm = HistoryManager()
        hm.append({"role": "user", "content": "test"})
        history = hm.get_history()
        history.append({"role": "user", "content": "extra"})
        assert len(hm.get_history()) == 1  # 内部不受影响


class TestHistoryManagerCompression:
    """压缩测试"""

    def test_should_compress(self):
        hm = HistoryManager(compression_threshold=0.5)
        # token_count > context_window * 0.5 时应压缩
        assert hm.should_compress(60, 100) is True

    def test_should_not_compress(self):
        hm = HistoryManager(compression_threshold=0.8)
        assert hm.should_compress(30, 100) is False

    def test_simple_compress(self):
        """简单压缩：保留最近轮次"""
        hm = HistoryManager(min_retain_rounds=1)
        hm.append({"role": "user", "content": "问题1"})
        hm.append({"role": "assistant", "content": "回答1"})
        hm.append({"role": "user", "content": "问题2"})
        hm.append({"role": "assistant", "content": "回答2"})

        hm.compress_simple(keep_recent=1)

        history = hm.get_history()
        # 保留的是最后一轮
        assert len(history) == 2
        assert history[0]["content"] == "问题2"
        assert history[1]["content"] == "回答2"

    def test_simple_compress_with_tools(self):
        """压缩含工具调用的历史"""
        hm = HistoryManager(min_retain_rounds=1)
        hm.append({"role": "user", "content": "问题1"})
        hm.append({"role": "assistant", "content": "调用工具"})
        hm.append({"role": "tool", "content": "工具结果"})
        hm.append({"role": "user", "content": "问题2"})
        hm.append({"role": "assistant", "content": "回答2"})

        hm.compress_simple(keep_recent=1)

        history = hm.get_history()
        # 保留最后一轮（2条消息）
        assert len(history) == 2

    def test_compression_generates_summary(self):
        hm = HistoryManager(min_retain_rounds=1)
        hm.append({"role": "user", "content": "问题1"})
        hm.append({"role": "assistant", "content": "回答1"})
        hm.append({"role": "user", "content": "问题2"})
        hm.append({"role": "assistant", "content": "回答2"})

        hm.compress_simple(keep_recent=1)

        messages = hm.get_messages()
        # 第一条消息是压缩摘要
        assert messages[0]["role"] == "system"
        assert "已压缩" in messages[0]["content"]

    def test_no_compress_when_few_rounds(self):
        """轮次不够时不压缩"""
        hm = HistoryManager(min_retain_rounds=5)
        hm.append({"role": "user", "content": "问题1"})
        hm.append({"role": "assistant", "content": "回答1"})

        hm.compress_simple()

        # 只有 1 轮，不应压缩
        history = hm.get_history()
        assert len(history) == 2


class TestHistoryRoundDetection:
    """轮次检测测试"""

    def test_find_rounds_basic(self):
        hm = HistoryManager()
        hm.append({"role": "user", "content": "q1"})
        hm.append({"role": "assistant", "content": "a1"})
        hm.append({"role": "user", "content": "q2"})
        hm.append({"role": "assistant", "content": "a2"})

        rounds = hm._find_rounds()
        assert len(rounds) == 2  # 2 个 user 消息 = 2 轮

    def test_find_rounds_single(self):
        hm = HistoryManager()
        hm.append({"role": "user", "content": "only question"})

        rounds = hm._find_rounds()
        assert len(rounds) == 1
