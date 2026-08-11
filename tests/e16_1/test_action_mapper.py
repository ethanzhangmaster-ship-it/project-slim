"""Action Mapper tests — covers the doc's Test5 (high ROAS -> INCREASE_UA_BUDGET).

Test5: high ROAS channel -> INCREASE_UA_BUDGET
"""
from src.revenue_intelligence.action_mapper import ActionMapper
from src.revenue_intelligence.analyzer import RevenueDeltaEngine
from src.revenue_intelligence.attribution import RevenueAttributionEngine
from src.revenue_intelligence.insight_engine import InsightEngine
from src.revenue_intelligence.models import RevenueAction
from tests.e16_1.fixtures import high_roas_pair


def _ctx(prev, cur):
    d = RevenueDeltaEngine().compare(cur, prev)
    a = RevenueAttributionEngine().analyze(cur, prev, d)
    ins = InsightEngine().generate(cur, prev, d, a)
    return d, ins


def test5_high_roas_increases_ua_budget():
    prev, cur = high_roas_pair()
    d, ins = _ctx(prev, cur)
    actions = ActionMapper().map(cur, prev, d, ins)
    assert actions, "expected at least one recommended action"
    assert any(a.action == RevenueAction.INCREASE_UA_BUDGET for a in actions)
    inc = next(a for a in actions if a.action == RevenueAction.INCREASE_UA_BUDGET)
    assert inc.confidence > 0
    assert inc.impact_score > 0


def test_decline_without_version_triggers_retention_investigation():
    from tests.e16_1.fixtures import decline_pair

    prev, cur = decline_pair()
    d, ins = _ctx(prev, cur)
    actions = ActionMapper().map(cur, prev, d, ins)
    assert any(a.action == RevenueAction.INVESTIGATE_RETENTION for a in actions)


def test_actions_are_deduplicated():
    prev, cur = high_roas_pair()
    d, ins = _ctx(prev, cur)
    actions = ActionMapper().map(cur, prev, d, ins)
    seen = {a.action for a in actions}
    assert len(seen) == len(actions), "duplicate actions were not de-duplicated"


def test_pattern_recommendation_becomes_action():
    from src.revenue_intelligence.models import PatternMatch

    prev, cur = high_roas_pair()
    d, ins = _ctx(prev, cur)
    patterns = [
        PatternMatch(
            pattern_id="pat1",
            description="Past scale worked",
            confidence=0.9,
            similar_case="case_a",
            recommended_action=RevenueAction.SCALE_FEATURE,
        )
    ]
    actions = ActionMapper().map(cur, prev, d, ins, patterns)
    assert any(a.action == RevenueAction.SCALE_FEATURE for a in actions)
