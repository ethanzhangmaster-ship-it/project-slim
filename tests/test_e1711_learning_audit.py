"""E17.11.5 Learning Loop Audit — 学习闭环审计.

Day 7.11 Step 5:
  验证长期运行后的记忆质量，覆盖三个生产关键问题:
    - Memory Aging: 旧 Pattern 是否自然衰减而非永久污染决策
    - Pattern Competition: 多 Pattern 竞争时决策是否选择最优模式
    - Autonomous Improvement: 多 cycle 后决策质量是否提升

测试结构:
  TestMemoryAging          — 记忆老化审计
  TestPatternCompetition   — 模式竞争审计
  TestAutonomousImprovement — 自主提升审计
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.pattern_decay_models import (
    DecayAction,
    DecayScore,
    PatternDecayReason,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.pattern_decay_engine import (
    PatternDecayEngine,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.learning_policy_controller import (
    LearningPolicyController,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.memory_consolidation_pipeline import (
    MemoryConsolidationPipeline,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.learning_memory_models import (
    ConsolidatedExperience,
    ExtractionResult,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.evaluation.models import (
    LearningEffectiveness,
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
    action_type: str = "increase_budget",
    success_rate: float = 0.75,
    samples: int = 20,
    success_count: int | None = None,
    avg_reward: float = 0.70,
    avg_confidence: float = 0.80,
    last_seen: str | None = None,
    metadata: dict | None = None,
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
        last_seen=last_seen or datetime.now(timezone.utc).isoformat(),
    )
    pattern = PatternMemory(
        dimension=PatternMiningDimension.OPPORTUNITY_ACTION,
        condition=condition,
        action=action,
        performance=perf,
        tags=tags or ["test"],
        metadata=metadata or {},
    )
    pattern.compute_score()
    return pattern


def _make_consolidated_experience(
    action_type: str = "increase_budget",
    success: bool = True,
    reward: float = 0.75,
    success_rate: float = 0.75,
    samples: int = 10,
    learning_gain: float = 0.15,
    significance_score: float = 0.60,
    feedback_classification: str = "GOOD_LEARNING",
) -> ConsolidatedExperience:
    """创建测试用 ConsolidatedExperience.

    设置 learning_gain + significance_score + feedback_classification
    确保 CompressedKnowledge.from_experiences 的 reliability >= 0.5，
    从而 is_reliable=True，让 reinforcement bridge 能正确执行强化。
    """
    return ConsolidatedExperience(
        source_cycle_id=str(uuid.uuid4()),
        cycle_number=0,
        action_type=action_type,
        action_params={},
        success=success,
        metrics_delta={},
        reward=reward,
        confidence=0.80,
        category="ua",
        learning_gain=learning_gain,
        significance_score=significance_score,
        feedback_classification=feedback_classification,
        tags=[action_type],
        metadata={
            "success_rate": success_rate,
            "experience_count": samples,
            "avg_reward": reward,
            "avg_confidence": 0.80,
        },
    )


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def pattern_store() -> PatternStore:
    return PatternStore()


@pytest.fixture
def policy_controller() -> LearningPolicyController:
    return LearningPolicyController()


# ═══════════════════════════════════════════════════════════════
# Audit 1 — Memory Aging
# ═══════════════════════════════════════════════════════════════


class TestMemoryAging:
    """记忆老化审计 — 验证旧 Pattern 自然衰减 + 持续成功 Pattern 保持."""

    def test_old_pattern_decay(self, pattern_store):
        """Case A: 长期未使用 Pattern 的置信度应衰减.

        验证: 30天未使用的 pattern，经过衰减后 confidence 下降。
        """
        # 设定当前时间
        now = datetime(2026, 7, 31, 12, 0, 0, tzinfo=timezone.utc)

        # 创建 30 天前最后使用的旧模式
        old_pattern = _make_pattern(
            action_type="old_strategy",
            success_rate=0.60,
            samples=5,
            avg_reward=0.50,
            avg_confidence=0.60,
            last_seen=datetime(2026, 7, 1, tzinfo=timezone.utc).isoformat(),  # 30 days ago
            metadata={
                "peak_reward": 0.70,
                "usage_count_recent": 2,
                "usage_count_peak": 50,
            },
        )
        old_pattern.confidence = 0.85  # 手动设置较高置信度
        confidence_before = old_pattern.confidence
        pattern_store.store(old_pattern)

        # 执行衰减
        engine = PatternDecayEngine(now=now)
        engine.decay_store(pattern_store)

        # 验证：置信度下降
        pattern_after = pattern_store.get_all()[0]
        assert pattern_after.confidence < confidence_before, (
            f"Expected confidence to decay from {confidence_before}, "
            f"got {pattern_after.confidence}"
        )

    def test_success_pattern_preserved(self, pattern_store):
        """Case B: 持续成功 Pattern 的置信度应保持.

        验证: 高成功率、大样本、最近使用的 pattern，衰减后 confidence 基本保持。
        """
        now = datetime(2026, 7, 31, 12, 0, 0, tzinfo=timezone.utc)

        # 创建持续成功的模式
        success_pattern = _make_pattern(
            action_type="winning_strategy",
            success_rate=0.90,
            samples=100,
            success_count=90,
            avg_reward=0.88,
            avg_confidence=0.92,
            last_seen=datetime(2026, 7, 30, tzinfo=timezone.utc).isoformat(),  # 1 day ago
            metadata={
                "peak_reward": 0.90,
                "usage_count_recent": 95,
                "usage_count_peak": 100,
            },
        )
        success_pattern.confidence = 0.90
        confidence_before = success_pattern.confidence
        pattern_store.store(success_pattern)

        # 执行衰减
        engine = PatternDecayEngine(now=now)
        engine.decay_store(pattern_store)

        # 验证：置信度保持 (不超过 5% 下降)
        pattern_after = pattern_store.get_all()[0]
        assert pattern_after.confidence >= confidence_before * 0.95, (
            f"Expected confidence to be preserved (>= {confidence_before * 0.95}), "
            f"got {pattern_after.confidence}"
        )

    def test_decay_score_increases_with_age(self):
        """随着 last_seen 时间增加，stale_factor 应单调递增."""
        now = datetime(2026, 7, 31, 12, 0, 0, tzinfo=timezone.utc)

        # 创建两个仅 last_seen 不同的模式
        fresh = _make_pattern(
            action_type="fresh",
            last_seen=datetime(2026, 7, 30, tzinfo=timezone.utc).isoformat(),
        )
        old = _make_pattern(
            action_type="old",
            last_seen=datetime(2026, 6, 1, tzinfo=timezone.utc).isoformat(),  # 60 days ago
        )

        engine = PatternDecayEngine(now=now)
        fresh_score = engine.calculate_decay_score(fresh)
        old_score = engine.calculate_decay_score(old)

        assert old_score.stale_factor > fresh_score.stale_factor, (
            f"Older pattern should have higher stale_factor: "
            f"old={old_score.stale_factor}, fresh={fresh_score.stale_factor}"
        )
        assert old_score.total > fresh_score.total, (
            f"Older pattern should have higher total decay score: "
            f"old={old_score.total}, fresh={fresh_score.total}"
        )


# ═══════════════════════════════════════════════════════════════
# Audit 2 — Pattern Competition
# ═══════════════════════════════════════════════════════════════


class TestPatternCompetition:
    """模式竞争审计 — 验证多 Pattern 竞争时选择最优."""

    def test_best_pattern_selected(self, pattern_store):
        """多个同 action_type 的 Pattern 竞争，应选择最优 (最高 score).

        Pattern A: success_rate=0.55, confidence=0.60
        Pattern B: success_rate=0.85, confidence=0.90
        预期: get_best_pattern 返回 Pattern B

        注意: 使用不同的 opportunity_type 避免 PatternStore._find_existing
        去重 (dedup by dimension+opportunity_type+action_type)。
        """
        action = "increase_bundle_offer"

        # Pattern A: 低成功率 (不同 opportunity_type 避免去重)
        pattern_a = _make_pattern(
            action_type=action,
            success_rate=0.55,
            samples=10,
            avg_reward=0.50,
            avg_confidence=0.60,
            tags=["variant_a"],
        )
        pattern_a.condition.opportunity_type = "increase_bundle_offer_variant_a"
        pattern_a.confidence = 0.60
        pattern_a.compute_score()

        # Pattern B: 高成功率
        pattern_b = _make_pattern(
            action_type=action,
            success_rate=0.85,
            samples=50,
            success_count=42,
            avg_reward=0.82,
            avg_confidence=0.90,
            tags=["variant_b"],
        )
        pattern_b.condition.opportunity_type = "increase_bundle_offer_variant_b"
        pattern_b.confidence = 0.90
        pattern_b.compute_score()

        pattern_store.store(pattern_a)
        pattern_store.store(pattern_b)

        # 查询最佳模式 (按 action_type 查询，两者都匹配)
        best = pattern_store.get_best_pattern(action_type=action)

        assert best is not None, "Expected a best pattern to be returned"
        assert best.pattern_id == pattern_b.pattern_id, (
            f"Expected Pattern B (score={pattern_b.score}) to be selected, "
            f"but got Pattern A (score={pattern_a.score})"
        )
        assert best.confidence > pattern_a.confidence, "Best pattern should have higher confidence"
        assert best.performance.success_rate > pattern_a.performance.success_rate, (
            "Best pattern should have higher success rate"
        )

    def test_low_confidence_pattern_ignored(self, pattern_store):
        """低置信度/低成功率 Pattern 在竞争中应被忽略.

        验证: 当存在高置信度 Pattern 时，低置信度 Pattern 不应被选为最佳。
        """
        action = "adjust_bid"

        # 低质量 Pattern
        low_pattern = _make_pattern(
            action_type=action,
            success_rate=0.25,
            samples=3,
            avg_reward=0.15,
            avg_confidence=0.20,
            tags=["low_quality"],
        )
        low_pattern.condition.opportunity_type = "adjust_bid_variant_low"
        low_pattern.confidence = 0.20
        low_pattern.compute_score()

        # 高质量 Pattern
        high_pattern = _make_pattern(
            action_type=action,
            success_rate=0.88,
            samples=80,
            success_count=70,
            avg_reward=0.85,
            avg_confidence=0.90,
            tags=["high_quality"],
        )
        high_pattern.condition.opportunity_type = "adjust_bid_variant_high"
        high_pattern.confidence = 0.90
        high_pattern.compute_score()

        pattern_store.store(low_pattern)
        pattern_store.store(high_pattern)

        best = pattern_store.get_best_pattern(action_type=action)

        assert best is not None
        assert best.pattern_id == high_pattern.pattern_id, (
            "Best pattern should be the high-quality one, not low-quality"
        )
        assert best.confidence >= 0.80, f"Best pattern confidence too low: {best.confidence}"

    def test_pattern_ranking_by_score(self, pattern_store):
        """get_top_patterns 应按 score 降序排列，而非按创建时间."""
        # 创建三个不同质量的 Pattern
        patterns = [
            _make_pattern(
                action_type=f"action_{i}",
                success_rate=0.5 + i * 0.15,
                samples=20 + i * 20,
                success_count=int((20 + i * 20) * (0.5 + i * 0.15)),
                avg_reward=0.4 + i * 0.2,
                avg_confidence=0.5 + i * 0.15,
                tags=[f"tier_{i}"],
            )
            for i in range(3)
        ]
        # 确保各自 compute_score
        for p in patterns:
            p.compute_score()
            pattern_store.store(p)

        top = pattern_store.get_top_patterns(3)

        # 验证按 score 降序排列
        for i in range(len(top) - 1):
            assert top[i].score >= top[i + 1].score, (
                f"Patterns should be sorted by score descending: "
                f"top[{i}].score={top[i].score}, top[{i+1}].score={top[i+1].score}"
            )


# ═══════════════════════════════════════════════════════════════
# Audit 3 — Autonomous Improvement
# ═══════════════════════════════════════════════════════════════


class TestAutonomousImprovement:
    """自主提升审计 — 验证多 cycle 后决策质量提升."""

    def test_learning_gain_over_cycles(self, pattern_store):
        """多 cycle 学习后，Pattern 的 success_rate 和 confidence 应提升.

        Initial: success_rate=0.5, confidence=0.5
        执行 10 cycles 成功反馈 → Consolidation → Reinforcement
        Final: success_rate ↑, confidence ↑
        """
        action = "learning_action"
        pipeline = MemoryConsolidationPipeline(pattern_store=pattern_store)

        # 创建初始 Pattern
        initial = _make_pattern(
            action_type=action,
            success_rate=0.50,
            samples=5,
            success_count=2,
            avg_reward=0.50,
            avg_confidence=0.50,
        )
        initial.confidence = 0.50
        pattern_store.store(initial)

        # 捕获初始值 (store 后 pattern_store 可能通过 _find_existing 修改同一对象)
        initial_sr = 0.50
        initial_conf = 0.50
        initial_samples = 5

        # 模拟 10 个 cycle 的成功反馈
        for cycle in range(10):
            # 每次 cycle 产生 5 条成功经验
            experiences = [
                _make_consolidated_experience(
                    action_type=action,
                    success=True,
                    reward=0.70 + cycle * 0.02,
                    success_rate=0.70 + cycle * 0.02,
                    samples=5,
                )
                for _ in range(5)
            ]

            # 构建 ExtractionResult
            extraction = ExtractionResult.from_experiences(
                experiences=experiences,
                source_cycle_id=f"cycle_{cycle}",
                cycle_number=cycle,
            )

            # 执行压缩 → 强化 (注意: _run_reinforce 需要 compression_result)
            compress_stage = pipeline._run_compress(extraction)
            if compress_stage.success and compress_stage.result_ref is not None:
                pipeline._run_reinforce(compress_stage.result_ref)

        # 获取最终 Pattern
        final = pattern_store.get_best_pattern(action_type=action, actionable_only=False)
        assert final is not None

        final_sr = final.performance.success_rate
        final_conf = final.confidence

        # 验证提升
        assert final_sr > initial_sr, (
            f"Expected success_rate to improve: {initial_sr} → {final_sr}"
        )
        assert final_conf > initial_conf, (
            f"Expected confidence to improve: {initial_conf} → {final_conf}"
        )
        assert final.performance.samples > initial_samples, (
            f"Expected samples to increase: {initial_samples} → {final.performance.samples}"
        )

    def test_decision_quality_improves(self, pattern_store, policy_controller):
        """多 cycle 后，决策质量应提升.

        验证: 用 PatternStore 增强决策后，enhanced_confidence 应高于 base_confidence。
        """
        action = "decision_action"

        # 创建高质量 Pattern
        pattern = _make_pattern(
            action_type=action,
            success_rate=0.85,
            samples=50,
            success_count=42,
            avg_reward=0.82,
            avg_confidence=0.90,
        )
        pattern.confidence = 0.90
        pattern_store.store(pattern)

        # 通过 PatternStore 增强决策
        result = pattern_store.enhance_decision(
            opportunity_type=action,
            action_type=action,
            base_confidence=0.50,
        )

        assert result["enhanced_confidence"] > 0.50, (
            f"Enhanced confidence should exceed base: {result}"
        )
        assert result["matched_pattern"] is not None, "Should match the stored pattern"
        assert result["recommendation"] in ("strong_recommend", "recommend"), (
            f"Unexpected recommendation: {result['recommendation']}"
        )

    def test_negative_feedback_does_not_improve(self, pattern_store):
        """负反馈不应提升 Pattern 质量.

        验证: 全是失败经验的 cycle 不会提升 Pattern 的 success_rate 和 confidence。
        """
        action = "failing_action"
        pipeline = MemoryConsolidationPipeline(pattern_store=pattern_store)

        # 创建初始 Pattern
        initial = _make_pattern(
            action_type=action,
            success_rate=0.50,
            samples=5,
            avg_reward=0.50,
            avg_confidence=0.50,
        )
        initial.confidence = 0.50
        pattern_store.store(initial)

        initial_sr = 0.50
        initial_conf = 0.50

        # 模拟 5 个 cycle 的失败反馈
        for cycle in range(5):
            experiences = [
                _make_consolidated_experience(
                    action_type=action,
                    success=False,
                    reward=0.15,
                    success_rate=0.15,
                    samples=3,
                    learning_gain=-0.10,
                    significance_score=0.30,
                    feedback_classification="BAD_LEARNING",
                )
                for _ in range(3)
            ]

            extraction = ExtractionResult.from_experiences(
                experiences=experiences,
                source_cycle_id=f"fail_cycle_{cycle}",
                cycle_number=cycle,
            )

            compress_stage = pipeline._run_compress(extraction)
            if compress_stage.success and compress_stage.result_ref is not None:
                pipeline._run_reinforce(compress_stage.result_ref)

        # 获取最终 Pattern
        final = pattern_store.get_best_pattern(action_type=action, actionable_only=False)
        assert final is not None

        # 负反馈不应提升 success_rate 和 confidence
        assert final.performance.success_rate <= initial_sr + 0.05, (
            f"Negative feedback should not improve success_rate: "
            f"{initial_sr} → {final.performance.success_rate}"
        )
        assert final.confidence <= initial_conf + 0.05, (
            f"Negative feedback should not improve confidence: "
            f"{initial_conf} → {final.confidence}"
        )


# ═══════════════════════════════════════════════════════════════
# __all__
# ═══════════════════════════════════════════════════════════════

__all__ = [
    "TestMemoryAging",
    "TestPatternCompetition",
    "TestAutonomousImprovement",
]