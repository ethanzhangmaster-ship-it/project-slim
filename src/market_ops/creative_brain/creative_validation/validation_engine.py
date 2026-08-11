"""V4.2 Validation Engine — unified validation pipeline.

Pipeline:
  Replay → Reasoning → Prediction → Evaluation → Calibration → Report

Usage:
    engine = ValidationEngine(reasoning_engine=engine)
    report = engine.run_full_validation(dataset_size=500)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .schemas import (
    ValidationReport, HistoricalCreative, ReplayRecord,
    SplitType, DriftType,
)
from .historical_replay import HistoricalReplay
from .offline_evaluator import OfflineEvaluator
from .prediction_metrics import PredictionMetricsCalculator
from .confusion_matrix import ConfusionMatrixCalculator
from .calibration import CalibrationEvaluator
from .decision_ab_test import DecisionABTest
from .drift_detector import DriftDetector
from .weight_optimizer import WeightOptimizer
from .report_generator import ReportGenerator
from .benchmark_dataset import BenchmarkDataset
from .error_analyzer import ErrorAnalyzer


class ValidationEngine:
    """Unified validation pipeline for the Creative Brain.

    Orchestrates: Replay → Evaluate → Calibrate → Report.

    Three core questions this answers:
      1. How accurate is the Reasoning Engine?
      2. Is it better than baseline rules?
      3. Can it learn and improve from real data?
    """

    def __init__(self, reasoning_engine=None, learning_loop=None) -> None:
        self._reasoning_engine = reasoning_engine
        self._learning_loop = learning_loop

        # Components
        self._replay = HistoricalReplay(engine=reasoning_engine)
        self._evaluator = OfflineEvaluator()
        self._prediction_metrics = PredictionMetricsCalculator()
        self._confusion = ConfusionMatrixCalculator()
        self._calibration = CalibrationEvaluator()
        self._ab_test = DecisionABTest()
        self._drift = DriftDetector()
        self._weight_optimizer = WeightOptimizer(evaluator=self._evaluator)
        self._report_generator = ReportGenerator()
        self._error_analyzer = ErrorAnalyzer()

    def run_full_validation(self, dataset_size: int = 500,
                            seed: int = 42) -> ValidationReport:
        """Run the complete validation pipeline.

        Args:
            dataset_size: Number of synthetic creatives to generate.
            seed: Random seed for reproducibility.

        Returns:
            ValidationReport with all metrics and analysis.
        """
        # 1. Generate benchmark dataset
        n_each = max(100, dataset_size // 5)
        dataset = BenchmarkDataset()
        dataset.generate(
            n_winners=n_each, n_losers=n_each,
            n_borderline=n_each // 2, n_new_trend=n_each // 2,
            n_dead_trend=n_each // 2, seed=seed,
        )

        # 2. Load into replay
        self._replay.load_dataset(dataset.all)

        # 3. Replay (test set only for evaluation)
        train_records = self._replay.replay_train()
        val_records = self._replay.replay_val()
        test_records = self._replay.replay_test()

        all_records = train_records + val_records + test_records

        # 4. Evaluate
        evaluation = self._evaluator.evaluate(test_records)
        prediction = self._prediction_metrics.compute(test_records)
        confusion = self._confusion.compute(test_records)

        # 5. Calibration
        calibration = self._calibration.evaluate(test_records)

        # 6. A/B Test
        ab_test = self._ab_test.compare(test_records, self._reasoning_engine)

        # 7. Drift detection
        train_data = [{"dna": c.dna, "performance": c.performance}
                      for c in dataset.train]
        test_data = [{"dna": c.dna, "performance": c.performance}
                     for c in dataset.test]
        drift_results = self._drift.detect(test_data, train_data)

        # 8. Weight optimization
        weight_opt = self._weight_optimizer.optimize(test_records)

        # 9. Error analysis
        error_analysis_text = self._evaluator.error_analysis(test_records)
        top_failures = self._evaluator.get_top_failures(test_records)
        top_successes = self._evaluator.get_top_successes(test_records)
        error_analysis = self._error_analyzer.analyze(test_records)

        # 10. Build summary
        summary = self._build_summary(evaluation, calibration, ab_test, error_analysis)

        return ValidationReport(
            timestamp=datetime.now().isoformat(),
            dataset_size=dataset.summary["total"],
            train_size=dataset.summary["train"],
            val_size=dataset.summary["val"],
            test_size=dataset.summary["test"],
            evaluation=evaluation,
            prediction=prediction,
            confusion=confusion,
            calibration=calibration,
            ab_test=ab_test,
            drift_results=drift_results,
            weight_optimization=weight_opt,
            top_failure_cases=top_failures,
            top_success_cases=top_successes,
            error_analysis_text=error_analysis_text,
            error_analysis=error_analysis,
            summary=summary,
        )

    def validate_custom(self, creatives: list[dict[str, Any]]) -> ValidationReport:
        """Validate with custom creative data.

        Args:
            creatives: List of dicts with creative data.

        Returns:
            ValidationReport.
        """
        dataset = BenchmarkDataset()
        dataset.load_custom(creatives)

        self._replay.load_dataset(dataset.all)
        test_records = self._replay.replay_test()

        evaluation = self._evaluator.evaluate(test_records)
        calibration = self._calibration.evaluate(test_records)
        ab_test = self._ab_test.compare(test_records, self._reasoning_engine)

        return ValidationReport(
            timestamp=datetime.now().isoformat(),
            dataset_size=len(creatives),
            test_size=len(test_records),
            evaluation=evaluation,
            calibration=calibration,
            ab_test=ab_test,
            summary="Custom dataset validation complete.",
        )

    def generate_report(self, report: ValidationReport,
                        format: str = "markdown") -> str:
        """Generate a formatted report."""
        return self._report_generator.generate(report, format=format)

    def save_report(self, report: ValidationReport,
                    filepath: str, format: str = "json") -> None:
        """Save report to file."""
        if format == "markdown":
            self._report_generator.save_markdown(report, filepath)
        elif format == "html":
            self._report_generator.save_html(report, filepath)
        else:
            self._report_generator.save_json(report, filepath)

    def _build_summary(self, evaluation, calibration,
                       ab_test, error_analysis=None) -> str:
        """Build a human-readable summary."""
        parts = [
            f"Creative Brain Validation Summary",
            f"",
            f"Accuracy: {evaluation.accuracy:.2%}",
            f"F1 (Macro): {evaluation.f1_macro:.2%}",
            f"ECE: {calibration.ece:.4f} ({'Calibrated' if calibration.is_calibrated else 'Not Calibrated'})",
        ]

        if error_analysis:
            parts.append(f"Error Rate: {error_analysis.error_rate:.2%}")
            if error_analysis.top_error_types:
                top = error_analysis.top_error_types[0]
                parts.append(f"Top Error: {top['type']} ({top['pct']:.0f}%)")

        if ab_test:
            improvement = ab_test.treatment_accuracy - ab_test.baseline_accuracy
            if improvement > 0:
                parts.append(
                    f"vs Rule Engine: {improvement:+.2%} "
                    f"({'Significant' if ab_test.is_significant else 'Not significant'})"
                )
            else:
                parts.append(f"vs Rule Engine: {improvement:+.2%} (no improvement)")

        return "\n".join(parts)

    # ── Accessors ──

    @property
    def replay(self) -> HistoricalReplay:
        return self._replay

    @property
    def evaluator(self) -> OfflineEvaluator:
        return self._evaluator