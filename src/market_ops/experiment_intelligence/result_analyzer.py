"""E9.9 Module 6: Result Analyzer.

Statistical analysis of experiment results:
  - Lift calculation: (variant - control) / control
  - p-value via t-test (scipy) or simplified z-test
  - Decision: WINNER / FAILED / INCONCLUSIVE
"""

from __future__ import annotations

import math
from typing import Any

from market_ops.experiment_intelligence.schemas import (
    ExperimentPlan, ExperimentResult, PerformanceSnapshot,
    ExperimentDecision,
)


# ── Decision Thresholds ────────────────────────────────────

WINNER_LIFT_THRESHOLD = 0.10      # 10% minimum positive lift
FAILED_LIFT_THRESHOLD = -0.05     # -5% maximum negative lift
P_VALUE_THRESHOLD = 0.05          # 95% confidence
MIN_SAMPLE_SIZE = 50              # Minimum installs per variant


class ResultAnalyzer:
    """Analyzes experiment results with statistical rigor.

    Usage:
        analyzer = ResultAnalyzer()
        result = analyzer.analyze(plan, control_perf, variant_perf)
    """

    def __init__(self) -> None:
        self._results: dict[str, ExperimentResult] = {}

    def analyze(
        self,
        plan: ExperimentPlan,
        control_performance: PerformanceSnapshot,
        variant_performance: PerformanceSnapshot,
    ) -> ExperimentResult:
        """Analyze experiment results.

        Args:
            plan: Experiment plan
            control_performance: Control group performance data
            variant_performance: Variant group performance data

        Returns:
            ExperimentResult with lift, p-value, confidence, decision
        """
        result = ExperimentResult(
            experiment_id=plan.experiment_id,
            control_creative_id=plan.control,
            variant_genome_id=plan.variant.get("genome_id", ""),
            sample_size_required=plan.sample_size_required,
        )

        # Fill performance data
        result.spend = variant_performance.spend
        result.installs = variant_performance.installs
        result.ctr = variant_performance.ctr
        result.cpi = variant_performance.cpi
        result.roas = variant_performance.roas
        result.d7_retention = variant_performance.d7_retention
        result.sample_size_achieved = variant_performance.installs

        # Calculate lift (primary metric: ROAS)
        if control_performance.roas > 0:
            result.lift = (
                (variant_performance.roas - control_performance.roas)
                / control_performance.roas
            )

        # Calculate p-value
        result.p_value = self._calculate_p_value_simple(
            control_performance, variant_performance
        )

        # Confidence
        result.confidence = 1.0 - result.p_value

        # Decision
        result.decision = self._make_decision(result)

        # Store
        self._results[plan.experiment_id] = result

        return result

    # ── Lift Calculation ───────────────────────────────────

    def _calculate_lift(
        self, control_value: float, variant_value: float
    ) -> float:
        """Calculate lift: (variant - control) / control."""
        if control_value == 0:
            return 0.0
        return (variant_value - control_value) / control_value

    # ── P-Value Calculation ────────────────────────────────

    def _calculate_p_value_simple(
        self,
        control: PerformanceSnapshot,
        variant: PerformanceSnapshot,
    ) -> float:
        """Simplified p-value calculation using ROAS with effect size.

        Uses a conservative approximation: ROAS difference normalized
        by pooled standard error. For ROAS (continuous metric, not a
        proportion), we estimate std from the coefficient of variation.
        """
        # Try scipy t-test if available
        try:
            return self._calculate_p_value_ttest(control, variant)
        except Exception:
            pass

        if control.installs < 2 or variant.installs < 2:
            return 1.0

        # Use ROAS as the metric (continuous, not proportion)
        p1 = control.roas
        p2 = variant.roas
        n1 = max(control.installs, 1)
        n2 = max(variant.installs, 1)

        # Estimate std from ROAS * CV (coefficient of variation ~0.5)
        std1 = p1 * 0.5
        std2 = p2 * 0.5

        # Pooled standard error
        se = math.sqrt(std1 ** 2 / n1 + std2 ** 2 / n2)
        if se == 0:
            return 1.0

        z = (p2 - p1) / se
        p_value = 2.0 * (1.0 - self._normal_cdf(abs(z)))

        return min(max(p_value, 0.0), 1.0)

    def _calculate_p_value_ttest(
        self,
        control: PerformanceSnapshot,
        variant: PerformanceSnapshot,
    ) -> float:
        """Full t-test using scipy (when available)."""
        from scipy.stats import ttest_ind_from_stats

        # Requires mean and std; use ROAS as mean, estimate std
        t_stat, p_value = ttest_ind_from_stats(
            mean1=control.roas,
            std1=control.roas * 0.5,       # rough estimate
            nobs1=max(control.installs, 1),
            mean2=variant.roas,
            std2=variant.roas * 0.5,
            nobs2=max(variant.installs, 1),
        )
        return float(p_value)

    def _normal_cdf(self, x: float) -> float:
        """Approximation of standard normal CDF."""
        # Abramowitz & Stegun approximation
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    # ── Decision Making ────────────────────────────────────

    def _make_decision(self, result: ExperimentResult) -> str:
        """Make statistical decision based on thresholds.

        WINNER:  lift > 10% AND p_value < 0.05 AND sample_size >= 50
        FAILED:  lift < -5% AND p_value < 0.05 AND sample_size >= 50
        INCONCLUSIVE: otherwise
        """
        # Check minimum sample size
        if result.sample_size_achieved < MIN_SAMPLE_SIZE:
            return ExperimentDecision.INCONCLUSIVE.value

        # Check statistical significance
        if result.p_value >= P_VALUE_THRESHOLD:
            return ExperimentDecision.INCONCLUSIVE.value

        # Check lift direction
        if result.lift >= WINNER_LIFT_THRESHOLD:
            return ExperimentDecision.WINNER.value
        elif result.lift <= FAILED_LIFT_THRESHOLD:
            return ExperimentDecision.FAILED.value

        return ExperimentDecision.INCONCLUSIVE.value

    # ── Summary ────────────────────────────────────────────

    def get_analysis_summary(self) -> dict[str, Any]:
        """Get summary of all analyzed results."""
        results = list(self._results.values())
        winners = sum(1 for r in results if r.decision == ExperimentDecision.WINNER.value)
        failed = sum(1 for r in results if r.decision == ExperimentDecision.FAILED.value)
        inconclusive = sum(1 for r in results if r.decision == ExperimentDecision.INCONCLUSIVE.value)

        lifts = [r.lift for r in results if r.lift != 0]

        return {
            "total_analyzed": len(results),
            "winners": winners,
            "failed": failed,
            "inconclusive": inconclusive,
            "win_rate": round(winners / max(1, len(results)), 3),
            "avg_lift": round(sum(lifts) / max(1, len(lifts)), 4),
            "max_lift": round(max(lifts), 4) if lifts else 0.0,
            "min_lift": round(min(lifts), 4) if lifts else 0.0,
        }