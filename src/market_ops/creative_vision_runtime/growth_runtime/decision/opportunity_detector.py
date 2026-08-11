"""E13.3.2 Opportunity Detector — 机会发现引擎.

核心职责: 基于 GrowthInsight，发现可执行的具体增长机会。

机会类型:
  - SCALE: 放量 (高 ROAS + 低疲劳)
  - STOP: 停投 (严重低效/疲劳)
  - PAUSE: 暂停 (ROAS 下降)
  - MUTATE: 变异 (疲劳但仍有潜力)
  - INCREASE_BUDGET: 加预算
  - DECREASE_BUDGET: 减预算
  - LAUNCH_EXPERIMENT: 新实验
  - DUPLICATE_WINNER: 复制 Winner

输入: GrowthInsight[]
输出: GrowthOpportunity[]
"""

from __future__ import annotations

from typing import Any

from ..pipeline.models import CreativeFitnessVector
from .models import (
    ActionType,
    GrowthInsight,
    GrowthOpportunity,
    InsightType,
    OpportunitySeverity,
)


# ═══════════════════════════════════════════════════════════════
# Opportunity Detector
# ═══════════════════════════════════════════════════════════════


class OpportunityDetector:
    """E13.3.2 Opportunity Detector — 机会发现引擎.

    功能:
      1. 从 GrowthInsight 发现可执行机会
      2. 按严重程度排序
      3. 输出 GrowthOpportunity 列表
    """

    # 默认阈值
    DEFAULT_THRESHOLDS = {
        "scale_budget_multiplier": 2.0,     # 放量预算倍数
        "strong_scale_multiplier": 3.0,     # 强放量倍数
        "decrease_budget_ratio": 0.5,       # 减预算比例
        "stop_budget_ratio": 0.0,           # 停投预算
        "min_confidence_for_scale": 0.8,    # 放量最低置信度
        "min_confidence_for_action": 0.7,   # 可执行动作最低置信度
    }

    def __init__(self, thresholds: dict[str, float] | None = None):
        self._thresholds = {**self.DEFAULT_THRESHOLDS, **(thresholds or {})}
        self._opportunities: list[GrowthOpportunity] = []

    # ── Properties ────────────────────────────────────────────

    @property
    def thresholds(self) -> dict[str, float]:
        return self._thresholds

    @property
    def opportunity_count(self) -> int:
        return len(self._opportunities)

    # ── Core Detection ────────────────────────────────────────

    def detect(
        self, insights: list[GrowthInsight],
    ) -> list[GrowthOpportunity]:
        """从 GrowthInsight 列表中发现机会.

        Args:
            insights: 增长洞察列表

        Returns:
            list[GrowthOpportunity]: 增长机会列表
        """
        if not insights:
            return []

        self._opportunities = []

        for insight in insights:
            opportunities = self._detect_from_insight(insight)
            self._opportunities.extend(opportunities)

        # 排序: 严重程度高 → 低
        severity_order = {
            OpportunitySeverity.CRITICAL: 0,
            OpportunitySeverity.HIGH: 1,
            OpportunitySeverity.MEDIUM: 2,
            OpportunitySeverity.LOW: 3,
        }
        self._opportunities.sort(
            key=lambda o: (severity_order.get(o.severity, 99), -o.confidence)
        )

        return self._opportunities

    def _detect_from_insight(
        self, insight: GrowthInsight,
    ) -> list[GrowthOpportunity]:
        """从单个洞察发现机会."""
        opportunities: list[GrowthOpportunity] = []

        if insight.insight_type == InsightType.WINNER_DISCOVERY:
            opportunities.append(self._create_scale_opportunity(insight))
        elif insight.insight_type == InsightType.SCALE_OPPORTUNITY:
            opportunities.append(self._create_scale_opportunity(insight))
        elif insight.insight_type == InsightType.CREATIVE_FATIGUE:
            opportunities.extend(self._create_fatigue_opportunities(insight))
        elif insight.insight_type == InsightType.ROAS_DROP:
            opportunities.append(self._create_budget_decrease(insight))
        elif insight.insight_type == InsightType.BUDGET_MISALLOCATION:
            opportunities.append(self._create_budget_decrease(insight))
        elif insight.insight_type == InsightType.UNDERPERFORMING:
            opportunities.append(self._create_stop_opportunity(insight))
        elif insight.insight_type == InsightType.HYBRID_WINNER:
            opportunities.append(self._create_scale_opportunity(insight))
        elif insight.insight_type == InsightType.RETENTION_SIGNAL:
            opportunities.append(self._create_scale_opportunity(insight))
        elif insight.insight_type == InsightType.CPI_ALERT:
            opportunities.append(self._create_budget_decrease(insight))

        return opportunities

    # ── Opportunity Creation ──────────────────────────────────

    def _create_scale_opportunity(
        self, insight: GrowthInsight,
    ) -> GrowthOpportunity:
        """创建放量机会."""
        source = insight.source_vector

        multiplier = self._thresholds["scale_budget_multiplier"]
        if source and isinstance(source, CreativeFitnessVector):
            if source.d30_roas > 2.0:
                multiplier = self._thresholds["strong_scale_multiplier"]

        current_budget = source.spend if source else 0.0

        return GrowthOpportunity(
            action=ActionType.SCALE,
            creative_id=insight.creative_id,
            creative_name=insight.creative_name,
            product_id=insight.product_id,
            reason=f"Scale opportunity: {insight.reason}",
            confidence=insight.confidence,
            severity=insight.severity,
            expected_impact={
                "roas_improvement": 0.0,
                "revenue_growth": current_budget * (multiplier - 1) * (source.d30_roas if source else 1.0),
            },
            budget_multiplier=multiplier,
            target_budget=current_budget * multiplier,
            current_budget=current_budget,
            source_insight=insight,
        )

    def _create_fatigue_opportunities(
        self, insight: GrowthInsight,
    ) -> list[GrowthOpportunity]:
        """创建疲劳相关机会."""
        opportunities: list[GrowthOpportunity] = []
        source = insight.source_vector

        current_budget = source.spend if source else 0.0

        # 1. 如果疲劳严重 → STOP
        if insight.severity == OpportunitySeverity.HIGH:
            opportunities.append(GrowthOpportunity(
                action=ActionType.STOP,
                creative_id=insight.creative_id,
                creative_name=insight.creative_name,
                product_id=insight.product_id,
                reason=f"Severe fatigue requires stop: {insight.reason}",
                confidence=insight.confidence,
                severity=OpportunitySeverity.CRITICAL,
                expected_impact={"cost_saved": current_budget},
                budget_multiplier=0.0,
                target_budget=0.0,
                current_budget=current_budget,
                source_insight=insight,
            ))

        # 2. 如果轻度疲劳 → MUTATE
        if source and isinstance(source, CreativeFitnessVector):
            if source.d30_roas > 0.8 or source.fitness_score > 0.5:
                opportunities.append(GrowthOpportunity(
                    action=ActionType.MUTATE,
                    creative_id=insight.creative_id,
                    creative_name=insight.creative_name,
                    product_id=insight.product_id,
                    reason=f"Creative fatigue, trigger mutation: {insight.reason}",
                    confidence=insight.confidence * 0.8,
                    severity=OpportunitySeverity.MEDIUM,
                    expected_impact={"new_variant_potential": 0.3},
                    source_insight=insight,
                ))

        return opportunities

    def _create_budget_decrease(
        self, insight: GrowthInsight,
    ) -> GrowthOpportunity:
        """创建减预算机会."""
        source = insight.source_vector
        current_budget = source.spend if source else 0.0
        ratio = self._thresholds["decrease_budget_ratio"]

        return GrowthOpportunity(
            action=ActionType.DECREASE_BUDGET,
            creative_id=insight.creative_id,
            creative_name=insight.creative_name,
            product_id=insight.product_id,
            reason=f"Decrease budget: {insight.reason}",
            confidence=insight.confidence,
            severity=insight.severity,
            expected_impact={"cost_saved": current_budget * (1 - ratio)},
            budget_multiplier=ratio,
            target_budget=current_budget * ratio,
            current_budget=current_budget,
            source_insight=insight,
        )

    def _create_stop_opportunity(
        self, insight: GrowthInsight,
    ) -> GrowthOpportunity:
        """创建停投机会."""
        source = insight.source_vector
        current_budget = source.spend if source else 0.0

        return GrowthOpportunity(
            action=ActionType.STOP,
            creative_id=insight.creative_id,
            creative_name=insight.creative_name,
            product_id=insight.product_id,
            reason=f"Stop underperforming creative: {insight.reason}",
            confidence=insight.confidence,
            severity=OpportunitySeverity.CRITICAL,
            expected_impact={"cost_saved": current_budget},
            budget_multiplier=0.0,
            target_budget=0.0,
            current_budget=current_budget,
            source_insight=insight,
        )

    # ── Query ─────────────────────────────────────────────────

    def get_opportunities_by_action(
        self, action: ActionType,
    ) -> list[GrowthOpportunity]:
        """按动作类型获取机会."""
        return [o for o in self._opportunities if o.action == action]

    def get_scale_opportunities(self) -> list[GrowthOpportunity]:
        """获取放量机会."""
        return [o for o in self._opportunities if o.is_scale_action]

    def get_stop_opportunities(self) -> list[GrowthOpportunity]:
        """获取停投机会."""
        return [o for o in self._opportunities if o.is_stop_action]

    def get_creative_opportunities(self) -> list[GrowthOpportunity]:
        """获取创意相关机会."""
        return [o for o in self._opportunities if o.is_creative_action]

    def get_high_confidence_opportunities(self) -> list[GrowthOpportunity]:
        """获取高置信度机会."""
        return [o for o in self._opportunities if o.confidence >= 0.85]

    def get_all_opportunities(self) -> list[GrowthOpportunity]:
        return list(self._opportunities)

    # ── Lifecycle ─────────────────────────────────────────────

    def reset(self) -> None:
        self._opportunities.clear()

    def get_summary(self) -> dict[str, Any]:
        return {
            "total_opportunities": self.opportunity_count,
            "by_action": {
                a.value: len(self.get_opportunities_by_action(a))
                for a in ActionType
                if self.get_opportunities_by_action(a)
            },
            "scale": len(self.get_scale_opportunities()),
            "stop": len(self.get_stop_opportunities()),
            "creative": len(self.get_creative_opportunities()),
            "high_confidence": len(self.get_high_confidence_opportunities()),
        }