"""E13.6 Pattern Feedback Loop — 测试用例.

测试覆盖:
  - PatternEvaluator:       模式有效性评估
  - PatternRewardUpdater:   执行结果奖励更新
  - PatternLifecycleManager: 生命周期管理
  - 集成: 完整反馈回路
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from market_ops.creative_vision_runtime.growth_runtime.memory import (
    EvaluationResult,
    LifecycleReport,
    LifecycleTransition,
    PatternEffectiveness,
    PatternEvaluator,
    PatternLifecycleManager,
    PatternLifecycleState,
    PatternMemory,
    PatternRewardUpdater,
    RewardSignal,
    RewardUpdateResult,
)
from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
    ExperienceContext,
    ExperienceOutcome,
    ExperienceOutcomeLevel,
    GrowthExperience,
    PatternAction,
    PatternCondition,
    PatternMiningDimension,
    PatternPerformance,
    PatternQuality,
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

def _make_pattern(
    pattern_id: str = "",
    opportunity_type: str = "creative_fatigue",
    action_type: str = "replace_creative",
    audience_segment: str = "iOS_FB",
    samples: int = 100,
    success_count: int = 82,
    success_rate: float = 0.82,
    avg_reward: float = 0.75,
    last_seen: str | None = None,
    score: float = 0.0,
    confidence: float = 0.91,
    metadata: dict | None = None,
) -> PatternMemory:
    """创建测试用 PatternMemory."""
    if last_seen is None:
        last_seen = datetime.now(timezone.utc).isoformat()
    return PatternMemory(
        pattern_id=pattern_id or f"pat_{hash(opportunity_type) % 10000:04d}",
        dimension=PatternMiningDimension.OPPORTUNITY_ACTION,
        condition=PatternCondition(
            opportunity_type=opportunity_type,
            action_type=action_type,
            audience_segment=audience_segment,
            category="creative",
            signal_types=["roas_decay", "fatigue_high"],
        ),
        action=PatternAction(action_type=action_type),
        performance=PatternPerformance(
            samples=samples,
            success_count=success_count,
            success_rate=success_rate,
            avg_reward=avg_reward,
            first_seen=datetime.now(timezone.utc).isoformat(),
            last_seen=last_seen,
        ),
        score=score,
        confidence=confidence,
        metadata=metadata or {},
    )


def _make_experience(
    action_type: str = "replace_creative",
    opportunity_type: str = "creative_fatigue",
    audience_segment: str = "iOS_FB",
    success: bool = True,
    outcome_level: ExperienceOutcomeLevel = ExperienceOutcomeLevel.SUCCESS,
    reward: float = 0.8,
    metrics_delta: dict | None = None,
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
            metrics_delta=metrics_delta or {},
        ),
        reward=reward,
    )


def _make_outcome(
    success: bool = True,
    metrics_delta: dict | None = None,
) -> ExperienceOutcome:
    """创建测试用 ExperienceOutcome."""
    return ExperienceOutcome(
        success=success,
        outcome_level=ExperienceOutcomeLevel.SUCCESS if success else ExperienceOutcomeLevel.FAILURE,
        actual_reward=0.8 if success else 0.0,
        metrics_delta=metrics_delta or {},
    )


# ═══════════════════════════════════════════════════════════════
# PatternEvaluator Tests
# ═══════════════════════════════════════════════════════════════

class TestPatternEvaluator:
    """PatternEvaluator — 模式有效性评估."""

    def test_evaluate_strong_pattern(self):
        """最近成功率高于历史，应评估为 STRONG."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        evaluator = PatternEvaluator(now=now)

        pattern = _make_pattern(
            success_rate=0.82,
            confidence=0.91,
        )

        # 最近 20 次经验，18 次成功
        experiences = [
            _make_experience(success=True) for _ in range(18)
        ] + [
            _make_experience(success=False) for _ in range(2)
        ]

        result = evaluator.evaluate(pattern, experiences)
        assert result.effectiveness == PatternEffectiveness.STRONG
        assert result.recent_success_rate == 0.90
        assert result.confidence_adjustment > 0
        assert result.should_update is False

    def test_evaluate_maintaining_pattern(self):
        """最近成功率接近历史，应评估为 MAINTAINING."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        evaluator = PatternEvaluator(now=now)

        pattern = _make_pattern(success_rate=0.82)

        # 最近 20 次，14 次成功 (70%)
        experiences = [
            _make_experience(success=True) for _ in range(14)
        ] + [
            _make_experience(success=False) for _ in range(6)
        ]

        result = evaluator.evaluate(pattern, experiences)
        assert result.effectiveness == PatternEffectiveness.MAINTAINING
        assert result.confidence_adjustment == 0.0

    def test_evaluate_weakening_pattern(self):
        """最近成功率明显下降，应评估为 WEAKENING."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        evaluator = PatternEvaluator(now=now)

        pattern = _make_pattern(success_rate=0.82)

        # 最近 20 次，10 次成功 (50%) → ratio=0.50/0.82=0.61 → WEAKENING
        experiences = [
            _make_experience(success=True) for _ in range(10)
        ] + [
            _make_experience(success=False) for _ in range(10)
        ]

        result = evaluator.evaluate(pattern, experiences)
        assert result.effectiveness == PatternEffectiveness.WEAKENING
        assert result.confidence_adjustment < 0
        assert result.should_update is True

    def test_evaluate_failing_pattern(self):
        """最近成功率极低，应评估为 FAILING."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        evaluator = PatternEvaluator(now=now)

        pattern = _make_pattern(success_rate=0.82)

        # 最近 20 次，仅 5 次成功 (25%)
        experiences = [
            _make_experience(success=True) for _ in range(5)
        ] + [
            _make_experience(success=False) for _ in range(15)
        ]

        result = evaluator.evaluate(pattern, experiences)
        assert result.effectiveness == PatternEffectiveness.FAILING
        assert result.confidence_adjustment < -0.15
        assert result.should_update is True

    def test_evaluate_expired_pattern(self):
        """超过 90 天未验证，应评估为 EXPIRED."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        evaluator = PatternEvaluator(now=now)

        old_date = (now - timedelta(days=120)).isoformat()
        pattern = _make_pattern(
            success_rate=0.82,
            last_seen=old_date,
        )

        # 没有最近经验
        result = evaluator.evaluate(pattern, [])
        assert result.effectiveness == PatternEffectiveness.EXPIRED
        assert result.should_update is True
        assert result.confidence_adjustment == -0.30

    def test_evaluate_insufficient_recent_samples(self):
        """最近样本不足，不应判定为过期."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        evaluator = PatternEvaluator(now=now)

        pattern = _make_pattern(success_rate=0.82)

        # 只有 3 个样本 (不足 min_recent_samples=5)
        experiences = [
            _make_experience(success=True) for _ in range(3)
        ]

        result = evaluator.evaluate(pattern, experiences)
        assert result.effectiveness == PatternEffectiveness.MAINTAINING
        assert result.should_update is False

    def test_apply_evaluation_updates_confidence(self):
        """apply_evaluation 应更新模式置信度和成功率."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        evaluator = PatternEvaluator(now=now)

        pattern = _make_pattern(
            success_rate=0.82,
            confidence=0.91,
        )

        # 失败模式
        experiences = [
            _make_experience(success=True) for _ in range(5)
        ] + [
            _make_experience(success=False) for _ in range(15)
        ]

        result = evaluator.evaluate(pattern, experiences)
        assert result.should_update is True

        updated = evaluator.apply_evaluation(pattern, result)
        assert updated.confidence < 0.91  # 被降低了
        assert "last_evaluation" in updated.metadata

    def test_filter_matching_experiences(self):
        """应只筛选匹配模式的执行经验."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        evaluator = PatternEvaluator(now=now)

        pattern = _make_pattern(
            action_type="replace_creative",
            opportunity_type="creative_fatigue",
            audience_segment="iOS_FB",
        )

        experiences = [
            _make_experience(action_type="replace_creative", opportunity_type="creative_fatigue"),  # match
            _make_experience(action_type="scale", opportunity_type="creative_fatigue"),              # no match
            _make_experience(action_type="replace_creative", opportunity_type="winner_discovery"),   # no match
            _make_experience(action_type="replace_creative", opportunity_type="creative_fatigue"),  # match
        ]

        result = evaluator.evaluate(pattern, experiences)
        # 只有 2 个匹配，不足 min_recent_samples=5
        assert result.recent_samples < 5
        assert result.effectiveness == PatternEffectiveness.MAINTAINING

    def test_historical_rate_zero_handling(self):
        """历史成功率为 0 时不应崩溃."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        evaluator = PatternEvaluator(now=now)

        pattern = _make_pattern(success_rate=0.0, samples=0)

        experiences = [
            _make_experience(success=True) for _ in range(10)
        ]

        result = evaluator.evaluate(pattern, experiences)
        # ratio 除以 max(0, 0.01) = 0.01 → ratio 很大 → STRONG
        assert result.effectiveness == PatternEffectiveness.STRONG


