"""
E15.1.4 — Google Play Mapper

Transforms StoreMetadata into Google Play Console API payload.
"""
from __future__ import annotations

from operation.publishing.metadata.models import StoreMetadata


class GooglePlayMapper:
    """Maps canonical StoreMetadata → Google Play listing payload."""

    def to_listing_payload(self, meta: StoreMetadata) -> dict:
        return {
            "title": meta.title,
            "shortDescription": meta.short_description,
            "fullDescription": meta.full_description,
            "category": {"categoryId": self._category_id(meta.category)},
            "contentRating": meta.age_rating,
            "privacyPolicyUrl": meta.privacy_url,
            "graphicAssets": {
                "featureGraphic": meta.feature_graphic,
                "icon": meta.icon,
                "screenshots": meta.screenshots,
            },
            "version": meta.version,
        }

    def _category_id(self, category: str) -> str:
        mapping = {
            "puzzle": "GAME_PUZZLE",
            "merge": "GAME_CASUAL",
            "casual": "GAME_CASUAL",
            "action": "GAME_ACTION",
            "simulation": "GAME_SIMULATION",
        }
        return mapping.get(category, "GAME_CASUAL")


__all__ = ["GooglePlayMapper"]
