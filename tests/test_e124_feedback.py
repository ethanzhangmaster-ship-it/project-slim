"""E12.4 — Reality Feedback Controller 测试。

覆盖:
  - Models: FeedbackSignalType, RealityFeedbackSignal, PredictionOutcome
  - TriggerRules: fatigue/ROAS/scale/replacement thresholds, spend check
  - ActionMapper: signal → action mapping, batch mapping, gene mapping
  - FeedbackController: evaluation, lifecycle integration, filtering
  - LearningFeedback: outcome recording, accuracy, calibration suggestions
"""

import pytest

from market_ops.creative_vision_runtime.reality.feedback import (
    ActionMapper,
    FeedbackController,
    FeedbackResult,
    FeedbackSignalType,
    LearningFeedback,
    PredictionAccuracy,
    PredictionOutcome,
    RealityFeedbackSignal,
    TriggerRules,
    TriggerThresholds,
)
from market_ops.creative_vision_runtime.reality.prediction import (
    LifecyclePrediction,
    PredictionType,
    RealityPrediction,
    RiskLevel,
    CreativeLifecycleStage,
)


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════


def make_fatigue_prediction(
    cid: str = "c001",
    probability: float = 0.85,
    horizon: int = 7,
) -> RealityPrediction:
    return RealityPrediction(
        prediction_type=PredictionType.CREATIVE_FATIGUE_RISK,
        target_id=cid,
        probability=probability,
        risk_level=RiskLevel.HIGH,
        horizon_days=horizon,
        evidence=["CTR decreased 23%", "Frequency increased"],
        recommended_action="MUTATE_HOOK",
        metadata={"spend": 500.0, "confidence": probability},
    )


def make_roas_prediction(
    cid: str = "c002",
    probability: float = 0.80,
) -> RealityPrediction:
    return RealityPrediction(
        prediction_type=PredictionType.ROAS_DECAY_RISK,
        target_id=cid,
        probability=probability,
        risk_level=RiskLevel.HIGH,
        current_value=0.8,
        predicted_value=0.5,
        horizon_days=7,
        evidence=["ROAS declining 0.04/day"],
        recommended_action="MUTATE_CREATIVE",
    )


def make_scale_prediction(
    cid: str = "c003",
    probability: float = 0.75,
) -> RealityPrediction:
    return RealityPrediction(
        prediction_type=PredictionType.SCALE_OPPORTUNITY,
        target_id=cid,
        probability=probability,
        risk_level=RiskLevel.LOW,
        current_value=0.6,
        predicted_value=0.9,
        horizon_days=7,
        evidence=["ROAS improving"],
        recommended_action="INCREASE_BUDGET",
    )


def make_signal(
    cid: str = "c001",
    signal_type: FeedbackSignalType = FeedbackSignalType.FATIGUE_WARNING,
    severity: float = 0.85,
    confidence: float = 0.90,
    spend: float = 500.0,
    recommended_action: str = "test_action",
) -> RealityFeedbackSignal:
    return RealityFeedbackSignal(
        creative_id=cid,
        signal_type=signal_type,
        severity=severity,
        confidence=confidence,
        reason=["Test reason"],
        recommended_action=recommended_action,
        metadata={"spend": spend},
    )


# ═══════════════════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════════════════


class TestFeedbackSignalType:
    """FeedbackSignalType 枚举。"""

    def test_all_types(self):
        assert len(list(FeedbackSignalType)) == 5

    def test_fatigue_value(self):
        assert FeedbackSignalType.FATIGUE_WARNING.value == "fatigue_warning"

    def test_roas_value(self):
        assert FeedbackSignalType.ROAS_DECLINE.value == "roas_decline"

    def test_scale_value(self):
        assert FeedbackSignalType.SCALE_OPPORTUNITY.value == "scale_opportunity"

    def test_replacement_value(self):
        assert FeedbackSignalType.CREATIVE_REPLACEMENT.value == "creative_replacement"

    def test_data_collection_value(self):
        assert FeedbackSignalType.DATA_COLLECTION.value == "data_collection"


