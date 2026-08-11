"""
E16.6.5 — ASO Growth Loop: data models for the autonomous ASO lifecycle.

The final integration layer that closes the ASO Agent. It:

* Aggregates signals from E16.6.1 (Intelligence), E16.6.2 (Reality),
  E16.6.3 (Creative) and E16.6.4 (Memory)
* Ranks opportunities by ``Priority = Impact × Confidence × Revenue × Urgency / Cost``
* Plans actions, manages experiment lifecycle, applies safety policies,
  and collects revenue-linked feedback to close the loop.

Each ``ASOGrowthCycle`` is a state machine that runs once per game per day,
producing an ``ASOGrowthReport``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


# --------------------------------------------------------------------------- #
# 1. Stage / State enums
# --------------------------------------------------------------------------- #
class ASOGrowthStage(str, Enum):
    """Seven-stage state machine for one growth cycle."""

    DISCOVER = "DISCOVER"
    ANALYZE = "ANALYZE"
    PLAN = "PLAN"
    APPROVAL = "APPROVAL"
    EXPERIMENT = "EXPERIMENT"
    MEASURE = "MEASURE"
    LEARN = "LEARN"


class ApprovalStatus(str, Enum):
    """Whether a planned action needs human sign-off."""

    AUTO_APPROVED = "AUTO_APPROVED"
    HUMAN_QUEUE = "HUMAN_QUEUE"
    RECORD_ONLY = "RECORD_ONLY"


# --------------------------------------------------------------------------- #
# 2. One growth cycle
# --------------------------------------------------------------------------- #
@dataclass
class ASOGrowthCycle:
    """Represents one optimisation cycle for one game.

    Each cycle progresses through the seven stages, recording what actions
    were taken at each step.
    """

    cycle_id: str
    game_id: str
    platform: str
    stage: ASOGrowthStage = ASOGrowthStage.DISCOVER
    current_actions: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)

    def advance(self, next_stage: ASOGrowthStage) -> None:
        """Transition to the next stage."""
        self.stage = next_stage
        self.updated_at = _now_iso()

    def add_action(self, action: str) -> None:
        if action not in self.current_actions:
            self.current_actions.append(action)
            self.updated_at = _now_iso()

    def is_terminal(self) -> bool:
        return self.stage == ASOGrowthStage.LEARN

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "game_id": self.game_id,
            "platform": self.platform,
            "stage": self.stage.value,
            "current_actions": self.current_actions,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ASOGrowthCycle":
        return cls(
            cycle_id=d.get("cycle_id", ""),
            game_id=d.get("game_id", ""),
            platform=d.get("platform", ""),
            stage=ASOGrowthStage(d.get("stage", "DISCOVER")),
            current_actions=list(d.get("current_actions", [])),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
        )


# --------------------------------------------------------------------------- #
# 3. Aggregated opportunity (multi-signal)
# --------------------------------------------------------------------------- #
@dataclass
class ASOOpportunity:
    """A combined ASO growth opportunity from multiple signal sources.

    ``source_signals`` records which modules contributed the signal
    (e.g. "aso_reality", "creative_optimization", "experiment_memory").
    ``priority_score`` is computed by the Priority Engine.
    """

    opportunity_id: str
    game_id: str
    title: str
    description: str = ""
    source_signals: Dict[str, float] = field(default_factory=dict)
    impact: float = 0.0
    confidence: float = 0.0
    revenue_potential: float = 0.0
    urgency: float = 0.0
    cost: float = 1.0  # default neutral
    priority_score: float = 0.0
    suggested_action: str = ""
    created_at: str = field(default_factory=_now_iso)

    def compute_priority(self) -> float:
        """Priority = Impact × Confidence × Revenue_Potential × Urgency / Cost."""
        score = (
            self.impact * self.confidence * self.revenue_potential * self.urgency
        ) / max(self.cost, 0.01)
        self.priority_score = round(score, 6)
        return self.priority_score

    def to_dict(self) -> Dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "game_id": self.game_id,
            "title": self.title,
            "description": self.description,
            "source_signals": self.source_signals,
            "impact": round(self.impact, 4),
            "confidence": round(self.confidence, 4),
            "revenue_potential": round(self.revenue_potential, 4),
            "urgency": round(self.urgency, 4),
            "cost": round(self.cost, 4),
            "priority_score": round(self.priority_score, 4),
            "suggested_action": self.suggested_action,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ASOOpportunity":
        opp = cls(
            opportunity_id=d.get("opportunity_id", ""),
            game_id=d.get("game_id", ""),
            title=d.get("title", ""),
            description=d.get("description", ""),
            source_signals=d.get("source_signals") or {},
            impact=float(d.get("impact", 0.0)),
            confidence=float(d.get("confidence", 0.0)),
            revenue_potential=float(d.get("revenue_potential", 0.0)),
            urgency=float(d.get("urgency", 0.0)),
            cost=float(d.get("cost", 1.0)),
            suggested_action=d.get("suggested_action", ""),
            created_at=d.get("created_at", ""),
        )
        opp.priority_score = float(d.get("priority_score", 0.0))
        return opp


# --------------------------------------------------------------------------- #
# 4. Action plan (from scheduler)
# --------------------------------------------------------------------------- #
@dataclass
class ASOActionPlan:
    """A concrete plan derived from an opportunity.

    ``steps`` are ordered execution steps (non-binding — the Growth Loop may
    only run the first subset depending on policy).
    ``approval_status`` is set by the Policy Gate.
    """

    plan_id: str
    game_id: str
    opportunity_id: str
    action: str  # ASOAction value or experiment action
    title: str
    steps: List[str] = field(default_factory=list)
    high_risk: bool = False
    approval_status: ApprovalStatus = ApprovalStatus.AUTO_APPROVED
    expected_impact: float = 0.0
    expected_confidence: float = 0.0
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "game_id": self.game_id,
            "opportunity_id": self.opportunity_id,
            "action": self.action,
            "title": self.title,
            "steps": self.steps,
            "high_risk": self.high_risk,
            "approval_status": self.approval_status.value,
            "expected_impact": round(self.expected_impact, 4),
            "expected_confidence": round(self.expected_confidence, 4),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ASOActionPlan":
        return cls(
            plan_id=d.get("plan_id", ""),
            game_id=d.get("game_id", ""),
            opportunity_id=d.get("opportunity_id", ""),
            action=d.get("action", ""),
            title=d.get("title", ""),
            steps=list(d.get("steps", [])),
            high_risk=bool(d.get("high_risk", False)),
            approval_status=ApprovalStatus(
                d.get("approval_status", "AUTO_APPROVED")
            ),
            expected_impact=float(d.get("expected_impact", 0.0)),
            expected_confidence=float(d.get("expected_confidence", 0.0)),
            created_at=d.get("created_at", ""),
        )


# --------------------------------------------------------------------------- #
# 5. Daily growth report
# --------------------------------------------------------------------------- #
@dataclass
class ASOGrowthReport:
    """Output of a day's growth cycle: what was found, planned, and done."""

    report_id: str
    game_id: str
    date: str  # ISO date (e.g. "2026-07-28")
    cycle: Optional[ASOGrowthCycle] = None
    opportunities: List[ASOOpportunity] = field(default_factory=list)
    plans: List[ASOActionPlan] = field(default_factory=list)
    experiments_created: int = 0
    patterns_updated: int = 0
    revenue_feedback_applied: bool = False
    created_at: str = field(default_factory=_now_iso)

    def top_opportunities(self, k: int = 3) -> List[ASOOpportunity]:
        """Highest-priority opportunities."""
        sorted_ops = sorted(
            self.opportunities, key=lambda o: o.priority_score, reverse=True
        )
        return sorted_ops[:k]

    def to_markdown(self) -> str:
        """Human-readable daily ASO report (the spec's format)."""
        lines: List[str] = []
        lines.append(f"# ASO Growth Report")
        lines.append(f"")
        lines.append(f"**Game:** {self.game_id}")
        lines.append(f"**Date:** {self.date}")
        if self.cycle:
            lines.append(f"**Stage:** {self.cycle.stage.value}")
        lines.append(f"")
        lines.append(f"## Opportunities")
        top = self.top_opportunities(5)
        if not top:
            lines.append(f"\nNo opportunities identified.\n")
        else:
            for i, opp in enumerate(top, 1):
                pct = f"{opp.priority_score:.2f}"
                lines.append(f"")
                lines.append(f"### {i}. {opp.title}")
                lines.append(f"")
                lines.append(f"**Impact:** {opp.impact:.2f}")
                lines.append(f"**Confidence:** {opp.confidence:.2f}")
                lines.append(f"**Priority Score:** {pct}")
                if opp.suggested_action:
                    lines.append(f"")
                    lines.append(f"**Recommended:** {opp.suggested_action}")
                if opp.source_signals:
                    lines.append(f"")
                    lines.append(f"**Signals from:**")
                    for src, val in opp.source_signals.items():
                        lines.append(f"  - {src}: {val:.2f}")
                lines.append(f"")

        if self.plans:
            lines.append(f"## Action Plans")
            for plan in self.plans:
                status = plan.approval_status.value
                lines.append(f"")
                lines.append(f"- **{plan.action}** ({status})")
                if plan.steps:
                    for step in plan.steps:
                        lines.append(f"  - {step}")
                lines.append(f"")

        if self.experiments_created > 0:
            lines.append(f"**Experiments created:** {self.experiments_created}")
        if self.patterns_updated > 0:
            lines.append(f"**Patterns updated:** {self.patterns_updated}")
        if self.revenue_feedback_applied:
            lines.append(f"**Revenue feedback:** Applied")

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "game_id": self.game_id,
            "date": self.date,
            "cycle": self.cycle.to_dict() if self.cycle else None,
            "opportunities": [o.to_dict() for o in self.opportunities],
            "plans": [p.to_dict() for p in self.plans],
            "experiments_created": self.experiments_created,
            "patterns_updated": self.patterns_updated,
            "revenue_feedback_applied": self.revenue_feedback_applied,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ASOGrowthReport":
        return cls(
            report_id=d.get("report_id", ""),
            game_id=d.get("game_id", ""),
            date=d.get("date", ""),
            cycle=ASOGrowthCycle.from_dict(d["cycle"])
            if d.get("cycle") else None,
            opportunities=[
                ASOOpportunity.from_dict(o) for o in d.get("opportunities", [])
            ],
            plans=[
                ASOActionPlan.from_dict(p) for p in d.get("plans", [])
            ],
            experiments_created=int(d.get("experiments_created", 0)),
            patterns_updated=int(d.get("patterns_updated", 0)),
            revenue_feedback_applied=bool(d.get("revenue_feedback_applied", False)),
            created_at=d.get("created_at", ""),
        )


__all__ = [
    "ASOGrowthStage",
    "ApprovalStatus",
    "ASOGrowthCycle",
    "ASOOpportunity",
    "ASOActionPlan",
    "ASOGrowthReport",
]
