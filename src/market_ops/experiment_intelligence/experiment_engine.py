"""E9.9 Module 8: Experiment Engine.

Orchestrates the full E9.9 experiment pipeline:
  1. Load mutation candidates from E9.8
  2. Select top experiments
  3. Load baseline performance
  4. Generate experiment plans
  5. Design A/B tests
  6. Allocate budget
  7. Track experiments
  8. Analyze results (mock data in v1.0)
  9. Generate feedback signals
  10. Apply feedback to E9.7
  11. Export all outputs
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_ops.experiment_intelligence.schemas import (
    ExperimentCandidate, ExperimentPlan, ExperimentResult,
    FeedbackSignal, PerformanceSnapshot, BudgetMode,
)
from market_ops.experiment_intelligence.experiment_selector import ExperimentSelector
from market_ops.experiment_intelligence.experiment_planner import ExperimentPlanner
from market_ops.experiment_intelligence.ab_test_designer import ABTestDesigner
from market_ops.experiment_intelligence.budget_allocator import BudgetAllocator
from market_ops.experiment_intelligence.experiment_tracker import ExperimentTracker
from market_ops.experiment_intelligence.result_analyzer import ResultAnalyzer
from market_ops.experiment_intelligence.feedback_engine import FeedbackEngine
from market_ops.experiment_intelligence.export import ExperimentExporter


class ExperimentEngine:
    """Orchestrates the full E9.9 experiment pipeline.

    Usage:
        engine = ExperimentEngine()
        result = engine.run()
        print(result["summary"])
    """

    def __init__(self) -> None:
        self._selector = ExperimentSelector()
        self._planner = ExperimentPlanner()
        self._designer = ABTestDesigner()
        self._allocator = BudgetAllocator()
        self._tracker = ExperimentTracker()
        self._analyzer = ResultAnalyzer()
        self._feedback = FeedbackEngine()
        self._exporter = ExperimentExporter()

    def run(
        self,
        mutations_path: str | Path = "output/creative_evolution/top_mutations.json",
        performance_path: str | Path = "output/creative_learning/actual_performance.json",
        output_dir: str | Path = "output/experiment_intelligence",
        total_budget: float = 2000.0,
        mode: str = "fixed",
        top_n: int = 20,
        seed: int = 42,
    ) -> dict[str, Any]:
        """Execute the full E9.9 experiment pipeline.

        Args:
            mutations_path: Path to E9.8 top_mutations.json
            performance_path: Path to actual_performance.json
            output_dir: Output directory for experiment files
            total_budget: Total budget across all experiments
            mode: Budget mode ("fixed", "dynamic", "bandit")
            top_n: Number of experiments to select
            seed: Random seed for reproducibility

        Returns:
            {status, summary, export_paths, candidates, plans, results, signals}
        """
        random.seed(seed)

        # Step 1: Load mutation candidates
        candidates = self._selector.select(str(mutations_path), top_n=top_n)

        # Step 2: Load baseline
        baseline = self._load_baseline(str(performance_path))

        # Step 3: Generate experiment plans
        plans = self._planner.create_plans(
            candidates, baseline_path=str(performance_path)
        )

        # Step 4: Design A/B tests
        for i, plan in enumerate(plans):
            parent_creative = plan.control
            parent_baseline = baseline.get(parent_creative, {})
            plans[i] = self._designer.design_test(plan, parent_baseline)

        # Step 5: Allocate budget
        budget_mode = BudgetMode(mode) if mode in [b.value for b in BudgetMode] else BudgetMode.FIXED
        plans = self._allocator.allocate(plans, total_budget=total_budget, mode=budget_mode)

        # Step 6: Track (start all experiments)
        for plan in plans:
            self._tracker.start(plan)

        # Step 7: Analyze results (mock data in v1.0)
        results = self._analyze_with_mock_data(plans, baseline)

        # Step 8: Generate feedback signals
        signals = self._feedback.generate_feedback(results, candidates)

        # Step 9: Apply feedback to E9.7
        feedback_status = self._feedback.apply_feedback_to_e97(signals)

        # Step 10: Export all outputs
        self._exporter._output_dir = Path(output_dir)
        export_paths = self._exporter.export_all(plans, results, signals)

        # Build summary
        selection_summary = self._selector.get_selection_summary(candidates)
        plan_summary = self._planner.get_plan_summary(plans)
        allocation_summary = self._allocator.get_allocation_summary(plans, budget_mode)
        tracking_summary = self._tracker.get_tracking_summary()
        analysis_summary = self._analyzer.get_analysis_summary()
        feedback_summary = self._feedback.get_feedback_summary(signals)

        return {
            "status": "success",
            "summary": {
                "selection": selection_summary,
                "plans": plan_summary,
                "allocation": allocation_summary,
                "tracking": tracking_summary,
                "analysis": analysis_summary,
                "feedback": feedback_summary,
                "feedback_applied": feedback_status,
            },
            "export_paths": export_paths,
            "candidates": candidates,
            "plans": plans,
            "results": results,
            "signals": signals,
        }

    # ── Mock Data Analysis ─────────────────────────────────

    def _analyze_with_mock_data(
        self,
        plans: list[ExperimentPlan],
        baseline: dict[str, dict[str, Any]],
    ) -> list[ExperimentResult]:
        """Generate mock performance data and analyze results.

        In v1.0, UA platform data is mocked. E10 will replace this
        with real API data using the same PerformanceSnapshot schema.

        Mock strategy: top 30% of plans (by mutation_score) are winners,
        middle 40% are inconclusive, bottom 30% are losers.
        """
        results = []

        # Sort plans by mutation_score for realistic winner distribution
        scored_plans = sorted(
            plans,
            key=lambda p: p.variant.get("mutation_score", 0.5),
            reverse=True,
        )

        # Assign tiers
        n = len(scored_plans)
        n_winner = max(1, n * 30 // 100)   # top 30% → winners
        n_loser = max(1, n * 30 // 100)    # bottom 30% → losers
        # middle 40% → inconclusive (mixed)

        tiers = {}
        for i, plan in enumerate(scored_plans):
            if i < n_winner:
                tiers[plan.experiment_id] = "winner"
            elif i >= n - n_loser:
                tiers[plan.experiment_id] = "loser"
            else:
                tiers[plan.experiment_id] = "inconclusive"

        for plan in plans:
            parent_creative = plan.control
            parent_baseline = baseline.get(parent_creative, {})

            tier = tiers.get(plan.experiment_id, "inconclusive")

            # Generate control (baseline) performance
            control_perf = self._generate_mock_performance(
                plan, parent_baseline, tier="control"
            )

            # Generate variant performance based on tier
            variant_perf = self._generate_mock_performance(
                plan, parent_baseline, tier=tier
            )

            # Record performance
            self._tracker.record_performance(plan.experiment_id, control_perf)
            self._tracker.record_performance(plan.experiment_id, variant_perf)

            # Analyze
            result = self._analyzer.analyze(plan, control_perf, variant_perf)

            # Update tracker status
            if result.decision == "WINNER":
                self._tracker.mark_winner(plan.experiment_id)
            elif result.decision == "FAILED":
                self._tracker.mark_failed(plan.experiment_id)
            else:
                self._tracker.complete(plan.experiment_id)

            results.append(result)

        return results

    def _generate_mock_performance(
        self,
        plan: ExperimentPlan,
        baseline_data: dict[str, Any],
        tier: str = "control",
    ) -> PerformanceSnapshot:
        """Generate realistic mock performance data.

        tier="control": baseline performance (neutral)
        tier="winner": better ROAS, higher retention
        tier="loser": worse ROAS, lower retention
        tier="inconclusive": mixed, close to control
        """
        # Base metrics from baseline
        base_roas = baseline_data.get("roas", 1.0) or 1.0
        base_ltv = baseline_data.get("ltv_d30", 3.0) or 3.0
        base_retention = baseline_data.get("d30_retention", 0.25) or 0.25

        # Adjust based on tier
        if tier == "control":
            roas = base_roas * random.uniform(0.95, 1.05)
            ltv = base_ltv
            retention = base_retention
        elif tier == "winner":
            roas = base_roas * random.uniform(1.15, 1.5)
            ltv = base_ltv * random.uniform(1.1, 1.3)
            retention = base_retention * random.uniform(1.05, 1.15)
        elif tier == "loser":
            roas = base_roas * random.uniform(0.5, 0.8)
            ltv = base_ltv * random.uniform(0.6, 0.85)
            retention = base_retention * random.uniform(0.75, 0.95)
        else:  # inconclusive
            roas = base_roas * random.uniform(0.9, 1.1)
            ltv = base_ltv * random.uniform(0.95, 1.05)
            retention = base_retention * random.uniform(0.95, 1.05)

        spend = plan.budget * random.uniform(0.8, 1.0)
        installs = int(spend / random.uniform(0.5, 2.0))  # CPI $0.5-$2.0 (merge game)
        impressions = int(installs / random.uniform(0.01, 0.05))  # 1-5% CTR
        clicks = int(installs / random.uniform(0.05, 0.15))  # 5-15% install rate

        return PerformanceSnapshot(
            creative_id=plan.variant.get("genome_id", ""),
            timestamp=datetime.now(timezone.utc).isoformat(),
            spend=round(spend, 2),
            impressions=impressions,
            clicks=clicks,
            installs=installs,
            revenue=round(spend * roas, 2),
            ctr=round(clicks / max(1, impressions), 4),
            cpi=round(spend / max(1, installs), 2),
            roas=round(roas, 3),
            d7_retention=round(retention * 0.7, 3),
            d30_ltv=round(ltv, 1),
        )

    # ── Baseline Loader ────────────────────────────────────

    def _load_baseline(self, path: str) -> dict[str, dict[str, Any]]:
        """Load actual_performance.json as baseline lookup."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

        records = data if isinstance(data, list) else data.get("records", [])
        return {r.get("creative_id", ""): r for r in records}


# ── Convenience Function ───────────────────────────────────

def run_e99_pipeline(
    mutations_path: str | Path | None = None,
    performance_path: str | Path | None = None,
    output_dir: str | Path | None = None,
    total_budget: float = 2000.0,
    mode: str = "fixed",
    top_n: int = 20,
    seed: int = 42,
) -> dict[str, Any]:
    """Run the full E9.9 experiment pipeline with default paths.

    Convenience wrapper around ExperimentEngine.run().
    """
    engine = ExperimentEngine()

    kwargs: dict[str, Any] = {
        "total_budget": total_budget,
        "mode": mode,
        "top_n": top_n,
        "seed": seed,
    }
    if mutations_path:
        kwargs["mutations_path"] = str(mutations_path)
    if performance_path:
        kwargs["performance_path"] = str(performance_path)
    if output_dir:
        kwargs["output_dir"] = str(output_dir)

    return engine.run(**kwargs)