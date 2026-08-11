"""
E14.3.2 — Module 1: MAX Provider (the Executor-facing surface)
==============================================================

    MaxProvider(MonetizationProvider)
        apply_change(change)   -> ProviderResult
        rollback_change(change)-> ProviderResult
        health_check()         -> ProviderResult

The Executor (and the Runtime Supervisor) know NOTHING about AppLovin MAX:
no API endpoint, no token, no SDK. They hand a `Change` and get a
`ProviderResult`. The three-layer split is:

    Provider  (this file)   -> contract surface + sandbox + isolation
    Mapper    (max_mapper)   -> Change -> MaxOperation
    Client    (max_client)   -> MAX backend interaction (mock now, real later)

Sandbox behaviour (inherited from E14.3.1):
  * SIMULATION  — applies to in-memory state, real_api_called = False.
  * SHADOW      — READ current value, NO write (write_calls stays 0).
  * PRODUCTION  — real write only if the provider is armed (production lock
                  lifted); otherwise refused by base.py's _result guard.

Credential isolation (E14.1 / E14.3.5): each MaxProvider owns its own client +
MaxGameState keyed by game_id, so game_A's floors can never touch game_B's.
"""
from __future__ import annotations

from typing import Optional

from monetization.providers.base import MonetizationProvider
from monetization.providers.models import Change, ProviderResult, SandboxMode
from monetization.providers.max.max_client import MockMaxClient, RealMaxClient
from monetization.providers.max.max_health import build_health
from monetization.providers.max.max_mapper import map_change_to_operation
from monetization.providers.max.max_models import MaxMappingError, RevenueMetrics
from monetization.providers.max.max_revenue import MaxRevenueReader


class MaxProvider(MonetizationProvider):
    name = "MAX"

    def __init__(self, sandbox: SandboxMode = SandboxMode.SIMULATION,
                 credential_ref=None, client=None, app_id: Optional[str] = None,
                 initial_state=None):
        super().__init__(sandbox, credential_ref)
        self.app_id = (app_id
                       or (credential_ref.game_id if credential_ref else None)
                       or "app_unset")
        # Per-game isolated client/state — never shared across games.
        self._client = client or MockMaxClient(app_id=self.app_id,
                                               state=initial_state)
        self._revenue = MaxRevenueReader(self._client)

    # ------------------------------------------------------------------ #
    # Write surface (contract)
    # ------------------------------------------------------------------ #
    def apply_change(self, change: Change) -> ProviderResult:
        d, lat = self._timed(self._apply, change)
        return self._result(
            d["operation"], d["success"], latency_ms=lat,
            real_api_called=d.get("real", False),
            change_id=change.change_id,
            detail=d.get("detail", ""), error=d.get("error", ""),
            before=d.get("before"), after=d.get("after"),
            shadow_read_only=d.get("shadow", False),
            extra=d.get("extra"),
        )

    def _apply(self, change: Change) -> dict:
        try:
            op = map_change_to_operation(change, self.app_id)
        except MaxMappingError as e:
            return {"operation": change.change_type, "success": False,
                    "error": str(e)}

        # Revenue read is a read, never a write.
        if op.operation == "READ_REVENUE":
            return self._read_revenue(op, change)

        # SHADOW: observe the current value, never write it.
        if self.sandbox == SandboxMode.SHADOW:
            current = self._shadow_current(op)
            return {"operation": op.operation, "success": True, "shadow": True,
                    "before": current, "after": current,
                    "detail": "shadow: read current value, no write performed"}

        # SIMULATION / PRODUCTION write (mock applies to in-memory state).
        real = self._real_flag()
        if real:
            self._client.real_network_calls += 1
        if op.operation == "UPDATE_BID_FLOOR":
            self._client.apply_bid_floor(op)
            return {"operation": op.operation, "success": True, "real": real,
                    "before": op.old_value, "after": op.new_value}
        if op.operation == "UPDATE_WATERFALL_PRIORITY":
            self._client.apply_waterfall(op)
            return {"operation": op.operation, "success": True, "real": real,
                    "before": op.old_order, "after": op.new_order}
        return {"operation": op.operation, "success": False,
                "error": "unsupported operation"}

    def rollback_change(self, change: Change) -> ProviderResult:
        d, lat = self._timed(self._rollback, change)
        return self._result(
            d["operation"], d["success"], latency_ms=lat,
            real_api_called=d.get("real", False),
            change_id=change.change_id,
            detail=d.get("detail", ""), error=d.get("error", ""),
            before=d.get("before"), after=d.get("after"),
        )

    def _rollback(self, change: Change) -> dict:
        try:
            op = map_change_to_operation(change, self.app_id)
        except MaxMappingError as e:
            return {"operation": change.change_type, "success": False,
                    "error": str(e)}

        real = self._real_flag()
        if real:
            self._client.real_network_calls += 1
        if op.operation == "UPDATE_BID_FLOOR":
            self._client.state.set_floor(op.country, op.ad_unit, op.old_value)
            return {"operation": op.operation, "success": True, "real": real,
                    "before": op.new_value, "after": op.old_value}
        if op.operation == "UPDATE_WATERFALL_PRIORITY":
            self._client.state.set_waterfall(op.placement, op.old_order)
            return {"operation": op.operation, "success": True, "real": real,
                    "before": op.new_order, "after": op.old_order}
        return {"operation": op.operation, "success": False,
                "error": "nothing to roll back"}

    # ------------------------------------------------------------------ #
    # Read surface (Reality Engine)
    # ------------------------------------------------------------------ #
    def get_revenue_metrics(self, date: str, geo: str, placement: str) -> RevenueMetrics:
        return self._revenue.get_revenue_metrics(date, geo, placement)

    def _read_revenue(self, op, change: Change) -> dict:
        rm = self._client.read_revenue(change.note or "", op.country, op.ad_unit)
        return {"operation": "READ_REVENUE", "success": True, "real": False,
                "shadow": (self.sandbox == SandboxMode.SHADOW),
                "extra": {"revenue": rm.to_dict()},
                "detail": "revenue read (no mutation)"}

    # ------------------------------------------------------------------ #
    # Health (E14.2 Runtime Supervisor)
    # ------------------------------------------------------------------ #
    def health_check(self) -> ProviderResult:
        h, lat = self._timed(lambda: build_health(self._client).to_dict())
        return self._result(
            "health_check", h["status"] == "healthy", latency_ms=lat,
            real_api_called=False,
            extra={"status": h["status"],
                   "credential_valid": h["credential_valid"],
                   "api_available": h["api_available"]},
        )

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _real_flag(self) -> bool:
        """A real MAX call only when PRODUCTION sandbox AND unlock armed."""
        return (self.sandbox == SandboxMode.PRODUCTION) and (not self._production_locked)

    def _shadow_current(self, op):
        if op.operation == "UPDATE_BID_FLOOR":
            return self._client.state.get_floor(op.country, op.ad_unit)
        if op.operation == "UPDATE_WATERFALL_PRIORITY":
            return self._client.state.get_waterfall(op.placement)
        return None

    # expose the real client seam for production wiring (guarded)
    def arm_real_client(self, api_key: str, endpoint: str = None) -> None:
        """Swap the mock for the real MAX client. Requires explicit credentials
        AND the provider to be in PRODUCTION sandbox — otherwise base.py refuses
        any real call via _result."""
        self._client = RealMaxClient(self.app_id, api_key,
                                     endpoint or RealMaxClient.MAX_API_BASE)
