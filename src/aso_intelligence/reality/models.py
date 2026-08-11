"""E16.6.2 — ASO Data Reality Layer: raw input models & data-quality gate.

The "data reality" for ASO: the unified, provider-agnostic *raw* capture of one
game's store presence at a point in time, plus the quality gate that scores how
trustworthy that capture is.

This layer is pure data + deterministic helpers — no I/O, no network, no LLM.
Provider implementations live in ``.providers``; the connector (``connector.py``)
merges them and the normalizer (``normalizer.py``) turns a raw
``ASORealitySnapshot`` into the analysis-ready ``ASOSnapshot`` (E16.6.1).

It deliberately mirrors E15.2's ``PlayRealitySnapshot`` shape (rate/raw fields +
``source`` provenance + append-only feature store) so ASO reality plugs into the
same Reality Layer the Release/Health agents already consume.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Platform(str, Enum):
    """A game's store platform. A single game_id may ship on both."""

    GOOGLE_PLAY = "google_play"
    APP_STORE = "app_store"


# --------------------------------------------------------------------------- #
# 1. Review record (raw player voice)
# --------------------------------------------------------------------------- #
@dataclass
class ReviewRecord:
    game_id: str
    platform: Platform
    rating: float  # 1.0–5.0
    text: str
    author: str = ""
    reviewed_at: Optional[datetime] = None
    source: str = "unknown"  # "google_play" / "app_store" / "fallback"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "platform": self.platform.value,
            "rating": round(self.rating, 2),
            "text": self.text,
            "author": self.author,
            "reviewed_at": self.reviewed_at.isoformat()
            if self.reviewed_at
            else None,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ReviewRecord":
        ts = d.get("reviewed_at")
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts)
            except ValueError:
                ts = None
        plat = d.get("platform", Platform.GOOGLE_PLAY.value)
        try:
            plat = Platform(plat)
        except ValueError:
            plat = Platform.GOOGLE_PLAY
        return cls(
            game_id=d.get("game_id", ""),
            platform=plat,
            rating=float(d.get("rating", 0.0)),
            text=d.get("text", ""),
            author=d.get("author", ""),
            reviewed_at=ts,
            source=d.get("source", "unknown"),
        )


# --------------------------------------------------------------------------- #
# 2. Keyword ranking (from external ASO tools, future)
# --------------------------------------------------------------------------- #
@dataclass
class KeywordRanking:
    keyword: str
    rank: Optional[int] = None  # store search rank (lower = better)
    volume: float = 0.0  # search volume 0.0–1.0
    difficulty: float = 0.0  # 0.0–1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "keyword": self.keyword,
            "rank": self.rank,
            "volume": round(self.volume, 4),
            "difficulty": round(self.difficulty, 4),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "KeywordRanking":
        return cls(
            keyword=d.get("keyword", ""),
            rank=d.get("rank"),
            volume=float(d.get("volume", 0.0)),
            difficulty=float(d.get("difficulty", 0.0)),
        )


# --------------------------------------------------------------------------- #
# 3. Raw reality snapshot — the unified Reality Layer input
# --------------------------------------------------------------------------- #
@dataclass
class ASORealitySnapshot:
    game_id: str
    platform: Platform
    timestamp: datetime = field(default_factory=_now)

    # --- Store funnel (Google Play / App Store / external ASO) ---
    impressions: Optional[int] = None  # times the listing was shown in search/browse
    product_page_views: Optional[int] = None  # times the store listing page opened
    installs: Optional[int] = None
    conversion_rate: Optional[float] = None  # installs / product_page_views

    # --- Ranking ---
    category_rank: Optional[int] = None
    keyword_rankings: List[KeywordRanking] = field(default_factory=list)

    # --- Store health ---
    rating: Optional[float] = None  # 0.0–5.0
    review_count: Optional[int] = None

    # --- Listing (raw assets — creative DNA deferred to E16.6.3) ---
    title: str = ""
    short_description: str = ""
    screenshots: List[str] = field(default_factory=list)  # raw URLs
    icon_url: str = ""

    # --- provenance + escape hatch ---
    source: str = "unknown"  # "google_play:live" / "app_store:unavailable" / "fallback"
    extra: Dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------ #
    def is_empty(self) -> bool:
        """True when this shell carries no real signal (fallback / unavailable)."""
        if self.source in ("fallback", "unavailable"):
            # a fallback shell is still "something" if it has hard metrics
            return self.installs is None and self.rating is None
        return (
            self.installs is None
            and self.rating is None
            and self.review_count is None
            and self.product_page_views is None
            and self.impressions is None
            and not self.title
            and self.category_rank is None
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "platform": self.platform.value,
            "timestamp": self.timestamp.isoformat(),
            "impressions": self.impressions,
            "product_page_views": self.product_page_views,
            "installs": self.installs,
            "conversion_rate": self.conversion_rate,
            "category_rank": self.category_rank,
            "keyword_rankings": [k.to_dict() for k in self.keyword_rankings],
            "rating": self.rating,
            "review_count": self.review_count,
            "title": self.title,
            "short_description": self.short_description,
            "screenshots": list(self.screenshots),
            "icon_url": self.icon_url,
            "source": self.source,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ASORealitySnapshot":
        ts = d.get("timestamp")
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts)
            except ValueError:
                ts = _now()
        else:
            ts = _now()
        plat = d.get("platform", Platform.GOOGLE_PLAY.value)
        try:
            plat = Platform(plat)
        except ValueError:
            plat = Platform.GOOGLE_PLAY
        return cls(
            game_id=d.get("game_id", ""),
            platform=plat,
            timestamp=ts,
            impressions=d.get("impressions"),
            product_page_views=d.get("product_page_views"),
            installs=d.get("installs"),
            conversion_rate=d.get("conversion_rate"),
            category_rank=d.get("category_rank"),
            keyword_rankings=[
                KeywordRanking.from_dict(k)
                for k in (d.get("keyword_rankings") or [])
            ],
            rating=d.get("rating"),
            review_count=d.get("review_count"),
            title=d.get("title", ""),
            short_description=d.get("short_description", ""),
            screenshots=list(d.get("screenshots") or []),
            icon_url=d.get("icon_url", ""),
            source=d.get("source", "unknown"),
            extra=d.get("extra") or {},
        )


