"""E13.1.4 MAX Connector Adapter — 对接 E13.1.1 BaseConnector 框架."""

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
    UserRevenueCurve,
)
from .client import MAXClient
from .models import (
    MAXPerformance,
    MAXRevenueEvent,
    MAXRevenueSnapshot,
    MAXWaterfallEntry,
)
from .revenue_mapper import MAXRevenueMapper
from .validator import (
    MAXPerformanceValidator,
    MAXRevenueEventValidator,
    MAXRevenueSnapshotValidator,
    MAXWaterfallValidator,
)


class MAXConnector(BaseConnector):
    """MAX 广告变现 Reality Connector.

    将 MAX 的广告收入、eCPM、ARPDAU、Waterfall 数据接入 Growth OS，
    为 IAA / Hybrid 产品提供完整的广告变现视图。

    数据流:
      MAX API → MAXClient → MAXRevenueMapper
        → MAXRevenueSnapshot → Reality Layer → UserValueSnapshot.ad_revenue
    """

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        is_mock = not config.api_key or config.api_key.lower() == "mock"
        self._client = MAXClient(
            api_key=config.api_key if not is_mock else "",
            use_mock=is_mock,
        )
        self._revenue_events: list[MAXRevenueEvent] = []
        self._performances: list[MAXPerformance] = []
        self._waterfall: list[MAXWaterfallEntry] = []
        self._snapshot: MAXRevenueSnapshot | None = None
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
        """拉取广告收入曲线."""
        self._sync_performance(product_id)

        if not self._performances:
            return None

        snapshot = MAXRevenueMapper.build_snapshot(
            performances=self._performances,
            product_id=product_id,
        )

        return UserRevenueCurve(
            product_id=snapshot.product_id,
            platform=DataSource.MAX,
            cohort_date=cohort_date or snapshot.date,
            d0_revenue=snapshot.arpdau,
            d1_revenue=snapshot.arpdau * 0.95,
            d7_revenue=snapshot.arpdau * 7,
            d30_revenue=snapshot.arpdau * 30,
            predicted_ltv=snapshot.arpdau * 30,
            cohort_size=snapshot.dau,
        )

    # ── Sync Operations ───────────────────────────────────────

    def sync_all(
        self,
        product_id: str = "",
        start_date: str = "",
        end_date: str = "",
    ) -> dict[str, Any]:
        """全量同步: Revenue Events, Performance, Waterfall."""
        self._sync_revenue_events(start_date, end_date)
        self._sync_performance(product_id, start_date, end_date)
        self._sync_waterfall()
        self._build_snapshot(product_id)
        self._last_sync_at = datetime.now(timezone.utc).isoformat()

        return {
            "revenue_events": len(self._revenue_events),
            "performances": len(self._performances),
            "waterfall": len(self._waterfall),
            "has_snapshot": self._snapshot is not None,
            "last_sync_at": self._last_sync_at,
        }

    def sync_revenue_events(
        self, start_date: str = "", end_date: str = "",
    ) -> list[MAXRevenueEvent]:
        """同步广告收入事件."""
        return self._sync_revenue_events(start_date, end_date)

    def sync_performance(
        self,
        product_id: str = "",
        start_date: str = "",
        end_date: str = "",
    ) -> list[MAXPerformance]:
        """同步聚合表现数据."""
        return self._sync_performance(product_id, start_date, end_date)

    def sync_waterfall(
        self, ad_unit_id: str = "", date: str = "",
    ) -> list[MAXWaterfallEntry]:
        """同步 Waterfall 数据."""
        return self._sync_waterfall(ad_unit_id, date)

    def _sync_revenue_events(
        self, start_date: str = "", end_date: str = "",
    ) -> list[MAXRevenueEvent]:
        if not start_date and not end_date:
            end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            start_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

        events = self._client.fetch_revenue_events(
            start_date=start_date,
            end_date=end_date,
        )
        validated = MAXRevenueEventValidator.filter_valid(events)
        self._revenue_events = validated
        return validated

    def _sync_performance(
        self,
        product_id: str = "",
        start_date: str = "",
        end_date: str = "",
    ) -> list[MAXPerformance]:
        if not start_date and not end_date:
            end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            start_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

        performances = self._client.fetch_performance(
            start_date=start_date,
            end_date=end_date,
        )
        validated = MAXPerformanceValidator.filter_valid(performances)
        self._performances = validated
        return validated

    def _sync_waterfall(
        self, ad_unit_id: str = "", date: str = "",
    ) -> list[MAXWaterfallEntry]:
        entries = self._client.fetch_waterfall(
            ad_unit_id=ad_unit_id,
            date=date,
        )
        validated = MAXWaterfallValidator.filter_valid(entries)
        self._waterfall = validated
        return validated

    def _build_snapshot(self, product_id: str = "") -> MAXRevenueSnapshot | None:
        """从同步数据构建收入快照."""
        if not self._performances:
            return None

        snapshot = MAXRevenueMapper.build_snapshot(
            performances=self._performances,
            revenue_events=self._revenue_events,
            waterfall=self._waterfall,
            product_id=product_id,
        )

        result = MAXRevenueSnapshotValidator.validate(snapshot)
        if result.is_valid:
            self._snapshot = snapshot
            return snapshot
        return None

    # ── Revenue Snapshot ──────────────────────────────────────

    def build_revenue_snapshot(
        self,
        product_id: str = "",
        date: str = "",
    ) -> MAXRevenueSnapshot | None:
        """构建收入快照 — 核心输出."""
        if not self._performances:
            self._sync_performance(product_id)

        return self._build_snapshot(product_id)

    def build_snapshots_by_date(
        self,
        product_id: str = "",
    ) -> list[MAXRevenueSnapshot]:
        """按日期构建多个快照."""
        if not self._performances:
            self._sync_performance(product_id)

        snapshots = MAXRevenueMapper.build_snapshots_by_date(
            performances=self._performances,
            product_id=product_id,
        )

        validated = []
        for s in snapshots:
            if MAXRevenueSnapshotValidator.validate(s).is_valid:
                validated.append(s)

        return validated

    def build_snapshot_by_network(
        self,
        product_id: str = "",
        date: str = "",
    ) -> dict[str, MAXRevenueSnapshot]:
        """按网络分别构建快照."""
        if not self._performances:
            self._sync_performance(product_id)

        return MAXRevenueMapper.build_snapshot_by_network(
            performances=self._performances,
            product_id=product_id,
            date=date,
        )

    # ── Growth Data Events ────────────────────────────────────

    def collect_events(
        self, product_id: str = "", date_from: str = "", date_to: str = "",
    ) -> list[GrowthDataEvent]:
        """收集所有 Growth Data Events — 输出到 E13.1.1 框架."""
        growth_events: list[GrowthDataEvent] = []

        if not self._performances:
            self._sync_performance(product_id, date_from, date_to)

        # Revenue event
        snapshot = self.build_revenue_snapshot(product_id)
        if snapshot:
            growth_events.append(GrowthDataEvent(
                event_type=MetricType.REVENUE,
                source=DataSource.MAX,
                product_id=snapshot.product_id,
                date=snapshot.date,
                metrics={
                    "ad_revenue": snapshot.total_revenue,
                    "total_impressions": snapshot.total_impressions,
                    "ecpm": snapshot.ecpm,
                    "arpdau": snapshot.arpdau,
                    "fill_rate": snapshot.fill_rate,
                    "show_rate": snapshot.show_rate,
                    "dau": snapshot.dau,
                },
            ))

        # ARPU event
        if snapshot:
            growth_events.append(GrowthDataEvent(
                event_type=MetricType.ARPU,
                source=DataSource.MAX,
                product_id=snapshot.product_id,
                date=snapshot.date,
                metrics={
                    "arpdau": snapshot.arpdau,
                    "ecpm": snapshot.ecpm,
                    "ad_revenue": snapshot.total_revenue,
                },
            ))

        return growth_events

    # ── Analytics ─────────────────────────────────────────────

    def get_network_stats(self) -> dict[str, dict[str, Any]]:
        """获取各网络收入统计."""
        return MAXRevenueMapper.compute_network_stats(self._performances)

    def get_waterfall_stats(self) -> dict[str, Any]:
        """获取 Waterfall 统计."""
        return MAXRevenueMapper.compute_waterfall_stats(self._waterfall)

    def get_ecpm_trend(
        self, days: int = 7,
    ) -> list[dict[str, Any]]:
        """获取 eCPM 趋势."""
        if not self._performances:
            self._sync_performance()

        by_date: dict[str, list[MAXPerformance]] = {}
        for p in self._performances:
            by_date.setdefault(p.date, []).append(p)

        trend = []
        for date_key in sorted(by_date.keys())[-days:]:
            perfs = by_date[date_key]
            total_rev = sum(p.revenue for p in perfs)
            total_imp = sum(p.impressions for p in perfs)
            trend.append({
                "date": date_key,
                "revenue": round(total_rev, 6),
                "impressions": total_imp,
                "ecpm": round(total_rev / total_imp * 1000, 4) if total_imp > 0 else 0.0,
            })

        return trend

    # ── Properties ────────────────────────────────────────────

    @property
    def revenue_events(self) -> list[MAXRevenueEvent]:
        return self._revenue_events

    @property
    def performances(self) -> list[MAXPerformance]:
        return self._performances

    @property
    def waterfall(self) -> list[MAXWaterfallEntry]:
        return self._waterfall

    @property
    def snapshot(self) -> MAXRevenueSnapshot | None:
        return self._snapshot

    @property
    def last_sync_at(self) -> str:
        return self._last_sync_at

    # ── Summary ───────────────────────────────────────────────

    def get_summary(self) -> dict[str, Any]:
        return {
            **super().get_summary(),
            "client_summary": self._client.get_summary(),
            "revenue_events_count": len(self._revenue_events),
            "performances_count": len(self._performances),
            "waterfall_count": len(self._waterfall),
            "has_snapshot": self._snapshot is not None,
            "last_sync_at": self._last_sync_at,
            "network_stats": self.get_network_stats() if self._performances else {},
            "waterfall_stats": self.get_waterfall_stats() if self._waterfall else {},
        }