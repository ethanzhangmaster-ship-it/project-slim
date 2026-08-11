"""
E16.6.6 — ASO User Quality Analyzer.

Evaluates the *quality* of organic users, not just volume. Detects the
"CVR trap" — where conversion goes up but payer quality goes down.

Key metrics:
  * ``payer_rate`` — fraction of installers who pay (most important)
  * ``arpu`` / ``ltv`` — revenue per user
  * ``dau_retention`` — rough day-1 retention proxy

CVR Trap: CVR uplift > 0 but payer_rate dropped > 10% → fake growth.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.aso_intelligence.revenue.models import (
    ASORevenueAttribution,
    ASOActionReward,
)


@dataclass
class UserQualityReport:
    """Quality assessment for one ASO source."""

    source_key: str
    payer_rate: float
    arpu: float
    ltv: float
    is_cvr_trap: bool = False
    cvr_trap_reason: str = ""


_DEFAULT_PAYER_THRESHOLD = 0.02  # 2% payer rate = baseline
_LTV_HIGH_THRESHOLD = 2.0       # ARPU ≥ $2 = high quality
_QUALITY_LABELS = {
    "high": "High quality users — strong monetisation",
    "moderate": "Moderate quality users — average monetisation",
    "low": "Low quality users — consider optimising for payers",
    "ultra_low": "Ultra-low quality — review keyword/country targeting",
}


class ASOUserQualityAnalyzer:
    """Assess organic user quality and detect CVR traps."""

    # ------------------------------------------------------------------ #
    def quality_label(self, payer_rate: float, arpu: float) -> str:
        """Label for user quality based on payer_rate and ARPU."""
        if payer_rate >= 0.05 and arpu >= _LTV_HIGH_THRESHOLD:
            return "high"
        if payer_rate >= _DEFAULT_PAYER_THRESHOLD or arpu >= 1.0:
            return "moderate"
        if payer_rate >= 0.005 or arpu >= 0.3:
            return "low"
        return "ultra_low"

    def quality_description(self, label: str) -> str:
        return _QUALITY_LABELS.get(label, "Unknown quality")

    # ------------------------------------------------------------------ #
    def evaluate(self, attribution: ASORevenueAttribution) -> UserQualityReport:
        """Evaluate organic user quality from one attribution."""
        label = self.quality_label(attribution.payer_rate, attribution.arpu)
        return UserQualityReport(
            source_key=attribution.source_key,
            payer_rate=attribution.payer_rate,
            arpu=attribution.arpu,
            ltv=attribution.ltv,
        )

    # ------------------------------------------------------------------ #
    def detect_cvr_trap(
        self,
        attribution_before: ASORevenueAttribution,
        attribution_after: ASORevenueAttribution,
    ) -> bool:
        """Detect CVR trap: installs/CVR went up but quality dropped.

        Returns True if this is fake growth (CVR trap).
        """
        # CVR proxy: installs growth
        install_growth = (
            (attribution_after.installs - attribution_before.installs)
            / max(attribution_before.installs, 1)
        )
        payer_rate_change = (
            attribution_after.payer_rate - attribution_before.payer_rate
        )

        # CVR trap: installs up > 10% but payer rate dropped > 10%
        if install_growth > 0.1 and payer_rate_change < -0.1 * max(
            attribution_before.payer_rate, 0.001
        ):
            return True
        return False

    # ------------------------------------------------------------------ #
    def evaluate_experiment_quality(
        self,
        attribution_before: ASORevenueAttribution,
        attribution_after: ASORevenueAttribution,
    ) -> ASOActionReward:
        """Full quality + revenue evaluation of an experiment.

        Returns an ``ASOActionReward`` with CVR trap detection built in.
        """
        cvr_uplift = (
            (attribution_after.installs - attribution_before.installs)
            / max(attribution_before.installs, 1)
        )
        reward = ASOActionReward(
            experiment_id="",
            game_id=attribution_before.game_id,
            cvr_uplift=max(0.0, cvr_uplift),
            payer_rate_before=attribution_before.payer_rate,
            payer_rate_after=attribution_after.payer_rate,
            ltv_before=attribution_before.ltv,
            ltv_after=attribution_after.ltv,
        )
        reward.compute()
        return reward

    # ------------------------------------------------------------------ #
    def rank_by_quality(
        self,
        attributions: List[ASORevenueAttribution],
    ) -> List[ASORevenueAttribution]:
        """Sort attributions by ARPU descending (best quality first)."""
        return sorted(
            attributions, key=lambda a: a.arpu, reverse=True
        )


__all__ = ["UserQualityReport", "ASOUserQualityAnalyzer"]
