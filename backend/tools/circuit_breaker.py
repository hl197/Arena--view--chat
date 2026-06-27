"""熔断器

状态机: Closed → [连续失败] → Open → [超时] → HalfOpen → [测试] → Closed/Open
"""

import time
from enum import Enum
from dataclasses import dataclass, field


class CircuitState(str, Enum):
    CLOSED = "closed"          # 正常
    OPEN = "open"              # 熔断
    HALF_OPEN = "half_open"    # 半开（探测恢复）


@dataclass
class CircuitBreaker:
    """熔断器——保护外部 API 调用"""

    failure_threshold: int = 3       # 连续失败次数触发熔断
    recovery_timeout: int = 300      # 熔断后 5 分钟尝试恢复
    half_open_max_calls: int = 1     # 半开状态最多允许的测试调用

    _state: CircuitState = CircuitState.CLOSED
    _failure_count: int = 0
    _last_failure_time: float = 0
    _half_open_calls: int = 0

    @property
    def state(self) -> CircuitState:
        self._transition()
        return self._state

    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN

    def _transition(self):
        """状态转换"""
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_failure_time > self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0

    def before_call(self) -> bool:
        """调用前检查——返回 True 表示允许调用"""
        self._transition()
        if self._state == CircuitState.OPEN:
            return False
        if self._state == CircuitState.HALF_OPEN:
            if self._half_open_calls >= self.half_open_max_calls:
                return False
            self._half_open_calls += 1
        return True

    def on_success(self):
        """调用成功"""
        self._failure_count = 0
        self._state = CircuitState.CLOSED
        self._half_open_calls = 0

    def on_failure(self):
        """调用失败"""
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            self._half_open_calls = 0

    def reset(self):
        """手动重置"""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._half_open_calls = 0
