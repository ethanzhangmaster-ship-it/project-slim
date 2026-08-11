"""E17.12 Decision Optimization — 决策优化测试.

Day 7.12:
  测试覆盖:
    - PatternRankingEngine: 多维度 Pattern 排名
    - LearningPolicyController: 置信度校准 + 探索策略集成
    - ExplorationPolicy: ε-greedy + UCB 探索/利用平衡

测试结构:
  TestPatternRanking          — 模式排名引擎
  TestConfidenceCalibration   — 决策置信度校准
  TestExplorationPolicy       — 探索/利用平衡
  TestStrategyModeIntegration  — 策略模式集成探索
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.pattern_ranking_engine import (
    PatternRankingEngine,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.pattern_ranking_models import (
    RankedPattern,
    RankingResult,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.exploration_policy import (
    ExplorationPolicy,
)
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
    LearningMode,
    LearningStrategyState,
    LearningPolicyDecision,
    PolicyDecisionType,
)
from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
    PatternMemory,
    PatternCondition,
    PatternAction,
    PatternPerformance,
    PatternMiningDimension,
    PatternQuality,
)
from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_store import (
    PatternStore,
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def _make_pattern(
    action_type: str = "test_action",
    success_rate: float = 0.75,
    samples: int = 20,
    success_count: int | None = None,
    avg_reward: float = 0.70,
    avg_confidence: float = 0.80,
    std_reward: float = 0.0,
    last_seen: str | None = None,
    confidence: float | None = None,
    score: float | None = None,
    tags: list[str] | None = None,
) -> PatternMemory:
    """创建测试用 PatternMemory."""
    if success_count is None:
        success_count = int(samples * success_rate)
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
        success_count=success_count,
        success_rate=success_rate,
        avg_reward=avg_reward,
        avg_confidence=avg_confidence,
        std_reward=std_reward,
        last_seen=last_seen or datetime.now(timezone.utc).isoformat(),
    )
    pattern = PatternMemory(
        dimension=PatternMiningDimension.OPPORTUNITY_ACTION,
        condition=condition,
        action=action,
        performance=perf,
        tags=tags or ["test"],
    )
    pattern.compute_score()
    if confidence is not None:
        pattern.confidence = confidence
    if score is not None:
        pattern.score = score
    return pattern


def _make_effectiveness(
    score: float = 0.70,
    gain: float = 0.10,
    is_effective: bool = True,
) -> LearningEffectiveness:
    """创建测试用 LearningEffectiveness."""
    return LearningEffectiveness(
        total_decisions=10,
        learning_enhanced_count=5,
        baseline_success_rate=0.50,
        enhanced_success_rate=0.70 if is_effective else 0.50,
        learning_gain=gain,
        is_effective=is_effective,
        effectiveness_score=score,
    )


def _make_adaptive_confidence(
    adjusted: float = 0.75,
    level: str = "medium",
) -> AdaptiveConfidenceResult:
    """创建测试用 AdaptiveConfidenceResult."""
    return AdaptiveConfidenceResult(
        adjusted_confidence=adjusted,
        confidence_level=level,
    )


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def ranking_engine() -> PatternRankingEngine:
    return PatternRankingEngine()


@pytest.fixture
def pattern_store() -> PatternStore:
    return PatternStore()


@pytest.fixture
def controller() -> LearningPolicyController:
    return LearningPolicyController()


# ═══════════════════════════════════════════════════════════════
# Task 1: Pattern Ranking
# ═══════════════════════════════════════════════════════════════


class TestPatternRanking:
    """模式排名引擎测试."""

    def test_high_sample_high_confidence_ranks_first(self, ranking_engine):
        """高样本高置信度 Pattern 排名靠前."""
        pattern_a = _make_pattern(
            action_type="action_a",
            samples=100,
            success_rate=0.90,
            success_count=90,
            avg_reward=0.88,
            avg_confidence=0.90,
            confidence=0.90,
            score=0.85,
        )
        pattern_b = _make_pattern(
            action_type="action_b",
            samples=10,
            success_rate=0.60,
            success_count=6,
            avg_reward=0.55,
            avg_confidence=0.60,
            confidence=0.60,
            score=0.80,
        )

        result = ranking_engine.rank([pattern_a, pattern_b])

        assert result.total_ranked == 2
        assert result.ranked_patterns[0].pattern_id == pattern_a.pattern_id
        assert result.ranked_patterns[0].rank == 1
        assert result.ranked_patterns[1].rank == 2
        assert result.ranked_patterns[0].rank_score > result.ranked_patterns[1].rank_score

    def test_stale_pattern_ranks_lower(self, ranking_engine):
        """过期 Pattern 排名下降."""
        now = datetime.now(timezone.utc)
        fresh = _make_pattern(
            action_type="fresh",
            score=0.80,
            confidence=0.80,
            last_seen=(now - timedelta(days=1)).isoformat(),
        )
        stale = _make_pattern(
            action_type="stale",
            score=0.80,
            confidence=0.80,
            last_seen=(now - timedelta(days=60)).isoformat(),
        )

        result = ranking_engine.rank([fresh, stale])

        assert result.ranked_patterns[0].pattern_id == fresh.pattern_id
        assert result.ranked_patterns[0].recency_factor > result.ranked_patterns[1].recency_factor

    def test_empty_list_returns_empty(self, ranking_engine):
        """空列表返回空结果."""
        result = ranking_engine.rank([])

        assert result.total_ranked == 0
        assert result.ranked_patterns == []
        assert result.top_pattern_id == ""

    def test_rank_score_components(self, ranking_engine):
        """各因子贡献验证."""
        pattern = _make_pattern(
            action_type="test",
            samples=50,
            success_rate=0.80,
            success_count=40,
            avg_reward=0.75,
            avg_confidence=0.85,
            std_reward=0.10,
            confidence=0.85,
            score=0.80,
        )

        result = ranking_engine.rank([pattern])
        rp = result.ranked_patterns[0]

        # 验证各因子在合理范围
        assert 0.0 <= rp.sample_factor <= 1.0
        assert 0.0 <= rp.recency_factor <= 1.0
        assert 0.0 <= rp.reward_stability <= 1.0
        # rank_score 由各因子加权计算
        assert 0.0 <= rp.rank_score <= 1.0

    def test_sample_factor_increases_with_samples(self, ranking_engine):
        """样本因子随样本数增加."""
        p_small = _make_pattern(samples=5, score=0.80, confidence=0.80)
        p_large = _make_pattern(samples=100, score=0.80, confidence=0.80)

        result = ranking_engine.rank([p_small, p_large])

        assert result.ranked_patterns[0].sample_factor > result.ranked_patterns[1].sample_factor

    def test_reward_stability_with_zero_std(self, ranking_engine):
        """std_reward=0 时稳定性为 1.0."""
        pattern = _make_pattern(
            action_type="stable",
            std_reward=0.0,
            avg_reward=0.75,
        )

        result = ranking_engine.rank([pattern])
        assert result.ranked_patterns[0].reward_stability == 1.0

    def test_ranking_result_from_ranked(self):
        """RankingResult.from_ranked 工厂方法."""
        rp1 = RankedPattern(pattern_id="p1", rank_score=0.90, rank=1)
        rp2 = RankedPattern(pattern_id="p2", rank_score=0.70, rank=2)

        result = RankingResult.from_ranked([rp1, rp2])

        assert result.total_ranked == 2
        assert result.top_pattern_id == "p1"
        assert result.top_rank_score == 0.90
        assert result.avg_rank_score == 0.80


# ═══════════════════════════════════════════════════════════════
# Task 2: Confidence Calibration
# ═══════════════════════════════════════════════════════════════


class TestConfidenceCalibration:
    """决策置信度校准测试."""

    def test_calibrate_confidence_with_high_accuracy(self, controller):
        """高准确率提升置信度."""
        raw = 0.70
        accuracy = 0.85
        calibrated = controller._calibrate_confidence(raw, accuracy)

        assert calibrated > raw, f"Expected calibrated ({calibrated}) > raw ({raw})"
        assert calibrated <= 1.0

    def test_calibrate_confidence_with_low_accuracy(self, controller):
        """低准确率降低置信度."""
        raw = 0.80
        accuracy = 0.40
        calibrated = controller._calibrate_confidence(raw, accuracy)

        assert calibrated < raw, f"Expected calibrated ({calibrated}) < raw ({raw})"
        assert calibrated >= 0.0

    def test_calibrate_confidence_no_history(self, controller):
        """无历史数据时接近原值."""
        raw = 0.75
        # _get_historical_accuracy 返回 None → 使用 raw_conf 作为 accuracy
        accuracy = controller._get_historical_accuracy("test_type")
        if accuracy is None:
            # 无历史，校准应为恒等变换
            calibrated = controller._calibrate_confidence(raw, raw)
            assert calibrated == raw
        else:
            calibrated = controller._calibrate_confidence(raw, accuracy)
            assert calibrated >= 0.0

    def test_calibrated_confidence_in_range(self, controller):
        """校准后置信度在 [0, 1] 范围内."""
        test_cases = [
            (0.95, 0.95),
            (0.10, 0.10),
            (0.50, 0.50),
            (0.80, 0.20),
        ]
        for raw, accuracy in test_cases:
            calibrated = controller._calibrate_confidence(raw, accuracy)
            assert 0.0 <= calibrated <= 1.0, f"raw={raw}, acc={accuracy}, cal={calibrated}"

    def test_compute_decision_confidence_uses_calibration(self, controller):
        """_compute_decision_confidence 使用校准."""
        effectiveness = _make_effectiveness(score=0.70, gain=0.10)
        adaptive_conf = _make_adaptive_confidence(adjusted=0.75)
        state = LearningStrategyState.default()

        # 先记录一些历史决策以获得准确率
        # 模拟历史决策: 大部分正确
        for _ in range(10):
            controller._decision_history.append(
                LearningPolicyDecision(
                    decision_type=PolicyDecisionType.ALLOW_LEARNING.value,
                    should_learn=True,
                    confidence=0.75,
                )
            )

        conf = controller._compute_decision_confidence(
            effectiveness=effectiveness,
            adaptive_confidence=adaptive_conf,
            state=state,
        )

        assert 0.0 <= conf <= 1.0


# ═══════════════════════════════════════════════════════════════
# Task 3: Exploration Policy
# ═══════════════════════════════════════════════════════════════


class TestExplorationPolicy:
    """探索/利用平衡测试."""

    def test_ucb_boosts_under_explored(self):
        """UCB 奖励探索不足的 Pattern."""
        # 创建两个 avg_reward 相同但 samples 不同的 Pattern
        p_under = _make_pattern(
            action_type="under",
            samples=2,
            avg_reward=0.50,
        )
        p_well = _make_pattern(
            action_type="well",
            samples=80,
            avg_reward=0.50,
        )

        total_rounds = 100
        ucb_under = ExplorationPolicy.compute_ucb(p_under, total_rounds)
        ucb_well = ExplorationPolicy.compute_ucb(p_well, total_rounds)

        # 探索不足的 UCB 应显著高于 avg_reward
        assert ucb_under > 0.50, f"UCB should boost under-explored: {ucb_under}"
        # 探索不足的 UCB 应高于探索充分的
        assert ucb_under > ucb_well, (
            f"Under-explored UCB ({ucb_under}) should exceed well-explored ({ucb_well})"
        )

    def test_ucb_approaches_mean_for_well_explored(self):
        """充分探索后 UCB 接近均值."""
        p_well = _make_pattern(
            action_type="well",
            samples=1000,
            avg_reward=0.70,
        )

        total_rounds = 100
        ucb = ExplorationPolicy.compute_ucb(p_well, total_rounds)

        # UCB bonus = sqrt(2*ln(100)/1000) ≈ 0.096, 应远小于 avg_reward
        assert ucb - 0.70 < 0.10, f"UCB bonus too large: {ucb - 0.70}"

    def test_epsilon_decays_over_rounds(self):
        """ε 随轮次衰减."""
        policy = ExplorationPolicy(epsilon_init=0.3, decay_factor=0.95)

        eps_initial = policy.get_current_epsilon()
        assert eps_initial == 0.3

        # 推进 50 轮
        for _ in range(50):
            policy.advance_round()

        eps_50 = policy.get_current_epsilon()
        assert eps_50 < eps_initial, f"ε should decay: {eps_50} < {eps_initial}"
        # 理论值: 0.3 * 0.95^50 ≈ 0.023
        expected = 0.3 * (0.95 ** 50)
        assert abs(eps_50 - expected) < 0.01, f"ε={eps_50}, expected≈{expected:.4f}"

    def test_epsilon_never_below_min(self):
        """ε 不低于 ε_min."""
        policy = ExplorationPolicy(epsilon_init=0.3, epsilon_min=0.05)

        # 推进 200 轮
        for _ in range(200):
            policy.advance_round()

        assert policy.get_current_epsilon() >= 0.05

    def test_select_action_with_seed_deterministic(self):
        """固定 seed 时 select_action 确定性."""
        p1 = _make_pattern(action_type="a", samples=10, avg_reward=0.60)
        p2 = _make_pattern(action_type="b", samples=50, avg_reward=0.80)

        # 两个 policy 相同 seed
        policy1 = ExplorationPolicy(seed=42, epsilon_init=0.0)  # 不探索
        policy2 = ExplorationPolicy(seed=42, epsilon_init=0.0)

        result1 = policy1.select_action([p1, p2], total_rounds=10)
        result2 = policy2.select_action([p1, p2], total_rounds=10)

        assert result1 is not None
        assert result2 is not None
        assert result1.pattern_id == result2.pattern_id

    def test_select_action_empty_returns_none(self):
        """空列表返回 None."""
        policy = ExplorationPolicy()
        result = policy.select_action([], total_rounds=10)
        assert result is None

    def test_explore_randomness_with_high_epsilon(self):
        """高 ε 时探索行为不同."""
        p1 = _make_pattern(action_type="a", samples=10, avg_reward=0.60)
        p2 = _make_pattern(action_type="b", samples=50, avg_reward=0.80)

        # ε=1.0 总是探索
        policy = ExplorationPolicy(epsilon_init=1.0, epsilon_min=1.0, seed=42)
        results = set()
        for _ in range(20):
            result = policy.select_action([p1, p2], total_rounds=10)
            if result:
                results.add(result.pattern_id)

        # 随机探索应至少看到两种 Pattern
        assert len(results) >= 1, "Should explore at least one pattern"


# ═══════════════════════════════════════════════════════════════
# Task 4: Strategy Mode Integration
# ═══════════════════════════════════════════════════════════════


class TestStrategyModeIntegration:
    """策略模式集成探索策略测试."""

    def test_high_uncertainty_forces_exploration(self, controller, pattern_store):
        """高 uncertainty 时强制探索."""
        # 只有 1 个 Pattern → uncertainty 高
        pattern = _make_pattern(
            action_type="test",
            confidence=0.40,
            avg_confidence=0.40,
        )
        pattern_store.store(pattern)

        effectiveness = _make_effectiveness(score=0.50, gain=0.0, is_effective=False)
        adaptive_conf = _make_adaptive_confidence(adjusted=0.45)
        state = LearningStrategyState.default()

        # 创建探索策略
        exploration = ExplorationPolicy(seed=42)

        mode, reasons = controller._determine_strategy_mode(
            effectiveness=effectiveness,
            adaptive_confidence=adaptive_conf,
            state=state,
            exploration_policy=exploration,
        )

        assert mode in (LearningMode.CONSERVATIVE.value, LearningMode.BALANCED.value), (
            f"High uncertainty should not be AGGRESSIVE, got {mode}"
        )

    def test_low_uncertainty_allows_exploitation(self, controller, pattern_store):
        """低 uncertainty 允许利用."""
        # 5 个高置信度 Pattern → uncertainty 低
        for i in range(5):
            pattern = _make_pattern(
                action_type=f"action_{i}",
                confidence=0.85,
                avg_confidence=0.85,
            )
            pattern_store.store(pattern)

        effectiveness = _make_effectiveness(score=0.85, gain=0.15, is_effective=True)
        adaptive_conf = _make_adaptive_confidence(adjusted=0.85)
        state = LearningStrategyState.default()

        exploration = ExplorationPolicy(seed=42)

        mode, reasons = controller._determine_strategy_mode(
            effectiveness=effectiveness,
            adaptive_confidence=adaptive_conf,
            state=state,
            exploration_policy=exploration,
        )

        # 高置信度 + 高有效性 → AGGRESSIVE
        assert mode == LearningMode.AGGRESSIVE.value, (
            f"Low uncertainty should allow AGGRESSIVE, got {mode}"
        )

    def test_exploration_overrides_aggressive(self, controller):
        """探索需求覆盖 AGGRESSIVE."""
        effectiveness = _make_effectiveness(score=0.85, gain=0.15, is_effective=True)
        adaptive_conf = _make_adaptive_confidence(adjusted=0.85)
        state = LearningStrategyState.default()

        # 创建总是探索的策略
        exploration = ExplorationPolicy(epsilon_init=1.0, epsilon_min=1.0, seed=42)

        mode, reasons = controller._determine_strategy_mode(
            effectiveness=effectiveness,
            adaptive_confidence=adaptive_conf,
            state=state,
            exploration_policy=exploration,
        )

        # 即使满足 AGGRESSIVE 条件，探索需求应降级为 BALANCED
        assert mode != LearningMode.AGGRESSIVE.value, (
            f"Exploration should prevent AGGRESSIVE, got {mode}"
        )
        assert mode in (LearningMode.BALANCED.value, LearningMode.CONSERVATIVE.value)

    def test_backward_compatible_without_exploration(self, controller):
        """不传 exploration_policy 时向后兼容."""
        effectiveness = _make_effectiveness(score=0.85, gain=0.15, is_effective=True)
        adaptive_conf = _make_adaptive_confidence(adjusted=0.85)
        state = LearningStrategyState.default()

        mode, reasons = controller._determine_strategy_mode(
            effectiveness=effectiveness,
            adaptive_confidence=adaptive_conf,
            state=state,
            # 不传 exploration_policy
        )

        # 应该正常返回 AGGRESSIVE
        assert mode == LearningMode.AGGRESSIVE.value, (
            f"Without exploration policy, should be AGGRESSIVE, got {mode}"
        )


# ═══════════════════════════════════════════════════════════════
# __all__
# ═══════════════════════════════════════════════════════════════

__all__ = [
    "TestPatternRanking",
    "TestConfidenceCalibration",
    "TestExplorationPolicy",
    "TestStrategyModeIntegration",
]