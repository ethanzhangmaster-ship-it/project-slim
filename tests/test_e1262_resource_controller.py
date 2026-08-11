"""E12.6.2 — Resource Controller 测试。

覆盖:
  - Models: ResourceType, ResourceRequest, ResourceAllocation, ProductResourceState, BudgetAdjustment
  - ResourcePolicy: WinnerScaling, FatigueRecovery, LowPotential, Exploration
  - PriorityAllocator: score calculation, softmax allocation, budget split
  - BudgetOptimizer: increase, decrease, freeze
  - ResourceController: allocate, allocate_single, optimize, summary
  - Integration: multi-product allocation, budget flow
"""

import pytest
from datetime import datetime, timezone

from market_ops.creative_vision_runtime.reality.meta_intelligence.resource_controller import (
    BudgetAdjustment,
    BudgetOptimizer,
    ExplorationPolicy,
    FatigueRecoveryPolicy,
    LowPotentialPolicy,
    PriorityAllocator,
    ProductResourceState,
    ResourceAllocation,
    ResourceController,
    ResourcePolicy,
    ResourceRequest,
    ResourceType,
    WinnerScalingPolicy,
    calculate_priority_score,
    get_resource_label,
    softmax_allocate,
)


# ── Helpers ─────────────────────────────────────────────────


def make_state(
    product_id: str = "P04",
    total_budget: float = 5000.0,
    allocated_budget: float = 1000.0,
    spent_budget: float = 500.0,
    active_experiments: int = 3,
    active_mutations: int = 2,
    recent_roas: float = 1.0,
    fatigue_score: float = 0.3,
    prediction_confidence: float = 0.7,
    population_diversity: float = 0.5,
) -> ProductResourceState:
    return ProductResourceState(
        product_id=product_id,
        total_budget=total_budget,
        allocated_budget=allocated_budget,
        spent_budget=spent_budget,
        active_experiments=active_experiments,
        active_mutations=active_mutations,
        recent_roas=recent_roas,
        fatigue_score=fatigue_score,
        prediction_confidence=prediction_confidence,
        population_diversity=population_diversity,
    )


def make_request(
    product_id: str = "P04",
    resource_type: ResourceType = ResourceType.EXPERIMENT_BUDGET,
    requested_amount: float = 1000.0,
    expected_return: float = 1.5,
    urgency: float = 0.6,
    learning_value: float = 0.7,
) -> ResourceRequest:
    return ResourceRequest(
        product_id=product_id,
        resource_type=resource_type,
        requested_amount=requested_amount,
        expected_return=expected_return,
        urgency=urgency,
        learning_value=learning_value,
    )


# ═══════════════════════════════════════════════════════════════
# TestResourceModels — 20 tests
# ═══════════════════════════════════════════════════════════════


class TestResourceModels:
    """ResourceType, ResourceRequest, ResourceAllocation, ProductResourceState, BudgetAdjustment"""

    # ── ResourceType ──

    def test_resource_type_enum_values(self):
        assert ResourceType.EXPERIMENT_BUDGET.value == "experiment_budget"
        assert ResourceType.MUTATION_BUDGET.value == "mutation_budget"
        assert ResourceType.GENERATION_CAPACITY.value == "generation_capacity"
        assert ResourceType.ANALYSIS_COMPUTE.value == "analysis_compute"
        assert ResourceType.HUMAN_REVIEW.value == "human_review"

    def test_resource_type_is_string_enum(self):
        assert isinstance(ResourceType.EXPERIMENT_BUDGET, str)
        assert ResourceType.EXPERIMENT_BUDGET == "experiment_budget"

    def test_resource_label(self):
        assert get_resource_label(ResourceType.EXPERIMENT_BUDGET) == "实验预算"
        assert get_resource_label(ResourceType.MUTATION_BUDGET) == "突变预算"
        assert get_resource_label(ResourceType.GENERATION_CAPACITY) == "生成容量"
        assert get_resource_label(ResourceType.ANALYSIS_COMPUTE) == "分析算力"
        assert get_resource_label(ResourceType.HUMAN_REVIEW) == "人工审核"

    # ── ResourceRequest ──

    def test_request_creation(self):
        req = make_request()
        assert req.product_id == "P04"
        assert req.requested_amount == 1000.0
        assert req.expected_return == 1.5

    def test_request_auto_generates_id(self):
        req = ResourceRequest()
        assert req.request_id.startswith("RR_")

    def test_request_is_urgent(self):
        req = make_request(urgency=0.8)
        assert req.is_urgent is True

        req2 = make_request(urgency=0.5)
        assert req2.is_urgent is False

    def test_request_is_high_value(self):
        req = make_request(expected_return=2.0)
        assert req.is_high_value is True

        req2 = make_request(expected_return=1.0)
        assert req2.is_high_value is False

    def test_request_to_dict(self):
        req = make_request()
        d = req.to_dict()
        assert d["product_id"] == "P04"
        assert d["requested_amount"] == 1000.0
        assert d["resource_type"] == "experiment_budget"

    def test_request_repr(self):
        req = make_request()
        r = repr(req)
        assert "P04" in r
        assert "experiment_budget" in r

    # ── ResourceAllocation ──

    def test_allocation_creation(self):
        alloc = ResourceAllocation(
            product_id="P04",
            allocated_amount=500.0,
            allocation_score=0.85,
            priority=85,
        )
        assert alloc.product_id == "P04"
        assert alloc.allocated_amount == 500.0
        assert alloc.allocation_score == 0.85

    def test_allocation_is_funded(self):
        alloc = ResourceAllocation(allocated_amount=500.0)
        assert alloc.is_funded is True

        alloc2 = ResourceAllocation(allocated_amount=0.0)
        assert alloc2.is_funded is False

    def test_allocation_to_dict(self):
        alloc = ResourceAllocation(product_id="P04", allocated_amount=500.0)
        d = alloc.to_dict()
        assert d["product_id"] == "P04"
        assert d["allocated_amount"] == 500.0
        assert "is_funded" in d

    # ── ProductResourceState ──

    def test_state_creation(self):
        s = make_state()
        assert s.product_id == "P04"
        assert s.total_budget == 5000.0
        assert s.allocated_budget == 1000.0

    def test_state_budget_remaining(self):
        s = make_state(total_budget=5000, allocated_budget=2000)
        assert s.budget_remaining == 3000.0

    def test_state_budget_remaining_non_negative(self):
        s = make_state(total_budget=1000, allocated_budget=2000)
        assert s.budget_remaining == 0.0

    def test_state_budget_utilization(self):
        s = make_state(total_budget=5000, allocated_budget=2500)
        assert s.budget_utilization == 0.5

    def test_state_budget_utilization_zero_budget(self):
        s = make_state(total_budget=0)
        assert s.budget_utilization == 0.0

    def test_state_is_healthy(self):
        s = make_state(fatigue_score=0.2, prediction_confidence=0.8, population_diversity=0.5)
        assert s.is_healthy is True

    def test_state_is_healthy_fatigue(self):
        s = make_state(fatigue_score=0.6)
        assert s.is_healthy is False

    def test_state_needs_attention(self):
        s = make_state(fatigue_score=0.85)
        assert s.needs_attention is True

    def test_state_needs_attention_low_roas(self):
        s = make_state(recent_roas=0.3)
        assert s.needs_attention is True

    # ── BudgetAdjustment ──

    def test_adjustment_creation(self):
        adj = BudgetAdjustment(
            product_id="P04",
            previous_amount=1000.0,
            new_amount=1500.0,
        )
        assert adj.product_id == "P04"
        assert adj.change_pct == pytest.approx(0.5)

    def test_adjustment_is_increase(self):
        adj = BudgetAdjustment(previous_amount=1000.0, new_amount=1500.0)
        assert adj.is_increase is True
        assert adj.is_decrease is False

    def test_adjustment_is_decrease(self):
        adj = BudgetAdjustment(previous_amount=1000.0, new_amount=500.0)
        assert adj.is_decrease is True
        assert adj.is_increase is False

    def test_adjustment_is_frozen(self):
        adj = BudgetAdjustment(previous_amount=1000.0, new_amount=0.0)
        assert adj.is_frozen is True

    def test_adjustment_not_frozen_if_was_zero(self):
        adj = BudgetAdjustment(previous_amount=0.0, new_amount=0.0)
        assert adj.is_frozen is False

    def test_adjustment_to_dict(self):
        adj = BudgetAdjustment(
            product_id="P04",
            previous_amount=1000.0,
            new_amount=1500.0,
        )
        d = adj.to_dict()
        assert d["product_id"] == "P04"
        assert d["is_increase"] is True

    def test_adjustment_repr(self):
        adj = BudgetAdjustment(
            product_id="P04",
            previous_amount=1000.0,
            new_amount=1500.0,
            reason="test",
        )
        r = repr(adj)
        assert "P04" in r
        assert "+50%" in r


