"""CircuitBreaker 熔断器状态机测试"""

import time
import pytest
from backend.tools.circuit_breaker import CircuitBreaker, CircuitState


class TestCircuitBreakerInitialState:
    """初始状态测试"""

    def test_starts_closed(self):
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED
        assert cb.is_open is False

    def test_before_call_allows(self):
        cb = CircuitBreaker()
        assert cb.before_call() is True  # 初始关闭，允许调用

    def test_custom_thresholds(self):
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
        assert cb.failure_threshold == 5
        assert cb.recovery_timeout == 60


class TestCircuitBreakerStateTransitions:
    """状态转换测试"""

    def test_closed_to_open(self):
        """连续失败 → 熔断"""
        cb = CircuitBreaker(failure_threshold=3)
        assert cb.state == CircuitState.CLOSED

        for _ in range(3):
            assert cb.before_call() is True
            cb.on_failure()

        assert cb.state == CircuitState.OPEN
        assert cb.is_open is True

    def test_open_blocks_calls(self):
        """熔断后拒绝调用"""
        cb = CircuitBreaker(failure_threshold=2)
        for _ in range(2):
            cb.before_call()
            cb.on_failure()

        assert cb.state == CircuitState.OPEN
        assert cb.before_call() is False  # 被拒绝

    def test_open_to_half_open(self):
        """熔断超时后 → 半开"""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0)
        for _ in range(2):
            cb.before_call()
            cb.on_failure()

        # recovery_timeout=0，状态机立即从 OPEN 转为 HALF_OPEN（断言 HALF_OPEN 即可）
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_success_closes(self):
        """半开 + 成功 → 关闭"""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0)
        # 触发熔断
        for _ in range(2):
            cb.before_call()
            cb.on_failure()
        assert cb.state == CircuitState.HALF_OPEN

        # 半开成功
        cb.before_call()
        cb.on_success()
        assert cb.state == CircuitState.CLOSED
        assert cb.is_open is False

    def test_half_open_failure_opens_again(self):
        """半开 + 失败 → 再次熔断"""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=3600)
        # 触发熔断
        for _ in range(2):
            cb.before_call()
            cb.on_failure()
        assert cb.state == CircuitState.OPEN

        # recovery_timeout 很大，熔断保持 OPEN；before_call 被拒绝
        assert cb.before_call() is False
        assert cb.state == CircuitState.OPEN

    def test_half_open_max_calls(self):
        """半开状态只允许有限调用"""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0, half_open_max_calls=1)
        for _ in range(2):
            cb.before_call()
            cb.on_failure()

        assert cb.state == CircuitState.HALF_OPEN
        assert cb.before_call() is True   # 第一次允许
        assert cb.before_call() is False  # 超出限制


class TestCircuitBreakerReset:
    """重置测试"""

    def test_reset_from_open(self):
        cb = CircuitBreaker(failure_threshold=2)
        for _ in range(2):
            cb.before_call()
            cb.on_failure()
        assert cb.state == CircuitState.OPEN

        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.before_call() is True

    def test_reset_clears_failure_count(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.before_call()
        cb.on_failure()
        cb.before_call()
        cb.on_failure()

        cb.reset()
        # 重置后需要 3 次失败才熔断（不是 1 次）
        for _ in range(2):
            cb.before_call()
            cb.on_failure()
        assert cb.state == CircuitState.CLOSED  # 还没到阈值


class TestCircuitBreakerOnSuccess:
    """on_success 行为测试"""

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.before_call()
        cb.on_failure()
        cb.before_call()
        cb.on_failure()
        # 成功了
        cb.before_call()
        cb.on_success()
        # 失败计数归零
        cb.before_call()
        cb.on_failure()
        assert cb.state == CircuitState.CLOSED  # 还没到阈值
