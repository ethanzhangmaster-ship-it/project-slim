"""E17.8 — 模型层：roundtrip 序列化 + 闸门辅助方法。"""
from src.ceo_intelligence.simulation_engine.models import (
    DEFAULT_SCENARIOS,
    CounterfactualComparison,
    DecisionSimulation,
    OutcomeDistribution,
    PortfolioSimulationReport,
    PreFlightFlag,
    PreFlightStatus,
    ScenarioOutcome,
    SimulationPrior,
    SimulationScenario,
)

TOL = 1e-6


def _sim(flag_status=PreFlightStatus.PASS, audit_id="dec_abc") -> DecisionSimulation:
    return DecisionSimulation(
        game_id="merge_witch",
        opportunity_id="merge_witch:creative_refresh",
        action="刷新创意素材（merge_witch）",
        decision_type="execute",
        prior=SimulationPrior(
            opportunity_type="creative_refresh",
            expected_revenue_change=0.12,
            expected_roas_change=0.10,
            confidence=0.80,
            risk=0.30,
        ),
        outcomes=[
            ScenarioOutcome(
                scenario_id="baseline",
                revenue=OutcomeDistribution(0.08, 0.12, 0.16, 0.12),
                roas=OutcomeDistribution(0.06, 0.10, 0.14, 0.10),
                confidence=0.80,
                risk=0.30,
            )
        ],
        flag=PreFlightFlag(flag_status, "test"),
        decision_audit_id=audit_id,
    )


def test_default_scenarios_shape():
    ids = [s.id for s in DEFAULT_SCENARIOS]
    assert ids == ["baseline", "optimistic", "pessimistic"]
    base = DEFAULT_SCENARIOS[0]
    assert abs(base.revenue_multiplier - 1.0) < TOL
    assert abs(base.risk_multiplier - 1.0) < TOL


def test_scenario_roundtrip():
    s = SimulationScenario("aggressive", "激进", 1.5, 1.2, 1.4)
    s2 = SimulationScenario.from_dict(s.to_dict())
    assert s2 == s


def test_prior_roundtrip():
    p = SimulationPrior(
        opportunity_type="ua_scale",
        expected_revenue_change=0.15,
        expected_roas_change=0.05,
        confidence=0.75,
        risk=0.35,
        memory_boost=0.12,
        avg_revenue_delta=0.08,
        samples=4,
        source="static+memory",
    )
    p2 = SimulationPrior.from_dict(p.to_dict())
    assert p2 == p


def test_decision_simulation_roundtrip_and_outcome_lookup():
    sim = _sim()
    sim2 = DecisionSimulation.from_dict(sim.to_dict())
    assert sim2.to_dict() == sim.to_dict()
    assert abs(sim2.outcome("baseline").revenue.p50 - 0.12) < TOL
    try:
        sim2.outcome("nonexistent")
        assert False, "expected KeyError"
    except KeyError:
        pass


def test_report_roundtrip_and_blocked_ids():
    report = PortfolioSimulationReport(
        created_at="2026-07-29",
        total_decisions=2,
        simulations=[
            _sim(PreFlightStatus.PASS, "dec_ok"),
            _sim(PreFlightStatus.BLOCK, "dec_bad"),
        ],
        portfolio={"baseline": OutcomeDistribution(0.05, 0.10, 0.15, 0.10)},
        comparisons=[
            CounterfactualComparison(
                game_id="merge_witch",
                opportunity_id="merge_witch:creative_refresh",
                scenario_a="optimistic",
                scenario_b="baseline",
                revenue_p50_delta=0.03,
                roas_p50_delta=0.015,
                winner="optimistic",
            )
        ],
        summary={"pass": 1, "block": 1, "real_api_called": False},
    )
    assert report.blocked_decision_ids() == ["dec_bad"]
    r2 = PortfolioSimulationReport.from_dict(report.to_dict())
    assert r2.to_dict() == report.to_dict()
    assert r2.summary["real_api_called"] is False


def test_report_markdown_contains_gate_and_portfolio():
    report = PortfolioSimulationReport(
        created_at="2026-07-29",
        total_decisions=1,
        simulations=[_sim()],
        portfolio={"baseline": OutcomeDistribution(0.05, 0.10, 0.15, 0.10)},
        summary={"pass": 1, "review": 0, "block": 0, "real_api_called": False},
    )
    md = report.to_markdown()
    assert "组合模拟报告" in md
    assert "merge_witch" in md
    assert "p50" in md
    assert "pass" in md
