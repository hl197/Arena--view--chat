"""ArenaView 测试公共 Fixtures"""

import sys
import os
import pytest

# 确保 backend 模块可导入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def sample_config():
    """返回一个 ArenaConfig 实例（用最小设置）"""
    # 避免环境变量干扰，设置 DEEPSEEK_API_KEY
    os.environ.setdefault("DEEPSEEK_API_KEY", "test-mock-key")
    from backend.core.config import ArenaConfig
    return ArenaConfig()


@pytest.fixture
def clean_env():
    """清除可能影响测试的环境变量"""
    old = os.environ.pop("DEEPSEEK_API_KEY", None)
    yield
    if old:
        os.environ["DEEPSEEK_API_KEY"] = old
