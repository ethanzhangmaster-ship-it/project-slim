"""E10.2 Phase 5 — Optimization Schema.

Defines the core optimization domain objects that bridge
LearningSignal feedback into actionable campaign mutations.

Core entities:
  - OptimizationDecision: feedback → action decision
  - MutationPlan: decision → specific budget/status mutation
  - CampaignScore: multi-campaign ranking for allocation
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class OptimizationDecision:
    """A decision derived from LearningSignal feedback.

    Maps a feedback signal to a concrete action with
    confidence and expected impact.
    """
    decision_id: str = ""
    campaign_id: str = ""
    action: str = ""            # SCALE / KILL / WATCH / RETEST
    confidence: float = 0.0
    reason: str = ""
    expected_impact: float = 0.0
    metrics: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.decision_id:
            self.decision_id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "campaign_id": self.campaign_id,
            "action": self.action,
            "confidence": round(self.confidence, 2),
            "reason": self.reason,
            "expected_impact": round(self.expected_impact, 2),
            "metrics": self.metrics,
            "created_at": self.created_at,
        }


@dataclass
class MutationPlan:
    """A concrete mutation to apply to a campaign.

    Maps an OptimizationDecision into specific budget/status
    changes with before/after values for audit trail.
    """
    plan_id: str = ""
    campaign_id: str = ""
    decision_id: str = ""
    mutation_type: str = ""       # BUDGET_CHANGE / STATUS_CHANGE / DUPLICATE
    action: str = ""              # SCALE / KILL / RETEST
    budget_before: float = 0.0
    budget_after: float = 0.0
    budget_delta: float = 0.0
    status_before: str = ""
    status_after: str = ""
    expected_gain: float = 0.0
    source_campaign_id: str = ""  # For RETEST (duplicate)
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.plan_id:
            self.plan_id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if self.budget_delta == 0.0 and self.mutation_type == "BUDGET_CHANGE":
            self.budget_delta = round(self.budget_after - self.budget_before, 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "campaign_id": self.campaign_id,
            "decision_id": self.decision_id,
            "mutation_type": self.mutation_type,
            "action": self.action,
            "budget_before": round(self.budget_before, 2),
            "budget_after": round(self.budget_after, 2),
            "budget_delta": round(self.budget_delta, 2),
            "status_before": self.status_before,
            "status_after": self.status_after,
            "expected_gain": round(self.expected_gain, 2),
            "source_campaign_id": self.source_campaign_id,
            "created_at": self.created_at,
        }


@dataclass
class CampaignScore:
    """Score for multi-campaign ranking in experiment allocation.

    Used by ExperimentAllocator to rank campaigns by ROAS
    and allocate budget proportionally.
    """
    campaign_id: str = ""
    roas: float = 0.0
    spend: float = 0.0
    revenue: float = 0.0
    score: float = 0.0
    rank: int = 0
    action: str = ""  # SCALE / KILL / WATCH

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "roas": round(self.roas, 2),
            "spend": round(self.spend, 2),
            "revenue": round(self.revenue, 2),
            "score": round(self.score, 2),
            "rank": self.rank,
            "action": self.action,
        }