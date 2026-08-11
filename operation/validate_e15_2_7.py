"""
E15.2.7 acceptance gate — Player Monetization event stream (Unity SDK -> backend).

Verifies the real-data line that unlocks the Ad Experience Optimizer:
  Unity RemoteEventUploader --POST--> Lean ingest receiver --> JSONL sink
  --> SDKProvider --> EventCollector --> PlayerProfile  (fed to analyzers)

C# sides are checked by source-token presence (cannot compile here, no Unity);
the Python pipeline is exercised end-to-end.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import threading
import time
import types
import urllib.request
from http.server import ThreadingHTTPServer

_passed, _failed = 0, 0


def ingest_server_src() -> str:
    return open("operation/player_monetization/ingest_server.py",
                encoding="utf-8").read()


def check(name: str, cond: bool) -> None:
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  [OK]   {name}")
    else:
        _failed += 1
        print(f"  [FAIL] {name}")


print("=== E15.2.7 Player Monetization Event Stream ===")

# ---- C# contract (source-token presence) -----------------------------------
_uploader = open(
    "com.gamefactory.sdk/Runtime/Analytics/Data/EventUploader.cs",
    encoding="utf-8").read()
_config = open(
    "com.gamefactory.sdk/Runtime/Core/GameFactoryConfig.cs",
    encoding="utf-8").read()
_analytics = open(
    "com.gamefactory.sdk/Runtime/Analytics/Analytics.cs",
    encoding="utf-8").read()

print("-- Game side (C# source contract) --")
check("RemoteEventUploader uses UnityWebRequest", "UnityWebRequest" in _uploader)
check("RemoteEventUploader is fire-and-forget (SendWebRequest)",
      "SendWebRequest" in _uploader)
check("RemoteEventUploader.Enabled gates on endpoint",
      "IsNullOrEmpty(_endpoint)" in _uploader)
check("AnalyticsConfig has event_endpoint", "event_endpoint" in _config)
check("Analytics.Initialize wires RemoteEventUploader on endpoint",
      "RemoteEventUploader(cfg.event_endpoint)" in _analytics)

# ---- Python normalizer ----------------------------------------------------
print("-- Normalizer (Unity envelope -> contract) --")
from operation.player_monetization.normalize import normalize_envelope

e = normalize_envelope({"event": "ad_show", "user_id": "u1",
                         "timestamp": "t", "props": {"ad_format": "reward"}})
check("ad_show -> type=ad", e["type"] == "ad")
check("ad_show -> ad_type=reward", e["ad_type"] == "reward")
check("ad_show -> show=True", e.get("show") is True)

e = normalize_envelope({"event": "level_complete", "user_id": "u1",
                         "timestamp": "t", "props": {"level": 7}})
check("level_complete -> type=game", e["type"] == "game")
check("level_complete -> level_start", e.get("level_start") == 7)

# ---- Receive pipeline -----------------------------------------------------
print("-- Lean ingest receiver (end-to-end) --")
from operation.player_monetization.events.collector import EventCollector, SDKProvider
from operation.player_monetization.ingest_server import IngestHandler, ingest

sink_dir = "data/player_events"
os.makedirs(sink_dir, exist_ok=True)
for f in os.listdir(sink_dir):
    os.remove(os.path.join(sink_dir, f))

envs = [
    {"event": "install", "user_id": "u1", "timestamp": "t", "props": {}},
    {"event": "ad_revenue", "user_id": "u1", "timestamp": "t",
     "props": {"ad_format": "reward", "revenue": 0.01}},
]
summary = ingest(envs, "accept_gate")
check("ingest accepts valid envelopes", summary["accepted"] == 2)
check("ingest rejects malformed ad (no ad_type)",
      ingest([{"event": "ad_show", "user_id": "x", "timestamp": "t", "props": {}}],
             "accept_gate")["rejected"] >= 1)

profiles = EventCollector(SDKProvider()).collect(app_id="accept_gate")
check("SDKProvider reads ingested events (not empty stub)", len(profiles) >= 1)
check("collector aggregates revenue", any(p.total_ad_revenue == 0.01 for p in profiles))

srv = ThreadingHTTPServer(("127.0.0.1", 8801), IngestHandler)
threading.Thread(target=srv.serve_forever, daemon=True).start()
time.sleep(0.2)
payload = json.dumps([
    {"event": "install", "user_id": "v1", "timestamp": "t", "props": {}},
    {"event": "ad_show", "user_id": "v1", "timestamp": "t",
     "props": {"ad_format": "reward"}},
]).encode()
req = urllib.request.Request("http://127.0.0.1:8801/events?app=http_gate",
                              data=payload,
                              headers={"Content-Type": "application/json"},
                              method="POST")
with urllib.request.urlopen(req, timeout=10) as r:
    srv_summary = json.loads(r.read())
srv.shutdown()
check("HTTP POST /events accepts batch", srv_summary["accepted"] == 2)
check("HTTP-ingested events reach collector",
      len(EventCollector(SDKProvider()).collect(app_id="http_gate")) >= 1)

# ---- CLI + config_generator ------------------------------------------------
print("-- CLI + config_generator --")
from operation.player_monetization import ingest as ingest_cli
check("ingest CLI module importable", hasattr(ingest_cli, "main"))

spec = importlib.util.spec_from_file_location("cg", "src/config_generator.py")
cg = importlib.util.module_from_spec(spec)
sys.modules["yaml"] = types.ModuleType("yaml")
spec.loader.exec_module(cg)
out = cg.build_config({"analytics": {"event_endpoint": "https://x/events"}})
check("config_generator emits event_endpoint",
      out["analytics"]["event_endpoint"] == "https://x/events")

# ---- Lean constraint ------------------------------------------------------
print("-- Lean constraint (no framework deps) --")
src = ingest_server_src()
check("ingest_server uses only stdlib (no flask/fastapi)",
      ("flask" not in src) and ("fastapi" not in src))
check("ingest_server uses http.server", "http.server" in src)

# ---- cleanup --------------------------------------------------------------
for app in ("accept_gate", "http_gate"):
    p = os.path.join(sink_dir, app + ".jsonl")
    if os.path.exists(p):
        os.remove(p)

print(f"\n=== E15.2.7: {_passed} passed, {_failed} failed ===")
raise SystemExit(1 if _failed else 0)
