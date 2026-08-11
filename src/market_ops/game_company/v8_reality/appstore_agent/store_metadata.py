from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime


@dataclass
class Localization:
    locale: str
    title: str = ""
    subtitle: str = ""
    description: str = ""
    keywords: List[str] = field(default_factory=list)
    what_s_new: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "locale": self.locale,
            "title": self.title,
            "subtitle": self.subtitle,
            "description": self.description,
            "keywords": self.keywords,
            "what_s_new": self.what_s_new,
        }


@dataclass
class AppMetadata:
    app_id: str
    primary_category: str = ""
    secondary_category: str = ""
    privacy_url: str = ""
    support_url: str = ""
    marketing_url: str = ""
    copyright: str = ""
    version: str = "1.0.0"
    localizations: Dict[str, Localization] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "app_id": self.app_id,
            "primary_category": self.primary_category,
            "secondary_category": self.secondary_category,
            "privacy_url": self.privacy_url,
            "support_url": self.support_url,
            "marketing_url": self.marketing_url,
            "copyright": self.copyright,
            "version": self.version,
            "localizations": {k: v.to_dict() for k, v in self.localizations.items()},
            "updated_at": self.updated_at.isoformat(),
        }


class StoreMetadata:
    def __init__(self):
        self._metadata_store: Dict[str, AppMetadata] = {}

    def update_metadata(self, app_id: str, metadata: Dict[str, Any]) -> AppMetadata:
        if app_id not in self._metadata_store:
            self._metadata_store[app_id] = AppMetadata(app_id=app_id)

        app_meta = self._metadata_store[app_id]
        if "primary_category" in metadata:
            app_meta.primary_category = metadata["primary_category"]
        if "secondary_category" in metadata:
            app_meta.secondary_category = metadata["secondary_category"]
        if "privacy_url" in metadata:
            app_meta.privacy_url = metadata["privacy_url"]
        if "support_url" in metadata:
            app_meta.support_url = metadata["support_url"]
        if "marketing_url" in metadata:
            app_meta.marketing_url = metadata["marketing_url"]
        if "copyright" in metadata:
            app_meta.copyright = metadata["copyright"]
        if "version" in metadata:
            app_meta.version = metadata["version"]
        if "localizations" in metadata:
            for locale, loc_data in metadata["localizations"].items():
                app_meta.localizations[locale] = Localization(**loc_data)

        app_meta.updated_at = datetime.now()
        return app_meta

    def get_metadata(self, app_id: str) -> Optional[AppMetadata]:
        return self._metadata_store.get(app_id)

    def validate_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        errors = []
        warnings = []

        if not metadata.get("primary_category"):
            errors.append("Primary category is required")
        if metadata.get("title") and len(metadata["title"]) > 30:
            warnings.append("Title exceeds 30 characters")
        if metadata.get("description") and len(metadata["description"]) > 4000:
            errors.append("Description exceeds 4000 characters")
        if not metadata.get("privacy_url"):
            warnings.append("Privacy URL is recommended")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "field_validations": {
                "primary_category": {"valid": bool(metadata.get("primary_category")), "message": "Required"},
                "title": {"valid": True, "max_length": 30},
                "description": {"valid": len(metadata.get("description", "")) <= 4000, "max_length": 4000},
            },
        }

    def get_localizations(self, app_id: str) -> Dict[str, Localization]:
        app_meta = self.get_metadata(app_id)
        return app_meta.localizations if app_meta else {}