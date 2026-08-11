"""E11 Phase 2 — Adjust Data Fetcher。

将 Adjust API 原始数据解析为 AdjustRevenueEntity 列表。
"""

from __future__ import annotations

from typing import Any

from .adjust_client import AdjustClient
from .models import AdjustRevenueEntity


class AdjustFetcher:
    """Adjust 数据抓取器。

    从 AdjustClient 获取原始 API 数据，解析为 AdjustRevenueEntity 列表。

    Usage:
        client = AdjustClient(api_token="xxx", app_token="yyy")
        fetcher = AdjustFetcher(client)
        entities = fetcher.fetch("2026-07-01", "2026-07-21")
    """

    def __init__(self, client: AdjustClient) -> None:
        self._client = client

    def fetch(
        self,
        start_date: str,
        end_date: str,
    ) -> list[AdjustRevenueEntity]:
        """抓取 Adjust 收入数据并解析为实体列表。

        Args:
            start_date: 起始日期 (YYYY-MM-DD)
            end_date:   结束日期 (YYYY-MM-DD)

        Returns:
            AdjustRevenueEntity 列表
        """
        raw_records = self._client.fetch_revenue(start_date, end_date)

        entities: list[AdjustRevenueEntity] = []
        for record in raw_records:
            entity = self._parse_one(record)
            if entity:
                entities.append(entity)

        return entities

    def _parse_one(self, record: dict[str, Any]) -> AdjustRevenueEntity | None:
        """解析单条 Adjust API 记录。

        Adjust API 字段映射：
          creative_id              → adjust_creative_id
          creative_name            → creative
          creative_asset_id        → creative_asset_id（匹配用）
          campaign_name            → campaign
          adgroup_name             → adgroup
          installs                 → installs
          sessions                 → sessions
          cohort_paying_users_d30  → purchasers
          cohort_retention_rate_d1 → retention_d1
          cohort_retention_rate_d7 → retention_d7
          cohort_retention_rate_d30→ retention_d30
          cohort_revenue_iap_d1    → iap_d1
          cohort_revenue_iap_d7    → iap_d7
          cohort_revenue_iap_d30   → iap_d30
          cohort_revenue_ad_d1     → ad_d1
          cohort_revenue_ad_d7     → ad_d7
          cohort_revenue_ad_d30    → ad_d30
        """
        creative_id = str(record.get("creative_id", ""))
        creative_asset_id = str(record.get("creative_asset_id", creative_id))

        if not creative_asset_id:
            return None

        installs = int(record.get("installs", 0))
        purchasers = int(record.get("cohort_paying_users_d30", 0))
        payer_rate = round(purchasers / installs, 4) if installs > 0 else 0.0

        return AdjustRevenueEntity(
            creative_asset_id=creative_asset_id,
            adjust_creative_id=creative_id,
            campaign=str(record.get("campaign_name", "")),
            adgroup=str(record.get("adgroup_name", "")),
            creative=str(record.get("creative_name", "")),
            installs=installs,
            sessions=int(record.get("sessions", 0)),
            purchasers=purchasers,
            payer_rate=payer_rate,
            retention_d1=float(record.get("cohort_retention_rate_d1", 0.0)),
            retention_d7=float(record.get("cohort_retention_rate_d7", 0.0)),
            retention_d30=float(record.get("cohort_retention_rate_d30", 0.0)),
            iap_d1=float(record.get("cohort_revenue_iap_d1", 0.0)),
            iap_d7=float(record.get("cohort_revenue_iap_d7", 0.0)),
            iap_d30=float(record.get("cohort_revenue_iap_d30", 0.0)),
            ad_d1=float(record.get("cohort_revenue_ad_d1", 0.0)),
            ad_d7=float(record.get("cohort_revenue_ad_d7", 0.0)),
            ad_d30=float(record.get("cohort_revenue_ad_d30", 0.0)),
            cost=float(record.get("cost", 0.0)),
            adjust_roas_d1=float(record.get("roas_d1", 0.0)),
            adjust_roas_d7=float(record.get("roas_d7", 0.0)),
            adjust_roas_d30=float(record.get("roas_d30", 0.0)),
            date_start=start_date if hasattr(self, '_start_date') else "",
            date_end=end_date if hasattr(self, '_end_date') else "",
        )

    def __repr__(self) -> str:
        return f"AdjustFetcher(client={self._client!r})"