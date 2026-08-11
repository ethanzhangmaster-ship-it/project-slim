"""
E15.2.5 — Shared score data models for the scoring layer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class Dimension:
    """One weighted sub-score inside a composite score."""
    name: str
    value: float          # 0-100
    weight: float         # relative weight within the composite
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "value": round(self.value, 1),
                "weight": self.weight, "detail": self.detail}


@dataclass
class ScoreResult:
    """A composite 0-100 score with its dimension breakdown."""
    kind: str                       # health | opportunity | risk
    score: int                      # 0-100 (rounded)
    grade: str                      # A/B/C/D (health) | HIGH/MEDIUM/LOW (opp/risk)
    headline: str                   # one-line human summary
    dimensions: List[Dimension] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind, "score": self.score, "grade": self.grade,
            "headline": self.headline,
            "dimensions": [d.to_dict() for d in self.dimensions],
            "metrics": self.metrics,
        }

    @staticmethod
    def weighted(dims: List[Dimension]) -> float:
        wsum = sum(d.weight for d in dims) or 1.0
        return sum(d.value * d.weight for d in dims) / wsum
