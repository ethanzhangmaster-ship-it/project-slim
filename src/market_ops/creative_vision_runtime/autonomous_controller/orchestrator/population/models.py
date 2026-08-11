"""E11.7.3 — Population Evolution Models。

GenomeIndividual:     进化个体
GenomeStatus:         个体状态
PopulationSnapshot:   种群快照
PopulationDecision:   种群级别进化决策
PopulationSummary:    种群汇总统计
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class GenomeStatus(str, Enum):
    """基因组个体状态。"""
    ACTIVE = "active"        # 活跃中
    ELITE = "elite"          # 精英（保留）
    MUTATING = "mutating"    # 突变中
    RETIRED = "retired"      # 已退役
    FAILED = "failed"        # 失败


@dataclass
class GenomeIndividual:
    """进化个体。

    Attributes:
        genome_id:         Genome ID
        fitness_score:     适应度评分
        generation:        所属代数
        status:            当前状态
        mutation_count:    已突变次数
        parent_id:         父代 ID（首次为 None）
        features:          基因特征（用于多样性计算）
        metadata:          附加元数据
    """

    genome_id: str = ""
    fitness_score: float = 0.0
    generation: int = 0
    status: GenomeStatus = GenomeStatus.ACTIVE
    mutation_count: int = 0
    parent_id: str | None = None
    features: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_elite(self) -> bool:
        return self.status == GenomeStatus.ELITE

    @property
    def is_retired(self) -> bool:
        return self.status == GenomeStatus.RETIRED

    @property
    def is_active(self) -> bool:
        return self.status in (GenomeStatus.ACTIVE, GenomeStatus.ELITE, GenomeStatus.MUTATING)

    def to_dict(self) -> dict[str, Any]:
        return {
            "genome_id": self.genome_id,
            "fitness_score": self.fitness_score,
            "generation": self.generation,
            "status": self.status.value,
            "mutation_count": self.mutation_count,
            "parent_id": self.parent_id,
            "features": self.features,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return (
            f"GenomeIndividual({self.genome_id}, "
            f"fitness={self.fitness_score:.1f}, "
            f"gen={self.generation}, "
            f"status={self.status.value})"
        )


@dataclass
class PopulationSnapshot:
    """种群快照。

    Attributes:
        population_id:   快照 ID
        generation:      代数
        individuals:     个体列表
        avg_fitness:     平均适应度
        min_fitness:     最低适应度
        max_fitness:     最高适应度
        diversity_score: 多样性评分
        elite_count:     精英数量
        total_count:     总数量
        created_at:      创建时间
    """

    population_id: str = ""
    generation: int = 0
    individuals: list[GenomeIndividual] = field(default_factory=list)
    avg_fitness: float = 0.0
    min_fitness: float = 0.0
    max_fitness: float = 0.0
    diversity_score: float = 0.0
    elite_count: int = 0
    total_count: int = 0
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.population_id:
            self.population_id = f"pop_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = _now()
        if self.total_count == 0:
            self.total_count = len(self.individuals)

    def to_dict(self) -> dict[str, Any]:
        return {
            "population_id": self.population_id,
            "generation": self.generation,
            "total_count": self.total_count,
            "elite_count": self.elite_count,
            "avg_fitness": self.avg_fitness,
            "min_fitness": self.min_fitness,
            "max_fitness": self.max_fitness,
            "diversity_score": self.diversity_score,
            "created_at": self.created_at,
        }

    def __repr__(self) -> str:
        return (
            f"PopulationSnapshot(gen={self.generation}, "
            f"size={self.total_count}, "
            f"avg_fitness={self.avg_fitness:.1f}, "
            f"diversity={self.diversity_score:.2f})"
        )


@dataclass
class PopulationDecision:
    """种群级别进化决策。

    Attributes:
        decision_id:    决策 ID
        generation:     代数
        elite:          精英个体 ID 列表
        mutate:         突变个体 ID 列表
        retire:         退役个体 ID 列表
        explore:        探索个体 ID 列表
        diversity_score: 多样性评分
        needs_exploration: 是否需要强制探索
        summary:        决策摘要
    """

    decision_id: str = ""
    generation: int = 0
    elite: list[str] = field(default_factory=list)
    mutate: list[str] = field(default_factory=list)
    retire: list[str] = field(default_factory=list)
    explore: list[str] = field(default_factory=list)
    diversity_score: float = 0.0
    needs_exploration: bool = False
    summary: str = ""

    def __post_init__(self) -> None:
        if not self.decision_id:
            self.decision_id = f"pd_{uuid.uuid4().hex[:12]}"

    @property
    def total_actions(self) -> int:
        return len(self.elite) + len(self.mutate) + len(self.retire) + len(self.explore)

    @property
    def mutation_count(self) -> int:
        return len(self.mutate) + len(self.explore)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "generation": self.generation,
            "elite": self.elite,
            "mutate": self.mutate,
            "retire": self.retire,
            "explore": self.explore,
            "diversity_score": self.diversity_score,
            "needs_exploration": self.needs_exploration,
            "summary": self.summary,
        }

    def __repr__(self) -> str:
        return (
            f"PopulationDecision(gen={self.generation}, "
            f"elite={len(self.elite)}, "
            f"mutate={len(self.mutate)}, "
            f"retire={len(self.retire)}, "
            f"explore={len(self.explore)})"
        )


@dataclass
class PopulationSummary:
    """种群汇总统计。

    Attributes:
        total_individuals:    总个体数
        active_count:         活跃数
        elite_count:          精英数
        retired_count:        退役数
        avg_fitness:          平均适应度
        best_fitness:         最佳适应度
        diversity_score:      多样性评分
        total_generations:    总代数
    """

    total_individuals: int = 0
    active_count: int = 0
    elite_count: int = 0
    retired_count: int = 0
    avg_fitness: float = 0.0
    best_fitness: float = 0.0
    diversity_score: float = 0.0
    total_generations: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_individuals": self.total_individuals,
            "active_count": self.active_count,
            "elite_count": self.elite_count,
            "retired_count": self.retired_count,
            "avg_fitness": self.avg_fitness,
            "best_fitness": self.best_fitness,
            "diversity_score": self.diversity_score,
            "total_generations": self.total_generations,
        }

    def __repr__(self) -> str:
        return (
            f"PopulationSummary(size={self.total_individuals}, "
            f"avg_fitness={self.avg_fitness:.1f}, "
            f"diversity={self.diversity_score:.2f})"
        )