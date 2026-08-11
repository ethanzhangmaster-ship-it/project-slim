"""P3.3 — StrategyMemoryAdapter 测试（含 Case1 成功经验增强 / Case2 连续失败降权）。"""
from __future__ import annotations

import pytest

from src.operator.strategy.memory import DEFAULT_STRATEGIES, StrategyMemoryAdapter
from src.operator.strategy.models import StrategyStatus
from .conftest import make_feedback


def test_default_strategies_seeded(adapter):
    states = adapter.all_states()
    ids = set(states.keys())
    assert {"network_cleanup", "aggressive_scale", "conservative_scale",
            "creative_fatigue_guard"} <= ids


def test_load_empty_uses_defaults(tmp_store):
    a = StrategyMemoryAdapter(store_path=tmp_store)
    assert len(a.all_states()) == len(DEFAULT_STRATEGIES)


# ---- Case1：成功经验增强 ------------------------------------------------ #
def test_case1_ten_successes_boost_confidence(adapter):
    st = adapter.ensure("network_cleanup")
    start = st.confidence
    for _ in range(10):
        adapter.apply_feedback(make_feedback("network_cleanup", "SUCCESS", 0.9))
    end = adapter.all_states()["network_cleanup"].confidence
    assert end > start
    perf = adapter.all_states()["network_cleanup"].performance
    assert perf["wins"] == 10
    assert perf["consecutive_failures"] == 0


def test_success_increments_wins_and_resets_consec_fail():
    a = StrategyMemoryAdapter()
    a.apply_feedback(make_feedback("x", "FAILURE"))
    a.apply_feedback(make_feedback("x", "FAILURE"))
    assert a.all_states()["x"].performance["consecutive_failures"] == 2
    a.apply_feedback(make_feedback("x", "SUCCESS"))
    assert a.all_states()["x"].performance["consecutive_failures"] == 0


# ---- Case2：连续失败降权（≥5 → DISABLED） ------------------------------ #
def test_case2_five_consecutive_failures_disables(adapter):
    st = adapter.ensure("aggressive_scale")
    assert st.status == StrategyStatus.ACTIVE
    for _ in range(5):
        adapter.apply_feedback(make_feedback("aggressive_scale", "FAILURE", -0.5))
    st2 = adapter.all_states()["aggressive_scale"]
    assert st2.status == StrategyStatus.DISABLED
    assert st2.performance["consecutive_failures"] >= 5


def test_four_failures_not_disabled():
    a = StrategyMemoryAdapter()
    for _ in range(4):
        a.apply_feedback(make_feedback("aggressive_scale", "FAILURE"))
    assert a.all_states()["aggressive_scale"].status == StrategyStatus.ACTIVE


def test_failure_lowers_confidence():
    a = StrategyMemoryAdapter()
    st = a.ensure("x")
    start = st.confidence
    a.apply_feedback(make_feedback("x", "FAILURE", -0.5))
    assert a.all_states()["x"].confidence < start


# ---- 中性反馈不影响 confidence --------------------------------------- #
def test_neutral_no_confidence_change():
    a = StrategyMemoryAdapter()
    st = a.ensure("x")
    st.confidence = 0.5
    a.apply_feedback(make_feedback("x", "NEUTRAL", 0.0))
    assert a.all_states()["x"].confidence == 0.5


def test_neutral_counts_as_sample_not_win_loss():
    a = StrategyMemoryAdapter()
    a.apply_feedback(make_feedback("x", "NEUTRAL", 0.0))
    perf = a.all_states()["x"].performance
    assert perf["wins"] == 0 and perf["losses"] == 0


# ---- 持久化 ----------------------------------------------------------- #
def test_save_then_reload_persists(adapter, tmp_store):
    adapter.apply_feedback(make_feedback("network_cleanup", "SUCCESS", 0.9))
    saved_conf = adapter.all_states()["network_cleanup"].confidence
    adapter.save()
    a2 = StrategyMemoryAdapter(store_path=tmp_store)
    assert a2.all_states()["network_cleanup"].confidence == saved_conf


def test_ensure_creates_new_state():
    a = StrategyMemoryAdapter()
    st = a.ensure("brand_new_strategy", dimension="retention")
    assert st.strategy_id == "brand_new_strategy"
    assert st.dimension == "retention"


# ---- 读 E17.7 构建洞察 ------------------------------------------------ #
def test_build_insights_uses_graph_when_available(adapter, monkeypatch, fake_patterns):
    import src.operator.strategy.memory as mm
    monkeypatch.setattr(mm, "extract_patterns", lambda g: fake_patterns)
    insights = adapter.build_insights(graph=object())
    by = {i.strategy_id: i for i in insights}
    assert by["network_cleanup"].historical_success_rate == 0.87
    assert by["network_cleanup"].recommendation == "boost"
    assert by["aggressive_scale"].recommendation == "reduce"


def test_build_insights_falls_back_to_local(adapter):
    for _ in range(8):
        adapter.apply_feedback(make_feedback("network_cleanup", "SUCCESS", 0.9))
    for _ in range(2):
        adapter.apply_feedback(make_feedback("network_cleanup", "FAILURE", -0.3))
    insights = adapter.build_insights(graph=None)
    ins = [i for i in insights if i.strategy_id == "network_cleanup"][0]
    assert ins.samples == 10
    assert abs(ins.historical_success_rate - 0.8) < 1e-6


def test_build_insights_recommend_disable(adapter, monkeypatch, fake_patterns):
    import src.operator.strategy.memory as mm
    monkeypatch.setattr(mm, "extract_patterns", lambda g: fake_patterns)
    # 先停用 aggressive_scale
    for _ in range(5):
        adapter.apply_feedback(make_feedback("aggressive_scale", "FAILURE"))
    insights = adapter.build_insights(graph=object())
    ins = [i for i in insights if i.strategy_id == "aggressive_scale"][0]
    assert ins.recommendation == "disable"
