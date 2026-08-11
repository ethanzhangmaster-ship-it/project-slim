from tests.player_monetization.pm_helpers import segment, profile
from operation.player_monetization.frequency.frequency_optimizer import FrequencyOptimizer
from operation.player_monetization.frequency.fatigue_detector import FatigueDetector
from operation.player_monetization.frequency.cooldown_manager import CooldownManager

def test_freq_high_value():
    r = FrequencyOptimizer().optimize("u1", segment(seg="high_value_ad_player"))
    assert r.max_per_session == 5 and r.cooldown_sec == 120 and r.max_per_day == 20

def test_freq_at_risk():
    r = FrequencyOptimizer().optimize("u1", segment(seg="at_risk_churn"))
    assert r.max_per_session == 1 and r.cooldown_sec == 600 and r.max_per_day == 2

def test_freq_fatigue_reduces():
    r_no = FrequencyOptimizer().optimize("u1", segment(), fatigue=0.0)
    r_fat = FrequencyOptimizer().optimize("u1", segment(), fatigue=0.8)
    assert r_fat.max_per_session < r_no.max_per_session

def test_freq_new_player():
    r = FrequencyOptimizer().optimize("u1", segment(seg="new_player"))
    assert r.max_per_session == 2 and r.cooldown_sec == 240

def test_fatigue_no_drop():
    assert FatigueDetector().detect([0.7, 0.72, 0.71]) == 0.0

def test_fatigue_drop_above_threshold():
    assert FatigueDetector().detect([0.8, 0.7, 0.5]) > 0

def test_fatigue_all_zero():
    assert FatigueDetector().detect([0.0, 0.0, 0.0]) == 1.0

def test_fatigue_too_few_sessions():
    assert FatigueDetector().detect([0.7]) == 0.0

def test_cooldown_can_show_empty():
    assert CooldownManager().can_show("", 100)

def test_cooldown_can_show_past():
    assert CooldownManager().can_show("2020-01-01T00:00:00", 100)

def test_freq_all_caps_are_ints():
    for seg_name in ["high_value_ad_player","moderate_ad_player","casual_player","new_player","power_user","at_risk_churn"]:
        r = FrequencyOptimizer().optimize("u1", segment(seg=seg_name))
        assert isinstance(r.max_per_session, int)
        assert isinstance(r.cooldown_sec, int)
        assert isinstance(r.max_per_day, int)

def test_fatigue_level_in_range():
    for rates in ([0.8,0.7,0.5], [0.9,0.9,0.9], [0.0,0.0,0.0]):
        f = FatigueDetector().detect(rates)
        assert 0.0 <= f <= 1.0

def test_cooldown_empty_returns_true():
    assert CooldownManager().can_show("", 9999)

def test_freq_moderate_default():
    r = FrequencyOptimizer().optimize("u1", segment(seg="moderate_ad_player"))
    assert r.max_per_session == 3

def test_freq_uses_user_id():
    r = FrequencyOptimizer().optimize("x99", segment())
    assert r.user_id == "x99"
