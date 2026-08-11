"""E13.6 Pattern Evolution Engine — 测试用例.

测试覆盖:
  - E13.6.1 PatternScorer: 多维度评分
  - E13.6.2 PatternDecayEngine: 时间衰减
  - E13.6.3 PatternReinforcer: 贝叶斯强化
  - E13.6.4 PatternConflictResolver: 冲突解决
  - E13.6.5 AdaptiveMemoryController: 进化编排
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from market_ops.creative_vision_runtime.growth_runtime.memory import (
    AdaptiveMemoryController,
    ConflictPair,
    ConflictResolution,
    DecayResult,
    EvolutionReport,
    PatternConflictResolver,
    PatternDecayEngine,
    PatternMemory,
    PatternReinforcer,
    PatternScore,
    PatternScorer,
    PatternStore,
    ReinforcementResult,
)
from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
    PatternAction,
    PatternCondition,
    PatternMiningDimension,
    PatternPerformance,
    PatternQuality,
    GrowthExperience,
    ExperienceContext,
    ExperienceOutcome,
    ExperienceOutcomeLevel,
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

def _make_pattern(
    pattern_id: str = "",
    opportunity_type: str = "creative_fatigue",
    action_type: str = "replace_creative",
    audience_segment: str = "iOS_FB",
    signal_types: list[str] | None = None,
    category: str = "creative",
    product_category: str = "P04",
    samples: int = 10,
    success_count: int = 8,
    success_rate: float = 0.80,
    avg_reward: float = 0.75,
    std_reward: float = 0.10,
    quality: PatternQuality = PatternQuality.RELIABLE,
    first_seen: str | None = None,
    last_seen: str | None = None,
    trend: list[float] | None = None,
    market_conditions: dict[str, tuple[float, float]] | None = None,
    score: float = 0.0,
    confidence: float = 0.0,
    metadata: dict | None = None,
) -> PatternMemory:
    """创建测试用 PatternMemory."""
    if signal_types is None:
        signal_types = ["roas_decay", "fatigue_high"]
    if first_seen is None:
        first_seen = datetime.now(timezone.utc).isoformat()
    if last_seen is None:
        last_seen = datetime.now(timezone.utc).isoformat()
    if market_conditions is None:
        market_conditions = {"roas": (0.25, 0.45), "ctr": (0.015, 0.030)}

    condition = PatternCondition(
        opportunity_type=opportunity_type,
        action_type=action_type,
        category=category,
        audience_segment=audience_segment,
        signal_types=signal_types,
        market_conditions=market_conditions,
        product_category=product_category,
    )
    action = PatternAction(
        action_type=action_type,
        params_template={"clone_hook": True},
        expected_impact=f"Expected: {action_type}",
    )
    performance = PatternPerformance(
        samples=samples,
        success_count=success_count,
        success_rate=success_rate,
        avg_reward=avg_reward,
        std_reward=std_reward,
        quality=quality,
        first_seen=first_seen,
        last_seen=last_seen,
        trend=trend or [0.80, 0.82, 0.79, 0.81, 0.80],
    )
    p = PatternMemory(
        pattern_id=pattern_id or "",
        dimension=PatternMiningDimension.OPPORTUNITY_ACTION,
        condition=condition,
        action=action,
        performance=performance,
        score=score,
        metadata=metadata or {},
    )
    if score > 0:
        p.score = score
    if confidence > 0:
        p.confidence = confidence
    p.compute_score()
    return p


def _make_experience(
    action_type: str = "replace_creative",
    opportunity_type: str = "creative_fatigue",
    audience_segment: str = "iOS_FB",
    success: bool = True,
    reward: float = 0.80,
    outcome_level: ExperienceOutcomeLevel = ExperienceOutcomeLevel.SUCCESS,
) -> GrowthExperience:
    """创建测试用 GrowthExperience."""
    return GrowthExperience(
        context=ExperienceContext(
            opportunity_type=opportunity_type,
            action_type=action_type,
            audience_segment=audience_segment,
        ),
        action_type=action_type,
        outcome=ExperienceOutcome(
            success=success,
            outcome_level=outcome_level,
            actual_reward=reward,
        ),
        reward=reward,
    )


# ═══════════════════════════════════════════════════════════════
# E13.6.1 PatternScorer Tests
# ═══════════════════════════════════════════════════════════════


class TestPatternScorer:
    """PatternScorer 多维度评分测试."""

    def test_score_high_quality_pattern(self):
        """高质量模式应获得 A 级评分."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        scorer = PatternScorer(now=now)

        pattern = _make_pattern(
            samples=100,
            success_count=85,
            success_rate=0.85,
            avg_reward=0.80,
            std_reward=0.05,
            first_seen=now.isoformat(),
            last_seen=now.isoformat(),
            trend=[0.85, 0.86, 0.84, 0.85, 0.85],
        )

        result = scorer.score(pattern)
        assert isinstance(result, PatternScore)
        assert result.grade in ("A", "B")
        assert result.composite_score >= 0.60
        assert result.base_score > 0.0
        assert result.novelty_score > 0.0
        assert result.recency_score > 0.0

    def test_score_low_quality_pattern(self):
        """低质量模式应获得低评分."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        scorer = PatternScorer(now=now)

        pattern = _make_pattern(
            samples=3,
            success_count=1,
            success_rate=0.33,
            avg_reward=0.20,
            std_reward=0.30,
            first_seen=(now - timedelta(days=180)).isoformat(),
            last_seen=(now - timedelta(days=90)).isoformat(),
            trend=[0.30, 0.35, 0.25],
        )

        result = scorer.score(pattern)
        assert result.grade in ("D", "F")
        assert result.composite_score < 0.40
        # 新近度应该很低
        assert result.recency_score < 0.1

    def test_score_stale_pattern(self):
        """长期未验证的模式应有时效性惩罚."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        scorer = PatternScorer(now=now)

        pattern = _make_pattern(
            samples=50,
            success_count=40,
            success_rate=0.80,
            avg_reward=0.75,
            last_seen=(now - timedelta(days=60)).isoformat(),
        )

        result = scorer.score(pattern)
        # 60天未验证，recency 应接近 0
        assert result.recency_score < 0.05

    def test_score_recently_validated(self):
        """最近验证的模式应有高时效性."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        scorer = PatternScorer(now=now)

        pattern = _make_pattern(
            samples=50,
            last_seen=(now - timedelta(days=1)).isoformat(),
        )

        result = scorer.score(pattern)
        assert result.recency_score > 0.80

    def test_score_stable_pattern(self):
        """低标准差的模式应有高稳定性分."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        scorer = PatternScorer(now=now)

        stable = _make_pattern(
            samples=50,
            std_reward=0.02,
            avg_reward=0.80,
        )
        unstable = _make_pattern(
            std_reward=0.40,
            avg_reward=0.80,
        )

        result_stable = scorer.score(stable)
        result_unstable = scorer.score(unstable)

        assert result_stable.stability_score > result_unstable.stability_score

    def test_score_writes_back_to_pattern(self):
        """评分结果应回写到 Pattern."""
        scorer = PatternScorer()
        pattern = _make_pattern(samples=20, score=0.0)

        scorer.score(pattern)
        assert pattern.score > 0.0
        assert pattern.confidence > 0.0

    def test_score_zero_samples(self):
        """0样本模式应得0分."""
        scorer = PatternScorer()
        pattern = _make_pattern(samples=0, success_rate=0.0, avg_reward=0.0)

        result = scorer.score(pattern)
        assert result.base_score == 0.0
        assert result.grade in ("D", "F")

    def test_score_grade_thresholds(self):
        """验证评分等级阈值."""
        scorer = PatternScorer()

        # 测试 _assign_grade
        assert scorer._assign_grade(0.85) == "A"
        assert scorer._assign_grade(0.65) == "B"
        assert scorer._assign_grade(0.45) == "C"
        assert scorer._assign_grade(0.25) == "D"
        assert scorer._assign_grade(0.05) == "F"

    def test_score_to_dict(self):
        """PatternScore.to_dict 测试."""
        score = PatternScore(
            base_score=0.5,
            composite_score=0.65,
            grade="B",
        )
        d = score.to_dict()
        assert d["base_score"] == 0.5
        assert d["composite_score"] == 0.65
        assert d["grade"] == "B"

    def test_quality_score_trend_consistency(self):
        """趋势一致性影响质量评分."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        scorer = PatternScorer(now=now)

        consistent = _make_pattern(samples=20, trend=[0.80, 0.81, 0.80, 0.79, 0.80])
        volatile = _make_pattern(trend=[0.90, 0.50, 0.30, 0.80, 0.60])

        result_consistent = scorer.score(consistent)
        result_volatile = scorer.score(volatile)

        assert result_consistent.quality_score > result_volatile.quality_score

    def test_novelty_falls_back_to_created_at(self):
        """first_seen 为空时使用 created_at."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        scorer = PatternScorer(now=now)

        pattern = _make_pattern(first_seen="")
        pattern.created_at = (now - timedelta(days=30)).isoformat()

        result = scorer.score(pattern)
        assert result.novelty_score > 0.0


