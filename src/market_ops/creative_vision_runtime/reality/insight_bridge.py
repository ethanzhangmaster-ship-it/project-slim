"""E12.2 — Insight Bridge。

将 RealityInsight 桥接到 E11 Evolution Opportunity。

职责：
  1. RealityInsight → E11 EvolutionOpportunity 格式
  2. 批量转换
  3. 与 E11.9 OpportunityDetector 兼容

Usage:
    bridge = InsightBridge()
    opportunities = bridge.to_opportunities(insights)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .intelligence.models import CombinedInsight, RealityInsight

logger = logging.getLogger(__name__)


class InsightBridge:
    """Reality Insight → E11 Evolution Opportunity 桥接器。

    将 E12.2 的 RealityInsight 转换为 E11.9 OpportunityDetector
    可消费的 EvolutionOpportunity 格式。

    Attributes:
        total_bridged: 累计桥接次数
    """

    def __init__(self) -> None:
        self.total_bridged: int = 0

    # ── Public API ───────────────────────────────────────

    def to_opportunities(
        self,
        insights: list[RealityInsight],
    ) -> list[dict[str, Any]]:
        """将 RealityInsight 列表转换为 EvolutionOpportunity 格式。

        Args:
            insights: RealityInsight 列表

        Returns:
            E11.9 EvolutionOpportunity 格式的 dict 列表
        """
        opportunities = []

        for insight in insights:
            if not insight.is_actionable:
                continue

            opportunities.append(insight.to_evolution_opportunity())

        self.total_bridged += len(opportunities)
        logger.info(
            f"InsightBridge: {len(opportunities)} opportunities "
            f"from {len(insights)} insights"
        )
        return opportunities

    def to_market_signal(
        self,
        combined: CombinedInsight,
    ) -> dict[str, Any]:
        """将 CombinedInsight 转换为 E11.9 market_signal 格式。

        包含 trends 信息，用于 E11.9 OpportunityDetector.detect()。

        Args:
            combined: CombinedInsight

        Returns:
            market_signal dict
        """
        # 提取指标趋势
        metrics = {}
        trends = {}

        for insight in combined.insights:
            if insight.type.value == "performance_drop":
                trends["ROI"] = -0.35  # 有性能下降 → negative trend
            elif insight.type.value == "creative_fatigue":
                trends["CTR"] = -0.25
            elif insight.type.value == "winning_pattern":
                trends["ROI"] = 0.30
            elif insight.type.value == "market_shift":
                trends["ROI"] = -0.15

        metrics["ROI"] = max(0.0, 1.0 + trends.get("ROI", 0.0))
        metrics["CTR"] = max(0.0, 0.03 + trends.get("CTR", 0.0))

        usage_count = len(combined.insights)

        return {
            "metrics": metrics,
            "trends": trends,
            "usage_count": usage_count,
            "insight_types": [i.type.value for i in combined.insights],
            "combined_id": combined.combined_id,
        }

    def bridge_and_enrich(
        self,
        combined: CombinedInsight,
    ) -> dict[str, Any]:
        """完整桥接：opportunities + market_signal。

        Args:
            combined: CombinedInsight

        Returns:
            {
                "opportunities": [...],
                "market_signal": {...},
                "summary": str,
            }
        """
        opportunities = self.to_opportunities(combined.insights)
        market_signal = self.to_market_signal(combined)

        return {
            "opportunities": opportunities,
            "market_signal": market_signal,
            "summary": (
                f"Combined insight: {combined.primary_type.value} "
                f"(severity={combined.severity.value}, "
                f"confidence={combined.aggregated_confidence:.2f}, "
                f"{len(opportunities)} actionable opportunities)"
            ),
        }

    def __repr__(self) -> str:
        return f"InsightBridge(bridged={self.total_bridged})"