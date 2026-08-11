"""
E16.6.11 — ASO Update Strategy: data models.

The operational rhythm decision layer for ASO. Decides WHEN to update
the store, WHAT to update, and how much RISK is acceptable.

Key concepts:
  * ``ASOUpdateSignal`` — aggregated signals from all ASO modules
  * ``UpdateType`` — what kind of update to perform (or HOLD)
  * ``UpdateOpportunityScore`` — ProblemSeverity × Opportunity × Confidence − Risk
  * ``UpdatePlan`` — the final decision (what, when, where, risk)
  * ``UpdateStrategyReport`` — daily output
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# 1. Update types and risk levels
# --------------------------------------------------------------------------- #
class UpdateType(str, Enum):
    """Type of store update to perform."""
    SCREENSHOT = "UPDATE_SCREENSHOT"
    ICON = "UPDATE_ICON"
    KEYWORD = "KEYWORD_REFRESH"
    FULL_LISTING = "FULL_LISTING_UPDATE"
    HOLD = "HOLD"


class RiskLevel(str, Enum):
    """Risk assessment for the update."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    BLOCKED = "BLOCKED"


# --------------------------------------------------------------------------- #
# 2. Update signal — aggregated from all ASO modules
# --------------------------------------------------------------------------- #
@dataclass
class ASOUpdateSignal:
    """Aggregated signals that feed the timing engine."""

    game_id: str
    market: str

    # Store performance
    cvr_change: float = 0.0  # negative = declining
    ranking_change: float = 0.0  # negative = dropping
    organic_install_change: float = 0.0

    # User feedback
    rating_change: float = 0.0
    review_sentiment: float = 0.0  # 0 = negative, 1 = positive

    # Competition
    competitor_pressure: float = 0.0  # 0–1

    # Lifecycle
    days_since_update: int = 0
    experiment_running: bool = False
    date: str = ""
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "market": self.market,
            "cvr_change": round(self.cvr_change, 4),
            "ranking_change": round(self.ranking_change, 4),
            "organic_install_change": round(self.organic_install_change, 4),
            "rating_change": round(self.rating_change, 4),
            "review_sentiment": round(self.review_sentiment, 4),
            "competitor_pressure": round(self.competitor_pressure, 4),
            "days_since_update": self.days_since_update,
            "experiment_running": self.experiment_running,
            "date": self.date,
            "created_at": self.created_at,
        }


# --------------------------------------------------------------------------- #
# 3. Update opportunity score
# --------------------------------------------------------------------------- #
@dataclass
class UpdateOpportunityScore:
    """Overall score for whether now is a good time to update.

    ``score = problem_severity × market_opportunity × timing_confidence − update_risk``

    Components (all 0–1):
      * problem_severity — how badly the store is underperforming
      * market_opportunity — potential gain from updating
      * timing_confidence — how sure we are about the timing
      * update_risk — risk of doing the update
    """

    problem_severity: float = 0.0
    market_opportunity: float = 0.0
    timing_confidence: float = 0.0
    update_risk: float = 0.0
    score: float = 0.0
    recommendation: str = "HOLD"

    def compute(self) -> float:
        self.score = round(
            self.problem_severity * self.market_opportunity * self.timing_confidence
            - self.update_risk,
            4,
        )

        if self.score >= 0.5:
            self.recommendation = "IMMEDIATE_UPDATE"
        elif self.score >= 0.2:
            self.recommendation = "PLAN_UPDATE"
        elif self.score >= 0:
            self.recommendation = "MONITOR"
        else:
            self.recommendation = "HOLD"

        return self.score

    def to_dict(self) -> Dict[str, Any]:
        return {
            "problem_severity": round(self.problem_severity, 4),
            "market_opportunity": round(self.market_opportunity, 4),
            "timing_confidence": round(self.timing_confidence, 4),
            "update_risk": round(self.update_risk, 4),
            "score": self.score,
            "recommendation": self.recommendation,
        }


