"""E13.7.5 Learning Memory Integration — 专项测试.

测试覆盖:
  1. integrate:         全量/部分/无 Memory 写入
  2. store_learning:    integrate 别名
  3. lessons:           各 reward 水平的经验教训
  4. recommendations:   各 reward 水平的改进建议
  5. next_action:       reinforce / adjust / observe / abandon
  6. learning_quality:  存储成功率 + 置信度
  7. retrieve_similar:  跨 Memory 检索
  8. Bridge:            GrowthExperience / PatternMemory 转换
  9. Edge cases:        极端值 / 空上下文 / None Store
  10. End-to-end:       完整 Pipeline
"""

from __future__ import annotations

from typing import Any

import pytest

from market_ops.creative_vision_runtime.growth_runtime.intelligence.decision.decision_memory import (
    DecisionMemory,
    DecisionOutput,
    DecisionType,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.memory_integration import (
    LearningMemoryIntegrator,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.learning_models import (
    AttributionResult,
    LearningExperience,
    LearningOutcome,
    LearningReward,
    RewardWeights,
)
from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import (
    ExperienceStore,
)
from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_store import (
    PatternStore,
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def _make_experience(
    learning_id: str = "L001",
    decision_id: str = "d001",
    action_type: str = "creative_refresh",
    strategy_name: str = "test_strategy",
    execution_success_rate: float = 1.0,
    was_blocked: bool = False,
    needed_approval: bool = False,
    confidence: float = 0.8,
    improvement_score: float = 0.3,
    context: dict[str, Any] | None = None,
) -> LearningExperience:
    """创建测试用 LearningExperience."""
    ctx = context or {}
    ctx.setdefault("opportunity_type", "creative_optimization")
    return LearningExperience(
        learning_id=learning_id,
        decision_id=decision_id,
        execution_id="e001",
        strategy_name=strategy_name,
        action_type=action_type,
        confidence=confidence,
        context=ctx,
        outcome=LearningOutcome(
            execution_success_rate=execution_success_rate,
            was_blocked=was_blocked,
            needed_approval=needed_approval,
            improvement_score=improvement_score,
        ),
    )


def _make_reward(
    total_reward: float = 0.72,
    business_reward: float = 0.77,
    execution_reward: float = 1.0,
    safety_reward: float = 1.0,
    efficiency_reward: float = 0.4,
    confidence: float = 0.83,
    reward_level: str = "positive",
) -> LearningReward:
    """创建测试用 LearningReward."""
    return LearningReward(
        total_reward=total_reward,
        business_reward=business_reward,
        execution_reward=execution_reward,
        safety_reward=safety_reward,
        efficiency_reward=efficiency_reward,
        confidence=confidence,
        reward_level=reward_level,
        weights=RewardWeights.default(),
        calculation_method="reward_attribution_engine",
    )


def _make_attribution(
    decision_id: str = "d001",
    creative_contribution: float = 0.65,
    strategy_contribution: float = 0.20,
    audience_contribution: float = 0.10,
    timing_contribution: float = 0.05,
    primary_factor: str = "creative",
    confidence: float = 0.83,
) -> AttributionResult:
    """创建测试用 AttributionResult."""
    return AttributionResult(
        decision_id=decision_id,
        total_reward=0.72,
        creative_contribution=creative_contribution,
        strategy_contribution=strategy_contribution,
        audience_contribution=audience_contribution,
        timing_contribution=timing_contribution,
        primary_factor=primary_factor,
        confidence=confidence,
        attribution_method="reward_attribution_engine",
    )


def _make_integrator(
    with_experience: bool = True,
    with_pattern: bool = True,
    with_decision: bool = True,
) -> LearningMemoryIntegrator:
    """创建测试用 Integrator."""
    return LearningMemoryIntegrator(
        experience_store=ExperienceStore() if with_experience else None,
        pattern_store=PatternStore() if with_pattern else None,
        decision_memory=DecisionMemory() if with_decision else None,
    )


# ═══════════════════════════════════════════════════════════════
# 1. integrate — Full Integration
# ═══════════════════════════════════════════════════════════════


class TestIntegrateFull:
    """全量 Integration — 三个 Store 都连接."""

    def test_integrate_all_stores(self) -> None:
        """全部三个 Store 写入成功."""
        integrator = _make_integrator()
        exp = _make_experience()
        reward = _make_reward()
        attr = _make_attribution()
        result = integrator.integrate(exp, reward, attr)
        assert result.experience_stored
        assert result.pattern_updated
        assert result.memory_updated
        assert result.learning_quality > 0.5

    def test_integrate_returns_learning_result(self) -> None:
        """返回 LearningResult."""
        integrator = _make_integrator()
        exp = _make_experience()
        reward = _make_reward()
        attr = _make_attribution()
        result = integrator.integrate(exp, reward, attr)
        assert result.learning_id == "L001"
        assert result.decision_id == "d001"
        assert result.cycle_duration_ms > 0

    def test_integrate_experience_stored_in_store(self) -> None:
        """ExperienceStore 中确实有数据."""
        exp_store = ExperienceStore()
        integrator = LearningMemoryIntegrator(experience_store=exp_store)
        exp = _make_experience(learning_id="L_store_test")
        reward = _make_reward()
        attr = _make_attribution()
        result = integrator.integrate(exp, reward, attr)
        assert result.experience_stored
        assert exp_store.count > 0

    def test_integrate_pattern_stored_in_store(self) -> None:
        """PatternStore 中确实有数据."""
        pat_store = PatternStore()
        integrator = LearningMemoryIntegrator(pattern_store=pat_store)
        exp = _make_experience(learning_id="L_pat_test")
        reward = _make_reward()
        attr = _make_attribution()
        result = integrator.integrate(exp, reward, attr)
        assert result.pattern_updated
        assert pat_store.count > 0

    def test_integrate_decision_recorded(self) -> None:
        """DecisionMemory 中记录决策."""
        dec_memory = DecisionMemory()
        # 先 record_decision 创建记录
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.decision.models import (
            DecisionOutput,
            DecisionType,
        )
        decision = DecisionOutput(
            decision_id="d001",
            decision_type=DecisionType.EXECUTE,
            strategy_id="S1",
            strategy_name="test_strategy",
            confidence=0.8,
            risk_score=0.2,
            final_score=0.7,
        )
        dec_memory.record_decision(decision, "creative_optimization")

        integrator = LearningMemoryIntegrator(decision_memory=dec_memory)
        exp = _make_experience(decision_id="d001")
        reward = _make_reward()
        attr = _make_attribution(decision_id="d001")
        result = integrator.integrate(exp, reward, attr)
        assert result.memory_updated

        # 验证决策结果已更新
        existing = dec_memory.get_by_decision("d001")
        assert existing is not None
        assert existing.is_resolved


# ═══════════════════════════════════════════════════════════════
# 2. integrate — No Stores
# ═══════════════════════════════════════════════════════════════


class TestIntegrateNoStores:
    """无 Store 连接."""

    def test_integrate_no_stores(self) -> None:
        """无任何 Store — 不崩溃，所有 flag 为 False."""
        integrator = _make_integrator(
            with_experience=False,
            with_pattern=False,
            with_decision=False,
        )
        exp = _make_experience()
        reward = _make_reward()
        attr = _make_attribution()
        result = integrator.integrate(exp, reward, attr)
        assert not result.experience_stored
        assert not result.pattern_updated
        assert not result.memory_updated
        assert result.learning_quality < 0.4  # 只有 confidence 部分

    def test_integrate_no_stores_still_generates_lessons(self) -> None:
        """无 Store — 仍然生成 lessons 和 recommendations."""
        integrator = _make_integrator(
            with_experience=False,
            with_pattern=False,
            with_decision=False,
        )
        exp = _make_experience()
        reward = _make_reward()
        attr = _make_attribution()
        result = integrator.integrate(exp, reward, attr)
        assert len(result.lessons) > 0
        assert len(result.recommendations) > 0


# ═══════════════════════════════════════════════════════════════
# 3. integrate — Partial Stores
# ═══════════════════════════════════════════════════════════════


class TestIntegratePartial:
    """部分 Store 连接."""

    def test_experience_only(self) -> None:
        """仅 ExperienceStore."""
        integrator = _make_integrator(
            with_experience=True,
            with_pattern=False,
            with_decision=False,
        )
        exp = _make_experience()
        reward = _make_reward()
        attr = _make_attribution()
        result = integrator.integrate(exp, reward, attr)
        assert result.experience_stored
        assert not result.pattern_updated
        assert not result.memory_updated

    def test_pattern_only(self) -> None:
        """仅 PatternStore."""
        integrator = _make_integrator(
            with_experience=False,
            with_pattern=True,
            with_decision=False,
        )
        exp = _make_experience()
        reward = _make_reward()
        attr = _make_attribution()
        result = integrator.integrate(exp, reward, attr)
        assert not result.experience_stored
        assert result.pattern_updated
        assert not result.memory_updated

    def test_decision_only(self) -> None:
        """仅 DecisionMemory."""
        integrator = _make_integrator(
            with_experience=False,
            with_pattern=False,
            with_decision=True,
        )
        exp = _make_experience()
        reward = _make_reward()
        attr = _make_attribution()
        result = integrator.integrate(exp, reward, attr)
        assert not result.experience_stored
        assert not result.pattern_updated
        assert result.memory_updated

    def test_delayed_store_injection(self) -> None:
        """延迟注入 Store."""
        integrator = LearningMemoryIntegrator()
        exp = _make_experience()
        reward = _make_reward()
        attr = _make_attribution()

        # 无 Store
        result = integrator.integrate(exp, reward, attr)
        assert not result.experience_stored

        # 注入 Store
        integrator.set_experience_store(ExperienceStore())
        result = integrator.integrate(exp, reward, attr)
        assert result.experience_stored


# ═══════════════════════════════════════════════════════════════
# 4. store_learning — Alias
# ═══════════════════════════════════════════════════════════════


class TestStoreLearning:
    """store_learning 别名."""

    def test_store_learning_is_alias(self) -> None:
        """store_learning 与 integrate 行为一致."""
        integrator = _make_integrator()
        exp = _make_experience()
        reward = _make_reward()
        attr = _make_attribution()
        result1 = integrator.integrate(exp, reward, attr)
        result2 = integrator.store_learning(exp, reward, attr)
        assert result1.experience_stored == result2.experience_stored
        assert result1.pattern_updated == result2.pattern_updated
        assert result1.memory_updated == result2.memory_updated


# ═══════════════════════════════════════════════════════════════
# 5. Lessons Generation
# ═══════════════════════════════════════════════════════════════


class TestLessons:
    """经验教训生成."""

    def test_highly_effective_lesson(self) -> None:
        """高奖励 → 高度有效."""
        integrator = _make_integrator()
        exp = _make_experience(strategy_name="winning_strategy")
        reward = _make_reward(total_reward=0.72)
        attr = _make_attribution(primary_factor="creative")
        result = integrator.integrate(exp, reward, attr)
        assert any("highly effective" in l for l in result.lessons)

    def test_neutral_lesson(self) -> None:
        """中性奖励 → 中性."""
        integrator = _make_integrator()
        exp = _make_experience()
        reward = _make_reward(total_reward=0.0, reward_level="neutral")
        attr = _make_attribution(primary_factor="unexplained")
        result = integrator.integrate(exp, reward, attr)
        assert any("neutral" in l for l in result.lessons)

    def test_negative_lesson(self) -> None:
        """负向奖励 → 需要调整."""
        integrator = _make_integrator()
        exp = _make_experience()
        reward = _make_reward(total_reward=-0.4, reward_level="negative")
        attr = _make_attribution(primary_factor="strategy", strategy_contribution=-0.4)
        result = integrator.integrate(exp, reward, attr)
        assert any("needs adjustment" in l for l in result.lessons)

    def test_abandon_lesson(self) -> None:
        """极低奖励 → 放弃."""
        integrator = _make_integrator()
        exp = _make_experience()
        reward = _make_reward(total_reward=-0.8, reward_level="negative")
        attr = _make_attribution(primary_factor="strategy", strategy_contribution=-0.6)
        result = integrator.integrate(exp, reward, attr)
        assert any("abandoned" in l for l in result.lessons)

    def test_creative_primary_lesson(self) -> None:
        """素材主因 → 素材相关 lesson."""
        integrator = _make_integrator()
        exp = _make_experience()
        reward = _make_reward()
        attr = _make_attribution(primary_factor="creative")
        result = integrator.integrate(exp, reward, attr)
        assert any("Creative was the primary driver" in l for l in result.lessons)

    def test_strategy_primary_lesson(self) -> None:
        """策略主因 → 策略相关 lesson."""
        integrator = _make_integrator()
        exp = _make_experience()
        reward = _make_reward()
        attr = _make_attribution(primary_factor="strategy")
        result = integrator.integrate(exp, reward, attr)
        assert any("Strategy selection was the primary driver" in l for l in result.lessons)

    def test_audience_primary_lesson(self) -> None:
        """受众主因 → 受众相关 lesson."""
        integrator = _make_integrator()
        exp = _make_experience()
        reward = _make_reward()
        attr = _make_attribution(primary_factor="audience")
        result = integrator.integrate(exp, reward, attr)
        assert any("Audience targeting was the primary driver" in l for l in result.lessons)

    def test_timing_primary_lesson(self) -> None:
        """时机主因 → 时机相关 lesson."""
        integrator = _make_integrator()
        exp = _make_experience()
        reward = _make_reward()
        attr = _make_attribution(primary_factor="timing")
        result = integrator.integrate(exp, reward, attr)
        assert any("Market timing was the primary driver" in l for l in result.lessons)

    def test_safety_concern_lesson(self) -> None:
        """安全警告 → 安全相关 lesson."""
        integrator = _make_integrator()
        exp = _make_experience()
        reward = _make_reward(safety_reward=-1.0)
        attr = _make_attribution()
        result = integrator.integrate(exp, reward, attr)
        assert any("Safety concern" in l for l in result.lessons)

    def test_efficiency_concern_lesson(self) -> None:
        """效率问题 → 效率相关 lesson."""
        integrator = _make_integrator()
        exp = _make_experience()
        reward = _make_reward(efficiency_reward=-0.5)
        attr = _make_attribution()
        result = integrator.integrate(exp, reward, attr)
        assert any("Efficiency issue" in l for l in result.lessons)


# ═══════════════════════════════════════════════════════════════
# 6. Recommendations Generation
# ═══════════════════════════════════════════════════════════════


class TestRecommendations:
    """改进建议生成."""

    def test_reinforce_recommendation(self) -> None:
        """高奖励 → reinforce 建议."""
        integrator = _make_integrator()
        exp = _make_experience()
        reward = _make_reward(total_reward=0.72)
        attr = _make_attribution()
        result = integrator.integrate(exp, reward, attr)
        assert any("Reinforce" in r for r in result.recommendations)

    def test_continue_recommendation(self) -> None:
        """中奖励 → continue 建议."""
        integrator = _make_integrator()
        exp = _make_experience()
        reward = _make_reward(total_reward=0.3)
        attr = _make_attribution()
        result = integrator.integrate(exp, reward, attr)
        assert any("Continue" in r for r in result.recommendations)

    def test_observe_recommendation(self) -> None:
        """中性 → observe 建议."""
        integrator = _make_integrator()
        exp = _make_experience()
        reward = _make_reward(total_reward=0.0, reward_level="neutral")
        attr = _make_attribution()
        result = integrator.integrate(exp, reward, attr)
        assert any("Observe" in r for r in result.recommendations)

    def test_adjust_recommendation(self) -> None:
        """负奖励 → adjust 建议."""
        integrator = _make_integrator()
        exp = _make_experience()
        reward = _make_reward(total_reward=-0.3, reward_level="negative")
        attr = _make_attribution()
        result = integrator.integrate(exp, reward, attr)
        assert any("Adjust" in r for r in result.recommendations)

    def test_abandon_recommendation(self) -> None:
        """极低奖励 → abandon 建议."""
        integrator = _make_integrator()
        exp = _make_experience()
        reward = _make_reward(total_reward=-0.8, reward_level="negative")
        attr = _make_attribution()
        result = integrator.integrate(exp, reward, attr)
        assert any("Abandon" in r for r in result.recommendations)

    def test_creative_improvement_recommendation(self) -> None:
        """素材负贡献 → 素材改进建议."""
        integrator = _make_integrator()
        exp = _make_experience()
        reward = _make_reward()
        attr = _make_attribution(creative_contribution=-0.3)
        result = integrator.integrate(exp, reward, attr)
        assert any("creative quality" in r.lower() for r in result.recommendations)

    def test_strategy_re_evaluate_recommendation(self) -> None:
        """策略负贡献 → 策略重新评估建议."""
        integrator = _make_integrator()
        exp = _make_experience()
        reward = _make_reward()
        attr = _make_attribution(strategy_contribution=-0.3)
        result = integrator.integrate(exp, reward, attr)
        assert any("strategy" in r.lower() for r in result.recommendations)

    def test_audience_refine_recommendation(self) -> None:
        """受众负贡献 → 受众优化建议."""
        integrator = _make_integrator()
        exp = _make_experience()
        reward = _make_reward()
        attr = _make_attribution(audience_contribution=-0.3)
        result = integrator.integrate(exp, reward, attr)
        assert any("audience" in r.lower() for r in result.recommendations)

    def test_timing_optimize_recommendation(self) -> None:
        """时机负贡献 → 时机优化建议."""
        integrator = _make_integrator()
        exp = _make_experience()
        reward = _make_reward()
        attr = _make_attribution(timing_contribution=-0.3)
        result = integrator.integrate(exp, reward, attr)
        assert any("timing" in r.lower() for r in result.recommendations)


# ═══════════════════════════════════════════════════════════════
# 7. next_action
# ═══════════════════════════════════════════════════════════════


class TestNextAction:
    """下一步动作判定."""

    def test_reinforce_action(self) -> None:
        """total_reward > 0.5 → reinforce."""
        integrator = _make_integrator()
        exp = _make_experience()
        reward = _make_reward(total_reward=0.72)
        attr = _make_attribution()
        result = integrator.integrate(exp, reward, attr)
        assert result.next_action == "reinforce"

    def test_adjust_action_positive(self) -> None:
        """0.15 < total_reward <= 0.5 → adjust."""
        integrator = _make_integrator()
        exp = _make_experience()
        reward = _make_reward(total_reward=0.3)
        attr = _make_attribution()
        result = integrator.integrate(exp, reward, attr)
        assert result.next_action == "adjust"

    def test_adjust_action_negative(self) -> None:
        """-0.5 <= total_reward < -0.15 → adjust."""
        integrator = _make_integrator()
        exp = _make_experience()
        reward = _make_reward(total_reward=-0.3)
        attr = _make_attribution()
        result = integrator.integrate(exp, reward, attr)
        assert result.next_action == "adjust"

    def test_observe_action(self) -> None:
        """-0.15 <= total_reward <= 0.15 → observe."""
        integrator = _make_integrator()
        exp = _make_experience()
        reward = _make_reward(total_reward=0.0, reward_level="neutral")
        attr = _make_attribution()
        result = integrator.integrate(exp, reward, attr)
        assert result.next_action == "observe"

    def test_abandon_action(self) -> None:
        """total_reward < -0.5 → abandon."""
        integrator = _make_integrator()
        exp = _make_experience()
        reward = _make_reward(total_reward=-0.8)
        attr = _make_attribution()
        result = integrator.integrate(exp, reward, attr)
        assert result.next_action == "abandon"


# ═══════════════════════════════════════════════════════════════
# 8. learning_quality
# ═══════════════════════════════════════════════════════════════


class TestLearningQuality:
    """学习质量评分."""

    def test_full_stores_high_quality(self) -> None:
        """三个 Store 全部写入 + 高置信度 → 高质量."""
        integrator = _make_integrator()
        exp = _make_experience()
        reward = _make_reward(confidence=0.9)
        attr = _make_attribution()
        result = integrator.integrate(exp, reward, attr)
        assert result.learning_quality > 0.7

    def test_no_stores_low_quality(self) -> None:
        """无 Store → 低质量."""
        integrator = _make_integrator(
            with_experience=False,
            with_pattern=False,
            with_decision=False,
        )
        exp = _make_experience()
        reward = _make_reward(confidence=0.5)
        attr = _make_attribution()
        result = integrator.integrate(exp, reward, attr)
        assert result.learning_quality < 0.5

    def test_partial_stores_medium_quality(self) -> None:
        """部分 Store → 中等质量."""
        integrator = _make_integrator(
            with_experience=True,
            with_pattern=False,
            with_decision=False,
        )
        exp = _make_experience()
        reward = _make_reward(confidence=0.8)
        attr = _make_attribution()
        result = integrator.integrate(exp, reward, attr)
        # 0.2 (experience) + 0.4*0.8 (confidence) = 0.52
        assert 0.3 < result.learning_quality < 0.7


# ═══════════════════════════════════════════════════════════════
# 9. retrieve_similar
# ═══════════════════════════════════════════════════════════════


class TestRetrieveSimilar:
    """跨 Memory 检索."""

    def test_retrieve_empty(self) -> None:
        """空 Store — 返回空列表."""
        integrator = _make_integrator()
        result = integrator.retrieve_similar(
            context={"action_type": "creative_refresh"},
        )
        assert result["experiences"] == []
        assert result["patterns"] == []
        assert result["decisions"] == []

    def test_retrieve_after_store(self) -> None:
        """存储后检索."""
        exp_store = ExperienceStore()
        pat_store = PatternStore()
        integrator = LearningMemoryIntegrator(
            experience_store=exp_store,
            pattern_store=pat_store,
        )
        exp = _make_experience(action_type="creative_refresh")
        reward = _make_reward()
        attr = _make_attribution()
        integrator.integrate(exp, reward, attr)

        result = integrator.retrieve_similar(action_type="creative_refresh")
        assert len(result["experiences"]) > 0
        assert len(result["patterns"]) > 0

    def test_retrieve_no_stores(self) -> None:
        """无 Store — 不崩溃."""
        integrator = _make_integrator(
            with_experience=False,
            with_pattern=False,
            with_decision=False,
        )
        result = integrator.retrieve_similar(
            context={"action_type": "creative_refresh"},
        )
        assert result["experiences"] == []
        assert result["patterns"] == []
        assert result["decisions"] == []

    def test_retrieve_with_context(self) -> None:
        """通过 context 检索."""
        dec_memory = DecisionMemory()
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.decision.models import (
            DecisionOutput,
            DecisionType,
        )
        decision = DecisionOutput(
            decision_id="d_ctx_001",
            decision_type=DecisionType.EXECUTE,
            strategy_id="S1",
            strategy_name="test",
            confidence=0.8,
            risk_score=0.2,
            final_score=0.7,
        )
        dec_memory.record_decision(decision, "creative_optimization")

        integrator = LearningMemoryIntegrator(decision_memory=dec_memory)
        result = integrator.retrieve_similar(
            context={"opportunity_type": "creative_optimization"},
        )
        assert len(result["decisions"]) > 0


# ═══════════════════════════════════════════════════════════════
# 10. Edge Cases
# ═══════════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界情况."""

    def test_empty_context(self) -> None:
        """空 context — 不崩溃."""
        integrator = _make_integrator()
        exp = _make_experience(context={})
        reward = _make_reward()
        attr = _make_attribution()
        result = integrator.integrate(exp, reward, attr)
        assert result.learning_quality > 0

    def test_extreme_positive_reward(self) -> None:
        """极端正向奖励."""
        integrator = _make_integrator()
        exp = _make_experience()
        reward = _make_reward(total_reward=1.0, business_reward=1.0)
        attr = _make_attribution(creative_contribution=0.95)
        result = integrator.integrate(exp, reward, attr)
        assert result.next_action == "reinforce"
        assert result.learning_quality > 0.5

    def test_extreme_negative_reward(self) -> None:
        """极端负向奖励."""
        integrator = _make_integrator()
        exp = _make_experience()
        reward = _make_reward(
            total_reward=-1.0,
            business_reward=-1.0,
            reward_level="negative",
        )
        attr = _make_attribution(creative_contribution=-0.8)
        result = integrator.integrate(exp, reward, attr)
        assert result.next_action == "abandon"

    def test_multiple_integrations(self) -> None:
        """多次 integrate — 不崩溃."""
        integrator = _make_integrator()
        for i in range(5):
            exp = _make_experience(
                learning_id=f"L_{i}",
                decision_id=f"d_{i}",
            )
            reward = _make_reward()
            attr = _make_attribution(decision_id=f"d_{i}")
            result = integrator.integrate(exp, reward, attr)
            assert result.learning_quality > 0

    def test_metadata_populated(self) -> None:
        """metadata 包含 integration_source."""
        integrator = _make_integrator()
        exp = _make_experience()
        reward = _make_reward()
        attr = _make_attribution()
        result = integrator.integrate(exp, reward, attr)
        assert result.metadata["integration_source"] == "learning_memory_integrator"
        assert result.metadata["primary_factor"] == "creative"
        assert result.metadata["reward_level"] == "positive"

    def test_pattern_impact_populated(self) -> None:
        """pattern_impact 包含归因数据."""
        integrator = _make_integrator()
        exp = _make_experience()
        reward = _make_reward()
        attr = _make_attribution()
        result = integrator.integrate(exp, reward, attr)
        assert result.pattern_impact["primary_factor"] == "creative"
        assert result.pattern_impact["pattern_updated"] is True

    def test_decision_memory_no_existing(self) -> None:
        """DecisionMemory 中无已有记录 — 仍然返回 True."""
        dec_memory = DecisionMemory()
        integrator = LearningMemoryIntegrator(decision_memory=dec_memory)
        exp = _make_experience(decision_id="d_no_exist")
        reward = _make_reward()
        attr = _make_attribution(decision_id="d_no_exist")
        result = integrator.integrate(exp, reward, attr)
        assert result.memory_updated  # 不报错，返回 True


# ═══════════════════════════════════════════════════════════════
# 11. End-to-end Pipeline
# ═══════════════════════════════════════════════════════════════


class TestEndToEnd:
    """完整 Pipeline."""

    def test_full_pipeline_positive(self) -> None:
        """正向完整流程: Experience → Integrator → LearningResult."""
        exp_store = ExperienceStore()
        pat_store = PatternStore()
        dec_memory = DecisionMemory()

        integrator = LearningMemoryIntegrator(
            experience_store=exp_store,
            pattern_store=pat_store,
            decision_memory=dec_memory,
        )

        exp = _make_experience(
            learning_id="L_e2e_001",
            decision_id="d_e2e_001",
            action_type="creative_refresh",
            strategy_name="creative_v2_strategy",
        )
        reward = _make_reward(
            total_reward=0.72,
            business_reward=0.77,
            confidence=0.83,
        )
        attr = _make_attribution(
            decision_id="d_e2e_001",
            primary_factor="creative",
            creative_contribution=0.65,
        )

        result = integrator.integrate(exp, reward, attr)

        # 验证结果
        assert result.experience_stored
        assert result.pattern_updated
        assert result.next_action == "reinforce"
        assert len(result.lessons) >= 2
        assert len(result.recommendations) >= 1
        assert result.learning_quality > 0.7

        # 验证数据持久化
        assert exp_store.count > 0
        assert pat_store.count > 0

    def test_full_pipeline_negative(self) -> None:
        """负向完整流程."""
        integrator = _make_integrator()

        exp = _make_experience(
            learning_id="L_e2e_002",
            decision_id="d_e2e_002",
            execution_success_rate=0.0,
        )
        reward = _make_reward(
            total_reward=-0.6,
            business_reward=-0.5,
            execution_reward=-1.0,
            safety_reward=1.0,
            reward_level="negative",
        )
        attr = _make_attribution(
            decision_id="d_e2e_002",
            primary_factor="strategy",
            strategy_contribution=-0.5,
            creative_contribution=-0.2,
        )

        result = integrator.integrate(exp, reward, attr)

        assert result.next_action == "abandon"
        assert any("abandoned" in l for l in result.lessons)
        assert any("Abandon" in r for r in result.recommendations)

    def test_full_pipeline_learning_loop(self) -> None:
        """完整学习闭环 — 多次执行后检索."""
        exp_store = ExperienceStore()
        pat_store = PatternStore()
        integrator = LearningMemoryIntegrator(
            experience_store=exp_store,
            pattern_store=pat_store,
        )

        # 模拟多次学习
        for i in range(5):
            exp = _make_experience(
                learning_id=f"L_loop_{i}",
                decision_id=f"d_loop_{i}",
                action_type="creative_refresh",
            )
            reward = _make_reward(total_reward=0.5 + i * 0.1)
            attr = _make_attribution(
                decision_id=f"d_loop_{i}",
                primary_factor="creative",
            )
            integrator.integrate(exp, reward, attr)

        # 检索相似经验
        result = integrator.retrieve_similar(action_type="creative_refresh")
        assert len(result["experiences"]) == 5
        # PatternStore 会去重同一 action_type 的模式 (相同 dimension+condition+action_type)
        assert len(result["patterns"]) >= 1

    def test_full_pipeline_decision_existing_update(self) -> None:
        """已有 DecisionExperience — 更新结果."""
        dec_memory = DecisionMemory()
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.decision.models import (
            DecisionOutput,
            DecisionType,
        )
        decision = DecisionOutput(
            decision_id="d_update_001",
            decision_type=DecisionType.EXECUTE,
            strategy_id="S1",
            strategy_name="test_strategy",
            confidence=0.8,
            risk_score=0.2,
            final_score=0.7,
        )
        dec_memory.record_decision(decision, "creative_optimization")

        integrator = LearningMemoryIntegrator(decision_memory=dec_memory)
        exp = _make_experience(decision_id="d_update_001")
        reward = _make_reward(total_reward=0.72)
        attr = _make_attribution(decision_id="d_update_001")
        result = integrator.integrate(exp, reward, attr)

        # 验证
        existing = dec_memory.get_by_decision("d_update_001")
        assert existing is not None
        assert existing.is_resolved
        assert existing.is_success
        assert "total_reward" in existing.result_metrics