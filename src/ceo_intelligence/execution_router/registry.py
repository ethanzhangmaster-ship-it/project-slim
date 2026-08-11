"""E17.6 — Adapter 注册表（路由表）。

domain -> ExecutionAdapter：
  UA → MetaAdapter ｜ ASO → GooglePlayAdapter ｜ CREATIVE → CreativeAdapter
  ECONOMY → RemoteConfigAdapter ｜ RELEASE → PlayReleaseAdapter（E15）
  ANALYTICS → AnalyticsAdapter
"""
from __future__ import annotations

from typing import Dict, Optional

from .adapters.analytics import AnalyticsAdapter
from .adapters.base import ExecutionAdapter
from .adapters.creative import CreativeAdapter
from .adapters.economy import RemoteConfigAdapter
from .adapters.meta import MetaAdapter
from .adapters.play import GooglePlayAdapter, PlayReleaseAdapter
from .models import ExecutionDomain


class AdapterRegistry:
    """domain -> adapter 查找表。"""

    def __init__(self):
        self._adapters: Dict[str, ExecutionAdapter] = {}

    def register(self, adapter: ExecutionAdapter) -> None:
        self._adapters[adapter.domain] = adapter

    def find(self, domain: str) -> Optional[ExecutionAdapter]:
        return self._adapters.get(domain)

    def domains(self):
        return sorted(self._adapters.keys())


def build_default_registry(*, release_state_path: Optional[str] = None) -> AdapterRegistry:
    """默认全 SIM 路由表（生产接入时按域替换 live adapter）。"""
    reg = AdapterRegistry()
    reg.register(MetaAdapter())
    reg.register(GooglePlayAdapter())
    reg.register(CreativeAdapter())
    reg.register(RemoteConfigAdapter())
    reg.register(PlayReleaseAdapter(state_path=release_state_path))
    reg.register(AnalyticsAdapter())
    assert set(reg.domains()) == {d.value for d in ExecutionDomain}
    return reg


__all__ = ["AdapterRegistry", "build_default_registry"]
