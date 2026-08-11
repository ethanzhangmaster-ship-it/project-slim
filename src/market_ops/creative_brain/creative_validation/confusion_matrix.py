"""V4.2 Confusion Matrix — 5x5 matrix for 5 decision types.

Classes: GO, TEST, EXPLORE, ADAPT, AVOID.

Outputs:
  - 5x5 confusion matrix
  - Per-class TP, FP, FN, TN
  - Summary statistics
"""

from __future__ import annotations

from typing import Any

from .schemas import ReplayRecord, ConfusionMatrix


class ConfusionMatrixCalculator:
    """Build and analyze 5x5 confusion matrix for creative decisions."""

    CLASSES = ["GO", "TEST", "EXPLORE", "ADAPT", "AVOID"]

    def compute(self, records: list[ReplayRecord]) -> ConfusionMatrix:
        """Build confusion matrix from replay records.

        Rows = predicted, Columns = actual.
        """
        class_to_idx = {c: i for i, c in enumerate(self.CLASSES)}

        # Initialize 5x5 matrix
        matrix = [[0] * 5 for _ in range(5)]

        for r in records:
            pred_idx = class_to_idx.get(r.predicted_decision, -1)
            actual_idx = class_to_idx.get(r.actual_decision, -1)
            if pred_idx >= 0 and actual_idx >= 0:
                matrix[pred_idx][actual_idx] += 1

        # Compute TP, FP, FN, TN per class
        tp = {}
        fp = {}
        fn = {}
        tn = {}

        for i, cls in enumerate(self.CLASSES):
            tp[cls] = matrix[i][i]
            fp[cls] = sum(matrix[i][j] for j in range(5) if j != i)
            fn[cls] = sum(matrix[k][i] for k in range(5) if k != i)
            tn[cls] = sum(matrix[k][j] for k in range(5) for j in range(5)
                         if k != i and j != i)

        return ConfusionMatrix(
            classes=list(self.CLASSES),
            matrix=matrix,
            tp=tp, fp=fp, fn=fn, tn=tn,
        )

    def summary(self, cm: ConfusionMatrix) -> str:
        """Generate a human-readable summary."""
        lines = ["Confusion Matrix (Predicted → Actual):", ""]

        # Header
        header = "         " + "  ".join(f"{c:>8}" for c in cm.classes)
        lines.append(header)
        lines.append("-" * len(header))

        # Rows
        for i, cls in enumerate(cm.classes):
            row = f"  {cls:>6}  " + "  ".join(f"{cm.matrix[i][j]:>8}" for j in range(5))
            lines.append(row)

        lines.append("")
        lines.append("Per-class metrics:")
        lines.append(f"  {'Class':>8}  {'TP':>6}  {'FP':>6}  {'FN':>6}  {'TN':>6}")
        lines.append("-" * 50)

        for cls in cm.classes:
            lines.append(
                f"  {cls:>8}  {cm.tp.get(cls, 0):>6}  "
                f"{cm.fp.get(cls, 0):>6}  {cm.fn.get(cls, 0):>6}  "
                f"{cm.tn.get(cls, 0):>6}"
            )

        # Accuracy from confusion matrix
        total = sum(sum(row) for row in cm.matrix)
        correct = sum(cm.matrix[i][i] for i in range(5))
        if total > 0:
            lines.append("")
            lines.append(f"  Overall Accuracy: {correct}/{total} = {correct/total:.2%}")

        return "\n".join(lines)

    def most_confused_pairs(self, cm: ConfusionMatrix,
                            top_k: int = 5) -> list[dict[str, Any]]:
        """Find the most confused prediction pairs."""
        pairs = []
        for i, pred_cls in enumerate(cm.classes):
            for j, actual_cls in enumerate(cm.classes):
                if i != j and cm.matrix[i][j] > 0:
                    pairs.append({
                        "predicted": pred_cls,
                        "actual": actual_cls,
                        "count": cm.matrix[i][j],
                    })

        pairs.sort(key=lambda p: -p["count"])
        return pairs[:top_k]