# --------------------------------------------------------------------------- #
# 4. Update plan — final decision
# --------------------------------------------------------------------------- #
@dataclass
class UpdatePlan:
    """One store update plan — what, where, when, and risk."""

    game_id: str
    market: str
    update_type: UpdateType
    score: float = 0.0
    confidence: float = 0.0
    risk_level: RiskLevel = RiskLevel.LOW
    reason: str = ""
    expected_cvr_uplift: float = 0.0
    expected_revenue_uplift: float = 0.0
    requires_human_approval: bool = False
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "market": self.market,
            "update_type": self.update_type.value,
            "score": round(self.score, 4),
            "confidence": round(self.confidence, 4),
            "risk_level": self.risk_level.value,
            "reason": self.reason,
            "expected_cvr_uplift": round(self.expected_cvr_uplift, 4),
            "expected_revenue_uplift": round(self.expected_revenue_uplift, 4),
            "requires_human_approval": self.requires_human_approval,
            "created_at": self.created_at,
        }


# --------------------------------------------------------------------------- #
# 5. Update experience — for memory learning
# --------------------------------------------------------------------------- #
@dataclass
class ASOUpdateExperience:
    """Record of one update and its revenue outcome."""

    game_id: str
    market: str
    update_type: UpdateType
    cvr_before: float = 0.0
    cvr_after: float = 0.0
    revenue_change: float = 0.0
    success: bool = False
    days_since_previous: int = 0
    notes: str = ""
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "market": self.market,
            "update_type": self.update_type.value,
            "cvr_before": round(self.cvr_before, 4),
            "cvr_after": round(self.cvr_after, 4),
            "revenue_change": round(self.revenue_change, 4),
            "success": self.success,
            "days_since_previous": self.days_since_previous,
            "notes": self.notes,
            "created_at": self.created_at,
        }


# --------------------------------------------------------------------------- #
# 6. Daily report
# --------------------------------------------------------------------------- #
@dataclass
class UpdateStrategyReport:
    """Daily ASO update strategy output."""

    game_id: str
    date: str
    signals: Optional[ASOUpdateSignal] = None
    opportunity_score: Optional[UpdateOpportunityScore] = None
    plan: Optional[UpdatePlan] = None
    seasonality_notes: List[str] = field(default_factory=list)
    patterns_learned: int = 0
    created_at: str = field(default_factory=_now_iso)

    def to_markdown(self) -> str:
        lines: List[str] = []
        lines.append(f"# ASO Update Strategy Report")
        lines.append(f"")
        lines.append(f"**Game:** {self.game_id}")
        lines.append(f"**Date:** {self.date}")
        lines.append(f"")

        if self.opportunity_score:
            os = self.opportunity_score
            lines.append(f"## Update Opportunity")
            lines.append(f"- **Score:** {os.score:.2f}")
            lines.append(f"- **Recommendation:** {os.recommendation}")
            lines.append(f"- **Problem Severity:** {os.problem_severity:.2f}")
            lines.append(f"- **Market Opportunity:** {os.market_opportunity:.2f}")
            lines.append(f"- **Timing Confidence:** {os.timing_confidence:.2f}")
            lines.append(f"- **Update Risk:** {os.update_risk:.2f}")
            lines.append(f"")

        if self.plan:
            p = self.plan
            lines.append(f"## Update Plan")
            lines.append(f"- **Action:** {p.update_type.value}")
            lines.append(f"- **Market:** {p.market}")
            lines.append(f"- **Confidence:** {p.confidence:.0%}")
            lines.append(f"- **Risk Level:** {p.risk_level.value}")
            lines.append(f"- **Reason:** {p.reason}")
            if p.expected_cvr_uplift > 0:
                lines.append(f"- **Expected CVR:** +{p.expected_cvr_uplift:.0%}")
            if p.expected_revenue_uplift > 0:
                lines.append(f"- **Expected Revenue:** +{p.expected_revenue_uplift:.0%}")
            if p.requires_human_approval:
                lines.append(f"- ⚠️ **Requires Human Approval**")
            lines.append(f"")

        if self.seasonality_notes:
            lines.append(f"## Seasonality")
            for note in self.seasonality_notes:
                lines.append(f"- {note}")
            lines.append(f"")

        if self.patterns_learned:
            lines.append(f"**Patterns learned:** {self.patterns_learned}")

        return "\n".join(lines)


__all__ = [
    "UpdateType",
    "RiskLevel",
    "ASOUpdateSignal",
    "UpdateOpportunityScore",
    "UpdatePlan",
    "ASOUpdateExperience",
    "UpdateStrategyReport",
]
