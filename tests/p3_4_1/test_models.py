"""P3.4.1 — models.py 单元测试。"""

import json

from src.operator.portfolio.models import (
    ExecutionSource,
    GamePortfolioSnapshot,
    LifecycleSource,
    PortfolioSignal,
    PortfolioSnapshot,
    RecoverySource,
    StrategySource,
)

EPS = 1e-6


def test_game_snapshot_defaults_all_none_except_game_id_and_metadata():
    s = GamePortfolioSnapshot(game_id="g1")
    assert s.game_id == "g1"
    assert s.revenue is None
    assert s.spend is None
    assert s.roas is None
    assert s.confidence is None
    assert s.coverage is None
    assert s.strategy_score is None
    assert s.strategy_success_rate is None
    assert s.active_strategy_count == 0
    assert s.execution_health is None
    assert s.failure_rate is None
    assert s.recovery_rate is None
    assert s.lifecycle_stage is None
    assert s.data_freshness is None
    assert s.metadata == {}


def test_game_snapshot_roundtrip_preserves_none_and_values():
    s = GamePortfolioSnapshot(
        game_id="g2",
        revenue=100.0,
        spend=50.0,
        roas=1.5,
        confidence=0.8,
        coverage=0.4,
        strategy_score=0.7,
        strategy_success_rate=0.7,
        active_strategy_count=3,
        execution_health=0.9,
        failure_rate=0.1,
        recovery_rate=0.85,
        lifecycle_stage="scale",
        data_freshness=0.95,
        metadata={"k": "v"},
    )
    d = s.to_dict()
    s2 = GamePortfolioSnapshot.from_dict(d)
    assert s2.game_id == "g2"
    assert s2.revenue == 100.0
    assert s2.roas == 1.5
    assert s2.confidence == 0.8
    assert s2.coverage == 0.4
    assert s2.strategy_score == 0.7
    assert s2.active_strategy_count == 3
    assert s2.execution_health == 0.9
    assert s2.recovery_rate == 0.85
    assert s2.lifecycle_stage == "scale"
    assert s2.data_freshness == 0.95
    assert s2.metadata == {"k": "v"}
    # 关键：None 必须保持 None，不能与 0.0 混淆
    assert s2.spend == 50.0


def test_has_reality_flag():
    assert GamePortfolioSnapshot(game_id="a", revenue=1.0).has_reality is True
    assert GamePortfolioSnapshot(game_id="a", spend=1.0).has_reality is True
    assert GamePortfolioSnapshot(game_id="a", roas=1.0).has_reality is True
    assert GamePortfolioSnapshot(game_id="a").has_reality is False


def test_has_strategy_flag():
    assert GamePortfolioSnapshot(game_id="a", strategy_success_rate=0.5).has_strategy is True
    assert GamePortfolioSnapshot(game_id="a").has_strategy is False


def test_has_execution_recovery_lifecycle_flags():
    assert GamePortfolioSnapshot(game_id="a", execution_health=0.5).has_execution is True
    assert GamePortfolioSnapshot(game_id="a", recovery_rate=0.5).has_recovery is True
    assert GamePortfolioSnapshot(game_id="a", lifecycle_stage="scale").has_lifecycle is True
    assert GamePortfolioSnapshot(game_id="a").has_execution is False
    assert GamePortfolioSnapshot(game_id="a").has_recovery is False
    assert GamePortfolioSnapshot(game_id="a").has_lifecycle is False


def test_is_known():
    assert GamePortfolioSnapshot(game_id="a", confidence=0.3).is_known is True
    assert GamePortfolioSnapshot(game_id="a", revenue=1.0).is_known is True
    assert GamePortfolioSnapshot(game_id="a").is_known is False


def test_to_signals_only_non_none():
    s = GamePortfolioSnapshot(
        game_id="g",
        revenue=100.0,
        confidence=0.8,
        lifecycle_stage="scale",  # 字符串，不应进 signals
    )
    sigs = s.to_signals(timestamp="t")
    sources = {sig.source for sig in sigs}
    assert sources == {"revenue", "confidence"}
    for sig in sigs:
        assert sig.timestamp == "t"
        assert sig.confidence == 1.0


def test_to_signals_skips_none_values():
    s = GamePortfolioSnapshot(game_id="g", roas=None, spend=None)
    assert s.to_signals() == []


def test_portfolio_snapshot_aggregation():
    g1 = GamePortfolioSnapshot(game_id="a", revenue=100.0, spend=40.0, coverage=0.4)
    g2 = GamePortfolioSnapshot(game_id="b", revenue=50.0, spend=10.0, coverage=0.6)
    ps = PortfolioSnapshot(
        generated_at="T",
        games=[g1, g2],
        total_revenue=g1.revenue + g2.revenue,
        total_spend=g1.spend + g2.spend,
        coverage=(g1.coverage + g2.coverage) / 2,
    )
    assert ps.total_revenue == 150.0
    assert ps.total_spend == 50.0
    assert abs(ps.coverage - 0.5) < EPS
    assert ps.game_ids == ["a", "b"]
    assert ps.count == 2


def test_portfolio_snapshot_get():
    g1 = GamePortfolioSnapshot(game_id="a")
    g2 = GamePortfolioSnapshot(game_id="b")
    ps = PortfolioSnapshot(generated_at="T", games=[g1, g2])
    assert ps.get("b") is g2
    assert ps.get("z") is None


def test_portfolio_snapshot_roundtrip():
    g1 = GamePortfolioSnapshot(game_id="a", revenue=100.0, coverage=0.4)
    ps = PortfolioSnapshot(generated_at="T", games=[g1], total_revenue=100.0, total_spend=0.0, coverage=0.4)
    d = ps.to_dict()
    ps2 = PortfolioSnapshot.from_dict(d)
    assert ps2.generated_at == "T"
    assert ps2.count == 1
    assert ps2.games[0].game_id == "a"
    assert ps2.total_revenue == 100.0
    assert ps2.coverage == 0.4


def test_portfolio_signal_roundtrip():
    sig = PortfolioSignal(source="roas", value=1.5, confidence=0.9, timestamp="t")
    d = sig.to_dict()
    assert d["source"] == "roas"
    assert d["value"] == 1.5
    sig2 = PortfolioSignal.from_dict(d)
    assert sig2.source == "roas"
    assert sig2.value == 1.5
    assert sig2.confidence == 0.9
    assert sig2.timestamp == "t"


def test_strategy_execution_recovery_lifecycle_source_defaults():
    assert StrategySource().strategy_score is None
    assert StrategySource().active_strategy_count == 0
    assert ExecutionSource().execution_health is None
    assert RecoverySource().recovery_rate is None
    assert LifecycleSource().lifecycle_stage is None
    assert LifecycleSource().data_freshness is None


def test_coverage_none_when_no_domains():
    # domain_coverage()==0 → coverage None（assembler 行为，这里验证模型接受 None）
    s = GamePortfolioSnapshot(game_id="g", coverage=None)
    assert s.coverage is None


def test_json_dump_load_roundtrip():
    g = GamePortfolioSnapshot(game_id="g", revenue=12.3456789, roas=None)
    d = g.to_dict()
    text = json.dumps(d)
    d2 = json.loads(text)
    g2 = GamePortfolioSnapshot.from_dict(d2)
    # 6 位精度四舍五入
    assert abs(g2.revenue - 12.345679) < EPS
    assert g2.roas is None
