"""
E13.2.8 — Deterministic synthetic event generator
==================================================

Produces a realistic GameFactoryEvent stream (matching the E13.2.7 contract)
with three *injected* anomalies so the validate script can assert the
Opportunity Detector actually fires:

  1. eCPM drop  + revenue drop  on US / android / reward / applovin
     (last day eCPM 32 -> 20, ~37% drop)
  2. fill drop  on US / android / interstitial / applovin
     (last day fill 0.80 -> 0.45)
  3. ad_frequency_issue: late-period ads_per_dau 2x early, while D1 retention
     drops (early installs D1~0.45, late installs D1~0.25)

Deterministic via random.seed(42). No I/O.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

GAME = "word001"
PLATFORM = "android"
COUNTRY = "US"
BASE = datetime(2026, 7, 10, 12, 0, 0, tzinfo=timezone.utc)
N_DAYS = 14

# installs per day (early < 7 heavier, plus a late bump to keep cohorts alive)
INSTALL_PLAN = [80, 60, 50, 40, 30, 25, 20, 60, 50, 40, 30, 25, 20, 70]


def _ts(day: int, offset_sec: int = 0) -> int:
    return int((BASE + timedelta(days=day, seconds=offset_sec)).timestamp() * 1000)


def _p1(install_day: int) -> float:
    return 0.45 if install_day <= 6 else 0.25


def generate(seed: int = 42) -> list:
    rng = random.Random(seed)
    events: list = []
    users: list = []  # each: (user_id, install_day, active_days:set)

    uid_counter = 0
    for d in range(N_DAYS):
        for _ in range(INSTALL_PLAN[d]):
            uid = f"u{uid_counter:05d}"
            uid_counter += 1
            active = {d}
            if d + 1 <= N_DAYS - 1 and rng.random() < _p1(d):
                active.add(d + 1)
            if d + 3 <= N_DAYS - 1 and rng.random() < 0.20:
                active.add(d + 3)
            if d + 7 <= N_DAYS - 1 and rng.random() < 0.15:
                active.add(d + 7)
            users.append((uid, d, active))
            events.append({
                "event": "install", "game": GAME, "platform": PLATFORM,
                "country": COUNTRY, "user_id": uid, "session_id": None,
                "timestamp_ms": _ts(d, 0), "timestamp": "",
            })

    for uid, i, active in users:
        for d in sorted(active):
            # session
            events.append({
                "event": "session_start", "game": GAME, "platform": PLATFORM,
                "country": COUNTRY, "user_id": uid, "session_id": f"s_{uid}_{d}",
                "timestamp_ms": _ts(d, 60), "timestamp": "",
            })
            # ---- reward ads (drives ads_per_dau + eCPM/revenue anomalies) ----
            reward_per_user = 2 if d < 7 else 4
            rev_per_impr = 0.032 if d < (N_DAYS - 1) else 0.020  # last-day eCPM drop
            for k in range(reward_per_user):
                pl = "reward_01"
                events.append({"event": "ad_request", "game": GAME, "platform": PLATFORM,
                               "country": COUNTRY, "user_id": uid, "session_id": f"s_{uid}_{d}",
                               "timestamp_ms": _ts(d, 120 + k * 10), "timestamp": "",
                               "ad_format": "reward", "placement": pl, "network": "applovin"})
                events.append({"event": "ad_show", "game": GAME, "platform": PLATFORM,
                               "country": COUNTRY, "user_id": uid, "session_id": f"s_{uid}_{d}",
                               "timestamp_ms": _ts(d, 125 + k * 10), "timestamp": "",
                               "ad_format": "reward", "placement": pl, "network": "applovin"})
                events.append({"event": "ad_complete", "game": GAME, "platform": PLATFORM,
                               "country": COUNTRY, "user_id": uid, "session_id": f"s_{uid}_{d}",
                               "timestamp_ms": _ts(d, 130 + k * 10), "timestamp": "",
                               "ad_format": "reward", "placement": pl, "network": "applovin",
                               "completed": True})
                events.append({"event": "ad_revenue", "game": GAME, "platform": PLATFORM,
                               "country": COUNTRY, "user_id": uid, "session_id": f"s_{uid}_{d}",
                               "timestamp_ms": _ts(d, 135 + k * 10), "timestamp": "",
                               "ad_format": "reward", "placement": pl, "ad_unit": pl,
                               "network": "applovin", "revenue": rev_per_impr,
                               "ecpm": round(rev_per_impr * 1000, 2), "latency": 350 + k * 20})
            # ---- interstitial ads (drives fill-drop anomaly on last day) ----
            show_prob = 0.80 if d < (N_DAYS - 1) else 0.45
            pl = "inter_01"
            events.append({"event": "ad_request", "game": GAME, "platform": PLATFORM,
                           "country": COUNTRY, "user_id": uid, "session_id": f"s_{uid}_{d}",
                           "timestamp_ms": _ts(d, 200), "timestamp": "",
                           "ad_format": "interstitial", "placement": pl, "network": "applovin"})
            if rng.random() < show_prob:
                events.append({"event": "ad_show", "game": GAME, "platform": PLATFORM,
                               "country": COUNTRY, "user_id": uid, "session_id": f"s_{uid}_{d}",
                               "timestamp_ms": _ts(d, 205), "timestamp": "",
                               "ad_format": "interstitial", "placement": pl,
                               "network": "applovin"})
    return events


if __name__ == "__main__":
    evs = generate()
    print(f"generated {len(evs)} events")
