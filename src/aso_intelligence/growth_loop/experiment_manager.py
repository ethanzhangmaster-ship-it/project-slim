"""
E16.6.5 — ASO Experiment Manager.

Bridges the Growth Loop (E16.6.5) with the Experiment Store (E16.6.4).

Manages the experiment lifecycle:
  CREATE → RUNNING → COLLECT → EVALUATE → LEARN

And closes the loop by triggering Pattern Mining + Memory write when
an experiment completes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from src.aso_intelligence.growth_loop.models import (
    ASOActionPlan,
    ASOGrowthReport,
    ApprovalStatus,
)
from src.aso_intelligence.experiment_memory.experiment_models import (
    ASOExperiment,
    ASOExperimentAction,
    ASOExperimentResult,
    ASOExperimentStatus,
    ASOPattern,
)
from src.aso_intelligence.experiment_memory.experiment_store import ASOExperimentStore
from src.aso_intelligence.experiment_memory.pattern_miner import ASOPatternMiner


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# Map growth-loop action → experiment action
_ACTION_TO_EXPERIMENT: Dict[str, ASOExperimentAction] = {
    "UPDATE_SCREENSHOT": ASOExperimentAction.UPDATE_SCREENSHOT,
    "UPDATE_ICON": ASOExperimentAction.UPDATE_ICON,
    "UPDATE_TITLE": ASOExperimentAction.UPDATE_TITLE,
    "ADD_KEYWORD": ASOExperimentAction.ADD_KEYWORD,
}


class ASOExperimentManager:
    """Create and manage experiments derived from action plans.

    Wraps ``ASOExperimentStore`` (E16.6.4) and provides lifecycle helpers
    for the Growth Loop orchestrator.
    """

    def __init__(
        self,
        store: ASOExperimentStore,
        miner: Optional[ASOPatternMiner] = None,
    ):
        self.store = store
        self.miner = miner or ASOPatternMiner()

    # ------------------------------------------------------------------ #
    def _resolve_action(self, action: str) -> ASOExperimentAction:
        upper = action.upper()
        return _ACTION_TO_EXPERIMENT.get(
            upper, ASOExperimentAction.UPDATE_SCREENSHOT
        )

    # ------------------------------------------------------------------ #
    def create_experiment(
        self,
        plan: ASOActionPlan,
        *,
        category: str = "unknown",
        condition: str = "",
        before_asset: str = "",
        after_asset: str = "",
        platform: str = "google_play",
    ) -> Optional[ASOExperiment]:
        """Create an experiment from an approved action plan.

        Returns ``None`` if the plan is not auto-approved (human queue or
        record-only plans do not create experiments — the loop tracks them
        for reporting but does not run them).
        """
        if plan.approval_status != ApprovalStatus.AUTO_APPROVED:
            return None

        experiment = ASOExperiment(
            experiment_id=str(uuid4()),
            game_id=plan.game_id,
            platform=platform,
            category=category,
            condition=condition,
            action_type=self._resolve_action(plan.action),
            before_asset=before_asset,
            after_asset=after_asset,
            start_date=_today_iso(),
            status=ASOExperimentStatus.RUNNING,
        )

        self.store.record(experiment)
        return experiment

    # ------------------------------------------------------------------ #
    def record_result(
        self,
        experiment: ASOExperiment,
        before: Dict[str, float],
        after: Dict[str, float],
        confidence: float = 0.0,
    ) -> ASOExperimentResult:
        """Record an experiment result and complete the experiment."""
        result = ASOExperimentResult(
            experiment_id=experiment.experiment_id,
            before=before,
            after=after,
            confidence=confidence,
        )
        self.store.record_result(result)

        # Mark experiment complete
        experiment.status = ASOExperimentStatus.COMPLETED
        experiment.end_date = _today_iso()
        self.store.record(experiment)

        return result

    # ------------------------------------------------------------------ #
    def handle_completion(
        self,
        experiment: ASOExperiment,
        result: ASOExperimentResult,
    ) -> List[ASOPattern]:
        """Called after an experiment completes: mine patterns.

        This is the key learning step — it extracts reusable ``ASOPattern``
        records from the experiment result and writes them to the pattern
        store. Uses the miner's three-arg signature:
        ``mine(experiments, results)``.
        """
        return self.miner.mine([experiment], [result])

    # ------------------------------------------------------------------ #
    def active_experiment_counts(
        self,
        game_ids: Optional[List[str]] = None,
    ) -> Dict[str, int]:
        """Number of currently RUNNING experiments per game.

        Used by the Policy Gate to enforce the concurrency limit.
        """
        all_exps = self.store.load_experiments()
        counts: Dict[str, int] = {}
        for exp in all_exps:
            if exp.status != ASOExperimentStatus.RUNNING:
                continue
            if game_ids is None or exp.game_id in game_ids:
                counts[exp.game_id] = counts.get(exp.game_id, 0) + 1
        return counts

    # ------------------------------------------------------------------ #
    def daily_summary(
        self,
        game_ids: Optional[List[str]] = None,
    ) -> Dict[str, Dict[str, int]]:
        """Count experiments (completed / failed / running) per game."""
        all_exps = self.store.load_experiments()
        summary: Dict[str, Dict[str, int]] = {}
        for exp in all_exps:
            if game_ids is not None and exp.game_id not in game_ids:
                continue
            bucket = summary.setdefault(exp.game_id, {
                "total": 0, "running": 0, "completed": 0, "failed": 0,
            })
            bucket["total"] += 1
            status_key = exp.status.value.lower()
            if status_key in bucket:
                bucket[status_key] += 1
        return summary


__all__ = ["ASOExperimentManager"]
