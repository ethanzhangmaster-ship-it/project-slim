"""E15.3.2 Autonomous Decision Loop — 自主决策循环.

核心循环类，整合所有组件实现完整的 Observe → Think → Decide → Act → Learn 流程。

架构:
  AutonomousDecisionLoop
      ├── CycleStateMachine    (状态机)
      ├── GoalEvaluator        (目标评估)
      ├── OpportunityEvaluator  (机会评估)
      ├── PlannerBridge        (E15.2.1 Planner 桥接)
      ├── ExecutorBridge       (E15.1 Workflow 桥接)
      ├── PerformanceEvaluator (性能评估)
      └── Learner              (E15.1.5 Memory 桥接)

用法:
    loop = AutonomousDecisionLoop(operator_id="op_001")
    loop.setup_goals([...])
    loop.setup_environment(metrics={...})
    loop.run_cycle()
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any

from .evaluator import GoalEvaluator, OpportunityEvaluator, PerformanceEvaluator
from .executor_bridge import ExecutorBridge
from .learner import Learner
from .models import (
    CycleOutcome,
    CycleResult,
    CycleState,
    CycleSummary,
    DecisionCycle,
    EnvironmentState,
    GoalEvaluation,
    OpportunitySignal,
)
from .planner_bridge import PlannerBridge
from .state_machine import CycleStateMachine


# ═══════════════════════════════════════════════════════════════
# Autonomous Decision Loop
# ═══════════════════════════════════════════════════════════════


class AutonomousDecisionLoop:
    """E15.3.2 Autonomous Decision Loop — 自主决策循环.

    Operator 的核心决策循环，实现:
      Observe → Analyze → Plan → Decide → Execute → Evaluate → Learn

    用法:
        loop = AutonomousDecisionLoop(operator_id="op_001")
        loop.setup_goals([
            {"name": "ROAS", "metric": "roas", "target": 0.8, "direction": "above"}
        ])
        loop.update_environment({"roas": 0.65, "ctr": 2.1, "spend": 2500})
        result = loop.run_cycle()
    """

    def __init__(
        self,
        operator_id: str = "",
        state_machine: CycleStateMachine | None = None,
        goal_evaluator: GoalEvaluator | None = None,
        opportunity_evaluator: OpportunityEvaluator | None = None,
        planner_bridge: PlannerBridge | None = None,
        executor_bridge: ExecutorBridge | None = None,
        performance_evaluator: PerformanceEvaluator | None = None,
        learner: Learner | None = None,
    ):
        self._operator_id = operator_id
        self._state_machine = state_machine or CycleStateMachine()
        self._goal_evaluator = goal_evaluator or GoalEvaluator()
        self._opportunity_evaluator = opportunity_evaluator or OpportunityEvaluator()
        self._planner_bridge = planner_bridge or PlannerBridge()
        self._executor_bridge = executor_bridge or ExecutorBridge()
        self._performance_evaluator = performance_evaluator or PerformanceEvaluator()
        self._learner = learner or Learner()

        self._active: bool = False
        self._paused: bool = False
        self._total_cycles: int = 0
        self._current_cycle: DecisionCycle | None = None
        self._cycle_history: list[CycleResult] = []
        self._goals: list[dict[str, Any]] = []
        self._environment: EnvironmentState = EnvironmentState()
        self._metrics_before: dict[str, float] = {}
        self._cycle_interval_seconds: float = 0.0
        self._max_cycles: int = 0

    # ── Properties ──────────────────────────────────────────────

    @property
    def operator_id(self) -> str:
        return self._operator_id

    @property
    def active(self) -> bool:
        return self._active

    @property
    def paused(self) -> bool:
        return self._paused

    @property
    def total_cycles(self) -> int:
        return self._total_cycles

    @property
    def current_cycle(self) -> DecisionCycle | None:
        return self._current_cycle

    @property
    def cycle_history(self) -> list[CycleResult]:
        return list(self._cycle_history)

    @property
    def state_machine(self) -> CycleStateMachine:
        return self._state_machine

    @property
    def goal_evaluator(self) -> GoalEvaluator:
        return self._goal_evaluator

    @property
    def opportunity_evaluator(self) -> OpportunityEvaluator:
        return self._opportunity_evaluator

    @property
    def planner_bridge(self) -> PlannerBridge:
        return self._planner_bridge

    @property
    def executor_bridge(self) -> ExecutorBridge:
        return self._executor_bridge

    @property
    def performance_evaluator(self) -> PerformanceEvaluator:
        return self._performance_evaluator

    @property
    def learner(self) -> Learner:
        return self._learner

    # ── Setup ───────────────────────────────────────────────────

    def setup_goals(self, goals: list[dict[str, Any]]) -> None:
        """设置目标列表.

        Args:
            goals: 目标定义列表, 每个目标包含:
                   - name, metric, target, direction, priority
        """
        self._goals = []
        for g in goals:
            self._goals.append({
                "goal_id": g.get("goal_id", str(uuid.uuid4())),
                "name": g.get("name", ""),
                "metric": g.get("metric", ""),
                "target": float(g.get("target", 0)),
                "direction": g.get("direction", "above"),
                "priority": g.get("priority", "medium"),
            })

    def setup_environment(
        self,
        metrics: dict[str, float] | None = None,
        anomalies: list[dict[str, Any]] | None = None,
        trends: list[dict[str, Any]] | None = None,
        opportunities: list[dict[str, Any]] | None = None,
        risks: list[str] | None = None,
    ) -> None:
        """设置环境状态.

        Args:
            metrics:       当前指标
            anomalies:     异常信号
            trends:        趋势信号
            opportunities: 机会信号
            risks:         风险因素
        """
        from .models import AnomalySignal, TrendSignal

        self._environment = EnvironmentState(
            metrics=metrics or {},
            anomalies=[
                AnomalySignal(**a) for a in (anomalies or [])
            ],
            trends=[
                TrendSignal(**t) for t in (trends or [])
            ],
            opportunities=[
                OpportunitySignal(**o) for o in (opportunities or [])
            ],
            risks=risks or [],
        )

    def update_environment(
        self,
        metrics: dict[str, float] | None = None,
        anomalies: list[dict[str, Any]] | None = None,
        trends: list[dict[str, Any]] | None = None,
    ) -> None:
        """更新环境状态 (增量更新).

        Args:
            metrics:   更新的指标
            anomalies: 新增异常
            trends:    新增趋势
        """
        if metrics:
            self._environment.metrics.update(metrics)
        if anomalies:
            from .models import AnomalySignal
            self._environment.anomalies.extend(
                AnomalySignal(**a) for a in anomalies
            )
        if trends:
            from .models import TrendSignal
            self._environment.trends.extend(
                TrendSignal(**t) for t in trends
            )

    def set_cycle_interval(self, seconds: float) -> None:
        """设置循环间隔."""
        self._cycle_interval_seconds = max(0.0, seconds)

    def set_max_cycles(self, max_cycles: int) -> None:
        """设置最大循环次数."""
        self._max_cycles = max(0, max_cycles)

    # ── Lifecycle ───────────────────────────────────────────────

    def start(self) -> bool:
        """启动循环."""
        if self._active:
            return False
        self._active = True
        self._paused = False
        return True

    def pause(self) -> bool:
        """暂停循环."""
        if not self._active or self._paused:
            return False
        self._paused = True
        if self._current_cycle:
            self._state_machine.transition(self._current_cycle, CycleState.PAUSED)
        return True

    def resume(self) -> bool:
        """恢复循环."""
        if not self._active or not self._paused:
            return False
        self._paused = False
        return True

    def stop(self) -> bool:
        """停止循环."""
        self._active = False
        self._paused = False
        return True

    # ── Core: Run Cycle ────────────────────────────────────────

    def run_cycle(self) -> CycleResult:
        """执行一个完整决策周期.

        流程:
          1. OBSERVE:  观察环境
          2. ANALYZE:  目标评估 + 机会检测
          3. PLAN:     生成候选动作
          4. DECIDE:   选择最优动作
          5. EXECUTE:  执行动作
          6. EVALUATE: 评估结果
          7. LEARN:    记录经验

        Returns:
            CycleResult: 周期结果
        """
        if not self._active:
            return CycleResult(
                cycle_number=self._total_cycles + 1,
                outcome=CycleOutcome.NO_ACTION,
                summary="Loop not active",
            )

        self._total_cycles += 1
        cycle = DecisionCycle(
            operator_id=self._operator_id,
            cycle_number=self._total_cycles,
            environment_state=self._environment,
        )
        self._current_cycle = cycle
        self._state_machine.reset()

        try:
            # Phase 1: OBSERVE
            self._state_machine.transition(cycle, CycleState.OBSERVING)
            observation = self._observe()
            cycle.observation = observation

            # Phase 2: ANALYZE
            self._state_machine.transition(cycle, CycleState.ANALYZING)
            goal_evals, opportunities = self._analyze(cycle)

            # Phase 3: PLAN
            self._state_machine.transition(cycle, CycleState.PLANNING)
            candidates = self._plan(cycle, goal_evals, opportunities)
            cycle.candidate_actions = candidates

            # Phase 4: DECIDE
            self._state_machine.transition(cycle, CycleState.DECIDING)
            selected = self._decide(candidates, cycle)
            cycle.selected_action = selected

            # Phase 5: EXECUTE
            self._state_machine.transition(cycle, CycleState.EXECUTING)
            self._metrics_before = dict(self._environment.metrics)
            execution_result = self._execute(selected, cycle)

            # Phase 6: EVALUATE
            self._state_machine.transition(cycle, CycleState.EVALUATING)
            cycle_result = self._evaluate(cycle)

            # Phase 7: LEARN
            self._state_machine.transition(cycle, CycleState.LEARNING)
            self._learn(cycle, cycle_result)

            # Complete
            self._state_machine.transition(cycle, CycleState.COMPLETED)
            cycle.completed_at = datetime.now(timezone.utc).isoformat()

        except Exception as e:
            self._state_machine.transition(cycle, CycleState.FAILED)
            cycle.error = str(e)
            cycle.completed_at = datetime.now(timezone.utc).isoformat()
            cycle_result = CycleResult(
                cycle_id=cycle.cycle_id,
                cycle_number=cycle.cycle_number,
                outcome=CycleOutcome.ERROR,
                reward=0.0,
                summary=f"Cycle failed: {str(e)}",
                action_taken=cycle.selected_action.get("action_type", ""),
                duration_seconds=cycle.duration_seconds(),
            )

        self._cycle_history.append(cycle_result)
        return cycle_result

    def run_loop(
        self,
        max_cycles: int | None = None,
        interval_seconds: float | None = None,
    ) -> list[CycleResult]:
        """持续运行决策循环.

        while operator.active:
            observe_environment()
            evaluate_goals()
            detect_opportunities()
            generate_actions()
            select_best_action()
            execute_action()
            evaluate_result()
            update_memory()
            wait_next_cycle()

        Args:
            max_cycles:      最大循环次数 (None = 使用配置值)
            interval_seconds: 循环间隔 (None = 使用配置值)

        Returns:
            list[CycleResult]: 所有周期结果
        """
        max_cycles = max_cycles or self._max_cycles or 0
        interval = interval_seconds if interval_seconds is not None else self._cycle_interval_seconds

        results: list[CycleResult] = []
        cycle_count = 0

        while self._active:
            if self._paused:
                time.sleep(0.1)
                continue

            if max_cycles > 0 and cycle_count >= max_cycles:
                break

            result = self.run_cycle()
            results.append(result)
            cycle_count += 1

            if interval > 0:
                time.sleep(interval)

        return results

    # ── Phase Methods ───────────────────────────────────────────

    def _observe(self) -> dict[str, Any]:
        """Phase 1: OBSERVE — 观察环境."""
        return {
            "metrics": self._environment.metrics,
            "anomalies": [a.to_dict() for a in self._environment.anomalies],
            "trends": [t.to_dict() for t in self._environment.trends],
            "risks": self._environment.risks,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _analyze(
        self, cycle: DecisionCycle
    ) -> tuple[list[GoalEvaluation], list[OpportunitySignal]]:
        """Phase 2: ANALYZE — 目标评估 + 机会检测."""
        # 目标评估
        goal_evals = self._goal_evaluator.evaluate(
            self._goals, self._environment.metrics
        )
        cycle.goal_evaluations = goal_evals

        # 机会检测
        opportunities = self._opportunity_evaluator.evaluate(
            self._environment
        )

        return goal_evals, opportunities

    def _plan(
        self,
        cycle: DecisionCycle,
        goal_evals: list[GoalEvaluation],
        opportunities: list[OpportunitySignal],
    ) -> list[dict[str, Any]]:
        """Phase 3: PLAN — 生成候选动作."""
        return self._planner_bridge.generate_actions(
            cycle, goal_evals, opportunities, self._environment
        )

    def _decide(
        self,
        candidates: list[dict[str, Any]],
        cycle: DecisionCycle,
    ) -> dict[str, Any]:
        """Phase 4: DECIDE — 选择最优动作.

        选择策略:
          1. 过滤掉 do_nothing (除非只有一个候选)
          2. 按置信度排序
          3. 选择置信度最高的动作
        """
        if not candidates:
            return {"action_type": "do_nothing", "confidence": 0.0}

        # 如果有多个候选，排除 do_nothing
        actionable = [c for c in candidates if c.get("action_type") != "do_nothing"]

        if not actionable:
            return candidates[0]  # 返回 do_nothing

        # 按置信度排序
        sorted_candidates = sorted(
            actionable, key=lambda c: c.get("confidence", 0), reverse=True
        )

        return sorted_candidates[0]

    def _execute(
        self,
        action: dict[str, Any],
        cycle: DecisionCycle,
    ) -> dict[str, Any]:
        """Phase 5: EXECUTE — 执行动作."""
        return self._executor_bridge.execute(action, cycle)

    def _evaluate(self, cycle: DecisionCycle) -> CycleResult:
        """Phase 6: EVALUATE — 评估结果."""
        return self._performance_evaluator.evaluate(
            cycle, self._metrics_before, self._environment.metrics
        )

    def _learn(
        self,
        cycle: DecisionCycle,
        cycle_result: CycleResult,
    ) -> dict[str, Any]:
        """Phase 7: LEARN — 记录经验."""
        context = {
            "operator_id": self._operator_id,
            "environment_metrics": self._environment.metrics,
            "goals": self._goals,
        }
        return self._learner.learn(cycle, cycle_result, context)

    # ── Query ───────────────────────────────────────────────────

    def get_cycle_summary(self) -> CycleSummary:
        """获取周期运行摘要."""
        return CycleSummary.from_results(self._cycle_history)

    def get_status(self) -> dict[str, Any]:
        """获取循环状态."""
        return {
            "operator_id": self._operator_id,
            "active": self._active,
            "paused": self._paused,
            "total_cycles": self._total_cycles,
            "current_state": (
                self._state_machine.current_state.value
                if self._state_machine else "unknown"
            ),
            "goals": self._goals,
            "environment": self._environment.to_dict(),
            "cycle_summary": self.get_cycle_summary().to_dict(),
            "executor_stats": self._executor_bridge.get_stats(),
            "learner_stats": self._learner.get_stats(),
        }

    def reset(self) -> None:
        """重置循环."""
        self._active = False
        self._paused = False
        self._total_cycles = 0
        self._current_cycle = None
        self._cycle_history = []
        self._goals = []
        self._environment = EnvironmentState()
        self._metrics_before = {}
        self._state_machine.reset()
        self._executor_bridge.reset()
        self._learner.reset()


__all__ = ["AutonomousDecisionLoop"]