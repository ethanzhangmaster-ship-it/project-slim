"""
E15.1.2 — Store Metadata models

StoreMetadata = canonical representation of a game's store listing,
independent of the target platform (Google Play / App Store).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class StoreMetadata:
    game_id: str
    platform: str = ""                         # "android" | "ios"
    locale: str = "en-US"
    title: str = ""
    short_description: str = ""
    full_description: str = ""
    keywords: List[str] = field(default_factory=list)
    category: str = ""
    age_rating: str = ""                       # e.g. "Everyone", "12+"
    privacy_url: str = ""
    screenshots: List[str] = field(default_factory=list)   # file paths
    feature_graphic: str = ""                  # path
    icon: str = ""                             # path
    app_preview: str = ""                      # path (App Store)
    assets: Dict[str, str] = field(default_factory=dict)   # {name: path}
    version: str = ""

    def to_dict(self) -> dict:
        return {
            "game_id": self.game_id, "platform": self.platform,
            "locale": self.locale, "title": self.title,
            "short_description": self.short_description,
            "full_description": self.full_description,
            "keywords": self.keywords, "category": self.category,
            "age_rating": self.age_rating, "privacy_url": self.privacy_url,
            "screenshots": self.screenshots,
            "feature_graphic": self.feature_graphic, "icon": self.icon,
            "app_preview": self.app_preview, "assets": self.assets,
            "version": self.version,
        }


@dataclass
class MetadataPackage:
    """One complete store-ready metadata bundle."""
    game_id: str
    platforms: Dict[str, StoreMetadata] = field(default_factory=dict)  # "android"/"ios"

    def to_dict(self) -> dict:
        return {
            "game_id": self.game_id,
            "platforms": {k: v.to_dict() for k, v in self.platforms.items()},
        }


__all__ = ["StoreMetadata", "MetadataPackage"]
