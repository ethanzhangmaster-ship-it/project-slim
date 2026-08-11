"""E11.9 — Decision Engine。

职责：根据 Opportunity + Budget + Risk 决定是否启动进化。

输入：
  - EvolutionOpportunity
  - Budget 状态
  - 历史成功率
  - 活跃周期数

输出：
  - EvolutionDecision

规则：
  opportunity.score > 0.8 → START_EVOLUTION
  opportunity.score > 0.5 → OBSERVE
  opportunity.score <= 0.5 → HOLD

调整因子：
  - 预算不足 → 降低 action
  - 活跃周期过多 → 降低 action
  - 历史成功率高 → 提升 confidence
"""

from __future__ import annotations

import logging
from typing import Any

from .models import (
    EvolutionAction,
    EvolutionDecision,
    EvolutionOpportunity,
)

logger = logging.getLogger(__name__)

# 决策阈值
START_THRESHOLD = 0.8
OBSERVE_THRESHOLD = 0.5

# 约束因子
MAX_ACTIVE_CYCLES = 3
MIN_BUDGET_RATIO = 0.1


class DecisionEngine:
    """进化决策引擎。

    根据机会评分和约束条件，决定是否启动进化。

    Attributes:
        start_threshold:    启动阈值
        observe_threshold:  观察阈值
        max_active_cycles:  最大活跃周期数
        min_budget_ratio:   最小预算比例
    """

    def __init__(
        self,
        start_threshold: float = START_THRESHOLD,
        observe_threshold: float = OBSERVE_THRESHOLD,
        max_active_cycles: int = MAX_ACTIVE_CYCLES,
        min_budget_ratio: float = MIN_BUDGET_RATIO,
    ) -> None:
        self._start_threshold = start_threshold
        self._observe_threshold = observe_threshold
        self._max_active_cycles = max_active_cycles
        self._min_budget_ratio = min_budget_ratio

    # ── 主入口 ──────────────────────────────────────────

    def decide(
        self,
        opportunity: EvolutionOpportunity,
        budget: dict[str, Any] | None = None,
        active_cycles: int = 0,
        historical_success_rate: float = 0.5,
    ) -> EvolutionDecision:
        """根据机会和约束决定行动。

        Args:
            opportunity:            进化机会
            budget:                 预算状态
            active_cycles:          当前活跃周期数
            historical_success_rate: 历史成功率

        Returns:
            EvolutionDecision
        """
        # 1. 基础评分
        action, confidence = self._evaluate_score(opportunity.score)

        # 2. 约束调整
        action, confidence = self._apply_constraints(
            action, confidence, budget, active_cycles
        )

        # 3. 历史调整
        confidence = self._apply_history(confidence, historical_success_rate)

        # 4. 构建理由
        reason = self._build_reason(
            action, opportunity, budget, active_cycles, historical_success_rate
        )

        return EvolutionDecision(
            action=action,
            reason=reason,
            confidence=round(confidence, 3),
            opportunity=opportunity,
        )

    def decide_batch(
        self,
        opportunities: list[EvolutionOpportunity],
        budget: dict[str, Any] | None = None,
        active_cycles: int = 0,
    ) -> list[EvolutionDecision]:
        """批量决策。"""
        return [
            self.decide(opp, budget, active_cycles)
            for opp in opportunities
        ]

    # ── 内部方法 ─────────────────────────────────────────

    def _evaluate_score(
        self, score: float
    ) -> tuple[EvolutionAction, float]:
        """根据评分确定基础 action 和 confidence。"""
        if score >= self._start_threshold:
            return EvolutionAction.START_EVOLUTION, min(1.0, score)
        elif score >= self._observe_threshold:
            return EvolutionAction.OBSERVE, score * 0.8
        else:
            return EvolutionAction.HOLD, score * 0.5

    def _apply_constraints(
        self,
        action: EvolutionAction,
        confidence: float,
        budget: dict[str, Any] | None,
        active_cycles: int,
    ) -> tuple[EvolutionAction, float]:
        """应用约束调整。"""
        budget = budget or {}

        # 预算不足 → 降级
        budget_ratio = budget.get("remaining_ratio", 1.0)
        if budget_ratio < self._min_budget_ratio:
            if action == EvolutionAction.START_EVOLUTION:
                action = EvolutionAction.OBSERVE
                confidence *= 0.7
            elif action == EvolutionAction.OBSERVE:
                action = EvolutionAction.HOLD
                confidence *= 0.5

        # 活跃周期过多 → 降级
        if active_cycles >= self._max_active_cycles:
            if action == EvolutionAction.START_EVOLUTION:
                action = EvolutionAction.OBSERVE
                confidence *= 0.8
            elif action == EvolutionAction.OBSERVE:
                action = EvolutionAction.HOLD
                confidence *= 0.6

        return action, confidence

    @staticmethod
    def _apply_history(
        confidence: float,
        historical_success_rate: float,
    ) -> float:
        """根据历史成功率调整置信度。"""
        if historical_success_rate > 0.7:
            return min(1.0, confidence * 1.1)
        elif historical_success_rate < 0.3:
            return confidence * 0.8
        return confidence

    def _build_reason(
        self,
        action: EvolutionAction,
        opportunity: EvolutionOpportunity,
        budget: dict[str, Any] | None,
        active_cycles: int,
        historical_success_rate: float,
    ) -> str:
        """构建决策理由。"""
        budget = budget or {}
        parts = [
            f"Opportunity: {opportunity.type.value} "
            f"(score={opportunity.score:.2f})"
        ]

        if action == EvolutionAction.START_EVOLUTION:
            parts.append("Action: START_EVOLUTION (high-confidence opportunity)")
        elif action == EvolutionAction.OBSERVE:
            parts.append("Action: OBSERVE (moderate opportunity, monitoring)")
        else:
            parts.append("Action: HOLD (low opportunity or constraints)")

        if budget.get("remaining_ratio", 1.0) < self._min_budget_ratio:
            parts.append("Warning: low budget")
        if active_cycles >= self._max_active_cycles:
            parts.append("Warning: max active cycles reached")

        parts.append(f"History success rate: {historical_success_rate:.0%}")

        return " | ".join(parts)

    def __repr__(self) -> str:
        return (
            f"DecisionEngine("
            f"start={self._start_threshold}, "
            f"observe={self._observe_threshold})"
        )