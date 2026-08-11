"""E11.8.3 — Metric Evaluator。

职责：进化前后性能指标对比。

输入：before_metrics / after_metrics（dict）
输出：MetricComparison 列表

支持指标：ROI, CTR, CVR, Revenue, Retention, Conversion, CPA, IPM
"""

from __future__ import annotations

import logging
from typing import Any

from .models import MetricComparison

logger = logging.getLogger(__name__)

# 默认比较指标及其优先级（用于排序）
DEFAULT_METRICS: list[str] = [
    "ROI", "CTR", "CVR", "Revenue", "Retention", "Conversion", "CPA", "IPM",
]

# 指标方向：True = 越高越好，False = 越低越好
METRIC_DIRECTION: dict[str, bool] = {
    "ROI": True,
    "CTR": True,
    "CVR": True,
    "Revenue": True,
    "Retention": True,
    "Conversion": True,
    "IPM": True,
    "CPA": False,  # CPA 越低越好
}

# 显著性阈值（百分比）
SIGNIFICANCE_THRESHOLD: dict[str, float] = {
    "significant": 0.05,  # 5%
    "marginal": 0.01,     # 1%
}


class MetricEvaluator:
    """指标评估器。

    比较进化前后指标，生成 MetricComparison 列表。

    Attributes:
        metrics:         需要比较的指标列表
        directions:      指标方向（越高越好/越低越好）
        significance:    显著性阈值
    """

    def __init__(
        self,
        metrics: list[str] | None = None,
        directions: dict[str, bool] | None = None,
        significance_thresholds: dict[str, float] | None = None,
    ) -> None:
        self._metrics = metrics or DEFAULT_METRICS
        self._directions = directions or METRIC_DIRECTION
        self._significance = significance_thresholds or SIGNIFICANCE_THRESHOLD

    # ── 主入口 ──────────────────────────────────────────

    def compare(
        self,
        before: dict[str, float],
        after: dict[str, float],
    ) -> list[MetricComparison]:
        """比较进化前后指标。

        Args:
            before: 进化前指标 {"ROI": 0.45, "CTR": 0.03, ...}
            after:  进化后指标 {"ROI": 0.62, "CTR": 0.035, ...}

        Returns:
            MetricComparison 列表
        """
        comparisons: list[MetricComparison] = []

        for metric in self._metrics:
            before_val = before.get(metric)
            after_val = after.get(metric)

            # 跳过缺少的指标
            if before_val is None or after_val is None:
                continue

            higher_better = self._directions.get(metric, True)
            delta = after_val - before_val
            delta_pct = delta / abs(before_val) if before_val != 0 else 0.0

            # 判断改善方向
            if higher_better:
                improvement = delta > 0
            else:
                improvement = delta < 0

            # 判断显著性
            significance = self._classify_significance(abs(delta_pct))

            comparisons.append(
                MetricComparison(
                    metric=metric,
                    before=before_val,
                    after=after_val,
                    delta=delta,
                    delta_pct=delta_pct,
                    improvement=improvement,
                    significance=significance,
                )
            )

        return comparisons

    def compare_focused(
        self,
        before: dict[str, float],
        after: dict[str, float],
        focus_metrics: list[str],
    ) -> list[MetricComparison]:
        """只比较关注的指标。

        Args:
            before:       进化前指标
            after:        进化后指标
            focus_metrics: 关注的指标列表

        Returns:
            MetricComparison 列表
        """
        all_comparisons = self.compare(before, after)
        focus_set = set(focus_metrics)
        return [c for c in all_comparisons if c.metric in focus_set]

    # ── 统计方法 ─────────────────────────────────────────

    def summarize(
        self,
        comparisons: list[MetricComparison],
    ) -> dict[str, Any]:
        """汇总比较结果。

        Returns:
            {
                "total": int,
                "improved": int,
                "degraded": int,
                "avg_delta_pct": float,
                "best_metric": str | None,
                "worst_metric": str | None,
            }
        """
        if not comparisons:
            return {
                "total": 0,
                "improved": 0,
                "degraded": 0,
                "avg_delta_pct": 0.0,
                "best_metric": None,
                "worst_metric": None,
            }

        improved = [c for c in comparisons if c.improvement]
        degraded = [c for c in comparisons if not c.improvement]
        avg_delta = sum(c.delta_pct for c in comparisons) / len(comparisons)

        best = max(comparisons, key=lambda c: c.delta_pct) if comparisons else None
        worst = min(comparisons, key=lambda c: c.delta_pct) if comparisons else None

        return {
            "total": len(comparisons),
            "improved": len(improved),
            "degraded": len(degraded),
            "avg_delta_pct": round(avg_delta, 4),
            "best_metric": best.metric if best else None,
            "worst_metric": worst.metric if worst else None,
        }

    # ── 辅助方法 ─────────────────────────────────────────

    def _classify_significance(self, abs_delta_pct: float) -> str:
        """根据变化幅度分类显著性。"""
        if abs_delta_pct >= self._significance.get("significant", 0.05):
            return "significant"
        elif abs_delta_pct >= self._significance.get("marginal", 0.01):
            return "marginal"
        else:
            return "none"

    def __repr__(self) -> str:
        return f"MetricEvaluator(metrics={len(self._metrics)})"