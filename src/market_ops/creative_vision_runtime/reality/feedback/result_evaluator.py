"""E12.4 Phase 2 — Result Evaluator。

实验闭环关键：比较原始创意 vs 突变创意，找出赢家。

输入:
  ExperimentRun（含 variants metrics）

输出:
  ExperimentEvaluation（winner, improvement_score, learning_signal）

评估指标:
  - CTR 对比
  - ROAS 对比
  - CVR 对比
  - CPI 对比
  - 综合 improvement_score
"""

from __future__ import annotations

from .models import (
    ExperimentEvaluation,
    ExperimentRun,
)


# ── Metric weights for improvement_score ───────────────────


METRIC_WEIGHTS: dict[str, float] = {
    "ctr": 0.25,
    "roas": 0.35,
    "cvr": 0.20,
    "cpi": 0.20,  # 负向指标（越低越好）
}

# 正向指标（越高越好）
HIGHER_IS_BETTER = {"ctr", "roas", "cvr"}

# 负向指标（越低越好）
LOWER_IS_BETTER = {"cpi", "cpa"}

# 指标显示名称
METRIC_DISPLAY_NAMES: dict[str, str] = {
    "ctr": "CTR",
    "roas": "ROAS",
    "cvr": "CVR",
    "cpi": "CPI",
    "cpa": "CPA",
    "spend": "Spend",
    "impressions": "Impressions",
}


