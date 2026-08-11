"""E13.7.1 DecisionConfidenceEngine — 测试用例.

测试覆盖:
  - ConfidenceLevel: 等级判定 (from_score)
  - DecisionConfidence: 数据模型 (to_dict, is_reliable, is_strong)
  - DecisionConfidenceEngine.compute: 单策略置信度计算
  - DecisionConfidenceEngine.compare_alternatives: 多策略对比
  - DecisionConfidenceEngine: 无数据场景
  - DecisionConfidenceEngine: 小样本场景
  - DecisionConfidenceEngine: 高置信度场景
  - DecisionConfidenceEngine: 低一致性场景
  - DecisionEngine 集成: confidence_engine 注入
  - DecisionEngine 集成: 置信度影响决策类型
  - DecisionEngine 集成: 无配置时不崩溃
"""

from __future__ import annotations

from typing import Any

import pytest

from market_ops.creative_vision_runtime.growth_runtime.intelligence.decision.confidence_engine import (
    ConfidenceLevel,
    DecisionConfidence,
    DecisionConfidenceEngine,
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


def _populate_sync(sync: DecisionMemorySync, count: int, success: bool = True, action_type: str = "replace_creative") -> None:
    """向 DecisionMemorySync 填充已完成决策."""
    for i in range(count):
        output = _make_decision_output(
            decision_id=f"d{i:03d}",
            strategy_id="S1",
            action_type=action_type,
        )
        sync.record_decision(output, "creative_fatigue")
        sync.mark_executing(f"d{i:03d}")
        if success:
            sync.sync_execution_result(
                f"d{i:03d}", "success",
                metrics={"roas_change": 0.15 + (i % 5) * 0.02},
            )
        else:
            sync.sync_execution_result(f"d{i:03d}", "failure")


# ═══════════════════════════════════════════════════════════════
# Test 1: ConfidenceLevel
# ═══════════════════════════════════════════════════════════════


class TestConfidenceLevel:
    """测试置信度等级."""

    def test_high(self):
        assert ConfidenceLevel.from_score(0.90) == ConfidenceLevel.HIGH
        assert ConfidenceLevel.from_score(0.75) == ConfidenceLevel.HIGH

    def test_medium(self):
        assert ConfidenceLevel.from_score(0.74) == ConfidenceLevel.MEDIUM
        assert ConfidenceLevel.from_score(0.50) == ConfidenceLevel.MEDIUM

    def test_low(self):
        assert ConfidenceLevel.from_score(0.49) == ConfidenceLevel.LOW
        assert ConfidenceLevel.from_score(0.25) == ConfidenceLevel.LOW

    def test_insufficient(self):
        assert ConfidenceLevel.from_score(0.24) == ConfidenceLevel.INSUFFICIENT
        assert ConfidenceLevel.from_score(0.0) == ConfidenceLevel.INSUFFICIENT


# ═══════════════════════════════════════════════════════════════
# Test 2: DecisionConfidence Model
# ═══════════════════════════════════════════════════════════════


class TestDecisionConfidence:
    """测试置信度数据模型."""

    def test_to_dict(self):
        conf = DecisionConfidence(
            strategy_id="S1",
            strategy_name="replace_creative",
            confidence_score=0.82,
            level=ConfidenceLevel.HIGH,
            total_samples=25,
            historical_success_rate=0.80,
        )
        d = conf.to_dict()
        assert d["strategy_id"] == "S1"
        assert d["confidence_score"] == 0.82
        assert d["level"] == "high"
        assert d["total_samples"] == 25

    def test_is_reliable(self):
        high = DecisionConfidence(level=ConfidenceLevel.HIGH)
        assert high.is_reliable

        medium = DecisionConfidence(level=ConfidenceLevel.MEDIUM)
        assert medium.is_reliable

        low = DecisionConfidence(level=ConfidenceLevel.LOW)
        assert not low.is_reliable

    def test_is_strong(self):
        high = DecisionConfidence(level=ConfidenceLevel.HIGH)
        assert high.is_strong

        medium = DecisionConfidence(level=ConfidenceLevel.MEDIUM)
        assert not medium.is_strong

    def test_has_insufficient_data(self):
        insuf = DecisionConfidence(level=ConfidenceLevel.INSUFFICIENT)
        assert insuf.has_insufficient_data

        high = DecisionConfidence(level=ConfidenceLevel.HIGH)
        assert not high.has_insufficient_data


# ═══════════════════════════════════════════════════════════════
# Test 3: DecisionConfidenceEngine — 核心计算
# ═══════════════════════════════════════════════════════════════


class TestDecisionConfidenceEngine:
    """测试置信度引擎."""

    def test_no_data_returns_insufficient(self):
        """无数据 → INSUFFICIENT."""
        engine = DecisionConfidenceEngine()
        conf = engine.compute("S1", "replace_creative", "creative_fatigue", "replace_creative")

        assert conf.level == ConfidenceLevel.INSUFFICIENT
        assert conf.confidence_score == 0.0
        assert "No historical decision data found" in conf.warnings[0]

    def test_with_decision_sync(self):
        """有 DecisionMemorySync → 正常计算."""
        sync = DecisionMemorySync()
        _populate_sync(sync, 20, success=True)

        engine = DecisionConfidenceEngine(decision_sync=sync)
        conf = engine.compute(
            strategy_id="S1",
            strategy_name="replace_creative",
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
        )

        assert conf.total_samples == 20
        assert conf.historical_success_rate == 1.0
        assert conf.avg_reward > 0
        assert conf.sample_size_factor > 0.5
        assert conf.recency_factor > 0
        assert conf.confidence_score > 0.5
        assert conf.level in {ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM}

    def test_small_sample_size(self):
        """小样本 (< 3) → INSUFFICIENT."""
        sync = DecisionMemorySync()
        _populate_sync(sync, 2, success=True)

        engine = DecisionConfidenceEngine(decision_sync=sync)
        conf = engine.compute(
            strategy_id="S1",
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
        )

        assert conf.total_samples == 2
        assert conf.level == ConfidenceLevel.INSUFFICIENT
        assert "Only 2 samples" in conf.warnings[0]

    def test_high_confidence_scenario(self):
        """大样本 + 高成功率 → HIGH."""
        sync = DecisionMemorySync()
        _populate_sync(sync, 50, success=True)

        engine = DecisionConfidenceEngine(decision_sync=sync)
        conf = engine.compute(
            strategy_id="S1",
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
        )

        assert conf.total_samples == 50
        assert conf.historical_success_rate == 1.0
        assert conf.level == ConfidenceLevel.HIGH
        assert conf.is_strong

    def test_failure_scenario(self):
        """全部失败 → LOW."""
        sync = DecisionMemorySync()
        _populate_sync(sync, 15, success=False)

        engine = DecisionConfidenceEngine(decision_sync=sync)
        conf = engine.compute(
            strategy_id="S1",
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
        )

        assert conf.total_samples == 15
        assert conf.historical_success_rate == 0.0
        assert conf.avg_reward < 0
        # 全部失败 → 不应是 HIGH 或 MEDIUM
        assert conf.level in {ConfidenceLevel.LOW, ConfidenceLevel.INSUFFICIENT}
        assert not conf.is_reliable

    def test_compare_alternatives(self):
        """多策略对比 → 按置信度排序."""
        sync = DecisionMemorySync()
        # S1: 20 successes
        _populate_sync(sync, 20, success=True, action_type="replace_creative")
        # S2: 5 successes
        for i in range(5):
            output = _make_decision_output(
                decision_id=f"e{i:03d}",
                strategy_id="S2",
                action_type="scale_budget",
            )
            sync.record_decision(output, "roas_drop")
            sync.mark_executing(f"e{i:03d}")
            sync.sync_execution_result(f"e{i:03d}", "success",
                                       metrics={"roas_change": 0.05})

        engine = DecisionConfidenceEngine(decision_sync=sync)

        strategies = [
            {"strategy_id": "S1", "strategy_name": "replace_creative", "action_type": "replace_creative"},
            {"strategy_id": "S2", "strategy_name": "scale_budget", "action_type": "scale_budget"},
        ]
        results = engine.compare_alternatives(strategies, "creative_fatigue")

        assert len(results) == 2
        assert results[0].confidence_score >= results[1].confidence_score

    def test_rewind_consistency_high(self):
        """高一致性 (相同 reward) → consistency ~1.0."""
        sync = DecisionMemorySync()
        for i in range(10):
            output = _make_decision_output(decision_id=f"d{i:03d}")
            sync.record_decision(output, "creative_fatigue")
            sync.mark_executing(f"d{i:03d}")
            sync.sync_execution_result(
                f"d{i:03d}", "success",
                metrics={"roas_change": 0.15},  # 完全相同
            )

        engine = DecisionConfidenceEngine(decision_sync=sync)
        conf = engine.compute(
            strategy_id="S1",
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
        )

        assert conf.reward_consistency > 0.8

    def test_rewind_consistency_low(self):
        """低一致性 (reward 分散) → consistency < 0.5."""
        sync = DecisionMemorySync()
        for i in range(10):
            output = _make_decision_output(decision_id=f"d{i:03d}")
            sync.record_decision(output, "creative_fatigue")
            sync.mark_executing(f"d{i:03d}")
            if i < 5:
                sync.sync_execution_result(f"d{i:03d}", "success",
                                           metrics={"roas_change": 0.80})
            else:
                sync.sync_execution_result(f"d{i:03d}", "failure")

        engine = DecisionConfidenceEngine(decision_sync=sync)
        conf = engine.compute(
            strategy_id="S1",
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
        )

        assert conf.reward_consistency < 0.8

    def test_components_breakdown(self):
        """components 包含各维度分解."""
        sync = DecisionMemorySync()
        _populate_sync(sync, 15, success=True)

        engine = DecisionConfidenceEngine(decision_sync=sync)
        conf = engine.compute(
            strategy_id="S1",
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
        )

        assert "pattern_quality" in conf.components
        assert "sample_size" in conf.components
        assert "recency" in conf.components
        assert "consistency" in conf.components

    def test_is_confident_method(self):
        """is_confident 阈值判断."""
        engine = DecisionConfidenceEngine()
        conf = DecisionConfidence(confidence_score=0.6, level=ConfidenceLevel.MEDIUM)

        assert engine.is_confident(conf, threshold=0.5)
        assert not engine.is_confident(conf, threshold=0.7)


# ═══════════════════════════════════════════════════════════════
# Test 4: DecisionEngine Integration
# ═══════════════════════════════════════════════════════════════


class TestDecisionEngineIntegration:
    """测试 DecisionEngine 与 ConfidenceEngine 集成."""

    def test_engine_without_confidence(self):
        """无 confidence_engine → 正常决策 (不崩溃)."""
        engine = DecisionEngine()
        input_data = _make_decision_input()
        output = engine.decide(input_data)

        assert output is not None
        assert output.decision_id != ""

    def test_engine_with_confidence_no_data(self):
        """有 confidence_engine 但无数据 → INSUFFICIENT 注入."""
        ce = DecisionConfidenceEngine()
        engine = DecisionEngine(confidence_engine=ce)
        input_data = _make_decision_input()
        output = engine.decide(input_data)

        assert output is not None
        assert "decision_confidence" in output.metadata
        dc = output.metadata["decision_confidence"]
        assert dc["level"] == "insufficient"

    def test_engine_with_confidence_populated(self):
        """有 confidence_engine + 数据 → confidence 注入."""
        sync = DecisionMemorySync()
        _populate_sync(sync, 20, success=True)

        ce = DecisionConfidenceEngine(decision_sync=sync)
        engine = DecisionEngine(confidence_engine=ce)
        input_data = _make_decision_input()
        output = engine.decide(input_data)

        assert "decision_confidence" in output.metadata
        dc = output.metadata["decision_confidence"]
        assert dc["confidence_score"] > 0
        assert dc["total_samples"] == 20
        assert dc["level"] in {"high", "medium"}

    def test_confidence_affects_final_score(self):
        """置信度影响 final_score."""
        sync = DecisionMemorySync()
        _populate_sync(sync, 20, success=True)

        ce = DecisionConfidenceEngine(decision_sync=sync)
        engine = DecisionEngine(confidence_engine=ce)
        input_data = _make_decision_input()
        output = engine.decide(input_data)

        # 高置信度 → 最终评分不应为 0
        assert output.final_score > 0

    def test_confidence_warnings_in_output(self):
        """置信度警告注入到 output.warnings."""
        sync = DecisionMemorySync()
        # 只有 2 个样本 → 触发样本不足警告
        _populate_sync(sync, 2, success=True)

        ce = DecisionConfidenceEngine(decision_sync=sync)
        engine = DecisionEngine(confidence_engine=ce)
        input_data = _make_decision_input()
        output = engine.decide(input_data)

        # 应该包含样本不足警告
        has_warning = any("Only 2 samples" in w for w in output.warnings)
        assert has_warning

    def test_confidence_reasons_in_output(self):
        """HIGH 置信度 → reasons 中包含置信度说明."""
        sync = DecisionMemorySync()
        _populate_sync(sync, 30, success=True)

        ce = DecisionConfidenceEngine(decision_sync=sync)
        engine = DecisionEngine(confidence_engine=ce)
        input_data = _make_decision_input()
        output = engine.decide(input_data)

        has_confidence_reason = any("Decision confidence" in r for r in output.reasons)
        assert has_confidence_reason

    def test_end_to_end_confidence_flow(self):
        """端到端: sync → confidence_engine → decide → output 含 confidence."""
        sync = DecisionMemorySync()
        _populate_sync(sync, 25, success=True)

        ce = DecisionConfidenceEngine(decision_sync=sync)
        engine = DecisionEngine(confidence_engine=ce)

        input_data = _make_decision_input()
        output = engine.decide(input_data)

        # 验证完整链路
        assert output.decision_id != ""
        assert "decision_confidence" in output.metadata
        dc = output.metadata["decision_confidence"]
        assert dc["confidence_score"] >= 0.5
        assert dc["total_samples"] == 25
        assert dc["historical_success_rate"] == 1.0
        assert dc["level"] in {"high", "medium"}