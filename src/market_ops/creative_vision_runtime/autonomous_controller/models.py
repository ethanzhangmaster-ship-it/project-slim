"""E11.5.1 — Controller Core Models。

CycleStatus:     循环状态枚举
CycleRecord:     单次进化循环的完整记录
CycleResult:     循环结果摘要
ControllerConfig: 控制器配置
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CycleStatus(str, Enum):
    """进化循环状态。"""
    IDLE = "idle"            # 等待触发
    ANALYZING = "analyzing"  # 视觉分析中
    DECIDING = "deciding"    # 决策生成中
    MUTATING = "mutating"    # 突变计划生成中
    EXECUTING = "executing"  # 突变执行中
    COMPLETED = "completed"  # 循环完成
    FAILED = "failed"        # 循环失败


@dataclass
class CycleRecord:
    """单次自主进化循环的完整记录。

    记录从 Vision Analysis 到 Genome Mutation 的完整链路。

    Attributes:
        cycle_id:          循环 ID
        cycle_number:      循环序号
        status:            当前状态
        input_asset_ids:   输入素材 ID 列表
        winner_asset_ids:  Winner 素材 ID 列表
        insights:          asset_id → VisionInsight 映射
        winner_dna:        Winner 视觉 DNA
        decisions:         asset_id → VisionDecision 映射
        mutation_plans:    asset_id → VisionMutationPlan 映射
        mutation_tasks:    asset_id → GenomeMutationTask 映射
        mutated_genomes:   genome_id → genome dict 映射
        started_at:        开始时间
        completed_at:      完成时间
        error_message:     错误信息
        stats:             统计信息
    """

    cycle_id: str = ""
    cycle_number: int = 0
    status: CycleStatus = CycleStatus.IDLE

    input_asset_ids: list[str] = field(default_factory=list)
    winner_asset_ids: list[str] = field(default_factory=list)

    insights: dict[str, Any] = field(default_factory=dict)
    winner_dna: Any = None
    decisions: dict[str, Any] = field(default_factory=dict)
    mutation_plans: dict[str, Any] = field(default_factory=dict)
    mutation_tasks: dict[str, Any] = field(default_factory=dict)
    mutated_genomes: dict[str, Any] = field(default_factory=dict)

    started_at: str = ""
    completed_at: str = ""
    error_message: str = ""

    stats: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.cycle_id:
            self.cycle_id = f"cycle_{uuid.uuid4().hex[:12]}"

    # ── Properties ──────────────────────────────────────

    @property
    def asset_count(self) -> int:
        return len(self.input_asset_ids)

    @property
    def insight_count(self) -> int:
        return len([v for v in self.insights.values() if v is not None])

    @property
    def decision_count(self) -> int:
        return len(self.decisions)

    @property
    def plan_count(self) -> int:
        return len(self.mutation_plans)

    @property
    def task_count(self) -> int:
        return len(self.mutation_tasks)

    @property
    def genome_count(self) -> int:
        return len(self.mutated_genomes)

    @property
    def total_mutations(self) -> int:
        return sum(
            t.mutation_count if hasattr(t, "mutation_count") else 0
            for t in self.mutation_tasks.values()
        )

    @property
    def is_completed(self) -> bool:
        return self.status == CycleStatus.COMPLETED

    @property
    def is_failed(self) -> bool:
        return self.status == CycleStatus.FAILED

    @property
    def duration(self) -> str:
        if not self.started_at or not self.completed_at:
            return "N/A"
        try:
            start = datetime.fromisoformat(self.started_at)
            end = datetime.fromisoformat(self.completed_at)
            delta = end - start
            return f"{delta.total_seconds():.2f}s"
        except (ValueError, TypeError):
            return "N/A"

    # ── Methods ─────────────────────────────────────────

    def mark_started(self) -> None:
        self.status = CycleStatus.ANALYZING
        self.started_at = _now()

    def mark_completed(self) -> None:
        self.status = CycleStatus.COMPLETED
        self.completed_at = _now()

    def mark_failed(self, error: str) -> None:
        self.status = CycleStatus.FAILED
        self.error_message = error
        self.completed_at = _now()

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "cycle_number": self.cycle_number,
            "status": self.status.value,
            "input_asset_ids": self.input_asset_ids,
            "winner_asset_ids": self.winner_asset_ids,
            "asset_count": self.asset_count,
            "insight_count": self.insight_count,
            "decision_count": self.decision_count,
            "plan_count": self.plan_count,
            "task_count": self.task_count,
            "genome_count": self.genome_count,
            "total_mutations": self.total_mutations,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration": self.duration,
            "error_message": self.error_message,
            "stats": self.stats,
        }

    def __repr__(self) -> str:
        return (
            f"CycleRecord({self.cycle_number}, "
            f"status={self.status.value}, "
            f"assets={self.asset_count}, "
            f"mutations={self.total_mutations})"
        )


@dataclass
class CycleResult:
    """循环结果摘要。"""

    cycle_id: str = ""
    cycle_number: int = 0
    status: CycleStatus = CycleStatus.IDLE
    asset_count: int = 0
    decisions_made: int = 0
    plans_created: int = 0
    tasks_generated: int = 0
    genomes_mutated: int = 0
    total_mutations: int = 0
    duration: str = ""
    error: str = ""

    @classmethod
    def from_record(cls, record: CycleRecord) -> CycleResult:
        return cls(
            cycle_id=record.cycle_id,
            cycle_number=record.cycle_number,
            status=record.status,
            asset_count=record.asset_count,
            decisions_made=record.decision_count,
            plans_created=record.plan_count,
            tasks_generated=record.task_count,
            genomes_mutated=record.genome_count,
            total_mutations=record.total_mutations,
            duration=record.duration,
            error=record.error_message,
        )

    def __repr__(self) -> str:
        return (
            f"CycleResult(#{self.cycle_number}, "
            f"{self.status.value}, "
            f"{self.total_mutations} mutations)"
        )


@dataclass
class ControllerConfig:
    """控制器配置。"""

    max_cycles: int = 10
    min_confidence: float = 0.3
    auto_evolve: bool = True
    stop_on_no_mutations: bool = True
    stop_on_max_cycles: bool = True

    def __post_init__(self) -> None:
        if self.max_cycles < 1:
            raise ValueError("max_cycles must be >= 1")
        if not 0.0 <= self.min_confidence <= 1.0:
            raise ValueError("min_confidence must be in [0, 1]")

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_cycles": self.max_cycles,
            "min_confidence": self.min_confidence,
            "auto_evolve": self.auto_evolve,
            "stop_on_no_mutations": self.stop_on_no_mutations,
            "stop_on_max_cycles": self.stop_on_max_cycles,
        }

    def __repr__(self) -> str:
        return (
            f"ControllerConfig(max_cycles={self.max_cycles}, "
            f"min_conf={self.min_confidence:.2f})"
        )