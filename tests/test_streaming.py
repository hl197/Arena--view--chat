"""StreamEvent + SSEManager 流式事件系统测试"""

import pytest
import asyncio
from backend.core.streaming import StreamEvent, StreamEventType, SSEManager


class TestStreamEventType:
    """事件类型枚举测试"""

    def test_all_types_defined(self):
        types = {e.value for e in StreamEventType}
        assert "session_start" in types
        assert "phase" in types
        assert "perspective_ready" in types
        assert "agent_status" in types
        assert "argument_chunk" in types
        assert "argument_complete" in types
        assert "debate_turn_start" in types
        assert "debate_chunk" in types
        assert "debate_turn_end" in types
        assert "synthesis_start" in types
        assert "tradeoff_update" in types
        assert "decision_map_chunk" in types
        assert "self_reflection" in types
        assert "complete" in types
        assert "error" in types
        assert "heartbeat" in types

    def test_total_count(self):
        assert len(list(StreamEventType)) == 16


class TestStreamEvent:
    """流式事件创建和格式化测试"""

    def test_create_event(self):
        event = StreamEvent(
            type=StreamEventType.PHASE,
            data={"phase": "research", "status": "running"}
        )
        assert event.type == StreamEventType.PHASE
        assert event.data["phase"] == "research"
        assert event.timestamp > 0

    def test_default_data(self):
        event = StreamEvent(type=StreamEventType.HEARTBEAT)
        assert event.data == {}

    def test_to_sse_format(self):
        event = StreamEvent(
            type=StreamEventType.AGENT_STATUS,
            data={"name": "风险厌恶者", "status": "thinking"}
        )
        sse = event.to_sse()
        assert sse.startswith("event: agent_status")
        assert "data: " in sse
        assert "风险厌恶者" in sse
        assert sse.endswith("\n\n")

    def test_sse_contains_timestamp(self):
        event = StreamEvent(type=StreamEventType.COMPLETE, data={})
        sse = event.to_sse()
        assert '"type": "complete"' in sse
        assert '"timestamp"' in sse

    def test_error_event(self):
        event = StreamEvent(
            type=StreamEventType.ERROR,
            data={"code": "TIMEOUT", "message": "超时"}
        )
        sse = event.to_sse()
        assert "event: error" in sse
        assert "TIMEOUT" in sse


class TestSSEManager:
    """SSE 连接管理测试"""

    @pytest.mark.asyncio
    async def test_create_session(self):
        mgr = SSEManager()
        queue = await mgr.create_session("session-1")
        assert queue is not None
        assert "session-1" in mgr._queues

    @pytest.mark.asyncio
    async def test_send_event(self):
        mgr = SSEManager()
        queue = await mgr.create_session("session-1")

        event = StreamEvent(type=StreamEventType.PHASE, data={"phase": "test"})
        await mgr.send("session-1", event)

        # 从队列取出
        received = await asyncio.wait_for(queue.get(), timeout=1)
        assert received.type == StreamEventType.PHASE

    @pytest.mark.asyncio
    async def test_send_error(self):
        mgr = SSEManager()
        queue = await mgr.create_session("session-1")
        await mgr.send_error("session-1", "TEST_ERROR", "测试错误")

        received = await asyncio.wait_for(queue.get(), timeout=1)
        assert received.type == StreamEventType.ERROR
        assert received.data["code"] == "TEST_ERROR"

    @pytest.mark.asyncio
    async def test_send_to_nonexistent_session(self):
        """发给不存在 session 不报错"""
        mgr = SSEManager()
        event = StreamEvent(type=StreamEventType.HEARTBEAT)
        await mgr.send("no-such-session", event)  # 不应抛异常

    @pytest.mark.asyncio
    async def test_close_session(self):
        mgr = SSEManager()
        await mgr.create_session("session-1")
        await mgr.close_session("session-1")
        assert "session-1" not in mgr._queues

    @pytest.mark.asyncio
    async def test_multiple_sessions(self):
        mgr = SSEManager()
        q1 = await mgr.create_session("s1")
        q2 = await mgr.create_session("s2")

        # 发到 s1
        event = StreamEvent(type=StreamEventType.HEARTBEAT)
        await mgr.send("s1", event)

        # q1 收到，q2 没收到
        r1 = await asyncio.wait_for(q1.get(), timeout=1)
        assert r1.type == StreamEventType.HEARTBEAT
        assert q2.empty()
