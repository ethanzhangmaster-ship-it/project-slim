"""E17.11 Memory Read Path — 测试用例.

Day 7.11 Step 1:
  覆盖 PatternStore → LearningPolicyController 的 Memory Read Path:
    - _analyze_pattern_context (Pattern 统计分析)
    - _check_pattern_override (Pattern 覆盖判断)
    - _compute_pattern_boost (置信度 boost 计算)
    - evaluate() with context_patterns (决策影响)
    - _query_relevant_patterns (Orchestrator 查询)
    - Backward compatibility (无 Pattern 时行为不变)
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.learning_policy_controller import (
    LearningPolicyController,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.evaluation.models import (
    LearningEffectiveness,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.adaptive_confidence_models import (
    AdaptiveConfidenceResult,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.learning_strategy_models import (
    LearningStrategyState,
    LearningMode,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.learning_cycle_orchestrator import (
    LearningCycleOrchestrator,
)
from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_store import (
    PatternStore,
)
from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
    PatternMemory,
    PatternCondition,
    PatternAction,
    PatternPerformance,
    PatternMiningDimension,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def controller() -> LearningPolicyController:
    return LearningPolicyController()


@pytest.fixture
def effective_learning() -> LearningEffectiveness:
    """学习有效."""
    return LearningEffectiveness(
        effectiveness_score=0.75,
        is_effective=True,
        learning_gain=0.15,
    )


@pytest.fixture
def ineffective_learning() -> LearningEffectiveness:
    """学习无效."""
    return LearningEffectiveness(
        effectiveness_score=0.30,
        is_effective=False,
        learning_gain=-0.05,
    )


@pytest.fixture
def high_confidence() -> AdaptiveConfidenceResult:
    """高置信度."""
    return AdaptiveConfidenceResult(
        base_confidence=0.80,
        adjusted_confidence=0.85,
    )


@pytest.fixture
def low_confidence() -> AdaptiveConfidenceResult:
    """低置信度."""
    return AdaptiveConfidenceResult(
        base_confidence=0.35,
        adjusted_confidence=0.30,
    )


@pytest.fixture
def default_state() -> LearningStrategyState:
    return LearningStrategyState.default()


def _make_pattern(
    success_rate: float = 0.85,
    avg_confidence: float = 0.90,
    samples: int = 20,
    action_type: str = "increase_budget",
    tags: list[str] | None = None,
) -> PatternMemory:
    """创建测试 Pattern."""
    condition = PatternCondition(
        opportunity_type=action_type,
        action_type=action_type,
    )
    action = PatternAction(
        action_type=action_type,
        expected_impact="amplify",
    )
    perf = PatternPerformance(
        samples=samples,
        success_count=int(samples * success_rate),
        success_rate=success_rate,
        avg_reward=success_rate * 0.9,
        avg_confidence=avg_confidence,
        last_seen=datetime(2026, 7, 29, tzinfo=timezone.utc).isoformat(),
    )
    p = PatternMemory(
        dimension=PatternMiningDimension.OPPORTUNITY_ACTION,
        condition=condition,
        action=action,
        performance=perf,
        tags=tags or ["positive"],
    )
    p.compute_score()
    return p


@pytest.fixture
def strong_pattern() -> PatternMemory:
    """强 Pattern: 高成功率、高置信度."""
    return _make_pattern(success_rate=0.85, avg_confidence=0.90, samples=20)


@pytest.fixture
def weak_pattern() -> PatternMemory:
    """弱 Pattern: 低成功率、低置信度."""
    return _make_pattern(success_rate=0.35, avg_confidence=0.30, samples=5)


@pytest.fixture
def medium_pattern() -> PatternMemory:
    """中等 Pattern."""
    return _make_pattern(success_rate=0.65, avg_confidence=0.70, samples=15)


# ═══════════════════════════════════════════════════════════════
# Test: _analyze_pattern_context
# ═══════════════════════════════════════════════════════════════


class TestAnalyzePatternContext:
    """Pattern 统计分析测试."""

    def test_empty_patterns(self, controller):
        """空列表."""
        stats = controller._analyze_pattern_context([])
        assert stats["count"] == 0
        assert stats["avg_success_rate"] == 0.0
        assert stats["avg_confidence"] == 0.0
        assert stats["high_confidence_count"] == 0
        assert stats["total_samples"] == 0

    def test_single_pattern(self, controller, strong_pattern):
        """单个 Pattern."""
        stats = controller._analyze_pattern_context([strong_pattern])
        assert stats["count"] == 1
        assert stats["avg_success_rate"] == 0.85
        assert stats["avg_confidence"] == 0.90
        assert stats["high_confidence_count"] == 1
        assert stats["total_samples"] == 20

    def test_multiple_patterns(self, controller, strong_pattern, medium_pattern, weak_pattern):
        """多个 Pattern 的聚合."""
        stats = controller._analyze_pattern_context([
            strong_pattern, medium_pattern, weak_pattern,
        ])
        assert stats["count"] == 3
        assert stats["avg_success_rate"] == pytest.approx(0.6167, abs=0.01)
        assert stats["avg_confidence"] == pytest.approx(0.6333, abs=0.01)
        assert stats["high_confidence_count"] == 2  # strong (0.90) + medium (0.70)
        assert stats["total_samples"] == 40  # 20 + 15 + 5

    def test_only_high_confidence(self, controller, strong_pattern):
        """全部高置信度."""
        p2 = _make_pattern(success_rate=0.80, avg_confidence=0.75, samples=10)
        stats = controller._analyze_pattern_context([strong_pattern, p2])
        assert stats["high_confidence_count"] == 2

    def test_no_high_confidence(self, controller, weak_pattern):
        """无高置信度 Pattern."""
        stats = controller._analyze_pattern_context([weak_pattern])
        assert stats["high_confidence_count"] == 0

    def test_success_rate_averaging(self, controller):
        """成功率平均计算."""
        p1 = _make_pattern(success_rate=0.50, avg_confidence=0.50, samples=10)
        p2 = _make_pattern(success_rate=0.90, avg_confidence=0.50, samples=10)
        stats = controller._analyze_pattern_context([p1, p2])
        assert stats["avg_success_rate"] == 0.70

    def test_total_samples_accumulation(self, controller):
        """样本数累加."""
        p1 = _make_pattern(success_rate=0.50, avg_confidence=0.50, samples=100)
        p2 = _make_pattern(success_rate=0.50, avg_confidence=0.50, samples=200)
        stats = controller._analyze_pattern_context([p1, p2])
        assert stats["total_samples"] == 300


# ═══════════════════════════════════════════════════════════════
# Test: _check_pattern_override
# ═══════════════════════════════════════════════════════════════


class TestCheckPatternOverride:
    """Pattern 覆盖判断测试."""

    def test_override_all_conditions_met(self, controller):
        """所有条件满足 → 覆盖."""
        stats = {
            "count": 3,
            "avg_success_rate": 0.75,
            "high_confidence_count": 2,
        }
        assert controller._check_pattern_override(0.30, False, stats) is True

    def test_override_too_few_patterns(self, controller):
        """Pattern 数量不足."""
        stats = {
            "count": 1,
            "avg_success_rate": 0.80,
            "high_confidence_count": 1,
        }
        assert controller._check_pattern_override(0.30, False, stats) is False

    def test_override_low_success_rate(self, controller):
        """平均成功率不足."""
        stats = {
            "count": 3,
            "avg_success_rate": 0.45,
            "high_confidence_count": 2,
        }
        assert controller._check_pattern_override(0.30, False, stats) is False

    def test_override_no_high_confidence(self, controller):
        """无高置信度 Pattern."""
        stats = {
            "count": 3,
            "avg_success_rate": 0.75,
            "high_confidence_count": 0,
        }
        assert controller._check_pattern_override(0.30, False, stats) is False

    def test_override_exact_threshold(self, controller):
        """刚好在阈值上."""
        stats = {
            "count": 2,
            "avg_success_rate": 0.60,
            "high_confidence_count": 1,
        }
        assert controller._check_pattern_override(0.30, False, stats) is True

    def test_override_empty_stats(self, controller):
        """空统计."""
        stats = {"count": 0, "avg_success_rate": 0.0, "high_confidence_count": 0}
        assert controller._check_pattern_override(0.30, False, stats) is False


# ═══════════════════════════════════════════════════════════════
# Test: _compute_pattern_boost
# ═══════════════════════════════════════════════════════════════


class TestComputePatternBoost:
    """置信度 boost 计算测试."""

    def test_boost_zero_patterns(self, controller):
        """无 Pattern → boost 0."""
        stats = {"count": 0, "avg_success_rate": 0.0}
        assert controller._compute_pattern_boost(stats) == 0.0

    def test_boost_single_pattern(self, controller):
        """单个 Pattern."""
        stats = {"count": 1, "avg_success_rate": 0.85}
        # boost = 1 * 0.02 + 0.85 * 0.10 = 0.02 + 0.085 = 0.105
        assert controller._compute_pattern_boost(stats) == 0.105

    def test_boost_multiple_patterns(self, controller):
        """多个 Pattern."""
        stats = {"count": 5, "avg_success_rate": 0.80}
        # boost = 5 * 0.02 + 0.80 * 0.10 = 0.10 + 0.08 = 0.18 → capped at 0.15
        assert controller._compute_pattern_boost(stats) == 0.15

    def test_boost_capped_at_max(self, controller):
        """boost 上限 0.15."""
        stats = {"count": 10, "avg_success_rate": 0.95}
        assert controller._compute_pattern_boost(stats) == 0.15

    def test_boost_low_success(self, controller):
        """低成功率."""
        stats = {"count": 2, "avg_success_rate": 0.30}
        # boost = 2 * 0.02 + 0.30 * 0.10 = 0.04 + 0.03 = 0.07
        assert controller._compute_pattern_boost(stats) == 0.07


# ═══════════════════════════════════════════════════════════════
# Test: evaluate() with context_patterns — Backward Compatibility
# ═══════════════════════════════════════════════════════════════


class TestEvaluateBackwardCompat:
    """向后兼容: 无 context_patterns 时行为不变."""

    def test_no_patterns_effective_learning(self, controller, effective_learning, high_confidence, default_state):
        """无 Pattern 时，有效学习 + 高置信度 → ALLOW."""
        decision = controller.evaluate(
            effectiveness=effective_learning,
            adaptive_confidence=high_confidence,
            current_state=default_state,
        )
        assert decision.should_learn is True
        # effective + high confidence → AGGRESSIVE mode, differs from default CONSERVATIVE → adjust_mode
        assert decision.decision_type == "adjust_mode"

    def test_no_patterns_ineffective_learning(self, controller, ineffective_learning, high_confidence, default_state):
        """无 Pattern 时，无效学习 + 高置信度 → BLOCK."""
        decision = controller.evaluate(
            effectiveness=ineffective_learning,
            adaptive_confidence=high_confidence,
            current_state=default_state,
        )
        assert decision.should_learn is False
        assert decision.decision_type == "block_learning"

    def test_no_patterns_low_confidence(self, controller, effective_learning, low_confidence, default_state):
        """无 Pattern 时，有效学习 + 低置信度 → BLOCK."""
        decision = controller.evaluate(
            effectiveness=effective_learning,
            adaptive_confidence=low_confidence,
            current_state=default_state,
        )
        assert decision.should_learn is False

    def test_no_patterns_none_values(self, controller, default_state):
        """无 Pattern 时，无 effectiveness/confidence → 默认."""
        decision = controller.evaluate(
            effectiveness=None,
            adaptive_confidence=None,
            current_state=default_state,
        )
        assert decision.should_learn is True

    def test_no_patterns_evidence_no_pattern_refs(self, controller, effective_learning, high_confidence, default_state):
        """无 Pattern 时 evidence 不含 pattern 字段."""
        decision = controller.evaluate(
            effectiveness=effective_learning,
            adaptive_confidence=high_confidence,
            current_state=default_state,
        )
        pattern_evidence = [e for e in decision.evidence if "pattern" in e.lower()]
        assert len(pattern_evidence) == 0


# ═══════════════════════════════════════════════════════════════
# Test: evaluate() with context_patterns — Pattern Influence
# ═══════════════════════════════════════════════════════════════


class TestEvaluatePatternInfluence:
    """Pattern 对决策的影响测试."""

    def test_patterns_override_low_confidence_block(self, controller, effective_learning, low_confidence, default_state):
        """低置信度但有强 Pattern → 覆盖 BLOCK → ALLOW."""
        p1 = _make_pattern(success_rate=0.80, avg_confidence=0.85, samples=20)
        p2 = _make_pattern(success_rate=0.75, avg_confidence=0.80, samples=15)
        decision = controller.evaluate(
            effectiveness=effective_learning,
            adaptive_confidence=low_confidence,
            current_state=default_state,
            context_patterns=[p1, p2],
        )
        # 有 2 个高成功率 Pattern，应该覆盖低置信度 → ALLOW
        assert decision.should_learn is True

    def test_patterns_no_override_weak_patterns(self, controller, effective_learning, low_confidence, default_state):
        """弱 Pattern 不足以覆盖."""
        p1 = _make_pattern(success_rate=0.40, avg_confidence=0.30, samples=5)
        p2 = _make_pattern(success_rate=0.45, avg_confidence=0.35, samples=5)
        decision = controller.evaluate(
            effectiveness=effective_learning,
            adaptive_confidence=low_confidence,
            current_state=default_state,
            context_patterns=[p1, p2],
        )
        # 弱 Pattern 不能覆盖
        assert decision.should_learn is False

    def test_patterns_boost_confidence(self, controller, effective_learning, high_confidence, default_state):
        """Pattern 提升置信度."""
        decision_no_patterns = controller.evaluate(
            effectiveness=effective_learning,
            adaptive_confidence=high_confidence,
            current_state=default_state,
        )
        p1 = _make_pattern(success_rate=0.85, avg_confidence=0.90, samples=20)
        p2 = _make_pattern(success_rate=0.80, avg_confidence=0.85, samples=15)
        decision_with_patterns = controller.evaluate(
            effectiveness=effective_learning,
            adaptive_confidence=high_confidence,
            current_state=default_state,
            context_patterns=[p1, p2],
        )
        assert decision_with_patterns.confidence >= decision_no_patterns.confidence

    def test_patterns_evidence_includes_pattern_refs(self, controller, effective_learning, high_confidence, default_state):
        """evidence 包含 Pattern 字段."""
        p1 = _make_pattern(success_rate=0.85, avg_confidence=0.90, samples=20)
        decision = controller.evaluate(
            effectiveness=effective_learning,
            adaptive_confidence=high_confidence,
            current_state=default_state,
            context_patterns=[p1],
        )
        pattern_evidence = [e for e in decision.evidence if "matched_patterns" in e]
        assert len(pattern_evidence) == 1
        assert "1" in pattern_evidence[0]

    def test_patterns_bias_aggressive_mode(self, controller, effective_learning, high_confidence, default_state):
        """强 Pattern → 倾向 AGGRESSIVE."""
        # 使用中等有效性 + 中等置信度，正常情况下不会 AGGRESSIVE
        medium_eff = LearningEffectiveness(
            effectiveness_score=0.55,
            is_effective=True,
            learning_gain=0.05,
        )
        medium_conf = AdaptiveConfidenceResult(
            base_confidence=0.55,
            adjusted_confidence=0.55,
        )
        p1 = _make_pattern(success_rate=0.85, avg_confidence=0.90, samples=20)
        p2 = _make_pattern(success_rate=0.80, avg_confidence=0.85, samples=15)
        p3 = _make_pattern(success_rate=0.75, avg_confidence=0.80, samples=10)
        decision = controller.evaluate(
            effectiveness=medium_eff,
            adaptive_confidence=medium_conf,
            current_state=default_state,
            context_patterns=[p1, p2, p3],
        )
        # 3 个高置信度 Pattern → AGGRESSIVE
        assert decision.strategy_mode == LearningMode.AGGRESSIVE.value

    def test_no_patterns_bias_conservative(self, controller, default_state):
        """无 Pattern → 倾向 CONSERVATIVE."""
        medium_eff = LearningEffectiveness(
            effectiveness_score=0.55,
            is_effective=True,
            learning_gain=0.02,
        )
        medium_conf = AdaptiveConfidenceResult(
            base_confidence=0.50,
            adjusted_confidence=0.50,
        )
        decision = controller.evaluate(
            effectiveness=medium_eff,
            adaptive_confidence=medium_conf,
            current_state=default_state,
            context_patterns=[],
        )
        assert decision.strategy_mode == LearningMode.CONSERVATIVE.value

    def test_patterns_empty_list_same_as_none(self, controller, effective_learning, high_confidence, default_state):
        """空列表 = None."""
        d1 = controller.evaluate(
            effectiveness=effective_learning,
            adaptive_confidence=high_confidence,
            current_state=default_state,
            context_patterns=[],
        )
        d2 = controller.evaluate(
            effectiveness=effective_learning,
            adaptive_confidence=high_confidence,
            current_state=default_state,
        )
        assert d1.confidence == d2.confidence


# ═══════════════════════════════════════════════════════════════
# Test: _query_relevant_patterns (Orchestrator)
# ═══════════════════════════════════════════════════════════════


class TestQueryRelevantPatterns:
    """Orchestrator 查询 Pattern 测试."""

    def test_no_pattern_store(self):
        """无 PatternStore → 返回空列表."""
        orchestrator = LearningCycleOrchestrator()
        result = orchestrator._query_relevant_patterns()
        assert result == []

    def test_empty_pattern_store(self):
        """空 PatternStore."""
        orchestrator = LearningCycleOrchestrator()
        orchestrator.set_pattern_store(PatternStore())
        result = orchestrator._query_relevant_patterns()
        assert result == []

    def test_with_patterns(self, strong_pattern):
        """有 Pattern 时返回列表."""
        store = PatternStore()
        store.store(strong_pattern)
        orchestrator = LearningCycleOrchestrator()
        orchestrator.set_pattern_store(store)
        result = orchestrator._query_relevant_patterns()
        assert len(result) == 1

    def test_multiple_patterns(self, strong_pattern, medium_pattern):
        """多个 Pattern (不同 action_type 避免去重)."""
        store = PatternStore()
        # strong_pattern 使用默认 action_type="increase_budget"
        store.store(strong_pattern)
        # medium_pattern 使用不同 action_type 避免被 PatternStore 去重
        p2 = _make_pattern(success_rate=0.65, avg_confidence=0.70, samples=15, action_type="decrease_budget")
        store.store(p2)
        orchestrator = LearningCycleOrchestrator()
        orchestrator.set_pattern_store(store)
        result = orchestrator._query_relevant_patterns()
        assert len(result) == 2

    def test_filters_out_zero_success_rate(self):
        """过滤掉零成功率 Pattern."""
        store = PatternStore()
        zero_pattern = _make_pattern(success_rate=0.0, avg_confidence=0.50, samples=0)
        store.store(zero_pattern)
        orchestrator = LearningCycleOrchestrator()
        orchestrator.set_pattern_store(store)
        result = orchestrator._query_relevant_patterns()
        # 成功率为 0 的 Pattern 应被过滤
        assert len(result) == 0


# ═══════════════════════════════════════════════════════════════
# Test: End-to-End: Decision Memory Read Path
# ═══════════════════════════════════════════════════════════════


class TestEndToEndMemoryReadPath:
    """端到端: Pattern 影响决策的完整链路."""

    def test_cycle_with_patterns_affects_decision(self, effective_learning, high_confidence):
        """有 Pattern 的完整决策链路."""
        store = PatternStore()
        p1 = _make_pattern(success_rate=0.85, avg_confidence=0.90, samples=20, action_type="increase_budget")
        p2 = _make_pattern(success_rate=0.80, avg_confidence=0.85, samples=15, action_type="decrease_budget")
        store.store(p1)
        store.store(p2)

        orchestrator = LearningCycleOrchestrator()
        orchestrator.set_pattern_store(store)

        # 模拟 _decide_policy 调用
        patterns = orchestrator._query_relevant_patterns()
        assert len(patterns) == 2

        decision = orchestrator._policy_controller.evaluate(
            effectiveness=effective_learning,
            adaptive_confidence=high_confidence,
            current_state=orchestrator.strategy_state,
            context_patterns=patterns,
        )
        assert decision.should_learn is True
        # Pattern 应该在 evidence 中体现
        pattern_evidence = [e for e in decision.evidence if "matched_patterns" in e]
        assert len(pattern_evidence) == 1

    def test_cycle_without_patterns_works(self, effective_learning, high_confidence):
        """无 Pattern 的决策链路正常."""
        orchestrator = LearningCycleOrchestrator()
        patterns = orchestrator._query_relevant_patterns()
        assert patterns == []

        decision = orchestrator._policy_controller.evaluate(
            effectiveness=effective_learning,
            adaptive_confidence=high_confidence,
            current_state=orchestrator.strategy_state,
        )
        assert decision.should_learn is True