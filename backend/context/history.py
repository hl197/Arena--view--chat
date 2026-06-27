"""对话历史管理器

参考 HelloAgents 的 HistoryManager：
- append-only 设计（KV Cache 友好）
- 按轮次压缩（保留最近 N 轮）
- 简单/智能两种压缩模式
"""

from dataclasses import dataclass, field
from typing import Optional
import re


@dataclass
class HistoryManager:
    """对话历史管理器"""

    min_retain_rounds: int = 5
    compression_threshold: float = 0.8

    _history: list[dict] = field(default_factory=list)
    _compressed_summary: str = ""

    def append(self, message: dict):
        """追加消息"""
        self._history.append(message)

    def get_history(self) -> list[dict]:
        """获取完整历史"""
        return list(self._history)

    def clear(self):
        """清空历史"""
        self._history.clear()
        self._compressed_summary = ""

    def get_messages(self) -> list[dict]:
        """获取消息列表（含压缩摘要）"""
        if self._compressed_summary:
            summary_msg = {"role": "system", "content": f"[历史摘要]\n{self._compressed_summary}"}
            return [summary_msg] + self._history
        return list(self._history)

    def should_compress(self, token_count: int, context_window: int) -> bool:
        """判断是否需要压缩（超过阈值触发）"""
        return token_count > int(context_window * self.compression_threshold)

    def compress_simple(self, keep_recent: int = None):
        """简单压缩——保留最近轮次，统计旧轮次"""
        if keep_recent is None:
            keep_recent = self.min_retain_rounds

        rounds = self._find_rounds()
        if len(rounds) <= keep_recent:
            return

        old_rounds = rounds[:-keep_recent]
        self._history = self._history[
            sum(len(r) for r in old_rounds):
        ]

        # 生成摘要
        user_count = sum(1 for m in sum(old_rounds, []) if m["role"] == "user")
        assistant_count = sum(1 for m in sum(old_rounds, []) if m["role"] == "assistant")
        tool_count = sum(1 for m in sum(old_rounds, []) if m["role"] == "tool")
        self._compressed_summary = (
            f"已压缩 {len(old_rounds)} 轮对话 ({user_count} 用户消息, "
            f"{assistant_count} AI 回复, {tool_count} 工具调用)。"
        )

    def _find_rounds(self) -> list[list[dict]]:
        """按 user 消息分轮次"""
        rounds = []
        current_round = []
        for msg in self._history:
            if msg["role"] == "user" and current_round:
                rounds.append(current_round)
                current_round = []
            current_round.append(msg)
        if current_round:
            rounds.append(current_round)
        return rounds
