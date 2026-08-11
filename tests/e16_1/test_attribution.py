"""Revenue Attribution Engine tests."""
from src.revenue_intelligence.analyzer import RevenueDeltaEngine
from src.revenue_intelligence.attribution import RevenueAttributionEngine
from tests.e16_1.fixtures import growth_pair, decline_pair, ua_pair


def _run(prev, cur):
        d = RevenueDeltaEngine().compare(cur, prev)
        a = RevenueAttributionEngine().analyze(cur, prev, d)
        return d, a


def test_factors_sum_to_total_change():
    # Signed invariant: factors' contribution shares sum to ±100%
    # (negative when revenue fell, positive when it rose).
    for pair in (growth_pair(), decline_pair(), ua_pair()):
        _, attr = _run(*pair)
        s = sum(f.contribution_pct for f in attr.factors)
        assert abs(abs(s) - 100.0) < 1e-6, s
        s_abs = sum(f.absolute for f in attr.factors)
        assert abs(s_abs - attr.revenue_change_abs) < 1e-3, s_abs


def test_ua_dominant_in_ua_case():
    # Test3: Spend +50%, Revenue +80% -> UA is the largest driver
    _, attr = _run(*ua_pair())
    dom = attr.dominant()
    assert dom is not None
    assert dom.name == "ua"
    # UA share is the largest single factor
    ua = next(f for f in attr.factors if f.name == "ua")
    assert ua.contribution_pct > 50.0


def test_retention_decline_has_product_or_monetization_drag():
    _, attr = _run(*decline_pair())
    # total change is negative; at least one factor is a negative drag
    drags = [f for f in attr.factors if f.contribution_pct < 0]
    assert drags, "expected a negative driver for a revenue decline"
