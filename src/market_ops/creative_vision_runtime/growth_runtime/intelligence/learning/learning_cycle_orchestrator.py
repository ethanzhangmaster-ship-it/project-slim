"""E13.7.8 Learning Cycle Orchestrator — 学习循环自主编排器.

Day 7.8:
  将现有 Learning Components 升级为 Autonomous Learning Agent，
  实现完整的 Observe → Measure → Evaluate → Policy → Execute → Memory → Optimize 闭环。

核心流程:
  IDLE
      |
      v
  OBSERVE              — 观察当前状态 (strategy_state, policy_state, experiences)
      |
      v
  MEASURE_OUTCOME      — 测量上一轮执行结果 (如果有)
      |
      v
  EVALUATE             — 调用 LearningEvaluator 评估学习有效性
      |
      v
  POLICY_DECISION      — 调用 LearningPolicyController 生成策略决策
      |
      v
  EXECUTE              — 调用 LearningExecutionAdapter 执行策略
      |
      v
  UPDATE_MEMORY        — 更新记忆/策略状态
      |
      v
  OPTIMIZE_STRATEGY    — 基于评估结果优化策略参数
      |
      v
  COMPLETED            — 周期完成，判定下一步 (continue/pause/stop)

集成组件:
  - LearningLoopController   → 学习循环执行
  - LearningEvaluator        → 学习有效性评估
  - LearningPolicyController → 策略决策生成
  - LearningExecutionAdapter → 策略执行路由
  - LearningStrategyOptimizer → 策略参数优化

设计原则:
  - 编排层，不实现具体算法
  - 每个阶段 fail-safe (某阶段失败不阻断整体)
  - 策略门控 (policy gating) 防止无效学习循环
  - 完整的生命周期管理 (start/pause/resume/stop)
  - 可审计的状态转换记录

用法:
  orchestrator = LearningCycleOrchestrator(
      config=OrchestratorConfig.default(),
      loop_controller=controller,
      evaluator=evaluator,
      policy_controller=policy_ctrl,
      execution_adapter=adapter,
      strategy_optimizer=optimizer,
  )
  orchestrator.start()
  result = orchestrator.run_cycle()
"""

from __future__ import annotations

import time
from typing import Any

from .evaluation.learning_evaluator import LearningEvaluator
from .learning_execution_adapter import LearningExecutionAdapter
from .learning_policy_controller import LearningPolicyController
from .learning_strategy_optimizer import LearningStrategyOptimizer
from .models.learning_execution_models import (
    LearningExecutionContext,
    LearningExecutionResult,
)
from .models.learning_orchestration_models import (
    CycleOrchestrationState,
    OrchestrationCycleResult,
    OrchestratorConfig,
)
from .models.learning_strategy_models import (
    LearningPolicyDecision,
    LearningStrategyState,
    PolicyDecisionType,
)
from .models.outcome_measurement_models import OutcomeMeasurement
from .outcome_measurement import OutcomeMeasurer
from .learning_feedback_router import LearningFeedbackRouter
from .learning_cycle_gate import CycleGate
from .models.cycle_gate_models import GateDecision
from .learning_policy_adjuster import PolicyAdjuster


# ═══════════════════════════════════════════════════════════════
# State Transition Map
# ═══════════════════════════════════════════════════════════════

_STATE_TRANSITIONS: dict[CycleOrchestrationState, CycleOrchestrationState] = {
    CycleOrchestrationState.IDLE: CycleOrchestrationState.OBSERVE,
    CycleOrchestrationState.OBSERVE: CycleOrchestrationState.MEASURE_OUTCOME,
    CycleOrchestrationState.MEASURE_OUTCOME: CycleOrchestrationState.FEEDBACK_INGESTION,
    CycleOrchestrationState.FEEDBACK_INGESTION: CycleOrchestrationState.CYCLE_GATE,
    CycleOrchestrationState.CYCLE_GATE: CycleOrchestrationState.EVALUATE,
    CycleOrchestrationState.EVALUATE: CycleOrchestrationState.POLICY_ADJUSTMENT,
    CycleOrchestrationState.POLICY_ADJUSTMENT: CycleOrchestrationState.POLICY_DECISION,
    CycleOrchestrationState.POLICY_DECISION: CycleOrchestrationState.EXECUTE,
    CycleOrchestrationState.EXECUTE: CycleOrchestrationState.UPDATE_MEMORY,
    CycleOrchestrationState.UPDATE_MEMORY: CycleOrchestrationState.OPTIMIZE_STRATEGY,
    CycleOrchestrationState.OPTIMIZE_STRATEGY: CycleOrchestrationState.COMPLETED,
    CycleOrchestrationState.COMPLETED: CycleOrchestrationState.OBSERVE,
    CycleOrchestrationState.PAUSED: CycleOrchestrationState.OBSERVE,
    CycleOrchestrationState.FAILED: CycleOrchestrationState.IDLE,
}


