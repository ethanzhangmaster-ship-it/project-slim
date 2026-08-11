"""E13.7.2 DecisionValuePredictor — 测试用例.

测试覆盖:
  - DecisionValuePrediction: 数据模型 (is_high_value, is_viable, is_high_decay, to_dict)
  - DecisionValuePredictor.predict: 无数据场景
  - DecisionValuePredictor.predict: 有数据 → 正常预测
  - DecisionValuePredictor.predict: 高价值策略 (大样本 + 高成功率 + 高奖励)
  - DecisionValuePredictor.predict: 衰减策略 (trend 下降)
  - DecisionValuePredictor.predict: 小样本 (预测置信度低)
  - DecisionValuePredictor.compare_alternatives: 多策略比较
  - DecisionValuePredictor: 负奖励策略 (expected_value 为负)
  - DecisionEngine 集成: 无 value_predictor → 不崩溃
  - DecisionEngine 集成: 有 value_predictor → 注入预测
  - DecisionEngine 集成: 价值预测影响 final_score
  - DecisionEngine 集成: 端到端流程
"""

from __future__ import annotations

from typing import Any

import pytest

from market_ops.creative_vision_runtime.growth_runtime.intelligence.decision.value_predictor import (
    DecisionValuePrediction,
    DecisionValuePredictor,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.decision.decision_engine import (
    DecisionEngine,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.decision.decision_sync import (
    DecisionMemorySync,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.decision.models import (
    DecisionInput,
    DecisionOutput,
    DecisionPlan,
    DecisionType,
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def _make_decision_output(
    decision_id: str = "d001",
    strategy_id: str = "S1",
    strategy_name: str = "replace_creative",
    action_type: str = "replace_creative",
    confidence: float = 0.75,
    **kwargs: Any,
) -> DecisionOutput:
    plan = DecisionPlan(action_type=action_type)
    return DecisionOutput(
        decision_id=decision_id,
        strategy_id=strategy_id,
        strategy_name=strategy_name,
        decision_type=DecisionType.EXECUTE,
        confidence=confidence,
        risk_score=0.2,
        final_score=0.65,
        action_plan=plan,
        **kwargs,
    )


def _make_decision_input(
    opportunity_type: str = "creative_fatigue",
    action_type: str = "replace_creative",
    **kwargs: Any,
) -> DecisionInput:
    return DecisionInput(
        strategies=[{
            "strategy_id": "S1",
            "action_type": action_type,
            "historical_score": 0.72,
            "confidence_score": 0.75,
        }],
        metadata={"opportunity_type": opportunity_type, **kwargs},
    )


def _populate_sync(
    sync: DecisionMemorySync,
    count: int,
    success: bool = True,
    action_type: str = "replace_creative",
    strategy_id: str = "S1",
    reward: float | None = None,
) -> None:
    """向 DecisionMemorySync 填充已完成决策."""
    for i in range(count):
        output = _make_decision_output(
            decision_id=f"d{i:03d}",
            strategy_id=strategy_id,
            action_type=action_type,
        )
        sync.record_decision(output, "creative_fatigue")
        sync.mark_executing(f"d{i:03d}")
        if success:
            metrics = {"roas_change": reward if reward is not None else 0.15 + (i % 5) * 0.02}
            sync.sync_execution_result(f"d{i:03d}", "success", metrics=metrics)
        else:
            sync.sync_execution_result(f"d{i:03d}", "failure")


# ═══════════════════════════════════════════════════════════════
# Test 1: DecisionValuePrediction Model
# ═══════════════════════════════════════════════════════════════


class TestDecisionValuePrediction:
    """测试价值预测数据模型."""

    def test_is_high_value(self):
        pred = DecisionValuePrediction(expected_value=0.65)
        assert pred.is_high_value

        pred2 = DecisionValuePrediction(expected_value=0.3)
        assert not pred2.is_high_value

    def test_is_viable(self):
        pred = DecisionValuePrediction(expected_value=0.35)
        assert pred.is_viable

        pred2 = DecisionValuePrediction(expected_value=0.1)
        assert not pred2.is_viable

    def test_is_high_decay(self):
        pred = DecisionValuePrediction(decay_risk=0.6)
        assert pred.is_high_decay

        pred2 = DecisionValuePrediction(decay_risk=0.2)
        assert not pred2.is_high_decay

    def test_has_sufficient_data(self):
        pred = DecisionValuePrediction(sample_size=5)
        assert pred.has_sufficient_data

        pred2 = DecisionValuePrediction(sample_size=1)
        assert not pred2.has_sufficient_data

    def test_to_dict(self):
        pred = DecisionValuePrediction(
            strategy_id="S1",
            strategy_name="replace_creative",
            expected_value=0.55,
            decision_utility=0.44,
            avg_reward=0.72,
            success_probability=0.85,
            scalability_score=0.8,
            decay_risk=0.1,
            sample_size=25,
            prediction_confidence=0.8,
        )
        d = pred.to_dict()
        assert d["strategy_id"] == "S1"
        assert d["expected_value"] == 0.55
        assert d["decision_utility"] == 0.44
        assert d["sample_size"] == 25
        assert d["horizon_days"] == 7
        assert "components" in d

    def test_defaults(self):
        pred = DecisionValuePrediction()
        assert pred.expected_value == 0.0
        assert pred.decision_utility == 0.0
        assert pred.sample_size == 0
        assert pred.horizon_days == 7
        assert pred.components == {}


# ═══════════════════════════════════════════════════════════════
# Test 2: DecisionValuePredictor — 核心预测
# ═══════════════════════════════════════════════════════════════


class TestDecisionValuePredictor:
    """测试价值预测引擎."""

    def test_no_data(self):
        """无数据 → 返回空预测."""
        predictor = DecisionValuePredictor()
        pred = predictor.predict("S1", "test", "creative_fatigue", "replace_creative")

        assert pred.expected_value == 0.0
        assert pred.decision_utility == 0.0
        assert pred.sample_size == 0
        assert "No historical decision data" in pred.warnings[0]

    def test_with_data(self):
        """有数据 → 正常预测."""
        sync = DecisionMemorySync()
        _populate_sync(sync, 15, success=True)

        predictor = DecisionValuePredictor(decision_sync=sync)
        pred = predictor.predict(
            strategy_id="S1",
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
        )

        assert pred.sample_size == 15
        assert pred.success_probability == 1.0
        assert pred.avg_reward > 0
        assert pred.expected_value > 0
        assert pred.decision_utility > 0
        assert pred.prediction_confidence >= 0.5
        assert "avg_reward" in pred.components
        assert "scalability" in pred.components
        assert "decay_risk" in pred.components

    def test_high_value_strategy(self):
        """大样本 + 高成功率 + 高奖励 → 高价值."""
        sync = DecisionMemorySync()
        _populate_sync(sync, 50, success=True, reward=0.8)

        predictor = DecisionValuePredictor(decision_sync=sync)
        pred = predictor.predict(
            strategy_id="S1",
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
        )

        assert pred.sample_size == 50
        assert pred.success_probability == 1.0
        assert pred.expected_value > 0.5
        assert pred.prediction_confidence >= 0.8
        assert pred.decision_utility > 0.4

    def test_decaying_strategy(self):
        """一半成功一半失败 → 衰减风险高."""
        sync = DecisionMemorySync()
        # 先成功 10 个，再失败 10 个
        for i in range(10):
            output = _make_decision_output(decision_id=f"d{i:03d}", strategy_id="S1")
            sync.record_decision(output, "creative_fatigue")
            sync.mark_executing(f"d{i:03d}")
            sync.sync_execution_result(f"d{i:03d}", "success", metrics={"roas_change": 0.2})
        for i in range(10, 20):
            output = _make_decision_output(decision_id=f"d{i:03d}", strategy_id="S1")
            sync.record_decision(output, "creative_fatigue")
            sync.mark_executing(f"d{i:03d}")
            sync.sync_execution_result(f"d{i:03d}", "failure")

        predictor = DecisionValuePredictor(decision_sync=sync)
        pred = predictor.predict(
            strategy_id="S1",
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
        )

        assert pred.sample_size == 20
        assert pred.success_probability == 0.5
        # 近期失败 → 衰减风险应该 > 0
        assert pred.decay_risk > 0

    def test_small_sample(self):
        """小样本 → 预测置信度低."""
        sync = DecisionMemorySync()
        _populate_sync(sync, 3, success=True)

        predictor = DecisionValuePredictor(decision_sync=sync)
        pred = predictor.predict(
            strategy_id="S1",
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
        )

        assert pred.sample_size == 3
        assert pred.prediction_confidence <= 0.6
        # 小样本 → 扩量潜力低
        assert pred.scalability_score < 0.6

    def test_negative_reward_strategy(self):
        """全部失败 → expected_value 为负."""
        sync = DecisionMemorySync()
        _populate_sync(sync, 15, success=False)

        predictor = DecisionValuePredictor(decision_sync=sync)
        pred = predictor.predict(
            strategy_id="S1",
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
        )

        assert pred.sample_size == 15
        assert pred.success_probability == 0.0
        assert pred.avg_reward < 0
        assert pred.expected_value <= 0.0
        assert "Negative average reward" in " ".join(pred.warnings)

    def test_compare_alternatives(self):
        """多策略对比 → 按 utility 排序."""
        sync = DecisionMemorySync()
        # S1: 20 successes
        _populate_sync(sync, 20, success=True, strategy_id="S1", action_type="replace_creative")
        # S2: 5 successes
        _populate_sync(sync, 5, success=True, strategy_id="S2", action_type="scale_budget")

        predictor = DecisionValuePredictor(decision_sync=sync)

        strategies = [
            {"strategy_id": "S1", "strategy_name": "replace_creative", "action_type": "replace_creative"},
            {"strategy_id": "S2", "strategy_name": "scale_budget", "action_type": "scale_budget"},
        ]
        results = predictor.compare_alternatives(strategies, "creative_fatigue")

        assert len(results) == 2
        # S1 has more samples → higher prediction_confidence → higher utility
        assert results[0].strategy_id == "S1"
        assert results[0].decision_utility >= results[1].decision_utility

    def test_components_breakdown(self):
        """components 包含各因子分解."""
        sync = DecisionMemorySync()
        _populate_sync(sync, 15, success=True)

        predictor = DecisionValuePredictor(decision_sync=sync)
        pred = predictor.predict(
            strategy_id="S1",
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
        )

        assert "avg_reward" in pred.components
        assert "success_probability" in pred.components
        assert "scalability" in pred.components
        assert "decay_risk" in pred.components
        assert "prediction_confidence" in pred.components

    def test_is_worth_executing(self):
        """is_worth_executing 阈值判断."""
        predictor = DecisionValuePredictor()
        high = DecisionValuePrediction(decision_utility=0.5)
        low = DecisionValuePrediction(decision_utility=0.1)

        assert predictor.is_worth_executing(high, min_utility=0.3)
        assert not predictor.is_worth_executing(low, min_utility=0.3)

    def test_no_sync_no_crash(self):
        """无 DecisionMemorySync → 不崩溃，返回空预测."""
        predictor = DecisionValuePredictor()
        pred = predictor.predict("S1", "test", "creative_fatigue", "replace_creative")
        assert pred.expected_value == 0.0
        assert pred.sample_size == 0

    def test_all_success_high_scalability(self):
        """全部成功 + 大样本 → 高扩量潜力."""
        sync = DecisionMemorySync()
        _populate_sync(sync, 30, success=True, reward=0.7)

        predictor = DecisionValuePredictor(decision_sync=sync)
        pred = predictor.predict(
            strategy_id="S1",
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
        )

        assert pred.scalability_score > 0.5
        assert pred.expected_value > 0.4


# ═══════════════════════════════════════════════════════════════
# Test 3: DecisionEngine Integration
# ═══════════════════════════════════════════════════════════════


class TestDecisionEngineIntegration:
    """测试 DecisionEngine 与 ValuePredictor 集成."""

    def test_engine_without_value_predictor(self):
        """无 value_predictor → 正常决策 (不崩溃)."""
        engine = DecisionEngine()
        input_data = _make_decision_input()
        output = engine.decide(input_data)

        assert output is not None
        assert output.decision_id != ""
        # 无预测数据
        assert "predicted_value" not in output.metadata

    def test_engine_with_value_predictor_no_data(self):
        """有 value_predictor 但无数据 → 预测注入但值为空."""
        predictor = DecisionValuePredictor()
        engine = DecisionEngine(value_predictor=predictor)
        input_data = _make_decision_input()
        output = engine.decide(input_data)

        assert output is not None
        assert "predicted_value" in output.metadata
        pv = output.metadata["predicted_value"]
        assert pv["expected_value"] == 0.0
        assert pv["sample_size"] == 0

    def test_engine_with_value_predictor_populated(self):
        """有 value_predictor + 数据 → 预测注入."""
        sync = DecisionMemorySync()
        _populate_sync(sync, 20, success=True)

        predictor = DecisionValuePredictor(decision_sync=sync)
        engine = DecisionEngine(value_predictor=predictor)
        input_data = _make_decision_input()
        output = engine.decide(input_data)

        assert "predicted_value" in output.metadata
        pv = output.metadata["predicted_value"]
        assert pv["expected_value"] > 0
        assert pv["sample_size"] == 20
        assert pv["success_probability"] == 1.0
        assert "components" in pv

    def test_value_prediction_affects_final_score(self):
        """价值预测影响 final_score."""
        sync = DecisionMemorySync()
        _populate_sync(sync, 30, success=True, reward=0.8)

        predictor = DecisionValuePredictor(decision_sync=sync)
        engine = DecisionEngine(value_predictor=predictor)
        input_data = _make_decision_input()
        output = engine.decide(input_data)

        # 高价值预测 → final_score 不应为 0
        assert output.final_score > 0

    def test_value_prediction_reasons_in_output(self):
        """价值预测理由注入到 output.reasons."""
        sync = DecisionMemorySync()
        _populate_sync(sync, 20, success=True)

        predictor = DecisionValuePredictor(decision_sync=sync)
        engine = DecisionEngine(value_predictor=predictor)
        input_data = _make_decision_input()
        output = engine.decide(input_data)

        has_value_reason = any("Value prediction" in r for r in output.reasons)
        assert has_value_reason

    def test_value_prediction_warnings_in_output(self):
        """价值预测警告注入到 output.warnings."""
        sync = DecisionMemorySync()
        _populate_sync(sync, 2, success=True)  # 小样本 → 警告

        predictor = DecisionValuePredictor(decision_sync=sync)
        engine = DecisionEngine(value_predictor=predictor)
        input_data = _make_decision_input()
        output = engine.decide(input_data)

        has_warning = any("prediction unreliable" in w for w in output.warnings)
        assert has_warning

    def test_end_to_end_value_flow(self):
        """端到端: sync → predictor → decide → output 含预测."""
        sync = DecisionMemorySync()
        _populate_sync(sync, 25, success=True, reward=0.75)

        predictor = DecisionValuePredictor(decision_sync=sync)
        engine = DecisionEngine(value_predictor=predictor)

        input_data = _make_decision_input()
        output = engine.decide(input_data)

        # 验证完整链路
        assert output.decision_id != ""
        assert "predicted_value" in output.metadata
        pv = output.metadata["predicted_value"]
        assert pv["expected_value"] >= 0.3
        assert pv["sample_size"] == 25
        assert pv["success_probability"] == 1.0
        assert pv["horizon_days"] == 7
        # 有预测理由
        assert any("Value prediction" in r for r in output.reasons)

    def test_negative_value_lowers_score(self):
        """负价值策略 → 降低 final_score."""
        sync = DecisionMemorySync()
        _populate_sync(sync, 20, success=False)  # 全部失败

        predictor = DecisionValuePredictor(decision_sync=sync)
        engine = DecisionEngine(value_predictor=predictor)

        input_data = _make_decision_input()
        output = engine.decide(input_data)

        pv = output.metadata["predicted_value"]
        assert pv["expected_value"] <= 0.0
        # 全部失败 → 最终评分应该很低
        assert output.final_score < 0.5

    def test_compare_strategies_by_value(self):
        """多策略价值比较: 高价值策略应优先."""
        sync = DecisionMemorySync()
        # S1: 高成功 (20 success)
        _populate_sync(sync, 20, success=True, strategy_id="S1", action_type="replace_creative", reward=0.8)
        # S2: 混合 (10 success + 10 failure)
        for i in range(10):
            output = _make_decision_output(decision_id=f"e{i:03d}", strategy_id="S2", action_type="scale_budget")
            sync.record_decision(output, "creative_fatigue")
            sync.mark_executing(f"e{i:03d}")
            sync.sync_execution_result(f"e{i:03d}", "success", metrics={"roas_change": 0.1})
        for i in range(10, 20):
            output = _make_decision_output(decision_id=f"e{i:03d}", strategy_id="S2", action_type="scale_budget")
            sync.record_decision(output, "creative_fatigue")
            sync.mark_executing(f"e{i:03d}")
            sync.sync_execution_result(f"e{i:03d}", "failure")

        predictor = DecisionValuePredictor(decision_sync=sync)

        strategies = [
            {"strategy_id": "S1", "strategy_name": "replace_creative", "action_type": "replace_creative"},
            {"strategy_id": "S2", "strategy_name": "scale_budget", "action_type": "scale_budget"},
        ]
        results = predictor.compare_alternatives(strategies, "creative_fatigue")

        # S1 应该排名更高
        assert results[0].strategy_id == "S1"
        assert results[0].decision_utility > results[1].decision_utility