"""TraceLogger — 可观测性追踪

参考 HelloAgents 的 TraceLogger，简化版：
- JSONL 格式追加写入
- 记录每次 LLM 调用和工具调用
- 第 3 周可升级为 HTML 交互版
"""

import json
import time
from pathlib import Path
from typing import Optional


class TraceLogger:
    """简化的追踪记录器"""

    def __init__(self, output_dir: str = "memory/traces", enabled: bool = True):
        self.enabled = enabled
        if not enabled:
            return

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.session_id = f"trace-{int(time.time())}"
        self.jsonl_path = self.output_dir / f"{self.session_id}.jsonl"
        self._events: list[dict] = []

    def log_event(self, event: str, payload: dict = None, step: int = None):
        """记录事件"""
        if not self.enabled:
            return

        event_obj = {
            "ts": time.time(),
            "session_id": self.session_id,
            "event": event,
            "payload": payload or {},
        }
        if step is not None:
            event_obj["step"] = step

        self._events.append(event_obj)

        # 追加写入 JSONL
        with open(self.jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event_obj, ensure_ascii=False) + "\n")

    def get_stats(self) -> dict:
        """获取统计信息"""
        if not self._events:
            return {}

        llm_calls = [e for e in self._events if e["event"] == "llm_call"]
        tool_calls = [e for e in self._events if e["event"] == "tool_call"]
        errors = [e for e in self._events if e["event"] == "error"]

        total_tokens = sum(e.get("payload", {}).get("tokens", 0) for e in llm_calls)

        return {
            "total_events": len(self._events),
            "llm_calls": len(llm_calls),
            "tool_calls": len(tool_calls),
            "errors": len(errors),
            "total_tokens": total_tokens,
        }
