"""
E15.1.2 — Store Experiment Planner
===================================

When a game's install rate drops, generate a ready-to-run store
experiment plan:

    Google Play  -> Store listing experiment
    App Store    -> Product Page Optimization (PPO)

The plan contains concrete variant briefs (icons / screenshots / copy)
produced by the existing E15.1.1 asset pipeline + ASO engine — the
operator pastes them into the store console by hand. No real API.

Trigger rule (deterministic):
    metrics.store_cvr < baseline_cvr * (1 - _DROP_PCT)
    or metrics.store_cvr < _ABS_FLOOR
"""
from __future__ import annotations

from typing import List, Optional

from operation.publishing_factory.asset_pipeline.icon_generator import (
    IconGenerator,
)
from operation.publishing_factory.asset_pipeline.screenshot_generator import (
    ScreenshotGenerator,
)
from operation.publishing_factory.catalog.product_profile import GameProduct
from operation.publishing_factory.metadata_engine.aso_generator import (
    AsoGenerator,
)

from .models import StoreExperimentPlan

_DROP_PCT = 0.20         # cvr fell >= 20% below its own baseline
_ABS_FLOOR = 0.10        # or cvr under 10% absolute
_N_ICONS = 5
_N_SHOT_SETS = 3
_N_COPY = 5


class StoreExperimentPlanner:
    """Builds PPO / Play-listing experiment plans from asset briefs."""

    def __init__(self):
        self.icons = IconGenerator()
        self.shots = ScreenshotGenerator()
        self.aso = AsoGenerator()

    # ------------------------------------------------------------------ #
    @staticmethod
    def needs_experiment(game: GameProduct) -> bool:
        m = game.metrics or {}
        cvr = m.get("store_cvr")
        if cvr is None:
            return False
        cvr = float(cvr)
        base = float(m.get("baseline_cvr", 0.0))
        if base > 0 and cvr < base * (1.0 - _DROP_PCT):
            return True
        return cvr < _ABS_FLOOR

    # ------------------------------------------------------------------ #
    def plan(self, game: GameProduct,
             store: str = "google_play") -> Optional[StoreExperimentPlan]:
        """One experiment plan for one game (None if no trigger)."""
        if not self.needs_experiment(game):
            return None

        # icon variants: base spec + deterministic style twists
        icon_variants: List[str] = []
        base_icon = self.icons.generate(game)
        for i in range(_N_ICONS):
            twist = ["high_contrast", "character_closeup", "bold_text",
                     "gradient_bg", "minimal"][i]
            icon_variants.append(
                f"icon_v{i+1}: {base_icon.style} + {twist}")

        # screenshot variants: reorder the hook->proof->fantasy sequence
        shot_set = self.shots.generate(game)
        orders = [
            "hook_first (default)",
            "gameplay_proof_first",
            "fantasy_payoff_first",
        ]
        screenshot_variants = [
            f"shots_v{i+1}: {orders[i]} "
            f"({len(shot_set.screenshots)} frames)"
            for i in range(_N_SHOT_SETS)
        ]

        # copy variants: seed from ASO pack + selling points
        pack = self.aso.generate(game)
        points = game.default_selling_points()
        copy_variants: List[str] = [f"copy_v1: {pack.title}"]
        for i, p in enumerate(points[:_N_COPY - 1], start=2):
            copy_variants.append(
                f"copy_v{i}: {p} — {game.display_name or game.game_id}")

        return StoreExperimentPlan(
            experiment_id=f"storeexp_{game.game_id}_{store}",
            game_id=game.game_id,
            store=store,
            trigger="install_rate_drop",
            icon_variants=icon_variants,
            screenshot_variants=screenshot_variants,
            copy_variants=copy_variants,
        )

    # ------------------------------------------------------------------ #
    def plan_fleet(self, games: List[GameProduct]) -> List[StoreExperimentPlan]:
        out: List[StoreExperimentPlan] = []
        for g in games:
            if not g.is_published():
                continue
            for store in g.platforms:
                p = self.plan(g, store=store)
                if p is not None:
                    out.append(p)
        return out


__all__ = ["StoreExperimentPlanner"]
