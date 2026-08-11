"""E11.6 — Evolution Policy Engine。

统一入口：LearningSignal → EvolutionPolicyDecision → PopulationDecision。

完整链路：
  LearningSignal
    → Rule Evaluation (policy_rules)
    → Strategy Selection (strategy_selector)
    → Population Decision (population_policy)
    → PolicyResult
"""

from __future__ import annotations

import logging
from typing import Any

from .models import (
    EvolutionAction,
    MutationStrategy,
    EvolutionPolicyDecision,
    PopulationDecision,
    PolicyResult,
)
from .policy_rules import PolicyRule, build_default_rules
from .strategy_selector import StrategySelector
from .population_policy import PopulationPolicy
from ..feedback.models import LearningSignal, LearningDirection, FitnessScore

logger = logging.getLogger(__name__)


class EvolutionPolicyEngine:
    """进化策略引擎。

    统一入口：将 LearningSignal 转换为 EvolutionPolicyDecision。

    完整链路：
      LearningSignal + FitnessScore
        → Rule Evaluation
        → Strategy Selection
        → EvolutionPolicyDecision

    Attributes:
        rules:             策略规则列表
        strategy_selector: StrategySelector
        population_policy: PopulationPolicy
        decide_count:      已决策次数
    """

    def __init__(
        self,
        rules: list[PolicyRule] | None = None,
        strategy_selector: StrategySelector | None = None,
        population_policy: PopulationPolicy | None = None,
    ) -> None:
        self._rules = rules or build_default_rules()
        # 按优先级排序
        self._rules.sort(key=lambda r: r.priority)
        self._strategy_selector = strategy_selector or StrategySelector()
        self._population_policy = population_policy or PopulationPolicy()
        self._decide_count: int = 0

    # ── 核心接口：decide ──────────────────────────────────

    def decide(
        self,
        learning_signal: LearningSignal,
        fitness: FitnessScore | None = None,
    ) -> EvolutionPolicyDecision:
        """根据学习信号生成进化策略决策。

        Args:
            learning_signal: 学习信号
            fitness:         适应度评分（可选）

        Returns:
            EvolutionPolicyDecision
        """
        # 1. 规则评估
        decision = self._evaluate_rules(learning_signal, fitness)

        # 2. 策略选择（如果规则未指定具体策略）
        if decision.mutation_strategy == MutationStrategy.SMALL and decision.action != EvolutionAction.KEEP:
            strategy = self._strategy_selector.select(learning_signal, fitness)
            decision.mutation_strategy = strategy
            decision.mutation_rate = StrategySelector.get_mutation_rate(strategy)
            decision.target_genes = StrategySelector.get_target_genes(strategy)

        # 3. 置信度整合
        if decision.confidence == 0.0:
            decision.confidence = learning_signal.confidence

        self._decide_count += 1
        return decision

    def decide_batch(
        self,
        learning_signals: list[LearningSignal],
        fitness_map: dict[str, FitnessScore] | None = None,
    ) -> list[EvolutionPolicyDecision]:
        """批量生成策略决策。"""
        fit_map = fitness_map or {}
        return [
            self.decide(ls, fit_map.get(ls.genome_id))
            for ls in learning_signals
        ]

    # ── 完整链路：decide_with_population ──────────────────

    def decide_with_population(
        self,
        learning_signals: list[LearningSignal],
        fitness_map: dict[str, FitnessScore] | None = None,
    ) -> PolicyResult:
        """完整链路：LearningSignal → PolicyDecision + PopulationDecision。

        Args:
            learning_signals: 学习信号列表
            fitness_map:      genome_id → FitnessScore 映射

        Returns:
            PolicyResult（含 decisions + population_decisions + summary）
        """
        fit_map = fitness_map or {}

        # 1. 生成策略决策
        decisions = self.decide_batch(learning_signals, fit_map)

        # 2. 生成种群决策
        pop_decisions = self._population_policy.decide_batch(decisions, fit_map)

        # 3. 汇总
        summary = self._build_summary(decisions, pop_decisions)

        self._decide_count += len(decisions)
        return PolicyResult(
            decisions=decisions,
            population_decisions=pop_decisions,
            summary=summary,
        )

    # ── 过滤方法 ──────────────────────────────────────────

    def get_active_decisions(
        self,
        decisions: list[EvolutionPolicyDecision],
    ) -> list[EvolutionPolicyDecision]:
        """获取需要执行的决策。"""
        return [d for d in decisions if d.is_active]

    def get_retire_decisions(
        self,
        decisions: list[EvolutionPolicyDecision],
    ) -> list[EvolutionPolicyDecision]:
        """获取需要退役的决策。"""
        return [d for d in decisions if d.is_retire]

    def get_decisions_by_action(
        self,
        decisions: list[EvolutionPolicyDecision],
        action: EvolutionAction,
    ) -> list[EvolutionPolicyDecision]:
        """按动作类型过滤决策。"""
        return [d for d in decisions if d.action == action]

    # ── 内部 ──────────────────────────────────────────────

    def _evaluate_rules(
        self,
        learning_signal: LearningSignal,
        fitness: FitnessScore | None,
    ) -> EvolutionPolicyDecision:
        """按优先级评估规则，返回第一个匹配的决策。"""
        for rule in self._rules:
            decision = rule.evaluate(learning_signal, fitness)
            if decision is not None:
                return decision

        # 不应到达这里（默认规则总是匹配）
        return EvolutionPolicyDecision(
            genome_id=learning_signal.genome_id,
            action=EvolutionAction.KEEP,
            reason=f"No rule matched for {learning_signal.genome_id}",
        )

    # ── 规则管理 ──────────────────────────────────────────

    def add_rule(self, rule: PolicyRule) -> None:
        """添加规则并重新排序。"""
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority)

    def remove_rule(self, name: str) -> bool:
        """按名称移除规则。"""
        original_len = len(self._rules)
        self._rules = [r for r in self._rules if r.name != name]
        return len(self._rules) < original_len

    def get_rules(self) -> list[PolicyRule]:
        """获取所有规则（按优先级排序）。"""
        return list(self._rules)

    # ── 汇总 ──────────────────────────────────────────────

    @staticmethod
    def _build_summary(
        decisions: list[EvolutionPolicyDecision],
        pop_decisions: list[PopulationDecision],
    ) -> dict[str, Any]:
        """构建决策摘要。"""
        action_counts: dict[str, int] = {}
        for d in decisions:
            key = d.action.value
            action_counts[key] = action_counts.get(key, 0) + 1

        return {
            "total_genomes": len(decisions),
            "active_decisions": sum(1 for d in decisions if d.is_active),
            "retire_decisions": sum(1 for d in decisions if d.is_retire),
            "action_counts": action_counts,
            "population_removes": sum(1 for p in pop_decisions if p.remove),
            "population_clones": sum(1 for p in pop_decisions if p.is_clone),
        }

    # ── Stats ─────────────────────────────────────────────

    @property
    def decide_count(self) -> int:
        return self._decide_count

    def get_stats(self) -> dict[str, Any]:
        return {
            "decide_count": self._decide_count,
            "rules_count": len(self._rules),
            "strategy_selections": self._strategy_selector.select_count,
            "population_decisions": self._population_policy.decide_count,
        }

    def reset(self) -> None:
        self._decide_count = 0
        self._strategy_selector.reset()
        self._population_policy.reset()

    def __repr__(self) -> str:
        return (
            f"EvolutionPolicyEngine(decided={self._decide_count}, "
            f"rules={len(self._rules)})"
        )