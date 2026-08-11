"""E13.7.7.5 Learning Execution Adapter — 策略执行适配器测试.

Day 7.7.5:
  测试 LearningExecutionAdapter 的所有执行分支，
  确保 PolicyDecision → Execution 的完整链路正确。

测试覆盖:
  - Contract: LearningExecutionAction enum, LearningExecutionResult 工厂/属性/序列化
  - Adapter Init: 默认创建
  - Action Classification: 5 种 DecisionType → Action 映射
  - Branch A (ALLOW_LEARNING): 执行学习循环 / 无 controller / 异常
  - Branch B (BLOCK_LEARNING): 阻止学习 / executed=False
  - Branch C (REFRESH_MEMORY): 记忆刷新 / 无 consolidator / 异常
  - Branch D (UPDATE_STRATEGY): AGGRESSIVE / BALANCED / CONSERVATIVE / 未知模式
  - Branch E (NO_ACTION / MAINTAIN): 无操作
  - Rollback: 可回滚 / 不可回滚 / 无 previous_state
  - execute_or_skip: None 决策 / 正常决策
  - Integration: 完整 Policy → Execution 流程
  - Edge Cases: 空 context / 部分依赖 / 重复执行
  - History: 执行历史追踪
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.learning_execution_adapter import (
    LearningExecutionAdapter,
    _MODE_PARAMS,
    _DECISION_TO_ACTION,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.learning_execution_models import (
    LearningExecutionAction,
    LearningExecutionContext,
    LearningExecutionResult,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.learning_strategy_models import (
    LearningMode,
    LearningPolicyDecision,
    LearningStrategyState,
    PolicyAction,
    PolicyDecisionType,
    PolicyPriority,
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def _make_state_dict(mode: str = "balanced") -> dict:
    """创建 LearningStrategyState 快照."""
    if mode == "aggressive":
        state = LearningStrategyState.aggressive()
    elif mode == "conservative":
        state = LearningStrategyState.conservative()
    else:
        state = LearningStrategyState.default()
    return state.to_dict()


def _make_policy_decision(
    decision_type: str = PolicyDecisionType.MAINTAIN.value,
    should_learn: bool = True,
    should_update_memory: bool = False,
    strategy_mode: str = LearningMode.BALANCED.value,
    previous_state: dict | None = None,
    reasons: list[str] | None = None,
) -> LearningPolicyDecision:
    """创建学习策略决策."""
    return LearningPolicyDecision(
        decision_type=decision_type,
        should_learn=should_learn,
        should_update_memory=should_update_memory,
        strategy_mode=strategy_mode,
        action=PolicyAction.INCREASE_EXPLORATION.value,
        priority=PolicyPriority.MEDIUM.value,
        evidence=["test_evidence"],
        reasons=reasons or ["test_reason"],
        confidence=0.80,
        previous_state_snapshot=previous_state or _make_state_dict(),
    )


def _make_context(
    loop_controller: object = None,
    memory_consolidator: object = None,
    strategy_optimizer: object = None,
) -> LearningExecutionContext:
    """创建执行上下文."""
    return LearningExecutionContext(
        context={"game": "TestGame", "country": "US"},
        loop_controller=loop_controller,
        memory_consolidator=memory_consolidator,
        strategy_optimizer=strategy_optimizer,
    )


def _make_mock_loop_controller() -> MagicMock:
    """创建 mock LearningLoopController."""
    mock = MagicMock()
    mock.cycle_count = 0
    cycle_result = MagicMock()
    cycle_result.cycle_confidence = 0.75
    cycle_result.actions_taken = ["knowledge_extracted", "pattern_predicted", "memory_updated"]
    cycle_result.improvements = ["System operating normally"]
    cycle_result.next_cycle_recommendations = ["Continue standard learning cycle"]
    cycle_result.metadata = {"cycle_number": 1}
    mock.run_cycle.return_value = cycle_result
    return mock


def _make_mock_memory_consolidator() -> MagicMock:
    """创建 mock MemoryConsolidator."""
    mock = MagicMock()
    result = MagicMock()
    result.total_evaluated = 100
    result.kept = 60
    result.archived = 25
    result.forgotten = 15
    result.core_patterns = 20
    result.temporary_patterns = 40
    result.noise_count = 30
    result.failed_count = 10
    result.avg_memory_value = 0.45
    result.retention_rate = 0.60
    result.cleanup_rate = 0.40
    mock.consolidate.return_value = result
    return mock


# ═══════════════════════════════════════════════════════════════
# 1. Contract — LearningExecutionAction
# ═══════════════════════════════════════════════════════════════


class TestLearningExecutionAction:
    """LearningExecutionAction 枚举测试."""

    def test_enum_values(self) -> None:
        assert LearningExecutionAction.EXECUTE_LEARNING.value == "execute_learning"
        assert LearningExecutionAction.BLOCK_LEARNING.value == "block_learning"
        assert LearningExecutionAction.REFRESH_MEMORY.value == "refresh_memory"
        assert LearningExecutionAction.UPDATE_STRATEGY.value == "update_strategy"
        assert LearningExecutionAction.NO_ACTION.value == "no_action"

    def test_enum_membership(self) -> None:
        assert LearningExecutionAction("execute_learning") == LearningExecutionAction.EXECUTE_LEARNING
        assert LearningExecutionAction("block_learning") == LearningExecutionAction.BLOCK_LEARNING
        assert LearningExecutionAction("no_action") == LearningExecutionAction.NO_ACTION

    def test_action_count(self) -> None:
        assert len(list(LearningExecutionAction)) == 5

    def test_all_actions_in_map(self) -> None:
        """所有 DecisionType 映射到有效 Action."""
        for action in _DECISION_TO_ACTION.values():
            assert action in LearningExecutionAction


# ═══════════════════════════════════════════════════════════════
# 2. Contract — LearningExecutionResult
# ═══════════════════════════════════════════════════════════════


class TestLearningExecutionResultDefaults:
    """LearningExecutionResult 默认值测试."""

    def test_default_creation(self) -> None:
        result = LearningExecutionResult()
        assert result.success is False
        assert result.action == LearningExecutionAction.NO_ACTION.value
        assert result.executed is False
        assert result.policy_decision_type == ""
        assert result.previous_state is None
        assert result.new_state is None
        assert result.memory_updated is False
        assert result.strategy_updated is False
        assert result.rollback_available is False
        assert result.error is None

    def test_default_properties(self) -> None:
        result = LearningExecutionResult()
        assert result.is_successful is False
        assert result.action_executed is False
        assert result.has_state_change is False
        assert result.can_rollback is False


class TestLearningExecutionResultFactory:
    """LearningExecutionResult 工厂方法测试."""

    def test_success_result(self) -> None:
        state = _make_state_dict()
        result = LearningExecutionResult.success_result(
            action=LearningExecutionAction.EXECUTE_LEARNING,
            policy_decision_type=PolicyDecisionType.ALLOW_LEARNING.value,
            previous_state=state,
            reasons=["test"],
        )
        assert result.success is True
        assert result.action == "execute_learning"
        assert result.executed is True
        assert result.policy_decision_type == "allow_learning"
        assert result.previous_state == state
        assert result.new_state == state
        assert result.rollback_available is True
        assert result.reasons == ["test"]

    def test_success_result_without_state(self) -> None:
        result = LearningExecutionResult.success_result(
            action=LearningExecutionAction.EXECUTE_LEARNING,
            policy_decision_type=PolicyDecisionType.ALLOW_LEARNING.value,
        )
        assert result.success is True
        assert result.rollback_available is False

    def test_success_result_with_custom_new_state(self) -> None:
        prev = _make_state_dict("balanced")
        new = _make_state_dict("aggressive")
        result = LearningExecutionResult.success_result(
            action=LearningExecutionAction.UPDATE_STRATEGY,
            policy_decision_type=PolicyDecisionType.ADJUST_MODE.value,
            previous_state=prev,
            new_state=new,
        )
        assert result.new_state == new
        assert result.new_state != prev

    def test_blocked_result(self) -> None:
        result = LearningExecutionResult.blocked_result(
            policy_decision_type=PolicyDecisionType.BLOCK_LEARNING.value,
            reasons=["blocked"],
        )
        assert result.success is True
        assert result.action == "block_learning"
        assert result.executed is False
        assert result.rollback_available is False
        assert result.reasons == ["blocked"]

    def test_no_action_result(self) -> None:
        result = LearningExecutionResult.no_action_result(
            policy_decision_type=PolicyDecisionType.MAINTAIN.value,
            reasons=["nothing to do"],
        )
        assert result.success is True
        assert result.action == "no_action"
        assert result.executed is False

    def test_error_result(self) -> None:
        state = _make_state_dict()
        result = LearningExecutionResult.error_result(
            action=LearningExecutionAction.EXECUTE_LEARNING,
            error="Something went wrong",
            policy_decision_type=PolicyDecisionType.ALLOW_LEARNING.value,
            previous_state=state,
        )
        assert result.success is False
        assert result.error == "Something went wrong"
        assert result.executed is True
        assert result.rollback_available is True  # 有 previous_state

    def test_error_result_without_state(self) -> None:
        result = LearningExecutionResult.error_result(
            action=LearningExecutionAction.EXECUTE_LEARNING,
            error="Something went wrong",
        )
        assert result.rollback_available is False


class TestLearningExecutionResultProperties:
    """LearningExecutionResult 属性测试."""

    def test_is_successful_with_error(self) -> None:
        result = LearningExecutionResult(success=True, error="minor")
        assert result.is_successful is False

    def test_is_successful_no_error(self) -> None:
        result = LearningExecutionResult(success=True)
        assert result.is_successful is True

    def test_action_executed_true(self) -> None:
        result = LearningExecutionResult(
            executed=True,
            action=LearningExecutionAction.EXECUTE_LEARNING.value,
        )
        assert result.action_executed is True

    def test_action_executed_no_action(self) -> None:
        result = LearningExecutionResult(
            executed=True,
            action=LearningExecutionAction.NO_ACTION.value,
        )
        assert result.action_executed is False

    def test_has_state_change_true(self) -> None:
        result = LearningExecutionResult(
            previous_state={"mode": "balanced"},
            new_state={"mode": "aggressive"},
        )
        assert result.has_state_change is True

    def test_has_state_change_false(self) -> None:
        state = {"mode": "balanced"}
        result = LearningExecutionResult(
            previous_state=state,
            new_state=dict(state),
        )
        assert result.has_state_change is False

    def test_can_rollback_true(self) -> None:
        result = LearningExecutionResult(
            rollback_available=True,
            previous_state={"mode": "balanced"},
        )
        assert result.can_rollback is True

    def test_can_rollback_missing_state(self) -> None:
        result = LearningExecutionResult(
            rollback_available=True,
            previous_state=None,
        )
        assert result.can_rollback is False


class TestLearningExecutionResultSerialization:
    """LearningExecutionResult 序列化测试."""

    def test_to_dict_basic(self) -> None:
        result = LearningExecutionResult(
            success=True,
            action="execute_learning",
            executed=True,
            policy_decision_type="allow_learning",
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["action"] == "execute_learning"
        assert d["executed"] is True
        assert d["policy_decision_type"] == "allow_learning"
        assert "executed_at" in d

    def test_to_dict_with_memory_result(self) -> None:
        result = LearningExecutionResult(
            memory_updated=True,
            memory_result={"kept": 50, "forgotten": 10},
        )
        d = result.to_dict()
        assert d["memory_updated"] is True
        assert d["memory_result"] == {"kept": 50, "forgotten": 10}

    def test_to_dict_with_strategy_adjustments(self) -> None:
        result = LearningExecutionResult(
            strategy_updated=True,
            strategy_adjustments=[
                {"parameter": "exploration_rate", "new_value": 0.05},
            ],
        )
        d = result.to_dict()
        assert d["strategy_updated"] is True
        assert len(d["strategy_adjustments"]) == 1

    def test_to_dict_with_learning_cycle(self) -> None:
        result = LearningExecutionResult(
            learning_cycle={"cycle_confidence": 0.75},
        )
        d = result.to_dict()
        assert d["learning_cycle"] == {"cycle_confidence": 0.75}

    def test_to_dict_roundtrip_basic(self) -> None:
        result = LearningExecutionResult(
            success=True,
            action="execute_learning",
            executed=True,
        )
        d = result.to_dict()
        assert d["success"] == result.success
        assert d["action"] == result.action


# ═══════════════════════════════════════════════════════════════
# 3. Contract — LearningExecutionContext
# ═══════════════════════════════════════════════════════════════


class TestLearningExecutionContext:
    """LearningExecutionContext 测试."""

    def test_default_creation(self) -> None:
        ctx = LearningExecutionContext()
        assert ctx.context == {}
        assert ctx.experiences == []
        assert ctx.loop_controller is None

    def test_with_context(self) -> None:
        ctx = LearningExecutionContext(context={"game": "Test"})
        assert ctx.context == {"game": "Test"}

    def test_to_dict(self) -> None:
        ctx = LearningExecutionContext(context={"game": "Test"})
        d = ctx.to_dict()
        assert d["context_keys"] == ["game"]
        assert d["experience_count"] == 0
        assert d["has_loop_controller"] is False

    def test_to_dict_with_dependencies(self) -> None:
        mock_loop = MagicMock()
        ctx = LearningExecutionContext(
            context={"game": "Test"},
            loop_controller=mock_loop,
            memory_consolidator=MagicMock(),
        )
        d = ctx.to_dict()
        assert d["has_loop_controller"] is True
        assert d["has_memory_consolidator"] is True


# ═══════════════════════════════════════════════════════════════
# 4. Adapter — Init
# ═══════════════════════════════════════════════════════════════


class TestAdapterInit:
    """LearningExecutionAdapter 初始化测试."""

    def test_default_creation(self) -> None:
        adapter = LearningExecutionAdapter()
        assert adapter.execution_count == 0
        assert adapter.get_execution_history() == []

    def test_repr(self) -> None:
        adapter = LearningExecutionAdapter()
        assert "LearningExecutionAdapter" in repr(adapter)
        assert "executions=0" in repr(adapter)


# ═══════════════════════════════════════════════════════════════
# 5. Action Classification
# ═══════════════════════════════════════════════════════════════


class TestActionClassification:
    """Action 分类测试."""

    def test_allow_learning_maps_to_execute(self) -> None:
        adapter = LearningExecutionAdapter()
        decision = _make_policy_decision(decision_type=PolicyDecisionType.ALLOW_LEARNING.value)
        action = adapter._classify_action(decision)
        assert action == LearningExecutionAction.EXECUTE_LEARNING

    def test_block_learning_maps_to_block(self) -> None:
        adapter = LearningExecutionAdapter()
        decision = _make_policy_decision(decision_type=PolicyDecisionType.BLOCK_LEARNING.value)
        action = adapter._classify_action(decision)
        assert action == LearningExecutionAction.BLOCK_LEARNING

    def test_request_memory_refresh_maps_to_refresh(self) -> None:
        adapter = LearningExecutionAdapter()
        decision = _make_policy_decision(decision_type=PolicyDecisionType.REQUEST_MEMORY_REFRESH.value)
        action = adapter._classify_action(decision)
        assert action == LearningExecutionAction.REFRESH_MEMORY

    def test_adjust_mode_maps_to_update_strategy(self) -> None:
        adapter = LearningExecutionAdapter()
        decision = _make_policy_decision(decision_type=PolicyDecisionType.ADJUST_MODE.value)
        action = adapter._classify_action(decision)
        assert action == LearningExecutionAction.UPDATE_STRATEGY

    def test_maintain_maps_to_no_action(self) -> None:
        adapter = LearningExecutionAdapter()
        decision = _make_policy_decision(decision_type=PolicyDecisionType.MAINTAIN.value)
        action = adapter._classify_action(decision)
        assert action == LearningExecutionAction.NO_ACTION

    def test_unknown_type_maps_to_no_action(self) -> None:
        adapter = LearningExecutionAdapter()
        decision = _make_policy_decision(decision_type="unknown_type")
        action = adapter._classify_action(decision)
        assert action == LearningExecutionAction.NO_ACTION


# ═══════════════════════════════════════════════════════════════
# 6. Branch A — ALLOW_LEARNING (Execute Learning)
# ═══════════════════════════════════════════════════════════════


class TestExecuteLearning:
    """Branch A: ALLOW_LEARNING 测试."""

    def test_allow_learning_executes_loop(self) -> None:
        adapter = LearningExecutionAdapter()
        loop_mock = _make_mock_loop_controller()
        state = _make_state_dict()
        decision = _make_policy_decision(
            decision_type=PolicyDecisionType.ALLOW_LEARNING.value,
            should_learn=True,
            previous_state=state,
        )
        ctx = _make_context(loop_controller=loop_mock)

        result = adapter.execute(decision, ctx)

        assert result.success is True
        assert result.action == "execute_learning"
        assert result.executed is True
        assert result.learning_cycle is not None
        assert result.learning_cycle["cycle_confidence"] == 0.75
        assert result.memory_updated is True
        loop_mock.run_cycle.assert_called_once()

    def test_allow_learning_no_controller(self) -> None:
        adapter = LearningExecutionAdapter()
        state = _make_state_dict()
        decision = _make_policy_decision(
            decision_type=PolicyDecisionType.ALLOW_LEARNING.value,
            should_learn=True,
            previous_state=state,
        )
        ctx = _make_context(loop_controller=None)

        result = adapter.execute(decision, ctx)

        assert result.action == "block_learning"
        assert result.executed is False
        assert "No LoopController" in result.reasons[-1]

    def test_allow_learning_exception(self) -> None:
        adapter = LearningExecutionAdapter()
        loop_mock = MagicMock()
        loop_mock.run_cycle.side_effect = RuntimeError("Boom")
        state = _make_state_dict()
        decision = _make_policy_decision(
            decision_type=PolicyDecisionType.ALLOW_LEARNING.value,
            should_learn=True,
            previous_state=state,
        )
        ctx = _make_context(loop_controller=loop_mock)

        result = adapter.execute(decision, ctx)

        assert result.success is False
        assert result.error == "Learning loop execution failed: Boom"
        assert result.rollback_available is True

    def test_allow_learning_preserves_previous_state(self) -> None:
        adapter = LearningExecutionAdapter()
        loop_mock = _make_mock_loop_controller()
        state = _make_state_dict()
        decision = _make_policy_decision(
            decision_type=PolicyDecisionType.ALLOW_LEARNING.value,
            should_learn=True,
            previous_state=state,
        )
        ctx = _make_context(loop_controller=loop_mock)

        result = adapter.execute(decision, ctx)

        assert result.previous_state == state
        assert result.new_state == state  # 学习循环不改变 strategy state

    def test_allow_learning_increments_count(self) -> None:
        adapter = LearningExecutionAdapter()
        loop_mock = _make_mock_loop_controller()
        decision = _make_policy_decision(
            decision_type=PolicyDecisionType.ALLOW_LEARNING.value,
            should_learn=True,
        )
        ctx = _make_context(loop_controller=loop_mock)

        adapter.execute(decision, ctx)
        assert adapter.execution_count == 1
        adapter.execute(decision, ctx)
        assert adapter.execution_count == 2


# ═══════════════════════════════════════════════════════════════
# 7. Branch B — BLOCK_LEARNING
# ═══════════════════════════════════════════════════════════════


class TestBlockLearning:
    """Branch B: BLOCK_LEARNING 测试."""

    def test_block_learning_skips_update(self) -> None:
        adapter = LearningExecutionAdapter()
        state = _make_state_dict()
        decision = _make_policy_decision(
            decision_type=PolicyDecisionType.BLOCK_LEARNING.value,
            should_learn=False,
            previous_state=state,
        )
        ctx = _make_context()

        result = adapter.execute(decision, ctx)

        assert result.success is True
        assert result.action == "block_learning"
        assert result.executed is False
        assert result.rollback_available is False
        assert "should_learn=False" in result.reasons[1]

    def test_block_learning_no_controller_needed(self) -> None:
        """BLOCK 不需要 LoopController."""
        adapter = LearningExecutionAdapter()
        decision = _make_policy_decision(
            decision_type=PolicyDecisionType.BLOCK_LEARNING.value,
            should_learn=False,
        )
        ctx = _make_context(loop_controller=None)

        result = adapter.execute(decision, ctx)
        assert result.success is True

    def test_block_learning_has_reasons(self) -> None:
        adapter = LearningExecutionAdapter()
        decision = _make_policy_decision(
            decision_type=PolicyDecisionType.BLOCK_LEARNING.value,
            should_learn=False,
            reasons=["Learning ineffective", "Confidence too low"],
        )
        ctx = _make_context()

        result = adapter.execute(decision, ctx)
        assert "Learning ineffective" in result.reasons
        assert "Confidence too low" in result.reasons


# ═══════════════════════════════════════════════════════════════
# 8. Branch C — REFRESH_MEMORY
# ═══════════════════════════════════════════════════════════════


class TestRefreshMemory:
    """Branch C: REFRESH_MEMORY 测试."""

    def test_refresh_memory_calls_consolidate(self) -> None:
        adapter = LearningExecutionAdapter()
        consolidator_mock = _make_mock_memory_consolidator()
        state = _make_state_dict()
        decision = _make_policy_decision(
            decision_type=PolicyDecisionType.REQUEST_MEMORY_REFRESH.value,
            should_update_memory=True,
            previous_state=state,
        )
        ctx = _make_context(memory_consolidator=consolidator_mock)

        result = adapter.execute(decision, ctx)

        assert result.success is True
        assert result.action == "refresh_memory"
        assert result.executed is True
        assert result.memory_updated is True
        consolidator_mock.consolidate.assert_called_once()

    def test_refresh_memory_result_details(self) -> None:
        adapter = LearningExecutionAdapter()
        consolidator_mock = _make_mock_memory_consolidator()
        decision = _make_policy_decision(
            decision_type=PolicyDecisionType.REQUEST_MEMORY_REFRESH.value,
            should_update_memory=True,
        )
        ctx = _make_context(memory_consolidator=consolidator_mock)

        result = adapter.execute(decision, ctx)

        assert result.memory_result is not None
        assert result.memory_result["total_evaluated"] == 100
        assert result.memory_result["kept"] == 60
        assert result.memory_result["forgotten"] == 15
        assert result.memory_result["core_patterns"] == 20
        assert result.memory_result["retention_rate"] == 0.60

    def test_refresh_memory_no_consolidator(self) -> None:
        adapter = LearningExecutionAdapter()
        decision = _make_policy_decision(
            decision_type=PolicyDecisionType.REQUEST_MEMORY_REFRESH.value,
            should_update_memory=True,
        )
        ctx = _make_context(memory_consolidator=None)

        result = adapter.execute(decision, ctx)

        assert result.action == "block_learning"
        assert result.executed is False
        assert "No MemoryConsolidator" in result.reasons[-1]

    def test_refresh_memory_exception(self) -> None:
        adapter = LearningExecutionAdapter()
        consolidator_mock = MagicMock()
        consolidator_mock.consolidate.side_effect = RuntimeError("Memory error")
        state = _make_state_dict()
        decision = _make_policy_decision(
            decision_type=PolicyDecisionType.REQUEST_MEMORY_REFRESH.value,
            should_update_memory=True,
            previous_state=state,
        )
        ctx = _make_context(memory_consolidator=consolidator_mock)

        result = adapter.execute(decision, ctx)

        assert result.success is False
        assert "Memory error" in (result.error or "")
        assert result.rollback_available is True


# ═══════════════════════════════════════════════════════════════
# 9. Branch D — UPDATE_STRATEGY
# ═══════════════════════════════════════════════════════════════


class TestUpdateStrategy:
    """Branch D: UPDATE_STRATEGY 测试."""

    def test_update_to_aggressive(self) -> None:
        adapter = LearningExecutionAdapter()
        state = _make_state_dict("balanced")
        decision = _make_policy_decision(
            decision_type=PolicyDecisionType.ADJUST_MODE.value,
            strategy_mode=LearningMode.AGGRESSIVE.value,
            previous_state=state,
        )
        ctx = _make_context()

        result = adapter.execute(decision, ctx)

        assert result.success is True
        assert result.action == "update_strategy"
        assert result.strategy_updated is True
        assert result.new_state is not None
        assert result.new_state["learning_mode"] == "aggressive"
        assert result.new_state["exploration_rate"] == 0.05
        assert result.new_state["confidence_threshold"] == 0.40
        assert result.new_state["pattern_weight"] == 0.85
        assert result.new_state["memory_decay_rate"] == 0.005

    def test_update_to_balanced(self) -> None:
        adapter = LearningExecutionAdapter()
        state = _make_state_dict("aggressive")
        decision = _make_policy_decision(
            decision_type=PolicyDecisionType.ADJUST_MODE.value,
            strategy_mode=LearningMode.BALANCED.value,
            previous_state=state,
        )
        ctx = _make_context()

        result = adapter.execute(decision, ctx)

        assert result.success is True
        assert result.new_state["learning_mode"] == "balanced"
        assert result.new_state["exploration_rate"] == 0.20
        assert result.new_state["confidence_threshold"] == 0.50
        assert result.new_state["pattern_weight"] == 0.70

    def test_update_to_conservative(self) -> None:
        adapter = LearningExecutionAdapter()
        state = _make_state_dict("balanced")
        decision = _make_policy_decision(
            decision_type=PolicyDecisionType.ADJUST_MODE.value,
            strategy_mode=LearningMode.CONSERVATIVE.value,
            previous_state=state,
        )
        ctx = _make_context()

        result = adapter.execute(decision, ctx)

        assert result.success is True
        assert result.new_state["learning_mode"] == "conservative"
        assert result.new_state["exploration_rate"] == 0.50
        assert result.new_state["confidence_threshold"] == 0.65
        assert result.new_state["pattern_weight"] == 0.40
        assert result.new_state["memory_decay_rate"] == 0.03

    def test_update_strategy_adjustments_list(self) -> None:
        adapter = LearningExecutionAdapter()
        state = _make_state_dict("balanced")
        decision = _make_policy_decision(
            decision_type=PolicyDecisionType.ADJUST_MODE.value,
            strategy_mode=LearningMode.AGGRESSIVE.value,
            previous_state=state,
        )
        ctx = _make_context()

        result = adapter.execute(decision, ctx)

        assert len(result.strategy_adjustments) == 5
        params = {a["parameter"] for a in result.strategy_adjustments}
        assert "learning_mode" in params
        assert "exploration_rate" in params
        assert "confidence_threshold" in params
        assert "pattern_weight" in params
        assert "memory_decay_rate" in params

    def test_update_strategy_unknown_mode(self) -> None:
        adapter = LearningExecutionAdapter()
        state = _make_state_dict()
        decision = _make_policy_decision(
            decision_type=PolicyDecisionType.ADJUST_MODE.value,
            strategy_mode="unknown_mode",
            previous_state=state,
        )
        ctx = _make_context()

        result = adapter.execute(decision, ctx)

        assert result.success is False
        assert "Unknown strategy mode" in (result.error or "")

    def test_update_strategy_rollback_available(self) -> None:
        adapter = LearningExecutionAdapter()
        state = _make_state_dict("balanced")
        decision = _make_policy_decision(
            decision_type=PolicyDecisionType.ADJUST_MODE.value,
            strategy_mode=LearningMode.AGGRESSIVE.value,
            previous_state=state,
        )
        ctx = _make_context()

        result = adapter.execute(decision, ctx)
        assert result.rollback_available is True

    def test_update_strategy_state_change_detected(self) -> None:
        adapter = LearningExecutionAdapter()
        prev = _make_state_dict("balanced")
        decision = _make_policy_decision(
            decision_type=PolicyDecisionType.ADJUST_MODE.value,
            strategy_mode=LearningMode.AGGRESSIVE.value,
            previous_state=prev,
        )
        ctx = _make_context()

        result = adapter.execute(decision, ctx)
        assert result.has_state_change is True

    def test_update_strategy_no_previous_state(self) -> None:
        adapter = LearningExecutionAdapter()
        decision = _make_policy_decision(
            decision_type=PolicyDecisionType.ADJUST_MODE.value,
            strategy_mode=LearningMode.AGGRESSIVE.value,
            previous_state=None,
        )
        ctx = _make_context()

        result = adapter.execute(decision, ctx)
        assert result.success is True
        assert result.new_state is not None
        assert result.new_state["learning_mode"] == "aggressive"


# ═══════════════════════════════════════════════════════════════
# 10. Branch E — NO_ACTION / MAINTAIN
# ═══════════════════════════════════════════════════════════════


class TestNoAction:
    """Branch E: NO_ACTION / MAINTAIN 测试."""

    def test_maintain_returns_no_action(self) -> None:
        adapter = LearningExecutionAdapter()
        state = _make_state_dict()
        decision = _make_policy_decision(
            decision_type=PolicyDecisionType.MAINTAIN.value,
            previous_state=state,
        )
        ctx = _make_context()

        result = adapter.execute(decision, ctx)

        assert result.success is True
        assert result.action == "no_action"
        assert result.executed is False
        assert result.rollback_available is False
        assert result.policy_decision_type == "maintain"

    def test_maintain_has_reasons(self) -> None:
        adapter = LearningExecutionAdapter()
        decision = _make_policy_decision(
            decision_type=PolicyDecisionType.MAINTAIN.value,
            reasons=["All indicators nominal"],
        )
        ctx = _make_context()

        result = adapter.execute(decision, ctx)
        assert "All indicators nominal" in result.reasons


# ═══════════════════════════════════════════════════════════════
# 11. Rollback
# ═══════════════════════════════════════════════════════════════


class TestRollback:
    """Rollback 测试."""

    def test_rollback_not_available(self) -> None:
        adapter = LearningExecutionAdapter()
        result = LearningExecutionResult(rollback_available=False)
        ctx = _make_context()

        rollback = adapter.rollback(result, ctx)
        assert rollback.success is False
        assert "Rollback not available" in (rollback.error or "")

    def test_rollback_no_previous_state(self) -> None:
        adapter = LearningExecutionAdapter()
        result = LearningExecutionResult(rollback_available=True, previous_state=None)
        ctx = _make_context()

        rollback = adapter.rollback(result, ctx)
        assert rollback.success is False
        assert "Rollback not available" in (rollback.error or "")

    def test_rollback_success(self) -> None:
        adapter = LearningExecutionAdapter()
        prev_state = _make_state_dict("balanced")
        new_state = _make_state_dict("aggressive")
        result = LearningExecutionResult(
            success=True,
            action="update_strategy",
            executed=True,
            policy_decision_type="adjust_mode",
            previous_state=prev_state,
            new_state=new_state,
            rollback_available=True,
        )
        ctx = _make_context()

        rollback = adapter.rollback(result, ctx)
        assert rollback.success is True
        assert rollback.new_state == prev_state

    def test_rollback_sets_metadata(self) -> None:
        adapter = LearningExecutionAdapter()
        result = LearningExecutionResult(
            previous_state=_make_state_dict(),
            new_state=_make_state_dict("aggressive"),
            rollback_available=True,
        )
        ctx = _make_context()

        rollback = adapter.rollback(result, ctx)
        assert "rollback_from" in rollback.metadata

    def test_rollback_with_strategy_optimizer(self) -> None:
        """Rollback 可以与 strategy_optimizer 一起工作."""
        adapter = LearningExecutionAdapter()
        optimizer_mock = MagicMock()
        result = LearningExecutionResult(
            previous_state=_make_state_dict("balanced"),
            new_state=_make_state_dict("aggressive"),
            rollback_available=True,
        )
        ctx = _make_context(strategy_optimizer=optimizer_mock)

        rollback = adapter.rollback(result, ctx)
        assert rollback.success is True


# ═══════════════════════════════════════════════════════════════
# 12. execute_or_skip
# ═══════════════════════════════════════════════════════════════


class TestExecuteOrSkip:
    """execute_or_skip 测试."""

    def test_none_decision_returns_no_action(self) -> None:
        adapter = LearningExecutionAdapter()
        ctx = _make_context()

        result = adapter.execute_or_skip(None, ctx)
        assert result.success is True
        assert result.action == "no_action"
        assert result.executed is False
        assert "No policy decision" in result.reasons[0]

    def test_normal_decision_executes(self) -> None:
        adapter = LearningExecutionAdapter()
        decision = _make_policy_decision(
            decision_type=PolicyDecisionType.MAINTAIN.value,
        )
        ctx = _make_context()

        result = adapter.execute_or_skip(decision, ctx)
        assert result.policy_decision_type == "maintain"


# ═══════════════════════════════════════════════════════════════
# 13. Integration
# ═══════════════════════════════════════════════════════════════


class TestIntegration:
    """集成测试: 完整 Policy → Execution 流程."""

    def test_full_allow_learning_flow(self) -> None:
        """完整 ALLOW_LEARNING 流程."""
        adapter = LearningExecutionAdapter()
        loop_mock = _make_mock_loop_controller()
        consolidator_mock = _make_mock_memory_consolidator()
        state = _make_state_dict()

        decision = _make_policy_decision(
            decision_type=PolicyDecisionType.ALLOW_LEARNING.value,
            should_learn=True,
            previous_state=state,
        )
        ctx = _make_context(
            loop_controller=loop_mock,
            memory_consolidator=consolidator_mock,
        )

        result = adapter.execute(decision, ctx)

        assert result.success is True
        assert result.action == "execute_learning"
        assert result.learning_cycle["cycle_confidence"] == 0.75
        loop_mock.run_cycle.assert_called_once()

    def test_full_block_flow(self) -> None:
        """完整 BLOCK_LEARNING 流程."""
        adapter = LearningExecutionAdapter()
        decision = _make_policy_decision(
            decision_type=PolicyDecisionType.BLOCK_LEARNING.value,
            should_learn=False,
        )
        ctx = _make_context()

        result = adapter.execute(decision, ctx)
        assert result.action == "block_learning"
        assert result.executed is False

    def test_full_refresh_flow(self) -> None:
        """完整 REFRESH_MEMORY 流程."""
        adapter = LearningExecutionAdapter()
        consolidator_mock = _make_mock_memory_consolidator()
        decision = _make_policy_decision(
            decision_type=PolicyDecisionType.REQUEST_MEMORY_REFRESH.value,
            should_update_memory=True,
        )
        ctx = _make_context(memory_consolidator=consolidator_mock)

        result = adapter.execute(decision, ctx)
        assert result.memory_updated is True
        assert result.memory_result["kept"] == 60

    def test_full_mode_switch_flow(self) -> None:
        """完整模式切换流程: BALANCED → AGGRESSIVE."""
        adapter = LearningExecutionAdapter()
        state = _make_state_dict("balanced")
        decision = _make_policy_decision(
            decision_type=PolicyDecisionType.ADJUST_MODE.value,
            strategy_mode=LearningMode.AGGRESSIVE.value,
            previous_state=state,
        )
        ctx = _make_context()

        result = adapter.execute(decision, ctx)
        assert result.strategy_updated is True
        assert result.new_state["learning_mode"] == "aggressive"
        assert result.new_state["exploration_rate"] == 0.05

    def test_multi_decision_history(self) -> None:
        """多次决策 → 执行历史."""
        adapter = LearningExecutionAdapter()
        loop_mock = _make_mock_loop_controller()

        for i in range(3):
            decision = _make_policy_decision(
                decision_type=PolicyDecisionType.ALLOW_LEARNING.value,
                should_learn=True,
            )
            ctx = _make_context(loop_controller=loop_mock)
            adapter.execute(decision, ctx)

        history = adapter.get_execution_history()
        assert len(history) == 3
        assert adapter.execution_count == 3

    def test_reset_clears_history(self) -> None:
        adapter = LearningExecutionAdapter()
        loop_mock = _make_mock_loop_controller()
        decision = _make_policy_decision(
            decision_type=PolicyDecisionType.ALLOW_LEARNING.value,
            should_learn=True,
        )
        ctx = _make_context(loop_controller=loop_mock)
        adapter.execute(decision, ctx)

        adapter.reset()
        assert adapter.execution_count == 0
        assert adapter.get_execution_history() == []


# ═══════════════════════════════════════════════════════════════
# 14. Edge Cases
# ═══════════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界情况测试."""

    def test_empty_context(self) -> None:
        adapter = LearningExecutionAdapter()
        decision = _make_policy_decision(
            decision_type=PolicyDecisionType.MAINTAIN.value,
        )
        ctx = LearningExecutionContext()

        result = adapter.execute(decision, ctx)
        assert result.success is True

    def test_partial_dependencies(self) -> None:
        """只有 loop_controller，没有 memory_consolidator."""
        adapter = LearningExecutionAdapter()
        loop_mock = _make_mock_loop_controller()
        decision = _make_policy_decision(
            decision_type=PolicyDecisionType.ALLOW_LEARNING.value,
            should_learn=True,
        )
        ctx = _make_context(loop_controller=loop_mock, memory_consolidator=None)

        result = adapter.execute(decision, ctx)
        assert result.success is True

    def test_low_confidence_decision(self) -> None:
        adapter = LearningExecutionAdapter()
        loop_mock = _make_mock_loop_controller()
        decision = _make_policy_decision(
            decision_type=PolicyDecisionType.ALLOW_LEARNING.value,
            should_learn=True,
        )
        decision.confidence = 0.05
        ctx = _make_context(loop_controller=loop_mock)

        result = adapter.execute(decision, ctx)
        assert result.success is True  # 低置信度不影响执行

    def test_high_priority_decision(self) -> None:
        adapter = LearningExecutionAdapter()
        decision = _make_policy_decision(
            decision_type=PolicyDecisionType.BLOCK_LEARNING.value,
            should_learn=False,
        )
        decision.priority = PolicyPriority.HIGH.value
        ctx = _make_context()

        result = adapter.execute(decision, ctx)
        assert result.success is True

    def test_same_mode_no_change(self) -> None:
        """BALANCED → BALANCED 不产生实际变化."""
        adapter = LearningExecutionAdapter()
        state = _make_state_dict("balanced")
        decision = _make_policy_decision(
            decision_type=PolicyDecisionType.ADJUST_MODE.value,
            strategy_mode=LearningMode.BALANCED.value,
            previous_state=state,
        )
        ctx = _make_context()

        result = adapter.execute(decision, ctx)
        # 即使 mode 相同，仍会应用参数 (确保一致性)
        assert result.new_state["learning_mode"] == "balanced"

    def test_execution_timestamp_present(self) -> None:
        adapter = LearningExecutionAdapter()
        decision = _make_policy_decision(
            decision_type=PolicyDecisionType.MAINTAIN.value,
        )
        ctx = _make_context()

        result = adapter.execute(decision, ctx)
        assert result.executed_at != ""