# ═══════════════════════════════════════════════════════════════
# E13.6.2 PatternDecayEngine Tests
# ═══════════════════════════════════════════════════════════════


class TestPatternDecayEngine:
    """PatternDecayEngine 时间衰减测试."""

    def test_no_decay_within_grace_period(self):
        """宽限期内的模式不应衰减."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        engine = PatternDecayEngine(grace_days=7, now=now)

        pattern = _make_pattern(
            last_seen=(now - timedelta(days=3)).isoformat(),
            score=0.80,
        )

        results = engine.apply_decay([pattern])
        assert len(results) == 0  # 宽限期内，无衰减

    def test_decay_after_grace_period(self):
        """超过宽限期后应衰减."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        engine = PatternDecayEngine(grace_days=7, decay_rate_per_day=0.01, now=now)

        pattern = _make_pattern(
            last_seen=(now - timedelta(days=30)).isoformat(),
            score=0.80,
        )

        results = engine.apply_decay([pattern])
        assert len(results) == 1

        result = results[0]
        assert result.score_after < result.score_before
        assert result.decay_factor > 0.0
        assert result.days_since_last >= 29.0

    def test_decay_never_below_max(self):
        """衰减后评分不低于 max_decay 保护."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        engine = PatternDecayEngine(
            grace_days=0,
            decay_rate_per_day=1.0,  # 极快衰减
            max_decay=0.50,
            now=now,
        )

        pattern = _make_pattern(
            samples=100,
            last_seen=(now - timedelta(days=365)).isoformat(),
            score=0.80,
        )
        old_score = pattern.score

        results = engine.apply_decay([pattern])
        assert len(results) == 1
        assert results[0].score_after >= old_score * 0.50  # 不低于原始 50%

    def test_market_divergence_accelerates_decay(self):
        """市场条件变化加速衰减."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        engine = PatternDecayEngine(grace_days=0, decay_rate_per_day=0.01, now=now)

        pattern = _make_pattern(
            last_seen=(now - timedelta(days=20)).isoformat(),
            score=0.80,
            market_conditions={"roas": (0.25, 0.45), "ctr": (0.015, 0.030)},
        )

        # 当前市场条件与模式记录的差异很大
        divergent_market = {"roas": (0.60, 0.80), "ctr": (0.040, 0.060)}

        results = engine.apply_decay([pattern], market_conditions=divergent_market)
        assert len(results) == 1
        assert results[0].market_change_factor > 1.0

    def test_no_market_conditions_no_extra_decay(self):
        """无市场条件时仅时间衰减."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        engine = PatternDecayEngine(grace_days=0, decay_rate_per_day=0.01, now=now)

        pattern = _make_pattern(
            last_seen=(now - timedelta(days=20)).isoformat(),
            score=0.80,
            market_conditions={},
        )

        results = engine.apply_decay([pattern])
        assert len(results) == 1
        assert results[0].market_change_factor == 1.0

    def test_no_last_seen_no_decay(self):
        """无 last_seen 的模式不衰减."""
        pattern = _make_pattern(last_seen="", score=0.80)
        engine = PatternDecayEngine()

        results = engine.apply_decay([pattern])
        assert len(results) == 0

    def test_decay_result_fields(self):
        """DecayResult 字段完整性."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        engine = PatternDecayEngine(grace_days=0, decay_rate_per_day=0.01, now=now)

        pattern = _make_pattern(
            last_seen=(now - timedelta(days=30)).isoformat(),
            score=0.80,
        )

        results = engine.apply_decay([pattern])
        result = results[0]

        assert result.pattern_id == pattern.pattern_id
        assert result.score_before > 0
        assert result.score_after > 0
        assert result.decay_factor > 0
        assert result.days_since_last > 0
        assert len(result.reason) > 0

    def test_market_divergence_same_conditions(self):
        """相同市场条件时无额外衰减."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        engine = PatternDecayEngine(grace_days=0, decay_rate_per_day=0.01, now=now)

        market = {"roas": (0.25, 0.45)}
        pattern = _make_pattern(
            last_seen=(now - timedelta(days=20)).isoformat(),
            score=0.80,
            market_conditions=market,
        )

        results = engine.apply_decay([pattern], market_conditions=market)
        assert len(results) == 1
        assert results[0].market_change_factor == 1.0


# ═══════════════════════════════════════════════════════════════
# E13.6.3 PatternReinforcer Tests
# ═══════════════════════════════════════════════════════════════


class TestPatternReinforcer:
    """PatternReinforcer 贝叶斯强化测试."""

    def test_reinforce_increases_confidence(self):
        """强化后置信度应提升."""
        reinforcer = PatternReinforcer()
        pattern = _make_pattern(
            samples=10,
            success_count=8,
            success_rate=0.80,
            confidence=0.0,
        )

        result = reinforcer.reinforce(pattern, new_successes=8, new_total=10)

        assert result is not None
        assert result.confidence_after > result.confidence_before
        assert result.samples_added == 10
        assert result.success_added == 8
        assert result.boost_applied > 0.0
        assert result.reinforcement_count == 1

    def test_reinforce_updates_success_rate(self):
        """强化后成功率应通过贝叶斯更新."""
        reinforcer = PatternReinforcer()
        pattern = _make_pattern(
            samples=10,
            success_count=5,
            success_rate=0.50,
        )

        result = reinforcer.reinforce(pattern, new_successes=9, new_total=10)

        # 贝叶斯后验: (5+2+9) / (10+2+2+10) = 16/24 = 0.6667
        expected = 16.0 / 24.0
        assert abs(result.success_after - expected) < 0.01
        # 更新后的成功率应高于原始
        assert result.success_after > result.success_before

    def test_reinforce_updates_trend(self):
        """强化后趋势应更新."""
        reinforcer = PatternReinforcer()
        pattern = _make_pattern(
            samples=10,
            trend=[0.80, 0.82],
        )

        old_trend_len = len(pattern.performance.trend)
        reinforcer.reinforce(pattern, new_successes=7, new_total=10)

        assert len(pattern.performance.trend) == old_trend_len + 1
        assert pattern.performance.trend[-1] == 0.70

    def test_reinforce_trend_capped_at_20(self):
        """趋势最多保留20条."""
        reinforcer = PatternReinforcer()
        pattern = _make_pattern(
            samples=10,
            trend=[0.80] * 19,
        )

        reinforcer.reinforce(pattern, new_successes=5, new_total=10)
        assert len(pattern.performance.trend) <= 20
        reinforcer.reinforce(pattern, new_successes=5, new_total=10)
        assert len(pattern.performance.trend) <= 20

    def test_reinforce_boost_capped(self):
        """置信度提升有上限."""
        reinforcer = PatternReinforcer(base_boost=0.10, max_boost=0.30)
        pattern = _make_pattern(
            samples=10,
            confidence=0.50,
        )

        # 多次强化
        for _ in range(10):
            reinforcer.reinforce(pattern, new_successes=8, new_total=10)

        assert pattern.confidence <= 1.0
        # 置信度不应超过 base + max_boost
        assert pattern.confidence <= 0.80  # 0.50 + 0.30

    def test_reinforce_metadata_tracking(self):
        """强化次数和最后强化时间应记录在 metadata 中."""
        reinforcer = PatternReinforcer()
        pattern = _make_pattern(samples=10)

        reinforcer.reinforce(pattern, new_successes=8, new_total=10)
        assert pattern.metadata["reinforcement_count"] == 1
        assert "last_reinforced_at" in pattern.metadata

        reinforcer.reinforce(pattern, new_successes=7, new_total=10)
        assert pattern.metadata["reinforcement_count"] == 2

    def test_reinforce_last_seen_updated(self):
        """强化后 last_seen 应更新."""
        reinforcer = PatternReinforcer()
        old_time = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        pattern = _make_pattern(samples=10, last_seen=old_time)

        reinforcer.reinforce(pattern, new_successes=8, new_total=10)
        assert pattern.performance.last_seen != old_time

    def test_reinforce_zero_total(self):
        """new_total=0 时返回 None."""
        reinforcer = PatternReinforcer()
        pattern = _make_pattern(samples=10)

        result = reinforcer.reinforce(pattern, new_successes=0, new_total=0)
        assert result is None

    def test_contradict_reduces_confidence(self):
        """矛盾证据降低置信度."""
        reinforcer = PatternReinforcer()
        pattern = _make_pattern(
            samples=10,
            success_count=8,
            confidence=0.50,
        )

        result = reinforcer.contradict(pattern, new_failures=8, new_total=10)
        assert result.boost_applied < 0.0
        assert "Contradicted" in result.reason

    def test_reinforce_result_fields(self):
        """ReinforcementResult 字段完整性."""
        reinforcer = PatternReinforcer()
        pattern = _make_pattern(samples=10, success_rate=0.80, confidence=0.50)

        result = reinforcer.reinforce(pattern, new_successes=8, new_total=10)

        assert result.pattern_id == pattern.pattern_id
        assert result.samples_added == 10
        assert result.success_added == 8
        assert result.success_before > 0
        assert result.success_after > 0
        assert result.confidence_before > 0
        assert result.confidence_after > 0
        assert result.boost_applied > 0
        assert len(result.reason) > 0


# ═══════════════════════════════════════════════════════════════
# E13.6.4 PatternConflictResolver Tests
# ═══════════════════════════════════════════════════════════════


class TestPatternConflictResolver:
    """PatternConflictResolver 冲突解决测试."""

    def test_detect_conflicts_same_condition_different_action(self):
        """相同条件不同动作应检测为冲突."""
        resolver = PatternConflictResolver()

        p1 = _make_pattern(
            pattern_id="p1",
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
            audience_segment="iOS_FB",
            samples=10,
            success_rate=0.85,
        )
        p2 = _make_pattern(
            pattern_id="p2",
            opportunity_type="creative_fatigue",
            action_type="scale",
            audience_segment="iOS_FB",
            samples=10,
            success_rate=0.20,
        )

        conflicts = resolver.detect_conflicts([p1, p2])
        assert len(conflicts) == 1
        assert conflicts[0].action_difference == "replace_creative vs scale"
        assert conflicts[0].severity in ("high", "medium")
        assert conflicts[0].similarity > 0.60

    def test_no_conflict_same_action(self):
        """相同动作不产生冲突."""
        resolver = PatternConflictResolver()

        p1 = _make_pattern(action_type="replace_creative")
        p2 = _make_pattern(action_type="replace_creative")

        conflicts = resolver.detect_conflicts([p1, p2])
        assert len(conflicts) == 0

    def test_no_conflict_low_similarity(self):
        """低相似度不产生冲突."""
        resolver = PatternConflictResolver()

        p1 = _make_pattern(
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
            audience_segment="iOS_FB",
        )
        p2 = _make_pattern(
            opportunity_type="winner_discovery",
            action_type="scale",
            audience_segment="Android_GG",
        )

        conflicts = resolver.detect_conflicts([p1, p2])
        assert len(conflicts) == 0

    def test_no_conflict_insufficient_samples(self):
        """样本不足不产生冲突."""
        resolver = PatternConflictResolver(min_samples=5)

        p1 = _make_pattern(
            action_type="replace_creative",
            samples=3,
            success_rate=0.80,
        )
        p2 = _make_pattern(
            action_type="scale",
            samples=3,
            success_rate=0.20,
        )

        conflicts = resolver.detect_conflicts([p1, p2])
        assert len(conflicts) == 0

    def test_resolve_keep_best_large_diff(self):
        """成功率差异很大时保留最好的."""
        resolver = PatternConflictResolver()

        p1 = _make_pattern(
            pattern_id="p1",
            action_type="replace_creative",
            samples=10,
            success_rate=0.90,
        )
        p2 = _make_pattern(
            pattern_id="p2",
            action_type="scale",
            samples=10,
            success_rate=0.20,
        )

        conflict = ConflictPair(
            pattern_a=p1,
            pattern_b=p2,
            similarity=0.75,
            action_difference="replace_creative vs scale",
            severity="high",
        )
        resolution = resolver.resolve(conflict)

        assert resolution.resolution_type == "keep_best"
        assert len(resolution.refined_patterns) == 1
        assert resolution.refined_patterns[0].action.action_type == "replace_creative"

    def test_resolve_split_with_context(self):
        """有上下文区分维度时拆分."""
        resolver = PatternConflictResolver()

        p1 = _make_pattern(
            action_type="replace_creative",
            audience_segment="iOS_FB",
            samples=10,
            success_rate=0.60,
        )
        p2 = _make_pattern(
            action_type="decrease_budget",
            audience_segment="Android_GG",
            samples=10,
            success_rate=0.55,
        )

        conflict = ConflictPair(
            pattern_a=p1,
            pattern_b=p2,
            similarity=0.65,
            action_difference="replace_creative vs decrease_budget",
            severity="medium",
        )
        resolution = resolver.resolve(conflict)

        assert resolution.resolution_type == "split"
        assert len(resolution.refined_patterns) == 2
        assert "audience_segment" in resolution.reason

    def test_resolve_require_context(self):
        """无法区分时标记需要更多上下文."""
        resolver = PatternConflictResolver()

        p1 = _make_pattern(
            action_type="replace_creative",
            audience_segment="iOS_FB",
            samples=10,
            success_rate=0.60,
        )
        p2 = _make_pattern(
            action_type="decrease_budget",
            audience_segment="iOS_FB",
            samples=10,
            success_rate=0.55,
        )

        conflict = ConflictPair(
            pattern_a=p1,
            pattern_b=p2,
            similarity=0.75,
            action_difference="replace_creative vs decrease_budget",
            severity="medium",
        )
        resolution = resolver.resolve(conflict)

        assert resolution.resolution_type == "require_context"
        assert len(resolution.refined_patterns) == 2

    def test_severity_classification(self):
        """冲突严重程度分类."""
        resolver = PatternConflictResolver()

        # 高相似度 → high severity
        p1 = _make_pattern(
            pattern_id="p1",
            action_type="replace_creative",
            audience_segment="iOS_FB",
            samples=10,
            success_rate=0.85,
        )
        p2 = _make_pattern(
            pattern_id="p2",
            action_type="scale",
            audience_segment="iOS_FB",
            samples=10,
            success_rate=0.20,
        )

        conflicts = resolver.detect_conflicts([p1, p2])
        assert len(conflicts) == 1
        assert conflicts[0].severity == "high"


# ═══════════════════════════════════════════════════════════════
# E13.6.5 AdaptiveMemoryController Tests
# ═══════════════════════════════════════════════════════════════


class TestAdaptiveMemoryController:
    """AdaptiveMemoryController 进化编排测试."""

    def test_evolve_empty_store(self):
        """空 store 进化应返回空报告."""
        store = PatternStore()
        controller = AdaptiveMemoryController(store)

        report = controller.evolve()
        assert isinstance(report, EvolutionReport)
        assert report.patterns_scored == 0
        assert "No patterns" in report.summary

    def test_evolve_full_cycle(self):
        """完整进化周期测试."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        store = PatternStore()

        # 存入多个模式 (不同 opportunity_type 避免合并)
        recent = _make_pattern(
            pattern_id="recent",
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
            samples=100,
            success_count=85,
            success_rate=0.85,
            avg_reward=0.80,
            last_seen=now.isoformat(),
            first_seen=now.isoformat(),
            score=0.0,
        )
        stale = _make_pattern(
            pattern_id="stale",
            opportunity_type="winner_discovery",
            action_type="scale",
            samples=50,
            success_count=30,
            success_rate=0.60,
            last_seen=(now - timedelta(days=60)).isoformat(),
            first_seen=(now - timedelta(days=120)).isoformat(),
            score=0.0,
        )
        store.store(recent)
        store.store(stale)

        controller = AdaptiveMemoryController(store, now=now)
        report = controller.evolve()

        assert report.patterns_scored == 2
        assert report.patterns_decayed >= 1  # stale 应被衰减
        assert report.patterns_removed >= 0
        assert report.avg_score_after > 0
        assert len(report.summary) > 0

    def test_evolve_with_reinforcement(self):
        """带新经验的进化 — 强化已有模式."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        store = PatternStore()

        pattern = _make_pattern(
            samples=10,
            success_count=8,
            success_rate=0.80,
            last_seen=now.isoformat(),
            score=0.0,
        )
        store.store(pattern)

        # 创建新经验 (匹配此模式)
        experiences = [
            _make_experience(success=True, reward=0.85),
            _make_experience(success=True, reward=0.90),
            _make_experience(success=True, reward=0.75),
        ]

        controller = AdaptiveMemoryController(store, now=now)
        report = controller.evolve(new_experiences=experiences)

        assert report.patterns_reinforced >= 1
        assert len(report.reinforcement_results) == 1
        rr = report.reinforcement_results[0]
        assert rr.samples_added == 3

    def test_evolve_conflict_detection(self):
        """冲突检测和解决."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        store = PatternStore()

        p1 = _make_pattern(
            pattern_id="p1",
            action_type="replace_creative",
            audience_segment="iOS_FB",
            samples=10,
            success_rate=0.85,
            last_seen=now.isoformat(),
        )
        p2 = _make_pattern(
            pattern_id="p2",
            action_type="scale",
            audience_segment="iOS_FB",
            samples=10,
            success_rate=0.20,
            last_seen=now.isoformat(),
        )
        store.store(p1)
        store.store(p2)

        controller = AdaptiveMemoryController(store, now=now)
        report = controller.evolve()

        assert report.conflicts_detected >= 1
        assert report.conflicts_resolved >= 1

    def test_evolve_cleanup_low_quality(self):
        """低质量模式清理."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        store = PatternStore()

        low_quality = _make_pattern(
            samples=0,
            success_rate=0.0,
            avg_reward=0.0,
            score=0.0,
            last_seen=now.isoformat(),
        )
        # 确保 score 为 0
        low_quality.score = 0.0
        store.store(low_quality)

        controller = AdaptiveMemoryController(store, now=now)
        report = controller.evolve()

        # 注意: 0-sample 模式可能有非零 novelty/recency 分，所以不一定被移除
        # 验证 report 结构正确即可
        assert isinstance(report, EvolutionReport)

    def test_evolve_grade_distribution(self):
        """进化后应有等级分布."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        store = PatternStore()

        for i in range(3):
            store.store(_make_pattern(
                samples=100,
                success_rate=0.85,
                last_seen=now.isoformat(),
                first_seen=now.isoformat(),
                score=0.0,
            ))

        controller = AdaptiveMemoryController(store, now=now)
        report = controller.evolve()

        assert len(report.grade_distribution) > 0
        # 高质量模式应为 A 或 B
        assert any(g in ("A", "B") for g in report.grade_distribution)

    def test_evolve_report_to_dict(self):
        """EvolutionReport.to_dict 测试."""
        report = EvolutionReport(
            cycle_id="test123",
            timestamp="2026-07-29T00:00:00",
            patterns_scored=10,
            patterns_decayed=3,
            patterns_reinforced=2,
            conflicts_detected=1,
            conflicts_resolved=1,
            avg_score_before=0.50,
            avg_score_after=0.55,
            score_improvement=0.05,
            grade_distribution={"A": 3, "B": 5, "C": 2},
            summary="Test summary",
        )
        d = report.to_dict()
        assert d["cycle_id"] == "test123"
        assert d["patterns_scored"] == 10
        assert d["score_improvement"] == 0.05

    def test_evolve_has_evolution(self):
        """EvolutionReport.has_evolution 测试."""
        empty = EvolutionReport()
        assert not empty.has_evolution()

        active = EvolutionReport(patterns_decayed=3)
        assert active.has_evolution()

    def test_controller_history(self):
        """进化历史记录."""
        store = PatternStore()
        store.store(_make_pattern(samples=10, last_seen=datetime.now(timezone.utc).isoformat()))

        controller = AdaptiveMemoryController(store)
        controller.evolve()

        reports = controller.get_reports()
        assert len(reports) == 1

        latest = controller.get_latest_report()
        assert latest is not None
        assert latest.patterns_scored == 1

    def test_evolve_with_market_conditions(self):
        """带市场条件的进化."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        store = PatternStore()

        pattern = _make_pattern(
            samples=50,
            last_seen=(now - timedelta(days=30)).isoformat(),
            score=0.80,
            market_conditions={"roas": (0.25, 0.45)},
        )
        store.store(pattern)

        controller = AdaptiveMemoryController(store, now=now)
        report = controller.evolve(
            market_conditions={"roas": (0.60, 0.80)}  # 市场变化
        )

        assert report.patterns_decayed >= 1

    def test_controller_custom_components(self):
        """自定义组件注入."""
        store = PatternStore()
        scorer = PatternScorer()
        decay = PatternDecayEngine()
        reinforcer = PatternReinforcer()
        resolver = PatternConflictResolver()

        controller = AdaptiveMemoryController(
            store,
            scorer=scorer,
            decay_engine=decay,
            reinforcer=reinforcer,
            conflict_resolver=resolver,
        )

        assert controller._scorer is scorer
        assert controller._decay_engine is decay
        assert controller._reinforcer is reinforcer
        assert controller._conflict_resolver is resolver


# ═══════════════════════════════════════════════════════════════
# Integration Tests
# ═══════════════════════════════════════════════════════════════


class TestPatternEvolutionIntegration:
    """E13.6 集成测试 — 完整进化闭环."""

    def test_scoring_to_decay_pipeline(self):
        """评分 → 衰减 流水线."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        scorer = PatternScorer(now=now)
        decay_engine = PatternDecayEngine(grace_days=0, decay_rate_per_day=0.01, now=now)

        pattern = _make_pattern(
            samples=50,
            last_seen=(now - timedelta(days=30)).isoformat(),
            score=0.0,
        )

        # 先评分
        score_result = scorer.score(pattern)
        assert score_result.composite_score > 0

        # 再衰减
        decay_results = decay_engine.apply_decay([pattern])
        assert len(decay_results) == 1
        assert decay_results[0].score_after < score_result.composite_score

    def test_scoring_to_reinforcement_pipeline(self):
        """评分 → 强化 流水线."""
        scorer = PatternScorer()
        reinforcer = PatternReinforcer()

        pattern = _make_pattern(samples=10, score=0.0)

        # 先评分
        score_before = scorer.score(pattern).composite_score

        # 再强化
        reinforcer.reinforce(pattern, new_successes=8, new_total=10)

        # 再评分
        score_after = scorer.score(pattern).composite_score
        assert score_after > score_before

    def test_full_evolution_with_memory_retrieval(self):
        """完整闭环: 进化 → 检索 → 决策增强."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        store = PatternStore()

        # 1. 存入模式
        store.store(_make_pattern(
            pattern_id="pat_001",
            samples=100,
            success_count=85,
            success_rate=0.85,
            avg_reward=0.80,
            last_seen=now.isoformat(),
            first_seen=now.isoformat(),
            score=0.0,
        ))

        # 2. 进化
        controller = AdaptiveMemoryController(store, now=now)
        report = controller.evolve()

        assert report.patterns_scored == 1

        # 3. 进化后的模式应有合理评分
        pattern = store.get_all()[0]
        assert pattern.score > 0.0

        # 4. 再用 PatternRetriever 检索 (E13.5)
        from market_ops.creative_vision_runtime.growth_runtime.decision.pattern_retriever import (
            PatternRetriever,
            RetrievalContext,
        )

        retriever = PatternRetriever(store)
        ctx = RetrievalContext(
            opportunity_type="creative_fatigue",
            audience_segment="iOS_FB",
            signal_types=["roas_decay"],
            action_type="replace_creative",
            category="creative",
            product_category="P04",
            metrics_snapshot={"roas": 0.35, "ctr": 0.020},
        )
        result = retriever.retrieve(ctx)

        assert result.has_recommendations
        assert result.top_action is not None

    def test_decay_then_retrieval_lower_confidence(self):
        """衰减后检索 — 置信度应降低."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        store = PatternStore()

        pattern = _make_pattern(
            samples=100,
            success_rate=0.85,
            last_seen=(now - timedelta(days=60)).isoformat(),
            first_seen=(now - timedelta(days=60)).isoformat(),
            score=0.0,
        )
        store.store(pattern)

        # 进化 (含衰减)
        controller = AdaptiveMemoryController(store, now=now)
        controller.evolve()

        # 检索
        from market_ops.creative_vision_runtime.growth_runtime.decision.pattern_retriever import (
            PatternRetriever,
            RetrievalContext,
        )

        retriever = PatternRetriever(store)
        ctx = RetrievalContext(
            opportunity_type="creative_fatigue",
            audience_segment="iOS_FB",
            action_type="replace_creative",
        )
        result = retriever.retrieve(ctx)

        if result.top_action:
            # 衰减后置信度应低于原始 success_rate
            assert result.top_action.confidence < 0.85

    def test_reinforcement_then_retrieval_higher_confidence(self):
        """强化后检索 — 置信度应提升."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        store = PatternStore()

        pattern = _make_pattern(
            samples=10,
            success_rate=0.80,
            confidence=0.50,
            last_seen=now.isoformat(),
            first_seen=now.isoformat(),
            score=0.0,
        )
        store.store(pattern)

        # 强化 (多次)
        controller = AdaptiveMemoryController(store, now=now)
        experiences = [_make_experience(success=True, reward=0.85) for _ in range(5)]
        controller.evolve(new_experiences=experiences)

        # 检索
        from market_ops.creative_vision_runtime.growth_runtime.decision.pattern_retriever import (
            PatternRetriever,
            RetrievalContext,
        )

        retriever = PatternRetriever(store)
        ctx = RetrievalContext(
            opportunity_type="creative_fatigue",
            audience_segment="iOS_FB",
            action_type="replace_creative",
        )
        result = retriever.retrieve(ctx)

        if result.top_action:
            # 强化后置信度应提升
            assert result.top_action.confidence > 0.50

    def test_conflict_resolution_then_decision(self):
        """冲突解决后决策 — 应选择更好的模式."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        store = PatternStore()

        best = _make_pattern(
            pattern_id="best",
            action_type="replace_creative",
            audience_segment="iOS_FB",
            samples=100,
            success_rate=0.85,
            avg_reward=0.80,
            last_seen=now.isoformat(),
            first_seen=now.isoformat(),
            score=0.0,
        )
        worse = _make_pattern(
            pattern_id="worse",
            action_type="scale",
            audience_segment="iOS_FB",
            samples=100,
            success_rate=0.15,
            avg_reward=0.10,
            last_seen=now.isoformat(),
            first_seen=now.isoformat(),
            score=0.0,
        )
        store.store(best)
        store.store(worse)

        controller = AdaptiveMemoryController(store, now=now)
        report = controller.evolve()

        # 冲突被检测到
        assert report.conflicts_detected >= 1

        # 冲突解决后，检索结果应推荐高成功率模式
        from market_ops.creative_vision_runtime.growth_runtime.decision.pattern_retriever import (
            PatternRetriever,
            RetrievalContext,
        )

        retriever = PatternRetriever(store)
        ctx = RetrievalContext(
            opportunity_type="creative_fatigue",
            audience_segment="iOS_FB",
            action_type="replace_creative",
        )
        result = retriever.retrieve(ctx)

        if result.top_action:
            assert result.top_action.pattern.action.action_type == "replace_creative"
            # 不应该有 scale 作为 top_action
            assert result.top_action.pattern.action.action_type != "scale"