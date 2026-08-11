"""
E16.6.12 — ASO Portfolio Manager: data models.

The ASO investment brain for managing 10–50 games. Decides which games
deserve ASO investment, what stage each game is in, and how to allocate
limited AI/human resources.

Key concepts:
  * ``ASOGamePortfolio`` — one game's ASO profile
  * ``ASOLifecycle`` — growth stage (NEW / GROWTH / MATURE / DECLINING / SUNSET)
  * ``ASOOpportunityScore`` — Revenue Potential × Growth Gap × Market Opp × Confidence / Cost
  * ``ASOResourceAllocation`` — budget distribution
  * ``PortfolioReport`` — daily portfolio brain output
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# 1. Lifecycle stages
# --------------------------------------------------------------------------- #
class ASOLifecycle(str, Enum):
    """Lifecycle stage of a game from an ASO investment perspective."""
    NEW = "NEW"
    GROWTH = "GROWTH"
    MATURE = "MATURE"
    DECLINING = "DECLINING"
    SUNSET = "SUNSET"


# --------------------------------------------------------------------------- #
# 2. One game's ASO portfolio profile
# --------------------------------------------------------------------------- #
@dataclass
class ASOGamePortfolio:
    """ASO profile for one game in the portfolio."""

    game_id: str
    genre: str
    markets: List[str] = field(default_factory=list)

    # Current performance
    organic_installs: int = 0
    organic_revenue: float = 0.0
    aso_score: float = 0.0  # 0–100 current ASO health

    # Opportunity signals (0–1)
    keyword_opportunity: float = 0.0
    localization_opportunity: float = 0.0
    creative_opportunity: float = 0.0

    # Cost estimates
    ai_generation_cost: float = 1.0  # relative cost (normalised)
    human_review_cost: float = 1.0

    date: str = ""
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "genre": self.genre,
            "markets": self.markets,
            "organic_installs": self.organic_installs,
            "organic_revenue": round(self.organic_revenue, 2),
            "aso_score": round(self.aso_score, 2),
            "keyword_opportunity": round(self.keyword_opportunity, 4),
            "localization_opportunity": round(self.localization_opportunity, 4),
            "creative_opportunity": round(self.creative_opportunity, 4),
            "ai_generation_cost": round(self.ai_generation_cost, 4),
            "human_review_cost": round(self.human_review_cost, 4),
            "date": self.date,
            "created_at": self.created_at,
        }


# --------------------------------------------------------------------------- #
# 3. Opportunity score (per game)
# --------------------------------------------------------------------------- #
@dataclass
class ASOOpportunityScore:
    """Overall ASO investment opportunity for one game.

    ``score = revenue_potential × growth_gap × market_opportunity × execution_confidence / investment_cost``
    """

    game_id: str
    revenue_potential: float = 0.0
    growth_gap: float = 0.0
    market_opportunity: float = 0.0
    execution_confidence: float = 0.0
    investment_cost: float = 1.0
    score: float = 0.0

    def compute(self) -> float:
        self.score = round(
            self.revenue_potential * self.growth_gap
            * self.market_opportunity * self.execution_confidence
            / max(self.investment_cost, 0.01),
            4,
        )
        return self.score

    def score_normalized(self, max_score: float) -> float:
        return round(self.score / max_score * 100, 1) if max_score > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "revenue_potential": round(self.revenue_potential, 4),
            "growth_gap": round(self.growth_gap, 4),
            "market_opportunity": round(self.market_opportunity, 4),
            "execution_confidence": round(self.execution_confidence, 4),
            "investment_cost": round(self.investment_cost, 4),
            "score": self.score,
        }


# --------------------------------------------------------------------------- #
# 4. Resource allocation
# --------------------------------------------------------------------------- #
@dataclass
class ASOResourceAllocation:
    """ASO resource budget allocated to one game."""

    game_id: str
    rank: int = 0
    creative_budget: int = 0  # AI generation count
    localization_budget: int = 0  # markets to localise
    experiment_budget: int = 0  # experiments to run
    priority: str = "low"  # high / medium / low
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "rank": self.rank,
            "creative_budget": self.creative_budget,
            "localization_budget": self.localization_budget,
            "experiment_budget": self.experiment_budget,
            "priority": self.priority,
            "reason": self.reason,
        }


# --------------------------------------------------------------------------- #
# 5. Investment simulation result
# --------------------------------------------------------------------------- #
@dataclass
class ASOInvestmentSimulation:
    """Projected outcome of an ASO investment in one game."""

    game_id: str
    investment_hours: float = 0.0
    projected_installs_uplift: float = 0.0
    projected_revenue_uplift: float = 0.0
    projected_monthly_revenue: float = 0.0
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "investment_hours": self.investment_hours,
            "projected_installs_uplift": round(self.projected_installs_uplift, 4),
            "projected_revenue_uplift": round(self.projected_revenue_uplift, 2),
            "projected_monthly_revenue": round(self.projected_monthly_revenue, 2),
            "confidence": round(self.confidence, 4),
        }


# --------------------------------------------------------------------------- #
# 6. Portfolio report
# --------------------------------------------------------------------------- #
@dataclass
class PortfolioReport:
    """Daily ASO portfolio brain output."""

    date: str
    game_count: int = 0
    scores: List[ASOOpportunityScore] = field(default_factory=list)
    lifecycles: Dict[str, ASOLifecycle] = field(default_factory=dict)
    allocations: List[ASOResourceAllocation] = field(default_factory=list)
    simulations: List[ASOInvestmentSimulation] = field(default_factory=list)
    patterns_learned: int = 0
    created_at: str = field(default_factory=_now_iso)

    def to_markdown(self) -> str:
        lines: List[str] = []
        lines.append(f"# ASO Portfolio Report")
        lines.append(f"")
        lines.append(f"**Date:** {self.date}")
        lines.append(f"**Games in portfolio:** {self.game_count}")
        lines.append(f"")

        # Investment ranking
        lines.append(f"## ASO Investment Ranking")
        if self.scores:
            max_score = max((s.score for s in self.scores), default=1.0)
            for i, s in enumerate(
                sorted(self.scores, key=lambda x: x.score, reverse=True)[:10], 1
            ):
                normalised = s.score_normalized(max_score)
                lifecycle = self.lifecycles.get(s.game_id, ASOLifecycle.MATURE)
                lines.append(f"")
                lines.append(f"### #{i} {s.game_id}")
                lines.append(f"- **Score:** {normalised}/100")
                lines.append(f"- **Lifecycle:** {lifecycle.value}")
                lines.append(f"- **Revenue Potential:** {s.revenue_potential:.2f}")
                lines.append(f"- **Growth Gap:** {s.growth_gap:.2f}")
                lines.append(f"- **Market Opportunity:** {s.market_opportunity:.2f}")
                lines.append(f"- **Execution Confidence:** {s.execution_confidence:.2f}")
                lines.append(f"")
        else:
            lines.append(f"\nNo games in portfolio.\n")

        # Resource allocation
        if self.allocations:
            lines.append(f"## Resource Allocation")
            lines.append(f"")
            lines.append(f"| Rank | Game | Creative | Localization | Experiments | Priority |")
            lines.append(f"| --- | --- | ---: | ---: | ---: | --- |")
            for a in sorted(self.allocations, key=lambda x: x.rank):
                lines.append(
                    f"| {a.rank} | {a.game_id} | {a.creative_budget} | "
                    f"{a.localization_budget} | {a.experiment_budget} | "
                    f"{a.priority} |"
                )
            lines.append(f"")

        # Lifecycle summary
        if self.lifecycles:
            lines.append(f"## Lifecycle Summary")
            for lc in ASOLifecycle:
                count = sum(
                    1 for v in self.lifecycles.values() if v == lc
                )
                if count > 0:
                    lines.append(f"- **{lc.value}:** {count} games")

        # Simulations
        if self.simulations:
            lines.append(f"## Investment Simulations")
            for sim in self.simulations:
                lines.append(
                    f"- **{sim.game_id}**: {sim.investment_hours}h → "
                    f"+${sim.projected_revenue_uplift:.0f}/month "
                    f"(confidence {sim.confidence:.0%})"
                )

        if self.patterns_learned:
            lines.append(f"\n**Patterns learned:** {self.patterns_learned}")

        return "\n".join(lines)


__all__ = [
    "ASOLifecycle",
    "ASOGamePortfolio",
    "ASOOpportunityScore",
    "ASOResourceAllocation",
    "ASOInvestmentSimulation",
    "PortfolioReport",
]
