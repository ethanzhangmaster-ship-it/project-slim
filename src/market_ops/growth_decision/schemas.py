"""E9.9.5: Growth Decision Layer — Core Data Models.

Growth Control Plane: converts E9.9 experiment results into
executable growth decisions for E10 Autonomous Growth.

Core entities:
  - GrowthDecision: experiment result → growth action
  - CreativePortfolio: creative asset lifecycle management
  - ScalePlan: automated budget scaling with guardrails
  - RiskReport: E10 safety gate (blocking signal)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
from typing import Any


# ═══════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════

class GrowthAction(str, Enum):
    """Growth decision action types."""
    SCALE = "SCALE"
    KILL = "KILL"
    WATCH = "WATCH"
    RETEST = "RETEST"


class WinnerLevel(str, Enum):
    """4-level winner classification from E9.9 experiment results."""
    WINNER = "WINNER"
    PROMISING = "PROMISING"
    FAILED = "FAILED"
    INCONCLUSIVE = "INCONCLUSIVE"


class PortfolioBucket(str, Enum):
    """3-tier portfolio allocation model."""
    EXPLORATION = "EXPLORATION"
    GROWTH = "GROWTH"
    HARVEST = "HARVEST"


class LifecycleStage(str, Enum):
    """Creative asset lifecycle stages."""
    NEW = "NEW"
    TESTING = "TESTING"
    GROWING = "GROWING"
    MATURE = "MATURE"
    HARVEST = "HARVEST"
    RETIRED = "RETIRED"


class ScaleStatus(str, Enum):
    """Scale plan execution status."""
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"


class RiskLevel(str, Enum):
    """Overall risk level for E10 safety gate."""
    SAFE = "SAFE"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


# ═══════════════════════════════════════════════════════════
# GrowthDecision
# ═══════════════════════════════════════════════════════════

@dataclass
class GrowthDecision:
    """E9.9 experiment result → E10 executable growth action.

    Answers: "What should we do next with this creative?"
    """
    decision_id: str = ""
    experiment_id: str = ""
    creative_id: str = ""

    # Decision
    decision: str = GrowthAction.WATCH.value
    # SCALE / KILL / WATCH / RETEST

    winner_level: str = WinnerLevel.INCONCLUSIVE.value
    # WINNER / PROMISING / FAILED / INCONCLUSIVE

    reason: str = ""

    confidence: float = 0.0

    # Budget change
    budget_before: float = 0.0
    budget_after: float = 0.0

    # Metadata
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "experiment_id": self.experiment_id,
            "creative_id": self.creative_id,
            "decision": self.decision,
            "winner_level": self.winner_level,
            "reason": self.reason,
            "confidence": round(self.confidence, 3),
            "budget_before": round(self.budget_before, 2),
            "budget_after": round(self.budget_after, 2),
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════
# CreativePortfolio
# ═══════════════════════════════════════════════════════════

@dataclass
class CreativePortfolio:
    """Creative asset lifecycle management.

    Tracks each creative's position in the 3-tier portfolio
    and its lifecycle stage from NEW to RETIRED.
    """
    creative_id: str = ""

    # Portfolio bucket
    bucket: str = PortfolioBucket.EXPLORATION.value
    # EXPLORATION (30%) / GROWTH (50%) / HARVEST (20%)

    lifecycle_stage: str = LifecycleStage.NEW.value
    # NEW → TESTING → GROWING → MATURE → HARVEST → RETIRED

    # Financials
    allocated_budget: float = 0.0
    roi: float = 0.0

    # Risk
    risk_score: float = 0.0

    # Archetype
    archetype: str = ""

    # Metadata
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "bucket": self.bucket,
            "lifecycle_stage": self.lifecycle_stage,
            "allocated_budget": round(self.allocated_budget, 2),
            "roi": round(self.roi, 3),
            "risk_score": round(self.risk_score, 3),
            "archetype": self.archetype,
            "updated_at": self.updated_at,
        }


# ═══════════════════════════════════════════════════════════
# ScalePlan
# ═══════════════════════════════════════════════════════════

@dataclass
class ScalePlan:
    """Automated budget scaling plan with ROAS decay guard.

    Scale ladder: 100 → 200 → 500 → 1000 → 2000 → 5000
    Each step requires ROAS >= original_roas * roas_guard_threshold.
    """
    creative_id: str = ""

    # Budget
    current_budget: float = 0.0
    target_budget: float = 0.0

    # Scale ladder
    scale_step: int = 0               # Current step (0-5)
    max_scale_level: int = 5          # Maximum 5 levels

    # ROAS Decay Guard
    roas_guard_threshold: float = 0.7  # Stop if ROAS < original * 0.7

    # Status
    status: str = ScaleStatus.ACTIVE.value
    # ACTIVE / PAUSED / STOPPED

    # Metadata
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "current_budget": round(self.current_budget, 2),
            "target_budget": round(self.target_budget, 2),
            "scale_step": self.scale_step,
            "max_scale_level": self.max_scale_level,
            "roas_guard_threshold": self.roas_guard_threshold,
            "status": self.status,
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════
# RiskReport
# ═══════════════════════════════════════════════════════════

@dataclass
class RiskReport:
    """E10 safety gate — must be SAFE before autonomous execution.

    Three risk dimensions:
      - Budget Risk: single creative <= 30% total budget
      - Scale Risk: daily increase <= 2x
      - Diversity Risk: HHI <= 0.5 (archetype concentration)
    """
    risk_id: str = ""
    creative_id: str = ""

    # Risk dimensions
    budget_risk: str = RiskLevel.SAFE.value
    scale_risk: str = RiskLevel.SAFE.value
    diversity_risk: str = RiskLevel.SAFE.value

    # Diversity metric (Herfindahl-Hirschman Index)
    hhi_score: float = 0.0

    # Gate
    blocking: bool = False            # E10 must halt if True
    reason: str = ""

    # Metadata
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "risk_id": self.risk_id,
            "creative_id": self.creative_id,
            "budget_risk": self.budget_risk,
            "scale_risk": self.scale_risk,
            "diversity_risk": self.diversity_risk,
            "hhi_score": round(self.hhi_score, 4),
            "blocking": self.blocking,
            "reason": self.reason,
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════
# GrowthReport
# ═══════════════════════════════════════════════════════════

@dataclass
class GrowthReport:
    """Orchestrator output — full pipeline summary.

    Aggregates all 4 modules into a single report for
    E10 consumption and human review.
    """
    report_id: str = ""

    # Experiment counts
    total_experiments: int = 0
    winner_count: int = 0
    failed_count: int = 0
    promising_count: int = 0
    inconclusive_count: int = 0

    # Action counts
    scale_count: int = 0
    kill_count: int = 0
    watch_count: int = 0
    retest_count: int = 0

    # Portfolio state
    portfolio_state: dict[str, Any] = field(default_factory=dict)

    # Risk status
    risk_status: dict[str, Any] = field(default_factory=dict)

    # Metadata
    generated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "total_experiments": self.total_experiments,
            "winner_count": self.winner_count,
            "failed_count": self.failed_count,
            "promising_count": self.promising_count,
            "inconclusive_count": self.inconclusive_count,
            "scale_count": self.scale_count,
            "kill_count": self.kill_count,
            "watch_count": self.watch_count,
            "retest_count": self.retest_count,
            "portfolio_state": self.portfolio_state,
            "risk_status": self.risk_status,
            "generated_at": self.generated_at,
        }