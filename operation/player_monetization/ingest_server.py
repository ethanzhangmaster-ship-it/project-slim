"""
E15.2.7 — Lean event ingest receiver.

A tiny HTTP server (Python stdlib only — NO Flask/FastAPI, per the architecture
principles) that accepts Unity SDK event envelopes, normalizes them to the
player_monetization contract, validates them, and appends accepted events to an
append-only JSONL sink under ``data/player_events/<app_id>.jsonl``.

Endpoints:
  POST /events   body = JSON envelope OR list of envelopes (optionally ?app=<id>)
               -> {"accepted": N, "rejected": M, "errors": [...]}
  GET  /health  -> {"ok": true}

The Python-side SDKProvider reads the same JSONL file, so the Unity SDK event
stream flows straight into EventCollector -> player_monetization analyzers
(Ad Experience Optimizer, frequency capping, user_value prediction, ...).

Run:  python -m operation.player_monetization.ingest_server --port 8765
"""
from __future__ import annotations

import argparse
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List
from urllib.parse import urlparse, parse_qs

from operation.player_monetization.events.validator import EventValidator
from operation.player_monetization.normalize import normalize_envelope

DATA_DIR = os.path.join("data", "player_events")
_SAFE = re.compile(r"[^A-Za-z0-9_.-]")


def _safe_app(app_id: str) -> str:
    """Sanitize an app id so it can't traverse the data dir."""
    if not app_id:
        return "default"
    cleaned = _SAFE.sub("_", app_id)
    return cleaned or "default"


def _sink_path(app_id: str) -> str:
    os.makedirs(DATA_DIR, exist_ok=True)
    return os.path.join(DATA_DIR, _safe_app(app_id) + ".jsonl")


def ingest(envelopes: List[Dict[str, Any]], app_id: str) -> Dict[str, Any]:
    """Validate + persist a batch. Returns the ingest summary."""
    validator = EventValidator()
    normalized = [normalize_envelope(e) for e in envelopes]
    result = validator.validate(normalized)
    accepted = [e for e in normalized if _is_accepted(e, result)]
    if accepted:
        path = _sink_path(app_id)
        with open(path, "a", encoding="utf-8") as f:
            for e in accepted:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
    return {
        "accepted": len(accepted),
        "rejected": result["rejected"],
        "errors": result["errors"][:50],
    }


def _is_accepted(e: Dict[str, Any], result: Dict[str, Any]) -> bool:
    # EventValidator returns errors keyed by original index; we recompute per-event
    # acceptance deterministically instead of relying on index alignment.
    tp = e.get("type", "")
    if tp == "player":
        return bool(e.get("user_id")) and bool(e.get("timestamp"))
    if tp == "ad":
        return bool(e.get("user_id")) and bool(e.get("ad_type")) and bool(e.get("timestamp"))
    if tp == "game":
        return bool(e.get("user_id")) and bool(e.get("timestamp"))
    return False


class IngestHandler(BaseHTTPRequestHandler):
    def _send(self, code: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.split("?")[0] == "/health":
            self._send(200, {"ok": True})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self.path.split("?")[0] == "/events":
            self._send(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"[]"
            data = json.loads(raw.decode("utf-8"))
        except (ValueError, json.JSONDecodeError):
            self._send(400, {"error": "invalid JSON body"})
            return
        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list):
            self._send(400, {"error": "body must be an object or array"})
            return
        app_id = "default"
        qs = parse_qs(urlparse(self.path).query)
        if qs.get("app"):
            app_id = qs["app"][0]
        elif self.headers.get("X-Game-Id"):
            app_id = self.headers["X-Game-Id"]
        summary = ingest(data, app_id)
        self._send(200, summary)

    def log_message(self, *args):  # silence default stderr logging
        pass


def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = ThreadingHTTPServer((host, port), IngestHandler)
    print(f"[ingest_server] listening on http://{host}:{port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Lean event ingest receiver")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args(argv)
    run_server(args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
