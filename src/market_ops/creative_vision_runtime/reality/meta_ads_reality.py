"""E12.1 — Meta Ads Reality Connector。

在 FacebookAdsAdapter 之上构建统一门面层，将 Meta Ads 数据
转换为 E11 Evolution 可消费的 AdPerformanceRecord。

设计原则：
  - 薄门面：不重复实现 API 逻辑，纯桥接
  - 默认 sandbox（mock），生产环境通过 config 切换
  - 支持按 Ad ID / Campaign ID / Date Range 批量拉取
  - 输出统一 AdPerformanceRecord

Usage:
    reality = MetaAdsReality(adapter)
    records = reality.fetch_ad_performance(["ad_001", "ad_002"])
    records = reality.fetch_campaign_performance("camp_001")
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING

from .models import AdPerformanceRecord, RealitySource

if TYPE_CHECKING:
    from market_ops.execution_runtime.adapters.facebook.facebook_adapter import (
        FacebookAdsAdapter,
    )

logger = logging.getLogger(__name__)


class MetaAdsReality:
    """Meta Ads 统一门面层。

    封装 FacebookAdsAdapter，提供 E11 友好的数据拉取接口。

    Attributes:
        adapter:           底层 FacebookAdsAdapter
        total_fetched:     累计拉取记录数
        last_fetched_at:   上次拉取时间
    """

    def __init__(
        self,
        adapter: FacebookAdsAdapter | None = None,
    ) -> None:
        self._adapter = adapter

        self.total_fetched: int = 0
        self.last_fetched_at: datetime | None = None

    # ── Public API ───────────────────────────────────────

    def fetch_ad_performance(
        self,
        ad_ids: list[str],
        date_range: dict[str, str] | None = None,
    ) -> list[AdPerformanceRecord]:
        """拉取指定广告的性能数据。

        Args:
            ad_ids:       Facebook Ad ID 列表
            date_range:   {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}

        Returns:
            AdPerformanceRecord 列表
        """
        if not ad_ids:
            return []

        records: list[AdPerformanceRecord] = []
        for ad_id in ad_ids:
            record = self._fetch_single_ad(ad_id, date_range)
            if record:
                records.append(record)

        self.total_fetched += len(records)
        self.last_fetched_at = datetime.now(timezone.utc)

        logger.info(
            f"MetaAdsReality: fetched {len(records)} ad records "
            f"(total: {self.total_fetched})"
        )
        return records

    def fetch_campaign_performance(
        self,
        campaign_id: str,
        date_range: dict[str, str] | None = None,
    ) -> list[AdPerformanceRecord]:
        """拉取指定 Campaign 下所有广告的性能数据。

        Args:
            campaign_id:  Facebook Campaign ID
            date_range:   {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}

        Returns:
            AdPerformanceRecord 列表
        """
        if not self._adapter:
            return self._mock_campaign_records(campaign_id, date_range)

        result = self._adapter.get_metrics(campaign_id, date_range)
        if not result.success:
            logger.warning(
                f"MetaAdsReality: failed to fetch metrics for {campaign_id}: "
                f"{result.error_message}"
            )
            return []

        return self._parse_adapter_result(campaign_id, result)

    def fetch_recent_performance(
        self,
        campaign_ids: list[str],
        lookback_days: int = 7,
    ) -> dict[str, list[AdPerformanceRecord]]:
        """拉取最近 N 天的 Campaign 性能数据。

        Args:
            campaign_ids:   Campaign ID 列表
            lookback_days:  回溯天数

        Returns:
            {campaign_id: [AdPerformanceRecord, ...]}
        """
        today = date.today()
        start = (today - timedelta(days=lookback_days)).isoformat()
        end = today.isoformat()
        date_range = {"start": start, "end": end}

        result: dict[str, list[AdPerformanceRecord]] = {}
        for cid in campaign_ids:
            records = self.fetch_campaign_performance(cid, date_range)
            if records:
                result[cid] = records

        return result

    def is_connected(self) -> bool:
        """检查是否已连接 Meta Ads API。"""
        if not self._adapter:
            return False
        config = self._adapter.config
        return config.is_configured

    # ── Internal ────────────────────────────────────────

    def _fetch_single_ad(
        self,
        ad_id: str,
        date_range: dict[str, str] | None,
    ) -> AdPerformanceRecord | None:
        """拉取单个广告性能数据。"""
        if not self._adapter:
            return self._mock_ad_record(ad_id, date_range)

        result = self._adapter.get_metrics(ad_id, date_range)
        if not result.success:
            return None

        metrics = result.raw_response.get("metrics", {})
        return AdPerformanceRecord(
            ad_id=ad_id,
            campaign_id=result.raw_response.get("campaign_id", ""),
            spend=float(metrics.get("spend", 0)),
            impressions=int(metrics.get("impressions", 0)),
            clicks=int(metrics.get("clicks", 0)),
            ctr=float(metrics.get("ctr", 0)),
            cpm=float(metrics.get("cpm", 0)),
            cpc=float(metrics.get("cpc", 0)),
            cpi=float(metrics.get("cpi", 0)),
            source=RealitySource.META_ADS,
        )

    def _parse_adapter_result(
        self,
        campaign_id: str,
        result,
    ) -> list[AdPerformanceRecord]:
        """解析 AdapterResult 为 AdPerformanceRecord 列表。"""
        metrics = result.raw_response.get("metrics", {})
        record = AdPerformanceRecord(
            ad_id=result.external_id,
            campaign_id=campaign_id,
            spend=float(metrics.get("spend", 0)),
            impressions=int(metrics.get("impressions", 0)),
            clicks=int(metrics.get("clicks", 0)),
            ctr=float(metrics.get("ctr", 0)),
            cpm=float(metrics.get("cpm", 0)),
            cpc=float(metrics.get("cpc", 0)),
            cpi=float(metrics.get("cpi", 0)),
            source=RealitySource.META_ADS,
        )
        return [record]

    # ── Mock (sandbox) ──────────────────────────────────

    def _mock_ad_record(
        self,
        ad_id: str,
        date_range: dict[str, str] | None,
    ) -> AdPerformanceRecord:
        """生成 mock 单广告性能数据。"""
        seed = sum(ord(c) for c in ad_id) % 100 + 1
        spend = 100.0 + seed * 5.0
        impressions = 5000 + seed * 200
        clicks = int(impressions * 0.03)
        installs = int(clicks * 0.1)

        return AdPerformanceRecord(
            ad_id=ad_id,
            campaign_id=f"camp_from_{ad_id}",
            spend=spend,
            impressions=impressions,
            clicks=clicks,
            installs=installs,
            ctr=round(clicks / impressions, 4) if impressions > 0 else 0.0,
            cpm=round(spend / impressions * 1000, 2) if impressions > 0 else 0.0,
            cpc=round(spend / clicks, 2) if clicks > 0 else 0.0,
            cpi=round(spend / installs, 2) if installs > 0 else 0.0,
            source=RealitySource.META_ADS,
        )

    def _mock_campaign_records(
        self,
        campaign_id: str,
        date_range: dict[str, str] | None,
    ) -> list[AdPerformanceRecord]:
        """生成 mock Campaign 广告列表。"""
        seed = sum(ord(c) for c in campaign_id) % 100 + 1
        records: list[AdPerformanceRecord] = []
        for i in range(3):
            ad_id = f"{campaign_id}_ad_{i + 1}"
            records.append(self._mock_ad_record(ad_id, date_range))
        return records

    def __repr__(self) -> str:
        return f"MetaAdsReality(fetched={self.total_fetched})"