"""E17.8 Cycle Gate — 测试用例.

Day 7.8 Step 5:
  覆盖 Cycle Gate 层的:
    - GateDecision / GateRule / CycleGateResult 模型
    - CycleGate 引擎 (evaluate, rules, history, stats, reset)
    - Orchestrator 集成 (CYCLE_GATE 阶段)
    - 默认规则触发 (ROLLBACK, PAUSE, REQUEST_MORE_DATA, CONTINUE)
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.cycle_gate_models import (
    CycleGateResult,
    GateDecision,
    GateRule,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.learning_feedback_models import (
    FeedbackClassification,
    LearningFeedback,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.outcome_measurement_models import (
    OutcomeMeasurement,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.learning_cycle_gate import (
    CycleGate,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def gate() -> CycleGate:
    """空门控引擎."""
    return CycleGate()


@pytest.fixture
def good_feedback() -> LearningFeedback:
    """GOOD_LEARNING 反馈."""
    outcome = OutcomeMeasurement.from_execution(
        cycle_number=1,
        execution_action="execute_learning",
        execution_success=True,
        metrics_before={"roas": 0.8, "ctr": 2.1},
        metrics_after={"roas": 1.2, "ctr": 3.0},
        strategy_state_before={"learning_mode": "balanced"},
        strategy_state_after={"learning_mode": "balanced"},
        measurement_confidence=0.8,
    )
    return LearningFeedback.from_measurement(outcome=outcome, cycle_number=1)


@pytest.fixture
def bad_feedback() -> LearningFeedback:
    """BAD_LEARNING 反馈 (moderate negative, learning_gain > -0.3)."""
    outcome = OutcomeMeasurement(
        cycle_number=2,
        is_measurable=True,
        learning_gain=-0.15,
        reward_delta=-0.1,
        confidence_delta=-0.02,
        success_delta=-0.05,
    )
    return LearningFeedback.from_measurement(outcome=outcome, cycle_number=2)


@pytest.fixture
def insufficient_feedback() -> LearningFeedback:
    """INSUFFICIENT_DATA 反馈."""
    outcome = OutcomeMeasurement(
        cycle_number=3,
        is_measurable=False,
        learning_gain=0.0,
        reward_delta=0.0,
        confidence_delta=0.0,
        success_delta=0.0,
    )
    return LearningFeedback.from_measurement(outcome=outcome, cycle_number=3)


@pytest.fixture
def stagnant_feedback() -> LearningFeedback:
    """STAGNANT 反馈."""
    outcome = OutcomeMeasurement.from_execution(
        cycle_number=4,
        execution_action="execute_learning",
        execution_success=True,
        metrics_before={"roas": 1.0, "ctr": 2.5},
        metrics_after={"roas": 1.02, "ctr": 2.52},
        strategy_state_before={"learning_mode": "balanced"},
        strategy_state_after={"learning_mode": "balanced"},
        measurement_confidence=0.7,
    )
    return LearningFeedback.from_measurement(outcome=outcome, cycle_number=4)


# ═══════════════════════════════════════════════════════════════
# Test: GateDecision Enum
# ═══════════════════════════════════════════════════════════════


class TestGateDecision:
    """GateDecision 枚举测试."""

    def test_enum_values(self):
        """验证枚举值."""
        assert GateDecision.CONTINUE.value == "continue"
        assert GateDecision.PAUSE.value == "pause"
        assert GateDecision.ROLLBACK.value == "rollback"
        assert GateDecision.REQUEST_MORE_DATA.value == "request_more_data"

    def test_enum_count(self):
        """验证枚举数量."""
        assert len(GateDecision) == 4


# ═══════════════════════════════════════════════════════════════
# Test: GateRule
# ═══════════════════════════════════════════════════════════════


class TestGateRule:
    """GateRule 模型测试."""

    def test_create_rule(self):
        """创建规则."""
        rule = GateRule(
            name="test_rule",
            description="Test rule",
            priority=10,
            condition=lambda ctx: ctx.get("value", 0) > 0.5,
            decision=GateDecision.PAUSE.value,
            reason_template="Value {value} exceeds threshold",
        )
        assert rule.name == "test_rule"
        assert rule.priority == 10
        assert rule.decision == "pause"

    def test_evaluate_triggered(self):
        """条件满足时触发."""
        rule = GateRule(
            name="test",
            condition=lambda ctx: ctx.get("x", 0) > 0,
            decision=GateDecision.PAUSE.value,
            reason_template="x={x} is positive",
        )
        triggered, reason = rule.evaluate({"x": 1.0})
        assert triggered is True
        assert "positive" in reason

    def test_evaluate_not_triggered(self):
        """条件不满足时不触发."""
        rule = GateRule(
            name="test",
            condition=lambda ctx: ctx.get("x", 0) > 0,
            decision=GateDecision.PAUSE.value,
            reason_template="x={x} is positive",
        )
        triggered, reason = rule.evaluate({"x": -1.0})
        assert triggered is False
        assert reason == ""

    def test_evaluate_exception_handling(self):
        """条件抛出异常时返回 False."""
        rule = GateRule(
            name="test",
            condition=lambda ctx: 1 / 0,  # 故意除零
            decision=GateDecision.PAUSE.value,
            reason_template="error",
        )
        triggered, reason = rule.evaluate({})
        assert triggered is False
        assert reason == ""

    def test_to_dict(self):
        """序列化."""
        rule = GateRule(
            name="test",
            description="desc",
            priority=5,
            decision="pause",
        )
        d = rule.to_dict()
        assert d["name"] == "test"
        assert d["description"] == "desc"
        assert d["priority"] == 5
        assert d["decision"] == "pause"


# ═══════════════════════════════════════════════════════════════
# Test: CycleGateResult
# ═══════════════════════════════════════════════════════════════


class TestCycleGateResult:
    """CycleGateResult 模型测试."""

    def test_default_continue(self):
        """默认决策为 CONTINUE."""
        result = CycleGateResult()
        assert result.decision == GateDecision.CONTINUE.value
        assert result.should_continue is True
        assert result.is_blocking is False

    def test_should_continue(self):
        """CONTINUE 决策."""
        result = CycleGateResult.continue_result(cycle_number=1)
        assert result.should_continue is True
        assert result.should_pause is False
        assert result.should_rollback is False
        assert result.should_request_data is False
        assert result.is_blocking is False

    def test_should_pause(self):
        """PAUSE 决策."""
        result = CycleGateResult.pause_result(
            cycle_number=2,
            reason="Test pause",
            triggered_rule="test_rule",
        )
        assert result.should_pause is True
        assert result.should_continue is False
        assert result.is_blocking is True
        assert result.decision_reason == "Test pause"
        assert result.triggered_rule == "test_rule"

    def test_should_rollback(self):
        """ROLLBACK 决策."""
        result = CycleGateResult.rollback_result(
            cycle_number=3,
            reason="Test rollback",
            triggered_rule="strong_negative",
        )
        assert result.should_rollback is True
        assert result.is_blocking is True
        assert result.decision == GateDecision.ROLLBACK.value

    def test_should_request_data(self):
        """REQUEST_MORE_DATA 决策."""
        result = CycleGateResult.request_data_result(
            cycle_number=4,
            reason="Need more samples",
        )
        assert result.should_request_data is True
        assert result.is_blocking is True
        assert result.decision == GateDecision.REQUEST_MORE_DATA.value

    def test_to_dict(self):
        """序列化."""
        result = CycleGateResult.continue_result(
            cycle_number=5,
            reason="All good",
        )
        result.feedback_classification = "good_learning"
        result.effectiveness_score = 0.8
        result.learning_gain = 0.15

        d = result.to_dict()
        assert d["decision"] == "continue"
        assert d["should_continue"] is True
        assert d["is_blocking"] is False
        assert d["feedback_classification"] == "good_learning"
        assert d["effectiveness_score"] == 0.8
        assert d["learning_gain"] == 0.15
        assert "gate_id" in d
        assert "created_at" in d


# ═══════════════════════════════════════════════════════════════
# Test: CycleGate Engine
# ═══════════════════════════════════════════════════════════════


class TestCycleGateEngine:
    """CycleGate 引擎测试."""

    def test_create_gate(self, gate):
        """创建门控引擎."""
        assert gate.evaluate_count == 0
        assert len(gate.rules) > 0

    def test_evaluate_good_feedback(self, gate, good_feedback):
        """GOOD_LEARNING 反馈 → CONTINUE."""
        result = gate.evaluate(
            feedback=good_feedback,
            cycle_number=1,
        )
        assert result.should_continue is True
        assert result.decision == GateDecision.CONTINUE.value
        assert result.feedback_classification == "good_learning"

    def test_evaluate_bad_feedback(self, gate, bad_feedback):
        """BAD_LEARNING 但 learning_gain > -0.3 → CONTINUE (不触发 rollback)."""
        result = gate.evaluate(
            feedback=bad_feedback,
            cycle_number=2,
        )
        # bad_learning 但 learning_gain 不够负，不触发 rollback
        assert result.decision == GateDecision.CONTINUE.value

    def test_evaluate_insufficient_feedback(self, gate, insufficient_feedback):
        """INSUFFICIENT_DATA → REQUEST_MORE_DATA."""
        result = gate.evaluate(
            feedback=insufficient_feedback,
            cycle_number=3,
        )
        assert result.should_request_data is True
        assert result.decision == GateDecision.REQUEST_MORE_DATA.value

    def test_evaluate_stagnant_feedback(self, gate, stagnant_feedback):
        """STAGNANT 反馈 → CONTINUE (非 negative)."""
        result = gate.evaluate(
            feedback=stagnant_feedback,
            cycle_number=4,
        )
        assert result.decision == GateDecision.CONTINUE.value

    def test_evaluate_with_effectiveness(self, gate, good_feedback):
        """带 effectiveness 的评估."""
        result = gate.evaluate(
            feedback=good_feedback,
            cycle_number=1,
        )
        assert result.effectiveness_score is None
        assert result.learning_gain > 0
        assert result.feedback_classification == "good_learning"

    def test_evaluate_count(self, gate, good_feedback):
        """评估计数."""
        assert gate.evaluate_count == 0
        gate.evaluate(feedback=good_feedback, cycle_number=1)
        assert gate.evaluate_count == 1
        gate.evaluate(feedback=good_feedback, cycle_number=2)
        assert gate.evaluate_count == 2

    def test_history(self, gate, good_feedback):
        """评估历史."""
        gate.evaluate(feedback=good_feedback, cycle_number=1)
        gate.evaluate(feedback=good_feedback, cycle_number=2)
        history = gate.get_history()
        assert len(history) == 2
        assert all(isinstance(r, CycleGateResult) for r in history)

    def test_get_latest(self, gate, good_feedback):
        """获取最近一次结果."""
        assert gate.get_latest() is None
        gate.evaluate(feedback=good_feedback, cycle_number=1)
        latest = gate.get_latest()
        assert latest is not None
        assert latest.cycle_number == 1

    def test_get_stats(self, gate, good_feedback, bad_feedback):
        """获取统计."""
        gate.evaluate(feedback=good_feedback, cycle_number=1)
        gate.evaluate(feedback=bad_feedback, cycle_number=2)
        stats = gate.get_stats()
        assert stats["evaluate_count"] == 2
        assert stats["continue_count"] >= 0
        assert "blocking_rate" in stats

    def test_get_stats_empty(self):
        """空统计."""
        gate = CycleGate()
        stats = gate.get_stats()
        assert stats["evaluate_count"] == 0
        assert stats["continue_count"] == 0

    def test_reset(self, gate, good_feedback):
        """重置."""
        gate.evaluate(feedback=good_feedback, cycle_number=1)
        assert gate.evaluate_count == 1
        gate.reset()
        assert gate.evaluate_count == 0
        assert len(gate.get_history()) == 0


# ═══════════════════════════════════════════════════════════════
# Test: Custom Rules
# ═══════════════════════════════════════════════════════════════


class TestCustomRules:
    """自定义规则测试."""

    def test_add_rule(self):
        """添加自定义规则."""
        gate = CycleGate()
        before = len(gate.rules)
        rule = GateRule(
            name="custom_always_pause",
            description="Always pause",
            priority=0,
            condition=lambda _: True,
            decision=GateDecision.PAUSE.value,
            reason_template="Custom pause",
        )
        gate.add_rule(rule)
        assert len(gate.rules) == before + 1

    def test_add_rule_triggers_first(self):
        """高优先级自定义规则先触发."""
        gate = CycleGate()
        rule = GateRule(
            name="custom_always_pause",
            description="Always pause",
            priority=0,  # 最高优先级
            condition=lambda _: True,
            decision=GateDecision.PAUSE.value,
            reason_template="Custom pause {cycle_number}",
        )
        gate.add_rule(rule)
        result = gate.evaluate(cycle_number=1)
        assert result.should_pause is True
        assert result.triggered_rule == "custom_always_pause"

    def test_remove_rule(self):
        """移除规则."""
        gate = CycleGate()
        rule = GateRule(
            name="removable",
            condition=lambda _: True,
            decision=GateDecision.PAUSE.value,
            reason_template="remove me",
        )
        gate.add_rule(rule)
        removed = gate.remove_rule("removable")
        assert removed is True
        removed_again = gate.remove_rule("removable")
        assert removed_again is False

    def test_clear_rules(self):
        """清空所有规则."""
        gate = CycleGate()
        gate.clear_rules()
        assert len(gate.rules) == 0

    def test_clear_rules_default_continue(self):
        """清空规则后无规则触发."""
        gate = CycleGate()
        gate.clear_rules()
        # 添加一个默认继续规则
        gate.add_rule(GateRule(
            name="default",
            condition=lambda _: True,
            decision=GateDecision.CONTINUE.value,
            reason_template="default",
        ))
        result = gate.evaluate(cycle_number=1)
        assert result.should_continue is True


# ═══════════════════════════════════════════════════════════════
# Test: Default Rule Triggers
# ═══════════════════════════════════════════════════════════════


class TestDefaultRuleTriggers:
    """默认规则触发条件测试."""

    def test_strong_negative_triggers_rollback(self):
        """learning_gain < -0.3 → ROLLBACK."""
        gate = CycleGate()
        outcome = OutcomeMeasurement(
            cycle_number=1,
            is_measurable=True,
            learning_gain=-0.5,
            reward_delta=-0.2,
            confidence_delta=-0.1,
            success_delta=-0.3,
        )
        feedback = LearningFeedback.from_measurement(outcome=outcome, cycle_number=1)
        result = gate.evaluate(feedback=feedback, cycle_number=1)
        assert result.should_rollback is True
        assert result.triggered_rule == "strong_negative_learning"

    def test_repeated_negative_triggers_pause(self):
        """连续 3 次负反馈 → PAUSE."""
        gate = CycleGate()
        # 构建连续 3 次负反馈的历史
        history = []
        for i in range(3):
            hist_result = CycleGateResult(
                cycle_number=i + 1,
                decision=GateDecision.CONTINUE.value,
                learning_gain=-0.1,
            )
            history.append(hist_result)

        outcome = OutcomeMeasurement(
            cycle_number=4,
            is_measurable=True,
            learning_gain=-0.1,
            reward_delta=-0.05,
            confidence_delta=-0.02,
            success_delta=-0.01,
        )
        feedback = LearningFeedback.from_measurement(outcome=outcome, cycle_number=4)
        result = gate.evaluate(
            feedback=feedback,
            cycle_number=4,
            cycle_history=history,
        )
        assert result.should_pause is True
        assert result.triggered_rule == "repeated_negative_cycles"

    def test_insufficient_triggers_request_data(self):
        """INSUFFICIENT_DATA → REQUEST_MORE_DATA."""
        gate = CycleGate()
        outcome = OutcomeMeasurement(
            cycle_number=1,
            is_measurable=False,
            learning_gain=0.0,
            reward_delta=0.0,
            confidence_delta=0.0,
            success_delta=0.0,
        )
        feedback = LearningFeedback.from_measurement(outcome=outcome, cycle_number=1)
        result = gate.evaluate(feedback=feedback, cycle_number=1)
        assert result.should_request_data is True
        assert result.triggered_rule == "insufficient_data"

    def test_effectiveness_below_threshold_triggers_pause(self):
        """有效性评分低于阈值 → PAUSE."""
        gate = CycleGate()
        # 模拟一个 effectiveness 对象
        class MockEffectiveness:
            effectiveness_score = 0.1
            learning_gain = 0.0

        eff = MockEffectiveness()
        outcome = OutcomeMeasurement(
            cycle_number=1,
            is_measurable=True,
            learning_gain=0.01,
            reward_delta=0.01,
            confidence_delta=0.01,
            success_delta=0.01,
        )
        feedback = LearningFeedback.from_measurement(outcome=outcome, cycle_number=1)

        class MockConfig:
            min_effectiveness_threshold = 0.3

        result = gate.evaluate(
            feedback=feedback,
            effectiveness=eff,
            cycle_number=1,
            config=MockConfig(),
        )
        assert result.should_pause is True
        assert result.triggered_rule == "effectiveness_below_threshold"

    def test_default_continue(self):
        """默认 → CONTINUE."""
        gate = CycleGate()
        outcome = OutcomeMeasurement(
            cycle_number=1,
            is_measurable=True,
            learning_gain=0.01,
            reward_delta=0.01,
            confidence_delta=0.01,
            success_delta=0.01,
        )
        feedback = LearningFeedback.from_measurement(outcome=outcome, cycle_number=1)
        result = gate.evaluate(feedback=feedback, cycle_number=1)
        assert result.should_continue is True
        assert result.triggered_rule == "default_continue"

    def test_rule_results_recorded(self):
        """规则评估结果全部记录."""
        gate = CycleGate()
        outcome = OutcomeMeasurement(
            cycle_number=1,
            is_measurable=True,
            learning_gain=0.01,
            reward_delta=0.01,
            confidence_delta=0.01,
            success_delta=0.01,
        )
        feedback = LearningFeedback.from_measurement(outcome=outcome, cycle_number=1)
        result = gate.evaluate(feedback=feedback, cycle_number=1)
        assert result.rules_evaluated > 0
        assert len(result.rule_results) == result.rules_evaluated
        # 验证每个规则结果的结构
        for rr in result.rule_results:
            assert "name" in rr
            assert "priority" in rr
            assert "decision" in rr
            assert "triggered" in rr
            assert "reason" in rr


# ═══════════════════════════════════════════════════════════════
# Test: CYCLE_GATE in Orchestrator
# ═══════════════════════════════════════════════════════════════


class TestCycleGateOrchestratorIntegration:
    """Orchestrator 集成测试."""

    @pytest.fixture
    def orchestrator(self):
        """创建带 CycleGate 的编排器."""
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.learning_cycle_orchestrator import (
            LearningCycleOrchestrator,
        )
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.learning_orchestration_models import (
            OrchestratorConfig,
        )

        config = OrchestratorConfig.test_mode()
        orch = LearningCycleOrchestrator(config=config)
        return orch

    def test_cycle_gate_initialized(self, orchestrator):
        """CycleGate 已初始化."""
        assert orchestrator.cycle_gate is not None
        assert orchestrator.cycle_gate.evaluate_count == 0

    def test_cycle_gate_in_state_transitions(self, orchestrator):
        """CYCLE_GATE 出现在状态转换中."""
        orchestrator.start()
        result = orchestrator.run_cycle()
        transitions = result.state_transitions
        states = [t["to"] for t in transitions]
        assert "cycle_gate" in states

    def test_cycle_gate_disabled_in_test_mode(self, orchestrator):
        """测试模式下 enable_cycle_gate 默认 True，但 test_mode 未显式禁用."""
        # 测试模式下 gate 仍然运行（因为 test_mode 没有设置 enable_cycle_gate=False）
        orchestrator.start()
        result = orchestrator.run_cycle()
        # 验证 gate_result 存在
        assert result.gate_result is not None

    def test_cycle_gate_disabled_explicitly(self):
        """显式禁用 cycle gate."""
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.learning_cycle_orchestrator import (
            LearningCycleOrchestrator,
        )
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.learning_orchestration_models import (
            OrchestratorConfig,
        )

        config = OrchestratorConfig.test_mode()
        config.enable_cycle_gate = False
        orch = LearningCycleOrchestrator(config=config)
        orch.start()
        result = orch.run_cycle()
        # 门控禁用时 decision 为 continue
        assert result.gate_result.should_continue is True

    def test_cycle_gate_stats_in_status(self, orchestrator):
        """CycleGate 统计出现在 get_status() 中."""
        orchestrator.start()
        orchestrator.run_cycle()
        status = orchestrator.get_status()
        assert "cycle_gate" in status
        assert status["cycle_gate"]["evaluate_count"] >= 1

    def test_cycle_gate_reset_with_orchestrator(self, orchestrator):
        """Orchestrator reset 重置 CycleGate."""
        orchestrator.start()
        orchestrator.run_cycle()
        assert orchestrator.cycle_gate.evaluate_count > 0
        orchestrator.reset()
        assert orchestrator.cycle_gate.evaluate_count == 0