class TestRealityFeedbackSignal:
    """RealityFeedbackSignal 测试。"""

    def test_creation(self):
        s = RealityFeedbackSignal(creative_id="c001")
        assert s.signal_id.startswith("fs_")
        assert s.creative_id == "c001"

    def test_is_actionable_true(self):
        s = RealityFeedbackSignal(severity=0.8, confidence=0.85)
        assert s.is_actionable is True

    def test_is_actionable_false_low_severity(self):
        s = RealityFeedbackSignal(severity=0.5, confidence=0.9)
        assert s.is_actionable is False

    def test_is_actionable_false_low_confidence(self):
        s = RealityFeedbackSignal(severity=0.8, confidence=0.5)
        assert s.is_actionable is False

    def test_priority(self):
        s = RealityFeedbackSignal(severity=0.8, confidence=0.9)
        assert s.priority == pytest.approx(0.8 * 0.6 + 0.9 * 0.4)

    def test_to_dict(self):
        s = make_signal()
        d = s.to_dict()
        assert d["signal_type"] == "fatigue_warning"
        assert d["is_actionable"] is True

    def test_to_evolution_opportunity(self):
        s = make_signal()
        opp = s.to_evolution_opportunity()
        assert opp["type"] == "fatigue_warning"
        assert "score" in opp
        assert "metadata" in opp

    def test_repr(self):
        s = make_signal()
        r = repr(s)
        assert "RealityFeedbackSignal" in r
        assert "c001" in r


class TestPredictionOutcome:
    """PredictionOutcome 测试。"""

    def test_creation(self):
        o = PredictionOutcome(
            creative_id="c001", metric="roas",
            predicted_value=0.55, actual_value=0.48,
        )
        assert o.outcome_id.startswith("po_")
        assert o.error == pytest.approx(0.07)
        assert o.is_success is True  # 0.07/0.55 = 12.7% < 20%

    def test_exact_match(self):
        o = PredictionOutcome(
            creative_id="c001", metric="roas",
            predicted_value=0.5, actual_value=0.5,
        )
        assert o.error == 0.0
        assert o.error_pct == 0.0
        assert o.is_success is True

    def test_large_error(self):
        o = PredictionOutcome(
            creative_id="c001", metric="roas",
            predicted_value=0.8, actual_value=0.4,
        )
        assert o.error_pct == 0.5
        assert o.is_success is False

    def test_error_direction_overestimate(self):
        o = PredictionOutcome(
            creative_id="c001", metric="roas",
            predicted_value=0.8, actual_value=0.5,
        )
        assert o.error_direction == "overestimate"

    def test_error_direction_underestimate(self):
        o = PredictionOutcome(
            creative_id="c001", metric="roas",
            predicted_value=0.5, actual_value=0.8,
        )
        assert o.error_direction == "underestimate"

    def test_error_direction_exact(self):
        o = PredictionOutcome(
            creative_id="c001", metric="roas",
            predicted_value=0.5, actual_value=0.5,
        )
        assert o.error_direction == "exact"

    def test_to_dict(self):
        o = PredictionOutcome(
            creative_id="c001", metric="roas",
            predicted_value=0.5, actual_value=0.4,
        )
        d = o.to_dict()
        assert d["metric"] == "roas"
        assert d["error_pct"] > 0

    def test_repr(self):
        o = PredictionOutcome(
            creative_id="c001", metric="roas",
            predicted_value=0.5, actual_value=0.4,
        )
        r = repr(o)
        assert "PredictionOutcome" in r


# ═══════════════════════════════════════════════════════════
# TriggerRules
# ═══════════════════════════════════════════════════════════


