"""E11.4.2 Generation Schema — 多代进化数据模型。

定义多代进化循环的稳定契约：

  GenerationStatus  — 单代状态 (CREATED → RUNNING → COMPLETED → FAILED)
  GenerationRecord  — 单代记录 (generation, population_id, best_genome_id, best_score)
  EvolutionHistory  — 进化历史 (多代记录汇总)

数据流：
  GenerationManager → GenerationRecord → EvolutionHistory → ConvergenceDetector
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════
# GenerationStatus — 单代状态
# ═══════════════════════════════════════════════════════════

class GenerationStatus(Enum):
    """单代进化状态。

    CREATED   — 已创建，等待执行
    RUNNING   — 正在执行
    COMPLETED — 执行完成
    FAILED    — 执行失败
    """
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# ═══════════════════════════════════════════════════════════
# GenerationRecord — 单代记录
# ═══════════════════════════════════════════════════════════

@dataclass
class GenerationRecord:
    """记录一代进化的完整信息。

    例如：
        GenerationRecord(
            generation=3,
            population_id="pop_003",
            best_genome_id="genome_021",
            best_score=0.91,
        )
    """
    generation: int = 0
    population_id: str = ""
    best_genome_id: str = ""
    best_score: float = 0.0
    avg_score: float = 0.0
    mutation_count: int = 0
    survivor_count: int = 0
    status: GenerationStatus = GenerationStatus.CREATED
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None

    # ── 生命周期 ──────────────────────────────────────

    def start(self) -> None:
        """标记开始执行。"""
        self.status = GenerationStatus.RUNNING
        self.created_at = datetime.now(timezone.utc)

    def complete(self) -> None:
        """标记完成。"""
        self.status = GenerationStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)

    def fail(self) -> None:
        """标记失败。"""
        self.status = GenerationStatus.FAILED
        self.completed_at = datetime.now(timezone.utc)

    # ── 序列化 ────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "generation": self.generation,
            "population_id": self.population_id,
            "best_genome_id": self.best_genome_id,
            "best_score": self.best_score,
            "avg_score": self.avg_score,
            "mutation_count": self.mutation_count,
            "survivor_count": self.survivor_count,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GenerationRecord:
        created_at = data.get("created_at")
        completed_at = data.get("completed_at")
        return cls(
            generation=data.get("generation", 0),
            population_id=data.get("population_id", ""),
            best_genome_id=data.get("best_genome_id", ""),
            best_score=data.get("best_score", 0.0),
            avg_score=data.get("avg_score", 0.0),
            mutation_count=data.get("mutation_count", 0),
            survivor_count=data.get("survivor_count", 0),
            status=GenerationStatus(data.get("status", "created")),
            created_at=datetime.fromisoformat(created_at) if created_at else datetime.now(timezone.utc),
            completed_at=datetime.fromisoformat(completed_at) if completed_at else None,
        )

    def __repr__(self) -> str:
        return (
            f"GenerationRecord(gen={self.generation}, "
            f"best={self.best_genome_id!r}, "
            f"score={self.best_score}, "
            f"status={self.status.value})"
        )


# ═══════════════════════════════════════════════════════════
# EvolutionHistory — 进化历史
# ═══════════════════════════════════════════════════════════

@dataclass
class EvolutionHistory:
    """保存一次进化运行的全部世代记录。

    例如：
        history = EvolutionHistory(run_id="evo_001")
        history.add_generation(record)
        history.latest()  # 最新一代
        history.best()    # 最优一代
    """
    run_id: str = field(default_factory=lambda: f"evo_{uuid.uuid4().hex[:8]}")
    generations: list[GenerationRecord] = field(default_factory=list)

    # ── 查询 ──────────────────────────────────────────

    @property
    def generation_count(self) -> int:
        """已完成的代数。"""
        return len(self.generations)

    @property
    def score_progression(self) -> list[float]:
        """各代最佳评分进展。"""
        return [g.best_score for g in self.generations]

    def highest_score(self) -> float:
        """历史最高评分。"""
        if not self.generations:
            return 0.0
        return max(g.best_score for g in self.generations)

    def latest(self) -> GenerationRecord | None:
        """最新一代记录。"""
        return self.generations[-1] if self.generations else None

    def best(self) -> GenerationRecord | None:
        """评分最高的一代。"""
        if not self.generations:
            return None
        return max(self.generations, key=lambda g: g.best_score)

    def get_generation(self, generation: int) -> GenerationRecord | None:
        """按代数查找记录。"""
        for g in self.generations:
            if g.generation == generation:
                return g
        return None

    # ── 写入 ──────────────────────────────────────────

    def add_generation(self, record: GenerationRecord) -> None:
        """添加一代记录。

        Args:
            record: GenerationRecord 实例
        """
        self.generations.append(record)

    def clear(self) -> None:
        """清空历史。"""
        self.generations.clear()

    # ── 序列化 ────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "generations": [g.to_dict() for g in self.generations],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvolutionHistory:
        generations = [GenerationRecord.from_dict(g) for g in data.get("generations", [])]
        return cls(
            run_id=data.get("run_id", ""),
            generations=generations,
        )

    def __repr__(self) -> str:
        return (
            f"EvolutionHistory(run_id={self.run_id!r}, "
            f"gen={self.generation_count}, "
            f"best={self.highest_score()})"
        )