"""API 中间件 —— CORS、限流、认证"""

import time
from fastapi import Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware


def setup_cors(app, origins: list[str] = None):
    """配置 CORS"""
    if origins is None:
        origins = ["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


class RateLimiter:
    """简单的内存限流器"""

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._clients: dict[str, list[float]] = {}

    def is_allowed(self, client_id: str) -> bool:
        """检查是否允许请求"""
        now = time.time()
        window_start = now - self.window_seconds

        if client_id not in self._clients:
            self._clients[client_id] = []

        # 清理过期记录
        self._clients[client_id] = [
            t for t in self._clients[client_id] if t > window_start
        ]

        # 检查是否超限
        if len(self._clients[client_id]) >= self.max_requests:
            return False

        self._clients[client_id].append(now)
        return True
