"""E12.7.6 Loop Engine — 核心循环引擎: Observe→Analyze→Strategy→Execute→Evaluate→Learn→Optimize."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..agent.agent_controller import AutonomousGrowthAgent
from ..agent.models import GrowthHypothesis, GrowthObservation, RootCause
from ..execution.execution_controller import ExecutionController
from ..execution.models import ExecutionPlan
from ..memory.memory_controller import MemoryController
from ..strategy.models import (
    GrowthStrategy,
    StrategyObjective,
    StrategyStatus,
    StrategyTemplateType,
)
from ..strategy.planner_controller import GrowthStrategyPlanner

from .models import (
    CycleOutcome,
    CycleRecord,
    GrowthLoop,
    GrowthMetrics,
    LoopState,
    TriggerType,
)

# Forward reference for pattern
try:
    from ..memory.models import GrowthPattern, MemoryQuery, MemoryType, Outcome
    HAS_MEMORY = True
except ImportError:
    HAS_MEMORY = False


class LoopEngine:
    """核心循环引擎 — 执行完整的 Observe→Analyze→Strategy→Execute→Evaluate→Learn→Optimize 闭环.

    依赖:
      - AgentController: 观察、诊断、假设
      - GrowthStrategyPlanner: 策略生成
      - ExecutionController: 执行
      - MemoryController: 学习、记忆
    """

    def __init__(
        self,
        agent: AutonomousGrowthAgent | None = None,
        planner: GrowthStrategyPlanner | None = None,
        executor: ExecutionController | None = None,
        memory: MemoryController | None = None,
    ):
        self._agent = agent or AutonomousGrowthAgent()
        self._planner = planner or GrowthStrategyPlanner()
        self._executor = executor or ExecutionController()
        self._memory = memory or MemoryController()

        self._default_metrics: dict[str, GrowthMetrics] = {}
        self._run_count: int = 0

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
    def run_count(self) -> int:
        return self._run_count

    # ── Run Loop ──────────────────────────────────────────────

    def run(
        self,
        product_id: str,
        max_cycles: int = 0,
        trigger_type: TriggerType = TriggerType.SCHEDULED,
        config: dict[str, Any] | None = None,
    ) -> GrowthLoop:
        """运行完整增长循环."""
        self._run_count += 1

        loop = GrowthLoop(
            product_id=product_id,
            max_cycles=max_cycles,
            trigger_type=trigger_type,
            state=LoopState.OBSERVING,
            started_at=datetime.now(timezone.utc),
            config=config or {},
        )

        cycle_num = 0
        while not loop.is_complete:
            cycle_num += 1
            loop.current_cycle = cycle_num

            # Run single cycle
            cycle = self.run_cycle(loop, cycle_num)
            loop.cycles.append(cycle)

            # Check if should stop
            if cycle.outcome == CycleOutcome.FAILURE:
                if self._should_abort(loop, cycle):
                    loop.state = LoopState.FAILED
                    break

            if max_cycles > 0 and cycle_num >= max_cycles:
                loop.state = LoopState.COMPLETED
                break

            # Check convergence
            if self._is_converged(loop):
                loop.state = LoopState.COMPLETED
                break

        loop.completed_at = datetime.now(timezone.utc)
        if loop.state not in {LoopState.COMPLETED, LoopState.FAILED}:
            loop.state = LoopState.COMPLETED

        return loop

    def run_cycle(self, loop: GrowthLoop, cycle_num: int) -> CycleRecord:
        """执行单次循环."""
        cycle = CycleRecord(
            cycle_number=cycle_num,
            started_at=datetime.now(timezone.utc),
        )

        try:
            # Step 1: Observe
            cycle.state = LoopState.OBSERVING
            cycle.observation = self._observe(loop)
            if cycle.observation.get("error"):
                cycle.errors.append(cycle.observation["error"])
                cycle.outcome = CycleOutcome.FAILURE
                cycle.state = LoopState.FAILED
                cycle.completed_at = datetime.now(timezone.utc)
                return cycle

            # Step 2: Analyze + Diagnose
            cycle.state = LoopState.ANALYZING
            cycle.diagnosis = self._analyze(loop, cycle)
            if cycle.diagnosis.get("error"):
                cycle.errors.append(cycle.diagnosis["error"])
                cycle.outcome = CycleOutcome.FAILURE
                cycle.state = LoopState.FAILED
                cycle.completed_at = datetime.now(timezone.utc)
                return cycle

            # Step 3: Generate Hypothesis
            cycle.hypothesis = self._hypothesize(loop, cycle)
            if cycle.hypothesis.get("error"):
                cycle.errors.append(cycle.hypothesis["error"])
                cycle.outcome = CycleOutcome.FAILURE
                cycle.state = LoopState.FAILED
                cycle.completed_at = datetime.now(timezone.utc)
                return cycle

            # Step 4: Build Strategy
            cycle.state = LoopState.STRATEGIZING
            strategy_result = self._strategize(loop, cycle)
            if strategy_result.get("error"):
                cycle.errors.append(strategy_result["error"])
                cycle.outcome = CycleOutcome.FAILURE
                cycle.state = LoopState.FAILED
                cycle.completed_at = datetime.now(timezone.utc)
                return cycle
            cycle.strategy_id = strategy_result.get("strategy_id", "")

            # Step 5: Execute
            cycle.state = LoopState.EXECUTING
            execution_result = self._execute(loop, cycle, strategy_result)
            cycle.execution_result = execution_result
            cycle.execution_id = execution_result.get("plan_id", "")
            if execution_result.get("error"):
                cycle.errors.append(execution_result["error"])
                cycle.outcome = CycleOutcome.FAILURE
                cycle.state = LoopState.FAILED
                cycle.completed_at = datetime.now(timezone.utc)
                return cycle

            # Step 6: Measure & Feedback
            cycle.state = LoopState.MEASURING
            cycle.feedback = self._measure(loop, cycle, execution_result)

            # Step 7: Learn
            cycle.state = LoopState.LEARNING
            cycle.learning = self._learn(loop, cycle, execution_result)

            # Step 8: Optimize (next cycle parameters)
            cycle.state = LoopState.OPTIMIZING
            self._optimize(loop, cycle)

            cycle.outcome = self._determine_outcome(cycle)
            cycle.state = LoopState.COMPLETED
            cycle.completed_at = datetime.now(timezone.utc)

        except Exception as e:
            cycle.errors.append(str(e))
            cycle.outcome = CycleOutcome.FAILURE
            cycle.state = LoopState.FAILED
            cycle.completed_at = datetime.now(timezone.utc)

        return cycle

    # ── Step Implementations ──────────────────────────────────

    def _observe(self, loop: GrowthLoop) -> dict[str, Any]:
        """Step 1: 观察 — 获取当前增长指标."""
        metrics = self._default_metrics.get(loop.product_id)
        if metrics is None:
            return {
                "product_id": loop.product_id,
                "metrics": GrowthMetrics(product_id=loop.product_id).to_dict(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        try:
            observation = self._agent.observe(loop.product_id)
            return {
                "product_id": loop.product_id,
                "observation": observation.to_dict() if observation else {},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception:
            return {
                "product_id": loop.product_id,
                "metrics": GrowthMetrics(product_id=loop.product_id).to_dict(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    def _analyze(self, loop: GrowthLoop, cycle: CycleRecord) -> dict[str, Any]:
        """Step 2: 分析诊断 — 发现问题和机会."""
        try:
            observation = self._agent.observe(loop.product_id)
            causes = self._agent.analyze(observation)
            return {
                "diagnosis": [c.to_dict() for c in causes] if causes else [],
                "cycle_number": cycle.cycle_number,
            }
        except Exception:
            return {
                "diagnosis": [],
                "cycle_number": cycle.cycle_number,
                "note": "diagnosis skipped",
            }

    def _hypothesize(self, loop: GrowthLoop, cycle: CycleRecord) -> dict[str, Any]:
        """Step 3: 生成假设."""
        try:
            observation = self._agent.observe(loop.product_id)
            causes = self._agent.analyze(observation)
            hypotheses = self._agent.generate_hypotheses(observation, causes)
            return {
                "hypothesis": [h.to_dict() for h in hypotheses] if hypotheses else [],
                "cycle_number": cycle.cycle_number,
            }
        except Exception:
            return {
                "hypothesis": [],
                "cycle_number": cycle.cycle_number,
                "note": "hypothesis skipped",
            }

    def _strategize(self, loop: GrowthLoop, cycle: CycleRecord) -> dict[str, Any]:
        """Step 4: 生成策略."""
        try:
            observation = self._agent.observe(loop.product_id)
            causes = self._agent.analyze(observation)
            hypotheses = self._agent.generate_hypotheses(observation, causes)

            plan = self._planner.plan_from_agent_result(
                observation=observation,
                hypotheses=hypotheses,
                product_id=loop.product_id,
            )
            if plan is None:
                strategy = GrowthStrategy(
                    product_id=loop.product_id,
                    objective=StrategyObjective(metric="roas", product_id=loop.product_id),
                    template_type=StrategyTemplateType.RECOVERY,
                    confidence=0.5,
                    status=StrategyStatus.VALIDATED,
                )
                return {
                    "strategy_id": strategy.strategy_id,
                    "strategy": strategy.to_dict(),
                }
            top_strategy = plan.top_strategy
            return {
                "strategy_id": top_strategy.strategy_id if top_strategy else "",
                "strategy": top_strategy.to_dict() if top_strategy else {},
            }
        except Exception as e:
            return {
                "strategy_id": "",
                "strategy": {},
                "error": str(e),
            }

    def _execute(
        self, loop: GrowthLoop, cycle: CycleRecord, strategy_result: dict[str, Any],
    ) -> dict[str, Any]:
        """Step 5: 执行策略."""
        strategy_dict = strategy_result.get("strategy", {})
        if not strategy_dict:
            return {"error": "No strategy to execute", "plan_id": ""}

        try:
            strategy = GrowthStrategy(
                product_id=loop.product_id,
                objective=StrategyObjective(metric="roas", product_id=loop.product_id),
                template_type=StrategyTemplateType.RECOVERY,
                confidence=strategy_dict.get("confidence", 0.5),
                status=StrategyStatus.VALIDATED,
            )
            result = self._executor.run(strategy, auto_rollback=False)
            return {
                "plan_id": result.get("plan", {}).get("plan_id", ""),
                "executed": result.get("executed", False),
                "success_tasks": result.get("success_tasks", 0),
                "failed_tasks": result.get("failed_tasks", 0),
                "result": result,
            }
        except Exception as e:
            return {"error": str(e), "plan_id": ""}

    def _measure(
        self, loop: GrowthLoop, cycle: CycleRecord, execution_result: dict[str, Any],
    ) -> dict[str, Any]:
        """Step 6: 测量反馈."""
        feedback: dict[str, Any] = {
            "cycle_number": cycle.cycle_number,
            "execution_success": execution_result.get("executed", False),
            "success_tasks": execution_result.get("success_tasks", 0),
            "failed_tasks": execution_result.get("failed_tasks", 0),
        }

        # Extract metrics from execution result
        plan = execution_result.get("result", {}).get("plan", {})
        if plan:
            feedback["has_failures"] = plan.get("has_failures", False)
            feedback["approval_status"] = plan.get("approval_status", "")

        return feedback

    def _learn(
        self, loop: GrowthLoop, cycle: CycleRecord, execution_result: dict[str, Any],
    ) -> dict[str, Any]:
        """Step 7: 学习 — 将执行结果存入记忆."""
        if not HAS_MEMORY:
            return {"note": "memory module not available"}

        try:
            # Create a mock plan for memory ingestion
            from ..execution.models import ExecutionPlan, ExecutionTask, TaskStatus, TaskType, TargetModule

            plan = ExecutionPlan(strategy_id=cycle.strategy_id)
            plan.plan_id = execution_result.get("plan_id", "")

            # Add a synthetic task to record the learning
            task = ExecutionTask(
                strategy_id=cycle.strategy_id,
                product_id=loop.product_id,
                task_type=TaskType.CREATE_CREATIVE,
                target_module=TargetModule.E11_EVOLUTION,
                parameters={},
            )
            if execution_result.get("executed"):
                task.status = TaskStatus.SUCCESS
            else:
                task.status = TaskStatus.FAILED
            plan.tasks = [task]

            ingest_result = self._memory.ingest(plan)
            patterns = self._memory.learn_patterns()

            return {
                "ingested": ingest_result.get("experiences_extracted", 0),
                "patterns_learned": len(patterns),
                "total_experiences": ingest_result.get("total_experiences", 0),
            }
        except Exception as e:
            return {"error": str(e), "note": "learning skipped"}

    def _optimize(self, loop: GrowthLoop, cycle: CycleRecord) -> None:
        """Step 8: 优化 — 调整下一次循环参数."""
        # Apply memory decay
        try:
            self._memory.optimize()
        except Exception:
            pass

    # ── Helpers ───────────────────────────────────────────────

    def _should_abort(self, loop: GrowthLoop, cycle: CycleRecord) -> bool:
        """判断是否应该中止循环."""
        if cycle.cycle_number <= 1:
            return False
        # Abort if last 3 cycles all failed
        recent = loop.cycles[-3:]
        if len(recent) >= 3:
            return all(
                c.outcome in {CycleOutcome.FAILURE, CycleOutcome.ABORTED}
                for c in recent
            )
        return False

    def _is_converged(self, loop: GrowthLoop) -> bool:
        """判断是否收敛."""
        if len(loop.cycles) < 3:
            return False
        recent = loop.cycles[-3:]
        return all(
            c.is_successful and c.feedback.get("execution_success", False)
            for c in recent
        )

    def _determine_outcome(self, cycle: CycleRecord) -> CycleOutcome:
        """判断循环结果."""
        if cycle.errors:
            return CycleOutcome.FAILURE
        if cycle.feedback.get("execution_success"):
            return CycleOutcome.SUCCESS
        if cycle.feedback.get("has_failures"):
            return CycleOutcome.PARTIAL
        return CycleOutcome.SUCCESS if not cycle.errors else CycleOutcome.FAILURE

    # ── Metrics Management ────────────────────────────────────

    def set_metrics(self, product_id: str, metrics: GrowthMetrics) -> None:
        """设置产品指标."""
        self._default_metrics[product_id] = metrics

    def get_metrics(self, product_id: str) -> GrowthMetrics | None:
        """获取产品指标."""
        return self._default_metrics.get(product_id)

    # ── Result ────────────────────────────────────────────────

    def build_result(self, loop: GrowthLoop) -> dict[str, Any]:
        """构建循环结果."""
        from .models import LoopResult

        result = LoopResult(
            loop_id=loop.loop_id,
            success=loop.state == LoopState.COMPLETED,
            total_cycles=loop.cycle_count,
            successful_cycles=sum(1 for c in loop.cycles if c.is_successful),
            failed_cycles=sum(1 for c in loop.cycles if c.outcome == CycleOutcome.FAILURE),
            final_state=loop.state,
            errors=[e for c in loop.cycles for e in c.errors],
        )

        # Extract lessons from all cycles
        for c in loop.cycles:
            if c.learning and c.learning.get("patterns_learned", 0) > 0:
                result.patterns_discovered += c.learning["patterns_learned"]
            if c.strategy_id:
                result.strategies_generated += 1

        return result.to_dict()