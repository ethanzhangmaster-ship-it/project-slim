from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from market_ops.models import CreativeAssetRow


class GoogleAdsCreativeClient:
    def __init__(
        self,
        developer_token: str,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        customer_id: str,
        login_customer_id: str | None,
        default_game_name: str,
    ) -> None:
        self._developer_token = developer_token.strip()
        self._client_id = client_id.strip()
        self._client_secret = client_secret.strip()
        self._refresh_token = refresh_token.strip()
        self._customer_id = customer_id.replace("-", "").strip()
        self._login_customer_id = (login_customer_id or "").replace("-", "").strip() or None
        self._default_game_name = default_game_name.strip()

    def fetch_creative_rows(self, start_date: date, end_date: date) -> list[CreativeAssetRow]:
        client = self._build_client()
        aggregated: dict[str, dict[str, Any]] = {}
        self._collect_ad_group_asset_rows(client, start_date, end_date, aggregated)
        self._collect_asset_group_rows(client, start_date, end_date, aggregated)
        rows = [self._to_creative_row(item) for item in aggregated.values()]
        rows.sort(key=lambda row: (row.game, -row.roas, -row.ctr, -row.spend, row.asset_id))
        return rows

    def _build_client(self):
        try:
            from google.ads.googleads.client import GoogleAdsClient
        except ImportError as exc:
            raise RuntimeError("google-ads package is required for Google Ads creative sync.") from exc

        config = {
            "developer_token": self._developer_token,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "refresh_token": self._refresh_token,
            "use_proto_plus": True,
        }
        if self._login_customer_id:
            config["login_customer_id"] = self._login_customer_id
        return GoogleAdsClient.load_from_dict(config)

    def _collect_ad_group_asset_rows(self, client, start_date: date, end_date: date, aggregated: dict[str, dict[str, Any]]) -> None:
        query = f"""
            SELECT
              asset.id,
              asset.name,
              asset.type,
              asset.text_asset.text,
              asset.image_asset.full_size.url,
              asset.youtube_video_asset.youtube_video_id,
              asset.youtube_video_asset.youtube_video_title,
              campaign.name,
              ad_group.name,
              ad_group_ad_asset_view.field_type,
              metrics.impressions,
              metrics.clicks,
              metrics.ctr,
              metrics.cost_micros,
              metrics.conversions,
              metrics.conversions_value
            FROM ad_group_ad_asset_view
            WHERE segments.date BETWEEN '{start_date.isoformat()}' AND '{end_date.isoformat()}'
        """
        self._run_query(client, query, aggregated, source_field="ad_group_ad_asset_view")

    def _collect_asset_group_rows(self, client, start_date: date, end_date: date, aggregated: dict[str, dict[str, Any]]) -> None:
        query = f"""
            SELECT
              asset.id,
              asset.name,
              asset.type,
              asset.text_asset.text,
              asset.image_asset.full_size.url,
              asset.youtube_video_asset.youtube_video_id,
              asset.youtube_video_asset.youtube_video_title,
              campaign.name,
              asset_group.name,
              asset_group_asset.field_type,
              metrics.impressions,
              metrics.clicks,
              metrics.ctr,
              metrics.cost_micros,
              metrics.conversions,
              metrics.conversions_value
            FROM asset_group_asset
            WHERE segments.date BETWEEN '{start_date.isoformat()}' AND '{end_date.isoformat()}'
        """
        self._run_query(client, query, aggregated, source_field="asset_group_asset")

    def _run_query(self, client, query: str, aggregated: dict[str, dict[str, Any]], source_field: str) -> None:
        service = client.get_service("GoogleAdsService")
        try:
            stream = service.search_stream(customer_id=self._customer_id, query=query)
        except Exception as exc:
            message = str(exc).lower()
            if "unrecognized field" in message or "cannot select" in message or "unsupported" in message:
                return
            raise

        for batch in stream:
            for row in batch.results:
                asset = row.asset
                asset_id = str(asset.id)
                if not asset_id:
                    continue
                item = aggregated.setdefault(
                    asset_id,
                    {
                        "asset_id": asset_id,
                        "creative_name": str(getattr(asset, "name", "") or ""),
                        "creative_type": str(asset.type_.name if hasattr(asset.type_, "name") else asset.type_),
                        "video_path": self._asset_media_url(asset),
                        "game": self._infer_game_name(
                            [
                                getattr(asset, "name", ""),
                                getattr(getattr(row, "campaign", None), "name", ""),
                                getattr(getattr(row, "ad_group", None), "name", ""),
                                getattr(getattr(row, "asset_group", None), "name", ""),
                            ]
                        ),
                        "country": "All",
                        "channel": "Google Ads",
                        "campaign": str(getattr(getattr(row, "campaign", None), "name", "") or ""),
                        "campaign_id": "",
                        "adgroup": str(getattr(getattr(row, "ad_group", None), "name", "") or getattr(getattr(row, "asset_group", None), "name", "") or ""),
                        "adgroup_id": "",
                        "ad_id": "",
                        "ad_name": "",
                        "source_name": str(getattr(getattr(row, "ad_group", None), "name", "") or getattr(getattr(row, "asset_group", None), "name", "") or ""),
                        "source_id": "",
                        "status": "ENABLED",
                        "hook_type": self._hook_label(asset),
                        "duration": 0.0,
                        "spend": 0.0,
                        "impressions": 0.0,
                        "clicks": 0.0,
                        "conversions": 0.0,
                        "conversions_value": 0.0,
                    },
                )
                metrics = row.metrics
                item["spend"] += float(metrics.cost_micros) / 1_000_000 if metrics.cost_micros else 0.0
                item["impressions"] += float(metrics.impressions or 0)
                item["clicks"] += float(metrics.clicks or 0)
                item["conversions"] += float(metrics.conversions or 0)
                item["conversions_value"] += float(metrics.conversions_value or 0)
                item["revenue_value"] = item["conversions_value"]

                field_type = self._field_type_label(row, source_field)
                if field_type and item["hook_type"] in {"Unknown", item["creative_type"]}:
                    item["hook_type"] = field_type
                media_url = self._asset_media_url(asset)
                if media_url and not item["video_path"]:
                    item["video_path"] = media_url
                campaign_id = self._resource_id(getattr(getattr(row, "campaign", None), "resource_name", ""))
                if campaign_id:
                    item["campaign_id"] = campaign_id
                adgroup_obj = getattr(row, "ad_group", None)
                asset_group_obj = getattr(row, "asset_group", None)
                adgroup_resource = getattr(adgroup_obj, "resource_name", "") or getattr(asset_group_obj, "resource_name", "")
                adgroup_id = self._resource_id(adgroup_resource)
                if adgroup_id:
                    item["adgroup_id"] = adgroup_id
                if adgroup_id:
                    item["source_id"] = adgroup_id
                if item["adgroup"]:
                    item["source_name"] = item["adgroup"]

    def _to_creative_row(self, item: dict[str, Any]) -> CreativeAssetRow:
        impressions = float(item["impressions"])
        clicks = float(item["clicks"])
        spend = float(item["spend"])
        conversions = float(item["conversions"])
        conversions_value = float(item["conversions_value"])
        ctr = clicks / impressions if impressions else 0.0
        cvr = conversions / clicks if clicks else 0.0
        roas = conversions_value / spend if spend else 0.0
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
            installs=conversions,
            conversions=conversions,
            revenue_value=conversions_value,
        )

    def _infer_game_name(self, texts: list[str]) -> str:
        for text in texts:
            match = re.search(r"\bP\d{2}\b(?:\s+[A-Za-z][A-Za-z0-9_-]*)?", str(text or ""))
            if match:
                return match.group(0).strip()
        return self._default_game_name

    @staticmethod
    def _asset_media_url(asset: Any) -> str:
        image_url = getattr(getattr(asset, "image_asset", None), "full_size", None)
        if image_url and getattr(image_url, "url", ""):
            return str(image_url.url)
        video_id = getattr(getattr(asset, "youtube_video_asset", None), "youtube_video_id", "")
        if video_id:
            return f"https://www.youtube.com/watch?v={video_id}"
        return ""

    @staticmethod
    def _hook_label(asset: Any) -> str:
        for value in (
            getattr(asset, "name", ""),
            getattr(getattr(asset, "text_asset", None), "text", ""),
            getattr(getattr(asset, "youtube_video_asset", None), "youtube_video_title", ""),
        ):
            text = re.sub(r"\s+", " ", str(value or "")).strip()
            if text:
                return text[:40]
        asset_type = getattr(asset, "type_", "")
        return getattr(asset_type, "name", str(asset_type)) or "Unknown"

    @staticmethod
    def _field_type_label(row: Any, source_field: str) -> str:
        if source_field == "ad_group_ad_asset_view":
            field_type = getattr(getattr(row, "ad_group_ad_asset_view", None), "field_type", None)
        else:
            field_type = getattr(getattr(row, "asset_group_asset", None), "field_type", None)
        if field_type is None:
            return ""
        return getattr(field_type, "name", str(field_type)) or ""

    @staticmethod
    def _resource_id(resource_name: str) -> str:
        text = str(resource_name or "").strip()
        if not text:
            return ""
        return text.rsplit("/", 1)[-1]