# ═══════════════════════════════════════════════════════════════
# TestPriorityScore — 30 tests
# ═══════════════════════════════════════════════════════════════


class TestPriorityScore:
    """calculate_priority_score, softmax_allocate"""

    # ── calculate_priority_score ──

    def test_basic_calculation(self):
        score = calculate_priority_score(1.5, 0.7, 0.6, 0.8)
        assert 0.0 <= score <= 1.0

    def test_high_roi_high_score(self):
        score = calculate_priority_score(3.0, 1.0, 1.0, 1.0)
        assert score == pytest.approx(1.0)

    def test_low_roi_low_score(self):
        score = calculate_priority_score(0.1, 0.5, 0.5, 0.5)
        assert score < 0.1

    def test_roi_normalized_capped(self):
        score = calculate_priority_score(10.0, 1.0, 1.0, 1.0)
        assert score <= 1.0

    def test_roi_negative_clamped(self):
        score = calculate_priority_score(-1.0, 0.5, 0.5, 0.5)
        assert score == 0.0

    def test_learning_value_clamped(self):
        score = calculate_priority_score(1.5, 1.5, 0.5, 0.5)
        assert 0.0 <= score <= 1.0

    def test_urgency_clamped(self):
        score = calculate_priority_score(1.5, 0.5, 1.5, 0.5)
        assert 0.0 <= score <= 1.0

    def test_confidence_clamped(self):
        score = calculate_priority_score(1.5, 0.5, 0.5, 1.5)
        assert 0.0 <= score <= 1.0

    def test_zero_confidence_zero_score(self):
        score = calculate_priority_score(2.0, 0.8, 0.9, 0.0)
        assert score == 0.0

    def test_zero_learning_value_zero_score(self):
        score = calculate_priority_score(2.0, 0.0, 0.9, 0.8)
        assert score == 0.0

    def test_zero_urgency_zero_score(self):
        score = calculate_priority_score(2.0, 0.8, 0.0, 0.8)
        assert score == 0.0

    def test_score_increases_with_roi(self):
        s1 = calculate_priority_score(1.0, 0.7, 0.6, 0.8)
        s2 = calculate_priority_score(2.0, 0.7, 0.6, 0.8)
        assert s2 > s1

    def test_score_increases_with_confidence(self):
        s1 = calculate_priority_score(1.5, 0.7, 0.6, 0.5)
        s2 = calculate_priority_score(1.5, 0.7, 0.6, 0.9)
        assert s2 > s1

    def test_score_with_half_values(self):
        score = calculate_priority_score(1.5, 0.5, 0.5, 0.5)
        expected = (1.5 / 3.0) * 0.5 * 0.5 * 0.5
        assert score == pytest.approx(expected, abs=1e-5)

    # ── softmax_allocate ──

    def test_softmax_empty(self):
        result = softmax_allocate([], 1000.0)
        assert result == []

    def test_softmax_zero_budget(self):
        result = softmax_allocate([("P04", 0.8)], 0.0)
        assert result[0][1] == 0.0

    def test_softmax_single_product(self):
        result = softmax_allocate([("P04", 0.8)], 1000.0)
        assert result[0][0] == "P04"
        assert result[0][1] == pytest.approx(1000.0, abs=0.1)

    def test_softmax_two_products_equal(self):
        result = softmax_allocate([("P04", 0.5), ("P05", 0.5)], 1000.0)
        assert len(result) == 2
        assert result[0][1] == pytest.approx(500.0, abs=1.0)
        assert result[1][1] == pytest.approx(500.0, abs=1.0)

    def test_softmax_higher_score_gets_more(self):
        result = softmax_allocate([("P04", 0.9), ("P05", 0.3)], 1000.0)
        p04_amount = [a for pid, a in result if pid == "P04"][0]
        p05_amount = [a for pid, a in result if pid == "P05"][0]
        assert p04_amount > p05_amount

    def test_softmax_three_products(self):
        result = softmax_allocate(
            [("P04", 0.9), ("P05", 0.5), ("P06", 0.1)], 1000.0
        )
        assert len(result) == 3
        p04 = [a for pid, a in result if pid == "P04"][0]
        p05 = [a for pid, a in result if pid == "P05"][0]
        p06 = [a for pid, a in result if pid == "P06"][0]
        assert p04 > p05 > p06

    def test_softmax_sum_equals_budget(self):
        result = softmax_allocate(
            [("P04", 0.8), ("P05", 0.5), ("P06", 0.2)], 1000.0
        )
        total = sum(a for _, a in result)
        assert total == pytest.approx(1000.0, abs=0.1)

    def test_softmax_min_allocation(self):
        result = softmax_allocate(
            [("P04", 5.0), ("P05", 0.01)], 1000.0, min_allocation=200.0
        )
        p05 = [a for pid, a in result if pid == "P05"][0]
        assert p05 == 0.0

    def test_softmax_negative_scores(self):
        result = softmax_allocate([("P04", -0.5)], 1000.0)
        assert result[0][1] == pytest.approx(1000.0, abs=0.1)

    def test_softmax_all_zero_scores(self):
        result = softmax_allocate([("P04", 0.0), ("P05", 0.0)], 1000.0)
        # All zero scores → equal distribution
        assert result[0][1] == pytest.approx(500.0, abs=0.1)
        assert result[1][1] == pytest.approx(500.0, abs=0.1)

    def test_softmax_temperature_effect(self):
        scores = [("P04", 0.8), ("P05", 0.4)]
        result_normal = softmax_allocate(scores, 1000.0)
        # With temperature 0.5 (more polarized), high scorer gets more
        hot_scores = [(pid, s / 0.5) for pid, s in scores]
        result_hot = softmax_allocate(hot_scores, 1000.0)
        p04_normal = [a for pid, a in result_normal if pid == "P04"][0]
        p04_hot = [a for pid, a in result_hot if pid == "P04"][0]
        assert p04_hot > p04_normal

    # ── Priority Score Edge Cases ──

    def test_score_boundary_max(self):
        score = calculate_priority_score(3.0, 1.0, 1.0, 1.0)
        assert score == pytest.approx(1.0)

    def test_score_boundary_min(self):
        score = calculate_priority_score(0.0, 0.0, 0.0, 0.0)
        assert score == 0.0

    def test_score_mid_range(self):
        score = calculate_priority_score(2.5, 0.8, 0.7, 0.8)
        assert 0.1 < score < 0.5

    def test_softmax_single_product_all_budget(self):
        result = softmax_allocate([("P04", 0.5)], 5000.0)
        assert result[0][1] == pytest.approx(5000.0, abs=0.1)

    def test_softmax_preserves_ordering(self):
        result = softmax_allocate(
            [("P04", 0.7), ("P05", 0.5), ("P06", 0.3)], 1000.0
        )
        amounts = {pid: a for pid, a in result}
        assert amounts["P04"] > amounts["P05"] > amounts["P06"]


