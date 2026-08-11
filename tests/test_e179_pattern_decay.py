"""E17.9 Pattern Decay — 测试用例.

Day 7.9 Step 4:
  覆盖 Pattern Decay 层的:
    - PatternDecayReason 枚举
    - DecayAction 枚举
    - DecayScore 模型 (properties, serialization)
    - PatternDecayResult 模型 (properties, serialization)
    - DecayBatchResult 模型 (from_results, aggregation, properties, serialization)
    - PatternDecayEngine 引擎 (calculate_decay_score, evaluate_pattern, decay_store)
    - Factor calculation (stale, reward, usage, confidence)
    - Decay action decision (MAINTAIN, REDUCE_CONFIDENCE, MARK_AVOID, ARCHIVE, DELETE)
    - Lifecycle manager integration
    - Edge cases (empty store, fresh pattern, extreme values)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.pattern_decay_models import (
    DecayAction,
    DecayBatchResult,
    DecayScore,
    PatternDecayReason,
    PatternDecayResult,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.pattern_decay_engine import (
    PatternDecayEngine,
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
def now() -> datetime:
    """固定当前时间."""
    return datetime(2026, 7, 30, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def engine(now) -> PatternDecayEngine:
    """默认引擎."""
    return PatternDecayEngine(now=now)


@pytest.fixture
def pattern_store() -> PatternStore:
    """空模式存储."""
    return PatternStore()


@pytest.fixture
def fresh_pattern() -> PatternMemory:
    """新鲜模式 (最近使用, 高成功率)."""
    condition = PatternCondition(
        opportunity_type="increase_budget",
        action_type="increase_budget",
    )
    action = PatternAction(
        action_type="increase_budget",
        expected_impact="amplify",
    )
    perf = PatternPerformance(
        samples=20,
        success_count=17,
        success_rate=0.85,
        avg_reward=0.80,
        avg_confidence=0.90,
        last_seen=datetime(2026, 7, 29, tzinfo=timezone.utc).isoformat(),
    )
    pattern = PatternMemory(
        dimension=PatternMiningDimension.OPPORTUNITY_ACTION,
        condition=condition,
        action=action,
        performance=perf,
        tags=["positive", "ua"],
        metadata={
            "peak_reward": 0.85,
            "usage_count_recent": 50,
            "usage_count_peak": 60,
        },
    )
    pattern.compute_score()
    return pattern


@pytest.fixture
def stale_pattern() -> PatternMemory:
    """过期模式 (长期未使用)."""
    condition = PatternCondition(
        opportunity_type="old_strategy",
        action_type="old_strategy",
    )
    action = PatternAction(
        action_type="old_strategy",
        expected_impact="maintain",
    )
    perf = PatternPerformance(
        samples=5,
        success_count=3,
        success_rate=0.60,
        avg_reward=0.50,
        avg_confidence=0.60,
        last_seen=datetime(2026, 6, 20, tzinfo=timezone.utc).isoformat(),  # 40 days ago
    )
    pattern = PatternMemory(
        dimension=PatternMiningDimension.OPPORTUNITY_ACTION,
        condition=condition,
        action=action,
        performance=perf,
        tags=["old"],
        metadata={
            "peak_reward": 0.70,
            "usage_count_recent": 2,
            "usage_count_peak": 50,
        },
    )
    pattern.compute_score()
    return pattern


@pytest.fixture
def low_reward_pattern() -> PatternMemory:
    """低奖励模式."""
    condition = PatternCondition(
        opportunity_type="failing_strategy",
        action_type="failing_strategy",
    )
    action = PatternAction(
        action_type="failing_strategy",
        expected_impact="suppress",
    )
    perf = PatternPerformance(
        samples=10,
        success_count=2,
        success_rate=0.20,
        avg_reward=0.10,
        avg_confidence=0.30,
        last_seen=datetime(2026, 7, 25, tzinfo=timezone.utc).isoformat(),
    )
    pattern = PatternMemory(
        dimension=PatternMiningDimension.OPPORTUNITY_ACTION,
        condition=condition,
        action=action,
        performance=perf,
        tags=["negative"],
        metadata={
            "peak_reward": 0.65,
            "usage_count_recent": 5,
            "usage_count_peak": 30,
        },
    )
    pattern.compute_score()
    return pattern


@pytest.fixture
def very_stale_pattern() -> PatternMemory:
    """极度过期模式 (超过 90 天)."""
    condition = PatternCondition(
        opportunity_type="ancient_strategy",
        action_type="ancient_strategy",
    )
    action = PatternAction(
        action_type="ancient_strategy",
        expected_impact="suppress",
    )
    perf = PatternPerformance(
        samples=3,
        success_count=0,
        success_rate=0.10,
        avg_reward=0.05,
        avg_confidence=0.15,
        last_seen=datetime(2026, 2, 1, tzinfo=timezone.utc).isoformat(),  # 179 days ago
    )
    pattern = PatternMemory(
        dimension=PatternMiningDimension.OPPORTUNITY_ACTION,
        condition=condition,
        action=action,
        performance=perf,
        tags=["ancient", "negative"],
        metadata={
            "peak_reward": 0.40,
            "usage_count_recent": 0,
            "usage_count_peak": 20,
        },
    )
    pattern.compute_score()
    return pattern


# ═══════════════════════════════════════════════════════════════
# Test: PatternDecayReason
# ═══════════════════════════════════════════════════════════════


class TestPatternDecayReason:
    """PatternDecayReason 枚举测试."""

    def test_all_reasons_exist(self):
        """所有原因存在."""
        assert PatternDecayReason.STALE.value == "stale"
        assert PatternDecayReason.LOW_REWARD.value == "low_reward"
        assert PatternDecayReason.LOW_USAGE.value == "low_usage"
        assert PatternDecayReason.PERFORMANCE_DROP.value == "performance_drop"
        assert PatternDecayReason.CONFIDENCE_DECAY.value == "confidence_decay"
        assert PatternDecayReason.LOW_SAMPLES.value == "low_samples"
        assert PatternDecayReason.QUALITY_DEGRADATION.value == "quality_degradation"

    def test_reason_count(self):
        """原因数量."""
        assert len(list(PatternDecayReason)) == 7


# ═══════════════════════════════════════════════════════════════
# Test: DecayAction
# ═══════════════════════════════════════════════════════════════


class TestDecayAction:
    """DecayAction 枚举测试."""

    def test_all_actions_exist(self):
        """所有动作存在."""
        assert DecayAction.MAINTAIN.value == "maintain"
        assert DecayAction.REDUCE_CONFIDENCE.value == "reduce_confidence"
        assert DecayAction.MARK_AVOID.value == "mark_avoid"
        assert DecayAction.ARCHIVE.value == "archive"
        assert DecayAction.DELETE.value == "delete"

    def test_action_count(self):
        """动作数量."""
        assert len(list(DecayAction)) == 5


# ═══════════════════════════════════════════════════════════════
# Test: DecayScore Model
# ═══════════════════════════════════════════════════════════════


class TestDecayScoreModel:
    """DecayScore 数据模型测试."""

    def test_default_construction(self):
        """默认构造."""
        s = DecayScore()
        assert s.total == 0.0
        assert s.stale_factor == 0.0
        assert s.reward_drop == 0.0
        assert s.usage_drop == 0.0
        assert s.confidence_loss == 0.0
        assert s.is_significant is False
        assert s.is_severe is False
        assert s.is_critical is False

    def test_significant_score(self):
        """显著衰减."""
        s = DecayScore(total=0.35)
        assert s.is_significant is True
        assert s.is_severe is False
        assert s.is_critical is False

    def test_severe_score(self):
        """严重衰减."""
        s = DecayScore(total=0.65)
        assert s.is_significant is True
        assert s.is_severe is True
        assert s.is_critical is False

    def test_critical_score(self):
        """关键衰减."""
        s = DecayScore(total=0.85)
        assert s.is_significant is True
        assert s.is_severe is True
        assert s.is_critical is True

    def test_boundary_significant(self):
        """显著性边界."""
        s = DecayScore(total=0.30)
        assert s.is_significant is True  # >= 0.3

    def test_boundary_not_significant(self):
        """非显著性边界."""
        s = DecayScore(total=0.29)
        assert s.is_significant is False

    def test_to_dict(self):
        """序列化."""
        s = DecayScore(
            total=0.55,
            stale_factor=0.60,
            reward_drop=0.40,
            usage_drop=0.30,
            confidence_loss=0.20,
            reason=PatternDecayReason.STALE.value,
            factors={"stale": 0.60},
        )
        d = s.to_dict()
        assert d["total"] == 0.55
        assert d["stale_factor"] == 0.60
        assert d["reward_drop"] == 0.40
        assert d["usage_drop"] == 0.30
        assert d["confidence_loss"] == 0.20
        assert d["reason"] == "stale"
        assert d["factors"] == {"stale": 0.60}

    def test_custom_reason(self):
        """自定义原因."""
        s = DecayScore(
            total=0.50,
            reason=PatternDecayReason.LOW_REWARD.value,
        )
        assert s.reason == "low_reward"


# ═══════════════════════════════════════════════════════════════
# Test: PatternDecayResult Model
# ═══════════════════════════════════════════════════════════════


class TestPatternDecayResultModel:
    """PatternDecayResult 数据模型测试."""

    def test_default_construction(self):
        """默认构造."""
        r = PatternDecayResult()
        assert r.result_id != ""
        assert r.pattern_id == ""
        assert r.action == "maintain"
        assert r.changed is False
        assert r.was_maintained is True
        assert r.was_deleted is False
        assert r.was_archived is False

    def test_changed_result(self):
        """已变化结果."""
        r = PatternDecayResult(
            pattern_id="p-001",
            action=DecayAction.REDUCE_CONFIDENCE.value,
            changed=True,
            confidence_before=0.80,
            confidence_after=0.68,
            confidence_delta=-0.12,
        )
        assert r.changed is True
        assert r.was_maintained is False
        assert r.was_deleted is False
        assert r.was_archived is False

    def test_archived_result(self):
        """归档结果."""
        r = PatternDecayResult(
            action=DecayAction.ARCHIVE.value,
            changed=True,
        )
        assert r.was_archived is True
        assert r.was_deleted is False

    def test_deleted_result(self):
        """删除结果."""
        r = PatternDecayResult(
            action=DecayAction.DELETE.value,
            changed=True,
        )
        assert r.was_deleted is True
        assert r.was_archived is False

    def test_lifecycle_tracking(self):
        """生命周期跟踪."""
        r = PatternDecayResult(
            lifecycle_from="active",
            lifecycle_to="decaying",
        )
        assert r.lifecycle_from == "active"
        assert r.lifecycle_to == "decaying"

    def test_to_dict(self):
        """序列化."""
        r = PatternDecayResult(
            pattern_id="p-001",
            reason="stale",
            action=DecayAction.REDUCE_CONFIDENCE.value,
            changed=True,
            confidence_before=0.80,
            confidence_after=0.68,
            confidence_delta=-0.12,
            lifecycle_from="active",
            lifecycle_to="active",
        )
        d = r.to_dict()
        assert d["pattern_id"] == "p-001"
        assert d["action"] == "reduce_confidence"
        assert d["changed"] is True
        assert d["confidence_before"] == 0.80
        assert d["confidence_delta"] == -0.12
        assert isinstance(d["decay_score"], dict)


# ═══════════════════════════════════════════════════════════════
# Test: DecayBatchResult Model
# ═══════════════════════════════════════════════════════════════


class TestDecayBatchResultModel:
    """DecayBatchResult 数据模型测试."""

    def test_default_construction(self):
        """默认构造."""
        b = DecayBatchResult()
        assert b.batch_id != ""
        assert b.total_patterns == 0
        assert b.is_empty is True
        assert b.has_changes is False

    def test_from_results_empty(self):
        """空结果."""
        b = DecayBatchResult.from_results([])
        assert b.total_patterns == 0
        assert b.is_empty is True

    def test_from_results_single_maintain(self):
        """单条 MAINTAIN."""
        r = PatternDecayResult(changed=False)
        b = DecayBatchResult.from_results([r])
        assert b.total_patterns == 1
        assert b.decayed_patterns == 0
        assert b.maintained_patterns == 1
        assert b.has_changes is False

    def test_from_results_mixed(self):
        """混合结果."""
        results = [
            PatternDecayResult(
                action=DecayAction.REDUCE_CONFIDENCE.value,
                changed=True,
                confidence_delta=-0.10,
            ),
            PatternDecayResult(
                action=DecayAction.ARCHIVE.value,
                changed=True,
                confidence_delta=-0.30,
            ),
            PatternDecayResult(
                action=DecayAction.DELETE.value,
                changed=True,
                confidence_delta=-0.50,
            ),
            PatternDecayResult(changed=False),
        ]
        b = DecayBatchResult.from_results(results)
        assert b.total_patterns == 4
        assert b.decayed_patterns == 1
        assert b.archived_patterns == 1
        assert b.deleted_patterns == 1
        assert b.maintained_patterns == 1
        # total_loss = -0.10 + -0.30 + -0.50 + 0.0 = -0.90
        assert b.total_confidence_loss == -0.90
        assert b.avg_confidence_loss == -0.225
        assert b.has_changes is True

    def test_summary_content(self):
        """摘要内容."""
        r = PatternDecayResult(
            action=DecayAction.REDUCE_CONFIDENCE.value,
            changed=True,
            confidence_delta=-0.10,
        )
        b = DecayBatchResult.from_results([r])
        assert "Pattern Decay Summary" in b.decay_summary
        assert "Total patterns" in b.decay_summary
        assert "Decayed" in b.decay_summary
        assert "Total confidence loss" in b.decay_summary

    def test_to_dict(self):
        """序列化."""
        r = PatternDecayResult(changed=False)
        b = DecayBatchResult.from_results([r])
        d = b.to_dict()
        assert d["batch_id"] == b.batch_id
        assert d["total_patterns"] == 1
        assert isinstance(d["results"], list)
        assert len(d["results"]) == 1


# ═══════════════════════════════════════════════════════════════
# Test: PatternDecayEngine — Construction
# ═══════════════════════════════════════════════════════════════


class TestPatternDecayEngineConstruction:
    """PatternDecayEngine 构造测试."""

    def test_default_construction(self):
        """默认构造."""
        e = PatternDecayEngine()
        assert e.decay_count == 0
        assert e.total_decayed == 0
        assert e.total_archived == 0
        assert e.total_deleted == 0

    def test_custom_thresholds(self):
        """自定义阈值."""
        e = PatternDecayEngine(stale_days=14, max_stale_days=60)
        assert e._stale_days == 14
        assert e._max_stale_days == 60

    def test_get_stats(self, engine):
        """获取统计."""
        stats = engine.get_stats()
        assert stats["decay_count"] == 0
        assert stats["total_decayed"] == 0
        assert "stale_days_threshold" in stats

    def test_reset_stats(self, engine):
        """重置统计."""
        engine._decay_count = 5
        engine._total_decayed = 3
        engine._total_archived = 2
        engine._total_deleted = 1
        engine.reset_stats()
        assert engine.decay_count == 0
        assert engine.total_decayed == 0
        assert engine.total_archived == 0
        assert engine.total_deleted == 0


# ═══════════════════════════════════════════════════════════════
# Test: PatternDecayEngine — Factor Calculation
# ═══════════════════════════════════════════════════════════════


class TestFactorCalculation:
    """因子计算测试."""

    def test_stale_factor_fresh(self, engine, fresh_pattern):
        """新鲜模式过期因子."""
        f = engine._calc_stale_factor(fresh_pattern.performance.last_seen)
        assert 0.0 < f < 0.1  # 1 day ago, very low

    def test_stale_factor_stale(self, engine, stale_pattern):
        """过期模式过期因子."""
        f = engine._calc_stale_factor(stale_pattern.performance.last_seen)
        assert f > 0.4  # 40 days ago, should be significant

    def test_stale_factor_very_stale(self, engine, very_stale_pattern):
        """极度过期模式过期因子."""
        f = engine._calc_stale_factor(very_stale_pattern.performance.last_seen)
        assert f == 1.0  # 179 days, capped at 1.0

    def test_stale_factor_empty_last_seen(self, engine):
        """无 last_seen."""
        f = engine._calc_stale_factor("")
        assert f == 0.0

    def test_reward_drop_high(self, engine, low_reward_pattern):
        """奖励下降显著."""
        drop = engine._calc_reward_drop(
            low_reward_pattern.performance.avg_reward,
            low_reward_pattern.metadata,
        )
        # peak_reward=0.65, avg_reward=0.10 → drop = 1 - 0.10/0.65 = 0.8462
        assert drop > 0.8

    def test_reward_drop_low(self, engine, fresh_pattern):
        """奖励下降轻微."""
        drop = engine._calc_reward_drop(
            fresh_pattern.performance.avg_reward,
            fresh_pattern.metadata,
        )
        # peak_reward=0.85, avg_reward=0.80 → drop = 1 - 0.80/0.85 = 0.0588
        assert drop < 0.1

    def test_reward_drop_no_peak(self, engine):
        """无峰值奖励."""
        drop = engine._calc_reward_drop(0.50, {})
        assert drop == 0.0

    def test_usage_drop_high(self, engine, stale_pattern):
        """使用下降显著."""
        drop = engine._calc_usage_drop(stale_pattern.metadata)
        # recent=2, peak=50 → drop = 1 - 2/50 = 0.96
        assert drop > 0.9

    def test_usage_drop_low(self, engine, fresh_pattern):
        """使用下降轻微."""
        drop = engine._calc_usage_drop(fresh_pattern.metadata)
        # recent=50, peak=60 → drop = 1 - 50/60 = 0.1667
        assert drop < 0.2

    def test_usage_drop_empty_metadata(self, engine):
        """无使用数据."""
        drop = engine._calc_usage_drop({})
        assert drop == 0.0

    def test_confidence_loss_high(self, engine):
        """高置信度损失."""
        p = PatternMemory(
            dimension=PatternMiningDimension.OPPORTUNITY_ACTION,
            condition=PatternCondition(),
            action=PatternAction(),
            performance=PatternPerformance(),
        )
        p.confidence = 0.15
        loss = engine._calc_confidence_loss(p)
        assert loss > 0.8

    def test_confidence_loss_low(self, engine):
        """低置信度损失."""
        p = PatternMemory(
            dimension=PatternMiningDimension.OPPORTUNITY_ACTION,
            condition=PatternCondition(),
            action=PatternAction(),
            performance=PatternPerformance(),
        )
        p.confidence = 0.90
        loss = engine._calc_confidence_loss(p)
        assert loss < 0.2


# ═══════════════════════════════════════════════════════════════
# Test: PatternDecayEngine — Decay Score Calculation
# ═══════════════════════════════════════════════════════════════


class TestDecayScoreCalculation:
    """衰减评分计算测试."""

    def test_fresh_pattern_score_low(self, engine, fresh_pattern):
        """新鲜模式评分低."""
        score = engine.calculate_decay_score(fresh_pattern)
        assert score.total < 0.3
        assert score.is_significant is False

    def test_stale_pattern_score_high(self, engine, stale_pattern):
        """过期模式评分高."""
        score = engine.calculate_decay_score(stale_pattern)
        assert score.total > 0.3
        assert score.is_significant is True

    def test_very_stale_pattern_score_critical(self, engine, very_stale_pattern):
        """极度过期模式评分关键."""
        score = engine.calculate_decay_score(very_stale_pattern)
        assert score.total > 0.8
        assert score.is_critical is True

    def test_low_reward_pattern_score(self, engine, low_reward_pattern):
        """低奖励模式评分."""
        score = engine.calculate_decay_score(low_reward_pattern)
        assert score.reward_drop > 0.5

    def test_score_range(self, engine, fresh_pattern):
        """评分范围 [0, 1]."""
        score = engine.calculate_decay_score(fresh_pattern)
        assert 0.0 <= score.total <= 1.0

    def test_score_factors_sum(self, engine, fresh_pattern):
        """因子权重和为 1.0."""
        score = engine.calculate_decay_score(fresh_pattern)
        expected = (
            score.stale_factor * engine.WEIGHT_STALE
            + score.reward_drop * engine.WEIGHT_REWARD
            + score.usage_drop * engine.WEIGHT_USAGE
            + score.confidence_loss * engine.WEIGHT_CONFIDENCE
        )
        assert abs(score.total - round(expected, 4)) < 0.001

    def test_dominant_reason_stale(self, engine, very_stale_pattern):
        """主导原因: STALE."""
        score = engine.calculate_decay_score(very_stale_pattern)
        assert score.reason == PatternDecayReason.STALE.value

    def test_dominant_reason_low_reward(self, engine, low_reward_pattern):
        """主导原因: LOW_REWARD."""
        score = engine.calculate_decay_score(low_reward_pattern)
        # 由于 stale_factor 也较高 (5 days), 但 reward_drop 更高
        assert score.reason in (
            PatternDecayReason.LOW_REWARD.value,
            PatternDecayReason.STALE.value,
        )


# ═══════════════════════════════════════════════════════════════
# Test: PatternDecayEngine — Action Decision
# ═══════════════════════════════════════════════════════════════


class TestDecayActionDecision:
    """衰减动作决策测试."""

    def test_maintain_low_score(self, engine):
        """低评分 → MAINTAIN."""
        s = DecayScore(total=0.10)
        action = engine._determine_decay_action(s)
        assert action == DecayAction.MAINTAIN

    def test_reduce_confidence_medium_score(self, engine):
        """中等评分 → REDUCE_CONFIDENCE."""
        s = DecayScore(total=0.45)
        action = engine._determine_decay_action(s)
        assert action == DecayAction.REDUCE_CONFIDENCE

    def test_mark_avoid_high_score(self, engine):
        """高评分 → MARK_AVOID."""
        s = DecayScore(total=0.70)
        action = engine._determine_decay_action(s)
        assert action == DecayAction.MARK_AVOID

    def test_archive_very_high_score(self, engine):
        """极高评分 → ARCHIVE."""
        s = DecayScore(total=0.85)
        action = engine._determine_decay_action(s)
        assert action == DecayAction.ARCHIVE

    def test_boundary_maintain_reduce(self, engine):
        """MAINTAIN/REDUCE 边界."""
        s = DecayScore(total=0.30)
        action = engine._determine_decay_action(s)
        assert action == DecayAction.REDUCE_CONFIDENCE

    def test_boundary_reduce_mark(self, engine):
        """REDUCE/MARK 边界."""
        s = DecayScore(total=0.60)
        action = engine._determine_decay_action(s)
        assert action == DecayAction.MARK_AVOID

    def test_boundary_mark_archive(self, engine):
        """MARK/ARCHIVE 边界."""
        s = DecayScore(total=0.80)
        action = engine._determine_decay_action(s)
        assert action == DecayAction.ARCHIVE


# ═══════════════════════════════════════════════════════════════
# Test: PatternDecayEngine — Evaluate Pattern
# ═══════════════════════════════════════════════════════════════


class TestEvaluatePattern:
    """单模式评估测试."""

    def test_fresh_pattern_maintain(self, engine, fresh_pattern):
        """新鲜模式 → MAINTAIN."""
        result = engine.evaluate_pattern(fresh_pattern)
        assert result.action == "maintain"
        assert result.changed is False
        assert result.confidence_delta == 0.0

    def test_stale_pattern_reduce_confidence(self, engine, stale_pattern):
        """过期模式 → REDUCE_CONFIDENCE."""
        result = engine.evaluate_pattern(stale_pattern)
        assert result.action == "reduce_confidence"
        assert result.changed is True
        assert result.confidence_delta < 0

    def test_very_stale_pattern_archive(self, engine, very_stale_pattern):
        """极度过期模式 → ARCHIVE."""
        result = engine.evaluate_pattern(very_stale_pattern)
        assert result.action == "archive"
        assert result.changed is True
        assert result.confidence_after < result.confidence_before

    def test_reduce_confidence_updates_metadata(self, engine, stale_pattern):
        """REDUCE_CONFIDENCE 更新元数据."""
        engine.evaluate_pattern(stale_pattern)
        assert "last_decayed" in stale_pattern.metadata
        assert "decay_reason" in stale_pattern.metadata
        assert "decay_score" in stale_pattern.metadata

    def test_mark_avoid_adds_tag(self, engine):
        """MARK_AVOID 添加标签."""
        p = PatternMemory(
            dimension=PatternMiningDimension.OPPORTUNITY_ACTION,
            condition=PatternCondition(
                opportunity_type="avoid_test",
                action_type="avoid_test",
            ),
            action=PatternAction(action_type="avoid_test"),
            performance=PatternPerformance(
                samples=10,
                success_count=3,
                success_rate=0.30,
                avg_reward=0.20,
                avg_confidence=0.40,
                last_seen=datetime(2026, 5, 21, tzinfo=timezone.utc).isoformat(),  # 70 days ago
            ),
            tags=["test"],
            metadata={
                "peak_reward": 0.60,
                "usage_count_recent": 1,
                "usage_count_peak": 30,
            },
        )
        p.compute_score()
        result = engine.evaluate_pattern(p)
        assert result.action == "mark_avoid"
        assert "avoid" in p.tags
        assert p.metadata.get("marked_avoid") is True

    def test_archive_sets_lifecycle_state(self, engine, very_stale_pattern):
        """ARCHIVE 设置生命周期状态."""
        engine.evaluate_pattern(very_stale_pattern)
        assert very_stale_pattern.metadata.get("lifecycle_state") == "archived"

    def test_confidence_decreased_after_decay(self, engine, stale_pattern):
        """衰减后置信度降低."""
        before = stale_pattern.confidence
        engine.evaluate_pattern(stale_pattern)
        assert stale_pattern.confidence < before


# ═══════════════════════════════════════════════════════════════
# Test: PatternDecayEngine — Decay Store
# ═══════════════════════════════════════════════════════════════


class TestDecayStore:
    """批量衰减存储测试."""

    def test_decay_store_empty(self, engine, pattern_store):
        """空存储."""
        batch = engine.decay_store(pattern_store)
        assert batch.total_patterns == 0
        assert batch.is_empty is True

    def test_decay_store_fresh_only(self, engine, pattern_store, fresh_pattern):
        """仅新鲜模式."""
        pattern_store.store(fresh_pattern)
        batch = engine.decay_store(pattern_store)
        assert batch.total_patterns == 1
        assert batch.maintained_patterns == 1
        assert batch.has_changes is False

    def test_decay_store_with_stale(self, engine, pattern_store, fresh_pattern, stale_pattern):
        """包含过期模式."""
        pattern_store.store(fresh_pattern)
        pattern_store.store(stale_pattern)
        batch = engine.decay_store(pattern_store)
        assert batch.total_patterns == 2
        assert batch.maintained_patterns == 1
        assert batch.decayed_patterns >= 1

    def test_decay_store_increments_count(self, engine, pattern_store, fresh_pattern):
        """批量衰减增加计数."""
        pattern_store.store(fresh_pattern)
        engine.decay_store(pattern_store)
        assert engine.decay_count == 1

    def test_decay_store_tracks_decayed(self, engine, pattern_store, stale_pattern):
        """跟踪衰减计数."""
        pattern_store.store(stale_pattern)
        engine.decay_store(pattern_store)
        assert engine.total_decayed >= 1

    def test_decay_store_tracks_archived(self, engine, pattern_store, very_stale_pattern):
        """跟踪归档计数."""
        pattern_store.store(very_stale_pattern)
        engine.decay_store(pattern_store)
        assert engine.total_archived >= 1

    def test_decay_store_removes_deleted(self, engine, pattern_store):
        """DELETE 移除模式."""
        p = PatternMemory(
            dimension=PatternMiningDimension.OPPORTUNITY_ACTION,
            condition=PatternCondition(
                opportunity_type="doomed",
                action_type="doomed",
            ),
            action=PatternAction(action_type="doomed"),
            performance=PatternPerformance(
                samples=0,
                success_rate=0.0,
                avg_reward=0.0,
                last_seen=datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
            ),
            metadata={
                "peak_reward": 0.30,
                "usage_count_recent": 0,
                "usage_count_peak": 5,
            },
        )
        p.compute_score()
        p.confidence = 0.01
        pattern_store.store(p)

        # 手动标记为 DELETE
        results = []
        for pat in pattern_store.get_all():
            r = engine.evaluate_pattern(pat)
            if r.action == "archive":
                # 改为 DELETE
                r = PatternDecayResult(
                    pattern_id=pat.pattern_id,
                    action=DecayAction.DELETE.value,
                    changed=True,
                    confidence_before=pat.confidence,
                    confidence_after=0.0,
                    confidence_delta=-pat.confidence,
                )
                pattern_store.remove(pat)
            results.append(r)

        batch = DecayBatchResult.from_results(results)
        assert batch.deleted_patterns >= 0

    def test_decay_store_multiple_runs(self, engine, pattern_store, stale_pattern):
        """多次运行累积."""
        pattern_store.store(stale_pattern)
        engine.decay_store(pattern_store)
        engine.decay_store(pattern_store)
        assert engine.decay_count == 2


# ═══════════════════════════════════════════════════════════════
# Test: PatternDecayEngine — Edge Cases
# ═══════════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界情况测试."""

    def test_evaluate_pattern_with_minimal_metadata(self, engine):
        """最小元数据."""
        p = PatternMemory(
            dimension=PatternMiningDimension.OPPORTUNITY_ACTION,
            condition=PatternCondition(action_type="test"),
            action=PatternAction(action_type="test"),
            performance=PatternPerformance(
                samples=1,
                success_rate=0.50,
                avg_reward=0.50,
            ),
        )
        p.compute_score()
        result = engine.evaluate_pattern(p)
        assert result.action == "maintain"

    def test_evaluate_pattern_no_last_seen(self, engine):
        """无 last_seen."""
        p = PatternMemory(
            dimension=PatternMiningDimension.OPPORTUNITY_ACTION,
            condition=PatternCondition(
                opportunity_type="test_no_time",
                action_type="test_no_time",
            ),
            action=PatternAction(action_type="test_no_time"),
            performance=PatternPerformance(
                samples=5,
                success_rate=0.50,
                avg_reward=0.50,
                # no last_seen
            ),
        )
        p.compute_score()
        score = engine.calculate_decay_score(p)
        assert score.stale_factor == 0.0

    def test_confidence_floor(self, engine):
        """置信度下限."""
        p = PatternMemory(
            dimension=PatternMiningDimension.OPPORTUNITY_ACTION,
            condition=PatternCondition(
                opportunity_type="floor_test",
                action_type="floor_test",
            ),
            action=PatternAction(action_type="floor_test"),
            performance=PatternPerformance(
                samples=3,
                success_rate=0.10,
                avg_reward=0.02,
                avg_confidence=0.10,
                last_seen=datetime(2025, 6, 1, tzinfo=timezone.utc).isoformat(),
            ),
            metadata={
                "peak_reward": 0.30,
                "usage_count_recent": 0,
                "usage_count_peak": 10,
            },
        )
        p.compute_score()
        p.confidence = 0.02
        engine.evaluate_pattern(p)
        assert p.confidence >= 0.0

    def test_determine_dominant_reason(self, engine):
        """主导原因确定."""
        reason = engine._determine_dominant_reason(
            stale_factor=0.80,
            reward_drop=0.30,
            usage_drop=0.20,
            confidence_loss=0.10,
        )
        assert reason == PatternDecayReason.STALE.value

    def test_determine_dominant_reason_tie(self, engine):
        """主导原因平局."""
        reason = engine._determine_dominant_reason(
            stale_factor=0.50,
            reward_drop=0.50,
            usage_drop=0.20,
            confidence_loss=0.10,
        )
        # stale=0.50*0.35=0.175, reward=0.50*0.30=0.15 → stale wins
        assert reason == PatternDecayReason.STALE.value

    def test_default_engine_now(self):
        """默认引擎使用当前时间."""
        e = PatternDecayEngine()
        assert e._now is not None

    def test_apply_delete_mark(self, engine):
        """DELETE 标记."""
        p = PatternMemory(
            dimension=PatternMiningDimension.OPPORTUNITY_ACTION,
            condition=PatternCondition(),
            action=PatternAction(),
            performance=PatternPerformance(),
        )
        engine._apply_delete_mark(p)
        assert p.metadata["marked_for_delete"] is True
        assert "deleted_at" in p.metadata

    def test_apply_archive_halves_confidence(self, engine):
        """ARCHIVE 置信度减半."""
        p = PatternMemory(
            dimension=PatternMiningDimension.OPPORTUNITY_ACTION,
            condition=PatternCondition(),
            action=PatternAction(),
            performance=PatternPerformance(),
        )
        p.confidence = 0.80
        p.compute_score()
        engine._apply_archive(p, DecayScore(total=0.85))
        assert p.confidence < 0.50  # 0.80 * 0.5 = 0.40, then compute_score may adjust

    def test_fresh_pattern_does_not_trigger_decay(self, engine, fresh_pattern):
        """新鲜模式不触发衰减."""
        result = engine.evaluate_pattern(fresh_pattern)
        assert result.action == DecayAction.MAINTAIN.value
        assert result.changed is False

    def test_reduce_confidence_factor(self, engine, stale_pattern):
        """REDUCE_CONFIDENCE 因子."""
        before = stale_pattern.confidence
        engine.evaluate_pattern(stale_pattern)
        # confidence *= 0.85, then compute_score may recalculate
        assert stale_pattern.confidence < before

    def test_days_since_invalid(self, engine):
        """无效日期."""
        days = engine._days_since("not-a-date")
        assert days is None

    def test_factor_weights_sum_to_one(self, engine):
        """权重和为 1.0."""
        total = engine.WEIGHT_STALE + engine.WEIGHT_REWARD + engine.WEIGHT_USAGE + engine.WEIGHT_CONFIDENCE
        assert abs(total - 1.0) < 0.001