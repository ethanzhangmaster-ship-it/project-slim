"""Causal Feature Engine — 特征-转化因果映射系统（V3.6 统一入口）。

将 frame-level visual features 与 ROAS/CTR/CVR 建立数学关系，
输出可解释的特征影响因子排序 + 因果分析报告。

Usage:
    cfe = CausalFeatureEngine()
    cfe.build_training_data()
    cfe.train()
    report = cfe.get_report("roas")
    print(report["causal_explanation"]["why_high_performance"]["root_cause"])
"""
from __future__ import annotations
import json, sys
from pathlib import Path
from typing import Optional, List, Tuple
import numpy as np

from engine.feature_label_builder import build_dataset, load_dataset
from engine.performance_regressor import PerformanceRegressor, train_test_split
from engine.feature_importance_report import generate_causal_report, generate_markdown_report


class CausalFeatureEngine:
    """Visual Feature → Performance Causal Mapping Engine."""

    def __init__(self, output_dir: Optional[Path] = None):
        ROOT = Path(__file__).resolve().parent.parent
        self.output_dir = output_dir or (ROOT / "output" / "video_intelligence" / "p04" / "v3_6")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.dataset_path = self.output_dir / "dataset.jsonl"
        self.X: Optional[np.ndarray] = None
        self.y: Optional[np.ndarray] = None
        self.feature_names: List[str] = []
        self.video_ids: List[str] = []
        self.regressor = PerformanceRegressor()
        self._built = False
        self._trained = False

    def build_training_data(self, force_rebuild: bool = False):
        """Build dataset from cached frames + FB performance data."""
        if self.dataset_path.exists() and not force_rebuild:
            print("[build] Loading existing dataset...")
            self.X, self.y, self.feature_names, self.video_ids = load_dataset(self.dataset_path)
            if len(self.X) > 0:
                self._built = True
                print(f"[build] Loaded {len(self.X)} samples, {len(self.feature_names)} features")
                return

        print("[build] Building training data from Eagle frames + FB data...")
        samples = build_dataset(output_path=self.dataset_path)
        self.X, self.y, self.feature_names, self.video_ids = load_dataset(self.dataset_path)
        self._built = True
        print(f"[build] Built {len(self.X)} samples with {len(self.feature_names)} features")

    def train(self, test_ratio: float = 0.2):
        """Train regression models with train/test split."""
        if not self._built or len(self.X) == 0:
            print("[train] No data. Call build_training_data() first.")
            return

        print(f"[train] Training on {len(self.X)} samples, {len(self.feature_names)} features...")

        X_train, X_test, y_train, y_test = train_test_split(self.X, self.y, test_ratio)

        self.regressor.fit(X_train, y_train, self.feature_names)
        self._trained = True

        score = self.regressor.r2_scores.get("roas_linear", 0)
        print(f"[train] ROAS R² = {score:.4f}")
        print(self.regressor.export_report())

    def get_report(self, target: str = "roas") -> dict:
        """Get structured causal report for a target metric."""
        if not self._trained:
            return {"error": "Model not trained. Call train() first."}

        impact = self.regressor.get_impact_report(target)
        if "error" in impact:
            return impact

        top = impact.get("top_drivers", [])
        neg = impact.get("negative_drivers", [])
        r2 = impact.get("r2")

        report = generate_causal_report(
            target=target,
            top_drivers=top,
            negative_drivers=neg,
            r2=r2,
            n_samples=len(self.X) if self.X is not None else 0,
        )
        return report

    def get_all_reports(self) -> List[dict]:
        """Get reports for all targets."""
        return [
            self.get_report("roas"),
            self.get_report("ctr"),
            self.get_report("cvr"),
        ]

    def run_pipeline(self):
        """End-to-end pipeline: build → train → report → save."""
        print("=" * 60)
        print("🧠 V3.6 Causal Feature Engine — Full Pipeline")
        print("=" * 60)

        self.build_training_data()
        if len(self.X) == 0:
            print("[pipeline] No training data. Pipeline stopped.")
            return

        self.train()

        reports = self.get_all_reports()
        markdown = generate_markdown_report(reports)

        # Save outputs
        (self.output_dir / "causal_report.json").write_text(
            json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
        (self.output_dir / "causal_report.md").write_text(markdown, encoding="utf-8")

        self.regressor.export_report()
        (self.output_dir / "feature_importance.txt").write_text(
            self.regressor.export_report(), encoding="utf-8")

        print(f"\n[report] Saved causal reports to {self.output_dir}")
        print(f"  ├── causal_report.json")
        print(f"  ├── causal_report.md")
        print(f"  └── feature_importance.txt")

        # Print summary
        print(f"\n{'=' * 60}")
        print("📊 TOP ROAS DRIVERS:")
        for r in reports:
            if "causal_explanation" in r:
                why = r["causal_explanation"]["why_high_performance"]
                print(f"\n  🎯 {r['target']}")
                print(f"  Root: {why.get('root_cause','')[:100]}")
                for d in why.get("details", [])[:2]:
                    print(f"  {d[:100]}")
                print(f"  Action: {r['causal_explanation']['recommended_action'][:100]}")

        return reports


def main():
    """CLI entry point."""
    engine = CausalFeatureEngine()
    engine.run_pipeline()


if __name__ == "__main__":
    main()
