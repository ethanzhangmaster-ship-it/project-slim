"""E11 Phase 1 — Creative Fetcher。

将 Facebook API 原始数据转换为 FacebookCreativeEntity。
负责：
  - 拉取 ads list
  - 拉取 creatives 详情
  - 拉取 insights 数据
  - 合并为 FacebookCreativeEntity
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from .facebook_client import FacebookClient
from .models import FacebookCreativeEntity, CreativeType


class CreativeFetcher:
    """从 Facebook Graph API 拉取并组装 Creative Entity。

    Usage:
        client = FacebookClient(token, account_id)
        fetcher = CreativeFetcher(client)
        entities = fetcher.fetch_all(start_date, end_date)
    """

    def __init__(self, client: FacebookClient) -> None:
        self._client = client

    def fetch_all(
        self,
        start_date: date,
        end_date: date,
    ) -> list[FacebookCreativeEntity]:
        """拉取完整素材数据（ads + creatives + insights）。

        Returns:
            FacebookCreativeEntity 列表
        """
        # 1. 拉取 ads
        ads = self._fetch_ads()

        # 2. 拉取 insights
        insights = self._fetch_insights(start_date, end_date)

        # 3. 构建 insights map
        insights_map: dict[str, dict[str, Any]] = {}
        for row in insights:
            ad_id = row.get("ad_id", "")
            if ad_id:
                insights_map[ad_id] = row

        # 4. 合并为 Entity
        entities: list[FacebookCreativeEntity] = []
        for ad_data in ads:
            entity = self._build_entity(ad_data, insights_map.get(ad_data.get("id", "")))
            if entity:
                entities.append(entity)

        return entities

    def _fetch_ads(self) -> list[dict[str, Any]]:
        """拉取广告列表。"""
        return self._client.get_ads()

    def _fetch_insights(
        self,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """拉取成效数据。"""
        return self._client.get_insights(start_date, end_date)

    def _build_entity(
        self,
        ad_data: dict[str, Any],
        insights: dict[str, Any] | None,
    ) -> FacebookCreativeEntity | None:
        """从 ad + insights 构建 FacebookCreativeEntity。"""
        ad_id = ad_data.get("id", "")
        if not ad_id:
            return None

        # ── Creative 数据 ────────────────────────────────
        creative = ad_data.get("creative") or {}
        creative_id = creative.get("id", "")

        # 判断类型
        if creative.get("video_id"):
            creative_type = CreativeType.VIDEO
        elif creative.get("image_url") or creative.get("thumbnail_url"):
            creative_type = CreativeType.IMAGE
        else:
            return None

        # ── Campaign / Adset ─────────────────────────────
        campaign = ad_data.get("campaign") or {}
        adset = ad_data.get("adset") or {}

        # ── Insights ─────────────────────────────────────
        insights = insights or {}

        # ── 构建 Entity ──────────────────────────────────
        now = datetime.now().isoformat()

        return FacebookCreativeEntity(
            creative_asset_id="",  # 由 ad_parser 后续填充
            creative_id=creative_id,
            ad_id=ad_id,
            ad_name=ad_data.get("name", ""),
            account_id=self._client.account_id,
            campaign_id=ad_data.get("campaign_id", "") or campaign.get("id", ""),
            campaign_name=campaign.get("name", "") or insights.get("campaign_name", ""),
            adset_id=ad_data.get("adset_id", "") or adset.get("id", ""),
            adset_name=adset.get("name", "") or insights.get("adset_name", ""),
            creative_type=creative_type,
            image_url=creative.get("image_url", ""),
            thumbnail_url=creative.get("thumbnail_url", ""),
            video_id=creative.get("video_id", ""),
            primary_text=creative.get("body", ""),
            headline=creative.get("title", ""),
            description=creative.get("description", ""),
            call_to_action=creative.get("call_to_action_type", ""),
            spend=float(insights.get("spend", 0.0)),
            impressions=int(insights.get("impressions", 0)),
            clicks=int(insights.get("clicks", 0)),
            ctr=float(insights.get("ctr", 0.0)),
            cpc=float(insights.get("cpc", 0.0)),
            cpm=float(insights.get("cpm", 0.0)),
            installs=self._extract_installs(insights),
            status=ad_data.get("status", ""),
            created_time=ad_data.get("created_time", ""),
            updated_time=ad_data.get("updated_time", ""),
            synced_at=now,
            sync_source="facebook",
        )

    @staticmethod
    def _extract_installs(insights: dict[str, Any]) -> int:
        """从 actions 中提取 installs 数量。"""
        actions = insights.get("actions", [])
        if isinstance(actions, list):
            for action in actions:
                if action.get("action_type") == "app_custom_event.fb_mobile_app_install":
                    return int(action.get("value", 0))
        return 0

    def __repr__(self) -> str:
        return f"CreativeFetcher(client={self._client})"