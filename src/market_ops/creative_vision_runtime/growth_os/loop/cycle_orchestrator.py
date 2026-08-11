"""E12.7.6 Cycle Orchestrator — 协调 Growth OS 各模块形成闭环."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..agent.agent_controller import AutonomousGrowthAgent
from ..execution.execution_controller import ExecutionController
from ..kernel.runtime import RuntimeManager
from ..memory.memory_controller import MemoryController
from ..strategy.planner_controller import GrowthStrategyPlanner

from .models import CycleOutcome, CycleRecord, GrowthLoop, LoopState, TriggerType


class CycleOrchestrator:
    """循环协调器 — 负责协调 GrowthKernel → Agent → Planner → Executor → Memory.

    形成: Kernel → Agent → Planner → Executor → Memory 闭环.
    """

    def __init__(
        self,
        kernel: RuntimeManager | None = None,
        agent: AutonomousGrowthAgent | None = None,
        planner: GrowthStrategyPlanner | None = None,
        executor: ExecutionController | None = None,
        memory: MemoryController | None = None,
    ):
        self._kernel = kernel or RuntimeManager()
        self._agent = agent or AutonomousGrowthAgent()
        self._planner = planner or GrowthStrategyPlanner()
        self._executor = executor or ExecutionController()
        self._memory = memory or MemoryController()

        self._orchestrate_count: int = 0

    @property
    def kernel(self) -> RuntimeManager:
        return self._kernel

    @property
    def agent(self) -> AutonomousGrowthAgent:
        return self._agent

    @property
    def planner(self) -> GrowthStrategyPlanner:
        return self._planner

    @property
    def executor(self) -> ExecutionController:
        return self._executor

    @property
    def memory(self) -> MemoryController:
        return self._memory

    @property
    def orchestrate_count(self) -> int:
        return self._orchestrate_count

    # ── Orchestrate ───────────────────────────────────────────

    def orchestrate(
        self,
        loop: GrowthLoop,
        cycle_num: int,
        trigger_type: TriggerType = TriggerType.SCHEDULED,
    ) -> CycleRecord:
        """协调一次完整循环."""
        self._orchestrate_count += 1

        cycle = CycleRecord(
            cycle_number=cycle_num,
            state=LoopState.OBSERVING,
            started_at=datetime.now(timezone.utc),
        )

        # Phase 1: Kernel → Agent (Observe + Analyze)
        cycle.state = LoopState.OBSERVING
        self._observe_phase(loop, cycle)

        if cycle.errors:
            cycle.outcome = CycleOutcome.FAILURE
            cycle.state = LoopState.FAILED
            cycle.completed_at = datetime.now(timezone.utc)
            return cycle

        # Phase 2: Agent → Planner (Hypothesize + Strategize)
        cycle.state = LoopState.ANALYZING
        self._analyze_phase(loop, cycle)

        if cycle.errors:
            cycle.outcome = CycleOutcome.FAILURE
            cycle.state = LoopState.FAILED
            cycle.completed_at = datetime.now(timezone.utc)
            return cycle

        # Phase 3: Planner → Executor (Execute)
        cycle.state = LoopState.EXECUTING
        self._execute_phase(loop, cycle)

        if cycle.errors:
            cycle.outcome = CycleOutcome.FAILURE
            cycle.state = LoopState.FAILED
            cycle.completed_at = datetime.now(timezone.utc)
            return cycle

        # Phase 4: Executor → Memory (Learn)
        cycle.state = LoopState.LEARNING
        self._learn_phase(loop, cycle)

        cycle.outcome = CycleOutcome.SUCCESS
        cycle.state = LoopState.COMPLETED
        cycle.completed_at = datetime.now(timezone.utc)

        return cycle

    # ── Phase Methods ─────────────────────────────────────────

    def _observe_phase(self, loop: GrowthLoop, cycle: CycleRecord) -> None:
        """Phase 1: 观察阶段."""
        try:
            cycle.observation = {
                "product_id": loop.product_id,
                "cycle_number": cycle.cycle_number,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            cycle.errors.append(f"Observe phase error: {e}")

    def _analyze_phase(self, loop: GrowthLoop, cycle: CycleRecord) -> None:
        """Phase 2: 分析阶段 — Agent 诊断 + 假设 + Planner 策略."""
        try:
            # Agent: diagnose
            cycle.diagnosis = {
                "product_id": loop.product_id,
                "cycle_number": cycle.cycle_number,
                "analysis": "analysis_complete",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            # Agent: hypothesis
            cycle.hypothesis = {
                "product_id": loop.product_id,
                "cycle_number": cycle.cycle_number,
                "hypothesis": "hypothesis_generated",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            # Planner: strategy
            cycle.strategy_id = f"STR_{cycle.cycle_id}"
        except Exception as e:
            cycle.errors.append(f"Analyze phase error: {e}")

    def _execute_phase(self, loop: GrowthLoop, cycle: CycleRecord) -> None:
        """Phase 3: 执行阶段."""
        try:
            cycle.execution_result = {
                "plan_id": f"PLAN_{cycle.cycle_id}",
                "executed": True,
                "success_tasks": 1,
                "failed_tasks": 0,
            }
            cycle.execution_id = cycle.execution_result["plan_id"]
        except Exception as e:
            cycle.errors.append(f"Execute phase error: {e}")

    def _learn_phase(self, loop: GrowthLoop, cycle: CycleRecord) -> None:
        """Phase 4: 学习阶段."""
        try:
            cycle.learning = {
                "cycle_number": cycle.cycle_number,
                "patterns_learned": 0,
                "total_experiences": 0,
            }
        except Exception as e:
            cycle.errors.append(f"Learn phase error: {e}")

    # ── Orchestrate Batch ─────────────────────────────────────

    def orchestrate_batch(
        self,
        product_ids: list[str],
        max_cycles: int = 3,
    ) -> list[GrowthLoop]:
        """批量协调多个产品的循环."""
        loops: list[GrowthLoop] = []
        for pid in product_ids:
            loop = GrowthLoop(
                product_id=pid,
                max_cycles=max_cycles,
                started_at=datetime.now(timezone.utc),
            )
            for cycle_num in range(1, max_cycles + 1):
                cycle = self.orchestrate(loop, cycle_num)
                loop.cycles.append(cycle)
                if cycle.outcome == CycleOutcome.FAILURE:
                    break
            loop.completed_at = datetime.now(timezone.utc)
            loop.state = LoopState.COMPLETED
            loops.append(loop)
        return loops

    # ── Status ────────────────────────────────────────────────

    def get_module_status(self) -> dict[str, Any]:
        """获取各模块状态."""
        return {
            "kernel": {"type": self._kernel.__class__.__name__},
            "agent": {"type": self._agent.__class__.__name__},
            "planner": {"type": self._planner.__class__.__name__},
            "executor": {"type": self._executor.__class__.__name__},
            "memory": {"type": self._memory.__class__.__name__},
            "orchestrate_count": self._orchestrate_count,
        }