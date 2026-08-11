"""E9.7: Prediction Error Analyzer — Compares predicted vs actual performance.

Computes per-creative prediction errors:
  - Archetype distribution error (MAE per archetype)
  - Metric errors (LTV, D30, payer_rate)
  - Aggregated error reports

Formulas:
  archetype_error = actual_prob - predicted_prob
  metric_error = actual_value - predicted_value
  MAE = mean(|error|) across all entries
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from market_ops.creative_learning.schemas import (
    PredictionRecord, CreativeActualPerformance,
    ArchetypeError, MetricError, PredictionError,
)


class PredictionErrorAnalyzer:
    """Computes prediction errors by comparing predictions with actuals.

    Usage:
        analyzer = PredictionErrorAnalyzer()
        errors = analyzer.compare(prediction_records, actual_performances)
        report = analyzer.get_error_report(errors)
    """

    def __init__(self) -> None:
        self._errors: dict[str, PredictionError] = {}

    # ── Comparison ─────────────────────────────────────────

    def compare(
        self,
        predictions: dict[str, PredictionRecord],
        actuals: dict[str, CreativeActualPerformance],
    ) -> dict[str, PredictionError]:
        """Compare predictions with actual performance.

        Args:
            predictions: {creative_id: PredictionRecord}
            actuals: {creative_id: CreativeActualPerformance}

        Returns:
            {creative_id: PredictionError}
        """
        self._errors = {}

        for creative_id, pred in predictions.items():
            actual = actuals.get(creative_id)
            if actual is None:
                continue

            error = self._compute_error(pred, actual)
            self._errors[creative_id] = error

        return self._errors

    def _compute_error(
        self,
        pred: PredictionRecord,
        actual: CreativeActualPerformance,
    ) -> PredictionError:
        """Compute full error for one creative."""
        genome_name = pred.creative_genome_name

        # ── Archetype errors ──
        archetype_errors: dict[str, ArchetypeError] = {}
        all_arches = set(pred.archetype_prediction.keys()) | set(actual.archetype_distribution.keys())

        for arch in all_arches:
            pred_p = pred.archetype_prediction.get(arch, 0.0)
            actual_p = actual.archetype_distribution.get(arch, 0.0)
            abs_err = actual_p - pred_p
            rel_err = abs_err / max(pred_p, 0.01)

            archetype_errors[arch] = ArchetypeError(
                archetype=arch,
                predicted=pred_p,
                actual=actual_p,
                absolute_error=abs_err,
                relative_error=rel_err,
            )

        # ── Metric errors ──
        metric_errors: dict[str, MetricError] = {}

        metric_map = {
            "ltv": (pred.predicted_metrics.get("ltv", 0), actual.ltv_d30),
            "d30_retention": (pred.predicted_metrics.get("d30_retention", 0), actual.d30_retention),
            "payer_rate": (pred.predicted_metrics.get("payer_rate", 0), actual.payer_rate),
        }

        for metric, (pred_v, actual_v) in metric_map.items():
            abs_err = actual_v - pred_v
            rel_err = abs_err / max(abs(pred_v), 0.01)

            metric_errors[metric] = MetricError(
                metric=metric,
                predicted=pred_v,
                actual=actual_v,
                absolute_error=abs_err,
                relative_error=rel_err,
            )

        # ── Aggregate scores ──
        archetype_mae = sum(
            abs(e.absolute_error) for e in archetype_errors.values()
        ) / max(len(archetype_errors), 1)

        metric_mae = sum(
            abs(e.absolute_error) for e in metric_errors.values()
        ) / max(len(metric_errors), 1)

        ltv_error = metric_errors.get("ltv", MetricError()).absolute_error

        return PredictionError(
            creative_id=pred.creative_id,
            creative_genome_name=genome_name,
            archetype_errors=archetype_errors,
            metric_errors=metric_errors,
            archetype_mae=round(archetype_mae, 3),
            metric_mae=round(metric_mae, 3),
            ltv_error=round(ltv_error, 2),
        )

    # ── Error Report ───────────────────────────────────────

    def get_error_report(
        self, errors: dict[str, PredictionError] | None = None,
    ) -> dict[str, Any]:
        """Generate aggregated error report."""
        errors = errors or self._errors
        if not errors:
            return {"status": "empty", "total_creatives": 0}

        error_list = list(errors.values())
        n = len(error_list)

        # Overall MAE
        avg_archetype_mae = sum(e.archetype_mae for e in error_list) / n
        avg_metric_mae = sum(e.metric_mae for e in error_list) / n
        avg_ltv_error = sum(e.ltv_error for e in error_list) / n

        # Per-archetype error summary
        arch_errors: dict[str, list[float]] = defaultdict(list)
        for e in error_list:
            for arch, ae in e.archetype_errors.items():
                arch_errors[arch].append(ae.absolute_error)

        archetype_summary = {}
        for arch, errs in arch_errors.items():
            archetype_summary[arch] = {
                "mean_error": round(sum(errs) / len(errs), 3),
                "max_overpredict": round(min(errs), 3),  # most negative
                "max_underpredict": round(max(errs), 3),  # most positive
                "count": len(errs),
            }

        # Per-metric error summary
        metric_errors_agg: dict[str, list[float]] = defaultdict(list)
        for e in error_list:
            for metric, me in e.metric_errors.items():
                metric_errors_agg[metric].append(me.absolute_error)

        metric_summary = {}
        for metric, errs in metric_errors_agg.items():
            metric_summary[metric] = {
                "mean_error": round(sum(errs) / len(errs), 3),
                "range": f"{round(min(errs), 2)} to {round(max(errs), 2)}",
                "count": len(errs),
            }

        # Top errors (largest absolute LTV error)
        top_errors = sorted(error_list, key=lambda e: -abs(e.ltv_error))[:10]

        return {
            "total_creatives": n,
            "avg_archetype_mae": round(avg_archetype_mae, 3),
            "avg_metric_mae": round(avg_metric_mae, 3),
            "avg_ltv_error": round(avg_ltv_error, 2),
            "archetype_summary": archetype_summary,
            "metric_summary": metric_summary,
            "top_errors": [
                {
                    "creative_id": e.creative_id,
                    "genome": e.creative_genome_name,
                    "ltv_error": e.ltv_error,
                    "archetype_mae": e.archetype_mae,
                }
                for e in top_errors
            ],
        }

    def get_errors_by_hook(
        self,
        errors: dict[str, PredictionError] | None = None,
        predictions: dict[str, PredictionRecord] | None = None,
    ) -> dict[str, list[PredictionError]]:
        """Group errors by hook type for pattern analysis."""
        errors = errors or self._errors
        predictions = predictions or {}

        by_hook: dict[str, list[PredictionError]] = defaultdict(list)
        for cid, error in errors.items():
            pred = predictions.get(cid)
            if pred is None:
                continue
            hook = pred.dna_features.get("hook_type", "unknown")
            by_hook[hook].append(error)

        return dict(by_hook)

    @property
    def errors(self) -> dict[str, PredictionError]:
        return self._errors