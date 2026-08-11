"""E11.3.2 Population Schema — 基因组种群数据模型。

定义 Population 管理的稳定契约：

  PopulationStatus  — 种群状态 (CREATED → ACTIVE → EVALUATED → ARCHIVED)
  GenomePopulation  — 进化种群 (population_id, generation, genome_ids, status)
  PopulationMember  — 种群成员 (genome_id, fitness_score, rank, is_elite)

数据流：
  Genome Pool → Population → Fitness Evaluation → Elite Selection
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .fitness_schema import FitnessScore


# ═══════════════════════════════════════════════════════════
# PopulationStatus — 种群状态
# ═══════════════════════════════════════════════════════════

class PopulationStatus(Enum):
    """种群生命周期状态。

    CREATED   — 已创建，尚未开始评估
    ACTIVE    — 活跃中，正在评估或变异
    EVALUATED — 已评估完成，可以 Selection
    ARCHIVED  — 已归档，不再活跃
    """
    CREATED = "created"
    ACTIVE = "active"
    EVALUATED = "evaluated"
    ARCHIVED = "archived"


# ═══════════════════════════════════════════════════════════
# PopulationMember — 种群成员
# ═══════════════════════════════════════════════════════════

@dataclass
class PopulationMember:
    """描述 Genome 在种群中的状态。

    例如：
        PopulationMember(
            genome_id="genome_001",
            fitness=FitnessScore(...),
            rank=1,
            is_elite=True,
        )
    """
    genome_id: str
    fitness: FitnessScore | None = None
    rank: int = 0
    is_elite: bool = False

    @property
    def score(self) -> float:
        """成员的评分值。"""
        return self.fitness.score if self.fitness else 0.0

    @property
    def is_healthy(self) -> bool:
        """成员是否健康。"""
        return self.fitness.is_healthy if self.fitness else False

    def to_dict(self) -> dict[str, Any]:
        return {
            "genome_id": self.genome_id,
            "fitness": self.fitness.to_dict() if self.fitness else None,
            "rank": self.rank,
            "is_elite": self.is_elite,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PopulationMember:
        fitness_data = data.get("fitness")
        fitness = FitnessScore.from_dict(fitness_data) if fitness_data else None
        return cls(
            genome_id=data["genome_id"],
            fitness=fitness,
            rank=data.get("rank", 0),
            is_elite=data.get("is_elite", False),
        )

    def __repr__(self) -> str:
        elite = "ELITE" if self.is_elite else ""
        return f"PopulationMember({self.genome_id!r}, score={self.score}, rank={self.rank} {elite})"


# ═══════════════════════════════════════════════════════════
# GenomePopulation — 进化种群
# ═══════════════════════════════════════════════════════════

@dataclass
class GenomePopulation:
    """一个进化种群，包含多个 Genome。

    例如：
        population = GenomePopulation(
            population_id="pop_001",
            generation=1,
            members=[
                PopulationMember(genome_id="genome_001", ...),
                PopulationMember(genome_id="genome_002", ...),
            ],
        )
    """
    population_id: str = field(default_factory=lambda: f"pop_{uuid.uuid4().hex[:8]}")
    generation: int = 1
    members: list[PopulationMember] = field(default_factory=list)
    status: PopulationStatus = PopulationStatus.CREATED
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ── 属性 ──────────────────────────────────────────

    @property
    def genome_ids(self) -> list[str]:
        """所有成员的 genome_id 列表。"""
        return [m.genome_id for m in self.members]

    @property
    def size(self) -> int:
        """种群大小。"""
        return len(self.members)

    @property
    def elite_count(self) -> int:
        """精英成员数量。"""
        return sum(1 for m in self.members if m.is_elite)

    @property
    def avg_score(self) -> float:
        """种群平均评分。"""
        if not self.members:
            return 0.0
        return round(sum(m.score for m in self.members) / len(self.members), 4)

    @property
    def best_score(self) -> float:
        """种群最高评分。"""
        if not self.members:
            return 0.0
        return max(m.score for m in self.members)

    @property
    def best_member(self) -> PopulationMember | None:
        """评分最高的成员。"""
        if not self.members:
            return None
        return max(self.members, key=lambda m: m.score)

    # ── 查询 ──────────────────────────────────────────

    def get_member(self, genome_id: str) -> PopulationMember | None:
        """按 genome_id 查找成员。"""
        for m in self.members:
            if m.genome_id == genome_id:
                return m
        return None

    def has_genome(self, genome_id: str) -> bool:
        """检查 genome_id 是否在种群中。"""
        return self.get_member(genome_id) is not None

    def get_top_candidates(self, top_k: int = 5) -> list[PopulationMember]:
        """获取评分最高的 top_k 个成员。

        Args:
            top_k: 返回数量

        Returns:
            按评分降序排列的成员列表
        """
        sorted_members = sorted(self.members, key=lambda m: m.score, reverse=True)
        return sorted_members[:top_k]

    def get_elite_candidates(self) -> list[PopulationMember]:
        """获取所有精英成员。"""
        return [m for m in self.members if m.is_elite]

    def get_healthy_candidates(self) -> list[PopulationMember]:
        """获取所有健康成员 (score >= 0.5)。"""
        return [m for m in self.members if m.is_healthy]

    # ── 序列化 ────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "population_id": self.population_id,
            "generation": self.generation,
            "members": [m.to_dict() for m in self.members],
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GenomePopulation:
        members = [PopulationMember.from_dict(m) for m in data.get("members", [])]
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        return cls(
            population_id=data.get("population_id", ""),
            generation=data.get("generation", 1),
            members=members,
            status=PopulationStatus(data.get("status", "created")),
            created_at=created_at or datetime.now(timezone.utc),
        )

    def __repr__(self) -> str:
        return (
            f"GenomePopulation(id={self.population_id!r}, "
            f"gen={self.generation}, size={self.size}, "
            f"status={self.status.value}, avg={self.avg_score})"
        )