# ═══════════════════════════════════════════════════════════════
# TestResourcePolicy — 30 tests
# ═══════════════════════════════════════════════════════════════


class TestWinnerScalingPolicy:
    """WinnerScalingPolicy — 放大赢家"""

    def test_triggers_on_winner(self):
        state = make_state(recent_roas=2.0, fatigue_score=0.1, prediction_confidence=0.8)
        policy = WinnerScalingPolicy()
        adj = policy.evaluate(state)
        assert adj is not None
        assert adj.is_increase

    def test_no_trigger_low_roas(self):
        state = make_state(recent_roas=1.0, fatigue_score=0.1, prediction_confidence=0.8)
        policy = WinnerScalingPolicy()
        adj = policy.evaluate(state)
        assert adj is None

    def test_no_trigger_high_fatigue(self):
        state = make_state(recent_roas=2.0, fatigue_score=0.5, prediction_confidence=0.8)
        policy = WinnerScalingPolicy()
        adj = policy.evaluate(state)
        assert adj is None

    def test_no_trigger_low_confidence(self):
        state = make_state(recent_roas=2.0, fatigue_score=0.1, prediction_confidence=0.5)
        policy = WinnerScalingPolicy()
        adj = policy.evaluate(state)
        assert adj is None

    def test_increase_amount(self):
        state = make_state(
            recent_roas=2.0, fatigue_score=0.1, prediction_confidence=0.9,
            allocated_budget=1000.0, total_budget=5000.0,
        )
        policy = WinnerScalingPolicy()
        adj = policy.evaluate(state)
        assert adj is not None
        assert adj.new_amount == pytest.approx(1500.0)

    def test_rule_name(self):
        policy = WinnerScalingPolicy()
        assert policy.name == "winner_scaling"


class TestFatigueRecoveryPolicy:
    """FatigueRecoveryPolicy — 疲劳恢复"""

    def test_triggers_on_high_fatigue(self):
        state = make_state(fatigue_score=0.85, prediction_confidence=0.85)
        policy = FatigueRecoveryPolicy()
        adj = policy.evaluate(state)
        assert adj is not None
        assert adj.resource_type == ResourceType.MUTATION_BUDGET

    def test_no_trigger_low_fatigue(self):
        state = make_state(fatigue_score=0.5, prediction_confidence=0.85)
        policy = FatigueRecoveryPolicy()
        adj = policy.evaluate(state)
        assert adj is None

    def test_no_trigger_low_confidence(self):
        state = make_state(fatigue_score=0.85, prediction_confidence=0.6)
        policy = FatigueRecoveryPolicy()
        adj = policy.evaluate(state)
        assert adj is None

    def test_fatigue_at_boundary(self):
        state = make_state(fatigue_score=0.80, prediction_confidence=0.85)
        policy = FatigueRecoveryPolicy()
        adj = policy.evaluate(state)
        assert adj is not None

    def test_increase_amount(self):
        state = make_state(
            fatigue_score=0.85, prediction_confidence=0.9,
            allocated_budget=1000.0, total_budget=5000.0,
        )
        policy = FatigueRecoveryPolicy()
        adj = policy.evaluate(state)
        assert adj is not None
        assert adj.new_amount == pytest.approx(1300.0)


