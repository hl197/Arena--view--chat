"""ArenaView 配置系统"""

import os
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path


@dataclass
class ArenaConfig:
    """ArenaView 全局配置"""

    # === LLM 默认配置 ===
    default_provider: str = "deepseek"
    default_model: str = "deepseek-chat"
    default_api_key: Optional[str] = field(default_factory=lambda: os.getenv("DEEPSEEK_API_KEY"))

    # === 搜索 API ===
    tavily_api_key: Optional[str] = field(default_factory=lambda: os.getenv("TAVILY_API_KEY", ""))

    # === 免费额度 ===
    guest_daily_limit: int = 3       # 游客每日辩论次数
    guest_max_perspectives: int = 4   # 游客最大视角数
    guest_debate_rounds: int = 1     # 游客辩论轮次

    registered_daily_limit: int = 5
    registered_max_perspectives: int = 5
    registered_debate_rounds: int = 2

    pro_daily_limit: int = 20
    pro_max_perspectives: int = 6
    pro_debate_rounds: int = 3

    # === Agent 执行 ===
    max_agent_steps: int = 8           # ReAct Agent 最大步数（搜→读→搜→读→发言 = 5步，留3步容错）
    agent_timeout_seconds: int = 90    # 单Agent超时（搜+读+发言 ~45秒，留一倍余量）
    debate_timeout_seconds: int = 300  # 整场辩论超时（5 人 × 3 轮 × 60秒 = 900秒理论，实际 5 分钟足够）
    search_timeout_seconds: int = 15   # 单次搜索/抓取超时（Tavily API 通常 3-8 秒，网页抓取 5-12 秒）

    # === Token 控制 ===
    max_tokens_per_debate: int = 50000
    perspective_max_tokens: int = 2000

    # === 上下文工程 ===
    context_window: int = 128000
    compression_threshold: float = 0.8
    min_retain_rounds: int = 5
    tool_output_max_lines: int = 2000

    # === 熔断器 ===
    circuit_enabled: bool = True
    circuit_failure_threshold: int = 3
    circuit_recovery_timeout: int = 300  # 5分钟

    # === 可观测性 ===
    trace_enabled: bool = True
    trace_dir: str = "memory/traces"

    # === 缓存 ===
    cache_enabled: bool = True
    cache_ttl_seconds: int = 86400       # 24小时
    cache_similarity_threshold: float = 0.85

    # === 数据库 ===
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///arena.db"))

    # === 流式 ===
    stream_enabled: bool = True
    heartbeat_interval: int = 15          # SSE 心跳间隔（秒）

    # === 部署 ===
    debug: bool = False
    cors_origins: list[str] = field(default_factory=lambda: ["http://localhost:5173", "http://localhost:3000"])