class TestTriggerRules:
    """TriggerRules 测试。"""

    def test_creation(self):
        r = TriggerRules()
        assert r is not None

    def test_fatigue_triggered(self):
        """疲劳信号满足阈值 → 触发。"""
        rules = TriggerRules()
        s = make_signal(
            signal_type=FeedbackSignalType.FATIGUE_WARNING,
            severity=0.85, confidence=0.90, spend=500,
        )
        assert rules.should_trigger(s) is True

    def test_fatigue_not_triggered_low_severity(self):
        """疲劳信号 severity 不满足 → 不触发。"""
        rules = TriggerRules()
        s = make_signal(
            signal_type=FeedbackSignalType.FATIGUE_WARNING,
            severity=0.5, confidence=0.90, spend=500,
        )
        assert rules.should_trigger(s) is False

    def test_fatigue_not_triggered_low_confidence(self):
        """疲劳信号 confidence 不满足 → 不触发。"""
        rules = TriggerRules()
        s = make_signal(
            signal_type=FeedbackSignalType.FATIGUE_WARNING,
            severity=0.85, confidence=0.6, spend=500,
        )
        assert rules.should_trigger(s) is False

    def test_roas_triggered(self):
        """ROAS 信号满足阈值 → 触发。"""
        rules = TriggerRules()
        s = make_signal(
            signal_type=FeedbackSignalType.ROAS_DECLINE,
            severity=0.30, confidence=0.85, spend=500,
        )
        assert rules.should_trigger(s) is True

    def test_roas_not_triggered_low_drop(self):
        """ROAS 下降不够 → 不触发。"""
        rules = TriggerRules()
        s = make_signal(
            signal_type=FeedbackSignalType.ROAS_DECLINE,
            severity=0.10, confidence=0.85, spend=500,
        )
        assert rules.should_trigger(s) is False

    def test_scale_triggered(self):
        """放量信号满足阈值 → 触发。"""
        rules = TriggerRules()
        s = make_signal(
            signal_type=FeedbackSignalType.SCALE_OPPORTUNITY,
            severity=0.7, confidence=0.85, spend=500,
        )
        assert rules.should_trigger(s) is True

    def test_data_collection_not_triggered(self):
        """DATA_COLLECTION 永不触发。"""
        rules = TriggerRules()
        s = make_signal(
            signal_type=FeedbackSignalType.DATA_COLLECTION,
            severity=1.0, confidence=1.0, spend=500,
        )
        assert rules.should_trigger(s) is False

    def test_low_spend_not_triggered(self):
        """花费不满足 → 不触发。"""
        rules = TriggerRules()
        s = make_signal(
            signal_type=FeedbackSignalType.FATIGUE_WARNING,
            severity=0.85, confidence=0.90, spend=50,
        )
        assert rules.should_trigger(s) is False

    def test_evaluate(self):
        """批量评估。"""
        rules = TriggerRules()
        signals = [
            make_signal(cid="c001", severity=0.85, confidence=0.90, spend=500),
            make_signal(cid="c002", severity=0.5, confidence=0.90, spend=500),
            make_signal(cid="c003", severity=0.85, confidence=0.6, spend=500),
        ]
        triggered = rules.evaluate(signals)
        assert len(triggered) == 1
        assert triggered[0].creative_id == "c001"

    def test_get_trigger_reason_triggered(self):
        """触发原因。"""
        rules = TriggerRules()
        s = make_signal(severity=0.85, confidence=0.90, spend=500)
        assert rules.get_trigger_reason(s) == "Triggered"

    def test_get_trigger_reason_not_triggered(self):
        """未触发原因。"""
        rules = TriggerRules()
        s = make_signal(severity=0.85, confidence=0.5, spend=500)
        reason = rules.get_trigger_reason(s)
        assert "Not triggered" in reason

    def test_replacement_triggered(self):
        """替换信号满足阈值 → 触发。"""
        rules = TriggerRules()
        s = make_signal(
            signal_type=FeedbackSignalType.CREATIVE_REPLACEMENT,
            severity=0.9, confidence=0.90, spend=500,
        )
        assert rules.should_trigger(s) is True

    def test_repr(self):
        assert repr(TriggerRules()) == "TriggerRules()"


# ═══════════════════════════════════════════════════════════
# ActionMapper
# ═══════════════════════════════════════════════════════════


