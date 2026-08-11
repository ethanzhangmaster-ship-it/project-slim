"""
E16.6.1 — ASO Intelligence Agent: data models & integration seams.

The "AI ASO Growth Agent": through store data, competitors, creative
understanding and revenue feedback, automatically discover ASO growth
opportunities.

This module is the contract layer (pure data, no I/O, no side effects):

* ``ASOSnapshot`` / ``KeywordRecord`` / ``ListingAsset`` / ``ScreenshotFeature``
  — the store & asset reality for one game/period
* ``ASOInsight`` / ``ASOInsightType`` — the "what's wrong / what's missing"
* ``ASOAction`` — the 7 executor-ready ASO moves (→ E13.3 Growth Executor)
* ``CompetitorSnapshot`` / ``CompetitorProvider`` — competitor intelligence seam
* ``ASOReport`` — the unified output

E16.6.1 depends ONE-WAY on E16.1 (``revenue_intelligence``): every ASO move is
emitted as a standard ``GrowthAction`` whose ``action`` field carries an
``ASOAction`` enum member, so it routes through the same Decision Validator /
Growth Executor pipeline as the Revenue Brain (E16.1) and Economy Brain (E16.2).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from src.revenue_intelligence.models import (
    GrowthAction,
    register_action_enum,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# 1. Enums
# --------------------------------------------------------------------------- #
class ASOInsightType(str, Enum):
    """The category of an ASO problem / opportunity."""

    LISTING_CONVERSION_DROP = "listing_conversion_drop"
    LISTING_FATIGUE = "listing_fatigue"
    MISSING_KEYWORD = "missing_keyword"
    KEYWORD_OPPORTUNITY = "keyword_opportunity"
    REVIEW_KEYWORD_SIGNAL = "review_keyword_signal"
    SCREENSHOT_WEAK = "screenshot_weak"
    ICON_OPTIMIZATION = "icon_optimization"
    COMPETITOR_CHANGE = "competitor_change"


class ASOAction(str, Enum):
    """The 7 executor-ready ASO moves.

    Each is a candidate ``GrowthAction.action`` value. The ASO Agent never
    executes these itself — it only emits them into the Growth Decision Layer.
    """

    UPDATE_TITLE = "aso_update_title"
    UPDATE_DESCRIPTION = "aso_update_description"
    UPDATE_SCREENSHOT = "aso_update_screenshot"
    UPDATE_ICON = "aso_update_icon"
    ADD_KEYWORD = "aso_add_keyword"
    REMOVE_KEYWORD = "aso_remove_keyword"
    CREATE_EXPERIMENT = "aso_create_experiment"


# Register with E16.1 so GrowthAction.from_dict / JsonlPatternMemory can
# round-trip ASO actions through the shared JSONL stores.
register_action_enum(ASOAction)


# --------------------------------------------------------------------------- #
# 2. Facts — store & asset reality
# --------------------------------------------------------------------------- #
@dataclass
class KeywordRecord:
    """One keyword's discoverability state for a game."""

    keyword: str
    rank: Optional[int] = None  # store rank for this keyword (lower = better)
    volume: float = 0.0  # search volume (0.0–1.0 normalized, or absolute)
    competition: float = 0.0  # 0.0–1.0
    difficulty: float = 0.0  # 0.0–1.0
    conversion_value: float = 0.0  # estimated CVR contribution (0.0–1.0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "keyword": self.keyword,
            "rank": self.rank,
            "volume": round(self.volume, 4),
            "competition": round(self.competition, 4),
            "difficulty": round(self.difficulty, 4),
            "conversion_value": round(self.conversion_value, 4),
        }


@dataclass
class ScreenshotFeature:
    """Creative DNA features extracted from one store screenshot.

    Reuses the E11 Creative DNA vision vocabulary (hook / clarity / value /
    density). Scores are 0.0–1.0.
    """

    asset_id: str
    hook_strength: float = 0.0  # does it stop the scroll?
    gameplay_clarity: float = 0.0  # is the core loop obvious?
    value_proposition: float = 0.0  # is the promise clear?
    visual_density: float = 0.0  # too busy / too empty?
    order: int = 0
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "hook_strength": round(self.hook_strength, 4),
            "gameplay_clarity": round(self.gameplay_clarity, 4),
            "value_proposition": round(self.value_proposition, 4),
            "visual_density": round(self.visual_density, 4),
            "order": self.order,
            "notes": self.notes,
        }


