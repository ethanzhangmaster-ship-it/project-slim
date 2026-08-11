"""
E15.1.1 — Product Profile
===========================

The atomic unit of the Publishing Factory: a GameProduct.

One GameProduct == one game on one-or-both stores, owned by the fleet
operator. The factory treats it as a manufacturing job: feed profile in,
get a PublishingPlan out.

Deterministic, no LLM. Plain dataclasses so they serialize to JSON for
the fleet registry on disk.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class GameStatus(str, Enum):
    """Lifecycle state of a game inside the factory."""
    DEVELOPMENT = "development"
    READY = "ready"            # build + metadata ready, not yet submitted
    SUBMITTED = "submitted"    # in store review
    PUBLISHED = "published"    # live
    REJECTED = "rejected"      # store bounced it
    ARCHIVED = "archived"


class Platform(str, Enum):
    GOOGLE_PLAY = "google_play"
    APP_STORE = "app_store"


class Genre(str, Enum):
    MERGE = "merge"
    PUZZLE = "puzzle"
    IDLE = "idle"
    WORD = "word"
    CASUAL = "casual"
    SIMULATION = "simulation"
    ACTION = "action"


class Monetization(str, Enum):
    IAA = "iaa"
    IAP = "iap"
    HYBRID = "hybrid"


# Default selling-point library per genre (deterministic seed copy).
_GENRE_SELLING_POINTS: Dict[str, List[str]] = {
    "merge": ["Combine", "Discover", "Build", "Explore"],
    "puzzle": ["Solve", "Train your brain", "Relax", "Master"],
    "idle": ["Automate", "Grow", "Upgrade", "Idle profits"],
    "word": ["Spell", "Learn", "Compete", "Expand vocabulary"],
    "casual": ["Tap", "Fun", "Easy", "Free"],
    "simulation": ["Build", "Manage", "Grow", "Tycoon"],
    "action": ["Battle", "Hero", "Epic", "Win"],
}


@dataclass
class GameProduct:
    """A single game in the fleet.

    `metrics` holds store performance signals used by the factory to
    decide ASO opportunities and by memory to learn what works.
    """
    game_id: str
    package_name: str = ""
    display_name: str = ""
    platforms: List[str] = field(default_factory=lambda: ["google_play"])
    genre: str = "casual"
    monetization: str = "iaa"
    status: str = "development"
    version: str = "1.0.0"
    build_number: int = 1
    # last published version (for "metadata outdated" detection)
    published_version: str = ""
    selling_points: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    locales: List[str] = field(default_factory=lambda: ["en-US"])
    # performance signals (may be empty until published)
    metrics: Dict[str, float] = field(default_factory=dict)
    # store rejection history: list of {store, code, reason, at}
    rejection_history: List[Dict[str, str]] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    # ------------------------------------------------------------------ #
    def default_selling_points(self) -> List[str]:
        if self.selling_points:
            return list(self.selling_points)
        return list(_GENRE_SELLING_POINTS.get(self.genre,
                                              _GENRE_SELLING_POINTS["casual"]))

    def is_published(self) -> bool:
        return self.status == GameStatus.PUBLISHED.value

    def needs_first_publish(self) -> bool:
        """Build exists but never submitted/published."""
        return self.status in (GameStatus.READY.value,
                               GameStatus.DEVELOPMENT.value)

    def metadata_outdated(self) -> bool:
        """Version moved past what was last published."""
        if not self.published_version:
            return False
        return self.version != self.published_version

    def to_dict(self) -> dict:
        return {
            "game_id": self.game_id,
            "package_name": self.package_name,
            "display_name": self.display_name,
            "platforms": list(self.platforms),
            "genre": self.genre,
            "monetization": self.monetization,
            "status": self.status,
            "version": self.version,
            "build_number": self.build_number,
            "published_version": self.published_version,
            "selling_points": list(self.selling_points),
            "keywords": list(self.keywords),
            "locales": list(self.locales),
            "metrics": dict(self.metrics),
            "rejection_history": [dict(r) for r in self.rejection_history],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "GameProduct":
        return cls(
            game_id=d["game_id"],
            package_name=d.get("package_name", ""),
            display_name=d.get("display_name", ""),
            platforms=list(d.get("platforms", ["google_play"])),
            genre=d.get("genre", "casual"),
            monetization=d.get("monetization", "iaa"),
            status=d.get("status", "development"),
            version=d.get("version", "1.0.0"),
            build_number=d.get("build_number", 1),
            published_version=d.get("published_version", ""),
            selling_points=list(d.get("selling_points", [])),
            keywords=list(d.get("keywords", [])),
            locales=list(d.get("locales", ["en-US"])),
            metrics=dict(d.get("metrics", {})),
            rejection_history=[dict(r) for r in d.get("rejection_history", [])],
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
        )


__all__ = [
    "GameStatus", "Platform", "Genre", "Monetization",
    "GameProduct", "_GENRE_SELLING_POINTS",
]