# ═══════════════════════════════════════════════════════════════
# PatternRewardUpdater Tests
# ═══════════════════════════════════════════════════════════════

class TestPatternRewardUpdater:
    """PatternRewardUpdater — 执行结果奖励更新."""

    def test_compute_reward_positive_roas(self):
        """ROAS 提升应产生正奖励."""
        updater = PatternRewardUpdater()

        outcome = _make_outcome(
            success=True,
            metrics_delta={"roas": 0.30, "ctr": 0.0, "cvr": 0.0, "spend": 0.0, "payer_rate": 0.0},
        )
        signal = updater.compute_reward(outcome)
        assert signal.roas_reward > 0.0
        assert signal.total_reward > 0.0

    def test_compute_reward_failure(self):
        """执行失败应产生 -1.0 惩罚."""
        updater = PatternRewardUpdater()

        outcome = _make_outcome(
            success=False,
            metrics_delta={"roas": -0.50, "ctr": -0.10},
        )
        signal = updater.compute_reward(outcome)
        assert signal.total_reward == -1.0
        assert signal.normalized_reward == 0.0

    def test_compute_reward_all_positive(self):
        """所有指标正向变化，综合奖励应为正值."""
        updater = PatternRewardUpdater()

        outcome = _make_outcome(
            success=True,
            metrics_delta={
                "roas": 0.40,
                "ctr": 0.20,
                "cvr": 0.15,
                "spend": 0.05,
                "payer_rate": 0.25,
            },
        )
        signal = updater.compute_reward(outcome)
        assert signal.total_reward > 0.3
        assert signal.normalized_reward > 0.6

    def test_compute_reward_spend_stability(self):
        """Spend 小幅变化应视为稳定，给正奖励."""
        updater = PatternRewardUpdater()

        outcome = _make_outcome(
            success=True,
            metrics_delta={"spend": 0.05},  # 5% 变化
        )
        signal = updater.compute_reward(outcome)
        assert signal.spend_reward > 0.0

    def test_compute_reward_spend_large_fluctuation(self):
        """Spend 大幅波动应给负奖励."""
        updater = PatternRewardUpdater()

        outcome = _make_outcome(
            success=True,
            metrics_delta={"spend": 0.50},  # 50% 变化
        )
        signal = updater.compute_reward(outcome)
        assert signal.spend_reward < 0.0

    def test_update_pattern_reward(self):
        """update 应通过 EMA 更新模式的平均奖励."""
        updater = PatternRewardUpdater(ema_alpha=0.3)

        pattern = _make_pattern(avg_reward=0.75)

        outcomes = [
            _make_outcome(
                success=True,
                metrics_delta={"roas": 0.20, "ctr": 0.10, "cvr": 0.05, "payer_rate": 0.15},
            )
            for _ in range(5)
        ]

        result = updater.update(pattern, outcomes)
        assert result is not None
        assert isinstance(result, RewardUpdateResult)
        assert result.reward_before == 0.75
        assert result.reward_after != 0.75  # EMA 更新了
        assert result.samples_added == 5

    def test_update_empty_outcomes(self):
        """空 outcomes 应返回 None."""
        updater = PatternRewardUpdater()
        pattern = _make_pattern()
        result = updater.update(pattern, [])
        assert result is None

    def test_update_with_failures(self):
        """包含失败的结果应降低平均奖励."""
        updater = PatternRewardUpdater(ema_alpha=0.5)

        pattern = _make_pattern(avg_reward=0.80)

        outcomes = [
            _make_outcome(success=True, metrics_delta={"roas": 0.3}),
            _make_outcome(success=False, metrics_delta={}),
            _make_outcome(success=False, metrics_delta={}),
        ]

        result = updater.update(pattern, outcomes)
        assert result is not None
        # 由于 2/3 失败，奖励应大幅下降
        assert result.reward_after < 0.50

    def test_update_preserves_trend(self):
        """更新应将平均奖励追加到趋势 (每次 update 调用追加一条)."""
        updater = PatternRewardUpdater()

        pattern = _make_pattern(avg_reward=0.75)
        old_trend_len = len(pattern.performance.trend)

        outcomes = [
            _make_outcome(success=True, metrics_delta={"roas": 0.1})
            for _ in range(3)
        ]

        result = updater.update(pattern, outcomes)
        assert result is not None
        # update 对所有 outcomes 聚合后追加一条趋势
        assert len(pattern.performance.trend) == old_trend_len + 1

    def test_normalized_reward_range(self):
        """归一化奖励应在 [0, 1] 范围内."""
        updater = PatternRewardUpdater()

        # 多种场景
        test_cases = [
            (True, {"roas": 0.5, "ctr": 0.3, "cvr": 0.2, "spend": 0.05, "payer_rate": 0.3}),
            (True, {"roas": -0.3, "ctr": -0.2, "cvr": -0.1}),
            (False, {}),
            (True, {}),
        ]

        for success, delta in test_cases:
            outcome = _make_outcome(success=success, metrics_delta=delta)
            signal = updater.compute_reward(outcome)
            assert 0.0 <= signal.normalized_reward <= 1.0

    def test_reward_weights_customizable(self):
        """奖励权重应可自定义."""
        # 极端权重: 只看 ROAS
        updater = PatternRewardUpdater(
            weights={"roas": 1.0, "ctr": 0.0, "cvr": 0.0, "spend": 0.0, "payer": 0.0},
        )

        outcome = _make_outcome(
            success=True,
            metrics_delta={"roas": 0.5, "ctr": -0.5, "cvr": -0.5, "spend": 0.5, "payer_rate": -0.5},
        )
        signal = updater.compute_reward(outcome)
        # 只看 ROAS，所以虽然 CTR/CVR 都降了，total 还是正的
        assert signal.total_reward > 0.0


