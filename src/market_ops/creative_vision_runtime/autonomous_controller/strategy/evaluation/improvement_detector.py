"""E11.8.3 — Improvement Detector。

职责：判断进化是否真正产生了提升。

输入：MetricComparison 列表
输出：EvaluationStatus + 综合评分

逻辑：
  - SUCCESS:      多数指标改善，整体增益 >= 阈值
  - PARTIAL:      部分改善，部分退化
  - FAILED:       多数指标退化
  - INCONCLUSIVE: 数据不足，无法判断
"""

from __future__ import annotations

import logging
from typing import Any

from .models import (
    EvaluationStatus,
    MetricComparison,
)

logger = logging.getLogger(__name__)

# 默认阈值
IMPROVEMENT_RATIO_THRESHOLD = 0.5     # 改善比例 >= 50% 为成功
FAILURE_RATIO_THRESHOLD = 0.3         # 改善比例 <= 30% 为失败
MIN_METRICS_FOR_CONCLUSION = 2        # 最少需要 2 个指标才能得出结论
SCORE_WEIGHT_SIGNIFICANT = 1.0        # 显著变化权重
SCORE_WEIGHT_MARGINAL = 0.5           # 边际变化权重
SCORE_WEIGHT_NONE = 0.2               # 无变化权重


class ImprovementDetector:
    """改善检测器。

    判断进化是否真正产生了提升。

    Attributes:
        improvement_threshold: 成功阈值
        failure_threshold:     失败阈值
        min_metrics:           最少指标数
    """

    def __init__(
        self,
        improvement_threshold: float = IMPROVEMENT_RATIO_THRESHOLD,
        failure_threshold: float = FAILURE_RATIO_THRESHOLD,
        min_metrics: int = MIN_METRICS_FOR_CONCLUSION,
    ) -> None:
        self._improvement_threshold = improvement_threshold
        self._failure_threshold = failure_threshold
        self._min_metrics = min_metrics

    # ── 主入口 ──────────────────────────────────────────

    def detect(
        self,
        comparisons: list[MetricComparison],
    ) -> tuple[EvaluationStatus, float]:
        """检测改善状态。

        Args:
            comparisons: MetricComparison 列表

        Returns:
            (EvaluationStatus, score)
        """
        if len(comparisons) < self._min_metrics:
            return EvaluationStatus.INCONCLUSIVE, 0.0

        # 计算加权分数
        score = self._compute_score(comparisons)

        # 计算改善比例
        improved = sum(1 for c in comparisons if c.improvement)
        ratio = improved / len(comparisons)

        # 判断状态
        if ratio >= self._improvement_threshold:
            status = EvaluationStatus.SUCCESS
        elif ratio <= self._failure_threshold:
            status = EvaluationStatus.FAILED
        else:
            status = EvaluationStatus.PARTIAL

        return status, round(score, 1)

    def detect_with_details(
        self,
        comparisons: list[MetricComparison],
    ) -> dict[str, Any]:
        """检测并返回详细信息。

        Returns:
            {
                "status": EvaluationStatus,
                "score": float,
                "improved_count": int,
                "degraded_count": int,
                "improvement_ratio": float,
                "reason": str,
            }
        """
        status, score = self.detect(comparisons)

        improved = sum(1 for c in comparisons if c.improvement)
        degraded = len(comparisons) - improved
        ratio = improved / len(comparisons) if comparisons else 0.0

        if status == EvaluationStatus.SUCCESS:
            reason = (
                f"Majority improved: {improved}/{len(comparisons)} metrics "
                f"({ratio:.0%}), score={score:.1f}"
            )
        elif status == EvaluationStatus.FAILED:
            reason = (
                f"Majority degraded: only {improved}/{len(comparisons)} metrics "
                f"improved ({ratio:.0%}), score={score:.1f}"
            )
        elif status == EvaluationStatus.PARTIAL:
            reason = (
                f"Mixed results: {improved}/{len(comparisons)} metrics "
                f"improved ({ratio:.0%}), score={score:.1f}"
            )
        else:
            reason = (
                f"Insufficient data: {len(comparisons)} metrics "
                f"(need {self._min_metrics})"
            )

        return {
            "status": status,
            "score": score,
            "improved_count": improved,
            "degraded_count": degraded,
            "improvement_ratio": round(ratio, 4),
            "reason": reason,
        }

    # ── 内部方法 ─────────────────────────────────────────

    def _compute_score(self, comparisons: list[MetricComparison]) -> float:
        """计算加权综合评分。

        正分 = 改善，负分 = 退化，权重按显著性。

        Returns:
            -100 到 100 的分数
        """
        if not comparisons:
            return 0.0

        total = 0.0
        for c in comparisons:
            weight = self._get_weight(c.significance)
            if c.improvement:
                total += c.delta_pct * 100 * weight
            else:
                total += c.delta_pct * 100 * weight  # 负数

        # 归一化到 [-100, 100]
        return max(-100.0, min(100.0, total / len(comparisons) * 2))

    @staticmethod
    def _get_weight(significance: str) -> float:
        if significance == "significant":
            return SCORE_WEIGHT_SIGNIFICANT
        elif significance == "marginal":
            return SCORE_WEIGHT_MARGINAL
        else:
            return SCORE_WEIGHT_NONE

    def __repr__(self) -> str:
        return (
            f"ImprovementDetector("
            f"success={self._improvement_threshold}, "
            f"failure={self._failure_threshold})"
        )