class TestLowPotentialPolicy:
    """LowPotentialPolicy — 低潜力削减"""

    def test_triggers_on_low_roas(self):
        state = make_state(recent_roas=0.4, fatigue_score=0.85)
        policy = LowPotentialPolicy()
        adj = policy.evaluate(state)
        assert adj is not None
        assert adj.is_decrease

    def test_no_trigger_good_roas(self):
        state = make_state(recent_roas=1.0)
        policy = LowPotentialPolicy()
        adj = policy.evaluate(state)
        assert adj is None

    def test_no_trigger_healthy(self):
        state = make_state(recent_roas=0.6, fatigue_score=0.3, population_diversity=0.5)
        policy = LowPotentialPolicy()
        adj = policy.evaluate(state)
        assert adj is None

    def test_decrease_amount(self):
        state = make_state(
            recent_roas=0.3, fatigue_score=0.85,
            allocated_budget=1000.0,
        )
        policy = LowPotentialPolicy()
        adj = policy.evaluate(state)
        assert adj is not None
        assert adj.new_amount == pytest.approx(500.0)


class TestExplorationPolicy:
    """ExplorationPolicy — 探索分配"""

    def test_triggers_on_high_diversity(self):
        state = make_state(
            population_diversity=0.8, prediction_confidence=0.7,
            total_budget=5000.0,
        )
        policy = ExplorationPolicy()
        adj = policy.evaluate(state)
        assert adj is not None
        assert adj.resource_type == ResourceType.GENERATION_CAPACITY

    def test_no_trigger_low_diversity(self):
        state = make_state(population_diversity=0.5, prediction_confidence=0.7)
        policy = ExplorationPolicy()
        adj = policy.evaluate(state)
        assert adj is None

    def test_no_trigger_low_confidence(self):
        state = make_state(population_diversity=0.8, prediction_confidence=0.3)
        policy = ExplorationPolicy()
        adj = policy.evaluate(state)
        assert adj is None

    def test_explore_amount(self):
        state = make_state(
            population_diversity=0.8, prediction_confidence=0.7,
            total_budget=5000.0,
        )
        policy = ExplorationPolicy()
        adj = policy.evaluate(state)
        assert adj is not None
        assert adj.new_amount == pytest.approx(1000.0)  # 20% of 5000


class TestResourcePolicyBase:
    """ResourcePolicy 基类"""

    def test_policy_repr(self):
        policy = WinnerScalingPolicy()
        r = repr(policy)
        assert "WinnerScalingPolicy" in r

    def test_policy_abstract(self):
        with pytest.raises(TypeError):
            ResourcePolicy()  # type: ignore


# ═══════════════════════════════════════════════════════════════
# TestPriorityAllocator — 30 tests
# ═══════════════════════════════════════════════════════════════


class TestPriorityAllocator:
    """PriorityAllocator — 多产品优先级分配"""

    def test_allocator_creation(self):
        allocator = PriorityAllocator()
        assert allocator.temperature == 1.0
        assert allocator.min_allocation == 0.0

    def test_calculate_scores_single(self):
        allocator = PriorityAllocator()
        states = [make_state(recent_roas=2.0, fatigue_score=0.2, prediction_confidence=0.8)]
        scores = allocator.calculate_scores(states)
        assert len(scores) == 1
        assert scores[0][0] == "P04"
        assert 0.0 <= scores[0][1] <= 1.0

    def test_calculate_scores_multiple(self):
        allocator = PriorityAllocator()
        states = [
            make_state("P04", recent_roas=2.0),
            make_state("P05", recent_roas=1.0),
            make_state("P06", recent_roas=0.5),
        ]
        scores = allocator.calculate_scores(states)
        assert len(scores) == 3

    def test_higher_roas_gives_higher_score(self):
        allocator = PriorityAllocator()
        s1 = make_state("P04", recent_roas=2.0, fatigue_score=0.2, prediction_confidence=0.8)
        s2 = make_state("P05", recent_roas=1.0, fatigue_score=0.2, prediction_confidence=0.8)
        scores = allocator.calculate_scores([s1, s2])
        p04_score = [s for pid, s in scores if pid == "P04"][0]
        p05_score = [s for pid, s in scores if pid == "P05"][0]
        assert p04_score > p05_score

    def test_score_state_returns_float(self):
        allocator = PriorityAllocator()
        score = allocator._score_state(make_state())
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_allocate_returns_allocations(self):
        allocator = PriorityAllocator()
        states = [make_state("P04"), make_state("P05")]
        result = allocator.allocate(states, 10000.0)
        assert len(result) == 2
        assert all(isinstance(a, ResourceAllocation) for a in result)

    def test_allocate_empty_states(self):
        allocator = PriorityAllocator()
        result = allocator.allocate([], 10000.0)
        assert result == []

    def test_allocate_single_product(self):
        allocator = PriorityAllocator()
        states = [make_state("P04")]
        result = allocator.allocate(states, 10000.0)
        assert len(result) == 1
        assert result[0].product_id == "P04"
        assert result[0].allocated_amount == pytest.approx(10000.0, abs=0.1)

    def test_allocate_preserves_ordering(self):
        allocator = PriorityAllocator()
        states = [
            make_state("P04", recent_roas=2.0),
            make_state("P05", recent_roas=1.0),
            make_state("P06", recent_roas=0.5),
        ]
        result = allocator.allocate(states, 10000.0)
        amounts = {a.product_id: a.allocated_amount for a in result}
        assert amounts["P04"] > amounts["P05"] > amounts["P06"]

    def test_allocate_sum_equals_budget(self):
        allocator = PriorityAllocator()
        states = [make_state("P04"), make_state("P05"), make_state("P06")]
        result = allocator.allocate(states, 10000.0)
        total = sum(a.allocated_amount for a in result)
        assert total == pytest.approx(10000.0, abs=0.1)

    def test_allocate_with_temperature(self):
        allocator = PriorityAllocator(temperature=0.5)
        states = [
            make_state("P04", recent_roas=2.0),
            make_state("P05", recent_roas=1.0),
        ]
        result = allocator.allocate(states, 10000.0)
        assert len(result) == 2

    def test_allocate_budget_split(self):
        allocator = PriorityAllocator()
        states = [make_state("P04"), make_state("P05")]
        result = allocator.allocate_budget_split(states, 10000.0)
        assert len(result) == 6  # 2 products × 3 resource types

    def test_allocate_budget_split_custom_ratio(self):
        allocator = PriorityAllocator()
        states = [make_state("P04")]
        split = {ResourceType.EXPERIMENT_BUDGET: 0.70, ResourceType.MUTATION_BUDGET: 0.30}
        result = allocator.allocate_budget_split(states, 10000.0, split_ratio=split)
        assert len(result) == 2

    def test_allocator_repr(self):
        allocator = PriorityAllocator(temperature=0.8)
        r = repr(allocator)
        assert "0.8" in r

    def test_build_reasons(self):
        allocator = PriorityAllocator()
        reasons = allocator._build_reasons("P04", 0.85, 5000.0, 10000.0)
        assert len(reasons) >= 2
        assert any("High priority" in r for r in reasons)

    def test_build_reasons_low_score(self):
        allocator = PriorityAllocator()
        reasons = allocator._build_reasons("P04", 0.2, 0.0, 10000.0)
        assert any("Low priority" in r for r in reasons)

    def test_build_reasons_medium(self):
        allocator = PriorityAllocator()
        reasons = allocator._build_reasons("P04", 0.5, 3000.0, 10000.0)
        assert any("Medium priority" in r for r in reasons)

    def test_find_state_roas(self):
        allocator = PriorityAllocator()
        states = [make_state("P04", recent_roas=2.5)]
        roas = allocator._find_state_roas(states, "P04")
        assert roas == 2.5

    def test_find_state_roas_not_found(self):
        allocator = PriorityAllocator()
        roas = allocator._find_state_roas([], "P99")
        assert roas == 0.0

    def test_allocate_with_requests_ignored(self):
        allocator = PriorityAllocator()
        states = [make_state("P04")]
        result = allocator.allocate(states, 10000.0, requests=[make_request()])
        assert len(result) == 1

    def test_zero_budget_allocation(self):
        allocator = PriorityAllocator()
        states = [make_state("P04")]
        result = allocator.allocate(states, 0.0)
        assert result[0].allocated_amount == 0.0

    def test_allocator_has_reasons(self):
        allocator = PriorityAllocator()
        states = [make_state("P04", recent_roas=2.0)]
        result = allocator.allocate(states, 10000.0)
        assert len(result[0].reasons) > 0


