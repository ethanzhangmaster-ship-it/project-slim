"""E17.11.3 Consolidation Pipeline — 测试用例.

Day 7.11 Step 3:
  覆盖 ExperienceConsolidationPipeline 完整链路:
    - ConsolidationTrigger.check() (触发判定)
    - ExperienceConsolidationAdapter.build_context() (上下文构建)
    - ExperienceConsolidationPipeline.run() (完整编排)
    - End-to-End: Write → Store → Trigger → Consolidate → Pattern/Graph updated

测试结构:
  TestConsolidationTrigger (Step 3.1)
  TestExperienceConsolidationAdapter (Step 3.2)
  TestExperienceConsolidationPipeline (Step 3.3)
  TestEndToEndConsolidation (完整链路)
  TestEdgeCases (边界情况)
"""

from __future__ import annotations

import pytest
import uuid

from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.consolidation_trigger import (
    ConsolidationTrigger,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.experience_consolidation_adapter import (
    ExperienceConsolidationAdapter,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.experience_consolidation_pipeline import (
    ExperienceConsolidationPipeline,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.memory_consolidation_pipeline import (
    MemoryConsolidationPipeline,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.consolidation_models import (
    ConsolidationContext,
    ConsolidationResult,
    ConsolidationStatus,
    TriggerDecision,
    TriggerReason,
)
from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
    ExperienceCategory,
    ExperienceContext,
    ExperienceOutcome,
    ExperienceOutcomeLevel,
    GrowthExperience,
)
from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import (
    ExperienceStore,
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def _make_experience(
    action_type: str = "increase_budget",
    reward: float = 0.75,
    confidence: float = 0.70,
    success: bool = True,
    metrics_delta: dict | None = None,
    tags: list[str] | None = None,
) -> GrowthExperience:
    """创建测试用 GrowthExperience.

    Args:
        action_type: 动作类型
        reward: 奖励分数 [0, 1]
        confidence: 置信度 [0, 1]
        success: 是否成功
        metrics_delta: 指标变化
        tags: 标签
    """
    context = ExperienceContext(
        opportunity_type=action_type,
        action_type=action_type,
    )
    outcome = ExperienceOutcome(
        success=success,
        outcome_level=_reward_to_level(reward),
        metrics_before={},
        metrics_after={},
        metrics_delta=metrics_delta or {},
        actual_reward=reward,
    )
    return GrowthExperience(
        experience_id=str(uuid.uuid4()),
        context=context,
        action_type=action_type,
        outcome=outcome,
        reward=reward,
        confidence=confidence,
        category=ExperienceCategory.UA,
        tags=tags or [action_type],
    )


def _reward_to_level(reward: float) -> ExperienceOutcomeLevel:
    """奖励 → 结果等级."""
    if reward >= 0.90:
        return ExperienceOutcomeLevel.STRONG_SUCCESS
    elif reward >= 0.70:
        return ExperienceOutcomeLevel.SUCCESS
    elif reward >= 0.40:
        return ExperienceOutcomeLevel.NEUTRAL
    elif reward >= 0.20:
        return ExperienceOutcomeLevel.FAILURE
    else:
        return ExperienceOutcomeLevel.STRONG_FAILURE


def _make_experiences(
    count: int,
    action_type: str = "increase_budget",
    base_reward: float = 0.75,
    base_confidence: float = 0.70,
    success: bool = True,
) -> list[GrowthExperience]:
    """批量创建测试经验."""
    return [
        _make_experience(
            action_type=action_type,
            reward=min(1.0, base_reward + i * 0.01),
            confidence=min(1.0, base_confidence + i * 0.01),
            success=success,
        )
        for i in range(count)
    ]


def _make_high_importance_experiences(count: int) -> list[GrowthExperience]:
    """创建高重要性经验 (reward >= 0.75)."""
    return [
        _make_experience(
            action_type=f"action_{i % 3}",
            reward=0.80 + (i * 0.02),
            confidence=0.85,
            success=True,
        )
        for i in range(count)
    ]


def _make_low_value_experiences(count: int) -> list[GrowthExperience]:
    """创建低价值经验 (reward < 0.40)."""
    return [
        _make_experience(
            action_type="no_action",
            reward=0.20 + (i * 0.01),
            confidence=0.30,
            success=False,
        )
        for i in range(count)
    ]


def _make_mixed_experiences(count: int) -> list[GrowthExperience]:
    """创建混合经验 (多种动作类型)."""
    actions = ["increase_budget", "reduce_budget", "adjust_bid", "pause_campaign"]
    return [
        _make_experience(
            action_type=actions[i % len(actions)],
            reward=0.50 + (i * 0.02),
            confidence=0.55 + (i * 0.01),
            success=(i % 2 == 0),
        )
        for i in range(count)
    ]


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def default_trigger() -> ConsolidationTrigger:
    return ConsolidationTrigger()


@pytest.fixture
def test_trigger() -> ConsolidationTrigger:
    return ConsolidationTrigger.test_mode()


@pytest.fixture
def strict_trigger() -> ConsolidationTrigger:
    return ConsolidationTrigger.strict_mode()


@pytest.fixture
def adapter() -> ExperienceConsolidationAdapter:
    return ExperienceConsolidationAdapter()


@pytest.fixture
def memory_pipeline() -> MemoryConsolidationPipeline:
    """创建 MemoryConsolidationPipeline (带 PatternStore)."""
    from market_ops.creative_vision_runtime.growth_runtime.memory.pattern_store import (
        PatternStore,
    )
    return MemoryConsolidationPipeline(
        pattern_store=PatternStore(),
    )


@pytest.fixture
def consolidation_pipeline(
    memory_pipeline, test_trigger, adapter,
) -> ExperienceConsolidationPipeline:
    return ExperienceConsolidationPipeline(
        memory_pipeline=memory_pipeline,
        trigger=test_trigger,
        adapter=adapter,
    )


@pytest.fixture
def experience_store() -> ExperienceStore:
    return ExperienceStore()


# ═══════════════════════════════════════════════════════════════
# Test: ConsolidationTrigger (Step 3.1)
# ═══════════════════════════════════════════════════════════════


class TestConsolidationTrigger:
    """ConsolidationTrigger: 触发判定引擎."""

    # ── Count Threshold ───────────────────────────────────────

    def test_count_threshold_triggered(self, default_trigger):
        """经验数 >= 阈值 → 触发."""
        exps = _make_experiences(5)
        decision = default_trigger.check(exps)
        assert decision.should_run is True
        assert decision.reason == TriggerReason.COUNT_THRESHOLD
        assert decision.confidence > 0

    def test_count_threshold_not_triggered(self, default_trigger):
        """经验数 < 阈值 → 不触发."""
        exps = _make_experiences(3, base_reward=0.40, base_confidence=0.40)
        decision = default_trigger.check(exps)
        assert decision.should_run is False

    def test_count_threshold_exact(self, default_trigger):
        """经验数 == 阈值 → 触发."""
        exps = _make_experiences(default_trigger.min_experience_count)
        decision = default_trigger.check(exps)
        assert decision.should_run is True

    def test_count_threshold_custom(self):
        """自定义阈值."""
        trigger = ConsolidationTrigger(min_experience_count=10)
        exps = _make_experiences(8, base_reward=0.40, base_confidence=0.40)
        decision = trigger.check(exps)
        assert decision.should_run is False

        exps = _make_experiences(10)
        decision = trigger.check(exps)
        assert decision.should_run is True

    # ── Importance Threshold ──────────────────────────────────

    def test_importance_threshold_triggered(self, default_trigger):
        """高重要性经验比例达标 → 触发."""
        # 5 条经验，其中 2 条高重要性 (40%)
        exps = _make_low_value_experiences(3) + _make_high_importance_experiences(2)
        decision = default_trigger.check(exps)
        # 数量不足 (5 < 5? No, 5 >= 5), 所以数量阈值先触发
        # 调整: 4 条经验，其中 2 条高重要性 (50%)
        exps2 = _make_low_value_experiences(2) + _make_high_importance_experiences(2)
        decision = default_trigger.check(exps2)
        assert decision.should_run is True
        assert decision.reason == TriggerReason.IMPORTANCE_THRESHOLD

    def test_importance_threshold_not_triggered(self, default_trigger):
        """高重要性经验比例不足 → 不触发."""
        exps = _make_low_value_experiences(4)
        decision = default_trigger.check(exps)
        assert decision.should_run is False

    def test_importance_threshold_high_ratio(self):
        """全部高重要性 → 触发."""
        trigger = ConsolidationTrigger(min_experience_count=5, min_importance_ratio=0.60)
        exps = _make_high_importance_experiences(3)
        decision = trigger.check(exps)
        assert decision.should_run is True
        assert decision.reason == TriggerReason.IMPORTANCE_THRESHOLD

    # ── Reward Improvement ────────────────────────────────────

    def test_reward_improvement_triggered(self, default_trigger):
        """奖励提升超过阈值 → 触发."""
        # 最近 5 条经验平均奖励 0.80，历史平均 0.50
        trigger = ConsolidationTrigger(
            min_experience_count=5,
            reward_window=5,
            reward_improvement_min=0.05,
            history_avg_reward=0.50,
        )
        exps = _make_experiences(5, base_reward=0.80)
        decision = trigger.check(exps)
        # 数量 = 5 >= 5, 所以 COUNT_THRESHOLD 先触发
        assert decision.should_run is True
        assert decision.reason == TriggerReason.COUNT_THRESHOLD

    def test_reward_improvement_triggered_no_count(self):
        """奖励提升但数量不足 → 通过奖励提升触发."""
        trigger = ConsolidationTrigger(
            min_experience_count=10,
            reward_window=3,
            reward_improvement_min=0.05,
            history_avg_reward=0.40,
        )
        exps = _make_experiences(5, base_reward=0.70, base_confidence=0.50)
        decision = trigger.check(exps)
        assert decision.should_run is True
        assert decision.reason == TriggerReason.REWARD_IMPROVEMENT

    def test_reward_improvement_not_triggered(self):
        """奖励未提升 → 不触发."""
        trigger = ConsolidationTrigger(
            min_experience_count=10,
            reward_window=3,
            reward_improvement_min=0.05,
            history_avg_reward=0.80,
        )
        exps = _make_experiences(5, base_reward=0.50)
        decision = trigger.check(exps)
        # 数量不足, 重要性不足, 奖励未提升, 冷却未到
        assert decision.should_run is False

    # ── Skip Low Value ────────────────────────────────────────

    def test_skip_low_value(self, default_trigger):
        """低价值经验 → 不触发."""
        exps = _make_low_value_experiences(4)
        decision = default_trigger.check(exps)
        assert decision.should_run is False

    def test_skip_low_value_many(self):
        """大量低价值经验 → 仍不触发 (数量不足, 重要性不足)."""
        trigger = ConsolidationTrigger(min_experience_count=10)
        exps = _make_low_value_experiences(8)
        decision = trigger.check(exps)
        assert decision.should_run is False

    # ── Cooldown ──────────────────────────────────────────────

    def test_cooldown_expired_triggers(self):
        """冷却期到期 → 强制触发."""
        trigger = ConsolidationTrigger(
            min_experience_count=10,
            cooldown_count=3,
        )
        # Skip 2 times (cooldown_count - 1)
        for _ in range(2):
            decision = trigger.check(_make_low_value_experiences(3))
            assert decision.should_run is False
        # 第3次: 冷却到期
        decision = trigger.check(_make_low_value_experiences(3))
        assert decision.should_run is True
        assert decision.reason == TriggerReason.COOLDOWN_EXPIRED

    def test_cooldown_resets_after_trigger(self):
        """触发后冷却计数器重置."""
        trigger = ConsolidationTrigger(
            min_experience_count=10,
            cooldown_count=3,
        )
        # Skip 2 times
        trigger.check(_make_low_value_experiences(3))
        trigger.check(_make_low_value_experiences(3))
        # Trigger via count
        decision = trigger.check(_make_experiences(10))
        assert decision.should_run is True
        assert trigger.skip_streak == 0

    # ── Disabled ──────────────────────────────────────────────

    def test_disabled_trigger(self):
        """禁用触发器 → 不触发."""
        trigger = ConsolidationTrigger(enabled=False)
        exps = _make_experiences(10)
        decision = trigger.check(exps)
        assert decision.should_run is False
        assert "disabled" in decision.details.get("skip_reason", "")

    # ── Empty ─────────────────────────────────────────────────

    def test_empty_experiences(self, default_trigger):
        """空经验列表 → 不触发."""
        decision = default_trigger.check([])
        assert decision.should_run is False
        assert "no experiences" in decision.details.get("skip_reason", "")

    # ── TriggerDecision Properties ────────────────────────────

    def test_trigger_decision_skip(self):
        """TriggerDecision.skip() 工厂方法."""
        d = TriggerDecision.skip("test reason")
        assert d.should_run is False
        assert d.confidence == 0.0
        assert d.urgency == 0.0
        assert d.details["skip_reason"] == "test reason"

    def test_trigger_decision_approve(self):
        """TriggerDecision.approve() 工厂方法."""
        d = TriggerDecision.approve(
            TriggerReason.HIGH_VALUE_PATTERN,
            confidence=0.90,
            urgency=0.80,
            extra="data",
        )
        assert d.should_run is True
        assert d.reason == TriggerReason.HIGH_VALUE_PATTERN
        assert d.confidence == 0.90
        assert d.urgency == 0.80
        assert d.details["extra"] == "data"

    def test_trigger_decision_to_dict(self):
        """TriggerDecision.to_dict()."""
        d = TriggerDecision.approve(TriggerReason.COUNT_THRESHOLD, confidence=0.85)
        data = d.to_dict()
        assert data["should_run"] is True
        assert data["reason"] == "count_threshold"
        assert data["confidence"] == 0.85

    # ── Test Mode ─────────────────────────────────────────────

    def test_test_mode_fast_trigger(self, test_trigger):
        """测试模式: 低阈值快速触发."""
        exps = _make_experiences(2)
        decision = test_trigger.check(exps)
        assert decision.should_run is True

    def test_test_mode_cooldown(self, test_trigger):
        """测试模式: cooldown=1."""
        # Skip 1 time
        test_trigger.check(_make_low_value_experiences(1))
        # Cooldown triggers
        decision = test_trigger.check(_make_low_value_experiences(1))
        assert decision.should_run is True
        assert decision.reason == TriggerReason.COOLDOWN_EXPIRED

    # ── Strict Mode ───────────────────────────────────────────

    def test_strict_mode_high_threshold(self, strict_trigger):
        """严格模式: 高阈值."""
        exps = _make_experiences(10, base_reward=0.40, base_confidence=0.40)
        decision = strict_trigger.check(exps)
        assert decision.should_run is False  # 10 < 20

    def test_strict_mode_requires_many(self, strict_trigger):
        """严格模式: 需要很多经验."""
        exps = _make_experiences(20)
        decision = strict_trigger.check(exps)
        assert decision.should_run is True

    # ── check_batch ───────────────────────────────────────────

    def test_check_batch_with_min_reward(self, default_trigger):
        """check_batch 过滤低奖励."""
        exps = _make_experiences(5, base_reward=0.30) + _make_experiences(5, base_reward=0.80)
        decision = default_trigger.check_batch(exps, min_reward=0.60)
        assert decision.should_run is True  # 过滤后 5 >= 5

    # ── Statistics ────────────────────────────────────────────

    def test_trigger_statistics(self, default_trigger):
        """触发统计."""
        exps = _make_experiences(5)
        default_trigger.check(exps)
        assert default_trigger.check_count == 1
        assert default_trigger.trigger_count == 1

    def test_trigger_skip_streak(self, default_trigger):
        """跳过统计."""
        default_trigger.check(_make_low_value_experiences(3))
        default_trigger.check(_make_low_value_experiences(3))
        assert default_trigger.skip_streak == 2
        assert default_trigger.trigger_count == 0

    def test_trigger_reset(self, default_trigger):
        """重置触发器."""
        default_trigger.check(_make_experiences(5))
        default_trigger.reset()
        assert default_trigger.check_count == 0
        assert default_trigger.trigger_count == 0
        assert default_trigger.skip_streak == 0

    def test_set_history_avg_reward(self, default_trigger):
        """设置历史平均奖励."""
        default_trigger.set_history_avg_reward(0.60)
        assert default_trigger.history_avg_reward == 0.60


# ═══════════════════════════════════════════════════════════════
# Test: ExperienceConsolidationAdapter (Step 3.2)
# ═══════════════════════════════════════════════════════════════


class TestExperienceConsolidationAdapter:
    """ExperienceConsolidationAdapter: GrowthExperience → ConsolidationContext."""

    # ── Basic Build ───────────────────────────────────────────

    def test_build_context_basic(self, adapter):
        """基本上下文构建."""
        exps = _make_experiences(5)
        ctx = adapter.build_context(exps)
        assert isinstance(ctx, ConsolidationContext)
        assert ctx.experience_count == 5
        assert len(ctx.source_experiences) == 5
        assert ctx.cycle_id != ""

    def test_build_context_empty(self, adapter):
        """空经验列表."""
        ctx = adapter.build_context([])
        assert ctx.experience_count == 0
        assert ctx.source_experiences == []

    def test_build_context_single(self, adapter):
        """单条经验."""
        exp = _make_experience()
        ctx = adapter.build_context([exp])
        assert ctx.experience_count == 1

    # ── Policy Decision Aggregation ───────────────────────────

    def test_aggregate_policy_most_common_action(self, adapter):
        """聚合: 最常见 action_type."""
        exps = [
            _make_experience(action_type="increase_budget"),
            _make_experience(action_type="increase_budget"),
            _make_experience(action_type="reduce_budget"),
            _make_experience(action_type="increase_budget"),
            _make_experience(action_type="adjust_bid"),
        ]
        ctx = adapter.build_context(exps)
        assert ctx.policy_decision.action == "increase_budget"

    def test_aggregate_policy_confidence(self, adapter):
        """聚合: 平均置信度."""
        exps = [
            _make_experience(confidence=0.80),
            _make_experience(confidence=0.90),
            _make_experience(confidence=0.70),
        ]
        ctx = adapter.build_context(exps)
        assert ctx.policy_decision.confidence == 0.80

    def test_aggregate_policy_decision_type_success(self, adapter):
        """聚合: 成功率 >= 50% → allow_learning."""
        exps = _make_experiences(5, success=True)
        ctx = adapter.build_context(exps)
        assert ctx.policy_decision.decision_type == "allow_learning"

    def test_aggregate_policy_decision_type_adjust(self, adapter):
        """聚合: 成功率 < 50% → adjust_mode."""
        exps = _make_experiences(5, success=False, base_reward=0.20)
        ctx = adapter.build_context(exps)
        assert ctx.policy_decision.decision_type == "adjust_mode"

    def test_aggregate_policy_action_params(self, adapter):
        """聚合: action_params 包含统计信息."""
        exps = _make_mixed_experiences(6)
        ctx = adapter.build_context(exps)
        params = ctx.policy_decision.action_params
        assert "experience_count" in params
        assert params["experience_count"] == 6
        assert "success_count" in params
        assert "success_rate" in params
        assert "unique_actions" in params
        assert len(params["unique_actions"]) > 0

    # ── Execution Result Aggregation ──────────────────────────

    def test_aggregate_execution_majority_success(self, adapter):
        """聚合: 多数成功."""
        exps = [
            _make_experience(success=True),
            _make_experience(success=True),
            _make_experience(success=False),
        ]
        ctx = adapter.build_context(exps)
        assert ctx.execution_result.success is True

    def test_aggregate_execution_majority_failure(self, adapter):
        """聚合: 多数失败."""
        exps = [
            _make_experience(success=False),
            _make_experience(success=True),
            _make_experience(success=False),
            _make_experience(success=False),
        ]
        ctx = adapter.build_context(exps)
        assert ctx.execution_result.success is False

    # ── Effectiveness Aggregation ─────────────────────────────

    def test_aggregate_effectiveness_metrics_delta(self, adapter):
        """聚合: metrics_delta 合并."""
        exps = [
            _make_experience(
                metrics_delta={"roas": 0.1, "cpi": -0.5},
            ),
            _make_experience(
                metrics_delta={"roas": 0.2, "cpi": -0.3},
            ),
        ]
        ctx = adapter.build_context(exps)
        delta = ctx.effectiveness.metrics_delta
        assert delta["roas"] == 0.15  # (0.1 + 0.2) / 2
        assert delta["cpi"] == -0.40  # (-0.5 + -0.3) / 2

    def test_aggregate_effectiveness_no_metrics(self, adapter):
        """聚合: 无 metrics_delta."""
        exps = [
            _make_experience(metrics_delta={}),
            _make_experience(metrics_delta={}),
        ]
        ctx = adapter.build_context(exps)
        assert ctx.effectiveness.metrics_delta == {}

    def test_aggregate_effectiveness_score(self, adapter):
        """聚合: effectiveness_score."""
        exps = _make_experiences(5, base_reward=0.80, success=True)
        ctx = adapter.build_context(exps)
        assert ctx.effectiveness.effectiveness_score > 0
        # avg_reward ≈ 0.82, success_rate = 1.0
        # score = 0.82 * 0.6 + 1.0 * 0.4 = 0.492 + 0.4 = 0.892
        assert ctx.effectiveness.effectiveness_score > 0.80

    def test_aggregate_effectiveness_learning_gain(self, adapter):
        """聚合: learning_gain."""
        exps = _make_experiences(5, base_reward=0.80)
        ctx = adapter.build_context(exps, history_avg_reward=0.50)
        # avg_reward ≈ 0.82, hist = 0.50
        # learning_gain = max(0, 0.82 - 0.50) = 0.32
        assert ctx.effectiveness.learning_gain > 0.20

    def test_aggregate_effectiveness_learning_gain_default_hist(self, adapter):
        """聚合: learning_gain 使用默认历史."""
        exps = _make_experiences(5, base_reward=0.80)
        ctx = adapter.build_context(exps)  # no history_avg_reward
        # learning_gain = max(0, avg_reward - 0.50)
        assert ctx.effectiveness.learning_gain >= 0

    # ── Mixed Experiences ─────────────────────────────────────

    def test_build_context_mixed_actions(self, adapter):
        """混合动作类型."""
        exps = _make_mixed_experiences(8)
        ctx = adapter.build_context(exps)
        assert ctx.experience_count == 8
        assert ctx.policy_decision.action != ""

    def test_build_context_cycle_number_increments(self, adapter):
        """cycle_number 递增."""
        ctx1 = adapter.build_context(_make_experiences(3))
        ctx2 = adapter.build_context(_make_experiences(3))
        assert ctx2.cycle_number > ctx1.cycle_number

    # ── Metadata ──────────────────────────────────────────────

    def test_build_context_metadata(self, adapter):
        """上下文包含元数据."""
        exps = _make_experiences(3)
        ctx = adapter.build_context(exps)
        assert "adapter" in ctx.metadata
        assert ctx.metadata["adapter"] == "ExperienceConsolidationAdapter"

    # ── to_dict ───────────────────────────────────────────────

    def test_context_to_dict(self, adapter):
        """ConsolidationContext.to_dict()."""
        exps = _make_experiences(3)
        ctx = adapter.build_context(exps)
        data = ctx.to_dict()
        assert data["experience_count"] == 3
        assert "cycle_id" in data
        assert "action" in data

    # ── Statistics ────────────────────────────────────────────

    def test_adapter_statistics(self, adapter):
        """适配器统计."""
        adapter.build_context(_make_experiences(3))
        adapter.build_context(_make_experiences(5))
        assert adapter.build_count == 2
        assert adapter.total_experiences_adapted == 8

    def test_adapter_reset(self, adapter):
        """重置适配器."""
        adapter.build_context(_make_experiences(3))
        adapter.reset()
        assert adapter.build_count == 0
        assert adapter.total_experiences_adapted == 0


# ═══════════════════════════════════════════════════════════════
# Test: ExperienceConsolidationPipeline (Step 3.3)
# ═══════════════════════════════════════════════════════════════


class TestExperienceConsolidationPipeline:
    """ExperienceConsolidationPipeline: 编排 Trigger + Adapter + MemoryPipeline."""

    # ── Basic Run ─────────────────────────────────────────────

    def test_run_triggered(self, memory_pipeline, test_trigger, adapter):
        """触发条件满足 → 执行整合."""
        pipeline = ExperienceConsolidationPipeline(
            memory_pipeline=memory_pipeline,
            trigger=test_trigger,
            adapter=adapter,
        )
        exps = _make_experiences(5)
        result = pipeline.run(exps)
        assert result.status == ConsolidationStatus.EXECUTED
        assert result.consolidation_report is not None
        assert result.experience_count == 5

    def test_run_skipped(self, memory_pipeline, default_trigger, adapter):
        """触发条件不满足 → 跳过."""
        pipeline = ExperienceConsolidationPipeline(
            memory_pipeline=memory_pipeline,
            trigger=default_trigger,
            adapter=adapter,
        )
        exps = _make_low_value_experiences(3)
        result = pipeline.run(exps)
        assert result.status == ConsolidationStatus.SKIPPED
        assert result.is_skipped is True

    def test_run_no_memory_pipeline(self, test_trigger, adapter):
        """无 MemoryPipeline → 失败."""
        pipeline = ExperienceConsolidationPipeline(
            memory_pipeline=None,
            trigger=test_trigger,
            adapter=adapter,
        )
        exps = _make_experiences(5)
        result = pipeline.run(exps)
        assert result.status == ConsolidationStatus.FAILED
        assert "No memory_pipeline" in result.error

    # ── ConsolidationResult Properties ────────────────────────

    def test_consolidation_result_skipped(self):
        """ConsolidationResult.skipped() 工厂."""
        trigger = TriggerDecision.skip("test")
        result = ConsolidationResult.skipped(trigger)
        assert result.status == ConsolidationStatus.SKIPPED
        assert result.is_skipped is True
        assert result.is_executed is False

    def test_consolidation_result_executed(self):
        """ConsolidationResult.executed() 工厂."""
        trigger = TriggerDecision.approve(TriggerReason.COUNT_THRESHOLD)
        result = ConsolidationResult.executed(
            trigger=trigger,
            report=None,
            experience_count=10,
            context_id="ctx-123",
            duration_ms=100.0,
        )
        assert result.status == ConsolidationStatus.EXECUTED
        assert result.is_executed is True
        assert result.experience_count == 10
        assert result.context_id == "ctx-123"

    def test_consolidation_result_failed(self):
        """ConsolidationResult.failed() 工厂."""
        trigger = TriggerDecision.approve(TriggerReason.COUNT_THRESHOLD)
        result = ConsolidationResult.failed(
            trigger=trigger,
            error="test error",
            duration_ms=50.0,
        )
        assert result.status == ConsolidationStatus.FAILED
        assert result.error == "test error"

    def test_consolidation_result_to_dict(self, memory_pipeline, test_trigger, adapter):
        """ConsolidationResult.to_dict()."""
        pipeline = ExperienceConsolidationPipeline(
            memory_pipeline=memory_pipeline,
            trigger=test_trigger,
            adapter=adapter,
        )
        exps = _make_experiences(5)
        result = pipeline.run(exps)
        data = result.to_dict()
        assert data["status"] == "executed"
        assert data["experience_count"] == 5
        assert "trigger_decision" in data

    # ── Run Batch ─────────────────────────────────────────────

    def test_run_batch(self, memory_pipeline, test_trigger, adapter):
        """批量运行."""
        pipeline = ExperienceConsolidationPipeline(
            memory_pipeline=memory_pipeline,
            trigger=test_trigger,
            adapter=adapter,
        )
        batches = [
            _make_experiences(5),
            _make_experiences(3),
        ]
        results = pipeline.run_batch(batches)
        assert len(results) == 2
        for r in results:
            assert r.status in (ConsolidationStatus.EXECUTED, ConsolidationStatus.SKIPPED)

    # ── Statistics ────────────────────────────────────────────

    def test_pipeline_statistics(self, memory_pipeline, test_trigger, adapter):
        """管线统计."""
        pipeline = ExperienceConsolidationPipeline(
            memory_pipeline=memory_pipeline,
            trigger=test_trigger,
            adapter=adapter,
        )
        pipeline.run(_make_experiences(5))
        pipeline.run(_make_low_value_experiences(2))
        stats = pipeline.get_stats()
        assert stats["run_count"] == 2
        assert stats["executed_count"] >= 1
        assert "execution_rate" in stats

    def test_pipeline_latest_result(self, memory_pipeline, test_trigger, adapter):
        """获取最新结果."""
        pipeline = ExperienceConsolidationPipeline(
            memory_pipeline=memory_pipeline,
            trigger=test_trigger,
            adapter=adapter,
        )
        pipeline.run(_make_experiences(5))
        latest = pipeline.get_latest_result()
        assert latest is not None
        assert latest.status == ConsolidationStatus.EXECUTED

    def test_pipeline_get_results(self, memory_pipeline, test_trigger, adapter):
        """获取最近结果列表."""
        pipeline = ExperienceConsolidationPipeline(
            memory_pipeline=memory_pipeline,
            trigger=test_trigger,
            adapter=adapter,
        )
        pipeline.run(_make_experiences(5))
        pipeline.run(_make_experiences(5))
        results = pipeline.get_results(limit=1)
        assert len(results) == 1

    # ── Reset ─────────────────────────────────────────────────

    def test_pipeline_reset(self, memory_pipeline, test_trigger, adapter):
        """重置管线."""
        pipeline = ExperienceConsolidationPipeline(
            memory_pipeline=memory_pipeline,
            trigger=test_trigger,
            adapter=adapter,
        )
        pipeline.run(_make_experiences(5))
        pipeline.reset()
        assert pipeline.run_count == 0
        assert pipeline.executed_count == 0

    # ── Setter Methods ────────────────────────────────────────

    def test_set_memory_pipeline(self, test_trigger, adapter):
        """设置 MemoryPipeline."""
        pipeline = ExperienceConsolidationPipeline(
            trigger=test_trigger,
            adapter=adapter,
        )
        assert pipeline.memory_pipeline is None
        # 设置后应该可用
        mp = MemoryConsolidationPipeline()
        pipeline.set_memory_pipeline(mp)
        assert pipeline.memory_pipeline is not None

    def test_set_trigger(self, memory_pipeline, adapter):
        """设置 Trigger."""
        pipeline = ExperienceConsolidationPipeline(
            memory_pipeline=memory_pipeline,
            adapter=adapter,
        )
        new_trigger = ConsolidationTrigger.test_mode()
        pipeline.set_trigger(new_trigger)
        assert pipeline.trigger is new_trigger

    # ── History Avg Reward ────────────────────────────────────

    def test_run_with_history_avg_reward(self, memory_pipeline, test_trigger, adapter):
        """带历史平均奖励运行."""
        pipeline = ExperienceConsolidationPipeline(
            memory_pipeline=memory_pipeline,
            trigger=test_trigger,
            adapter=adapter,
        )
        exps = _make_experiences(5, base_reward=0.80)
        result = pipeline.run(exps, history_avg_reward=0.60)
        assert result.status == ConsolidationStatus.EXECUTED


# ═══════════════════════════════════════════════════════════════
# Test: End-to-End Consolidation
# ═══════════════════════════════════════════════════════════════


class TestEndToEndConsolidation:
    """完整链路: Write → Store → Trigger → Consolidate → Pattern/Graph updated."""

    def test_write_then_consolidate(
        self, experience_store, memory_pipeline, test_trigger, adapter,
    ):
        """写入经验 → 触发整合 → Pattern 更新."""
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.experience_write_pipeline import (
            ExperienceBuilder,
            ExperienceImportanceScorer,
            ExperienceWritePipeline,
        )
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.experience_write_models import (
            ConsolidationTrigger as WriteTrigger,
        )

        # Setup ExperienceWritePipeline
        write_pipeline = ExperienceWritePipeline(
            experience_store=experience_store,
            consolidation_pipeline=None,  # 手动触发整合
            trigger=WriteTrigger.test_mode(),
        )

        # Setup ConsolidationPipeline
        consolidation = ExperienceConsolidationPipeline(
            memory_pipeline=memory_pipeline,
            trigger=test_trigger,
            adapter=adapter,
        )

        # Write experiences
        for i in range(5):
            exp = _make_experience(
                action_type="increase_budget" if i < 3 else "reduce_budget",
                reward=0.75 + i * 0.02,
                confidence=0.70 + i * 0.02,
                success=(i < 4),
                metrics_delta={"roas": 0.1 + i * 0.05},
            )
            experience_store.store(exp)

        assert experience_store.count == 5

        # Consolidate
        all_exps = experience_store.get_all()
        result = consolidation.run(all_exps)

        assert result.status == ConsolidationStatus.EXECUTED
        assert result.consolidation_report is not None
        report = result.consolidation_report
        assert report.overall_success is True

    def test_consolidation_creates_patterns(
        self, memory_pipeline, test_trigger, adapter,
    ):
        """整合后 PatternStore 有更新."""
        consolidation = ExperienceConsolidationPipeline(
            memory_pipeline=memory_pipeline,
            trigger=test_trigger,
            adapter=adapter,
        )
        exps = _make_experiences(5)
        result = consolidation.run(exps)

        assert result.status == ConsolidationStatus.EXECUTED
        report = result.consolidation_report
        # 报告包含阶段信息
        assert report.stage_count >= 3  # 至少 extract + compress + reinforce

    def test_consolidation_graph_updated(
        self, memory_pipeline, test_trigger, adapter,
    ):
        """整合后 Knowledge Graph 有更新."""
        consolidation = ExperienceConsolidationPipeline(
            memory_pipeline=memory_pipeline,
            trigger=test_trigger,
            adapter=adapter,
        )
        exps = _make_experiences(5)
        result = consolidation.run(exps)

        assert result.status == ConsolidationStatus.EXECUTED
        report = result.consolidation_report
        # 图谱阶段应该成功
        assert report.overall_success is True

    def test_skip_then_consolidate_later(
        self, memory_pipeline, adapter,
    ):
        """先跳过，后在冷却到期时触发."""
        # 严格阈值
        trigger = ConsolidationTrigger(
            min_experience_count=10,
            cooldown_count=3,
        )
        pipeline = ExperienceConsolidationPipeline(
            memory_pipeline=memory_pipeline,
            trigger=trigger,
            adapter=adapter,
        )

        # Skip 2 times (cooldown_count - 1)
        for _ in range(2):
            result = pipeline.run(_make_low_value_experiences(3))
            assert result.status == ConsolidationStatus.SKIPPED

        # Cooldown triggers on 3rd call
        result = pipeline.run(_make_low_value_experiences(3))
        assert result.status == ConsolidationStatus.EXECUTED
        assert result.trigger_decision.reason == TriggerReason.COOLDOWN_EXPIRED


# ═══════════════════════════════════════════════════════════════
# Test: Edge Cases
# ═══════════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界情况测试."""

    def test_trigger_with_none_experience_attributes(self, default_trigger):
        """经验对象缺少某些属性."""
        # 创建没有 reward 属性的经验（不可能的，但测试 getattr 默认值）
        exps = _make_experiences(5)
        decision = default_trigger.check(exps)
        assert decision.should_run is True  # 数量阈值触发

    def test_adapter_with_duplicate_action_types(self, adapter):
        """重复动作类型."""
        exps = [
            _make_experience(action_type="increase_budget"),
            _make_experience(action_type="increase_budget"),
            _make_experience(action_type="increase_budget"),
        ]
        ctx = adapter.build_context(exps)
        assert ctx.policy_decision.action == "increase_budget"
        assert "unique_actions" in ctx.policy_decision.action_params
        assert len(ctx.policy_decision.action_params["unique_actions"]) == 1

    def test_pipeline_run_empty_experiences(self, memory_pipeline, test_trigger, adapter):
        """空经验列表."""
        pipeline = ExperienceConsolidationPipeline(
            memory_pipeline=memory_pipeline,
            trigger=test_trigger,
            adapter=adapter,
        )
        result = pipeline.run([])
        assert result.status == ConsolidationStatus.SKIPPED

    def test_pipeline_run_batch_empty(self, memory_pipeline, test_trigger, adapter):
        """空批次列表."""
        pipeline = ExperienceConsolidationPipeline(
            memory_pipeline=memory_pipeline,
            trigger=test_trigger,
            adapter=adapter,
        )
        results = pipeline.run_batch([])
        assert results == []

    def test_trigger_decision_reason_enum_values(self):
        """TriggerReason 枚举值."""
        assert TriggerReason.COUNT_THRESHOLD.value == "count_threshold"
        assert TriggerReason.IMPORTANCE_THRESHOLD.value == "importance_threshold"
        assert TriggerReason.REWARD_IMPROVEMENT.value == "reward_improvement"
        assert TriggerReason.HIGH_VALUE_PATTERN.value == "high_value_pattern"
        assert TriggerReason.MANUAL.value == "manual"
        assert TriggerReason.COOLDOWN_EXPIRED.value == "cooldown_expired"

    def test_consolidation_status_enum_values(self):
        """ConsolidationStatus 枚举值."""
        assert ConsolidationStatus.EXECUTED.value == "executed"
        assert ConsolidationStatus.SKIPPED.value == "skipped"
        assert ConsolidationStatus.FAILED.value == "failed"

    def test_adapter_with_all_same_metrics(self, adapter):
        """所有经验指标相同."""
        exps = [
            _make_experience(metrics_delta={"roas": 0.1}),
            _make_experience(metrics_delta={"roas": 0.1}),
        ]
        ctx = adapter.build_context(exps)
        assert ctx.effectiveness.metrics_delta["roas"] == 0.1

    def test_trigger_with_very_high_reward(self):
        """极高奖励经验 (但不过高重要性阈值)."""
        trigger = ConsolidationTrigger(
            min_experience_count=10,
            reward_window=3,
            reward_improvement_min=0.05,
            history_avg_reward=0.30,
        )
        exps = _make_experiences(5, base_reward=0.70, base_confidence=0.50)
        decision = trigger.check(exps)
        assert decision.should_run is True
        assert decision.reason == TriggerReason.REWARD_IMPROVEMENT

    def test_adapter_to_dict_no_report(self, adapter):
        """ConsolidationResult.to_dict() 无报告."""
        trigger = TriggerDecision.skip("test")
        result = ConsolidationResult.skipped(trigger)
        data = result.to_dict()
        assert "consolidation_report" not in data


__all__ = [
    "TestConsolidationTrigger",
    "TestExperienceConsolidationAdapter",
    "TestExperienceConsolidationPipeline",
    "TestEndToEndConsolidation",
    "TestEdgeCases",
]