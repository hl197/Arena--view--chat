"""用户 API 路由 — JWT认证 + 邮箱验证 + API Key加密 + 额度管理"""

import uuid
from fastapi import APIRouter, HTTPException, Request
from ..schemas import (
    UserRegisterRequest, UserLoginRequest, UserResponse,
    QuotaResponse, LLMConfigUpdate,
    RegisterResponse, VerifyResponse,
    VerifyCodeRequest, ResendCodeRequest,
)

router = APIRouter(prefix="/api", tags=["user"])

# 由 main.py 注入
auth_service = None
crypto_service = None
db = None
email_service = None


def init_user_routes(_auth_service, _crypto_service, _db, _email_service=None):
    global auth_service, crypto_service, db, email_service
    auth_service = _auth_service
    crypto_service = _crypto_service
    db = _db
    email_service = _email_service


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


@router.post("/auth/register", response_model=RegisterResponse)
async def register(req: UserRegisterRequest):
    """用户注册——发送验证码，需验证后才能登录"""
    existing = db.get_user_by_email(req.email)
    if existing:
        # 如果用户已存在但未验证，提示去验证
        if not existing.get("email_verified"):
            raise HTTPException(status_code=409, detail="这个邮箱注册过了但还没验证，去收件箱找找验证码吧")
        raise HTTPException(status_code=409, detail="这个邮箱已经注册过了，换个邮箱或直接登录吧")

    user_id = f"u_{uuid.uuid4().hex[:8]}"
    password_hash = auth_service.hash_password(req.password)
    db.create_user(user_id, req.email, password_hash, email_verified=0)

    # 生成并发送验证码
    code = email_service.generate_code() if email_service else "000000"
    db.save_verification_code(req.email, code, purpose="register", ttl_minutes=10)

    email_sent = False
    if email_service and email_service.configured:
        try:
            email_service.send_verification_email(req.email, code)
            email_sent = True
        except Exception as e:
            # 邮件发送失败不阻塞注册，用户可后续重发验证码
            import sys
            print(f"   ⚠️  验证码邮件发送失败: {e}", file=sys.stderr, flush=True)

    return RegisterResponse(
        user_id=user_id,
        email=req.email,
        message="验证码已发送，请查收邮件" if email_sent else "验证码发送失败，请稍后重发",
        requires_verification=True,
    )


@router.post("/auth/login", response_model=UserResponse)
async def login(req: UserLoginRequest):
    """用户登录——返回 JWT token，未验证邮箱则拒绝"""
    user = db.get_user_by_email(req.email)
    if not user or not auth_service.verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="邮箱或密码不对，再检查一下？")

    if not user.get("email_verified"):
        raise HTTPException(status_code=403, detail="邮箱还没验证，先去验证一下才能登录")

    token = auth_service.create_token(user["id"])
    llm_config = db.get_llm_config(user["id"])

    return UserResponse(
        user_id=user["id"],
        email=user["email"],
        tier=user.get("tier", "registered"),
        api_key_configured=llm_config is not None,
        token=token,
    )


@router.post("/auth/verify", response_model=VerifyResponse)
async def verify_email(req: VerifyCodeRequest):
    """验证邮箱——校验验证码，标记已验证，返回 JWT"""
    user = db.get_user_by_email(req.email)
    if not user:
        raise HTTPException(status_code=404, detail="这个邮箱还没注册，先注册一个账号吧")

    if user.get("email_verified"):
        # 已验证的直接登录
        token = auth_service.create_token(user["id"])
        return VerifyResponse(
            user_id=user["id"],
            email=user["email"],
            tier=user.get("tier", "registered"),
            token=token,
            message="已验证，欢迎回来",
        )

    if not db.verify_code(req.email, req.code, purpose="register"):
        raise HTTPException(status_code=400, detail="验证码不对或者过期了，重新获取一个吧")

    db.mark_user_verified(user["id"])
    db.init_quota(user["id"], tier="registered", daily_limit=5, token_limit=999999)

    token = auth_service.create_token(user["id"])

    return VerifyResponse(
        user_id=user["id"],
        email=user["email"],
        tier=user.get("tier", "registered"),
        token=token,
        message="验证成功",
    )


@router.post("/auth/resend-code")
async def resend_code(req: ResendCodeRequest):
    """重新发送验证码——60 秒冷却"""
    user = db.get_user_by_email(req.email)
    if not user:
        raise HTTPException(status_code=404, detail="这个邮箱还没注册，先注册一个账号吧")

    if user.get("email_verified"):
        raise HTTPException(status_code=400, detail="邮箱已经验证过了，直接登录就行")

    # 检查冷却时间
    pending = db.get_pending_code(req.email, purpose="register")
    if pending and email_service:
        elapsed = __import__("time").time() - pending.get("last_sent_at", 0)
        cooldown = 60
        if elapsed < cooldown:
            remaining = int(cooldown - elapsed)
            raise HTTPException(
                status_code=429,
                detail=f"发送太快啦，等 {remaining} 秒再试试",
            )

    if not email_service or not email_service.configured:
        raise HTTPException(status_code=500, detail="邮件服务还没配置好，请联系管理员")

    code = email_service.generate_code()
    db.save_verification_code(req.email, code, purpose="register", ttl_minutes=10)

    try:
        email_service.send_verification_email(req.email, code)
        return {"message": "验证码已重新发送"}
    except Exception as e:
        raise HTTPException(status_code=500, detail="邮件发送失败了，请稍后再试")


@router.get("/user/quota", response_model=QuotaResponse)
async def get_quota(request: Request):
    """查询当前用户额度——必须登录"""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")

    user_id = user["id"]
    quota = db.get_quota(user_id)
    if not quota:
        db.init_quota(user_id, tier=user.get("tier", "registered"), daily_limit=5, token_limit=999999)
        quota = db.get_quota(user_id) or {}

    return QuotaResponse(
        tier=quota.get("tier", "registered"),
        daily_debates_used=quota.get("daily_debates_used", 0),
        daily_debates_limit=quota.get("daily_debates_limit", 5),
        total_tokens_used=quota.get("total_tokens_used", 0),
        total_tokens_limit=quota.get("total_tokens_limit", 999999),
        api_key_configured=db.get_llm_config(user_id) is not None,
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
