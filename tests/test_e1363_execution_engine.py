"""E13.6.3 Execution Engine — 测试套件.

覆盖:
  - BaseExecutor (ExecutionResult, GuardContext, 执行器基类)
  - ExecutionStateMachine (状态转移, 完整周期, 回滚)
  - ExecutorRegistry (注册, 查询, 默认执行器)
  - AuditLog (审计记录, 查询, 统计, Memory格式)
  - ExecutionEngine (引擎核心, 编排执行, 回滚)
  - Integration (完整链路: ActionPlan → Engine → Results → AuditLog)
"""

import pytest

from market_ops.creative_vision_runtime.growth_runtime.execution import (
    ActionDependency,
    ActionGraph,
    ActionNode,
    ActionPlan,
    ActionPlanner,
    ActionStatus,
    ActionTemplate,
    AuditEntry,
    AuditLog,
    BaseExecutor,
    EngineResult,
    ExecutionAction,
    ExecutionActionType,
    ExecutionContext,
    ExecutionDomain,
    ExecutionEngine,
    ExecutionPhase,
    ExecutionPriority,
    ExecutionResult,
    ExecutionResultStatus,
    ExecutionStateMachine,
    ExecutionStatus,
    ExecutionTask,
    ExecutorRegistry,
    GuardContext,
    PlanPhase,
    TaskConverter,
    TransitionRecord,
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def make_action(
    action_type: ExecutionActionType = ExecutionActionType.MONITOR,
    domain: ExecutionDomain = ExecutionDomain.MONITOR,
    priority: ExecutionPriority = ExecutionPriority.MEDIUM,
    **kwargs,
) -> ExecutionAction:
    params = {"action_type": action_type, "domain": domain, "priority": priority}
    params.update(kwargs)
    return ExecutionAction(**params)


def make_node(
    action_type: ExecutionActionType = ExecutionActionType.MONITOR,
    phase: PlanPhase = PlanPhase.EXECUTE,
    **kwargs,
) -> ActionNode:
    action = make_action(action_type=action_type, **kwargs)
    return ActionNode(action=action, phase=phase)


def make_plan(
    nodes: list[ActionNode] | None = None,
    rollback_enabled: bool = True,
    **kwargs,
) -> ActionPlan:
    plan = ActionPlan(rollback_enabled=rollback_enabled, **kwargs)
    if nodes:
        for n in nodes:
            plan.add_node(n)
        plan.execution_order = [n.node_id for n in nodes]
        plan.rollback_order = list(reversed([n.node_id for n in nodes]))
    return plan


# ═══════════════════════════════════════════════════════════════
# 1. BaseExecutor — ExecutionResult
# ═══════════════════════════════════════════════════════════════


class TestExecutionResult:
    """ExecutionResult 模型测试."""

    def test_create_default(self):
        result = ExecutionResult()
        assert result.action_id == ""
        assert result.status == ExecutionResultStatus.SUCCESS
        assert result.is_success is True
        assert result.is_failed is False
        assert result.needs_approval is False

    def test_create_with_params(self):
        result = ExecutionResult(
            action_id="act_001",
            action_type=ExecutionActionType.CREATE_CREATIVE,
            status=ExecutionResultStatus.FAILED,
            executor="CreativeExecutor",
            error_message="API timeout",
            reason="creative generation failed",
            confidence=0.85,
        )
        assert result.action_id == "act_001"
        assert result.action_type == ExecutionActionType.CREATE_CREATIVE
        assert result.status == ExecutionResultStatus.FAILED
        assert result.executor == "CreativeExecutor"
        assert result.error_message == "API timeout"
        assert result.reason == "creative generation failed"
        assert result.confidence == 0.85
        assert result.is_success is False
        assert result.is_failed is True

    def test_pending_approval_status(self):
        result = ExecutionResult(status=ExecutionResultStatus.PENDING_APPROVAL)
        assert result.needs_approval is True
        assert result.is_success is False
        assert result.is_failed is False

    def test_rolled_back_status(self):
        result = ExecutionResult(status=ExecutionResultStatus.ROLLED_BACK)
        assert result.is_success is False
        assert result.is_failed is False

    def test_duration_ms_with_timestamps(self):
        result = ExecutionResult(
            started_at="2026-07-27T10:00:00+00:00",
            completed_at="2026-07-27T10:00:01+00:00",
        )
        assert result.duration_ms == 1000.0

    def test_duration_ms_no_timestamps(self):
        result = ExecutionResult()
        assert result.duration_ms == 0.0

    def test_duration_ms_invalid_timestamps(self):
        result = ExecutionResult(started_at="invalid", completed_at="also_invalid")
        assert result.duration_ms == 0.0

    def test_to_dict(self):
        result = ExecutionResult(
            action_id="act_001",
            action_type=ExecutionActionType.MONITOR,
            executor="TestExecutor",
            before={"budget": 100},
            after={"budget": 120},
        )
        d = result.to_dict()
        assert d["action_id"] == "act_001"
        assert d["action_type"] == "monitor"
        assert d["executor"] == "TestExecutor"
        assert d["before"] == {"budget": 100}
        assert d["after"] == {"budget": 120}
        assert d["status"] == "success"

    def test_unique_result_id(self):
        r1 = ExecutionResult()
        r2 = ExecutionResult()
        assert r1.result_id != r2.result_id

    def test_skipped_status(self):
        result = ExecutionResult(status=ExecutionResultStatus.SKIPPED)
        assert result.is_success is False
        assert result.is_failed is False
        assert result.needs_approval is False

    def test_timed_out_status(self):
        result = ExecutionResult(status=ExecutionResultStatus.TIMED_OUT)
        assert result.is_failed is False
        assert result.is_success is False


# ═══════════════════════════════════════════════════════════════
# 2. BaseExecutor — GuardContext
# ═══════════════════════════════════════════════════════════════


class TestGuardContext:
    """GuardContext 安全上下文测试."""

    def test_default_values(self):
        gc = GuardContext()
        assert gc.risk_level == "safe"
        assert gc.requires_approval is False
        assert gc.budget_impact == 0.0
        assert gc.confidence == 0.0
        assert gc.cooldown_minutes == 0
        assert gc.max_retries == 3
        assert gc.allowed_domains == []
        assert gc.is_high_risk is False

    def test_high_risk(self):
        gc = GuardContext(risk_level="high")
        assert gc.is_high_risk is True

    def test_critical_risk(self):
        gc = GuardContext(risk_level="critical")
        assert gc.is_high_risk is True

    def test_medium_risk_not_high(self):
        gc = GuardContext(risk_level="medium")
        assert gc.is_high_risk is False

    def test_requires_approval(self):
        gc = GuardContext(requires_approval=True, confidence=0.75)
        assert gc.requires_approval is True
        assert gc.confidence == 0.75

    def test_budget_impact(self):
        gc = GuardContext(budget_impact=5000.0)
        assert gc.budget_impact == 5000.0

    def test_custom_values(self):
        gc = GuardContext(
            risk_level="high",
            requires_approval=True,
            budget_impact=10000.0,
            confidence=0.9,
            cooldown_minutes=30,
            max_retries=5,
            allowed_domains=["campaign", "creative"],
            metadata={"source": "decision_engine"},
        )
        assert gc.risk_level == "high"
        assert gc.is_high_risk is True
        assert gc.cooldown_minutes == 30
        assert gc.max_retries == 5
        assert gc.allowed_domains == ["campaign", "creative"]
        assert gc.metadata == {"source": "decision_engine"}


# ═══════════════════════════════════════════════════════════════
# 2.5. ExecutionContext
# ═══════════════════════════════════════════════════════════════


class TestExecutionContext:
    """ExecutionContext 执行上下文测试."""

    def test_create_default(self):
        ctx = ExecutionContext()
        assert ctx.guard_context.risk_level == "safe"
        assert ctx.decision_id == ""
        assert ctx.user_confirmation == "none"
        assert ctx.risk_score == 0.0
        assert ctx.safety_check is True
        assert ctx.approval_required is False
        assert ctx.dry_run is False
        assert ctx.can_execute is True

    def test_create_with_params(self):
        gc = GuardContext(risk_level="medium", confidence=0.85)
        ctx = ExecutionContext(
            guard_context=gc,
            decision_id="dec_001",
            opportunity_id="opp_001",
            strategy_id="strat_001",
            task_id="task_001",
            reason="winner creative scale up",
        )
        assert ctx.guard_context.risk_level == "medium"
        assert ctx.guard_context.confidence == 0.85
        assert ctx.decision_id == "dec_001"
        assert ctx.opportunity_id == "opp_001"
        assert ctx.strategy_id == "strat_001"
        assert ctx.task_id == "task_001"
        assert ctx.reason == "winner creative scale up"

    def test_is_approved(self):
        ctx = ExecutionContext(user_confirmation="approved")
        assert ctx.is_approved is True
        assert ctx.is_denied is False
        assert ctx.is_pending_user is False

    def test_is_denied(self):
        ctx = ExecutionContext(user_confirmation="denied")
        assert ctx.is_denied is True
        assert ctx.can_execute is False

    def test_is_pending_user(self):
        ctx = ExecutionContext(user_confirmation="pending")
        assert ctx.is_pending_user is True
        assert ctx.is_approved is False

    def test_is_high_risk(self):
        ctx = ExecutionContext(guard_context=GuardContext(risk_level="high"))
        assert ctx.is_high_risk is True

    def test_needs_approval(self):
        ctx = ExecutionContext(
            guard_context=GuardContext(requires_approval=True),
            approval_required=True,
        )
        assert ctx.needs_approval is True

    def test_needs_approval_guard_only(self):
        ctx = ExecutionContext(
            guard_context=GuardContext(requires_approval=True),
        )
        assert ctx.needs_approval is True

    def test_no_approval_needed(self):
        ctx = ExecutionContext(
            guard_context=GuardContext(requires_approval=False),
            approval_required=False,
        )
        assert ctx.needs_approval is False

    def test_dry_run_cannot_execute(self):
        ctx = ExecutionContext(dry_run=True, user_confirmation="none")
        assert ctx.can_execute is False

    def test_dry_run_approved_can_execute(self):
        ctx = ExecutionContext(dry_run=True, user_confirmation="approved")
        assert ctx.can_execute is True

    def test_safety_check_false_cannot_execute(self):
        ctx = ExecutionContext(safety_check=False)
        assert ctx.can_execute is False

    def test_to_dict(self):
        ctx = ExecutionContext(
            decision_id="dec_001",
            task_id="task_001",
            reason="test",
            risk_score=0.3,
        )
        d = ctx.to_dict()
        assert d["decision_id"] == "dec_001"
        assert d["task_id"] == "task_001"
        assert d["reason"] == "test"
        assert d["risk_score"] == 0.3
        assert d["guard_context"]["risk_level"] == "safe"

    def test_from_guard_context(self):
        gc = GuardContext(risk_level="high", confidence=0.9)
        ctx = ExecutionContext.from_guard_context(
            gc,
            decision_id="dec_001",
            reason="from guard",
        )
        assert ctx.guard_context is gc
        assert ctx.decision_id == "dec_001"
        assert ctx.reason == "from guard"

    def test_safe_factory(self):
        ctx = ExecutionContext.safe(decision_id="dec_001")
        assert ctx.guard_context.risk_level == "safe"
        assert ctx.approval_required is False
        assert ctx.can_execute is True

    def test_medium_risk_factory(self):
        ctx = ExecutionContext.medium_risk(decision_id="dec_001")
        assert ctx.guard_context.risk_level == "medium"
        assert ctx.safety_check is True

    def test_high_risk_factory(self):
        ctx = ExecutionContext.high_risk(decision_id="dec_001")
        assert ctx.guard_context.risk_level == "high"
        assert ctx.approval_required is True
        assert ctx.guard_context.requires_approval is True

    def test_critical_factory(self):
        ctx = ExecutionContext.critical(decision_id="dec_001")
        assert ctx.guard_context.risk_level == "critical"
        assert ctx.approval_required is True
        assert ctx.user_confirmation == "pending"


# ═══════════════════════════════════════════════════════════════
# 3. BaseExecutor — 执行器基类
# ═══════════════════════════════════════════════════════════════


class _SuccessExecutor(BaseExecutor):
    """总是成功的测试执行器."""

    def _do_execute(self, action, guard_context):
        return ExecutionResult(
            action_id=action.action_id,
            action_type=action.action_type,
            status=ExecutionResultStatus.SUCCESS,
            before={"state": "before"},
            after={"state": "after"},
            reason="success",
        )


class _FailingExecutor(BaseExecutor):
    """总是失败的测试执行器."""

    def _do_execute(self, action, guard_context):
        return ExecutionResult(
            action_id=action.action_id,
            action_type=action.action_type,
            status=ExecutionResultStatus.FAILED,
            error_message="simulated failure",
            reason="simulated failure",
        )


class _ThrowingExecutor(BaseExecutor):
    """抛出异常的测试执行器."""

    def _do_execute(self, action, guard_context):
        raise RuntimeError("unexpected error")


class _RollbackExecutor(BaseExecutor):
    """支持回滚的测试执行器."""

    def _do_execute(self, action, guard_context):
        return ExecutionResult(
            action_id=action.action_id,
            action_type=action.action_type,
            status=ExecutionResultStatus.FAILED,
            error_message="failed",
        )

    def _rollback(self, action):
        return ExecutionResult(
            action_id=action.action_id,
            action_type=action.action_type,
            reason="rolled back",
        )


class _ValidatingExecutor(BaseExecutor):
    """带前置校验的执行器."""

    def _pre_validate(self, action, guard_context):
        return action.parameters.get("valid", True)

    def _do_execute(self, action, guard_context):
        return ExecutionResult(
            action_id=action.action_id,
            action_type=action.action_type,
            status=ExecutionResultStatus.SUCCESS,
        )


class TestBaseExecutor:
    """BaseExecutor 基类测试."""

    def test_name_default(self):
        executor = _SuccessExecutor()
        assert executor.name == "_SuccessExecutor"

    def test_name_custom(self):
        executor = _SuccessExecutor(name="CustomExecutor")
        assert executor.name == "CustomExecutor"

    def test_execute_success(self):
        executor = _SuccessExecutor()
        action = make_action(ExecutionActionType.CREATE_CREATIVE)
        result = executor.execute(action)

        assert result.is_success is True
        assert result.action_id == action.action_id
        assert result.executor == "_SuccessExecutor"
        assert result.before == {"state": "before"}
        assert result.after == {"state": "after"}
        assert result.started_at != ""
        assert result.completed_at != ""

    def test_execute_failure(self):
        executor = _FailingExecutor()
        action = make_action(ExecutionActionType.UPDATE_BUDGET)
        result = executor.execute(action)

        assert result.is_failed is True
        assert result.error_message == "simulated failure"

    def test_execute_throws_exception(self):
        executor = _ThrowingExecutor()
        action = make_action()
        result = executor.execute(action)

        assert result.is_failed is True
        assert result.status == ExecutionResultStatus.FAILED
        assert "unexpected error" in result.error_message

    def test_execute_with_approval_required(self):
        executor = _SuccessExecutor()
        action = make_action()
        gc = GuardContext(requires_approval=True)
        result = executor.execute(action, guard_context=gc)

        assert result.needs_approval is True
        assert result.status == ExecutionResultStatus.PENDING_APPROVAL
        assert result.reason == "approval_required"

    def test_execute_pre_validation_fails(self):
        executor = _ValidatingExecutor()
        action = make_action(parameters={"valid": False})
        result = executor.execute(action)

        assert result.status == ExecutionResultStatus.SKIPPED
        assert result.reason == "pre_validation_failed"

    def test_execute_pre_validation_passes(self):
        executor = _ValidatingExecutor()
        action = make_action(parameters={"valid": True})
        result = executor.execute(action)

        assert result.is_success is True

    def test_execution_count_tracking(self):
        executor = _SuccessExecutor()
        action = make_action()

        executor.execute(action)
        executor.execute(action)
        executor.execute(action)

        assert executor.execution_count == 3

    def test_success_rate(self):
        executor = _SuccessExecutor()
        action = make_action()

        executor.execute(action)
        executor.execute(action)

        assert executor.success_rate == 1.0

    def test_success_rate_with_failures(self):
        executor = _FailingExecutor()
        action = make_action()

        executor.execute(action)
        executor.execute(action)

        assert executor.success_rate == 0.0

    def test_rollback_success(self):
        executor = _RollbackExecutor()
        action = make_action()
        result = executor.rollback(action)

        assert result.status == ExecutionResultStatus.ROLLED_BACK
        assert result.reason == "rolled back"

    def test_rollback_not_implemented(self):
        executor = _SuccessExecutor()
        action = make_action()
        result = executor.rollback(action)

        assert result.status == ExecutionResultStatus.ROLLED_BACK
        assert result.reason == "rollback_not_implemented"

    def test_rollback_throws_exception(self):
        class _BadRollbackExecutor(BaseExecutor):
            def _do_execute(self, action, guard_context):
                return ExecutionResult()

            def _rollback(self, action):
                raise RuntimeError("rollback error")

        executor = _BadRollbackExecutor()
        action = make_action()
        result = executor.rollback(action)

        assert result.status == ExecutionResultStatus.FAILED
        assert "rollback error" in result.error_message

    def test_stats(self):
        executor = _SuccessExecutor(name="StatExecutor")
        action = make_action()
        executor.execute(action)
        executor.execute(action)

        stats = executor.stats()
        assert stats["name"] == "StatExecutor"
        assert stats["execution_count"] == 2
        assert stats["success_count"] == 2
        assert stats["failure_count"] == 0
        assert stats["success_rate"] == 1.0

    def test_execute_with_guard_context_confidence(self):
        executor = _SuccessExecutor()
        action = make_action()
        gc = GuardContext(confidence=0.92)
        result = executor.execute(action, guard_context=gc)

        assert result.confidence == 0.92


# ═══════════════════════════════════════════════════════════════
# 4. ExecutionStateMachine
# ═══════════════════════════════════════════════════════════════


class TestExecutionPhase:
    """ExecutionPhase 枚举测试."""

    def test_all_phases_exist(self):
        phases = [
            ExecutionPhase.CREATED,
            ExecutionPhase.VALIDATING,
            ExecutionPhase.READY,
            ExecutionPhase.EXECUTING,
            ExecutionPhase.SUCCESS,
            ExecutionPhase.VERIFYING,
            ExecutionPhase.COMPLETED,
            ExecutionPhase.FAILED,
            ExecutionPhase.ROLLBACK_PENDING,
            ExecutionPhase.ROLLBACK_EXECUTING,
            ExecutionPhase.ROLLED_BACK,
            ExecutionPhase.SKIPPED,
            ExecutionPhase.PENDING_APPROVAL,
            ExecutionPhase.TIMED_OUT,
        ]
        for p in phases:
            assert isinstance(p, ExecutionPhase)

    def test_terminal_phases(self):
        terminals = ExecutionStateMachine.get_terminal_phases()
        assert ExecutionPhase.COMPLETED in terminals
        assert ExecutionPhase.ROLLED_BACK in terminals
        assert ExecutionPhase.SKIPPED in terminals
        assert ExecutionPhase.EXECUTING not in terminals


class TestTransitionRecord:
    """TransitionRecord 测试."""

    def test_create(self):
        record = TransitionRecord(
            from_phase=ExecutionPhase.CREATED,
            to_phase=ExecutionPhase.VALIDATING,
            reason="开始校验",
        )
        assert record.from_phase == ExecutionPhase.CREATED
        assert record.to_phase == ExecutionPhase.VALIDATING
        assert record.reason == "开始校验"
        assert record.timestamp != ""

    def test_with_metadata(self):
        record = TransitionRecord(
            from_phase=ExecutionPhase.EXECUTING,
            to_phase=ExecutionPhase.SUCCESS,
            reason="执行成功",
            metadata={"duration_ms": 150},
        )
        assert record.metadata["duration_ms"] == 150


class TestExecutionStateMachine:
    """ExecutionStateMachine 状态机测试."""

    def test_initial_state(self):
        sm = ExecutionStateMachine(node_id="node_001")
        assert sm.current_phase == ExecutionPhase.CREATED
        assert sm.node_id == "node_001"
        assert sm.is_terminal is False
        assert sm.transition_count == 0
        assert sm.created_at != ""

    def test_valid_transition(self):
        sm = ExecutionStateMachine()
        result = sm.transition(ExecutionPhase.VALIDATING, "开始校验")
        assert result is True
        assert sm.current_phase == ExecutionPhase.VALIDATING
        assert sm.transition_count == 1

    def test_invalid_transition_raises(self):
        sm = ExecutionStateMachine()
        with pytest.raises(ValueError, match="非法状态转移"):
            sm.transition(ExecutionPhase.EXECUTING)  # CREATED → EXECUTING 非法

    def test_try_transition_invalid(self):
        sm = ExecutionStateMachine()
        result = sm.try_transition(ExecutionPhase.EXECUTING)
        assert result is False
        assert sm.current_phase == ExecutionPhase.CREATED

    def test_can_transition(self):
        sm = ExecutionStateMachine()
        assert sm.can_transition(ExecutionPhase.VALIDATING) is True
        assert sm.can_transition(ExecutionPhase.SKIPPED) is True
        assert sm.can_transition(ExecutionPhase.EXECUTING) is False

    def test_full_success_cycle(self):
        sm = ExecutionStateMachine(node_id="node_001")
        history = sm.execute_full_cycle(reason="测试执行")

        assert sm.current_phase == ExecutionPhase.COMPLETED
        assert sm.is_terminal is True
        assert sm.is_success is True
        assert len(history) == 5  # VALIDATING → READY → EXECUTING → SUCCESS → COMPLETED
        assert history[0].to_phase == ExecutionPhase.VALIDATING
        assert history[-1].to_phase == ExecutionPhase.COMPLETED

    def test_full_failure_rollback_cycle(self):
        sm = ExecutionStateMachine()
        # 先到 EXECUTING
        sm.mark_validating()
        sm.mark_ready()
        sm.mark_executing()

        history = sm.execute_failure_rollback(reason="执行失败")

        assert sm.current_phase == ExecutionPhase.ROLLED_BACK
        assert sm.is_terminal is True
        assert sm.is_rolled_back is True
        # history 包含之前 3 次转移 + 4 次回滚 = 7
        assert len(history) == 7

    def test_history_tracking(self):
        sm = ExecutionStateMachine()
        sm.mark_validating("v1")
        sm.mark_ready("r1")
        sm.mark_executing("e1")
        sm.mark_success("s1")
        sm.mark_completed("c1")

        assert sm.transition_count == 5
        assert len(sm.history) == 5
        assert sm.history[0].reason == "v1"
        assert sm.history[-1].reason == "c1"

    def test_is_running(self):
        sm = ExecutionStateMachine()
        assert sm.is_running is False
        sm.mark_validating()
        sm.mark_ready()
        sm.mark_executing()
        assert sm.is_running is True

    def test_is_failed(self):
        sm = ExecutionStateMachine()
        sm.mark_validating()
        sm.mark_ready()
        sm.mark_executing()
        sm.mark_failed()
        assert sm.is_failed is True

    def test_skipped_path(self):
        sm = ExecutionStateMachine()
        sm.mark_skipped("跳过")
        assert sm.current_phase == ExecutionPhase.SKIPPED
        assert sm.is_terminal is True

    def test_pending_approval_to_ready(self):
        sm = ExecutionStateMachine()
        sm.mark_validating()
        sm.mark_ready()
        sm.mark_executing()
        sm.mark_pending_approval("需要审批")
        assert sm.current_phase == ExecutionPhase.PENDING_APPROVAL

        sm.mark_ready("审批通过")
        assert sm.current_phase == ExecutionPhase.READY

    def test_pending_approval_to_skipped(self):
        sm = ExecutionStateMachine()
        sm.mark_validating()
        sm.mark_ready()
        sm.mark_executing()
        sm.mark_pending_approval("需要审批")
        sm.mark_skipped("审批拒绝")
        assert sm.current_phase == ExecutionPhase.SKIPPED

    def test_timed_out_to_failed(self):
        sm = ExecutionStateMachine()
        sm.mark_validating()
        sm.mark_ready()
        sm.mark_executing()
        sm.mark_timed_out("超时")
        assert sm.current_phase == ExecutionPhase.TIMED_OUT

        sm.mark_failed("超时失败")
        assert sm.current_phase == ExecutionPhase.FAILED

    def test_get_valid_transitions(self):
        transitions = ExecutionStateMachine.get_valid_transitions(ExecutionPhase.CREATED)
        assert ExecutionPhase.VALIDATING in transitions
        assert ExecutionPhase.SKIPPED in transitions
        assert ExecutionPhase.EXECUTING not in transitions

    def test_to_dict(self):
        sm = ExecutionStateMachine(node_id="node_001")
        sm.mark_validating("校验")
        sm.mark_ready("就绪")

        d = sm.to_dict()
        assert d["node_id"] == "node_001"
        assert d["current_phase"] == "ready"
        assert d["transition_count"] == 2
        assert len(d["history"]) == 2

    def test_last_transition_at(self):
        sm = ExecutionStateMachine()
        sm.mark_validating()
        assert sm.last_transition_at >= sm.created_at

    def test_completed_is_terminal(self):
        sm = ExecutionStateMachine()
        sm.execute_full_cycle()
        assert sm.is_terminal is True
        # 终态不能再转移
        with pytest.raises(ValueError):
            sm.transition(ExecutionPhase.EXECUTING)

    def test_rolled_back_is_terminal(self):
        sm = ExecutionStateMachine()
        sm.mark_validating()
        sm.mark_ready()
        sm.mark_executing()
        sm.execute_failure_rollback()
        assert sm.is_terminal is True

    def test_verify_to_failed(self):
        sm = ExecutionStateMachine()
        sm.mark_validating()
        sm.mark_ready()
        sm.mark_executing()
        sm.mark_success()
        sm.mark_verifying()
        sm.mark_failed("验证失败")
        assert sm.current_phase == ExecutionPhase.FAILED


# ═══════════════════════════════════════════════════════════════
# 5. ExecutorRegistry
# ═══════════════════════════════════════════════════════════════


class TestExecutorRegistry:
    """ExecutorRegistry 注册表测试."""

    def test_register_and_get(self):
        registry = ExecutorRegistry()
        executor = _SuccessExecutor()
        registry.register(ExecutionActionType.CREATE_CREATIVE, executor)

        assert registry.has(ExecutionActionType.CREATE_CREATIVE) is True
        assert registry.get(ExecutionActionType.CREATE_CREATIVE) is executor

    def test_get_unregistered_returns_none(self):
        registry = ExecutorRegistry()
        assert registry.get(ExecutionActionType.UPDATE_BUDGET) is None

    def test_get_unregistered_with_default(self):
        registry = ExecutorRegistry()
        default_exec = _SuccessExecutor(name="default")
        registry.set_default(default_exec)

        result = registry.get(ExecutionActionType.UPDATE_BUDGET)
        assert result is default_exec

    def test_register_many(self):
        registry = ExecutorRegistry()
        e1 = _SuccessExecutor(name="e1")
        e2 = _FailingExecutor(name="e2")

        registry.register_many({
            ExecutionActionType.CREATE_CREATIVE: e1,
            ExecutionActionType.UPDATE_BUDGET: e2,
        })

        assert registry.get(ExecutionActionType.CREATE_CREATIVE) is e1
        assert registry.get(ExecutionActionType.UPDATE_BUDGET) is e2

    def test_unregister(self):
        registry = ExecutorRegistry()
        e = _SuccessExecutor()
        registry.register(ExecutionActionType.MONITOR, e)
        assert registry.has(ExecutionActionType.MONITOR) is True

        registry.unregister(ExecutionActionType.MONITOR)
        assert registry.has(ExecutionActionType.MONITOR) is False

    def test_unregister_nonexistent(self):
        registry = ExecutorRegistry()
        registry.unregister(ExecutionActionType.MONITOR)  # 不抛异常

    def test_get_all(self):
        registry = ExecutorRegistry()
        e1 = _SuccessExecutor(name="e1")
        e2 = _FailingExecutor(name="e2")
        registry.register(ExecutionActionType.MONITOR, e1)
        registry.register(ExecutionActionType.UPDATE_BUDGET, e2)

        all_executors = registry.get_all()
        assert len(all_executors) == 2
        assert all_executors[ExecutionActionType.MONITOR] is e1

    def test_get_registered_types(self):
        registry = ExecutorRegistry()
        registry.register(ExecutionActionType.MONITOR, _SuccessExecutor())
        registry.register(ExecutionActionType.CREATE_CREATIVE, _SuccessExecutor())

        types = registry.get_registered_types()
        assert ExecutionActionType.MONITOR in types
        assert ExecutionActionType.CREATE_CREATIVE in types
        assert len(types) == 2

    def test_len_and_contains(self):
        registry = ExecutorRegistry()
        registry.register(ExecutionActionType.MONITOR, _SuccessExecutor())

        assert len(registry) == 1
        assert ExecutionActionType.MONITOR in registry
        assert ExecutionActionType.UPDATE_BUDGET not in registry

    def test_stats(self):
        registry = ExecutorRegistry()
        e = _SuccessExecutor(name="TestExec")
        e.execute(make_action())  # 增加执行计数
        registry.register(ExecutionActionType.MONITOR, e)

        stats = registry.stats()
        assert stats["total_registered"] == 1
        assert stats["has_default"] is False
        assert "TestExec" in stats["executors"]

    def test_overwrite_registration(self):
        registry = ExecutorRegistry()
        e1 = _SuccessExecutor(name="e1")
        e2 = _SuccessExecutor(name="e2")
        registry.register(ExecutionActionType.MONITOR, e1)
        registry.register(ExecutionActionType.MONITOR, e2)

        assert registry.get(ExecutionActionType.MONITOR) is e2


# ═══════════════════════════════════════════════════════════════
# 6. AuditLog
# ═══════════════════════════════════════════════════════════════


class TestAuditEntry:
    """AuditEntry 审计条目测试."""

    def test_create_default(self):
        entry = AuditEntry()
        assert entry.action_id == ""
        assert entry.result == ExecutionResultStatus.SUCCESS
        assert entry.is_success is True
        assert entry.is_failed is False

    def test_create_with_params(self):
        entry = AuditEntry(
            action_id="act_001",
            action_type=ExecutionActionType.CREATE_CREATIVE,
            reason="winner detected",
            confidence=0.88,
            executor="CreativeExecutor",
            before={"count": 0},
            after={"count": 1},
            result=ExecutionResultStatus.SUCCESS,
            node_id="node_001",
            plan_id="plan_001",
            task_id="task_001",
            decision_id="dec_001",
        )
        assert entry.action_id == "act_001"
        assert entry.reason == "winner detected"
        assert entry.confidence == 0.88
        assert entry.node_id == "node_001"
        assert entry.plan_id == "plan_001"
        assert entry.task_id == "task_001"
        assert entry.decision_id == "dec_001"
        assert entry.timestamp != ""

    def test_from_execution_result(self):
        result = ExecutionResult(
            action_id="act_001",
            action_type=ExecutionActionType.UPDATE_BUDGET,
            status=ExecutionResultStatus.SUCCESS,
            executor="BudgetExecutor",
            before={"budget": 100},
            after={"budget": 120},
            reason="scale up",
            confidence=0.9,
            error_message="",
        )
        entry = AuditEntry.from_execution_result(
            result,
            reason="budget adjustment",
            node_id="node_001",
            plan_id="plan_001",
            task_id="task_001",
            decision_id="dec_001",
        )
        assert entry.action_id == "act_001"
        assert entry.reason == "budget adjustment"
        assert entry.confidence == 0.9
        assert entry.before == {"budget": 100}
        assert entry.after == {"budget": 120}
        assert entry.node_id == "node_001"
        assert entry.plan_id == "plan_001"
        assert entry.task_id == "task_001"
        assert entry.decision_id == "dec_001"

    def test_from_execution_result_fallback_reason(self):
        result = ExecutionResult(reason="original reason")
        entry = AuditEntry.from_execution_result(result)
        assert entry.reason == "original reason"

    def test_to_dict(self):
        entry = AuditEntry(
            action_id="act_001",
            action_type=ExecutionActionType.MONITOR,
            reason="check",
            executor="MonitorExecutor",
        )
        d = entry.to_dict()
        assert d["action_id"] == "act_001"
        assert d["action_type"] == "monitor"
        assert d["reason"] == "check"
        assert d["executor"] == "MonitorExecutor"
        assert d["result"] == "success"

    def test_is_failed(self):
        entry = AuditEntry(result=ExecutionResultStatus.FAILED)
        assert entry.is_failed is True
        assert entry.is_success is False

    def test_needs_approval(self):
        entry = AuditEntry(result=ExecutionResultStatus.PENDING_APPROVAL)
        assert entry.needs_approval is True

    def test_unique_entry_id(self):
        e1 = AuditEntry()
        e2 = AuditEntry()
        assert e1.entry_id != e2.entry_id


class TestAuditLog:
    """AuditLog 审计日志测试."""

    def _make_result(self, action_id="act_001", status=ExecutionResultStatus.SUCCESS):
        return ExecutionResult(
            action_id=action_id,
            action_type=ExecutionActionType.MONITOR,
            status=status,
            executor="TestExecutor",
            before={},
            after={},
        )

    def test_record_returns_entry(self):
        log = AuditLog()
        result = self._make_result()
        entry = log.record(result, reason="test", task_id="task_001")

        assert isinstance(entry, AuditEntry)
        assert entry.action_id == "act_001"
        assert entry.task_id == "task_001"
        assert len(log) == 1

    def test_record_multiple(self):
        log = AuditLog()
        log.record(self._make_result("act_001"), task_id="task_001")
        log.record(self._make_result("act_002"), task_id="task_001")
        log.record(self._make_result("act_003"), task_id="task_002")

        assert len(log) == 3

    def test_get_by_task(self):
        log = AuditLog()
        log.record(self._make_result("act_001"), task_id="task_001")
        log.record(self._make_result("act_002"), task_id="task_001")
        log.record(self._make_result("act_003"), task_id="task_002")

        entries = log.get_by_task("task_001")
        assert len(entries) == 2
        assert entries[0].action_id == "act_001"
        assert entries[1].action_id == "act_002"

    def test_get_by_plan(self):
        log = AuditLog()
        log.record(self._make_result("act_001"), plan_id="plan_001")
        log.record(self._make_result("act_002"), plan_id="plan_002")

        assert len(log.get_by_plan("plan_001")) == 1
        assert len(log.get_by_plan("plan_002")) == 1
        assert len(log.get_by_plan("plan_003")) == 0

    def test_get_by_decision(self):
        log = AuditLog()
        log.record(self._make_result("act_001"), decision_id="dec_001")
        log.record(self._make_result("act_002"), decision_id="dec_001")

        assert len(log.get_by_decision("dec_001")) == 2
        assert len(log.get_by_decision("dec_002")) == 0

    def test_get_by_action_type(self):
        log = AuditLog()
        r1 = ExecutionResult(
            action_id="act_001",
            action_type=ExecutionActionType.CREATE_CREATIVE,
            status=ExecutionResultStatus.SUCCESS,
        )
        r2 = ExecutionResult(
            action_id="act_002",
            action_type=ExecutionActionType.UPDATE_BUDGET,
            status=ExecutionResultStatus.SUCCESS,
        )
        log.record(r1)
        log.record(r2)

        creatives = log.get_by_action_type(ExecutionActionType.CREATE_CREATIVE)
        assert len(creatives) == 1
        assert creatives[0].action_id == "act_001"

    def test_get_successful(self):
        log = AuditLog()
        log.record(self._make_result("act_001", ExecutionResultStatus.SUCCESS))
        log.record(self._make_result("act_002", ExecutionResultStatus.FAILED))
        log.record(self._make_result("act_003", ExecutionResultStatus.SUCCESS))

        successful = log.get_successful()
        assert len(successful) == 2

    def test_get_failed(self):
        log = AuditLog()
        log.record(self._make_result("act_001", ExecutionResultStatus.SUCCESS))
        log.record(self._make_result("act_002", ExecutionResultStatus.FAILED))
        log.record(self._make_result("act_003", ExecutionResultStatus.TIMED_OUT))

        failed = log.get_failed()
        assert len(failed) == 2

    def test_get_pending_approval(self):
        log = AuditLog()
        log.record(self._make_result("act_001", ExecutionResultStatus.PENDING_APPROVAL))
        log.record(self._make_result("act_002", ExecutionResultStatus.SUCCESS))

        pending = log.get_pending_approval()
        assert len(pending) == 1

    def test_get_recent(self):
        log = AuditLog()
        for i in range(20):
            log.record(self._make_result(f"act_{i:03d}"))

        recent = log.get_recent(5)
        assert len(recent) == 5
        assert recent[-1].action_id == "act_019"

    def test_get_all(self):
        log = AuditLog()
        log.record(self._make_result("act_001"))
        log.record(self._make_result("act_002"))

        all_entries = log.get_all()
        assert len(all_entries) == 2

    def test_stats_empty(self):
        log = AuditLog()
        stats = log.stats()
        assert stats["total"] == 0
        assert stats["success_rate"] == 0.0

    def test_stats_with_data(self):
        log = AuditLog()
        log.record(self._make_result("act_001", ExecutionResultStatus.SUCCESS))
        log.record(self._make_result("act_002", ExecutionResultStatus.SUCCESS))
        log.record(self._make_result("act_003", ExecutionResultStatus.FAILED))

        stats = log.stats()
        assert stats["total"] == 3
        assert stats["success_count"] == 2
        assert stats["failure_count"] == 1
        assert stats["success_rate"] == pytest.approx(2 / 3, rel=0.01)

    def test_to_memory_format(self):
        log = AuditLog()
        log.record(
            self._make_result("act_001", ExecutionResultStatus.SUCCESS),
            reason="budget scale",
            task_id="task_001",
            decision_id="dec_001",
        )

        memory = log.to_memory_format()
        assert len(memory) == 1
        assert memory[0]["action_id"] == "act_001"
        assert memory[0]["task_id"] == "task_001"
        assert memory[0]["decision_id"] == "dec_001"
        assert memory[0]["reason"] == "budget scale"
        assert "timestamp" in memory[0]

    def test_record_entry(self):
        log = AuditLog()
        entry = AuditEntry(action_id="direct_entry")
        log.record_entry(entry)
        assert len(log) == 1
        assert log.get_all()[0].action_id == "direct_entry"

    def test_clear(self):
        log = AuditLog()
        log.record(self._make_result("act_001"))
        log.record(self._make_result("act_002"))
        assert len(log) == 2

        log.clear()
        assert len(log) == 0

    def test_iter(self):
        log = AuditLog()
        log.record(self._make_result("act_001"))
        log.record(self._make_result("act_002"))

        entries = list(log)
        assert len(entries) == 2


# ═══════════════════════════════════════════════════════════════
# 7. ExecutionEngine — EngineResult
# ═══════════════════════════════════════════════════════════════


class TestEngineResult:
    """EngineResult 模型测试."""

    def test_create_default(self):
        result = EngineResult()
        assert result.plan_id == ""
        assert result.total_nodes == 0
        assert result.success_count == 0
        assert result.failure_count == 0
        assert result.status == ExecutionResultStatus.SUCCESS
        assert result.is_success is True
        assert result.has_failures is False

    def test_success_rate(self):
        result = EngineResult(total_nodes=10, success_count=8, failure_count=2)
        assert result.success_rate == 0.8

    def test_success_rate_empty(self):
        result = EngineResult(total_nodes=0)
        assert result.success_rate == 1.0

    def test_has_failures(self):
        result = EngineResult(failure_count=2)
        assert result.has_failures is True

    def test_to_dict(self):
        result = EngineResult(
            plan_id="plan_001",
            task_id="task_001",
            total_nodes=3,
            success_count=2,
            failure_count=1,
            status=ExecutionResultStatus.FAILED,
        )
        d = result.to_dict()
        assert d["plan_id"] == "plan_001"
        assert d["task_id"] == "task_001"
        assert d["total_nodes"] == 3
        assert d["success_count"] == 2
        assert d["failure_count"] == 1
        assert d["status"] == "failed"
        assert d["success_rate"] == pytest.approx(2 / 3, rel=0.01)

    def test_stats(self):
        result = EngineResult(
            total_nodes=5,
            success_count=3,
            failure_count=1,
            skipped_count=1,
            rollback_count=0,
        )
        s = result.stats()
        assert s["total"] == 5
        assert s["success"] == 3
        assert s["failure"] == 1
        assert s["skipped"] == 1
        assert s["rollback"] == 0

    def test_skipped_status(self):
        result = EngineResult(status=ExecutionResultStatus.SKIPPED)
        assert result.is_success is False


# ═══════════════════════════════════════════════════════════════
# 8. ExecutionEngine — 引擎核心
# ═══════════════════════════════════════════════════════════════


class TestExecutionEngine:
    """ExecutionEngine 执行引擎测试."""

    def test_execute_single_node(self):
        registry = ExecutorRegistry()
        registry.register(ExecutionActionType.MONITOR, _SuccessExecutor())

        engine = ExecutionEngine(registry)
        node = make_node(ExecutionActionType.MONITOR)
        plan = make_plan([node])

        result = engine.execute(plan)

        assert result.total_nodes == 1
        assert result.success_count == 1
        assert result.failure_count == 0
        assert result.is_success is True
        assert node.node_id in result.node_results

    def test_execute_multiple_nodes(self):
        registry = ExecutorRegistry()
        registry.register(ExecutionActionType.MONITOR, _SuccessExecutor())
        registry.register(ExecutionActionType.CREATE_CREATIVE, _SuccessExecutor())
        registry.register(ExecutionActionType.UPDATE_BUDGET, _SuccessExecutor())

        engine = ExecutionEngine(registry)
        nodes = [
            make_node(ExecutionActionType.MONITOR),
            make_node(ExecutionActionType.CREATE_CREATIVE),
            make_node(ExecutionActionType.UPDATE_BUDGET),
        ]
        plan = make_plan(nodes)

        result = engine.execute(plan)

        assert result.total_nodes == 3
        assert result.success_count == 3
        assert result.failure_count == 0
        assert len(result.node_results) == 3

    def test_execute_missing_executor(self):
        registry = ExecutorRegistry()
        engine = ExecutionEngine(registry)
        node = make_node(ExecutionActionType.MONITOR)
        plan = make_plan([node])

        result = engine.execute(plan)

        assert result.skipped_count == 1
        assert result.success_count == 0

    def test_execute_with_failure(self):
        registry = ExecutorRegistry()
        registry.register(ExecutionActionType.MONITOR, _FailingExecutor())

        engine = ExecutionEngine(registry)
        node = make_node(ExecutionActionType.MONITOR)
        plan = make_plan([node])

        result = engine.execute(plan)

        assert result.failure_count == 1
        assert result.success_count == 0
        assert result.status == ExecutionResultStatus.FAILED

    def test_execute_mixed_results(self):
        registry = ExecutorRegistry()
        registry.register(ExecutionActionType.MONITOR, _SuccessExecutor())
        registry.register(ExecutionActionType.CREATE_CREATIVE, _FailingExecutor())

        engine = ExecutionEngine(registry)
        nodes = [
            make_node(ExecutionActionType.MONITOR),
            make_node(ExecutionActionType.CREATE_CREATIVE),
        ]
        plan = make_plan(nodes)

        result = engine.execute(plan)

        assert result.success_count == 1
        assert result.failure_count == 1
        assert result.status == ExecutionResultStatus.FAILED

    def test_execute_with_approval_required(self):
        registry = ExecutorRegistry()
        registry.register(ExecutionActionType.MONITOR, _SuccessExecutor())

        engine = ExecutionEngine(registry)
        node = make_node(ExecutionActionType.MONITOR)
        plan = make_plan([node])
        gc = GuardContext(requires_approval=True)

        result = engine.execute(plan, guard_context=gc)

        assert result.skipped_count == 1
        assert result.success_count == 0

    def test_execute_with_decision_id(self):
        registry = ExecutorRegistry()
        registry.register(ExecutionActionType.MONITOR, _SuccessExecutor())

        engine = ExecutionEngine(registry)
        node = make_node(ExecutionActionType.MONITOR)
        plan = make_plan([node])

        result = engine.execute(plan, decision_id="dec_001", reason="test decision")

        # 验证审计日志记录了 decision_id
        entries = engine.audit_log.get_by_decision("dec_001")
        assert len(entries) == 1
        assert entries[0].reason == "test decision"

    def test_audit_log_records_all_actions(self):
        registry = ExecutorRegistry()
        registry.register(ExecutionActionType.MONITOR, _SuccessExecutor())
        registry.register(ExecutionActionType.CREATE_CREATIVE, _SuccessExecutor())

        engine = ExecutionEngine(registry)
        nodes = [
            make_node(ExecutionActionType.MONITOR),
            make_node(ExecutionActionType.CREATE_CREATIVE),
        ]
        plan = make_plan(nodes)

        engine.execute(plan)

        # 2 条审计记录
        assert len(engine.audit_log) == 2
        entries = engine.audit_log.get_all()
        assert entries[0].plan_id == plan.plan_id
        assert entries[1].plan_id == plan.plan_id

    def test_state_machine_tracking(self):
        registry = ExecutorRegistry()
        registry.register(ExecutionActionType.MONITOR, _SuccessExecutor())

        engine = ExecutionEngine(registry)
        node = make_node(ExecutionActionType.MONITOR)
        plan = make_plan([node])

        engine.execute(plan)

        sm = engine.get_state_machine(node.node_id)
        assert sm is not None
        assert sm.current_phase == ExecutionPhase.COMPLETED
        assert sm.is_success is True

    def test_state_machine_failure_tracking(self):
        registry = ExecutorRegistry()
        registry.register(ExecutionActionType.MONITOR, _FailingExecutor())

        engine = ExecutionEngine(registry)
        node = make_node(ExecutionActionType.MONITOR)
        plan = make_plan([node], rollback_enabled=False)

        engine.execute(plan)

        sm = engine.get_state_machine(node.node_id)
        assert sm is not None
        assert sm.current_phase == ExecutionPhase.FAILED

    def test_execute_with_rollback_enabled(self):
        registry = ExecutorRegistry()
        registry.register(ExecutionActionType.MONITOR, _RollbackExecutor())

        engine = ExecutionEngine(registry)
        node = make_node(ExecutionActionType.MONITOR)
        plan = make_plan([node], rollback_enabled=True)

        result = engine.execute(plan)

        assert result.rollback_count == 1
        sm = engine.get_state_machine(node.node_id)
        assert sm.current_phase == ExecutionPhase.ROLLED_BACK

    def test_execute_with_rollback_disabled(self):
        registry = ExecutorRegistry()
        registry.register(ExecutionActionType.MONITOR, _RollbackExecutor())

        engine = ExecutionEngine(registry)
        node = make_node(ExecutionActionType.MONITOR)
        plan = make_plan([node], rollback_enabled=False)

        result = engine.execute(plan)

        assert result.rollback_count == 0
        sm = engine.get_state_machine(node.node_id)
        assert sm.current_phase == ExecutionPhase.FAILED

    def test_execute_with_guard_context(self):
        registry = ExecutorRegistry()
        registry.register(ExecutionActionType.MONITOR, _SuccessExecutor())

        engine = ExecutionEngine(registry)
        node = make_node(ExecutionActionType.MONITOR)
        plan = make_plan([node])
        gc = GuardContext(risk_level="safe", confidence=0.95, budget_impact=0)

        result = engine.execute(plan, guard_context=gc)

        assert result.is_success is True
        assert result.success_count == 1

    def test_execute_custom_execution_order(self):
        registry = ExecutorRegistry()
        registry.register(ExecutionActionType.MONITOR, _SuccessExecutor())
        registry.register(ExecutionActionType.CREATE_CREATIVE, _SuccessExecutor())

        engine = ExecutionEngine(registry)
        n1 = make_node(ExecutionActionType.MONITOR)
        n2 = make_node(ExecutionActionType.CREATE_CREATIVE)
        plan = make_plan([n1, n2])

        # 自定义顺序: n2 先执行
        plan.execution_order = [n2.node_id, n1.node_id]

        result = engine.execute(plan)
        assert result.execution_order == [n2.node_id, n1.node_id]
        assert result.success_count == 2

    def test_execute_empty_plan(self):
        registry = ExecutorRegistry()
        engine = ExecutionEngine(registry)
        plan = ActionPlan()

        result = engine.execute(plan)

        assert result.total_nodes == 0
        # 空计划所有节点都被跳过 → status = SKIPPED
        assert result.status == ExecutionResultStatus.SKIPPED

    def test_execute_plan_with_no_execution_order(self):
        registry = ExecutorRegistry()
        registry.register(ExecutionActionType.MONITOR, _SuccessExecutor())

        engine = ExecutionEngine(registry)
        node = make_node(ExecutionActionType.MONITOR)
        plan = ActionPlan()
        plan.add_node(node)
        # 不设置 execution_order, engine 应 fallback 到 nodes 列表

        result = engine.execute(plan)

        assert result.total_nodes == 1
        assert result.success_count == 1

    def test_execute_exception_in_node(self):
        registry = ExecutorRegistry()
        registry.register(ExecutionActionType.MONITOR, _ThrowingExecutor())

        engine = ExecutionEngine(registry)
        node = make_node(ExecutionActionType.MONITOR)
        plan = make_plan([node])

        result = engine.execute(plan)

        assert result.failure_count == 1
        assert "unexpected error" in result.node_results[node.node_id].error_message
        # 审计日志仍然记录了异常
        assert len(engine.audit_log) == 1

    def test_rollback_plan(self):
        registry = ExecutorRegistry()
        registry.register(ExecutionActionType.MONITOR, _RollbackExecutor())
        registry.register(ExecutionActionType.CREATE_CREATIVE, _RollbackExecutor())

        engine = ExecutionEngine(registry)
        n1 = make_node(ExecutionActionType.MONITOR)
        n2 = make_node(ExecutionActionType.CREATE_CREATIVE)
        plan = make_plan([n1, n2])

        result = engine.rollback_plan(plan)

        assert result.rollback_count == 2
        assert result.failure_count == 0
        assert result.status == ExecutionResultStatus.SUCCESS

    def test_rollback_plan_no_rollback_order(self):
        registry = ExecutorRegistry()
        engine = ExecutionEngine(registry)
        plan = ActionPlan()  # 无 rollback_order

        result = engine.rollback_plan(plan)

        assert result.status == ExecutionResultStatus.SKIPPED
        assert result.error_message == "无回滚顺序"

    def test_rollback_plan_missing_executor(self):
        registry = ExecutorRegistry()
        engine = ExecutionEngine(registry)
        node = make_node(ExecutionActionType.MONITOR)
        plan = make_plan([node])

        result = engine.rollback_plan(plan)

        assert result.skipped_count == 1

    def test_get_all_state_machines(self):
        registry = ExecutorRegistry()
        registry.register(ExecutionActionType.MONITOR, _SuccessExecutor())
        registry.register(ExecutionActionType.CREATE_CREATIVE, _SuccessExecutor())

        engine = ExecutionEngine(registry)
        nodes = [make_node(ExecutionActionType.MONITOR), make_node(ExecutionActionType.CREATE_CREATIVE)]
        plan = make_plan(nodes)

        engine.execute(plan)

        sms = engine.get_all_state_machines()
        assert len(sms) == 2

    def test_get_running_nodes(self):
        registry = ExecutorRegistry()
        registry.register(ExecutionActionType.MONITOR, _SuccessExecutor())

        engine = ExecutionEngine(registry)
        node = make_node(ExecutionActionType.MONITOR)
        plan = make_plan([node])

        engine.execute(plan)

        # 执行完成后没有 running 节点
        assert len(engine.get_running_nodes()) == 0

    def test_get_failed_nodes(self):
        registry = ExecutorRegistry()
        registry.register(ExecutionActionType.MONITOR, _FailingExecutor())

        engine = ExecutionEngine(registry)
        node = make_node(ExecutionActionType.MONITOR)
        plan = make_plan([node], rollback_enabled=False)

        engine.execute(plan)

        failed = engine.get_failed_nodes()
        assert len(failed) == 1
        assert node.node_id in failed

    def test_stats(self):
        registry = ExecutorRegistry()
        registry.register(ExecutionActionType.MONITOR, _SuccessExecutor())

        engine = ExecutionEngine(registry)
        node = make_node(ExecutionActionType.MONITOR)
        plan = make_plan([node])

        engine.execute(plan)

        stats = engine.stats()
        assert "registry" in stats
        assert "audit_log" in stats
        assert "active_state_machines" in stats
        assert stats["active_state_machines"] == 1

    def test_engine_result_has_plan_id(self):
        registry = ExecutorRegistry()
        registry.register(ExecutionActionType.MONITOR, _SuccessExecutor())

        engine = ExecutionEngine(registry)
        node = make_node(ExecutionActionType.MONITOR)
        plan = make_plan([node])

        result = engine.execute(plan)
        assert result.plan_id == plan.plan_id
        assert result.task_id == plan.task_id

    def test_engine_result_timestamps(self):
        registry = ExecutorRegistry()
        registry.register(ExecutionActionType.MONITOR, _SuccessExecutor())

        engine = ExecutionEngine(registry)
        node = make_node(ExecutionActionType.MONITOR)
        plan = make_plan([node])

        result = engine.execute(plan)
        assert result.started_at != ""
        assert result.completed_at != ""
        assert result.started_at <= result.completed_at


# ═══════════════════════════════════════════════════════════════
# 9. Integration — 完整链路
# ═══════════════════════════════════════════════════════════════


class TestIntegration:
    """端到端集成测试: ActionPlan → ExecutionEngine → Results → AuditLog."""

    def test_full_pipeline_success(self):
        """完整成功链路."""
        registry = ExecutorRegistry()
        registry.register(ExecutionActionType.MONITOR, _SuccessExecutor())
        registry.register(ExecutionActionType.CREATE_CREATIVE, _SuccessExecutor())
        registry.register(ExecutionActionType.UPDATE_BUDGET, _SuccessExecutor())

        engine = ExecutionEngine(registry)

        # 模拟 Planner 产出
        nodes = [
            make_node(ExecutionActionType.MONITOR, phase=PlanPhase.PREPARE),
            make_node(ExecutionActionType.CREATE_CREATIVE, phase=PlanPhase.EXECUTE),
            make_node(ExecutionActionType.UPDATE_BUDGET, phase=PlanPhase.EXECUTE),
        ]
        plan = make_plan(nodes, task_id="task_full_001")

        # 执行
        result = engine.execute(
            plan,
            decision_id="dec_001",
            reason="winner creative detected",
        )

        # 验证 EngineResult
        assert result.is_success is True
        assert result.total_nodes == 3
        assert result.success_count == 3
        assert result.failure_count == 0

        # 验证 AuditLog
        entries = engine.audit_log.get_by_decision("dec_001")
        assert len(entries) == 3
        for entry in entries:
            assert entry.result == ExecutionResultStatus.SUCCESS
            assert entry.plan_id == plan.plan_id
            assert entry.task_id == "task_full_001"

        # 验证 State Machines
        for node in nodes:
            sm = engine.get_state_machine(node.node_id)
            assert sm is not None
            assert sm.current_phase == ExecutionPhase.COMPLETED

    def test_full_pipeline_partial_failure(self):
        """部分失败链路 — 一个节点失败, 其他继续."""
        registry = ExecutorRegistry()
        registry.register(ExecutionActionType.MONITOR, _SuccessExecutor())
        registry.register(ExecutionActionType.CREATE_CREATIVE, _FailingExecutor())
        registry.register(ExecutionActionType.UPDATE_BUDGET, _SuccessExecutor())

        engine = ExecutionEngine(registry)

        nodes = [
            make_node(ExecutionActionType.MONITOR),
            make_node(ExecutionActionType.CREATE_CREATIVE),
            make_node(ExecutionActionType.UPDATE_BUDGET),
        ]
        plan = make_plan(nodes, task_id="task_partial_001")

        result = engine.execute(plan, decision_id="dec_002")

        assert result.is_success is False
        assert result.success_count == 2
        assert result.failure_count == 1

        # 审计日志: 成功 + 失败 + 回滚 = 3 条 (失败节点有回滚)
        # 注意: 失败+回滚会产生2条记录, 加上2个成功 = 4条
        all_entries = engine.audit_log.get_all()
        assert len(all_entries) >= 3

        # 成功的节点状态正确
        sm0 = engine.get_state_machine(nodes[0].node_id)
        assert sm0.current_phase == ExecutionPhase.COMPLETED

        sm2 = engine.get_state_machine(nodes[2].node_id)
        assert sm2.current_phase == ExecutionPhase.COMPLETED

    def test_full_pipeline_with_rollback(self):
        """完整链路 + 回滚."""
        registry = ExecutorRegistry()
        registry.register(ExecutionActionType.MONITOR, _RollbackExecutor())
        registry.register(ExecutionActionType.CREATE_CREATIVE, _RollbackExecutor())

        engine = ExecutionEngine(registry)

        nodes = [
            make_node(ExecutionActionType.MONITOR),
            make_node(ExecutionActionType.CREATE_CREATIVE),
        ]
        plan = make_plan(nodes, rollback_enabled=True, task_id="task_rollback_001")

        result = engine.execute(plan, decision_id="dec_003")

        # 两个节点都失败并回滚
        assert result.rollback_count == 2
        assert result.failure_count == 2

        # 状态机: ROLLED_BACK
        for node in nodes:
            sm = engine.get_state_machine(node.node_id)
            assert sm.current_phase == ExecutionPhase.ROLLED_BACK

    def test_full_pipeline_memory_format(self):
        """验证 AuditLog → Memory 格式输出."""
        registry = ExecutorRegistry()
        registry.register(ExecutionActionType.MONITOR, _SuccessExecutor())
        registry.register(ExecutionActionType.CREATE_CREATIVE, _SuccessExecutor())

        engine = ExecutionEngine(registry)

        nodes = [
            make_node(ExecutionActionType.MONITOR),
            make_node(ExecutionActionType.CREATE_CREATIVE),
        ]
        plan = make_plan(nodes, task_id="task_memory_001")

        engine.execute(plan, decision_id="dec_004", reason="memory test")

        memory_data = engine.audit_log.to_memory_format()
        assert len(memory_data) == 2
        for record in memory_data:
            assert "action_id" in record
            assert "action_type" in record
            assert "reason" in record
            assert "confidence" in record
            assert "executor" in record
            assert "result" in record
            assert "before" in record
            assert "after" in record
            assert "task_id" in record
            assert "decision_id" in record
            assert "timestamp" in record

    def test_full_pipeline_guard_context_flow(self):
        """验证 GuardContext 贯穿全链路."""
        registry = ExecutorRegistry()
        registry.register(ExecutionActionType.MONITOR, _SuccessExecutor())

        engine = ExecutionEngine(registry)

        node = make_node(ExecutionActionType.MONITOR)
        plan = make_plan([node], task_id="task_guard_001")

        gc = GuardContext(
            risk_level="medium",
            requires_approval=False,
            confidence=0.88,
            budget_impact=500.0,
        )

        result = engine.execute(plan, guard_context=gc, decision_id="dec_005")

        assert result.is_success is True
        # 审计日志中 confidence 应传递
        entry = engine.audit_log.get_all()[0]
        assert entry.confidence == 0.88

    def test_full_pipeline_engine_stats_after_execution(self):
        """验证执行后引擎统计."""
        registry = ExecutorRegistry()
        registry.register(ExecutionActionType.MONITOR, _SuccessExecutor())
        registry.register(ExecutionActionType.CREATE_CREATIVE, _FailingExecutor())

        engine = ExecutionEngine(registry)

        nodes = [
            make_node(ExecutionActionType.MONITOR),
            make_node(ExecutionActionType.CREATE_CREATIVE),
        ]
        plan = make_plan(nodes)

        engine.execute(plan)

        stats = engine.stats()
        assert stats["active_state_machines"] == 2
        assert stats["audit_log"]["total"] >= 2

    def test_execute_with_execution_context(self):
        """验证通过 ExecutionContext 执行."""
        registry = ExecutorRegistry()
        registry.register(ExecutionActionType.MONITOR, _SuccessExecutor())
        registry.register(ExecutionActionType.CREATE_CREATIVE, _SuccessExecutor())

        engine = ExecutionEngine(registry)

        nodes = [
            make_node(ExecutionActionType.MONITOR),
            make_node(ExecutionActionType.CREATE_CREATIVE),
        ]
        plan = make_plan(nodes, task_id="task_ctx_001")

        ctx = ExecutionContext.safe(
            decision_id="dec_ctx_001",
            task_id="task_ctx_001",
            reason="context-based execution",
        )

        result = engine.execute(plan, context=ctx)

        assert result.is_success is True
        assert result.success_count == 2

        # 审计日志中记录了 decision_id
        entries = engine.audit_log.get_by_decision("dec_ctx_001")
        assert len(entries) == 2

    def test_execute_with_context_high_risk(self):
        """验证高风险 ExecutionContext."""
        registry = ExecutorRegistry()
        registry.register(ExecutionActionType.MONITOR, _SuccessExecutor())

        engine = ExecutionEngine(registry)
        node = make_node(ExecutionActionType.MONITOR)
        plan = make_plan([node])

        ctx = ExecutionContext.high_risk(decision_id="dec_high_risk")
        # high_risk 设置了 requires_approval=True, 执行器应返回 PENDING_APPROVAL
        result = engine.execute(plan, context=ctx)

        assert result.skipped_count == 1
        assert result.success_count == 0