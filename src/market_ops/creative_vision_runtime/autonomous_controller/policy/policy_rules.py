"""E11.6 — Policy Rules。

规则引擎：根据 LearningSignal 和 FitnessScore 匹配 EvolutionAction。

内置规则：
  1. Winner Rule:    fitness >= 80, direction=KEEP    → EXPLOIT + SMALL
  2. Improvement Rule: fitness 50-80, direction=IMPROVE → MUTATE + MEDIUM
  3. Failure Rule:     fitness < 50, direction=MUTATE  → EXPLORE + LARGE
  4. Dead Genome Rule: consecutive_failures >= 3        → RETIRE
  5. Default Rule:     fallback                          → KEEP
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from .models import EvolutionAction, MutationStrategy, EvolutionPolicyDecision
from ..feedback.models import LearningSignal, LearningDirection, FitnessScore

logger = logging.getLogger(__name__)


@dataclass
class PolicyRule:
    """策略规则。

    Attributes:
        name:        规则名称
        priority:    优先级（数字越小越优先）
        description: 规则描述
        condition:   条件函数 (learning_signal, fitness) -> bool
        action:      匹配时返回的 EvolutionAction
        strategy:    匹配时返回的 MutationStrategy
        reason:      决策理由模板
    """

    name: str = ""
    priority: int = 100
    description: str = ""
    condition: Callable[
        [LearningSignal, FitnessScore | None], bool
    ] = lambda ls, f: False
    action: EvolutionAction = EvolutionAction.KEEP
    strategy: MutationStrategy = MutationStrategy.SMALL
    reason: str = ""

    def evaluate(
        self,
        learning_signal: LearningSignal,
        fitness: FitnessScore | None = None,
    ) -> EvolutionPolicyDecision | None:
        """评估规则，匹配则返回决策。"""
        if not self.condition(learning_signal, fitness):
            return None

        # 用 fitness 的 overall_score 作为置信度基础
        base_confidence = fitness.overall_score / 100 if fitness else learning_signal.confidence

        return EvolutionPolicyDecision(
            genome_id=learning_signal.genome_id,
            action=self.action,
            mutation_strategy=self.strategy,
            confidence=round(base_confidence, 2),
            reason=self.reason.format(
                genome_id=learning_signal.genome_id,
                fitness=fitness.overall_score if fitness else "N/A",
                direction=learning_signal.direction.value,
                failures=learning_signal.consecutive_failures,
            ),
        )

    def __repr__(self) -> str:
        return (
            f"PolicyRule(name={self.name!r}, priority={self.priority}, "
            f"action={self.action.value})"
        )


# ── 内置规则条件 ──────────────────────────────────────────

def _is_winner(ls: LearningSignal, fitness: FitnessScore | None) -> bool:
    """Winner: fitness >= 80 且 direction=KEEP。"""
    if fitness is None:
        return False
    return fitness.is_winner and ls.direction == LearningDirection.KEEP


def _is_improvement(ls: LearningSignal, fitness: FitnessScore | None) -> bool:
    """Improvement: fitness 50-80 且 direction=IMPROVE。"""
    if fitness is None:
        return False
    return fitness.is_average and ls.direction == LearningDirection.IMPROVE


def _is_failure(ls: LearningSignal, fitness: FitnessScore | None) -> bool:
    """Failure: fitness < 50 且 direction=MUTATE。"""
    if fitness is None:
        return ls.direction == LearningDirection.MUTATE
    return fitness.is_failed and ls.direction == LearningDirection.MUTATE


def _is_dead(ls: LearningSignal, fitness: FitnessScore | None) -> bool:
    """Dead: 连续失败 >= 3。"""
    return ls.consecutive_failures >= 3


def _is_crossover(ls: LearningSignal, fitness: FitnessScore | None) -> bool:
    """Crossover: fitness >= 80 且有多个 winner 时。"""
    if fitness is None:
        return False
    return fitness.is_winner and ls.direction == LearningDirection.KEEP


# ── 内置规则 ──────────────────────────────────────────────

def build_default_rules() -> list[PolicyRule]:
    """构建默认规则集。

    优先级排序:
      1. Dead Genome (highest)
      2. Winner (EXPLOIT)
      3. Improvement (MUTATE)
      4. Failure (EXPLORE)
      5. Default (KEEP)
    """
    return [
        PolicyRule(
            name="dead_genome_retire",
            priority=1,
            description="连续失败 3 次以上 → RETIRE",
            condition=_is_dead,
            action=EvolutionAction.RETIRE,
            strategy=MutationStrategy.SMALL,
            reason="Genome {genome_id} failed {failures} consecutive times, retiring",
        ),
        PolicyRule(
            name="winner_exploit",
            priority=10,
            description="Winner genome (fitness >= 80) → EXPLOIT + SMALL",
            condition=_is_winner,
            action=EvolutionAction.EXPLOIT,
            strategy=MutationStrategy.SMALL,
            reason="Winner genome {genome_id} (fitness={fitness}), exploiting with small mutations",
        ),
        PolicyRule(
            name="improvement_mutate",
            priority=20,
            description="Average genome (fitness 50-80) → MUTATE + MEDIUM",
            condition=_is_improvement,
            action=EvolutionAction.MUTATE,
            strategy=MutationStrategy.MEDIUM,
            reason="Genome {genome_id} (fitness={fitness}), improving with medium mutations",
        ),
        PolicyRule(
            name="failure_explore",
            priority=30,
            description="Failed genome (fitness < 50) → EXPLORE + LARGE",
            condition=_is_failure,
            action=EvolutionAction.EXPLORE,
            strategy=MutationStrategy.LARGE,
            reason="Genome {genome_id} (fitness={fitness}), exploring with large mutations",
        ),
        PolicyRule(
            name="default_keep",
            priority=100,
            description="Default: no action needed → KEEP",
            condition=lambda ls, f: True,
            action=EvolutionAction.KEEP,
            strategy=MutationStrategy.SMALL,
            reason="Genome {genome_id}, no specific action needed, keeping current state",
        ),
    ]