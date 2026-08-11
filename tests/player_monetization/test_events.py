from tests.player_monetization.pm_helpers import profile, high_value_profile, casual_profile, new_profile, power_profile, churn_profile, events_for_profiles
from operation.player_monetization.events.event_schema import validate_player_event, validate_ad_event, validate_game_event
from operation.player_monetization.events.collector import EventCollector, SDKProvider, SyntheticProvider
from operation.player_monetization.events.validator import EventValidator, validate_profile

def test_validate_player_ok():
    assert validate_player_event({"user_id":"u1","timestamp":"t"})["ok"]

def test_validate_player_missing():
    assert not validate_player_event({"timestamp":"t"})["ok"]

def test_validate_ad_ok():
    assert validate_ad_event({"user_id":"u1","ad_type":"reward","timestamp":"t"})["ok"]

def test_validate_ad_bad_type():
    r = validate_ad_event({"user_id":"u1","ad_type":"weird","timestamp":"t"})
    assert not r["ok"]

def test_validate_game_ok():
    assert validate_game_event({"user_id":"u1","timestamp":"t"})["ok"]

def test_validate_game_missing():
    assert not validate_game_event({"ad_type":"reward"})["ok"]

def test_synthetic_provider_generates():
    ev = SyntheticProvider().one_user("u1")
    assert len(ev) > 0

def test_collector_aggregates():
    ev = SyntheticProvider().one_user("u1")
    profiles = EventCollector._aggregate(ev)
    assert len(profiles) == 1

def test_collector_counts():
    ev = SyntheticProvider().one_user("u1", sessions=5, ad_requests=20, ad_shows=15)
    p = EventCollector._aggregate(ev)[0]
    assert p.total_ad_requests == 20
    assert p.total_ad_shows == 15

def test_collector_accept_rate():
    ev = SyntheticProvider().one_user("u1", ad_requests=20, ad_shows=10)
    p = EventCollector._aggregate(ev)[0]
    assert 0 <= p.reward_accept_rate <= 1

def test_validator_accepts():
    ev = [{"type":"player","user_id":"u1","timestamp":"t"}]
    assert EventValidator().validate(ev)["accepted"] == 1

def test_validator_rejects():
    ev = [{"type":"player","timestamp":"t"}]
    r = EventValidator().validate(ev)
    assert r["rejected"] == 1

def test_validate_profile_shows_gt_requests():
    p = profile(ad_req=5, ad_show=10)
    assert not validate_profile(p)["ok"]

def test_validate_profile_negative_rev():
    p = profile(ad_rev=-1.0)
    assert not validate_profile(p)["ok"]

def test_sdk_provider_returns_empty():
    assert SDKProvider().fetch("","","") == []
