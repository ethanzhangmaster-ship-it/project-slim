from tests.revenue_optimizer.ro_helpers import (report, zombie_sig, winner_sig, floor_sig, sig,
                       diversify_sig)
from operation.revenue_optimizer.opportunity.detector import OpportunityDetector
from operation.revenue_optimizer.opportunity.scorer import OpportunityScorer
from operation.revenue_optimizer.opportunity.ranking import OpportunityRanker


def test_detector_finds_zombie():
    opps = OpportunityDetector().detect(report(signals=[zombie_sig()]))
    assert any(o.action == "disable_network" for o in opps)


def test_detector_finds_hidden_winner():
    opps = OpportunityDetector().detect(report(signals=[winner_sig()]))
    assert any(o.action == "increase_bid_opportunity" for o in opps)


def test_detector_finds_bid_floor():
    opps = OpportunityDetector().detect(report(signals=[floor_sig()]))
    assert any(o.action == "adjust_bid_constraint" for o in opps)


def test_detector_skips_non_eligible():
    # geo_opportunity with a non-A/B action is not an optimization opportunity
    opps = OpportunityDetector().detect(
        report(signals=[sig("geo_opportunity", "US", "review_segment")]))
    assert opps == []


def test_scorer_higher_lift_higher_score():
    s = OpportunityScorer()
    a = type("O", (), {"expected_lift": 0.2, "confidence": 0.9, "risk": 0.1})()
    b = type("O", (), {"expected_lift": 0.05, "confidence": 0.9, "risk": 0.1})()
    assert s.score(a) > s.score(b)


def test_scorer_risk_reduces_score():
    s = OpportunityScorer()
    a = type("O", (), {"expected_lift": 0.1, "confidence": 0.9, "risk": 0.1})()
    b = type("O", (), {"expected_lift": 0.1, "confidence": 0.9, "risk": 0.9})()
    assert s.score(a) > s.score(b)


def test_ranker_sorts_by_score():
    ranked = OpportunityRanker().rank([
        type("O", (), {"expected_lift": 0.01, "confidence": 0.9, "risk": 0.1})(),
        type("O", (), {"expected_lift": 0.2, "confidence": 0.9, "risk": 0.1})(),
    ])
    assert ranked[0][1] > ranked[1][1]


def test_ranker_top_n_caps():
    opps = [type("O", (), {"expected_lift": 0.1 * i, "confidence": 0.9,
                           "risk": 0.1})() for i in range(5)]
    ranked = OpportunityRanker().rank(opps, top_n=2)
    assert len(ranked) == 2


def test_detector_sorts_by_expected_lift():
    opps = OpportunityDetector().detect(
        report(signals=[zombie_sig(), winner_sig()]))
    if len(opps) >= 2:
        assert opps[0].expected_lift >= opps[1].expected_lift


def test_opportunity_fields_populated():
    opps = OpportunityDetector().detect(report(signals=[winner_sig()]))
    o = opps[0]
    assert 0 < o.expected_lift < 1
    assert o.confidence == 0.85
    assert o.risk == 0.15
