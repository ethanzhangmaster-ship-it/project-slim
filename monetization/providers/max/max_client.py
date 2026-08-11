"""
E14.3.2 — Module 3: MAX Client (network seam)
=============================================

The third layer of the adapter. It is intentionally split from the Provider so
the *real* AppLovin MAX call is a single, gated, replaceable seam:

    MockMaxClient   — in-memory simulation of the MAX backend (no network).
                      Used in SIMULATION / SHADOW and for all local validation.
    RealMaxClient   — the future network seam. NOT wired in this environment;
                      it documents the endpoint and is only invoked when the
                      provider is armed for PRODUCTION (see base.py lock).

Neither client is ever reached in SHADOW mode for writes (the Provider blocks
that). The MockClient tracks write_calls / real_network_calls so the sandbox
guarantees are observable in tests.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from monetization.providers.max.max_models import (
    MaxGameState, MaxHealth, MaxOperation, RevenueMetrics,
)


class MaxClient(ABC):
    @abstractmethod
    def apply_bid_floor(self, op: MaxOperation) -> dict:
        ...

    @abstractmethod
    def apply_waterfall(self, op: MaxOperation) -> dict:
        ...

    @abstractmethod
    def read_revenue(self, date: str, geo: str, placement: str) -> RevenueMetrics:
        ...

    @abstractmethod
    def check_credential(self) -> bool:
        ...

    @abstractmethod
    def ping(self) -> bool:
        ...


class MockMaxClient(MaxClient):
    """In-memory stand-in for the MAX backend. Mutates MaxGameState only."""

    def __init__(self, app_id: str, state: Optional[MaxGameState] = None,
                 latency_ms: float = 0.0):
        self.app_id = app_id
        self.state = state or MaxGameState(app_id=app_id)
        self._latency = latency_ms
        self._credential_valid = True
        self._api_available = True
        # observability for sandbox guarantees
        self.write_calls = 0
        self.real_network_calls = 0

    def apply_bid_floor(self, op: MaxOperation) -> dict:
        self.write_calls += 1
        self.state.set_floor(op.country, op.ad_unit, float(op.new_value))
        return {"ok": True, "applied": "bid_floor", "value": op.new_value}

    def apply_waterfall(self, op: MaxOperation) -> dict:
        self.write_calls += 1
        self.state.set_waterfall(op.placement, op.new_order)
        return {"ok": True, "applied": "waterfall", "order": op.new_order}

    def read_revenue(self, date: str, geo: str, placement: str) -> RevenueMetrics:
        key = f"{date}|{geo}|{placement}"
        rm = self.state.revenue.get(key)
        if rm is None:
            # Graceful zeroed observation so the Reality Engine still has a cell.
            return RevenueMetrics(date=date, geo=geo, placement=placement,
                                  impressions=0, revenue=0.0, ecpm=0.0)
        return rm

    def check_credential(self) -> bool:
        return self._credential_valid

    def ping(self) -> bool:
        return self._api_available

    # test/integration hooks
    def set_credential_valid(self, v: bool) -> None:
        self._credential_valid = v

    def set_api_available(self, v: bool) -> None:
        self._api_available = v


class RealMaxClient(MaxClient):
    """Network seam for AppLovin MAX REST/SDK.

    DELIBERATELY NOT WIRED in this environment. Wiring requires the real API
    token + endpoint, and is only ever invoked when the owning MaxProvider is
    armed for PRODUCTION (base.py `_production_locked` lifted). Every method
    raises until then, so a half-configured deployment fails loud, never silent.
    """

    MAX_API_BASE = "https://api.applovin.com/v1"

    def __init__(self, app_id: str, api_key: str, endpoint: str = MAX_API_BASE):
        self.app_id = app_id
        self.api_key = api_key
        self.endpoint = endpoint.rstrip("/")

    def _not_wired(self) -> None:
        raise NotImplementedError(
            "RealMaxClient is not wired in this environment. Arm a production "
            "client only with real AppLovin MAX credentials and a PRODUCTION sandbox."
        )

    def apply_bid_floor(self, op: MaxOperation) -> dict:
        self._not_wired()

    def apply_waterfall(self, op: MaxOperation) -> dict:
        self._not_wired()

    def read_revenue(self, date: str, geo: str, placement: str) -> RevenueMetrics:
        self._not_wired()

    def check_credential(self) -> bool:
        return bool(self.api_key)

    def ping(self) -> bool:
        return False
