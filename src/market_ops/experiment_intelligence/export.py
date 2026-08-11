"""E9.9: Export Module — Standalone export for all Experiment output files.

Exports:
  1. experiment_plans.json     — all experiment plans
  2. experiment_results.json   — experiment outcomes
  3. feedback_signals.json     — learning signals to E9.7
  4. experiment_report.json    — full experiment cycle summary
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_ops.experiment_intelligence.schemas import (
    ExperimentPlan, ExperimentResult, FeedbackSignal,
)


class ExperimentExporter:
    """Standalone export module for E9.9 Experiment outputs.

    Usage:
        exporter = ExperimentExporter(output_dir="output/experiment_intelligence")
        paths = exporter.export_all(plans, results, signals)
    """

    def __init__(self, output_dir: str | Path = "output/experiment_intelligence") -> None:
        self._output_dir = Path(output_dir)

    def ensure_output_dir(self) -> Path:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        return self._output_dir

    # ── File 1: experiment_plans.json ──────────────────────

    def export_plans(
        self,
        plans: list[ExperimentPlan],
        filename: str = "experiment_plans.json",
    ) -> Path:
        """Export all experiment plans."""
        path = self._output_dir / filename
        self.ensure_output_dir()

        data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_experiments": len(plans),
            "experiments": [p.to_dict() for p in plans],
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path

    # ── File 2: experiment_results.json ────────────────────

    def export_results(
        self,
        results: list[ExperimentResult],
        filename: str = "experiment_results.json",
    ) -> Path:
        """Export experiment results."""
        path = self._output_dir / filename
        self.ensure_output_dir()

        winners = sum(1 for r in results if r.decision == "WINNER")
        failed = sum(1 for r in results if r.decision == "FAILED")
        inconclusive = sum(1 for r in results if r.decision == "INCONCLUSIVE")

        data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_experiments": len(results),
            "winners": winners,
            "failed": failed,
            "inconclusive": inconclusive,
            "results": [r.to_dict() for r in results],
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path

    # ── File 3: feedback_signals.json ──────────────────────

    def export_feedback(
        self,
        signals: list[FeedbackSignal],
        filename: str = "feedback_signals.json",
    ) -> Path:
        """Export feedback signals for E9.7."""
        path = self._output_dir / filename
        self.ensure_output_dir()

        data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_signals": len(signals),
            "signals": [s.to_dict() for s in signals],
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path

    # ── File 4: experiment_report.json ─────────────────────

    def export_report(
        self,
        plans: list[ExperimentPlan],
        results: list[ExperimentResult],
        signals: list[FeedbackSignal],
        filename: str = "experiment_report.json",
    ) -> Path:
        """Export full experiment summary report."""
        path = self._output_dir / filename
        self.ensure_output_dir()

        winners = sum(1 for r in results if r.decision == "WINNER")
        failed = sum(1 for r in results if r.decision == "FAILED")
        inconclusive = sum(1 for r in results if r.decision == "INCONCLUSIVE")

        total = len(results)
        avg_lift = (
            sum(r.lift for r in results) / total if total > 0 else 0.0
        )
        total_spend = sum(r.spend for r in results)

        # By mutation type
        by_type: dict[str, dict[str, Any]] = {}
        for r in results:
            # Find matching plan to get mutation type
            plan = next((p for p in plans if p.experiment_id == r.experiment_id), None)
            if plan:
                # Extract from variant
                mtype = plan.variant.get("mutation_type", "unknown")
                if mtype not in by_type:
                    by_type[mtype] = {"total": 0, "winners": 0, "avg_lift": 0.0}
                by_type[mtype]["total"] += 1
                if r.decision == "WINNER":
                    by_type[mtype]["winners"] += 1
                by_type[mtype]["avg_lift"] = round(
                    (by_type[mtype]["avg_lift"] * (by_type[mtype]["total"] - 1) + r.lift)
                    / by_type[mtype]["total"], 4
                )

        # Best mutation
        best_type = ""
        best_lift = 0.0
        for mtype, stats in by_type.items():
            if stats["avg_lift"] > best_lift:
                best_lift = stats["avg_lift"]
                best_type = mtype

        data = {
            "report_time": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_experiments": total,
                "winners": winners,
                "failed": failed,
                "inconclusive": inconclusive,
                "win_rate": round(winners / max(1, total), 3),
                "average_lift": round(avg_lift, 4),
                "total_budget_spent": round(total_spend, 2),
                "best_mutation_type": best_type,
                "best_mutation_lift": round(best_lift, 4),
            },
            "by_mutation_type": by_type,
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path

    # ── Batch Export ───────────────────────────────────────

    def export_all(
        self,
        plans: list[ExperimentPlan],
        results: list[ExperimentResult],
        signals: list[FeedbackSignal],
    ) -> dict[str, str]:
        """Export all 4 output files.

        Returns:
            {file_category: full_path}
        """
        return {
            "experiment_plans": str(self.export_plans(plans)),
            "experiment_results": str(self.export_results(results)),
            "feedback_signals": str(self.export_feedback(signals)),
            "experiment_report": str(self.export_report(plans, results, signals)),
        }

    # ── Summary ────────────────────────────────────────────

    def get_export_summary(self, paths: dict[str, str]) -> dict[str, Any]:
        """Get summary of exported files with sizes."""
        summary = {}
        for category, path_str in paths.items():
            p = Path(path_str)
            if p.exists():
                summary[category] = {
                    "path": path_str,
                    "size_kb": round(p.stat().st_size / 1024, 1),
                }
            else:
                summary[category] = {"path": path_str, "status": "missing"}
        return summary