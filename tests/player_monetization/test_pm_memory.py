import tempfile, os
from operation.player_monetization.models import PlayerLearningRecord
from operation.player_monetization.memory.player_learning import PlayerLearningMemory

def _rec(**kw):
    defaults = {"user_id":"u1","segment":"high_value","action":"reward_boost",
                "ad_type":"reward","arpdau_before":0.1,"arpdau_after":0.12,
                "retention_before":0.7,"retention_after":0.69,
                "decision":"positive","confidence":0.9,"recorded_at":"2026-07-24"}
    defaults.update(kw)
    return PlayerLearningRecord(**defaults)

def _mem():
    return PlayerLearningMemory(os.path.join(tempfile.mkdtemp(),"pl.jsonl"))

def test_record_returns():
    m = _mem(); assert m.record(_rec())["decision"] == "positive"

def test_record_persists():
    m = _mem(); m.record(_rec()); assert len(m._load()) == 1

def test_query_precedents():
    m = _mem(); m.record(_rec()); assert m.query()["precedents"] == 1

def test_query_by_segment():
    m = _mem(); m.record(_rec()); m.record(_rec(segment="casual"))
    assert m.query(segment="high_value")["precedents"] == 1

def test_query_by_action():
    m = _mem(); m.record(_rec()); m.record(_rec(action="freq_cap", decision="negative"))
    assert m.query(action="reward_boost")["precedents"] == 1

def test_positive_rate():
    m = _mem(); m.record(_rec()); m.record(_rec(decision="negative"))
    assert m.query()["positive_rate"] == 0.5

def test_query_empty():
    assert _mem().query()["precedents"] == 0

def test_record_positive_decision():
    r = _mem().record(_rec(decision="positive"))
    assert r["decision"] == "positive"

def test_record_negative_decision():
    r = _mem().record(_rec(decision="negative"))
    assert r["decision"] == "negative"

def test_query_no_match_rate_zero():
    assert _mem().query(segment="nope")["positive_rate"] == 0.0
