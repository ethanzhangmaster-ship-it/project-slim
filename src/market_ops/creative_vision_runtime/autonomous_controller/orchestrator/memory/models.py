"""E11.7.4 — Evolution Memory Models。

EvolutionMemoryRecord:  完整进化经验记录
MemoryOutcome:           经验结果
MemoryQuery:             内存检索查询
MemoryQueryResult:       查询结果（含统计）
MemoryInsight:           内存洞察（含推荐）
MemoryStats:             内存统计
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MemoryOutcome(str, Enum):
    """经验结果。"""
    SUCCESS = "success"      # 成功（fitness 提升）
    NEUTRAL = "neutral"      # 中性（无明显变化）
    FAILURE = "failure"      # 失败（fitness 下降）
    RETIRED = "retired"      # 退役（被淘汰）


@dataclass
class EvolutionMemoryRecord:
    """一次完整进化经验记录。

    Attributes:
        memory_id:          记录 ID
        genome_id:          基因组 ID
        parent_genome_id:   父代基因组 ID
        mutation_type:      突变类型（hook, visual, gameplay, ...）
        mutation_params:    突变参数
        creative_id:        关联创意 ID
        category:           分类（merge, purge, explore, ...）
        fitness_before:     突变前适应度
        fitness_after:      突变后适应度
        fitness_gain:       适应度变化
        outcome:            结果
        success_patterns:   成功模式列表
        failure_patterns:   失败模式列表
        generation:         代数
        notes:              备注
        created_at:         创建时间
    """

    memory_id: str = ""
    genome_id: str = ""
    parent_genome_id: str | None = None
    mutation_type: str = ""
    mutation_params: dict[str, Any] = field(default_factory=dict)
    creative_id: str | None = None
    category: str = ""
    fitness_before: float = 0.0
    fitness_after: float = 0.0
    fitness_gain: float = 0.0
    outcome: MemoryOutcome = MemoryOutcome.NEUTRAL
    success_patterns: list[str] = field(default_factory=list)
    failure_patterns: list[str] = field(default_factory=list)
    generation: int = 0
    notes: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.memory_id:
            self.memory_id = f"mem_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = _now()
        if self.fitness_gain == 0.0:
            self.fitness_gain = self.fitness_after - self.fitness_before

    @property
    def is_success(self) -> bool:
        return self.outcome == MemoryOutcome.SUCCESS

    @property
    def is_failure(self) -> bool:
        return self.outcome == MemoryOutcome.FAILURE

    @property
    def is_retired(self) -> bool:
        return self.outcome == MemoryOutcome.RETIRED

    @property
    def all_patterns(self) -> list[str]:
        return self.success_patterns + self.failure_patterns

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "genome_id": self.genome_id,
            "parent_genome_id": self.parent_genome_id,
            "mutation_type": self.mutation_type,
            "mutation_params": self.mutation_params,
            "creative_id": self.creative_id,
            "category": self.category,
            "fitness_before": self.fitness_before,
            "fitness_after": self.fitness_after,
            "fitness_gain": self.fitness_gain,
            "outcome": self.outcome.value,
            "success_patterns": self.success_patterns,
            "failure_patterns": self.failure_patterns,
            "generation": self.generation,
            "notes": self.notes,
            "created_at": self.created_at,
        }

    def __repr__(self) -> str:
        return (
            f"EvolutionMemoryRecord({self.memory_id}, "
            f"genome={self.genome_id}, "
            f"mutation={self.mutation_type}, "
            f"outcome={self.outcome.value}, "
            f"gain={self.fitness_gain:+.2f})"
        )


@dataclass
class MemoryQuery:
    """内存检索查询。

    Attributes:
        mutation_type:   突变类型（可选）
        category:        分类（可选）
        patterns:        模式列表
        min_fitness_gain: 最低适应度提升
        outcome:         结果过滤（可选）
        max_records:     最大返回记录数
    """

    mutation_type: str | None = None
    category: str | None = None
    patterns: list[str] = field(default_factory=list)
    min_fitness_gain: float = 0.0
    outcome: MemoryOutcome | None = None
    max_records: int = 100

    def to_dict(self) -> dict[str, Any]:
        return {
            "mutation_type": self.mutation_type,
            "category": self.category,
            "patterns": self.patterns,
            "min_fitness_gain": self.min_fitness_gain,
            "outcome": self.outcome.value if self.outcome else None,
            "max_records": self.max_records,
        }


@dataclass
class MemoryQueryResult:
    """内存查询结果。

    Attributes:
        query:            原始查询
        records:          匹配的记录
        total_matches:    总匹配数
        success_count:    成功次数
        failure_count:    失败次数
        success_rate:     成功率
        avg_gain:         平均适应度提升
        best_patterns:    最佳模式
        bad_patterns:     最差模式
        recommendation:   推荐
    """

    query: MemoryQuery = field(default_factory=MemoryQuery)
    records: list[EvolutionMemoryRecord] = field(default_factory=list)
    total_matches: int = 0
    success_count: int = 0
    failure_count: int = 0
    success_rate: float = 0.0
    avg_gain: float = 0.0
    best_patterns: list[str] = field(default_factory=list)
    bad_patterns: list[str] = field(default_factory=list)
    recommendation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query.to_dict(),
            "total_matches": self.total_matches,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": self.success_rate,
            "avg_gain": self.avg_gain,
            "best_patterns": self.best_patterns,
            "bad_patterns": self.bad_patterns,
            "recommendation": self.recommendation,
        }

    def __repr__(self) -> str:
        return (
            f"MemoryQueryResult(matches={self.total_matches}, "
            f"success_rate={self.success_rate:.0%}, "
            f"avg_gain={self.avg_gain:+.2f})"
        )


@dataclass
class MemoryInsight:
    """内存洞察。

    Attributes:
        total_records:        总记录数
        overall_success_rate: 总体成功率
        overall_avg_gain:     总体平均适应度提升
        by_mutation_type:     mutation_type → 统计
        by_category:          category → 统计
        best_mutation:        最佳突变类型
        worst_mutation:       最差突变类型
        top_success_patterns: 最成功模式
        top_failure_patterns: 最失败模式
        recommendation:       全局推荐
        generated_at:         生成时间
    """

    total_records: int = 0
    overall_success_rate: float = 0.0
    overall_avg_gain: float = 0.0
    by_mutation_type: dict[str, MemoryQueryResult] = field(default_factory=dict)
    by_category: dict[str, MemoryQueryResult] = field(default_factory=dict)
    best_mutation: str = ""
    worst_mutation: str = ""
    top_success_patterns: list[str] = field(default_factory=list)
    top_failure_patterns: list[str] = field(default_factory=list)
    recommendation: str = ""
    generated_at: str = ""

    def __post_init__(self) -> None:
        if not self.generated_at:
            self.generated_at = _now()

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_records": self.total_records,
            "overall_success_rate": self.overall_success_rate,
            "overall_avg_gain": self.overall_avg_gain,
            "best_mutation": self.best_mutation,
            "worst_mutation": self.worst_mutation,
            "top_success_patterns": self.top_success_patterns,
            "top_failure_patterns": self.top_failure_patterns,
            "recommendation": self.recommendation,
            "generated_at": self.generated_at,
        }

    def __repr__(self) -> str:
        return (
            f"MemoryInsight(records={self.total_records}, "
            f"success_rate={self.overall_success_rate:.0%}, "
            f"best={self.best_mutation})"
        )


@dataclass
class MemoryStats:
    """内存统计。"""

    total_records: int = 0
    success_count: int = 0
    neutral_count: int = 0
    failure_count: int = 0
    retired_count: int = 0
    unique_genomes: int = 0
    unique_mutation_types: int = 0
    unique_categories: int = 0
    avg_fitness_gain: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_records": self.total_records,
            "success_count": self.success_count,
            "neutral_count": self.neutral_count,
            "failure_count": self.failure_count,
            "retired_count": self.retired_count,
            "unique_genomes": self.unique_genomes,
            "unique_mutation_types": self.unique_mutation_types,
            "unique_categories": self.unique_categories,
            "avg_fitness_gain": self.avg_fitness_gain,
        }

    def __repr__(self) -> str:
        return (
            f"MemoryStats(total={self.total_records}, "
            f"success={self.success_count}, "
            f"failure={self.failure_count})"
        )