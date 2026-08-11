"""Uploader + aggregation tests — 30 (Uploader 10 + Aggregation 20)."""
import tempfile, os
from tests.e15_2_8.e15_2_8_helpers import synthetic_events, write_jsonl
from operation.player_monetization.events.collector import FileEventReceiver, EventCollector
from operation.player_monetization.events.event_schema import validate_player_event

# ---- FileEventReceiver / uploader (10) ----
def test_file_receiver_empty():
    d = tempfile.mkdtemp(); p = os.path.join(d, "events.jsonl")
    assert FileEventReceiver(p).fetch() == []

def test_file_receiver_reads():
    d = tempfile.mkdtemp(); p = os.path.join(d, "events.jsonl")
    write_jsonl(p, synthetic_events(1))
    assert len(FileEventReceiver(p).fetch()) > 0

def test_file_receiver_skips_invalid():
    d = tempfile.mkdtemp(); p = os.path.join(d, "events.jsonl")
    with open(p, "w") as f:
        f.write('not json\n{"type":"player","user_id":"u1","timestamp":"t"}\n')
    assert len(FileEventReceiver(p).fetch()) == 1

def test_file_receiver_skips_empty_lines():
    d = tempfile.mkdtemp(); p = os.path.join(d, "events.jsonl")
    with open(p, "w") as f:
        f.write('\n{"type":"player","user_id":"u1","timestamp":"t"}\n\n')
    assert len(FileEventReceiver(p).fetch()) == 1

def test_file_receiver_multiple_users():
    d = tempfile.mkdtemp(); p = os.path.join(d, "events.jsonl")
    write_jsonl(p, synthetic_events(3))
    profiles = EventCollector._aggregate(FileEventReceiver(p).fetch())
    assert len(profiles) == 3

def test_file_receiver_params_ignored():
    d = tempfile.mkdtemp(); p = os.path.join(d, "events.jsonl")
    write_jsonl(p, synthetic_events(1))
    assert len(FileEventReceiver(p).fetch("2020-01-01","2099-01-01","app")) > 0

def test_collector_with_file_receiver():
    d = tempfile.mkdtemp(); p = os.path.join(d, "events.jsonl")
    write_jsonl(p, synthetic_events(2))
    profiles = EventCollector(FileEventReceiver(p)).collect()
    assert len(profiles) == 2

def test_aggregate_game_fail_rate():
    ev = [{"type":"game","user_id":"u1","timestamp":"t","level_fail":1},
          {"type":"game","user_id":"u1","timestamp":"t2","level_fail":0}]
    p = EventCollector._aggregate(ev)[0]
    assert p.fail_rate == 0.5

def test_aggregate_reward_accept():
    ev = [{"type":"ad","user_id":"u1","ad_type":"reward","timestamp":"t","show":True},
          {"type":"ad","user_id":"u1","ad_type":"reward","timestamp":"t2","show":False}]
    p = EventCollector._aggregate(ev)[0]
    assert p.reward_accept_rate == 0.5

def test_aggregate_country_preserved():
    ev = synthetic_events(1)
    p = EventCollector._aggregate(ev)[0]
    assert p.country == "US"

# ---- Aggregation (20) ----
def test_agg_session_count():
    ev = synthetic_events(2)
    profiles = EventCollector._aggregate(ev)
    assert all(p.session_count > 0 for p in profiles)

def test_agg_play_time_positive():
    ev = synthetic_events(1)
    p = EventCollector._aggregate(ev)[0]
    assert p.total_play_time_sec > 0

def test_agg_ad_revenue_positive():
    ev = synthetic_events(1)
    p = EventCollector._aggregate(ev)[0]
    assert p.total_ad_revenue > 0

def test_agg_days_active():
    ev = synthetic_events(1)
    p = EventCollector._aggregate(ev)[0]
    assert p.days_active >= 1

def test_agg_active_flag():
    ev = synthetic_events(1)
    p = EventCollector._aggregate(ev)[0]
    assert p.active

