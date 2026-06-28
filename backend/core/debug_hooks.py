"""Debug Hook 系统 —— 开发调试日志（v2）

单例，全局开关。所有输出走 stderr，不影响 SSE/HTTP 响应。

用法：
    from backend.core.debug_hooks import debug

    debug.checkpoint("Phase 1", "生成视角")
    debug.hook("agent_start", name="风险厌恶者")
    debug.hook("tool_call", name="web_search", stats={"results": 5, "ms": 302})
    debug.hook("agent_speak", name="XX", chars=522, searched=True, fetched=True)
    debug.hook("agent_nudge", reason="搜了没读")
    debug.error("web_fetch 超时", detail="xxx.com 15s")
"""

import sys
import time


class DebugHooks:
    """调试钩子系统 —— 单例，全局开关"""

    def __init__(self):
        self.enabled = True
        self._start_time = time.time()
        self._indent = 0

    # ── 基础输出 ───────────────────────────────

    def _w(self, text: str):
        if self.enabled:
            print(f"   {'   ' * self._indent}{text}", file=sys.stderr, flush=True)

    def _ts(self) -> str:
        """相对时间戳"""
        elapsed = time.time() - self._start_time
        return f"{elapsed:.1f}s"

    # ── 公开 API ────────────────────────────────

    def checkpoint(self, tag: str, detail: str = ""):
        """阶段标记"""
        text = f"🔵 {tag}"
        if detail:
            text += f": {detail}"
        line = "─" * 60
        if self.enabled:
            print(f"\n{line}\n{text}\n{line}", file=sys.stderr, flush=True)

    def separator(self, text: str):
        """分隔线"""
        if self.enabled:
            label = f"  {text}  "
            side = "═" * ((58 - len(label)) // 2)
            print(f"\n{side}{label}{side}\n", file=sys.stderr, flush=True)

    def hook(self, event: str, **kwargs):
        """事件钩子"""
        if event == "agent_start":
            self._w(f"🟢 [{self._ts()}] {kwargs['name']} 开始发言")
        elif event == "agent_turn":
            self._w(f"🎤 Round {kwargs.get('round', '?')}: {kwargs['name']} 准备 prompt")
        elif event == "agent_speak":
            flags = []
            if kwargs.get("searched"):
                flags.append("搜✅")
            else:
                flags.append("搜❌")
            if kwargs.get("fetched"):
                flags.append("读✅")
            else:
                flags.append("读❌")
            self._w(f"💬 [{self._ts()}] {kwargs['name']} 发言 ({kwargs.get('chars', 0)}字) | {' '.join(flags)}")
        elif event == "agent_nudge":
            self._w(f"⚠️  [{self._ts()}] {kwargs.get('reason', '')} → 提醒 Agent")
        elif event == "tool_call":
            s = kwargs.get("stats", {})
            detail = ", ".join(f"{k}={v}" for k, v in s.items())
            self._w(f"🔧 [{self._ts()}] {kwargs['name']} → {detail}")
        elif event == "round_start":
            self._w(f"🔄 Round {kwargs.get('num', '?')}/{kwargs.get('total', '?')} 开始")
        elif event == "round_end":
            self._w(f"✅ Round {kwargs.get('num', '?')} 结束")
        elif event == "phase":
            self._w(f"📋 进入 Phase: {kwargs.get('name', '?')}")
        elif event == "reflection":
            self._w(f"🪞 裁判自审 第 {kwargs.get('iteration', '?')} 轮")
        elif event == "custom":
            self._w(kwargs.get("text", ""))

    def error(self, title: str, detail: str = ""):
        """错误标记"""
        text = f"❌ [{self._ts()}] {title}"
        if detail:
            text += f": {detail}"
        if self.enabled:
            print(f"   {text}", file=sys.stderr, flush=True)

    def indent(self):
        """增加缩进"""
        self._indent += 1

    def dedent(self):
        """减少缩进"""
        self._indent = max(0, self._indent - 1)


# 全局单例
debug = DebugHooks()
