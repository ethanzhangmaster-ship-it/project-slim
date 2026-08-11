"""Event schema tests — 20 (spec: Event Schema 20)."""
from tests.e15_2_8.e15_2_8_helpers import synthetic_events
from operation.player_monetization.events.event_schema import (
    validate_player_event, validate_ad_event, validate_game_event,
)
from operation.player_monetization.events.validator import EventValidator, validate_profile
from operation.player_monetization.events.collector import SDKProvider, SyntheticProvider, EventCollector
from operation.player_monetization.models import PlayerProfile

# ---- schema (8) ----
def test_player_ok():
    assert validate_player_event({"user_id":"u1","timestamp":"t"})["ok"]
def test_player_no_user():
    assert not validate_player_event({"timestamp":"t"})["ok"]
def test_ad_reward_ok():
    assert validate_ad_event({"user_id":"u1","ad_type":"reward","timestamp":"t"})["ok"]
def test_ad_bad_type():
    assert not validate_ad_event({"user_id":"u1","ad_type":"unknown","timestamp":"t"})["ok"]
def test_game_ok():
    assert validate_game_event({"user_id":"u1","timestamp":"t"})["ok"]
def test_game_no_user():
    assert not validate_game_event({"timestamp":"t"})["ok"]
def test_player_null_user():
    assert not validate_player_event({"user_id":None,"timestamp":"t"})["ok"]
def test_ad_missing_type():
    assert not validate_ad_event({"user_id":"u1","timestamp":"t"})["ok"]

# ---- validator (6) ----
def test_validator_accepts_all():
    ev = synthetic_events(1)
    r = EventValidator().validate(ev)
    assert r["ok"]
    assert r["rejected"] == 0
def test_validator_mixed():
    ev = synthetic_events(1) + [{"type":"zzz"}]
    r = EventValidator().validate(ev)
    assert r["rejected"] >= 1
def test_validator_unknown_type():
    r = EventValidator().validate([{"type":"unknown","user_id":"u1"}])
    assert r["rejected"] == 1
def test_validate_profile_ok():
    p = PlayerProfile(user_id="x", total_ad_requests=10, total_ad_shows=5,
                      reward_accept_rate=0.5, fail_rate=0.2, total_ad_revenue=0.5)
    assert validate_profile(p)["ok"]
def test_validate_profile_bad_rate():
    p = PlayerProfile(user_id="x", reward_accept_rate=1.5)
    assert not validate_profile(p)["ok"]
def test_validate_profile_negative():
    p = PlayerProfile(user_id="x", total_ad_revenue=-0.1)
    assert not validate_profile(p)["ok"]

# ---- collector / synthetic (3) ----
def test_synthetic_events_count():
    ev = synthetic_events(2)
    assert len(ev) > 10
def test_collector_from_synthetic():
    ev = synthetic_events(2)
    profiles = EventCollector._aggregate(ev)
    assert len(profiles) == 2
def test_collector_aggregate_counts():
    ev = SyntheticProvider().one_user("u99", sessions=3, ad_requests=9, ad_shows=6)
    p = EventCollector._aggregate(ev)[0]
    assert p.total_ad_requests == 9 and p.total_ad_shows == 6

# ---- SDK stub (3) ----
def test_sdk_provider_empty():
    assert SDKProvider().fetch("","","") == []
def test_sdk_provider_app_id_ignored():
    assert SDKProvider().fetch("","","com.x.y") == []
def test_sdk_provider_returns_list():
    assert isinstance(SDKProvider().fetch("","",""), list)