@dataclass
class ListingAsset:
    """One piece of store listing creative.

    ``asset_type`` is one of: ``icon`` / ``screenshot`` / ``video`` /
    ``description``. Only the matching field carries payload.
    """

    asset_type: str
    icon: Optional[Dict[str, Any]] = None  # {"focal_strength", "face_area_ratio"}
    screenshot: Optional[ScreenshotFeature] = None
    video: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    version: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_type": self.asset_type,
            "icon": self.icon,
            "screenshot": self.screenshot.to_dict() if self.screenshot else None,
            "video": self.video,
            "description": self.description,
            "version": self.version,
        }


@dataclass
class ASOSnapshot:
    """One period of App Store Optimization reality for a single game.

    Carries both the store traffic facts (visits / installs / CVR), the listing
    assets (title / description / keywords / icon / screenshots), and the store
    health signals (rating / review_count / category ranking).
    """

    game_id: str
    platform: str  # "google_play" | "app_store"
    date: str  # period label, e.g. "2026-07-28"

    # --- store traffic & conversion ---
    store_visits: int = 0
    installs: int = 0
    conversion_rate: Optional[float] = None  # installs / store_visits (if precomputed)

    # --- store health ---
    rating: float = 0.0  # 0.0–5.0
    review_count: int = 0
    ranking: Optional[int] = None  # category rank (lower = better)

    # --- listing assets (text) ---
    title: str = ""
    short_description: str = ""
    keywords: List[str] = field(default_factory=list)

    # --- listing assets (creative) ---
    screenshots: List[ScreenshotFeature] = field(default_factory=list)
    icon: Dict[str, Any] = field(default_factory=dict)

    extra: Dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------ #
    def computed_cvr(self) -> float:
        """CVR = installs / store_visits (0.0 if no visits)."""
        if self.store_visits <= 0:
            return 0.0
        return self.installs / self.store_visits

    def cvr(self) -> float:
        return (
            self.conversion_rate
            if self.conversion_rate is not None
            else self.computed_cvr()
        )

    def title_tokens(self) -> List[str]:
        return [t.strip().lower() for t in self.title.replace(",", " ").split() if t.strip()]

    def description_tokens(self) -> List[str]:
        text = f"{self.title} {self.short_description}"
        return [t.strip().lower() for t in text.replace(",", " ").split() if t.strip()]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "platform": self.platform,
            "date": self.date,
            "store_visits": self.store_visits,
            "installs": self.installs,
            "conversion_rate": self.conversion_rate,
            "computed_cvr": round(self.computed_cvr(), 4),
            "rating": round(self.rating, 4),
            "review_count": self.review_count,
            "ranking": self.ranking,
            "title": self.title,
            "short_description": self.short_description,
            "keywords": list(self.keywords),
            "screenshots": [s.to_dict() for s in self.screenshots],
            "icon": self.icon,
            "extra": self.extra,
        }


# --------------------------------------------------------------------------- #
# 3. Competitor intelligence
# --------------------------------------------------------------------------- #
@dataclass
class CompetitorSnapshot:
    """One competitor's store state at a point in time."""

    competitor_id: str
    game_id: str  # the game this competitor is measured against
    date: str
    ranking: Optional[int] = None  # their category rank (lower = better)
    previous_ranking: Optional[int] = None  # rank in the prior period
    title: str = ""
    keywords: List[str] = field(default_factory=list)
    icon_changed: bool = False
    screenshot_changed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "competitor_id": self.competitor_id,
            "game_id": self.game_id,
            "date": self.date,
            "ranking": self.ranking,
            "previous_ranking": self.previous_ranking,
            "title": self.title,
            "keywords": list(self.keywords),
            "icon_changed": self.icon_changed,
            "screenshot_changed": self.screenshot_changed,
        }


