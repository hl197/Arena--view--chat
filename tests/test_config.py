"""ArenaConfig 配置系统测试"""

import os
import pytest
from backend.core.config import ArenaConfig


class TestArenaConfigDefaults:
    """默认配置值测试"""

    def test_default_provider(self):
        c = ArenaConfig()
        assert c.default_provider == "deepseek"
        assert c.default_model == "deepseek-chat"

    def test_guest_limits(self):
        c = ArenaConfig()
        assert c.guest_daily_limit == 3
        assert c.guest_max_perspectives == 4
        assert c.guest_debate_rounds == 1

    def test_registered_limits(self):
        c = ArenaConfig()
        assert c.registered_daily_limit == 5
        assert c.registered_max_perspectives == 5
        assert c.registered_debate_rounds == 2

    def test_pro_limits(self):
        c = ArenaConfig()
        assert c.pro_daily_limit == 20
        assert c.pro_max_perspectives == 6
        assert c.pro_debate_rounds == 3

    def test_agent_execution(self):
        c = ArenaConfig()
        assert c.max_agent_steps == 5
        assert c.agent_timeout_seconds == 60
        assert c.debate_timeout_seconds == 120

    def test_token_control(self):
        c = ArenaConfig()
        assert c.max_tokens_per_debate == 50000
        assert c.perspective_max_tokens == 2000

    def test_context_engineering(self):
        c = ArenaConfig()
        assert c.context_window == 128000
        assert c.compression_threshold == 0.8
        assert c.min_retain_rounds == 5
        assert c.tool_output_max_lines == 2000

    def test_circuit_breaker(self):
        c = ArenaConfig()
        assert c.circuit_enabled is True
        assert c.circuit_failure_threshold == 3
        assert c.circuit_recovery_timeout == 300

    def test_observability(self):
        c = ArenaConfig()
        assert c.trace_enabled is True
        assert c.trace_dir == "memory/traces"

    def test_cache_settings(self):
        c = ArenaConfig()
        assert c.cache_enabled is True
        assert c.cache_ttl_seconds == 86400
        assert c.cache_similarity_threshold == 0.85

    def test_streaming(self):
        c = ArenaConfig()
        assert c.stream_enabled is True
        assert c.heartbeat_interval == 15

    def test_debug_default(self):
        c = ArenaConfig()
        assert c.debug is False

    def test_cors_origins_default(self):
        c = ArenaConfig()
        assert "http://localhost:5173" in c.cors_origins
        assert "http://localhost:3000" in c.cors_origins


class TestArenaConfigOverride:
    """配置覆盖测试"""

    def test_custom_values(self):
        c = ArenaConfig()
        c.max_agent_steps = 10
        c.debug = True
        assert c.max_agent_steps == 10
        assert c.debug is True

    def test_database_url_default(self):
        """数据库 URL 默认值"""
        c = ArenaConfig()
        assert "sqlite" in c.database_url or "arena.db" in c.database_url

    def test_api_key_from_env(self):
        """API Key 从环境变量读取"""
        # 确保环境变量已设置
        os.environ.setdefault("DEEPSEEK_API_KEY", "test-key-from-env")
        c = ArenaConfig()
        assert c.default_api_key is not None
