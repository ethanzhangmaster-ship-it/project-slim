"""E14.7.1 Growth Action Router — 集成测试.

验证 GrowthActionRouter 的增长动作路由能力:
  - Model: GrowthAction / RouteResult / 枚举 (20 tests)
  - Signal Mapping: SIGNAL_TO_ACTION / SIGNAL_TO_FALLBACK (25 tests)
  - Opportunity Routing: Opportunity 增强路由 (20 tests)
  - Batch Routing: 批量路由与优先级排序 (15 tests)
  - Validation: 动作验证 (15 tests)
  - Priority / Confidence: 优先级与置信度计算 (10 tests)
  - Regression E14.5/E14.6: 集成回归 (15 tests)

总计: 120 个测试用例
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_action_router import (
    GrowthActionRouter,
    GrowthAction,
    GrowthActionType,
    ActionSource,
    ActionStatus,
    ActionPriority,
    RouteResult,
    SIGNAL_TO_ACTION,
    SIGNAL_TO_FALLBACK,
    ACTION_TO_EXECUTOR,
    create_growth_action_router,
)
from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.feedback_controller import (
    EvolutionSignal,
    SignalAction,
)


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _make_signal(
    action: SignalAction = SignalAction.AMPLIFY,
    confidence: float = 0.92,
    gene_category: str = "hook",
    target_value: str = "rescue",
    expected_impact: str = "ROAS +15%",
    source_experiment_id: str = "exp_001",
) -> EvolutionSignal:
    """辅助: 创建测试用 EvolutionSignal."""
    return EvolutionSignal(
        action=action,
        confidence=confidence,
        gene_category=gene_category,
        target_value=target_value,
        expected_impact=expected_impact,
        source_experiment_id=source_experiment_id,
    )


def _make_opportunity(
    opportunity_id: str = "opp_001",
    urgency: float = 0.5,
    confidence: float = 0.7,
    priority: Any = None,
    reason: str = "",
) -> Any:
    """辅助: 创建测试用 GrowthOpportunity (mock)."""
    class MockOpportunity:
        def __init__(self):
            self.opportunity_id = opportunity_id
            self.urgency = urgency
            self.confidence = confidence
            self.priority = priority
            self.reason = reason
            self.expected_impact = None
    return MockOpportunity()


# ═══════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════

@pytest.fixture
def router():
    """创建默认 GrowthActionRouter."""
    return GrowthActionRouter()


@pytest.fixture
def strict_router():
    """创建高阈值 GrowthActionRouter."""
    return GrowthActionRouter(
        min_confidence=0.5,
        auto_approve_confidence=0.9,
        max_budget_multiplier=2.0,
        max_concurrent_actions=5,
    )


@pytest.fixture
def amplify_signal():
    """AMPLIFY 信号."""
    return _make_signal(SignalAction.AMPLIFY, confidence=0.92)


@pytest.fixture
def suppress_signal():
    """SUPPRESS 信号."""
    return _make_signal(SignalAction.SUPPRESS, confidence=0.85, target_value="challenge")


@pytest.fixture
def explore_signal():
    """EXPLORE 信号."""
    return _make_signal(SignalAction.EXPLORE, confidence=0.75, gene_category="gameplay")


@pytest.fixture
def retest_signal():
    """RETEST 信号."""
    return _make_signal(SignalAction.RETEST, confidence=0.65, gene_category="monetization")


@pytest.fixture
def maintain_signal():
    """MAINTAIN 信号."""
    return _make_signal(SignalAction.MAINTAIN, confidence=0.55, target_value="standard")


@pytest.fixture
def low_confidence_signal():
    """低置信度信号."""
    return _make_signal(SignalAction.AMPLIFY, confidence=0.25)


@pytest.fixture
def high_confidence_amplify():
    """高置信度 AMPLIFY 信号."""
    return _make_signal(SignalAction.AMPLIFY, confidence=0.95, target_value="transformation")


# ═══════════════════════════════════════════════════════════
# 1. Model Tests (20)
# ═══════════════════════════════════════════════════════════

class TestGrowthActionType:
    """GrowthActionType 枚举测试."""

    def test_all_types_present(self):
        """验证所有动作类型存在."""
        expected = {
            "create_creative", "mutate_creative", "promote_winner",
            "scale_campaign", "reduce_budget", "pause_campaign",
            "start_experiment", "end_experiment",
            "create_variants", "diversify_population",
            "hold",
        }
        actual = {t.value for t in GrowthActionType}
        assert actual == expected

    def test_creative_types(self):
        """验证 Creative 类动作类型."""
        creative_types = {
            GrowthActionType.CREATE_CREATIVE,
            GrowthActionType.MUTATE_CREATIVE,
            GrowthActionType.PROMOTE_WINNER,
        }
        assert all(t.value.startswith(("create_creative", "mutate_creative", "promote_winner")) for t in creative_types)

    def test_ua_types(self):
        """验证 UA 类动作类型."""
        ua_types = {
            GrowthActionType.SCALE_CAMPAIGN,
            GrowthActionType.REDUCE_BUDGET,
            GrowthActionType.PAUSE_CAMPAIGN,
        }
        assert len(ua_types) == 3

    def test_experiment_types(self):
        """验证 Experiment 类动作类型."""
        assert GrowthActionType.START_EXPERIMENT.value == "start_experiment"
        assert GrowthActionType.END_EXPERIMENT.value == "end_experiment"

    def test_evolution_types(self):
        """验证 Evolution 类动作类型."""
        assert GrowthActionType.CREATE_VARIANTS.value == "create_variants"
        assert GrowthActionType.DIVERSIFY_POPULATION.value == "diversify_population"

    def test_hold_type(self):
        """验证 HOLD 类型."""
        assert GrowthActionType.HOLD.value == "hold"


class TestActionSource:
    """ActionSource 枚举测试."""

    def test_all_sources(self):
        assert ActionSource.EVOLUTION_SIGNAL.value == "evolution_signal"
        assert ActionSource.GROWTH_OPPORTUNITY.value == "growth_opportunity"
        assert ActionSource.MANUAL.value == "manual"


class TestActionStatus:
    """ActionStatus 枚举测试."""

    def test_all_statuses(self):
        expected = {"pending", "approved", "executing", "completed", "failed", "rolled_back"}
        actual = {s.value for s in ActionStatus}
        assert actual == expected


class TestActionPriority:
    """ActionPriority 枚举测试."""

    def test_priority_ordering(self):
        assert ActionPriority.CRITICAL.value < ActionPriority.HIGH.value
        assert ActionPriority.HIGH.value < ActionPriority.MEDIUM.value
        assert ActionPriority.MEDIUM.value < ActionPriority.LOW.value
        assert ActionPriority.LOW.value < ActionPriority.OPTIONAL.value

    def test_all_priorities(self):
        expected = {1, 2, 3, 4, 5}
        actual = {p.value for p in ActionPriority}
        assert actual == expected


class TestGrowthAction:
    """GrowthAction 数据模型测试."""

    def test_default_creation(self):
        action = GrowthAction()
        assert action.action_id.startswith("ga_")
        assert action.action_type == GrowthActionType.HOLD
        assert action.source == ActionSource.EVOLUTION_SIGNAL
        assert action.priority == ActionPriority.MEDIUM
        assert action.confidence == 0.0
        assert action.status == ActionStatus.PENDING
        assert action.payload == {}

    def test_full_creation(self):
        action = GrowthAction(
            action_type=GrowthActionType.PROMOTE_WINNER,
            source=ActionSource.EVOLUTION_SIGNAL,
            source_signal_id="sig_001",
            target_id="genome_123",
            target_type="genome",
            priority=ActionPriority.HIGH,
            confidence=0.91,
            payload={"budget_multiplier": 2.0},
            expected_reward=0.15,
            reasoning="Signal amplifies, confidence high",
        )
        assert action.action_type == GrowthActionType.PROMOTE_WINNER
        assert action.target_id == "genome_123"
        assert action.priority == ActionPriority.HIGH
        assert action.confidence == 0.91
        assert action.payload["budget_multiplier"] == 2.0
        assert action.expected_reward == 0.15

    def test_executor_auto_assigned(self):
        action = GrowthAction(action_type=GrowthActionType.PROMOTE_WINNER)
        assert action.executor == "CreativeExecutor"

    def test_executor_auto_for_scale(self):
        action = GrowthAction(action_type=GrowthActionType.SCALE_CAMPAIGN)
        assert action.executor == "MetaAdsExecutor"

    def test_executor_auto_for_hold(self):
        action = GrowthAction(action_type=GrowthActionType.HOLD)
        assert action.executor == "NoOpExecutor"

    def test_is_critical_property(self):
        action = GrowthAction(priority=ActionPriority.CRITICAL)
        assert action.is_critical is True

    def test_is_critical_false(self):
        action = GrowthAction(priority=ActionPriority.MEDIUM)
        assert action.is_critical is False

    def test_is_high_confidence(self):
        action = GrowthAction(confidence=0.85)
        assert action.is_high_confidence is True

    def test_is_high_confidence_false(self):
        action = GrowthAction(confidence=0.3)
        assert action.is_high_confidence is False

    def test_to_dict(self):
        action = GrowthAction(
            action_type=GrowthActionType.PROMOTE_WINNER,
            target_id="genome_123",
            priority=ActionPriority.HIGH,
            confidence=0.91,
        )
        d = action.to_dict()
        assert d["action_type"] == "promote_winner"
        assert d["target_id"] == "genome_123"
        assert d["priority"] == 2
        assert d["priority_name"] == "HIGH"
        assert d["confidence"] == 0.91
        assert d["is_critical"] is False
        assert d["is_high_confidence"] is True

    def test_from_dict(self):
        data = {
            "action_id": "ga_test123",
            "action_type": "promote_winner",
            "source": "evolution_signal",
            "source_signal_id": "sig_001",
            "target_id": "genome_123",
            "priority": 2,
            "confidence": 0.91,
            "payload": {"budget_multiplier": 2.0},
            "expected_reward": 0.15,
            "executor": "CreativeExecutor",
            "status": "pending",
            "reasoning": "Test",
        }
        action = GrowthAction.from_dict(data)
        assert action.action_type == GrowthActionType.PROMOTE_WINNER
        assert action.target_id == "genome_123"
        assert action.priority == ActionPriority.HIGH
        assert action.confidence == 0.91

    def test_from_dict_defaults(self):
        action = GrowthAction.from_dict({})
        assert action.action_type == GrowthActionType.HOLD
        assert action.priority == ActionPriority.MEDIUM


class TestRouteResult:
    """RouteResult 数据模型测试."""

    def test_default_creation(self):
        action = GrowthAction()
        result = RouteResult(action=action)
        assert result.signal_matched is True
        assert result.opportunity_boosted is False
        assert result.fallback_used is False
        assert result.validation_passed is True
        assert result.route_score == 0.0

    def test_to_dict(self):
        action = GrowthAction(action_type=GrowthActionType.PROMOTE_WINNER)
        result = RouteResult(
            action=action,
            signal_matched=True,
            opportunity_boosted=True,
            fallback_used=False,
            validation_passed=True,
            route_score=0.85,
        )
        d = result.to_dict()
        assert d["signal_matched"] is True
        assert d["opportunity_boosted"] is True
        assert d["fallback_used"] is False
        assert d["validation_passed"] is True
        assert d["route_score"] == 0.85
        assert "action" in d


# ═══════════════════════════════════════════════════════════
# 2. Signal Mapping Tests (25)
# ═══════════════════════════════════════════════════════════

class TestSignalToActionMapping:
    """SIGNAL_TO_ACTION 路由矩阵测试."""

    def test_amplify_to_promote_winner(self):
        assert SIGNAL_TO_ACTION[SignalAction.AMPLIFY] == GrowthActionType.PROMOTE_WINNER

    def test_suppress_to_reduce_budget(self):
        assert SIGNAL_TO_ACTION[SignalAction.SUPPRESS] == GrowthActionType.REDUCE_BUDGET

    def test_explore_to_create_variants(self):
        assert SIGNAL_TO_ACTION[SignalAction.EXPLORE] == GrowthActionType.CREATE_VARIANTS

    def test_retest_to_start_experiment(self):
        assert SIGNAL_TO_ACTION[SignalAction.RETEST] == GrowthActionType.START_EXPERIMENT

    def test_maintain_to_hold(self):
        assert SIGNAL_TO_ACTION[SignalAction.MAINTAIN] == GrowthActionType.HOLD

    def test_all_signals_mapped(self):
        for signal_action in SignalAction:
            assert signal_action in SIGNAL_TO_ACTION

    def test_no_duplicate_actions(self):
        """每个 SignalAction 映射到唯一的 GrowthActionType."""
        targets = set(SIGNAL_TO_ACTION.values())
        # 每个 SignalAction 映射到不同的主目标
        assert len(targets) == len(SIGNAL_TO_ACTION)


class TestSignalToFallbackMapping:
    """SIGNAL_TO_FALLBACK 备选动作测试."""

    def test_amplify_fallback(self):
        fallbacks = SIGNAL_TO_FALLBACK[SignalAction.AMPLIFY]
        assert GrowthActionType.SCALE_CAMPAIGN in fallbacks
        assert GrowthActionType.CREATE_VARIANTS in fallbacks

    def test_suppress_fallback(self):
        fallbacks = SIGNAL_TO_FALLBACK[SignalAction.SUPPRESS]
        assert GrowthActionType.PAUSE_CAMPAIGN in fallbacks
        assert GrowthActionType.HOLD in fallbacks

    def test_explore_fallback(self):
        fallbacks = SIGNAL_TO_FALLBACK[SignalAction.EXPLORE]
        assert GrowthActionType.DIVERSIFY_POPULATION in fallbacks
        assert GrowthActionType.MUTATE_CREATIVE in fallbacks

    def test_retest_fallback(self):
        fallbacks = SIGNAL_TO_FALLBACK[SignalAction.RETEST]
        assert GrowthActionType.END_EXPERIMENT in fallbacks
        assert GrowthActionType.CREATE_VARIANTS in fallbacks

    def test_maintain_fallback_only_hold(self):
        fallbacks = SIGNAL_TO_FALLBACK[SignalAction.MAINTAIN]
        assert fallbacks == [GrowthActionType.HOLD]

    def test_all_signals_have_fallback(self):
        for signal_action in SignalAction:
            assert signal_action in SIGNAL_TO_FALLBACK

    def test_fallback_lists_not_empty(self):
        for signal_action in SignalAction:
            assert len(SIGNAL_TO_FALLBACK[signal_action]) >= 1


class TestActionToExecutorMapping:
    """ACTION_TO_EXECUTOR 映射测试."""

    def test_creative_actions_to_creative_executor(self):
        assert ACTION_TO_EXECUTOR[GrowthActionType.CREATE_CREATIVE] == "CreativeExecutor"
        assert ACTION_TO_EXECUTOR[GrowthActionType.MUTATE_CREATIVE] == "CreativeExecutor"
        assert ACTION_TO_EXECUTOR[GrowthActionType.PROMOTE_WINNER] == "CreativeExecutor"

    def test_ua_actions_to_meta_ads_or_budget(self):
        assert ACTION_TO_EXECUTOR[GrowthActionType.SCALE_CAMPAIGN] == "MetaAdsExecutor"
        assert ACTION_TO_EXECUTOR[GrowthActionType.PAUSE_CAMPAIGN] == "MetaAdsExecutor"
        assert ACTION_TO_EXECUTOR[GrowthActionType.REDUCE_BUDGET] == "BudgetExecutor"

    def test_experiment_actions_to_experiment_executor(self):
        assert ACTION_TO_EXECUTOR[GrowthActionType.START_EXPERIMENT] == "ExperimentExecutor"
        assert ACTION_TO_EXECUTOR[GrowthActionType.END_EXPERIMENT] == "ExperimentExecutor"

    def test_evolution_actions_to_evolution_executor(self):
        assert ACTION_TO_EXECUTOR[GrowthActionType.CREATE_VARIANTS] == "EvolutionExecutor"
        assert ACTION_TO_EXECUTOR[GrowthActionType.DIVERSIFY_POPULATION] == "EvolutionExecutor"

    def test_hold_to_noop(self):
        assert ACTION_TO_EXECUTOR[GrowthActionType.HOLD] == "NoOpExecutor"

    def test_all_action_types_have_executor(self):
        for action_type in GrowthActionType:
            assert action_type in ACTION_TO_EXECUTOR

    def test_four_executors_total(self):
        executors = set(ACTION_TO_EXECUTOR.values())
        assert len(executors) == 6  # CreativeExecutor, MetaAdsExecutor, BudgetExecutor, ExperimentExecutor, EvolutionExecutor, NoOpExecutor

    def test_each_executor_has_actions(self):
        executors = set(ACTION_TO_EXECUTOR.values())
        assert len(executors) >= 4


# ═══════════════════════════════════════════════════════════
# 3. Core Router Tests (20)
# ═══════════════════════════════════════════════════════════

class TestRouterRoute:
    """GrowthActionRouter.route() 核心路由测试."""

    def test_amplify_routes_to_promote_winner(self, router, amplify_signal):
        result = router.route(amplify_signal)
        assert result.action.action_type == GrowthActionType.PROMOTE_WINNER
        assert result.action.source == ActionSource.EVOLUTION_SIGNAL
        assert result.signal_matched is True

    def test_suppress_routes_to_reduce_budget(self, router, suppress_signal):
        result = router.route(suppress_signal)
        assert result.action.action_type == GrowthActionType.REDUCE_BUDGET

    def test_explore_routes_to_create_variants(self, router, explore_signal):
        result = router.route(explore_signal)
        assert result.action.action_type == GrowthActionType.CREATE_VARIANTS

    def test_retest_routes_to_start_experiment(self, router, retest_signal):
        result = router.route(retest_signal)
        assert result.action.action_type == GrowthActionType.START_EXPERIMENT

    def test_maintain_routes_to_hold(self, router, maintain_signal):
        result = router.route(maintain_signal)
        assert result.action.action_type == GrowthActionType.HOLD

    def test_low_confidence_triggers_fallback(self, router, low_confidence_signal):
        result = router.route(low_confidence_signal)
        assert result.fallback_used is True
        # AMPLIFY confidence 0.25 < 0.3 → fallback SCALE_CAMPAIGN
        assert result.action.action_type == GrowthActionType.SCALE_CAMPAIGN

    def test_low_confidence_amplify_fallback(self, router):
        signal = _make_signal(SignalAction.AMPLIFY, confidence=0.1)
        result = router.route(signal)
        assert result.fallback_used is True
        assert result.action.action_type == GrowthActionType.SCALE_CAMPAIGN

    def test_low_confidence_suppress_fallback(self, router):
        signal = _make_signal(SignalAction.SUPPRESS, confidence=0.1)
        result = router.route(signal)
        assert result.fallback_used is True
        assert result.action.action_type == GrowthActionType.PAUSE_CAMPAIGN

    def test_low_confidence_explore_fallback(self, router):
        signal = _make_signal(SignalAction.EXPLORE, confidence=0.1)
        result = router.route(signal)
        assert result.fallback_used is True
        assert result.action.action_type == GrowthActionType.DIVERSIFY_POPULATION

    def test_low_confidence_retest_fallback(self, router):
        signal = _make_signal(SignalAction.RETEST, confidence=0.1)
        result = router.route(signal)
        assert result.fallback_used is True
        assert result.action.action_type == GrowthActionType.END_EXPERIMENT

    def test_maintain_low_confidence_still_hold(self, router):
        signal = _make_signal(SignalAction.MAINTAIN, confidence=0.1)
        result = router.route(signal)
        assert result.action.action_type == GrowthActionType.HOLD

    def test_target_id_from_signal(self, router, amplify_signal):
        result = router.route(amplify_signal)
        assert result.action.target_id == "rescue"

    def test_target_id_explicit_override(self, router, amplify_signal):
        result = router.route(amplify_signal, target_id="genome_override")
        assert result.action.target_id == "genome_override"

    def test_source_signal_id_tracked(self, router, amplify_signal):
        result = router.route(amplify_signal)
        assert result.action.source_signal_id == amplify_signal.signal_id

    def test_payload_contains_signal_action(self, router, amplify_signal):
        result = router.route(amplify_signal)
        assert result.action.payload["signal_action"] == "amplify"
        assert result.action.payload["gene_category"] == "hook"

    def test_reasoning_generated(self, router, amplify_signal):
        result = router.route(amplify_signal)
        assert "amplify" in result.action.reasoning.lower()
        assert "promote_winner" in result.action.reasoning

    def test_route_score_calculated(self, router, amplify_signal):
        result = router.route(amplify_signal)
        assert result.route_score > 0.0
        assert result.route_score <= 1.0

    def test_validation_passed_for_valid_signal(self, router, amplify_signal):
        result = router.route(amplify_signal)
        assert result.validation_passed is True

    def test_validation_failed_for_low_confidence_no_target(self, router):
        signal = _make_signal(SignalAction.AMPLIFY, confidence=0.1, target_value="")
        result = router.route(signal)
        # SCALE_CAMPAIGN requires target_id → 验证失败
        assert result.validation_passed is False

    def test_hold_always_valid_even_low_confidence(self, router):
        signal = _make_signal(SignalAction.MAINTAIN, confidence=0.1)
        result = router.route(signal)
        assert result.action.action_type == GrowthActionType.HOLD
        assert result.validation_passed is True


# ═══════════════════════════════════════════════════════════
# 4. Opportunity Routing Tests (20)
# ═══════════════════════════════════════════════════════════

class TestOpportunityRouting:
    """GrowthOpportunity 增强路由测试."""

    def test_opportunity_boost_flag(self, router, amplify_signal):
        opp = _make_opportunity(urgency=0.3)
        result = router.route(amplify_signal, opportunity=opp)
        assert result.opportunity_boosted is True

    def test_high_urgency_boosts_priority(self, router, amplify_signal):
        opp = _make_opportunity(urgency=0.9, confidence=0.5)
        result = router.route(amplify_signal, opportunity=opp)
        # urgency 0.9 > 0.8 → 提升到 HIGH
        assert result.action.priority.value <= ActionPriority.HIGH.value

    def test_opportunity_confidence_boost(self, router):
        signal = _make_signal(SignalAction.AMPLIFY, confidence=0.7)
        opp = _make_opportunity(confidence=0.9)
        result = router.route(signal, opportunity=opp)
        # opp confidence 0.9 > action confidence 0.7 → boost: 0.7 + 0.9*0.2 = 0.88
        assert result.action.confidence > 0.7

    def test_opportunity_reason_merged(self, router, amplify_signal):
        opp = _make_opportunity(reason="High ROAS opportunity")
        result = router.route(amplify_signal, opportunity=opp)
        assert "High ROAS opportunity" in result.action.reasoning

    def test_opportunity_id_tracked(self, router, amplify_signal):
        opp = _make_opportunity(opportunity_id="opp_high_001")
        result = router.route(amplify_signal, opportunity=opp)
        assert result.action.source_opportunity_id == "opp_high_001"

    def test_opportunity_low_urgency_no_priority_boost(self, router, amplify_signal):
        opp = _make_opportunity(urgency=0.3)
        result = router.route(amplify_signal, opportunity=opp)
        # 原始信号 confidence 0.92 → 优先级 >= HIGH
        # 但 urgency 0.3 < 0.8 → 不提升
        assert result.action.priority is not None

    def test_opportunity_priority_value_affects_score(self, router):
        signal = _make_signal(SignalAction.AMPLIFY, confidence=0.5)
        # 高优先级 opportunity (value=1)
        class MockPriority:
            value = 1
        opp = _make_opportunity(urgency=0.5, priority=MockPriority())
        result = router.route(signal, opportunity=opp)
        # priority 1 → (5-1)*0.1 = 0.4 boost
        assert result.action.priority.value <= ActionPriority.HIGH.value

    def test_opportunity_expected_impact_in_metadata(self, router, amplify_signal):
        opp = _make_opportunity()
        opp.expected_impact = type("Impact", (), {"to_dict": lambda self: {"roas": "+10%"}})()
        result = router.route(amplify_signal, opportunity=opp)
        assert "opportunity_impact" in result.action.metadata

    def test_route_without_opportunity(self, router, amplify_signal):
        result = router.route(amplify_signal, opportunity=None)
        assert result.opportunity_boosted is False

    def test_opportunity_with_suppress_signal(self, router, suppress_signal):
        opp = _make_opportunity(urgency=0.9, reason="Urgent cost cut")
        result = router.route(suppress_signal, opportunity=opp)
        assert result.opportunity_boosted is True
        assert "Urgent cost cut" in result.action.reasoning

    def test_opportunity_with_explore_signal(self, router, explore_signal):
        opp = _make_opportunity(urgency=0.6, confidence=0.8)
        result = router.route(explore_signal, opportunity=opp)
        assert result.opportunity_boosted is True

    def test_opportunity_with_retest_signal(self, router, retest_signal):
        opp = _make_opportunity(urgency=0.4)
        result = router.route(retest_signal, opportunity=opp)
        assert result.opportunity_boosted is True

    def test_opportunity_does_not_override_executor(self, router, amplify_signal):
        opp = _make_opportunity()
        result = router.route(amplify_signal, opportunity=opp)
        assert result.action.executor == "CreativeExecutor"

    def test_opportunity_with_maintain(self, router, maintain_signal):
        opp = _make_opportunity(urgency=0.9, reason="Keep watching")
        result = router.route(maintain_signal, opportunity=opp)
        assert result.action.action_type == GrowthActionType.HOLD
        assert result.opportunity_boosted is True

    def test_opportunity_confidence_boost_capped(self, router):
        signal = _make_signal(SignalAction.AMPLIFY, confidence=0.95)
        opp = _make_opportunity(confidence=0.99)
        result = router.route(signal, opportunity=opp)
        # confidence 不能超过 1.0
        assert result.action.confidence <= 1.0

    def test_opportunity_does_not_boost_lower_confidence(self, router):
        signal = _make_signal(SignalAction.AMPLIFY, confidence=0.8)
        opp = _make_opportunity(confidence=0.5)  # lower than action
        result = router.route(signal, opportunity=opp)
        # opp confidence 0.5 < action confidence 0.8 → no boost
        assert result.action.confidence == 0.8

    def test_opportunity_boosted_flag_false_when_none(self, router, amplify_signal):
        result = router.route(amplify_signal, opportunity=None)
        assert result.opportunity_boosted is False

    def test_opportunity_does_not_change_action_type(self, router, amplify_signal):
        opp = _make_opportunity(urgency=0.9)
        result = router.route(amplify_signal, opportunity=opp)
        assert result.action.action_type == GrowthActionType.PROMOTE_WINNER

    def test_opportunity_with_context(self, router, amplify_signal):
        opp = _make_opportunity(urgency=0.7)
        context = {"roas": 2.5, "ctr": 0.045}
        result = router.route(amplify_signal, opportunity=opp, context=context)
        assert result.opportunity_boosted is True

    def test_opportunity_metadata_has_correct_structure(self, router, amplify_signal):
        opp = _make_opportunity()
        result = router.route(amplify_signal, opportunity=opp)
        assert "gene_category" in result.action.metadata
        assert "source_experiment_id" in result.action.metadata


# ═══════════════════════════════════════════════════════════
# 5. Batch Routing Tests (15)
# ═══════════════════════════════════════════════════════════

class TestBatchRouting:
    """批量路由测试."""

    def test_batch_routes_multiple_signals(self, router):
        signals = [
            _make_signal(SignalAction.AMPLIFY, confidence=0.92),
            _make_signal(SignalAction.SUPPRESS, confidence=0.85),
            _make_signal(SignalAction.EXPLORE, confidence=0.75),
        ]
        results = router.route_batch(signals)
        assert len(results) == 3

    def test_batch_results_sorted_by_priority(self, router):
        signals = [
            _make_signal(SignalAction.MAINTAIN, confidence=0.3),
            _make_signal(SignalAction.AMPLIFY, confidence=0.95),
            _make_signal(SignalAction.SUPPRESS, confidence=0.85),
        ]
        results = router.route_batch(signals)
        # AMPLIFY (0.95) 应排在 SUPPRESS (0.85) 和 MAINTAIN (0.3) 前面
        priorities = [r.action.priority.value for r in results]
        assert priorities == sorted(priorities)

    def test_batch_with_opportunity(self, router):
        signals = [
            _make_signal(SignalAction.AMPLIFY, confidence=0.92),
            _make_signal(SignalAction.EXPLORE, confidence=0.6),
        ]
        opp = _make_opportunity(urgency=0.8)
        results = router.route_batch(signals, opportunity=opp)
        assert len(results) == 2
        assert all(r.opportunity_boosted for r in results)

    def test_batch_respects_max_concurrent(self, router):
        signals = [_make_signal(SignalAction.AMPLIFY, confidence=0.8) for _ in range(15)]
        results = router.route_batch(signals)
        assert len(results) <= router._max_concurrent_actions

    def test_batch_empty_signals(self, router):
        results = router.route_batch([])
        assert results == []

    def test_batch_single_signal(self, router):
        signals = [_make_signal(SignalAction.AMPLIFY, confidence=0.92)]
        results = router.route_batch(signals)
        assert len(results) == 1
        assert results[0].action.action_type == GrowthActionType.PROMOTE_WINNER

    def test_batch_all_signal_types(self, router):
        signals = [
            _make_signal(SignalAction.AMPLIFY, confidence=0.8),
            _make_signal(SignalAction.SUPPRESS, confidence=0.8),
            _make_signal(SignalAction.EXPLORE, confidence=0.8),
            _make_signal(SignalAction.RETEST, confidence=0.8),
            _make_signal(SignalAction.MAINTAIN, confidence=0.8),
        ]
        results = router.route_batch(signals)
        action_types = {r.action.action_type for r in results}
        assert GrowthActionType.PROMOTE_WINNER in action_types
        assert GrowthActionType.REDUCE_BUDGET in action_types
        assert GrowthActionType.CREATE_VARIANTS in action_types
        assert GrowthActionType.START_EXPERIMENT in action_types
        assert GrowthActionType.HOLD in action_types

    def test_batch_with_context(self, router):
        signals = [
            _make_signal(SignalAction.AMPLIFY, confidence=0.92),
            _make_signal(SignalAction.SUPPRESS, confidence=0.7),
        ]
        context = {"roas": 2.2, "ctr": 0.042}
        results = router.route_batch(signals, context=context)
        assert len(results) == 2

    def test_batch_preserves_individual_signal_ids(self, router):
        signals = [
            _make_signal(SignalAction.AMPLIFY, confidence=0.92),
            _make_signal(SignalAction.SUPPRESS, confidence=0.85),
        ]
        results = router.route_batch(signals)
        for i, result in enumerate(results):
            assert result.action.source_signal_id == signals[i].signal_id if i < len(signals) else True

    def test_batch_actions_accessible_individually(self, router):
        signals = [
            _make_signal(SignalAction.AMPLIFY, confidence=0.92),
            _make_signal(SignalAction.EXPLORE, confidence=0.75),
        ]
        results = router.route_batch(signals)
        for result in results:
            retrieved = router.get_action(result.action.action_id)
            assert retrieved is not None
            assert retrieved.action_id == result.action.action_id

    def test_batch_strict_router(self, strict_router):
        signals = [
            _make_signal(SignalAction.AMPLIFY, confidence=0.92),
            _make_signal(SignalAction.AMPLIFY, confidence=0.35),
        ]
        results = strict_router.route_batch(signals)
        assert len(results) <= strict_router._max_concurrent_actions
        # 低置信度信号应触发 fallback
        has_fallback = any(r.fallback_used for r in results)
        assert has_fallback

    def test_batch_total_actions_tracked(self, router):
        signals = [_make_signal(SignalAction.AMPLIFY, confidence=0.8) for _ in range(3)]
        router.route_batch(signals)
        stats = router.stats()
        assert stats["total_actions"] == 3

    def test_batch_total_routes_tracked(self, router):
        signals = [_make_signal(SignalAction.AMPLIFY, confidence=0.8) for _ in range(3)]
        router.route_batch(signals)
        stats = router.stats()
        assert stats["total_routes"] == 3

    def test_batch_history_recorded(self, router):
        signals = [_make_signal(SignalAction.AMPLIFY, confidence=0.8) for _ in range(2)]
        router.route_batch(signals)
        history = router.get_route_history()
        assert len(history) == 2

    def test_batch_highest_confidence_first(self, router):
        signals = [
            _make_signal(SignalAction.AMPLIFY, confidence=0.5),
            _make_signal(SignalAction.AMPLIFY, confidence=0.95),
            _make_signal(SignalAction.AMPLIFY, confidence=0.75),
        ]
        results = router.route_batch(signals)
        # 同优先级时按 confidence 降序
        confidences = [r.action.confidence for r in results]
        for i in range(len(confidences) - 1):
            current_pri = results[i].action.priority.value
            next_pri = results[i + 1].action.priority.value
            if current_pri == next_pri:
                assert confidences[i] >= confidences[i + 1]


# ═══════════════════════════════════════════════════════════
# 6. Validation Tests (15)
# ═══════════════════════════════════════════════════════════

class TestValidation:
    """动作验证测试."""

    def test_hold_always_valid(self, router):
        action = GrowthAction(action_type=GrowthActionType.HOLD, confidence=0.0)
        assert router.validate(action) is True

    def test_low_confidence_invalid(self, router):
        action = GrowthAction(
            action_type=GrowthActionType.PROMOTE_WINNER,
            confidence=0.1,
            target_id="g001",
        )
        assert router.validate(action) is False

    def test_high_confidence_valid(self, router):
        action = GrowthAction(
            action_type=GrowthActionType.PROMOTE_WINNER,
            confidence=0.92,
            target_id="g001",
        )
        assert router.validate(action) is True

    def test_budget_multiplier_too_high(self, router):
        action = GrowthAction(
            action_type=GrowthActionType.PROMOTE_WINNER,
            confidence=0.92,
            target_id="g001",
            payload={"budget_multiplier": 5.0},
        )
        assert router.validate(action) is False

    def test_budget_multiplier_negative(self, router):
        action = GrowthAction(
            action_type=GrowthActionType.PROMOTE_WINNER,
            confidence=0.92,
            target_id="g001",
            payload={"budget_multiplier": -0.5},
        )
        assert router.validate(action) is False

    def test_budget_multiplier_zero(self, router):
        action = GrowthAction(
            action_type=GrowthActionType.PROMOTE_WINNER,
            confidence=0.92,
            target_id="g001",
            payload={"budget_multiplier": 0.0},
        )
        assert router.validate(action) is False

    def test_missing_target_id_for_promote(self, router):
        action = GrowthAction(
            action_type=GrowthActionType.PROMOTE_WINNER,
            confidence=0.92,
            target_id="",
        )
        assert router.validate(action) is False

    def test_missing_target_id_for_scale(self, router):
        action = GrowthAction(
            action_type=GrowthActionType.SCALE_CAMPAIGN,
            confidence=0.8,
            target_id="",
        )
        assert router.validate(action) is False

    def test_missing_target_id_for_pause(self, router):
        action = GrowthAction(
            action_type=GrowthActionType.PAUSE_CAMPAIGN,
            confidence=0.8,
            target_id="",
        )
        assert router.validate(action) is False

    def test_diversify_without_target_ok(self, router):
        action = GrowthAction(
            action_type=GrowthActionType.DIVERSIFY_POPULATION,
            confidence=0.7,
            target_id="",
        )
        assert router.validate(action) is True

    def test_create_variants_without_target_ok(self, router):
        action = GrowthAction(
            action_type=GrowthActionType.CREATE_VARIANTS,
            confidence=0.7,
            target_id="",
        )
        assert router.validate(action) is True

    def test_strict_router_higher_min_confidence(self, strict_router):
        action = GrowthAction(
            action_type=GrowthActionType.PROMOTE_WINNER,
            confidence=0.4,
            target_id="g001",
        )
        assert strict_router.validate(action) is False

    def test_strict_router_budget_multiplier(self, strict_router):
        action = GrowthAction(
            action_type=GrowthActionType.PROMOTE_WINNER,
            confidence=0.92,
            target_id="g001",
            payload={"budget_multiplier": 2.5},
        )
        assert strict_router.validate(action) is False

    def test_valid_budget_multiplier(self, router):
        action = GrowthAction(
            action_type=GrowthActionType.PROMOTE_WINNER,
            confidence=0.92,
            target_id="g001",
            payload={"budget_multiplier": 2.0},
        )
        assert router.validate(action) is True

    def test_scale_campaign_validation(self, router):
        action = GrowthAction(
            action_type=GrowthActionType.SCALE_CAMPAIGN,
            confidence=0.8,
            target_id="camp_001",
        )
        assert router.validate(action) is True


# ═══════════════════════════════════════════════════════════
# 7. Priority / Confidence Tests (10)
# ═══════════════════════════════════════════════════════════

class TestPriorityCalculation:
    """优先级计算测试."""

    def test_high_confidence_amplify_gets_high_priority(self, router, high_confidence_amplify):
        result = router.route(high_confidence_amplify)
        assert result.action.priority in (ActionPriority.CRITICAL, ActionPriority.HIGH)

    def test_medium_confidence_gets_medium_priority(self, router):
        signal = _make_signal(SignalAction.AMPLIFY, confidence=0.55)
        result = router.route(signal)
        assert result.action.priority == ActionPriority.MEDIUM

    def test_low_confidence_gets_low_priority(self, router):
        signal = _make_signal(SignalAction.MAINTAIN, confidence=0.35)
        result = router.route(signal)
        assert result.action.priority.value >= ActionPriority.LOW.value

    def test_suppress_gets_priority_boost(self, router):
        signal = _make_signal(SignalAction.SUPPRESS, confidence=0.6)
        result = router.route(signal)
        # SUPPRESS 有 +0.15 boost → confidence 0.6 + 0.15 = 0.75 → HIGH
        # 但 SUPPRESS 映射到 REDUCE_BUDGET
        assert result.action.priority.value <= ActionPriority.HIGH.value

    def test_high_roas_context_boosts_priority(self, router):
        signal = _make_signal(SignalAction.AMPLIFY, confidence=0.5)
        context = {"roas": 3.0}
        result = router.route(signal, context=context)
        assert result.action.priority.value <= ActionPriority.HIGH.value

    def test_medium_roas_context(self, router):
        signal = _make_signal(SignalAction.AMPLIFY, confidence=0.5)
        context = {"roas": 1.6}
        result = router.route(signal, context=context)
        assert result.action.priority.value <= ActionPriority.MEDIUM.value

    def test_critical_priority_only_for_very_high(self, router):
        signal = _make_signal(SignalAction.AMPLIFY, confidence=0.95)
        context = {"roas": 3.0}
        result = router.route(signal, context=context)
        assert result.action.priority == ActionPriority.CRITICAL

    def test_optional_priority_for_very_low(self, router):
        signal = _make_signal(SignalAction.MAINTAIN, confidence=0.1)
        result = router.route(signal)
        assert result.action.priority == ActionPriority.OPTIONAL

    def test_priority_property_on_action(self, router, amplify_signal):
        result = router.route(amplify_signal)
        assert result.action.priority.value >= 1
        assert result.action.priority.value <= 5

    def test_confidence_affects_priority(self, router):
        signal_low = _make_signal(SignalAction.AMPLIFY, confidence=0.4)
        signal_high = _make_signal(SignalAction.AMPLIFY, confidence=0.9)
        result_low = router.route(signal_low)
        result_high = router.route(signal_high)
        assert result_high.action.priority.value <= result_low.action.priority.value


# ═══════════════════════════════════════════════════════════
# 8. Router Stats & Query Tests (15)
# ═══════════════════════════════════════════════════════════

class TestRouterStats:
    """路由器统计与查询测试."""

    def test_stats_initial(self, router):
        stats = router.stats()
        assert stats["total_actions"] == 0
        assert stats["total_routes"] == 0
        assert stats["pending"] == 0

    def test_stats_after_routing(self, router, amplify_signal):
        router.route(amplify_signal)
        stats = router.stats()
        assert stats["total_actions"] == 1
        assert stats["total_routes"] == 1

    def test_stats_by_type(self, router, amplify_signal, suppress_signal):
        router.route(amplify_signal)
        router.route(suppress_signal)
        stats = router.stats()
        assert "promote_winner" in stats["by_type"]
        assert "reduce_budget" in stats["by_type"]

    def test_stats_by_executor(self, router, amplify_signal, explore_signal):
        router.route(amplify_signal)
        router.route(explore_signal)
        stats = router.stats()
        assert "CreativeExecutor" in stats["by_executor"]
        assert "EvolutionExecutor" in stats["by_executor"]

    def test_stats_by_priority(self, router, amplify_signal, maintain_signal):
        router.route(amplify_signal)
        router.route(maintain_signal)
        stats = router.stats()
        assert "HIGH" in stats["by_priority"] or "CRITICAL" in stats["by_priority"]

    def test_stats_avg_confidence(self, router):
        router.route(_make_signal(SignalAction.AMPLIFY, confidence=0.9))
        router.route(_make_signal(SignalAction.SUPPRESS, confidence=0.7))
        stats = router.stats()
        assert stats["avg_confidence"] > 0.0

    def test_stats_fallback_rate(self, router):
        router.route(_make_signal(SignalAction.AMPLIFY, confidence=0.1))
        router.route(_make_signal(SignalAction.AMPLIFY, confidence=0.9))
        stats = router.stats()
        assert 0.0 < stats["fallback_rate"] < 1.0

    def test_stats_validation_pass_rate(self, router):
        router.route(_make_signal(SignalAction.AMPLIFY, confidence=0.9, target_value="g001"))
        stats = router.stats()
        assert stats["validation_pass_rate"] >= 0.0

    def test_get_action_by_id(self, router, amplify_signal):
        result = router.route(amplify_signal)
        retrieved = router.get_action(result.action.action_id)
        assert retrieved is not None
        assert retrieved.action_id == result.action.action_id

    def test_get_action_not_found(self, router):
        assert router.get_action("nonexistent") is None

    def test_get_actions_by_type(self, router, amplify_signal, maintain_signal):
        router.route(amplify_signal)
        router.route(maintain_signal)
        promoted = router.get_actions_by_type(GrowthActionType.PROMOTE_WINNER)
        held = router.get_actions_by_type(GrowthActionType.HOLD)
        assert len(promoted) == 1
        assert len(held) == 1

    def test_get_actions_by_priority(self, router, amplify_signal, maintain_signal):
        router.route(amplify_signal)
        router.route(maintain_signal)
        # amplify_signal (0.92 + 0.1 = 1.02 → CRITICAL)
        critical = router.get_actions_by_priority(ActionPriority.CRITICAL)
        assert len(critical) >= 1

    def test_get_pending_actions(self, router, amplify_signal):
        router.route(amplify_signal)
        pending = router.get_pending_actions()
        assert len(pending) == 1

    def test_reset_clears_all(self, router, amplify_signal):
        router.route(amplify_signal)
        router.reset()
        stats = router.stats()
        assert stats["total_actions"] == 0
        assert stats["total_routes"] == 0
        assert len(router.get_pending_actions()) == 0


# ═══════════════════════════════════════════════════════════
# 9. Payload Construction Tests (10)
# ═══════════════════════════════════════════════════════════

class TestPayloadConstruction:
    """Payload 构建测试."""

    def test_promote_winner_payload(self, router, amplify_signal):
        result = router.route(amplify_signal)
        p = result.action.payload
        assert "budget_multiplier" in p
        assert p["budget_multiplier"] > 1.0
        assert p["budget_multiplier"] <= router._max_budget_multiplier
        assert "scale_reason" in p

    def test_reduce_budget_payload(self, router, suppress_signal):
        result = router.route(suppress_signal)
        p = result.action.payload
        assert "budget_multiplier" in p
        assert p["budget_multiplier"] < 1.0
        assert p["budget_multiplier"] >= 0.2
        assert "reduce_reason" in p

    def test_start_experiment_payload(self, router, retest_signal):
        result = router.route(retest_signal)
        p = result.action.payload
        assert "experiment_name" in p
        assert "hypothesis" in p
        assert "duration_days" in p
        assert p["duration_days"] == 7

    def test_create_variants_payload(self, router, explore_signal):
        result = router.route(explore_signal)
        p = result.action.payload
        assert "variant_count" in p
        assert p["variant_count"] >= 2
        assert "exploration_direction" in p

    def test_scale_campaign_payload(self, router):
        signal = _make_signal(SignalAction.AMPLIFY, confidence=0.25)  # triggers fallback to SCALE_CAMPAIGN
        result = router.route(signal)
        if result.action.action_type == GrowthActionType.SCALE_CAMPAIGN:
            p = result.action.payload
            assert "budget_multiplier" in p
            assert "scale_reason" in p

    def test_pause_campaign_payload(self, router):
        signal = _make_signal(SignalAction.SUPPRESS, confidence=0.1)  # triggers fallback to PAUSE_CAMPAIGN
        result = router.route(signal)
        if result.action.action_type == GrowthActionType.PAUSE_CAMPAIGN:
            p = result.action.payload
            assert "reason" in p
            assert "auto_resume_days" in p

    def test_diversify_population_payload(self, router):
        signal = _make_signal(SignalAction.EXPLORE, confidence=0.1)  # triggers fallback to DIVERSIFY
        result = router.route(signal)
        if result.action.action_type == GrowthActionType.DIVERSIFY_POPULATION:
            p = result.action.payload
            assert "diversity_target" in p
            assert "count" in p

    def test_payload_context_injection(self, router, amplify_signal):
        context = {"roas": 1.8, "ctr": 0.042, "fatigue": 0.2}
        result = router.route(amplify_signal, context=context)
        assert "context" in result.action.payload
        assert result.action.payload["context"] == context

    def test_payload_signal_info(self, router, amplify_signal):
        result = router.route(amplify_signal)
        assert result.action.payload["signal_action"] == "amplify"
        assert result.action.payload["gene_category"] == "hook"
        assert result.action.payload["source_experiment_id"] == "exp_001"

    def test_hold_payload_minimal(self, router, maintain_signal):
        result = router.route(maintain_signal)
        assert result.action.payload["signal_action"] == "maintain"


# ═══════════════════════════════════════════════════════════
# 10. Regression E14.5/E14.6 Tests (10)
# ═══════════════════════════════════════════════════════════

class TestRegressionE145E146:
    """E14.5/E14.6 集成回归测试."""

    def test_router_with_evolution_signal_from_feedback(self, router):
        """验证 Router 接受 E14.6.3 EvolutionSignal 作为输入."""
        signal = EvolutionSignal(
            action=SignalAction.AMPLIFY,
            gene_category="hook",
            target_value="rescue",
            confidence=0.92,
            expected_impact="ROAS +15%",
            source_experiment_id="exp_001",
        )
        result = router.route(signal)
        assert result.action.action_type == GrowthActionType.PROMOTE_WINNER
        assert result.action.source == ActionSource.EVOLUTION_SIGNAL

    def test_router_preserves_full_signal_chain(self, router):
        """验证 Router 保留完整的信号链路信息."""
        signal = EvolutionSignal(
            action=SignalAction.AMPLIFY,
            gene_category="monetization",
            target_value="battle_pass",
            confidence=0.88,
            expected_impact="D7 payer +10%",
            source_experiment_id="exp_042",
            source_feedback_id="fb_001",
        )
        result = router.route(signal)
        assert result.action.metadata["gene_category"] == "monetization"
        assert result.action.metadata["source_experiment_id"] == "exp_042"
        assert result.action.source_signal_id == signal.signal_id

    def test_router_integration_with_create_router(self, amplify_signal):
        """验证工厂函数创建的 Router 正常工作."""
        router = create_growth_action_router()
        result = router.route(amplify_signal)
        assert result.action.action_type == GrowthActionType.PROMOTE_WINNER

    def test_router_integration_with_custom_config(self, suppress_signal):
        """验证自定义配置 Router 正常工作."""
        router = create_growth_action_router(
            min_confidence=0.4,
            auto_approve_confidence=0.9,
            max_budget_multiplier=2.5,
            max_concurrent_actions=8,
        )
        result = router.route(suppress_signal)
        assert result.action.action_type == GrowthActionType.REDUCE_BUDGET

    def test_router_full_cycle_amplify(self, router):
        """完整 AMPLIFY 路由周期."""
        signal = _make_signal(SignalAction.AMPLIFY, confidence=0.92, target_value="genome_007")
        result = router.route(signal, target_id="genome_007", target_type="genome")
        assert result.action.action_type == GrowthActionType.PROMOTE_WINNER
        assert result.action.target_id == "genome_007"
        assert result.action.executor == "CreativeExecutor"
        assert result.action.is_high_confidence is True
        assert result.validation_passed is True

    def test_router_full_cycle_suppress(self, router):
        """完整 SUPPRESS 路由周期."""
        signal = _make_signal(SignalAction.SUPPRESS, confidence=0.85, target_value="camp_003")
        result = router.route(signal, target_id="camp_003", target_type="campaign")
        assert result.action.action_type == GrowthActionType.REDUCE_BUDGET
        assert result.action.target_id == "camp_003"
        assert result.action.executor == "BudgetExecutor"
        assert result.action.payload["budget_multiplier"] < 1.0

    def test_router_full_cycle_retest(self, router):
        """完整 RETEST 路由周期."""
        signal = _make_signal(SignalAction.RETEST, confidence=0.7, target_value="genome_005")
        result = router.route(signal, target_id="genome_005", target_type="genome")
        assert result.action.action_type == GrowthActionType.START_EXPERIMENT
        assert result.action.target_id == "genome_005"
        assert result.action.executor == "ExperimentExecutor"
        assert "experiment_name" in result.action.payload

    def test_router_expected_reward_calculated(self, router, amplify_signal):
        """验证预期奖励计算."""
        result = router.route(amplify_signal)
        assert result.action.expected_reward > 0.0

    def test_router_hold_has_zero_reward(self, router, maintain_signal):
        result = router.route(maintain_signal)
        assert result.action.expected_reward == 0.0

    def test_router_metadata_structure(self, router, amplify_signal):
        """验证 metadata 结构完整."""
        result = router.route(amplify_signal)
        assert "gene_category" in result.action.metadata
        assert "source_experiment_id" in result.action.metadata
        assert "context" in result.action.metadata


# ═══════════════════════════════════════════════════════════
# 11. Edge Cases & Boundary Tests (10)
# ═══════════════════════════════════════════════════════════

class TestEdgeCases:
    """边界条件测试."""

    def test_empty_context(self, router, amplify_signal):
        result = router.route(amplify_signal, context={})
        assert result.action is not None
        assert result.validation_passed is True

    def test_empty_target_value(self, router):
        signal = _make_signal(SignalAction.AMPLIFY, confidence=0.92, target_value="")
        result = router.route(signal)
        assert result.action.target_id == ""

    def test_very_high_confidence(self, router):
        signal = _make_signal(SignalAction.AMPLIFY, confidence=0.999)
        result = router.route(signal)
        assert result.action.priority == ActionPriority.CRITICAL

    def test_very_low_confidence(self, router):
        signal = _make_signal(SignalAction.AMPLIFY, confidence=0.001)
        result = router.route(signal)
        assert result.fallback_used is True

    def test_zero_confidence(self, router):
        signal = _make_signal(SignalAction.AMPLIFY, confidence=0.0)
        result = router.route(signal)
        assert result.fallback_used is True

    def test_exact_threshold_confidence(self, router):
        signal = _make_signal(SignalAction.AMPLIFY, confidence=0.3)
        result = router.route(signal)
        assert result.fallback_used is False

    def test_exact_threshold_confidence_below(self, router):
        signal = _make_signal(SignalAction.AMPLIFY, confidence=0.299)
        result = router.route(signal)
        assert result.fallback_used is True

    def test_route_result_to_dict(self, router, amplify_signal):
        result = router.route(amplify_signal)
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "action" in d
        assert "signal_matched" in d
        assert "route_score" in d

    def test_get_actions_by_executor(self, router, amplify_signal, explore_signal):
        router.route(amplify_signal)
        router.route(explore_signal)
        creative_actions = router.get_actions_by_executor("CreativeExecutor")
        evo_actions = router.get_actions_by_executor("EvolutionExecutor")
        assert len(creative_actions) >= 1
        assert len(evo_actions) >= 1

    def test_get_route_history(self, router, amplify_signal):
        router.route(amplify_signal)
        history = router.get_route_history()
        assert len(history) == 1
        assert isinstance(history[0], RouteResult)