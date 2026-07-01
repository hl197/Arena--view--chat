"""历史辩论 API 路由"""

from fastapi import APIRouter, HTTPException, Request
from ..schemas import HistoryItem, HistoryListResponse
from ...memory.debate_memory import DebateMemory
from .user import get_current_user

router = APIRouter(prefix="/api", tags=["history"])

# 由 main.py 注入
memory: DebateMemory = None
db = None


def init_history_routes(_memory: DebateMemory, _db):
    global memory, db
    memory = _memory
    db = _db


@router.get("/history", response_model=HistoryListResponse)
async def list_history(request: Request, page: int = 1, page_size: int = 10):
    """列出当前用户的历史辩论——必须登录"""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="请先登录，登录后才能看历史记录")

    user_id = user["id"]

    # 从 DB 获取该用户的历史
    items = db.list_debates(user_id=user_id, limit=page_size, offset=(page - 1) * page_size) if db else []

    # 合并内存中的记录（也按用户过滤）
    mem_items = [
        r for r in memory._sessions.values()
        if getattr(r, 'user_id', None) == user_id
    ]
    mem_items.sort(key=lambda r: r.created_at, reverse=True)

    if not items:
        total = len(mem_items)
        page_items = mem_items[(page - 1) * page_size: page * page_size]
        return HistoryListResponse(
            items=[
                HistoryItem(
                    session_id=r.session_id,
                    question=r.question[:100],
                    status=r.status,
                    perspectives_count=len(r.perspectives),
                    created_at=str(r.created_at),
                )
                for r in page_items
            ],
            total=total,
            page=page,
        )

    return HistoryListResponse(
        items=[
            HistoryItem(
                session_id=it["id"],
                question=it.get("question", "")[:100],
                status=it.get("status", "completed"),
                perspectives_count=it.get("perspectives_count", 0),
                created_at=str(it.get("created_at", "")),
            )
            for it in items
        ],
        total=len(items),
        page=page,
    )


def _format_debate_detail(record) -> dict:
    """统一格式化辩论详情——兼容内存 SessionRecord 和 DB dict"""
    if isinstance(record, dict):
        return {
            "session_id": record.get("id", ""),
            "question": record.get("question", ""),
            "perspectives": record.get("perspectives", []),
            "arguments": record.get("arguments", {}),
            "debate_transcript": record.get("debate_transcript", []),
            "decision_map": record.get("decision_map", ""),
            "total_tokens": record.get("total_tokens", 0),
            "total_time_ms": record.get("total_time_ms", 0),
            "status": record.get("status", "completed"),
        }
    # SessionRecord dataclass
    return {
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


@router.get("/history/{session_id}")
async def get_history_detail(session_id: str, request: Request):
    """获取历史辩论详情——需登录且为本人记录"""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")

    user_id = user["id"]

    record = memory.get(session_id)
    if record:
        if getattr(record, 'user_id', 'anonymous') != user_id:
            raise HTTPException(status_code=404, detail="这条记录找不到了")
        return _format_debate_detail(record)

    # DB 降级
    if db:
        db_record = db.get_debate(session_id)
        if db_record:
            if db_record.get("user_id", "anonymous") != user_id:
                raise HTTPException(status_code=404, detail="这条记录找不到了")
            return _format_debate_detail(db_record)

    raise HTTPException(status_code=404, detail="这条记录找不到了")


@router.delete("/history/{session_id}")
async def delete_history(session_id: str, request: Request):
    """删除历史辩论——需登录且为本人记录"""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")

    user_id = user["id"]

    # 验证所有权——不存在的记录和别人的记录都返回 404
    record = memory.get(session_id)
    if record:
        if getattr(record, 'user_id', 'anonymous') != user_id:
            raise HTTPException(status_code=404, detail="这条记录找不到了")

    db_record = db.get_debate(session_id) if db else None
    if db_record and db_record.get("user_id", "anonymous") != user_id:
        raise HTTPException(status_code=404, detail="这条记录找不到了")

    # 记录不存在（内存和 DB 都没有）
    if not record and not db_record:
        raise HTTPException(status_code=404, detail="这条记录找不到了")

    import sys
    # 删除内存中的记录
    memory.delete(session_id)
    # 删除 DB 中的记录
    if db:
        try:
            db.delete_debate(session_id)
            print(f"   🗑️  已从数据库删除: {session_id}", file=sys.stderr, flush=True)
        except Exception as e:
            print(f"   ⚠️  数据库删除失败: {session_id} — {e}", file=sys.stderr, flush=True)
    else:
        print(f"   ⚠️  数据库未初始化，无法删除: {session_id}", file=sys.stderr, flush=True)
    return {"status": "deleted", "session_id": session_id}
