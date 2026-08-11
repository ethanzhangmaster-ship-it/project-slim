"""E12.1 — Adjust Reality Connector。

在 AdjustTracker 之上构建统一门面层，将 Adjust 归因数据
转换为 E11 Evolution 可消费的 RevenuePerformance。

设计原则：
  - 薄门面：不重复实现 API 逻辑，纯桥接
  - 默认 sandbox（mock），生产环境通过 config 切换
  - 支持按 Campaign ID / Date Range 拉取
  - 输出统一 RevenuePerformance（含 D1/D7/D30 ROAS、LTV、留存）

Usage:
    reality = AdjustReality(tracker)
    records = reality.fetch_revenue("camp_001", "2024-01-01", "2024-01-07")
    records = reality.fetch_recent_revenue(["camp_001", "camp_002"], lookback_days=7)
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING

from .models import RealitySource, RevenuePerformance

if TYPE_CHECKING:
    from market_ops.execution_runtime.attribution.base_tracker import (
        AttributionMetrics,
        AttributionTracker,
    )

logger = logging.getLogger(__name__)


class AdjustReality:
    """Adjust 统一门面层。

    封装 AttributionTracker（AdjustTracker），提供 E11 友好的
    收入/留存数据拉取接口。

    Attributes:
        tracker:           底层 AttributionTracker
        total_fetched:     累计拉取记录数
        last_fetched_at:   上次拉取时间
    """

    def __init__(
        self,
        tracker: AttributionTracker | None = None,
    ) -> None:
        self._tracker = tracker

        self.total_fetched: int = 0
        self.last_fetched_at: datetime | None = None

    # ── Public API ───────────────────────────────────────

    def fetch_revenue(
        self,
        campaign_id: str,
        start_date: str,
        end_date: str,
    ) -> RevenuePerformance | None:
        """拉取单个 Campaign 的收入性能数据。

        Args:
            campaign_id:   Campaign ID
            start_date:    ISO date (YYYY-MM-DD)
            end_date:      ISO date (YYYY-MM-DD)

        Returns:
            RevenuePerformance 或 None
        """
        if not self._tracker:
            return self._mock_revenue(campaign_id, start_date, end_date)

        metrics = self._tracker.get_campaign_metrics(
            campaign_id, start_date, end_date,
        )
        return self._metrics_to_revenue(metrics)

    def fetch_multi_revenue(
        self,
        campaign_ids: list[str],
        start_date: str,
        end_date: str,
    ) -> list[RevenuePerformance]:
        """批量拉取多个 Campaign 的收入数据。

        Args:
            campaign_ids:  Campaign ID 列表
            start_date:    ISO date
            end_date:      ISO date

        Returns:
            RevenuePerformance 列表
        """
        records: list[RevenuePerformance] = []
        for cid in campaign_ids:
            record = self.fetch_revenue(cid, start_date, end_date)
            if record:
                records.append(record)

        self.total_fetched += len(records)
        self.last_fetched_at = datetime.now(timezone.utc)

        logger.info(
            f"AdjustReality: fetched {len(records)} revenue records "
            f"(total: {self.total_fetched})"
        )
        return records

    def fetch_recent_revenue(
        self,
        campaign_ids: list[str],
        lookback_days: int = 7,
    ) -> list[RevenuePerformance]:
        """拉取最近 N 天的收入数据。

        Args:
            campaign_ids:   Campaign ID 列表
            lookback_days:  回溯天数

        Returns:
            RevenuePerformance 列表
        """
        today = date.today()
        start = (today - timedelta(days=lookback_days)).isoformat()
        end = today.isoformat()
        return self.fetch_multi_revenue(campaign_ids, start, end)

    def is_connected(self) -> bool:
        """检查是否已连接 Adjust API。"""
        if not self._tracker:
            return False
        return True

    # ── Internal ────────────────────────────────────────

    def _metrics_to_revenue(
        self,
        metrics: AttributionMetrics,
    ) -> RevenuePerformance:
        """将 AttributionMetrics 转换为 RevenuePerformance。"""
        return RevenuePerformance(
            campaign_id=metrics.campaign_id,
            installs=metrics.installs,
            revenue_d1=metrics.revenue_d1,
            revenue_d7=metrics.revenue_d7,
            revenue_d30=metrics.revenue_d30,
            ltv=metrics.revenue_d30 * 1.5,  # 简单 LTV 估算
            roas_d1=round(metrics.revenue_d1 / metrics.spend, 4) if metrics.spend > 0 else 0.0,
            roas_d7=metrics.roi_d7,
            roas_d30=metrics.roi_d30,
            retention_d1=round(metrics.installs / metrics.installs, 4) if metrics.installs > 0 else 0.0,
            retention_d7=0.3,  # mock 默认值
            retention_d30=0.1,
            payer_rate=metrics.cvr,
            arppu=round(metrics.revenue_d30 / metrics.installs, 2) if metrics.installs > 0 else 0.0,
            cohort_size=metrics.installs,
            source=RealitySource.ADJUST,
        )

    # ── Mock (sandbox) ──────────────────────────────────

    def _mock_revenue(
        self,
        campaign_id: str,
        start_date: str,
        end_date: str,
    ) -> RevenuePerformance:
        """生成 mock 收入数据。"""
        seed = sum(ord(c) for c in campaign_id) % 100 + 1
        installs = 200 + seed * 5
        spend = 500.0 + seed * 10.0
        revenue_d7 = spend * (1.0 + seed * 0.02)
        revenue_d30 = revenue_d7 * 1.5

        return RevenuePerformance(
            campaign_id=campaign_id,
            installs=installs,
            revenue_d1=round(revenue_d7 * 0.3, 2),
            revenue_d7=round(revenue_d7, 2),
            revenue_d30=round(revenue_d30, 2),
            revenue_d120=round(revenue_d30 * 1.8, 2),
            ltv=round(revenue_d30 * 1.5, 2),
            roas_d1=round(revenue_d7 * 0.3 / spend, 4) if spend > 0 else 0.0,
            roas_d7=round(revenue_d7 / spend, 4) if spend > 0 else 0.0,
            roas_d30=round(revenue_d30 / spend, 4) if spend > 0 else 0.0,
            roas_d120=round(revenue_d30 * 1.8 / spend, 4) if spend > 0 else 0.0,
            retention_d1=0.45,
            retention_d7=0.30,
            retention_d30=0.12,
            payer_rate=0.05,
            arppu=round(revenue_d30 / (installs * 0.05), 2) if installs > 0 else 0.0,
            cohort_size=installs,
            source=RealitySource.ADJUST,
        )

    def __repr__(self) -> str:
        return f"AdjustReality(fetched={self.total_fetched})"