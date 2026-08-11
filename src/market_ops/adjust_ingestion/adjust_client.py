"""E11 Phase 2 — Adjust API Client。

Adjust API 客户端，负责：
  - API Token 管理
  - 请求 Adjust 数据
  - 分页
  - 重试
  - 错误处理

当前使用 Mock 实现，后续可替换为真实 Adjust API 调用。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


class AdjustAPIError(Exception):
    """Adjust API 异常。"""
    pass


@dataclass
class AdjustClient:
    """Adjust API 客户端。

    支持分页（PAGE_LIMIT=200）和自动重试（MAX_RETRIES=3）。

    Usage:
        client = AdjustClient(api_token="xxx", app_token="yyy")
        records = client.fetch_revenue("2026-07-01", "2026-07-21")
    """

    api_token: str = ""
    app_token: str = ""
    base_url: str = "https://api.adjust.com"

    _page_limit: int = field(default=200, repr=False)
    _max_retries: int = field(default=3, repr=False)
    _retry_delay: float = field(default=1.0, repr=False)

    def fetch_revenue(
        self,
        start_date: str,
        end_date: str,
    ) -> list[dict[str, Any]]:
        """获取 Adjust 收入数据。

        Args:
            start_date: 起始日期 (YYYY-MM-DD)
            end_date:   结束日期 (YYYY-MM-DD)

        Returns:
            Adjust 收入记录列表，每条记录包含 creative_id, installs, revenue 等字段
        """
        return self._fetch_with_pagination(start_date, end_date)

    def _fetch_with_pagination(
        self,
        start_date: str,
        end_date: str,
    ) -> list[dict[str, Any]]:
        """分页获取所有数据。"""
        all_records: list[dict[str, Any]] = []
        page = 0

        while True:
            page += 1
            records = self._request(start_date, end_date, page)
            if not records:
                break
            all_records.extend(records)
            if len(records) < self._page_limit:
                break

        return all_records

    def _request(
        self,
        start_date: str,
        end_date: str,
        page: int,
    ) -> list[dict[str, Any]]:
        """发送请求（含重试逻辑）。"""
        last_error: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                return self._do_request(start_date, end_date, page)
            except Exception as e:
                last_error = e
                if attempt < self._max_retries:
                    time.sleep(self._retry_delay * attempt)

        raise AdjustAPIError(
            f"Adjust API request failed after {self._max_retries} retries: {last_error}"
        )

    def _do_request(
        self,
        start_date: str,
        end_date: str,
        page: int,
    ) -> list[dict[str, Any]]:
        """实际请求（Mock 实现）。

        Mock 返回 3 条测试数据，模拟真实 Adjust API 响应格式。
        """
        # Mock: 只返回第一页数据
        if page > 1:
            return []

        return [
            {
                # ── Identity ──────────────────────────────
                "creative_id": "adj_001",
                "creative_name": "dragon_video_000123",
                "creative_asset_id": "MW_VID_260721_000123",

                # ── Attribution ───────────────────────────
                "campaign_name": "MW_AEO_Install",
                "adgroup_name": "MW_Video_AdSet",

                # ── Users ─────────────────────────────────
                "installs": 2000,
                "sessions": 5000,
                "cohort_paying_users_d30": 120,

                # ── Retention ─────────────────────────────
                "cohort_retention_rate_d1": 0.45,
                "cohort_retention_rate_d7": 0.22,
                "cohort_retention_rate_d30": 0.10,

                # ── IAP Revenue ───────────────────────────
                "cohort_revenue_iap_d1": 800.0,
                "cohort_revenue_iap_d7": 3000.0,
                "cohort_revenue_iap_d30": 10000.0,

                # ── Ads Revenue ───────────────────────────
                "cohort_revenue_ad_d1": 200.0,
                "cohort_revenue_ad_d7": 500.0,
                "cohort_revenue_ad_d30": 2000.0,

                "date": "2026-07-21",
            },
            {
                "creative_id": "adj_002",
                "creative_name": "witch_image_000001",
                "creative_asset_id": "MW_IMG_260701_000001",
                "campaign_name": "MW_AEO_Install",
                "adgroup_name": "MW_Image_AdSet",
                "installs": 500,
                "sessions": 1200,
                "cohort_paying_users_d30": 30,
                "cohort_retention_rate_d1": 0.40,
                "cohort_retention_rate_d7": 0.20,
                "cohort_retention_rate_d30": 0.08,
                "cohort_revenue_iap_d1": 200.0,
                "cohort_revenue_iap_d7": 800.0,
                "cohort_revenue_iap_d30": 3000.0,
                "cohort_revenue_ad_d1": 50.0,
                "cohort_revenue_ad_d7": 150.0,
                "cohort_revenue_ad_d30": 500.0,
                "date": "2026-07-21",
            },
            {
                "creative_id": "adj_003",
                "creative_name": "special_video",
                "creative_asset_id": "MW_VID_000003",
                "campaign_name": "MW_AEO_ROAS",
                "adgroup_name": "MW_Video_ROAS",
                "installs": 300,
                "sessions": 800,
                "cohort_paying_users_d30": 15,
                "cohort_retention_rate_d1": 0.35,
                "cohort_retention_rate_d7": 0.18,
                "cohort_retention_rate_d30": 0.07,
                "cohort_revenue_iap_d1": 100.0,
                "cohort_revenue_iap_d7": 400.0,
                "cohort_revenue_iap_d30": 1500.0,
                "cohort_revenue_ad_d1": 30.0,
                "cohort_revenue_ad_d7": 100.0,
                "cohort_revenue_ad_d30": 300.0,
                "date": "2026-07-21",
            },
        ]

    def __repr__(self) -> str:
        return f"AdjustClient(api_token={'***' if self.api_token else 'None'}, app_token={'***' if self.app_token else 'None'})"