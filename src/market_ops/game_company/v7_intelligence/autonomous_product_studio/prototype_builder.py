"""Prototype building module for autonomous product studio."""

from dataclasses import dataclass, field
from typing import List, Dict, Any
import random
import uuid


@dataclass
class Feature:
    """Represents a prototype feature."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    status: str = ""  # planned, in_progress, implemented, tested
    priority: str = ""  # low, medium, high, critical
    estimated_hours: float = 0.0
    dependencies: List[str] = field(default_factory=list)


@dataclass
class EffortEstimate:
    """Effort estimation for a prototype."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    total_hours: float = 0.0
    total_days: float = 0.0
    team_size: int = 0
    risk_buffer_hours: float = 0.0
    breakdown: Dict[str, float] = field(default_factory=dict)


class PrototypeBuilder:
    """Builds game prototypes and tracks feature development."""

    def __init__(self):
        self._features: List[Feature] = []
        self._design: Any | None = None
        self._effort: EffortEstimate | None = None

    def build_prototype(self, design: Any) -> List[Feature]:
        """Build a prototype based on a game design."""
        self._design = design
        feature_specs = [
            ("Core Movement", "high", 16.0),
            ("Basic Combat", "high", 24.0),
            ("UI Framework", "high", 20.0),
            ("Inventory System", "medium", 12.0),
            ("Save/Load", "medium", 8.0),
            ("Audio Manager", "low", 10.0),
            ("Particle Effects", "low", 6.0),
            ("Analytics Hook", "medium", 4.0),
        ]
        self._features = [
            Feature(
                name=name,
                status=random.choice(["planned", "in_progress", "implemented"]),
                priority=priority,
                estimated_hours=hours,
                dependencies=[],
            )
            for name, priority, hours in feature_specs
        ]
        return self._features

    def get_features(self) -> List[Feature]:
        """Return the current list of prototype features."""
        return self._features

    def estimate_effort(self) -> EffortEstimate:
        """Estimate development effort for the prototype."""
        if not self._features:
            self.build_prototype(None)
        total_hours = sum(f.estimated_hours for f in self._features)
        team_size = random.randint(2, 5)
        risk_buffer = round(total_hours * 0.2, 2)
        breakdown = {
            "programming": round(total_hours * 0.5, 2),
            "art": round(total_hours * 0.25, 2),
            "design": round(total_hours * 0.15, 2),
            "qa": round(total_hours * 0.1, 2),
        }
        self._effort = EffortEstimate(
            total_hours=round(total_hours + risk_buffer, 2),
            total_days=round((total_hours + risk_buffer) / (team_size * 6), 2),
            team_size=team_size,
            risk_buffer_hours=risk_buffer,
            breakdown=breakdown,
        )
        return self._effort