# ═══════════════════════════════════════════════════════════════
# PatternLifecycleManager Tests
# ═══════════════════════════════════════════════════════════════

class TestPatternLifecycleManager:
    """PatternLifecycleManager — 生命周期管理."""

    def test_initial_state_active(self):
        """新模式的初始状态应为 ACTIVE."""
        manager = PatternLifecycleManager()
        pattern = _make_pattern()
        assert manager._get_state(pattern) == PatternLifecycleState.ACTIVE

    def test_active_to_decaying_by_days(self):
        """超过 30 天未验证 → ACTIVE → DECAYING."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        manager = PatternLifecycleManager(now=now)

        old_date = (now - timedelta(days=45)).isoformat()
        pattern = _make_pattern(last_seen=old_date, metadata={"initial_score": 0.80})

        transition = manager.check_pattern(pattern)
        assert transition is not None
        assert transition.from_state == PatternLifecycleState.ACTIVE
        assert transition.to_state == PatternLifecycleState.DECAYING
        assert "45d" in transition.trigger or "Unused" in transition.trigger

    def test_active_to_decaying_by_score(self):
        """评分衰减至 60% 以下 → ACTIVE → DECAYING."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        manager = PatternLifecycleManager(now=now)

        pattern = _make_pattern(
            score=0.40,
            metadata={"initial_score": 0.80},  # 50% of initial
        )

        transition = manager.check_pattern(pattern)
        assert transition is not None
        assert transition.to_state == PatternLifecycleState.DECAYING
        assert "Score decayed" in transition.trigger

    def test_active_to_decaying_by_evaluation(self):
        """评估为 FAILING/EXPIRED → ACTIVE → DECAYING."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        manager = PatternLifecycleManager(now=now)

        pattern = _make_pattern(
            score=0.80,
            metadata={"initial_score": 0.80},
        )

        evaluation = EvaluationResult(
            pattern_id=pattern.pattern_id,
            effectiveness=PatternEffectiveness.FAILING,
            reason="Failing: recent 0.25 vs historical 0.82",
        )

        transition = manager.check_pattern(pattern, evaluation)
        assert transition is not None
        assert transition.to_state == PatternLifecycleState.DECAYING
        assert "Evaluation" in transition.trigger

    def test_decaying_to_active_recovery(self):
        """被重新验证为 STRONG → DECAYING → ACTIVE."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        manager = PatternLifecycleManager(now=now)

        old_date = (now - timedelta(days=40)).isoformat()
        pattern = _make_pattern(
            last_seen=old_date,
            metadata={"lifecycle_state": "decaying"},
        )

        evaluation = EvaluationResult(
            pattern_id=pattern.pattern_id,
            effectiveness=PatternEffectiveness.STRONG,
            reason="Strong: recent 0.88 vs historical 0.82",
        )

        transition = manager.check_pattern(pattern, evaluation)
        assert transition is not None
        assert transition.from_state == PatternLifecycleState.DECAYING
        assert transition.to_state == PatternLifecycleState.ACTIVE
        assert "Re-validated" in transition.trigger

    def test_decaying_to_archived_by_days(self):
        """超过 60 天未验证 → DECAYING → ARCHIVED."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        manager = PatternLifecycleManager(now=now)

        old_date = (now - timedelta(days=75)).isoformat()
        pattern = _make_pattern(
            last_seen=old_date,
            metadata={"lifecycle_state": "decaying"},
        )

        transition = manager.check_pattern(pattern)
        assert transition is not None
        assert transition.to_state == PatternLifecycleState.ARCHIVED

    def test_decaying_to_archived_by_score(self):
        """评分衰减至 30% 以下 → DECAYING → ARCHIVED."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        manager = PatternLifecycleManager(now=now)

        pattern = _make_pattern(
            score=0.15,
            metadata={
                "lifecycle_state": "decaying",
                "initial_score": 0.80,
            },
        )

        transition = manager.check_pattern(pattern)
        assert transition is not None
        assert transition.to_state == PatternLifecycleState.ARCHIVED

    def test_archived_to_active_strong_recovery(self):
        """ARCHIVED 模式被强验证 → 恢复为 ACTIVE."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        manager = PatternLifecycleManager(now=now)

        pattern = _make_pattern(
            metadata={"lifecycle_state": "archived"},
        )

        evaluation = EvaluationResult(
            pattern_id=pattern.pattern_id,
            effectiveness=PatternEffectiveness.STRONG,
            reason="Strong recovery",
        )

        transition = manager.check_pattern(pattern, evaluation)
        assert transition is not None
        assert transition.to_state == PatternLifecycleState.ACTIVE

    def test_no_transition_when_stable(self):
        """最近验证且评分正常的模式不应发生迁移."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        manager = PatternLifecycleManager(now=now)

        pattern = _make_pattern(
            score=0.80,
            metadata={"initial_score": 0.80},
        )

        transition = manager.check_pattern(pattern)
        assert transition is None

    def test_check_patterns_batch(self):
        """批量检查应正确处理多个模式."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        manager = PatternLifecycleManager(now=now)

        old_date = (now - timedelta(days=50)).isoformat()
        recent_date = now.isoformat()

        patterns = [
            _make_pattern(pattern_id="pat_001", last_seen=old_date, score=0.80, metadata={"initial_score": 0.80}),  # 应迁移
            _make_pattern(pattern_id="pat_002", last_seen=recent_date, score=0.80, metadata={"initial_score": 0.80}),  # 不应迁移
            _make_pattern(pattern_id="pat_003", last_seen=old_date, score=0.80, metadata={"initial_score": 0.80}),  # 应迁移
        ]

        transitions = manager.check_patterns(patterns)
        assert len(transitions) == 2
        assert all(t.to_state == PatternLifecycleState.DECAYING for t in transitions)

    def test_get_active_patterns(self):
        """get_active_patterns 应排除 ARCHIVED 和 DEPRECATED."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        manager = PatternLifecycleManager(now=now)

        patterns = [
            _make_pattern(pattern_id="pat_001", metadata={"lifecycle_state": "active"}),
            _make_pattern(pattern_id="pat_002", metadata={"lifecycle_state": "decaying"}),
            _make_pattern(pattern_id="pat_003", metadata={"lifecycle_state": "archived"}),
            _make_pattern(pattern_id="pat_004", metadata={"lifecycle_state": "deprecated"}),
        ]

        active = manager.get_active_patterns(patterns)
        assert len(active) == 2  # active + decaying
        active_ids = {p.pattern_id for p in active}
        assert "pat_003" not in active_ids
        assert "pat_004" not in active_ids

    def test_lifecycle_report(self):
        """生命周期报告应包含正确的状态分布."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        manager = PatternLifecycleManager(now=now)

        old_date = (now - timedelta(days=50)).isoformat()
        patterns = [
            _make_pattern(pattern_id="pat_001", last_seen=old_date),
            _make_pattern(pattern_id="pat_002", last_seen=old_date),
            _make_pattern(pattern_id="pat_003", last_seen=now.isoformat()),
        ]

        manager.check_patterns(patterns)
        report = manager.get_lifecycle_report()

        assert isinstance(report, LifecycleReport)
        assert report.patterns_checked == 3
        assert report.active_count + report.decaying_count == 3
        assert report.summary != ""

    def test_transition_updates_pattern_metadata(self):
        """状态迁移应更新 pattern.metadata."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        manager = PatternLifecycleManager(now=now)

        old_date = (now - timedelta(days=50)).isoformat()
        pattern = _make_pattern(last_seen=old_date)

        transition = manager.check_pattern(pattern)
        assert transition is not None
        assert pattern.metadata["lifecycle_state"] == "decaying"
        assert "lifecycle_transition" in pattern.metadata