# ═══════════════════════════════════════════════════════════════
# 15. _MODE_PARAMS
# ═══════════════════════════════════════════════════════════════


class TestModeParams:
    """_MODE_PARAMS 映射表测试."""

    def test_all_modes_defined(self) -> None:
        assert "aggressive" in _MODE_PARAMS
        assert "balanced" in _MODE_PARAMS
        assert "conservative" in _MODE_PARAMS

    def test_all_params_present(self) -> None:
        required = {"exploration_rate", "confidence_threshold", "pattern_weight", "memory_weight", "memory_decay_rate"}
        for mode, params in _MODE_PARAMS.items():
            assert set(params.keys()) == required, f"Mode {mode} missing params"

    def test_aggressive_params(self) -> None:
        p = _MODE_PARAMS["aggressive"]
        assert p["exploration_rate"] == 0.05
        assert p["confidence_threshold"] == 0.40
        assert p["pattern_weight"] == 0.85

    def test_balanced_params(self) -> None:
        p = _MODE_PARAMS["balanced"]
        assert p["exploration_rate"] == 0.20
        assert p["confidence_threshold"] == 0.50
        assert p["pattern_weight"] == 0.70

    def test_conservative_params(self) -> None:
        p = _MODE_PARAMS["conservative"]
        assert p["exploration_rate"] == 0.50
        assert p["confidence_threshold"] == 0.65
        assert p["pattern_weight"] == 0.40

    def test_mode_params_consistent_with_factory(self) -> None:
        """_MODE_PARAMS 与 LearningStrategyState 工厂方法一致."""
        agg = LearningStrategyState.aggressive()
        assert _MODE_PARAMS["aggressive"]["exploration_rate"] == agg.exploration_rate
        assert _MODE_PARAMS["aggressive"]["confidence_threshold"] == agg.confidence_threshold
        assert _MODE_PARAMS["aggressive"]["pattern_weight"] == agg.pattern_weight

        bal = LearningStrategyState.default()
        assert _MODE_PARAMS["balanced"]["exploration_rate"] == bal.exploration_rate
        assert _MODE_PARAMS["balanced"]["confidence_threshold"] == bal.confidence_threshold
        assert _MODE_PARAMS["balanced"]["pattern_weight"] == bal.pattern_weight

        con = LearningStrategyState.conservative()
        assert _MODE_PARAMS["conservative"]["exploration_rate"] == con.exploration_rate
        assert _MODE_PARAMS["conservative"]["confidence_threshold"] == con.confidence_threshold
        assert _MODE_PARAMS["conservative"]["pattern_weight"] == con.pattern_weight


