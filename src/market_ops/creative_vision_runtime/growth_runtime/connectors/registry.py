"""E13.1.1 Connector Registry — 管理所有外部数据连接器的注册、发现和生命周期."""

from __future__ import annotations

from typing import Any

from .base import BaseConnector
from .models import (
    ConnectorConfig,
    ConnectorHealth,
    ConnectorInfo,
    ConnectorStatus,
    DataSource,
    GrowthDataEvent,
)


class ConnectorRegistry:
    """连接器注册表 — 管理所有外部数据连接器.

    功能:
      - register(connector):    注册连接器
      - unregister(source):     注销连接器
      - get(source):            获取连接器
      - get_all():              获取所有连接器
      - get_healthy():          获取健康连接器
      - connect_all():          连接所有
      - health_check_all():     全量健康检查
      - collect_data():         从所有连接器收集数据
    """

    def __init__(self):
        self._connectors: dict[DataSource, BaseConnector] = {}
        self._configs: dict[DataSource, ConnectorConfig] = {}

    @property
    def connector_count(self) -> int:
        return len(self._connectors)

    @property
    def sources(self) -> list[DataSource]:
        return list(self._connectors.keys())

    # ── Registration ──────────────────────────────────────────

    def register(self, connector: BaseConnector) -> bool:
        """注册连接器."""
        source = connector.source
        self._connectors[source] = connector
        self._configs[source] = connector.config
        return True

    def unregister(self, source: DataSource) -> bool:
        """注销连接器."""
        if source in self._connectors:
            connector = self._connectors[source]
            connector.disconnect()
            del self._connectors[source]
            self._configs.pop(source, None)
            return True
        return False

    def get(self, source: DataSource) -> BaseConnector | None:
        """获取指定连接器."""
        return self._connectors.get(source)

    def get_all(self) -> list[BaseConnector]:
        """获取所有连接器."""
        return list(self._connectors.values())

    def get_healthy(self) -> list[BaseConnector]:
        """获取所有健康连接器."""
        return [c for c in self._connectors.values()
                if c.info.health == ConnectorHealth.HEALTHY]

    def get_connected(self) -> list[BaseConnector]:
        """获取所有已连接连接器."""
        return [c for c in self._connectors.values()
                if c.info.status == ConnectorStatus.CONNECTED]

    # ── Lifecycle ─────────────────────────────────────────────

    def connect_all(self) -> dict[DataSource, bool]:
        """连接所有连接器."""
        results: dict[DataSource, bool] = {}
        for source, connector in self._connectors.items():
            results[source] = connector.connect()
            if results[source]:
                connector.authenticate()
        return results

    def disconnect_all(self) -> None:
        """断开所有连接器."""
        for connector in self._connectors.values():
            connector.disconnect()

    def health_check_all(self) -> dict[DataSource, ConnectorHealth]:
        """全量健康检查."""
        results: dict[DataSource, ConnectorHealth] = {}
        for source, connector in self._connectors.items():
            results[source] = connector.health_check()
        return results

    # ── Data Collection ───────────────────────────────────────

    def collect_campaign_data(
        self, product_id: str = "", date_from: str = "", date_to: str = "",
    ) -> list[GrowthDataEvent]:
        """从所有广告连接器收集 Campaign 数据."""
        events: list[GrowthDataEvent] = []

        for connector in self.get_connected():
            if connector.source in {DataSource.META_ADS, DataSource.GOOGLE_ADS, DataSource.ASA}:
                try:
                    campaigns = connector.fetch_campaigns(
                        product_id=product_id,
                        date_from=date_from,
                        date_to=date_to,
                    )
                    for cm in campaigns:
                        events.append(GrowthDataEvent.from_campaign_metrics(cm))
                except Exception:
                    continue

        return events

    def collect_revenue_data(
        self, product_id: str = "", cohort_date: str = "",
    ) -> list[GrowthDataEvent]:
        """从归因平台收集收入数据."""
        events: list[GrowthDataEvent] = []

        for connector in self.get_connected():
            if connector.source in {DataSource.ADJUST, DataSource.APPSFLYER}:
                try:
                    retention = connector.fetch_retention(
                        product_id=product_id,
                        cohort_date=cohort_date,
                    )
                    if retention:
                        events.append(GrowthDataEvent.from_retention(retention))
                except Exception:
                    continue

        return events

    def collect_all(
        self, product_id: str = "", date_from: str = "", date_to: str = "",
    ) -> list[GrowthDataEvent]:
        """从所有连接器收集所有数据."""
        events: list[GrowthDataEvent] = []

        events.extend(self.collect_campaign_data(product_id, date_from, date_to))
        events.extend(self.collect_revenue_data(product_id))

        return events

    # ── Query ─────────────────────────────────────────────────

    def get_connector_info(self, source: DataSource) -> ConnectorInfo | None:
        """获取连接器信息."""
        connector = self._connectors.get(source)
        if connector:
            return connector.info
        return None

    def get_all_info(self) -> list[ConnectorInfo]:
        """获取所有连接器信息."""
        return [c.info for c in self._connectors.values()]

    def get_status_summary(self) -> dict[str, Any]:
        """获取状态摘要."""
        total = len(self._connectors)
        connected = len(self.get_connected())
        healthy = len(self.get_healthy())
        unhealthy = total - healthy

        return {
            "total_connectors": total,
            "connected": connected,
            "healthy": healthy,
            "unhealthy": unhealthy,
            "sources": [s.value for s in self._connectors],
            "connectors": [c.info.to_dict() for c in self._connectors.values()],
        }

    # ── Summary ───────────────────────────────────────────────

    def get_summary(self) -> dict[str, Any]:
        return {
            "connector_count": self.connector_count,
            "sources": [s.value for s in self._connectors],
            "status": self.get_status_summary(),
        }