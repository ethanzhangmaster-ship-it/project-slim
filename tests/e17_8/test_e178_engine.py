"""E17.8 — DeterministicSimulator：可复现性 / 分布形状 / 情景 / 闸门 / 组合 / 反事实。"""
from src.ceo_intelligence.decision_engine.models import DecisionType, GrowthDecision
from src.ceo_intelligence.simulation_engine.engine import DeterministicSimulator
from src.ceo_intelligence.simulation_engine.models import (
    PreFlightStatus,
    SimulationPrior,
)

TOL = 1e-6


def _decision(game_id="merge_witch", opp_type="creative_refresh",
              dtype=DecisionType.EXECUTE) -> GrowthDecision:
    return GrowthDecision(
        game_id=game_id,
        opportunity_id=f"{game_id}:{opp_type}",
        action=f"act({game_id})",
        decision_type=dtype,
        expected_value=0.12,
        confidence=0.8,
        risk=0.3,
        reason="test",
        audit_id=f"dec_{game_id}_{opp_type}",
    )


def _prior(rev=0.12, roas=0.10, conf=0.80, risk=0.30,
           opp_type="creative_refresh") -> SimulationPrior:
    return SimulationPrior(
        opportunity_type=opp_type,
        expected_revenue_change=rev,
        expected_roas_change=roas,
        confidence=conf,
        risk=risk,
    )


def test_deterministic_reproducible_to_1e6():
    """同种子两次模拟逐字段一致（跨运行可复现）。"""
    a = DeterministicSimulator().simulate_decision(_decision(), _prior())
    b = DeterministicSimulator().simulate_decision(_decision(), _prior())
    assert a.to_dict() == b.to_dict()
    base_a = a.outcome("baseline")
    base_b = b.outcome("baseline")
    assert abs(base_a.revenue.p50 - base_b.revenue.p50) < TOL


def test_different_seed_changes_samples():
    a = DeterministicSimulator(seed=1).simulate_decision(_decision(), _prior())
    b = DeterministicSimulator(seed=2).simulate_decision(_decision(), _prior())
    assert abs(
        a.outcome("baseline").revenue.p10 - b.outcome("baseline").revenue.p10
    ) > 0.0


def test_distribution_shape_and_center():
    """p10 <= p50 <= p90；对称三角分布 p50 贴近先验均值。"""
    sim = DeterministicSimulator().simulate_decision(_decision(), _prior())
    for scenario_id in ("baseline", "optimistic", "pessimistic"):
        o = sim.outcome(scenario_id)
        assert o.revenue.p10 <= o.revenue.p50 <= o.revenue.p90
        assert o.roas.p10 <= o.roas.p50 <= o.roas.p90
    base = sim.outcome("baseline")
    assert abs(base.revenue.p50 - 0.12) < 0.01
    assert abs(base.revenue.mean - 0.12) < 0.01
    assert abs(base.roas.p50 - 0.10) < 0.01


def test_risk_widens_distribution():
    """风险越高，p90-p10 区间越宽。"""
    engine = DeterministicSimulator()
    low = engine.simulate_decision(_decision(), _prior(risk=0.15))
    high = engine.simulate_decision(_decision(), _prior(risk=0.60))
    lo = low.outcome("baseline").revenue
    hi = high.outcome("baseline").revenue
    assert (hi.p90 - hi.p10) > (lo.p90 - lo.p10)


def test_scenario_multipliers_shift_center():
    """乐观情景收入 p50 高于基线，悲观低于基线。"""
    sim = DeterministicSimulator().simulate_decision(_decision(), _prior())
    base = sim.outcome("baseline").revenue.p50
    assert sim.outcome("optimistic").revenue.p50 > base
    assert sim.outcome("pessimistic").revenue.p50 < base


def test_pre_flight_pass():
    sim = DeterministicSimulator().simulate_decision(_decision(), _prior())
    assert sim.flag.status == PreFlightStatus.PASS


def test_pre_flight_block_on_negative_expectation():
    sim = DeterministicSimulator().simulate_decision(
        _decision(), _prior(rev=-0.24)
    )
    assert sim.flag.status == PreFlightStatus.BLOCK
    assert "负期望" in sim.flag.reason


def test_pre_flight_review_on_high_risk():
    sim = DeterministicSimulator().simulate_decision(
        _decision(), _prior(risk=0.70)
    )
    assert sim.flag.status == PreFlightStatus.REVIEW
    assert "高风险" in sim.flag.reason


def test_pre_flight_review_on_low_confidence():
    sim = DeterministicSimulator().simulate_decision(
        _decision(), _prior(conf=0.40)
    )
    assert sim.flag.status == PreFlightStatus.REVIEW
    assert "低置信" in sim.flag.reason


def test_portfolio_excludes_blocked():
    """组合分布不计 BLOCK 决策：受污染决策剔除后组合 p50 回正。"""
    engine = DeterministicSimulator()
    good = engine.simulate_decision(
        _decision("game_a", "creative_refresh"), _prior()
    )
    bad = engine.simulate_decision(
        _decision("game_b", "revenue_recovery"),
        _prior(rev=-0.30, opp_type="revenue_recovery"),
    )
    assert bad.flag.status == PreFlightStatus.BLOCK
    portfolio = engine.simulate_portfolio([good, bad])
    assert portfolio["baseline"].p50 > 0.0
    # 只剩 good 一条 → 组合 p50 与 good 自身 p50 一致
    assert abs(
        portfolio["baseline"].p50 - good.outcome("baseline").revenue.p50
    ) < TOL


def test_portfolio_empty_when_all_blocked():
    engine = DeterministicSimulator()
    bad = engine.simulate_decision(_decision(), _prior(rev=-0.30))
    portfolio = engine.simulate_portfolio([bad])
    assert abs(portfolio["baseline"].p50 - 0.0) < TOL


def test_counterfactual_comparison():
    sim = DeterministicSimulator().simulate_decision(_decision(), _prior())
    cmp = DeterministicSimulator.compare_counterfactual(
        sim, "optimistic", "pessimistic"
    )
    assert cmp.winner == "optimistic"
    assert cmp.revenue_p50_delta > 0.0
    expected = (
        sim.outcome("optimistic").revenue.p50
        - sim.outcome("pessimistic").revenue.p50
    )
    assert abs(cmp.revenue_p50_delta - round(expected, 6)) < TOL
