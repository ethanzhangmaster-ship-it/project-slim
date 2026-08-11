"""E11.6 — Population Policy。

连接 V5 PopulationManager，控制基因组种群权重。

核心职责：
  1. 根据 EvolutionPolicyDecision 生成 PopulationDecision
  2. Winner → 增加权重 + 克隆
  3. Failed → 减少权重
  4. Retire → 移除
"""

from __future__ import annotations

import logging
from typing import Any

from .models import (
    EvolutionAction,
    EvolutionPolicyDecision,
    PopulationDecision,
)
from ..feedback.models import FitnessScore

logger = logging.getLogger(__name__)


class PopulationPolicy:
    """种群策略。

    将 EvolutionPolicyDecision 转换为 PopulationDecision。

    Attributes:
        decide_count: 已决策次数
    """

    # 权重变化常量
    WINNER_WEIGHT_INCREASE = 0.2
    IMPROVE_WEIGHT_INCREASE = 0.1
    FAILURE_WEIGHT_DECREASE = -0.15
    RETIRE_WEIGHT_DECREASE = -1.0  # 完全移除

    # 克隆数量
    WINNER_CLONE_COUNT = 2
    EXPLOIT_CLONE_COUNT = 1

    def __init__(self) -> None:
        self._decide_count: int = 0

    # ── 核心接口 ──────────────────────────────────────────

    def decide(
        self,
        policy_decision: EvolutionPolicyDecision,
        fitness: FitnessScore | None = None,
    ) -> PopulationDecision:
        """根据策略决策生成种群决策。

        Args:
            policy_decision: 进化策略决策
            fitness:         适应度评分（可选）

        Returns:
            PopulationDecision
        """
        action = policy_decision.action

        if action == EvolutionAction.KEEP:
            decision = self._handle_keep(policy_decision)
        elif action == EvolutionAction.EXPLOIT:
            decision = self._handle_exploit(policy_decision, fitness)
        elif action == EvolutionAction.EXPLORE:
            decision = self._handle_explore(policy_decision, fitness)
        elif action == EvolutionAction.MUTATE:
            decision = self._handle_mutate(policy_decision, fitness)
        elif action == EvolutionAction.RETIRE:
            decision = self._handle_retire(policy_decision)
        else:
            decision = self._handle_keep(policy_decision)

        self._decide_count += 1
        return decision

    def decide_batch(
        self,
        policy_decisions: list[EvolutionPolicyDecision],
        fitness_map: dict[str, FitnessScore] | None = None,
    ) -> list[PopulationDecision]:
        """批量生成种群决策。"""
        fit_map = fitness_map or {}
        return [
            self.decide(pd, fit_map.get(pd.genome_id))
            for pd in policy_decisions
        ]

    # ── 动作处理 ──────────────────────────────────────────

    @staticmethod
    def _handle_keep(pd: EvolutionPolicyDecision) -> PopulationDecision:
        """KEEP: 无变化。"""
        return PopulationDecision(
            genome_id=pd.genome_id,
            weight_change=0.0,
            reason=f"Genome {pd.genome_id} kept, no population change",
        )

    @staticmethod
    def _handle_exploit(
        pd: EvolutionPolicyDecision,
        fitness: FitnessScore | None,
    ) -> PopulationDecision:
        """EXPLOIT: 增加权重 + 克隆。"""
        clone_count = PopulationPolicy.WINNER_CLONE_COUNT
        return PopulationDecision(
            genome_id=pd.genome_id,
            weight_change=PopulationPolicy.WINNER_WEIGHT_INCREASE,
            clone_count=clone_count,
            reason=f"Genome {pd.genome_id} is winner, increasing weight +{PopulationPolicy.WINNER_WEIGHT_INCREASE}, cloning x{clone_count}",
        )

    @staticmethod
    def _handle_explore(
        pd: EvolutionPolicyDecision,
        fitness: FitnessScore | None,
    ) -> PopulationDecision:
        """EXPLORE: 减少权重（为探索腾出空间）。"""
        return PopulationDecision(
            genome_id=pd.genome_id,
            weight_change=PopulationPolicy.FAILURE_WEIGHT_DECREASE,
            reason=f"Genome {pd.genome_id} exploring, decreasing weight {PopulationPolicy.FAILURE_WEIGHT_DECREASE}",
        )

    @staticmethod
    def _handle_mutate(
        pd: EvolutionPolicyDecision,
        fitness: FitnessScore | None,
    ) -> PopulationDecision:
        """MUTATE: 保持或小幅增加权重。"""
        return PopulationDecision(
            genome_id=pd.genome_id,
            weight_change=PopulationPolicy.IMPROVE_WEIGHT_INCREASE,
            reason=f"Genome {pd.genome_id} mutating, small weight increase +{PopulationPolicy.IMPROVE_WEIGHT_INCREASE}",
        )

    @staticmethod
    def _handle_retire(
        pd: EvolutionPolicyDecision,
    ) -> PopulationDecision:
        """RETIRE: 移除。"""
        return PopulationDecision(
            genome_id=pd.genome_id,
            weight_change=PopulationPolicy.RETIRE_WEIGHT_DECREASE,
            remove=True,
            reason=f"Genome {pd.genome_id} retired, removing from population",
        )

    # ── Stats ─────────────────────────────────────────────

    @property
    def decide_count(self) -> int:
        return self._decide_count

    def reset(self) -> None:
        self._decide_count = 0

    def __repr__(self) -> str:
        return f"PopulationPolicy(decided={self._decide_count})"