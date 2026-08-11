"""
E15.2.4 v2 — Optimization Data Models

OptimizationSignal: detected issue or opportunity
OptimizationAction: a proposed change
OptimizationPlan: ordered set of actions for one game
OptimizationResult: execution outcome
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class OptimizationSignal:
    """A detected monetization issue or opportunity."""
    game_id: str
    signal_type: str        # ecpm_decline | fill_drop | revenue_anomaly | floor_opportunity | network_underperform
    country: str
    platform: str
    ad_format: str          # rewarded | interstitial | banner | app_open

    metric: str             # ecpm | fill_rate | revenue_daily | impressions
    current_value: float
    expected_value: float   # baseline or threshold
    change_pct: float       # negative = decline

    severity: str           # critical | warning | info
    description: str
    suggested_action: str   # raise_bid_floor | lower_floor | reorder_waterfall | add_network | adjust_frequency
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_critical(self) -> bool:
        return self.severity == "critical"

    @property
    def is_opportunity(self) -> bool:
        return self.change_pct > 0


@dataclass
class OptimizationAction:
    """A concrete optimization action to execute."""
    action_id: str
    action_type: str        # raise_bid_floor | lower_bid_floor | reorder_waterfall | add_network | remove_network | adjust_frequency
    game_id: str
    provider: str           # max | admob | levelplay
    country: str
    ad_format: str

    changes: Dict[str, Any] = field(default_factory=dict)
    # e.g. {"new_floor": 35.0, "old_floor": 30.0} or {"new_order": ["AppLovin", "Mintegral"]}

    expected_impact: Dict[str, Any] = field(default_factory=dict)
    # e.g. {"revenue_change_pct": 5.0, "ecpm_change_pct": 3.0}

    priority: int = 0       # 0=critical, 1=high, 2=medium, 3=low
    source_signal: Optional[OptimizationSignal] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type,
            "game_id": self.game_id,
            "provider": self.provider,
            "country": self.country,
            "ad_format": self.ad_format,
            "changes": self.changes,
            "expected_impact": self.expected_impact,
            "priority": self.priority,
        }


@dataclass
class OptimizationPlan:
    """Ordered set of optimization actions for one game."""
    plan_id: str
    game_id: str
    created_at: float = 0.0
    actions: List[OptimizationAction] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def total_actions(self) -> int:
        return len(self.actions)

    @property
    def critical_actions(self) -> List[OptimizationAction]:
        return [a for a in self.actions if a.priority == 0]

    def sorted_by_priority(self) -> List[OptimizationAction]:
        return sorted(self.actions, key=lambda a: (a.priority, a.action_type))


@dataclass
class OptimizationResult:
    """Outcome of executing an optimization plan."""
    plan_id: str
    game_id: str
    actions_total: int = 0
    actions_executed: int = 0
    actions_blocked: int = 0
    actions_failed: int = 0
    results: List[Dict[str, Any]] = field(default_factory=list)
    # each: {"action_id": "...", "status": "executed"|"blocked"|"failed", "reason": "...", "provider_result": {...}}

    @property
    def success_rate(self) -> float:
        if self.actions_total == 0:
            return 1.0
        return self.actions_executed / self.actions_total

    @property
    def summary(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "game_id": self.game_id,
            "actions_total": self.actions_total,
            "executed": self.actions_executed,
            "blocked": self.actions_blocked,
            "failed": self.actions_failed,
            "success_rate": round(self.success_rate, 3),
        }