# ═══════════════════════════════════════════════════════════════
# 16. _DECISION_TO_ACTION
# ═══════════════════════════════════════════════════════════════


class TestDecisionToActionMap:
    """_DECISION_TO_ACTION 映射表测试."""

    def test_all_types_mapped(self) -> None:
        assert PolicyDecisionType.ALLOW_LEARNING.value in _DECISION_TO_ACTION
        assert PolicyDecisionType.BLOCK_LEARNING.value in _DECISION_TO_ACTION
        assert PolicyDecisionType.REQUEST_MEMORY_REFRESH.value in _DECISION_TO_ACTION
        assert PolicyDecisionType.ADJUST_MODE.value in _DECISION_TO_ACTION
        assert PolicyDecisionType.MAINTAIN.value in _DECISION_TO_ACTION

    def test_count_matches_decision_types(self) -> None:
        assert len(_DECISION_TO_ACTION) == len(list(PolicyDecisionType))

    def test_mapping_is_unique(self) -> None:
        """每个 DecisionType 映射到唯一的 Action."""
        actions = list(_DECISION_TO_ACTION.values())
        assert len(actions) == len(set(actions))


# ═══════════════════════════════════════════════════════════════
# 17. Serialization Roundtrip
# ═══════════════════════════════════════════════════════════════


