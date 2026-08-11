"""E13.1.3 Adjust Connector — Adjust 用户生命周期 Reality Connector."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from ..base import BaseConnector
from ..models import (
    ConnectorConfig,
    ConnectorHealth,
    DataSource,
    GrowthDataEvent,
    MetricType,
    RetentionCurve,
    UserRevenueCurve,
)
from .attribution import AttributionMapper
from .client import AdjustClient
from .mapper import AdjustValueMapper
from .models import (
    AdjustEventType,
    AdjustUserEvent,
    AttributionRecord,
    RetentionSnapshot,
    UserValueSnapshot,
)
from .validator import (
    AdjustEventValidator,
    AttributionValidator,
    RetentionValidator,
    UserValueValidator,
)


class AdjustConnector(BaseConnector):
    """Adjust 用户生命周期 Reality Connector.

    将 Adjust 的归因、用户行为、留存、收入事件接入 Growth OS，
    为 IAA / IAP / Hybrid 产品提供统一用户价值视图。

    数据流:
      Adjust API → AdjustClient → AdjustEventParser → AdjustValueMapper
        → UserValueSnapshot → Reality Layer → ROAS Predictor → Meta Decision Engine
    """

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        is_mock = not config.access_token or config.access_token.lower() == "mock"
        self._client = AdjustClient(
            api_token=config.access_token if not is_mock else "",
            app_token=config.app_id,
            use_mock=is_mock,
        )
        self._events: list[AdjustUserEvent] = []
        self._attributions: list[AttributionRecord] = []
        self._retention: RetentionSnapshot | None = None
        self._snapshots: list[UserValueSnapshot] = []
        self._last_sync_at: str = ""

    # ── BaseConnector Abstract Methods ────────────────────────

    def _do_connect(self) -> None:
        self._client.connect()

    def _do_disconnect(self) -> None:
        self._client.disconnect()

    def _do_authenticate(self) -> None:
        self._client.authenticate()

    def _do_health_check(self) -> ConnectorHealth:
        if not self._client.is_connected:
            return ConnectorHealth.UNHEALTHY
        if not self._client.is_authenticated:
            return ConnectorHealth.DEGRADED
        return ConnectorHealth.HEALTHY

    # ── Data Fetching Overrides ───────────────────────────────

    def fetch_revenue_curve(
        self, product_id: str = "", cohort_date: str = "",
    ) -> UserRevenueCurve | None:
        """拉取用户收入曲线 — 从 Adjust 事件聚合."""
        self._sync_events(product_id)
        self._sync_retention(product_id)

        if not self._events:
            return None

        snapshot = AdjustValueMapper.build_snapshot(
            events=self._events,
            retention=self._retention,
            attributions=self._attributions,
            product_id=product_id,
        )

        return UserRevenueCurve(
            product_id=snapshot.product_id,
            platform=DataSource.ADJUST,
            cohort_date=cohort_date or snapshot.date,
            d0_revenue=snapshot.arpu,
            d1_revenue=snapshot.arpu * 0.95,
            d7_revenue=snapshot.arpu * 7,
            d30_revenue=snapshot.arpu * 30,
            predicted_ltv=snapshot.ltv_indicator,
            cohort_size=snapshot.total_users,
        )

    def fetch_retention(
        self, product_id: str = "", cohort_date: str = "",
    ) -> RetentionCurve | None:
        """拉取留存数据."""
        retention = self._client.fetch_retention(
            product_id=product_id,
            cohort_date=cohort_date,
        )
        if retention is None:
            return None

        retention_result = RetentionValidator.validate(retention)
        if not retention_result.is_valid:
            return None

        return retention.to_e1311_retention_curve()

    # ── Sync Operations ───────────────────────────────────────

    def sync_all(
        self,
        product_id: str = "",
        start_date: str = "",
        end_date: str = "",
    ) -> dict[str, Any]:
        """全量同步: Events, Attribution, Retention."""
        self._sync_events(product_id, start_date, end_date)
        self._sync_attribution(start_date, end_date)
        self._sync_retention(product_id)
        self._last_sync_at = datetime.now(timezone.utc).isoformat()

        return {
            "events": len(self._events),
            "attributions": len(self._attributions),
            "has_retention": self._retention is not None,
            "last_sync_at": self._last_sync_at,
        }

    def sync_events(
        self,
        product_id: str = "",
        start_date: str = "",
        end_date: str = "",
    ) -> list[AdjustUserEvent]:
        """同步用户事件."""
        return self._sync_events(product_id, start_date, end_date)

    def sync_attribution(
        self, start_date: str = "", end_date: str = "",
    ) -> list[AttributionRecord]:
        """同步归因数据."""
        return self._sync_attribution(start_date, end_date)

    def sync_retention(
        self, product_id: str = "", cohort_date: str = "",
    ) -> RetentionSnapshot | None:
        """同步留存数据."""
        return self._sync_retention(product_id, cohort_date)

    def _sync_events(
        self,
        product_id: str = "",
        start_date: str = "",
        end_date: str = "",
    ) -> list[AdjustUserEvent]:
        if not start_date and not end_date:
            end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            start_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

        events = self._client.fetch_events(
            product_id=product_id,
            start_date=start_date,
            end_date=end_date,
        )

        validated = AdjustEventValidator.filter_valid(events)
        self._events = validated
        return validated

    def _sync_attribution(
        self, start_date: str = "", end_date: str = "",
    ) -> list[AttributionRecord]:
        if not start_date and not end_date:
            end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            start_date = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")

        attributions = self._client.fetch_attribution(
            start_date=start_date,
            end_date=end_date,
        )

        validated = AttributionValidator.filter_valid(attributions)
        self._attributions = validated
        return validated

    def _sync_retention(
        self, product_id: str = "", cohort_date: str = "",
    ) -> RetentionSnapshot | None:
        retention = self._client.fetch_retention(
            product_id=product_id,
            cohort_date=cohort_date,
        )
        if retention is not None:
            result = RetentionValidator.validate(retention)
            if result.is_valid:
                self._retention = retention
                return retention
        return None

    # ── User Value Snapshot ───────────────────────────────────

    def build_user_value_snapshot(
        self,
        product_id: str = "",
        date: str = "",
    ) -> UserValueSnapshot | None:
        """构建用户价值快照 — 核心输出.

        聚合 Adjust 事件、归因和留存数据，生成标准 UserValueSnapshot。
        """
        if not self._events:
            self._sync_events(product_id)

        snapshot = AdjustValueMapper.build_snapshot(
            events=self._events,
            retention=self._retention,
            attributions=self._attributions,
            product_id=product_id,
            date=date,
        )

        result = UserValueValidator.validate(snapshot)
        if not result.is_valid:
            return None

        return snapshot

    def build_snapshots_by_date(
        self,
        product_id: str = "",
    ) -> list[UserValueSnapshot]:
        """按日期构建多个快照."""
        if not self._events:
            self._sync_events(product_id)

        snapshots = AdjustValueMapper.build_snapshots_by_date(
            events=self._events,
            retention=self._retention,
            attributions=self._attributions,
            product_id=product_id,
        )

        validated = []
        for s in snapshots:
            if UserValueValidator.validate(s).is_valid:
                validated.append(s)

        self._snapshots = validated
        return validated

    def build_snapshot_by_network(
        self,
        product_id: str = "",
        date: str = "",
    ) -> dict[str, UserValueSnapshot]:
        """按网络分别构建快照."""
        if not self._events:
            self._sync_events(product_id)

        return AdjustValueMapper.build_snapshot_by_network(
            events=self._events,
            product_id=product_id,
            date=date,
        )

    # ── Growth Data Events ────────────────────────────────────

    def collect_events(
        self, product_id: str = "", date_from: str = "", date_to: str = "",
    ) -> list[GrowthDataEvent]:
        """收集所有 Growth Data Events — 输出到 E13.1.1 框架."""
        growth_events: list[GrowthDataEvent] = []

        if not self._events:
            self._sync_events(product_id, date_from, date_to)

        # Revenue event
        snapshot = self.build_user_value_snapshot(product_id)
        if snapshot:
            growth_events.append(GrowthDataEvent(
                event_type=MetricType.REVENUE,
                source=DataSource.ADJUST,
                product_id=snapshot.product_id,
                date=snapshot.date,
                metrics={
                    "total_revenue": snapshot.total_revenue,
                    "iap_revenue": snapshot.iap_revenue,
                    "ad_revenue": snapshot.ad_revenue,
                    "subscription_revenue": snapshot.subscription_revenue,
                    "arpu": snapshot.arpu,
                    "arppu": snapshot.arppu,
                    "paying_rate": snapshot.paying_rate,
                    "total_users": snapshot.total_users,
                    "new_users": snapshot.new_users,
                    "paying_users": snapshot.paying_users,
                    "installs": snapshot.installs,
                },
            ))

        # Retention event
        if self._retention:
            growth_events.append(GrowthDataEvent(
                event_type=MetricType.RETENTION,
                source=DataSource.ADJUST,
                product_id=self._retention.product_id,
                date=self._retention.cohort_date,
                metrics={
                    "d1_retention": self._retention.d1,
                    "d7_retention": self._retention.d7,
                    "d30_retention": self._retention.d30,
                    "cohort_size": self._retention.cohort_size,
                },
            ))

        # ARPU event
        if snapshot:
            growth_events.append(GrowthDataEvent(
                event_type=MetricType.ARPU,
                source=DataSource.ADJUST,
                product_id=snapshot.product_id,
                date=snapshot.date,
                metrics={
                    "arpu": snapshot.arpu,
                    "arppu": snapshot.arppu,
                    "ltv_indicator": snapshot.ltv_indicator,
                },
            ))

        return growth_events

    # ── Attribution Analytics ─────────────────────────────────

    def get_network_stats(self) -> dict[str, dict[str, Any]]:
        """获取网络归因统计."""
        return AttributionMapper.get_network_stats(self._attributions)

    def get_organic_vs_paid_split(self) -> dict[str, int]:
        """获取 Organic vs Paid 分布."""
        return AttributionMapper.compute_organic_vs_paid_split(self._attributions)

    def link_events_to_attribution(self) -> list[AdjustUserEvent]:
        """将事件链接到归因记录."""
        self._events = AttributionMapper.link_events_to_attribution(
            self._events, self._attributions,
        )
        return self._events

    def get_revenue_breakdown(self) -> dict[str, float]:
        """获取收入构成."""
        return AdjustValueMapper.compute_revenue_breakdown(self._events)

    def get_event_type_counts(self) -> dict[str, int]:
        """获取事件类型统计."""
        return AdjustValueMapper.compute_event_type_counts(self._events)

    # ── Properties ────────────────────────────────────────────

    @property
    def events(self) -> list[AdjustUserEvent]:
        return self._events

    @property
    def attributions(self) -> list[AttributionRecord]:
        return self._attributions

    @property
    def retention(self) -> RetentionSnapshot | None:
        return self._retention

    @property
    def snapshots(self) -> list[UserValueSnapshot]:
        return self._snapshots

    @property
    def last_sync_at(self) -> str:
        return self._last_sync_at

    # ── Summary ───────────────────────────────────────────────

    def get_summary(self) -> dict[str, Any]:
        return {
            **super().get_summary(),
            "client_summary": self._client.get_summary(),
            "events_count": len(self._events),
            "attributions_count": len(self._attributions),
            "has_retention": self._retention is not None,
            "snapshots_count": len(self._snapshots),
            "last_sync_at": self._last_sync_at,
            "network_stats": self.get_network_stats() if self._attributions else {},
            "revenue_breakdown": self.get_revenue_breakdown() if self._events else {},
        }