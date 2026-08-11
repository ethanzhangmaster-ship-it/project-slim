"""V4.3 Creative Policy Schemas — decision-layer data structures.

All policy decisions, priorities, allocations, and reports use these schemas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════

class PolicyAction(str, Enum):
    """Final decision output by the Policy Engine."""
    GENERATE = "generate"       # Proceed with generation
    DONT_GENERATE = "dont_generate"  # Skip this creative
    RETEST = "retest"           # Re-run with modified parameters
    ADAPT = "adapt"             # Adapt DNA for different market
    KILL = "kill"               # Stop all related creatives


class PortfolioCategory(str, Enum):
    """Portfolio allocation categories."""
    WINNER = "winner"           # Proven high-ROAS creatives
    EXPLORE = "explore"         # Novel combinations
    ADAPT = "adapt"             # Cross-market adaptation
    RETEST = "retest"           # Previously failed, retry


class RiskLevel(str, Enum):
    """Risk severity levels."""
    SAFE = "safe"
    CAUTION = "caution"
    WARNING = "warning"
    CRITICAL = "critical"
    HALT = "halt"


class ExploreMode(str, Enum):
    """Exploration strategy mode."""
    EXPLOIT = "exploit"         # Focus on known winners
    BALANCED = "balanced"       # Equal exploit/explore
    EXPLORE = "explore"         # Prioritize discovery


# ═══════════════════════════════════════════════
# Core Decision Schemas
# ═══════════════════════════════════════════════

@dataclass
class PriorityScore:
    """Creative priority score (0-100)."""
    creative_id: str = ""
    total_score: float = 0.0       # 0-100
    roi_score: float = 0.0         # ROAS contribution
    trend_score: float = 0.0       # Trend alignment
    confidence_score: float = 0.0  # Reasoning confidence
    novelty_score: float = 0.0     # Diversity bonus
    budget_score: float = 0.0      # Budget efficiency
    country: str = ""
    platform: str = "facebook"
    dna: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "total_score": round(self.total_score, 1),
            "roi_score": round(self.roi_score, 2),
            "trend_score": round(self.trend_score, 2),
            "confidence_score": round(self.confidence_score, 2),
            "novelty_score": round(self.novelty_score, 2),
            "budget_score": round(self.budget_score, 2),
            "country": self.country,
            "platform": self.platform,
        }


@dataclass
class RiskScore:
    """Risk assessment for a creative/country/trend."""
    target_id: str = ""            # creative_id, country, or trend
    target_type: str = "creative"  # creative/country/trend/platform
    level: RiskLevel = RiskLevel.SAFE
    consecutive_failures: int = 0
    failure_rate: float = 0.0
    budget_consumed: float = 0.0
    budget_limit: float = 0.0
    should_halt: bool = False
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "target_type": self.target_type,
            "level": self.level.value,
            "consecutive_failures": self.consecutive_failures,
            "failure_rate": round(self.failure_rate, 3),
            "budget_consumed": round(self.budget_consumed, 2),
            "should_halt": self.should_halt,
            "reason": self.reason,
        }


@dataclass
class BudgetAllocation:
    """Budget allocation across countries/platforms."""
    total_budget: float = 0.0
    allocations: dict[str, float] = field(default_factory=dict)  # country → budget
    allocations_pct: dict[str, float] = field(default_factory=dict)  # country → %
    remaining: float = 0.0
    daily_spend: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_budget": round(self.total_budget, 2),
            "allocations": {k: round(v, 2) for k, v in self.allocations.items()},
            "allocations_pct": {k: round(v, 1) for k, v in self.allocations_pct.items()},
            "remaining": round(self.remaining, 2),
        }


@dataclass
class Portfolio:
    """Dynamic portfolio allocation."""
    categories: dict[PortfolioCategory, float] = field(default_factory=dict)  # category → %
    total_creatives: int = 0
    allocations: dict[PortfolioCategory, int] = field(default_factory=dict)  # category → count
    explore_ratio: float = 0.2       # Current explore ratio
    exploit_ratio: float = 0.8       # Current exploit ratio

    def to_dict(self) -> dict[str, Any]:
        return {
            "categories": {k.value: round(v, 1) for k, v in self.categories.items()},
            "total_creatives": self.total_creatives,
            "allocations": {k.value: v for k, v in self.allocations.items()},
            "explore_ratio": round(self.explore_ratio, 2),
            "exploit_ratio": round(self.exploit_ratio, 2),
        }


@dataclass
class CreativeTask:
    """A single creative task in the production queue."""
    creative_id: str = ""
    dna: dict[str, Any] = field(default_factory=dict)
    priority: PriorityScore = field(default_factory=PriorityScore)
    action: PolicyAction = PolicyAction.GENERATE
    country: str = ""
    platform: str = "facebook"
    budget: float = 0.0
    reasoning_confidence: float = 0.0
    validation_accuracy: float = 0.0
    trend_status: str = "stable"       # growing/stable/declining/dead
    roi_prediction: float = 0.0
    risk: RiskScore = field(default_factory=RiskScore)
    status: str = "queued"             # queued/scheduled/generating/done/killed

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "action": self.action.value,
            "priority": self.priority.to_dict(),
            "country": self.country,
            "platform": self.platform,
            "budget": round(self.budget, 2),
            "reasoning_confidence": round(self.reasoning_confidence, 3),
            "validation_accuracy": round(self.validation_accuracy, 3),
            "trend_status": self.trend_status,
            "roi_prediction": round(self.roi_prediction, 3),
            "risk_level": self.risk.level.value,
            "status": self.status,
        }


@dataclass
class DecisionPolicy:
    """Complete policy configuration for the Policy Engine."""
    version: str = "1.0.0"
    # Thresholds
    confidence_threshold_go: float = 0.72     # Confidence > this → GO
    confidence_threshold_test: float = 0.55   # Confidence > this → TEST
    confidence_threshold_kill: float = 0.35   # Confidence < this → KILL
    roi_threshold_go: float = 0.7
    roi_threshold_kill: float = 0.2
    trend_growing_bonus: float = 0.10         # Add to confidence if trend growing
    trend_dead_penalty: float = 0.25          # Subtract from confidence if trend dead
    # Risk limits
    max_consecutive_failures: int = 5
    max_failure_rate: float = 0.4
    max_budget_per_creative: float = 500.0
    max_daily_budget: float = 10000.0
    # Portfolio defaults
    default_portfolio: dict[str, float] = field(default_factory=lambda: {
        "winner": 0.50, "explore": 0.20, "adapt": 0.20, "retest": 0.10,
    })
    # Explore/Exploit
    default_explore_ratio: float = 0.20
    max_explore_ratio: float = 0.40
    min_explore_ratio: float = 0.05
    # Learning
    learning_rate: float = 0.05
    decay_factor: float = 0.95
    # Version tracking
    previous_version: str = ""
    improved_from: str = ""
    improvement_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "thresholds": {
                "confidence_go": self.confidence_threshold_go,
                "confidence_test": self.confidence_threshold_test,
                "confidence_kill": self.confidence_threshold_kill,
                "roi_go": self.roi_threshold_go,
                "roi_kill": self.roi_threshold_kill,
                "trend_growing_bonus": self.trend_growing_bonus,
                "trend_dead_penalty": self.trend_dead_penalty,
            },
            "risk_limits": {
                "max_consecutive_failures": self.max_consecutive_failures,
                "max_failure_rate": self.max_failure_rate,
                "max_budget_per_creative": self.max_budget_per_creative,
                "max_daily_budget": self.max_daily_budget,
            },
            "portfolio": self.default_portfolio,
            "explore_ratio": self.default_explore_ratio,
            "learning": {
                "learning_rate": self.learning_rate,
                "decay_factor": self.decay_factor,
            },
            "previous_version": self.previous_version,
            "improvement_score": self.improvement_score,
        }


@dataclass
class DecisionLog:
    """A single decision record for audit trail."""
    timestamp: str = ""
    creative_id: str = ""
    action: PolicyAction = PolicyAction.DONT_GENERATE
    reason: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    policy_version: str = ""
    overridden_by_risk: bool = False
    overridden_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "creative_id": self.creative_id,
            "action": self.action.value,
            "reason": self.reason,
            "evidence": self.evidence,
            "policy_version": self.policy_version,
            "overridden_by_risk": self.overridden_by_risk,
            "overridden_reason": self.overridden_reason,
        }


@dataclass
class DailyProductionPlan:
    """Daily production plan output."""
    date: str = ""
    total_creatives: int = 0
    generate_count: int = 0
    retest_count: int = 0
    adapt_count: int = 0
    kill_count: int = 0
    tasks: list[CreativeTask] = field(default_factory=list)
    portfolio: Portfolio = field(default_factory=Portfolio)
    budget: BudgetAllocation = field(default_factory=BudgetAllocation)
    risk_summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "total_creatives": self.total_creatives,
            "actions": {
                "generate": self.generate_count,
                "retest": self.retest_count,
                "adapt": self.adapt_count,
                "kill": self.kill_count,
            },
            "tasks": [t.to_dict() for t in self.tasks[:50]],
            "portfolio": self.portfolio.to_dict(),
            "budget": self.budget.to_dict(),
            "risk_summary": self.risk_summary,
        }


@dataclass
class PolicyReport:
    """Daily policy report."""
    date: str = ""
    plan: DailyProductionPlan = field(default_factory=DailyProductionPlan)
    policy_version: str = ""
    decisions_log: list[DecisionLog] = field(default_factory=list)
    kill_reasons: list[dict[str, Any]] = field(default_factory=list)
    explore_ratio: float = 0.0
    portfolio_summary: dict[str, Any] = field(default_factory=dict)
    budget_summary: dict[str, Any] = field(default_factory=dict)
    risk_summary: dict[str, Any] = field(default_factory=dict)
    revenue_prediction: float = 0.0
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "plan": self.plan.to_dict(),
            "policy_version": self.policy_version,
            "decisions_count": len(self.decisions_log),
            "kill_reasons": self.kill_reasons[:10],
            "explore_ratio": round(self.explore_ratio, 2),
            "portfolio": self.portfolio_summary,
            "budget": self.budget_summary,
            "risk": self.risk_summary,
            "revenue_prediction": round(self.revenue_prediction, 2),
            "summary": self.summary,
        }