# ═══════════════════════════════════════════════════════════════
# Integration Tests
# ═══════════════════════════════════════════════════════════════

class TestPatternFeedbackIntegration:
    """E13.6 反馈回路集成测试."""

    def test_full_feedback_loop(self):
        """完整反馈回路: 评估 → 奖励更新 → 生命周期检查."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)

        # 1. 创建模式
        pattern = _make_pattern(
            success_rate=0.82,
            confidence=0.91,
            avg_reward=0.75,
            metadata={"initial_score": 0.80},
        )

        # 2. 模拟近期执行结果 (部分失败)
        experiences = [
            _make_experience(success=True) for _ in range(8)
        ] + [
            _make_experience(success=False) for _ in range(12)
        ]

        outcomes = [
            _make_outcome(
                success=i < 8,
                metrics_delta={"roas": 0.1 if i < 8 else -0.3, "ctr": 0.05 if i < 8 else -0.1},
            )
            for i in range(20)
        ]

        # 3. PatternEvaluator: 评估
        evaluator = PatternEvaluator(now=now)
        eval_result = evaluator.evaluate(pattern, experiences)
        assert eval_result.effectiveness in (
            PatternEffectiveness.WEAKENING,
            PatternEffectiveness.FAILING,
        )

        # 4. Apply evaluation
        evaluator.apply_evaluation(pattern, eval_result)
        assert pattern.confidence < 0.91  # 被降低

        # 5. PatternRewardUpdater: 奖励更新
        updater = PatternRewardUpdater(now=now)
        reward_result = updater.update(pattern, outcomes)
        assert reward_result is not None
        assert reward_result.reward_after < reward_result.reward_before  # 失败多，奖励下降

        # 6. PatternLifecycleManager: 生命周期
        lifecycle = PatternLifecycleManager(now=now)
        transition = lifecycle.check_pattern(pattern, eval_result)
        if eval_result.effectiveness == PatternEffectiveness.FAILING:
            assert transition is not None
            assert transition.to_state == PatternLifecycleState.DECAYING

    def test_weakening_then_recovery_loop(self):
        """模式先减弱后恢复的完整回路."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)

        pattern = _make_pattern(
            success_rate=0.82,
            confidence=0.91,
            metadata={"initial_score": 0.80},
        )

        # Phase 1: 模式减弱
        evaluator = PatternEvaluator(now=now)
        failing_experiences = [
            _make_experience(success=True) for _ in range(5)
        ] + [
            _make_experience(success=False) for _ in range(15)
        ]

        eval1 = evaluator.evaluate(pattern, failing_experiences)
        evaluator.apply_evaluation(pattern, eval1)
        conf_after_fail = pattern.confidence

        # Phase 2: 模式恢复
        strong_experiences = [
            _make_experience(success=True) for _ in range(18)
        ] + [
            _make_experience(success=False) for _ in range(2)
        ]

        eval2 = evaluator.evaluate(pattern, strong_experiences)
        if eval2.should_update:
            evaluator.apply_evaluation(pattern, eval2)

        assert eval2.effectiveness == PatternEffectiveness.STRONG

    def test_feedback_with_experience_store(self):
        """使用 GrowthExperience 进行反馈回路."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)

        pattern = _make_pattern(
            action_type="replace_creative",
            opportunity_type="creative_fatigue",
            success_rate=0.82,
        )

        # 混合经验
        experiences = []
        for i in range(30):
            success = i < 18  # 前 18 个成功, 后 12 个失败
            exp = GrowthExperience(
                context=ExperienceContext(
                    opportunity_type="creative_fatigue",
                    action_type="replace_creative",
                    audience_segment="iOS_FB",
                ),
                action_type="replace_creative",
                outcome=ExperienceOutcome(
                    success=success,
                    outcome_level=ExperienceOutcomeLevel.SUCCESS if success else ExperienceOutcomeLevel.FAILURE,
                    actual_reward=0.8 if success else 0.0,
                    metrics_delta={"roas": 0.2 if success else -0.3},
                ),
                reward=0.8 if success else 0.0,
            )
            experiences.append(exp)

        evaluator = PatternEvaluator(now=now)
        eval_result = evaluator.evaluate(pattern, experiences)
        assert eval_result is not None
        assert eval_result.recent_samples == 20  # 默认窗口 20

    def test_evaluator_and_lifecycle_integration(self):
        """评估器与生命周期管理器集成."""
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)

        evaluator = PatternEvaluator(now=now)
        lifecycle = PatternLifecycleManager(now=now)

        patterns = []
        for i in range(5):
            # 每个模式有不同的成功率
            rate = 0.9 - i * 0.15  # 0.90, 0.75, 0.60, 0.45, 0.30
            pattern = _make_pattern(
                pattern_id=f"pat_{i:03d}",
                success_rate=rate,
                metadata={"initial_score": 0.80},
            )

            # 最近执行结果 (保持一致)
            experiences = [
                _make_experience(success=(j < int(rate * 20)))
                for j in range(20)
            ]

            eval_result = evaluator.evaluate(pattern, experiences)
            lifecycle.check_pattern(pattern, eval_result)

            patterns.append(pattern)

        report = lifecycle.get_lifecycle_report()
        assert report.patterns_checked == 5
        # 低成功率模式应进入 DECAYING
        assert report.decaying_count >= 1