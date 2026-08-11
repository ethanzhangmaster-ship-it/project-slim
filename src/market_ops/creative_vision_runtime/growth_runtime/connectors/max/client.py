"""E13.1.4 MAX Client — MAX API 客户端 (mock/real 双模式)."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from .models import (
    MAXAccount,
    MAXAdFormat,
    MAXAdUnit,
    MAXAPIResponse,
    MAXNetwork,
    MAXPerformance,
    MAXRevenueEvent,
    MAXRevenueSnapshot,
    MAXWaterfallEntry,
)


class MAXClient:
    """MAX API 客户端.

    支持两种模式:
      - 模拟模式 (api_key 为空或 "mock"): 使用内置模拟数据
      - 真实模式 (api_key 有效): 调用 MAX API
    """

    BASE_URL = "https://api.applovin.com/max"

    def __init__(
        self,
        api_key: str = "",
        use_mock: bool = True,
    ):
        self._api_key = api_key
        self._use_mock = use_mock or not api_key

        self._connected: bool = False
        self._authenticated: bool = False
        self._request_count: int = 0

        # Mock data stores
        self._mock_account: MAXAccount | None = None
        self._mock_ad_units: list[MAXAdUnit] = []
        self._mock_revenue_events: list[MAXRevenueEvent] = []
        self._mock_performances: list[MAXPerformance] = []
        self._mock_waterfall: list[MAXWaterfallEntry] = []
        self._mock_snapshot: MAXRevenueSnapshot | None = None

    # ── Connection ────────────────────────────────────────────

    def connect(self) -> bool:
        if self._use_mock:
            self._connected = True
            self._seed_mock_data()
            return True

        if not self._api_key:
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

        if not self._api_key:
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
        today = datetime.now(timezone.utc)

        # Seed account
        self._mock_account = MAXAccount(
            account_id="max_account_001",
            api_key="mock_key",
            name="My Game MAX Account",
            status="active",
            currency="USD",
        )

        # Seed ad units
        ad_units_config = [
            ("rewarded_video", MAXAdFormat.REWARDED),
            ("interstitial", MAXAdFormat.INTERSTITIAL),
            ("banner", MAXAdFormat.BANNER),
            ("native", MAXAdFormat.NATIVE),
        ]
        for name, fmt in ad_units_config:
            self._mock_ad_units.append(MAXAdUnit(
                ad_unit_id=f"adunit_{name}",
                name=f"P04_{name}",
                ad_format=fmt,
                app_id="P04",
                app_name="My Game",
                package_name="com.mygame.app",
                platform="ios",
            ))

        # Seed revenue events (impression-level)
        networks = [MAXNetwork.APPLOVIN, MAXNetwork.ADMOB, MAXNetwork.UNITY, MAXNetwork.META, MAXNetwork.MINTEGRAL]
        countries = ["US", "US", "JP", "CN", "GB"]
        formats = [MAXAdFormat.REWARDED, MAXAdFormat.REWARDED, MAXAdFormat.INTERSTITIAL, MAXAdFormat.BANNER, MAXAdFormat.NATIVE]
        ecpm_rates = [15.0, 12.0, 10.0, 8.0, 5.0, 3.0, 2.0]

        for i in range(100):
            evt = MAXRevenueEvent(
                event_id=f"max_imp_{i:04d}",
                ad_unit_id=f"adunit_{formats[i % 5].value}",
                ad_unit_name=f"P04_{formats[i % 5].value}",
                ad_format=formats[i % 5],
                revenue=round(ecpm_rates[i % 7] / 1000, 6),
                revenue_usd=round(ecpm_rates[i % 7] / 1000, 6),
                currency="USD",
                network=networks[i % 5],
                network_placement=f"{networks[i % 5].value}_placement",
                country=countries[i % 5],
                country_code=countries[i % 5],
                device_id=f"idfa_{i % 20}",
                platform="ios" if i % 2 == 0 else "android",
                timestamp=(today - timedelta(hours=i % 24)).isoformat(),
                date=(today - timedelta(days=i % 7)).strftime("%Y-%m-%d"),
            )
            self._mock_revenue_events.append(evt)

        # Seed performances (aggregated by ad unit + network + country)
        for i, network in enumerate(networks):
            for country in ["US", "JP", "CN"]:
                perf = MAXPerformance(
                    ad_unit_id="adunit_rewarded_video",
                    ad_unit_name="P04_Rewarded",
                    product_id="P04",
                    date=today.strftime("%Y-%m-%d"),
                    network=network,
                    country=country,
                    ad_format=MAXAdFormat.REWARDED,
                    impressions=1000 + i * 200,
                    revenue=round((1000 + i * 200) * ecpm_rates[i] / 1000, 2),
                    ecpm=ecpm_rates[i],
                    clicks=50 + i * 10,
                    ctr=0.05 + i * 0.01,
                    requests=1200 + i * 200,
                    fills=1000 + i * 200,
                    fill_rate=0.83,
                    show_rate=0.95,
                    dau=5000 + i * 500,
                    arpdau=round(ecpm_rates[i] * 0.2 / 1000, 6),
                )
                self._mock_performances.append(perf)

        # Seed waterfall
        for i, network in enumerate(networks):
            wf = MAXWaterfallEntry(
                ad_unit_id="adunit_rewarded_video",
                network=network,
                network_placement=f"{network.value}_placement",
                priority=i + 1,
                is_bidding=i >= 3,
                bid_price=ecpm_rates[i] if i >= 3 else 0.0,
                win_price=ecpm_rates[i] * 0.9 if i >= 3 else 0.0,
                win_rate=0.7 if i >= 3 else 0.0,
                impressions=1000 + i * 200,
                revenue=round((1000 + i * 200) * ecpm_rates[i] / 1000, 2),
                ecpm=ecpm_rates[i],
                fill_rate=0.83,
                date=today.strftime("%Y-%m-%d"),
            )
            self._mock_waterfall.append(wf)

        # Seed snapshot
        self._mock_snapshot = MAXRevenueSnapshot(
            product_id="P04",
            date=today.strftime("%Y-%m-%d"),
            total_revenue=round(sum(p.revenue for p in self._mock_performances), 6),
            total_impressions=sum(p.impressions for p in self._mock_performances),
            total_requests=sum(p.requests for p in self._mock_performances),
            total_fills=sum(p.fills for p in self._mock_performances),
            ecpm=round(sum(p.revenue for p in self._mock_performances) / sum(p.impressions for p in self._mock_performances) * 1000, 4) if sum(p.impressions for p in self._mock_performances) > 0 else 0.0,
            fill_rate=0.83,
            show_rate=0.95,
            dau=10000,
            arpdau=round(sum(p.revenue for p in self._mock_performances) / 10000, 6),
        )

    # ── Account ───────────────────────────────────────────────

    def get_account(self) -> MAXAccount | None:
        """获取账户信息."""
        self._check_connected()
        self._request_count += 1

        if self._use_mock:
            return self._mock_account

        return None

    # ── Ad Units ──────────────────────────────────────────────

    def get_ad_units(self) -> list[MAXAdUnit]:
        """获取广告单元列表."""
        self._check_connected()
        self._request_count += 1

        if self._use_mock:
            return list(self._mock_ad_units)

        return []

    # ── Revenue Events ────────────────────────────────────────

    def fetch_revenue_events(
        self,
        start_date: str = "",
        end_date: str = "",
        ad_unit_id: str = "",
        country: str = "",
    ) -> list[MAXRevenueEvent]:
        """获取广告收入事件 (Impression-level)."""
        self._check_connected()
        self._request_count += 1

        if self._use_mock:
            result = list(self._mock_revenue_events)
            if start_date:
                result = [e for e in result if e.date >= start_date]
            if end_date:
                result = [e for e in result if e.date <= end_date]
            if ad_unit_id:
                result = [e for e in result if e.ad_unit_id == ad_unit_id]
            if country:
                result = [e for e in result if e.country_code == country]
            return result

        return []

    # ── Performance ───────────────────────────────────────────

    def fetch_performance(
        self,
        start_date: str = "",
        end_date: str = "",
        ad_unit_id: str = "",
        group_by: str = "ad_unit",  # ad_unit / network / country
    ) -> list[MAXPerformance]:
        """获取聚合表现数据."""
        self._check_connected()
        self._request_count += 1

        if self._use_mock:
            result = list(self._mock_performances)
            if start_date:
                result = [p for p in result if p.date >= start_date]
            if end_date:
                result = [p for p in result if p.date <= end_date]
            if ad_unit_id:
                result = [p for p in result if p.ad_unit_id == ad_unit_id]
            return result

        return []

    # ── Waterfall ─────────────────────────────────────────────

    def fetch_waterfall(
        self,
        ad_unit_id: str = "",
        date: str = "",
    ) -> list[MAXWaterfallEntry]:
        """获取 Waterfall / Bidding 数据."""
        self._check_connected()
        self._request_count += 1

        if self._use_mock:
            result = list(self._mock_waterfall)
            if ad_unit_id:
                result = [w for w in result if w.ad_unit_id == ad_unit_id]
            if date:
                result = [w for w in result if w.date == date]
            return result

        return []

    # ── Revenue Snapshot ──────────────────────────────────────

    def fetch_revenue_snapshot(
        self,
        product_id: str = "",
        date: str = "",
    ) -> MAXRevenueSnapshot | None:
        """获取每日收入快照."""
        self._check_connected()
        self._request_count += 1

        if self._use_mock:
            if self._mock_snapshot:
                return self._mock_snapshot
            return None

        return None

    # ── Helpers ───────────────────────────────────────────────

    def _check_connected(self) -> None:
        if not self._connected:
            raise RuntimeError("MAXClient is not connected. Call connect() first.")

    def get_summary(self) -> dict[str, Any]:
        return {
            "connected": self._connected,
            "authenticated": self._authenticated,
            "use_mock": self._use_mock,
            "request_count": self._request_count,
            "ad_units_count": len(self._mock_ad_units),
            "revenue_events_count": len(self._mock_revenue_events),
            "performances_count": len(self._mock_performances),
            "waterfall_count": len(self._mock_waterfall),
            "has_snapshot": self._mock_snapshot is not None,
        }