# ═══════════════════════════════════════════════════════════════
# Cycle Gating Conditions
# ═══════════════════════════════════════════════════════════════


def _should_gate_on_effectiveness(
    effectiveness: Any,
    config: OrchestratorConfig,
) -> tuple[bool, str]:
    """基于有效性评估的门控判断.

    Returns:
        (should_gate, reason)
    """
    if not config.enable_policy_gating:
        return False, ""

    if effectiveness is None:
        return False, ""

    # 检查有效性评分
    if hasattr(effectiveness, "effectiveness_score"):
        if effectiveness.effectiveness_score < config.min_effectiveness_threshold:
            return True, (
                f"Effectiveness score {effectiveness.effectiveness_score:.2f} "
                f"below threshold {config.min_effectiveness_threshold:.2f}"
            )

    # 检查学习增益
    if hasattr(effectiveness, "learning_gain"):
        if config.auto_pause_on_negative and effectiveness.learning_gain < 0:
            return True, (
                f"Negative learning gain: {effectiveness.learning_gain:.4f}"
            )

    return False, ""


# ═══════════════════════════════════════════════════════════════
# LearningCycleOrchestrator
# ═══════════════════════════════════════════════════════════════


class LearningCycleOrchestrator:
    """学习循环自主编排器 — 将 Learning Components 升级为 Autonomous Agent.

    用法:
        orchestrator = LearningCycleOrchestrator(
            config=OrchestratorConfig.test_mode(),
            evaluator=LearningEvaluator(),
            policy_controller=LearningPolicyController(),
            execution_adapter=LearningExecutionAdapter(),
        )
        orchestrator.start()
        for _ in range(10):
            result = orchestrator.run_cycle()
            if result.should_stop:
                break
    """

    def __init__(
        self,
        config: OrchestratorConfig | None = None,
        loop_controller: Any = None,  # LearningLoopController
        evaluator: LearningEvaluator | None = None,
        policy_controller: LearningPolicyController | None = None,
        execution_adapter: LearningExecutionAdapter | None = None,
        strategy_optimizer: LearningStrategyOptimizer | None = None,
    ) -> None:
        """初始化编排器.

        Args:
            config: 编排器配置
            loop_controller: LearningLoopController 实例
            evaluator: LearningEvaluator 实例
            policy_controller: LearningPolicyController 实例
            execution_adapter: LearningExecutionAdapter 实例
            strategy_optimizer: LearningStrategyOptimizer 实例
        """
        self._config = config or OrchestratorConfig.default()
        self._loop_controller = loop_controller
        self._evaluator = evaluator or LearningEvaluator()
        self._policy_controller = policy_controller or LearningPolicyController()
        self._execution_adapter = execution_adapter or LearningExecutionAdapter()
        self._strategy_optimizer = strategy_optimizer

        # ── 生命周期状态 ──
        self._active: bool = False
        self._paused: bool = False
        self._current_state: CycleOrchestrationState = CycleOrchestrationState.IDLE
        self._total_cycles: int = 0
        self._cycle_history: list[OrchestrationCycleResult] = []

        # ── 组件状态 ──
        self._strategy_state: LearningStrategyState = LearningStrategyState.default()
        self._previous_execution_result: LearningExecutionResult | None = None
        self._experiences: list[Any] = []
        self._rewards: list[Any] = []

        # ── Outcome Measurement (Day 7.8 Step 3) ──
        self._outcome_measurer: OutcomeMeasurer = OutcomeMeasurer()

        # ── Feedback Router (Day 7.8 Step 4) ──
        self._feedback_router: LearningFeedbackRouter = LearningFeedbackRouter()

        # ── Cycle Gate (Day 7.8 Step 5) ──
        self._cycle_gate: CycleGate = CycleGate()

        # ── Policy Adjuster (Day 7.8 Step 6) ──
        self._policy_adjuster: PolicyAdjuster = PolicyAdjuster()

        # ── 控制状态 ──
        self._retry_count: int = 0
        self._decision_memory: Any = None
        self._experience_store: Any = None
        self._pattern_store: Any = None

    # ── Properties ──────────────────────────────────────────────

    @property
    def active(self) -> bool:
        return self._active

    @property
    def paused(self) -> bool:
        return self._paused

    @property
    def current_state(self) -> CycleOrchestrationState:
        return self._current_state

    @property
    def total_cycles(self) -> int:
        return self._total_cycles

    @property
    def cycle_history(self) -> list[OrchestrationCycleResult]:
        return list(self._cycle_history)

    @property
    def strategy_state(self) -> LearningStrategyState:
        return self._strategy_state

    @property
    def config(self) -> OrchestratorConfig:
        return self._config

    @property
    def cycle_gate(self) -> CycleGate:
        return self._cycle_gate

    @property
    def policy_adjuster(self) -> PolicyAdjuster:
        return self._policy_adjuster

    # ── Lifecycle Management ────────────────────────────────────

    def start(self) -> bool:
        """启动编排器."""
        if self._active:
            return False
        self._active = True
        self._paused = False
        self._current_state = CycleOrchestrationState.IDLE
        return True

    def pause(self) -> bool:
        """暂停编排器."""
        if not self._active or self._paused:
            return False
        self._paused = True
        self._current_state = CycleOrchestrationState.PAUSED
        return True

    def resume(self) -> bool:
        """恢复编排器."""
        if not self._active or not self._paused:
            return False
        self._paused = False
        self._current_state = CycleOrchestrationState.OBSERVE
        return True

    def stop(self) -> bool:
        """停止编排器."""
        self._active = False
        self._paused = False
        self._current_state = CycleOrchestrationState.IDLE
        return True

    def reset(self) -> None:
        """重置编排器."""
        self._active = False
        self._paused = False
        self._current_state = CycleOrchestrationState.IDLE
        self._total_cycles = 0
        self._cycle_history = []
        self._strategy_state = LearningStrategyState.default()
        self._previous_execution_result = None
        self._experiences = []
        self._rewards = []
        self._retry_count = 0
        self._cycle_gate.reset()
        self._policy_adjuster.reset()

    # ── Dependency Injection ────────────────────────────────────

    def set_decision_memory(self, memory: Any) -> None:
        """设置 DecisionMemory."""
        self._decision_memory = memory

    def set_experience_store(self, store: Any) -> None:
        """设置 ExperienceStore."""
        self._experience_store = store

    def set_pattern_store(self, store: Any) -> None:
        """设置 PatternStore."""
        self._pattern_store = store

    def feed_experiences(self, experiences: list[Any]) -> None:
        """注入学习经验."""
        self._experiences = list(experiences)

    def feed_rewards(self, rewards: list[Any]) -> None:
        """注入奖励."""
        self._rewards = list(rewards)

    def set_strategy_state(self, state: LearningStrategyState) -> None:
        """设置策略状态."""
        self._strategy_state = state

    # ── Core: Run Cycle ────────────────────────────────────────

    def run_cycle(self) -> OrchestrationCycleResult:
        """执行一次完整编排周期.

        流程:
          OBSERVE → MEASURE_OUTCOME → EVALUATE → POLICY_DECISION
          → EXECUTE → UPDATE_MEMORY → OPTIMIZE_STRATEGY → COMPLETED

        Returns:
            OrchestrationCycleResult: 周期结果
        """
        if not self._active:
            return OrchestrationCycleResult.idle_result(self._total_cycles + 1)

        if self._paused:
            return OrchestrationCycleResult.paused_result(
                self._total_cycles + 1,
                gating_reason="Orchestrator is paused",
            )

        self._total_cycles += 1
        cycle_number = self._total_cycles
        start_time = time.perf_counter()
        transitions: list[dict[str, Any]] = []

        # ── 检查 max_cycles ──
        if (
            self._config.max_cycles > 0
            and cycle_number > self._config.max_cycles
        ):
            return OrchestrationCycleResult.stopped_result(
                cycle_number,
                reason=f"Max cycles ({self._config.max_cycles}) reached",
            )

        try:
            # ── Phase 1: OBSERVE ──
            self._transition(CycleOrchestrationState.OBSERVE, transitions)
            observation = self._observe()

            # ── Phase 2: MEASURE_OUTCOME ──
            self._transition(CycleOrchestrationState.MEASURE_OUTCOME, transitions)
            outcome = self._measure_outcome()

            # ── Phase 2.5: FEEDBACK_INGESTION (Day 7.8 Step 4) ──
            self._transition(CycleOrchestrationState.FEEDBACK_INGESTION, transitions)
            feedback = self._ingest_feedback(outcome)

            # ── Phase 2.6: CYCLE_GATE (Day 7.8 Step 5) ──
            self._transition(CycleOrchestrationState.CYCLE_GATE, transitions)
            gate_result = self._gate_cycle(feedback, effectiveness=None)
            if gate_result.is_blocking and gate_result.decision != GateDecision.REQUEST_MORE_DATA.value:
                self._current_state = CycleOrchestrationState.PAUSED
                return OrchestrationCycleResult.gated_result(
                    cycle_number=cycle_number,
                    gate_result=gate_result,
                    gating_reason=gate_result.decision_reason,
                    state_transitions=transitions,
                )

            # ── Phase 3: EVALUATE ──
            self._transition(CycleOrchestrationState.EVALUATE, transitions)
            effectiveness = self._evaluate()

            # ── Phase 3.5: POLICY_ADJUSTMENT (Day 7.8 Step 6) ──
            self._transition(CycleOrchestrationState.POLICY_ADJUSTMENT, transitions)
            policy_adjustments = self._adjust_policy(feedback, gate_result, effectiveness)

            # ── 门控检查 ──
            should_gate, gate_reason = _should_gate_on_effectiveness(
                effectiveness, self._config
            )
            if should_gate:
                self._current_state = CycleOrchestrationState.PAUSED
                return OrchestrationCycleResult.paused_result(
                    cycle_number,
                    gating_reason=gate_reason,
                    state_transitions=transitions,
                )

            # ── Phase 4: POLICY_DECISION ──
            self._transition(CycleOrchestrationState.POLICY_DECISION, transitions)
            policy_decision = self._decide_policy(effectiveness)

            # ── Phase 5: EXECUTE ──
            self._transition(CycleOrchestrationState.EXECUTE, transitions)
            execution_result = self._execute(policy_decision)

            # ── Phase 6: UPDATE_MEMORY ──
            self._transition(CycleOrchestrationState.UPDATE_MEMORY, transitions)
            memory_updates = self._update_memory(execution_result)

            # ── Phase 7: OPTIMIZE_STRATEGY ──
            self._transition(CycleOrchestrationState.OPTIMIZE_STRATEGY, transitions)
            strategy_adjusted = self._optimize_strategy(effectiveness, execution_result)

            # ── Phase 8: COMPLETED ──
            self._transition(CycleOrchestrationState.COMPLETED, transitions)

            duration_ms = (time.perf_counter() - start_time) * 1000

            result = OrchestrationCycleResult.completed_result(
                cycle_number=cycle_number,
                effectiveness=effectiveness,
                policy_decision=policy_decision,
                execution_result=execution_result,
                memory_updates=memory_updates,
                state_transitions=transitions,
                duration_ms=round(duration_ms, 2),
                strategy_adjusted=strategy_adjusted,
                gate_result=gate_result,
                policy_adjustments=policy_adjustments,
            )

            self._previous_execution_result = execution_result
            self._cycle_history.append(result)
            self._retry_count = 0
            return result

        except Exception as e:
            self._retry_count += 1
            self._current_state = CycleOrchestrationState.FAILED

            next_action = "retry" if self._retry_count < self._config.failure_max_retries else "stop"

            result = OrchestrationCycleResult.failed_result(
                cycle_number=cycle_number,
                error=str(e),
                state=CycleOrchestrationState.FAILED.value,
                state_transitions=transitions,
            )
            result.next_action = next_action
            if next_action == "stop":
                result.gating_reason = (
                    f"Max retries ({self._config.failure_max_retries}) exceeded"
                )

            self._cycle_history.append(result)
            return result

    def run_loop(
        self,
        max_cycles: int | None = None,
        interval_seconds: float | None = None,
    ) -> list[OrchestrationCycleResult]:
        """持续运行编排循环.

        Args:
            max_cycles: 最大循环次数 (None = 使用配置值)
            interval_seconds: 循环间隔 (None = 使用配置值)

        Returns:
            list[OrchestrationCycleResult]: 所有周期结果
        """
        max_cyc = max_cycles or self._config.max_cycles or 0
        interval = (
            interval_seconds
            if interval_seconds is not None
            else self._config.cycle_interval_seconds
        )

        results: list[OrchestrationCycleResult] = []
        cycle_count = 0

        while self._active:
            if self._paused:
                time.sleep(0.1)
                continue

            if max_cyc > 0 and cycle_count >= max_cyc:
                break

            result = self.run_cycle()
            results.append(result)
            cycle_count += 1

            if result.should_stop or result.next_action == "stop":
                break

            if result.next_action == "pause":
                self._paused = True
                continue

            if interval > 0:
                time.sleep(interval)

        return results

    # ═══════════════════════════════════════════════════════════
    # Phase Methods
    # ═══════════════════════════════════════════════════════════

    def _observe(self) -> dict[str, Any]:
        """Phase 1: OBSERVE — 观察当前状态."""
        return {
            "strategy_state": self._strategy_state.to_dict(),
            "active": self._active,
            "paused": self._paused,
            "total_cycles": self._total_cycles,
            "experience_count": len(self._experiences),
            "reward_count": len(self._rewards),
            "has_previous_execution": self._previous_execution_result is not None,
        }

    def _measure_outcome(self) -> OutcomeMeasurement:
        """Phase 2: MEASURE_OUTCOME — 测量上一轮执行结果.

        Day 7.8 Step 3:
            使用 OutcomeMeasurer 将 LearningExecutionResult 转化为
            可量化的 OutcomeMeasurement，填补 Execution → Evaluation 的缺口。

        Returns:
            OutcomeMeasurement: 测量结果 (含 reward_delta, confidence_delta,
                                success_delta, learning_gain)
        """
        prev = self._previous_execution_result

        if prev is None:
            return self._outcome_measurer.measure(
                execution_result=None,
                cycle_number=self._total_cycles,
            )

        # 收集执行前后指标
        metrics_before: dict[str, float] = {}
        metrics_after: dict[str, float] = {}
        if prev.previous_state:
            metrics_before = prev.previous_state.get("metrics", {})
        if prev.new_state:
            metrics_after = prev.new_state.get("metrics", {})

        return self._outcome_measurer.measure(
            execution_result=prev,
            cycle_number=self._total_cycles,
            previous_strategy_state=prev.previous_state,
            current_strategy_state=prev.new_state,
            metrics_before=metrics_before,
            metrics_after=metrics_after,
        )

    def _ingest_feedback(self, outcome: OutcomeMeasurement) -> Any:
        """Phase 2.5: FEEDBACK_INGESTION — 分类并路由反馈.

        Day 7.8 Step 4:
            将 OutcomeMeasurement 通过 FeedbackRouter 分类为
            GOOD_LEARNING / BAD_LEARNING / INSUFFICIENT_DATA / STAGNANT，
            并生成可执行的反馈信号。

        Args:
            outcome: OutcomeMeasurement 实例

        Returns:
            LearningFeedback
        """
        return self._feedback_router.route(
            outcome_measurement=outcome,
            cycle_number=self._total_cycles,
            effectiveness=None,  # 此时尚未评估，evaluate 在后
        )

    def _gate_cycle(self, feedback: Any, effectiveness: Any = None) -> Any:
        """Phase 2.6: CYCLE_GATE — 门控评估.

        Day 7.8 Step 5:
            基于 Feedback 分类 + 历史趋势，独立控制学习循环的
            继续/暂停/回滚/请求更多数据 决策。

        Args:
            feedback: LearningFeedback 实例
            effectiveness: LearningEffectiveness 实例 (此时可能尚未评估)

        Returns:
            CycleGateResult
        """
        if not self._config.enable_cycle_gate:
            from .models.cycle_gate_models import CycleGateResult
            return CycleGateResult.continue_result(
                cycle_number=self._total_cycles,
                reason="Cycle gate disabled",
            )

        return self._cycle_gate.evaluate(
            feedback=feedback,
            effectiveness=effectiveness,
            cycle_number=self._total_cycles,
            cycle_history=self._cycle_history,
            config=self._config,
        )

    def _adjust_policy(
        self,
        feedback: Any,
        gate_result: Any,
        effectiveness: Any,
    ) -> Any:
        """Phase 3.5: POLICY_ADJUSTMENT — 策略参数调整.

        Day 7.8 Step 6:
            将 Feedback + Gate + Effectiveness 三路信号融合，
            生成具体的策略参数调整建议。

        Args:
            feedback: LearningFeedback 实例
            gate_result: CycleGateResult 实例
            effectiveness: LearningEffectiveness 实例

        Returns:
            PolicyAdjustmentSet
        """
        if not self._config.enable_policy_adjustment:
            from .models.learning_policy_models import PolicyAdjustmentSet
            return PolicyAdjustmentSet.empty(cycle_number=self._total_cycles)

        return self._policy_adjuster.adjust(
            feedback=feedback,
            gate_result=gate_result,
            effectiveness=effectiveness,
            current_state=self._strategy_state,
            cycle_number=self._total_cycles,
        )

    def _evaluate(self) -> Any:
        """Phase 3: EVALUATE — 评估学习有效性.

        如果有 DecisionImpactTracker 数据，执行评估。
        否则返回空评估结果。
        """
        # 如果没有 tracker 数据，返回空评估
        try:
            from .evaluation.decision_impact_tracker import DecisionImpactTracker

            # 尝试使用已有的 tracker
            tracker = DecisionImpactTracker()
            effectiveness = self._evaluator.evaluate(tracker)
            return effectiveness
        except Exception:
            return None

    def _decide_policy(self, effectiveness: Any) -> LearningPolicyDecision:
        """Phase 4: POLICY_DECISION — 生成策略决策.

        将 LearningEffectiveness 反馈给 LearningPolicyController，
        生成策略决策。

        Day 7.11 Step 1:
            查询 PatternStore 获取历史 Pattern，注入决策上下文。

        Args:
            effectiveness: LearningEffectiveness 评估结果

        Returns:
            LearningPolicyDecision
        """
        # [Day 7.11] 查询历史 Pattern
        context_patterns = self._query_relevant_patterns()

        # 调用 LearningPolicyController.evaluate()
        decision = self._policy_controller.evaluate(
            effectiveness=effectiveness,
            adaptive_confidence=None,  # TODO: 集成 AdaptiveConfidenceEngine
            current_state=self._strategy_state,
            triggered_by=f"cycle_{self._total_cycles}",
            context_patterns=context_patterns,
        )
        return decision

    def _query_relevant_patterns(self) -> list[Any]:
        """[Day 7.11] 查询与当前策略状态相关的历史 Pattern.

        从 PatternStore 中获取所有 Pattern，按当前策略状态筛选。

        Returns:
            list[PatternMemory]: 相关 Pattern 列表
        """
        if self._pattern_store is None:
            return []

        try:
            all_patterns = self._pattern_store.get_all()
        except Exception:
            return []

        if not all_patterns:
            return []

        # 按当前策略模式筛选相关 Pattern
        current_mode = self._strategy_state.learning_mode
        relevant: list[Any] = []

        for p in all_patterns:
            perf = getattr(p, "performance", None)
            if perf is None:
                continue

            # 排除已归档/废弃的 Pattern
            success_rate = getattr(perf, "success_rate", 0.0)
            if success_rate <= 0.0:
                continue

            # 匹配策略模式
            tags = getattr(p, "tags", [])
            action = getattr(p, "action", None)
            action_type = getattr(action, "action_type", "") if action else ""

            # 简单匹配: 任何有成功率的 Pattern 都视为相关
            relevant.append(p)

        return relevant

    def _execute(
        self,
        policy_decision: LearningPolicyDecision,
    ) -> LearningExecutionResult:
        """Phase 5: EXECUTE — 执行策略决策.

        通过 LearningExecutionAdapter 路由执行。

        Args:
            policy_decision: 策略决策

        Returns:
            LearningExecutionResult
        """
        # 构建执行上下文
        exec_context = LearningExecutionContext(
            context={
                "cycle_number": self._total_cycles,
                "strategy_mode": self._strategy_state.learning_mode,
            },
            experiences=self._experiences,
            rewards=self._rewards,
            decision_memory=self._decision_memory,
            experience_store=self._experience_store,
            pattern_store=self._pattern_store,
            loop_controller=self._loop_controller,
            strategy_optimizer=self._strategy_optimizer,
        )

        return self._execution_adapter.execute(policy_decision, exec_context)

    def _update_memory(
        self,
        execution_result: LearningExecutionResult,
    ) -> dict[str, Any]:
        """Phase 6: UPDATE_MEMORY — 更新记忆/策略状态.

        如果执行结果改变了策略状态，更新内部状态。

        Args:
            execution_result: 执行结果

        Returns:
            dict: 记忆更新记录
        """
        updates: dict[str, Any] = {}

        if execution_result.strategy_updated and execution_result.new_state:
            try:
                self._strategy_state = LearningStrategyState.from_dict(
                    execution_result.new_state
                )
                updates["strategy_updated"] = True
                updates["new_mode"] = self._strategy_state.learning_mode
            except Exception:
                updates["strategy_updated"] = False

        if execution_result.memory_updated:
            updates["memory_updated"] = True
            if execution_result.memory_result:
                updates["memory_result"] = execution_result.memory_result

        # 从执行结果中提取学习循环数据
        if execution_result.learning_cycle:
            updates["learning_cycle"] = execution_result.learning_cycle

        return updates

    def _optimize_strategy(
        self,
        effectiveness: Any,
        execution_result: LearningExecutionResult,
    ) -> bool:
        """Phase 7: OPTIMIZE_STRATEGY — 优化策略参数.

        基于评估结果优化策略参数。

        Args:
            effectiveness: 有效性评估
            execution_result: 执行结果

        Returns:
            bool: 是否进行了优化
        """
        if not self._config.enable_auto_optimization:
            return False

        if self._strategy_optimizer is None:
            return False

        if effectiveness is None:
            return False

        try:
            # 使用 LearningStrategyOptimizer.optimize()
            new_state, adjustments = self._strategy_optimizer.optimize(
                effectiveness=effectiveness,
                trend=None,  # TODO: 集成 ImprovementTrend
                current_state=self._strategy_state,
            )
            self._strategy_state = new_state
            return len(adjustments) > 0
        except Exception:
            return False

    # ═══════════════════════════════════════════════════════════
    # State Machine
    # ═══════════════════════════════════════════════════════════

    def _transition(
        self,
        new_state: CycleOrchestrationState,
        transitions: list[dict[str, Any]],
    ) -> None:
        """执行状态转换并记录."""
        previous = self._current_state
        self._current_state = new_state
        transitions.append({
            "from": previous.value,
            "to": new_state.value,
            "timestamp": "",  # 轻量记录
        })

    # ═══════════════════════════════════════════════════════════
    # Query
    # ═══════════════════════════════════════════════════════════

    def get_status(self) -> dict[str, Any]:
        """获取编排器状态."""
        return {
            "active": self._active,
            "paused": self._paused,
            "current_state": self._current_state.value,
            "total_cycles": self._total_cycles,
            "strategy_state": self._strategy_state.to_dict(),
            "cycle_history_count": len(self._cycle_history),
            "config": self._config.to_dict(),
            "has_previous_execution": self._previous_execution_result is not None,
            "retry_count": self._retry_count,
            "cycle_gate": self._cycle_gate.get_stats(),
            "policy_adjuster": self._policy_adjuster.get_stats(),
        }

    def get_cycle_summary(self) -> dict[str, Any]:
        """获取周期运行摘要."""
        if not self._cycle_history:
            return {
                "total_cycles": 0,
                "completed": 0,
                "paused": 0,
                "failed": 0,
                "stopped": 0,
            }

        completed = sum(
            1 for r in self._cycle_history
            if r.state == CycleOrchestrationState.COMPLETED.value
        )
        paused = sum(
            1 for r in self._cycle_history
            if r.state == CycleOrchestrationState.PAUSED.value
        )
        failed = sum(
            1 for r in self._cycle_history
            if r.state == CycleOrchestrationState.FAILED.value
        )
        stopped = sum(1 for r in self._cycle_history if r.next_action == "stop")

        return {
            "total_cycles": self._total_cycles,
            "completed": completed,
            "paused": paused,
            "failed": failed,
            "stopped": stopped,
        }

    def __repr__(self) -> str:
        return (
            f"LearningCycleOrchestrator("
            f"state={self._current_state.value}, "
            f"cycles={self._total_cycles}, "
            f"active={self._active})"
        )


__all__ = [
    "LearningCycleOrchestrator",
    "_should_gate_on_effectiveness",
    "CycleGate",
    "GateDecision",
    "PolicyAdjuster",
]