class ResultEvaluator:
    """实验结果评估器。

    比较原始创意 vs 变体创意，找出赢家，生成学习信号。

    Usage:
        >>> evaluator = ResultEvaluator()
        >>> baseline = {"ctr": 0.021, "roas": 0.55}
        >>> variants = {
        ...     "v1": {"ctr": 0.028, "roas": 0.68},
        ...     "v2": {"ctr": 0.030, "roas": 0.72},
        ...     "v3": {"ctr": 0.019, "roas": 0.50},
        ... }
        >>> evaluation = evaluator.evaluate(
        ...     experiment, baseline, variants
        ... )
        >>> print(evaluation.winner_id, evaluation.improvement_score)
    """

    # ── Main API ───────────────────────────────────────────

    def evaluate(
        self,
        experiment: ExperimentRun,
        baseline_metrics: dict[str, float],
        variant_metrics: dict[str, dict[str, float]],
    ) -> ExperimentEvaluation:
        """评估实验结果。

        Args:
            experiment:       实验运行记录
            baseline_metrics: 原始创意指标（如 {"ctr": 0.021, "roas": 0.55}）
            variant_metrics:  变体指标映射（如 {"v1": {"ctr": 0.028, ...}, ...}）

        Returns:
            ExperimentEvaluation
        """
        if not variant_metrics:
            return ExperimentEvaluation(
                experiment_id=experiment.experiment_id,
                creative_id=experiment.creative_id,
                winner_id="",
                improvement_score=0.0,
                metrics_delta={},
                raw_metrics={"baseline": baseline_metrics},
                learning_signal="No variants to evaluate",
                confidence=0.0,
            )

        # 1. 计算每个变体的 improvement_score
        variant_scores: dict[str, float] = {}
        variant_deltas: dict[str, dict[str, float]] = {}

        for variant_id, metrics in variant_metrics.items():
            score, deltas = self._compute_improvement(
                baseline_metrics, metrics
            )
            variant_scores[variant_id] = score
            variant_deltas[variant_id] = deltas

        # 2. 找出 winner
        if not variant_scores:
            winner_id = ""
            best_score = 0.0
        else:
            winner_id = max(variant_scores, key=lambda k: variant_scores[k])
            best_score = variant_scores[winner_id]

        # 3. 计算置信度
        confidence = self._compute_confidence(
            len(variant_metrics),
            best_score,
            baseline_metrics,
        )

        # 4. 生成学习信号
        learning_signal = self._generate_learning_signal(
            winner_id,
            best_score,
            variant_deltas.get(winner_id, {}),
            baseline_metrics,
            variant_metrics.get(winner_id, {}),
        )

        return ExperimentEvaluation(
            experiment_id=experiment.experiment_id,
            creative_id=experiment.creative_id,
            winner_id=winner_id,
            improvement_score=best_score,
            metrics_delta=variant_deltas.get(winner_id, {}),
            raw_metrics={
                "baseline": baseline_metrics,
                **variant_metrics,
            },
            learning_signal=learning_signal,
            confidence=confidence,
        )

    def evaluate_from_experiment_metrics(
        self,
        experiment: ExperimentRun,
    ) -> ExperimentEvaluation:
        """从 ExperimentRun.metrics 中提取基线和新指标进行评估。

        期望 metrics 格式:
          {
            "baseline": {"ctr": 0.021, "roas": 0.55},
            "variants": {
              "v1": {"ctr": 0.028, "roas": 0.68},
              "v2": {"ctr": 0.030, "roas": 0.72},
            }
          }
        """
        baseline = experiment.metrics.get("baseline", {})
        variants = experiment.metrics.get("variants", {})
        return self.evaluate(experiment, baseline, variants)

    def evaluate_batch(
        self,
        experiments: list[ExperimentRun],
        baselines: list[dict[str, float]],
        variants_list: list[dict[str, dict[str, float]]],
    ) -> list[ExperimentEvaluation]:
        """批量评估。

        Args:
            experiments:   实验列表
            baselines:     基线指标列表（与 experiments 一一对应）
            variants_list: 变体指标列表（与 experiments 一一对应）

        Returns:
            ExperimentEvaluation 列表
        """
        results: list[ExperimentEvaluation] = []
        for exp, baseline, variants in zip(experiments, baselines, variants_list):
            results.append(self.evaluate(exp, baseline, variants))
        return results

    def find_winners(
        self,
        evaluations: list[ExperimentEvaluation],
    ) -> list[ExperimentEvaluation]:
        """筛选出有赢家的评估。"""
        return [e for e in evaluations if e.has_winner]

    def get_best_improvement(
        self,
        evaluations: list[ExperimentEvaluation],
    ) -> ExperimentEvaluation | None:
        """获取改善幅度最大的评估。"""
        if not evaluations:
            return None
        return max(evaluations, key=lambda e: e.improvement_score)

    # ── Private helpers ────────────────────────────────────

    @staticmethod
    def _compute_improvement(
        baseline: dict[str, float],
        variant: dict[str, float],
    ) -> tuple[float, dict[str, float]]:
        """计算综合改善幅度。

        Args:
            baseline: 原始指标
            variant:  变体指标

        Returns:
            (improvement_score, metrics_delta)
        """
        total_weight = 0.0
        weighted_score = 0.0
        deltas: dict[str, float] = {}

        for metric, weight in METRIC_WEIGHTS.items():
            base_val = baseline.get(metric, 0.0)
            var_val = variant.get(metric, 0.0)

            if base_val == 0.0 and var_val == 0.0:
                continue

            # 计算 delta
            if base_val == 0.0:
                delta = 1.0 if var_val > 0 else 0.0
            else:
                delta = (var_val - base_val) / abs(base_val)

            # 负向指标反向
            if metric in LOWER_IS_BETTER:
                delta = -delta

            deltas[metric] = delta
            total_weight += weight
            weighted_score += delta * weight

        improvement_score = weighted_score / total_weight if total_weight > 0 else 0.0
        return improvement_score, deltas

    @staticmethod
    def _compute_confidence(
        variant_count: int,
        best_score: float,
        baseline: dict[str, float],
    ) -> float:
        """计算评估置信度。

        基于：变体数量、改善幅度、样本指标。
        """
        confidence = 0.5  # 基础置信度

        # 变体数量越多，置信度越高
        if variant_count >= 3:
            confidence += 0.15
        elif variant_count >= 2:
            confidence += 0.08

        # 改善幅度越大，置信度越高
        if best_score > 0.3:
            confidence += 0.20
        elif best_score > 0.15:
            confidence += 0.12
        elif best_score > 0.05:
            confidence += 0.05

        # 有 ROAS 数据 → 置信度更高
        if baseline.get("roas", 0) > 0:
            confidence += 0.10

        return min(1.0, confidence)

    @staticmethod
    def _generate_learning_signal(
        winner_id: str,
        improvement_score: float,
        deltas: dict[str, float],
        baseline: dict[str, float],
        winner_metrics: dict[str, float],
    ) -> str:
        """生成学习信号。"""
        if not winner_id:
            return "No winner found — all variants underperformed baseline"

        if improvement_score <= 0:
            return "No improvement over baseline — mutation ineffective"

        # 找出贡献最大的指标
        best_metric = ""
        best_delta = 0.0
        for metric, delta in deltas.items():
            if delta > best_delta:
                best_delta = delta
                best_metric = metric

        # 生成可读信号
        if best_metric and best_delta > 0.05:
            display = METRIC_DISPLAY_NAMES.get(best_metric, best_metric)
            pct = abs(best_delta * 100)
            direction = "improved" if best_metric not in LOWER_IS_BETTER else "reduced"
            return (
                f"Winner {winner_id}: {display} {direction} by {pct:.0f}% "
                f"(overall improvement {improvement_score:+.0%})"
            )

        return (
            f"Winner {winner_id}: overall improvement {improvement_score:+.0%}"
        )

    def __repr__(self) -> str:
        return "ResultEvaluator()"