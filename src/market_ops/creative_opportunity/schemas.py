"""Core data models for Opportunity Intelligence Layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any


class OpportunitySource(Enum):
    """Where an opportunity came from."""
    HUMAN = auto()
    AI_SCANNER = auto()
    MERGED = auto()


class OpportunityCategory(Enum):
    """Type of market opportunity."""
    GAMEPLAY_INNOVATION = "gameplay_innovation"
    VISUAL_TREND = "visual_trend"
    MONETIZATION_TREND = "monetization_trend"
    UA_OPPORTUNITY = "ua_opportunity"
    MARKET_GAP = "market_gap"


class OpportunityStatus(Enum):
    """Lifecycle status of an opportunity."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    IN_EXPERIMENT = "in_experiment"
    VALIDATED = "validated"
    FAILED = "failed"


class Recommendation(Enum):
    """What to do with an opportunity."""
    BUILD = "build"
    WATCH = "watch"
    IGNORE = "ignore"


@dataclass
class HumanIdea:
    """A human-submitted game concept."""
    idea_id: str = ""
    source: OpportunitySource = OpportunitySource.HUMAN
    title: str = ""
    description: str = ""
    reference_games: list[str] = field(default_factory=list)
    creator: str = ""
    created_time: str = field(default_factory=lambda: datetime.now().isoformat())
    status: OpportunityStatus = OpportunityStatus.PENDING
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.idea_id:
            self.idea_id = f"idea_{datetime.now().strftime('%Y%m%d%H%M%S')}_{hash(self.title) % 10000:04d}"


@dataclass
class MarketSignal:
    """A raw signal from market scanning."""
    signal_id: str = ""
    source: str = ""  # e.g. "google_play", "meta_ads", "reddit"
    signal_type: str = ""  # e.g. "new_release", "ranking_jump", "ad_volume"
    entity: str = ""  # e.g. "Merge Dragon", "Sort Puzzle"
    value: float = 0.0  # e.g. ranking change, ad volume
    confidence: float = 0.5
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class Opportunity:
    """A unified game/creative opportunity."""
    opportunity_id: str = ""
    name: str = ""
    description: str = ""
    category: OpportunityCategory = OpportunityCategory.GAMEPLAY_INNOVATION
    source: OpportunitySource = OpportunitySource.AI_SCANNER
    score: float = 0.0
    confidence: float = 0.5
    signals: list[MarketSignal] = field(default_factory=list)
    # Scoring components
    market_momentum: float = 0.0  # 0-100
    competition_gap: float = 0.0  # 0-100
    ua_potential: float = 0.0  # 0-100
    production_cost: float = 0.0  # 0-100 (lower is better, but stored as score)
    creative_fit: float = 0.0  # 0-100
    historical_success: float = 0.0  # 0-100
    # Enrichment
    reference_games: list[str] = field(default_factory=list)
    similar_winners: list[str] = field(default_factory=list)  # creative_ids
    estimated_dev_days: int = 0
    tags: list[str] = field(default_factory=list)
    status: OpportunityStatus = OpportunityStatus.PENDING
    created_time: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.opportunity_id:
            self.opportunity_id = f"opp_{datetime.now().strftime('%Y%m%d%H%M%S')}_{hash(self.name) % 10000:04d}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "source": self.source.name.lower(),
            "score": round(self.score, 2),
            "confidence": round(self.confidence, 2),
            "market_momentum": round(self.market_momentum, 2),
            "competition_gap": round(self.competition_gap, 2),
            "ua_potential": round(self.ua_potential, 2),
            "production_cost": round(self.production_cost, 2),
            "creative_fit": round(self.creative_fit, 2),
            "historical_success": round(self.historical_success, 2),
            "reference_games": self.reference_games,
            "similar_winners": self.similar_winners,
            "estimated_dev_days": self.estimated_dev_days,
            "tags": self.tags,
            "status": self.status.value,
            "created_time": self.created_time,
            "metadata": self.metadata,
        }


@dataclass
class RankedOpportunity:
    """An opportunity with ranking recommendation."""
    opportunity: Opportunity = field(default_factory=Opportunity)
    rank: int = 0
    recommendation: Recommendation = Recommendation.WATCH
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "opportunity": self.opportunity.to_dict(),
            "rank": self.rank,
            "recommendation": self.recommendation.value,
            "reason": self.reason,
        }


@dataclass
class ExperimentVariant:
    """One creative variant for hypothesis testing."""
    variant_id: str = ""
    name: str = ""  # e.g. "A: Factory Merge"
    description: str = ""
    genome_hint: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "name": self.name,
            "description": self.description,
            "genome_hint": self.genome_hint,
        }


@dataclass
class ExperimentPlan:
    """A plan to test a creative hypothesis."""
    plan_id: str = ""
    hypothesis: str = ""
    opportunity_id: str = ""
    variants: list[ExperimentVariant] = field(default_factory=list)
    success_metrics: list[str] = field(default_factory=lambda: ["CTR", "CVR", "D7_ROAS"])
    estimated_budget: float = 0.0
    estimated_duration_days: int = 7

    def __post_init__(self) -> None:
        if not self.plan_id:
            self.plan_id = f"exp_{datetime.now().strftime('%Y%m%d%H%M%S')}_{hash(self.hypothesis) % 10000:04d}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "hypothesis": self.hypothesis,
            "opportunity_id": self.opportunity_id,
            "variants": [v.to_dict() for v in self.variants],
            "success_metrics": self.success_metrics,
            "estimated_budget": self.estimated_budget,
            "estimated_duration_days": self.estimated_duration_days,
        }


@dataclass
class OpportunityReport:
    """Daily opportunity report."""
    report_id: str = ""
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    ranked_opportunities: list[RankedOpportunity] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.report_id:
            self.report_id = f"report_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "generated_at": self.generated_at,
            "opportunities": [o.to_dict() for o in self.ranked_opportunities],
            "summary": self.summary,
        }

    def to_markdown(self) -> str:
        """Generate human-readable markdown report."""
        lines = [
            "# Daily Opportunity Report",
            f"Generated: {self.generated_at}",
            "",
            f"## Summary",
            f"- Total Opportunities: {len(self.ranked_opportunities)}",
            f"- BUILD: {sum(1 for o in self.ranked_opportunities if o.recommendation == Recommendation.BUILD)}",
            f"- WATCH: {sum(1 for o in self.ranked_opportunities if o.recommendation == Recommendation.WATCH)}",
            f"- IGNORE: {sum(1 for o in self.ranked_opportunities if o.recommendation == Recommendation.IGNORE)}",
            "",
            "## Top Opportunities",
            "",
        ]
        for ranked in self.ranked_opportunities[:10]:
            opp = ranked.opportunity
            lines.extend([
                f"### #{ranked.rank} {opp.name} (Score: {opp.score:.0f})",
                f"- **Category**: {opp.category.value}",
                f"- **Confidence**: {opp.confidence:.0%}",
                f"- **Recommendation**: {ranked.recommendation.value.upper()}",
                f"- **Why**: {ranked.reason}",
                f"- **Dev Estimate**: {opp.estimated_dev_days} days",
                "",
            ])
        return "\n".join(lines)
