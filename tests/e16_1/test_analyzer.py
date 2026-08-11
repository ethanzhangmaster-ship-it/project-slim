"""Revenue Delta Engine tests."""
from src.revenue_intelligence.analyzer import RevenueDeltaEngine
from tests.e16_1.fixtures import growth_pair, decline_pair, ua_pair, high_roas_pair


def test_delta_growth_pct():
    prev, cur = growth_pair()
    d = RevenueDeltaEngine().compare(cur, prev)
    assert d.revenue_total_pct == 20.0
    assert d.revenue_total_abs == 2000.0
    assert d.roas_pct == 25.0  # 1.2 -> 1.5


def test_delta_decline_pct():
    prev, cur = decline_pair()
    d = RevenueDeltaEngine().compare(cur, prev)
    assert d.revenue_total_pct == -30.0
    assert d.revenue_total_abs == -3000.0
    assert d.retention_d7_pct == -25.0


def test_delta_ua_case():
    prev, cur = ua_pair()
    d = RevenueDeltaEngine().compare(cur, prev)
    assert d.revenue_total_pct == 80.0
    assert d.spend_pct == 50.0
    assert d.dau_pct == 50.0


def test_delta_zero_previous_is_none():
    from src.revenue_intelligence.models import RevenueSnapshot

    prev = RevenueSnapshot(game_id="g", date="P0", revenue_total=0.0)
    cur = RevenueSnapshot(game_id="g", date="P1", revenue_total=100.0)
    d = RevenueDeltaEngine().compare(cur, prev)
    # never divide by zero
    assert d.revenue_total_pct is None
    assert d.revenue_total_abs == 100.0


def test_delta_flat_spend_is_zero():
    prev, cur = high_roas_pair()
    d = RevenueDeltaEngine().compare(cur, prev)
    assert d.spend_pct == 0.0  # 5000 -> 5000
