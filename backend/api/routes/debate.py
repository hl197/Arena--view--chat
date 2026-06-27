"""辩论 API 路由"""

import uuid
import asyncio
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from ..schemas import (
    DebateStartRequest, DebateStartResponse,
    DebateStatusResponse, DebateResultResponse,
    ErrorResponse, UserMessageRequest,
)
from ...core.harness_engine import HarnessEngine, ArenaSession
from ...core.config import ArenaConfig
from ...core.streaming import StreamEvent, StreamEventType, SSEManager
from ...memory.debate_memory import DebateMemory, SessionRecord
from ...adapters.unified_llm import ArenaLLM

router = APIRouter(prefix="/api/debate", tags=["debate"])

# 全局实例（由 main.py 注入）
engine: HarnessEngine = None
memory: DebateMemory = None
sse_manager: SSEManager = None
db = None
active_sessions: dict[str, ArenaSession] = {}
session_queues: dict[str, asyncio.Queue] = {}


def init_debate_routes(_engine: HarnessEngine, _memory: DebateMemory, _sse: SSEManager, _db):
    """初始化路由依赖"""
    global engine, memory, sse_manager, db
    engine = _engine
    memory = _memory
    sse_manager = _sse
    db = _db


@router.post("/start", response_model=DebateStartResponse)
async def start_debate(req: DebateStartRequest, request: Request):
    """发起辩论——返回 session_id 和 SSE 流地址"""
    session_id = f"s_{uuid.uuid4().hex[:12]}"

    # 创建 SSE 队列
    queue = asyncio.Queue()
    session_queues[session_id] = queue

    # 异步启动辩论（不阻塞响应）
    async def stream_callback(event: StreamEvent):
        await queue.put(event)

    async def run_debate():
        try:
            session = await engine.run(
                question=req.question,
                session_id=session_id,
                user_options=req.options,
                num_perspectives=req.num_perspectives,
                debate_rounds=req.debate_rounds,
                stream_callback=stream_callback,
            )
            active_sessions[session_id] = session

            # 保存到内存
            memory.save(SessionRecord(
                session_id=session.id,
                question=session.question,
                user_options=session.user_options,
                perspectives=[
                    {"id": p.id, "name": p.name, "stance": p.stance}
                    for p in session.perspectives
                ],
                arguments=session.arguments,
                debate_transcript=[
                    {
                        "round": t.round,
                        "challenger_name": t.challenger_name,
                        "defender_name": t.defender_name,
                        "challenge": t.challenge,
                        "defense": t.defense,
                        "judge_note": t.judge_note,
                    }
                    for t in session.debate_turns
                ],
                decision_map=session.decision_map,
                total_tokens=session.total_tokens,
                total_time_ms=session.total_time_ms,
                status=session.status,
            ))

            # 保存到 SQLite
            db.save_debate({
                "id": session.id,
                "question": session.question,
                "status": session.status,
                "perspectives": [
                    {"id": p.id, "name": p.name, "stance": p.stance}
                    for p in session.perspectives
                ],
                "arguments": session.arguments,
                "debate_transcript": [
                    {
                        "round": t.round,
                        "challenger_name": t.challenger_name,
                        "defender_name": t.defender_name,
                        "challenge": t.challenge,
                        "defense": t.defense,
                        "judge_note": t.judge_note,
                    }
                    for t in session.debate_turns
                ],
                "decision_map": session.decision_map,
                "total_tokens": session.total_tokens,
                "total_time_ms": session.total_time_ms,
            })
        except Exception as e:
            await queue.put(StreamEvent(
                type=StreamEventType.ERROR,
                data={"code": "DEBATE_ERROR", "message": str(e)}
            ))
        finally:
            await queue.put(None)  # 结束信号
            if session_id in session_queues:
                del session_queues[session_id]

    asyncio.create_task(run_debate())

    return DebateStartResponse(
        session_id=session_id,
        stream_url=f"/api/debate/{session_id}/stream",
        perspectives=[],  # 视角在 SSE 流中动态推送
    )


@router.get("/{session_id}/stream")
async def stream_debate(session_id: str):
    """SSE 流式返回辩论全过程"""
    if session_id not in session_queues:
        raise HTTPException(status_code=404, detail="会话不存在或已结束")

    queue = session_queues[session_id]

    async def event_generator():
        # 发送 session_start
        start_event = StreamEvent(
            type=StreamEventType.SESSION_START,
            data={"session_id": session_id}
        )
        yield start_event.to_sse()

        while True:
            event = await queue.get()
            if event is None:
                break
            yield event.to_sse()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/{session_id}/status", response_model=DebateStatusResponse)
async def get_debate_status(session_id: str):
    """查询辩论状态"""
    if session_id in active_sessions:
        session = active_sessions[session_id]
        return DebateStatusResponse(
            session_id=session_id,
            status=session.status,
            progress=0.5,
        )

    record = memory.get(session_id)
    if record:
        return DebateStatusResponse(
            session_id=session_id,
            status=record.status,
            progress=1.0,
        )

    raise HTTPException(status_code=404, detail="会话不存在")


@router.get("/{session_id}/result", response_model=DebateResultResponse)
async def get_debate_result(session_id: str):
    """获取辩论结果"""
    record = memory.get(session_id)
    if not record:
        raise HTTPException(status_code=404, detail="会话不存在")

    return DebateResultResponse(
        session_id=record.session_id,
        question=record.question,
        status=record.status,
        perspectives=record.perspectives,
        arguments=record.arguments,
        debate_transcript=record.debate_transcript,
        decision_map=record.decision_map,
        total_tokens=record.total_tokens,
        total_time_ms=record.total_time_ms,
    )


@router.post("/{session_id}/message")
async def send_user_message(session_id: str, req: UserMessageRequest):
    """用户在群聊中发送消息——广播给所有 SSE 观众"""
    if session_id not in session_queues:
        raise HTTPException(status_code=404, detail="会话不存在或已结束")

    queue = session_queues[session_id]
    event = StreamEvent(
        type=StreamEventType.USER_MESSAGE,
        data={
            "sender_id": "user",
            "sender_name": "我",
            "content": req.content,
        }
    )
    await queue.put(event)
    return {"status": "sent"}


@router.post("/{session_id}/cancel")
async def cancel_debate(session_id: str):
    """取消正在进行的辩论"""
    if session_id in session_queues:
        await session_queues[session_id].put(None)  # 发送结束信号
        del session_queues[session_id]
        return {"status": "cancelled"}

    raise HTTPException(status_code=404, detail="会话不存在或已结束")
