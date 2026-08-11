"""
E13.3.3 — Provider adapters (MOCK in v1)
=======================================

All providers share the MonetizationProvider surface (apply / rollback /
status). v1 implementations never call a real ad platform; each response
certifies `real_api_called: false`. Real MAX / LevelPlay / RemoteConfig clients
land in E13.4 behind the same interface.
"""
from monetization.executor.providers.base import MonetizationProvider, _assert_mock
from monetization.executor.providers.max_executor import MaxProvider
from monetization.executor.providers.levelplay_executor import LevelPlayProvider
from monetization.executor.providers.remote_config_executor import RemoteConfigProvider

__all__ = [
    "MonetizationProvider", "_assert_mock",
    "MaxProvider", "LevelPlayProvider", "RemoteConfigProvider",
]
