"""E17.9 Knowledge Compression — 测试用例.

Day 7.9 Step 2:
  覆盖 Knowledge Compression 层的:
    - CompressionDimension 枚举
    - CompressedKnowledge 模型 (factory methods, properties, serialization)
    - CompressionResult 模型 (factory methods, aggregation, serialization)
    - KnowledgeCompressor 引擎 (compress, group, dimension keys)
    - Memory System 桥接 (to_pattern_memory, compress_and_store)
    - Edge cases (empty, single, dedup)
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.knowledge_compression_models import (
    CompressedKnowledge,
    CompressionDimension,
    CompressionResult,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.learning_memory_models import (
    ConsolidatedExperience,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.knowledge_compressor import (
    KnowledgeCompressor,
)
from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_store import (
    PatternStore,
)
from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
    PatternMemory,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def compressor() -> KnowledgeCompressor:
    """默认压缩器."""
    return KnowledgeCompressor(min_reliable_samples=3)


@pytest.fixture
def strict_compressor() -> KnowledgeCompressor:
    """严格压缩器 (需要更多样本)."""
    return KnowledgeCompressor(min_reliable_samples=10)


@pytest.fixture
def pattern_store() -> PatternStore:
    """空模式存储."""
    return PatternStore()


@pytest.fixture
def good_experiences() -> list[ConsolidatedExperience]:
    """好的经验列表 (increase_budget, GOOD_LEARNING)."""
    return [
        ConsolidatedExperience(
            experience_id=f"exp-{i:03d}",
            source_cycle_id=f"cycle-{i:03d}",
            cycle_number=i,
            action_type="increase_budget",
            category="ua",
            success=True,
            reward=0.75 + i * 0.01,
            confidence=0.85,
            learning_gain=0.15,
            effectiveness_score=0.78,
            feedback_classification="good_learning",
            is_significant=True,
            significance_score=0.6,
        )
        for i in range(1, 6)
    ]


@pytest.fixture
def bad_experiences() -> list[ConsolidatedExperience]:
    """坏的经验列表 (reduce_budget, BAD_LEARNING)."""
    return [
        ConsolidatedExperience(
            experience_id=f"bad-exp-{i:03d}",
            source_cycle_id=f"bad-cycle-{i:03d}",
            cycle_number=i,
            action_type="reduce_budget",
            category="ua",
            success=True,
            reward=0.30,
            confidence=0.55,
            learning_gain=-0.15,
            effectiveness_score=0.25,
            feedback_classification="bad_learning",
            is_significant=True,
            significance_score=0.5,
        )
        for i in range(1, 6)
    ]


@pytest.fixture
def mixed_experiences(good_experiences, bad_experiences) -> list[ConsolidatedExperience]:
    """混合经验列表."""
    return good_experiences + bad_experiences


@pytest.fixture
def creative_experiences() -> list[ConsolidatedExperience]:
    """创意类经验."""
    return [
        ConsolidatedExperience(
            experience_id=f"creative-{i:03d}",
            action_type="mutate_hook",
            category="creative",
            success=True,
            reward=0.70,
            confidence=0.80,
            learning_gain=0.10,
            effectiveness_score=0.70,
            feedback_classification="good_learning",
            is_significant=True,
            significance_score=0.55,
        )
        for i in range(1, 4)
    ]


# ═══════════════════════════════════════════════════════════════
# Test: CompressionDimension
# ═══════════════════════════════════════════════════════════════


class TestCompressionDimension:
    """CompressionDimension 枚举测试."""

    def test_all_dimensions_exist(self):
        """所有维度存在."""
        assert CompressionDimension.ACTION_TYPE.value == "action_type"
        assert CompressionDimension.CATEGORY.value == "category"
        assert CompressionDimension.FEEDBACK_CLASSIFICATION.value == "feedback_classification"
        assert CompressionDimension.ACTION_CATEGORY.value == "action_category"
        assert CompressionDimension.ACTION_FEEDBACK.value == "action_feedback"
        assert CompressionDimension.CATEGORY_FEEDBACK.value == "category_feedback"
        assert CompressionDimension.FULL_CONTEXT.value == "full_context"


# ═══════════════════════════════════════════════════════════════
# Test: CompressedKnowledge Model
# ═══════════════════════════════════════════════════════════════


class TestCompressedKnowledgeModel:
    """CompressedKnowledge 数据模型测试."""

    def test_default_construction(self):
        """默认构造."""
        k = CompressedKnowledge()
        assert k.knowledge_id != ""
        assert k.experience_count == 0
        assert k.is_positive is False
        assert k.is_reliable is False
        assert k.is_actionable is False

    def test_from_experiences_positive(self, good_experiences):
        """从正向经验创建."""
        k = CompressedKnowledge.from_experiences(
            good_experiences, CompressionDimension.ACTION_FEEDBACK, "increase_budget|good_learning",
        )
        assert k.experience_count == 5
        assert k.action_type == "increase_budget"
        assert k.category == "ua"
        assert k.is_positive is True
        assert k.avg_learning_gain > 0
        assert k.success_rate > 0.9
        assert k.dominant_feedback == "good_learning"
        assert len(k.key_insights) > 0
        assert k.is_reliable is True  # 5 >= 3

    def test_from_experiences_negative(self, bad_experiences):
        """从负向经验创建."""
        k = CompressedKnowledge.from_experiences(
            bad_experiences, CompressionDimension.ACTION_FEEDBACK, "reduce_budget|bad_learning",
        )
        assert k.experience_count == 5
        assert k.action_type == "reduce_budget"
        assert k.is_positive is False
        assert k.avg_learning_gain < 0
        assert k.recommended_action.startswith("suppress")

    def test_from_experiences_empty(self):
        """空经验."""
        k = CompressedKnowledge.from_experiences(
            [], CompressionDimension.ACTION_TYPE, "empty",
        )
        assert k.experience_count == 0
        assert k.action_type == ""

    def test_from_experiences_single(self):
        """单条经验."""
        exp = ConsolidatedExperience(
            action_type="test_action",
            success=True,
            reward=0.80,
            learning_gain=0.20,
            feedback_classification="good_learning",
        )
        k = CompressedKnowledge.from_experiences(
            [exp], CompressionDimension.ACTION_TYPE, "test_action",
        )
        assert k.experience_count == 1
        assert k.avg_learning_gain == 0.20

    def test_is_reliable_with_few_samples(self):
        """样本不足不可靠."""
        exp = ConsolidatedExperience(action_type="test")
        k = CompressedKnowledge.from_experiences(
            [exp], CompressionDimension.ACTION_TYPE, "test",
            min_reliable_samples=5,
        )
        assert k.is_reliable is False

    def test_is_reliable_with_enough_samples(self, good_experiences):
        """样本足够可靠."""
        k = CompressedKnowledge.from_experiences(
            good_experiences, CompressionDimension.ACTION_FEEDBACK, "key",
            min_reliable_samples=3,
        )
        assert k.is_reliable is True

    def test_has_high_confidence_true(self, good_experiences):
        """高置信度."""
        k = CompressedKnowledge.from_experiences(
            good_experiences, CompressionDimension.ACTION_FEEDBACK, "key",
        )
        assert k.has_high_confidence is True

    def test_has_high_confidence_false(self, bad_experiences):
        """低置信度."""
        k = CompressedKnowledge.from_experiences(
            bad_experiences, CompressionDimension.ACTION_FEEDBACK, "key",
        )
        assert k.has_high_confidence is False

    def test_insights_positive(self, good_experiences):
        """正向洞察."""
        k = CompressedKnowledge.from_experiences(
            good_experiences, CompressionDimension.ACTION_FEEDBACK, "key",
        )
        assert any("Strong positive" in insight for insight in k.key_insights)
        assert any("High success" in insight for insight in k.key_insights)

    def test_insights_negative(self, bad_experiences):
        """负向洞察."""
        k = CompressedKnowledge.from_experiences(
            bad_experiences, CompressionDimension.ACTION_FEEDBACK, "key",
        )
        assert any("Negative learning" in insight for insight in k.key_insights)

    def test_recommendation_amplify(self, good_experiences):
        """推荐放大."""
        k = CompressedKnowledge.from_experiences(
            good_experiences, CompressionDimension.ACTION_FEEDBACK, "key",
        )
        assert "amplify" in k.recommended_action

    def test_recommendation_suppress(self, bad_experiences):
        """推荐抑制."""
        k = CompressedKnowledge.from_experiences(
            bad_experiences, CompressionDimension.ACTION_FEEDBACK, "key",
        )
        assert "suppress" in k.recommended_action

    def test_to_dict(self, good_experiences):
        """序列化."""
        k = CompressedKnowledge.from_experiences(
            good_experiences, CompressionDimension.ACTION_FEEDBACK, "key",
        )
        d = k.to_dict()
        assert d["knowledge_id"] == k.knowledge_id
        assert d["experience_count"] == 5
        assert d["is_reliable"] is True
        assert isinstance(d["key_insights"], list)


# ═══════════════════════════════════════════════════════════════
# Test: CompressionResult Model
# ═══════════════════════════════════════════════════════════════


class TestCompressionResultModel:
    """CompressionResult 数据模型测试."""

    def test_default_construction(self):
        """默认构造."""
        r = CompressionResult()
        assert r.compression_id != ""
        assert r.total_experiences == 0
        assert r.total_compressed == 0
        assert r.is_empty is True
        assert r.has_reliable is False

    def test_from_knowledge_units_empty(self):
        """空知识单元."""
        r = CompressionResult.from_knowledge_units([])
        assert r.total_compressed == 0
        assert r.is_empty is True

    def test_from_knowledge_units(self, good_experiences, bad_experiences):
        """从知识单元创建."""
        k1 = CompressedKnowledge.from_experiences(
            good_experiences, CompressionDimension.ACTION_FEEDBACK, "good|good_learning",
        )
        k2 = CompressedKnowledge.from_experiences(
            bad_experiences, CompressionDimension.ACTION_FEEDBACK, "bad|bad_learning",
        )
        r = CompressionResult.from_knowledge_units(
            [k1, k2],
            total_experiences=10,
            dimensions_used=["action_feedback"],
        )
        assert r.total_compressed == 2
        assert r.total_experiences == 10
        assert r.compression_ratio == 5.0  # 10/2
        assert r.has_reliable is True
        assert r.reliable_count == 2

    def test_reliable_knowledge_property(self, good_experiences, bad_experiences):
        """可靠知识属性."""
        k1 = CompressedKnowledge.from_experiences(
            good_experiences, CompressionDimension.ACTION_FEEDBACK, "key1",
        )
        k2 = CompressedKnowledge.from_experiences(
            bad_experiences, CompressionDimension.ACTION_FEEDBACK, "key2",
        )
        r = CompressionResult.from_knowledge_units([k1, k2])
        reliable = r.reliable_knowledge
        assert len(reliable) == 2

    def test_actionable_knowledge_property(self, good_experiences):
        """可执行知识属性."""
        k = CompressedKnowledge.from_experiences(
            good_experiences, CompressionDimension.ACTION_FEEDBACK, "key",
        )
        r = CompressionResult.from_knowledge_units([k])
        actionable = r.actionable_knowledge
        assert len(actionable) == 1

    def test_compression_summary(self, good_experiences):
        """压缩摘要."""
        k = CompressedKnowledge.from_experiences(
            good_experiences, CompressionDimension.ACTION_FEEDBACK, "key",
        )
        r = CompressionResult.from_knowledge_units([k], total_experiences=5)
        assert "Knowledge Compression Summary" in r.compression_summary
        assert "Input experiences" in r.compression_summary
        assert "Compression ratio" in r.compression_summary

    def test_to_dict(self, good_experiences):
        """序列化."""
        k = CompressedKnowledge.from_experiences(
            good_experiences, CompressionDimension.ACTION_FEEDBACK, "key",
        )
        r = CompressionResult.from_knowledge_units([k])
        d = r.to_dict()
        assert d["total_compressed"] == 1
        assert isinstance(d["knowledge_units"], list)
        assert len(d["knowledge_units"]) == 1


# ═══════════════════════════════════════════════════════════════
# Test: KnowledgeCompressor Engine
# ═══════════════════════════════════════════════════════════════


class TestKnowledgeCompressorEngine:
    """KnowledgeCompressor 引擎测试."""

    # ── Construction ──

    def test_default_construction(self):
        """默认构造."""
        c = KnowledgeCompressor()
        assert c.min_reliable_samples == 5
        assert c.compress_count == 0
        assert c.total_experiences_processed == 0
        assert c.total_knowledge_generated == 0

    def test_custom_min_samples(self):
        """自定义最小样本."""
        c = KnowledgeCompressor(min_reliable_samples=10)
        assert c.min_reliable_samples == 10

    def test_min_samples_minimum(self):
        """最小样本边界."""
        c = KnowledgeCompressor(min_reliable_samples=0)
        assert c.min_reliable_samples == 1

    # ── Compress ──

    def test_compress_empty(self, compressor):
        """压缩空列表."""
        result = compressor.compress([])
        assert result.is_empty is True
        assert result.total_compressed == 0

    def test_compress_good_experiences(self, compressor, good_experiences):
        """压缩好经验."""
        result = compressor.compress(good_experiences)
        assert result.total_experiences == 5
        assert result.total_compressed > 0
        assert result.has_reliable is True

    def test_compress_mixed_experiences(self, compressor, mixed_experiences):
        """压缩混合经验."""
        result = compressor.compress(mixed_experiences)
        assert result.total_experiences == 10
        # 应有至少 2 个知识单元 (good 和 bad 分组)
        assert result.total_compressed >= 2

    def test_compress_increments_counters(self, compressor, good_experiences):
        """压缩增加计数器."""
        assert compressor.compress_count == 0
        compressor.compress(good_experiences)
        assert compressor.compress_count == 1
        assert compressor.total_experiences_processed == 5
        assert compressor.total_knowledge_generated > 0

    def test_compress_default_dimensions(self, compressor, good_experiences):
        """默认维度压缩."""
        result = compressor.compress(good_experiences)
        assert "action_feedback" in result.dimensions_used
        assert "category_feedback" in result.dimensions_used

    # ── Compress Single Dimension ──

    def test_compress_action_type(self, compressor, mixed_experiences):
        """按 ACTION_TYPE 压缩."""
        result = compressor.compress_single_dimension(
            mixed_experiences, CompressionDimension.ACTION_TYPE,
        )
        assert result.total_compressed >= 2  # increase_budget + reduce_budget
        assert result.total_experiences == 10

    def test_compress_category(self, compressor, mixed_experiences):
        """按 CATEGORY 压缩."""
        result = compressor.compress_single_dimension(
            mixed_experiences, CompressionDimension.CATEGORY,
        )
        assert result.total_compressed >= 1  # ua
        assert result.total_experiences == 10

    def test_compress_feedback_classification(self, compressor, mixed_experiences):
        """按 FEEDBACK_CLASSIFICATION 压缩."""
        result = compressor.compress_single_dimension(
            mixed_experiences, CompressionDimension.FEEDBACK_CLASSIFICATION,
        )
        assert result.total_compressed >= 2  # good_learning + bad_learning

    def test_compress_action_category(self, compressor, mixed_experiences):
        """按 ACTION_CATEGORY 压缩."""
        result = compressor.compress_single_dimension(
            mixed_experiences, CompressionDimension.ACTION_CATEGORY,
        )
        assert result.total_compressed >= 2

    def test_compress_action_feedback(self, compressor, mixed_experiences):
        """按 ACTION_FEEDBACK 压缩."""
        result = compressor.compress_single_dimension(
            mixed_experiences, CompressionDimension.ACTION_FEEDBACK,
        )
        assert result.total_compressed >= 2

    def test_compress_category_feedback(self, compressor, mixed_experiences):
        """按 CATEGORY_FEEDBACK 压缩."""
        result = compressor.compress_single_dimension(
            mixed_experiences, CompressionDimension.CATEGORY_FEEDBACK,
        )
        assert result.total_compressed >= 2

    def test_compress_full_context(self, compressor, mixed_experiences):
        """按 FULL_CONTEXT 压缩."""
        result = compressor.compress_single_dimension(
            mixed_experiences, CompressionDimension.FULL_CONTEXT,
        )
        assert result.total_compressed >= 2

    # ── Dimension Keys ──

    def test_dimension_key_action_type(self, compressor):
        """ACTION_TYPE 维度键."""
        exp = ConsolidatedExperience(action_type="increase_budget")
        key = compressor._dimension_key(exp, CompressionDimension.ACTION_TYPE)
        assert key == "increase_budget"

    def test_dimension_key_category(self, compressor):
        """CATEGORY 维度键."""
        exp = ConsolidatedExperience(category="ua")
        key = compressor._dimension_key(exp, CompressionDimension.CATEGORY)
        assert key == "ua"

    def test_dimension_key_feedback(self, compressor):
        """FEEDBACK_CLASSIFICATION 维度键."""
        exp = ConsolidatedExperience(feedback_classification="good_learning")
        key = compressor._dimension_key(exp, CompressionDimension.FEEDBACK_CLASSIFICATION)
        assert key == "good_learning"

    def test_dimension_key_action_feedback(self, compressor):
        """ACTION_FEEDBACK 维度键."""
        exp = ConsolidatedExperience(action_type="increase_budget", feedback_classification="good_learning")
        key = compressor._dimension_key(exp, CompressionDimension.ACTION_FEEDBACK)
        assert key == "increase_budget|good_learning"

    def test_dimension_key_full_context(self, compressor):
        """FULL_CONTEXT 维度键."""
        exp = ConsolidatedExperience(
            action_type="increase_budget",
            category="ua",
            feedback_classification="good_learning",
        )
        key = compressor._dimension_key(exp, CompressionDimension.FULL_CONTEXT)
        assert key == "increase_budget|ua|good_learning"

    def test_dimension_key_empty(self, compressor):
        """空值维度键."""
        exp = ConsolidatedExperience()
        key = compressor._dimension_key(exp, CompressionDimension.ACTION_TYPE)
        assert key == "unknown"

    # ── to_pattern_memory ──

    def test_to_pattern_memory(self, compressor, good_experiences):
        """转换为 PatternMemory."""
        result = compressor.compress(good_experiences)
        k = result.knowledge_units[0]
        pattern = compressor.to_pattern_memory(k)
        assert isinstance(pattern, PatternMemory)
        assert pattern.action.action_type == k.action_type
        assert pattern.performance.samples == k.experience_count
        assert pattern.performance.success_rate == k.success_rate
        assert pattern.confidence == k.reliability_score

    def test_to_pattern_memory_tags(self, compressor, good_experiences):
        """PatternMemory 包含标签."""
        result = compressor.compress(good_experiences)
        k = result.knowledge_units[0]
        pattern = compressor.to_pattern_memory(k)
        assert len(pattern.tags) > 0
        assert "positive" in pattern.tags
        assert "reliable" in pattern.tags

    def test_to_pattern_memories_batch(self, compressor, good_experiences):
        """批量转换."""
        result = compressor.compress(good_experiences)
        patterns = compressor.to_pattern_memories(result.knowledge_units)
        assert len(patterns) == result.total_compressed
        assert all(isinstance(p, PatternMemory) for p in patterns)

    def test_to_pattern_memory_bad(self, compressor, bad_experiences):
        """坏经验的 PatternMemory."""
        result = compressor.compress(bad_experiences)
        k = result.knowledge_units[0]
        pattern = compressor.to_pattern_memory(k)
        assert "negative" in pattern.tags
        assert pattern.performance.avg_reward < 0.5

    # ── compress_and_store ──

    def test_compress_and_store(self, compressor, good_experiences, pattern_store):
        """压缩并存储."""
        assert pattern_store.count == 0
        result = compressor.compress_and_store(good_experiences, pattern_store)
        assert result.total_compressed > 0
        # 可靠知识应被存储
        assert pattern_store.count > 0

    def test_compress_and_store_non_reliable(self, strict_compressor, good_experiences, pattern_store):
        """不可靠知识不存储."""
        # 严格压缩器需要 10 个样本才算可靠
        assert pattern_store.count == 0
        result = strict_compressor.compress_and_store(good_experiences, pattern_store)
        assert result.total_compressed > 0
        # 只有 5 个样本，不够，所以不应存储
        assert pattern_store.count == 0

    def test_compress_from_extraction(self, compressor, good_experiences):
        """从 ExtractionResult 压缩."""
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.learning_memory_models import (
            ExtractionResult,
        )
        extraction = ExtractionResult.from_experiences(good_experiences)
        result = compressor.compress_from_extraction(extraction)
        assert result.total_experiences == 5
        assert result.total_compressed > 0

    # ── Deduplication ──

    def test_deduplicate_same_key(self, compressor, good_experiences):
        """去重相同键."""
        # 使用两个维度压缩，可能产生重复键
        result = compressor.compress(
            good_experiences,
            dimensions=[CompressionDimension.ACTION_FEEDBACK, CompressionDimension.ACTION_FEEDBACK],
        )
        # 相同维度的重复结果应被去重
        keys = [k.dimension_key for k in result.knowledge_units]
        assert len(keys) == len(set(keys))  # 所有键唯一

    # ── Edge Cases ──

    def test_compress_single_experience(self, compressor):
        """单条经验压缩."""
        exp = ConsolidatedExperience(
            action_type="test_action",
            category="creative",
            success=True,
            reward=0.80,
            learning_gain=0.10,
        )
        result = compressor.compress([exp])
        assert result.total_experiences == 1
        assert result.total_compressed > 0

    def test_compress_creative_experiences(self, compressor, creative_experiences):
        """创意类经验压缩."""
        result = compressor.compress(creative_experiences)
        assert result.total_experiences == 3
        assert result.total_compressed > 0
        for k in result.knowledge_units:
            assert k.category == "creative"

    def test_compress_many_dimensions(self, compressor, mixed_experiences):
        """多维度同时压缩."""
        all_dims = list(CompressionDimension)
        result = compressor.compress(mixed_experiences, dimensions=all_dims)
        assert result.total_compressed > 0
        assert len(result.dimensions_used) == len(all_dims)

    # ── Statistics ──

    def test_get_stats(self, compressor, good_experiences):
        """获取统计."""
        compressor.compress(good_experiences)
        stats = compressor.get_stats()
        assert stats["compress_count"] == 1
        assert stats["total_experiences_processed"] == 5
        assert stats["total_knowledge_generated"] > 0
        assert "avg_compression_ratio" in stats

    def test_reset_stats(self, compressor, good_experiences):
        """重置统计."""
        compressor.compress(good_experiences)
        compressor.reset_stats()
        assert compressor.compress_count == 0
        assert compressor.total_experiences_processed == 0
        assert compressor.total_knowledge_generated == 0

    # ── Quality Mapping ──

    def test_quality_strong(self, compressor):
        """STRONG 质量."""
        exps = [
            ConsolidatedExperience(
                action_type="test", success=True, reward=0.80,
                learning_gain=0.15, feedback_classification="good_learning",
            )
            for _ in range(30)
        ]
        result = compressor.compress(exps)
        k = result.knowledge_units[0]
        pattern = compressor.to_pattern_memory(k)
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternQuality
        assert pattern.performance.quality == PatternQuality.STRONG

    def test_quality_weak(self, compressor):
        """WEAK 质量."""
        exps = [
            ConsolidatedExperience(
                action_type="test", success=False, reward=0.20,
                learning_gain=-0.10, feedback_classification="bad_learning",
            )
            for _ in range(2)
        ]
        result = compressor.compress(exps)
        k = result.knowledge_units[0]
        pattern = compressor.to_pattern_memory(k)
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternQuality
        assert pattern.performance.quality == PatternQuality.WEAK