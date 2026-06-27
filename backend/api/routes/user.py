"""用户 API 路由 — JWT认证 + API Key加密 + 额度管理"""

import uuid
from fastapi import APIRouter, HTTPException, Request, Depends
from ..schemas import (
    UserRegisterRequest, UserLoginRequest, UserResponse,
    QuotaResponse, LLMConfigUpdate,
)

router = APIRouter(prefix="/api", tags=["user"])

# 由 main.py 注入
auth_service = None
crypto_service = None
db = None


def init_user_routes(_auth_service, _crypto_service, _db):
    global auth_service, crypto_service, db
    auth_service = _auth_service
    crypto_service = _crypto_service
    db = _db


async def get_current_user(request: Request) -> dict | None:
    """从 Authorization header 提取用户"""
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        token = header[7:]
        payload = auth_service.verify_token(token)
        if payload:
            user = db.get_user(payload["sub"])
            return user
    return None


@router.post("/auth/register", response_model=UserResponse)
async def register(req: UserRegisterRequest):
    """用户注册"""
    existing = db.get_user_by_email(req.email)
    if existing:
        raise HTTPException(status_code=409, detail="该邮箱已注册")

    user_id = f"u_{uuid.uuid4().hex[:8]}"
    password_hash = auth_service.hash_password(req.password)
    db.create_user(user_id, req.email, password_hash)

    # 初始化额度
    db.init_quota(user_id, tier="registered", daily_limit=5, token_limit=300000)

    return UserResponse(
        user_id=user_id,
        email=req.email,
        tier="registered",
    )


@router.post("/auth/login", response_model=UserResponse)
async def login(req: UserLoginRequest):
    """用户登录——返回 JWT token"""
    user = db.get_user_by_email(req.email)
    if not user or not auth_service.verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")

    token = auth_service.create_token(user["id"])
    llm_config = db.get_llm_config(user["id"])

    return UserResponse(
        user_id=user["id"],
        email=user["email"],
        tier=user.get("tier", "registered"),
        api_key_configured=llm_config is not None,
    )


@router.get("/user/quota", response_model=QuotaResponse)
async def get_quota(request: Request):
    """查询用户额度"""
    user = await get_current_user(request)
    if user:
        quota = db.get_quota(user["id"])
        if quota:
            return QuotaResponse(
                tier=quota.get("tier", "registered"),
                daily_debates_used=quota.get("daily_debates_used", 0),
                daily_debates_limit=quota.get("daily_debates_limit", 5),
                total_tokens_used=quota.get("total_tokens_used", 0),
                total_tokens_limit=quota.get("total_tokens_limit", 300000),
                api_key_configured=db.get_llm_config(user["id"]) is not None,
            )

    return QuotaResponse(
        tier="guest",
        daily_debates_used=0,
        daily_debates_limit=3,
        total_tokens_used=0,
        total_tokens_limit=150000,
        api_key_configured=False,
    )


@router.put("/user/llm-config")
async def update_llm_config(req: LLMConfigUpdate, request: Request):
    """配置自定义 LLM（加密存储 API Key）"""
    user = await get_current_user(request)
    user_id = user["id"] if user else "guest"

    encrypted_key = crypto_service.encrypt(req.api_key)
    db.save_llm_config(
        user_id=user_id,
        provider=req.provider,
        api_key_encrypted=encrypted_key,
        model=req.model,
        base_url=req.base_url,
    )

    return {
        "status": "configured",
        "provider": req.provider,
        "key_masked": crypto_service.mask_key(req.api_key),
    }


@router.get("/user/llm-config")
async def get_llm_config(request: Request):
    """获取当前 LLM 配置"""
    user = await get_current_user(request)
    user_id = user["id"] if user else "guest"

    config = db.get_llm_config(user_id)
    if config:
        return {
            "configured": True,
            "provider": config["provider"],
            "model": config.get("model", ""),
            "model_display": config.get("model", "") or f"{config['provider']} (用户配置)",
        }

    return {
        "configured": False,
        "provider": "gemini",
        "model": "gemini-2.0-flash",
        "model_display": "Gemini 2.0 Flash（免费）",
    }
