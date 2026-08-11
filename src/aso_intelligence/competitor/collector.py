"""
E16.6.10 — Competitor Collector.

Collects competitor data from providers (E16.6.2 CompetitorProvider bridge,
manual data, or built-in deterministic stubs for testing).
"""

from __future__ import annotations

from typing import Dict, List, Optional

from src.aso_intelligence.competitor.models import CompetitorSnapshot


class CompetitorCollector:
    """Collect competitor snapshots from one or more sources."""

    def __init__(self):
        self._snapshots: Dict[str, List[CompetitorSnapshot]] = {}

    # ------------------------------------------------------------------ #
    def record_snapshot(self, snapshot: CompetitorSnapshot) -> None:
        """Store a single snapshot."""
        key = f"{snapshot.app_id}:{snapshot.country}"
        if key not in self._snapshots:
            self._snapshots[key] = []
        self._snapshots[key].append(snapshot)

    def record_batch(self, snapshots: List[CompetitorSnapshot]) -> None:
        for s in snapshots:
            self.record_snapshot(s)

    # ------------------------------------------------------------------ #
    def latest_snapshot(
        self, app_id: str, country: str
    ) -> Optional[CompetitorSnapshot]:
        """Most recent snapshot for a competitor in a country."""
        key = f"{app_id}:{country}"
        snaps = self._snapshots.get(key, [])
        if not snaps:
            return None
        return snaps[-1]

    def previous_snapshot(
        self, app_id: str, country: str
    ) -> Optional[CompetitorSnapshot]:
        """Second-most-recent snapshot (for comparison)."""
        key = f"{app_id}:{country}"
        snaps = self._snapshots.get(key, [])
        if len(snaps) < 2:
            return None
        return snaps[-2]

    def history(
        self, app_id: str, country: str
    ) -> List[CompetitorSnapshot]:
        key = f"{app_id}:{country}"
        return self._snapshots.get(key, [])

    # ------------------------------------------------------------------ #
    def all_competitors(self) -> List[str]:
        """List all tracked app_ids."""
        apps = set()
        for key in self._snapshots:
            app_id = key.split(":")[0]
            apps.add(app_id)
        return sorted(apps)

    # ------------------------------------------------------------------ #
    def clear(self) -> None:
        self._snapshots.clear()


__all__ = ["CompetitorCollector"]
