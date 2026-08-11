"""E11.6 — Evolution Policy Models。

EvolutionAction:       系统动作（KEEP/EXPLOIT/EXPLORE/MUTATE/CROSSOVER/RETIRE）
MutationStrategy:      突变策略（SMALL/MEDIUM/LARGE/RADICAL）
EvolutionPolicyDecision: 核心决策输出
PopulationDecision:    种群级别决策
PolicyResult:          批量决策结果
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class EvolutionAction(str, Enum):
    """系统进化动作。"""
    KEEP = "keep"          # 保持当前基因组
    EXPLOIT = "exploit"    # 利用（复制赢家，小幅优化）
    EXPLORE = "explore"    # 探索（大幅突变，寻找新方向）
    MUTATE = "mutate"      # 突变（中等程度改变）
    CROSSOVER = "crossover"  # 交叉（组合多个赢家基因）
    RETIRE = "retire"      # 退役（淘汰基因组）


class MutationStrategy(str, Enum):
    """突变策略强度。"""
    SMALL = "small"        # 小幅度（mutation_rate=0.1, 1-2个基因）
    MEDIUM = "medium"      # 中等幅度（mutation_rate=0.3, 3-4个基因）
    LARGE = "large"        # 大幅度（mutation_rate=0.6, 5-6个基因）
    RADICAL = "radical"    # 激进（mutation_rate=0.9, 全部基因）


# 默认突变率映射
MUTATION_RATE_MAP: dict[MutationStrategy, float] = {
    MutationStrategy.SMALL: 0.1,
    MutationStrategy.MEDIUM: 0.3,
    MutationStrategy.LARGE: 0.6,
    MutationStrategy.RADICAL: 0.9,
}

# 默认目标基因列表
TARGET_GENES_MAP: dict[MutationStrategy, list[str]] = {
    MutationStrategy.SMALL: ["hook"],
    MutationStrategy.MEDIUM: ["hook", "visual", "reward"],
    MutationStrategy.LARGE: ["hook", "visual", "reward", "gameplay", "monetization"],
    MutationStrategy.RADICAL: ["hook", "visual", "reward", "gameplay", "monetization", "audience", "psychology", "context"],
}


@dataclass
class EvolutionPolicyDecision:
    """进化策略决策。

    Policy Engine 的核心输出，告诉系统对一个 Genome 应该采取什么进化动作。

    Attributes:
        decision_id:       决策 ID
        genome_id:         Genome ID
        action:            进化动作
        mutation_strategy: 突变策略强度
        mutation_rate:     突变率 (0.0-1.0)
        target_genes:      目标基因列表
        confidence:        置信度 (0.0-1.0)
        reason:            决策理由
        created_at:        创建时间
    """

    decision_id: str = ""
    genome_id: str = ""
    action: EvolutionAction = EvolutionAction.KEEP
    mutation_strategy: MutationStrategy = MutationStrategy.SMALL
    mutation_rate: float = 0.0
    target_genes: list[str] = field(default_factory=list)
    confidence: float = 0.0
    reason: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.decision_id:
            self.decision_id = f"epd_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = _now()
        # 自动填充 mutation_rate 和 target_genes
        if self.mutation_rate == 0.0:
            self.mutation_rate = MUTATION_RATE_MAP.get(
                self.mutation_strategy, 0.0
            )
        if not self.target_genes:
            self.target_genes = list(
                TARGET_GENES_MAP.get(self.mutation_strategy, [])
            )

    @property
    def is_active(self) -> bool:
        """是否需要执行进化动作。"""
        return self.action != EvolutionAction.KEEP

    @property
    def is_retire(self) -> bool:
        return self.action == EvolutionAction.RETIRE

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "genome_id": self.genome_id,
            "action": self.action.value,
            "mutation_strategy": self.mutation_strategy.value,
            "mutation_rate": self.mutation_rate,
            "target_genes": self.target_genes,
            "confidence": self.confidence,
            "reason": self.reason,
        }

    def __repr__(self) -> str:
        return (
            f"EvolutionPolicyDecision({self.genome_id}, "
            f"action={self.action.value}, "
            f"strategy={self.mutation_strategy.value}, "
            f"rate={self.mutation_rate})"
        )


@dataclass
class PopulationDecision:
    """种群级别决策。

    连接 V5 PopulationManager，控制基因组的种群权重。

    Attributes:
        genome_id:      Genome ID
        weight_change:  权重变化（正=增加，负=减少）
        remove:         是否移除
        clone_count:    克隆数量（EXPLOIT 时复制赢家）
        reason:         决策理由
    """

    genome_id: str = ""
    weight_change: float = 0.0
    remove: bool = False
    clone_count: int = 0
    reason: str = ""

    @property
    def is_remove(self) -> bool:
        return self.remove

    @property
    def is_clone(self) -> bool:
        return self.clone_count > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "genome_id": self.genome_id,
            "weight_change": self.weight_change,
            "remove": self.remove,
            "clone_count": self.clone_count,
            "reason": self.reason,
        }

    def __repr__(self) -> str:
        if self.remove:
            return f"PopulationDecision({self.genome_id}, REMOVE)"
        if self.clone_count > 0:
            return f"PopulationDecision({self.genome_id}, CLONE x{self.clone_count})"
        return (
            f"PopulationDecision({self.genome_id}, "
            f"weight={self.weight_change:+.2f})"
        )


@dataclass
class PolicyResult:
    """批量策略决策结果。

    Attributes:
        decisions:            EvolutionPolicyDecision 列表
        population_decisions: PopulationDecision 列表
        summary:              决策摘要
    """

    decisions: list[EvolutionPolicyDecision] = field(default_factory=list)
    population_decisions: list[PopulationDecision] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    @property
    def active_count(self) -> int:
        return sum(1 for d in self.decisions if d.is_active)

    @property
    def retire_count(self) -> int:
        return sum(1 for d in self.decisions if d.is_retire)

    def get_decisions_by_action(
        self, action: EvolutionAction
    ) -> list[EvolutionPolicyDecision]:
        return [d for d in self.decisions if d.action == action]

    def to_dict(self) -> dict[str, Any]:
        return {
            "decisions": [d.to_dict() for d in self.decisions],
            "population_decisions": [p.to_dict() for p in self.population_decisions],
            "summary": self.summary,
        }

    def __repr__(self) -> str:
        return (
            f"PolicyResult(decisions={len(self.decisions)}, "
            f"active={self.active_count}, "
            f"retire={self.retire_count})"
        )