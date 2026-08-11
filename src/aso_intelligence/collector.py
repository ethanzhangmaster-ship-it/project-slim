"""
E16.6.1 — ASO Collector: data-source adapters & seams.

Bridges raw store data into the ASO reality layer (``ASOSnapshot`` /
``CompetitorSnapshot`` / reviews). All adapters are deterministic and purely
about *format conversion* — no analysis happens here.

Provided adapters:

* ``InMemoryASOSource``   — test / demo double (implements both ASODataSource
  and CompetitorProvider)
* ``ManualASOSource``     — feeds snapshots + reviews + competitors from a JSON
  file (the first-version "human drops the data" path)
* ``NullCompetitorProvider`` — the first-version competitor provider (no
  external data yet; future bridges plug into CompetitorProvider)
* ``PlayStoreMetricsAdapter`` — maps the E15.2 Play Reality ``StoreMetrics``
  feed into an ``ASOSnapshot`` (the real Google Play seam)

E16.6.1 depends one-way on E16.1 / E15.2 reality models only through loose
dict/attribute duck-typing, so no hard import cycle is introduced.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .models import (
    ASOSnapshot,
    CompetitorProvider,
    CompetitorSnapshot,
    ScreenshotFeature,
)


def _key(game_id: str, period: str) -> Tuple[str, str]:
    return (game_id, period)


# --------------------------------------------------------------------------- #
# In-memory double (tests / demos)
# --------------------------------------------------------------------------- #
class InMemoryASOSource:
    """Pure in-memory ASO data source + competitor provider.

    Implements both ``ASODataSource`` and ``CompetitorProvider`` so a single
    object can back a full analyze run in tests.
    """

    def __init__(
        self,
        snapshots: Optional[Dict[Tuple[str, str], ASOSnapshot]] = None,
        reviews: Optional[Dict[str, List[str]]] = None,
        competitors: Optional[Dict[Tuple[str, str], List[CompetitorSnapshot]]] = None,
    ):
        self._snapshots = dict(snapshots or {})
        self._reviews = dict(reviews or {})
        self._competitors = dict(competitors or {})

    def load_snapshot(self, game_id: str, period: str) -> ASOSnapshot:
        snap = self._snapshots.get(_key(game_id, period))
        if snap is None:
            raise KeyError(f"no snapshot for {game_id} @ {period}")
        return snap

    def load_reviews(self, game_id: str, limit: int = 1000) -> List[str]:
        revs = self._reviews.get(game_id, [])
        return revs[:limit]

    def load_competitors(
        self, game_id: str, period: str
    ) -> List[CompetitorSnapshot]:
        return list(self._competitors.get(_key(game_id, period), []))

    # convenience builders for tests
    def add_snapshot(self, snap: ASOSnapshot) -> None:
        self._snapshots[_key(snap.game_id, snap.date)] = snap

    def add_reviews(self, game_id: str, reviews: List[str]) -> None:
        self._reviews[game_id] = list(reviews)

    def add_competitors(
        self, game_id: str, period: str, comps: List[CompetitorSnapshot]
    ) -> None:
        self._competitors[_key(game_id, period)] = list(comps)


# --------------------------------------------------------------------------- #
# Manual JSON file source
# --------------------------------------------------------------------------- #
class ManualASOSource:
    """Feeds ASO reality from a JSON file.

    Expected layout::

        {
          "snapshots": {
            "<game_id>": {"<period>": { <ASOSnapshot fields> }, ...},
            ...
          },
          "reviews":    { "<game_id>": ["review text", ...], ... },
          "competitors":{
            "<game_id>": {"<period>": [ { <CompetitorSnapshot fields> }, ... ]}
          }
        }

    Missing sections are tolerated (empty). Screenshots/icon are rebuilt from
    the raw dict via ``_build_snapshot``.
    """

    def __init__(self, path: str):
        self.path = Path(path)
        self._data = self._load()

    def _load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8") or "{}")

    # ------------------------------------------------------------------ #
    @staticmethod
    def _build_snapshot(raw: Dict[str, Any]) -> ASOSnapshot:
        screenshots = [
            ScreenshotFeature(
                asset_id=s.get("asset_id", f"shot_{i}"),
                hook_strength=float(s.get("hook_strength", 0.0)),
                gameplay_clarity=float(s.get("gameplay_clarity", 0.0)),
                value_proposition=float(s.get("value_proposition", 0.0)),
                visual_density=float(s.get("visual_density", 0.0)),
                order=int(s.get("order", i)),
                notes=s.get("notes", ""),
            )
            for i, s in enumerate(raw.get("screenshots", []) or [])
        ]
        icon = raw.get("icon") or {}
        return ASOSnapshot(
            game_id=raw["game_id"],
            platform=raw.get("platform", "google_play"),
            date=raw["date"],
            store_visits=int(raw.get("store_visits", 0)),
            installs=int(raw.get("installs", 0)),
            conversion_rate=raw.get("conversion_rate"),
            rating=float(raw.get("rating", 0.0)),
            review_count=int(raw.get("review_count", 0)),
            ranking=raw.get("ranking"),
            title=raw.get("title", ""),
            short_description=raw.get("short_description", ""),
            keywords=list(raw.get("keywords", []) or []),
            screenshots=screenshots,
            icon=icon,
            extra=raw.get("extra", {}) or {},
        )

    def load_snapshot(self, game_id: str, period: str) -> ASOSnapshot:
        snap = (
            self._data.get("snapshots", {})
            .get(game_id, {})
            .get(period)
        )
        if snap is None:
            raise KeyError(f"no snapshot for {game_id} @ {period}")
        return self._build_snapshot(snap)

    def load_reviews(self, game_id: str, limit: int = 1000) -> List[str]:
        revs = self._data.get("reviews", {}).get(game_id, []) or []
        return revs[:limit]

    def load_competitors(
        self, game_id: str, period: str
    ) -> List[CompetitorSnapshot]:
        raw_list = (
            self._data.get("competitors", {})
            .get(game_id, {})
            .get(period, [])
            or []
        )
        return [
            CompetitorSnapshot(
                competitor_id=c["competitor_id"],
                game_id=game_id,
                date=period,
                ranking=c.get("ranking"),
                title=c.get("title", ""),
                keywords=list(c.get("keywords", []) or []),
                icon_changed=bool(c.get("icon_changed", False)),
                screenshot_changed=bool(c.get("screenshot_changed", False)),
            )
            for c in raw_list
        ]


# --------------------------------------------------------------------------- #
# Null competitor provider (first version)
# --------------------------------------------------------------------------- #
class NullCompetitorProvider:
    """No external competitor data yet.

    Future versions implement ``CompetitorProvider`` against Sensor Tower /
    data.ai / AppTweak / AppMagic. Returns an empty list so the rest of the
    pipeline runs unchanged.
    """

    def load_competitors(
        self, game_id: str, period: str
    ) -> List[CompetitorSnapshot]:
        return []


# --------------------------------------------------------------------------- #
# Play Store reality adapter (E15.2 seam)
# --------------------------------------------------------------------------- #
class PlayStoreMetricsAdapter:
    """Maps an E15.2 Play Reality ``StoreMetrics`` feed into ASOSnapshot.

    The Play Reality layer (``operation/publishing_factory/play_runtime/reality``)
    already collects store metrics per package. This adapter converts that dict
    (or attribute bag) into the ASO reality model without the ASO module knowing
    anything about the Play client internals.
    """

    def __init__(self, platform: str = "google_play"):
        self.platform = platform

    def to_snapshot(
        self,
        game_id: str,
        date: str,
        store_metrics: Any,
    ) -> ASOSnapshot:
        """``store_metrics`` may be a dict or an object exposing the fields."""
        if isinstance(store_metrics, dict):
            get = store_metrics.get
        else:
            get = lambda k, d=None: getattr(store_metrics, k, d)  # noqa: E731

        screenshots_raw = get("screenshots", []) or []
        screenshots = [
            ScreenshotFeature(
                asset_id=s.get("asset_id", f"shot_{i}"),
                hook_strength=float(s.get("hook_strength", 0.0)),
                gameplay_clarity=float(s.get("gameplay_clarity", 0.0)),
                value_proposition=float(s.get("value_proposition", 0.0)),
                visual_density=float(s.get("visual_density", 0.0)),
                order=int(s.get("order", i)),
            )
            for i, s in enumerate(screenshots_raw)
        ]
        return ASOSnapshot(
            game_id=game_id,
            platform=self.platform,
            date=date,
            store_visits=int(get("store_visits", 0) or 0),
            installs=int(get("installs", 0) or 0),
            conversion_rate=get("conversion_rate"),
            rating=float(get("rating", 0.0) or 0.0),
            review_count=int(get("review_count", 0) or 0),
            ranking=get("ranking"),
            title=get("title", "") or "",
            short_description=get("short_description", "") or "",
            keywords=list(get("keywords", []) or []),
            screenshots=screenshots,
            icon=get("icon") or {},
            extra=get("extra", {}) or {},
        )


__all__ = [
    "InMemoryASOSource",
    "ManualASOSource",
    "NullCompetitorProvider",
    "PlayStoreMetricsAdapter",
]
