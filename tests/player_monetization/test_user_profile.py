from tests.player_monetization.pm_helpers import profile, high_value_profile, casual_profile, new_profile, power_profile, churn_profile
from operation.player_monetization.user_profile.player_segment import PlayerSegmenter
from operation.player_monetization.user_profile.value_predictor import ValuePredictor
from operation.player_monetization.user_profile.lifecycle import LifecycleDetector

def test_segment_new():
    s = PlayerSegmenter().classify(new_profile())
    assert s.segment == "new_player"

def test_segment_churn():
    s = PlayerSegmenter().classify(churn_profile())
    assert s.segment == "at_risk_churn"

def test_segment_high_value():
    s = PlayerSegmenter().classify(high_value_profile())
    assert s.segment == "high_value_ad_player"

def test_segment_power_user():
    s = PlayerSegmenter().classify(power_profile())
    assert s.segment == "power_user"

def test_segment_casual():
    s = PlayerSegmenter().classify(casual_profile())
    assert s.segment == "casual_player"

def test_value_us():
    vp = ValuePredictor().predict(high_value_profile("u1"))
    cn = ValuePredictor().predict(profile("u2", country="IN"))
    assert vp.predicted_30d_iaa > cn.predicted_30d_iaa

def test_value_churn_low():
    vp = ValuePredictor().predict(churn_profile())
    assert vp.predicted_30d_iaa < 0.5

def test_value_power_alive():
    vp = ValuePredictor().predict(power_profile())
    assert vp.predicted_30d_iaa > 0

def test_value_confidence():
    vp = ValuePredictor().predict(profile())
    assert 0.3 <= vp.confidence <= 0.95

def test_lifecycle_new():
    assert LifecycleDetector().stage(new_profile()) == "NEW"

def test_lifecycle_engaged():
    assert LifecycleDetector().stage(high_value_profile()) == "ENGAGED"

def test_lifecycle_churning():
    assert LifecycleDetector().stage(profile(days=10), days_since_last_active=5) == "CHURNING"

def test_lifecycle_lapsed():
    assert LifecycleDetector().stage(profile(days=30), days_since_last_active=15) == "LAPSED"

def test_segment_score_range():
    s = PlayerSegmenter().classify(high_value_profile())
    assert 0 <= s.value_score <= 100

def test_segment_tolerance():
    s = PlayerSegmenter().classify(high_value_profile())
    assert s.ad_tolerance in ("high", "medium", "low")
