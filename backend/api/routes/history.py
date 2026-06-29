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
async def get_history_detail(session_id: str):
    """获取历史辩论详情——内存优先，DB 降级"""
    record = memory.get(session_id)
    if record:
        return _format_debate_detail(record)

    # DB 降级
    if db:
        db_record = db.get_debate(session_id)
        if db_record:
            return _format_debate_detail(db_record)

    raise HTTPException(status_code=404, detail="会话不存在")


@router.delete("/history/{session_id}")
async def delete_history(session_id: str):
    """删除历史辩论——同时删除内存和 DB 中的记录"""
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
