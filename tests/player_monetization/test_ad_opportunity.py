from tests.player_monetization.pm_helpers import profile, segment, high_value_profile
from operation.player_monetization.ad_opportunity.opportunity_detector import (
    OpportunityDetector, RewardPredictor, InterstitialPredictor,
)

def test_reward_fail_streak_boosts():
    p = profile()
    seg = segment("u1", "moderate_ad_player", tol="medium")
    low = RewardPredictor().predict(p, seg, fail_streak=0)
    high = RewardPredictor().predict(p, seg, fail_streak=2)
    assert high > low

def test_reward_low_tolerance():
    seg_low = segment("u1", "moderate_ad_player", tol="low")
    seg_high = segment("u1", "moderate_ad_player", tol="high")
    p = profile()
    assert RewardPredictor().predict(p, seg_high, 0) > RewardPredictor().predict(p, seg_low, 0)

def test_reward_at_risk_lowers():
    seg = segment("u1", "at_risk_churn", tol="low")
    p = profile(ad_rev=0.05, ad_show=2, ad_req=10, reward_show=2, reward_req=10)
    assert RewardPredictor().predict(p, seg) < 0.5

def test_inter_level_complete_low_risk():
    r = InterstitialPredictor().predict(profile(), segment(), level_complete=True)
    assert r.quit_risk < 0.2

def test_inter_level_fail_high_risk():
    r = InterstitialPredictor().predict(profile(), segment(), level_fail=True)
    assert r.quit_risk > 0.2

def test_inter_churn_high_risk():
    r = InterstitialPredictor().predict(profile(), segment(seg="at_risk_churn"))
    assert r.quit_risk > 0.2

def test_inter_show_when_low_risk():
    r = InterstitialPredictor().predict(profile(), segment(tol="high"), level_complete=True)
    assert r.decision == "show"

def test_inter_skip_when_high_risk():
    r = InterstitialPredictor().predict(profile(), segment(seg="at_risk_churn"), level_fail=True)
    assert r.decision == "skip"

def test_detector_reward_on_fail():
    opps = OpportunityDetector().detect(profile(), segment(), fail_streak=1)
    assert any(o.opportunity_type == "reward" for o in opps)

def test_detector_reward_show_when_prob_high():
    p = profile()
    p.reward_accept_rate = 0.8
    opps = OpportunityDetector().detect(p, segment(tol="high"), fail_streak=2)
    rew = [o for o in opps if o.opportunity_type == "reward"]
    if rew: assert rew[0].decision == "show"

def test_detector_inter_on_complete():
    opps = OpportunityDetector().detect(profile(), segment(tol="high"), level_complete=True)
    assert any(o.opportunity_type == "interstitial" for o in opps)

def test_detector_empty_when_no_conditions():
    seg = segment("u1", "at_risk_churn", tol="low")
    opps = OpportunityDetector().detect(profile(), seg, fail_streak=0, level_complete=False, level_fail=False)
    assert opps == []

def test_reward_prob_clamped():
    p = profile()
    p.reward_accept_rate = 1.0
    r = RewardPredictor().predict(p, segment(tol="high"), fail_streak=5, session_early=True)
    assert 0 <= r <= 1

def test_inter_risk_clamped():
    r = InterstitialPredictor().predict(profile(), segment(seg="at_risk_churn", tol="low"), level_fail=True)
    assert 0 <= r.quit_risk <= 1

def test_detector_multiple_possible():
    opps = OpportunityDetector().detect(profile(), segment(tol="high"), fail_streak=1, level_complete=True)
    types = {o.opportunity_type for o in opps}
    assert len(types) >= 1

def test_reward_expected_revenue():
    p = profile()
    p.reward_accept_rate = 0.7
    opps = OpportunityDetector().detect(p, segment(tol="high"), fail_streak=2)
    rew = [o for o in opps if o.opportunity_type == "reward"]
    assert rew[0].expected_revenue > 0

def test_reward_session_early_boost():
    p = profile()
    seg = segment()
    base = RewardPredictor().predict(p, seg, fail_streak=0, session_early=False)
    boosted = RewardPredictor().predict(p, seg, fail_streak=0, session_early=True)
    assert boosted > base

def test_inter_default_ecpm():
    r = InterstitialPredictor().predict(profile(), segment(), level_complete=True)
    assert r.expected_revenue > 0

def test_inter_defer_mid_risk():
    r = InterstitialPredictor().predict(profile(), segment())
    assert r.decision in ("show", "skip", "defer")

def test_reward_acceptor_high_tol():
    seg = segment(tol="high")
    p = profile()
    p.reward_accept_rate = 0.6
    assert RewardPredictor().predict(p, seg, fail_streak=1) > 0.5
