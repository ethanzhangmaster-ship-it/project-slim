"""P3.3 — StrategyMutationEngine 测试（产出建议，不执行）。"""
from __future__ import annotations

from src.operator.strategy.memory import StrategyMemoryAdapter
from src.operator.strategy.models import (
    StrategyInsight,
    StrategyState,
    StrategyStatus,
)
from src.operator.strategy.mutation import StrategyMutationEngine
from .conftest import make_feedback


def _engine():
    return StrategyMutationEngine()


def _state(strategy_id, **kw):
    perf = kw.pop("performance", {})
    st = StrategyState(strategy_id=strategy_id, dimension="ua",
                       parameters=kw.get("parameters", {}),
                       confidence=kw.get("confidence", 0.5),
                       status=kw.get("status", StrategyStatus.ACTIVE))
    st.performance.update(perf)
    # 补齐 samples（覆盖 __post_init__ 的默认值 0），与 wins/losses 保持一致
    w = int(st.performance.get("wins", 0))
    l = int(st.performance.get("losses", 0))
    st.performance["samples"] = w + l
    return st


def _insight(strategy_id, rate, samples, rec):
    return StrategyInsight(strategy_id, "ua", rate, samples, 0.0, rec, "r")


def test_underperforming_aggressive_scale_proposes_mutation():
    eng = _engine()
    states = {"aggressive_scale": _state("aggressive_scale",
                                         parameters={"budget_growth": 0.30},
                                         performance={"wins": 8, "losses": 22})}
    insights = [_insight("aggressive_scale", 0.26, 30, "reduce")]
    props = eng.propose(states, insights)
    assert len(props) == 1
    p = props[0]
    assert "conservative_scale" in p.proposed_change
    assert "budget_growth" in p.proposed_change


def test_proposal_requires_simulation_true():
    eng = _engine()
    states = {"aggressive_scale": _state("aggressive_scale",
                                         performance={"wins": 1, "losses": 9})}
    insights = [_insight("aggressive_scale", 0.1, 10, "reduce")]
    props = eng.propose(states, insights)
    assert all(p.requires_simulation for p in props)


def test_no_mutation_for_unknown_strategy():
    eng = _engine()
    states = {"mystery_strategy": _state("mystery_strategy",
                                        performance={"wins": 0, "losses": 20})}
    insights = [_insight("mystery_strategy", 0.0, 20, "reduce")]
    assert eng.propose(states, insights) == []


def test_disabled_strategy_with_variant_triggers():
    eng = _engine()
    states = {"aggressive_scale": _state("aggressive_scale", status=StrategyStatus.DISABLED,
                                         performance={"wins": 1, "losses": 9})}
    insights = [_insight("aggressive_scale", 0.1, 10, "disable")]
    props = eng.propose(states, insights)
    assert len(props) == 1


def test_consecutive_failures_trigger():
    eng = _engine()
    states = {"aggressive_scale": _state("aggressive_scale",
                                         performance={"consecutive_failures": 3,
                                                      "wins": 2, "losses": 8})}
    insights = [_insight("aggressive_scale", 0.2, 10, "hold")]
    props = eng.propose(states, insights)
    assert len(props) == 1


def test_no_trigger_when_healthy():
    eng = _engine()
    states = {"aggressive_scale": _state("aggressive_scale",
                                         performance={"wins": 20, "losses": 2})}
    insights = [_insight("aggressive_scale", 0.9, 22, "boost")]
    assert eng.propose(states, insights) == []


def test_proposal_confidence_bounded():
    eng = _engine()
    states = {"aggressive_scale": _state("aggressive_scale",
                                         performance={"wins": 1, "losses": 9})}
    insights = [_insight("aggressive_scale", 0.1, 200, "reduce")]
    props = eng.propose(states, insights)
    assert 0.0 <= props[0].confidence <= 0.9


def test_adapter_driven_mutation_flow(tmp_store):
    # 端到端用 adapter 产 states/insights，再交给 mutation
    a = StrategyMemoryAdapter(store_path=tmp_store)
    for _ in range(8):
        a.apply_feedback(make_feedback("aggressive_scale", "FAILURE", -0.4))
    insights = a.build_insights(graph=None)
    props = StrategyMutationEngine().propose(a.all_states(), insights)
    # 8 次连续失败 → DISABLED → 触发以更稳妥变体重启
    assert len(props) == 1
    assert props[0].requires_simulation is True
