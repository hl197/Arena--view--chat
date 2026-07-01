"""数据库——SQLite（MVP）/ PostgreSQL（生产）"""

import sqlite3
import json
import time
from pathlib import Path
from typing import Optional


class Database:
    """轻量数据库封装——SQLite"""

    def __init__(self, db_path: str = "arena.db"):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self):
        """初始化表结构"""
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    tier TEXT DEFAULT 'registered',
                    created_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS llm_configs (
                    user_id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    api_key_encrypted TEXT NOT NULL,
                    model TEXT DEFAULT '',
                    base_url TEXT DEFAULT '',
                    created_at REAL NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS quotas (
                    user_id TEXT PRIMARY KEY,
                    tier TEXT DEFAULT 'guest',
                    daily_debates_used INTEGER DEFAULT 0,
                    daily_debates_limit INTEGER DEFAULT 3,
                    total_tokens_used INTEGER DEFAULT 0,
                    total_tokens_limit INTEGER DEFAULT 150000,
                    last_reset_date TEXT DEFAULT '',
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS debates (
                    id TEXT PRIMARY KEY,
                    user_id TEXT DEFAULT 'anonymous',
                    question TEXT NOT NULL,
                    status TEXT DEFAULT 'completed',
                    perspectives_json TEXT DEFAULT '[]',
                    arguments_json TEXT DEFAULT '{}',
                    debate_transcript_json TEXT DEFAULT '[]',
                    decision_map TEXT DEFAULT '',
                    total_tokens INTEGER DEFAULT 0,
                    total_time_ms INTEGER DEFAULT 0,
                    created_at REAL NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );

                CREATE INDEX IF NOT EXISTS idx_debates_user ON debates(user_id);
                CREATE INDEX IF NOT EXISTS idx_debates_created ON debates(created_at);

                CREATE TABLE IF NOT EXISTS verification_codes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL,
                    code TEXT NOT NULL,
                    purpose TEXT DEFAULT 'register',
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    used INTEGER DEFAULT 0,
                    last_sent_at REAL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_vcode_email_purpose ON verification_codes(email, purpose);
            """)

            # 迁移：给现有用户加 email_verified 列（SQLite 不支持 IF NOT EXISTS for ALTER TABLE）
            try:
                conn.execute("ALTER TABLE users ADD COLUMN email_verified INTEGER DEFAULT 1")
            except Exception:
                pass  # 列已存在

            # 确保匿名用户存在（JWT 认证未上线前的默认用户）
            conn.execute(
                "INSERT OR IGNORE INTO users (id, email, password_hash, tier, created_at) VALUES (?, ?, ?, ?, ?)",
                ("anonymous", "anonymous@arena.local", "$none$", "guest", 0.0)
            )

    # === User ===
    def create_user(self, user_id: str, email: str, password_hash: str, tier: str = "registered",
                    email_verified: int = 0) -> dict:
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO users (id, email, password_hash, tier, created_at, email_verified) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, email, password_hash, tier, time.time(), email_verified)
            )
        return {"user_id": user_id, "email": email, "tier": tier}

    def get_user_by_email(self, email: str) -> Optional[dict]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            return dict(row) if row else None

    def get_user(self, user_id: str) -> Optional[dict]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return dict(row) if row else None

    # === LLM Config ===
    def save_llm_config(self, user_id: str, provider: str, api_key_encrypted: str,
                        model: str = "", base_url: str = ""):
        with self._get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO llm_configs (user_id, provider, api_key_encrypted, model, base_url, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, provider, api_key_encrypted, model, base_url, time.time())
            )

    def get_llm_config(self, user_id: str) -> Optional[dict]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM llm_configs WHERE user_id = ?", (user_id,)).fetchone()
            return dict(row) if row else None

    # === Quota ===
    def get_quota(self, user_id: str) -> Optional[dict]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM quotas WHERE user_id = ?", (user_id,)).fetchone()
            return dict(row) if row else None

    def init_quota(self, user_id: str, tier: str = "guest",
                   daily_limit: int = 3, token_limit: int = 150000):
        with self._get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO quotas (user_id, tier, daily_debates_limit, total_tokens_limit, last_reset_date)
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, tier, daily_limit, token_limit, time.strftime("%Y-%m-%d"))
            )

    def increment_quota(self, user_id: str) -> bool:
        """辩论次数 +1。返回 True 表示未超限，False 表示今日次数已用完。"""
        with self._get_conn() as conn:
            quota = dict(conn.execute("SELECT * FROM quotas WHERE user_id = ?", (user_id,)).fetchone())
            today = time.strftime("%Y-%m-%d")

            # 日期重置
            if quota["last_reset_date"] != today:
                conn.execute(
                    "UPDATE quotas SET daily_debates_used=0, last_reset_date=? WHERE user_id=?",
                    (today, user_id)
                )
                quota["daily_debates_used"] = 0

            # 检查限额
            if quota["daily_debates_used"] >= quota["daily_debates_limit"]:
                return False

            conn.execute(
                "UPDATE quotas SET daily_debates_used=daily_debates_used+1 WHERE user_id=?",
                (user_id,)
            )
            return True

    # === Verification Codes ===
    def save_verification_code(self, email: str, code: str, purpose: str = "register", ttl_minutes: int = 10):
        """保存验证码，同时将同邮箱同用途的旧码标记为已使用"""
        with self._get_conn() as conn:
            now = time.time()
            conn.execute(
                "UPDATE verification_codes SET used=1 WHERE email=? AND purpose=? AND used=0",
                (email, purpose)
            )
            conn.execute(
                """INSERT INTO verification_codes (email, code, purpose, created_at, expires_at, last_sent_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (email, code, purpose, now, now + ttl_minutes * 60, now)
            )

    def verify_code(self, email: str, code: str, purpose: str = "register") -> bool:
        """验证码校验——有效且匹配返回 True，同时标记为已使用"""
        with self._get_conn() as conn:
            row = conn.execute(
                """SELECT * FROM verification_codes
                   WHERE email=? AND code=? AND purpose=? AND used=0 AND expires_at > ?
                   ORDER BY created_at DESC LIMIT 1""",
                (email, code, purpose, time.time())
            ).fetchone()
            if not row:
                return False
            conn.execute(
                "UPDATE verification_codes SET used=1 WHERE id=?",
                (row["id"],)
            )
            return True

    def get_pending_code(self, email: str, purpose: str = "register"):
        """获取最新未使用、未过期的验证码（用于检查冷却时间）"""
        with self._get_conn() as conn:
            row = conn.execute(
                """SELECT * FROM verification_codes
                   WHERE email=? AND purpose=? AND used=0 AND expires_at > ?
                   ORDER BY created_at DESC LIMIT 1""",
                (email, purpose, time.time())
            ).fetchone()
            return dict(row) if row else None

    def mark_user_verified(self, user_id: str):
        """标记用户邮箱已验证"""
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE users SET email_verified=1 WHERE id=?",
                (user_id,)
            )

    def is_email_verified(self, user_id: str) -> bool:
        """检查用户邮箱是否已验证"""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT email_verified FROM users WHERE id=?",
                (user_id,)
            ).fetchone()
            return bool(row["email_verified"]) if row else False

    # === Debates ===
    def save_debate(self, debate_data: dict):
        with self._get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO debates
                   (id, user_id, question, status, perspectives_json, arguments_json,
                    debate_transcript_json, decision_map, total_tokens, total_time_ms, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    debate_data["id"],
                    debate_data.get("user_id", "anonymous"),
                    debate_data["question"],
                    debate_data.get("status", "completed"),
                    json.dumps(debate_data.get("perspectives", []), ensure_ascii=False),
                    json.dumps(debate_data.get("arguments", {}), ensure_ascii=False),
                    json.dumps(debate_data.get("debate_transcript", []), ensure_ascii=False),
                    debate_data.get("decision_map", ""),
                    debate_data.get("total_tokens", 0),
                    debate_data.get("total_time_ms", 0),
                    debate_data.get("created_at", time.time()),
                )
            )

    def get_debate(self, debate_id: str) -> Optional[dict]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM debates WHERE id = ?", (debate_id,)).fetchone()
            if not row:
                return None
            d = dict(row)
            d["perspectives"] = json.loads(d.get("perspectives_json", "[]"))
            d["arguments"] = json.loads(d.get("arguments_json", "{}"))
            d["debate_transcript"] = json.loads(d.get("debate_transcript_json", "[]"))
            return d

    def list_debates(self, user_id: str = "", limit: int = 20, offset: int = 0) -> list[dict]:
        with self._get_conn() as conn:
            if user_id:
                rows = conn.execute(
                    "SELECT id, question, status, perspectives_json, created_at FROM debates WHERE user_id=? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (user_id, limit, offset)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, question, status, perspectives_json, created_at FROM debates ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (limit, offset)
                ).fetchall()

            result = []
            for row in rows:
                d = dict(row)
                perspectives = json.loads(d.get("perspectives_json", "[]"))
                d["perspectives_count"] = len(perspectives) if isinstance(perspectives, list) else 0
                result.append(d)
            return result

    def delete_debate(self, debate_id: str):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM debates WHERE id = ?", (debate_id,))
