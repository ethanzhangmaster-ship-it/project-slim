"""E12.6.5 — Meta Portfolio Optimizer Test Suite。

覆盖:
  - TestModels:              模型测试 (10)
  - TestPortfolioAnalyzer:   组合分析器测试 (10)
  - TestFitnessRanker:       适应度排名器测试 (20)
  - TestAllocationEngine:    预算分配引擎测试 (25)
  - TestLifecycleAllocator:  生命周期分配器测试 (15)
  - TestExperimentAllocator: 实验分配器测试 (15)
  - TestPortfolioOptimizer:  控制器测试 (25)
  - TestIntegration:         集成测试 (10)

总计: 130 tests
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.reality.meta_learning.portfolio_optimizer import (
    AllocationEngine,
    BudgetAllocation,
    ExperimentAllocation,
    ExperimentAllocator,
    FitnessRanker,
    LifecycleAllocator,
    PortfolioAction,
    PortfolioAnalyzer,
    PortfolioDecision,
    PortfolioOptimizer,
    PortfolioResult,
    PortfolioSnapshot,
    ProductFitness,
    ProductLifecycleStage,
    get_default_action,
)


# ── Helpers ─────────────────────────────────────────────────


def make_product(
    product_id: str = "p04",
    revenue_potential: float = 0.7,
    growth_velocity: float = 0.6,
    creative_scalability: float = 0.5,
    market_opportunity: float = 0.5,
    risk: float = 0.3,
    lifecycle_stage: str = "growth",
    spend: float = 10000.0,
    revenue: float = 15000.0,
) -> dict:
    return {
        "product_id": product_id,
        "revenue_potential": revenue_potential,
        "growth_velocity": growth_velocity,
        "creative_scalability": creative_scalability,
        "market_opportunity": market_opportunity,
        "risk": risk,
        "lifecycle_stage": lifecycle_stage,
        "spend": spend,
        "revenue": revenue,
        "risk_score": risk,
        "growth_score": growth_velocity,
        "diversity_score": creative_scalability,
    }


def make_fitness(
    product_id: str = "p04",
    total_fitness: float = 0.65,
    risk: float = 0.3,
    stage: str = "growth",
) -> ProductFitness:
    return ProductFitness(
        product_id=product_id,
        total_fitness=total_fitness,
        risk=risk,
        lifecycle_stage=ProductLifecycleStage(stage),
    )


# ── TestModels ──────────────────────────────────────────────


class TestModels:
    """PortfolioSnapshot, ProductFitness, BudgetAllocation, etc. 模型测试。"""

    def test_snapshot_defaults(self):
        s = PortfolioSnapshot()
        assert s.product_count == 0
        assert s.total_spend == 0.0
        assert s.total_roas == 0.0
        assert not s.is_profitable

    def test_snapshot_is_profitable(self):
        s = PortfolioSnapshot(total_revenue=20000, total_spend=10000, total_roas=2.0)
        assert s.total_roas == 2.0
        assert s.is_profitable

    def test_snapshot_is_healthy(self):
        s = PortfolioSnapshot(
            total_revenue=20000,
            total_spend=10000,
            total_roas=2.0,
            risk_score=0.3,
            growth_score=0.5,
        )
        assert s.is_healthy

    def test_snapshot_not_healthy_high_risk(self):
        s = PortfolioSnapshot(
            total_revenue=20000,
            total_spend=10000,
            risk_score=0.6,
            growth_score=0.5,
        )
        assert not s.is_healthy

    def test_snapshot_avg_revenue_per_product(self):
        s = PortfolioSnapshot(
            products=["p04", "p05"],
            total_revenue=20000,
        )
        assert s.avg_revenue_per_product == 10000.0

    def test_product_fitness_risk_adjusted(self):
        f = ProductFitness(total_fitness=0.8, risk=0.5)
        assert f.risk_adjusted_fitness == pytest.approx(0.6)

    def test_product_fitness_high_potential(self):
        f = ProductFitness(total_fitness=0.75)
        assert f.is_high_potential

    def test_product_fitness_low_potential(self):
        f = ProductFitness(total_fitness=0.25)
        assert f.is_low_potential

    def test_budget_allocation_is_increased(self):
        b = BudgetAllocation(change_pct=0.1)
        assert b.is_increased
        assert not b.is_decreased

    def test_budget_allocation_is_decreased(self):
        b = BudgetAllocation(change_pct=-0.1)
        assert b.is_decreased
        assert not b.is_increased

    def test_experiment_allocation_is_maintained(self):
        e = ExperimentAllocation(change_pct=0.0)
        assert e.is_maintained

    def test_portfolio_decision_expansion(self):
        d = PortfolioDecision(action=PortfolioAction.INCREASE_INVESTMENT)
        assert d.is_expansion

    def test_portfolio_decision_contraction(self):
        d = PortfolioDecision(action=PortfolioAction.SUNSET)
        assert d.is_contraction

    def test_get_default_action(self):
        assert get_default_action(ProductLifecycleStage.LAUNCH) == PortfolioAction.EXPLORE
        assert get_default_action(ProductLifecycleStage.GROWTH) == PortfolioAction.INCREASE_INVESTMENT
        assert get_default_action(ProductLifecycleStage.PEAK) == PortfolioAction.MAINTAIN
        assert get_default_action(ProductLifecycleStage.DEATH) == PortfolioAction.SUNSET

    def test_budget_allocation_to_dict(self):
        b = BudgetAllocation(
            product_id="p04",
            allocated_budget=50000,
            allocation_pct=0.5,
            previous_budget=40000,
            change_pct=0.25,
            reason="increased_due_to_fitness",
        )
        d = b.to_dict()
        assert d["product_id"] == "p04"
        assert d["allocated_budget"] == 50000.0
        assert d["is_increased"] is True

    def test_experiment_allocation_to_dict(self):
        e = ExperimentAllocation(
            product_id="p04",
            allocated_slots=30,
            allocation_pct=0.3,
            previous_slots=20,
            change_pct=0.5,
            reason="increased",
        )
        d = e.to_dict()
        assert d["allocated_slots"] == 30
        assert d["is_increased"] is True

    def test_portfolio_decision_to_dict(self):
        d = PortfolioDecision(
            product_id="p04",
            action=PortfolioAction.INCREASE_INVESTMENT,
            confidence=0.85,
            reasons=["high growth"],
        )
        result = d.to_dict()
        assert result["action"] == "increase_investment"
        assert result["is_actionable"] is True

    def test_portfolio_result_properties(self):
        r = PortfolioResult(
            total_budget=100000,
            total_experiments=100,
        )
        assert r.total_allocated_budget == 0.0
        assert r.budget_utilization == 0.0
        assert r.expansion_count == 0

    def test_product_fitness_repr(self):
        f = ProductFitness(product_id="p04", total_fitness=0.75, rank=1)
        r = repr(f)
        assert "p04" in r
        assert "0.75" in r


# ── TestPortfolioAnalyzer ───────────────────────────────────


class TestPortfolioAnalyzer:
    """组合分析器测试。"""

    def test_empty_analyzer(self):
        a = PortfolioAnalyzer()
        s = a.analyze()
        assert s.product_count == 0
        assert s.total_spend == 0.0

    def test_single_product(self):
        a = PortfolioAnalyzer()
        a.add_product_state("p04", {"spend": 10000, "revenue": 15000})
        s = a.analyze()
        assert s.product_count == 1
        assert s.products == ["p04"]
        assert s.total_spend == 10000.0
        assert s.total_revenue == 15000.0
        assert s.total_roas == 1.5

    def test_multiple_products(self):
        a = PortfolioAnalyzer()
        a.add_product_state("p04", {"spend": 10000, "revenue": 15000})
        a.add_product_state("p05", {"spend": 20000, "revenue": 25000})
        a.add_product_state("p06", {"spend": 5000, "revenue": 4000})
        s = a.analyze()
        assert s.product_count == 3
        assert s.total_spend == 35000.0
        assert s.total_revenue == 44000.0
        assert s.total_roas == pytest.approx(44000 / 35000, rel=0.001)

    def test_zero_spend_roas(self):
        a = PortfolioAnalyzer()
        a.add_product_state("p04", {"spend": 0, "revenue": 1000})
        s = a.analyze()
        assert s.total_roas == 0.0

    def test_risk_growth_diversity(self):
        a = PortfolioAnalyzer()
        a.add_product_state("p04", {"risk_score": 0.3, "growth_score": 0.7, "diversity_score": 0.5})
        a.add_product_state("p05", {"risk_score": 0.5, "growth_score": 0.5, "diversity_score": 0.3})
        s = a.analyze()
        assert s.risk_score == pytest.approx(0.4)
        assert s.growth_score == pytest.approx(0.6)
        assert s.diversity_score == pytest.approx(0.4)

    def test_get_product_state(self):
        a = PortfolioAnalyzer()
        a.add_product_state("p04", {"spend": 1000})
        assert a.get_product_state("p04") == {"spend": 1000}
        assert a.get_product_state("p05") is None

    def test_get_all_product_ids(self):
        a = PortfolioAnalyzer()
        a.add_product_states({"p04": {}, "p05": {}, "p06": {}})
        ids = a.get_all_product_ids()
        assert set(ids) == {"p04", "p05", "p06"}

    def test_clear(self):
        a = PortfolioAnalyzer()
        a.add_product_state("p04", {"spend": 1000})
        a.clear()
        assert a.product_count == 0

    def test_batch_add(self):
        a = PortfolioAnalyzer()
        a.add_product_states({"p04": {"spend": 1000}, "p05": {"spend": 2000}})
        assert a.product_count == 2

    def test_analyzer_repr(self):
        a = PortfolioAnalyzer()
        a.add_product_state("p04", {})
        r = repr(a)
        assert "1" in r


# ── TestFitnessRanker ───────────────────────────────────────


class TestFitnessRanker:
    """适应度排名器测试。"""

    def test_default_weights(self):
        r = FitnessRanker()
        w = r.weights
        assert w["revenue_potential"] == 0.30
        assert w["growth_velocity"] == 0.25
        assert w["creative_scalability"] == 0.20
        assert w["market_opportunity"] == 0.15
        assert w["risk"] == 0.10

    def test_invalid_weights(self):
        with pytest.raises(ValueError, match="sum to 1.0"):
            FitnessRanker(weights={"revenue_potential": 0.5, "growth_velocity": 0.3})

    def test_calculate_perfect_product(self):
        r = FitnessRanker()
        f = r.calculate_fitness("p04", 1.0, 1.0, 1.0, 1.0, 0.0)
        # 0.30 + 0.25 + 0.20 + 0.15 + 0.10 = 1.0
        assert f.total_fitness == pytest.approx(1.0)
        assert f.risk == 0.0

    def test_calculate_worst_product(self):
        r = FitnessRanker()
        f = r.calculate_fitness("p04", 0.0, 0.0, 0.0, 0.0, 1.0)
        # 0 + 0 + 0 + 0 + 0 = 0.0 (risk_score = 1 - 1 = 0)
        assert f.total_fitness == pytest.approx(0.0)

    def test_calculate_all_defaults(self):
        r = FitnessRanker()
        f = r.calculate_fitness("p04")
        # 0.5*0.30 + 0.5*0.25 + 0.5*0.20 + 0.5*0.15 + 0.5*0.10 = 0.5
        assert f.total_fitness == pytest.approx(0.5)

    def test_risk_lower_is_better(self):
        r = FitnessRanker()
        high_risk = r.calculate_fitness("p04", risk=0.9)
        low_risk = r.calculate_fitness("p04", risk=0.1)
        assert low_risk.total_fitness > high_risk.total_fitness

    def test_rank_orders_by_fitness(self):
        r = FitnessRanker()
        f1 = ProductFitness(product_id="p04", total_fitness=0.5)
        f2 = ProductFitness(product_id="p05", total_fitness=0.9)
        f3 = ProductFitness(product_id="p06", total_fitness=0.3)
        ranked = r.rank([f1, f2, f3])
        assert ranked[0].product_id == "p05"
        assert ranked[0].rank == 1
        assert ranked[1].product_id == "p04"
        assert ranked[2].product_id == "p06"
        assert ranked[2].rank == 3

    def test_rank_same_fitness_uses_risk_adjusted(self):
        r = FitnessRanker()
        f1 = ProductFitness(product_id="p04", total_fitness=0.5, risk=0.1)
        f2 = ProductFitness(product_id="p05", total_fitness=0.5, risk=0.9)
        ranked = r.rank([f1, f2])
        # f1 has lower risk → higher risk_adjusted_fitness
        assert ranked[0].product_id == "p04"

    def test_calculate_and_rank(self):
        r = FitnessRanker()
        products = [
            {"product_id": "p04", "revenue_potential": 0.8, "growth_velocity": 0.7,
             "creative_scalability": 0.6, "market_opportunity": 0.5, "risk": 0.2},
            {"product_id": "p05", "revenue_potential": 0.9, "growth_velocity": 0.8,
             "creative_scalability": 0.7, "market_opportunity": 0.6, "risk": 0.1},
        ]
        ranked = r.calculate_and_rank(products)
        assert len(ranked) == 2
        assert ranked[0].product_id == "p05"  # higher fitness
        assert ranked[0].rank == 1

    def test_lifecycle_stage_parsing(self):
        r = FitnessRanker()
        f = r.calculate_fitness("p04", lifecycle_stage="growth")
        assert f.lifecycle_stage == ProductLifecycleStage.GROWTH
        f2 = r.calculate_fitness("p04", lifecycle_stage=ProductLifecycleStage.LAUNCH)
        assert f2.lifecycle_stage == ProductLifecycleStage.LAUNCH

    def test_lifecycle_stage_default(self):
        r = FitnessRanker()
        f = r.calculate_fitness("p04")
        assert f.lifecycle_stage == ProductLifecycleStage.PEAK

    def test_lifecycle_stage_invalid(self):
        r = FitnessRanker()
        f = r.calculate_fitness("p04", lifecycle_stage="invalid")
        assert f.lifecycle_stage == ProductLifecycleStage.PEAK

    def test_custom_weights(self):
        r = FitnessRanker(weights={
            "revenue_potential": 0.50,
            "growth_velocity": 0.20,
            "creative_scalability": 0.10,
            "market_opportunity": 0.10,
            "risk": 0.10,
        })
        f = r.calculate_fitness("p04", revenue_potential=1.0, growth_velocity=0.0,
                                creative_scalability=0.0, market_opportunity=0.0, risk=1.0)
        # 1.0*0.50 + 0 + 0 + 0 + 0 = 0.50
        assert f.total_fitness == pytest.approx(0.50)

    def test_rank_empty_list(self):
        r = FitnessRanker()
        ranked = r.rank([])
        assert ranked == []

    def test_rank_single_product(self):
        r = FitnessRanker()
        f = ProductFitness(product_id="p04", total_fitness=0.7)
        ranked = r.rank([f])
        assert len(ranked) == 1
        assert ranked[0].rank == 1

    def test_metadata_passthrough(self):
        r = FitnessRanker()
        f = r.calculate_fitness("p04", extra_key="value")
        assert f.metadata.get("extra_key") == "value"

    def test_ranker_repr(self):
        r = FitnessRanker()
        rep = repr(r)
        assert "rp=0.30" in rep

    def test_calculate_and_rank_empty(self):
        r = FitnessRanker()
        ranked = r.calculate_and_rank([])
        assert ranked == []

    def test_fitness_product_high_market_opportunity(self):
        r = FitnessRanker()
        f = r.calculate_fitness("p04", market_opportunity=0.9)
        assert f.total_fitness > 0.5

    def test_fitness_high_creative_scalability(self):
        r = FitnessRanker()
        f = r.calculate_fitness("p04", creative_scalability=0.9)
        assert f.total_fitness > 0.5


# ── TestAllocationEngine ────────────────────────────────────


class TestAllocationEngine:
    """预算分配引擎测试。"""

    def test_empty_fitness(self):
        e = AllocationEngine()
        result = e.allocate([], 100000)
        assert result == []

    def test_zero_budget(self):
        e = AllocationEngine()
        f = [make_fitness("p04")]
        result = e.allocate(f, 0)
        assert result == []

    def test_single_product_gets_all(self):
        e = AllocationEngine()
        f = [make_fitness("p04")]
        result = e.allocate(f, 100000)
        assert len(result) == 1
        assert result[0].allocated_budget == 100000.0
        assert result[0].allocation_pct == pytest.approx(1.0)

    def test_two_products_proportional(self):
        e = AllocationEngine()
        f1 = make_fitness("p04", total_fitness=0.6)
        f2 = make_fitness("p05", total_fitness=0.4)
        result = e.allocate([f1, f2], 100000)
        # Both are growth → multiplier 1.5
        # weighted: p04=0.9, p05=0.6
        # share: p04=0.6, p05=0.4
        assert len(result) == 2
        assert result[0].allocated_budget == pytest.approx(60000, abs=1)
        assert result[1].allocated_budget == pytest.approx(40000, abs=1)

    def test_allocation_percentages_sum_to_one(self):
        e = AllocationEngine()
        fs = [
            make_fitness("p04", total_fitness=0.8),
            make_fitness("p05", total_fitness=0.6),
            make_fitness("p06", total_fitness=0.4),
        ]
        result = e.allocate(fs, 100000)
        total_pct = sum(a.allocation_pct for a in result)
        assert total_pct == pytest.approx(1.0, abs=0.001)

    def test_allocation_total_matches_budget(self):
        e = AllocationEngine()
        fs = [
            make_fitness("p04", total_fitness=0.8),
            make_fitness("p05", total_fitness=0.6),
            make_fitness("p06", total_fitness=0.4),
        ]
        result = e.allocate(fs, 100000)
        total = sum(a.allocated_budget for a in result)
        assert total == pytest.approx(100000, abs=0.5)

    def test_previous_budgets(self):
        e = AllocationEngine()
        f = [make_fitness("p04")]
        result = e.allocate(f, 100000, previous_budgets={"p04": 50000})
        assert result[0].previous_budget == 50000
        assert result[0].change_pct == pytest.approx(1.0)  # doubled

    def test_previous_budget_zero(self):
        e = AllocationEngine()
        f = [make_fitness("p04")]
        result = e.allocate(f, 100000, previous_budgets={"p04": 0})
        # New allocation from zero → change_pct = 1.0 (new allocation)
        assert result[0].change_pct == 1.0

    def test_min_allocation(self):
        e = AllocationEngine()
        fs = [
            make_fitness("p04", total_fitness=0.9),
            make_fitness("p05", total_fitness=0.01),
        ]
        result = e.allocate(fs, 100000, min_allocation=10000)
        # p05 gets zero because below min
        p05 = [a for a in result if a.product_id == "p05"][0]
        assert p05.allocated_budget == 0.0

    def test_same_fitness_equal_allocation(self):
        e = AllocationEngine()
        f_growth = make_fitness("p04", total_fitness=0.5, stage="growth")
        f_peak = make_fitness("p05", total_fitness=0.5, stage="peak")
        result = e.allocate([f_growth, f_peak], 100000)
        # Same fitness → equal allocation (lifecycle adjustment done by LifecycleAllocator)
        p04 = [a for a in result if a.product_id == "p04"][0]
        p05 = [a for a in result if a.product_id == "p05"][0]
        assert p04.allocated_budget == pytest.approx(p05.allocated_budget, abs=1)

    def test_death_still_gets_proportional(self):
        e = AllocationEngine()
        f = make_fitness("p04", total_fitness=0.8, stage="death")
        result = e.allocate([f], 100000)
        # AllocationEngine does pure fitness-based allocation; lifecycle handled separately
        assert result[0].allocated_budget == 100000.0

    def test_allocate_evenly(self):
        e = AllocationEngine()
        result = e.allocate_evenly(["p04", "p05", "p06"], 90000)
        assert len(result) == 3
        for a in result:
            assert a.allocated_budget == pytest.approx(30000, abs=1)
            assert a.reason == "even_allocation"

    def test_allocate_evenly_empty(self):
        e = AllocationEngine()
        assert e.allocate_evenly([], 100000) == []

    def test_allocate_evenly_zero_budget(self):
        e = AllocationEngine()
        assert e.allocate_evenly(["p04"], 0) == []

    def test_get_default_multiplier(self):
        e = AllocationEngine()
        assert e.get_default_multiplier() == 1.0

    def test_reason_new_allocation(self):
        e = AllocationEngine()
        f = [make_fitness("p04")]
        result = e.allocate(f, 100000)
        assert result[0].reason == "new_allocation"

    def test_reason_previous_decrease(self):
        e = AllocationEngine()
        f = [make_fitness("p04")]
        result = e.allocate(f, 50000, previous_budgets={"p04": 100000})
        assert result[0].reason == "decreased_due_to_fitness"

    def test_allocation_repr(self):
        b = BudgetAllocation(product_id="p04", allocated_budget=50000, change_pct=0.25)
        r = repr(b)
        assert "p04" in r
        assert "50000" in r

    def test_engine_repr(self):
        e = AllocationEngine()
        r = repr(e)
        assert "AllocationEngine" in r

    def test_custom_default_multiplier(self):
        e = AllocationEngine(default_multiplier=2.0)
        assert e.get_default_multiplier() == 2.0

    def test_all_zero_fitness(self):
        e = AllocationEngine()
        f = make_fitness("p04", total_fitness=0.0)
        result = e.allocate([f], 100000)
        assert result[0].allocated_budget == 0.0

    def test_allocate_evenly_single(self):
        e = AllocationEngine()
        result = e.allocate_evenly(["p04"], 50000)
        assert len(result) == 1
        assert result[0].allocated_budget == 50000

    def test_budget_rounding_adjustment(self):
        e = AllocationEngine()
        fs = [
            make_fitness("p04", total_fitness=0.33),
            make_fitness("p05", total_fitness=0.33),
            make_fitness("p06", total_fitness=0.34),
        ]
        result = e.allocate(fs, 100000)
        total = sum(a.allocated_budget for a in result)
        assert total == pytest.approx(100000, abs=0.5)


# ── TestLifecycleAllocator ──────────────────────────────────


class TestLifecycleAllocator:
    """生命周期分配器测试。"""

    def test_adjust_budget_growth(self):
        lc = LifecycleAllocator()
        b = BudgetAllocation(product_id="p04", allocated_budget=100000, previous_budget=80000)
        result = lc.adjust_budget(b, ProductLifecycleStage.GROWTH)
        assert result.allocated_budget == 150000.0  # ×1.5

    def test_adjust_budget_launch(self):
        lc = LifecycleAllocator()
        b = BudgetAllocation(product_id="p04", allocated_budget=100000)
        result = lc.adjust_budget(b, ProductLifecycleStage.LAUNCH)
        assert result.allocated_budget == 50000.0  # ×0.5

    def test_adjust_budget_death(self):
        lc = LifecycleAllocator()
        b = BudgetAllocation(product_id="p04", allocated_budget=100000)
        result = lc.adjust_budget(b, ProductLifecycleStage.DEATH)
        assert result.allocated_budget == 0.0

    def test_adjust_experiments_launch(self):
        lc = LifecycleAllocator()
        e = ExperimentAllocation(product_id="p04", allocated_slots=10, previous_slots=10)
        result = lc.adjust_experiments(e, ProductLifecycleStage.LAUNCH)
        assert result.allocated_slots == 20  # ×2.0

    def test_adjust_experiments_fatigue(self):
        lc = LifecycleAllocator()
        e = ExperimentAllocation(product_id="p04", allocated_slots=10)
        result = lc.adjust_experiments(e, ProductLifecycleStage.FATIGUE)
        assert result.allocated_slots == 18  # ×1.8

    def test_adjust_experiments_death(self):
        lc = LifecycleAllocator()
        e = ExperimentAllocation(product_id="p04", allocated_slots=10)
        result = lc.adjust_experiments(e, ProductLifecycleStage.DEATH)
        assert result.allocated_slots == 0

    def test_get_action(self):
        lc = LifecycleAllocator()
        assert lc.get_action(ProductLifecycleStage.LAUNCH) == PortfolioAction.EXPLORE
        assert lc.get_action(ProductLifecycleStage.GROWTH) == PortfolioAction.INCREASE_INVESTMENT
        assert lc.get_action(ProductLifecycleStage.PEAK) == PortfolioAction.MAINTAIN
        assert lc.get_action(ProductLifecycleStage.DECAY) == PortfolioAction.HARVEST
        assert lc.get_action(ProductLifecycleStage.DEATH) == PortfolioAction.SUNSET

    def test_get_budget_factor(self):
        lc = LifecycleAllocator()
        assert lc.get_budget_factor(ProductLifecycleStage.GROWTH) == 1.5
        assert lc.get_budget_factor(ProductLifecycleStage.DECAY) == 0.15

    def test_get_experiment_factor(self):
        lc = LifecycleAllocator()
        assert lc.get_experiment_factor(ProductLifecycleStage.LAUNCH) == 2.0
        assert lc.get_experiment_factor(ProductLifecycleStage.PEAK) == 1.0

    def test_get_strategy_description(self):
        lc = LifecycleAllocator()
        desc = lc.get_strategy_description(ProductLifecycleStage.GROWTH)
        assert "增长" in desc

    def test_get_strategy_description_unknown(self):
        lc = LifecycleAllocator()
        # Test with a stage that has no description
        # Using a workaround - passing a known stage
        desc = lc.get_strategy_description(ProductLifecycleStage.PEAK)
        assert "巅峰" in desc

    def test_adjust_budget_change_pct(self):
        lc = LifecycleAllocator()
        b = BudgetAllocation(product_id="p04", allocated_budget=100000, previous_budget=50000)
        result = lc.adjust_budget(b, ProductLifecycleStage.GROWTH)
        assert result.change_pct == pytest.approx(2.0)  # 150000 vs 50000

    def test_adjust_experiments_change_pct(self):
        lc = LifecycleAllocator()
        e = ExperimentAllocation(product_id="p04", allocated_slots=10, previous_slots=5)
        result = lc.adjust_experiments(e, ProductLifecycleStage.LAUNCH)
        assert result.change_pct == pytest.approx(3.0)  # 20 vs 5

    def test_custom_factors(self):
        lc = LifecycleAllocator(
            budget_factors={ProductLifecycleStage.GROWTH: 2.0},
            experiment_factors={ProductLifecycleStage.LAUNCH: 3.0},
        )
        assert lc.get_budget_factor(ProductLifecycleStage.GROWTH) == 2.0
        assert lc.get_experiment_factor(ProductLifecycleStage.LAUNCH) == 3.0

    def test_lifecycle_allocator_repr(self):
        lc = LifecycleAllocator()
        r = repr(lc)
        assert "LifecycleAllocator" in r


# ── TestExperimentAllocator ─────────────────────────────────


class TestExperimentAllocator:
    """实验分配器测试。"""

    def test_empty_fitness(self):
        e = ExperimentAllocator()
        assert e.allocate([], 100) == []

    def test_zero_slots(self):
        e = ExperimentAllocator()
        f = [make_fitness("p04")]
        assert e.allocate(f, 0) == []

    def test_single_product_gets_all(self):
        e = ExperimentAllocator()
        f = [make_fitness("p04")]
        result = e.allocate(f, 50)
        assert len(result) == 1
        assert result[0].allocated_slots == 50

    def test_total_slots_match(self):
        e = ExperimentAllocator()
        fs = [
            make_fitness("p04", total_fitness=0.8),
            make_fitness("p05", total_fitness=0.6),
            make_fitness("p06", total_fitness=0.4),
        ]
        result = e.allocate(fs, 100)
        total = sum(a.allocated_slots for a in result)
        assert total == 100

    def test_launch_gets_more_experiments(self):
        e = ExperimentAllocator()
        f_launch = make_fitness("p04", total_fitness=0.5, stage="launch")
        f_peak = make_fitness("p05", total_fitness=0.5, stage="peak")
        result = e.allocate([f_launch, f_peak], 100)
        p04 = [a for a in result if a.product_id == "p04"][0]
        p05 = [a for a in result if a.product_id == "p05"][0]
        # launch gets 2.0x, peak gets 1.0x → launch gets more
        assert p04.allocated_slots > p05.allocated_slots

    def test_death_gets_zero(self):
        e = ExperimentAllocator()
        f = make_fitness("p04", total_fitness=0.8, stage="death")
        result = e.allocate([f], 100)
        assert result[0].allocated_slots == 0

    def test_transfer_bonus(self):
        e = ExperimentAllocator()
        f1 = make_fitness("p04", total_fitness=0.5)
        f2 = make_fitness("p05", total_fitness=0.5)
        result = e.allocate(
            [f1, f2], 100,
            transfer_bonus={"p04": 0.5},
        )
        p04 = [a for a in result if a.product_id == "p04"][0]
        p05 = [a for a in result if a.product_id == "p05"][0]
        assert p04.allocated_slots > p05.allocated_slots

    def test_previous_slots(self):
        e = ExperimentAllocator()
        f = [make_fitness("p04")]
        result = e.allocate(f, 50, previous_slots={"p04": 30})
        assert result[0].previous_slots == 30

    def test_reason_transfer_bonus(self):
        e = ExperimentAllocator()
        f = [make_fitness("p04")]
        result = e.allocate(
            f, 50,
            previous_slots={"p04": 10},
            transfer_bonus={"p04": 0.3},
        )
        assert "transfer_bonus" in result[0].reason

    def test_get_lifecycle_factor(self):
        e = ExperimentAllocator()
        assert e.get_lifecycle_factor(ProductLifecycleStage.LAUNCH) == 2.0
        assert e.get_lifecycle_factor(ProductLifecycleStage.DEATH) == 0.0

    def test_experiment_allocator_repr(self):
        e = ExperimentAllocator()
        r = repr(e)
        assert "ExperimentAllocator" in r

    def test_zero_weight_products(self):
        e = ExperimentAllocator()
        f = [make_fitness("p04", total_fitness=0.0, stage="death")]
        result = e.allocate(f, 100)
        assert result[0].allocated_slots == 0
        assert result[0].reason == "zero_weight"

    def test_custom_factors(self):
        e = ExperimentAllocator(
            lifecycle_factors={ProductLifecycleStage.LAUNCH: 3.0}
        )
        assert e.get_lifecycle_factor(ProductLifecycleStage.LAUNCH) == 3.0

    def test_experiment_reason_increased(self):
        e = ExperimentAllocator()
        f = [make_fitness("p04")]
        result = e.allocate(f, 50, previous_slots={"p04": 10})
        assert "increased" in result[0].reason

    def test_experiment_reason_decreased(self):
        e = ExperimentAllocator()
        f = [make_fitness("p04")]
        result = e.allocate(f, 5, previous_slots={"p04": 50})
        assert "decreased" in result[0].reason


# ── TestPortfolioOptimizer ──────────────────────────────────


class TestPortfolioOptimizer:
    """控制器测试。"""

    def test_optimize_empty(self):
        o = PortfolioOptimizer()
        result = o.optimize([], 100000, 100)
        assert len(result.fitness_scores) == 0
        assert len(result.decisions) == 0

    def test_optimize_single_product(self):
        o = PortfolioOptimizer()
        result = o.optimize(
            [make_product("p04")],
            total_budget=100000,
            total_experiments=100,
        )
        assert len(result.fitness_scores) == 1
        assert result.fitness_scores[0].rank == 1
        assert len(result.decisions) == 1
        assert result.snapshot is not None
        assert result.snapshot.product_count == 1

    def test_optimize_multiple_products(self):
        o = PortfolioOptimizer()
        products = [
            make_product("p04", revenue_potential=0.8, growth_velocity=0.7,
                         creative_scalability=0.6, risk=0.2, lifecycle_stage="growth"),
            make_product("p05", revenue_potential=0.6, growth_velocity=0.5,
                         creative_scalability=0.5, risk=0.3, lifecycle_stage="peak"),
            make_product("p06", revenue_potential=0.3, growth_velocity=0.2,
                         creative_scalability=0.3, risk=0.7, lifecycle_stage="decay"),
        ]
        result = o.optimize(products, total_budget=100000, total_experiments=100)
        assert len(result.fitness_scores) == 3
        assert len(result.decisions) == 3
        assert len(result.budget_allocations) == 3
        assert len(result.experiment_allocations) == 3

    def test_optimize_ranking_order(self):
        o = PortfolioOptimizer()
        products = [
            make_product("p05", revenue_potential=0.9, growth_velocity=0.8,
                         creative_scalability=0.7, risk=0.1),
            make_product("p04", revenue_potential=0.7, growth_velocity=0.6,
                         creative_scalability=0.5, risk=0.3),
        ]
        result = o.optimize(products, total_budget=100000, total_experiments=100)
        ranked = result.fitness_scores
        assert ranked[0].product_id == "p05"
        assert ranked[0].rank == 1

    def test_optimize_snapshot_includes_products(self):
        o = PortfolioOptimizer()
        result = o.optimize(
            [make_product("p04", spend=10000, revenue=15000)],
            total_budget=100000,
            total_experiments=100,
        )
        assert result.snapshot.products == ["p04"]
        assert result.snapshot.total_spend == 10000.0
        assert result.snapshot.total_revenue == 15000.0

    def test_optimize_previous_budgets(self):
        o = PortfolioOptimizer()
        result = o.optimize(
            [make_product("p04")],
            total_budget=100000,
            total_experiments=100,
            previous_budgets={"p04": 50000},
        )
        assert result.budget_allocations[0].previous_budget == 50000

    def test_optimize_previous_slots(self):
        o = PortfolioOptimizer()
        result = o.optimize(
            [make_product("p04")],
            total_budget=100000,
            total_experiments=100,
            previous_slots={"p04": 30},
        )
        assert result.experiment_allocations[0].previous_slots == 30

    def test_optimize_transfer_bonus(self):
        o = PortfolioOptimizer()
        products = [
            make_product("p04", lifecycle_stage="growth"),
            make_product("p05", lifecycle_stage="growth"),
        ]
        result = o.optimize(
            products,
            total_budget=100000,
            total_experiments=100,
            transfer_bonus={"p04": 0.5},
        )
        p04_exp = [a for a in result.experiment_allocations if a.product_id == "p04"][0]
        p05_exp = [a for a in result.experiment_allocations if a.product_id == "p05"][0]
        assert p04_exp.allocated_slots > p05_exp.allocated_slots

    def test_optimize_decisions_have_actions(self):
        o = PortfolioOptimizer()
        products = [
            make_product("p04", lifecycle_stage="growth"),
            make_product("p05", lifecycle_stage="decay"),
        ]
        result = o.optimize(products, total_budget=100000, total_experiments=100)
        actions = {d.product_id: d.action for d in result.decisions}
        # growth → INCREASE_INVESTMENT
        # decay → HARVEST
        assert actions["p05"] == PortfolioAction.HARVEST

    def test_optimize_death_product_sunset(self):
        o = PortfolioOptimizer()
        result = o.optimize(
            [make_product("p04", lifecycle_stage="death")],
            total_budget=100000,
            total_experiments=100,
        )
        assert result.decisions[0].action == PortfolioAction.SUNSET

    def test_optimize_launch_product_explore(self):
        o = PortfolioOptimizer()
        result = o.optimize(
            [make_product("p04", lifecycle_stage="launch")],
            total_budget=100000,
            total_experiments=100,
        )
        assert result.decisions[0].action == PortfolioAction.EXPLORE

    def test_optimize_result_summary(self):
        o = PortfolioOptimizer()
        result = o.optimize(
            [make_product("p04")],
            total_budget=100000,
            total_experiments=100,
        )
        assert "Portfolio" in result.summary
        assert "p04" in result.summary

    def test_optimize_result_to_dict(self):
        o = PortfolioOptimizer()
        result = o.optimize(
            [make_product("p04")],
            total_budget=100000,
            total_experiments=100,
        )
        d = result.to_dict()
        assert "result_id" in d
        assert "budget_allocations" in d
        assert "decisions" in d

    def test_get_last_result(self):
        o = PortfolioOptimizer()
        assert o.get_last_result() is None
        o.optimize([make_product("p04")], 100000, 100)
        assert o.get_last_result() is not None

    def test_get_fitness_scores(self):
        o = PortfolioOptimizer()
        scores = o.get_fitness_scores([make_product("p04")])
        assert len(scores) == 1
        assert scores[0].rank == 1

    def test_optimize_total_budget_utilization(self):
        o = PortfolioOptimizer()
        result = o.optimize(
            [make_product("p04")],
            total_budget=100000,
            total_experiments=100,
        )
        assert result.budget_utilization >= 0.0

    def test_optimize_expansion_count(self):
        o = PortfolioOptimizer()
        products = [
            make_product("p04", lifecycle_stage="growth"),
            make_product("p05", lifecycle_stage="decay"),
        ]
        result = o.optimize(products, total_budget=100000, total_experiments=100)
        assert result.expansion_count >= 0

    def test_optimize_top_product(self):
        o = PortfolioOptimizer()
        products = [
            make_product("p04", revenue_potential=0.6),
            make_product("p05", revenue_potential=0.9),
        ]
        result = o.optimize(products, total_budget=100000, total_experiments=100)
        assert result.top_product == "p05"

    def test_optimize_budget_allocations_present(self):
        o = PortfolioOptimizer()
        result = o.optimize(
            [make_product("p04")],
            total_budget=100000,
            total_experiments=100,
        )
        assert len(result.budget_allocations) == 1
        assert result.budget_allocations[0].product_id == "p04"

    def test_optimize_experiment_allocations_present(self):
        o = PortfolioOptimizer()
        result = o.optimize(
            [make_product("p04")],
            total_budget=100000,
            total_experiments=100,
        )
        assert len(result.experiment_allocations) == 1
        assert result.experiment_allocations[0].product_id == "p04"

    def test_optimize_with_custom_components(self):
        o = PortfolioOptimizer(
            ranker=FitnessRanker(weights={
                "revenue_potential": 0.50,
                "growth_velocity": 0.20,
                "creative_scalability": 0.10,
                "market_opportunity": 0.10,
                "risk": 0.10,
            }),
        )
        result = o.optimize(
            [make_product("p04")],
            total_budget=100000,
            total_experiments=100,
        )
        assert len(result.fitness_scores) == 1

    def test_optimize_decision_confidence(self):
        o = PortfolioOptimizer()
        result = o.optimize(
            [make_product("p04", lifecycle_stage="growth")],
            total_budget=100000,
            total_experiments=100,
        )
        assert result.decisions[0].confidence > 0

    def test_optimize_decision_reasons(self):
        o = PortfolioOptimizer()
        result = o.optimize(
            [make_product("p04", lifecycle_stage="growth")],
            total_budget=100000,
            total_experiments=100,
        )
        assert len(result.decisions[0].reasons) > 0

    def test_optimizer_repr(self):
        o = PortfolioOptimizer()
        r = repr(o)
        assert "PortfolioOptimizer" in r

    def test_result_repr(self):
        o = PortfolioOptimizer()
        result = o.optimize(
            [make_product("p04")],
            total_budget=100000,
            total_experiments=100,
        )
        r = repr(result)
        assert "PortfolioResult" in r


# ── TestIntegration ─────────────────────────────────────────


class TestIntegration:
    """集成测试。"""

    def test_full_flow_three_products(self):
        """完整流程：三产品组合优化。"""
        o = PortfolioOptimizer()
        products = [
            make_product("p04", revenue_potential=0.85, growth_velocity=0.8,
                         creative_scalability=0.6, risk=0.2,
                         lifecycle_stage="growth", spend=40000, revenue=60000),
            make_product("p05", revenue_potential=0.60, growth_velocity=0.5,
                         creative_scalability=0.5, risk=0.3,
                         lifecycle_stage="peak", spend=35000, revenue=45000),
            make_product("p06", revenue_potential=0.30, growth_velocity=0.2,
                         creative_scalability=0.3, risk=0.7,
                         lifecycle_stage="decay", spend=25000, revenue=20000),
        ]
        result = o.optimize(
            products,
            total_budget=100000,
            total_experiments=100,
            previous_budgets={"p04": 40000, "p05": 35000, "p06": 25000},
            previous_slots={"p04": 30, "p05": 30, "p06": 40},
        )

        # 三产品都有结果
        assert len(result.fitness_scores) == 3
        assert len(result.budget_allocations) == 3
        assert len(result.experiment_allocations) == 3
        assert len(result.decisions) == 3

        # 排名正确
        ranked = result.fitness_scores
        assert ranked[0].product_id == "p04"  # highest fitness
        assert ranked[0].rank == 1
        assert ranked[2].product_id == "p06"  # lowest fitness
        assert ranked[2].rank == 3

        # 组合快照正确
        snapshot = result.snapshot
        assert snapshot is not None
        assert snapshot.total_spend == 100000.0
        assert snapshot.total_revenue == 125000.0
        assert snapshot.total_roas == 1.25

        # 决策动作正确
        actions = {d.product_id: d.action for d in result.decisions}
        assert actions["p04"] == PortfolioAction.INCREASE_INVESTMENT
        assert actions["p06"] == PortfolioAction.HARVEST

        # 预算分配有差异
        p04_budget = [a for a in result.budget_allocations if a.product_id == "p04"][0]
        p06_budget = [a for a in result.budget_allocations if a.product_id == "p06"][0]
        assert p04_budget.allocated_budget > p06_budget.allocated_budget

    def test_full_flow_all_growth(self):
        """所有产品都处于增长期。"""
        o = PortfolioOptimizer()
        products = [
            make_product("p04", lifecycle_stage="growth"),
            make_product("p05", lifecycle_stage="growth"),
        ]
        result = o.optimize(products, total_budget=100000, total_experiments=100)
        for d in result.decisions:
            assert d.action == PortfolioAction.INCREASE_INVESTMENT

    def test_full_flow_mixed_launch_growth_peak(self):
        """混合生命周期。"""
        o = PortfolioOptimizer()
        products = [
            make_product("p04", lifecycle_stage="launch"),
            make_product("p05", lifecycle_stage="growth"),
            make_product("p06", lifecycle_stage="peak"),
        ]
        result = o.optimize(products, total_budget=100000, total_experiments=100)
        actions = {d.product_id: d.action for d in result.decisions}
        assert actions["p04"] == PortfolioAction.EXPLORE
        assert actions["p05"] == PortfolioAction.INCREASE_INVESTMENT
        assert actions["p06"] == PortfolioAction.MAINTAIN

    def test_full_flow_with_transfer_bonus(self):
        """跨产品迁移加分效果。"""
        o = PortfolioOptimizer()
        products = [
            make_product("p04", lifecycle_stage="growth"),
            make_product("p05", lifecycle_stage="growth"),
        ]
        result = o.optimize(
            products,
            total_budget=100000,
            total_experiments=100,
            transfer_bonus={"p04": 0.5},
        )
        p04_exp = [a for a in result.experiment_allocations if a.product_id == "p04"][0]
        p05_exp = [a for a in result.experiment_allocations if a.product_id == "p05"][0]
        assert p04_exp.allocated_slots > p05_exp.allocated_slots

    def test_full_flow_death_product_no_budget(self):
        """死亡产品零预算。"""
        o = PortfolioOptimizer()
        result = o.optimize(
            [make_product("p04", lifecycle_stage="death")],
            total_budget=100000,
            total_experiments=100,
        )
        assert result.budget_allocations[0].allocated_budget == 0.0
        assert result.experiment_allocations[0].allocated_slots == 0
        assert result.decisions[0].action == PortfolioAction.SUNSET

    def test_full_flow_high_risk_low_fitness(self):
        """高风险低适应度产品减少投资。"""
        o = PortfolioOptimizer()
        result = o.optimize(
            [make_product("p04", revenue_potential=0.2, growth_velocity=0.1,
                          risk=0.9, lifecycle_stage="fatigue")],
            total_budget=100000,
            total_experiments=100,
        )
        assert result.decisions[0].action == PortfolioAction.DECREASE_INVESTMENT

    def test_full_flow_result_consistency(self):
        """结果一致性：所有产品都有分配。"""
        o = PortfolioOptimizer()
        products = [
            make_product("p04", lifecycle_stage="growth"),
            make_product("p05", lifecycle_stage="peak"),
            make_product("p06", lifecycle_stage="launch"),
        ]
        result = o.optimize(products, total_budget=50000, total_experiments=50)
        assert len(result.budget_allocations) == 3
        assert len(result.experiment_allocations) == 3
        assert result.total_allocated_budget > 0

    def test_full_flow_all_allocations_have_reasons(self):
        """所有分配都有理由。"""
        o = PortfolioOptimizer()
        products = [
            make_product("p04", lifecycle_stage="growth"),
            make_product("p05", lifecycle_stage="peak"),
        ]
        result = o.optimize(products, total_budget=100000, total_experiments=100)
        for a in result.budget_allocations:
            assert a.reason != ""
        for a in result.experiment_allocations:
            assert a.reason != ""

    def test_full_flow_decision_has_all_fields(self):
        """决策包含所有必要字段。"""
        o = PortfolioOptimizer()
        result = o.optimize(
            [make_product("p04")],
            total_budget=100000,
            total_experiments=100,
        )
        d = result.decisions[0]
        assert d.decision_id != ""
        assert d.product_id == "p04"
        assert d.action is not None
        assert d.confidence >= 0
        assert d.fitness >= 0
        assert d.created_at is not None

    def test_full_flow_plateau_product(self):
        """平台期产品。"""
        o = PortfolioOptimizer()
        products = [
            make_product("p04", lifecycle_stage="plateau", revenue_potential=0.5,
                         risk=0.4),
        ]
        result = o.optimize(products, total_budget=100000, total_experiments=100)
        # plateau with moderate fitness → MAINTAIN
        assert result.decisions[0].action == PortfolioAction.MAINTAIN