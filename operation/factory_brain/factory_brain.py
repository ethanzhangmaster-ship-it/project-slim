"""
E15.1.2 — Factory Brain (daily orchestrator)
=============================================

The first true closure of the three lines:

    Growth OS ──(opportunity drop-in)──> OpportunityIntake
                                              │
    PatternMiner <──(fleet outcomes)── Revenue/DAU metrics
        │  weights                            │
        v                                     v
    SpecGenerator ──(GameProduct)──> GameRegistry ──> Publishing Factory
                                              │
    PortfolioManager (daily ROAS judgements)  │
    AsoBandit (listing winners -> memory)     │
    StoreExperimentPlanner (PPO / listing experiments)

run_daily() executes the whole cycle and returns a BrainReport.
Everything is a PROPOSAL (requires_manual_apply); real_api_called is
locked False forever. New GameProducts enter the registry with
status=development — a human decides whether to actually build them.
"""
from __future__ import annotations

import datetime as _dt
from typing import List, Optional

from operation.publishing_factory.catalog.game_registry import GameRegistry
from operation.publishing_factory.memory import PublishingMemory

from .aso_bandit import AsoBandit
from .blueprint_generator import BlueprintGenerator
from .decision_engine import GameDecisionEngine
from .models import BrainReport, ProductSpec
from .opportunity_intake import OpportunityIntake
from .opportunity_predictor import OpportunityPredictor
from .pattern_miner import PatternMiner
from .portfolio_manager import PortfolioManager
from .spec_generator import SpecGenerator
from .store_experiment_planner import StoreExperimentPlanner

_DEFAULT_CAPACITY = 3        # max new specs per day (production capacity)
_MAX_FLEET = 50              # hard portfolio ceiling (user runs 10-50)


class FactoryBrain:
    """AI decides what the factory builds next — humans approve."""

    def __init__(self, registry: GameRegistry,
                 memory: Optional[PublishingMemory] = None,
                 dropin_path: str = "data/market_opportunities.json",
                 portfolio_state: str = "data/portfolio_state.json",
                 aso_trials: str = "data/aso_trials.jsonl",
                 capacity: int = _DEFAULT_CAPACITY):
        self.registry = registry
        self.memory = memory or PublishingMemory()
        self.intake = OpportunityIntake(registry, dropin_path=dropin_path)
        self.miner = PatternMiner(registry, memory=self.memory)
        self.portfolio = PortfolioManager(registry,
                                          state_path=portfolio_state)
        self.bandit = AsoBandit(path=aso_trials, memory=self.memory)
        self.exp_planner = StoreExperimentPlanner()
        self.predictor = OpportunityPredictor()
        self.blueprinter = BlueprintGenerator()
        self.decision_engine = GameDecisionEngine()
        self.capacity = capacity

    # ------------------------------------------------------------------ #
    def run_daily(self, register_specs: bool = False) -> BrainReport:
        """One full brain cycle.

        register_specs=False (default): specs are proposals only.
        register_specs=True: accepted specs enter the registry as
        status=development (the operator has pre-approved intake).
        Portfolio ceiling (_MAX_FLEET) is always enforced.
        """
        today = _dt.date.today().isoformat()

        # 1. what worked (Revenue OS -> weights)
        patterns = self.miner.mine()

        # 2. what the market wants (Growth OS + fleet signals)
        opportunities = self.intake.collect()

        # 2b. economics forecast per opportunity (CPI / D30 / D90 ROAS)
        predictions = self.predictor.predict_batch(opportunities)

        # 3. what to build next (respecting capacity + fleet ceiling)
        headroom = max(0, _MAX_FLEET - self.registry.count())
        capacity = min(self.capacity, headroom)
        gen = SpecGenerator(patterns=patterns)
        specs = gen.generate_batch(opportunities, capacity=capacity)
        specs = self._drop_duplicates(specs)

        # 3b. full product design for each proposed spec
        blueprints = self.blueprinter.build_batch(specs)

        if register_specs:
            for spec in specs:
                gp = SpecGenerator.to_game_product(spec)
                if self.registry.get(gp.game_id) is None:
                    self.registry.add(gp)
                    self.portfolio.set_stage(gp.game_id, "idea")

        # 4. daily portfolio judgements (ROAS ladder etc.)
        decisions = self.portfolio.daily_decisions()

        # 4b. retention/economics-aware KEEP/SCALE/KILL verdicts
        verdicts = self.decision_engine.evaluate_fleet(self.registry)

        # 5. ASO bandit: commit any decided listing trials
        aso_winners: List[dict] = []
        for g in self.registry.list_all():
            for kind in ("title", "icon", "screenshot_set"):
                w = self.bandit.pick_winner(g.game_id, kind, genre=g.genre)
                if w is not None:
                    aso_winners.append(w.to_dict())

        # 6. store experiments for install-rate drops
        store_experiments = self.exp_planner.plan_fleet(
            self.registry.list_all())

        return BrainReport(
            date=today,
            opportunities=opportunities,
            predictions=predictions,
            specs=specs,
            blueprints=blueprints,
            decisions=decisions,
            verdicts=verdicts,
            patterns=patterns,
            aso_winners=aso_winners,
            store_experiments=store_experiments,
            real_api_called=False,
        )

    # ------------------------------------------------------------------ #
    def _drop_duplicates(self, specs: List[ProductSpec]) -> List[ProductSpec]:
        """Never propose a (genre, theme) we already operate."""
        existing = set()
        for g in self.registry.list_all():
            # theme is recoverable from package_name convention
            parts = g.package_name.split(".")
            theme = parts[-1] if len(parts) >= 4 else ""
            existing.add((g.genre, theme))
        out = []
        for s in specs:
            if (s.genre, s.theme) in existing:
                continue
            out.append(s)
        return out

    # ------------------------------------------------------------------ #
    @property
    def real_api_called(self) -> bool:
        return False


__all__ = ["FactoryBrain"]
