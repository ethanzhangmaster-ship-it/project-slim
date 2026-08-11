"""Insight Engine tests — covers the doc's Test1 / Test2 / Test3.

Test1: revenue growth 10000->12000, ROAS 1.2->1.5  -> REVENUE_GROWTH
Test2: revenue decline 10000->7000, retention down  -> RETENTION_CHANGE
Test3: Spend +50%, Revenue +80%                    -> UA_EFFICIENCY
"""
from src.revenue_intelligence.analyzer import RevenueDeltaEngine
from src.revenue_intelligence.attribution import RevenueAttributionEngine
from src.revenue_intelligence.insight_engine import InsightEngine
from src.revenue_intelligence.models import InsightType
from tests.e16_1.fixtures import growth_pair, decline_pair, ua_pair


def _insights(prev, cur):
    d = RevenueDeltaEngine().compare(cur, prev)
    a = RevenueAttributionEngine().analyze(cur, prev, d)
    return InsightEngine().generate(cur, prev, d, a)


def test1_revenue_growth():
    prev, cur = growth_pair()
    ins = _insights(prev, cur)
    types = {i.insight_type for i in ins}
    assert InsightType.REVENUE_GROWTH in types
    growth = next(i for i in ins if i.insight_type == InsightType.REVENUE_GROWTH)
    assert growth.confidence > 0
    assert growth.impact_score > 0


def test2_retention_change():
    prev, cur = decline_pair()
    ins = _insights(prev, cur)
    types = {i.insight_type for i in ins}
    assert InsightType.REVENUE_DECLINE in types
    assert InsightType.RETENTION_CHANGE in types
    ret = next(i for i in ins if i.insight_type == InsightType.RETENTION_CHANGE)
    assert "D7" in ret.description or "retention" in ret.description.lower()


def test3_ua_efficiency():
    prev, cur = ua_pair()
    ins = _insights(prev, cur)
    types = {i.insight_type for i in ins}
    assert InsightType.UA_EFFICIENCY in types
    ua = next(i for i in ins if i.insight_type == InsightType.UA_EFFICIENCY)
    assert "efficient" in ua.description.lower()


def test_version_impact_detected():
    from tests.e16_1.fixtures import snap

    prev = snap(date="P0", revenue_total=10000, version="1.0.0")
    cur = snap(date="P1", revenue_total=11000, version="1.1.0")
    ins = _insights(prev, cur)
    assert InsightType.VERSION_IMPACT in {i.insight_type for i in ins}
