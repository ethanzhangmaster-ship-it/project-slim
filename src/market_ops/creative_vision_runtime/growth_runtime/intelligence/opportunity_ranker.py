"""E13.5.2 Opportunity Ranker — 机会评分与排序.

将检测到的 GrowthOpportunity 候选按综合评分排序，并通过 Memory 增强置信度。

评分公式:
  Opportunity Score = Impact × 0.4 + Confidence × 0.3 + Urgency × 0.2 + MemoryEvidence × 0.1

Memory Boost:
  - 查询 StrategyMemory 中是否有匹配策略 → 提升 confidence
  - 查询 PatternStore 中是否有匹配模式 → 提升 impact_score
  - 查询 FailureMemory 中是否有相关失败 → 降低 confidence (警告标记)

连接:
  Opportunity Detection → Ranker → Memory Boost → Ranked Opportunities
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .intelligence_models import GrowthOpportunity, MemoryContext, OpportunitySource

if TYPE_CHECKING:
    from ..memory.failure_memory import FailureMemory
    from ..memory.pattern_store import PatternStore
    from ..memory.strategy_memory import StrategyMemory


class OpportunityRanker:
    """机会排序器 — 评分、Memory增强、排序.

    用法:
        ranker = OpportunityRanker()
        ranker.set_strategy_memory(sm)
        ranker.set_pattern_store(ps)
        ranker.set_failure_memory(fm)
        ranked = ranker.rank(opportunities)
    """

    # 评分权重
    WEIGHT_IMPACT = 0.4
    WEIGHT_CONFIDENCE = 0.3
    WEIGHT_URGENCY = 0.2
    WEIGHT_MEMORY = 0.1

    # Memory Boost 参数
    STRATEGY_BOOST = 0.15       # 匹配到策略时 confidence 提升
    PATTERN_BOOST = 0.10         # 匹配到模式时 impact_score 提升
    FAILURE_PENALTY = 0.10       # 匹配到失败模式时 confidence 降低
    MAX_MEMORY_BOOST = 0.25      # Memory 最大增益

    def __init__(self):
        self._strategy_memory: StrategyMemory | None = None
        self._pattern_store: PatternStore | None = None
        self._failure_memory: FailureMemory | None = None

    def set_strategy_memory(self, sm: StrategyMemory) -> None:
        """设置策略记忆."""
        self._strategy_memory = sm

    def set_pattern_store(self, ps: PatternStore) -> None:
        """设置模式存储."""
        self._pattern_store = ps

    def set_failure_memory(self, fm: FailureMemory) -> None:
        """设置失败记忆."""
        self._failure_memory = fm

    # ═══════════════════════════════════════════════════════════
    # Ranking
    # ═══════════════════════════════════════════════════════════

    def rank(
        self,
        opportunities: list[GrowthOpportunity],
        memory_context: MemoryContext | None = None,
        top_n: int = 10,
    ) -> list[GrowthOpportunity]:
        """对机会列表评分并排序.

        Args:
            opportunities: 待排序的机会列表
            memory_context: 记忆上下文 (已预检索的匹配)
            top_n: 返回前 N 个

        Returns:
            list[GrowthOpportunity]: 按综合得分降序排列
        """
        if not opportunities:
            return []

        for opp in opportunities:
            # 计算 Memory Boost
            memory_boost = self._compute_memory_boost(opp, memory_context)

            # 计算综合得分
            score = self._compute_score(opp, memory_boost)
            opp.metadata["rank_score"] = round(score, 4)
            opp.metadata["memory_boost"] = round(memory_boost, 4)

        # 排序: 综合得分降序
        ranked = sorted(opportunities, key=lambda o: o.metadata.get("rank_score", 0.0), reverse=True)

        return ranked[:top_n] if top_n > 0 else ranked

    def rank_with_memory(
        self,
        opportunities: list[GrowthOpportunity],
        top_n: int = 10,
    ) -> list[GrowthOpportunity]:
        """使用已连接的 Memory 进行实时增强排序.

        Args:
            opportunities: 待排序的机会列表
            top_n: 返回前 N 个

        Returns:
            list[GrowthOpportunity]: 增强排序后的机会列表
        """
        for opp in opportunities:
            # 实时 Memory Boost
            boost = self._compute_real_memory_boost(opp)
            score = self._compute_score(opp, boost)
            opp.metadata["rank_score"] = round(score, 4)
            opp.metadata["memory_boost"] = round(boost, 4)

        ranked = sorted(opportunities, key=lambda o: o.metadata.get("rank_score", 0.0), reverse=True)
        return ranked[:top_n] if top_n > 0 else ranked

    # ═══════════════════════════════════════════════════════════
    # Scoring
    # ═══════════════════════════════════════════════════════════

    def _compute_score(self, opp: GrowthOpportunity, memory_boost: float) -> float:
        """计算综合得分.

        Score = Impact × 0.4 + Confidence × 0.3 + Urgency × 0.2 + Memory × 0.1
        """
        base_score = (
            opp.impact_score * self.WEIGHT_IMPACT
            + opp.confidence * self.WEIGHT_CONFIDENCE
            + opp.urgency * self.WEIGHT_URGENCY
        )
        memory_score = memory_boost * self.WEIGHT_MEMORY
        return round(base_score + memory_score, 4)

    def _compute_memory_boost(
        self,
        opp: GrowthOpportunity,
        memory_context: MemoryContext | None = None,
    ) -> float:
        """根据预检索的 MemoryContext 计算 Memory Boost.

        - 有匹配策略 → +STRATEGY_BOOST
        - 有匹配模式 → +PATTERN_BOOST
        - 有相关失败 → -FAILURE_PENALTY
        """
        if memory_context is None:
            return 0.0

        boost = 0.0

        # 策略匹配增强
        if memory_context.recommended_strategies:
            boost += min(self.STRATEGY_BOOST * len(memory_context.recommended_strategies), self.STRATEGY_BOOST * 2)

        # 模式匹配增强
        if memory_context.matched_patterns:
            boost += min(self.PATTERN_BOOST * len(memory_context.matched_patterns), self.PATTERN_BOOST * 2)

        # 失败记忆惩罚
        if memory_context.relevant_failures:
            boost -= min(self.FAILURE_PENALTY * len(memory_context.relevant_failures), self.FAILURE_PENALTY * 3)

        # 历史成功率加权
        if memory_context.historical_success_rate > 0:
            boost += memory_context.historical_success_rate * 0.05

        return round(max(-self.MAX_MEMORY_BOOST, min(self.MAX_MEMORY_BOOST, boost)), 4)

    # ═══════════════════════════════════════════════════════════
    # Real-time Memory Boost
    # ═══════════════════════════════════════════════════════════

    def _compute_real_memory_boost(self, opp: GrowthOpportunity) -> float:
        """通过已连接的 Memory 实时查询计算 Boost.

        不使用预检索的 MemoryContext，而是直接查询 StrategyMemory、
        PatternStore、FailureMemory。
        """
        boost = 0.0

        opp_type = opp.opportunity_type.value
        action = opp.recommended_action

        # 策略匹配
        if self._strategy_memory:
            strategies = self._strategy_memory.recommend(
                opportunity_type=opp_type,
                actionable_only=True,
                top_n=3,
            )
            if strategies:
                boost += min(self.STRATEGY_BOOST * len(strategies), self.STRATEGY_BOOST * 2)
                # 记录匹配的策略 ID
                opp.source_strategy_id = strategies[0].strategy_id
                opp.source_pattern_ids = list(set(
                    opp.source_pattern_ids + strategies[0].source_pattern_ids
                ))

        # 模式匹配
        if self._pattern_store and action:
            pattern = self._pattern_store.get_best_pattern(
                opportunity_type=opp_type,
                action_type=action,
                actionable_only=True,
            )
            if pattern:
                boost += self.PATTERN_BOOST
                if pattern.pattern_id not in opp.source_pattern_ids:
                    opp.source_pattern_ids.append(pattern.pattern_id)

        # 失败记忆检查
        if self._failure_memory and action:
            risk_score = self._failure_memory.compute_risk_score(
                action_type=action,
                opportunity_type=opp_type,
            )
            if risk_score > 0:
                boost -= min(self.FAILURE_PENALTY * (1 + risk_score), self.FAILURE_PENALTY * 3)
                # 记录相关失败
                failures = self._failure_memory.check_action(
                    action_type=action,
                    opportunity_type=opp_type,
                )
                for f in failures:
                    if f.pattern_id not in opp.related_failure_ids:
                        opp.related_failure_ids.append(f.pattern_id)

        return round(max(-self.MAX_MEMORY_BOOST, min(self.MAX_MEMORY_BOOST, boost)), 4)

    # ═══════════════════════════════════════════════════════════
    # Top-N Selection
    # ═══════════════════════════════════════════════════════════

    def get_top(self, opportunities: list[GrowthOpportunity], n: int = 3) -> list[GrowthOpportunity]:
        """获取 Top-N 机会 (如果未排名则先排名)."""
        if not opportunities:
            return []
        # 如果未排名，先排名
        if not any("rank_score" in opp.metadata for opp in opportunities):
            return self.rank(opportunities, top_n=n)
        ranked = sorted(opportunities, key=lambda o: o.metadata.get("rank_score", 0.0), reverse=True)
        return ranked[:n]

    def get_critical_only(self, opportunities: list[GrowthOpportunity]) -> list[GrowthOpportunity]:
        """获取紧急/高优先级机会."""
        from .intelligence_models import DecisionPriority
        return [o for o in opportunities if o.is_high_priority]

    def get_actionable_only(self, opportunities: list[GrowthOpportunity]) -> list[GrowthOpportunity]:
        """获取可执行机会."""
        return [o for o in opportunities if o.is_actionable]