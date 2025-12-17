"""
Pytest 配置和夹具
"""

import pytest

from lyxamour_mcp.config.models import Config


@pytest.fixture
def config() -> Config:
    """提供测试配置"""
    return Config()


@pytest.fixture
def event_loop():
    """提供事件循环夹具"""
    import asyncio

    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
