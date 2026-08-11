"""E11.2.4 — Facebook Runtime Connector。

将 Facebook SyncEngine 封装为事件驱动 Connector：
  - 拉取新广告 → 发布 FACEBOOK_CREATIVE_CREATED
  - 提取 A-Number → 触发 BindingWorker
  - 支持增量同步（仅拉取新数据）

设计原则：
  - 薄封装：不重复 SyncEngine 逻辑，只做事件转换
  - 幂等：重复拉取不会重复发布事件（通过 last_synced_at 去重）
  - 容错：API 失败不影响事件总线

Usage:
    client = FacebookClient(access_token="xxx", ad_account_id="123456")
    connector = FacebookConnector(client, event_bus)
    new_creatives = connector.poll()
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

from market_ops.facebook_ingestion.facebook_client import FacebookClient
from market_ops.facebook_ingestion.sync_engine import SyncEngine

from ..events.asset_events import AssetEvent, AssetEventType

if TYPE_CHECKING:
    from ..events.event_bus_adapter import AssetEventBus

logger = logging.getLogger(__name__)


class FacebookConnector:
    """Facebook Graph API → AssetEvent 适配器。

    封装 SyncEngine，将拉取到的 FacebookCreativeEntity 转换为
    FACEBOOK_CREATIVE_CREATED 事件。

    Attributes:
        last_synced_at: 上次同步时间（用于增量去重）
        total_synced:   累计同步数量
    """

    def __init__(
        self,
        client: FacebookClient,
        event_bus: AssetEventBus | None = None,
        product: str = "MW",
    ) -> None:
        self._engine = SyncEngine(client)
        self._bus = event_bus
        self._product = product

        self.last_synced_at: datetime | None = None
        self.total_synced: int = 0
        self._seen_creative_ids: set[str] = set()

    # ── Public API ───────────────────────────────────────

    def poll(self, lookback_days: int = 1) -> list[AssetEvent]:
        """拉取最新广告数据并发布事件。

        Args:
            lookback_days: 回溯天数（默认 1 = 昨天至今）

        Returns:
            发布的事件列表
        """
        today = date.today()
        start = today - timedelta(days=lookback_days)

        logger.info(f"FacebookConnector: polling {start} → {today}")
        result = self._engine.sync(start, today)

        events: list[AssetEvent] = []

        # 遍历所有已同步的 Entity
        entities = self._engine.merge_all_entities()
        for entity in entities:
            # 去重：已见过的 creative_id 跳过
            if entity.creative_id in self._seen_creative_ids:
                continue

            self._seen_creative_ids.add(entity.creative_id)

            # 提取 A-Number
            a_number = self._extract_a_number(entity.ad_name)

            # 构建事件
            event = AssetEvent(
                event_type=AssetEventType.FACEBOOK_CREATIVE_CREATED,
                creative_id=entity.creative_id,
                payload={
                    "ad_name": entity.ad_name,
                    "creative_id": entity.creative_id,
                    "ad_id": entity.ad_id,
                    "creative_asset_id": entity.creative_asset_id,
                    "legacy_id": entity.legacy_id,
                    "creative_type": entity.creative_type.value,
                    "campaign_id": entity.campaign_id,
                    "campaign_name": entity.campaign_name,
                    "adset_name": entity.adset_name,
                    "status": entity.status,
                    "created_time": entity.created_time,
                    "a_number": a_number,
                    "spend": entity.spend,
                    "impressions": entity.impressions,
                    "clicks": entity.clicks,
                    "installs": entity.installs,
                },
            )

            events.append(event)

            if self._bus:
                self._bus.publish(event)

        self.total_synced += len(events)
        self.last_synced_at = datetime.now()

        logger.info(
            f"FacebookConnector: {result.total_ads} ads, "
            f"{len(events)} new creatives published"
        )
        return events

    def poll_insights(
        self,
        lookback_days: int = 1,
    ) -> list[AssetEvent]:
        """拉取广告成效数据并发布 PERFORMANCE_UPDATED 事件。

        Args:
            lookback_days: 回溯天数

        Returns:
            发布的事件列表
        """
        today = date.today()
        start = today - timedelta(days=lookback_days)

        insights = self._engine.client.get_creative_insights(start, today)
        events: list[AssetEvent] = []

        for row in insights:
            creative_data = row.get("creative", {})
            creative_id = creative_data.get("id", "") if isinstance(creative_data, dict) else ""

            if not creative_id:
                continue

            event = AssetEvent(
                event_type=AssetEventType.PERFORMANCE_UPDATED,
                creative_id=creative_id,
                payload={
                    "ad_name": row.get("ad_name", ""),
                    "spend": float(row.get("spend", 0)),
                    "impressions": int(row.get("impressions", 0)),
                    "clicks": int(row.get("clicks", 0)),
                    "ctr": float(row.get("ctr", 0)),
                    "cpc": float(row.get("cpc", 0)),
                    "cpm": float(row.get("cpm", 0)),
                    "date_start": row.get("date_start", ""),
                    "date_stop": row.get("date_stop", ""),
                    "source": "facebook_insights",
                },
            )

            events.append(event)

            if self._bus:
                self._bus.publish(event)

        return events

    def is_connected(self) -> bool:
        """检查 API 是否可用（简单健康检查）。"""
        try:
            ads = self._engine.client.get_ads()
            return len(ads) > 0
        except Exception:
            return False

    # ── Internal ────────────────────────────────────────

    @staticmethod
    def _extract_a_number(ad_name: str) -> str:
        """从广告名称提取 A-Number。"""
        import re
        match = re.search(r"A(\d{1,4})", ad_name, re.IGNORECASE)
        if match:
            return f"A{match.group(1)}"
        return ""

    def __repr__(self) -> str:
        return (
            f"FacebookConnector(account={self._engine.client.account_id}, "
            f"synced={self.total_synced})"
        )