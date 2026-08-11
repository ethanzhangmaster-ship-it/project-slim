"""E13.6.1 Execution Foundation — 测试套件.

覆盖:
  - Models (ExecutionStatus, ExecutionAction, ExecutionTask, ExecutionPlan)
  - TaskConverter (EXECUTE/TEST/BLOCK/ESCALATE/HOLD 转换)
  - Action 构建 (素材/预算/受众/通用)
  - 回滚计划生成
  - Edge Cases (空决策, 零参数, 边界值)
  - Integration (Decision → Task → Plan 完整流程)
"""

import pytest

from market_ops.creative_vision_runtime.growth_runtime.execution import (
    ExecutionAction,
    ExecutionActionType,
    ExecutionDomain,
    ExecutionPlan,
    ExecutionPriority,
    ExecutionStatus,
    ExecutionTask,
    TaskConverter,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.decision.models import (
    DecisionOutput,
    DecisionPlan,
    DecisionType,
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def make_decision(
    decision_type: DecisionType = DecisionType.TEST,
    strategy_name: str = "creative_mutation_v3",
    opportunity_id: str = "opp_001",
    strategy_id: str = "S001",
    confidence: float = 0.87,
    risk_score: float = 0.22,
    risk_level: str = "low",
    requires_approval: bool = False,
) -> DecisionOutput:
    """创建测试用 DecisionOutput."""
    return DecisionOutput(
        opportunity_id=opportunity_id,
        strategy_id=strategy_id,
        strategy_name=strategy_name,
        decision_type=decision_type,
        confidence=confidence,
        risk_score=risk_score,
        risk_level=risk_level,
        requires_approval=requires_approval,
    )


def make_decision_with_plan(
    decision_type: DecisionType = DecisionType.TEST,
    strategy_name: str = "creative_mutation_v3",
    test_budget: float = 500.0,
    execute_budget: float = 2000.0,
    duration_days: int = 3,
) -> DecisionOutput:
    """创建带执行计划的 DecisionOutput."""
    plan = DecisionPlan(
        action_type=decision_type.value,
        test_budget=test_budget,
        execute_budget=execute_budget,
        duration_days=duration_days,
        params={"generate_creatives": 5},
    )
    return DecisionOutput(
        opportunity_id="opp_001",
        strategy_id="S001",
        strategy_name=strategy_name,
        decision_type=decision_type,
        confidence=0.85,
        risk_score=0.15,
        action_plan=plan,
    )


# ═══════════════════════════════════════════════════════════════
# ExecutionStatus Enum Tests
# ═══════════════════════════════════════════════════════════════


class TestExecutionStatus:
    """ExecutionStatus 枚举测试."""

    def test_all_values_present(self):
        assert ExecutionStatus.PENDING.value == "pending"
        assert ExecutionStatus.QUEUED.value == "queued"
        assert ExecutionStatus.RUNNING.value == "running"
        assert ExecutionStatus.SUCCESS.value == "success"
        assert ExecutionStatus.FAILED.value == "failed"
        assert ExecutionStatus.CANCELLED.value == "cancelled"
        assert ExecutionStatus.ROLLED_BACK.value == "rolled_back"
        assert ExecutionStatus.TIMED_OUT.value == "timed_out"

    def test_is_string_enum(self):
        assert isinstance(ExecutionStatus.PENDING.value, str)
        assert ExecutionStatus.PENDING == "pending"


class TestExecutionActionType:
    """ExecutionActionType 枚举测试."""

    def test_all_action_types(self):
        types = list(ExecutionActionType)
        assert len(types) >= 10
        assert ExecutionActionType.CREATE_CAMPAIGN.value == "create_campaign"
        assert ExecutionActionType.MUTATE_CREATIVE.value == "mutate_creative"
        assert ExecutionActionType.SCALE_BUDGET.value == "scale_budget"

    def test_monitor_action(self):
        assert ExecutionActionType.MONITOR.value == "monitor"
        assert ExecutionActionType.COLLECT_RESULT.value == "collect_result"


class TestExecutionPriority:
    """ExecutionPriority 枚举测试."""

    def test_all_priorities(self):
        assert ExecutionPriority.CRITICAL.value == "critical"
        assert ExecutionPriority.HIGH.value == "high"
        assert ExecutionPriority.MEDIUM.value == "medium"
        assert ExecutionPriority.LOW.value == "low"


class TestExecutionDomain:
    """ExecutionDomain 枚举测试."""

    def test_all_domains(self):
        assert ExecutionDomain.CAMPAIGN.value == "campaign"
        assert ExecutionDomain.CREATIVE.value == "creative"
        assert ExecutionDomain.BUDGET.value == "budget"
        assert ExecutionDomain.MONITOR.value == "monitor"


# ═══════════════════════════════════════════════════════════════
# ExecutionAction Tests
# ═══════════════════════════════════════════════════════════════


class TestExecutionAction:
    """ExecutionAction 模型测试."""

    def test_default_action(self):
        action = ExecutionAction()
        assert action.action_type == ExecutionActionType.MONITOR
        assert action.status == ExecutionStatus.PENDING
        assert action.priority == ExecutionPriority.MEDIUM
        assert action.max_retries == 3
        assert not action.is_running

    def test_full_construction(self):
        action = ExecutionAction(
            action_type=ExecutionActionType.CREATE_CAMPAIGN,
            domain=ExecutionDomain.CAMPAIGN,
            target_entity="camp_001",
            parameters={"budget": 500},
            priority=ExecutionPriority.HIGH,
        )
        assert action.action_type == ExecutionActionType.CREATE_CAMPAIGN
        assert action.domain == ExecutionDomain.CAMPAIGN
        assert action.target_entity == "camp_001"

    def test_mark_running(self):
        action = ExecutionAction()
        action.mark_running()
        assert action.is_running
        assert action.started_at

    def test_mark_success(self):
        action = ExecutionAction()
        action.mark_success({"roas": 1.5})
        assert action.is_success
        assert action.is_completed
        assert action.result == {"roas": 1.5}

    def test_mark_failed(self):
        action = ExecutionAction()
        action.mark_failed("API timeout")
        assert action.is_failed
        assert action.is_completed
        assert action.error_message == "API timeout"

    def test_mark_cancelled(self):
        action = ExecutionAction()
        action.mark_cancelled("风险拦截")
        assert action.status == ExecutionStatus.CANCELLED
        assert action.error_message == "风险拦截"

    def test_can_retry(self):
        action = ExecutionAction(max_retries=3, retry_count=2)
        assert action.can_retry
        action.retry_count = 3
        assert not action.can_retry

    def test_depends_on(self):
        action = ExecutionAction(depends_on=["action_001", "action_002"])
        assert len(action.depends_on) == 2

    def test_rollback_action(self):
        action = ExecutionAction(rollback_action_id="rollback_001")
        assert action.rollback_action_id == "rollback_001"

    def test_to_dict(self):
        action = ExecutionAction(
            action_type=ExecutionActionType.CREATE_CAMPAIGN,
            domain=ExecutionDomain.CAMPAIGN,
            target_entity="camp_001",
            parameters={"budget": 500},
        )
        d = action.to_dict()
        assert d["action_type"] == "create_campaign"
        assert d["domain"] == "campaign"
        assert d["target_entity"] == "camp_001"
        assert d["status"] == "pending"


# ═══════════════════════════════════════════════════════════════
# ExecutionTask Tests
# ═══════════════════════════════════════════════════════════════


class TestExecutionTask:
    """ExecutionTask 模型测试."""

    def test_default_task(self):
        task = ExecutionTask()
        assert task.status == ExecutionStatus.PENDING
        assert task.action_count == 0
        assert not task.has_actions

    def test_add_action(self):
        task = ExecutionTask()
        action = ExecutionAction(action_type=ExecutionActionType.CREATE_CAMPAIGN)
        task.add_action(action)
        assert task.has_actions
        assert task.action_count == 1

    def test_get_pending_actions(self):
        task = ExecutionTask()
        a1 = ExecutionAction(action_type=ExecutionActionType.CREATE_CAMPAIGN)
        a2 = ExecutionAction(action_type=ExecutionActionType.MONITOR)
        a2.mark_success()
        task.add_action(a1)
        task.add_action(a2)
        pending = task.get_pending_actions()
        assert len(pending) == 1

    def test_get_failed_actions(self):
        task = ExecutionTask()
        a1 = ExecutionAction(action_type=ExecutionActionType.CREATE_CAMPAIGN)
        a1.mark_failed("error")
        task.add_action(a1)
        assert len(task.get_failed_actions()) == 1

    def test_get_actions_by_domain(self):
        task = ExecutionTask()
        task.add_action(ExecutionAction(domain=ExecutionDomain.CREATIVE))
        task.add_action(ExecutionAction(domain=ExecutionDomain.CAMPAIGN))
        task.add_action(ExecutionAction(domain=ExecutionDomain.CREATIVE))
        creative = task.get_actions_by_domain(ExecutionDomain.CREATIVE)
        assert len(creative) == 2

    def test_mark_running(self):
        task = ExecutionTask()
        task.mark_running()
        assert task.is_running
        assert task.started_at

    def test_mark_success(self):
        task = ExecutionTask()
        task.mark_success()
        assert task.is_success
        assert task.is_completed
        assert task.completed_at

    def test_mark_failed(self):
        task = ExecutionTask()
        task.mark_failed("Critical error")
        assert task.is_failed
        assert task.error_message == "Critical error"

    def test_mark_cancelled(self):
        task = ExecutionTask()
        task.mark_cancelled("Blocked by risk")
        assert task.status == ExecutionStatus.CANCELLED

    def test_all_actions_completed(self):
        task = ExecutionTask()
        a1 = ExecutionAction()
        a2 = ExecutionAction()
        a1.mark_success()
        a2.mark_success()
        task.add_action(a1)
        task.add_action(a2)
        assert task.all_actions_completed()

    def test_not_all_actions_completed(self):
        task = ExecutionTask()
        a1 = ExecutionAction()
        a2 = ExecutionAction()
        a1.mark_success()
        task.add_action(a1)
        task.add_action(a2)
        assert not task.all_actions_completed()

    def test_compute_overall_status_running(self):
        task = ExecutionTask()
        a1 = ExecutionAction()
        a1.mark_running()
        task.add_action(a1)
        assert task.compute_overall_status() == ExecutionStatus.RUNNING

    def test_compute_overall_status_success(self):
        task = ExecutionTask()
        a1 = ExecutionAction()
        a2 = ExecutionAction()
        a1.mark_success()
        a2.mark_success()
        task.add_action(a1)
        task.add_action(a2)
        assert task.compute_overall_status() == ExecutionStatus.SUCCESS

    def test_compute_overall_status_failed(self):
        task = ExecutionTask()
        a1 = ExecutionAction()
        a2 = ExecutionAction()
        a1.mark_success()
        a2.mark_failed("error")
        task.add_action(a1)
        task.add_action(a2)
        assert task.compute_overall_status() == ExecutionStatus.FAILED

    def test_to_dict(self):
        task = ExecutionTask(
            decision_id="dec_001",
            strategy_id="S001",
            strategy_name="Test",
            status=ExecutionStatus.PENDING,
        )
        task.add_action(ExecutionAction(action_type=ExecutionActionType.CREATE_CAMPAIGN))
        d = task.to_dict()
        assert d["decision_id"] == "dec_001"
        assert d["strategy_id"] == "S001"
        assert len(d["actions"]) == 1


# ═══════════════════════════════════════════════════════════════
# ExecutionPlan Tests
# ═══════════════════════════════════════════════════════════════


class TestExecutionPlan:
    """ExecutionPlan 模型测试."""

    def test_default_plan(self):
        plan = ExecutionPlan()
        assert plan.status == ExecutionStatus.PENDING
        assert plan.task_count == 0
        assert plan.progress == 0.0

    def test_add_task(self):
        plan = ExecutionPlan()
        task = ExecutionTask()
        task.add_action(ExecutionAction())
        task.add_action(ExecutionAction())
        plan.add_task(task)
        assert plan.task_count == 1
        assert plan.total_actions == 2

    def test_get_pending_tasks(self):
        plan = ExecutionPlan()
        t1 = ExecutionTask()
        t2 = ExecutionTask()
        t2.mark_running()
        plan.add_task(t1)
        plan.add_task(t2)
        assert len(plan.get_pending_tasks()) == 1

    def test_get_running_tasks(self):
        plan = ExecutionPlan()
        t1 = ExecutionTask()
        t1.mark_running()
        plan.add_task(t1)
        assert len(plan.get_running_tasks()) == 1

    def test_recompute_progress(self):
        plan = ExecutionPlan()
        task = ExecutionTask()
        a1 = ExecutionAction()
        a2 = ExecutionAction()
        a1.mark_success()
        task.add_action(a1)
        task.add_action(a2)
        plan.add_task(task)
        plan.recompute_progress()
        assert plan.total_actions == 2
        assert plan.completed_actions == 1
        assert plan.progress == 0.5

    def test_compute_status_running(self):
        plan = ExecutionPlan()
        t1 = ExecutionTask()
        t1.mark_running()
        plan.add_task(t1)
        assert plan.compute_status() == ExecutionStatus.RUNNING

    def test_compute_status_success(self):
        plan = ExecutionPlan()
        t1 = ExecutionTask()
        t1.mark_success()
        plan.add_task(t1)
        assert plan.compute_status() == ExecutionStatus.SUCCESS

    def test_to_dict(self):
        plan = ExecutionPlan(decision_id="dec_001")
        d = plan.to_dict()
        assert d["decision_id"] == "dec_001"
        assert d["status"] == "pending"


# ═══════════════════════════════════════════════════════════════
# TaskConverter Tests — 各决策类型转换
# ═══════════════════════════════════════════════════════════════


class TestTaskConverterExecute:
    """EXECUTE 类型转换测试."""

    def test_convert_execute_creative(self):
        converter = TaskConverter()
        decision = make_decision_with_plan(
            DecisionType.EXECUTE,
            strategy_name="creative_mutation_v3",
        )
        task = converter.convert(decision)
        assert task.status == ExecutionStatus.PENDING
        assert task.decision_type == "execute"
        assert task.strategy_id == "S001"
        assert task.priority == ExecutionPriority.HIGH
        assert task.has_actions
        # 素材策略应包含 mutation + upload + campaign
        action_types = [a.action_type for a in task.actions]
        assert ExecutionActionType.MUTATE_CREATIVE in action_types
        assert ExecutionActionType.UPLOAD_CREATIVE in action_types

    def test_convert_execute_budget(self):
        converter = TaskConverter()
        decision = make_decision_with_plan(
            DecisionType.EXECUTE,
            strategy_name="scale_budget_v2",
        )
        task = converter.convert(decision)
        action_types = [a.action_type for a in task.actions]
        assert ExecutionActionType.SCALE_BUDGET in action_types

    def test_convert_execute_has_rollback(self):
        converter = TaskConverter()
        decision = make_decision_with_plan(
            DecisionType.EXECUTE,
            strategy_name="creative_mutation",
        )
        task = converter.convert(decision)
        assert len(task.rollback_plan) > 0

    def test_convert_execute_has_deadline(self):
        converter = TaskConverter()
        decision = make_decision_with_plan(DecisionType.EXECUTE)
        task = converter.convert(decision)
        assert task.deadline
        assert task.estimated_duration_hours == 168.0


class TestTaskConverterTest:
    """TEST 类型转换测试."""

    def test_convert_test_creative(self):
        converter = TaskConverter()
        decision = make_decision_with_plan(
            DecisionType.TEST,
            strategy_name="creative_mutation",
        )
        task = converter.convert(decision)
        assert task.decision_type == "test"
        assert task.priority == ExecutionPriority.MEDIUM
        assert task.has_actions
        # TEST 应包含监控
        action_types = [a.action_type for a in task.actions]
        assert ExecutionActionType.MONITOR in action_types
        assert task.estimated_duration_hours == 72.0

    def test_convert_test_budget(self):
        converter = TaskConverter()
        decision = make_decision_with_plan(
            DecisionType.TEST,
            strategy_name="budget_adjust",
        )
        task = converter.convert(decision)
        action_types = [a.action_type for a in task.actions]
        assert ExecutionActionType.UPDATE_BUDGET in action_types

    def test_convert_test_has_rollback(self):
        converter = TaskConverter()
        decision = make_decision_with_plan(DecisionType.TEST)
        task = converter.convert(decision)
        assert len(task.rollback_plan) > 0

    def test_convert_test_creative_count(self):
        converter = TaskConverter(default_test_creative_count=5)
        decision = make_decision_with_plan(
            DecisionType.TEST,
            strategy_name="creative_mutation",
        )
        task = converter.convert(decision)
        mutate_action = next(
            (a for a in task.actions if a.action_type == ExecutionActionType.MUTATE_CREATIVE),
            None,
        )
        assert mutate_action is not None
        assert mutate_action.parameters["count"] == 5

    def test_convert_test_has_deadline(self):
        converter = TaskConverter()
        decision = make_decision_with_plan(DecisionType.TEST)
        task = converter.convert(decision)
        assert task.deadline
        assert task.estimated_duration_hours == 72.0


class TestTaskConverterBlockEscalateHold:
    """BLOCK/ESCALATE/HOLD 类型转换测试."""

    def test_convert_block(self):
        converter = TaskConverter()
        decision = make_decision(DecisionType.BLOCK, risk_score=0.9)
        task = converter.convert(decision)
        assert task.status == ExecutionStatus.CANCELLED
        assert task.error_message

    def test_convert_escalate(self):
        converter = TaskConverter()
        decision = make_decision(DecisionType.ESCALATE, risk_score=0.7)
        task = converter.convert(decision)
        assert task.status == ExecutionStatus.PENDING
        assert task.requires_approval
        assert "escalation_reason" in task.metadata

    def test_convert_hold(self):
        converter = TaskConverter()
        decision = make_decision(DecisionType.HOLD, confidence=0.3)
        task = converter.convert(decision)
        assert task.status == ExecutionStatus.PENDING
        assert task.metadata.get("observation") is True
        assert len(task.actions) == 1
        assert task.actions[0].action_type == ExecutionActionType.MONITOR


class TestTaskConverterBatch:
    """批量转换测试."""

    def test_convert_batch(self):
        converter = TaskConverter()
        decisions = [
            make_decision_with_plan(DecisionType.EXECUTE, strategy_name="creative_mutation"),
            make_decision_with_plan(DecisionType.TEST, strategy_name="budget_adjust"),
            make_decision(DecisionType.BLOCK),
        ]
        tasks = converter.convert_batch(decisions)
        assert len(tasks) == 3
        assert tasks[0].decision_type == "execute"
        assert tasks[1].decision_type == "test"
        assert tasks[2].status == ExecutionStatus.CANCELLED

    def test_convert_to_plan(self):
        converter = TaskConverter()
        decision = make_decision_with_plan(DecisionType.EXECUTE)
        plan = converter.convert_to_plan(decision)
        assert plan.task_count == 1
        assert plan.decision_id == decision.decision_id


# ═══════════════════════════════════════════════════════════════
# Action 构建细节测试
# ═══════════════════════════════════════════════════════════════


class TestActionConstruction:
    """Action 构建细节测试."""

    def test_creative_strategy_generates_creative_domain(self):
        converter = TaskConverter()
        decision = make_decision_with_plan(
            DecisionType.EXECUTE,
            strategy_name="creative_mutation",
        )
        task = converter.convert(decision)
        creative_actions = task.get_actions_by_domain(ExecutionDomain.CREATIVE)
        assert len(creative_actions) >= 2

    def test_budget_strategy_generates_budget_domain(self):
        converter = TaskConverter()
        decision = make_decision_with_plan(
            DecisionType.EXECUTE,
            strategy_name="scale_budget",
        )
        task = converter.convert(decision)
        budget_actions = task.get_actions_by_domain(ExecutionDomain.BUDGET)
        assert len(budget_actions) >= 1

    def test_execute_uses_execute_budget(self):
        converter = TaskConverter()
        decision = make_decision_with_plan(
            DecisionType.EXECUTE,
            execute_budget=3000.0,
        )
        task = converter.convert(decision)
        campaign_action = next(
            (a for a in task.actions if a.action_type == ExecutionActionType.CREATE_CAMPAIGN),
            None,
        )
        assert campaign_action is not None
        assert campaign_action.parameters["budget"] == 3000.0

    def test_test_uses_test_budget(self):
        converter = TaskConverter()
        decision = make_decision_with_plan(
            DecisionType.TEST,
            test_budget=800.0,
        )
        task = converter.convert(decision)
        campaign_action = next(
            (a for a in task.actions if a.action_type == ExecutionActionType.CREATE_CAMPAIGN),
            None,
        )
        assert campaign_action is not None
        assert campaign_action.parameters["budget"] == 800.0

    def test_mutate_action_has_mode(self):
        converter = TaskConverter()
        decision = make_decision_with_plan(DecisionType.EXECUTE, strategy_name="creative_mutation")
        task = converter.convert(decision)
        mutate = next(
            (a for a in task.actions if a.action_type == ExecutionActionType.MUTATE_CREATIVE),
            None,
        )
        assert mutate is not None
        assert mutate.parameters["mode"] == "execute"

    def test_test_mutate_action_has_test_mode(self):
        converter = TaskConverter()
        decision = make_decision_with_plan(DecisionType.TEST, strategy_name="creative_mutation")
        task = converter.convert(decision)
        mutate = next(
            (a for a in task.actions if a.action_type == ExecutionActionType.MUTATE_CREATIVE),
            None,
        )
        assert mutate is not None
        assert mutate.parameters["mode"] == "test"

    def test_rollback_plan_covers_campaign_actions(self):
        converter = TaskConverter()
        decision = make_decision_with_plan(DecisionType.EXECUTE, strategy_name="creative_mutation")
        task = converter.convert(decision)
        campaign_actions = [
            a for a in task.actions
            if a.action_type in {ExecutionActionType.CREATE_CAMPAIGN, ExecutionActionType.SCALE_BUDGET}
        ]
        assert len(task.rollback_plan) >= len(campaign_actions)


# ═══════════════════════════════════════════════════════════════
# Edge Cases & Integration
# ═══════════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界情况测试."""

    def test_empty_decision(self):
        converter = TaskConverter()
        decision = DecisionOutput()
        task = converter.convert(decision)
        assert task.status == ExecutionStatus.PENDING
        assert task.metadata.get("observation") is True

    def test_no_action_plan(self):
        converter = TaskConverter()
        decision = make_decision(DecisionType.EXECUTE, strategy_name="creative_mutation")
        task = converter.convert(decision)
        assert task.has_actions

    def test_custom_converter_settings(self):
        converter = TaskConverter(
            default_test_creative_count=10,
            default_test_budget=1000.0,
            default_test_duration_days=7,
        )
        # 不带 params 的决策，使用 converter 默认值
        plan = DecisionPlan(
            action_type="test",
            test_budget=1000.0,
            duration_days=7,
        )
        decision = DecisionOutput(
            opportunity_id="opp_001",
            strategy_id="S001",
            strategy_name="creative_mutation",
            decision_type=DecisionType.TEST,
            action_plan=plan,
        )
        task = converter.convert(decision)
        mutate = next(
            (a for a in task.actions if a.action_type == ExecutionActionType.MUTATE_CREATIVE),
            None,
        )
        assert mutate is not None
        assert mutate.parameters["count"] == 10

    def test_unknown_strategy_name(self):
        converter = TaskConverter()
        decision = make_decision_with_plan(DecisionType.EXECUTE, strategy_name="some_new_strategy")
        task = converter.convert(decision)
        # 应生成通用 Campaign + Monitor
        action_types = [a.action_type for a in task.actions]
        assert ExecutionActionType.CREATE_CAMPAIGN in action_types or ExecutionActionType.UPDATE_CAMPAIGN in action_types

    def test_audience_strategy(self):
        converter = TaskConverter()
        decision = make_decision_with_plan(DecisionType.EXECUTE, strategy_name="audience_expansion")
        task = converter.convert(decision)
        action_types = [a.action_type for a in task.actions]
        campaign_types = {ExecutionActionType.CREATE_CAMPAIGN, ExecutionActionType.UPDATE_CAMPAIGN}
        assert any(t in campaign_types for t in action_types)

    def test_decision_with_approval_requirement(self):
        converter = TaskConverter()
        decision = make_decision(DecisionType.EXECUTE, requires_approval=True)
        task = converter.convert(decision)
        assert task.requires_approval

    def test_decision_metadata_preserved(self):
        converter = TaskConverter()
        decision = make_decision_with_plan(DecisionType.EXECUTE)
        decision.metadata = {"source": "auto", "version": "1.0"}
        task = converter.convert(decision)
        assert task.metadata["source"] == "auto"


class TestFullIntegration:
    """端到端集成测试."""

    def test_decision_to_task_to_plan(self):
        """完整链路: Decision → Task → Plan."""
        decision = make_decision_with_plan(
            DecisionType.EXECUTE,
            strategy_name="creative_mutation",
            test_budget=500,
            execute_budget=2000,
        )
        converter = TaskConverter()

        # Step 1: Decision → Task
        task = converter.convert(decision)
        assert task.decision_id == decision.decision_id
        assert task.has_actions
        assert task.priority == ExecutionPriority.HIGH

        # Step 2: Task → Plan
        plan = converter.convert_to_plan(decision)
        assert plan.task_count == 1
        assert plan.total_actions > 0

        # Step 3: 模拟执行
        task.mark_running()
        assert task.is_running

        for action in task.actions:
            action.mark_running()
            action.mark_success()

        assert task.all_actions_completed()
        task.mark_success()
        assert task.is_success

    def test_test_workflow(self):
        """TEST 决策完整流程."""
        decision = make_decision_with_plan(
            DecisionType.TEST,
            strategy_name="creative_mutation",
            test_budget=500,
        )
        converter = TaskConverter()
        task = converter.convert(decision)

        assert task.decision_type == "test"
        assert task.priority == ExecutionPriority.MEDIUM
        assert task.has_actions
        assert task.estimated_duration_hours == 72.0

        # 监控 Action 存在
        monitor_actions = task.get_actions_by_domain(ExecutionDomain.MONITOR)
        assert len(monitor_actions) >= 1

    def test_block_workflow(self):
        """BLOCK 决策完整流程."""
        decision = make_decision(DecisionType.BLOCK, risk_score=0.9)
        converter = TaskConverter()
        task = converter.convert(decision)

        assert task.status == ExecutionStatus.CANCELLED
        assert not task.has_actions
        assert task.error_message

    def test_escalate_workflow(self):
        """ESCALATE 决策完整流程."""
        decision = make_decision(DecisionType.ESCALATE, risk_score=0.7)
        converter = TaskConverter()
        task = converter.convert(decision)

        assert task.status == ExecutionStatus.PENDING
        assert task.requires_approval
        assert not task.has_actions

    def test_create_execute_plan_with_multiple_steps(self):
        """创建多步骤执行计划."""
        converter = TaskConverter()
        plan = ExecutionPlan(decision_id="dec_001")

        # Step 1: 创建 Campaign
        task1 = converter.convert(make_decision_with_plan(DecisionType.EXECUTE, strategy_name="creative_mutation"))
        plan.add_task(task1)

        # Step 2: 监控
        task2 = converter.convert(make_decision(DecisionType.TEST, strategy_name="monitor"))
        plan.add_task(task2)

        assert plan.task_count == 2
        assert plan.total_actions > 0

    def test_rollback_integration(self):
        """回滚计划完整性."""
        converter = TaskConverter()
        decision = make_decision_with_plan(DecisionType.EXECUTE, strategy_name="creative_mutation")
        task = converter.convert(decision)

        assert len(task.rollback_plan) > 0
        for rb in task.rollback_plan:
            assert "action_id" in rb
            assert "rollback_type" in rb
            assert rb["rollback_type"] == "pause_campaign"

    def test_different_decision_types_produce_different_actions(self):
        """不同决策类型生成不同的 Action 序列."""
        converter = TaskConverter()

        execute_task = converter.convert(
            make_decision_with_plan(DecisionType.EXECUTE, strategy_name="creative_mutation")
        )
        test_task = converter.convert(
            make_decision_with_plan(DecisionType.TEST, strategy_name="creative_mutation")
        )

        # EXECUTE 和 TEST 的 Action 数量可能不同
        assert execute_task.has_actions
        assert test_task.has_actions
        # EXECUTE 的 creative count 应 >= TEST
        execute_mutate = next(
            (a for a in execute_task.actions if a.action_type == ExecutionActionType.MUTATE_CREATIVE),
            None,
        )
        test_mutate = next(
            (a for a in test_task.actions if a.action_type == ExecutionActionType.MUTATE_CREATIVE),
            None,
        )
        if execute_mutate and test_mutate:
            assert execute_mutate.parameters["count"] >= test_mutate.parameters["count"]