"""E10.2 Facebook Action Mapper.

Maps E10.1 ActionTypes to Facebook Graph API parameters.
This is the translation layer between Runtime semantics and
platform-specific API calls.

Mapping:
    SCALE  → {"daily_budget": <cents>}
    KILL   → {"status": "PAUSED"}
    WATCH  → {"fields": "<insights_fields>"}
    RETEST → {"operation": "duplicate"}
"""

from __future__ import annotations

from typing import Any

from market_ops.execution_runtime.schemas import ActionType


class FacebookMapper:
    """Maps E10.1 ActionType to Facebook API parameters.

    All monetary values are converted to cents (integer) for
    Facebook's API. The mapper is stateless and thread-safe.

    Usage:
        mapper = FacebookMapper()
        params = mapper.map_action(ActionType.SCALE, {"after": 500.0})
        # → {"daily_budget": "50000"}
    """

    # ── Action → operation name ────────────────────────────
    _ACTION_OPERATION: dict[str, str] = {
        ActionType.SCALE.value:  "update_budget",
        ActionType.KILL.value:   "pause_campaign",
        ActionType.WATCH.value:  "get_metrics",
        ActionType.RETEST.value: "duplicate_campaign",
    }

    def map_action(self, action_type: str, budget_change: dict[str, float], config: dict[str, Any] | None = None) -> dict[str, Any]:
        """Map an E10.1 action to Facebook API parameters.

        Args:
            action_type: One of SCALE, KILL, WATCH, RETEST.
            budget_change: {"before": float, "after": float}.
            config: Optional extra config (retest budget, etc.).

        Returns:
            Dict with 'operation', 'params', and 'method' keys.
        """
        operation = self._ACTION_OPERATION.get(action_type, "unknown")

        if action_type == ActionType.SCALE.value:
            return self._map_scale(budget_change)
        elif action_type == ActionType.KILL.value:
            return self._map_kill()
        elif action_type == ActionType.WATCH.value:
            return self._map_watch()
        elif action_type == ActionType.RETEST.value:
            return self._map_retest(config or {})
        else:
            return {"operation": "unknown", "params": {}, "method": "GET"}

    # ── Individual mappings ────────────────────────────────

    def _map_scale(self, budget_change: dict[str, float]) -> dict[str, Any]:
        """SCALE → update daily_budget in cents."""
        amount = budget_change.get("after", 0.0)
        return {
            "operation": "update_budget",
            "method": "POST",
            "params": {"daily_budget": self._to_cents(amount)},
        }

    def _map_kill(self) -> dict[str, Any]:
        """KILL → pause campaign."""
        return {
            "operation": "pause_campaign",
            "method": "POST",
            "params": {"status": "PAUSED"},
        }

    def _map_watch(self) -> dict[str, Any]:
        """WATCH → get campaign + insights."""
        return {
            "operation": "get_metrics",
            "method": "GET",
            "params": {
                "fields": "id,name,status,daily_budget,insights{impressions,clicks,spend,cpm,cpc,ctr}",
            },
        }

    def _map_retest(self, config: dict[str, Any]) -> dict[str, Any]:
        """RETEST → duplicate campaign with reduced budget."""
        budget = config.get("budget", 50.0)
        return {
            "operation": "duplicate_campaign",
            "method": "POST",
            "params": {"daily_budget": self._to_cents(float(budget))},
        }

    # ── Helpers ────────────────────────────────────────────

    @staticmethod
    def _to_cents(amount: float) -> str:
        """Convert dollars to cents string for Facebook API.

        Facebook expects daily_budget in cents as integer string.
        """
        return str(int(round(amount * 100, 0)))

    @staticmethod
    def from_cents(cents: str | int) -> float:
        """Convert cents back to dollars."""
        return float(cents) / 100.0

    def get_operation(self, action_type: str) -> str:
        """Get the operation name for an action type."""
        return self._ACTION_OPERATION.get(action_type, "unknown")