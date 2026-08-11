"""E15.1.2 — OpportunityPredictor (CPI / D30 / D90 ROAS forecast)."""
from operation.factory_brain import MarketOpportunity, OpportunityPredictor
from operation.factory_brain.opportunity_predictor import BASE_CPI

from tests.e15_1_2.brainhelpers import opportunity


def _pred(**kw):
    return OpportunityPredictor().predict(opportunity(**kw))


def test_predict_returns_roasprediction_with_ids():
    op = opportunity(oid="oX")
    p = OpportunityPredictor().predict(op)
    assert p.opportunity_id == "oX"
    assert p.cpi > 0 and p.d30_roas >= 0 and p.d90_roas >= 0


def test_deterministic_same_input_same_output():
    a = _pred(oid="o1", score_hint=0.7)
    b = _pred(oid="o1", score_hint=0.7)
    assert a.to_dict() == b.to_dict()


def test_competition_raises_cpi():
    low = OpportunityPredictor().predict(
        MarketOpportunity("o", "merge", competition=0.1, keyword_trend=0.5))
    high = OpportunityPredictor().predict(
        MarketOpportunity("o", "merge", competition=0.9, keyword_trend=0.5))
    assert high.cpi > low.cpi


def test_keyword_trend_lowers_cpi():
    cold = OpportunityPredictor().predict(
        MarketOpportunity("o", "merge", keyword_trend=0.1, competition=0.5))
    hot = OpportunityPredictor().predict(
        MarketOpportunity("o", "merge", keyword_trend=0.9, competition=0.5))
    assert hot.cpi < cold.cpi


def test_cpi_bounded():
    p = OpportunityPredictor().predict(
        MarketOpportunity("o", "merge", competition=1.0, keyword_trend=0.0))
    assert 0.30 <= p.cpi <= 4.00


def test_strong_monetization_gives_higher_roas():
    weak = _pred(ecpm_signal=0.1, ltv_forecast=0.1)
    strong = _pred(ecpm_signal=0.9, ltv_forecast=0.9)
    assert strong.d30_roas > weak.d30_roas
    assert strong.d90_roas > weak.d90_roas


def test_d90_matures_over_d30():
    p = _pred(score_hint=0.7)
    assert p.d90_roas >= p.d30_roas


def test_payback_ok_flag_matches_d90():
    p = _pred(ecpm_signal=0.95, ltv_forecast=0.95, keyword_trend=0.9,
              competition=0.1)
    assert p.payback_ok == (p.d90_roas >= 1.0)


def test_confidence_tracks_score_and_completeness():
    full = _pred(score_hint=0.8)
    sparse = OpportunityPredictor().predict(
        MarketOpportunity("o", "merge", keyword_trend=0.8))  # only 1 filled
    # a fully-specified strong opp should be at least as confident
    assert full.confidence >= sparse.confidence
    assert 0.0 <= full.confidence <= 1.0


def test_predict_batch_length_and_order():
    ops = [opportunity(oid="a"), opportunity(oid="b"),
           opportunity(oid="c")]
    preds = OpportunityPredictor().predict_batch(ops)
    assert [p.opportunity_id for p in preds] == ["a", "b", "c"]


def test_base_cpi_constant_is_reasonable():
    assert 0.5 <= BASE_CPI <= 3.0
