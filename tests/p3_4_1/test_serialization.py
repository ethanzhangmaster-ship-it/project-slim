"""P3.4.1 — 序列化 / 反序列化完整性测试。"""

import json

from src.operator.portfolio.models import (
    GamePortfolioSnapshot,
    PortfolioSignal,
    PortfolioSnapshot,
)

EPS = 1e-6


def test_full_game_snapshot_json_roundtrip():
    g = GamePortfolioSnapshot(
        game_id="gX",
        revenue=99.1234567,
        spend=33.0,
        roas=2.0,
        confidence=0.65,
        coverage=0.8,
        strategy_score=0.5,
        strategy_success_rate=0.5,
        active_strategy_count=2,
        execution_health=0.77,
        failure_rate=0.23,
        recovery_rate=0.9,
        lifecycle_stage="ua_test",
        data_freshness=0.88,
        metadata={"src": ["reality", "graph"]},
    )
    text = json.dumps(g.to_dict())
    d = json.loads(text)
    g2 = GamePortfolioSnapshot.from_dict(d)
    assert g2.game_id == "gX"
    assert abs(g2.revenue - 99.123457) < EPS  # 6 位精度
    assert g2.spend == 33.0
    assert g2.roas == 2.0
    assert g2.confidence == 0.65
    assert g2.coverage == 0.8
    assert g2.strategy_score == 0.5
    assert g2.active_strategy_count == 2
    assert g2.execution_health == 0.77
    assert g2.failure_rate == 0.23
    assert g2.recovery_rate == 0.9
    assert g2.lifecycle_stage == "ua_test"
    assert g2.data_freshness == 0.88
    assert g2.metadata == {"src": ["reality", "graph"]}


def test_game_snapshot_from_dict_missing_keys_defaults():
    d = {"game_id": "gY"}  # 仅 game_id
    g = GamePortfolioSnapshot.from_dict(d)
    assert g.game_id == "gY"
    assert g.revenue is None
    assert g.confidence is None
    assert g.active_strategy_count == 0
    assert g.metadata == {}


def test_full_portfolio_snapshot_json_roundtrip():
    g1 = GamePortfolioSnapshot(game_id="a", revenue=10.0, coverage=0.4)
    g2 = GamePortfolioSnapshot(game_id="b", revenue=20.0, coverage=0.6)
    ps = PortfolioSnapshot(
        generated_at="2026-07-30T00:00:00Z",
        games=[g1, g2],
        total_revenue=30.0,
        total_spend=0.0,
        coverage=0.5,
    )
    text = json.dumps(ps.to_dict())
    ps2 = PortfolioSnapshot.from_dict(json.loads(text))
    assert ps2.generated_at == "2026-07-30T00:00:00Z"
    assert ps2.count == 2
    assert ps2.total_revenue == 30.0
    assert ps2.coverage == 0.5
    assert ps2.game_ids == ["a", "b"]


def test_signal_json_roundtrip():
    sig = PortfolioSignal(source="confidence", value=0.8, confidence=0.9, timestamp="t")
    text = json.dumps(sig.to_dict())
    sig2 = PortfolioSignal.from_dict(json.loads(text))
    assert sig2.source == "confidence"
    assert sig2.value == 0.8
    assert sig2.confidence == 0.9
    assert sig2.timestamp == "t"


def test_float_rounding_six_dp():
    g = GamePortfolioSnapshot(game_id="g", revenue=1.0 / 3.0)
    d = g.to_dict()
    # 1/3 四舍五入 6 位 = 0.333333
    assert abs(d["revenue"] - 0.333333) < EPS


def test_empty_games_portfolio_roundtrip():
    ps = PortfolioSnapshot(generated_at="T", games=[])
    d = ps.to_dict()
    ps2 = PortfolioSnapshot.from_dict(d)
    assert ps2.count == 0
    assert ps2.total_revenue == 0.0
    assert ps2.coverage == 0.0


def test_none_vs_zero_preserved():
    # 0.0 与 None 在序列化后必须区分
    g = GamePortfolioSnapshot(game_id="g", spend=0.0, roas=None)
    d = g.to_dict()
    assert d["spend"] == 0.0
    assert d["roas"] is None
    g2 = GamePortfolioSnapshot.from_dict(d)
    assert g2.spend == 0.0
    assert g2.roas is None


def test_nested_metadata_preserved():
    g = GamePortfolioSnapshot(game_id="g", metadata={"a": {"b": [1, 2, 3]}})
    g2 = GamePortfolioSnapshot.from_dict(g.to_dict())
    assert g2.metadata == {"a": {"b": [1, 2, 3]}}
