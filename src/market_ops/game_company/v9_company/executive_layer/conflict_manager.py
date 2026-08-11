from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum


class ConflictSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ResolutionStrategy:
    strategy_id: str
    name: str
    description: str = ""
    success_rate: float = 0.5
    applicable_severities: List[ConflictSeverity] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "name": self.name,
            "description": self.description,
            "success_rate": self.success_rate,
            "applicable_severities": [s.value for s in self.applicable_severities],
        }


@dataclass
class ConflictResolution:
    resolution_id: str
    conflict_id: str
    strategy: Optional[ResolutionStrategy] = None
    outcome: str = ""
    resolved_by: str = ""
    resolved_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "resolution_id": self.resolution_id,
            "conflict_id": self.conflict_id,
            "strategy": self.strategy.to_dict() if self.strategy else None,
            "outcome": self.outcome,
            "resolved_by": self.resolved_by,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


@dataclass
class Conflict:
    conflict_id: str
    title: str
    description: str = ""
    severity: ConflictSeverity = ConflictSeverity.MEDIUM
    parties: List[str] = field(default_factory=list)
    status: str = "open"
    resolution: Optional[ConflictResolution] = None
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "title": self.title,
            "description": self.description,
            "severity": self.severity.value,
            "parties": self.parties,
            "status": self.status,
            "resolution": self.resolution.to_dict() if self.resolution else None,
            "created_at": self.created_at.isoformat(),
        }


class ConflictManager:
    def __init__(self):
        self._conflicts: Dict[str, Conflict] = {}
        self._resolution_history: List[ConflictResolution] = []

    def detect_conflicts(self) -> List[Conflict]:
        detected = [
            Conflict(
                conflict_id="conf_001",
                title="Budget contention between UA and Product",
                description="Both departments requested additional Q3 budget.",
                severity=ConflictSeverity.HIGH,
                parties=["ua", "product"],
                status="open",
            ),
            Conflict(
                conflict_id="conf_002",
                title="Engineering capacity shortage",
                description="Too many parallel initiatives for available engineers.",
                severity=ConflictSeverity.MEDIUM,
                parties=["product", "tech"],
                status="open",
            ),
        ]
        for c in detected:
            self._conflicts[c.conflict_id] = c
        return detected

    def resolve_conflict(self, conflict_id: str) -> Optional[ConflictResolution]:
        conflict = self._conflicts.get(conflict_id)
        if not conflict or conflict.status != "open":
            return None

        strategy = ResolutionStrategy(
            strategy_id="strat_001",
            name="Compromise split",
            description="Split resources 60/40 based on ROI projection.",
            success_rate=0.75,
            applicable_severities=[ConflictSeverity.MEDIUM, ConflictSeverity.HIGH],
        )

        resolution = ConflictResolution(
            resolution_id=f"res_{conflict_id}",
            conflict_id=conflict_id,
            strategy=strategy,
            outcome="Accepted by both parties",
            resolved_by="executive_layer",
            resolved_at=datetime.now(),
        )

        conflict.resolution = resolution
        conflict.status = "resolved"
        self._resolution_history.append(resolution)
        return resolution

    def escalate_conflict(self, conflict_id: str) -> Optional[Conflict]:
        conflict = self._conflicts.get(conflict_id)
        if not conflict:
            return None

        if conflict.severity == ConflictSeverity.LOW:
            conflict.severity = ConflictSeverity.MEDIUM
        elif conflict.severity == ConflictSeverity.MEDIUM:
            conflict.severity = ConflictSeverity.HIGH
        elif conflict.severity == ConflictSeverity.HIGH:
            conflict.severity = ConflictSeverity.CRITICAL

        conflict.status = "escalated"
        return conflict

    def get_conflict_status(self, conflict_id: str) -> Optional[Dict[str, Any]]:
        conflict = self._conflicts.get(conflict_id)
        if not conflict:
            return None
        return {
            "conflict_id": conflict.conflict_id,
            "status": conflict.status,
            "severity": conflict.severity.value,
            "has_resolution": conflict.resolution is not None,
        }

    def get_conflict_history(self) -> List[Conflict]:
        return list(self._conflicts.values())

    def get_stats(self) -> Dict[str, Any]:
        total = len(self._conflicts)
        open_count = sum(1 for c in self._conflicts.values() if c.status == "open")
        resolved = sum(1 for c in self._conflicts.values() if c.status == "resolved")
        escalated = sum(1 for c in self._conflicts.values() if c.status == "escalated")
        return {
            "total_conflicts": total,
            "open": open_count,
            "resolved": resolved,
            "escalated": escalated,
            "resolution_rate": resolved / total if total else 0.0,
        }
