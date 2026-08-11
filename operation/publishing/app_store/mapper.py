"""
E15.1.5 — App Store Mapper
"""
from operation.publishing.metadata.models import StoreMetadata


class AppStoreMapper:
    def to_listing_payload(self, meta: StoreMetadata) -> dict:
        return {
            "name": meta.title,
            "subtitle": meta.short_description[:30] if meta.short_description else "",
            "description": meta.full_description,
            "keywords": meta.keywords,
            "primaryCategory": meta.category,
            "contentAdvisoryRating": meta.age_rating,
            "privacyPolicyUrl": meta.privacy_url,
            "screenshots": meta.screenshots,
            "preview": meta.app_preview,
            "version": meta.version,
        }


__all__ = ["AppStoreMapper"]
