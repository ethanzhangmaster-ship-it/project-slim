"""E9.7: Export Module — Handles all 5 output files for the learning engine.

Exports:
  1. prediction_history.json    — frozen prediction snapshots
  2. actual_performance.json    — real campaign performance data
  3. prediction_error_report.json — error analysis
  4. dna_weight_config.json     — learned DNA feature weights
  5. learning_report.json       — summary of what the system learned
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_ops.creative_learning.schemas import (
    PredictionRecord, CreativeActualPerformance, PredictionError,
    DNAWeightConfig, LearningReport,
)
from market_ops.creative_learning.prediction_tracker import PredictionTracker
from market_ops.creative_learning.prediction_error_analyzer import PredictionErrorAnalyzer
from market_ops.creative_learning.dna_weight_optimizer import DNAWeightOptimizer


class LearningExporter:
    """Standalone export module for all E9.7 output files.

    Usage:
        exporter = LearningExporter(output_dir="output/creative_learning")
        exporter.export_all(
            tracker, performances, errors, weight_config, learning_report,
        )
    """

    def __init__(self, output_dir: str | Path = "output/creative_learning") -> None:
        self._output_dir = Path(output_dir)

    # ── Directory Management ───────────────────────────────

    def ensure_output_dir(self) -> Path:
        """Create output directory if it doesn't exist."""
        self._output_dir.mkdir(parents=True, exist_ok=True)
        return self._output_dir

    # ── File 1: prediction_history.json ────────────────────

    def export_prediction_history(
        self,
        tracker: PredictionTracker,
        filename: str = "prediction_history.json",
    ) -> Path:
        """Export frozen prediction snapshots."""
        path = self._output_dir / filename
        self.ensure_output_dir()
        tracker.save_history(path)
        return path

    # ── File 2: actual_performance.json ────────────────────

    def export_actual_performance(
        self,
        performances: dict[str, CreativeActualPerformance],
        filename: str = "actual_performance.json",
    ) -> Path:
        """Export real campaign performance data."""
        path = self._output_dir / filename
        self.ensure_output_dir()

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(
                [p.to_dict() for p in performances.values()],
                f, ensure_ascii=False, indent=2,
            )
        return path

    # ── File 3: prediction_error_report.json ───────────────

    def export_error_report(
        self,
        errors: dict[str, PredictionError],
        analyzer: PredictionErrorAnalyzer | None = None,
        filename: str = "prediction_error_report.json",
    ) -> Path:
        """Export prediction error analysis report."""
        path = self._output_dir / filename
        self.ensure_output_dir()

        a = analyzer or PredictionErrorAnalyzer()
        report = a.get_error_report(errors)

        with open(path, 'w', encoding='utf-8') as f:
            json.dump({
                "export_time": datetime.now(timezone.utc).isoformat(),
                "summary": report,
                "errors": {
                    cid: e.to_dict() for cid, e in errors.items()
                },
            }, f, ensure_ascii=False, indent=2)
        return path

    # ── File 4: dna_weight_config.json ─────────────────────

    def export_weight_config(
        self,
        weight_config: DNAWeightConfig,
        optimizer: DNAWeightOptimizer | None = None,
        filename: str = "dna_weight_config.json",
    ) -> Path:
        """Export learned DNA feature weight configuration."""
        path = self._output_dir / filename
        self.ensure_output_dir()

        if optimizer:
            optimizer.save_weights(str(path))
        else:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(
                    weight_config.to_dict(),
                    f, ensure_ascii=False, indent=2,
                )
        return path

    # ── File 5: learning_report.json ───────────────────────

    def export_learning_report(
        self,
        learning_report: LearningReport,
        filename: str = "learning_report.json",
    ) -> Path:
        """Export learning summary report."""
        path = self._output_dir / filename
        self.ensure_output_dir()

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(
                learning_report.to_dict(),
                f, ensure_ascii=False, indent=2,
            )
        return path

    # ── Batch Export ───────────────────────────────────────

    def export_all(
        self,
        tracker: PredictionTracker,
        performances: dict[str, CreativeActualPerformance],
        errors: dict[str, PredictionError],
        weight_config: DNAWeightConfig | None = None,
        learning_report: LearningReport | None = None,
        analyzer: PredictionErrorAnalyzer | None = None,
        optimizer: DNAWeightOptimizer | None = None,
    ) -> dict[str, str]:
        """Export all 5 output files in one call.

        Returns:
            {file_category: full_path}
        """
        paths: dict[str, str] = {}

        # 1. prediction_history.json
        paths["prediction_history"] = str(
            self.export_prediction_history(tracker)
        )

        # 2. actual_performance.json
        paths["actual_performance"] = str(
            self.export_actual_performance(performances)
        )

        # 3. prediction_error_report.json
        paths["prediction_error_report"] = str(
            self.export_error_report(errors, analyzer)
        )

        # 4. dna_weight_config.json
        if weight_config:
            paths["dna_weight_config"] = str(
                self.export_weight_config(weight_config, optimizer)
            )

        # 5. learning_report.json
        if learning_report:
            paths["learning_report"] = str(
                self.export_learning_report(learning_report)
            )

        return paths

    # ── Summary ────────────────────────────────────────────

    def get_export_summary(
        self,
        paths: dict[str, str],
    ) -> dict[str, Any]:
        """Get summary of exported files with sizes."""
        summary = {}
        for category, path_str in paths.items():
            p = Path(path_str)
            if p.exists():
                summary[category] = {
                    "path": path_str,
                    "size_bytes": p.stat().st_size,
                    "size_kb": round(p.stat().st_size / 1024, 1),
                }
            else:
                summary[category] = {
                    "path": path_str,
                    "status": "missing",
                }
        return summary