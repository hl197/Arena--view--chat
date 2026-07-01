"""辩论记忆系统

存储每次辩论会话的完整记录。
MVP 阶段用内存 dict，第 3 周迁移到 SQLite。
"""

import json
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SessionRecord:
    """单次辩论会话记录"""
    session_id: str
    question: str
    user_id: str = "anonymous"
    user_options: list[str] = field(default_factory=list)
    perspectives: list[dict] = field(default_factory=list)
    arguments: dict[str, str] = field(default_factory=dict)
    debate_transcript: list[dict] = field(default_factory=list)
    decision_map: str = ""
    total_tokens: int = 0
    total_time_ms: int = 0
    status: str = "completed"
    created_at: float = field(default_factory=time.time)


class DebateMemory:
    """辩论记忆管理器——存储和检索会话"""

    def __init__(self):
        self._sessions: dict[str, SessionRecord] = {}
        self._user_sessions: dict[str, list[str]] = {}  # user_id -> [session_ids]

    def save(self, record: SessionRecord):
        """保存会话"""
        self._sessions[record.session_id] = record

    def get(self, session_id: str) -> Optional[SessionRecord]:
        """获取会话"""
        return self._sessions.get(session_id)

    def list_by_user(self, user_id: str, limit: int = 20) -> list[SessionRecord]:
        """列出用户的历史会话"""
        ids = self._user_sessions.get(user_id, [])[-limit:]
        return [self._sessions[sid] for sid in ids if sid in self._sessions]

    def delete(self, session_id: str):
        """删除会话"""
        if session_id in self._sessions:
            del self._sessions[session_id]

    def to_json(self, session_id: str) -> str:
        """导出为 JSON"""
        record = self._sessions.get(session_id)
        if not record:
            return "{}"
        data = {
            "session_id": record.session_id,
            "question": record.question,
            "perspectives": record.perspectives,
            "arguments": record.arguments,
            "debate_transcript": record.debate_transcript,
            "decision_map": record.decision_map,
            "total_tokens": record.total_tokens,
            "total_time_ms": record.total_time_ms,
            "status": record.status,
        }
        return json.dumps(data, ensure_ascii=False, indent=2)