# --------------------------------------------------------------------------- #
# 4. Data quality gate (missing / stale / anomaly -> confidence)
# --------------------------------------------------------------------------- #
class ASODataQualityFlag(str, Enum):
    OK = "ok"
    MISSING_FIELDS = "missing_fields"
    STALE_DATA = "stale_data"
    ANOMALY = "anomaly"


@dataclass
class ASODataQuality:
    snapshot_timestamp: datetime
    flags: List[ASODataQualityFlag] = field(default_factory=list)
    missing_fields: List[str] = field(default_factory=list)
    is_stale: bool = False
    is_anomaly: bool = False
    anomaly_fields: List[str] = field(default_factory=list)
    confidence: float = 1.0  # adjusted data-trust, 0.0–1.0
    notes: str = ""

    @property
    def status(self) -> ASODataQualityFlag:
        """Priority: anomaly > stale > missing > ok."""
        if self.is_anomaly:
            return ASODataQualityFlag.ANOMALY
        if self.is_stale:
            return ASODataQualityFlag.STALE_DATA
        if ASODataQualityFlag.MISSING_FIELDS in self.flags:
            return ASODataQualityFlag.MISSING_FIELDS
        return ASODataQualityFlag.OK

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_timestamp": self.snapshot_timestamp.isoformat(),
            "flags": [f.value for f in self.flags],
            "missing_fields": list(self.missing_fields),
            "is_stale": self.is_stale,
            "is_anomaly": self.is_anomaly,
            "anomaly_fields": list(self.anomaly_fields),
            "confidence": round(self.confidence, 4),
            "status": self.status.value,
            "notes": self.notes,
        }

    @classmethod
    def from_snapshot(
        cls,
        snap: "ASORealitySnapshot",
        previous: Optional["ASORealitySnapshot"] = None,
        *,
        now: Optional[datetime] = None,
        stale_days: int = 30,
        anomaly_factor: float = 10.0,
        required_fields: tuple = ("installs", "rating", "review_count"),
    ) -> "ASODataQuality":
        """Score how trustworthy ``snap`` is.

        * MISSING_FIELDS — any field in ``required_fields`` is None.
        * STALE_DATA     — ``snap`` is older than ``stale_days``.
        * ANOMALY        — a core metric swung >= ``anomaly_factor`` vs ``previous``
                          (e.g. installs 100 -> 1_000_000).
        Confidence is a multiplicative penalty (1.0 healthy, floor ~0.08).
        """
        now = now or _now()
        flags: List[ASODataQualityFlag] = []

        missing = [f for f in required_fields if getattr(snap, f, None) is None]
        if missing:
            flags.append(ASODataQualityFlag.MISSING_FIELDS)

        is_stale = (now - snap.timestamp).days > stale_days
        if is_stale:
            flags.append(ASODataQualityFlag.STALE_DATA)

        anomaly_fields: List[str] = []
        if previous is not None:
            for f in ("installs", "product_page_views"):
                cur = getattr(snap, f, None)
                prev = getattr(previous, f, None)
                if cur is not None and prev is not None and prev > 0:
                    ratio = cur / prev
                    if ratio >= anomaly_factor or ratio <= (1.0 / anomaly_factor):
                        anomaly_fields.append(f)
        is_anomaly = bool(anomaly_fields)
        if is_anomaly:
            flags.append(ASODataQualityFlag.ANOMALY)

        conf = 1.0
        if missing:
            conf *= max(0.4, 1.0 - 0.15 * len(missing))
        if is_stale:
            conf *= 0.5
        if is_anomaly:
            conf *= 0.4
        conf = round(min(1.0, max(0.0, conf)), 4)

        notes: List[str] = []
        if missing:
            notes.append(f"missing: {', '.join(missing)}")
        if is_stale:
            notes.append(f"stale >{stale_days}d")
        if anomaly_fields:
            notes.append(f"anomaly: {', '.join(anomaly_fields)}")

        return cls(
            snapshot_timestamp=snap.timestamp,
            flags=flags,
            missing_fields=missing,
            is_stale=is_stale,
            is_anomaly=is_anomaly,
            anomaly_fields=anomaly_fields,
            confidence=conf,
            notes="; ".join(notes),
        )


__all__ = [
    "Platform",
    "ReviewRecord",
    "KeywordRanking",
    "ASORealitySnapshot",
    "ASODataQuality",
    "ASODataQualityFlag",
]
