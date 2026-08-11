"""E11.5.4 Feedback Loop Schema — 进化反馈闭环数据模型。

定义 Evolution Feedback Loop 的稳定契约：

  LoopStatus               — 循环状态 (CREATED → RUNNING → WAITING_FEEDBACK → EVOLVING → COMPLETED)
  EvolutionFeedbackEvent   — 一次市场反馈事件
  FeedbackLoopState        — 循环状态记录
  EvolutionEventStore      — 事件存储（演化时间线）

数据流：
  PerformanceFeedback → FeedbackLoopController → EvolutionFeedbackEvent → EventStore
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════
# LoopStatus — 循环状态
# ═══════════════════════════════════════════════════════════

class LoopStatus(Enum):
    """进化反馈循环状态。

    CREATED         — 已创建，等待首次运行
    RUNNING         — 正在执行
    WAITING_FEEDBACK — 等待市场数据反馈
    EVOLVING        — 正在进化（Mutation + Selection）
    COMPLETED       — 完成
    FAILED          — 失败
    """
    CREATED = "created"
    RUNNING = "running"
    WAITING_FEEDBACK = "waiting_feedback"
    EVOLVING = "evolving"
    COMPLETED = "completed"
    FAILED = "failed"


# ═══════════════════════════════════════════════════════════
# EvolutionFeedbackEvent — 市场反馈事件
# ═══════════════════════════════════════════════════════════

@dataclass
class EvolutionFeedbackEvent:
    """记录一次市场反馈事件。

    例如：
        EvolutionFeedbackEvent(
            genome_id="genome_001",
            creative_id="creative_005",
            feedback_id="fb_abc123",
            fitness_score=0.87,
            generation=3,
        )
    """
    event_id: str = field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:8]}")
    genome_id: str = ""
    creative_id: str = ""
    feedback_id: str = ""
    signal_id: str = ""
    fitness_id: str = ""
    fitness_score: float = 0.0
    generation: int = 0
    action: str = ""               # "feedback_processed" | "genome_updated" | "population_ranked" | "selection_applied"
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "genome_id": self.genome_id,
            "creative_id": self.creative_id,
            "feedback_id": self.feedback_id,
            "signal_id": self.signal_id,
            "fitness_id": self.fitness_id,
            "fitness_score": self.fitness_score,
            "generation": self.generation,
            "action": self.action,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvolutionFeedbackEvent:
        return cls(
            event_id=data.get("event_id", ""),
            genome_id=data.get("genome_id", ""),
            creative_id=data.get("creative_id", ""),
            feedback_id=data.get("feedback_id", ""),
            signal_id=data.get("signal_id", ""),
            fitness_id=data.get("fitness_id", ""),
            fitness_score=data.get("fitness_score", 0.0),
            generation=data.get("generation", 0),
            action=data.get("action", ""),
            details=data.get("details", {}),
            timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else datetime.now(timezone.utc),
        )

    def __repr__(self) -> str:
        return (
            f"EvolutionFeedbackEvent(gen={self.generation}, "
            f"genome={self.genome_id!r}, "
            f"fitness={self.fitness_score}, "
            f"action={self.action!r})"
        )


# ═══════════════════════════════════════════════════════════
# FeedbackLoopState — 循环状态
# ═══════════════════════════════════════════════════════════

@dataclass
class FeedbackLoopState:
    """记录当前进化反馈循环的状态。

    例如：
        FeedbackLoopState(
            loop_id="loop_001",
            generation=3,
            status=LoopStatus.EVOLVING,
            processed_count=15,
            best_fitness=0.91,
            best_genome_id="genome_021",
        )
    """
    loop_id: str = field(default_factory=lambda: f"loop_{uuid.uuid4().hex[:8]}")
    generation: int = 0
    status: LoopStatus = LoopStatus.CREATED
    processed_count: int = 0
    best_fitness: float = 0.0
    best_genome_id: str = ""
    population_id: str = ""
    last_action: str = ""
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # ── 生命周期 ──────────────────────────────────────

    def start(self) -> None:
        self.status = LoopStatus.RUNNING
        self.started_at = datetime.now(timezone.utc)

    def wait_for_feedback(self) -> None:
        self.status = LoopStatus.WAITING_FEEDBACK

    def evolve(self) -> None:
        self.status = LoopStatus.EVOLVING

    def complete(self) -> None:
        self.status = LoopStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)

    def fail(self) -> None:
        self.status = LoopStatus.FAILED
        self.completed_at = datetime.now(timezone.utc)

    # ── 便捷属性 ──────────────────────────────────────

    @property
    def is_active(self) -> bool:
        return self.status in (LoopStatus.RUNNING, LoopStatus.WAITING_FEEDBACK, LoopStatus.EVOLVING)

    @property
    def is_terminal(self) -> bool:
        return self.status in (LoopStatus.COMPLETED, LoopStatus.FAILED)

    # ── 序列化 ────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "loop_id": self.loop_id,
            "generation": self.generation,
            "status": self.status.value,
            "processed_count": self.processed_count,
            "best_fitness": self.best_fitness,
            "best_genome_id": self.best_genome_id,
            "population_id": self.population_id,
            "last_action": self.last_action,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FeedbackLoopState:
        started_at = data.get("started_at")
        completed_at = data.get("completed_at")
        return cls(
            loop_id=data.get("loop_id", ""),
            generation=data.get("generation", 0),
            status=LoopStatus(data.get("status", "created")),
            processed_count=data.get("processed_count", 0),
            best_fitness=data.get("best_fitness", 0.0),
            best_genome_id=data.get("best_genome_id", ""),
            population_id=data.get("population_id", ""),
            last_action=data.get("last_action", ""),
            started_at=datetime.fromisoformat(started_at) if started_at else None,
            completed_at=datetime.fromisoformat(completed_at) if completed_at else None,
        )

    def __repr__(self) -> str:
        return (
            f"FeedbackLoopState(loop={self.loop_id!r}, "
            f"gen={self.generation}, "
            f"best={self.best_fitness}, "
            f"status={self.status.value})"
        )


# ═══════════════════════════════════════════════════════════
# EvolutionEventStore — 事件存储
# ═══════════════════════════════════════════════════════════

class EvolutionEventStore:
    """进化事件存储。

    记录完整的演化时间线，用于：
      - 分析 DNA 演化路径
      - 回滚优秀版本
      - 找 Winner Pattern

    Usage:
        store = EvolutionEventStore()
        store.add_event(event)
        timeline = store.get_timeline()
    """

    def __init__(self) -> None:
        self._events: list[EvolutionFeedbackEvent] = []

    def add_event(self, event: EvolutionFeedbackEvent) -> None:
        self._events.append(event)

    def get_timeline(self) -> list[EvolutionFeedbackEvent]:
        """获取按时间排序的事件时间线。"""
        return sorted(self._events, key=lambda e: e.timestamp)

    def get_by_generation(self, generation: int) -> list[EvolutionFeedbackEvent]:
        """按代数获取事件。"""
        return [e for e in self._events if e.generation == generation]

    def get_by_genome(self, genome_id: str) -> list[EvolutionFeedbackEvent]:
        """按 Genome ID 获取事件。"""
        return [e for e in self._events if e.genome_id == genome_id]

    def get_by_creative(self, creative_id: str) -> list[EvolutionFeedbackEvent]:
        """按 Creative ID 获取事件。"""
        return [e for e in self._events if e.creative_id == creative_id]

    def get_best_events(self) -> list[EvolutionFeedbackEvent]:
        """获取 fitness 最高的事件（Top 10）。"""
        sorted_events = sorted(self._events, key=lambda e: e.fitness_score, reverse=True)
        return sorted_events[:10]

    @property
    def event_count(self) -> int:
        return len(self._events)

    @property
    def best_score(self) -> float:
        if not self._events:
            return 0.0
        return max(e.fitness_score for e in self._events)

    def clear(self) -> None:
        self._events.clear()

    def to_dict(self) -> dict[str, Any]:
        return {
            "events": [e.to_dict() for e in self._events],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvolutionEventStore:
        store = cls()
        for e_data in data.get("events", []):
            store._events.append(EvolutionFeedbackEvent.from_dict(e_data))
        return store

    def __repr__(self) -> str:
        return f"EvolutionEventStore(events={self.event_count}, best={self.best_score})"