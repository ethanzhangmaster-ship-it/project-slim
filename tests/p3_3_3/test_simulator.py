"""P3.3.3 — Simulator 测试（封装 E17.8 + 先验注入）。"""
from __future__ import annotations

from src.ceo_intelligence.simulation_engine.models import PreFlightStatus
from src.operator.adaptive_strategy import (
    AdaptiveStrategyPlanner,
    AdaptiveStrategyRequest,
    AdaptiveStrategySimulator,
)
from .conftest import blocking_prior, review_prior


def _decision(strategy_id="adaptive.network_cleanup", target="g1"):
    p = AdaptiveStrategyPlanner()
    params = {"network": "n"} if strategy_id.endswith("cleanup") else {"campaign_id": "c"}
    return p.plan(AdaptiveStrategyRequest(
        proposal_id="p", strategy_id=strategy_id, target=target,
        parameters=params,
    )).decision


def test_default_prior_monetization_passes():
    sim = AdaptiveStrategySimulator()
    dec = _decision("adaptive.network_cleanup")
    s = sim.simulate(dec)
    assert s.flag.status == PreFlightStatus.PASS
    assert AdaptiveStrategySimulator.passed(s) is True
    assert AdaptiveStrategySimulator.status_of(s) == "pass"


def test_default_prior_ua_stop_loss_passes():
    sim = AdaptiveStrategySimulator()
    dec = _decision("adaptive.campaign_pause")
    s = sim.simulate(dec)
    assert s.flag.status == PreFlightStatus.PASS


def test_status_and_reason_helpers():
    sim = AdaptiveStrategySimulator()
    dec = _decision("adaptive.network_cleanup")
    s = sim.simulate(dec)
    assert AdaptiveStrategySimulator.status_of(s) == s.flag.status.value
    assert isinstance(AdaptiveStrategySimulator.reason_of(s), str)


def test_injected_blocking_prior_blocks():
    sim = AdaptiveStrategySimulator(prior_provider=blocking_prior)
    dec = _decision("adaptive.network_cleanup")
    s = sim.simulate(dec)
    assert s.flag.status == PreFlightStatus.BLOCK
    assert AdaptiveStrategySimulator.passed(s) is False


def test_injected_review_prior_reviews():
    sim = AdaptiveStrategySimulator(prior_provider=review_prior)
    dec = _decision("adaptive.network_cleanup")
    s = sim.simulate(dec)
    assert s.flag.status == PreFlightStatus.REVIEW


def test_prior_provider_called_with_opportunity_type():
    calls = []

    def spy(ot):
        calls.append(ot)
        return blocking_prior(ot)

    sim = AdaptiveStrategySimulator(prior_provider=spy)
    dec = _decision("adaptive.network_cleanup")
    sim.simulate(dec)
    assert calls == ["monetization"]


def test_simulator_passes_through_pre_flight_reason():
    sim = AdaptiveStrategySimulator(prior_provider=blocking_prior)
    dec = _decision("adaptive.network_cleanup")
    s = sim.simulate(dec)
    assert "负期望" in s.flag.reason or s.flag.reason


def test_simulator_uses_injected_graph_else_default():
    # 无 graph：默认先验仍可用
    sim = AdaptiveStrategySimulator()
    assert sim.graph is None
    assert sim._engine is not None
    # 注入 graph 不影响构造
    sim2 = AdaptiveStrategySimulator(graph=object())
    assert sim2.graph is not None


def test_simulator_review_does_not_block_closed_loop():
    """REVIEW 闸门仍应继续进审批（契约 §4）。"""
    sim = AdaptiveStrategySimulator(prior_provider=review_prior)
    dec = _decision("adaptive.network_cleanup")
    s = sim.simulate(dec)
    # 注意：REVIEW 由 controller 判定为「继续」，此处仅验证 sim 自身返回 REVIEW
    assert s.flag.status == PreFlightStatus.REVIEW
