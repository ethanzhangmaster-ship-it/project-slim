"""Creative Optimizer — 创意结构优化器（V3.7 统一入口）。

从"这个视频为什么差"升级为"改哪里能让它变好"。

流程:
  1. 加载已训练的 PerformanceRegressor (V3.6)
  2. 对目标视频提取 25-dim 帧级特征
  3. structure_mutation_engine → 生成 14 个 mutation candidates
  4. counterfactual_simulator → 模拟每个改动后的 ΔROAS/ΔCTR/ΔCVR
  5. improvement_ranker → 排序输出 Top 优化建议
  6. 输出 VIDEO OPTIMIZATION REPORT

用法:
    from engine.creative_optimizer import CreativeOptimizer
    opt = CreativeOptimizer()
    opt.load_regressor(regressor)
    report = opt.optimize_video(video_features)
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, List, Optional
import numpy as np

from engine.structure_mutation_engine import generate_mutations, apply_mutation
from engine.counterfactual_simulator import CounterfactualSimulator
from engine.improvement_ranker import rank_improvements, summarize_improvements
from engine.feature_label_builder import load_dataset, _extract_eagle_features
from engine.performance_regressor import PerformanceRegressor


class CreativeOptimizer:
    """Creative structure optimizer — from explanation to ΔROAS optimization."""

    def __init__(self):
        self.regressor = None
        self.simulator = CounterfactualSimulator()
        self._loaded = False

    def load_regressor(self, regressor: PerformanceRegressor) -> None:
        """Load trained regressor from V3.6."""
        self.regressor = regressor
        self.simulator.load_model(regressor)
        self._loaded = True

    def load_from_regressor_path(self, path: Path) -> None:
        """Load regressor from pickled/saved file."""
        # In production, load from joblib/pickle
        # For now, must pass regressor directly
        raise NotImplementedError("Use load_regressor() directly")

    def optimize_video(self, video_features: Dict[str, float],
                       target: str = "roas",
                       max_improvements: int = 5) -> Dict:
        """Generate optimization report for a single video.

        Args:
            video_features: 25-dim feature dict
            target: "roas", "ctr", or "cvr"
            max_improvements: top N suggestions

        Returns:
            VIDEO OPTIMIZATION REPORT
        """
        if not self._loaded:
            return {"error": "No regressor loaded"}

        # ── 1. Current prediction ──
        X = self._features_to_vector(video_features)
        current_pred = float(self.regressor.predict(
            X.reshape(1, -1), target=target, method="linear"
        )[0])

        # ── 2. Generate mutations ──
        mutations = generate_mutations(video_features)

        # ── 3. Simulate counterfactuals ──
        results = self.simulator.simulate_all(video_features, mutations, target)

        # ── 4. Rank improvements ──
        ranked = rank_improvements(results, target, max_improvements)
        summary = summarize_improvements(ranked, current_pred)

        # ── 5. Build report ──
        report = self._build_report(summary, target)
        return report

    def optimize_eagle_video(self, eagle_name: str,
                             target: str = "roas",
                             max_improvements: int = 5) -> Dict:
        """Optimize an Eagle video by name (extracts features from cache)."""
        features = _extract_eagle_features(eagle_name)
        if features is None:
            return {"error": f"Cannot extract features for '{eagle_name}'"}

        return self.optimize_video(features, target, max_improvements)

    def optimize_all(self, feature_list: List[Dict[str, float]],
                     target: str = "roas",
                     max_improvements: int = 5) -> List[Dict]:
        """Generate optimization reports for multiple videos."""
        return [
            self.optimize_video(f, target, max_improvements)
            for f in feature_list
        ]

    # ═══════════════════════════════════════════════════════════
    # Report Generation
    # ═══════════════════════════════════════════════════════════

    def _build_report(self, summary: Dict, target: str) -> Dict:
        """Build standardized VIDEO OPTIMIZATION REPORT."""
        return {
            "type": "video_optimization_report",
            "target": target.upper(),
            "current_performance": {
                f"current_{target}": summary["current_roas"],
            },
            "predicted_optimized": {
                f"predicted_optimized_{target}": summary["predicted_optimized_roas"],
                f"total_{target}_uplift": summary["total_roas_uplift"],
            },
            "top_focus_dimension": summary["top_focus"],
            "n_improvements": summary["n_improvements"],
            "improvements": summary["improvements"],
        }

    def report_to_markdown(self, report: Dict) -> str:
        """Render optimization report as readable markdown."""
        if "error" in report:
            return f"# Optimization Report\n\n❌ Error: {report['error']}\n"

        lines = []
        target = report.get("target", "ROAS")
        cur = report.get("current_performance", {}).get(f"current_{target.lower()}", 0)
        opt = report.get("predicted_optimized", {}).get(f"predicted_optimized_{target.lower()}", 0)
        uplift = report.get("predicted_optimized", {}).get(f"total_{target.lower()}_uplift", 0)

        lines.append(f"# 🚀 Video Optimization Report")
        lines.append(f"")
        lines.append(f"## Current vs Optimized")
        lines.append(f"| Metric | Current | Optimized | Uplift |")
        lines.append(f"|--------|---------|-----------|--------|")
        lines.append(f"| **{target}** | {cur:.2f} | {opt:.2f} | **+{uplift:.2f}** |")
        lines.append(f"")
        lines.append(f"## 🔥 Top Improvements")
        lines.append(f"")

        for imp in report.get("improvements", []):
            rank = imp["rank"]
            delta = imp["delta"]
            delta_pct = imp["delta_pct"]
            lines.append(f"### {rank}. {imp['description']}")
            lines.append(f"")
            lines.append(f"- **Expected uplift**: +{delta:.4f} (+{delta_pct:.1f}%)")
            lines.append(f"- **Dimension**: {imp['dimension']} | **Time**: {imp['time_window']}")
            lines.append(f"- **Feature**: {imp['feature']}: {imp['current_value']:.3f} → {imp['new_value']:.3f}")
            lines.append(f"- **AE Instruction**: {imp['ae_instruction']}")
            lines.append(f"")

        lines.append(f"---")
        lines.append(f"*Generated by V3.7 Creative Growth Loop Engine*")
        return "\n".join(lines)

    # ═══════════════════════════════════════════════════════════
    # Internal
    # ═══════════════════════════════════════════════════════════

    def _features_to_vector(self, features: Dict[str, float]) -> np.ndarray:
        fnames = self.regressor.feature_names
        vec = np.zeros(len(fnames), dtype=np.float32)
        for i, name in enumerate(fnames):
            vec[i] = features.get(name, 0)
        return vec
