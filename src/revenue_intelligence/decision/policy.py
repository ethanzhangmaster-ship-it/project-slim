"""
E16.1.1 — Decision Policy & Confidence Gate

Transforms a raw ``GrowthAction`` (which only carries ``confidence`` + an
``impact_score``) into a richer ``GrowthDecisionScore`` that also carries
``impact``, ``risk`` and ``sample_size``, then routes the action through a
three-tier confidence gate:

    high  : confidence > 0.9  AND  risk == low  AND  sample_size >= min
            -> ApprovalRoute.AUTO
    mid   : 0.7 <= confidence < 0.9
            -> ApprovalRoute.HUMAN_QUEUE
    low   : confidence < 0.7
            -> ApprovalRoute.RECORD_ONLY

Risk is graded per-action-type and can be *downgraded one notch* when the
agent's own historical experience for that (game, action) shows a strong,
consistent winning track record -- proven-safe actions get less friction.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict

from ..models import GrowthAction, RevenueAction


class ImpactLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ApprovalRoute(str, Enum):
    AUTO = "auto"
    HUMAN_QUEUE = "human_queue"
    RECORD_ONLY = "record_only"


@dataclass
class GrowthDecisionScore:
    """A confidence-gated, risk-aware decision score for one GrowthAction."""
    action: str
    confidence: float
    impact: ImpactLevel
    risk: RiskLevel
    sample_size: int
    approval: ApprovalRoute
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "confidence": round(self.confidence, 4),
            "impact": self.impact.value,
            "risk": self.risk.value,
            "sample_size": self.sample_size,
            "approval": self.approval.value,
            "reason": self.reason,
        }


# Per-action-type default risk. Higher blast-radius actions are riskier.
_DEFAULT_RISK: Dict[str, RiskLevel] = {
    RevenueAction.INCREASE_UA_BUDGET.value: RiskLevel.LOW,
    RevenueAction.DECREASE_UA_BUDGET.value: RiskLevel.MEDIUM,
    RevenueAction.CREATE_OFFER.value: RiskLevel.LOW,
    RevenueAction.MODIFY_PRICE.value: RiskLevel.HIGH,
    RevenueAction.INVESTIGATE_RETENTION.value: RiskLevel.LOW,
    RevenueAction.ROLLBACK_VERSION.value: RiskLevel.HIGH,
    RevenueAction.SCALE_FEATURE.value: RiskLevel.MEDIUM,
}

# Per-action-type default business impact (overridden by action.impact_score).
_DEFAULT_IMPACT: Dict[str, ImpactLevel] = {
    RevenueAction.INCREASE_UA_BUDGET.value: ImpactLevel.HIGH,
    RevenueAction.DECREASE_UA_BUDGET.value: ImpactLevel.MEDIUM,
    RevenueAction.CREATE_OFFER.value: ImpactLevel.HIGH,
    RevenueAction.MODIFY_PRICE.value: ImpactLevel.HIGH,
    RevenueAction.INVESTIGATE_RETENTION.value: ImpactLevel.LOW,
    RevenueAction.ROLLBACK_VERSION.value: ImpactLevel.HIGH,
    RevenueAction.SCALE_FEATURE.value: ImpactLevel.MEDIUM,
}


class DecisionPolicy:
    """Three-tier confidence gate that converts a raw action into a route."""

    def __init__(
        self,
        high_confidence: float = 0.9,
        mid_confidence: float = 0.7,
        min_sample_size: int = 5,
        winning_success_rate: float = 0.8,
        winning_min_samples: int = 3,
        extra_risk: Dict[str, RiskLevel] | None = None,
        extra_impact: Dict[str, ImpactLevel] | None = None,
    ):
        self.high_confidence = high_confidence
        self.mid_confidence = mid_confidence
        self.min_sample_size = min_sample_size
        self.winning_success_rate = winning_success_rate
        self.winning_min_samples = winning_min_samples
        # Sibling Brain packages (e.g. E16.2 economy) extend the risk/impact
        # tables without touching the revenue defaults.
        self.risk_table: Dict[str, RiskLevel] = {**_DEFAULT_RISK, **(extra_risk or {})}
        self.impact_table: Dict[str, ImpactLevel] = {
            **_DEFAULT_IMPACT,
            **(extra_impact or {}),
        }

    # ------------------------------------------------------------------ #
    @staticmethod
    def impact_level(impact_score: float) -> ImpactLevel:
        if impact_score >= 60.0:
            return ImpactLevel.HIGH
        if impact_score >= 25.0:
            return ImpactLevel.MEDIUM
        return ImpactLevel.LOW

    def _risk_for(
        self, action_value: str, success_rate: float, sample_size: int
    ) -> RiskLevel:
        base = self.risk_table.get(action_value, RiskLevel.MEDIUM)
        if base == RiskLevel.LOW:
            return base
        # proven winning track record downgrades risk one notch
        if (
            sample_size >= self.winning_min_samples
            and success_rate >= self.winning_success_rate
        ):
            return RiskLevel.MEDIUM if base == RiskLevel.HIGH else RiskLevel.LOW
        return base

    def _impact_for(self, action_value: str, impact_score: float) -> ImpactLevel:
        if impact_score > 0.0:
            return self.impact_level(impact_score)
        return self.impact_table.get(action_value, ImpactLevel.MEDIUM)

    # ------------------------------------------------------------------ #
    def score(
        self,
        action: GrowthAction,
        *,
        sample_size: int = 0,
        success_rate: float = 0.0,
    ) -> GrowthDecisionScore:
        action_value = getattr(action.action, "value", str(action.action))
        impact = self._impact_for(action_value, action.impact_score)
        risk = self._risk_for(action_value, success_rate, sample_size)
        approval, reason = self._route(action.confidence, sample_size, risk)
        return GrowthDecisionScore(
            action=action_value,
            confidence=action.confidence,
            impact=impact,
            risk=risk,
            sample_size=sample_size,
            approval=approval,
            reason=reason,
        )

    def _route(self, confidence: float, sample_size: int, risk: RiskLevel):
        if confidence >= self.high_confidence:
            if risk == RiskLevel.LOW and sample_size >= self.min_sample_size:
                return ApprovalRoute.AUTO, (
                    "high confidence + low risk + sufficient sample -> auto-execute"
                )
            if risk == RiskLevel.LOW:
                return ApprovalRoute.HUMAN_QUEUE, (
                    f"high confidence + low risk but sample {sample_size} "
                    f"< {self.min_sample_size} -> human review"
                )
            return ApprovalRoute.HUMAN_QUEUE, (
                "high confidence but elevated risk -> human review"
            )
        if confidence >= self.mid_confidence:
            return ApprovalRoute.HUMAN_QUEUE, "mid confidence -> human approval queue"
        return ApprovalRoute.RECORD_ONLY, (
            "low confidence -> record pattern only, no execution"
        )


__all__ = [
    "ImpactLevel",
    "RiskLevel",
    "ApprovalRoute",
    "GrowthDecisionScore",
    "DecisionPolicy",
]
