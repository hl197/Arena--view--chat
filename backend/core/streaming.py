"""SSE 流式事件系统

ArenaView 使用 SSE（Server-Sent Events）向前端推送辩论全流程。
所有事件通过单一 SSE 端点推送，用 event type 区分阶段。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any
import json
import time


class StreamEventType(str, Enum):
    """SSE 事件类型"""
    # 会话级
    SESSION_START = "session_start"

    # 阶段切换
    PHASE = "phase"

    # 视角生成
    PERSPECTIVE_READY = "perspective_ready"

    # 自我介绍（Phase 1.5）
    SELF_INTRO = "self_intro"               # data: {perspective_name, perspective_id, text}

    # Agent 状态
    AGENT_STATUS = "agent_status"
    ARGUMENT_CHUNK = "argument_chunk"
    ARGUMENT_COMPLETE = "argument_complete"

    # 研究阶段完整内容流（替代截断的 ARGUMENT_COMPLETE summary）
    RESEARCH_CHUNK = "research_chunk"       # data: {perspective_name, perspective_id, text, is_final: bool}

    # 辩论（旧版，保留向后兼容）
    DEBATE_TURN_START = "debate_turn_start"
    DEBATE_CHUNK = "debate_chunk"
    DEBATE_TURN_END = "debate_turn_end"

    # 群聊轮次（新版 Round-Based Multi-Agent Group Chat）
    ROUND_START = "round_start"         # 新一轮开始, data: {round_number, total_rounds, description}
    ROUND_END = "round_end"             # 本轮结束, data: {round_number}
    SPEECH_CHUNK = "speech_chunk"       # 发言片段, data: {perspective_id, perspective_name, text, is_final}
    SPEECH_END = "speech_end"           # 发言结束, data: {perspective_id, perspective_name}

    # 裁判合成
    SYNTHESIS_START = "synthesis_start"
    TRADEOFF_UPDATE = "tradeoff_update"
    DECISION_MAP_CHUNK = "decision_map_chunk"
    SELF_REFLECTION = "self_reflection"

    # 结束
    COMPLETE = "complete"
    ERROR = "error"

    # 用户参与
    USER_MESSAGE = "user_message"

    # 心跳
    HEARTBEAT = "heartbeat"


@dataclass
class StreamEvent:
    """流式事件"""
    type: StreamEventType
    timestamp: float = field(default_factory=time.time)
    data: dict = field(default_factory=dict)

    def to_sse(self) -> str:
        """转为 SSE 格式"""
        payload = json.dumps({
            "type": self.type.value,
            "timestamp": self.timestamp,
            **self.data
        }, ensure_ascii=False)
        return f"event: {self.type.value}\ndata: {payload}\n\n"


class SSEManager:
    """管理 SSE 连接和事件推送"""

    def __init__(self):
        self._queues: dict[str, "asyncio.Queue"] = {}

    async def create_session(self, session_id: str) -> "asyncio.Queue":
        import asyncio
        queue = asyncio.Queue()
        self._queues[session_id] = queue
        return queue

    async def send(self, session_id: str, event: StreamEvent):
        if session_id in self._queues:
            await self._queues[session_id].put(event)

    async def send_error(self, session_id: str, code: str, message: str):
        await self.send(session_id, StreamEvent(
            type=StreamEventType.ERROR,
            data={"code": code, "message": message}
        ))

    async def close_session(self, session_id: str):
        if session_id in self._queues:
            await self._queues[session_id].put(None)  # 结束信号
            del self._queues[session_id]