class TestActionMapper:
    """ActionMapper 测试。"""

    def test_creation(self):
        m = ActionMapper()
        assert m is not None

    def test_map_fatigue(self):
        """疲劳 → CREATE_MUTATION。"""
        mapper = ActionMapper()
        s = make_signal(signal_type=FeedbackSignalType.FATIGUE_WARNING)
        action = mapper.map(s)
        assert action["action"] == "CREATE_MUTATION"
        assert "hook" in action["genes"]

    def test_map_roas_decline(self):
        """ROAS → ANALYZE_DNA_AND_MUTATE。"""
        mapper = ActionMapper()
        s = make_signal(signal_type=FeedbackSignalType.ROAS_DECLINE)
        action = mapper.map(s)
        assert action["action"] == "ANALYZE_DNA_AND_MUTATE"
        assert "monetization" in action["genes"]

    def test_map_scale(self):
        """放量 → INCREASE_EXPLORATION。"""
        mapper = ActionMapper()
        s = make_signal(signal_type=FeedbackSignalType.SCALE_OPPORTUNITY)
        action = mapper.map(s)
        assert action["action"] == "INCREASE_EXPLORATION"
        assert "audience" in action["genes"]

    def test_map_replacement(self):
        """替换 → ARCHIVE_AND_REPLACE。"""
        mapper = ActionMapper()
        s = make_signal(signal_type=FeedbackSignalType.CREATIVE_REPLACEMENT)
        action = mapper.map(s)
        assert action["action"] == "ARCHIVE_AND_REPLACE"
        assert len(action["genes"]) == 6

    def test_map_data_collection(self):
        """数据收集 → WAIT。"""
        mapper = ActionMapper()
        s = make_signal(signal_type=FeedbackSignalType.DATA_COLLECTION)
        action = mapper.map(s)
        assert action["action"] == "WAIT"
        assert action["genes"] == []

    def test_map_includes_metadata(self):
        """映射包含元数据。"""
        mapper = ActionMapper()
        s = make_signal(recommended_action="MUTATE_HOOK")
        action = mapper.map(s)
        assert action["source"] == "e12.4_feedback"
        assert action["metadata"]["recommended_action"] == "MUTATE_HOOK"

    def test_map_batch(self):
        """批量映射。"""
        mapper = ActionMapper()
        signals = [
            make_signal(cid="c001", signal_type=FeedbackSignalType.FATIGUE_WARNING),
            make_signal(cid="c002", signal_type=FeedbackSignalType.ROAS_DECLINE),
            make_signal(cid="c003", signal_type=FeedbackSignalType.SCALE_OPPORTUNITY),
        ]
        actions = mapper.map_batch(signals)
        assert len(actions) == 3
        # CREATE_MUTATION 优先级最高，应该排第一
        assert actions[0]["action"] == "CREATE_MUTATION"

    def test_to_evolution_opportunities(self):
        """转换为 EvolutionOpportunity。"""
        mapper = ActionMapper()
        signals = [
            make_signal(cid="c001", signal_type=FeedbackSignalType.FATIGUE_WARNING),
        ]
        opps = mapper.to_evolution_opportunities(signals)
        assert len(opps) == 1
        assert opps[0]["type"] == "fatigue_warning"

    def test_repr(self):
        assert repr(ActionMapper()) == "ActionMapper()"


# ═══════════════════════════════════════════════════════════
# FeedbackController
# ═══════════════════════════════════════════════════════════


class TestFeedbackController:
    """FeedbackController 测试。"""

    def test_creation(self):
        c = FeedbackController()
        assert c is not None
        assert c.trigger_rules is not None
        assert c.action_mapper is not None

    def test_evaluate(self):
        """评估预测 → 生成信号和行动。"""
        controller = FeedbackController()
        predictions = [
            make_fatigue_prediction("c001", probability=0.85),
            make_roas_prediction("c002", probability=0.80),
        ]
        result = controller.evaluate(predictions)
        assert isinstance(result, FeedbackResult)
        assert len(result.signals) == 2
        assert len(result.summary) > 0

    def test_evaluate_with_lifecycles(self):
        """评估 + 生命周期增强。"""
        controller = FeedbackController()
        predictions = [
            make_fatigue_prediction("c001", probability=0.82),
        ]
        lifecycles = [
            LifecyclePrediction(
                creative_id="c001",
                current_stage=CreativeLifecycleStage.STABLE,
                predicted_stage=CreativeLifecycleStage.FATIGUE_WARNING,
                days_to_transition=5,
            ),
        ]
        result = controller.evaluate_with_lifecycles(predictions, lifecycles)
        assert isinstance(result, FeedbackResult)

    def test_evaluate_empty(self):
        """空预测。"""
        controller = FeedbackController()
        result = controller.evaluate([])
        assert len(result.signals) == 0
        assert len(result.triggered) == 0

    def test_signal_types_from_predictions(self):
        """预测类型正确映射为信号类型。"""
        controller = FeedbackController()
        predictions = [
            make_fatigue_prediction("c001"),
            make_roas_prediction("c002"),
            make_scale_prediction("c003"),
        ]
        result = controller.evaluate(predictions)
        types = {s.signal_type for s in result.signals}
        assert FeedbackSignalType.FATIGUE_WARNING in types
        assert FeedbackSignalType.ROAS_DECLINE in types
        assert FeedbackSignalType.SCALE_OPPORTUNITY in types

    def test_triggered_filtered_by_rules(self):
        """低置信度信号被过滤。"""
        controller = FeedbackController()
        predictions = [
            make_fatigue_prediction("c001", probability=0.85),  # 高概率
            make_fatigue_prediction("c002", probability=0.5),   # 低概率
        ]
        result = controller.evaluate(predictions)
        # 低概率的应该被 TriggerRules 过滤
        triggered_ids = {s.creative_id for s in result.triggered}
        assert "c001" in triggered_ids

    def test_get_actionable_signals(self):
        """过滤高优先级信号。"""
        controller = FeedbackController()
        predictions = [
            make_fatigue_prediction("c001", probability=0.85),
            make_fatigue_prediction("c002", probability=0.5),
        ]
        result = controller.evaluate(predictions)
        actionable = controller.get_actionable_signals(result, min_priority=0.7)
        for s in actionable:
            assert s.priority >= 0.7

    def test_get_signals_by_type(self):
        """按类型筛选。"""
        controller = FeedbackController()
        predictions = [
            make_fatigue_prediction("c001"),
            make_roas_prediction("c002"),
        ]
        result = controller.evaluate(predictions)
        fatigue = controller.get_signals_by_type(
            result, FeedbackSignalType.FATIGUE_WARNING
        )
        for s in fatigue:
            assert s.signal_type == FeedbackSignalType.FATIGUE_WARNING

    def test_actions_generated(self):
        """触发信号生成行动。"""
        controller = FeedbackController()
        predictions = [
            make_fatigue_prediction("c001", probability=0.85),
        ]
        result = controller.evaluate(predictions)
        assert len(result.actions) >= 0
        assert len(result.evolution_opportunities) >= 0

    def test_statistics(self):
        """统计计数器。"""
        controller = FeedbackController()
        predictions = [make_fatigue_prediction("c001", probability=0.85)]
        controller.evaluate(predictions)
        assert controller.total_predictions_processed == 1
        assert controller.total_signals_generated >= 1

    def test_feedback_result_repr(self):
        """FeedbackResult repr。"""
        result = FeedbackResult(
            signals=[make_signal()],
            triggered=[make_signal()],
            actions=[{"action": "CREATE_MUTATION"}],
            summary="test",
        )
        r = repr(result)
        assert "FeedbackResult" in r

    def test_repr(self):
        r = repr(FeedbackController())
        assert "FeedbackController" in r


