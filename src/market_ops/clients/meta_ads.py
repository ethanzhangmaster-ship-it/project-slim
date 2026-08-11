from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date
from typing import Any

import requests

from market_ops.models import AdsPerformanceRow, CreativeAssetRow


class MetaAdsCreativeClient:
    def __init__(
        self,
        access_token: str,
        ad_account_id: str,
        api_version: str,
        default_game_name: str,
    ) -> None:
        self._access_token = access_token.strip()
        self._ad_account_id = ad_account_id.removeprefix("act_").strip()
        self._api_version = api_version.strip()
        self._default_game_name = default_game_name.strip()
        self._base_url = f"https://graph.facebook.com/{self._api_version}"

    def fetch_creative_rows(self, start_date: date, end_date: date) -> list[CreativeAssetRow]:
        insights_rows = self._fetch_insights(start_date=start_date, end_date=end_date)
        ads_map = self._fetch_ads_map()
        aggregated = self._aggregate_by_creative(insights_rows=insights_rows, ads_map=ads_map)
        rows = [self._to_creative_row(item) for item in aggregated.values()]
        rows.sort(key=lambda row: (row.game, -row.roas, -row.ctr, -row.spend, row.asset_id))
        return rows

    def fetch_performance_rows(self, start_date: date, end_date: date) -> list[AdsPerformanceRow]:
        """Return daily ad-level performance directly from Meta Insights."""
        ads_map = self._fetch_ads_map()
        result: list[AdsPerformanceRow] = []
        for insight in self._fetch_insights(start_date=start_date, end_date=end_date):
            ad_id = str(insight.get("ad_id") or "")
            ad_meta = ads_map.get(ad_id) or {}
            creative_id = str((ad_meta.get("creative") or {}).get("id") or ad_id)
            row_date = date.fromisoformat(str(insight.get("date_start") or ""))
            spend = self._to_float(insight.get("spend"))
            clicks = int(self._to_float(insight.get("clicks")))
            impressions = self._to_float(insight.get("impressions"))
            installs = self._extract_conversion_count(insight.get("actions"))
            revenue = self._extract_conversion_value(insight.get("action_values"))
            names = [str((ad_meta.get("creative") or {}).get("name") or ""), str(ad_meta.get("name") or insight.get("ad_name") or ""), str((ad_meta.get("campaign") or {}).get("name") or insight.get("campaign_name") or "")]
            result.append(AdsPerformanceRow(
                date=row_date, game=self._infer_game_name(names), country="All", channel="Facebook",
                ad_id=ad_id, creative_id=creative_id, spend=spend, clicks=clicks,
                ctr=clicks / impressions if impressions else 0.0,
                cpi=spend / installs if installs else 0.0,
                roas=revenue / spend if spend else 0.0,
                retention_d1=0.0, retention_d7=0.0, retention_d30=0.0,
            ))
        return result

    def _fetch_insights(self, start_date: date, end_date: date) -> list[dict[str, Any]]:
        params = {
            "access_token": self._access_token,
            "level": "ad",
            "time_range": json.dumps({"since": start_date.isoformat(), "until": end_date.isoformat()}),
            "time_increment": 1,
            "fields": ",".join(
                [
                    "date_start",
                    "date_stop",
                    "ad_id",
                    "ad_name",
                    "campaign_name",
                    "adset_name",
                    "spend",
                    "impressions",
                    "clicks",
                    "ctr",
                    "actions",
                    "action_values",
                    "purchase_roas",
                ]
            ),
            "limit": 500,
        }
        return self._get_paginated(f"/act_{self._ad_account_id}/insights", params)

    def _fetch_ads_map(self) -> dict[str, dict[str, Any]]:
        params = {
            "access_token": self._access_token,
            "fields": ",".join(
                [
                    "id",
                    "name",
                    "effective_status",
                    "campaign{name}",
                    "adset{name}",
                    "creative{id,name,title,body,thumbnail_url,image_url,object_story_spec,asset_feed_spec,effective_object_story_id,effective_instagram_media_id}",
                ]
            ),
            "limit": 500,
        }
        try:
            rows = self._get_paginated(f"/act_{self._ad_account_id}/ads", params)
        except RuntimeError as exc:
            if "HTTP 5" not in str(exc):
                raise
            fallback = dict(params)
            fallback["fields"] = "id,name,effective_status,campaign{id,name},adset{id,name},creative{id,name}"
            rows = self._get_paginated(f"/act_{self._ad_account_id}/ads", fallback)
        return {str(row.get("id") or ""): row for row in rows if row.get("id")}

    def _aggregate_by_creative(
        self,
        insights_rows: list[dict[str, Any]],
        ads_map: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        aggregated: dict[str, dict[str, Any]] = {}
        for row in insights_rows:
            ad_id = str(row.get("ad_id") or "")
            ad_meta = ads_map.get(ad_id, {})
            creative = ad_meta.get("creative") or {}
            creative_id = str(creative.get("id") or ad_id)
            if not creative_id:
                continue

            item = aggregated.setdefault(
                creative_id,
                {
                    "asset_id": creative_id,
                    "creative_name": str(creative.get("name") or ""),
                    "creative_type": self._infer_creative_type(creative),
                    "video_path": self._best_media_url(creative),
                    "game": self._infer_game_name(
                        [
                            str(creative.get("name") or ""),
                            str(ad_meta.get("name") or row.get("ad_name") or ""),
                            str((ad_meta.get("campaign") or {}).get("name") or row.get("campaign_name") or ""),
                            str((ad_meta.get("adset") or {}).get("name") or row.get("adset_name") or ""),
                        ]
                    ),
                    "country": "All",
                    "channel": "Facebook",
                    "campaign": str((ad_meta.get("campaign") or {}).get("name") or row.get("campaign_name") or ""),
                    "campaign_id": str((ad_meta.get("campaign") or {}).get("id") or ""),
                    "adgroup": str((ad_meta.get("adset") or {}).get("name") or row.get("adset_name") or ""),
                    "adgroup_id": str((ad_meta.get("adset") or {}).get("id") or ""),
                    "ad_id": ad_id,
                    "ad_name": str(ad_meta.get("name") or row.get("ad_name") or ""),
                    "source_name": str((ad_meta.get("adset") or {}).get("name") or row.get("adset_name") or ""),
                    "source_id": str((ad_meta.get("adset") or {}).get("id") or ""),
                    "status": str(ad_meta.get("effective_status") or "UNKNOWN"),
                    "hook_type": self._infer_hook_label(creative),
                    "duration": 0.0,
                    "spend": 0.0,
                    "impressions": 0.0,
                    "clicks": 0.0,
                    "conversion_count": 0.0,
                    "conversion_value": 0.0,
                },
            )

            item["spend"] += self._to_float(row.get("spend"))
            item["impressions"] += self._to_float(row.get("impressions"))
            item["clicks"] += self._to_float(row.get("clicks"))
            item["conversion_count"] += self._extract_conversion_count(row.get("actions"))
            item["conversion_value"] += self._extract_conversion_value(row.get("action_values"))

            media_url = self._best_media_url(creative)
            if media_url and not item["video_path"]:
                item["video_path"] = media_url
            if item["hook_type"] in {"Unknown", "video", "image", "carousel"}:
                item["hook_type"] = self._infer_hook_label(creative)
        return aggregated

    def _to_creative_row(self, item: dict[str, Any]) -> CreativeAssetRow:
        clicks = float(item["clicks"])
        impressions = float(item["impressions"])
        spend = float(item["spend"])
        conversion_count = float(item["conversion_count"])
        conversion_value = float(item["conversion_value"])
        ctr = clicks / impressions if impressions else 0.0
        cvr = conversion_count / clicks if clicks else 0.0
        roas = conversion_value / spend if spend else 0.0

        return CreativeAssetRow(
            asset_id=str(item["asset_id"]),
            creative_type=str(item["creative_type"]),
            video_path=str(item["video_path"]),
            game=str(item["game"]),
            country=str(item["country"]),
            channel=str(item["channel"]),
            ctr=ctr,
            cvr=cvr,
            roas=roas,
            spend=spend,
            status=str(item["status"]),
            hook_type=str(item["hook_type"]),
            duration=float(item["duration"]),
            creative_name=str(item.get("creative_name", "")),
            campaign=str(item.get("campaign", "")),
            campaign_id=str(item.get("campaign_id", "")),
            adgroup=str(item.get("adgroup", "")),
            adgroup_id=str(item.get("adgroup_id", "")),
            ad_id=str(item.get("ad_id", "")),
            ad_name=str(item.get("ad_name", "")),
            source_name=str(item.get("source_name", "")),
            source_id=str(item.get("source_id", "")),
            installs=conversion_count,
            conversions=conversion_count,
            revenue_value=conversion_value,
        )

    def _get_paginated(self, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        url = f"{self._base_url}{path}"
        results: list[dict[str, Any]] = []
        next_params: dict[str, Any] | None = params
        while url:
            response = requests.get(url, params=next_params, timeout=60)
            if not response.ok:
                raise RuntimeError(f"Meta Ads API request failed (HTTP {response.status_code})")
            payload = response.json()
            if "error" in payload:
                raise RuntimeError(f"Meta Ads API error: {payload['error']}")
            results.extend(payload.get("data", []))
            paging = payload.get("paging") or {}
            url = paging.get("next") or ""
            next_params = None
        return results

    def _infer_game_name(self, texts: list[str]) -> str:
        for text in texts:
            match = re.search(r"\bP\d{2}\b(?:\s+[A-Za-z][A-Za-z0-9_-]*)?", text)
            if match:
                return match.group(0).strip()
        return self._default_game_name

    @staticmethod
    def _infer_creative_type(creative: dict[str, Any]) -> str:
        story_spec = creative.get("object_story_spec") or {}
        link_data = story_spec.get("link_data") or {}
        video_data = story_spec.get("video_data") or {}
        if video_data or creative.get("effective_object_story_id"):
            return "video"
        if link_data.get("child_attachments"):
            return "carousel"
        if creative.get("image_url") or link_data.get("image_hash"):
            return "image"
        return "ad"

    @staticmethod
    def _best_media_url(creative: dict[str, Any]) -> str:
        return str(
            creative.get("image_url")
            or creative.get("thumbnail_url")
            or ((creative.get("object_story_spec") or {}).get("link_data") or {}).get("link")
            or ""
        )

    @classmethod
    def _infer_hook_label(cls, creative: dict[str, Any]) -> str:
        for candidate in (
            creative.get("title"),
            creative.get("name"),
            creative.get("body"),
            (((creative.get("object_story_spec") or {}).get("video_data") or {}).get("message")),
            (((creative.get("object_story_spec") or {}).get("link_data") or {}).get("message")),
        ):
            text = cls._clean_text(candidate)
            if text:
                return text[:40]
        return cls._infer_creative_type(creative)

    @staticmethod
    def _clean_text(value: Any) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()

    @classmethod
    def _extract_conversion_count(cls, actions: Any) -> float:
        values = cls._normalize_action_map(actions)
        for key in (
            "mobile_app_install",
            "app_install",
            "omni_app_install",
            "offsite_conversion.fb_mobile_purchase",
            "omni_purchase",
            "purchase",
        ):
            if key in values:
                return values[key]
        return 0.0

    @classmethod
    def _extract_conversion_value(cls, action_values: Any) -> float:
        values = cls._normalize_action_map(action_values)
        for key in (
            "omni_purchase",
            "offsite_conversion.fb_mobile_purchase",
            "purchase",
            "mobile_purchase",
        ):
            if key in values:
                return values[key]
        return 0.0

    @staticmethod
    def _normalize_action_map(items: Any) -> dict[str, float]:
        result: dict[str, float] = defaultdict(float)
        if not isinstance(items, list):
            return result
        for item in items:
            if not isinstance(item, dict):
                continue
            action_type = str(item.get("action_type") or "").strip()
            if not action_type:
                continue
            result[action_type] += MetaAdsCreativeClient._to_float(item.get("value"))
        return result

    @staticmethod
    def _to_float(value: Any) -> float:
        if value in (None, ""):
            return 0.0
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
