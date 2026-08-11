"""
E16.6.8 — Creative Experiment Bridge.

Connects generated creative assets to E16.6.4's experiment lifecycle.

Pipeline: Candidate → ASOExperiment → RUNNING → Result → Pattern → Memory

Also integrates E16.6.6 Revenue Feedback:
  * CVR up + payers up → pattern reward HIGH
  * CVR up + payers down → pattern downweighted (fake growth)
"""

from __future__ import annotations

from typing import Dict, List, Optional
from uuid import uuid4

from src.aso_intelligence.creative_generator.models import (
    CreativeCandidate,
    StoreAssetType,
)
from src.aso_intelligence.experiment_memory.experiment_store import (
    ASOExperimentStore,
)
from src.aso_intelligence.experiment_memory.experiment_models import (
    ASOExperiment,
    ASOExperimentAction,
    ASOExperimentResult,
    ASOExperimentStatus,
    ASOPattern,
)


# Map store asset type → experiment action
_ASSET_TO_ACTION = {
    StoreAssetType.ICON: ASOExperimentAction.UPDATE_ICON,
    StoreAssetType.SCREENSHOT: ASOExperimentAction.UPDATE_SCREENSHOT,
}


class CreativeExperimentBridge:
    """Manage experiment lifecycle for generated creative assets."""

    def __init__(self, store: Optional[ASOExperimentStore] = None):
        self.store = store

    # ------------------------------------------------------------------ #
    def create_experiment(
        self,
        game_id: str,
        candidate: CreativeCandidate,
        category: str = "unknown",
        condition: str = "",
        platform: str = "google_play",
    ) -> Optional[ASOExperiment]:
        """Create an experiment comparing current listing → candidate.

        Creates a RUNNING experiment in E16.6.4 store.
        Returns ``None`` if no store is configured.
        """
        if self.store is None:
            return None

        action = _ASSET_TO_ACTION.get(
            candidate.asset_type, ASOExperimentAction.UPDATE_SCREENSHOT
        )

        experiment = ASOExperiment(
            experiment_id=str(uuid4()),
            game_id=game_id,
            platform=platform,
            category=category,
            condition=condition or f"{candidate.asset_type.value}_generated",
            action_type=action,
            before_asset="current_listing",
            after_asset=candidate.variant_label,
            start_date=_today_iso(),
            status=ASOExperimentStatus.RUNNING,
        )
        self.store.record(experiment)
        return experiment

    # ------------------------------------------------------------------ #
    def record_result(
        self,
        experiment: ASOExperiment,
        cvr_before: float = 0.0,
        cvr_after: float = 0.0,
        installs_before: int = 0,
        installs_after: int = 0,
        ltv_before: float = 0.0,
        ltv_after: float = 0.0,
        payer_rate_before: float = 0.0,
        payer_rate_after: float = 0.0,
        confidence: float = 0.85,
    ) -> Optional[ASOExperimentResult]:
        """Record experiment result with revenue data.

        Returns the result, or None if no store configured.
        """
        if self.store is None:
            return None

        result = ASOExperimentResult(
            experiment_id=experiment.experiment_id,
            before={
                "store_cvr": cvr_before,
                "installs": float(installs_before),
                "ltv": ltv_before,
                "payer_rate": payer_rate_before,
            },
            after={
                "store_cvr": cvr_after,
                "installs": float(installs_after),
                "ltv": ltv_after,
                "payer_rate": payer_rate_after,
            },
            confidence=confidence,
        )
        self.store.record_result(result)

        # Mark experiment complete
        experiment.status = ASOExperimentStatus.COMPLETED
        experiment.end_date = _today_iso()
        self.store.record(experiment)

        return result

    # ------------------------------------------------------------------ #
    def learn_pattern(
        self,
        experiment: ASOExperiment,
        result: ASOExperimentResult,
        candidate: CreativeCandidate,
    ) -> Optional[ASOPattern]:
        """Learn from experiment result → Creative Pattern in store.

        Uses revenue feedback: if CVR went up but payer_rate dropped,
        the pattern's success is downweighted.
        """
        if self.store is None:
            return None

        cvr_uplift = result.cvr_change()
        ltv_change = result.ltv_change()

        # Revenue-adjusted reward
        payer_before = result.before.get("payer_rate", 0.0)
        payer_after = result.after.get("payer_rate", 0.0)
        revenue_quality = (
            payer_after / max(payer_before, 0.001) if payer_before > 0 else 1.0
        )

        is_fake_growth = cvr_uplift > 0 and revenue_quality < 0.9
        reward = cvr_uplift * revenue_quality * max(0.0, 1.0 + ltv_change)

        genome_desc = ""
        if candidate.genome:
            genome_desc = (
                f"char={candidate.genome.hook_character},"
                f"reward={candidate.genome.hook_reward}"
            )

        pattern = ASOPattern(
            category=experiment.category,
            condition=experiment.condition,
            action=experiment.action_type.value,
            result=(
                f"CVR {cvr_uplift:+.0%}, "
                f"LTV {ltv_change:+.0%}, "
                f"reward {reward:+.1%}"
                f"{' (FAKE GROWTH)' if is_fake_growth else ''}"
                f" | genome: {genome_desc}"
            ),
            confidence=result.confidence,
            sample_size=1,
            success_rate=0.0 if is_fake_growth else 1.0,
            reward=reward,
            pattern_id=f"{experiment.category}:{experiment.condition}:"
                       f"{experiment.action_type.value}:creative",
        )
        self.store.record_pattern(pattern)
        return pattern


def _today_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


__all__ = ["CreativeExperimentBridge"]
