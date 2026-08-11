"""E12.7.6 Loop Models — GrowthLoop, LoopState, LoopResult, CycleRecord."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class LoopState(str, Enum):
    """增长循环状态."""
    IDLE = "idle"
    OBSERVING = "observing"
    ANALYZING = "analyzing"
    STRATEGIZING = "strategizing"
    EXECUTING = "executing"
    MEASURING = "measuring"
    LEARNING = "learning"
    OPTIMIZING = "optimizing"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class CycleOutcome(str, Enum):
    """循环结果."""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"
    ABORTED = "aborted"


class TriggerType(str, Enum):
    """触发类型."""
    SCHEDULED = "scheduled"
    PERFORMANCE_DROP = "performance_drop"
    OPPORTUNITY = "opportunity"
    MANUAL = "manual"
    CONTINUOUS = "continuous"


# ── CycleRecord ──────────────────────────────────────────────


@dataclass
class CycleRecord:
    """单次循环记录."""

    cycle_id: str = field(default_factory=lambda: f"CYC_{uuid.uuid4().hex[:8].upper()}")
    cycle_number: int = 0
    state: LoopState = LoopState.IDLE
    outcome: CycleOutcome = CycleOutcome.PARTIAL

    observation: dict[str, Any] = field(default_factory=dict)
    diagnosis: dict[str, Any] = field(default_factory=dict)
    hypothesis: dict[str, Any] = field(default_factory=dict)
    strategy_id: str = ""
    execution_id: str = ""
    execution_result: dict[str, Any] = field(default_factory=dict)
    feedback: dict[str, Any] = field(default_factory=dict)
    learning: dict[str, Any] = field(default_factory=dict)

    started_at: datetime | None = None
    completed_at: datetime | None = None

    errors: list[str] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0.0

    @property
    def is_successful(self) -> bool:
        return self.outcome == CycleOutcome.SUCCESS

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "cycle_number": self.cycle_number,
            "state": self.state.value,
            "outcome": self.outcome.value,
            "observation": self.observation,
            "diagnosis": self.diagnosis,
            "hypothesis": self.hypothesis,
            "strategy_id": self.strategy_id,
            "execution_id": self.execution_id,
            "execution_result": self.execution_result,
            "feedback": self.feedback,
            "learning": self.learning,
            "duration_seconds": self.duration_seconds,
            "is_successful": self.is_successful,
            "errors": self.errors,
        }


# ── GrowthLoop ───────────────────────────────────────────────


@dataclass
class GrowthLoop:
    """一次完整增长循环 — 包含多个 Cycle."""

    loop_id: str = field(default_factory=lambda: f"LOOP_{uuid.uuid4().hex[:8].upper()}")
    product_id: str = ""
    current_cycle: int = 0
    max_cycles: int = 0  # 0 = unlimited
    state: LoopState = LoopState.IDLE
    trigger_type: TriggerType = TriggerType.SCHEDULED

    cycles: list[CycleRecord] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    started_at: datetime | None = None
    completed_at: datetime | None = None
    paused_at: datetime | None = None

    config: dict[str, Any] = field(default_factory=dict)

    @property
    def cycle_count(self) -> int:
        return len(self.cycles)

    @property
    def is_running(self) -> bool:
        return self.state not in {LoopState.IDLE, LoopState.COMPLETED, LoopState.FAILED, LoopState.PAUSED}

    @property
    def is_complete(self) -> bool:
        return self.state in {LoopState.COMPLETED, LoopState.FAILED}

    @property
    def success_rate(self) -> float:
        if not self.cycles:
            return 0.0
        successful = sum(1 for c in self.cycles if c.is_successful)
        return successful / len(self.cycles)

    @property
    def last_cycle(self) -> CycleRecord | None:
        return self.cycles[-1] if self.cycles else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "loop_id": self.loop_id,
            "product_id": self.product_id,
            "current_cycle": self.current_cycle,
            "max_cycles": self.max_cycles,
            "state": self.state.value,
            "trigger_type": self.trigger_type.value,
            "cycle_count": self.cycle_count,
            "success_rate": self.success_rate,
            "is_running": self.is_running,
            "is_complete": self.is_complete,
            "metrics": self.metrics,
            "cycles": [c.to_dict() for c in self.cycles],
            "config": self.config,
        }


# ── LoopResult ───────────────────────────────────────────────


@dataclass
class LoopResult:
    """循环结束结果."""

    loop_id: str = ""
    success: bool = False
    total_cycles: int = 0
    successful_cycles: int = 0
    failed_cycles: int = 0

    growth_delta: float = 0.0
    roi_change: float = 0.0
    avg_roas: float = 0.0

    lessons: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    patterns_discovered: int = 0
    strategies_generated: int = 0

    final_state: LoopState = LoopState.COMPLETED
    errors: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        return (
            f"Loop {self.loop_id}: {self.total_cycles} cycles, "
            f"{self.successful_cycles} success, {self.failed_cycles} failed, "
            f"ROI change: {self.roi_change:+.2%}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "loop_id": self.loop_id,
            "success": self.success,
            "total_cycles": self.total_cycles,
            "successful_cycles": self.successful_cycles,
            "failed_cycles": self.failed_cycles,
            "growth_delta": self.growth_delta,
            "roi_change": self.roi_change,
            "avg_roas": self.avg_roas,
            "lessons": self.lessons,
            "next_actions": self.next_actions,
            "patterns_discovered": self.patterns_discovered,
            "strategies_generated": self.strategies_generated,
            "final_state": self.final_state.value,
            "errors": self.errors,
            "summary": self.summary,
        }


# ── GrowthMetrics ────────────────────────────────────────────


@dataclass
class GrowthMetrics:
    """增长指标快照."""

    product_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    roas: float = 0.0
    ctr: float = 0.0
    cvr: float = 0.0
    spend: float = 0.0
    revenue: float = 0.0
    installs: int = 0
    impressions: int = 0
    retention_d7: float = 0.0
    payer_rate: float = 0.0

    active_creatives: int = 0
    active_experiments: int = 0
    fatigue_score: float = 0.0

    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "product_id": self.product_id,
            "roas": self.roas,
            "ctr": self.ctr,
            "cvr": self.cvr,
            "spend": self.spend,
            "revenue": self.revenue,
            "installs": self.installs,
            "impressions": self.impressions,
            "retention_d7": self.retention_d7,
            "payer_rate": self.payer_rate,
            "active_creatives": self.active_creatives,
            "active_experiments": self.active_experiments,
            "fatigue_score": self.fatigue_score,
            "extra": self.extra,
        }