# ═══════════════════════════════════════════════════════════════
# TestBudgetOptimizer — 20 tests
# ═══════════════════════════════════════════════════════════════


class TestBudgetOptimizer:
    """BudgetOptimizer — 动态预算调整"""

    def test_optimizer_creation(self):
        opt = BudgetOptimizer()
        assert opt.roi_target == 1.2

    def test_optimize_increase(self):
        state = make_state(
            recent_roas=2.0, prediction_confidence=0.8,
            allocated_budget=1000.0,
        )
        opt = BudgetOptimizer()
        adj = opt.optimize(state)
        assert adj is not None
        assert adj.is_increase
        assert adj.new_amount == pytest.approx(1300.0)

    def test_optimize_decrease(self):
        state = make_state(
            recent_roas=0.8, allocated_budget=1000.0,
        )
        opt = BudgetOptimizer()
        adj = opt.optimize(state)
        assert adj is not None
        assert adj.is_decrease
        assert adj.new_amount == pytest.approx(500.0)

    def test_optimize_freeze_extreme(self):
        state = make_state(
            fatigue_score=0.9, population_diversity=0.1,
            allocated_budget=1000.0,
        )
        opt = BudgetOptimizer()
        adj = opt.optimize(state)
        assert adj is not None
        assert adj.is_frozen

    def test_optimize_freeze_critical_roas(self):
        state = make_state(
            recent_roas=0.2, allocated_budget=1000.0,
        )
        opt = BudgetOptimizer()
        adj = opt.optimize(state)
        assert adj is not None
        assert adj.is_frozen

    def test_optimize_no_change(self):
        state = make_state(
            recent_roas=1.2, allocated_budget=1000.0,
            fatigue_score=0.3, prediction_confidence=0.7,
        )
        opt = BudgetOptimizer()
        adj = opt.optimize(state)
        assert adj is None

    def test_optimize_no_increase_low_confidence(self):
        state = make_state(
            recent_roas=2.0, prediction_confidence=0.4,
            allocated_budget=1000.0,
        )
        opt = BudgetOptimizer()
        adj = opt.optimize(state)
        assert adj is None or adj.is_decrease  # might still decrease

    def test_optimize_no_increase_high_fatigue(self):
        state = make_state(
            recent_roas=2.0, prediction_confidence=0.8,
            fatigue_score=0.9, allocated_budget=1000.0,
        )
        opt = BudgetOptimizer()
        adj = opt.optimize(state)
        assert adj is None or adj.is_frozen  # freeze beats increase

    def test_optimize_max_increase_cap(self):
        state = make_state(
            recent_roas=5.0, prediction_confidence=0.9,
            allocated_budget=1000.0,
        )
        opt = BudgetOptimizer()
        adj = opt.optimize(state)
        assert adj is not None
        assert adj.new_amount <= 3000.0  # max_increase = 3x

    def test_optimize_min_budget(self):
        state = make_state(
            recent_roas=0.5, allocated_budget=100.0,
        )
        opt = BudgetOptimizer()
        adj = opt.optimize(state)
        assert adj is not None
        assert adj.new_amount >= 0.0

    def test_optimize_all(self):
        opt = BudgetOptimizer()
        states = [
            make_state("P04", recent_roas=2.0, prediction_confidence=0.8, allocated_budget=1000.0),
            make_state("P05", recent_roas=0.0, allocated_budget=1000.0),
            make_state("P06", recent_roas=1.2, allocated_budget=500.0),
        ]
        adjustments = opt.optimize_all(states)
        assert len(adjustments) >= 2

    def test_optimize_decrease_zero_budget(self):
        state = make_state(recent_roas=0.5, allocated_budget=0.0)
        opt = BudgetOptimizer()
        adj = opt.optimize(state)
        assert adj is None  # no budget to decrease

    def test_optimizer_custom_params(self):
        opt = BudgetOptimizer(roi_target=2.0, increase_ratio=0.5, decrease_ratio=0.3)
        assert opt.roi_target == 2.0
        assert opt.increase_ratio == 0.5
        assert opt.decrease_ratio == 0.3

    def test_optimizer_repr(self):
        opt = BudgetOptimizer()
        r = repr(opt)
        assert "BudgetOptimizer" in r

    def test_freeze_with_custom_current_budget(self):
        state = make_state(
            fatigue_score=0.9, population_diversity=0.1,
            allocated_budget=500.0,
        )
        opt = BudgetOptimizer()
        adj = opt.optimize(state, current_budget=2000.0)
        assert adj is not None
        assert adj.is_frozen

    def test_increase_uses_current_budget(self):
        state = make_state(
            recent_roas=2.0, prediction_confidence=0.8,
            allocated_budget=500.0,
        )
        opt = BudgetOptimizer()
        adj = opt.optimize(state, current_budget=2000.0)
        assert adj is not None
        assert adj.new_amount == pytest.approx(2600.0)

    def test_decrease_no_trigger_at_target(self):
        state = make_state(
            recent_roas=1.2, allocated_budget=1000.0,
        )
        opt = BudgetOptimizer()
        adj = opt.optimize(state)
        assert adj is None

    def test_freeze_beats_increase(self):
        state = make_state(
            recent_roas=2.0, prediction_confidence=0.8,
            fatigue_score=0.9, population_diversity=0.1,
            allocated_budget=1000.0,
        )
        opt = BudgetOptimizer()
        adj = opt.optimize(state)
        assert adj is not None
        assert adj.is_frozen  # freeze wins over increase

    def test_optimize_roas_exactly_at_threshold(self):
        state = make_state(
            recent_roas=1.8, prediction_confidence=0.8,
            allocated_budget=1000.0,
        )
        opt = BudgetOptimizer()
        adj = opt.optimize(state)
        assert adj is not None
        assert adj.is_increase


