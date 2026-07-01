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
from .user import get_current_user
from ...core.harness_engine import HarnessEngine, ArenaSession
from ...core.streaming import StreamEvent, StreamEventType, SSEManager
from ...core.config import ArenaConfig
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

    # 额度检查与扣减——必须登录
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="请先登录后再使用辩论功能")

    user_id = user["id"]

    # 用户配置了自己的 API Key → 不限制次数
    llm_config = db.get_llm_config(user_id)
    if not llm_config:
        quota = db.get_quota(user_id)
        if not quota:
            db.init_quota(user_id, tier=user.get("tier", "registered"), daily_limit=5, token_limit=999999)
            quota = db.get_quota(user_id)
        allowed = db.increment_quota(user_id)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=f"今日辩论次数已用完（{quota['daily_debates_used']}/{quota['daily_debates_limit']}）。请明天再来，或配置自己的 API Key 解除限制。"
            )

    # 创建 SSE 队列
    queue = asyncio.Queue()
    session_queues[session_id] = queue

    # 立即写入数据库（status=running），让侧边栏能马上看到进行中的辩论
    try:
        db.save_debate({
            "id": session_id,
            "user_id": user_id,
            "question": req.question,
            "status": "running",
            "perspectives": [],
            "arguments": {},
            "debate_transcript": [],
            "decision_map": "",
            "total_tokens": 0,
            "total_time_ms": 0,
        })
    except Exception:
        pass  # 非致命，不影响辩论执行

    # 异步启动辩论（不阻塞响应）
    async def stream_callback(event: StreamEvent):
        await queue.put(event)

    async def run_debate():
        # 提前创建 session 并注册到 active_sessions，
        # 让 REST API 在辩论进行中就能查到 perspectives + conversation_history
        session = ArenaSession(
            id=session_id,
            user_id=user_id,
            question=req.question,
            user_options=req.options or [],
        )
        active_sessions[session_id] = session

        try:
            session = await engine.run(
                question=req.question,
                session_id=session_id,
                user_id=user_id,
                user_options=req.options,
                num_perspectives=req.num_perspectives,
                debate_rounds=req.debate_rounds,
                stream_callback=stream_callback,
                session=session,  # 传入预创建的 session，engine 直接修改它
            )

            # 保存到内存
            memory.save(SessionRecord(
                session_id=session.id,
                user_id=user_id,
                question=session.question,
                user_options=session.user_options,
                perspectives=[
                    {"id": p.id, "name": p.name, "stance": p.stance}
                    for p in session.perspectives
                ],
                arguments=session.arguments,
                debate_transcript=[
                    {
                        "round": h.get("round", 0),
                        "speaker": h.get("speaker", ""),
                        "speaker_id": h.get("speaker_id", ""),
                        "text": h.get("text", ""),
                    }
                    for h in session.conversation_history
                ] if session.conversation_history else [],
                decision_map=session.decision_map,
                total_tokens=session.total_tokens,
                total_time_ms=session.total_time_ms,
                status=session.status,
            ))

            # 保存到 SQLite（非致命——失败不影响辩论结果）
            try:
                db.save_debate({
                    "id": session.id,
                    "user_id": user_id,
                    "question": session.question,
                    "status": session.status,
                    "perspectives": [
                        {"id": p.id, "name": p.name, "stance": p.stance}
                        for p in session.perspectives
                    ],
                    "arguments": session.arguments,
                    "debate_transcript": [
                        {
                            "round": h.get("round", 0),
                            "speaker": h.get("speaker", ""),
                            "speaker_id": h.get("speaker_id", ""),
                            "text": h.get("text", ""),
                        }
                        for h in session.conversation_history
                    ] if session.conversation_history else [],
                    "decision_map": session.decision_map,
                    "total_tokens": session.total_tokens,
                    "total_time_ms": session.total_time_ms,
                })
            except Exception as db_err:
                import sys
                print(f"   ⚠️  数据库保存失败（非致命）: {db_err}", file=sys.stderr, flush=True)

            # token 消耗不单独追踪，仅统计辩论次数
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
        raise HTTPException(status_code=404, detail="这个会话已经结束了")

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
async def get_debate_status(session_id: str, request: Request):
    """查询辩论状态——活跃会话优先，历史记录 DB 降级（需登录，仅本人）"""
    user = await get_current_user(request)
    user_id = user["id"] if user else None

    if session_id in active_sessions:
        session = active_sessions[session_id]
        # 活跃会话仅创建者可查
        if user_id and getattr(session, 'user_id', None) and session.user_id != user_id:
            raise HTTPException(status_code=404, detail="这条记录找不到了")
        return DebateStatusResponse(
            session_id=session_id,
            status=session.status,
            progress=0.5,
        )

    record = memory.get(session_id)
    if record:
        if user_id and getattr(record, 'user_id', 'anonymous') != user_id:
            raise HTTPException(status_code=404, detail="这条记录找不到了")
        return DebateStatusResponse(
            session_id=session_id,
            status=record.status,
            progress=1.0,
        )

    # DB 降级
    if db:
        db_record = db.get_debate(session_id)
        if db_record:
            if user_id and db_record.get("user_id", "anonymous") != user_id:
                raise HTTPException(status_code=404, detail="这条记录找不到了")
            return DebateStatusResponse(
                session_id=session_id,
                status=db_record.get("status", "completed"),
                progress=1.0,
            )

    raise HTTPException(status_code=404, detail="这条记录找不到了")


