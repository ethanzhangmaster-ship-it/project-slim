"""E9.9 Module 3: A/B Test Designer.

Statistical design for experiments:
  - Sample size calculation (z-test based)
  - Baseline rate estimation per metric
  - Design validation (fills sample_size_required in ExperimentPlan)

Uses scipy.stats.norm.ppf if available, falls back to hardcoded z-scores.
"""

from __future__ import annotations

import math
from typing import Any

from market_ops.experiment_intelligence.schemas import ExperimentPlan


# ── Z-score lookup (fallback when scipy unavailable) ──────

# Pre-computed z-scores for common confidence/power levels
_Z_SCORES = {
    0.80: 1.2816,
    0.85: 1.4395,
    0.90: 1.6449,
    0.95: 1.9600,
    0.99: 2.5758,
}


def _z_score(alpha: float) -> float:
    """Get z-score for a given significance level.

    Tries scipy.stats.norm.ppf first, falls back to lookup table.
    """
    try:
        from scipy.stats import norm
        return norm.ppf(1.0 - alpha / 2.0)
    except ImportError:
        pass

    # Fallback: find closest in lookup table
    closest = min(_Z_SCORES.keys(), key=lambda k: abs(k - (1.0 - alpha)))
    return _Z_SCORES[closest]


# ── Baseline rates per metric type ─────────────────────────

# Default baseline conversion rates (industry averages for mobile games)
_DEFAULT_BASELINE = {
    "CTR": 0.02,          # 2% click-through rate
    "CPI": 0.12,          # 12% conversion from click to install
    "D7_ROAS": 0.15,     # 15% D7 ROAS (revenue/spend)
    "D30_LTV": 0.25,     # 25% D30 LTV rate
    "RETENTION": 0.25,   # 25% D7 retention
    "ROAS": 0.12,        # 12% ROAS
}


class ABTestDesigner:
    """Statistical A/B test designer.

    Calculates minimum sample sizes and validates experiment designs.

    Usage:
        designer = ABTestDesigner()
        plans = [designer.design_test(p, baseline) for p in plans]
    """

    def __init__(self) -> None:
        pass

    def design_test(
        self,
        plan: ExperimentPlan,
        baseline_performance: dict[str, Any] | None = None,
    ) -> ExperimentPlan:
        """Design an A/B test for a given experiment plan.

        Fills in sample_size_required based on primary metric.

        Args:
            plan: Experiment plan to design
            baseline_performance: Optional baseline metrics dict

        Returns:
            Updated ExperimentPlan with sample_size_required
        """
        primary_metric = plan.metrics[0] if plan.metrics else "CTR"

        # Get baseline rate
        baseline_rate = self._get_baseline_rate(primary_metric, baseline_performance)

        # Calculate sample size
        plan.sample_size_required = self.calculate_sample_size(
            baseline_rate=baseline_rate,
            expected_lift=0.15,  # default 15% improvement
            confidence=plan.confidence_level,
            power=plan.statistical_power,
        )

        return plan

    def calculate_sample_size(
        self,
        baseline_rate: float,
        expected_lift: float = 0.15,
        confidence: float = 0.95,
        power: float = 0.80,
    ) -> int:
        """Calculate minimum sample size per variant.

        Formula: n = (Z_alpha/2 + Z_beta)^2 * 2 * p * (1-p) / delta^2

        Args:
            baseline_rate: Baseline conversion rate (e.g., 0.05 for 5%)
            expected_lift: Minimum detectable effect (e.g., 0.15 for 15%)
            confidence: Confidence level (default 0.95)
            power: Statistical power (default 0.80)

        Returns:
            Minimum sample size per variant (rounded up to integer)
        """
        if baseline_rate <= 0:
            baseline_rate = 0.01

        # Z-scores
        z_alpha = _z_score(1.0 - confidence)
        z_beta = _z_score(1.0 - power)

        # Minimum detectable effect
        delta = baseline_rate * expected_lift

        if delta <= 0:
            return 50000  # fallback

        p = baseline_rate
        n = (z_alpha + z_beta) ** 2 * 2 * p * (1.0 - p) / (delta ** 2)

        return math.ceil(n)

    def _get_baseline_rate(
        self,
        metric: str,
        baseline_performance: dict[str, Any] | None = None,
    ) -> float:
        """Get baseline rate for a metric.

        Prefers provided baseline, falls back to industry defaults.
        """
        if baseline_performance:
            rate = baseline_performance.get(metric.lower())
            if rate is not None and rate > 0:
                return float(rate)

        return _DEFAULT_BASELINE.get(metric.upper(), 0.05)

    # ── Design Summary ─────────────────────────────────────

    def get_design_summary(
        self, plans: list[ExperimentPlan]
    ) -> dict[str, Any]:
        """Get summary of A/B test designs."""
        sample_sizes = [p.sample_size_required for p in plans if p.sample_size_required > 0]
        return {
            "total_experiments": len(plans),
            "designed": len(sample_sizes),
            "avg_sample_size": (
                sum(sample_sizes) / len(sample_sizes) if sample_sizes else 0
            ),
            "min_sample_size": min(sample_sizes) if sample_sizes else 0,
            "max_sample_size": max(sample_sizes) if sample_sizes else 0,
        }