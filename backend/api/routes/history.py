"""历史辩论 API 路由"""

from fastapi import APIRouter, HTTPException
from ..schemas import HistoryItem, HistoryListResponse
from ...memory.debate_memory import DebateMemory

router = APIRouter(prefix="/api", tags=["history"])

# 由 main.py 注入
memory: DebateMemory = None
db = None


def init_history_routes(_memory: DebateMemory, _db):
    global memory, db
    memory = _memory
    db = _db


@router.get("/history", response_model=HistoryListResponse)
async def list_history(page: int = 1, page_size: int = 10):
    """列出历史辩论——内存优先，降级 DB"""
    # 从 DB 获取
    items = db.list_debates(limit=page_size, offset=(page - 1) * page_size) if db else []

    # 合并内存中的记录
    mem_items = list(memory._sessions.values())
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


@router.get("/history/{session_id}")
async def get_history_detail(session_id: str):
    """获取历史辩论详情"""
    record = memory.get(session_id)
    if not record:
        raise HTTPException(status_code=404, detail="会话不存在")

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


@router.delete("/history/{session_id}")
async def delete_history(session_id: str):
    """删除历史辩论"""
    memory.delete(session_id)
    return {"status": "deleted"}
