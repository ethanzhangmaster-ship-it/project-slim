"""E12.7.3 — Planner Controller。

策略规划器控制器 —— E12.7.3 核心入口。

职责:
  1. 整合 ObjectiveEngine → StrategyBuilder → TacticGenerator → ConstraintManager → StrategyRanker
  2. 提供完整规划流程
  3. 输出 StrategyPlan

完整链路:
  GrowthObservation → Objective → Strategy → Tactics → Validate → Rank → StrategyPlan
"""

from __future__ import annotations

from typing import Any

from ..agent.models import GrowthHypothesis, GrowthObservation
from .constraint_manager import ConstraintManager
from .models import (
    ConstraintCheck,
    GrowthStrategy,
    StrategyPlan,
    StrategyTemplateType,
)
from .objective_engine import ObjectiveEngine
from .strategy_builder import StrategyBuilder
from .strategy_ranker import StrategyRanker
from .tactic_generator import TacticGenerator


class GrowthStrategyPlanner:
    """增长策略规划器。

    整合目标分析、策略构建、战术生成、约束验证、策略排名。
    """

    def __init__(
        self,
        objective_engine: ObjectiveEngine | None = None,
        strategy_builder: StrategyBuilder | None = None,
        tactic_generator: TacticGenerator | None = None,
        constraint_manager: ConstraintManager | None = None,
        strategy_ranker: StrategyRanker | None = None,
    ) -> None:
        self._objective_engine = objective_engine or ObjectiveEngine()
        self._strategy_builder = strategy_builder or StrategyBuilder()
        self._tactic_generator = tactic_generator or TacticGenerator()
        self._constraint_manager = constraint_manager or ConstraintManager()
        self._strategy_ranker = strategy_ranker or StrategyRanker()

    # ── Core Pipeline ──────────────────────────────────────

    def analyze_objective(
        self, observation: GrowthObservation
    ) -> list[Any]:
        """Step 1: 分析目标。

        Returns:
            StrategyObjective 列表
        """
        from .models import StrategyObjective
        return self._objective_engine.analyze(observation)

    def build_strategies(
        self,
        hypotheses: list[GrowthHypothesis],
        objectives: list[Any],
        product_id: str = "",
    ) -> list[GrowthStrategy]:
        """Step 2: 构建策略。

        Returns:
            GrowthStrategy 列表
        """
        return self._strategy_builder.build_from_hypotheses(
            hypotheses, objectives, product_id
        )

    def generate_tactics(
        self, strategies: list[GrowthStrategy]
    ) -> list[GrowthStrategy]:
        """Step 3: 生成战术。

        Returns:
            更新后的策略列表（含动作）
        """
        for strategy in strategies:
            self._tactic_generator.generate_and_attach(strategy)
        return strategies

    def validate(
        self, strategies: list[GrowthStrategy]
    ) -> dict[str, tuple[bool, list[ConstraintCheck]]]:
        """Step 4: 验证约束。

        Returns:
            {strategy_id: (passed, checks)}
        """
        return self._constraint_manager.validate_batch(strategies)

    def rank(self, strategies: list[GrowthStrategy]) -> list[GrowthStrategy]:
        """Step 5: 排名策略。

        Returns:
            排名后的策略列表
        """
        return self._strategy_ranker.rank(strategies)

    # ── Full Pipeline ──────────────────────────────────────

    def plan(
        self,
        observation: GrowthObservation,
        hypotheses: list[GrowthHypothesis],
        product_id: str = "",
        auto_validate: bool = True,
    ) -> StrategyPlan:
        """完整规划流程。

        Objective → Strategy → Tactics → Validate → Rank → StrategyPlan

        Args:
            observation:   增长观察
            hypotheses:    增长假设
            product_id:    产品 ID
            auto_validate: 是否自动验证

        Returns:
            StrategyPlan
        """
        # Step 1: Analyze Objectives
        objectives = self.analyze_objective(observation)

        # Step 2: Build Strategies
        strategies = self.build_strategies(hypotheses, objectives, product_id)

        # Step 3: Generate Tactics
        strategies = self.generate_tactics(strategies)

        # Step 4: Validate
        constraint_results: dict[str, tuple[bool, list[ConstraintCheck]]] = {}
        all_checks: list[ConstraintCheck] = []
        if auto_validate:
            constraint_results = self.validate(strategies)
            for _, checks in constraint_results.values():
                all_checks.extend(checks)

        # Step 5: Rank
        ranked = self.rank(strategies)
        top = ranked[0] if ranked else None

        # Build summary
        summary = self._build_summary(observation, ranked, constraint_results)

        return StrategyPlan(
            product_id=product_id,
            strategies=ranked,
            top_strategy=top,
            constraints=all_checks,
            summary=summary,
        )

    def plan_from_agent_result(
        self,
        observation: GrowthObservation,
        hypotheses: list[GrowthHypothesis],
        product_id: str = "",
    ) -> StrategyPlan:
        """从 Agent 结果直接规划（便捷方法）。

        Args:
            observation: 增长观察
            hypotheses:  增长假设
            product_id:  产品 ID

        Returns:
            StrategyPlan
        """
        return self.plan(observation, hypotheses, product_id, auto_validate=True)

    def _build_summary(
        self,
        observation: GrowthObservation,
        strategies: list[GrowthStrategy],
        constraint_results: dict[str, tuple[bool, list[ConstraintCheck]]],
    ) -> str:
        """构建规划摘要。"""
        parts: list[str] = []

        parts.append(
            f"Product: {observation.product_id} "
            f"(severity={observation.severity.value})"
        )

        parts.append(f"Strategies: {len(strategies)} generated")

        if strategies:
            top = strategies[0]
            parts.append(
                f"Top: {top.template_type.value} "
                f"(impact={top.expected_impact:.2f}, "
                f"confidence={top.confidence:.2f})"
            )

        if constraint_results:
            passed = sum(1 for p, _ in constraint_results.values() if p)
            parts.append(f"Validated: {passed}/{len(constraint_results)}")

        total_actions = sum(s.action_count for s in strategies)
        parts.append(f"Total actions: {total_actions}")

        return " | ".join(parts)

    def __repr__(self) -> str:
        return (
            f"GrowthStrategyPlanner("
            f"templates={self._strategy_builder.template_count}, "
            f"tactics={self._tactic_generator.rule_count})"
        )