# ═══════════════════════════════════════════════════════════════
# TestResourceController — 20 tests
# ═══════════════════════════════════════════════════════════════


class TestResourceController:
    """ResourceController — 核心控制器"""

    def test_controller_creation(self):
        ctrl = ResourceController()
        assert ctrl.total_budget == 10000.0
        assert len(ctrl.policies) == 4

    def test_allocate_single_product(self):
        ctrl = ResourceController(total_budget=10000.0)
        states = [make_state("P04")]
        result = ctrl.allocate(states)
        assert len(result) >= 1
        assert any(a.product_id == "P04" for a in result)

    def test_allocate_multi_product(self):
        ctrl = ResourceController(total_budget=10000.0)
        states = [
            make_state("P04", recent_roas=2.0),
            make_state("P05", recent_roas=1.0),
            make_state("P06", recent_roas=0.5),
        ]
        result = ctrl.allocate(states)
        assert len(result) >= 3

    def test_allocate_empty(self):
        ctrl = ResourceController()
        result = ctrl.allocate([])
        assert result == []

    def test_allocate_single(self):
        ctrl = ResourceController(total_budget=5000.0)
        state = make_state("P04", recent_roas=2.0)
        alloc = ctrl.allocate_single(state)
        assert alloc.product_id == "P04"
        assert alloc.allocated_amount >= 0.0

    def test_allocate_single_winner(self):
        ctrl = ResourceController(total_budget=5000.0)
        state = make_state(
            "P04", recent_roas=2.5, fatigue_score=0.6,
            prediction_confidence=0.9,
        )
        alloc = ctrl.allocate_single(state)
        assert alloc.allocation_score > 0.15

    def test_allocate_single_low_performer(self):
        ctrl = ResourceController(total_budget=5000.0)
        state = make_state(
            "P04", recent_roas=0.3, fatigue_score=0.9,
            prediction_confidence=0.5,
        )
        alloc = ctrl.allocate_single(state)
        assert alloc.allocation_score < 0.5

    def test_calculate_priority(self):
        ctrl = ResourceController()
        state = make_state(recent_roas=2.0, fatigue_score=0.2, prediction_confidence=0.8)
        score = ctrl.calculate_priority(state)
        assert 0.0 <= score <= 1.0

    def test_get_summary(self):
        ctrl = ResourceController(total_budget=10000.0)
        allocs = [
            ResourceAllocation(product_id="P04", allocated_amount=6000.0, allocation_score=0.8),
            ResourceAllocation(product_id="P05", allocated_amount=3000.0, allocation_score=0.5),
            ResourceAllocation(product_id="P06", allocated_amount=0.0, allocation_score=0.2),
        ]
        summary = ctrl.get_summary(allocs)
        assert summary["total_allocated"] == pytest.approx(9000.0)
        assert summary["funded_products"] == 2
        assert summary["unfunded_products"] == 1
        assert "P04" in summary["by_product"]

    def test_get_summary_top_products(self):
        ctrl = ResourceController()
        allocs = [
            ResourceAllocation(product_id="P04", allocated_amount=6000.0),
            ResourceAllocation(product_id="P05", allocated_amount=3000.0),
            ResourceAllocation(product_id="P06", allocated_amount=500.0),
        ]
        summary = ctrl.get_summary(allocs)
        top = summary["top_products"]
        assert top[0]["product_id"] == "P04"
        assert top[0]["amount"] == 6000.0

    def test_optimize_budgets(self):
        ctrl = ResourceController()
        states = [
            make_state("P04", recent_roas=2.0, prediction_confidence=0.8, allocated_budget=1000.0),
            make_state("P05", recent_roas=0.8, allocated_budget=1000.0),
        ]
        adjustments = ctrl.optimize_budgets(states)
        assert len(adjustments) >= 2

    def test_controller_repr(self):
        ctrl = ResourceController(total_budget=5000.0)
        r = repr(ctrl)
        assert "5000" in r

    def test_apply_adjustments(self):
        ctrl = ResourceController()
        states = [make_state("P04", allocated_budget=1000.0)]
        adj = BudgetAdjustment(
            product_id="P04",
            resource_type=ResourceType.EXPERIMENT_BUDGET,
            previous_amount=1000.0,
            new_amount=1500.0,
        )
        updated = ctrl._apply_adjustments(states, [adj])
        assert updated[0].allocated_budget == 1500.0

    def test_apply_mutation_adjustment(self):
        ctrl = ResourceController()
        states = [make_state("P04")]
        adj = BudgetAdjustment(
            product_id="P04",
            resource_type=ResourceType.MUTATION_BUDGET,
            previous_amount=0.0,
            new_amount=100.0,
        )
        updated = ctrl._apply_adjustments(states, [adj])
        assert updated[0].active_mutations > 0

    def test_apply_generation_adjustment(self):
        ctrl = ResourceController()
        states = [make_state("P04")]
        adj = BudgetAdjustment(
            product_id="P04",
            resource_type=ResourceType.GENERATION_CAPACITY,
            previous_amount=0.0,
            new_amount=100.0,
        )
        updated = ctrl._apply_adjustments(states, [adj])
        assert updated[0].generation_queue_size > 0

    def test_build_allocation_reasons(self):
        ctrl = ResourceController()
        state = make_state("P04", recent_roas=2.0, fatigue_score=0.85, population_diversity=0.8)
        reasons = ctrl._build_allocation_reasons(state, 0.85)
        assert len(reasons) >= 3

    def test_build_allocation_reasons_low(self):
        ctrl = ResourceController()
        state = make_state("P04", recent_roas=0.3, population_diversity=0.1)
        reasons = ctrl._build_allocation_reasons(state, 0.1)
        assert any("Low ROAS" in r for r in reasons)
        assert any("Low diversity" in r for r in reasons)

    def test_custom_policies(self):
        ctrl = ResourceController(policies=[WinnerScalingPolicy()])
        assert len(ctrl.policies) == 1

    def test_custom_allocator(self):
        allocator = PriorityAllocator(temperature=0.5)
        ctrl = ResourceController(allocator=allocator)
        assert ctrl.allocator.temperature == 0.5

    def test_custom_optimizer(self):
        opt = BudgetOptimizer(roi_target=2.0)
        ctrl = ResourceController(optimizer=opt)
        assert ctrl.optimizer.roi_target == 2.0


