"""
E15.1.2 — Public-chart market-opportunity source (REAL data, no auth)
======================================================================

A real, zero-credential scraper that turns public app-store top-charts
into ``MarketOpportunity`` records for the Growth intake drop-in
(``data/market_opportunities.json``).

Default provider — **Apple App Store top-free *Games* charts** via the
official, key-free Apple Marketing Tools RSS feed:

    https://rss.applemarketingtools.com/api/v2/{geo}/apps/
        top-free/{limit}/genre=6014/json

Why this feed and not others:
  * It is the only major storefront chart that is (a) free,
    (b) requires NO API key, (c) returns plain JSON, (d) is not behind
    aggressive anti-bot/HTML scraping. Google Play's equivalent needs a
    session token + HTML parsing, which we deliberately avoid.
  * ``genre=6014`` restricts to Games; we then map each app's sub-genre
    and title keywords onto our brain's (genre, theme) taxonomy.

Execution / safety model (same as the rest of the brain):
  * Deterministic, no LLM.
  * ``fetch()`` NEVER raises — any network/parse failure degrades to [].
  * **Live-first, cache-fallback.** A successful live fetch is written to
    ``data/_cache/apple_topfree_<geo>.json``; if the network is down the
    next run falls back to that cache so the daily scheduler keeps
    producing signal. Provenance is reported honestly in ``status()``
    and in each record's ``notes`` ([CHART] = live, [CHART-CACHE] = cache).
  * eCPM / LTV are *genre-median priors* (transparent table below), meant
    to be corroborated downstream by live MAX eCPM via FleetBridge — they
    are NOT measurements, and the notes say so.
"""
from __future__ import annotations

import json
import os
import re
from typing import Callable, Dict, List, Optional, Tuple

from .base import MarketSource
from operation.factory_brain.models import MarketOpportunity

DEFAULT_CACHE_DIR = "data/_cache"
DEFAULT_GEOS = ("us", "gb", "jp", "de")
DEFAULT_LIMIT = 200          # Apple RSS max is 200

# Apple sub-genre name -> our brain genre. First match in an app's
# `genres` list wins (most specific sub-genre appears alongside "Games").
APPLE_GENRE_MAP: Dict[str, str] = {
    "Puzzle": "puzzle",
    "Word": "word",
    "Trivia": "word",
    "Casual": "sort",
    "Arcade": "sort",
    "Simulation": "idle",
    "Strategy": "idle",
    "Board": "match",
    "Entertainment": "match",
    "Adventure": "merge",
    "Role Playing": "merge",
}

# Title keyword -> theme. Scanned in order; first hit wins.
THEME_KEYWORDS: List[Tuple[str, str]] = [
    ("merge", "merge"),
    ("word", "word"), ("wordle", "word"),
    ("puzzle", "puzzle"),
    ("sort", "sort"), ("color", "sort"), ("water", "sort"), ("tile", "sort"),
    ("cook", "cooking"), ("restaurant", "cooking"), ("food", "cooking"),
    ("kitchen", "cooking"), ("pizza", "cooking"),
    ("match", "match"), ("blast", "match"), ("candy", "match"),
    ("crush", "match"),
    ("draw", "draw"), ("paint", "draw"),
    ("idle", "idle"), ("tycoon", "idle"), ("clicker", "idle"),
    ("empire", "idle"),
]

# Genre-median eCPM prior (0..1), aligned with our real MAX blended eCPM
# knowledge (merge ~0.80, word ~0.70, puzzle ~0.65, idle ~0.60,
# sort ~0.70, draw ~0.60, cooking ~0.62, match ~0.55). PRIOR only.
ECPM_PRIOR: Dict[str, float] = {
    "merge": 0.80, "word": 0.70, "puzzle": 0.65, "idle": 0.60,
    "sort": 0.70, "draw": 0.60, "cooking": 0.62, "match": 0.55,
    "casual": 0.65,
}


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def map_genre(apple_genres: List[str]) -> str:
    """Map an Apple `genres` list to our brain genre (default 'casual')."""
    for g in apple_genres or []:
        if g in APPLE_GENRE_MAP:
            return APPLE_GENRE_MAP[g]
    return "casual"


def derive_theme(title: str) -> str:
    """Extract a theme token from an app title via curated keywords."""
    low = (title or "").lower()
    for kw, theme in THEME_KEYWORDS:
        if kw in low:
            return theme
    # fallback: first meaningful word of the title
    words = re.findall(r"[a-z0-9]+", low)
    stop = {"the", "a", "an", "of", "and", "to", "in", "my", "go", "play"}
    for w in words:
        if w not in stop and len(w) > 2:
            return w
    return "casual"


