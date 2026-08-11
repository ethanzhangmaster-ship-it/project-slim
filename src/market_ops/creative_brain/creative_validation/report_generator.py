"""V4.2 Report Generator — generate validation reports.

Output formats: JSON, Markdown, HTML (PDF placeholder).

Usage:
    gen = ReportGenerator()
    report = gen.generate(validation_report)
    gen.save_json(report, "validation_report.json")
    gen.save_markdown(report, "validation_report.md")
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from .schemas import ValidationReport


class ReportGenerator:
    """Generate formatted validation reports."""

    def generate(self, report: ValidationReport,
                 format: str = "json") -> str:
        """Generate a report in the specified format.

        Args:
            report: ValidationReport to format.
            format: "json", "markdown", or "html".

        Returns:
            Formatted report string.
        """
        if format == "markdown":
            return self._to_markdown(report)
        elif format == "html":
            return self._to_html(report)
        else:
            return self._to_json(report)

    def save_json(self, report: ValidationReport,
                  filepath: str) -> None:
        """Save report as JSON."""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)

    def save_markdown(self, report: ValidationReport,
                      filepath: str) -> None:
        """Save report as Markdown."""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(self._to_markdown(report))

    def save_html(self, report: ValidationReport,
                  filepath: str) -> None:
        """Save report as HTML."""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(self._to_html(report))

    # ── Format-specific generators ──

    def _to_json(self, report: ValidationReport) -> str:
        """Generate JSON report."""
        return json.dumps(report.to_dict(), indent=2, ensure_ascii=False)

    def _to_markdown(self, report: ValidationReport) -> str:
        """Generate Markdown report."""
        lines = [
            f"# Creative Brain Validation Report",
            f"",
            f"**Generated:** {report.timestamp or datetime.now().isoformat()}",
            f"",
            f"---",
            f"",
            f"## Dataset",
            f"",
            f"| Split | Count |",
            f"|-------|-------|",
            f"| Train | {report.train_size} |",
            f"| Validation | {report.val_size} |",
            f"| Test | {report.test_size} |",
            f"| **Total** | **{report.dataset_size}** |",
            f"",
            f"---",
            f"",
            f"## Evaluation Metrics",
            f"",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Accuracy | {report.evaluation.accuracy:.2%} |",
            f"| Balanced Accuracy | {report.evaluation.balanced_accuracy:.2%} |",
            f"| Precision (Macro) | {report.evaluation.precision_macro:.2%} |",
            f"| Recall (Macro) | {report.evaluation.recall_macro:.2%} |",
            f"| F1 (Macro) | {report.evaluation.f1_macro:.2%} |",
            f"| ROC-AUC | {report.evaluation.roc_auc:.4f} |",
            f"| PR-AUC | {report.evaluation.pr_auc:.4f} |",
            f"",
            f"**Total Samples:** {report.evaluation.total_samples}",
            f"**Correct:** {report.evaluation.correct_samples}",
            f"",
            f"---",
            f"",
            f"## Prediction Metrics",
            f"",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Recall@5 | {report.prediction.recall_at_5:.4f} |",
            f"| Recall@10 | {report.prediction.recall_at_10:.4f} |",
            f"| Recall@20 | {report.prediction.recall_at_20:.4f} |",
            f"| MRR | {report.prediction.mrr:.4f} |",
            f"| MAP | {report.prediction.map_score:.4f} |",
            f"| NDCG@10 | {report.prediction.ndcg_at_10:.4f} |",
            f"| NDCG@20 | {report.prediction.ndcg_at_20:.4f} |",
            f"| Hit Rate | {report.prediction.hit_rate:.4f} |",
            f"| Coverage | {report.prediction.coverage:.4f} |",
            f"| Novelty | {report.prediction.novelty:.4f} |",
            f"| Diversity | {report.prediction.diversity:.4f} |",
            f"",
            f"---",
            f"",
            f"## Calibration",
            f"",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| ECE | {report.calibration.ece:.4f} (target: < 0.10) |",
            f"| MCE | {report.calibration.mce:.4f} |",
            f"| Brier Score | {report.calibration.brier_score:.4f} |",
            f"| Is Calibrated | {report.calibration.is_calibrated} |",
            f"",
        ]

        if report.ab_test:
            lines.extend([
                f"---",
                f"",
                f"## A/B Test",
                f"",
                f"| Metric | Baseline ({report.ab_test.baseline_name}) | Treatment ({report.ab_test.treatment_name}) | Improvement |",
                f"|--------|----------|------------|-------------|",
                f"| Accuracy | {report.ab_test.baseline_accuracy:.2%} | {report.ab_test.treatment_accuracy:.2%} | {report.ab_test.treatment_accuracy - report.ab_test.baseline_accuracy:+.2%} |",
                f"| Winner Recall | {report.ab_test.winner_recall_baseline:.2%} | {report.ab_test.winner_recall_treatment:.2%} | {report.ab_test.winner_recall_treatment - report.ab_test.winner_recall_baseline:+.2%} |",
                f"",
                f"Significant: {report.ab_test.is_significant} (p={report.ab_test.p_value:.4f})",
                f"",
            ])

        if report.weight_optimization:
            lines.extend([
                f"---",
                f"",
                f"## Weight Optimization",
                f"",
                f"Method: {report.weight_optimization.method.value}",
                f"",
                f"| Source | Initial | Optimized | Change |",
                f"|--------|---------|-----------|--------|",
            ])
            for key in report.weight_optimization.initial_weights:
                old = report.weight_optimization.initial_weights[key]
                new = report.weight_optimization.optimized_weights.get(key, old)
                lines.append(f"| {key} | {old:.0%} | {new:.0%} | {new - old:+.0%} |")

            lines.extend([
                f"",
                f"Accuracy: {report.weight_optimization.initial_score:.2%} → {report.weight_optimization.optimized_score:.2%} ({report.weight_optimization.improvement:+.4f})",
                f"",
            ])

        if report.drift_results:
            lines.extend([
                f"---",
                f"",
                f"## Drift Detection",
                f"",
                f"| Dimension | Value | Direction | Change | Confidence |",
                f"|-----------|-------|-----------|--------|------------|",
            ])
            for d in report.drift_results[:10]:
                lines.append(
                    f"| {d.affected_dimension} | {d.affected_value} | "
                    f"{d.direction} | {d.change_pct:+.0f}% | {d.confidence:.0%} |"
                )
            lines.append("")

        if report.top_failure_cases:
            lines.extend([
                f"---",
                f"",
                f"## Top Failure Cases",
                f"",
            ])
            for i, case in enumerate(report.top_failure_cases[:5]):
                lines.append(
                    f"  {i+1}. {case.get('creative_id', '')}: "
                    f"predicted={case.get('predicted_decision', '')} "
                    f"actual={case.get('actual_decision', '')} "
                    f"(conf={case.get('confidence', 0):.0%})"
                )
            lines.append("")

        if report.error_analysis:
            ea = report.error_analysis
            lines.extend([
                f"---",
                f"",
                f"## Error Analysis",
                f"",
                f"**Error Rate:** {ea.error_rate:.2%} ({ea.total_errors}/{ea.total_predictions})",
                f"",
                f"### Error Distribution",
                f"",
                f"| Error Type | Count | Percentage |",
                f"|------------|-------|------------|",
            ])
            for item in ea.top_error_types:
                lines.append(
                    f"| {item['type']} | {item['count']} | {item['pct']:.0f}% |"
                )
            lines.append("")

            if ea.recommendations:
                lines.extend([
                    f"### Recommendations",
                    f"",
                ])
                for i, rec in enumerate(ea.recommendations):
                    lines.append(f"  {i+1}. {rec}")
                lines.append("")

            if ea.top_failure_creatives:
                lines.extend([
                    f"### Top Failure Creatives",
                    f"",
                    f"| Creative ID | Predicted | Actual | Confidence | Error Type |",
                    f"|-------------|-----------|--------|------------|------------|",
                ])
                for fc in ea.top_failure_creatives[:10]:
                    lines.append(
                        f"| {fc.get('creative_id', '')} | "
                        f"{fc.get('predicted_decision', '')} | "
                        f"{fc.get('actual_decision', '')} | "
                        f"{fc.get('confidence', 0):.0%} | "
                        f"{fc.get('error_type', '')} |"
                    )
                lines.append("")

            if ea.summary:
                lines.extend([
                    f"### Summary",
                    f"",
                    ea.summary,
                    f"",
                ])

        if report.summary:
            lines.extend([
                f"---",
                f"",
                f"## Summary",
                f"",
                report.summary,
                f"",
            ])

        return "\n".join(lines)

    def _to_html(self, report: ValidationReport) -> str:
        """Generate HTML report."""
        md = self._to_markdown(report)
        # Simple HTML wrapper
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Creative Brain Validation Report</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       max-width: 900px; margin: 0 auto; padding: 20px; background: #f8f9fa; }}
h1 {{ color: #1a1a2e; }}
h2 {{ color: #16213e; border-bottom: 2px solid #e94560; padding-bottom: 5px; }}
table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
th {{ background: #16213e; color: white; }}
tr:nth-child(even) {{ background: #f2f2f2; }}
pre {{ background: #1a1a2e; color: #e94560; padding: 15px; border-radius: 5px; overflow-x: auto; }}
</style>
</head>
<body>
<pre>{md}</pre>
</body>
</html>"""