"""
E13.3.1 — Demo event batch (with the two new dimensions)
=========================================================

Reuses the E13.2.8 synthetic generator (whose injected anomalies are proven
to fire ecpm_drop / fill_drop / ad_frequency_issue) and annotates every event
with `traffic_source` and `user_cohort` so the Segment Engine can demonstrate
the finer grain.

  * traffic_source: facebook | google | organic  (hash of user_id)
  * user_cohort:    early (install day <= 6) | late

Deterministic. No I/O.
"""
from __future__ import annotations

from datetime import date, datetime

from intelligence.synthetic_events import GAME, PLATFORM, generate

_BASE = date(2026, 7, 10)
_SOURCES = ["facebook", "google", "organic"]


def _install_day(ts_ms: int) -> int:
    d = datetime.utcfromtimestamp(ts_ms / 1000).date()
    return (d - _BASE).days


def generate_demo() -> list:
    events = generate()
    # pass 1: capture each user's install day
    install_day = {}
    for e in events:
        if e.get("event") == "install":
            install_day[e["user_id"]] = _install_day(e["timestamp_ms"])
    # pass 2: annotate
    for e in events:
        uid = e.get("user_id")
        if not uid:
            e["traffic_source"] = "organic"
            e["user_cohort"] = "unknown"
            continue
        e["traffic_source"] = _SOURCES[hash(uid) % len(_SOURCES)]
        day = install_day.get(uid)
        e["user_cohort"] = "early" if day is not None and day <= 6 else "late"
    return events


if __name__ == "__main__":
    evs = generate_demo()
    print(f"generated {len(evs)} demo events with traffic_source/user_cohort")
