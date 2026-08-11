"""V4.3.5 Trend Updater — update trend statuses based on validation.

Detects trend changes:
  - Dragon Merge: ROAS 1.4 → 0.6 → Expired
  - Goods Sort: ROAS 0.5 → 1.8 → Growing

Auto-updates trend labels for all tracked patterns.
"""

from __future__ import annotations

from typing import Any

from .schemas import TrendDirection


class TrendUpdater:
    """Update trend statuses based on performance data."""

    def __init__(self) -> None:
        self._trends: dict[str, dict[str, Any]] = {}  # trend_id → {status, history}
        self._update_history: list[dict[str, Any]] = []

    def register_trend(self, trend_id: str, initial_roas: float,
                        name: str = "") -> None:
        """Register a new trend to track."""
        self._trends[trend_id] = {
            "name": name or trend_id,
            "status": TrendDirection.STABLE.value,
            "current_roas": initial_roas,
            "roas_history": [initial_roas],
            "peak_roas": initial_roas,
            "trough_roas": initial_roas,
        }

    def update(self, trend_id: str, new_roas: float) -> TrendDirection:
        """Update a trend with new ROAS data.

        Returns the new trend direction.
        """
        if trend_id not in self._trends:
            self.register_trend(trend_id, new_roas)

        trend = self._trends[trend_id]
        old_roas = trend["current_roas"]
        trend["current_roas"] = new_roas
        trend["roas_history"].append(new_roas)
        trend["peak_roas"] = max(trend["peak_roas"], new_roas)
        trend["trough_roas"] = min(trend["trough_roas"], new_roas)

        # Determine direction
        old_status = trend["status"]
        new_status = self._determine_direction(trend, old_roas, new_roas)
        trend["status"] = new_status.value

        self._update_history.append({
            "trend_id": trend_id,
            "old_status": old_status,
            "new_status": new_status.value,
            "old_roas": old_roas,
            "new_roas": new_roas,
        })

        return new_status

    def _determine_direction(self, trend: dict[str, Any],
                              old_roas: float, new_roas: float) -> TrendDirection:
        """Determine trend direction from ROAS movement."""
        history = trend["roas_history"]

        if len(history) < 3:
            return TrendDirection.STABLE

        # Look at recent trend (last 3 data points)
        recent = history[-3:]
        if all(recent[i] < recent[i + 1] for i in range(len(recent) - 1)):
            # Consistently rising
            if new_roas > trend["peak_roas"] * 0.8:
                return TrendDirection.GROWING
            return TrendDirection.EMERGING

        if all(recent[i] > recent[i + 1] for i in range(len(recent) - 1)):
            # Consistently falling
            if new_roas < trend["peak_roas"] * 0.3:
                return TrendDirection.DEAD
            return TrendDirection.DECLINING

        return TrendDirection.STABLE

    def update_batch(self, updates: list[dict[str, Any]]) -> list[TrendDirection]:
        """Update multiple trends at once.

        Args:
            updates: List of {trend_id, roas}.

        Returns:
            List of new TrendDirection for each update.
        """
        return [self.update(u["trend_id"], u["roas"]) for u in updates]

    def get_trend(self, trend_id: str) -> dict[str, Any] | None:
        """Get trend data by ID."""
        return self._trends.get(trend_id)

    def get_all_trends(self) -> dict[str, dict[str, Any]]:
        """Get all tracked trends."""
        return dict(self._trends)

    def get_by_status(self, status: TrendDirection) -> list[dict[str, Any]]:
        """Get all trends with a specific status."""
        return [
            {"trend_id": tid, **t}
            for tid, t in self._trends.items()
            if t["status"] == status.value
        ]

    def get_growing_trends(self) -> list[dict[str, Any]]:
        """Get all growing trends."""
        return self.get_by_status(TrendDirection.GROWING)

    def get_dead_trends(self) -> list[dict[str, Any]]:
        """Get all dead trends."""
        return self.get_by_status(TrendDirection.DEAD)

    def get_update_history(self) -> list[dict[str, Any]]:
        return list(self._update_history)