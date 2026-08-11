"""E17.9 Experience Extraction — 测试用例.

Day 7.9 Step 1:
  覆盖 Experience Extraction 层的:
    - ConsolidatedExperience 模型 (factory methods, properties, serialization)
    - ExtractionResult 模型 (factory methods, aggregation, serialization)
    - ExperienceExtractor 引擎 (extract, extract_batch, to_growth_experience)
    - Memory System 桥接 (extract_and_store)
    - Edge cases (empty cycle, gated, adjusted, batch)
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.learning_memory_models import (
    ConsolidatedExperience,
    ExtractionResult,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.learning_orchestration_models import (
    OrchestrationCycleResult,
    CycleOrchestrationState,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.learning_strategy_models import (
    LearningPolicyDecision,
    PolicyDecisionType,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.learning_execution_models import (
    LearningExecutionResult,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.learning_feedback_models import (
    LearningFeedback,
    FeedbackClassification,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.cycle_gate_models import (
    CycleGateResult,
    GateDecision,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.learning_policy_models import (
    PolicyAdjustment,
    PolicyAdjustmentSet,
    AdjustmentDirection,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.learning_experience_extractor import (
    ExperienceExtractor,
)
from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import (
    ExperienceStore,
)
from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
    GrowthExperience,
    ExperienceOutcomeLevel,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def extractor() -> ExperienceExtractor:
    """默认提取器."""
    return ExperienceExtractor(significance_threshold=0.3)


@pytest.fixture
def low_threshold_extractor() -> ExperienceExtractor:
    """低阈值提取器 (更容易标记为显著)."""
    return ExperienceExtractor(significance_threshold=0.1)


@pytest.fixture
def high_threshold_extractor() -> ExperienceExtractor:
    """高阈值提取器 (更难标记为显著)."""
    return ExperienceExtractor(significance_threshold=0.9)


@pytest.fixture
def experience_store() -> ExperienceStore:
    """空经验存储."""
    return ExperienceStore()


@pytest.fixture
def good_policy_decision() -> LearningPolicyDecision:
    """好的策略决策 (GOOD_LEARNING)."""
    return LearningPolicyDecision(
        decision_type=PolicyDecisionType.ADJUST_MODE.value,
        action="increase_budget",
        should_learn=True,
        should_update_memory=True,
        strategy_mode="exploit",
        confidence=0.85,
        expected_impact=0.25,
        priority="high",
        adjustments=["exploration_rate: 0.35 → 0.20"],
    )


@pytest.fixture
def good_execution_result() -> LearningExecutionResult:
    """成功执行结果."""
    return LearningExecutionResult(
        success=True,
        action="increase_budget",
        executed=True,
        memory_updated=True,
        strategy_updated=True,
    )


@pytest.fixture
def good_effectiveness():
    """好的有效性评估 (有学习增益)."""
    class MockEffectiveness:
        def __init__(self):
            self.learning_gain = 0.15
            self.effectiveness_score = 0.78
            self.baseline_success_rate = 0.60
            self.enhanced_success_rate = 0.75
            self.baseline_avg_confidence = 0.65
            self.enhanced_avg_confidence = 0.82
    return MockEffectiveness()


@pytest.fixture
def good_feedback() -> LearningFeedback:
    """GOOD_LEARNING 反馈."""
    return LearningFeedback(
        classification=FeedbackClassification.GOOD_LEARNING.value,
        actions=["BOOST_CONFIDENCE", "REDUCE_EXPLORATION"],
        confidence_adjustment=0.1,
        exploration_adjustment=-0.15,
        recommendation="Good learning detected, reinforce patterns",
    )


@pytest.fixture
def good_gate_result() -> CycleGateResult:
    """CONTINUE 门控."""
    return CycleGateResult(
        decision=GateDecision.CONTINUE.value,
        decision_reason="Learning is effective",
        triggered_rule="positive_learning_gain",
        feedback_classification=FeedbackClassification.GOOD_LEARNING.value,
        learning_gain=0.15,
    )


@pytest.fixture
def good_adjustments() -> PolicyAdjustmentSet:
    """策略调整集合."""
    return PolicyAdjustmentSet.from_adjustments(
        cycle_number=1,
        adjustments=[
            PolicyAdjustment(
                cycle_number=1,
                target_policy="exploration_rate",
                current_value=0.35,
                recommended_value=0.20,
                adjustment_delta=-0.15,
                direction=AdjustmentDirection.DECREASE.value,
                reason="Good learning, reduce exploration",
                confidence=0.85,
            ),
            PolicyAdjustment(
                cycle_number=1,
                target_policy="confidence_threshold",
                current_value=0.75,
                recommended_value=0.82,
                adjustment_delta=0.07,
                direction=AdjustmentDirection.INCREASE.value,
                reason="Increase execution threshold",
                confidence=0.80,
            ),
        ],
        source_feedback=FeedbackClassification.GOOD_LEARNING.value,
        source_gate=GateDecision.CONTINUE.value,
    )


@pytest.fixture
def good_cycle_result(
    good_policy_decision,
    good_execution_result,
    good_effectiveness,
    good_gate_result,
    good_adjustments,
) -> OrchestrationCycleResult:
    """完整的成功编排周期结果."""
    return OrchestrationCycleResult(
        cycle_number=1,
        state=CycleOrchestrationState.COMPLETED.value,
        effectiveness=good_effectiveness,
        policy_decision=good_policy_decision,
        execution_result=good_execution_result,
        gate_result=good_gate_result,
        policy_adjustments=good_adjustments,
        next_action="continue",
    )


@pytest.fixture
def bad_cycle_result() -> OrchestrationCycleResult:
    """失败的编排周期结果 (BAD_LEARNING)."""
    class BadEffectiveness:
        learning_gain = -0.15
        effectiveness_score = 0.25
        baseline_success_rate = 0.60
        enhanced_success_rate = 0.45
        baseline_avg_confidence = 0.60
        enhanced_avg_confidence = 0.40

    return OrchestrationCycleResult(
        cycle_number=2,
        state=CycleOrchestrationState.COMPLETED.value,
        effectiveness=BadEffectiveness(),
        policy_decision=LearningPolicyDecision(
            decision_type=PolicyDecisionType.ADJUST_MODE.value,
            action="reduce_budget",
            confidence=0.55,
            expected_impact=-0.10,
            priority="medium",
        ),
        execution_result=LearningExecutionResult(
            success=True,
            action="reduce_budget",
            executed=True,
        ),
        gate_result=CycleGateResult(
            decision=GateDecision.CONTINUE.value,
            feedback_classification=FeedbackClassification.BAD_LEARNING.value,
            learning_gain=-0.15,
        ),
        next_action="continue",
    )


@pytest.fixture
def gated_cycle_result() -> OrchestrationCycleResult:
    """被门控的编排周期结果."""
    class GatedEffectiveness:
        learning_gain = -0.30
        effectiveness_score = 0.20
        baseline_success_rate = 0.60
        enhanced_success_rate = 0.30
        baseline_avg_confidence = 0.60
        enhanced_avg_confidence = 0.35

    return OrchestrationCycleResult(
        cycle_number=3,
        state=CycleOrchestrationState.PAUSED.value,
        effectiveness=GatedEffectiveness(),
        next_action="pause",
        gate_result=CycleGateResult(
            decision=GateDecision.PAUSE.value,
            decision_reason="Negative learning trend detected",
            triggered_rule="consecutive_negative",
            feedback_classification=FeedbackClassification.BAD_LEARNING.value,
            learning_gain=-0.30,
        ),
    )


@pytest.fixture
def minimal_cycle_result() -> OrchestrationCycleResult:
    """最小编排周期结果 (无附加数据)."""
    return OrchestrationCycleResult(
        cycle_number=0,
        state=CycleOrchestrationState.IDLE.value,
        next_action="continue",
    )


# ═══════════════════════════════════════════════════════════════
# Test: ConsolidatedExperience Model
# ═══════════════════════════════════════════════════════════════


class TestConsolidatedExperienceModel:
    """ConsolidatedExperience 数据模型测试."""

    # ── Default Construction ──

    def test_default_construction(self):
        """默认构造."""
        exp = ConsolidatedExperience()
        assert exp.experience_id != ""
        assert exp.cycle_number == 0
        assert exp.action_type == ""
        assert exp.success is False
        assert exp.reward == 0.0
        assert exp.confidence == 0.0
        assert exp.category == "creative"
        assert exp.is_significant is False

    def test_custom_construction(self):
        """自定义构造."""
        exp = ConsolidatedExperience(
            source_cycle_id="cycle-001",
            cycle_number=5,
            action_type="increase_budget",
            success=True,
            reward=0.75,
            confidence=0.85,
            category="ua",
            learning_gain=0.15,
            effectiveness_score=0.78,
            is_significant=True,
        )
        assert exp.source_cycle_id == "cycle-001"
        assert exp.cycle_number == 5
        assert exp.action_type == "increase_budget"
        assert exp.success is True
        assert exp.reward == 0.75
        assert exp.confidence == 0.85
        assert exp.category == "ua"
        assert exp.learning_gain == 0.15
        assert exp.effectiveness_score == 0.78
        assert exp.is_significant is True

    # ── Properties ──

    def test_has_learning_gain_positive(self):
        """正向学习增益."""
        exp = ConsolidatedExperience(learning_gain=0.20)
        assert exp.has_learning_gain is True

    def test_has_learning_gain_negative(self):
        """负向学习增益."""
        exp = ConsolidatedExperience(learning_gain=-0.10)
        assert exp.has_learning_gain is False

    def test_has_learning_gain_zero(self):
        """零增益."""
        exp = ConsolidatedExperience(learning_gain=0.0)
        assert exp.has_learning_gain is False

    def test_is_effective_true(self):
        """有效学习."""
        exp = ConsolidatedExperience(effectiveness_score=0.75)
        assert exp.is_effective is True

    def test_is_effective_false(self):
        """无效学习."""
        exp = ConsolidatedExperience(effectiveness_score=0.30)
        assert exp.is_effective is False

    def test_is_effective_boundary(self):
        """边界值 0.5."""
        exp = ConsolidatedExperience(effectiveness_score=0.50)
        assert exp.is_effective is True

    def test_is_gated_pause(self):
        """门控 PAUSE."""
        exp = ConsolidatedExperience(gate_decision="pause")
        assert exp.is_gated is True

    def test_is_gated_rollback(self):
        """门控 ROLLBACK."""
        exp = ConsolidatedExperience(gate_decision="rollback")
        assert exp.is_gated is True

    def test_is_gated_continue(self):
        """未门控."""
        exp = ConsolidatedExperience(gate_decision="continue")
        assert exp.is_gated is False

    def test_has_adjustments_true(self):
        """有策略调整."""
        exp = ConsolidatedExperience(policy_adjustments=[{"target": "exploration_rate"}])
        assert exp.has_adjustments is True

    def test_has_adjustments_false(self):
        """无策略调整."""
        exp = ConsolidatedExperience()
        assert exp.has_adjustments is False

    def test_adjustment_count(self):
        """调整数量."""
        exp = ConsolidatedExperience(policy_adjustments=[{}, {}, {}])
        assert exp.adjustment_count == 3

    def test_adjustment_count_zero(self):
        """零调整."""
        exp = ConsolidatedExperience()
        assert exp.adjustment_count == 0

    # ── Factory: from_cycle_result ──

    def test_from_good_cycle_result(self, good_cycle_result):
        """从好的编排周期结果创建经验."""
        exp = ConsolidatedExperience.from_cycle_result(good_cycle_result)
        assert exp.source_cycle_id == good_cycle_result.cycle_id
        assert exp.cycle_number == 1
        assert exp.action_type == "increase_budget"
        assert exp.success is True
        assert exp.learning_gain == 0.15
        assert exp.effectiveness_score == 0.78
        assert exp.confidence == 0.85
        assert exp.category == "ua"
        assert exp.feedback_classification == FeedbackClassification.GOOD_LEARNING.value
        assert exp.gate_decision == GateDecision.CONTINUE.value
        assert exp.has_adjustments is True
        assert exp.adjustment_count == 2
        assert "positive_learning" in exp.tags
        assert "effective" in exp.tags
        assert "success" in exp.tags
        assert "adjusted" in exp.tags

    def test_from_good_cycle_result_significance(self, good_cycle_result):
        """好的周期结果应有高显著性."""
        exp = ConsolidatedExperience.from_cycle_result(good_cycle_result)
        assert exp.significance_score > 0.3
        assert exp.is_significant is True

    def test_from_bad_cycle_result(self, bad_cycle_result):
        """从坏的编排周期结果创建经验."""
        exp = ConsolidatedExperience.from_cycle_result(bad_cycle_result)
        assert exp.cycle_number == 2
        assert exp.action_type == "reduce_budget"
        assert exp.learning_gain == -0.15
        assert exp.effectiveness_score == 0.25
        assert exp.feedback_classification == FeedbackClassification.BAD_LEARNING.value
        assert exp.has_learning_gain is False
        assert exp.is_effective is False

    def test_from_gated_cycle_result(self, gated_cycle_result):
        """从门控的周期结果创建经验."""
        exp = ConsolidatedExperience.from_cycle_result(gated_cycle_result)
        assert exp.cycle_number == 3
        assert exp.is_gated is True
        assert exp.gate_decision == GateDecision.PAUSE.value
        assert exp.feedback_classification == FeedbackClassification.BAD_LEARNING.value
        assert exp.learning_gain == -0.30
        assert "gated" in exp.tags

    def test_from_minimal_cycle_result(self, minimal_cycle_result):
        """从最小编排周期结果创建经验."""
        exp = ConsolidatedExperience.from_cycle_result(minimal_cycle_result)
        assert exp.cycle_number == 0
        assert exp.action_type == ""
        assert exp.success is False
        # learning_gain=0, effectiveness=0, success=False
        # gain_normalized = max(0, min(1, 0+0.5)) = 0.5
        # reward = 0.5*0.5 + 0*0.3 + 0*0.2 = 0.25
        assert exp.reward == 0.25

    def test_from_cycle_result_with_significance_threshold(self, good_cycle_result):
        """测试显著性阈值."""
        exp_high = ConsolidatedExperience.from_cycle_result(good_cycle_result, significance_threshold=0.9)
        exp_low = ConsolidatedExperience.from_cycle_result(good_cycle_result, significance_threshold=0.1)
        # 高阈值下可能不显著
        assert exp_low.is_significant is True

    # ── Category Inference ──

    def test_infer_category_creative(self):
        """推断创意类别."""
        exp = ConsolidatedExperience.from_cycle_result(
            OrchestrationCycleResult(
                cycle_number=1,
                policy_decision=LearningPolicyDecision(action="mutate_hook"),
                state=CycleOrchestrationState.COMPLETED.value,
            )
        )
        assert exp.category == "creative"

    def test_infer_category_ua(self):
        """推断UA类别."""
        exp = ConsolidatedExperience.from_cycle_result(
            OrchestrationCycleResult(
                cycle_number=1,
                policy_decision=LearningPolicyDecision(action="increase_budget"),
                state=CycleOrchestrationState.COMPLETED.value,
            )
        )
        assert exp.category == "ua"

    def test_infer_category_revenue(self):
        """推断收入类别."""
        exp = ConsolidatedExperience.from_cycle_result(
            OrchestrationCycleResult(
                cycle_number=1,
                policy_decision=LearningPolicyDecision(action="optimize_pricing"),
                state=CycleOrchestrationState.COMPLETED.value,
            )
        )
        assert exp.category == "revenue"

    def test_infer_category_unknown(self):
        """未知动作默认为 creative."""
        exp = ConsolidatedExperience.from_cycle_result(
            OrchestrationCycleResult(
                cycle_number=1,
                policy_decision=LearningPolicyDecision(action="unknown_action"),
                state=CycleOrchestrationState.COMPLETED.value,
            )
        )
        assert exp.category == "creative"

    # ── Serialization ──

    def test_to_dict(self, good_cycle_result):
        """序列化 to_dict."""
        exp = ConsolidatedExperience.from_cycle_result(good_cycle_result)
        d = exp.to_dict()
        assert d["experience_id"] == exp.experience_id
        assert d["source_cycle_id"] == exp.source_cycle_id
        assert d["cycle_number"] == exp.cycle_number
        assert d["action_type"] == "increase_budget"
        assert d["success"] is True
        assert d["reward"] == exp.reward
        assert d["confidence"] == 0.85
        assert d["category"] == "ua"
        assert d["learning_gain"] == 0.15
        assert d["effectiveness_score"] == 0.78
        assert d["is_significant"] is True
        assert isinstance(d["tags"], list)
        assert isinstance(d["policy_adjustments"], list)
        assert isinstance(d["metrics_delta"], dict)

    def test_from_dict_roundtrip(self, good_cycle_result):
        """序列化往返."""
        exp = ConsolidatedExperience.from_cycle_result(good_cycle_result)
        d = exp.to_dict()
        restored = ConsolidatedExperience.from_dict(d)
        assert restored.experience_id == exp.experience_id
        assert restored.cycle_number == exp.cycle_number
        assert restored.action_type == exp.action_type
        assert restored.reward == exp.reward
        assert restored.is_significant == exp.is_significant

    # ── Reward Computation ──

    def test_reward_successful_learning(self):
        """成功学习的奖励."""
        exp = ConsolidatedExperience(success=True, learning_gain=0.20, effectiveness_score=0.80)
        exp.reward = ConsolidatedExperience._compute_reward(exp)
        # gain_normalized = max(0, min(1, 0.20+0.5)) = 0.70
        # reward = 0.70*0.5 + 1.0*0.3 + 0.80*0.2 = 0.35 + 0.30 + 0.16 = 0.81
        assert exp.reward == 0.81

    def test_reward_failed_learning(self):
        """失败学习的奖励."""
        exp = ConsolidatedExperience(success=False, learning_gain=-0.20, effectiveness_score=0.20)
        exp.reward = ConsolidatedExperience._compute_reward(exp)
        # gain_normalized = max(0, min(1, -0.20+0.5)) = 0.30
        # reward = 0.30*0.5 + 0*0.3 + 0.20*0.2 = 0.15 + 0 + 0.04 = 0.19
        assert exp.reward == 0.19

    # ── Tags ──

    def test_tags_positive_learning(self):
        """正向学习标签."""
        exp = ConsolidatedExperience(learning_gain=0.20, effectiveness_score=0.80, success=True)
        exp.tags = ConsolidatedExperience._generate_tags(exp)
        assert "positive_learning" in exp.tags
        assert "effective" in exp.tags
        assert "success" in exp.tags

    def test_tags_negative_learning(self):
        """负向学习标签."""
        exp = ConsolidatedExperience(learning_gain=-0.20, effectiveness_score=0.20, success=False)
        exp.tags = ConsolidatedExperience._generate_tags(exp)
        assert "positive_learning" not in exp.tags
        assert "effective" not in exp.tags
        assert "failure" in exp.tags

    def test_tags_gated(self):
        """门控标签."""
        exp = ConsolidatedExperience(gate_decision="pause")
        exp.tags = ConsolidatedExperience._generate_tags(exp)
        assert "gated" in exp.tags

    def test_tags_adjusted(self):
        """调整标签."""
        exp = ConsolidatedExperience(policy_adjustments=[{"target": "x"}])
        exp.tags = ConsolidatedExperience._generate_tags(exp)
        assert "adjusted" in exp.tags


# ═══════════════════════════════════════════════════════════════
# Test: ExtractionResult Model
# ═══════════════════════════════════════════════════════════════


class TestExtractionResultModel:
    """ExtractionResult 数据模型测试."""

    def test_default_construction(self):
        """默认构造."""
        result = ExtractionResult()
        assert result.extraction_id != ""
        assert result.total_extracted == 0
        assert result.significant_count == 0
        assert result.is_empty is True
        assert result.has_significant is False

    def test_from_experiences_empty(self):
        """空经验列表."""
        result = ExtractionResult.from_experiences([])
        assert result.total_extracted == 0
        assert result.is_empty is True
        assert result.has_significant is False
        assert result.avg_reward == 0.0
        assert result.avg_significance == 0.0

    def test_from_experiences_single(self, good_cycle_result):
        """单条经验."""
        exp = ConsolidatedExperience.from_cycle_result(good_cycle_result)
        result = ExtractionResult.from_experiences(
            [exp],
            source_cycle_id=exp.source_cycle_id,
            cycle_number=exp.cycle_number,
        )
        assert result.total_extracted == 1
        assert result.is_empty is False
        assert result.has_significant is True
        assert result.source_cycle_id == exp.source_cycle_id
        assert result.cycle_number == exp.cycle_number

    def test_from_experiences_multiple(self, good_cycle_result, bad_cycle_result):
        """多条经验."""
        exp1 = ConsolidatedExperience.from_cycle_result(good_cycle_result)
        exp2 = ConsolidatedExperience.from_cycle_result(bad_cycle_result)
        result = ExtractionResult.from_experiences([exp1, exp2])
        assert result.total_extracted == 2
        assert result.avg_reward > 0
        assert result.avg_significance > 0

    def test_category_distribution(self, good_cycle_result, bad_cycle_result):
        """类别分布."""
        exp1 = ConsolidatedExperience.from_cycle_result(good_cycle_result)  # ua
        exp2 = ConsolidatedExperience.from_cycle_result(bad_cycle_result)   # ua
        result = ExtractionResult.from_experiences([exp1, exp2])
        assert "ua" in result.category_distribution
        assert result.category_distribution["ua"] == 2

    def test_significant_experiences_property(self, good_cycle_result):
        """显著经验属性."""
        exp = ConsolidatedExperience.from_cycle_result(good_cycle_result)
        exp.is_significant = True
        result = ExtractionResult.from_experiences([exp])
        assert len(result.significant_experiences) == 1

    def test_non_significant_excluded(self):
        """非显著经验被排除."""
        exp = ConsolidatedExperience(is_significant=False)
        result = ExtractionResult.from_experiences([exp])
        assert result.has_significant is False
        assert len(result.significant_experiences) == 0

    def test_extraction_summary(self, good_cycle_result):
        """提取摘要."""
        exp = ConsolidatedExperience.from_cycle_result(good_cycle_result)
        result = ExtractionResult.from_experiences([exp])
        assert "Experience Extraction Summary" in result.extraction_summary
        assert "Total extracted" in result.extraction_summary
        assert "Significant" in result.extraction_summary

    def test_to_dict(self, good_cycle_result):
        """序列化."""
        exp = ConsolidatedExperience.from_cycle_result(good_cycle_result)
        result = ExtractionResult.from_experiences([exp])
        d = result.to_dict()
        assert d["total_extracted"] == 1
        assert isinstance(d["experiences"], list)
        assert len(d["experiences"]) == 1
        assert isinstance(d["category_distribution"], dict)


# ═══════════════════════════════════════════════════════════════
# Test: ExperienceExtractor Engine
# ═══════════════════════════════════════════════════════════════


class TestExperienceExtractorEngine:
    """ExperienceExtractor 引擎测试."""

    # ── Construction ──

    def test_default_construction(self):
        """默认构造."""
        ext = ExperienceExtractor()
        assert ext.significance_threshold == 0.3
        assert ext.extract_count == 0
        assert ext.total_extracted == 0
        assert ext.total_significant == 0

    def test_custom_threshold(self):
        """自定义阈值."""
        ext = ExperienceExtractor(significance_threshold=0.5)
        assert ext.significance_threshold == 0.5

    def test_threshold_clamped(self):
        """阈值边界."""
        ext_low = ExperienceExtractor(significance_threshold=-0.5)
        assert ext_low.significance_threshold == 0.0
        ext_high = ExperienceExtractor(significance_threshold=1.5)
        assert ext_high.significance_threshold == 1.0

    # ── Extract ──

    def test_extract_good_cycle(self, extractor, good_cycle_result):
        """提取好的周期."""
        result = extractor.extract(good_cycle_result)
        assert result.total_extracted == 1
        assert result.has_significant is True
        assert result.cycle_number == 1
        exp = result.experiences[0]
        assert exp.action_type == "increase_budget"
        assert exp.learning_gain == 0.15

    def test_extract_bad_cycle(self, extractor, bad_cycle_result):
        """提取坏的周期."""
        result = extractor.extract(bad_cycle_result)
        assert result.total_extracted == 1
        exp = result.experiences[0]
        assert exp.learning_gain == -0.15
        assert exp.is_effective is False

    def test_extract_gated_cycle(self, extractor, gated_cycle_result):
        """提取门控周期."""
        result = extractor.extract(gated_cycle_result)
        assert result.total_extracted == 1
        exp = result.experiences[0]
        assert exp.is_gated is True
        assert exp.gate_decision == "pause"

    def test_extract_minimal_cycle(self, extractor, minimal_cycle_result):
        """提取最小周期."""
        result = extractor.extract(minimal_cycle_result)
        assert result.total_extracted == 1
        exp = result.experiences[0]
        assert exp.cycle_number == 0
        assert exp.action_type == ""
        assert exp.success is False

    def test_extract_increments_counters(self, extractor, good_cycle_result):
        """提取增加计数器."""
        assert extractor.extract_count == 0
        extractor.extract(good_cycle_result)
        assert extractor.extract_count == 1
        assert extractor.total_extracted == 1
        assert extractor.total_significant == 1

    # ── Extract Batch ──

    def test_extract_batch(self, extractor, good_cycle_result, bad_cycle_result):
        """批量提取."""
        results = extractor.extract_batch([good_cycle_result, bad_cycle_result])
        assert len(results) == 2
        assert all(isinstance(r, ExtractionResult) for r in results)
        assert results[0].cycle_number == 1
        assert results[1].cycle_number == 2

    def test_extract_batch_empty(self, extractor):
        """空批量."""
        results = extractor.extract_batch([])
        assert results == []

    def test_extract_all_experiences(self, extractor, good_cycle_result, bad_cycle_result):
        """提取所有经验."""
        all_exp = extractor.extract_all_experiences([good_cycle_result, bad_cycle_result])
        assert len(all_exp) == 2

    def test_extract_significant_only(self, extractor, good_cycle_result, minimal_cycle_result):
        """仅提取显著经验."""
        significant = extractor.extract_significant_only([good_cycle_result, minimal_cycle_result])
        # minimal_cycle_result 可能不显著
        assert len(significant) >= 1
        assert all(e.is_significant for e in significant)

    # ── Significance Threshold ──

    def test_low_threshold_more_significant(self, low_threshold_extractor, minimal_cycle_result):
        """低阈值 → 更多显著."""
        result = low_threshold_extractor.extract(minimal_cycle_result)
        # 低阈值 (0.1) 时有些经验可能被标记为显著
        assert result.total_extracted == 1

    def test_high_threshold_fewer_significant(self, high_threshold_extractor, good_cycle_result):
        """高阈值 → 更少显著."""
        result = high_threshold_extractor.extract(good_cycle_result)
        # 高阈值 (0.9) 时即使好的经验也可能不显著
        assert result.total_extracted == 1

    # ── to_growth_experience ──

    def test_to_growth_experience(self, extractor, good_cycle_result):
        """转换为 GrowthExperience."""
        result = extractor.extract(good_cycle_result)
        exp = result.experiences[0]
        growth = extractor.to_growth_experience(exp)
        assert isinstance(growth, GrowthExperience)
        assert growth.action_type == "increase_budget"
        assert growth.reward == exp.reward
        assert growth.confidence == exp.confidence
        # 验证上下文
        assert growth.context.opportunity_type == exp.decision_type
        assert growth.context.action_type == exp.action_type
        # 验证结果
        assert growth.outcome.success is True
        assert growth.outcome.actual_reward == exp.reward
        # 验证元数据
        assert growth.metadata["source_cycle_id"] == exp.source_cycle_id
        assert growth.metadata["cycle_number"] == exp.cycle_number
        assert growth.metadata["learning_gain"] == exp.learning_gain
        assert growth.metadata["is_significant"] is True

    def test_to_growth_experience_tags(self, extractor, good_cycle_result):
        """GrowthExperience 包含标签."""
        result = extractor.extract(good_cycle_result)
        exp = result.experiences[0]
        growth = extractor.to_growth_experience(exp)
        assert len(growth.tags) > 0
        assert "positive_learning" in growth.tags

    def test_to_growth_experience_failure(self, extractor, bad_cycle_result):
        """失败经验的 GrowthExperience."""
        result = extractor.extract(bad_cycle_result)
        exp = result.experiences[0]
        growth = extractor.to_growth_experience(exp)
        assert growth.outcome.success is True  # execution was successful
        assert growth.outcome.outcome_level == ExperienceOutcomeLevel.FAILURE

    # ── extract_and_store ──

    def test_extract_and_store(self, extractor, good_cycle_result, experience_store):
        """提取并存储."""
        assert experience_store.count == 0
        result = extractor.extract_and_store(good_cycle_result, experience_store)
        assert result.total_extracted == 1
        # 显著经验应该被存储
        assert experience_store.count == 1

    def test_extract_and_store_non_significant(self, high_threshold_extractor, bad_cycle_result, experience_store):
        """非显著经验不存储."""
        assert experience_store.count == 0
        result = high_threshold_extractor.extract_and_store(bad_cycle_result, experience_store)
        assert result.total_extracted == 1
        # 非显著经验不被存储
        assert experience_store.count == 0

    def test_extract_batch_and_store(self, extractor, good_cycle_result, bad_cycle_result, experience_store):
        """批量提取并存储."""
        results = extractor.extract_batch_and_store(
            [good_cycle_result, bad_cycle_result],
            experience_store,
        )
        assert len(results) == 2

    # ── Statistics ──

    def test_get_stats(self, extractor, good_cycle_result):
        """获取统计."""
        extractor.extract(good_cycle_result)
        stats = extractor.get_stats()
        assert stats["extract_count"] == 1
        assert stats["total_extracted"] == 1
        assert "significant_ratio" in stats

    def test_reset_stats(self, extractor, good_cycle_result):
        """重置统计."""
        extractor.extract(good_cycle_result)
        extractor.reset_stats()
        assert extractor.extract_count == 0
        assert extractor.total_extracted == 0
        assert extractor.total_significant == 0

    # ── Edge Cases ──

    def test_extract_cycle_without_effectiveness(self, extractor):
        """无有效性评估的周期."""
        result = extractor.extract(
            OrchestrationCycleResult(
                cycle_number=4,
                state=CycleOrchestrationState.COMPLETED.value,
                policy_decision=LearningPolicyDecision(action="test_action"),
                execution_result=LearningExecutionResult(success=True),
            )
        )
        exp = result.experiences[0]
        assert exp.learning_gain == 0.0
        assert exp.effectiveness_score == 0.0

    def test_extract_cycle_without_policy_decision(self, extractor):
        """无策略决策的周期."""
        result = extractor.extract(
            OrchestrationCycleResult(
                cycle_number=5,
                state=CycleOrchestrationState.COMPLETED.value,
                execution_result=LearningExecutionResult(success=True, action="executed_action"),
            )
        )
        exp = result.experiences[0]
        assert exp.action_type == "executed_action"

    def test_extract_cycle_without_gate_result(self, extractor):
        """无门控结果的周期."""
        result = extractor.extract(
            OrchestrationCycleResult(
                cycle_number=6,
                state=CycleOrchestrationState.COMPLETED.value,
                policy_decision=LearningPolicyDecision(action="test_action"),
            )
        )
        exp = result.experiences[0]
        assert exp.gate_decision == ""
        assert exp.feedback_classification == ""

    def test_to_growth_experience_minimal(self, extractor, minimal_cycle_result):
        """最小编排周期转 GrowthExperience."""
        result = extractor.extract(minimal_cycle_result)
        exp = result.experiences[0]
        growth = extractor.to_growth_experience(exp)
        assert isinstance(growth, GrowthExperience)
        assert growth.action_type == ""

    # ── Multiple Cycles ──

    def test_multiple_cycles_same_extractor(self, extractor, good_cycle_result, bad_cycle_result, gated_cycle_result):
        """同一提取器多次提取."""
        results = extractor.extract_batch([good_cycle_result, bad_cycle_result, gated_cycle_result])
        assert len(results) == 3
        assert extractor.extract_count == 3
        assert extractor.total_extracted == 3