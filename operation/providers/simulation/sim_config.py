"""E15.2.3 — Simulation Config Provider"""
from __future__ import annotations
from typing import Any, Dict, Optional
from operation.providers.contracts.config import ConfigProvider


class SimulationConfigProvider(ConfigProvider):
    name = "simulation_config"

    def __init__(self):
        self._store: Dict[str, Any] = {
            "reward_amount": 100,
            "energy_cost": 5,
            "ad_frequency": 60,
            "cooldown": 30,
            "bid_floor_rewarded_US": 15.0,
        }

    def get(self, key: str, default: Any = None) -> Any:
        return self._store.get(key, default)

    def update(self, key: str, value: Any) -> Dict[str, Any]:
        old = self._store.get(key)
        self._store[key] = value
        return {"success": True, "key": key, "old_value": old, "new_value": value}

    def rollback(self, version: Optional[str] = None) -> Dict[str, Any]:
        return {"success": True, "detail": "rollback not supported in simulation"}

    def get_all(self, prefix: str = "") -> Dict[str, Any]:
        if not prefix:
            return dict(self._store)
        return {k: v for k, v in self._store.items() if k.startswith(prefix)}

    def health_check(self) -> Dict[str, Any]:
        return {"success": True, "detail": "simulation config healthy"}


__all__ = ["SimulationConfigProvider"]