# ═══════════════════════════════════════════════════════════════
# TestIntegration — 20 tests
# ═══════════════════════════════════════════════════════════════


class TestIntegration:
    """Integration tests — 完整流程"""

    def test_full_flow_winner(self):
        """完整流程：高 ROI 产品获得更多资源"""
        ctrl = ResourceController(total_budget=10000.0)
        states = [
            make_state("P04", recent_roas=2.5, fatigue_score=0.1, prediction_confidence=0.9),
            make_state("P05", recent_roas=1.0, fatigue_score=0.3, prediction_confidence=0.7),
            make_state("P06", recent_roas=0.5, fatigue_score=0.5, prediction_confidence=0.5),
        ]
        result = ctrl.allocate(states)

        by_product: dict[str, float] = {}
        for a in result:
            by_product[a.product_id] = by_product.get(a.product_id, 0.0) + a.allocated_amount

        assert by_product["P04"] > by_product["P05"] > by_product["P06"]

    def test_full_flow_fatigue(self):
        """完整流程：疲劳产品获得突变预算"""
        ctrl = ResourceController(total_budget=10000.0)
        states = [
            make_state("P04", fatigue_score=0.85, prediction_confidence=0.85),
        ]
        result = ctrl.allocate(states)
        assert len(result) >= 1

    def test_full_flow_exploration(self):
        """完整流程：高多样性触发探索"""
        ctrl = ResourceController(total_budget=10000.0)
        states = [
            make_state("P04", population_diversity=0.8, prediction_confidence=0.7),
        ]
        result = ctrl.allocate(states)
        assert len(result) >= 1

    def test_prediction_to_resource_flow(self):
        """Prediction → Resource 流程"""
        ctrl = ResourceController(total_budget=10000.0)
        # 模拟 E12.3 Prediction 结果
        state = make_state(
            "P04",
            recent_roas=2.1,
            fatigue_score=0.6,
            prediction_confidence=0.92,
        )
        alloc = ctrl.allocate_single(state)
        assert alloc.allocation_score > 0.10
        assert len(alloc.reasons) > 0

    def test_resource_to_budget_flow(self):
        """Resource → E11 Budget 流程"""
        ctrl = ResourceController()
        states = [
            make_state("P04", recent_roas=2.0, prediction_confidence=0.8, allocated_budget=1000.0),
        ]
        adjustments = ctrl.optimize_budgets(states)
        assert len(adjustments) >= 1
        assert adjustments[0].is_increase

    def test_resource_to_evolution_flow(self):
        """Resource → Evolution 流程"""
        ctrl = ResourceController()
        state = make_state(
            "P04", fatigue_score=0.85, prediction_confidence=0.85,
        )
        # 疲劳 → 突变预算
        alloc = ctrl.allocate_single(state, resource_type=ResourceType.MUTATION_BUDGET)
        assert alloc is not None

    def test_multi_product_budget_split(self):
        """多产品预算拆分"""
        ctrl = ResourceController(total_budget=30000.0)
        states = [
            make_state("P04", total_budget=15000.0, recent_roas=2.0),
            make_state("P05", total_budget=10000.0, recent_roas=1.0),
            make_state("P06", total_budget=5000.0, recent_roas=0.5),
        ]
        result = ctrl.allocate(states)
        # 验证三种资源类型都有分配
        resource_types = {a.resource_type for a in result}
        assert ResourceType.EXPERIMENT_BUDGET in resource_types
        assert ResourceType.MUTATION_BUDGET in resource_types
        assert ResourceType.GENERATION_CAPACITY in resource_types

    def test_single_product_complete_allocation(self):
        """单产品完整分配"""
        ctrl = ResourceController(total_budget=5000.0)
        state = make_state("P04")
        alloc = ctrl.allocate_single(state)
        assert alloc.allocation_id.startswith("RA_")
        assert alloc.priority > 0

    def test_decision_summarizes_correctly(self):
        """决策摘要正确"""
        ctrl = ResourceController(total_budget=20000.0)
        states = [
            make_state("P04", recent_roas=2.0),
            make_state("P05", recent_roas=1.0),
        ]
        result = ctrl.allocate(states)
        summary = ctrl.get_summary(result)
        assert summary["total_budget"] == 20000.0
        assert summary["allocation_rate"] > 0

    def test_allocation_has_expected_roi(self):
        """分配结果包含预期 ROI"""
        ctrl = ResourceController()
        state = make_state("P04", recent_roas=2.5)
        alloc = ctrl.allocate_single(state)
        assert alloc.expected_roi == 2.5

    def test_allocation_has_confidence(self):
        """分配结果包含置信度"""
        ctrl = ResourceController()
        state = make_state("P04", prediction_confidence=0.88)
        alloc = ctrl.allocate_single(state)
        assert alloc.confidence > 0

    def test_policy_adjustment_flow(self):
        """策略 → 调整 → 分配完整链"""
        ctrl = ResourceController(total_budget=10000.0)
        # 赢家产品
        winner = make_state("P04", recent_roas=2.0, fatigue_score=0.1, prediction_confidence=0.9)
        # 低潜力产品
        loser = make_state("P05", recent_roas=0.3, fatigue_score=0.85)
        result = ctrl.allocate([winner, loser])
        by_product = {}
        for a in result:
            by_product[a.product_id] = by_product.get(a.product_id, 0.0) + a.allocated_amount
        assert by_product["P04"] > by_product["P05"]

    def test_controller_with_requests(self):
        """带请求的分配"""
        ctrl = ResourceController(total_budget=10000.0)
        states = [make_state("P04")]
        requests = [make_request("P04", requested_amount=5000.0)]
        result = ctrl.allocate(states, requests=requests)
        assert len(result) >= 1

    def test_optimize_and_allocate_combined(self):
        """优化 + 分配组合"""
        ctrl = ResourceController(total_budget=20000.0)
        states = [
            make_state("P04", recent_roas=2.0, prediction_confidence=0.8, allocated_budget=1000.0),
            make_state("P05", recent_roas=0.8, allocated_budget=1000.0),
        ]
        # 先优化
        adjustments = ctrl.optimize_budgets(states)
        assert len(adjustments) >= 2
        # 再分配
        result = ctrl.allocate(states)
        assert len(result) >= 4

    def test_summary_by_resource_type(self):
        """摘要按资源类型分组"""
        ctrl = ResourceController(total_budget=10000.0)
        states = [make_state("P04")]
        result = ctrl.allocate(states)
        summary = ctrl.get_summary(result)
        assert "by_resource_type" in summary
        assert len(summary["by_resource_type"]) >= 1

    def test_empty_controller_does_not_crash(self):
        """空控制器不崩溃"""
        ctrl = ResourceController()
        result = ctrl.allocate([])
        assert result == []

    def test_request_metadata_preserved(self):
        """请求元数据保留"""
        req = make_request()
        req.metadata = {"source": "e12.3", "prediction_id": "P123"}
        assert req.metadata["source"] == "e12.3"

    def test_state_to_dict(self):
        """状态序列化"""
        s = make_state()
        d = s.to_dict()
        assert d["product_id"] == "P04"
        assert "is_healthy" in d
        assert "needs_attention" in d

    def test_allocation_priority_rounds_to_100(self):
        """分配优先级在 0-100 范围"""
        ctrl = ResourceController()
        state = make_state("P04")
        alloc = ctrl.allocate_single(state)
        assert 0 <= alloc.priority <= 100

    def test_softmax_handles_single_product_with_min_allocation(self):
        """Softmax 单产品最小分配"""
        result = softmax_allocate([("P04", 0.8)], 1000.0, min_allocation=2000.0)
        assert result[0][1] == 0.0


