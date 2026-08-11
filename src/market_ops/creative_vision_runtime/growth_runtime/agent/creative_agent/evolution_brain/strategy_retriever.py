"""E14.8.3 Strategy Retriever — 策略检索器.

E14.8 Autonomous Growth Agent 第三层:
  连接 E14.7.4 StrategyMemory，根据当前 GrowthState 检索最佳历史策略.

核心模型:
  - StrategyMatch: 策略匹配结果
  - StrategyRetriever: 策略检索器
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from market_ops.creative_vision_runtime.growth_runtime.memory.strategy_models import (
    GrowthStrategyPattern,
    StrategyCategory,
    StrategyQuery,
)


# ═══════════════════════════════════════════════════════════
# 模型
# ═══════════════════════════════════════════════════════════

@dataclass
class StrategyMatch:
    """策略匹配结果 — 一条策略及其匹配度.

    Attributes:
        strategy: 匹配的策略
        match_score: 匹配度 [0, 1]
        match_reason: 匹配原因
        is_primary: 是否为主推荐
    """
    strategy: GrowthStrategyPattern
    match_score: float = 0.0
    match_reason: str = ""
    is_primary: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy.strategy_id,
            "name": self.strategy.name,
            "category": self.strategy.category.value,
            "score": self.strategy.score,
            "confidence": self.strategy.confidence,
            "match_score": self.match_score,
            "match_reason": self.match_reason,
            "is_primary": self.is_primary,
            "steps": len(self.strategy.steps),
            "success_rate": self.strategy.performance.success_rate,
            "quality": self.strategy.performance.quality.value,
        }


# ═══════════════════════════════════════════════════════════
# StrategyRetriever
# ═══════════════════════════════════════════════════════════

class StrategyRetriever:
    """策略检索器 — 根据 GrowthState 检索最佳策略.

    连接 E14.7.4 StrategyMemory，将状态映射为策略查询.

    用法:
        retriever = StrategyRetriever(strategy_memory)
        matches = retriever.retrieve(growth_state)
    """

    # 机会类型 → 策略类别映射
    OPPORTUNITY_TO_CATEGORY: dict[str, StrategyCategory] = {
        "creative_fatigue": StrategyCategory.CREATIVE_REVIVAL,
        "creative_refresh": StrategyCategory.CREATIVE_REVIVAL,
        "creative_scale": StrategyCategory.CREATIVE_SCALE,
        "scale_opportunity": StrategyCategory.CREATIVE_SCALE,
        "aggressive_scale": StrategyCategory.CREATIVE_SCALE,
        "roas_drop": StrategyCategory.ROAS_RECOVERY,
        "roas_improvement": StrategyCategory.ROAS_RECOVERY,
        "budget_waste": StrategyCategory.BUDGET_OPTIMIZATION,
        "payer_optimization": StrategyCategory.AUDIENCE_EXPANSION,
        "scale_up": StrategyCategory.CREATIVE_SCALE,
    }

    def __init__(
        self,
        strategy_memory: Any,
        min_confidence: float = 0.3,
        max_results: int = 10,
    ):
        """初始化检索器.

        Args:
            strategy_memory: E13.4.3 StrategyMemory 实例
            min_confidence: 最低置信度
            max_results: 最大返回数
        """
        self._strategy_memory = strategy_memory
        self._min_confidence = min_confidence
        self._max_results = max_results
        self._retrieval_count: int = 0

    def retrieve(
        self,
        state: Any,  # GrowthState
        top_n: int = 5,
    ) -> list[StrategyMatch]:
        """根据 GrowthState 检索最佳策略.

        Args:
            state: GrowthState 实例
            top_n: 返回前 N 个匹配

        Returns:
            list[StrategyMatch]: 匹配策略列表
        """
        self._retrieval_count += 1

        # 获取机会列表
        opportunities = getattr(state, "opportunities", [])
        primary_opp = getattr(state, "primary_opportunity", "")

        # 从 StrategyMemory 检索
        all_matches: list[StrategyMatch] = []

        # 按主要机会检索
        if primary_opp:
            opp_matches = self._retrieve_by_opportunity(primary_opp, state)
            all_matches.extend(opp_matches)

        # 按其他机会检索
        for opp in opportunities:
            if opp == primary_opp:
                continue
            opp_matches = self._retrieve_by_opportunity(opp, state)
            all_matches.extend(opp_matches)

        # 如果没有机会匹配，检索通用策略
        if not all_matches:
            general = self._retrieve_general(state)
            all_matches.extend(general)

        # 去重
        seen: set[str] = set()
        unique: list[StrategyMatch] = []
        for m in all_matches:
            if m.strategy.strategy_id not in seen:
                seen.add(m.strategy.strategy_id)
                unique.append(m)

        # 排序
        unique.sort(key=lambda m: -m.match_score)

        # 标记主推荐
        if unique:
            unique[0].is_primary = True

        return unique[:top_n]

    def _retrieve_by_opportunity(
        self,
        opportunity: str,
        state: Any,
    ) -> list[StrategyMatch]:
        """按机会类型检索策略."""
        # 获取策略
        strategies = self._strategy_memory.recommend(
            opportunity_type=opportunity,
            actionable_only=True,
            top_n=5,
        )

        matches: list[StrategyMatch] = []
        for s in strategies:
            match_score = self._compute_state_match(s, state, opportunity)
            matches.append(StrategyMatch(
                strategy=s,
                match_score=match_score,
                match_reason=f"Opportunity: {opportunity}",
            ))

        return matches

    def _retrieve_general(self, state: Any) -> list[StrategyMatch]:
        """检索通用高分策略."""
        strategies = self._strategy_memory.get_top_strategies(n=5)
        matches: list[StrategyMatch] = []
        for s in strategies:
            if s.performance.success_rate >= 0.5:
                matches.append(StrategyMatch(
                    strategy=s,
                    match_score=s.score * 0.5,  # 通用匹配降权
                    match_reason="General top strategy",
                ))
        return matches

    def _compute_state_match(
        self,
        strategy: GrowthStrategyPattern,
        state: Any,
        opportunity: str,
    ) -> float:
        """计算策略与状态的匹配度 [0, 1]."""
        score = 0.0
        weight = 0.0

        # 机会匹配 (权重 0.4)
        weight += 0.4
        if strategy.trigger.opportunity_type == opportunity:
            score += 0.4

        # 策略质量 (权重 0.3)
        weight += 0.3
        quality = strategy.performance.quality.value
        quality_weights = {
            "proven": 0.3,
            "reliable": 0.25,
            "emerging": 0.2,
            "experimental": 0.1,
            "untested": 0.05,
        }
        score += quality_weights.get(quality, 0)

        # 策略评分 (权重 0.3)
        weight += 0.3
        score += strategy.score * 0.3

        return round(score / weight, 4) if weight > 0 else 0.0

    def retrieve_best(
        self,
        state: Any,
    ) -> StrategyMatch | None:
        """检索最佳单条策略."""
        matches = self.retrieve(state, top_n=1)
        return matches[0] if matches else None

    def retrieve_by_category(
        self,
        category: StrategyCategory,
        state: Any,
        top_n: int = 5,
    ) -> list[StrategyMatch]:
        """按类别检索策略."""
        strategies = self._strategy_memory.get_by_category(category)
        matches: list[StrategyMatch] = []
        for s in strategies:
            if s.is_actionable():
                match_score = self._compute_state_match(s, state, "")
                matches.append(StrategyMatch(
                    strategy=s,
                    match_score=match_score,
                    match_reason=f"Category: {category.value}",
                ))
        matches.sort(key=lambda m: -m.match_score)
        return matches[:top_n]

    @property
    def retrieval_count(self) -> int:
        return self._retrieval_count

    @property
    def strategy_memory(self) -> Any:
        return self._strategy_memory


def create_strategy_retriever(
    strategy_memory: Any,
    min_confidence: float = 0.3,
    max_results: int = 10,
) -> StrategyRetriever:
    """创建默认 StrategyRetriever."""
    return StrategyRetriever(
        strategy_memory=strategy_memory,
        min_confidence=min_confidence,
        max_results=max_results,
    )