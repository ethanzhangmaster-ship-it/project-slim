"""V4.0: Facebook Adapter — wraps existing Facebook API data.

Bridges Facebook creative performance data into the Creative Repository.
Reuses existing video_intelligence/fetcher.py and creative_performance data.
"""

from __future__ import annotations

from typing import Any


class FacebookAdapter:
    """Adapter for Facebook Ads data → Creative Repository.

    Reuses existing Facebook fetcher and performance data.
    Does NOT reimplement Facebook API calls.
    """

    def __init__(self, access_token: str | None = None, ad_account_id: str | None = None) -> None:
        self._token = access_token
        self._account_id = ad_account_id

    def extract_creative_data(self, creative_record: dict[str, Any]) -> dict[str, Any]:
        """Extract standardized creative data from Facebook record.

        Compatible with existing video_records.json and creative_performance formats.
        """
        return {
            "creative_id": creative_record.get("creative_id", ""),
            "creative_name": creative_record.get("creative_name", ""),
            "creative_type": self._detect_type(creative_record),
            "campaign_id": creative_record.get("campaign_id", ""),
            "adset_id": creative_record.get("adset_id", ""),
            "ad_id": creative_record.get("ad_id", ""),
            "spend": float(creative_record.get("spend", 0)),
            "impressions": int(creative_record.get("impressions", 0)),
            "clicks": int(creative_record.get("clicks", 0)),
            "ctr": float(creative_record.get("ctr", 0)),
            "cpm": float(creative_record.get("cpm", 0)),
            "cpi": float(creative_record.get("cpi", 0)),
            "ipm": float(creative_record.get("ipm", 0)),
            "installs": int(creative_record.get("installs", 0)),
            "roas_d1": float(creative_record.get("roas_d1", 0)),
            "roas_d7": float(creative_record.get("roas_d7", 0)),
            "frequency": float(creative_record.get("frequency", 0)),
            "status": creative_record.get("status", "ACTIVE"),
            "video_id": creative_record.get("video_id", ""),
            "image_url": creative_record.get("image_url", ""),
            "thumbnail_url": creative_record.get("thumbnail_url", ""),
            "primary_text": creative_record.get("primary_text", ""),
            "headline": creative_record.get("headline", ""),
            "call_to_action": creative_record.get("call_to_action", ""),
        }

    def _detect_type(self, record: dict[str, Any]) -> str:
        if record.get("video_id") or record.get("object_story_spec_video_data_video_id"):
            return "video"
        if record.get("image_url") or record.get("thumbnail_url"):
            return "image"
        return "unknown"

    @property
    def available(self) -> bool:
        return bool(self._token and self._account_id)