def test_agg_max_level():
    ev = [{"type":"player","user_id":"u1","level":5,"timestamp":"t"},
          {"type":"player","user_id":"u1","level":10,"timestamp":"t2"}]
    p = EventCollector._aggregate(ev)[0]
    assert p.level == 10

def test_agg_empty_ev_returns_empty():
    assert EventCollector._aggregate([]) == []

def test_agg_unknown_type_ignored():
    ev = [{"type":"weird","user_id":"u1"}]
    p = EventCollector._aggregate(ev)[0]
    assert p.total_ad_requests == 0

def test_agg_multiple_days():
    ev = [{"type":"player","user_id":"u1","timestamp":"2026-07-20T00:00:00"},
          {"type":"player","user_id":"u1","timestamp":"2026-07-22T00:00:00"}]
    p = EventCollector._aggregate(ev)[0]
    assert p.days_active == 2

def test_agg_ad_completion_tracked():
    ev = [{"type":"ad","user_id":"u1","ad_type":"reward","timestamp":"t","show":True,"complete":True}]
    p = EventCollector._aggregate(ev)[0]
    assert p.total_ad_completions == 1

def test_agg_avg_session_computed():
    ev = [{"type":"player","user_id":"u1","level":1,"session_count":1,"play_time_sec":300,"timestamp":"t0"},
          {"type":"player","user_id":"u1","level":2,"session_count":2,"play_time_sec":200,"timestamp":"t1"}]
    p = EventCollector._aggregate(ev)[0]
    assert p.avg_session_sec > 0

def test_agg_zero_fail_rate_when_no_fails():
    ev = [{"type":"game","user_id":"u1","timestamp":"t","level_fail":0}]
    p = EventCollector._aggregate(ev)[0]
    assert p.fail_rate == 0.0

def test_agg_install_day_not_required():
    ev = [{"type":"player","user_id":"u1","timestamp":"t","country":"US"}]
    p = EventCollector._aggregate(ev)[0]
    assert p.country == "US"

def test_agg_play_time_seconds_aggregated():
    ev = [{"type":"player","user_id":"u1","play_time_sec":100,"timestamp":"t0"},
          {"type":"player","user_id":"u1","play_time_sec":200,"timestamp":"t1"}]
    p = EventCollector._aggregate(ev)[0]
    assert p.total_play_time_sec == 300

def test_agg_sessions_dedup_by_count():
    ev = [{"type":"player","user_id":"u1","session_count":1,"timestamp":"t1"},
          {"type":"player","user_id":"u1","session_count":1,"timestamp":"t2"}]
    p = EventCollector._aggregate(ev)[0]
    assert p.session_count == 1

def test_agg_reward_accept_clamped():
    ev = [{"type":"ad","user_id":"u1","ad_type":"reward","show":True,"timestamp":"t"}] * 10
    p = EventCollector._aggregate(ev)[0]
    assert 0 <= p.reward_accept_rate <= 1

def test_agg_multiple_ad_types():
    ev = [{"type":"ad","user_id":"u1","ad_type":"reward","show":True,"timestamp":"t"},
          {"type":"ad","user_id":"u1","ad_type":"interstitial","show":True,"timestamp":"t2"}]
    p = EventCollector._aggregate(ev)[0]
    assert p.total_ad_shows == 2

def test_agg_level_from_player_events():
    ev = [{"type":"player","user_id":"u1","level":7,"timestamp":"t0"},
          {"type":"player","user_id":"u1","level":12,"timestamp":"t1"}]
    p = EventCollector._aggregate(ev)[0]
    assert p.level == 12

def test_agg_no_user_id_skipped():
    ev = [{"type":"player","timestamp":"t"}]
    assert EventCollector._aggregate(ev) == []

def test_agg_country_from_first_event():
    ev = [{"type":"player","user_id":"u1","country":"JP","timestamp":"t0"},
          {"type":"player","user_id":"u1","country":"","timestamp":"t1"}]
    p = EventCollector._aggregate(ev)[0]
    assert p.country == "JP"
