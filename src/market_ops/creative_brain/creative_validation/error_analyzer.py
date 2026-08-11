"""V4.2.1 Error Analyzer — root cause analysis for prediction failures.

Answers: "WHY was this prediction wrong?"

Classifies errors into 7 types:
  - RETRIEVER: Wrong/missing similar creatives
  - PATTERN: Pattern outdated or misclassified
  - TREND: Trend drift caused misprediction
  - GRAPH: Knowledge graph missing relationships
  - LEARNING: Learning loop not updated
  - CONSTRAINT: Constraint optimization failure
  - CONFIDENCE: Confidence score miscalibrated

Outputs:
  - Per-error diagnosis (root cause + suggested fix)
  - Error distribution (which module causes most errors)
  - Auto-recommendations (adjust weights, update patterns, etc.)

Usage:
    analyzer = ErrorAnalyzer()
    analysis = analyzer.analyze(records)
    # analysis.recommendations = ["降低Trend权重", "增加Retriever Recall", ...]
"""

from __future__ import annotations

import math
from typing import Any

from .schemas import (
    ReplayRecord, ErrorDiagnosis, ErrorAnalysis, ErrorType,
)


class ErrorAnalyzer:
    """Analyze WHY predictions failed and what to do about it.

    Every error gets:
      1. Root cause classification (which module failed)
      2. Detailed explanation
      3. Suggested fix
      4. Severity rating
    """

    # Thresholds for error classification
    CONFIDENCE_OVERCONFIDENT = 0.7   # Confidence > 0.7 but wrong → overconfidence
    CONFIDENCE_HIGH = 0.6
    ROAS_MEDIUM = 0.5

    def analyze(self, records: list[ReplayRecord]) -> ErrorAnalysis:
        """Analyze all prediction errors.

        Args:
            records: Replay records with predictions and ground truth.

        Returns:
            ErrorAnalysis with diagnoses, distribution, and recommendations.
        """
        if not records:
            return ErrorAnalysis()

        errors = [r for r in records if not r.is_correct]
        total = len(records)

        if not errors:
            return ErrorAnalysis(
                total_errors=0,
                total_predictions=total,
                error_rate=0.0,
                summary="No errors found. All predictions correct.",
            )

        # Diagnose each error
        diagnoses = [self.diagnose(e) for e in errors]

        # Compute distribution
        distribution: dict[str, int] = {}
        for d in diagnoses:
            et = d.error_type.value
            distribution[et] = distribution.get(et, 0) + 1

        distribution_pct = {
            k: round(v / len(errors), 4) * 100
            for k, v in distribution.items()
        }

        # Top error types
        top_error_types = sorted(
            [{"type": k, "count": v, "pct": distribution_pct.get(k, 0)}
             for k, v in distribution.items()],
            key=lambda x: -x["count"],
        )

        # Top failure creatives
        high_conf_errors = sorted(
            [d for d in diagnoses if d.confidence > self.CONFIDENCE_HIGH],
            key=lambda d: -d.confidence,
        )
        top_failures = [d.to_dict() for d in high_conf_errors[:10]]

        # Generate recommendations
        recommendations = self._generate_recommendations(
            distribution_pct, diagnoses
        )

        # Build summary
        summary = self._build_summary(distribution_pct, top_error_types, recommendations)

        return ErrorAnalysis(
            total_errors=len(errors),
            total_predictions=total,
            error_rate=len(errors) / total if total > 0 else 0,
            diagnoses=diagnoses,
            error_distribution=distribution,
            error_distribution_pct=distribution_pct,
            top_error_types=top_error_types,
            top_failure_creatives=top_failures,
            recommendations=recommendations,
            summary=summary,
        )

    def diagnose(self, record: ReplayRecord) -> ErrorDiagnosis:
        """Diagnose a single prediction error.

        Determines:
          - Which module caused the error
          - Why it happened
          - How to fix it
        """
        pred = record.predicted_decision
        actual = record.actual_decision
        confidence = record.confidence
        actual_roas = record.actual_roas
        predicted_roas = record.predicted_roas

        # Classify the error type
        error_type = self._classify_error(record)

        # Build root cause explanation
        root_cause = self._build_root_cause(error_type, pred, actual, confidence, actual_roas)
        root_cause_detail = self._build_detail(error_type, record)

        # Contributing modules
        contributing = self._contributing_modules(error_type)

        # Suggested fix
        suggested_fix = self._suggested_fix(error_type)

        # Severity
        severity = self._compute_severity(error_type, confidence, pred, actual)

        return ErrorDiagnosis(
            creative_id=record.creative_id,
            predicted_decision=pred,
            actual_decision=actual,
            confidence=confidence,
            error_type=error_type,
            root_cause=root_cause,
            root_cause_detail=root_cause_detail,
            contributing_modules=contributing,
            suggested_fix=suggested_fix,
            severity=severity,
        )

    # ── Error Classification ──

    def _classify_error(self, record: ReplayRecord) -> ErrorType:
        """Classify the root cause of a prediction error."""
        pred = record.predicted_decision
        actual = record.actual_decision
        confidence = record.confidence
        actual_roas = record.actual_roas
        predicted_roas = record.predicted_roas

        # Overconfidence: high confidence but wrong
        if confidence > self.CONFIDENCE_OVERCONFIDENT:
            return ErrorType.CONFIDENCE

        # ROAS prediction was way off → pattern error
        if abs(predicted_roas - actual_roas) > 0.3:
            return ErrorType.PATTERN

        # Predicted GO but actual AVOID → trend drift (pattern expired)
        if pred in ("GO", "TEST") and actual == "AVOID":
            return ErrorType.TREND

        # Predicted AVOID but actual GO → retriever missed winner
        if pred == "AVOID" and actual in ("GO", "TEST"):
            return ErrorType.RETRIEVER

        # Predicted EXPLORE but actual GO → learning not updated
        if pred == "EXPLORE" and actual == "GO":
            return ErrorType.LEARNING

        # Predicted different from actual with moderate confidence
        if confidence > 0.4:
            return ErrorType.CONSTRAINT

        # Default: pattern error
        return ErrorType.PATTERN

    def _build_root_cause(self, error_type: ErrorType,
                          pred: str, actual: str,
                          confidence: float, actual_roas: float) -> str:
        """Build human-readable root cause."""
        templates = {
            ErrorType.TREND: (
                f"Trend drift detected. Pattern was predicted {pred} but "
                f"actual performance ({actual_roas:.2f} ROAS) indicates {actual}. "
                f"The underlying pattern may have expired."
            ),
            ErrorType.RETRIEVER: (
                f"Retriever failed to find relevant winners. Predicted {pred} "
                f"but actual was {actual}. Missing similar creatives in retrieval."
            ),
            ErrorType.PATTERN: (
                f"Pattern misclassification. Predicted {pred} but actual {actual}. "
                f"Pattern database may be outdated or missing relevant combinations."
            ),
            ErrorType.CONFIDENCE: (
                f"Confidence overestimation. Confidence={confidence:.0%} but "
                f"prediction was wrong. Calibration needed."
            ),
            ErrorType.LEARNING: (
                f"Learning loop not updated. Predicted {pred} but actual {actual}. "
                f"Recent performance data not reflected in learning weights."
            ),
            ErrorType.CONSTRAINT: (
                f"Constraint optimization error. Predicted {pred} but actual {actual}. "
                f"Budget/country/platform constraints may need recalibration."
            ),
            ErrorType.GRAPH: (
                f"Knowledge graph missing relationship. Predicted {pred} but "
                f"actual {actual}. Relevant entity connections not in graph."
            ),
        }
        return templates.get(error_type, f"Unclassified error: {pred} → {actual}")

    def _build_detail(self, error_type: ErrorType,
                      record: ReplayRecord) -> str:
        """Build detailed technical explanation."""
        parts = [
            f"Creative: {record.creative_id}",
            f"Predicted: {record.predicted_decision} (conf={record.confidence:.0%})",
            f"Actual: {record.actual_decision} (ROAS={record.actual_roas:.2f})",
            f"Predicted ROAS: {record.predicted_roas:.2f}",
            f"ROAS Gap: {abs(record.predicted_roas - record.actual_roas):.2f}",
            f"Error Type: {error_type.value}",
        ]

        if error_type == ErrorType.CONFIDENCE:
            parts.append(
                f"Confidence gap: {record.confidence:.0%} vs actual correctness (0%)"
            )
        elif error_type == ErrorType.PATTERN:
            parts.append(
                f"Pattern ROAS mismatch: predicted {record.predicted_roas:.2f} "
                f"vs actual {record.actual_roas:.2f}"
            )
        elif error_type == ErrorType.TREND:
            parts.append(
                f"Decision inversion: {record.predicted_decision} → {record.actual_decision}"
            )

        return " | ".join(parts)

    def _contributing_modules(self, error_type: ErrorType) -> list[str]:
        """List modules that contributed to this error."""
        module_map = {
            ErrorType.RETRIEVER: ["Retriever", "VectorStore", "Embedding"],
            ErrorType.PATTERN: ["PatternMining", "PatternClassifier", "Reranker"],
            ErrorType.TREND: ["TrendReasoner", "DriftDetector", "LearningLoop"],
            ErrorType.GRAPH: ["KnowledgeGraph", "GraphReasoner"],
            ErrorType.LEARNING: ["LearningLoop", "WeightOptimizer", "OnlineFeedback"],
            ErrorType.CONSTRAINT: ["ConstraintOptimizer", "DecisionEngine"],
            ErrorType.CONFIDENCE: ["ConfidenceEngine", "Calibration"],
        }
        return module_map.get(error_type, ["Unknown"])

    def _suggested_fix(self, error_type: ErrorType) -> str:
        """Generate suggested fix for this error type."""
        fixes = {
            ErrorType.RETRIEVER: (
                "Increase retriever recall. Consider: (1) expand embedding model, "
                "(2) lower similarity threshold, (3) add keyword search fallback."
            ),
            ErrorType.PATTERN: (
                "Update pattern database. Consider: (1) re-mine patterns with recent data, "
                "(2) lower min_support threshold, (3) add temporal decay to old patterns."
            ),
            ErrorType.TREND: (
                "Reduce trend weight in evidence scoring. Consider: (1) shorten trend window "
                "from 30d to 7d, (2) add trend confidence threshold, (3) increase retriever weight."
            ),
            ErrorType.GRAPH: (
                "Expand knowledge graph. Consider: (1) add missing entity relationships, "
                "(2) increase graph traversal depth, (3) add cross-country relationship edges."
            ),
            ErrorType.LEARNING: (
                "Update learning loop. Consider: (1) increase learning rate, "
                "(2) add more recent training data, (3) reduce decay factor."
            ),
            ErrorType.CONSTRAINT: (
                "Recalibrate constraint optimizer. Consider: (1) adjust budget allocation, "
                "(2) relax explore/exploit ratio, (3) add country-specific constraint profiles."
            ),
            ErrorType.CONFIDENCE: (
                "Recalibrate confidence engine. Consider: (1) run calibration with ECE < 0.1, "
                "(2) add temperature scaling, (3) reduce overconfident source weights."
            ),
        }
        return fixes.get(error_type, "Review error and adjust relevant module parameters.")

    def _compute_severity(self, error_type: ErrorType,
                          confidence: float,
                          pred: str, actual: str) -> str:
        """Compute error severity."""
        # High confidence wrong = critical
        if confidence > 0.8:
            return "critical"
        # GO→AVOID or AVOID→GO = high severity
        if (pred == "GO" and actual == "AVOID") or (pred == "AVOID" and actual == "GO"):
            return "high"
        if confidence > 0.6:
            return "high"
        if error_type in (ErrorType.CONFIDENCE, ErrorType.TREND):
            return "medium"
        return "low"

    # ── Recommendations ──

    def _generate_recommendations(self, distribution_pct: dict[str, float],
                                  diagnoses: list[ErrorDiagnosis]) -> list[str]:
        """Generate actionable recommendations based on error distribution."""
        recommendations = []

        # Sort error types by frequency
        sorted_errors = sorted(distribution_pct.items(), key=lambda x: -x[1])

        for error_type_str, pct in sorted_errors:
            if pct >= 30:
                recommendations.append(
                    f"[HIGH PRIORITY] {error_type_str} errors dominate ({pct:.0f}%). "
                    f"Focus on fixing this module first."
                )
            elif pct >= 15:
                recommendations.append(
                    f"[MEDIUM PRIORITY] {error_type_str} errors significant ({pct:.0f}%). "
                    f"Consider adjusting related weights."
                )

        # Specific recommendations
        if distribution_pct.get("trend", 0) >= 20:
            recommendations.append(
                "Reduce Trend weight in evidence scoring (current: 15% → suggested: 8%). "
                "Trend drift is causing overreliance on stale patterns."
            )
        if distribution_pct.get("retriever", 0) >= 20:
            recommendations.append(
                "Increase Retriever Recall. Add keyword search fallback and "
                "lower similarity threshold to improve winner coverage."
            )
        if distribution_pct.get("confidence", 0) >= 15:
            recommendations.append(
                "Run calibration with ECE target < 0.10. Apply temperature scaling "
                "to reduce overconfidence in high-confidence predictions."
            )
        if distribution_pct.get("pattern", 0) >= 20:
            recommendations.append(
                "Update Pattern database. Re-mine patterns with recent 90-day data "
                "and add temporal decay to expire outdated patterns."
            )
        if distribution_pct.get("learning", 0) >= 15:
            recommendations.append(
                "Increase Learning Loop update frequency. Add daily feedback "
                "ingestion and reduce learning rate decay."
            )

        return recommendations

    def _build_summary(self, distribution_pct: dict[str, float],
                       top_error_types: list[dict[str, Any]],
                       recommendations: list[str]) -> str:
        """Build a human-readable summary."""
        if not top_error_types:
            return "No errors to analyze."

        lines = ["Error Analysis Summary:", ""]

        # Top error types
        lines.append("Top Error Types:")
        for item in top_error_types[:5]:
            lines.append(
                f"  {item['type']}: {item['count']} errors ({item['pct']:.0f}%)"
            )

        lines.append("")

        # Key recommendations
        if recommendations:
            lines.append("Key Recommendations:")
            for i, rec in enumerate(recommendations[:5]):
                lines.append(f"  {i+1}. {rec}")

        return "\n".join(lines)

    def get_error_type_summary(self, diagnoses: list[ErrorDiagnosis]) -> str:
        """Generate a per-error-type summary."""
        from collections import Counter
        counter = Counter(d.error_type for d in diagnoses)

        lines = []
        for error_type, count in counter.most_common():
            pct = count / len(diagnoses) * 100
            lines.append(
                f"{error_type.value}: {count} ({pct:.0f}%)"
            )
        return "\n".join(lines)