# ═══════════════════════════════════════════════════════════════
# TestEdgeCases — 10 tests
# ═══════════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界情况"""

    def test_state_all_zeros(self):
        s = ProductResourceState(product_id="P00")
        assert s.budget_remaining == 0.0
        assert s.budget_utilization == 0.0
        assert s.spend_efficiency == 0.0

    def test_state_all_max_values(self):
        s = ProductResourceState(
            product_id="P99",
            total_budget=100000.0,
            allocated_budget=100000.0,
            recent_roas=10.0,
            fatigue_score=1.0,
            prediction_confidence=1.0,
            population_diversity=1.0,
        )
        assert s.budget_remaining == 0.0
        assert s.budget_utilization == 1.0
        assert s.is_healthy is False

    def test_request_negative_amount(self):
        req = ResourceRequest(
            product_id="P04",
            requested_amount=-100.0,
        )
        assert req.requested_amount == -100.0

    def test_adjustment_zero_previous(self):
        adj = BudgetAdjustment(
            previous_amount=0.0,
            new_amount=1000.0,
        )
        assert adj.change_pct == 0.0  # no division by zero

    def test_softmax_very_large_scores(self):
        result = softmax_allocate([("P04", 100.0), ("P05", 1.0)], 1000.0)
        p04 = [a for pid, a in result if pid == "P04"][0]
        p05 = [a for pid, a in result if pid == "P05"][0]
        assert p04 > p05

    def test_allocator_very_similar_scores(self):
        allocator = PriorityAllocator()
        states = [
            make_state("P04", recent_roas=1.0, fatigue_score=0.3, prediction_confidence=0.7),
            make_state("P05", recent_roas=1.0, fatigue_score=0.3, prediction_confidence=0.7),
        ]
        result = allocator.allocate(states, 10000.0)
        assert result[0].allocated_amount == pytest.approx(result[1].allocated_amount, abs=1.0)

    def test_budget_split_zero_ratio(self):
        allocator = PriorityAllocator()
        states = [make_state("P04")]
        split = {ResourceType.EXPERIMENT_BUDGET: 0.0, ResourceType.MUTATION_BUDGET: 1.0}
        result = allocator.allocate_budget_split(states, 10000.0, split_ratio=split)
        assert len(result) == 1

    def test_controller_all_policies_trigger(self):
        ctrl = ResourceController(total_budget=10000.0)
        state = make_state(
            "P04",
            recent_roas=2.0, fatigue_score=0.9,
            prediction_confidence=0.9, population_diversity=0.8,
            allocated_budget=1000.0, total_budget=5000.0,
        )
        # 多个策略可能同时触发
        alloc = ctrl.allocate_single(state)
        assert alloc is not None

    def test_optimize_all_no_adjustments(self):
        opt = BudgetOptimizer()
        states = [make_state("P04", recent_roas=1.2, allocated_budget=500.0)]
        adjustments = opt.optimize_all(states)
        assert adjustments == []

    def test_get_summary_empty(self):
        ctrl = ResourceController(total_budget=10000.0)
        summary = ctrl.get_summary([])
        assert summary["total_allocated"] == 0.0
        assert summary["funded_products"] == 0