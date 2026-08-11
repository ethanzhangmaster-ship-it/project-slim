"""E9.7: Learning Engine — Orchestrates the prediction→feedback→learning loop.

Full pipeline:
  1. Load E9.6 predictions → PredictionTracker
  2. Generate mock "actual" performance → MockPerformanceGenerator
  3. Reconstruct actual archetypes → ArchetypeReconstructionEngine
  4. Compare predicted vs actual → PredictionErrorAnalyzer
  5. Learn DNA weight adjustments → DNAWeightOptimizer
  6. Re-predict with new weights → measure improvement
  7. Export all 5 output files → LearningExporter

Outputs:
  - prediction_history.json
  - actual_performance.json
  - prediction_error_report.json
  - dna_weight_config.json
  - learning_report.json
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
from market_ops.creative_learning.performance_collector import (
    PerformanceCollector, MockPerformanceGenerator,
)
from market_ops.creative_learning.prediction_error_analyzer import PredictionErrorAnalyzer
from market_ops.creative_learning.dna_weight_optimizer import DNAWeightOptimizer
from market_ops.creative_learning.archetype_reconstruction import ArchetypeReconstructionEngine
from market_ops.creative_learning.export import LearningExporter


class LearningEngine:
    """Orchestrates the full feedback learning loop.

    Usage:
        engine = LearningEngine()
        report = engine.run()
        # or step by step:
        engine.load_predictions()
        engine.generate_mock_performance()
        engine.reconstruct_archetypes()
        engine.calculate_errors()
        engine.optimize_weights()
        engine.re_predict()
        engine.export_all()
    """

    def __init__(self) -> None:
        # Components
        self._tracker = PredictionTracker()
        self._collector = PerformanceCollector()
        self._mock_generator = MockPerformanceGenerator(seed=42)
        self._reconstructor = ArchetypeReconstructionEngine()
        self._analyzer = PredictionErrorAnalyzer()
        self._optimizer = DNAWeightOptimizer()
        self._exporter = LearningExporter()

        # Data
        self._predictions_raw: list[dict[str, Any]] = []
        self._prediction_records: dict[str, PredictionRecord] = {}
        self._actual_performances: dict[str, CreativeActualPerformance] = {}
        self._reconstructed_archetypes: dict[str, dict[str, float]] = {}
        self._errors: dict[str, PredictionError] = {}
        self._weight_config: DNAWeightConfig | None = None
        self._re_predictions: dict[str, dict[str, Any]] = {}
        self._learning_report: LearningReport | None = None

        # Paths
        self._prediction_path = Path("output/creative_matching/creative_prediction.json")
        self._output_dir = Path("output/creative_learning")
        self._dna_master_path = Path("output/active/creative_dna_master.json")

    # ── Step 1: Load Predictions ───────────────────────────

    def load_predictions(self, path: str | Path | None = None) -> int:
        """Load E9.6 predictions into tracker."""
        p = Path(path) if path else self._prediction_path
        n = self._tracker.load_predictions(p)

        # Also keep raw predictions for re-prediction
        if p.exists():
            with open(p, 'r', encoding='utf-8') as f:
                self._predictions_raw = json.load(f)

        self._prediction_records = {
            r.creative_id: r for r in self._tracker.records
        }
        return n

    # ── Step 2: Generate Mock Performance ──────────────────

    def generate_mock_performance(self, seed: int = 42) -> int:
        """Generate mock 'actual' campaign performance with systematic biases."""
        if not self._predictions_raw:
            return 0

        self._mock_generator = MockPerformanceGenerator(seed=seed)
        performances = self._mock_generator.generate(self._predictions_raw)

        for perf in performances:
            self._collector.add_performance(perf)
            self._actual_performances[perf.creative_id] = perf

        return len(performances)

    def load_real_performance(
        self, path: str | Path, source: str = "csv",
    ) -> int:
        """Load real campaign performance data."""
        p = Path(path)
        if source == "csv":
            return self._collector.load_from_csv(p)
        elif source == "json":
            return self._collector.load_from_json(p)
        return 0

    # ── Step 3: Reconstruct Archetypes ──────────────────────

    def reconstruct_archetypes(self) -> dict[str, dict[str, float]]:
        """Reconstruct actual archetype distributions from real player data.

        In mock mode: extracts pre-computed distributions from performances.
        In real mode: re-runs the full E9.5 pipeline on player events.

        Returns:
            {creative_id: {archetype: proportion}}
        """
        # Use mock mode: extract from pre-computed performances
        self._reconstructed_archetypes = (
            self._reconstructor.reconstruct_from_performances(
                self._actual_performances,
            )
        )

        # Also update performances with reconstructed distributions
        for cid, dist in self._reconstructed_archetypes.items():
            if cid in self._actual_performances:
                self._actual_performances[cid].archetype_distribution = dist

        return self._reconstructed_archetypes

    # ── Step 4: Calculate Errors ───────────────────────────

    def calculate_errors(self) -> dict[str, PredictionError]:
        """Compare predictions with actual performance."""
        self._errors = self._analyzer.compare(
            self._prediction_records,
            self._actual_performances,
        )
        return self._errors

    # ── Step 4: Optimize Weights ───────────────────────────

    def optimize_weights(self) -> DNAWeightConfig:
        """Learn optimal DNA feature weights from errors."""
        self._weight_config = self._optimizer.optimize(
            self._errors,
            self._prediction_records,
            self._actual_performances,
        )
        return self._weight_config

    # ── Step 5: Re-Predict with New Weights ─────────────────

    def re_predict(self) -> dict[str, dict[str, Any]]:
        """Re-run predictions with learned weights and measure improvement."""
        if not self._weight_config or not self._predictions_raw:
            return {}

        from market_ops.creative_matching.dna_feature_encoder import DNAFeatureEncoder
        from market_ops.creative_matching.creative_archetype_profile import CreativeArchetypeProfileDB
        from market_ops.creative_matching.archetype_predictor import ArchetypePredictor

        # Load DNA master
        dna_map = {}
        if self._dna_master_path.exists():
            with open(self._dna_master_path, 'r', encoding='utf-8') as f:
                dna_data = json.load(f)
            for item in dna_data:
                dna_map[item.get("creative_id", "")] = item

        # Re-encode and re-predict with new weights
        encoder = DNAFeatureEncoder()
        profile_db = CreativeArchetypeProfileDB()
        profile_db.load()

        predictor = ArchetypePredictor(profile_db)
        predictor.set_weights(self._weight_config.weights)

        self._re_predictions = {}
        for pred in self._predictions_raw:
            cid = pred.get("creative_id", "")
            dna = dna_map.get(cid, {})
            if not dna:
                continue

            fv = encoder.encode(dna)
            new_pred = predictor.predict(fv)
            self._re_predictions[cid] = new_pred.to_dict()

        return self._re_predictions

    # ── Step 6: Build Learning Report ──────────────────────

    def build_learning_report(self) -> LearningReport:
        """Build comprehensive learning report."""
        before_errors = self._analyzer.get_error_report(self._errors)

        # Compute "after" errors by comparing re-predictions with actuals
        after_ltv_errors: list[float] = []
        after_arch_mae: list[float] = []

        for cid, new_pred in self._re_predictions.items():
            actual = self._actual_performances.get(cid)
            if actual is None:
                continue

            # LTV error after
            new_ltv = new_pred.get("expected", {}).get("ltv", 0)
            after_ltv_errors.append(abs(new_ltv - actual.ltv_d30))

            # Archetype MAE after
            new_arch = {
                arch: detail.get("adjusted_probability", 0)
                for arch, detail in new_pred.get("prediction", {}).items()
            }
            arch_errors = []
            for arch in set(list(new_arch.keys()) + list(actual.archetype_distribution.keys())):
                arch_errors.append(abs(
                    new_arch.get(arch, 0) - actual.archetype_distribution.get(arch, 0)
                ))
            if arch_errors:
                after_arch_mae.append(sum(arch_errors) / len(arch_errors))

        avg_ltv_error_before = before_errors.get("avg_ltv_error", 0)
        avg_ltv_error_after = (
            sum(after_ltv_errors) / len(after_ltv_errors)
            if after_ltv_errors else avg_ltv_error_before
        )
        avg_arch_mae_before = before_errors.get("avg_archetype_mae", 0)
        avg_arch_mae_after = (
            sum(after_arch_mae) / len(after_arch_mae)
            if after_arch_mae else avg_arch_mae_before
        )

        # Improvement percentages
        ltv_improvement = (
            (avg_ltv_error_before - avg_ltv_error_after) / max(avg_ltv_error_before, 0.01) * 100
        )
        arch_improvement = (
            (avg_arch_mae_before - avg_arch_mae_after) / max(avg_arch_mae_before, 0.01) * 100
        )

        # Top learnings
        top_learnings = []
        for update in self._optimizer.updates[:10]:
            top_learnings.append({
                "feature": update.feature,
                "archetype": update.archetype,
                "weight_change": update.delta,
                "reason": update.reason,
            })

        # Archetype-level learnings
        archetype_learnings = {}
        for arch in ["power", "collector", "explorer", "progression"]:
            updates_for_arch = [
                u for u in self._optimizer.updates
                if u.archetype == arch
            ]
            if updates_for_arch:
                archetype_learnings[arch] = {
                    "total_updates": len(updates_for_arch),
                    "top_features": [
                        {"feature": u.feature, "delta": u.delta}
                        for u in updates_for_arch[:3]
                    ],
                }

        self._learning_report = LearningReport(
            report_time=datetime.now(timezone.utc).isoformat(),
            total_creatives=len(self._prediction_records),
            total_creatives_with_feedback=len(self._actual_performances),
            avg_ltv_error_before=round(avg_ltv_error_before, 2),
            avg_ltv_error_after=round(avg_ltv_error_after, 2),
            ltv_error_improvement=round(ltv_improvement, 1),
            avg_archetype_mae_before=round(avg_arch_mae_before, 3),
            avg_archetype_mae_after=round(avg_arch_mae_after, 3),
            archetype_mae_improvement=round(arch_improvement, 1),
            total_weight_updates=self._optimizer.total_updates,
            top_learnings=top_learnings,
            archetype_learnings=archetype_learnings,
        )
        return self._learning_report

    # ── Export ─────────────────────────────────────────────

    def export_all(self) -> dict[str, str]:
        """Export all 5 output files via LearningExporter."""
        self._exporter._output_dir = self._output_dir
        return self._exporter.export_all(
            tracker=self._tracker,
            performances=self._actual_performances,
            errors=self._errors,
            weight_config=self._weight_config,
            learning_report=self._learning_report,
            analyzer=self._analyzer,
            optimizer=self._optimizer,
        )

    # ── Full Pipeline ──────────────────────────────────────

    def run(self) -> dict[str, Any]:
        """Run the complete feedback learning loop.

        Returns: full pipeline report.
        """
        # Step 1: Load predictions
        n_pred = self.load_predictions()
        if n_pred == 0:
            return {"status": "error", "message": "No predictions loaded"}

        # Step 2: Generate mock performance
        n_perf = self.generate_mock_performance()

        # Step 3: Reconstruct actual archetypes
        n_arch = self.reconstruct_archetypes()

        # Step 4: Calculate errors
        self.calculate_errors()

        # Step 5: Optimize weights
        self.optimize_weights()

        # Step 6: Re-predict with new weights
        self.re_predict()

        # Step 7: Build learning report
        self.build_learning_report()

        # Step 8: Export
        export_paths = self.export_all()

        return {
            "summary": self._learning_report.to_dict() if self._learning_report else {},
            "export_paths": export_paths,
            "data_loaded": {
                "predictions": n_pred,
                "actual_performances": n_perf,
                "reconstructed_archetypes": n_arch,
                "errors_computed": len(self._errors),
                "weight_updates": self._optimizer.total_updates,
            },
        }


# ═══════════════════════════════════════════════════════════
# Convenience function
# ═══════════════════════════════════════════════════════════

def run_e97_pipeline(
    prediction_path: str | Path | None = None,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Run the complete E9.7 feedback learning pipeline."""
    engine = LearningEngine()

    if prediction_path:
        engine._prediction_path = Path(prediction_path)
    if output_dir:
        engine._output_dir = Path(output_dir)

    return engine.run()