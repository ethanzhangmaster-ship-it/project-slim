"""
E15.2.7 — Event ingest CLI (one entry point, lazy-friendly).

  python -m operation.player_monetization.ingest serve    # run the Lean HTTP receiver
  python -m operation.player_monetization.ingest collect --app ACCT_2::MergeMonster
  python -m operation.player_monetization.ingest simulate --app demo \\
        --post http://127.0.0.1:8765/events               # generate Unity-shaped
                                                            # events, POST them, prove E2E

`simulate` needs a receiver running (start `serve` in another terminal, or pass
--self-serve to launch one in-process). It emits envelopes in the EXACT Unity SDK
shape (Analytics.LogEvent -> GameEvent.ToDictionary) so the same code path that
real games use is exercised.
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List

from operation.player_monetization.events.collector import EventCollector, SDKProvider
from operation.player_monetization.ingest_server import run_server


def _unity_envelope(event_name: str, user_id: str, app: str,
                    props: Dict[str, Any] | None = None,
                    country: str = "US") -> Dict[str, Any]:
    """Produce an event in the canonical Unity SDK envelope shape."""
    return {
        "event": event_name,
        "game": app,
        "platform": "android",
        "country": country,
        "user_id": user_id,
        "session_id": f"sess_{user_id}",
        "timestamp_ms": int(time.time() * 1000),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "props": props or {},
    }


def _demo_envelopes(app: str, users: int = 5) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for i in range(users):
        uid = f"u{i:03d}"
        out.append(_unity_envelope("install", uid, app))
        out.append(_unity_envelope("session_start", uid, app))
        out.append(_unity_envelope("level_start", uid, app, {"level": 1}))
        out.append(_unity_envelope("ad_request", uid, app,
                                    {"ad_format": "reward", "placement": "rv_1"}))
        out.append(_unity_envelope("ad_show", uid, app,
                                    {"ad_format": "reward", "placement": "rv_1"}))
        out.append(_unity_envelope("ad_complete", uid, app,
                                    {"ad_format": "reward", "placement": "rv_1",
                                     "completed": True}))
        out.append(_unity_envelope("ad_revenue", uid, app,
                                    {"ad_format": "reward", "placement": "rv_1",
                                     "network": "AppLovin", "revenue": 0.012}))
        out.append(_unity_envelope("level_complete", uid, app,
                                    {"level": 1, "score": 120}))
    return out


def _post(url: str, payload: Any) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def cmd_serve(args: argparse.Namespace) -> int:
    run_server(args.host, args.port)
    return 0


def cmd_collect(args: argparse.Namespace) -> int:
    collector = EventCollector(SDKProvider())
    profiles = collector.collect(app_id=args.app)
    if not profiles:
        print(f"[collect] no events yet for app={args.app} "
              f"(run `simulate` or let the game send events)")
        return 0
    print(f"[collect] app={args.app} -> {len(profiles)} player profiles")
    for p in profiles[:5]:
        print("  ", p.to_dict())
    return 0


def cmd_simulate(args: argparse.Namespace) -> int:
    import threading

    url = args.post.rstrip("/")
    if args.self_serve:
        t = threading.Thread(target=run_server, args=(args.host, args.port),
                             daemon=True)
        t.start()
        time.sleep(0.4)
        url = f"http://{args.host}:{args.port}/events"

    envelopes = _demo_envelopes(args.app, users=args.users)
    summary = _post(url + f"?app={args.app}", envelopes)
    print(f"[simulate] POST {len(envelopes)} Unity-shaped envelopes -> {url}")
    print(f"[simulate] ingest summary: {summary}")
    # Immediately prove the data flows into the collector.
    collector = EventCollector(SDKProvider())
    profiles = collector.collect(app_id=args.app)
    print(f"[simulate] collector produced {len(profiles)} player profiles "
          f"from the ingested events")
    return 0


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="E15.2.7 event ingest CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("serve", help="run the Lean HTTP event receiver")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8765)
    s.set_defaults(func=cmd_serve)

    c = sub.add_parser("collect", help="read ingested events -> player profiles")
    c.add_argument("--app", required=True)
    c.set_defaults(func=cmd_collect)

    m = sub.add_parser("simulate", help="generate Unity-shaped events and POST them")
    m.add_argument("--app", default="demo")
    m.add_argument("--users", type=int, default=5)
    m.add_argument("--post", default="http://127.0.0.1:8765/events")
    m.add_argument("--self-serve", action="store_true",
                   help="launch the receiver in-process before posting")
    m.add_argument("--host", default="127.0.0.1")
    m.add_argument("--port", type=int, default=8765)
    m.set_defaults(func=cmd_simulate)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