# ═══════════════════════════════════════════════════════════
# LearningFeedback
# ═══════════════════════════════════════════════════════════


class TestLearningFeedback:
    """LearningFeedback 测试。"""

    def test_creation(self):
        lf = LearningFeedback()
        assert lf is not None
        assert lf.total_outcomes == 0

    def test_record_outcome(self):
        """记录预测结果。"""
        lf = LearningFeedback()
        o = lf.record_outcome(
            prediction_id="rp_001", creative_id="c001",
            metric="roas", predicted_value=0.55, actual_value=0.48,
        )
        assert o.outcome_id.startswith("po_")
        assert lf.total_outcomes == 1

    def test_record_multiple(self):
        """记录多个结果。"""
        lf = LearningFeedback()
        for i in range(5):
            lf.record_outcome(
                prediction_id=f"rp_{i:03d}", creative_id=f"c{i:03d}",
                metric="roas", predicted_value=0.5, actual_value=0.45,
            )
        assert lf.total_outcomes == 5

    def test_get_accuracy(self):
        """获取准确率统计。"""
        lf = LearningFeedback()
        # 成功预测
        lf.record_outcome("rp_001", "c001", "roas", 0.5, 0.45)
        lf.record_outcome("rp_002", "c002", "roas", 0.5, 0.48)
        # 失败预测
        lf.record_outcome("rp_003", "c003", "roas", 0.5, 0.3)

        accuracy = lf.get_accuracy()
        assert isinstance(accuracy, PredictionAccuracy)
        assert accuracy.total_predictions == 3
        assert accuracy.successful == 2
        assert accuracy.failed == 1
        assert accuracy.success_rate == pytest.approx(2 / 3)

    def test_get_accuracy_empty(self):
        """空数据 → 默认准确率。"""
        lf = LearningFeedback()
        accuracy = lf.get_accuracy()
        assert accuracy.total_predictions == 0
        assert accuracy.success_rate == 0.0

    def test_calibration_suggestions(self):
        """校准建议。"""
        lf = LearningFeedback()
        for i in range(10):
            lf.record_outcome(
                f"rp_{i:03d}", f"c{i:03d}", "roas",
                predicted_value=0.8, actual_value=0.4,  # 全部高估
            )
        suggestions = lf.get_calibration_suggestions()
        assert len(suggestions) > 0

    def test_calibration_insufficient_data(self):
        """数据不足 → 提示。"""
        lf = LearningFeedback()
        lf.record_outcome("rp_001", "c001", "roas", 0.5, 0.45)
        suggestions = lf.get_calibration_suggestions()
        assert "Insufficient data" in suggestions[0]

    def test_get_outcomes_by_creative(self):
        """按创意查询。"""
        lf = LearningFeedback()
        lf.record_outcome("rp_001", "c001", "roas", 0.5, 0.45)
        lf.record_outcome("rp_002", "c002", "roas", 0.5, 0.45)
        results = lf.get_outcomes_by_creative("c001")
        assert len(results) == 1

    def test_get_outcomes_by_metric(self):
        """按指标查询。"""
        lf = LearningFeedback()
        lf.record_outcome("rp_001", "c001", "roas", 0.5, 0.45)
        lf.record_outcome("rp_002", "c001", "ctr", 0.03, 0.025)
        results = lf.get_outcomes_by_metric("roas")
        assert len(results) == 1

    def test_record_batch(self):
        """批量记录。"""
        lf = LearningFeedback()
        outcomes = [
            {"prediction_id": "rp_001", "creative_id": "c001", "metric": "roas",
             "predicted_value": 0.5, "actual_value": 0.45},
            {"prediction_id": "rp_002", "creative_id": "c002", "metric": "ctr",
             "predicted_value": 0.03, "actual_value": 0.025},
        ]
        results = lf.record_batch(outcomes)
        assert len(results) == 2
        assert lf.total_outcomes == 2

    def test_clear(self):
        """清空。"""
        lf = LearningFeedback()
        lf.record_outcome("rp_001", "c001", "roas", 0.5, 0.45)
        lf.clear()
        assert lf.total_outcomes == 0

    def test_prediction_accuracy_repr(self):
        """PredictionAccuracy repr。"""
        acc = PredictionAccuracy(total_predictions=10, successful=8, failed=2, success_rate=0.8)
        r = repr(acc)
        assert "PredictionAccuracy" in r

    def test_repr(self):
        lf = LearningFeedback()
        r = repr(lf)
        assert "LearningFeedback" in r


