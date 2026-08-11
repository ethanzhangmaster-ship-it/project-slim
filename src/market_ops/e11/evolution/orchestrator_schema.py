"""E11.4.1 Orchestrator Schema — 进化调度器数据模型。

定义 Evolution Orchestrator 的稳定契约：

  EvolutionStatus  — 进化任务状态 (CREATED → RUNNING → COMPLETED → FAILED)
  EvolutionConfig  — 进化配置 (population_size, max_generations, mutation_rate, elite_count)
  EvolutionRun     — 一次进化执行实例
  GenerationResult — 单代执行结果
  EvolutionResult  — 最终进化输出

数据流：
  EvolutionConfig → EvolutionOrchestrator.run() → EvolutionRun → EvolutionResult
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════
# EvolutionStatus — 进化任务状态
# ═══════════════════════════════════════════════════════════

class EvolutionStatus(Enum):
    """进化任务生命周期状态。

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
# EvolutionConfig — 进化配置
# ═══════════════════════════════════════════════════════════

@dataclass
class EvolutionConfig:
    """定义一次进化任务的配置参数。

    例如：
        EvolutionConfig(
            population_size=50,
            max_generations=10,
            mutation_rate=0.3,
            elite_count=5,
        )
    """
    population_size: int = 50
    max_generations: int = 10
    mutation_rate: float = 0.3
    elite_count: int = 5
    min_fitness_threshold: float = 0.5
    selection_mode: str = "elite"  # "elite" | "threshold" | "diversity"

    def to_dict(self) -> dict[str, Any]:
        return {
            "population_size": self.population_size,
            "max_generations": self.max_generations,
            "mutation_rate": self.mutation_rate,
            "elite_count": self.elite_count,
            "min_fitness_threshold": self.min_fitness_threshold,
            "selection_mode": self.selection_mode,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvolutionConfig:
        return cls(
            population_size=data.get("population_size", 50),
            max_generations=data.get("max_generations", 10),
            mutation_rate=data.get("mutation_rate", 0.3),
            elite_count=data.get("elite_count", 5),
            min_fitness_threshold=data.get("min_fitness_threshold", 0.5),
            selection_mode=data.get("selection_mode", "elite"),
        )

    def __repr__(self) -> str:
        return (
            f"EvolutionConfig(pop_size={self.population_size}, "
            f"max_gen={self.max_generations}, "
            f"mutation_rate={self.mutation_rate}, "
            f"elite={self.elite_count})"
        )


# ═══════════════════════════════════════════════════════════
# EvolutionRun — 进化执行实例
# ═══════════════════════════════════════════════════════════

@dataclass
class EvolutionRun:
    """一次进化执行的运行实例。

    追踪当前世代、状态和时间信息。
    """
    run_id: str = field(default_factory=lambda: f"evo_{uuid.uuid4().hex[:8]}")
    population_id: str = ""
    generation: int = 0
    status: EvolutionStatus = EvolutionStatus.CREATED
    config: EvolutionConfig | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def start(self) -> None:
        """标记开始运行。"""
        self.status = EvolutionStatus.RUNNING
        self.started_at = datetime.now(timezone.utc)

    def complete(self) -> None:
        """标记完成。"""
        self.status = EvolutionStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)

    def fail(self) -> None:
        """标记失败。"""
        self.status = EvolutionStatus.FAILED
        self.completed_at = datetime.now(timezone.utc)

    @property
    def is_active(self) -> bool:
        """是否正在运行。"""
        return self.status == EvolutionStatus.RUNNING

    @property
    def elapsed_seconds(self) -> float | None:
        """运行耗时（秒）。"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "population_id": self.population_id,
            "generation": self.generation,
            "status": self.status.value,
            "config": self.config.to_dict() if self.config else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvolutionRun:
        config_data = data.get("config")
        started = data.get("started_at")
        completed = data.get("completed_at")
        return cls(
            run_id=data.get("run_id", ""),
            population_id=data.get("population_id", ""),
            generation=data.get("generation", 0),
            status=EvolutionStatus(data.get("status", "created")),
            config=EvolutionConfig.from_dict(config_data) if config_data else None,
            started_at=datetime.fromisoformat(started) if started else None,
            completed_at=datetime.fromisoformat(completed) if completed else None,
        )

    def __repr__(self) -> str:
        return (
            f"EvolutionRun(id={self.run_id!r}, gen={self.generation}, "
            f"status={self.status.value})"
        )


# ═══════════════════════════════════════════════════════════
# GenerationResult — 单代执行结果
# ═══════════════════════════════════════════════════════════

@dataclass
class GenerationResult:
    """单代进化周期的执行结果。

    记录一代中：
      - children_created: 产生的子代数量
      - survivors: 存活者数量
      - best_score: 本代最佳评分
      - avg_score: 本代平均评分
    """
    generation: int = 0
    children_created: int = 0
    survivors: int = 0
    best_score: float = 0.0
    avg_score: float = 0.0
    best_genome_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "generation": self.generation,
            "children_created": self.children_created,
            "survivors": self.survivors,
            "best_score": self.best_score,
            "avg_score": self.avg_score,
            "best_genome_id": self.best_genome_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GenerationResult:
        return cls(
            generation=data.get("generation", 0),
            children_created=data.get("children_created", 0),
            survivors=data.get("survivors", 0),
            best_score=data.get("best_score", 0.0),
            avg_score=data.get("avg_score", 0.0),
            best_genome_id=data.get("best_genome_id", ""),
        )

    def __repr__(self) -> str:
        return (
            f"GenerationResult(gen={self.generation}, "
            f"created={self.children_created}, "
            f"survivors={self.survivors}, "
            f"best={self.best_score})"
        )


# ═══════════════════════════════════════════════════════════
# EvolutionResult — 最终进化输出
# ═══════════════════════════════════════════════════════════

@dataclass
class EvolutionResult:
    """一次进化任务的最终输出。

    包含：
      - 最佳 Genome ID
      - 各代历史
      - 成功状态
      - 运行摘要
    """
    run_id: str = ""
    best_genome_id: str = ""
    best_score: float = 0.0
    generations: list[GenerationResult] = field(default_factory=list)
    success: bool = False
    total_generations: int = 0
    total_children: int = 0
    error_message: str = ""

    @property
    def generation_count(self) -> int:
        """执行的代数。"""
        return len(self.generations)

    @property
    def score_progression(self) -> list[float]:
        """各代最佳评分进展。"""
        return [g.best_score for g in self.generations]

    @property
    def has_improvement(self) -> bool:
        """是否有代际改进。"""
        if len(self.generations) < 2:
            return False
        return self.generations[-1].best_score > self.generations[0].best_score

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "best_genome_id": self.best_genome_id,
            "best_score": self.best_score,
            "generations": [g.to_dict() for g in self.generations],
            "success": self.success,
            "total_generations": self.total_generations,
            "total_children": self.total_children,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvolutionResult:
        generations = [GenerationResult.from_dict(g) for g in data.get("generations", [])]
        return cls(
            run_id=data.get("run_id", ""),
            best_genome_id=data.get("best_genome_id", ""),
            best_score=data.get("best_score", 0.0),
            generations=generations,
            success=data.get("success", False),
            total_generations=data.get("total_generations", 0),
            total_children=data.get("total_children", 0),
            error_message=data.get("error_message", ""),
        )

    def __repr__(self) -> str:
        status = "SUCCESS" if self.success else "FAILED"
        return (
            f"EvolutionResult({status}, gen={self.generation_count}, "
            f"best={self.best_genome_id!r}, score={self.best_score})"
        )