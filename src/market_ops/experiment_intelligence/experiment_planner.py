"""E9.9 Module 2: Experiment Planner.

Generates full experiment plans from selected candidates and baseline performance.
Each plan includes: hypothesis, control, variant, metrics, budget, duration.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from market_ops.experiment_intelligence.schemas import (
    ExperimentCandidate, ExperimentPlan,
)


class ExperimentPlanner:
    """Generates experiment plans from candidates.

    Usage:
        planner = ExperimentPlanner()
        plans = planner.create_plans(candidates, baseline_path="output/creative_learning/actual_performance.json")
    """

    # Default configuration
    DEFAULT_METRICS = ["CTR", "CPI", "D7_ROAS", "D30_LTV"]
    DEFAULT_BUDGET = 100.0           # Total budget per experiment
    DEFAULT_DURATION_DAYS = 7
    DEFAULT_CONFIDENCE = 0.95
    DEFAULT_POWER = 0.80

    def __init__(self) -> None:
        self._baseline: dict[str, dict[str, Any]] = {}

    def create_plans(
        self,
        candidates: list[ExperimentCandidate],
        baseline_path: str | Path | None = None,
        total_budget: float | None = None,
    ) -> list[ExperimentPlan]:
        """Generate experiment plans for each candidate.

        Args:
            candidates: Selected experiment candidates
            baseline_path: Path to actual_performance.json (optional)
            total_budget: Total budget across all experiments (optional)

        Returns:
            List of ExperimentPlan objects
        """
        # Load baseline if provided
        if baseline_path:
            self._load_baseline(baseline_path)

        budget_per = self._calculate_budget_per_experiment(
            len(candidates), total_budget
        )

        plans = []
        for candidate in candidates:
            plan = self._create_single_plan(candidate, budget_per)
            plans.append(plan)

        return plans

    # ── Baseline ───────────────────────────────────────────

    def _load_baseline(self, path: str | Path) -> None:
        """Load actual_performance.json for baseline LTV."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return

        records = data if isinstance(data, list) else data.get("records", [])
        self._baseline = {
            r.get("creative_id", ""): r for r in records
        }

    def _get_baseline_ltv(self, creative_id: str) -> float:
        """Get baseline LTV for a creative."""
        record = self._baseline.get(creative_id, {})
        return record.get("ltv_d30", 0.0) or record.get("ltv", 0.0)

    # ── Plan Creation ──────────────────────────────────────

    def _create_single_plan(
        self,
        candidate: ExperimentCandidate,
        budget: float,
    ) -> ExperimentPlan:
        """Create a single experiment plan."""
        experiment_id = f"EXP_{uuid.uuid4().hex[:8]}"

        # Generate hypothesis
        baseline_ltv = self._get_baseline_ltv(candidate.creative_id)
        lift_pct = 0.0
        if baseline_ltv > 0 and candidate.predicted_ltv > 0:
            lift_pct = ((candidate.predicted_ltv - baseline_ltv) / baseline_ltv) * 100
        hypothesis = self._generate_hypothesis(candidate, lift_pct)

        # Build variant dict
        variant = {
            "genome_id": candidate.genome_id,
            "hook": candidate.hook,
            "reward": candidate.reward,
            "visual_style": candidate.visual_style,
            "fantasy": candidate.fantasy,
            "mutation_type": candidate.mutation_type,
            "before": candidate.before,
            "after": candidate.after,
        }

        return ExperimentPlan(
            experiment_id=experiment_id,
            mutation_id=candidate.genome_id,
            hypothesis=hypothesis,
            control=candidate.creative_id,
            variant=variant,
            metrics=list(self.DEFAULT_METRICS),
            budget=budget,
            daily_budget=round(budget / self.DEFAULT_DURATION_DAYS, 2),
            duration_days=self.DEFAULT_DURATION_DAYS,
            confidence_level=self.DEFAULT_CONFIDENCE,
            statistical_power=self.DEFAULT_POWER,
            status="CREATED",
        )

    # ── Hypothesis Generation ──────────────────────────────

    def _generate_hypothesis(
        self, candidate: ExperimentCandidate, lift_pct: float
    ) -> str:
        """Generate a human-readable hypothesis."""
        mutation_type = candidate.mutation_type or "mutation"
        before = candidate.before or "current"
        after = candidate.after or "new"

        lift_str = f"{abs(lift_pct):.0f}%"
        direction = "improve" if lift_pct >= 0 else "reduce"

        return (
            f"Changing {mutation_type} from '{before}' to '{after}' "
            f"will {direction} LTV by {lift_str}"
        )

    # ── Budget Calculation ─────────────────────────────────

    def _calculate_budget_per_experiment(
        self, num_candidates: int, total_budget: float | None = None
    ) -> float:
        """Calculate budget per experiment."""
        if total_budget is not None and total_budget > 0:
            return total_budget / max(1, num_candidates)
        return self.DEFAULT_BUDGET

    # ── Summary ────────────────────────────────────────────

    def get_plan_summary(self, plans: list[ExperimentPlan]) -> dict[str, Any]:
        """Get summary of generated plans."""
        by_type: dict[str, int] = {}
        by_metric: dict[str, int] = {}
        total_budget = 0.0

        for p in plans:
            mtype = p.variant.get("mutation_type", "unknown")
            by_type[mtype] = by_type.get(mtype, 0) + 1
            for m in p.metrics:
                by_metric[m] = by_metric.get(m, 0) + 1
            total_budget += p.budget

        return {
            "total_plans": len(plans),
            "by_mutation_type": by_type,
            "by_metric": by_metric,
            "total_budget": round(total_budget, 2),
            "avg_budget_per_experiment": (
                round(total_budget / len(plans), 2) if plans else 0.0
            ),
            "avg_duration_days": (
                round(sum(p.duration_days for p in plans) / len(plans), 1)
                if plans else 0.0
            ),
        }