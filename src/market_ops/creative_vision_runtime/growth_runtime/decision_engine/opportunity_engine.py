"""E13.3.2 GrowthOpportunityEngine — 增长机会引擎.

核心职责:
  将 GrowthSignal 列表转换为可执行的 GrowthOpportunity 列表,
  并进行优先级排序.

输入:
  - list[GrowthSignal]: 增长信号列表

输出:
  - list[GrowthOpportunity]: 排序后的增长机会列表
  - OpportunityBatch: 批量机会结果 (含统计)
"""

from __future__ import annotations

import time
from typing import Any

from .models import (
    GrowthOpportunity,
    GrowthSignal,
    OpportunityBatch,
    OpportunityPriority,
    OpportunityType,
    SignalCategory,
    SignalType,
    SIGNAL_CATEGORY_MAP,
)
from .strategies import (
    CreativeOpportunityMapper,
    RevenueOpportunityMapper,
    UAOpportunityMapper,
)


# ═══════════════════════════════════════════════════════════════
# Default Risk Weights
# ═══════════════════════════════════════════════════════════════

RISK_WEIGHTS = {
    "low": 1.0,
    "medium": 0.7,
    "high": 0.4,
    "critical": 0.2,
}


class GrowthOpportunityEngine:
    """增长机会引擎 — 将信号转换为可执行的机会并排序.

    用法:
        engine = GrowthOpportunityEngine()
        opportunities = engine.analyze(signals)
        batch = engine.analyze_batch(signals, product_id="p1")
    """

    def __init__(self, gains: dict[OpportunityType, float] | None = None):
        """初始化引擎.

        Args:
            gains: 自定义预期收益映射
        """
        self._creative_mapper = CreativeOpportunityMapper(gains)
        self._ua_mapper = UAOpportunityMapper(gains)
        self._revenue_mapper = RevenueOpportunityMapper(gains)

    def analyze(self, signals: list[GrowthSignal]) -> list[GrowthOpportunity]:
        """分析信号列表，生成排序后的机会列表.

        Args:
            signals: GrowthSignal 列表

        Returns:
            list[GrowthOpportunity]: 按 score 降序排序的机会列表
        """
        if not signals:
            return []

        all_opportunities: list[GrowthOpportunity] = []

        for signal in signals:
            opportunities = self._map_signal(signal)
            all_opportunities.extend(opportunities)

        # 计算评分并排序
        self._rank(all_opportunities)

        return all_opportunities

    def analyze_batch(
        self,
        signals: list[GrowthSignal],
        product_id: str = "",
        date: str = "",
    ) -> OpportunityBatch:
        """批量分析，返回 OpportunityBatch.

        Args:
            signals: 信号列表
            product_id: 产品ID
            date: 分析日期

        Returns:
            OpportunityBatch: 含完整机会列表和分类统计
        """
        start = time.perf_counter()

        opportunities = self.analyze(signals)

        elapsed_ms = (time.perf_counter() - start) * 1000

        # 计算分类统计
        summary: dict[str, int] = {}
        for opp in opportunities:
            key = opp.opportunity_type.value
            summary[key] = summary.get(key, 0) + 1

        return OpportunityBatch(
            product_id=product_id,
            date=date,
            opportunities=opportunities,
            total_signals=len(signals),
            total_opportunities=len(opportunities),
            summary=summary,
            elapsed_ms=round(elapsed_ms, 2),
        )

    # ═══════════════════════════════════════════════════════════
    # Mapping
    # ═══════════════════════════════════════════════════════════

    def _map_signal(self, signal: GrowthSignal) -> list[GrowthOpportunity]:
        """根据信号类型路由到对应的 mapper."""
        category = SIGNAL_CATEGORY_MAP.get(signal.signal_type, SignalCategory.CREATIVE)

        if category == SignalCategory.CREATIVE:
            return self._creative_mapper.map(signal)
        elif category == SignalCategory.UA:
            return self._ua_mapper.map(signal)
        elif category in (SignalCategory.REVENUE, SignalCategory.MONETIZATION):
            return self._revenue_mapper.map(signal)

        return []

    # ═══════════════════════════════════════════════════════════
    # Ranking
    # ═══════════════════════════════════════════════════════════

    def _rank(self, opportunities: list[GrowthOpportunity]) -> None:
        """计算每个机会的综合评分并排序.

        公式:
          score = confidence * expected_gain * business_value / risk_weight

        排序: score 降序
        """
        for opp in opportunities:
            risk_weight = RISK_WEIGHTS.get(opp.risk, 0.7)
            opp.score = round(
                opp.confidence * opp.expected_gain * opp.business_value / max(risk_weight, 0.01),
                4,
            )

        # 按 score 降序排序
        opportunities.sort(key=lambda o: -o.score)

    # ═══════════════════════════════════════════════════════════
    # Convenience filters
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def filter_by_priority(
        opportunities: list[GrowthOpportunity],
        min_priority: OpportunityPriority = OpportunityPriority.HIGH,
    ) -> list[GrowthOpportunity]:
        """按最低优先级过滤."""
        priority_order = {
            OpportunityPriority.CRITICAL: 0,
            OpportunityPriority.HIGH: 1,
            OpportunityPriority.MEDIUM: 2,
            OpportunityPriority.LOW: 3,
        }
        threshold = priority_order.get(min_priority, 99)
        return [o for o in opportunities if priority_order.get(o.priority, 99) <= threshold]

    @staticmethod
    def filter_by_type(
        opportunities: list[GrowthOpportunity],
        opp_type: OpportunityType,
    ) -> list[GrowthOpportunity]:
        """按机会类型过滤."""
        return [o for o in opportunities if o.opportunity_type == opp_type]

    @staticmethod
    def get_top_opportunities(
        opportunities: list[GrowthOpportunity],
        n: int = 5,
    ) -> list[GrowthOpportunity]:
        """获取 Top N 个高分机会."""
        sorted_opps = sorted(opportunities, key=lambda o: -o.score)
        return sorted_opps[:n]

    @staticmethod
    def get_actionable_opportunities(
        opportunities: list[GrowthOpportunity],
    ) -> list[GrowthOpportunity]:
        """获取可直接执行的机会 (置信度 > 0.5)."""
        return [o for o in opportunities if o.confidence > 0.5]