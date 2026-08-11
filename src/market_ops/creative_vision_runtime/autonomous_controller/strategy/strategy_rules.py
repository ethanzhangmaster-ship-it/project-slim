"""E11.8.1 — Strategy Rules。

规则层：将 EvolutionObjective + 输入状态 转换为 EvolutionStrategy。

规则优先级（从高到低）：
  1. POPULATION_COLLAPSE — 种群塌缩，最高优先级
  2. FIX_FAILURE — 连续失败修复
  3. SCALE_SUCCESS — 高 ROI 扩大
  4. EXPLOIT_WINNER — 利用赢家
  5. EXPLORE_NEW — 默认探索
"""

from __future__ import annotations

import logging
from typing import Any

from .models import (
    EvolutionObjective,
    EvolutionStrategy,
    Horizon,
    Intensity,
    MutationFocus,
    StrategyType,
)

logger = logging.getLogger(__name__)

# 规则阈值
WINNER_FITNESS_THRESHOLD = 80.0
WINNER_SUCCESS_COUNT = 5
FAILURE_COUNT_THRESHOLD = 3
DIVERSITY_COLLAPSE_THRESHOLD = 0.2
SCALE_ROI_THRESHOLD = 1.5
SCALE_SUCCESS_COUNT = 10


class StrategyRules:
    """策略规则引擎。

    根据 EvolutionObjective + 输入状态 生成 EvolutionStrategy。

    规则评估顺序：
      1. Population Collapse（最高优先级）
      2. Fix Failure
      3. Scale Success
      4. Winner Exploit
      5. Explore New（兜底）
    """

    def __init__(
        self,
        winner_fitness: float = WINNER_FITNESS_THRESHOLD,
        winner_success_count: int = WINNER_SUCCESS_COUNT,
        failure_count: int = FAILURE_COUNT_THRESHOLD,
        diversity_threshold: float = DIVERSITY_COLLAPSE_THRESHOLD,
        scale_roi: float = SCALE_ROI_THRESHOLD,
        scale_success: int = SCALE_SUCCESS_COUNT,
    ) -> None:
        self._winner_fitness = winner_fitness
        self._winner_success_count = winner_success_count
        self._failure_count = failure_count
        self._diversity_threshold = diversity_threshold
        self._scale_roi = scale_roi
        self._scale_success = scale_success

    # ── 主入口 ──────────────────────────────────────────

    def evaluate(
        self,
        objective: EvolutionObjective,
        feedback: dict[str, Any] | None = None,
        population: dict[str, Any] | None = None,
    ) -> EvolutionStrategy:
        """根据 objective + 状态 评估策略。

        Args:
            objective:  进化目标
            feedback:   反馈数据
            population: 种群状态

        Returns:
            EvolutionStrategy
        """
        feedback = feedback or {}
        population = population or {}

        # Rule 1: Population Collapse（最高优先级）
        strategy = self._rule_population_collapse(objective, population)
        if strategy:
            return strategy

        # Rule 2: Fix Failure
        strategy = self._rule_fix_failure(objective, feedback)
        if strategy:
            return strategy

        # Rule 3: Scale Success
        strategy = self._rule_scale_success(objective, feedback)
        if strategy:
            return strategy

        # Rule 4: Winner Exploit
        strategy = self._rule_winner_exploit(objective, feedback)
        if strategy:
            return strategy

        # Rule 5: Explore New（兜底）
        return self._rule_explore_new(objective, feedback)

    def evaluate_multiple(
        self,
        objectives: list[EvolutionObjective],
        feedback: dict[str, Any] | None = None,
        population: dict[str, Any] | None = None,
    ) -> list[EvolutionStrategy]:
        """对多个 objective 评估策略。

        Returns:
            EvolutionStrategy 列表（与 objectives 一一对应）
        """
        return [
            self.evaluate(obj, feedback, population)
            for obj in objectives
        ]

    # ── 规则实现 ─────────────────────────────────────────

    def _rule_winner_exploit(
        self,
        objective: EvolutionObjective,
        feedback: dict[str, Any],
    ) -> EvolutionStrategy | None:
        """Rule 1: Winner Exploit。

        条件：
          - 最高 fitness > 80
          - 成功次数 >= 5

        输出：
          - EXPLOIT_WINNER
          - focus: HOOK/VISUAL
          - intensity: SMALL
        """
        max_fitness = feedback.get("max_fitness", 0.0)
        success_count = feedback.get("success_count", 0)

        if max_fitness >= self._winner_fitness and success_count >= self._winner_success_count:
            # 确定聚焦维度
            focus = self._infer_focus_from_objective(objective)
            if focus == MutationFocus.FULL:
                focus = MutationFocus.HOOK  # 赢家默认聚焦 HOOK

            return EvolutionStrategy(
                strategy_type=StrategyType.EXPLOIT_WINNER,
                objective=objective,
                target_genomes=feedback.get("top_genomes", []),
                mutation_focus=focus,
                intensity=Intensity.SMALL,
                confidence=min(1.0, max_fitness / 100.0),
                reason=(
                    f"Winner exploit: max_fitness={max_fitness:.1f}, "
                    f"success_count={success_count}. "
                    f"Keep winner stable, small variants only."
                ),
                metadata={
                    "rule": "winner_exploit",
                    "max_fitness": max_fitness,
                    "success_count": success_count,
                },
            )

        return None

    def _rule_fix_failure(
        self,
        objective: EvolutionObjective,
        feedback: dict[str, Any],
    ) -> EvolutionStrategy | None:
        """Rule 2: Failure Repair。

        条件：
          - failure_count >= 3

        输出：
          - FIX_FAILURE
          - intensity: LARGE
        """
        failure_count = feedback.get("failure_count", 0)

        if failure_count >= self._failure_count:
            # 找到最弱的指标
            weak_metrics = feedback.get("weak_metrics", {})
            focus = self._infer_focus_from_objective(objective)

            return EvolutionStrategy(
                strategy_type=StrategyType.FIX_FAILURE,
                objective=objective,
                target_genomes=feedback.get("failing_genomes", []),
                mutation_focus=focus,
                intensity=Intensity.LARGE,
                confidence=min(1.0, failure_count / 10.0),
                reason=(
                    f"Failure repair: failure_count={failure_count}. "
                    f"Applying large mutations to fix pattern."
                ),
                metadata={
                    "rule": "fix_failure",
                    "failure_count": failure_count,
                    "weak_metrics": weak_metrics,
                },
            )

        return None

    def _rule_population_collapse(
        self,
        objective: EvolutionObjective,
        population: dict[str, Any],
    ) -> EvolutionStrategy | None:
        """Rule 3: Population Collapse。

        条件：
          - diversity < threshold

        输出：
          - DIVERSIFY
          - focus: FULL
          - intensity: RADICAL
        """
        diversity = population.get("diversity_score", 0.5)

        if diversity < self._diversity_threshold:
            return EvolutionStrategy(
                strategy_type=StrategyType.DIVERSIFY,
                objective=objective,
                target_genomes=population.get("elite_ids", []),
                mutation_focus=MutationFocus.FULL,
                intensity=Intensity.RADICAL,
                confidence=min(1.0, (self._diversity_threshold - diversity) * 10.0),
                reason=(
                    f"Population collapse: diversity={diversity:.2f} "
                    f"(threshold={self._diversity_threshold}). "
                    f"Radical diversification needed."
                ),
                metadata={
                    "rule": "population_collapse",
                    "diversity_score": diversity,
                    "threshold": self._diversity_threshold,
                },
            )

        return None

    def _rule_scale_success(
        self,
        objective: EvolutionObjective,
        feedback: dict[str, Any],
    ) -> EvolutionStrategy | None:
        """Rule 4: Scale Success。

        条件：
          - avg ROI > 1.5
          - success_count >= 10

        输出：
          - SCALE_SUCCESS
          - intensity: MEDIUM
        """
        avg_roi = feedback.get("avg_roi", 0.0)
        success_count = feedback.get("success_count", 0)

        if avg_roi >= self._scale_roi and success_count >= self._scale_success:
            focus = self._infer_focus_from_objective(objective)

            return EvolutionStrategy(
                strategy_type=StrategyType.SCALE_SUCCESS,
                objective=objective,
                target_genomes=feedback.get("top_genomes", []),
                mutation_focus=focus,
                intensity=Intensity.MEDIUM,
                confidence=min(1.0, avg_roi / 3.0),
                reason=(
                    f"Scale success: avg_roi={avg_roi:.2f}, "
                    f"success_count={success_count}. "
                    f"Incrementally scale winning patterns."
                ),
                metadata={
                    "rule": "scale_success",
                    "avg_roi": avg_roi,
                    "success_count": success_count,
                },
            )

        return None

    def _rule_explore_new(
        self,
        objective: EvolutionObjective,
        feedback: dict[str, Any],
    ) -> EvolutionStrategy:
        """Rule 5: Explore New（兜底规则）。

        输出：
          - EXPLORE_NEW
          - intensity: MEDIUM
        """
        focus = self._infer_focus_from_objective(objective)
        sample_count = feedback.get("sample_count", 0)
        confidence = min(0.5, sample_count / 200.0) if sample_count > 0 else 0.3

        return EvolutionStrategy(
            strategy_type=StrategyType.EXPLORE_NEW,
            objective=objective,
            target_genomes=[],
            mutation_focus=focus,
            intensity=Intensity.MEDIUM,
            confidence=confidence,
            reason=(
                f"Explore new directions for '{objective.metric}': "
                f"current={objective.current_value:.3f}, "
                f"target={objective.target_value:.3f}."
            ),
            metadata={
                "rule": "explore_new",
                "sample_count": sample_count,
            },
        )

    # ── 辅助方法 ─────────────────────────────────────────

    @staticmethod
    def _infer_focus_from_objective(
        objective: EvolutionObjective,
    ) -> MutationFocus:
        """从 objective metadata 推断聚焦维度。"""
        focus_val = objective.metadata.get("focus")
        if focus_val:
            try:
                return MutationFocus(focus_val)
            except ValueError:
                pass
        return MutationFocus.FULL

    def __repr__(self) -> str:
        return (
            f"StrategyRules("
            f"winner_fitness={self._winner_fitness}, "
            f"failure_count={self._failure_count}, "
            f"diversity={self._diversity_threshold})"
        )