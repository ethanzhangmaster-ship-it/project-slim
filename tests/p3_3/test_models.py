"""P3.3 — models 契约测试。"""
from __future__ import annotations

from src.operator.strategy.models import (
    BusinessOutcome,
    StrategyFeedback,
    StrategyInsight,
    StrategyLoopResult,
    StrategyProposal,
    StrategyState,
    StrategyStatus,
)


def test_strategy_status_values():
    assert StrategyStatus.ACTIVE.value == "active"
    assert StrategyStatus.LEARNING.value == "learning"
    assert StrategyStatus.DISABLED.value == "disabled"


def test_strategy_state_default_performance_keys():
    st = StrategyState(strategy_id="x", dimension="ua")
    for k in ("wins", "losses", "reward_sum", "samples",
              "consecutive_failures", "last_outcome"):
        assert k in st.performance


def test_strategy_state_roundtrip():
    st = StrategyState(
        strategy_id="network_cleanup", dimension="monetization",
        parameters={"target": "low_ecpm"}, confidence=0.73,
        status=StrategyStatus.DISABLED,
    )
    d = st.to_dict()
    assert d["status"] == "disabled"
    st2 = StrategyState.from_dict(d)
    assert st2.strategy_id == st.strategy_id
    assert st2.confidence == 0.73
    assert st2.status == StrategyStatus.DISABLED
    assert st2.parameters == {"target": "low_ecpm"}


def test_success_rate_property():
    st = StrategyState(strategy_id="x", dimension="ua",
                      performance={"wins": 8, "losses": 2})
    st.performance["samples"] = 10
    assert abs(st.success_rate - 0.8) < 1e-6


def test_success_rate_zero_when_no_samples():
    st = StrategyState(strategy_id="x", dimension="ua")
    assert st.success_rate == 0.0


def test_feedback_roundtrip():
    fb = StrategyFeedback("a1", "net", 0.82, "SUCCESS", "eCPM 2.1->4.8")
    d = fb.to_dict()
    assert d["reward"] == 0.82
    fb2 = StrategyFeedback.from_dict(d)
    assert fb2.outcome == "SUCCESS" and fb2.strategy_id == "net"


def test_proposal_default_requires_simulation_true():
    p = StrategyProposal("aggressive_scale", "switch conservative",
                         "lower variance", 0.5)
    assert p.requires_simulation is True


def test_proposal_roundtrip():
    p = StrategyProposal("a", "b", "c", 0.6, requires_simulation=False)
    p2 = StrategyProposal.from_dict(p.to_dict())
    assert p2.requires_simulation is False
    assert p2.confidence == 0.6


def test_insight_to_line_contains_strategy():
    ins = StrategyInsight("network_cleanup", "monetization", 0.87, 87,
                          0.42, "boost", "历史成功率高")
    line = ins.to_line()
    assert "network_cleanup" in line and "boost" in line


def test_insight_roundtrip():
    ins = StrategyInsight("x", "ua", 0.4, 5, -0.1, "reduce", "低成功")
    ins2 = StrategyInsight.from_dict(ins.to_dict())
    assert ins2.historical_success_rate == 0.4
    assert ins2.recommendation == "reduce"


def test_business_outcome_delta_ratio():
    bo = BusinessOutcome("ecpm", 2.1, 4.8)
    assert abs(bo.delta_ratio() - (2.7 / 2.1)) < 1e-6
    bo2 = BusinessOutcome("ecpm", 0.0, 5.0)
    assert bo2.delta_ratio() == 1.0


def test_loop_result_roundtrip():
    lr = StrategyLoopResult(
        insights=[StrategyInsight("x", "ua", 0.5, 4, 0.1, "hold", "t")],
        proposals=[StrategyProposal("x", "y", "z", 0.5)],
        states={"x": StrategyState("x", "ua")},
        feedbacks=[StrategyFeedback("a", "x", 1.0, "SUCCESS", "ok")],
        patterns=["line1"],
    )
    d = lr.to_dict()
    assert d["patterns"] == ["line1"]
    assert len(d["insights"]) == 1
    assert len(d["proposals"]) == 1
    assert "x" in d["states"]
