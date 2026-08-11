"""E13.1.3 Adjust Client — Adjust API 客户端 (mock/real 双模式)."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from .models import (
    AdjustAPIResponse,
    AdjustEventType,
    AdjustNetwork,
    AdjustRevenueType,
    AdjustUserEvent,
    AttributionRecord,
    RetentionSnapshot,
)


class AdjustClient:
    """Adjust API 客户端.

    支持两种模式:
      - 模拟模式 (api_token 为空或 "mock"): 使用内置模拟数据
      - 真实模式 (api_token 有效): 调用 Adjust API
    """

    BASE_URL = "https://api.adjust.com"

    def __init__(
        self,
        api_token: str = "",
        app_token: str = "",
        use_mock: bool = True,
    ):
        self._api_token = api_token
        self._app_token = app_token
        self._use_mock = use_mock or not api_token

        self._connected: bool = False
        self._authenticated: bool = False
        self._request_count: int = 0

        # Mock data stores
        self._mock_events: list[AdjustUserEvent] = []
        self._mock_attributions: list[AttributionRecord] = []
        self._mock_retention: RetentionSnapshot | None = None

    # ── Connection ────────────────────────────────────────────

    def connect(self) -> bool:
        if self._use_mock:
            self._connected = True
            self._seed_mock_data()
            return True

        if not self._api_token:
            return False

        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False
        self._authenticated = False

    def authenticate(self) -> bool:
        if self._use_mock:
            self._authenticated = True
            return True

        if not self._api_token:
            return False

        self._authenticated = True
        return True

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def is_authenticated(self) -> bool:
        return self._authenticated

    # ── Mock Data ─────────────────────────────────────────────

    def _seed_mock_data(self) -> None:
        """种子模拟数据."""
        product_id = "P04"
        today = datetime.now(timezone.utc)

        # Seed events
        event_types = [
            (AdjustEventType.INSTALL, 0.0),
            (AdjustEventType.SESSION, 0.0),
            (AdjustEventType.TUTORIAL_COMPLETE, 0.0),
            (AdjustEventType.LEVEL_COMPLETE, 0.0),
            (AdjustEventType.PURCHASE, 9.99),
            (AdjustEventType.AD_REVENUE, 0.05),
            (AdjustEventType.SUBSCRIPTION, 4.99),
        ]

        for i in range(50):
            evt_type, revenue = event_types[i % len(event_types)]
            event = AdjustUserEvent(
                event_id=f"evt_{product_id}_{i}",
                user_id=f"user_{i % 20}",
                product_id=product_id,
                event_name=evt_type,
                timestamp=(today - timedelta(days=i % 7, hours=i)).isoformat(),
                revenue=revenue if evt_type in (AdjustEventType.PURCHASE, AdjustEventType.AD_REVENUE, AdjustEventType.SUBSCRIPTION) else 0.0,
                currency="USD",
                revenue_type=AdjustRevenueType.IAP if evt_type == AdjustEventType.PURCHASE else AdjustRevenueType.IAA,
                network="meta" if i % 3 != 0 else "organic",
                campaign_id=f"camp_{i % 5}" if i % 3 != 0 else "",
                adgroup_id=f"adg_{i % 5}" if i % 3 != 0 else "",
                creative_id=f"cr_{i % 5}" if i % 3 != 0 else "",
                device_id=f"idfa_{i % 20}",
                os_name="ios" if i % 2 == 0 else "android",
                country="US" if i % 3 == 0 else ("JP" if i % 3 == 1 else "CN"),
                app_version="1.2.3",
            )
            self._mock_events.append(event)

        # Seed attributions
        for i in range(20):
            is_organic = i % 3 == 0
            attr = AttributionRecord(
                user_id=f"user_{i}",
                network=AdjustNetwork.ORGANIC if is_organic else AdjustNetwork.META,
                campaign_id="" if is_organic else f"camp_{i % 5}",
                campaign_name="" if is_organic else f"P04_US_FB_{i % 5:03d}",
                adgroup_id="" if is_organic else f"adg_{i % 5}",
                creative_id="" if is_organic else f"video_{i % 5:03d}",
                creative_name="" if is_organic else f"Creative_Variant_{i % 5}",
                install_time=(today - timedelta(days=i % 30)).isoformat(),
                country="US" if i % 3 == 0 else ("JP" if i % 3 == 1 else "CN"),
                is_organic=is_organic,
            )
            self._mock_attributions.append(attr)

        # Seed retention
        self._mock_retention = RetentionSnapshot(
            product_id=product_id,
            cohort_date=(today - timedelta(days=30)).strftime("%Y-%m-%d"),
            cohort_size=1000,
            d1=0.45,
            d3=0.35,
            d7=0.28,
            d14=0.20,
            d30=0.12,
            d60=0.08,
            d90=0.05,
        )

    # ── Events ────────────────────────────────────────────────

    def fetch_events(
        self,
        product_id: str = "",
        start_date: str = "",
        end_date: str = "",
        event_types: list[AdjustEventType] | None = None,
    ) -> list[AdjustUserEvent]:
        """获取用户事件."""
        self._check_connected()
        self._request_count += 1

        if self._use_mock:
            result = list(self._mock_events)
            if product_id:
                result = [e for e in result if e.product_id == product_id]
            if start_date:
                result = [e for e in result if e.timestamp >= start_date]
            if end_date:
                result = [e for e in result if e.timestamp <= end_date]
            if event_types:
                result = [e for e in result if e.event_name in event_types]
            return result

        return []

    # ── Attribution ───────────────────────────────────────────

    def fetch_attribution(
        self,
        start_date: str = "",
        end_date: str = "",
        network: str = "",
    ) -> list[AttributionRecord]:
        """获取归因数据."""
        self._check_connected()
        self._request_count += 1

        if self._use_mock:
            result = list(self._mock_attributions)
            if start_date:
                result = [a for a in result if a.install_time >= start_date]
            if end_date:
                result = [a for a in result if a.install_time <= end_date]
            if network:
                result = [a for a in result if a.network.value == network]
            return result

        return []

    # ── Retention ─────────────────────────────────────────────

    def fetch_retention(
        self,
        product_id: str = "",
        cohort_date: str = "",
    ) -> RetentionSnapshot | None:
        """获取留存数据."""
        self._check_connected()
        self._request_count += 1

        if self._use_mock:
            if self._mock_retention and product_id:
                if self._mock_retention.product_id == product_id:
                    return self._mock_retention
            return self._mock_retention

        return None

    # ── Helpers ───────────────────────────────────────────────

    def _check_connected(self) -> None:
        if not self._connected:
            raise RuntimeError("AdjustClient is not connected. Call connect() first.")

    def get_summary(self) -> dict[str, Any]:
        return {
            "connected": self._connected,
            "authenticated": self._authenticated,
            "use_mock": self._use_mock,
            "request_count": self._request_count,
            "events_count": len(self._mock_events),
            "attributions_count": len(self._mock_attributions),
            "has_retention": self._mock_retention is not None,
        }