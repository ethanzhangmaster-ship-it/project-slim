"""
E16.6.12 — ASO Portfolio Agent.

The ASO Portfolio Brain — decides which games to invest ASO resources in,
at what lifecycle stage, and how to allocate limited budgets.

Pipeline: score games → rank → allocate resources → lifecycle → simulate
→ learn → PortfolioReport
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.aso_intelligence.portfolio.models import (
    ASOGamePortfolio,
    ASOOpportunityScore,
    ASOResourceAllocation,
    ASOInvestmentSimulation,
    PortfolioReport,
)
from src.aso_intelligence.portfolio.scoring import ASOPortfolioScoringEngine
from src.aso_intelligence.portfolio.opportunity_ranker import (
    ASOOpportunityRanker,
)
from src.aso_intelligence.portfolio.resource_allocator import (
    ASOResourceAllocator,
)
from src.aso_intelligence.portfolio.lifecycle import GameLifecycleManager
from src.aso_intelligence.portfolio.memory import PortfolioMemory
from src.aso_intelligence.experiment_memory.experiment_store import (
    ASOExperimentStore,
)


def _today_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class ASOPortfolioAgent:
    """AI ASO Portfolio Director — manages ASO across 10–50 games.

    Typical usage:

        agent = ASOPortfolioAgent.build(store)
        report = agent.run(games=[...])
        print(report.to_markdown())
        # Shows Investment Ranking / Resource Allocation / Lifecycles
    """

    def __init__(
        self,
        scoring: Optional[ASOPortfolioScoringEngine] = None,
        ranker: Optional[ASOOpportunityRanker] = None,
        allocator: Optional[ASOResourceAllocator] = None,
        lifecycle: Optional[GameLifecycleManager] = None,
        memory: Optional[PortfolioMemory] = None,
    ):
        self.scoring = scoring or ASOPortfolioScoringEngine()
        self.ranker = ranker or ASOOpportunityRanker()
        self.allocator = allocator or ASOResourceAllocator()
        self.lifecycle = lifecycle or GameLifecycleManager()
        self.memory = memory or PortfolioMemory()

    @classmethod
    def build(
        cls, store: Optional[ASOExperimentStore] = None
    ) -> "ASOPortfolioAgent":
        return cls(memory=PortfolioMemory(store))

    # ------------------------------------------------------------------ #
    def run(
        self,
        games: List[ASOGamePortfolio],
        *,
        growth_map: Dict[str, float] = None,
        days_map: Dict[str, int] = None,
        declining_map: Dict[str, int] = None,
        total_creative_budget: int = 100,
        total_localization_budget: int = 50,
        total_experiment_budget: int = 20,
        # Optional: record an ASO investment outcome
        investment_record: Dict[str, Any] = None,
    ) -> PortfolioReport:
        """Run the full portfolio management cycle.

        1. Score all games
        2. Rank by opportunity (revenue-aware)
        3. Classify lifecycles
        4. Allocate resources
        5. Simulate top opportunities
        6. Learn from investments
        """
        # Step 1: Score
        scores = [self.scoring.compute(g) for g in games]

        # Step 2: Rank
        ranked = self.ranker.rank(games, scores)
        top = self.ranker.top_opportunities(ranked, k=5)

        # Step 3: Lifecycle
        lifecycles = self.lifecycle.classify_all(
            games, growth_map, days_map, declining_map
        )

        # Step 4: Allocate
        allocations = self.allocator.allocate(
            ranked, games,
            total_creative_budget=total_creative_budget,
            total_localization_budget=total_localization_budget,
            total_experiment_budget=total_experiment_budget,
        )

        # Step 5: Simulate top opportunities
        game_map = {g.game_id: g for g in games}
        simulations: List[ASOInvestmentSimulation] = []
        for s in top[:3]:
            game = game_map.get(s.game_id)
            if game:
                sim = self._simulate(game, s)
                simulations.append(sim)

        # Step 6: Learn
        patterns_learned = 0
        if investment_record:
            self.memory.record_investment(
                game_id=investment_record.get("game_id", ""),
                genre=investment_record.get("genre", ""),
                aso_investment_hours=investment_record.get("hours", 0),
                revenue_uplift=investment_record.get("revenue_uplift", 0),
                success=investment_record.get("success", False),
            )
            genre = investment_record.get("genre", "")
            if genre:
                sr = self.memory.genre_success_rate(genre)
                if sr > 0.5:
                    patterns_learned = 1

        # Report
        report = PortfolioReport(
            date=_today_iso(),
            game_count=len(games),
            scores=ranked,
            lifecycles=lifecycles,
            allocations=allocations,
            simulations=simulations,
            patterns_learned=patterns_learned,
        )
        return report

    # ------------------------------------------------------------------ #
    def _simulate(
        self,
        game: ASOGamePortfolio,
        score: ASOOpportunityScore,
        investment_hours: float = 10.0,
    ) -> ASOInvestmentSimulation:
        """Project ASO investment outcome for one game."""
        base_revenue = game.organic_revenue

        # Predicted uplift based on opportunity score
        uplift_factor = min(0.5, score.score * 2)
        projected_revenue_uplift = base_revenue * uplift_factor

        # Install uplift proportional to revenue uplift
        projected_installs_uplift = uplift_factor * 0.8

        confidence = min(0.9, 0.3 + score.score * 0.5)

        return ASOInvestmentSimulation(
            game_id=game.game_id,
            investment_hours=investment_hours,
            projected_installs_uplift=round(projected_installs_uplift, 4),
            projected_revenue_uplift=round(projected_revenue_uplift, 2),
            projected_monthly_revenue=round(
                base_revenue + projected_revenue_uplift, 2
            ),
            confidence=round(confidence, 4),
        )


__all__ = ["ASOPortfolioAgent"]
