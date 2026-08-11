"""E12.7.6 Loop Controller — 统一入口: start_loop / pause / resume / stop / run_cycle / get_status."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .adaptive_scheduler import AdaptiveScheduler, SchedulePolicy, TriggerReason
from .cycle_orchestrator import CycleOrchestrator
from .evolution_manager import EvolutionManager
from .feedback_processor import FeedbackProcessor
from .loop_engine import LoopEngine
from .models import (
    CycleOutcome,
    CycleRecord,
    GrowthLoop,
    GrowthMetrics,
    LoopState,
    TriggerType,
)


class LoopController:
    """循环控制器 — Growth OS 闭环的统一入口.

    提供:
      - start_loop(product_id): 启动增长循环
      - pause(): 暂停
      - resume(): 恢复
      - stop(): 停止
      - run_cycle(): 手动执行单次循环
      - get_status(): 获取状态
    """

    def __init__(
        self,
        engine: LoopEngine | None = None,
        orchestrator: CycleOrchestrator | None = None,
        feedback: FeedbackProcessor | None = None,
        evolution: EvolutionManager | None = None,
        scheduler: AdaptiveScheduler | None = None,
    ):
        self._engine = engine or LoopEngine()
        self._orchestrator = orchestrator or CycleOrchestrator()
        self._feedback = feedback or FeedbackProcessor()
        self._evolution = evolution or EvolutionManager()
        self._scheduler = scheduler or AdaptiveScheduler()

        self._active_loops: dict[str, GrowthLoop] = {}
        self._paused_loops: dict[str, GrowthLoop] = {}
        self._completed_loops: list[GrowthLoop] = []
        self._loop_history: list[GrowthLoop] = []

    @property
    def engine(self) -> LoopEngine:
        return self._engine

    @property
    def orchestrator(self) -> CycleOrchestrator:
        return self._orchestrator

    @property
    def feedback(self) -> FeedbackProcessor:
        return self._feedback

    @property
    def evolution(self) -> EvolutionManager:
        return self._evolution

    @property
    def scheduler(self) -> AdaptiveScheduler:
        return self._scheduler

    @property
    def active_loops(self) -> dict[str, GrowthLoop]:
        return self._active_loops

    @property
    def active_count(self) -> int:
        return len(self._active_loops)

    # ── Loop Lifecycle ────────────────────────────────────────

    def start_loop(
        self,
        product_id: str,
        max_cycles: int = 0,
        trigger_type: TriggerType = TriggerType.SCHEDULED,
        config: dict[str, Any] | None = None,
        metrics: GrowthMetrics | None = None,
    ) -> GrowthLoop:
        """启动增长循环."""
        if metrics:
            self._engine.set_metrics(product_id, metrics)

        loop = self._engine.run(
            product_id=product_id,
            max_cycles=max_cycles,
            trigger_type=trigger_type,
            config=config,
        )

        self._active_loops[loop.loop_id] = loop
        return loop

    def pause(self, loop_id: str) -> bool:
        """暂停循环."""
        loop = self._active_loops.get(loop_id)
        if loop is None:
            return False
        loop.state = LoopState.PAUSED
        loop.paused_at = datetime.now(timezone.utc)
        self._paused_loops[loop_id] = loop
        del self._active_loops[loop_id]
        return True

    def resume(self, loop_id: str) -> GrowthLoop | None:
        """恢复循环."""
        loop = self._paused_loops.pop(loop_id, None)
        if loop is None:
            return None
        loop.state = LoopState.OBSERVING

        # Continue from where it left off
        remaining_cycles = loop.max_cycles - loop.current_cycle
        if remaining_cycles <= 0 and loop.max_cycles > 0:
            loop.state = LoopState.COMPLETED
            loop.completed_at = datetime.now(timezone.utc)
            self._completed_loops.append(loop)
            return loop

        # Run remaining cycles
        for cycle_num in range(loop.current_cycle + 1, loop.max_cycles + 1 if loop.max_cycles > 0 else loop.current_cycle + 2):
            cycle = self._engine.run_cycle(loop, cycle_num)
            loop.cycles.append(cycle)
            loop.current_cycle = cycle_num

        loop.state = LoopState.COMPLETED
        loop.completed_at = datetime.now(timezone.utc)
        self._completed_loops.append(loop)
        return loop

    def stop(self, loop_id: str) -> GrowthLoop | None:
        """停止循环."""
        loop = self._active_loops.pop(loop_id, None)
        if loop is None:
            loop = self._paused_loops.pop(loop_id, None)
        if loop is None:
            return None

        loop.state = LoopState.COMPLETED
        loop.completed_at = datetime.now(timezone.utc)
        self._completed_loops.append(loop)
        self._loop_history.append(loop)
        return loop

    def abort(self, loop_id: str) -> GrowthLoop | None:
        """中止循环（失败状态）."""
        loop = self._active_loops.pop(loop_id, None)
        if loop is None:
            loop = self._paused_loops.pop(loop_id, None)
        if loop is None:
            return None

        loop.state = LoopState.FAILED
        loop.completed_at = datetime.now(timezone.utc)
        self._completed_loops.append(loop)
        self._loop_history.append(loop)
        return loop

    # ── Manual Cycle ──────────────────────────────────────────

    def run_cycle(
        self,
        loop: GrowthLoop,
        cycle_num: int | None = None,
    ) -> CycleRecord:
        """手动执行单次循环."""
        if cycle_num is None:
            cycle_num = loop.current_cycle + 1

        cycle = self._engine.run_cycle(loop, cycle_num)
        loop.cycles.append(cycle)
        loop.current_cycle = cycle_num
        return cycle

    # ── Status ────────────────────────────────────────────────

    def get_status(self, loop_id: str | None = None) -> dict[str, Any]:
        """获取状态."""
        if loop_id:
            loop = self._active_loops.get(loop_id)
            if loop is None:
                loop = self._paused_loops.get(loop_id)
            if loop is None:
                return {"error": f"Loop {loop_id} not found"}
            return {"loop": loop.to_dict()}

        return {
            "active_loops": len(self._active_loops),
            "paused_loops": len(self._paused_loops),
            "completed_loops": len(self._completed_loops),
            "active_loop_ids": [lid for lid in self._active_loops],
            "paused_loop_ids": [lid for lid in self._paused_loops],
        }

    def get_loop(self, loop_id: str) -> GrowthLoop | None:
        """获取循环."""
        return (
            self._active_loops.get(loop_id)
            or self._paused_loops.get(loop_id)
            or next((l for l in self._completed_loops if l.loop_id == loop_id), None)
        )

    def get_all_loops(self) -> list[GrowthLoop]:
        """获取所有循环."""
        return list(self._active_loops.values()) + list(self._paused_loops.values())

    def get_loop_by_product(self, product_id: str) -> GrowthLoop | None:
        """按产品获取循环."""
        for loop in list(self._active_loops.values()) + list(self._paused_loops.values()) + self._completed_loops:
            if loop.product_id == product_id:
                return loop
        return None

    # ── Auto-Schedule ─────────────────────────────────────────

    def auto_trigger(
        self,
        product_id: str,
        current_metrics: dict[str, Any] | None = None,
        previous_metrics: dict[str, Any] | None = None,
        max_cycles: int = 3,
    ) -> tuple[bool, GrowthLoop | None, list[TriggerReason]]:
        """自动触发检查 — 根据调度器决定是否启动循环."""
        should_run, reasons = self._scheduler.should_trigger(
            product_id, current_metrics, previous_metrics,
        )
        if not should_run:
            return False, None, reasons

        loop = self.start_loop(
            product_id=product_id,
            max_cycles=max_cycles,
            trigger_type=TriggerType.SCHEDULED,
            metrics=GrowthMetrics(**current_metrics) if current_metrics else None,
        )
        return True, loop, reasons

    # ── Summary ───────────────────────────────────────────────

    def get_summary(self) -> dict[str, Any]:
        return {
            "status": self.get_status(),
            "engine_runs": self._engine.run_count,
            "orchestrations": self._orchestrator.orchestrate_count,
            "feedback_processed": self._feedback.process_count,
            "evolutions": self._evolution.evolution_count,
            "scheduler": self._scheduler.get_summary(),
            "total_loops": len(self._loop_history) + len(self._completed_loops),
        }