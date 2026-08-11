"""Value Prediction tests — separate from User Segment (spec requires 15 each)."""
from tests.player_monetization.pm_helpers import (
    profile, high_value_profile, casual_profile, new_profile,
    power_profile, churn_profile,
)
from operation.player_monetization.user_profile.value_predictor import ValuePredictor
from operation.player_monetization.user_profile.player_segment import PlayerSegmenter

def _pred(p):
    seg = PlayerSegmenter().classify(p)
    return ValuePredictor().predict(p, seg)


def test_pred_us_higher_than_in():
    us = _pred(profile("u1", "US"))
    ind = _pred(profile("u2", "IN"))
    assert us.predicted_30d_iaa > ind.predicted_30d_iaa


def test_pred_high_value_highest():
    hv = _pred(high_value_profile())
    ca = _pred(casual_profile())
    assert hv.predicted_ltv > ca.predicted_ltv


def test_pred_churn_lowest():
    ch = _pred(churn_profile())
    ca = _pred(casual_profile())
    assert ch.predicted_30d_iaa < ca.predicted_30d_iaa


def test_pred_new_low():
    n = _pred(new_profile())
    assert n.predicted_ltv < 5.0


def test_pred_confidence_range():
    for p in [high_value_profile(), casual_profile(), new_profile(), churn_profile()]:
        c = _pred(p).confidence
        assert 0.3 <= c <= 0.95


def test_pred_has_features():
    vp = _pred(high_value_profile())
    assert "daily_rev" in vp.features
    assert "churn_rate" in vp.features


def test_pred_30d_positive():
    vp = _pred(high_value_profile())
    assert vp.predicted_30d_iaa > 0


def test_pred_ltv_positive():
    vp = _pred(profile())
    assert vp.predicted_ltv > 0


def test_pred_segment_preserved():
    vp = _pred(high_value_profile())
    assert vp.segment == "high_value_ad_player"


def test_pred_country_mult_GB():
    gb = _pred(profile("u", "GB"))
    ind = _pred(profile("u", "IN"))
    assert gb.predicted_30d_iaa > ind.predicted_30d_iaa


def test_pred_power_user_moderate():
    pw = _pred(power_profile())
    assert pw.predicted_ltv > 0


def test_pred_to_dict():
    d = _pred(profile()).to_dict()
    assert "predicted_30d_IAA" in d
    assert "predicted_LTV" in d


def test_pred_daily_rev_computed():
    vp = _pred(profile())
    assert vp.features["daily_rev"] > 0


def test_pred_churn_rate_in_range():
    vp = _pred(churn_profile())
    assert 0 < vp.features["churn_rate"] < 1


def test_pred_moderate_default():
    p = profile(sessions=5, ad_rev=0.15, ad_show=8, ad_req=20, reward_show=5, reward_req=15)
    vp = _pred(p)
    assert vp.segment == "moderate_ad_player"
