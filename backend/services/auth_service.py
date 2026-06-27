"""认证服务 — JWT + bcrypt"""

import os
import hashlib
import hmac
import time
import json
import base64


class AuthService:
    """JWT 认证服务

    MVP 阶段用 HMAC-SHA256 签名，无需额外依赖。
    生产环境可切换到 PyJWT。
    """

    def __init__(self, secret_key: str = None):
        self.secret_key = secret_key or os.urandom(32).hex()

    def hash_password(self, password: str) -> str:
        """密码哈希——SHA256 + salt（MVP 简化版）"""
        import hashlib
        salt = os.urandom(16).hex()
        hashed = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
        return f"{salt}${hashed}"

    def verify_password(self, password: str, stored: str) -> bool:
        """验证密码"""
        try:
            salt, hashed = stored.split("$", 1)
            return hashlib.sha256(f"{salt}{password}".encode()).hexdigest() == hashed
        except (ValueError, AttributeError):
            return False

    def create_token(self, user_id: str, expires_hours: int = 72) -> str:
        """创建 JWT token"""
        header = {"alg": "HS256", "typ": "JWT"}
        payload = {
            "sub": user_id,
            "iat": int(time.time()),
            "exp": int(time.time()) + expires_hours * 3600,
        }

        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=")
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=")

        signature = hmac.new(
            self.secret_key.encode(),
            f"{header_b64.decode()}.{payload_b64.decode()}".encode(),
            hashlib.sha256,
        ).digest()
        sig_b64 = base64.urlsafe_b64encode(signature).rstrip(b"=")

        return f"{header_b64.decode()}.{payload_b64.decode()}.{sig_b64.decode()}"

    def verify_token(self, token: str) -> dict | None:
        """验证 token，返回 payload 或 None"""
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return None

            header_b64, payload_b64, sig_b64 = parts

            # 验证签名
            expected_sig = hmac.new(
                self.secret_key.encode(),
                f"{header_b64}.{payload_b64}".encode(),
                hashlib.sha256,
            ).digest()

            # 补齐 padding
            sig_b64_padded = sig_b64 + "=" * (4 - len(sig_b64) % 4)
            if base64.urlsafe_b64decode(sig_b64_padded) != expected_sig:
                return None

            # 解析 payload
            payload_b64_padded = payload_b64 + "=" * (4 - len(payload_b64) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_b64_padded))

            # 验证过期
            if payload.get("exp", 0) < time.time():
                return None

            return payload

        except Exception:
            return None