class TestSerializationRoundtrip:
    """序列化往返测试."""

    def test_execution_result_full_roundtrip(self) -> None:
        result = LearningExecutionResult(
            success=True,
            action="execute_learning",
            executed=True,
            policy_decision_type="allow_learning",
            previous_state=_make_state_dict(),
            new_state=_make_state_dict(),
            memory_updated=True,
            memory_result={"kept": 50},
            strategy_updated=True,
            strategy_adjustments=[{"parameter": "exploration_rate", "new_value": 0.05}],
            learning_cycle={"cycle_confidence": 0.75},
            rollback_available=True,
            reasons=["test"],
            error=None,
            metadata={"key": "value"},
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["action"] == "execute_learning"
        assert d["memory_updated"] is True
        assert d["memory_result"] == {"kept": 50}
        assert d["learning_cycle"] == {"cycle_confidence": 0.75}
        assert d["rollback_available"] is True
        assert d["error"] is None
        assert d["metadata"] == {"key": "value"}

    def test_context_to_dict_roundtrip(self) -> None:
        ctx = LearningExecutionContext(
            context={"game": "Test", "country": "US"},
            experiences=[MagicMock(), MagicMock()],
        )
        d = ctx.to_dict()
        assert d["context_keys"] == ["game", "country"]
        assert d["experience_count"] == 2