"""加密服务 — 用户 API Key 的 Fernet 加密存储"""

import os
import base64
import hashlib


class CryptoService:
    """API Key 加密服务

    用户填入的 LLM API Key 在服务器端用 Fernet 加密后存储。
    数据库泄露不会直接暴露用户 Key。
    """

    def __init__(self, master_key: str = None):
        self.master_key = master_key or os.getenv("ARENA_MASTER_KEY") or os.urandom(32).hex()

    def encrypt(self, plaintext: str) -> str:
        """加密——AES-CBC + HMAC（简化的 Fernet）"""
        from cryptography.fernet import Fernet
        key = base64.urlsafe_b64encode(
            hashlib.sha256(self.master_key.encode()).digest()
        )
        f = Fernet(key)
        return f.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        """解密"""
        try:
            from cryptography.fernet import Fernet
            key = base64.urlsafe_b64encode(
                hashlib.sha256(self.master_key.encode()).digest()
            )
            f = Fernet(key)
            return f.decrypt(ciphertext.encode()).decode()
        except Exception:
            return ""

    @staticmethod
    def mask_key(key: str) -> str:
        """脱敏显示——sk-...xxx"""
        if len(key) <= 8:
            return key[:2] + "***"
        return key[:4] + "***" + key[-4:]
