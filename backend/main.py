"""ArenaView — 多视角决策分析平台 API 入口"""

import os
import re
import base64
import hashlib
from pathlib import Path
from dotenv import load_dotenv

# 自动加载项目根目录 .env 文件
_project_root = Path(__file__).parent.parent
load_dotenv(_project_root / ".env")


def _ensure_master_key():
    """确保 ARENA_MASTER_KEY 已配置——没有则自动生成并持久化到 .env"""
    if os.getenv("ARENA_MASTER_KEY"):
        return

    # 尝试 .env.key 文件
    key_file = _project_root / ".env.key"
    if key_file.exists():
        os.environ["ARENA_MASTER_KEY"] = key_file.read_text().strip()
        return

    # 自动生成
    master_key = os.urandom(32).hex()
    os.environ["ARENA_MASTER_KEY"] = master_key
    env_file = _project_root / ".env"
    line = f"\n# === 自动生成 — 加密主密钥，请勿提交到 Git ===\nARENA_MASTER_KEY={master_key}\n"
    try:
        if env_file.exists():
            content = env_file.read_text(encoding="utf-8")
            if "ARENA_MASTER_KEY" not in content:
                with open(env_file, "a", encoding="utf-8") as f:
                    f.write(line)
        else:
            with open(env_file, "w", encoding="utf-8") as f:
                f.write(f"# ArenaView 环境配置\n{line}")
        print(f"🔑 已生成 ARENA_MASTER_KEY → {env_file}")
    except OSError as e:
        print(f"⚠️  无法写入 .env ({e})，加密 Key 将无法在重启后解密")


def _decrypt_env_api_keys():
    """解密所有 *_ENC 环境变量并注入对应的明文变量"""
    master_key = os.getenv("ARENA_MASTER_KEY")
    if not master_key:
        return

    from cryptography.fernet import Fernet
    fernet_key = base64.urlsafe_b64encode(hashlib.sha256(master_key.encode()).digest())
    f = Fernet(fernet_key)

    for env_key in list(os.environ.keys()):
        if not env_key.endswith("_ENC"):
            continue

        target_key = env_key[:-4]  # 去掉 _ENC 后缀

        # 明文优先
        if os.getenv(target_key):
            continue

        try:
            decrypted = f.decrypt(os.environ[env_key].encode()).decode()
            os.environ[target_key] = decrypted
            print(f"🔓 已解密 {env_key} → {target_key}")
        except Exception as e:
            print(f"⚠️  解密 {env_key} 失败: {e}")


# === 启动时密钥初始化 ===
_ensure_master_key()
_decrypt_env_api_keys()

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .version import __version__, __description__
from .core.config import ArenaConfig
from .core.harness_engine import HarnessEngine
from .core.streaming import SSEManager
from .adapters.unified_llm import ArenaLLM
from .memory.debate_memory import DebateMemory
from .db.database import Database
from .services.auth_service import AuthService
from .services.crypto_service import CryptoService
from .services.email_service import EmailService
from .api.middleware import setup_cors
from .api.routes import debate, user, history


# === 全局服务实例 ===
config = ArenaConfig()
db = Database(db_path=os.getenv("DATABASE_URL", "arena.db").replace("sqlite:///", ""))
auth_service = AuthService(secret_key=os.getenv("ARENA_SECRET_KEY"))
crypto_service = CryptoService(master_key=os.getenv("ARENA_MASTER_KEY"))
email_service = EmailService(config)  # SMTP 邮件验证码
memory = DebateMemory()
sse_manager = SSEManager()

# LLM（从环境变量读取默认配置，用户可通过 API 覆盖）
llm = ArenaLLM()

# Harness Engine
engine = HarnessEngine(config=config, llm=llm)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    print(f"🤖 ArenaView v{__version__} 启动")
    print(f"🧠 默认 LLM: DeepSeek (deepseek-chat)")
    print(f"🔧 工具: {', '.join(engine.tool_registry.list_tools())}")
    print(f"📦 数据库: {db.db_path}")
    yield
    print("👋 ArenaView 关闭")


app = FastAPI(
    title="ArenaView",
    description="多视角决策分析平台 — 让 AI 辩论帮你理解决策全貌",
    version=__version__,
    lifespan=lifespan,
)

# CORS
setup_cors(app, origins=config.cors_origins)

# 健康检查端点（始终可用，不受路由注册影响）
@app.get("/api/health")
async def api_health_check():
    return {"status": "ok", "version": __version__}


# 初始化路由（注入全局服务）
debate.init_debate_routes(engine, memory, sse_manager, db)
history.init_history_routes(memory, db)
user.init_user_routes(auth_service, crypto_service, db, email_service)

# 注册路由
app.include_router(debate.router)
app.include_router(user.router)
app.include_router(history.router)


# === 错误处理 ===
@app.exception_handler(404)
async def not_found(request, exc):
    return JSONResponse(status_code=404, content={"code": "NOT_FOUND", "message": "页面找不到了，检查一下地址？"})


@app.exception_handler(500)
async def internal_error(request, exc):
    return JSONResponse(status_code=500, content={"code": "INTERNAL_ERROR", "message": "服务器出了点问题，稍后再试吧"})


# === 基础端点 ===
@app.get("/")
async def root():
    return {
        "name": "ArenaView",
        "version": __version__,
        "description": "多视角决策分析平台",
        "tools": engine.tool_registry.list_tools(),
        "endpoints": {
            "debate": "/api/debate/start",
            "history": "/api/history",
            "user": "/api/auth/register",
        }
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "version": __version__,
        "tools_available": len(engine.tool_registry.list_tools()),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=config.debug,
    )
