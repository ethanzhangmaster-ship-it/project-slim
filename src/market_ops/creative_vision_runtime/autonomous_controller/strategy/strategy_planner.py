"""E11.8.1 — Strategy Planner。

核心入口：将 feedback + knowledge + population 转换为 EvolutionStrategy。

流程：
  Input → ObjectiveEngine → StrategyRules → EvolutionStrategy

职责：
  1. 接收 Feedback / Knowledge / Population 多源输入
  2. 通过 ObjectiveEngine 生成 EvolutionObjective
  3. 通过 StrategyRules 评估并输出 EvolutionStrategy
  4. 提供 plan() 和 plan_batch() 两个入口
"""

from __future__ import annotations

import logging
from typing import Any

from .models import EvolutionObjective, EvolutionStrategy
from .objective_engine import ObjectiveEngine
from .strategy_rules import StrategyRules

logger = logging.getLogger(__name__)


class EvolutionStrategyPlanner:
    """进化策略规划器。

    组合 ObjectiveEngine + StrategyRules，提供统一入口。

    Attributes:
        objective_engine: 目标引擎
        strategy_rules:   策略规则引擎
    """

    def __init__(
        self,
        objective_engine: ObjectiveEngine | None = None,
        strategy_rules: StrategyRules | None = None,
    ) -> None:
        self._objective_engine = objective_engine or ObjectiveEngine()
        self._strategy_rules = strategy_rules or StrategyRules()

    # ── 主入口 ──────────────────────────────────────────

    def plan(
        self,
        feedback: dict[str, Any] | None = None,
        knowledge: dict[str, Any] | None = None,
        population: dict[str, Any] | None = None,
    ) -> list[EvolutionStrategy]:
        """规划进化策略。

        完整流程：
          1. ObjectiveEngine.build() → list[EvolutionObjective]
          2. StrategyRules.evaluate_multiple() → list[EvolutionStrategy]

        Args:
            feedback:   反馈数据
            knowledge:  知识图谱数据
            population: 种群状态

        Returns:
            EvolutionStrategy 列表（按优先级降序）
        """
        # 1. 构建目标
        objectives = self._objective_engine.build(
            feedback=feedback,
            knowledge=knowledge,
            population=population,
        )

        if not objectives:
            logger.info("No objectives generated, returning empty plan")
            return []

        # 2. 评估策略
        strategies = self._strategy_rules.evaluate_multiple(
            objectives=objectives,
            feedback=feedback,
            population=population,
        )

        logger.info(
            f"Plan generated: {len(strategies)} strategies from "
            f"{len(objectives)} objectives"
        )

        return strategies

    def plan_single(
        self,
        feedback: dict[str, Any] | None = None,
        knowledge: dict[str, Any] | None = None,
        population: dict[str, Any] | None = None,
    ) -> EvolutionStrategy | None:
        """规划单一最高优先级策略。

        Returns:
            最高优先级策略，无目标时返回 None
        """
        strategies = self.plan(feedback, knowledge, population)
        return strategies[0] if strategies else None

    def plan_with_objective(
        self,
        objective: EvolutionObjective,
        feedback: dict[str, Any] | None = None,
        population: dict[str, Any] | None = None,
    ) -> EvolutionStrategy:
        """基于已有 objective 直接生成策略。

        跳过 ObjectiveEngine，直接使用 StrategyRules。

        Args:
            objective:  已有进化目标
            feedback:   反馈数据
            population: 种群状态

        Returns:
            EvolutionStrategy
        """
        return self._strategy_rules.evaluate(
            objective=objective,
            feedback=feedback,
            population=population,
        )

    # ── 总结 ────────────────────────────────────────────

    def summarize(
        self,
        strategies: list[EvolutionStrategy],
    ) -> dict[str, Any]:
        """对策略列表进行汇总。

        Returns:
            {
                "total": int,
                "by_type": dict[str, int],
                "by_focus": dict[str, int],
                "top_strategy": EvolutionStrategy | None,
                "avg_confidence": float,
                "exploit_count": int,
                "explore_count": int,
            }
        """
        if not strategies:
            return {
                "total": 0,
                "by_type": {},
                "by_focus": {},
                "top_strategy": None,
                "avg_confidence": 0.0,
                "exploit_count": 0,
                "explore_count": 0,
            }

        by_type: dict[str, int] = {}
        by_focus: dict[str, int] = {}
        exploit_count = 0
        explore_count = 0
        total_conf = 0.0

        for s in strategies:
            by_type[s.strategy_type.value] = by_type.get(s.strategy_type.value, 0) + 1
            by_focus[s.mutation_focus.value] = by_focus.get(s.mutation_focus.value, 0) + 1
            total_conf += s.confidence

            if s.is_exploit:
                exploit_count += 1
            if s.is_explore:
                explore_count += 1

        return {
            "total": len(strategies),
            "by_type": by_type,
            "by_focus": by_focus,
            "top_strategy": strategies[0],
            "avg_confidence": round(total_conf / len(strategies), 3),
            "exploit_count": exploit_count,
            "explore_count": explore_count,
        }

    # ── 属性 ────────────────────────────────────────────

    @property
    def objective_engine(self) -> ObjectiveEngine:
        return self._objective_engine

    @property
    def strategy_rules(self) -> StrategyRules:
        return self._strategy_rules

    def __repr__(self) -> str:
        return (
            f"EvolutionStrategyPlanner("
            f"objective_engine={self._objective_engine}, "
            f"rules={self._strategy_rules})"
        )