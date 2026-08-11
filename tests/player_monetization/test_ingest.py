"""
E15.2.7 — Event ingest pipeline tests.

Covers the anti-corruption normalizer (Unity envelope -> player_monetization
contract) and the full Lean receive path: Unity-shaped envelopes -> HTTP POST
-> validate -> JSONL sink -> SDKProvider -> EventCollector -> PlayerProfile.
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from operation.player_monetization.events.collector import EventCollector, SDKProvider
from operation.player_monetization.ingest_server import IngestHandler, ingest
from operation.player_monetization.normalize import normalize_envelope


@pytest.fixture(autouse=True)
def _isolate_player_events():
    # The ingest server appends to data/player_events/<app>.jsonl. Wipe the
    # sink before each test so re-runs don't accumulate stale events and
    # break the exact-count assertions below.
    d = os.path.join("data", "player_events")
    if os.path.isdir(d):
        for fn in os.listdir(d):
            if fn.endswith(".jsonl"):
                os.remove(os.path.join(d, fn))
    yield


def _env(event, uid="u1", props=None, ts="2026-07-27T00:00:00+00:00"):
    return {
        "event": event, "game": "demo", "platform": "android",
        "country": "US", "user_id": uid, "session_id": "s1",
        "timestamp_ms": 1750000000000, "timestamp": ts,
        "props": props or {},
    }


# ---- normalizer unit tests -------------------------------------------------

def test_ad_show_normalizes():
    out = normalize_envelope(_env("ad_show", props={"ad_format": "reward"}))
    assert out["type"] == "ad"
    assert out["ad_type"] == "reward"
    assert out["show"] is True
    assert out["user_id"] == "u1"


def test_ad_revenue_carries_revenue():
    out = normalize_envelope(_env("ad_revenue",
                                   props={"ad_format": "interstitial", "revenue": 0.02}))
    assert out["type"] == "ad"
    assert out["ad_type"] == "interstitial"
    assert out["revenue"] == 0.02
    assert out["complete"] is True


def test_level_events_are_game_type():
    out = normalize_envelope(_env("level_complete", props={"level": 5}))
    assert out["type"] == "game"
    assert out["level_start"] == 5
    assert out["level_complete"] is True


def test_install_is_player():
    out = normalize_envelope(_env("install"))
    assert out["type"] == "player"


# ---- receive pipeline ------------------------------------------------------

@pytest.fixture
def receiver():
    srv = ThreadingHTTPServer(("127.0.0.1", 8799), IngestHandler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    time.sleep(0.2)
    yield "http://127.0.0.1:8799/events"
    srv.shutdown()


def _post(url, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def test_ingest_accepts_unity_envelopes(receiver):
    envs = [
        _env("install"),
        _env("ad_request", props={"ad_format": "reward"}),
        _env("ad_show", props={"ad_format": "reward"}),
        _env("ad_revenue", props={"ad_format": "reward", "revenue": 0.01}),
    ]
    summary = _post(receiver + "?app=demo", envs)
    assert summary["accepted"] == 4
    assert summary["rejected"] == 0


def test_ingest_persists_and_collects(receiver):
    envs = [_env("install", uid=f"u{i}") for i in range(3)]
    envs += [_env("ad_revenue", uid=f"u{i}",
                  props={"ad_format": "reward", "revenue": 0.01}) for i in range(3)]
    _post(receiver + "?app=collect_demo", envs)

    profiles = EventCollector(SDKProvider()).collect(app_id="collect_demo")
    assert len(profiles) == 3
    for p in profiles:
        assert p.total_ad_revenue == 0.01
        assert p.total_ad_shows == 1


def test_ingest_rejects_malformed():
    # ad event missing ad_type -> rejected by validator
    bad = [{"event": "ad_show", "user_id": "x", "timestamp": "t", "props": {}}]
    summary = ingest(bad, "demo")
    assert summary["rejected"] >= 1


def test_single_object_body(receiver):
    summary = _post(receiver + "?app=single", _env("install"))
    assert summary["accepted"] == 1
