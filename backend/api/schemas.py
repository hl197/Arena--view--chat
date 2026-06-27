"""API 请求/响应模型"""

from pydantic import BaseModel, Field
from typing import Optional


# === 辩论相关 ===
class DebateStartRequest(BaseModel):
    question: str = Field(..., description="决策问题", min_length=10, max_length=1000)
    options: list[str] = Field(default_factory=list, description="用户已考虑的选项")
    num_perspectives: int = Field(default=5, ge=3, le=6, description="视角数量")
    debate_rounds: int = Field(default=2, ge=0, le=3, description="辩论轮次")
    value_weights: Optional[dict[str, float]] = Field(default=None, description="价值权重")


class DebateStartResponse(BaseModel):
    session_id: str
    stream_url: str
    perspectives: list[dict]


class DebateStatusResponse(BaseModel):
    session_id: str
    status: str  # pending | running | completed | error
    phase: str = ""
    progress: float = 0.0
    message: str = ""


class DebateResultResponse(BaseModel):
    session_id: str
    question: str
    status: str
    perspectives: list[dict]
    arguments: dict[str, str]
    debate_transcript: list[dict]
    decision_map: str
    total_tokens: int = 0
    total_time_ms: int = 0


# === 用户相关 ===
class UserRegisterRequest(BaseModel):
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=8, max_length=128)


class UserLoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    user_id: str
    email: str
    tier: str  # guest | registered | pro
    api_key_configured: bool = False


class QuotaResponse(BaseModel):
    tier: str
    daily_debates_used: int
    daily_debates_limit: int
    total_tokens_used: int
    total_tokens_limit: int
    api_key_configured: bool


class LLMConfigUpdate(BaseModel):
    provider: str = Field(..., description="openai | deepseek | groq | custom")
    api_key: str = Field(..., min_length=1)
    model: str = ""
    base_url: str = ""


# === 历史相关 ===
class HistoryItem(BaseModel):
    session_id: str
    question: str
    status: str
    perspectives_count: int
    created_at: str


class HistoryListResponse(BaseModel):
    items: list[HistoryItem]
    total: int
    page: int


class UserMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000, description="用户消息内容")


# === 通用 ===
class ErrorResponse(BaseModel):
    code: str
    message: str
    detail: str = ""