# --------------------------------------------------------------------------- #
# 4. Insights
# --------------------------------------------------------------------------- #
@dataclass
class ASOInsight:
    """A single explained ASO observation (the "what's wrong / missing")."""

    game_id: str
    insight_type: ASOInsightType
    description: str
    recommendation: str = ""  # human-readable next step
    evidence: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0  # 0.0–1.0
    impact_score: float = 0.0  # 0.0–100.0 (business materiality)
    generated_at: datetime = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "insight_type": self.insight_type.value,
            "description": self.description,
            "recommendation": self.recommendation,
            "evidence": self.evidence,
            "confidence": round(self.confidence, 4),
            "impact_score": round(self.impact_score, 2),
            "generated_at": self.generated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ASOInsight":
        ts = d.get("generated_at")
        if ts:
            try:
                ts = datetime.fromisoformat(ts)
            except Exception:
                ts = _now()
        else:
            ts = _now()
        it = d.get("insight_type")
        try:
            it = ASOInsightType(it)
        except (ValueError, TypeError):
            it = ASOInsightType.LISTING_CONVERSION_DROP
        return cls(
            game_id=d["game_id"],
            insight_type=it,
            description=d.get("description", ""),
            recommendation=d.get("recommendation", ""),
            evidence=d.get("evidence", {}),
            confidence=float(d.get("confidence", 0.0)),
            impact_score=float(d.get("impact_score", 0.0)),
            generated_at=ts,
        )


# --------------------------------------------------------------------------- #
# 5. Report
# --------------------------------------------------------------------------- #
@dataclass
class ASOReport:
    """Unified output of one ASO Intelligence run."""

    game_id: str
    current_date: str
    previous_date: str
    platform: str = "google_play"
    generated_at: datetime = field(default_factory=_now)
    insights: List[ASOInsight] = field(default_factory=list)
    actions: List[GrowthAction] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "current_date": self.current_date,
            "previous_date": self.previous_date,
            "platform": self.platform,
            "generated_at": self.generated_at.isoformat(),
            "insights": [i.to_dict() for i in self.insights],
            "actions": [a.to_dict() for a in self.actions],
            "summary": self.summary,
        }

    def to_markdown(self) -> str:
        lines = [
            f"# ASO Intelligence — {self.game_id}",
            f"Period: {self.previous_date} → {self.current_date} ({self.platform})",
            "",
        ]
        if self.summary:
            lines += [self.summary, ""]
        if self.insights:
            lines.append("## Insights")
            for i in self.insights:
                lines.append(
                    f"- [{i.insight_type.value}] {i.description} "
                    f"(conf {i.confidence:.0%}, impact {i.impact_score:.0f})"
                )
            lines.append("")
        if self.actions:
            lines.append("## Recommended ASO Actions")
            for a in self.actions:
                lines.append(
                    f"- {getattr(a.action, 'value', a.action)}: {a.title}"
                )
            lines.append("")
        return "\n".join(lines)


# --------------------------------------------------------------------------- #
# 6. Integration seams (Protocols) — no hard dependencies
# --------------------------------------------------------------------------- #
@runtime_checkable
class ASODataSource(Protocol):
    """Supplies ASO facts (snapshot + reviews) for a game."""

    def load_snapshot(self, game_id: str, period: str) -> ASOSnapshot:
        ...

    def load_reviews(self, game_id: str, limit: int = 1000) -> List[str]:
        ...


@runtime_checkable
class CompetitorProvider(Protocol):
    """Supplies competitor store state. First version: Null implementation;
    future versions bridge Sensor Tower / data.ai / AppTweak / AppMagic."""

    def load_competitors(
        self, game_id: str, period: str
    ) -> List[CompetitorSnapshot]:
        ...


__all__ = [
    "ASOInsightType",
    "ASOAction",
    "KeywordRecord",
    "ScreenshotFeature",
    "ListingAsset",
    "ASOSnapshot",
    "CompetitorSnapshot",
    "ASOInsight",
    "ASOReport",
    "ASODataSource",
    "CompetitorProvider",
]
