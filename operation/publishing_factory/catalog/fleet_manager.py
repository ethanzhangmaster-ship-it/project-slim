"""
E15.1.1 — Fleet Manager
========================

The AI scheduler that turns a static registry into a prioritized
daily work queue.

scan() inspects every GameProduct and emits FleetTask entries:

    VERSION_READY      build exists, never submitted -> publish
    METADATA_OUTDATED  version moved past published -> update listing
    ASO_OPPORTUNITY    stale keywords / no localization -> refresh
    COMPLIANCE_RISK    prior rejection -> pre-scan before resubmit
    RESUBMIT           status == rejected -> fix + resubmit

Pure scheduling logic, deterministic, no external calls.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List

from operation.publishing_factory.catalog.game_registry import GameRegistry
from operation.publishing_factory.catalog.product_profile import (
    GameProduct, GameStatus,
)


class TaskType(str, Enum):
    VERSION_READY = "version_ready"
    METADATA_OUTDATED = "metadata_outdated"
    ASO_OPPORTUNITY = "aso_opportunity"
    COMPLIANCE_RISK = "compliance_risk"
    RESUBMIT = "resubmit"


_PRIORITY = {
    TaskType.RESUBMIT: 0,           # rejected games unblock first
    TaskType.VERSION_READY: 1,      # net-new revenue
    TaskType.METADATA_OUTDATED: 2,
    TaskType.COMPLIANCE_RISK: 2,
    TaskType.ASO_OPPORTUNITY: 3,
}


@dataclass
class FleetTask:
    game_id: str
    task_type: str
    reason: str = ""
    priority: int = 9

    def to_dict(self) -> dict:
        return {"game_id": self.game_id, "task_type": self.task_type,
                "reason": self.reason, "priority": self.priority}


@dataclass
class FleetScanReport:
    scanned: int = 0
    tasks: List[FleetTask] = field(default_factory=list)
    by_type: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "scanned": self.scanned,
            "tasks": [t.to_dict() for t in self.tasks],
            "by_type": self.by_type,
        }


class FleetManager:
    """Owns a registry and produces the daily task queue."""

    def __init__(self, registry: GameRegistry):
        self.registry = registry

    # ------------------------------------------------------------------ #
    def _task_for(self, g: GameProduct) -> List[FleetTask]:
        out: List[FleetTask] = []

        # 1) rejected -> must fix + resubmit (highest priority)
        if g.status == GameStatus.REJECTED.value:
            out.append(self._mk(g, TaskType.RESUBMIT,
                                "store rejected; generate fix + resubmit"))
            return out

        # 2) never published but ready/dev -> first publish
        if g.needs_first_publish():
            if g.status == GameStatus.READY.value or g.version:
                out.append(self._mk(g, TaskType.VERSION_READY,
                                    f"v{g.version} ready, not yet submitted"))
            return out

        # 3) published but version moved -> update listing
        if g.metadata_outdated():
            out.append(self._mk(g, TaskType.METADATA_OUTDATED,
                                f"v{g.version} > published v{g.published_version}"))
            return out

        # 4) published & current -> look for ASO opportunity
        if g.is_published():
            if not g.keywords or len(g.locales) <= 1:
                out.append(self._mk(g, TaskType.ASO_OPPORTUNITY,
                                    "stale keywords / single-locale listing"))
            if g.metrics.get("store_cvr", 1.0) < 0.15:
                out.append(self._mk(g, TaskType.COMPLIANCE_RISK,
                                    "low store CVR, re-scan before next push"))
        return out

    @staticmethod
    def _mk(g: GameProduct, t: TaskType, reason: str) -> FleetTask:
        return FleetTask(game_id=g.game_id, task_type=t.value,
                         reason=reason, priority=_PRIORITY[t])

    # ------------------------------------------------------------------ #
    def scan(self) -> FleetScanReport:
        report = FleetScanReport()
        for g in self.registry.list_all():
            report.tasks.extend(self._task_for(g))
        report.tasks.sort(key=lambda t: t.priority)
        report.scanned = self.registry.count()
        by_type: dict = {}
        for t in report.tasks:
            by_type[t.task_type] = by_type.get(t.task_type, 0) + 1
        report.by_type = by_type
        return report

    # convenience alias used by the batch orchestrator
    def schedule_daily(self) -> FleetScanReport:
        return self.scan()

    def metrics_summary(self) -> dict:
        games = self.registry.list_all()
        by_status: dict = {}
        for g in games:
            by_status[g.status] = by_status.get(g.status, 0) + 1
        return {
            "total": len(games),
            "by_status": by_status,
            "genres": sorted({g.genre for g in games}),
            "published": sum(1 for g in games if g.is_published()),
        }


__all__ = ["FleetManager", "FleetTask", "FleetScanReport", "TaskType"]
