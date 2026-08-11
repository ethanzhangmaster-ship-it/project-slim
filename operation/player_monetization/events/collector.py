"""
E15.2.7 §1 — Event collector.

Ingests player, ad, and game events and aggregates them into PlayerProfile
objects for downstream models. The collector is provider-agnostic:

  * SDKProvider       — Unity SDK stub (returns nothing; placeholder for real)
  * AdjustProvider    — uses existing Adjust KPI to get country-level DAU as
                        a crude aggregate proxy (not per-user)
  * SyntheticProvider — produces deterministic synthetic events for tests

No LLM, no external calls beyond the existing Adjust client.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
import json, os

from operation.player_monetization.models import AdEvent, GameEvent, PlayerEvent, PlayerProfile

EventList = List[Dict[str, Any]]


class SDKProvider:
    """Unity SDK event stream. Reads the JSONL sink that the Lean ingest receiver
    (operation.player_monetization.ingest_server) writes from the game's
    RemoteEventUploader. When no events have arrived yet, returns [] (the game
    hasn't sent anything) — never raises, so the collector degrades gracefully."""

    @staticmethod
    def _sink_path(app_id: str) -> str:
        safe = "".join(c if (c.isalnum() or c in "_.-") else "_" for c in (app_id or "default"))
        os.makedirs("data/player_events", exist_ok=True)
        return os.path.join("data/player_events", (safe or "default") + ".jsonl")

    def fetch(self, start: str, end: str,
              app_id: str = "") -> EventList:
        return FileEventReceiver(self._sink_path(app_id)).fetch(start, end, app_id)


class SyntheticProvider:
    """Deterministic event generator for tests. Call build_events() with
    a list of user profiles to get corresponding raw event dicts."""

    @staticmethod
    def one_user(user_id: str, country: str = "US", level: int = 10,
                 sessions: int = 5, play_sec: int = 900,
                 ad_requests: int = 20, ad_shows: int = 15,
                 ad_revenue: float = 0.5) -> EventList:
        out: EventList = []
        for s in range(1, sessions + 1):
            t = f"2026-07-{20 + s:02d}"
            out.append({"type": "player", "user_id": user_id,
                        "country": country, "level": level + s,
                        "session_count": s,
                        "play_time_sec": play_sec // sessions,
                        "timestamp": t})
            for a in range(ad_requests // sessions):
                out.append({"type": "ad", "user_id": user_id,
                            "ad_type": "reward", "request": True,
                            "show": a < (ad_shows // sessions),
                            "complete": a < (ad_shows // sessions),
                            "revenue": round(ad_revenue / ad_requests, 4),
                            "timestamp": t})
            out.append({"type": "game", "user_id": user_id,
                        "level_start": level + s,
                        "level_fail": 1 if s % 3 == 0 else 0,
                        "level_complete": s % 3 != 0,
                        "fail_streak": 1 if s % 3 == 0 else 0,
                        "timestamp": t})
        return out

    @classmethod
    def cohort(cls, user_ids: List[str], country: str = "US",
               levels: Optional[List[int]] = None) -> EventList:
        all_ev: EventList = []
        if levels is None:
            levels = [10] * len(user_ids)
        for uid, lv in zip(user_ids, levels):
            all_ev.extend(cls.one_user(uid, country, lv))
        return all_ev


class EventCollector:
    """Aggregates raw events into PlayerProfile objects."""

    def __init__(self, provider=None) -> None:
        self.provider = provider or SDKProvider()

    def collect(self, app_id: str = "", start: str = "",
                end: str = "") -> List[PlayerProfile]:
        events = self.provider.fetch(start, end, app_id)
        return self._aggregate(events)

    @staticmethod
    def _aggregate(events: EventList) -> List[PlayerProfile]:
        by_user: Dict[str, Dict[str, Any]] = {}
        for e in events:
            uid = e.get("user_id", "")
            if not uid:
                continue
            if uid not in by_user:
                by_user[uid] = {"country": e.get("country", ""),
                                "max_level": 0, "sessions": set(),
                                "play_sec": 0, "ad_req": 0, "ad_show": 0,
                                "ad_comp": 0, "ad_rev": 0.0,
                                "reward_req": 0, "reward_show": 0,
                                "fails": 0, "levels": 0, "days": set(),
                                "active": False}
            rec = by_user[uid]
            tp = e.get("type", "")
            if tp == "player":
                c = e.get("country", "")
                if c:
                    rec["country"] = c
                rec["max_level"] = max(rec["max_level"], e.get("level", 0))
                rec["play_sec"] += e.get("play_time_sec", 0)
                rec["sessions"].add(e.get("session_count", 0))
                rec["days"].add(e.get("timestamp", "")[:10])
                rec["active"] = True
            elif tp == "ad":
                rec["ad_req"] += 1
                if e.get("show"):
                    rec["ad_show"] += 1
                if e.get("complete"):
                    rec["ad_comp"] += 1
                rec["ad_rev"] += float(e.get("revenue", 0) or 0)
                if e.get("ad_type") == "reward":
                    rec["reward_req"] += 1
                    if e.get("show"):
                        rec["reward_show"] += 1
            elif tp == "game":
                rec["fails"] += e.get("level_fail", 0)
                rec["levels"] += 1
                rec["days"].add(e.get("timestamp", "")[:10])
        profiles: List[PlayerProfile] = []
        for uid, r in by_user.items():
            sess = max(len(r["sessions"]), 1)
            rr = r["reward_req"]
            profiles.append(PlayerProfile(
                user_id=uid, country=r["country"], level=r["max_level"],
                session_count=sess,
                total_play_time_sec=r["play_sec"],
                total_ad_requests=r["ad_req"],
                total_ad_shows=r["ad_show"],
                total_ad_completions=r["ad_comp"],
                total_ad_revenue=round(r["ad_rev"], 4),
                reward_accept_rate=round(r["reward_show"] / rr, 4) if rr else 0.0,
                avg_session_sec=round(r["play_sec"] / sess, 1) if sess else 0.0,
                fail_rate=round(r["fails"] / r["levels"], 4) if r["levels"] else 0.0,
                days_active=len(r["days"]),
                active=r["active"]))
        return profiles


class FileEventReceiver:
    """Reads events from a JSONL file (one event per line). Use when the
    Unity SDK writes to a shared volume / local file instead of HTTP."""

    def __init__(self, path: str) -> None:
        self.path = path

    def fetch(self, start: str = "", end: str = "",
              app_id: str = "") -> EventList:
        if not os.path.exists(self.path):
            return []
        events: EventList = []
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line: continue
                try:
                    events.append(json.loads(line))
                except (json.JSONDecodeError, ValueError):
                    continue
        return events
