"""E17.9 Pattern Reinforcement — 测试用例.

Day 7.9 Step 3:
  覆盖 Pattern Reinforcement 层的:
    - ReinforcementAction 枚举
    - PatternReinforcementResult 模型 (properties, serialization)
    - ReinforcementBatchResult 模型 (from_results, aggregation, properties, serialization)
    - PatternReinforcementBridge 引擎 (determine_action, reinforce_single, reinforce batch)
    - Pattern Store 交互 (find_or_create, boost, decay, suppress, maintain)
    - Edge cases (empty, single, stats, custom thresholds)
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.pattern_reinforcement_models import (
    PatternReinforcementResult,
    ReinforcementAction,
    ReinforcementBatchResult,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.knowledge_compression_models import (
    CompressedKnowledge,
    CompressionDimension,
    CompressionResult,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.pattern_reinforcement_bridge import (
    PatternReinforcementBridge,
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
    PatternQuality,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def bridge() -> PatternReinforcementBridge:
    """默认桥接器."""
    return PatternReinforcementBridge()


@pytest.fixture
def pattern_store() -> PatternStore:
    """空模式存储."""
    return PatternStore()


@pytest.fixture
def existing_pattern() -> PatternMemory:
    """已有模式 (increase_budget, 高成功率)."""
    condition = PatternCondition(
        opportunity_type="increase_budget",
        action_type="increase_budget",
    )
    action = PatternAction(
        action_type="increase_budget",
        expected_impact="amplify",
    )
    perf = PatternPerformance(
        samples=10,
        success_count=8,
        success_rate=0.80,
        avg_reward=0.70,
        avg_confidence=0.85,
        quality=PatternQuality.RELIABLE,
    )
    pattern = PatternMemory(
        dimension=PatternMiningDimension.OPPORTUNITY_ACTION,
        condition=condition,
        action=action,
        performance=perf,
        tags=["positive", "ua"],
    )
    pattern.compute_score()
    return pattern


@pytest.fixture
def weak_pattern() -> PatternMemory:
    """弱模式 (reduce_budget, 中等成功率 — 可被 get_best_pattern 找到)."""
    condition = PatternCondition(
        opportunity_type="reduce_budget",
        action_type="reduce_budget",
    )
    action = PatternAction(
        action_type="reduce_budget",
        expected_impact="suppress",
    )
    perf = PatternPerformance(
        samples=5,
        success_count=3,
        success_rate=0.60,
        avg_reward=0.40,
        avg_confidence=0.50,
        quality=PatternQuality.EMERGING,
    )
    pattern = PatternMemory(
        dimension=PatternMiningDimension.OPPORTUNITY_ACTION,
        condition=condition,
        action=action,
        performance=perf,
        tags=["negative", "ua"],
    )
    pattern.compute_score()
    return pattern


@pytest.fixture
def boost_knowledge() -> CompressedKnowledge:
    """BOOST 触发知识 (正向学习 + 高成功率)."""
    return CompressedKnowledge(
        action_type="increase_budget",
        category="ua",
        experience_count=8,
        avg_reward=0.75,
        avg_confidence=0.85,
        avg_learning_gain=0.15,
        avg_significance=0.60,
        success_rate=0.85,
        dominant_feedback="good_learning",
        recommended_action="amplify_increase_budget",
        is_reliable=True,
        reliability_score=0.80,
        dimension_key="increase_budget",
        source_experience_ids=["exp-001", "exp-002"],
    )


@pytest.fixture
def decay_knowledge() -> CompressedKnowledge:
    """DECAY 触发知识 (负向学习)."""
    return CompressedKnowledge(
        action_type="reduce_budget",
        category="ua",
        experience_count=5,
        avg_reward=0.25,
        avg_confidence=0.50,
        avg_learning_gain=-0.12,
        avg_significance=0.30,
        success_rate=0.40,
        dominant_feedback="bad_learning",
        recommended_action="suppress_reduce_budget",
        is_reliable=True,
        reliability_score=0.45,
        dimension_key="reduce_budget",
        source_experience_ids=["exp-003", "exp-004"],
    )


@pytest.fixture
def suppress_knowledge() -> CompressedKnowledge:
    """SUPPRESS 触发知识 (负向学习 + 极低成功率)."""
    return CompressedKnowledge(
        action_type="random_action",
        category="creative",
        experience_count=10,
        avg_reward=0.05,
        avg_confidence=0.30,
        avg_learning_gain=-0.20,
        avg_significance=0.15,
        success_rate=0.10,
        dominant_feedback="bad_learning",
        recommended_action="suppress_random_action",
        is_reliable=True,
        reliability_score=0.20,
        dimension_key="random_action",
        source_experience_ids=["exp-005", "exp-006"],
    )


@pytest.fixture
def maintain_knowledge() -> CompressedKnowledge:
    """MAINTAIN 触发知识 (边界情况)."""
    return CompressedKnowledge(
        action_type="adjust_bid",
        category="ua",
        experience_count=4,
        avg_reward=0.50,
        avg_confidence=0.60,
        avg_learning_gain=0.02,
        avg_significance=0.40,
        success_rate=0.55,
        dominant_feedback="neutral",
        recommended_action="maintain_adjust_bid",
        is_reliable=True,
        reliability_score=0.55,
        dimension_key="adjust_bid",
        source_experience_ids=["exp-007"],
    )


@pytest.fixture
def compression_result_with_knowledge(
    boost_knowledge, decay_knowledge, suppress_knowledge, maintain_knowledge,
) -> CompressionResult:
    """包含多种知识单元的压缩结果."""
    return CompressionResult.from_knowledge_units(
        [boost_knowledge, decay_knowledge, suppress_knowledge, maintain_knowledge],
        total_experiences=27,
        dimensions_used=["action_type"],
    )


@pytest.fixture
def populated_store(
    existing_pattern, weak_pattern,
) -> PatternStore:
    """已有模式的存储."""
    store = PatternStore()
    store.store(existing_pattern)
    store.store(weak_pattern)
    return store


# ═══════════════════════════════════════════════════════════════
# Test: ReinforcementAction
# ═══════════════════════════════════════════════════════════════


class TestReinforcementAction:
    """ReinforcementAction 枚举测试."""

    def test_all_actions_exist(self):
        """所有动作存在."""
        assert ReinforcementAction.BOOST.value == "boost"
        assert ReinforcementAction.DECAY.value == "decay"
        assert ReinforcementAction.MAINTAIN.value == "maintain"
        assert ReinforcementAction.SUPPRESS.value == "suppress"

    def test_action_is_string(self):
        """动作值为字符串."""
        assert isinstance(ReinforcementAction.BOOST.value, str)
        assert isinstance(ReinforcementAction.DECAY.value, str)

    def test_action_count(self):
        """动作数量."""
        actions = list(ReinforcementAction)
        assert len(actions) == 4


# ═══════════════════════════════════════════════════════════════
# Test: PatternReinforcementResult Model
# ═══════════════════════════════════════════════════════════════


class TestPatternReinforcementResultModel:
    """PatternReinforcementResult 数据模型测试."""

    def test_default_construction(self):
        """默认构造."""
        r = PatternReinforcementResult()
        assert r.result_id != ""
        assert r.pattern_id == ""
        assert r.action == "maintain"
        assert r.confidence_before == 0.0
        assert r.confidence_delta == 0.0
        assert r.was_changed is False
        assert r.was_boosted is False
        assert r.was_decayed is False

    def test_boost_result(self):
        """BOOST 结果."""
        r = PatternReinforcementResult(
            pattern_id="p-001",
            action=ReinforcementAction.BOOST.value,
            confidence_before=0.70,
            confidence_after=0.80,
            confidence_delta=0.10,
        )
        assert r.was_changed is True
        assert r.was_boosted is True
        assert r.was_decayed is False

    def test_decay_result(self):
        """DECAY 结果."""
        r = PatternReinforcementResult(
            action=ReinforcementAction.DECAY.value,
            confidence_before=0.50,
            confidence_after=0.42,
            confidence_delta=-0.08,
        )
        assert r.was_changed is True
        assert r.was_boosted is False
        assert r.was_decayed is True

    def test_suppress_result(self):
        """SUPPRESS 结果."""
        r = PatternReinforcementResult(
            action=ReinforcementAction.SUPPRESS.value,
            confidence_before=0.30,
            confidence_after=0.15,
            confidence_delta=-0.15,
        )
        assert r.was_changed is True
        assert r.was_boosted is False
        assert r.was_decayed is True

    def test_maintain_is_not_changed(self):
        """MAINTAIN 不算变化."""
        r = PatternReinforcementResult(
            action=ReinforcementAction.MAINTAIN.value,
        )
        assert r.was_changed is False
        assert r.was_boosted is False
        assert r.was_decayed is False

    def test_to_dict(self):
        """序列化."""
        r = PatternReinforcementResult(
            pattern_id="p-001",
            knowledge_id="k-001",
            action=ReinforcementAction.BOOST.value,
            confidence_before=0.70,
            confidence_after=0.80,
            confidence_delta=0.10,
            score_before=0.30,
            score_after=0.35,
            score_delta=0.05,
            evidence_count=5,
            reason="Boosted: good performance",
        )
        d = r.to_dict()
        assert d["result_id"] == r.result_id
        assert d["pattern_id"] == "p-001"
        assert d["knowledge_id"] == "k-001"
        assert d["action"] == "boost"
        assert d["confidence_before"] == 0.70
        assert d["confidence_after"] == 0.80
        assert d["confidence_delta"] == 0.10
        assert d["score_before"] == 0.30
        assert d["score_after"] == 0.35
        assert d["score_delta"] == 0.05
        assert d["evidence_count"] == 5
        assert d["reason"] == "Boosted: good performance"

    def test_score_fields(self):
        """评分字段."""
        r = PatternReinforcementResult(
            score_before=0.50,
            score_after=0.65,
            score_delta=0.15,
        )
        assert r.score_before == 0.50
        assert r.score_after == 0.65
        assert r.score_delta == 0.15

    def test_evidence_count(self):
        """证据数量."""
        r = PatternReinforcementResult(evidence_count=10)
        assert r.evidence_count == 10

    def test_metadata(self):
        """元数据."""
        r = PatternReinforcementResult(metadata={"source": "test"})
        assert r.metadata["source"] == "test"
        assert r.to_dict()["metadata"] == {"source": "test"}


# ═══════════════════════════════════════════════════════════════
# Test: ReinforcementBatchResult Model
# ═══════════════════════════════════════════════════════════════


class TestReinforcementBatchResultModel:
    """ReinforcementBatchResult 数据模型测试."""

    def test_default_construction(self):
        """默认构造."""
        b = ReinforcementBatchResult()
        assert b.batch_id != ""
        assert b.total_processed == 0
        assert b.is_empty is True
        assert b.has_changes is False

    def test_from_results_empty(self):
        """空结果列表."""
        b = ReinforcementBatchResult.from_results([])
        assert b.total_processed == 0
        assert b.is_empty is True
        assert b.has_changes is False

    def test_from_results_single_boost(self):
        """单条 BOOST 结果."""
        r = PatternReinforcementResult(
            pattern_id="p-001",
            action=ReinforcementAction.BOOST.value,
            confidence_before=0.70,
            confidence_after=0.80,
            confidence_delta=0.10,
        )
        b = ReinforcementBatchResult.from_results([r])
        assert b.total_processed == 1
        assert b.boosted_count == 1
        assert b.decayed_count == 0
        assert b.maintained_count == 0
        assert b.suppressed_count == 0
        assert b.total_confidence_gain == 0.10
        assert b.avg_confidence_gain == 0.10
        assert b.is_empty is False
        assert b.has_changes is True

    def test_from_results_mixed(self):
        """混合结果."""
        results = [
            PatternReinforcementResult(
                action=ReinforcementAction.BOOST.value,
                confidence_delta=0.10,
            ),
            PatternReinforcementResult(
                action=ReinforcementAction.BOOST.value,
                confidence_delta=0.08,
            ),
            PatternReinforcementResult(
                action=ReinforcementAction.DECAY.value,
                confidence_delta=-0.08,
            ),
            PatternReinforcementResult(
                action=ReinforcementAction.SUPPRESS.value,
                confidence_delta=-0.15,
            ),
            PatternReinforcementResult(
                action=ReinforcementAction.MAINTAIN.value,
                confidence_delta=0.0,
            ),
        ]
        b = ReinforcementBatchResult.from_results(results)
        assert b.total_processed == 5
        assert b.boosted_count == 2
        assert b.decayed_count == 2  # DECAY + SUPPRESS
        assert b.maintained_count == 1
        assert b.suppressed_count == 1
        # total_gain = 0.10 + 0.08 + (-0.08) + (-0.15) + 0.0 = -0.05
        assert b.total_confidence_gain == -0.05
        assert b.avg_confidence_gain == -0.01
        assert b.has_changes is True

    def test_from_results_all_maintain(self):
        """全部 MAINTAIN."""
        results = [
            PatternReinforcementResult(action=ReinforcementAction.MAINTAIN.value)
            for _ in range(3)
        ]
        b = ReinforcementBatchResult.from_results(results)
        assert b.total_processed == 3
        assert b.boosted_count == 0
        assert b.decayed_count == 0
        assert b.maintained_count == 3
        assert b.has_changes is False

    def test_summary_content(self):
        """摘要内容."""
        r = PatternReinforcementResult(
            action=ReinforcementAction.BOOST.value,
            confidence_delta=0.10,
        )
        b = ReinforcementBatchResult.from_results([r])
        assert "Pattern Reinforcement Summary" in b.reinforcement_summary
        assert "Total processed" in b.reinforcement_summary
        assert "Boosted" in b.reinforcement_summary
        assert "Total confidence gain" in b.reinforcement_summary

    def test_to_dict(self):
        """序列化."""
        r = PatternReinforcementResult(
            action=ReinforcementAction.BOOST.value,
            confidence_delta=0.10,
        )
        b = ReinforcementBatchResult.from_results([r])
        d = b.to_dict()
        assert d["batch_id"] == b.batch_id
        assert d["total_processed"] == 1
        assert d["boosted_count"] == 1
        assert isinstance(d["results"], list)
        assert len(d["results"]) == 1

    def test_to_dict_empty(self):
        """空批量序列化."""
        b = ReinforcementBatchResult.from_results([])
        d = b.to_dict()
        assert d["total_processed"] == 0
        assert d["results"] == []


# ═══════════════════════════════════════════════════════════════
# Test: PatternReinforcementBridge — Construction
# ═══════════════════════════════════════════════════════════════


class TestPatternReinforcementBridgeConstruction:
    """PatternReinforcementBridge 构造测试."""

    def test_default_construction(self):
        """默认构造."""
        b = PatternReinforcementBridge()
        assert b.reinforce_count == 0
        assert b.total_boosted == 0
        assert b.total_decayed == 0

    def test_custom_thresholds(self):
        """自定义阈值."""
        b = PatternReinforcementBridge(
            boost_threshold=0.10,
            decay_threshold=-0.10,
            suppress_rate=0.20,
            boost_rate=0.80,
        )
        assert b._boost_threshold == 0.10
        assert b._decay_threshold == -0.10
        assert b._suppress_rate == 0.20
        assert b._boost_rate == 0.80

    def test_get_stats(self):
        """获取统计."""
        b = PatternReinforcementBridge()
        stats = b.get_stats()
        assert stats["reinforce_count"] == 0
        assert stats["total_boosted"] == 0
        assert stats["total_decayed"] == 0
        assert "boost_threshold" in stats
        assert "decay_threshold" in stats

    def test_reset_stats(self):
        """重置统计."""
        b = PatternReinforcementBridge()
        b._reinforce_count = 5
        b._total_boosted = 3
        b._total_decayed = 2
        b.reset_stats()
        assert b.reinforce_count == 0
        assert b.total_boosted == 0
        assert b.total_decayed == 0


# ═══════════════════════════════════════════════════════════════
# Test: PatternReinforcementBridge — Action Determination
# ═══════════════════════════════════════════════════════════════


class TestActionDetermination:
    """强化动作决策测试."""

    def test_determine_boost(self, bridge, boost_knowledge):
        """决定 BOOST."""
        action = bridge._determine_action(boost_knowledge)
        assert action == ReinforcementAction.BOOST

    def test_determine_decay(self, bridge, decay_knowledge):
        """决定 DECAY."""
        action = bridge._determine_action(decay_knowledge)
        assert action == ReinforcementAction.DECAY

    def test_determine_suppress(self, bridge, suppress_knowledge):
        """决定 SUPPRESS."""
        action = bridge._determine_action(suppress_knowledge)
        assert action == ReinforcementAction.SUPPRESS

    def test_determine_maintain(self, bridge, maintain_knowledge):
        """决定 MAINTAIN."""
        action = bridge._determine_action(maintain_knowledge)
        assert action == ReinforcementAction.MAINTAIN

    def test_determine_boost_high_gain_high_rate(self, bridge):
        """高增益 + 高成功率 → BOOST."""
        k = CompressedKnowledge(
            avg_learning_gain=0.20,
            success_rate=0.85,
        )
        assert bridge._determine_action(k) == ReinforcementAction.BOOST

    def test_determine_maintain_high_gain_low_rate(self, bridge):
        """高增益 + 低成功率 → MAINTAIN."""
        k = CompressedKnowledge(
            avg_learning_gain=0.20,
            success_rate=0.40,
        )
        assert bridge._determine_action(k) == ReinforcementAction.MAINTAIN

    def test_determine_decay_low_gain_medium_rate(self, bridge):
        """低增益 + 中等成功率 → DECAY."""
        k = CompressedKnowledge(
            avg_learning_gain=-0.10,
            success_rate=0.50,
        )
        assert bridge._determine_action(k) == ReinforcementAction.DECAY

    def test_determine_suppress_low_gain_low_rate(self, bridge):
        """低增益 + 低成功率 → SUPPRESS."""
        k = CompressedKnowledge(
            avg_learning_gain=-0.15,
            success_rate=0.15,
        )
        assert bridge._determine_action(k) == ReinforcementAction.SUPPRESS

    def test_determine_decay_low_rate_no_gain(self, bridge):
        """低成功率 + 无增益 → DECAY."""
        k = CompressedKnowledge(
            avg_learning_gain=0.0,
            success_rate=0.20,
        )
        assert bridge._determine_action(k) == ReinforcementAction.DECAY

    def test_determine_boundary_boost(self, bridge):
        """BOOST 边界值."""
        k = CompressedKnowledge(
            avg_learning_gain=0.051,  # just above threshold
            success_rate=0.70,        # at threshold
        )
        assert bridge._determine_action(k) == ReinforcementAction.BOOST

    def test_determine_boundary_decay(self, bridge):
        """DECAY 边界值."""
        k = CompressedKnowledge(
            avg_learning_gain=-0.051,  # just below threshold
            success_rate=0.50,
        )
        assert bridge._determine_action(k) == ReinforcementAction.DECAY

    def test_determine_boundary_maintain(self, bridge):
        """MAINTAIN 边界值 (正好在阈值)."""
        k = CompressedKnowledge(
            avg_learning_gain=0.05,  # at threshold
            success_rate=0.69,       # just below boost threshold
        )
        assert bridge._determine_action(k) == ReinforcementAction.MAINTAIN


# ═══════════════════════════════════════════════════════════════
# Test: PatternReinforcementBridge — Reinforce Single
# ═══════════════════════════════════════════════════════════════


class TestReinforceSingle:
    """单模式强化测试."""

    def test_reinforce_single_boost(
        self, bridge, boost_knowledge, pattern_store, existing_pattern,
    ):
        """强化单个模式 — BOOST."""
        pattern_store.store(existing_pattern)
        result = bridge.reinforce_single(boost_knowledge, pattern_store)

        assert result.action == "boost"
        assert result.was_boosted is True
        # confidence_delta = BOOST_CONFIDENCE_DELTA (0.10) + base confidence change
        assert result.confidence_delta > 0
        assert result.confidence_after == round(result.confidence_before + result.confidence_delta, 4)
        assert result.evidence_count == 8
        assert "Boosted" in result.reason

    def test_reinforce_single_decay(
        self, bridge, decay_knowledge, pattern_store, weak_pattern,
    ):
        """强化单个模式 — DECAY."""
        pattern_store.store(weak_pattern)
        result = bridge.reinforce_single(decay_knowledge, pattern_store)

        assert result.action == "decay"
        assert result.was_decayed is True
        # confidence_delta includes both base confidence change and DECAY delta
        assert result.confidence_delta < 0
        assert result.confidence_after == round(result.confidence_before + result.confidence_delta, 4)
        assert "Decayed" in result.reason

    def test_reinforce_single_suppress(
        self, bridge, suppress_knowledge, pattern_store,
    ):
        """强化单个模式 — SUPPRESS."""
        # 创建可被 get_best_pattern 找到的模式
        pattern = PatternMemory(
            dimension=PatternMiningDimension.OPPORTUNITY_ACTION,
            condition=PatternCondition(
                opportunity_type="random_action",
                action_type="random_action",
            ),
            action=PatternAction(
                action_type="random_action",
                expected_impact="suppress",
            ),
            performance=PatternPerformance(
                samples=5,
                success_count=3,
                success_rate=0.60,
                avg_reward=0.40,
                avg_confidence=0.50,
                quality=PatternQuality.EMERGING,
            ),
        )
        pattern.compute_score()
        pattern_store.store(pattern)
        result = bridge.reinforce_single(suppress_knowledge, pattern_store)

        assert result.action == "suppress"
        assert result.was_decayed is True
        assert result.confidence_delta < 0
        assert result.confidence_after == round(result.confidence_before + result.confidence_delta, 4)
        assert "Suppressed" in result.reason

    def test_reinforce_single_maintain(
        self, bridge, maintain_knowledge, pattern_store,
    ):
        """强化单个模式 — MAINTAIN."""
        result = bridge.reinforce_single(maintain_knowledge, pattern_store)

        assert result.action == "maintain"
        assert result.was_changed is False
        assert "Maintained" in result.reason

    def test_reinforce_single_creates_new_pattern(
        self, bridge, boost_knowledge, pattern_store,
    ):
        """强化单个模式 — 创建新模式."""
        result = bridge.reinforce_single(boost_knowledge, pattern_store)

        assert result.pattern_id != ""
        assert result.action == "boost"
        # 新模式置信度从 knowledge.reliability_score 开始
        assert result.confidence_before == boost_knowledge.reliability_score

    def test_reinforce_single_score_changes(
        self, bridge, boost_knowledge, pattern_store, existing_pattern,
    ):
        """评分变化."""
        pattern_store.store(existing_pattern)
        result = bridge.reinforce_single(boost_knowledge, pattern_store)

        assert result.score_before > 0
        assert result.score_after != result.score_before
        assert result.score_delta != 0.0

    def test_reinforce_single_confidence_capped(
        self, bridge, pattern_store,
    ):
        """置信度上限 1.0."""
        pattern = PatternMemory(
            dimension=PatternMiningDimension.OPPORTUNITY_ACTION,
            condition=PatternCondition(
                opportunity_type="already_high",
                action_type="already_high",
            ),
            action=PatternAction(
                action_type="already_high",
                expected_impact="amplify",
            ),
            performance=PatternPerformance(
                samples=10,
                success_count=9,
                success_rate=0.90,
                avg_reward=0.80,
                avg_confidence=0.90,
            ),
        )
        pattern.compute_score()
        pattern_store.store(pattern)

        k = CompressedKnowledge(
            action_type="already_high",
            experience_count=10,
            avg_learning_gain=0.20,
            success_rate=0.90,
            avg_reward=0.80,
            avg_confidence=0.90,
            is_reliable=True,
            reliability_score=0.85,
            dimension_key="already_high",
        )
        result = bridge.reinforce_single(k, pattern_store)
        assert result.confidence_after <= 1.0

    def test_reinforce_single_confidence_floor(
        self, bridge, suppress_knowledge, pattern_store,
    ):
        """置信度下限 0.05."""
        # 针对 random_action 的极低模式
        pattern = PatternMemory(
            dimension=PatternMiningDimension.OPPORTUNITY_ACTION,
            condition=PatternCondition(
                opportunity_type="random_action",
                action_type="random_action",
            ),
            action=PatternAction(
                action_type="random_action",
                expected_impact="suppress",
            ),
            performance=PatternPerformance(
                samples=3,
                success_count=0,
                success_rate=0.10,
                avg_reward=0.05,
                avg_confidence=0.20,
            ),
        )
        pattern.compute_score()
        pattern_store.store(pattern)

        result = bridge.reinforce_single(suppress_knowledge, pattern_store)
        assert result.confidence_after >= 0.05


# ═══════════════════════════════════════════════════════════════
# Test: PatternReinforcementBridge — Reinforce Batch
# ═══════════════════════════════════════════════════════════════


class TestReinforceBatch:
    """批量强化测试."""

    def test_reinforce_batch(
        self, bridge, compression_result_with_knowledge, pattern_store,
        existing_pattern, weak_pattern,
    ):
        """批量强化."""
        pattern_store.store(existing_pattern)
        pattern_store.store(weak_pattern)

        batch = bridge.reinforce(compression_result_with_knowledge, pattern_store)

        assert batch.total_processed >= 1
        assert batch.batch_id != ""
        assert batch.has_changes is True
        assert batch.boosted_count >= 1

    def test_reinforce_batch_empty_compression(self, bridge, pattern_store):
        """空压缩结果."""
        cr = CompressionResult.from_knowledge_units([])
        batch = bridge.reinforce(cr, pattern_store)
        assert batch.total_processed == 0
        assert batch.is_empty is True

    def test_reinforce_batch_increments_count(
        self, bridge, boost_knowledge, pattern_store,
    ):
        """批量强化增加计数."""
        cr = CompressionResult.from_knowledge_units([boost_knowledge])
        bridge.reinforce(cr, pattern_store)
        assert bridge.reinforce_count == 1

    def test_reinforce_batch_tracks_boosted(
        self, bridge, boost_knowledge, pattern_store,
    ):
        """批量强化跟踪 BOOST 计数."""
        cr = CompressionResult.from_knowledge_units([boost_knowledge])
        bridge.reinforce(cr, pattern_store)
        assert bridge.total_boosted == 1

    def test_reinforce_batch_tracks_decayed(
        self, bridge, decay_knowledge, pattern_store,
    ):
        """批量强化跟踪 DECAY 计数."""
        cr = CompressionResult.from_knowledge_units([decay_knowledge])
        bridge.reinforce(cr, pattern_store)
        assert bridge.total_decayed == 1

    def test_reinforce_from_extraction(
        self, bridge, compression_result_with_knowledge, pattern_store,
    ):
        """全链路强化."""
        batch = bridge.reinforce_from_extraction(
            compression_result_with_knowledge, pattern_store,
        )
        assert batch.total_processed >= 1

    def test_reinforce_from_extraction_with_experience_store(
        self, bridge, compression_result_with_knowledge, pattern_store,
    ):
        """全链路强化 (带 experience_store)."""
        batch = bridge.reinforce_from_extraction(
            compression_result_with_knowledge, pattern_store,
            experience_store=None,
        )
        assert batch.total_processed >= 1

    def test_reinforce_multiple_calls_accumulate(self, bridge, boost_knowledge, pattern_store):
        """多次调用累积计数."""
        cr = CompressionResult.from_knowledge_units([boost_knowledge])
        bridge.reinforce(cr, pattern_store)
        bridge.reinforce(cr, pattern_store)
        assert bridge.reinforce_count == 2
        assert bridge.total_boosted == 2


# ═══════════════════════════════════════════════════════════════
# Test: PatternReinforcementBridge — Pattern Store Interaction
# ═══════════════════════════════════════════════════════════════


class TestPatternStoreInteraction:
    """PatternStore 交互测试."""

    def test_find_or_create_returns_existing(
        self, bridge, boost_knowledge, populated_store,
    ):
        """查找已有模式."""
        pattern = bridge._find_or_create_pattern(boost_knowledge, populated_store)
        assert pattern.pattern_id != ""
        assert pattern.condition.opportunity_type == "increase_budget"

    def test_find_or_create_creates_new(
        self, bridge, suppress_knowledge, pattern_store,
    ):
        """创建新模式."""
        pattern = bridge._find_or_create_pattern(suppress_knowledge, pattern_store)
        assert pattern.pattern_id != ""
        assert pattern.condition.action_type == "random_action"
        assert pattern.confidence == suppress_knowledge.reliability_score

    def test_new_pattern_has_correct_performance(
        self, bridge, boost_knowledge, pattern_store,
    ):
        """新模式性能正确."""
        pattern = bridge._find_or_create_pattern(boost_knowledge, pattern_store)
        assert pattern.performance.samples == boost_knowledge.experience_count
        assert pattern.performance.success_rate == boost_knowledge.success_rate
        assert pattern.performance.avg_reward == boost_knowledge.avg_reward

    def test_new_pattern_has_tags(self, bridge, boost_knowledge, pattern_store):
        """新模式有标签."""
        pattern = bridge._find_or_create_pattern(boost_knowledge, pattern_store)
        assert "positive" in pattern.tags
        assert "ua" in pattern.tags

    def test_boost_updates_pattern_metadata(
        self, bridge, boost_knowledge, pattern_store, existing_pattern,
    ):
        """BOOST 更新元数据."""
        pattern_store.store(existing_pattern)
        bridge.reinforce_single(boost_knowledge, pattern_store)

        # 从 store 获取更新后的模式
        updated = pattern_store.get_best_pattern(
            condition=PatternCondition(
                opportunity_type="increase_budget",
                action_type="increase_budget",
            ),
            opportunity_type="increase_budget",
            action_type="increase_budget",
        )
        assert updated is not None
        assert "last_boosted" in updated.metadata
        assert updated.metadata.get("boost_count", 0) >= 1

    def test_decay_updates_pattern_metadata(
        self, bridge, decay_knowledge, pattern_store, weak_pattern,
    ):
        """DECAY 更新元数据."""
        pattern_store.store(weak_pattern)
        bridge.reinforce_single(decay_knowledge, pattern_store)

        updated = pattern_store.get_best_pattern(
            condition=PatternCondition(
                opportunity_type="reduce_budget",
                action_type="reduce_budget",
            ),
            opportunity_type="reduce_budget",
            action_type="reduce_budget",
        )
        assert updated is not None
        assert "last_decayed" in updated.metadata
        assert updated.metadata.get("decay_count", 0) >= 1

    def test_suppress_updates_pattern_metadata(
        self, bridge, suppress_knowledge, pattern_store,
    ):
        """SUPPRESS 更新元数据."""
        pattern = PatternMemory(
            dimension=PatternMiningDimension.OPPORTUNITY_ACTION,
            condition=PatternCondition(
                opportunity_type="random_action",
                action_type="random_action",
            ),
            action=PatternAction(
                action_type="random_action",
                expected_impact="suppress",
            ),
            performance=PatternPerformance(
                samples=5, success_count=3, success_rate=0.60,
                avg_reward=0.40, avg_confidence=0.50,
            ),
        )
        pattern.compute_score()
        pattern_store.store(pattern)
        bridge.reinforce_single(suppress_knowledge, pattern_store)

        updated = pattern_store.get_best_pattern(
            condition=PatternCondition(
                opportunity_type="random_action",
                action_type="random_action",
            ),
            opportunity_type="random_action",
            action_type="random_action",
            actionable_only=False,
        )
        assert updated is not None
        assert "last_suppressed" in updated.metadata
        assert updated.metadata.get("suppress_count", 0) >= 1


# ═══════════════════════════════════════════════════════════════
# Test: PatternReinforcementBridge — Edge Cases
# ═══════════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界情况测试."""

    def test_reinforce_with_unreliable_knowledge(self, bridge, pattern_store):
        """不可靠知识不处理."""
        k = CompressedKnowledge(
            is_reliable=False,
            action_type="test",
            dimension_key="test",
        )
        cr = CompressionResult.from_knowledge_units([k])
        batch = bridge.reinforce(cr, pattern_store)
        assert batch.total_processed == 0

    def test_reinforce_single_unreliable(self, bridge, pattern_store):
        """不可靠知识的 reinforce_single 仍可执行."""
        k = CompressedKnowledge(
            is_reliable=False,
            action_type="test",
            dimension_key="test",
            avg_learning_gain=0.0,
            success_rate=0.50,
            reliability_score=0.30,
        )
        result = bridge.reinforce_single(k, pattern_store)
        assert result.pattern_id != ""
        assert result.action is not None

    def test_build_reason_boost(self, bridge, boost_knowledge):
        """构建 BOOST 原因."""
        reason = bridge._build_reason(boost_knowledge, ReinforcementAction.BOOST)
        assert "Boosted" in reason
        assert "avg_gain" in reason
        assert "success_rate" in reason

    def test_build_reason_decay(self, bridge, decay_knowledge):
        """构建 DECAY 原因."""
        reason = bridge._build_reason(decay_knowledge, ReinforcementAction.DECAY)
        assert "Decayed" in reason
        assert "avg_gain" in reason

    def test_build_reason_suppress(self, bridge, suppress_knowledge):
        """构建 SUPPRESS 原因."""
        reason = bridge._build_reason(suppress_knowledge, ReinforcementAction.SUPPRESS)
        assert "Suppressed" in reason
        assert "low" in reason.lower()

    def test_build_reason_maintain(self, bridge, maintain_knowledge):
        """构建 MAINTAIN 原因."""
        reason = bridge._build_reason(maintain_knowledge, ReinforcementAction.MAINTAIN)
        assert "Maintained" in reason
        assert "avg_gain" in reason

    def test_generate_tags_positive(self, bridge, boost_knowledge):
        """正向标签."""
        tags = bridge._generate_tags(boost_knowledge)
        assert "positive" in tags
        assert "ua" in tags
        assert "good_learning" in tags

    def test_generate_tags_negative(self, bridge, decay_knowledge):
        """负向标签."""
        tags = bridge._generate_tags(decay_knowledge)
        assert "negative" in tags
        assert "bad_learning" in tags

    def test_generate_tags_no_category(self, bridge, boost_knowledge):
        """无类别标签."""
        k = CompressedKnowledge(
            category="",
            dominant_feedback="",
            avg_learning_gain=0.10,
        )
        tags = bridge._generate_tags(k)
        assert "positive" in tags
        # 无空字符串标签
        assert "" not in tags

    def test_boost_performance_update(self, bridge, boost_knowledge, pattern_store):
        """BOOST 更新性能指标."""
        result = bridge.reinforce_single(boost_knowledge, pattern_store)
        # 从 store 获取更新后的模式
        updated = pattern_store.get_best_pattern(
            condition=PatternCondition(
                opportunity_type="increase_budget",
                action_type="increase_budget",
            ),
            opportunity_type="increase_budget",
            action_type="increase_budget",
            actionable_only=False,
        )
        assert updated is not None
        # 性能样本数应增加
        assert updated.performance.samples >= boost_knowledge.experience_count

    def test_decay_performance_update(self, bridge, decay_knowledge, pattern_store):
        """DECAY 更新性能指标."""
        result = bridge.reinforce_single(decay_knowledge, pattern_store)
        updated = pattern_store.get_best_pattern(
            condition=PatternCondition(
                opportunity_type="reduce_budget",
                action_type="reduce_budget",
            ),
            opportunity_type="reduce_budget",
            action_type="reduce_budget",
            actionable_only=False,
        )
        assert updated is not None
        assert updated.performance.samples >= decay_knowledge.experience_count

    def test_full_cycle_boost_to_decay(self, bridge, pattern_store, existing_pattern):
        """完整周期: BOOST → DECAY."""
        pattern_store.store(existing_pattern)

        # 先 BOOST
        boost_k = CompressedKnowledge(
            action_type="increase_budget",
            experience_count=5,
            avg_learning_gain=0.15,
            success_rate=0.85,
            avg_reward=0.75,
            avg_confidence=0.85,
            is_reliable=True,
            reliability_score=0.80,
            dimension_key="increase_budget",
        )
        r1 = bridge.reinforce_single(boost_k, pattern_store)
        assert r1.action == "boost"

        # 再 DECAY
        decay_k = CompressedKnowledge(
            action_type="increase_budget",
            experience_count=3,
            avg_learning_gain=-0.10,
            success_rate=0.40,
            avg_reward=0.30,
            avg_confidence=0.50,
            is_reliable=True,
            reliability_score=0.40,
            dimension_key="increase_budget",
        )
        r2 = bridge.reinforce_single(decay_k, pattern_store)
        assert r2.action == "decay"

    def test_stats_after_full_cycle(
        self, bridge, compression_result_with_knowledge, pattern_store,
    ):
        """完整周期后的统计."""
        bridge.reinforce(compression_result_with_knowledge, pattern_store)
        stats = bridge.get_stats()
        assert stats["reinforce_count"] == 1
        assert stats["total_boosted"] >= 0
        assert stats["total_decayed"] >= 0