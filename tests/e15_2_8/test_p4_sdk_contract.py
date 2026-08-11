"""
P4 — Unity SDK -> LaunchForge event contract (end-to-end, no Unity needed).

The C# side (GameFactory.Analytics.Events.GameEvent.ToDictionary) FLATTENS its
`props` bag onto the top level of the envelope. This test proves the Python
ingest receiver (operation.player_monetization) accepts that exact shape over
HTTP exactly as the SDK would POST it — so the SDK is drop-in ready before any
Unity Editor exists.

It also proves app routing: the X-Game-Id header selects which
data/player_events/<app>.jsonl sink events land in.
"""
import json
import os
import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

import operation.player_monetization.ingest_server as INGEST
from operation.player_monetization.ingest_server import IngestHandler
from operation.player_monetization.normalize import normalize_envelope

# Per-test isolated sink. The server's ingest()/_sink_path read
# INGEST.DATA_DIR at call time, so redirecting it (plus the test's own
# DATA_DIR used by _read_jsonl/_cleanup) to a fresh tmp dir makes every
# test hermetic — no cross-run contamination from a crashed/interrupted
# prior run leaving stale *.jsonl behind.
DATA_DIR = os.path.join("data", "player_events")
_TS = "2026-07-27T08:00:00.0000000Z"
_TS_MS = 1753603200000


@pytest.fixture(autouse=True)
def _isolated_sink(tmp_path, monkeypatch):
    global DATA_DIR
    monkeypatch.setattr(INGEST, "DATA_DIR", str(tmp_path))
    DATA_DIR = str(tmp_path)
    yield


def _envelope(event, props=None, **extra):
    """Mirror GameFactory.Analytics.Events.GameEvent.ToDictionary() exactly."""
    d = {
        "event": event,
        "game": "com.test.p4",
        "platform": "android",
        "country": "US",
        "user_id": "u1",
        "session_id": "s1",
        "timestamp_ms": _TS_MS,
        "timestamp": _TS,
    }
    if props:
        d.update(props)  # C# flattens props to the top level — no nested "props" key
    d.update(extra)
    return d


def _start_server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), IngestHandler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, port


def _post(port, envelopes, app_id):
    body = json.dumps(envelopes).encode("utf-8")
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/events",
        data=body, headers={"Content-Type": "application/json", "X-Game-Id": app_id},
        method="POST")
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read().decode("utf-8"))


def _read_jsonl(app_id):
    path = os.path.join(DATA_DIR, app_id + ".jsonl")
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _cleanup(app_ids):
    for aid in app_ids:
        p = os.path.join(DATA_DIR, aid + ".jsonl")
        if os.path.exists(p):
            os.remove(p)


# ---- unit: normalize accepts the flattened C# envelope (the core regression) ----
def test_normalize_flattened_ad_event_keeps_ad_type():
    env = _envelope("ad_show", {"ad_format": "reward", "placement": "rv_1"})
    out = normalize_envelope(env)
    assert out["type"] == "ad"
    assert out["ad_type"] == "reward"          # must NOT be empty (old bug)
    assert out["show"] is True
    assert out["game"] == "com.test.p4"


def test_normalize_flattened_ad_revenue_keeps_revenue():
    env = _envelope("ad_revenue", {
        "ad_format": "reward", "network": "AppLovin", "placement": "rv_1",
        "ad_unit": "unit", "revenue": 0.0123, "ecpm": 12.3, "latency": 50})
    out = normalize_envelope(env)
    assert out["type"] == "ad"
    assert out["ad_type"] == "reward"
    assert abs(out.get("revenue", 0) - 0.0123) < 1e-9


# ---- integration: the SDK-POSTed batch is fully ingested + routed by app id ----
def test_sdk_batch_ingested_over_http_and_routed():
    srv, port = _start_server()
    try:
        batch = [
            _envelope("install"),
            _envelope("session_start"),
            _envelope("level_start", {"level": 3}),
            _envelope("ad_request", {"ad_format": "reward", "placement": "rv_1"}),
            _envelope("ad_show", {"ad_format": "reward", "placement": "rv_1"}),
            _envelope("ad_complete", {"ad_format": "reward", "placement": "rv_1", "completed": True}),
            _envelope("ad_revenue", {"ad_format": "reward", "network": "AppLovin",
                                     "placement": "rv_1", "ad_unit": "u", "revenue": 0.02}),
        ]
        resp = _post(port, batch, "com.test.p4")
        assert resp["accepted"] == len(batch), resp
        assert resp["rejected"] == 0, resp

        lines = _read_jsonl("com.test.p4")
        assert len(lines) == len(batch)
        types = {l["type"] for l in lines}
        assert types == {"player", "game", "ad"}
        # the ad_revenue line must carry the revenue + network the SDK sent
        rev = [l for l in lines if l.get("type") == "ad" and l.get("revenue")][0]
        assert abs(rev["revenue"] - 0.02) < 1e-9
        assert rev["network"] == "AppLovin"
    finally:
        srv.shutdown()
        _cleanup(["com.test.p4"])


def test_app_routing_via_x_game_id_header():
    srv, port = _start_server()
    try:
        # Two different games POST to the same endpoint; header routes them apart.
        _post(port, [_envelope("install")], "com.test.alpha")
        _post(port, [_envelope("level_start", {"level": 5})], "com.test.beta")
        time.sleep(0.1)
        alpha = _read_jsonl("com.test.alpha")
        beta = _read_jsonl("com.test.beta")
        assert len(alpha) == 1 and alpha[0]["type"] == "player"
        assert len(beta) == 1 and beta[0]["type"] == "game"
    finally:
        srv.shutdown()
        _cleanup(["com.test.alpha", "com.test.beta"])
