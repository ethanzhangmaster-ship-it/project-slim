"""
E15.2.6 IAA Revenue Optimization Autopilot — data models.

Spec sections 4/5/6/7/9 data contracts, expressed as plain dataclasses so they
are trivially testable without live MAX/Adjust data.

These wrap / reuse the proven engine in `operation.optimizer`:
  * `OptimizationExperiment` is an alias of `ExperimentDefinition` (section 6).
  * `ExperimentResult` is derived from `ImpactMeasurement` + `WinnerDecision`.

Deterministic. No LLM. No external calls.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import date as _date
from typing import Any, Dict, List, Optional

from operation.optimizer.experiments.experiment_models import (
    ExperimentDefinition,
)
from operation.optimizer.intel_models import IntelSignal


# alias: the spec's OptimizationExperiment IS the existing ExperimentDefinition
OptimizationExperiment = ExperimentDefinition


@dataclass
class RevenueOpportunity:
    """Spec §4 — one discovered place revenue could increase."""
    id: str
    app_id: str
    dimension: str            # network | geo | format | waterfall | floor
    rule: str                 # intel rule that spawned it
    action: str               # disable_network | increase_bid_opportunity | ...
    target: str               # network / country / segment key
    current_value: float = 0.0
    target_value: float = 0.0
    expected_lift: float = 0.0    # fraction (0.12 == +12% revenue)
    confidence: float = 0.0        # 0..1
    risk: float = 0.0              # 0..1
    reason: str = ""
    metrics: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_experiment(cls, exp: ExperimentDefinition,
                        sig: Optional[IntelSignal] = None) -> "RevenueOpportunity":
        m = (sig.metrics if sig else {}) or {}
        dim = {
            "zombie_network": "network",
            "hidden_winner": "network",
            "bid_floor": "floor",
            "revenue_concentration": "network",
            "geo_opportunity": "geo",
            "waterfall_waste": "waterfall",
        }.get(exp.source_rule or (sig.rule if sig else ""), "network")
        cur = float(m.get("impressions", 0) or 0)
        return cls(
            id=exp.exp_id, app_id=exp.account, dimension=dim,
            rule=exp.source_rule, action=exp.action_type, target=exp.target,
            current_value=cur,
            target_value=cur * (1.0 + (exp.expected_lift_pct or 0) / 100.0),
            expected_lift=(exp.expected_lift_pct or 0) / 100.0,
            confidence=sig.confidence if sig else 0.0,
            risk=round(1.0 - (sig.confidence if sig else 0.0), 4),
            reason=exp.hypothesis, metrics=m,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "app_id": self.app_id, "dimension": self.dimension,
            "rule": self.rule, "action": self.action, "target": self.target,
            "current_value": self.current_value, "target_value": self.target_value,
            "expected_lift": self.expected_lift, "confidence": self.confidence,
            "risk": self.risk, "reason": self.reason, "metrics": self.metrics,
        }


@dataclass
class PredictionResult:
    """Spec §5 — projected revenue impact of a proposed change."""
    change: str
    before_revenue: float
    after_revenue: float
    lift_percent: float
    confidence: float
    risk: float
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "change": self.change,
            "before_revenue": round(self.before_revenue, 2),
            "after_revenue": round(self.after_revenue, 2),
            "lift_percent": round(self.lift_percent, 2),
            "confidence": round(self.confidence, 2),
            "risk": round(self.risk, 2),
            "note": self.note,
        }


@dataclass
class ExperimentResult:
    """Spec §9 — verdict for one finished experiment."""
    exp_id: str
    target: str
    winner: bool
    lift: Optional[float]      # net impact %, None if not measurable
    confidence: float
    decision: str              # WINNER | LOSER | UNKNOWN
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exp_id": self.exp_id, "target": self.target,
            "winner": self.winner, "lift": self.lift,
            "confidence": round(self.confidence, 2),
            "decision": self.decision, "note": self.note,
        }


@dataclass
class ChangeAction:
    """Spec §7 — one atomic, operator-applied MAX change."""
    type: str                  # disable_network | change_floor | increase_bid_opportunity
    network: str
    value: Optional[float] = None
    requires_manual_apply: bool = True   # MAX Management API cannot write

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type, "network": self.network,
            "value": self.value,
            "requires_manual_apply": self.requires_manual_apply,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ChangeAction":
        return cls(type=d["type"], network=d["network"],
                   value=d.get("value"),
                   requires_manual_apply=d.get("requires_manual_apply", True))


@dataclass
class ChangePackage:
    """Spec §7 — a bundle of change actions for one experiment."""
    account: str
    experiment_id: str
    actions: List[ChangeAction] = field(default_factory=list)
    created_at: str = ""
    note: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = _date.today().isoformat()

    def write(self, out_dir: str = "change_packages") -> str:
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f"{self.account}_{self.experiment_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        return path

    def to_dict(self) -> Dict[str, Any]:
        return {
            "account": self.account, "experiment_id": self.experiment_id,
            "created_at": self.created_at, "note": self.note,
            "actions": [a.to_dict() for a in self.actions],
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ChangePackage":
        return cls(
            account=d["account"], experiment_id=d["experiment_id"],
            created_at=d.get("created_at", ""), note=d.get("note", ""),
            actions=[ChangeAction.from_dict(a) for a in d.get("actions", [])],
        )