@router.get("/{session_id}/result", response_model=DebateResultResponse)
async def get_debate_result(session_id: str, request: Request):
    """获取辩论结果——活跃会话优先 → 内存 → DB 降级（需登录，仅本人）"""
    user = await get_current_user(request)
    user_id = user["id"] if user else None

    # 1. 活跃会话（进行中的辩论，含最新 perspectives + conversation_history）
    active = active_sessions.get(session_id)
    if active:
        if user_id and active.user_id and active.user_id != user_id:
            raise HTTPException(status_code=404, detail="这条记录找不到了")
        return DebateResultResponse(
            session_id=active.id,
            question=active.question,
            status=active.status,
            perspectives=[
                {"id": p.id, "name": p.name, "stance": p.stance}
                for p in active.perspectives
            ],
            arguments=active.arguments,
            debate_transcript=active.conversation_history if active.conversation_history else [],
            decision_map=active.decision_map,
            total_tokens=active.total_tokens,
            total_time_ms=active.total_time_ms,
        )

    # 2. 内存（已完成的辩论）
    record = memory.get(session_id)
    if record:
        if user_id and getattr(record, 'user_id', 'anonymous') != user_id:
            raise HTTPException(status_code=404, detail="这条记录找不到了")
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

    # 3. DB 降级
    if db:
        db_record = db.get_debate(session_id)
        if db_record:
            if user_id and db_record.get("user_id", "anonymous") != user_id:
                raise HTTPException(status_code=404, detail="这条记录找不到了")
            return DebateResultResponse(
                session_id=db_record.get("id", ""),
                question=db_record.get("question", ""),
                status=db_record.get("status", "completed"),
                perspectives=db_record.get("perspectives", []),
                arguments=db_record.get("arguments", {}),
                debate_transcript=db_record.get("debate_transcript", []),
                decision_map=db_record.get("decision_map", ""),
                total_tokens=db_record.get("total_tokens", 0),
                total_time_ms=db_record.get("total_time_ms", 0),
            )

    raise HTTPException(status_code=404, detail="这条记录找不到了")


@router.post("/{session_id}/message")
async def send_user_message(session_id: str, req: UserMessageRequest, request: Request):
    """用户在群聊中发送消息——仅会话创建者可发送"""
    user = await get_current_user(request)
    user_id = user["id"] if user else None

    if session_id not in session_queues:
        raise HTTPException(status_code=404, detail="这个会话已经结束了")

    # 检查所有权
    session = active_sessions.get(session_id)
    if session and user_id and session.user_id and session.user_id != user_id:
        raise HTTPException(status_code=404, detail="这个会话已经结束了")

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
async def cancel_debate(session_id: str, request: Request):
    """取消正在进行的辩论——仅创建者可取消"""
    user = await get_current_user(request)
    user_id = user["id"] if user else None

    if session_id not in session_queues:
        raise HTTPException(status_code=404, detail="这个会话已经结束了")

    # 检查所有权
    session = active_sessions.get(session_id)
    if session and user_id and session.user_id and session.user_id != user_id:
        raise HTTPException(status_code=404, detail="这个会话已经结束了")

    await session_queues[session_id].put(None)  # 发送结束信号
    del session_queues[session_id]
    return {"status": "cancelled"}
