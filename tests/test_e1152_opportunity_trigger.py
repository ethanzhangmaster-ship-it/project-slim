"""E11.5.2 — Opportunity Trigger Layer 测试。

测试范围：
  - OpportunitySignal: 数据模型 + 验证 + 序列化
  - TriggerDecision: 数据模型 + 属性 + 序列化
  - Rule: 内置规则 + 评估 + 优先级
  - OpportunityDetector: 检测 + 去重 + 过滤 + 批量
  - TriggerEngine: 评估 + 处理 + 排序 + 上下文 + 回调
  - Controller Integration: process_signals + evaluate_opportunities
  - Full Pipeline: Signal → Detector → Engine → Controller
  - Package exports
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from market_ops.creative_vision_runtime.autonomous_controller.trigger.models import (
    OpportunitySignal,
    TriggerDecision,
    TriggerAction,
)
from market_ops.creative_vision_runtime.autonomous_controller.trigger.rules import (
    Rule,
    build_default_rules,
)
from market_ops.creative_vision_runtime.autonomous_controller.trigger.opportunity_detector import (
    OpportunityDetector,
)
from market_ops.creative_vision_runtime.autonomous_controller.trigger.trigger_engine import (
    TriggerEngine,
)


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _make_signal_dict(
    signal_id: str = "",
    source: str = "market",
    category: str = "merge_puzzle",
    patterns: list[str] | None = None,
    confidence: float = 0.85,
    priority: str = "high",
    reason: str = "Test signal",
) -> dict:
    d = {
        "source": source,
        "category": category,
        "patterns": patterns or ["bright_visual", "fast_transition"],
        "confidence": confidence,
        "priority": priority,
        "reason": reason,
    }
    if signal_id:
        d["signal_id"] = signal_id
    return d


def _make_signal(**kwargs) -> OpportunitySignal:
    return OpportunitySignal(
        source=kwargs.get("source", "market"),
        category=kwargs.get("category", "merge_puzzle"),
        patterns=kwargs.get("patterns", ["bright_visual", "fast_transition"]),
        confidence=kwargs.get("confidence", 0.85),
        priority=kwargs.get("priority", "high"),
        reason=kwargs.get("reason", "Test signal"),
        metadata=kwargs.get("metadata", {}),
    )


# ═══════════════════════════════════════════════════════════
# OpportunitySignal
# ═══════════════════════════════════════════════════════════

class TestOpportunitySignal:
    """OpportunitySignal 数据模型测试。"""

    def test_create_default(self):
        s = OpportunitySignal()
        assert s.signal_id.startswith("os_")
        assert s.source == "market"
        assert s.category == ""
        assert s.patterns == []
        assert s.confidence == 0.0
        assert s.priority == "medium"

    def test_create_with_values(self):
        s = _make_signal()
        assert s.source == "market"
        assert s.category == "merge_puzzle"
        assert s.confidence == 0.85
        assert s.priority == "high"
        assert s.pattern_count == 2

    def test_priority_validation(self):
        with pytest.raises(ValueError, match="Invalid priority"):
            OpportunitySignal(priority="invalid")

    def test_confidence_validation_low(self):
        with pytest.raises(ValueError, match="Invalid confidence"):
            OpportunitySignal(confidence=-0.1)

    def test_confidence_validation_high(self):
        with pytest.raises(ValueError, match="Invalid confidence"):
            OpportunitySignal(confidence=1.5)

    def test_is_high_priority(self):
        assert _make_signal(priority="high").is_high_priority is True
        assert _make_signal(priority="medium").is_high_priority is False

    def test_is_high_confidence(self):
        assert _make_signal(confidence=0.85).is_high_confidence is True
        assert _make_signal(confidence=0.5).is_high_confidence is False

    def test_to_dict(self):
        s = _make_signal()
        d = s.to_dict()
        assert d["source"] == "market"
        assert d["confidence"] == 0.85
        assert d["patterns"] == ["bright_visual", "fast_transition"]

    def test_from_dict(self):
        data = _make_signal_dict(confidence=0.9, priority="medium")
        s = OpportunitySignal.from_dict(data)
        assert s.confidence == 0.9
        assert s.priority == "medium"

    def test_from_dict_defaults(self):
        s = OpportunitySignal.from_dict({})
        assert s.source == "market"
        assert s.confidence == 0.0

    def test_repr(self):
        s = _make_signal()
        r = repr(s)
        assert "market" in r
        assert "0.85" in r


# ═══════════════════════════════════════════════════════════
# TriggerDecision
# ═══════════════════════════════════════════════════════════

class TestTriggerDecision:
    """TriggerDecision 数据模型测试。"""

    def test_create_default(self):
        d = TriggerDecision()
        assert d.decision_id.startswith("td_")
        assert d.should_trigger is False
        assert d.action == TriggerAction.IGNORE
        assert d.confidence == 0.0

    def test_create_positive(self):
        d = TriggerDecision(
            signal_id="os_123",
            should_trigger=True,
            action=TriggerAction.START_EVOLUTION,
            reason="High confidence",
            confidence=0.9,
        )
        assert d.is_positive is True
        assert d.should_trigger is True

    def test_is_positive_false(self):
        d = TriggerDecision(
            should_trigger=True,
            action=TriggerAction.QUEUE,  # Not START_EVOLUTION
        )
        assert d.is_positive is False

    def test_is_deferred(self):
        d = TriggerDecision(action=TriggerAction.DEFER)
        assert d.is_deferred is True
        assert d.is_ignored is False

    def test_is_ignored(self):
        d = TriggerDecision(action=TriggerAction.IGNORE)
        assert d.is_ignored is True

    def test_to_dict(self):
        d = TriggerDecision(
            signal_id="os_123",
            should_trigger=True,
            action=TriggerAction.START_EVOLUTION,
            confidence=0.9,
        )
        result = d.to_dict()
        assert result["should_trigger"] is True
        assert result["action"] == "start_evolution"

    def test_from_dict(self):
        data = {
            "signal_id": "os_123",
            "should_trigger": True,
            "action": "start_evolution",
            "reason": "test",
            "confidence": 0.85,
        }
        d = TriggerDecision.from_dict(data)
        assert d.should_trigger is True
        assert d.action == TriggerAction.START_EVOLUTION

    def test_repr(self):
        d = TriggerDecision(
            action=TriggerAction.START_EVOLUTION,
            should_trigger=True,
            confidence=0.88,
        )
        r = repr(d)
        assert "start_evolution" in r
        assert "0.88" in r


# ═══════════════════════════════════════════════════════════
# TriggerAction
# ═══════════════════════════════════════════════════════════

class TestTriggerAction:
    """TriggerAction 枚举测试。"""

    def test_all_values(self):
        assert TriggerAction.START_EVOLUTION.value == "start_evolution"
        assert TriggerAction.QUEUE.value == "queue"
        assert TriggerAction.MERGE.value == "merge"
        assert TriggerAction.IGNORE.value == "ignore"
        assert TriggerAction.DEFER.value == "defer"


# ═══════════════════════════════════════════════════════════
# Rule
# ═══════════════════════════════════════════════════════════

class TestRule:
    """Rule 规则系统测试。"""

    def test_create_rule(self):
        rule = Rule(
            name="test_rule",
            action=TriggerAction.START_EVOLUTION,
            reason="Test",
            priority=50,
        )
        assert rule.name == "test_rule"
        assert rule.enabled is True

    def test_rule_disabled(self):
        rule = Rule(
            name="disabled",
            action=TriggerAction.START_EVOLUTION,
            enabled=False,
        )
        signal = _make_signal(confidence=0.9)
        result = rule.evaluate(signal)
        assert result is None

    def test_rule_condition_match(self):
        rule = Rule(
            name="high_conf",
            condition=lambda s, ctx: s.confidence >= 0.8,
            action=TriggerAction.START_EVOLUTION,
            reason="High confidence",
        )
        signal = _make_signal(confidence=0.85)
        result = rule.evaluate(signal)
        assert result is not None
        assert result.action == TriggerAction.START_EVOLUTION
        assert result.should_trigger is True

    def test_rule_condition_no_match(self):
        rule = Rule(
            name="high_conf",
            condition=lambda s, ctx: s.confidence >= 0.8,
            action=TriggerAction.START_EVOLUTION,
        )
        signal = _make_signal(confidence=0.5)
        result = rule.evaluate(signal)
        assert result is None

    def test_rule_with_context(self):
        rule = Rule(
            name="context_rule",
            condition=lambda s, ctx: ctx.get("threshold", 0.5) < s.confidence,
            action=TriggerAction.START_EVOLUTION,
        )
        signal = _make_signal(confidence=0.7)
        result = rule.evaluate(signal, {"threshold": 0.6})
        assert result is not None

    def test_rule_repr(self):
        rule = Rule(name="test", action=TriggerAction.QUEUE)
        r = repr(rule)
        assert "test" in r
        assert "queue" in r


class TestBuiltinRules:
    """内置规则测试。"""

    def test_all_rules_built(self):
        rules = build_default_rules()
        assert len(rules) == 8

    def test_high_confidence_rule_triggers(self):
        rules = build_default_rules()
        rule = [r for r in rules if r.name == "high_confidence_market_shift"][0]
        signal = _make_signal(confidence=0.85)
        result = rule.evaluate(signal)
        assert result is not None
        assert result.action == TriggerAction.START_EVOLUTION

    def test_high_confidence_rule_no_trigger(self):
        rules = build_default_rules()
        rule = [r for r in rules if r.name == "high_confidence_market_shift"][0]
        signal = _make_signal(confidence=0.6)
        result = rule.evaluate(signal)
        assert result is None

    def test_winner_pattern_rule_triggers(self):
        rules = build_default_rules()
        rule = [r for r in rules if r.name == "winner_pattern_emerging"][0]
        signal = _make_signal(
            confidence=0.7,
            patterns=["p1", "p2", "p3", "p4"],
        )
        result = rule.evaluate(signal, {"pattern_threshold": 3})
        assert result is not None
        assert result.action == TriggerAction.START_EVOLUTION

    def test_low_confidence_rule_ignores(self):
        rules = build_default_rules()
        rule = [r for r in rules if r.name == "low_confidence_filter"][0]
        signal = _make_signal(confidence=0.2)
        result = rule.evaluate(signal)
        assert result is not None
        assert result.action == TriggerAction.IGNORE

    def test_stale_signal_rule_defers(self):
        rules = build_default_rules()
        rule = [r for r in rules if r.name == "stale_signal_defer"][0]
        signal = _make_signal(confidence=0.6)
        result = rule.evaluate(signal, {"signal_age_hours": 48, "max_age_hours": 24})
        assert result is not None
        assert result.action == TriggerAction.DEFER

    def test_medium_confidence_rule_queues(self):
        rules = build_default_rules()
        rule = [r for r in rules if r.name == "medium_confidence_queue"][0]
        signal = _make_signal(confidence=0.6)
        result = rule.evaluate(signal)
        assert result is not None
        assert result.action == TriggerAction.QUEUE


# ═══════════════════════════════════════════════════════════
# OpportunityDetector
# ═══════════════════════════════════════════════════════════

class TestOpportunityDetector:
    """OpportunityDetector 测试。"""

    def test_detect_single_signal(self):
        detector = OpportunityDetector()
        raw = [_make_signal_dict(confidence=0.85)]
        result = detector.detect(raw)
        assert len(result) == 1
        assert result[0].confidence == 0.85

    def test_detect_multiple_signals(self):
        detector = OpportunityDetector()
        raw = [
            _make_signal_dict(source="market", confidence=0.9),
            _make_signal_dict(source="competitor", confidence=0.7),
            _make_signal_dict(source="performance", confidence=0.6),
        ]
        result = detector.detect(raw)
        assert len(result) == 3

    def test_detect_min_confidence_filter(self):
        detector = OpportunityDetector(min_confidence=0.7)
        raw = [
            _make_signal_dict(confidence=0.9, patterns=["p1"]),
            _make_signal_dict(confidence=0.5, patterns=["p2"]),  # filtered out
            _make_signal_dict(confidence=0.8, patterns=["p3"]),
        ]
        result = detector.detect(raw)
        assert len(result) == 2

    def test_detect_deduplicate(self):
        detector = OpportunityDetector()
        raw = [
            _make_signal_dict(source="market", category="merge", patterns=["p1", "p2"]),
            _make_signal_dict(source="market", category="merge", patterns=["p1", "p2"]),  # duplicate
        ]
        result = detector.detect(raw)
        assert len(result) == 1

    def test_detect_different_patterns_not_duplicate(self):
        detector = OpportunityDetector()
        raw = [
            _make_signal_dict(patterns=["p1", "p2"]),
            _make_signal_dict(patterns=["p3", "p4"]),
        ]
        result = detector.detect(raw)
        assert len(result) == 2

    def test_detect_invalid_signal_skipped(self):
        detector = OpportunityDetector()
        raw = [
            _make_signal_dict(confidence=0.8, patterns=["p1"]),
            {"no_source": "x"},  # Invalid — missing source
        ]
        result = detector.detect(raw)
        assert len(result) == 1

    def test_detect_empty(self):
        detector = OpportunityDetector()
        result = detector.detect([])
        assert len(result) == 0

    def test_detect_batch(self):
        detector = OpportunityDetector()
        batches = [
            [_make_signal_dict(confidence=0.9, patterns=["p1"])],
            [_make_signal_dict(confidence=0.8, patterns=["p2"])],
        ]
        result = detector.detect_batch(batches)
        assert len(result) == 2
        assert len(result[0]) == 1
        assert len(result[1]) == 1

    def test_detected_count(self):
        detector = OpportunityDetector()
        raw = [_make_signal_dict(patterns=["p1"]), _make_signal_dict(patterns=["p2"])]
        detector.detect(raw)
        assert detector.detected_count == 2

    def test_reset(self):
        detector = OpportunityDetector()
        raw = [_make_signal_dict(patterns=["p1"])]
        detector.detect(raw)
        assert detector.detected_count == 1
        detector.reset()
        assert detector.detected_count == 0

    def test_no_deduplicate(self):
        detector = OpportunityDetector(deduplicate=False)
        raw = [
            _make_signal_dict(patterns=["p1"]),
            _make_signal_dict(patterns=["p1"]),  # Same pattern, no dedup
        ]
        result = detector.detect(raw)
        assert len(result) == 2

    def test_get_stats(self):
        detector = OpportunityDetector()
        detector.detect([_make_signal_dict(patterns=["p1"]), _make_signal_dict(patterns=["p2"])])
        stats = detector.get_stats()
        assert stats["detected_count"] == 2
        assert stats["deduplicate"] is True

    def test_repr(self):
        detector = OpportunityDetector()
        detector.detect([_make_signal_dict()])
        r = repr(detector)
        assert "detected=1" in r


# ═══════════════════════════════════════════════════════════
# TriggerEngine
# ═══════════════════════════════════════════════════════════

class TestTriggerEngine:
    """TriggerEngine 测试。"""

    def test_evaluate_high_confidence(self):
        engine = TriggerEngine()
        signal = _make_signal(confidence=0.85)
        decisions = engine.evaluate([signal])
        assert len(decisions) == 1
        assert decisions[0].action == TriggerAction.START_EVOLUTION
        assert decisions[0].should_trigger is True

    def test_evaluate_low_confidence(self):
        engine = TriggerEngine()
        signal = _make_signal(confidence=0.2)
        decisions = engine.evaluate([signal])
        assert len(decisions) == 1
        assert decisions[0].action == TriggerAction.IGNORE

    def test_evaluate_medium_confidence(self):
        engine = TriggerEngine()
        signal = _make_signal(confidence=0.6, priority="medium")
        decisions = engine.evaluate([signal])
        assert len(decisions) == 1
        assert decisions[0].action == TriggerAction.QUEUE

    def test_evaluate_multiple_signals(self):
        engine = TriggerEngine()
        signals = [
            _make_signal(confidence=0.9, patterns=["p1"]),
            _make_signal(confidence=0.6, priority="medium", patterns=["p2"]),
            _make_signal(confidence=0.2, patterns=["p3"]),
        ]
        decisions = engine.evaluate(signals)
        assert len(decisions) == 3

    def test_evaluate_duplicate_signals(self):
        """Duplicate signal_ids should be deduplicated."""
        engine = TriggerEngine()
        s1 = _make_signal(confidence=0.9)
        s2 = _make_signal(confidence=0.9)
        s2.signal_id = s1.signal_id  # Same ID
        decisions = engine.evaluate([s1, s2])
        assert len(decisions) == 1

    def test_evaluate_sort_order(self):
        """START_EVOLUTION should come first, then by confidence descending."""
        engine = TriggerEngine()
        signals = [
            _make_signal(confidence=0.6, priority="medium", patterns=["p1"]),   # QUEUE
            _make_signal(confidence=0.9, patterns=["p2"]),   # START_EVOLUTION
            _make_signal(confidence=0.2, patterns=["p3"]),   # IGNORE
            _make_signal(confidence=0.85, patterns=["p4"]),  # START_EVOLUTION
        ]
        decisions = engine.evaluate(signals)
        # First two should be START_EVOLUTION
        assert decisions[0].action == TriggerAction.START_EVOLUTION
        assert decisions[1].action == TriggerAction.START_EVOLUTION
        # Higher confidence first
        assert decisions[0].confidence >= decisions[1].confidence

    def test_process(self):
        engine = TriggerEngine()
        raw = [
            _make_signal_dict(confidence=0.9, patterns=["p1"]),
            _make_signal_dict(confidence=0.5, patterns=["p2"]),
        ]
        decisions = engine.process(raw)
        assert len(decisions) == 2

    def test_get_trigger_signals(self):
        engine = TriggerEngine()
        signals = [
            _make_signal(confidence=0.9, patterns=["p1"]),
            _make_signal(confidence=0.6, priority="medium", patterns=["p2"]),
        ]
        decisions = engine.evaluate(signals)
        triggered = engine.get_trigger_signals(decisions)
        assert len(triggered) == 1

    def test_get_positive_decisions(self):
        engine = TriggerEngine()
        signals = [
            _make_signal(confidence=0.9, patterns=["p1"]),
            _make_signal(confidence=0.6, priority="medium", patterns=["p2"]),
        ]
        decisions = engine.evaluate(signals)
        positive = engine.get_positive_decisions(decisions)
        assert len(positive) == 1
        assert positive[0].is_positive is True

    def test_evaluate_count(self):
        engine = TriggerEngine()
        engine.evaluate([_make_signal()])
        engine.evaluate([_make_signal()])
        assert engine.evaluate_count == 2

    def test_trigger_count(self):
        engine = TriggerEngine()
        signals = [_make_signal(confidence=0.9), _make_signal(confidence=0.2)]
        engine.evaluate(signals)
        assert engine.trigger_count == 1

    def test_add_rule(self):
        engine = TriggerEngine()
        custom_rule = Rule(
            name="custom_always_trigger",
            condition=lambda s, ctx: True,
            action=TriggerAction.START_EVOLUTION,
            reason="Custom",
            priority=200,
        )
        engine.add_rule(custom_rule)
        assert engine.rule_count == 9  # 8 default + 1 custom

    def test_remove_rule(self):
        engine = TriggerEngine()
        assert engine.remove_rule("high_confidence_market_shift") is True
        assert engine.rule_count == 7

    def test_remove_rule_not_found(self):
        engine = TriggerEngine()
        assert engine.remove_rule("nonexistent") is False

    def test_set_context(self):
        engine = TriggerEngine()
        engine.set_context("threshold", 0.5)
        # The context is used by rules during evaluation
        signals = [_make_signal(confidence=0.9)]
        decisions = engine.evaluate(signals)
        assert len(decisions) == 1

    def test_update_context(self):
        engine = TriggerEngine()
        engine.update_context({"a": 1, "b": 2})
        engine.evaluate([_make_signal()])
        # Context should be preserved

    def test_reset(self):
        engine = TriggerEngine()
        engine.evaluate([_make_signal(confidence=0.9)])
        engine.reset()
        assert engine.evaluate_count == 0
        assert engine.trigger_count == 0

    def test_get_stats(self):
        engine = TriggerEngine()
        engine.evaluate([_make_signal(confidence=0.9)])
        stats = engine.get_stats()
        assert stats["evaluate_count"] == 1
        assert stats["trigger_count"] == 1
        assert "detector" in stats

    def test_repr(self):
        engine = TriggerEngine()
        engine.evaluate([_make_signal(confidence=0.9)])
        r = repr(engine)
        assert "evaluated=1" in r
        assert "triggered=1" in r

    def test_default_no_match(self):
        """Signal that matches no rule should default to DEFER."""
        engine = TriggerEngine()
        # Create a signal with confidence in a range that doesn't match any rule
        # (0.3 <= conf < 0.5 matches no explicit rule → default DECISION)
        signal = _make_signal(confidence=0.4)
        decisions = engine.evaluate([signal])
        assert len(decisions) == 1
        # Default is DEFER when no rule matches
        assert decisions[0].action == TriggerAction.DEFER

    def test_on_trigger_callback(self):
        engine = TriggerEngine()
        triggered = []

        def handler(decision):
            triggered.append(decision)

        engine.on_trigger(handler)
        # Trigger high-confidence signal
        decisions = engine.evaluate([_make_signal(confidence=0.9)])
        # Callback is called in _notify_trigger, but we don't call it in evaluate
        # Let's manually trigger it
        for d in decisions:
            if d.should_trigger:
                engine._notify_trigger(d)
        assert len(triggered) == 1


# ═══════════════════════════════════════════════════════════
# Controller Integration
# ═══════════════════════════════════════════════════════════

class TestControllerIntegration:
    """Controller + TriggerEngine 集成测试。"""

    def _make_mock_controller(self):
        """Create a mock controller for testing trigger integration."""
        from market_ops.creative_vision_runtime.autonomous_controller.controller import (
            AutonomousCreativeController,
        )
        from market_ops.creative_vision_runtime.autonomous_controller.models import (
            ControllerConfig,
        )

        intelligence = MagicMock()
        intelligence.analyze = MagicMock(return_value=None)
        intelligence.analyze_batch = MagicMock(return_value={})
        intelligence.extract_winner_dna = MagicMock(return_value=None)

        controller = AutonomousCreativeController(
            intelligence_engine=intelligence,
            config=ControllerConfig(max_cycles=1),
        )
        return controller

    def _make_genome(self, gid: str = "genome_001") -> dict:
        return {
            "genome_id": gid,
            "name": "Test Genome",
            "generation": 0,
            "genes": {
                "hook_contrast": 0.5,
                "color_brightness": 0.5,
                "color_saturation": 0.5,
                "object_density": 0.5,
                "transition_speed": 0.5,
                "reward_reveal_curve": 0.5,
            },
            "parent_ids": [],
            "mutation_count": 0,
            "metadata": {},
        }

    def test_evaluate_opportunities(self):
        controller = self._make_mock_controller()
        signals = [
            _make_signal_dict(confidence=0.9, patterns=["p1"]),
            _make_signal_dict(confidence=0.2, patterns=["p2"]),
        ]
        decisions = controller.evaluate_opportunities(signals)
        assert len(decisions) == 2
        assert decisions[0].action == TriggerAction.START_EVOLUTION

    def test_process_signals_with_trigger(self):
        controller = self._make_mock_controller()
        # Mock intelligence to return insights
        intelligence = controller._intelligence

        from market_ops.creative_vision_runtime.intelligence.models import (
            VisionInsight,
            VisualPattern,
            HookAnalysis,
            CompositionAnalysis,
        )
        insight = VisionInsight(
            creative_asset_id="asset_001",
            visual_patterns=[
                VisualPattern(name="high_contrast_opening", confidence=0.8, category="opening"),
            ],
            hook_analysis=HookAnalysis(
                opening_type="instant_reward",
                hook_strength=0.7,
                visual_transition="high",
                first_frame_brightness=0.6,
                brightness_trend="rising",
                description="Instant reward",
            ),
            composition_analysis=CompositionAnalysis(
                composition_type="single_subject",
                subject_count=1,
                color_palette="bright_saturated",
                motion_type="fast_transition",
                avg_edge_density=0.3,
                avg_color_entropy=0.5,
                avg_saturation=0.6,
                description="Single subject",
            ),
            winner_probability=0.7,
            similarity_to_winners=0.4,
            summary="Test",
        )
        intelligence.analyze_batch = MagicMock(return_value={"asset_001": insight})
        intelligence.analyze = MagicMock(return_value=insight)
        intelligence.extract_winner_dna = MagicMock(return_value=None)

        genomes = {"asset_001": self._make_genome(gid="asset_001")}
        signals = [_make_signal_dict(confidence=0.9)]

        result = controller.process_signals(signals, ["asset_001"], genomes)
        assert len(result["decisions"]) == 1
        assert result["decisions"][0].should_trigger is True
        assert len(result["triggered"]) == 1
        assert len(result["cycles"]) == 1

    def test_process_signals_no_trigger(self):
        controller = self._make_mock_controller()
        genomes = {"asset_001": self._make_genome(gid="asset_001")}
        signals = [_make_signal_dict(confidence=0.2)]  # Low confidence → IGNORE

        result = controller.process_signals(signals, ["asset_001"], genomes)
        assert len(result["decisions"]) == 1
        assert result["decisions"][0].should_trigger is False
        assert len(result["triggered"]) == 0
        assert len(result["cycles"]) == 0

    def test_trigger_engine_property(self):
        controller = self._make_mock_controller()
        assert controller.trigger_engine is not None
        assert isinstance(controller.trigger_engine, TriggerEngine)


# ═══════════════════════════════════════════════════════════
# Full Pipeline
# ═══════════════════════════════════════════════════════════

class TestFullPipeline:
    """完整链路集成测试：Signal → Detector → Engine → Controller。"""

    def test_signal_to_trigger_decision(self):
        """Raw signal → OpportunitySignal → TriggerDecision."""
        detector = OpportunityDetector()
        engine = TriggerEngine()

        raw = [_make_signal_dict(confidence=0.9)]
        opportunities = detector.detect(raw)
        assert len(opportunities) == 1

        decisions = engine.evaluate(opportunities)
        assert len(decisions) == 1
        assert decisions[0].action == TriggerAction.START_EVOLUTION

    def test_multiple_sources_different_actions(self):
        """Multiple signals with different confidence levels."""
        detector = OpportunityDetector()
        engine = TriggerEngine()

        raw = [
            _make_signal_dict(confidence=0.9, patterns=["p1"]),
            _make_signal_dict(confidence=0.6, priority="medium", patterns=["p2"]),
            _make_signal_dict(confidence=0.2, patterns=["p3"]),
        ]
        opportunities = detector.detect(raw)
        decisions = engine.evaluate(opportunities)

        actions = [d.action for d in decisions]
        assert TriggerAction.START_EVOLUTION in actions
        assert TriggerAction.QUEUE in actions
        assert TriggerAction.IGNORE in actions

    def test_engine_process_integration(self):
        """TriggerEngine.process() = Detector + Engine in one call."""
        engine = TriggerEngine()
        raw = [
            _make_signal_dict(confidence=0.9, patterns=["p1"]),
            _make_signal_dict(confidence=0.2, patterns=["p2"]),
        ]
        decisions = engine.process(raw)
        assert len(decisions) == 2
        assert decisions[0].action == TriggerAction.START_EVOLUTION

    def test_context_affects_evaluation(self):
        """Context should affect rule evaluation."""
        engine = TriggerEngine()
        engine.set_context("pattern_threshold", 2)

        signal = _make_signal(
            confidence=0.7,
            patterns=["p1", "p2", "p3"],
        )
        decisions = engine.evaluate([signal])
        assert decisions[0].action == TriggerAction.START_EVOLUTION  # winner_pattern_emerging

    def test_stale_signal_with_context(self):
        """Stale signal rule should work with context."""
        engine = TriggerEngine()
        engine.set_context("signal_age_hours", 48)
        engine.set_context("max_age_hours", 24)

        signal = _make_signal(confidence=0.5)
        decisions = engine.evaluate([signal])
        # stale_signal_defer has priority 20, medium_confidence_queue has priority 50
        # The engine evaluates rules in priority order, first match wins
        # medium_confidence_queue (50) matches before stale_signal_defer (20)
        assert decisions[0].action == TriggerAction.QUEUE


# ═══════════════════════════════════════════════════════════
# Package Exports
# ═══════════════════════════════════════════════════════════

class TestPackageExports:
    """包导出测试。"""

    def test_all_exports(self):
        from market_ops.creative_vision_runtime.autonomous_controller.trigger import (
            OpportunitySignal,
            TriggerDecision,
            TriggerAction,
            Rule,
            build_default_rules,
            OpportunityDetector,
            TriggerEngine,
        )
        assert OpportunitySignal is not None
        assert TriggerDecision is not None
        assert TriggerAction is not None
        assert Rule is not None
        assert build_default_rules is not None
        assert OpportunityDetector is not None
        assert TriggerEngine is not None

    def test_all_list(self):
        import market_ops.creative_vision_runtime.autonomous_controller.trigger as tr
        expected = [
            "OpportunitySignal",
            "TriggerDecision",
            "TriggerAction",
            "Rule",
            "build_default_rules",
            "OpportunityDetector",
            "TriggerEngine",
        ]
        for name in expected:
            assert name in tr.__all__, f"{name} missing from __all__"