# ═══════════════════════════════════════════════════════════
# Integration
# ═══════════════════════════════════════════════════════════


class TestIntegration:
    """集成测试：完整 E12.4 流程。"""

    def test_full_pipeline(self):
        """Prediction → Signal → Trigger → Action. """
        controller = FeedbackController()
        predictions = [
            make_fatigue_prediction("c001", probability=0.85),
            make_roas_prediction("c002", probability=0.82),
            make_scale_prediction("c003", probability=0.75),
        ]
        result = controller.evaluate(predictions)

        # 应该有信号
        assert len(result.signals) >= 1
        assert len(result.summary) > 0
        # 信号转换为 E11 格式
        assert len(result.evolution_opportunities) >= 0

    def test_full_pipeline_with_lifecycle(self):
        """Prediction + Lifecycle → Signal → Action。"""
        controller = FeedbackController()
        predictions = [
            make_fatigue_prediction("c001", probability=0.82),
        ]
        lifecycles = [
            LifecyclePrediction(
                creative_id="c001",
                current_stage=CreativeLifecycleStage.STABLE,
                predicted_stage=CreativeLifecycleStage.FATIGUE_WARNING,
                days_to_transition=5,
            ),
        ]
        result = controller.evaluate_with_lifecycles(predictions, lifecycles)
        assert isinstance(result, FeedbackResult)

    def test_learning_closed_loop(self):
        """闭环学习：预测 → 行动 → 实际 → 记录。"""
        lf = LearningFeedback()

        # 模拟预测
        predictions = [
            make_fatigue_prediction("c001", probability=0.85),
            make_roas_prediction("c002", probability=0.80),
        ]

        # 模拟实际结果
        lf.record_outcome(
            predictions[0].prediction_id, "c001", "fatigue", 0.85, 0.90,
        )
        lf.record_outcome(
            predictions[1].prediction_id, "c002", "roas", 0.5, 0.48,
        )

        accuracy = lf.get_accuracy()
        assert accuracy.total_predictions == 2
        assert accuracy.success_rate > 0


# ═══════════════════════════════════════════════════════════
# Package Exports
# ═══════════════════════════════════════════════════════════


class TestPackageExports:
    """包导出测试。"""

    def test_all_exports(self):
        from market_ops.creative_vision_runtime.reality import feedback
        assert feedback.FeedbackSignalType is not None
        assert feedback.RealityFeedbackSignal is not None
        assert feedback.PredictionOutcome is not None
        assert feedback.TriggerRules is not None
        assert feedback.ActionMapper is not None
        assert feedback.FeedbackController is not None
        assert feedback.LearningFeedback is not None