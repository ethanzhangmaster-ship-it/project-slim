"""E13.1.3 Adjust Attribution — 归因记录映射与网络关联."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .models import (
    AdjustNetwork,
    AdjustUserEvent,
    AttributionRecord,
)


class AttributionMapper:
    """Adjust 归因映射器.

    将 Adjust 归因数据与广告平台 (Meta, Google, ASA) 关联，
    构建 AttributionRecord 并连接用户事件。
    """

    # 网络名称映射
    NETWORK_NAME_MAP: dict[str, AdjustNetwork] = {
        "meta": AdjustNetwork.META,
        "facebook": AdjustNetwork.META,
        "google": AdjustNetwork.GOOGLE,
        "google ads": AdjustNetwork.GOOGLE,
        "googleadwords": AdjustNetwork.GOOGLE,
        "asa": AdjustNetwork.ASA,
        "apple search ads": AdjustNetwork.ASA,
        "tiktok": AdjustNetwork.TIKTOK,
        "bytedance": AdjustNetwork.TIKTOK,
        "unity": AdjustNetwork.UNITY,
        "unityads": AdjustNetwork.UNITY,
        "applovin": AdjustNetwork.APPLOVIN,
        "ironsource": AdjustNetwork.IRONSOURCE,
        "mintegral": AdjustNetwork.MINTEGRAL,
        "organic": AdjustNetwork.ORGANIC,
    }

    @classmethod
    def map_network(cls, network_name: str) -> AdjustNetwork:
        """映射网络名称到 AdjustNetwork."""
        if not network_name:
            return AdjustNetwork.ORGANIC
        return cls.NETWORK_NAME_MAP.get(
            network_name.lower().strip(), AdjustNetwork.UNKNOWN,
        )

    @classmethod
    def parse_raw_attribution(
        cls, raw: dict[str, Any],
    ) -> AttributionRecord:
        """从 Adjust 原始归因数据解析 AttributionRecord.

        Args:
            raw: Adjust 原始归因 JSON

        Returns:
            AttributionRecord 标准模型
        """
        network_name = raw.get("network", raw.get("network_name", ""))
        is_organic = network_name.lower() in ("organic", "") or raw.get("is_organic", False)

        return AttributionRecord(
            user_id=raw.get("user_id", raw.get("adid", "")),
            network=cls.map_network(network_name),
            campaign_id=raw.get("campaign_id", raw.get("campaign", "")),
            campaign_name=raw.get("campaign_name", raw.get("campaign", "")),
            adgroup_id=raw.get("adgroup_id", raw.get("adgroup", "")),
            adgroup_name=raw.get("adgroup_name", raw.get("adgroup", "")),
            creative_id=raw.get("creative_id", raw.get("creative", "")),
            creative_name=raw.get("creative_name", raw.get("creative", "")),
            install_time=raw.get("installed_at", raw.get("install_time", "")),
            click_time=raw.get("clicked_at", raw.get("click_time", "")),
            attribution_time=raw.get("attributed_at", raw.get("attribution_time", "")),
            country=raw.get("country", ""),
            language=raw.get("language", ""),
            device_type=raw.get("device_type", raw.get("device", "")),
            is_organic=is_organic,
            raw_data=raw,
        )

    @classmethod
    def parse_batch(
        cls, raw_attributions: list[dict[str, Any]],
    ) -> list[AttributionRecord]:
        """批量解析归因数据."""
        return [cls.parse_raw_attribution(a) for a in raw_attributions]

    @classmethod
    def group_by_network(
        cls, attributions: list[AttributionRecord],
    ) -> dict[AdjustNetwork, list[AttributionRecord]]:
        """按网络分组归因记录."""
        groups: dict[AdjustNetwork, list[AttributionRecord]] = defaultdict(list)
        for attr in attributions:
            groups[attr.network].append(attr)
        return dict(groups)

    @classmethod
    def group_by_campaign(
        cls, attributions: list[AttributionRecord],
    ) -> dict[str, list[AttributionRecord]]:
        """按 Campaign 分组归因记录."""
        groups: dict[str, list[AttributionRecord]] = defaultdict(list)
        for attr in attributions:
            key = attr.campaign_id or "organic"
            groups[key].append(attr)
        return dict(groups)

    @classmethod
    def get_network_stats(
        cls, attributions: list[AttributionRecord],
    ) -> dict[str, dict[str, Any]]:
        """获取各网络归因统计."""
        groups = cls.group_by_network(attributions)
        stats: dict[str, dict[str, Any]] = {}

        for network, records in groups.items():
            paid = sum(1 for r in records if r.is_paid)
            organic = sum(1 for r in records if r.is_organic)
            stats[network.value] = {
                "total": len(records),
                "paid": paid,
                "organic": organic,
                "paid_ratio": paid / len(records) if records else 0.0,
            }

        return stats

    @classmethod
    def link_events_to_attribution(
        cls,
        events: list[AdjustUserEvent],
        attributions: list[AttributionRecord],
    ) -> list[AdjustUserEvent]:
        """将事件链接到归因记录.

        根据 user_id 匹配，补充事件中的网络和 Campaign 信息。
        """
        attr_map: dict[str, AttributionRecord] = {}
        for attr in attributions:
            if attr.user_id and attr.user_id not in attr_map:
                attr_map[attr.user_id] = attr

        for event in events:
            if event.user_id in attr_map:
                attr = attr_map[event.user_id]
                if not event.network:
                    event.network = attr.network.value
                if not event.campaign_id:
                    event.campaign_id = attr.campaign_id
                if not event.adgroup_id:
                    event.adgroup_id = attr.adgroup_id
                if not event.creative_id:
                    event.creative_id = attr.creative_id

        return events

    @classmethod
    def compute_organic_vs_paid_split(
        cls, attributions: list[AttributionRecord],
    ) -> dict[str, int]:
        """计算 Organic vs Paid 分布."""
        organic = sum(1 for a in attributions if a.is_organic)
        paid = sum(1 for a in attributions if a.is_paid)
        return {
            "organic": organic,
            "paid": paid,
            "total": len(attributions),
            "organic_ratio": organic / len(attributions) if attributions else 0.0,
        }