"""V4.2 Offline Evaluator — compare predictions against reality.

Computes:
  - Accuracy, Balanced Accuracy, Precision, Recall, F1 (macro + weighted)
  - ROC-AUC, PR-AUC
  - Per-class metrics
  - Top failure/success cases

Usage:
    evaluator = OfflineEvaluator()
    metrics = evaluator.evaluate(records)
"""

from __future__ import annotations

import math
from typing import Any

from .schemas import ReplayRecord, EvaluationMetrics


class OfflineEvaluator:
    """Compare Reasoning Engine predictions against ground truth."""

    DECISION_CLASSES = ["GO", "TEST", "EXPLORE", "ADAPT", "AVOID"]

    def evaluate(self, records: list[ReplayRecord]) -> EvaluationMetrics:
        """Compute all evaluation metrics.

        Args:
            records: Replay records with predicted and actual decisions.

        Returns:
            EvaluationMetrics with all computed scores.
        """
        if not records:
            return EvaluationMetrics(total_samples=0)

        total = len(records)
        correct = sum(1 for r in records if r.is_correct)

        # Per-class metrics
        per_class = self._compute_per_class(records)

        # Weighted metrics
        class_counts = self._count_classes(records)
        weighted = self._compute_weighted(per_class, class_counts)

        # Macro metrics
        precisions = [per_class.get(c, {}).get("precision", 0) for c in self.DECISION_CLASSES]
        recalls = [per_class.get(c, {}).get("recall", 0) for c in self.DECISION_CLASSES]
        f1s = [per_class.get(c, {}).get("f1", 0) for c in self.DECISION_CLASSES]

        valid_prec = [p for p in precisions if p > 0]
        valid_rec = [r for r in recalls if r > 0]
        valid_f1 = [f for f in f1s if f > 0]

        precision_macro = sum(valid_prec) / len(valid_prec) if valid_prec else 0
        recall_macro = sum(valid_rec) / len(valid_rec) if valid_rec else 0
        f1_macro = sum(valid_f1) / len(valid_f1) if valid_f1 else 0

        # ROC-AUC and PR-AUC (simplified for multi-class)
        roc_auc = self._compute_roc_auc(records)
        pr_auc = self._compute_pr_auc(records)

        return EvaluationMetrics(
            accuracy=correct / total if total > 0 else 0,
            balanced_accuracy=recall_macro,
            precision_macro=precision_macro,
            recall_macro=recall_macro,
            f1_macro=f1_macro,
            precision_weighted=weighted.get("precision", 0),
            recall_weighted=weighted.get("recall", 0),
            f1_weighted=weighted.get("f1", 0),
            roc_auc=roc_auc,
            pr_auc=pr_auc,
            per_class=per_class,
            total_samples=total,
            correct_samples=correct,
        )

    def get_top_failures(self, records: list[ReplayRecord],
                         top_k: int = 10) -> list[dict[str, Any]]:
        """Get top failure cases — highest confidence wrong predictions."""
        failures = [r for r in records if not r.is_correct]
        failures.sort(key=lambda r: r.confidence, reverse=True)
        return [r.to_dict() for r in failures[:top_k]]

    def get_top_successes(self, records: list[ReplayRecord],
                          top_k: int = 10) -> list[dict[str, Any]]:
        """Get top success cases — highest confidence correct predictions."""
        successes = [r for r in records if r.is_correct]
        successes.sort(key=lambda r: r.confidence, reverse=True)
        return [r.to_dict() for r in successes[:top_k]]

    def error_analysis(self, records: list[ReplayRecord]) -> str:
        """Generate error analysis text."""
        failures = [r for r in records if not r.is_correct]
        if not failures:
            return "No errors found."

        # Group by predicted → actual
        error_groups: dict[str, int] = {}
        for r in failures:
            key = f"{r.predicted_decision}→{r.actual_decision}"
            error_groups[key] = error_groups.get(key, 0) + 1

        lines = [f"Error Analysis ({len(failures)} errors):", ""]
        for key, count in sorted(error_groups.items(), key=lambda x: -x[1]):
            lines.append(f"  {key}: {count} ({count/len(failures)*100:.0f}%)")

        # Most confused pairs
        lines.append("")
        lines.append("Top confusion pairs:")
        sorted_errors = sorted(error_groups.items(), key=lambda x: -x[1])[:5]
        for key, count in sorted_errors:
            pred, actual = key.split("→")
            lines.append(f"  Predicted {pred} but actual was {actual}: {count} times")

        return "\n".join(lines)

    # ── Private helpers ──

    def _compute_per_class(self, records: list[ReplayRecord]) -> dict[str, dict[str, float]]:
        """Compute per-class precision, recall, f1."""
        per_class: dict[str, dict[str, float]] = {}

        for cls in self.DECISION_CLASSES:
            tp = sum(1 for r in records
                     if r.predicted_decision == cls and r.actual_decision == cls)
            fp = sum(1 for r in records
                     if r.predicted_decision == cls and r.actual_decision != cls)
            fn = sum(1 for r in records
                     if r.predicted_decision != cls and r.actual_decision == cls)

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

            per_class[cls] = {
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1": round(f1, 4),
                "tp": tp, "fp": fp, "fn": fn,
            }

        return per_class

    def _count_classes(self, records: list[ReplayRecord]) -> dict[str, int]:
        """Count actual class occurrences."""
        counts: dict[str, int] = {}
        for r in records:
            counts[r.actual_decision] = counts.get(r.actual_decision, 0) + 1
        return counts

    def _compute_weighted(self, per_class: dict[str, dict[str, float]],
                          class_counts: dict[str, int]) -> dict[str, float]:
        """Compute weighted average metrics."""
        total = sum(class_counts.values())
        if total == 0:
            return {"precision": 0, "recall": 0, "f1": 0}

        precision_w = 0
        recall_w = 0
        f1_w = 0

        for cls, count in class_counts.items():
            weight = count / total
            precision_w += per_class.get(cls, {}).get("precision", 0) * weight
            recall_w += per_class.get(cls, {}).get("recall", 0) * weight
            f1_w += per_class.get(cls, {}).get("f1", 0) * weight

        return {
            "precision": round(precision_w, 4),
            "recall": round(recall_w, 4),
            "f1": round(f1_w, 4),
        }

    def _compute_roc_auc(self, records: list[ReplayRecord]) -> float:
        """Compute simplified multi-class ROC-AUC."""
        # Simplified: average of per-class binary AUC
        per_class = self._compute_per_class(records)
        aucs = []
        for cls in self.DECISION_CLASSES:
            tp = per_class.get(cls, {}).get("tp", 0)
            fp = per_class.get(cls, {}).get("fp", 0)
            fn = per_class.get(cls, {}).get("fn", 0)
            total_actual = tp + fn
            total_negative = len(records) - total_actual
            tpr = tp / total_actual if total_actual > 0 else 0
            fpr = fp / total_negative if total_negative > 0 else 0
            aucs.append((tpr + (1 - fpr)) / 2)
        return sum(aucs) / len(aucs) if aucs else 0

    def _compute_pr_auc(self, records: list[ReplayRecord]) -> float:
        """Compute simplified PR-AUC."""
        per_class = self._compute_per_class(records)
        aucs = []
        for cls in self.DECISION_CLASSES:
            precision = per_class.get(cls, {}).get("precision", 0)
            recall = per_class.get(cls, {}).get("recall", 0)
            aucs.append((precision + recall) / 2)
        return sum(aucs) / len(aucs) if aucs else 0