def build_record(app: dict, geo: str, rank: int, total: int,
                 live: bool) -> Optional[MarketOpportunity]:
    """Turn one Apple RSS app dict into a MarketOpportunity (or None)."""
    name = (app.get("name") or "").strip()
    if not name:
        return None
    genres = app.get("genres") or []
    genre = map_genre(genres)
    theme = derive_theme(name)
    if not theme:
        return None

    # rank-based trend: #1 -> 1.0, last -> 1/total
    trend = _clamp((total - rank + 1) / max(total, 1))
    ecpm = ECPM_PRIOR.get(genre, 0.6)
    ltv = _clamp(0.5 * trend + 0.5 * ecpm)

    provenance = "CHART" if live else "CHART-CACHE"
    notes = (f"[{provenance}] Apple top-free Games {geo.upper()} "
             f"#{rank} {name} (genre={genre})")
    return MarketOpportunity(
        opportunity_id=f"chart_{geo}_{genre}_{theme}",
        genre=genre,
        theme=theme,
        source="public_chart",
        target_geos=[geo.upper()],
        keyword_trend=round(trend, 4),
        competition=0.5,          # refined by caller (per-genre share)
        ecpm_signal=round(ecpm, 4),
        ltv_forecast=round(ltv, 4),
        notes=notes,
    )


class AppleTopFreeSource(MarketSource):
    """Real, no-auth public-chart scraper (Apple top-free Games RSS).

    Safe by construction: ``fetch()`` swallows every fault and returns [].
    A live fetch that succeeds is cached so subsequent offline runs still
    yield signal.
    """
    name = "public_chart_apple"
    kind = "real"

    def __init__(self, geos: Tuple[str, ...] = DEFAULT_GEOS,
                 limit: int = DEFAULT_LIMIT,
                 cache_dir: str = DEFAULT_CACHE_DIR,
                 client: Optional[Callable[[str], dict]] = None) -> None:
        self.geos = tuple(geos)
        self.limit = int(limit)
        self.cache_dir = cache_dir
        self._client = client          # injectable transport (offline tests)

    # ------------------------------------------------------------------ #
    def _url(self, geo: str) -> str:
        return (f"https://rss.applemarketingtools.com/api/v2/{geo}/apps/"
                f"top-free/{self.limit}/genre=6014/json")

    def _cache_path(self, geo: str) -> str:
        return os.path.join(self.cache_dir,
                            f"apple_topfree_{geo}.json")

    def _http_get(self, geo: str) -> dict:
        import urllib.request
        req = urllib.request.Request(
            self._url(geo),
            headers={"User-Agent": "Mozilla/5.0 (LaunchForge growth intake)"})
        with urllib.request.urlopen(req, timeout=12) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))

    def _read_cache(self, geo: str) -> Optional[dict]:
        p = self._cache_path(geo)
        if not os.path.exists(p):
            return None
        try:
            with open(p, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return None

    def _write_cache(self, geo: str, payload: dict) -> None:
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
            with open(self._cache_path(geo), "w", encoding="utf-8") as fh:
                json.dump(payload, fh)
        except OSError:
            pass

    # ------------------------------------------------------------------ #
    def status(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "kind": self.kind,
            "configured": True,
            "geos": list(self.geos),
            "endpoint": self._url(self.geos[0]) if self.geos else "",
            "note": "live-first; falls back to data/_cache on network failure",
        }

    def fetch_raw(self) -> List[dict]:
        """Return raw Apple RSS app dicts across all geos.

        Each raw item is wrapped with ``_geo`` / ``_rank`` / ``_live`` so
        ``normalize`` can reconstruct provenance. Never raises.
        """
        raw: List[dict] = []
        for geo in self.geos:
            payload = None
            live = False
            try:
                payload = (self._client(geo) if self._client
                           else self._http_get(geo))
                if payload:
                    live = True
                    self._write_cache(geo, payload)
            except Exception:              # noqa: BLE001 — network fault
                payload = self._read_cache(geo)
            if not isinstance(payload, dict):
                continue
            results = (payload.get("feed") or {}).get("results") or []
            total = len(results)
            for i, app in enumerate(results, 1):
                if not isinstance(app, dict):
                    continue
                app = dict(app)
                app["_geo"] = geo
                app["_rank"] = i
                app["_total"] = total
                app["_live"] = live
                raw.append(app)
        return raw

    def normalize(self, raw: List[dict]) -> List[MarketOpportunity]:
        out: List[MarketOpportunity] = []
        # per-genre competition = share of top-N apps in that genre
        genre_counts: Dict[str, int] = {}
        for r in raw:
            g = map_genre(r.get("genres") or [])
            genre_counts[g] = genre_counts.get(g, 0) + 1
        for r in raw:
            rec = build_record(
                r, r.get("_geo", "us"), int(r.get("_rank", 1)),
                int(r.get("_total", 1)), bool(r.get("_live", False)))
            if rec is None:
                continue
            total = int(r.get("_total", 1))
            share = (genre_counts.get(rec.genre, 1) / max(total, 1))
            rec.competition = round(_clamp(share), 4)
            out.append(rec)
        return out


__all__ = ["AppleTopFreeSource", "map_genre", "derive_theme",
           "build_record", "ECPM_PRIOR"]
