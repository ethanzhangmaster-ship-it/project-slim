"""
E16.6.11 — ASO Update Strategy Agent.

The "ASO Release Manager" — decides WHEN to update the store, WHAT
to update, and at what RISK level.

Pipeline: collect signals → evaluate timing → plan update → assess risk
→ record memory → UpdateStrategyReport
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.aso_intelligence.update_strategy.models import (
    ASOUpdateSignal,
    UpdateOpportunityScore,
    UpdatePlan,
    ASOUpdateExperience,
    UpdateStrategyReport,
    UpdateType,
)
from src.aso_intelligence.update_strategy.timing_engine import (
    UpdateTimingEngine,
)
from src.aso_intelligence.update_strategy.update_planner import UpdatePlanner
from src.aso_intelligence.update_strategy.risk_manager import RiskManager
from src.aso_intelligence.update_strategy.memory import UpdateStrategyMemory
from src.aso_intelligence.experiment_memory.experiment_store import (
    ASOExperimentStore,
)


def _today_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class ASOUpdateStrategyAgent:
    """AI ASO Release Manager — decide when, what, and how to update.

    Typical usage:

        agent = ASOUpdateStrategyAgent.build(store)
        report = agent.run(
            game_id="merge_witch",
            market="US",
            signal=ASOUpdateSignal(
                cvr_change=-0.22,
                ranking_change=-15,
                competitor_pressure=0.8,
                days_since_update=90,
            ),
        )
        print(report.to_markdown())
    """

    def __init__(
        self,
        timing: Optional[UpdateTimingEngine] = None,
        planner: Optional[UpdatePlanner] = None,
        risk: Optional[RiskManager] = None,
        memory: Optional[UpdateStrategyMemory] = None,
    ):
        self.timing = timing or UpdateTimingEngine()
        self.planner = planner or UpdatePlanner()
        self.risk = risk or RiskManager()
        self.memory = memory or UpdateStrategyMemory()

    @classmethod
    def build(
        cls, store: Optional[ASOExperimentStore] = None
    ) -> "ASOUpdateStrategyAgent":
        return cls(memory=UpdateStrategyMemory(store))

    # ------------------------------------------------------------------ #
    def run(
        self,
        game_id: str,
        market: str,
        signal: ASOUpdateSignal,
        *,
        # Optional: record result of a previous update
        record_experience: Optional[ASOUpdateExperience] = None,
    ) -> UpdateStrategyReport:
        """Run the full update strategy cycle.

        1. Evaluate timing (Update Score)
        2. Plan update (type + scope)
        3. Assess risk (cooldown, experiment, human approval)
        4. Seasonality intelligence
        5. Record experience (if provided)
        """
        # Step 1: Timing evaluation
        opportunity = self.timing.evaluate(signal)

        # Step 2: Plan update
        plan = self.planner.plan(game_id, market, signal, opportunity)

        # Step 3: Risk assessment
        plan = self.risk.apply_gates(plan, signal)

        # Step 4: Seasonality
        now = datetime.now(timezone.utc)
        seasonality_notes = self.timing.get_seasonality_notes(now.month)
        season_patterns = self.memory.seasonality_patterns(now.month)

        # Combine seasonality notes
        for sp in season_patterns:
            seasonality_notes.append(
                f"{sp.get('event', '')}: {sp.get('action', '')} "
                f"(expected +{sp.get('expected_cvr_boost', 0):.0%} CVR)"
            )

        # Step 5: Record experience (if provided)
        patterns_learned = 0
        if record_experience:
            self.memory.record_experience(record_experience)

            # Check if we learned new patterns
            sr = self.memory.success_rate(market, record_experience.update_type)
            if sr > 0.5:
                patterns_learned = 1

        # Report
        report = UpdateStrategyReport(
            game_id=game_id,
            date=_today_iso(),
            signals=signal,
            opportunity_score=opportunity,
            plan=plan,
            seasonality_notes=seasonality_notes,
            patterns_learned=patterns_learned,
        )
        return report


__all__ = ["ASOUpdateStrategyAgent"]
