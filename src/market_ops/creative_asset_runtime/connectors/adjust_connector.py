"""E11.2.4 — Adjust Performance Connector。

将 Adjust API 封装为事件驱动 Connector：
  - 拉取收入数据 → 发布 PERFORMANCE_UPDATED
  - 计算 ROAS → 触发 LifecycleWorker 状态转换
  - 支持增量同步（按日期范围）

设计原则：
  - 薄封装：将 Adjust 数据转换为 AssetEvent
  - 默认使用 Mock（AdjustClient 当前为 Mock 实现）
  - 事件格式兼容 LifecycleWorker.on_performance_updated()

Usage:
    client = AdjustClient(api_token="xxx", app_token="yyy")
    connector = AdjustConnector(client, event_bus)
    events = connector.poll()
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

from market_ops.adjust_ingestion.adjust_client import AdjustClient

from ..events.asset_events import AssetEvent, AssetEventType

if TYPE_CHECKING:
    from ..events.event_bus_adapter import AssetEventBus

logger = logging.getLogger(__name__)


class AdjustConnector:
    """Adjust API → AssetEvent 适配器。

    封装 AdjustClient，将拉取到的收入/留存数据转换为
    PERFORMANCE_UPDATED 事件。

    Attributes:
        last_synced_at: 上次同步时间
        total_synced:   累计同步数量
    """

    def __init__(
        self,
        client: AdjustClient,
        event_bus: AssetEventBus | None = None,
    ) -> None:
        self._client = client
        self._bus = event_bus

        self.last_synced_at: datetime | None = None
        self.total_synced: int = 0

    # ── Public API ───────────────────────────────────────

    def poll(self, lookback_days: int = 7) -> list[AssetEvent]:
        """拉取最新 Adjust 数据并发布事件。

        Args:
            lookback_days: 回溯天数（默认 7 = 最近一周）

        Returns:
            发布的事件列表
        """
        today = date.today()
        start = today - timedelta(days=lookback_days)

        logger.info(f"AdjustConnector: polling {start} → {today}")
        records = self._client.fetch_revenue(
            start_date=start.isoformat(),
            end_date=today.isoformat(),
        )

        events: list[AssetEvent] = []
        for record in records:
            event = self._record_to_event(record)
            events.append(event)

            if self._bus:
                self._bus.publish(event)

        self.total_synced += len(events)
        self.last_synced_at = datetime.now()

        logger.info(f"AdjustConnector: {len(events)} performance records published")
        return events

    def is_connected(self) -> bool:
        """检查 API 是否可用。"""
        return bool(self._client.api_token and self._client.app_token)

    # ── Internal ────────────────────────────────────────

    def _record_to_event(self, record: dict) -> AssetEvent:
        """将 Adjust 记录转换为 AssetEvent。

        Adjust 字段映射：
          creative_id → creative_id
          creative_name → payload.ad_name
          creative_asset_id → payload.creative_asset_id
          installs → payload.installs
          cohort_revenue_iap_d7 → payload.revenue_d7
          cohort_revenue_iap_d30 → payload.revenue_d30
          cohort_revenue_ad_d7 → payload.ad_revenue_d7
          cohort_retention_rate_d1 → payload.retention_d1
          cohort_retention_rate_d7 → payload.retention_d7
          cohort_paying_users_d30 → payload.payer_count_d30
        """
        creative_id = record.get("creative_id", "")

        # 计算总收入和 ROAS
        revenue_d7 = (
            float(record.get("cohort_revenue_iap_d7", 0))
            + float(record.get("cohort_revenue_ad_d7", 0))
        )
        revenue_d30 = (
            float(record.get("cohort_revenue_iap_d30", 0))
            + float(record.get("cohort_revenue_ad_d30", 0))
        )

        # ROAS: 收入 / 花费（spend 来自 Facebook，Adjust 不一定有 spend）
        # 此处暂设 spend=0，实际由 Facebook Insights 补充
        # 或由上游合并层填充
        roas_d7 = 0.0
        roas_d30 = 0.0

        return AssetEvent(
            event_type=AssetEventType.PERFORMANCE_UPDATED,
            creative_id=creative_id,
            payload={
                # Identity
                "creative_id": creative_id,
                "creative_name": record.get("creative_name", ""),
                "creative_asset_id": record.get("creative_asset_id", ""),
                "campaign_name": record.get("campaign_name", ""),

                # Users
                "installs": int(record.get("installs", 0)),
                "sessions": int(record.get("sessions", 0)),
                "payer_count_d30": int(record.get("cohort_paying_users_d30", 0)),

                # Retention
                "retention_d1": float(record.get("cohort_retention_rate_d1", 0)),
                "retention_d7": float(record.get("cohort_retention_rate_d7", 0)),
                "retention_d30": float(record.get("cohort_retention_rate_d30", 0)),

                # Revenue
                "revenue_iap_d7": float(record.get("cohort_revenue_iap_d7", 0)),
                "revenue_iap_d30": float(record.get("cohort_revenue_iap_d30", 0)),
                "revenue_ad_d7": float(record.get("cohort_revenue_ad_d7", 0)),
                "revenue_ad_d30": float(record.get("cohort_revenue_ad_d30", 0)),
                "revenue_d7": revenue_d7,
                "revenue_d30": revenue_d30,

                # ROAS (待 Facebook spend 合并)
                "roas_d7": roas_d7,
                "roas_d30": roas_d30,

                # Meta
                "date": record.get("date", ""),
                "source": "adjust",
            },
        )

    def __repr__(self) -> str:
        return f"AdjustConnector(synced={self.total_synced})"