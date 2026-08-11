"""E13.1.4 MAX Connector — 测试套件.

预计: enums 25, models 55, client 45, mapper 35, validator 40, connector 50, integration 30
Total: ~280 tests
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone

import pytest

# Ensure src is on path
sys.path.insert(0, "src")

from market_ops.creative_vision_runtime.growth_runtime.connectors.max import (
    # Enums
    MAXAdFormat,
    MAXNetwork,
    MAXRevenueType,
    # Models
    MAXAccount,
    MAXAdUnit,
    MAXAPIResponse,
    MAXPerformance,
    MAXRevenueEvent,
    MAXRevenueSnapshot,
    MAXWaterfallEntry,
    # Client
    MAXClient,
    # Mapper
    MAXRevenueMapper,
    # Validator
    MAXAdUnitValidator,
    MAXPerformanceValidator,
    MAXRevenueEventValidator,
    MAXRevenueSnapshotValidator,
    MAXWaterfallValidator,
    ValidationResult,
    # Adapter
    MAXConnector,
    # Exceptions
    MAXAPIError,
    MAXAuthError,
    MAXConfigError,
    MAXConnectionError,
    MAXDataNotFoundError,
    MAXError,
    MAXRateLimitError,
    MAXValidationError,
)
from market_ops.creative_vision_runtime.growth_runtime.connectors.models import (
    ConnectorConfig,
    ConnectorHealth,
    DataSource,
    GrowthDataEvent,
    MetricType,
    UserRevenueCurve,
)


# ═══════════════════════════════════════════════════════════════
# Test Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def mock_client():
    """创建已连接并认证的 mock MAXClient."""
    client = MAXClient(api_key="", use_mock=True)
    client.connect()
    client.authenticate()
    return client


@pytest.fixture
def sample_events() -> list[MAXRevenueEvent]:
    """创建样本收入事件列表."""
    events = []
    for i in range(20):
        events.append(MAXRevenueEvent(
            event_id=f"max_imp_{i:04d}",
            ad_unit_id="adunit_rewarded_video",
            ad_unit_name="P04_Rewarded",
            ad_format=MAXAdFormat.REWARDED,
            revenue=0.015,
            revenue_usd=0.015,
            currency="USD",
            network=MAXNetwork.APPLOVIN if i < 10 else MAXNetwork.ADMOB,
            network_placement="applovin_placement",
            country="US",
            country_code="US",
            device_id=f"idfa_{i}",
            platform="ios",
            timestamp=datetime.now(timezone.utc).isoformat(),
            date="2026-07-24",
        ))
    return events


@pytest.fixture
def sample_performances() -> list[MAXPerformance]:
    """创建样本聚合表现数据."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    performances = []
    networks = [MAXNetwork.APPLOVIN, MAXNetwork.ADMOB, MAXNetwork.UNITY, MAXNetwork.META, MAXNetwork.MINTEGRAL]
    countries = ["US", "JP", "CN"]
    for network in networks:
        for country in countries:
            performances.append(MAXPerformance(
                ad_unit_id="adunit_rewarded_video",
                ad_unit_name="P04_Rewarded",
                product_id="P04",
                date=today,
                network=network,
                country=country,
                ad_format=MAXAdFormat.REWARDED,
                impressions=1000,
                revenue=15.0,
                ecpm=15.0,
                clicks=50,
                ctr=0.05,
                requests=1200,
                fills=1000,
                fill_rate=0.83,
                show_rate=0.95,
                dau=5000,
                arpdau=0.003,
            ))
    return performances


@pytest.fixture
def sample_waterfall() -> list[MAXWaterfallEntry]:
    """创建样本 Waterfall 数据."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entries = []
    networks = [MAXNetwork.APPLOVIN, MAXNetwork.ADMOB, MAXNetwork.UNITY, MAXNetwork.META, MAXNetwork.MINTEGRAL]
    for i, network in enumerate(networks):
        entries.append(MAXWaterfallEntry(
            ad_unit_id="adunit_rewarded_video",
            network=network,
            network_placement=f"{network.value}_placement",
            priority=i + 1,
            is_bidding=i >= 3,
            bid_price=15.0 if i >= 3 else 0.0,
            win_price=13.5 if i >= 3 else 0.0,
            win_rate=0.7 if i >= 3 else 0.0,
            impressions=1000,
            revenue=15.0,
            ecpm=15.0,
            fill_rate=0.83,
            date=today,
        ))
    return entries


@pytest.fixture
def connector_config() -> ConnectorConfig:
    """创建 MAX Connector 配置."""
    return ConnectorConfig(
        connector_type=DataSource.MAX,
        api_key="mock",
        account_id="test_account",
    )


@pytest.fixture
def max_connector(connector_config) -> MAXConnector:
    """创建已连接的 MAXConnector."""
    conn = MAXConnector(connector_config)
    conn.connect()
    conn.authenticate()
    return conn


# ═══════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════


class TestMAXAdFormat:
    def test_interstitial_value(self):
        assert MAXAdFormat.INTERSTITIAL.value == "interstitial"

    def test_rewarded_value(self):
        assert MAXAdFormat.REWARDED.value == "rewarded"

    def test_banner_value(self):
        assert MAXAdFormat.BANNER.value == "banner"

    def test_mrec_value(self):
        assert MAXAdFormat.MREC.value == "mrec"

    def test_native_value(self):
        assert MAXAdFormat.NATIVE.value == "native"

    def test_app_open_value(self):
        assert MAXAdFormat.APP_OPEN.value == "app_open"

    def test_string_enum_behavior(self):
        assert str(MAXAdFormat.REWARDED) == "MAXAdFormat.REWARDED"


class TestMAXNetwork:
    def test_meta_value(self):
        assert MAXNetwork.META.value == "meta"

    def test_admob_value(self):
        assert MAXNetwork.ADMOB.value == "admob"

    def test_unity_value(self):
        assert MAXNetwork.UNITY.value == "unity"

    def test_applovin_value(self):
        assert MAXNetwork.APPLOVIN.value == "applovin"

    def test_ironsource_value(self):
        assert MAXNetwork.IRONSOURCE.value == "ironsource"

    def test_mintegral_value(self):
        assert MAXNetwork.MINTEGRAL.value == "mintegral"

    def test_vungle_value(self):
        assert MAXNetwork.VUNGLE.value == "vungle"

    def test_chartboost_value(self):
        assert MAXNetwork.CHARTBOOST.value == "chartboost"

    def test_fyber_value(self):
        assert MAXNetwork.FYBER.value == "fyber"

    def test_inmobi_value(self):
        assert MAXNetwork.INMOBI.value == "inmobi"

    def test_adcolony_value(self):
        assert MAXNetwork.ADCOLONY.value == "adcolony"

    def test_pangle_value(self):
        assert MAXNetwork.PANGLE.value == "pangle"

    def test_custom_value(self):
        assert MAXNetwork.CUSTOM.value == "custom"

    def test_unknown_value(self):
        assert MAXNetwork.UNKNOWN.value == "unknown"


class TestMAXRevenueType:
    def test_impression_value(self):
        assert MAXRevenueType.IMPRESSION.value == "impression"

    def test_ecpm_value(self):
        assert MAXRevenueType.ECPM.value == "ecpm"

    def test_arpdau_value(self):
        assert MAXRevenueType.ARPDAU.value == "arpdau"

    def test_fill_rate_value(self):
        assert MAXRevenueType.FILL_RATE.value == "fill_rate"

    def test_show_rate_value(self):
        assert MAXRevenueType.SHOW_RATE.value == "show_rate"


# ═══════════════════════════════════════════════════════════════
# Models: MAXAccount
# ═══════════════════════════════════════════════════════════════


class TestMAXAccount:
    def test_default_values(self):
        account = MAXAccount()
        assert account.account_id == ""
        assert account.api_key == ""
        assert account.name == ""
        assert account.status == "active"
        assert account.currency == "USD"

    def test_custom_account(self):
        account = MAXAccount(
            account_id="max_acc_001",
            api_key="key_abc",
            name="My Game",
            status="active",
            currency="USD",
            timezone="America/New_York",
        )
        assert account.account_id == "max_acc_001"
        assert account.name == "My Game"
        assert account.currency == "USD"
        assert account.timezone == "America/New_York"

    def test_to_dict(self):
        account = MAXAccount(
            account_id="max_acc_001",
            name="My Game",
            status="active",
            currency="USD",
        )
        d = account.to_dict()
        assert d["account_id"] == "max_acc_001"
        assert d["name"] == "My Game"
        assert d["status"] == "active"
        assert d["currency"] == "USD"

    def test_created_at_updated_at(self):
        account = MAXAccount(
            created_at="2026-01-01",
            updated_at="2026-07-24",
        )
        assert account.created_at == "2026-01-01"
        assert account.updated_at == "2026-07-24"


# ═══════════════════════════════════════════════════════════════
# Models: MAXAdUnit
# ═══════════════════════════════════════════════════════════════


class TestMAXAdUnit:
    def test_default_values(self):
        unit = MAXAdUnit()
        assert unit.ad_unit_id == ""
        assert unit.name == ""
        assert unit.ad_format == MAXAdFormat.INTERSTITIAL
        assert unit.platform == ""

    def test_custom_ad_unit(self):
        unit = MAXAdUnit(
            ad_unit_id="adunit_001",
            name="P04_Rewarded",
            ad_format=MAXAdFormat.REWARDED,
            app_id="P04",
            app_name="My Game",
            package_name="com.mygame.app",
            platform="ios",
            status="active",
        )
        assert unit.ad_unit_id == "adunit_001"
        assert unit.name == "P04_Rewarded"
        assert unit.ad_format == MAXAdFormat.REWARDED
        assert unit.app_id == "P04"
        assert unit.platform == "ios"

    def test_to_dict(self):
        unit = MAXAdUnit(
            ad_unit_id="adunit_001",
            name="P04_Rewarded",
            ad_format=MAXAdFormat.REWARDED,
            app_id="P04",
            platform="ios",
            status="active",
        )
        d = unit.to_dict()
        assert d["ad_unit_id"] == "adunit_001"
        assert d["name"] == "P04_Rewarded"
        assert d["ad_format"] == "rewarded"
        assert d["app_id"] == "P04"
        assert d["platform"] == "ios"
        assert d["status"] == "active"


# ═══════════════════════════════════════════════════════════════
# Models: MAXRevenueEvent
# ═══════════════════════════════════════════════════════════════


class TestMAXRevenueEvent:
    def test_default_values(self):
        event = MAXRevenueEvent()
        assert event.event_id == ""
        assert event.revenue == 0.0
        assert event.currency == "USD"
        assert event.ad_format == MAXAdFormat.REWARDED
        assert event.network == MAXNetwork.UNKNOWN

    def test_custom_event(self):
        event = MAXRevenueEvent(
            event_id="max_imp_001",
            ad_unit_id="adunit_rewarded",
            ad_unit_name="P04_Rewarded",
            ad_format=MAXAdFormat.REWARDED,
            revenue=0.015,
            revenue_usd=0.015,
            currency="USD",
            network=MAXNetwork.APPLOVIN,
            country="US",
            country_code="US",
            device_id="idfa_abc",
            platform="ios",
            timestamp="2026-07-24T00:00:00",
            date="2026-07-24",
        )
        assert event.event_id == "max_imp_001"
        assert event.revenue == 0.015
        assert event.network == MAXNetwork.APPLOVIN
        assert event.country == "US"

    def test_is_rewarded_true(self):
        event = MAXRevenueEvent(ad_format=MAXAdFormat.REWARDED)
        assert event.is_rewarded is True

    def test_is_rewarded_false(self):
        event = MAXRevenueEvent(ad_format=MAXAdFormat.INTERSTITIAL)
        assert event.is_rewarded is False

    def test_is_interstitial_true(self):
        event = MAXRevenueEvent(ad_format=MAXAdFormat.INTERSTITIAL)
        assert event.is_interstitial is True

    def test_is_interstitial_false(self):
        event = MAXRevenueEvent(ad_format=MAXAdFormat.REWARDED)
        assert event.is_interstitial is False

    def test_to_dict(self):
        event = MAXRevenueEvent(
            event_id="max_imp_001",
            ad_unit_id="adunit_rewarded",
            ad_format=MAXAdFormat.REWARDED,
            revenue=0.015,
            revenue_usd=0.015,
            currency="USD",
            network=MAXNetwork.APPLOVIN,
            country="US",
            platform="ios",
            date="2026-07-24",
            timestamp="2026-07-24T00:00:00",
        )
        d = event.to_dict()
        assert d["event_id"] == "max_imp_001"
        assert d["ad_format"] == "rewarded"
        assert d["revenue"] == 0.015
        assert d["network"] == "applovin"
        assert d["country"] == "US"

    def test_to_dict_rounds_revenue(self):
        event = MAXRevenueEvent(revenue=0.0156789)
        d = event.to_dict()
        assert d["revenue"] == 0.015679  # round(0.0156789, 6) = 0.015679

    def test_fetched_at_auto_generated(self):
        event = MAXRevenueEvent()
        assert event.fetched_at != ""

    def test_raw_event_stored(self):
        event = MAXRevenueEvent(raw_event={"ad_type": "video"})
        assert event.raw_event["ad_type"] == "video"

    def test_network_placement(self):
        event = MAXRevenueEvent(
            network=MAXNetwork.APPLOVIN,
            network_placement="applovin_interstitial",
        )
        assert event.network_placement == "applovin_interstitial"


# ═══════════════════════════════════════════════════════════════
# Models: MAXPerformance
# ═══════════════════════════════════════════════════════════════


class TestMAXPerformance:
    def test_default_values(self):
        perf = MAXPerformance()
        assert perf.ad_unit_id == ""
        assert perf.impressions == 0
        assert perf.revenue == 0.0
        assert perf.ecpm == 0.0
        assert perf.dau == 0

    def test_custom_performance(self):
        perf = MAXPerformance(
            ad_unit_id="adunit_rewarded",
            ad_unit_name="P04_Rewarded",
            product_id="P04",
            date="2026-07-24",
            network=MAXNetwork.APPLOVIN,
            country="US",
            ad_format=MAXAdFormat.REWARDED,
            impressions=1000,
            revenue=15.0,
            ecpm=15.0,
            clicks=50,
            ctr=0.05,
            requests=1200,
            fills=1000,
            fill_rate=0.83,
            show_rate=0.95,
            dau=5000,
            arpdau=0.003,
        )
        assert perf.ad_unit_id == "adunit_rewarded"
        assert perf.impressions == 1000
        assert perf.revenue == 15.0
        assert perf.ecpm == 15.0
        assert perf.dau == 5000

    def test_revenue_per_impression(self):
        perf = MAXPerformance(impressions=1000, revenue=15.0)
        assert perf.revenue_per_impression == 0.015

    def test_revenue_per_impression_zero(self):
        perf = MAXPerformance(impressions=0, revenue=15.0)
        assert perf.revenue_per_impression == 0.0

    def test_is_high_ecpm_true(self):
        perf = MAXPerformance(ecpm=15.0)
        assert perf.is_high_ecpm(threshold=10.0) is True

    def test_is_high_ecpm_false(self):
        perf = MAXPerformance(ecpm=5.0)
        assert perf.is_high_ecpm(threshold=10.0) is False

    def test_is_high_ecpm_boundary(self):
        perf = MAXPerformance(ecpm=10.0)
        assert perf.is_high_ecpm(threshold=10.0) is True

    def test_to_dict(self):
        perf = MAXPerformance(
            ad_unit_id="adunit_rewarded",
            ad_unit_name="P04_Rewarded",
            product_id="P04",
            date="2026-07-24",
            network=MAXNetwork.APPLOVIN,
            country="US",
            ad_format=MAXAdFormat.REWARDED,
            impressions=1000,
            revenue=15.0,
            ecpm=15.0,
            clicks=50,
            ctr=0.05,
            fill_rate=0.83,
            show_rate=0.95,
            dau=5000,
            arpdau=0.003,
        )
        d = perf.to_dict()
        assert d["ad_unit_id"] == "adunit_rewarded"
        assert d["product_id"] == "P04"
        assert d["impressions"] == 1000
        assert d["revenue"] == 15.0
        assert d["dau"] == 5000

    def test_fetched_at_auto_generated(self):
        perf = MAXPerformance()
        assert perf.fetched_at != ""

    def test_requests_fills(self):
        perf = MAXPerformance(requests=1200, fills=1000)
        assert perf.requests == 1200
        assert perf.fills == 1000


# ═══════════════════════════════════════════════════════════════
# Models: MAXRevenueSnapshot
# ═══════════════════════════════════════════════════════════════


class TestMAXRevenueSnapshot:
    def test_default_values(self):
        snap = MAXRevenueSnapshot()
        assert snap.product_id == ""
        assert snap.date == ""
        assert snap.total_revenue == 0.0
        assert snap.total_impressions == 0
        assert snap.ecpm == 0.0
        assert snap.dau == 0

    def test_custom_snapshot(self):
        snap = MAXRevenueSnapshot(
            product_id="P04",
            date="2026-07-24",
            total_revenue=150.0,
            total_impressions=10000,
            total_requests=12000,
            total_fills=10000,
            ecpm=15.0,
            fill_rate=0.83,
            show_rate=0.95,
            dau=5000,
            arpdau=0.03,
        )
        assert snap.product_id == "P04"
        assert snap.total_revenue == 150.0
        assert snap.ecpm == 15.0
        assert snap.dau == 5000
        assert snap.arpdau == 0.03

    def test_revenue_per_impression(self):
        snap = MAXRevenueSnapshot(total_impressions=10000, total_revenue=150.0)
        assert snap.revenue_per_impression == 0.015

    def test_revenue_per_impression_zero(self):
        snap = MAXRevenueSnapshot(total_impressions=0, total_revenue=150.0)
        assert snap.revenue_per_impression == 0.0

    def test_impressions_per_user(self):
        snap = MAXRevenueSnapshot(total_impressions=10000, dau=5000)
        assert snap.impressions_per_user == 2.0

    def test_impressions_per_user_zero(self):
        snap = MAXRevenueSnapshot(total_impressions=10000, dau=0)
        assert snap.impressions_per_user == 0.0

    def test_is_iaa_healthy_true(self):
        snap = MAXRevenueSnapshot(arpdau=0.05, fill_rate=0.83)
        assert snap.is_iaa_healthy is True

    def test_is_iaa_healthy_false_low_arpdau(self):
        snap = MAXRevenueSnapshot(arpdau=0.005, fill_rate=0.83)
        assert snap.is_iaa_healthy is False

    def test_is_iaa_healthy_false_low_fill(self):
        snap = MAXRevenueSnapshot(arpdau=0.05, fill_rate=0.4)
        assert snap.is_iaa_healthy is False

    def test_is_iaa_healthy_boundary(self):
        snap = MAXRevenueSnapshot(arpdau=0.01, fill_rate=0.5)
        assert snap.is_iaa_healthy is True

    def test_to_dict(self):
        snap = MAXRevenueSnapshot(
            product_id="P04",
            date="2026-07-24",
            total_revenue=150.0,
            total_impressions=10000,
            total_requests=12000,
            total_fills=10000,
            ecpm=15.0,
            fill_rate=0.83,
            show_rate=0.95,
            dau=5000,
            arpdau=0.03,
        )
        d = snap.to_dict()
        assert d["product_id"] == "P04"
        assert d["total_revenue"] == 150.0
        assert d["ecpm"] == 15.0
        assert d["dau"] == 5000

    def test_by_format_dict(self):
        snap = MAXRevenueSnapshot(
            by_format={"rewarded": {"revenue": 100.0, "impressions": 5000}},
        )
        assert snap.by_format["rewarded"]["revenue"] == 100.0

    def test_by_network_dict(self):
        snap = MAXRevenueSnapshot(
            by_network={"applovin": {"revenue": 80.0, "impressions": 4000}},
        )
        assert snap.by_network["applovin"]["revenue"] == 80.0

    def test_by_country_dict(self):
        snap = MAXRevenueSnapshot(
            by_country={"US": {"revenue": 60.0, "impressions": 3000}},
        )
        assert snap.by_country["US"]["revenue"] == 60.0

    def test_by_ad_unit_dict(self):
        snap = MAXRevenueSnapshot(
            by_ad_unit={"adunit_rewarded": {"revenue": 50.0, "impressions": 2500}},
        )
        assert snap.by_ad_unit["adunit_rewarded"]["revenue"] == 50.0

    def test_fetched_at_auto_generated(self):
        snap = MAXRevenueSnapshot()
        assert snap.fetched_at != ""


# ═══════════════════════════════════════════════════════════════
# Models: MAXAPIResponse
# ═══════════════════════════════════════════════════════════════


class TestMAXAPIResponse:
    def test_default_values(self):
        resp = MAXAPIResponse()
        assert resp.success is True
        assert resp.data == []
        assert resp.error_message == ""
        assert resp.error_code == ""

    def test_error_response(self):
        resp = MAXAPIResponse(
            success=False,
            error_message="API Error",
            error_code="401",
        )
        assert resp.is_error is True
        assert resp.error_message == "API Error"
        assert resp.error_code == "401"

    def test_success_response(self):
        resp = MAXAPIResponse(success=True)
        assert resp.is_error is False

    def test_to_dict(self):
        resp = MAXAPIResponse(
            success=True,
            data=[{"id": 1}],
            total_count=100,
            has_more=True,
            next_page_token="token_abc",
        )
        d = resp.to_dict()
        assert d["success"] is True
        assert d["data_count"] == 1
        assert d["total_count"] == 100
        assert d["has_more"] is True

    def test_raw_response(self):
        resp = MAXAPIResponse(raw_response={"meta": {"count": 100}})
        assert resp.raw_response["meta"]["count"] == 100


# ═══════════════════════════════════════════════════════════════
# Models: MAXWaterfallEntry
# ═══════════════════════════════════════════════════════════════


class TestMAXWaterfallEntry:
    def test_default_values(self):
        entry = MAXWaterfallEntry()
        assert entry.ad_unit_id == ""
        assert entry.network == MAXNetwork.UNKNOWN
        assert entry.priority == 0
        assert entry.is_bidding is False
        assert entry.impressions == 0

    def test_bidding_entry(self):
        entry = MAXWaterfallEntry(
            ad_unit_id="adunit_rewarded",
            network=MAXNetwork.APPLOVIN,
            network_placement="applovin_placement",
            priority=1,
            is_bidding=True,
            bid_price=15.0,
            win_price=13.5,
            win_rate=0.7,
            impressions=1000,
            revenue=15.0,
            ecpm=15.0,
            fill_rate=0.83,
            date="2026-07-24",
        )
        assert entry.is_bidding is True
        assert entry.bid_price == 15.0
        assert entry.win_price == 13.5
        assert entry.win_rate == 0.7

    def test_mediated_entry(self):
        entry = MAXWaterfallEntry(
            ad_unit_id="adunit_rewarded",
            network=MAXNetwork.ADMOB,
            network_placement="admob_placement",
            priority=2,
            is_bidding=False,
            impressions=800,
            revenue=12.0,
            ecpm=15.0,
            fill_rate=0.83,
        )
        assert entry.is_bidding is False
        assert entry.bid_price == 0.0
        assert entry.win_rate == 0.0

    def test_to_dict(self):
        entry = MAXWaterfallEntry(
            ad_unit_id="adunit_rewarded",
            network=MAXNetwork.APPLOVIN,
            priority=1,
            is_bidding=True,
            bid_price=15.0,
            win_price=13.5,
            win_rate=0.7,
            impressions=1000,
            revenue=15.0,
            ecpm=15.0,
            fill_rate=0.83,
            date="2026-07-24",
        )
        d = entry.to_dict()
        assert d["ad_unit_id"] == "adunit_rewarded"
        assert d["network"] == "applovin"
        assert d["is_bidding"] is True
        assert d["bid_price"] == 15.0
        assert d["revenue"] == 15.0

    def test_fetched_at_auto_generated(self):
        entry = MAXWaterfallEntry()
        assert entry.fetched_at != ""


# ═══════════════════════════════════════════════════════════════
# MAXClient
# ═══════════════════════════════════════════════════════════════


class TestMAXClientInit:
    def test_default_init(self):
        client = MAXClient()
        assert client.is_connected is False
        assert client.is_authenticated is False

    def test_init_with_api_key(self):
        client = MAXClient(api_key="real_key", use_mock=False)
        assert client.is_connected is False

    def test_init_mock_mode(self):
        client = MAXClient(use_mock=True)
        assert client.is_connected is False

    def test_init_auto_mock_when_no_key(self):
        client = MAXClient(api_key="")
        assert client.is_connected is False


class TestMAXClientConnect:
    def test_connect_mock(self):
        client = MAXClient(use_mock=True)
        assert client.connect() is True
        assert client.is_connected is True

    def test_connect_no_key_auto_mock(self):
        client = MAXClient(api_key="", use_mock=False)
        assert client.connect() is True

    def test_connect_real_mode(self):
        client = MAXClient(api_key="real", use_mock=False)
        assert client.connect() is True
        assert client.is_connected is True

    def test_authenticate_mock(self):
        client = MAXClient(use_mock=True)
        client.connect()
        assert client.authenticate() is True
        assert client.is_authenticated is True

    def test_authenticate_no_key_auto_mock(self):
        client = MAXClient(api_key="", use_mock=False)
        client.connect()
        assert client.authenticate() is True

    def test_disconnect(self):
        client = MAXClient(use_mock=True)
        client.connect()
        client.disconnect()
        assert client.is_connected is False
        assert client.is_authenticated is False


class TestMAXClientAccount:
    def test_get_account_mock(self, mock_client):
        account = mock_client.get_account()
        assert account is not None
        assert account.account_id == "max_account_001"
        assert account.name == "My Game MAX Account"
        assert account.currency == "USD"

    def test_get_account_not_connected(self):
        client = MAXClient(use_mock=True)
        with pytest.raises(RuntimeError, match="not connected"):
            client.get_account()


class TestMAXClientAdUnits:
    def test_get_ad_units_mock(self, mock_client):
        units = mock_client.get_ad_units()
        assert len(units) == 4
        formats = {u.ad_format for u in units}
        assert MAXAdFormat.REWARDED in formats
        assert MAXAdFormat.INTERSTITIAL in formats
        assert MAXAdFormat.BANNER in formats
        assert MAXAdFormat.NATIVE in formats

    def test_get_ad_units_not_connected(self):
        client = MAXClient(use_mock=True)
        with pytest.raises(RuntimeError, match="not connected"):
            client.get_ad_units()


class TestMAXClientRevenueEvents:
    def test_fetch_revenue_events_mock(self, mock_client):
        events = mock_client.fetch_revenue_events()
        assert len(events) == 100

    def test_fetch_revenue_events_by_date(self, mock_client):
        events = mock_client.fetch_revenue_events(
            start_date="2020-01-01",
            end_date="2099-12-31",
        )
        assert len(events) == 100

    def test_fetch_revenue_events_by_ad_unit(self, mock_client):
        events = mock_client.fetch_revenue_events(ad_unit_id="adunit_rewarded")
        assert len(events) > 0
        for e in events:
            assert e.ad_unit_id == "adunit_rewarded"

    def test_fetch_revenue_events_by_country(self, mock_client):
        events = mock_client.fetch_revenue_events(country="US")
        assert len(events) > 0
        for e in events:
            assert e.country_code == "US"

    def test_fetch_revenue_events_not_connected(self):
        client = MAXClient(use_mock=True)
        with pytest.raises(RuntimeError, match="not connected"):
            client.fetch_revenue_events()


class TestMAXClientPerformance:
    def test_fetch_performance_mock(self, mock_client):
        perfs = mock_client.fetch_performance()
        assert len(perfs) == 15  # 5 networks * 3 countries

    def test_fetch_performance_by_date(self, mock_client):
        perfs = mock_client.fetch_performance(
            start_date="2020-01-01",
            end_date="2099-12-31",
        )
        assert len(perfs) == 15

    def test_fetch_performance_by_ad_unit(self, mock_client):
        perfs = mock_client.fetch_performance(ad_unit_id="adunit_rewarded_video")
        assert len(perfs) == 15

    def test_fetch_performance_wrong_ad_unit(self, mock_client):
        perfs = mock_client.fetch_performance(ad_unit_id="nonexistent")
        assert len(perfs) == 0

    def test_fetch_performance_not_connected(self):
        client = MAXClient(use_mock=True)
        with pytest.raises(RuntimeError, match="not connected"):
            client.fetch_performance()


class TestMAXClientWaterfall:
    def test_fetch_waterfall_mock(self, mock_client):
        entries = mock_client.fetch_waterfall()
        assert len(entries) == 5

    def test_fetch_waterfall_by_ad_unit(self, mock_client):
        entries = mock_client.fetch_waterfall(ad_unit_id="adunit_rewarded_video")
        assert len(entries) == 5

    def test_fetch_waterfall_by_date(self, mock_client):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        entries = mock_client.fetch_waterfall(date=today)
        assert len(entries) == 5

    def test_fetch_waterfall_not_connected(self):
        client = MAXClient(use_mock=True)
        with pytest.raises(RuntimeError, match="not connected"):
            client.fetch_waterfall()


class TestMAXClientSnapshot:
    def test_fetch_revenue_snapshot_mock(self, mock_client):
        snap = mock_client.fetch_revenue_snapshot()
        assert snap is not None
        assert snap.product_id == "P04"
        assert snap.total_revenue > 0
        assert snap.total_impressions > 0

    def test_fetch_revenue_snapshot_not_connected(self):
        client = MAXClient(use_mock=True)
        with pytest.raises(RuntimeError, match="not connected"):
            client.fetch_revenue_snapshot()


class TestMAXClientSummary:
    def test_get_summary(self, mock_client):
        summary = mock_client.get_summary()
        assert summary["connected"] is True
        assert summary["authenticated"] is True
        assert summary["use_mock"] is True
        assert summary["ad_units_count"] == 4
        assert summary["revenue_events_count"] == 100
        assert summary["performances_count"] == 15
        assert summary["waterfall_count"] == 5
        assert summary["has_snapshot"] is True

    def test_get_summary_before_connect(self):
        client = MAXClient(use_mock=True)
        summary = client.get_summary()
        assert summary["connected"] is False
        assert summary["authenticated"] is False


class TestMAXClientRequestCount:
    def test_request_count_increments(self, mock_client):
        initial = mock_client.get_summary()["request_count"]
        mock_client.fetch_revenue_events()
        assert mock_client.get_summary()["request_count"] == initial + 1

    def test_request_count_multiple_calls(self, mock_client):
        mock_client.fetch_revenue_events()
        mock_client.fetch_performance()
        mock_client.fetch_waterfall()
        mock_client.get_account()
        assert mock_client.get_summary()["request_count"] == 4


# ═══════════════════════════════════════════════════════════════
# MAXRevenueMapper
# ═══════════════════════════════════════════════════════════════


class TestMAXRevenueMapperBuildSnapshot:
    def test_build_snapshot(self, sample_performances):
        snap = MAXRevenueMapper.build_snapshot(
            performances=sample_performances,
            product_id="P04",
            date="2026-07-24",
        )
        assert snap.product_id == "P04"
        assert snap.date == "2026-07-24"
        assert snap.total_revenue > 0
        assert snap.total_impressions > 0
        assert snap.ecpm > 0
        assert snap.dau > 0
        assert snap.arpdau > 0

    def test_build_snapshot_no_performances(self):
        snap = MAXRevenueMapper.build_snapshot(
            performances=[],
            product_id="P04",
            date="2026-07-24",
        )
        assert snap.product_id == "P04"
        assert snap.total_revenue == 0.0
        assert snap.total_impressions == 0
        assert snap.ecpm == 0.0
        assert snap.dau == 0

    def test_build_snapshot_auto_product_id(self, sample_performances):
        snap = MAXRevenueMapper.build_snapshot(performances=sample_performances)
        assert snap.product_id == "P04"

    def test_build_snapshot_auto_date(self, sample_performances):
        snap = MAXRevenueMapper.build_snapshot(performances=sample_performances)
        assert snap.date != ""

    def test_build_snapshot_by_format(self, sample_performances):
        snap = MAXRevenueMapper.build_snapshot(performances=sample_performances)
        assert "rewarded" in snap.by_format
        assert snap.by_format["rewarded"]["revenue"] > 0

    def test_build_snapshot_by_network(self, sample_performances):
        snap = MAXRevenueMapper.build_snapshot(performances=sample_performances)
        assert "applovin" in snap.by_network
        assert "admob" in snap.by_network

    def test_build_snapshot_by_country(self, sample_performances):
        snap = MAXRevenueMapper.build_snapshot(performances=sample_performances)
        assert "US" in snap.by_country
        assert "JP" in snap.by_country

    def test_build_snapshot_by_ad_unit(self, sample_performances):
        snap = MAXRevenueMapper.build_snapshot(performances=sample_performances)
        assert "adunit_rewarded_video" in snap.by_ad_unit

    def test_build_snapshot_unit_economics(self, sample_performances):
        snap = MAXRevenueMapper.build_snapshot(performances=sample_performances)
        assert snap.ecpm > 0
        assert 0 <= snap.fill_rate <= 1
        assert 0 <= snap.show_rate <= 1


class TestMAXRevenueMapperBuildSnapshotsByDate:
    def test_build_snapshots_by_date(self, sample_performances):
        snapshots = MAXRevenueMapper.build_snapshots_by_date(
            performances=sample_performances,
            product_id="P04",
        )
        assert len(snapshots) >= 1

    def test_build_snapshots_by_date_sorted(self, sample_performances):
        snapshots = MAXRevenueMapper.build_snapshots_by_date(
            performances=sample_performances,
            product_id="P04",
        )
        for i in range(len(snapshots) - 1):
            assert snapshots[i].date <= snapshots[i + 1].date


class TestMAXRevenueMapperBuildSnapshotByNetwork:
    def test_build_snapshot_by_network(self, sample_performances):
        snapshots = MAXRevenueMapper.build_snapshot_by_network(
            performances=sample_performances,
            product_id="P04",
        )
        assert "applovin" in snapshots
        assert "admob" in snapshots
        assert snapshots["applovin"].product_id == "P04"

    def test_build_snapshot_by_network_revenue(self, sample_performances):
        snapshots = MAXRevenueMapper.build_snapshot_by_network(
            performances=sample_performances,
        )
        for network, snap in snapshots.items():
            assert snap.total_revenue > 0


class TestMAXRevenueMapperAggregateEvents:
    def test_aggregate_events_to_performance(self, sample_events):
        perfs = MAXRevenueMapper.aggregate_events_to_performance(
            events=sample_events,
            product_id="P04",
            date="2026-07-24",
        )
        assert len(perfs) > 0
        for perf in perfs:
            assert perf.product_id == "P04"
            assert perf.impressions > 0
            assert perf.revenue > 0

    def test_aggregate_events_empty(self):
        perfs = MAXRevenueMapper.aggregate_events_to_performance(events=[])
        assert perfs == []

    def test_aggregate_events_groups_by_network(self, sample_events):
        perfs = MAXRevenueMapper.aggregate_events_to_performance(
            events=sample_events,
        )
        networks = {p.network for p in perfs}
        assert MAXNetwork.APPLOVIN in networks
        assert MAXNetwork.ADMOB in networks


class TestMAXRevenueMapperWaterfallStats:
    def test_compute_waterfall_stats(self, sample_waterfall):
        stats = MAXRevenueMapper.compute_waterfall_stats(sample_waterfall)
        assert stats["total_networks"] == 5
        assert stats["bidding_networks"] == 2
        assert stats["mediated_networks"] == 3
        assert stats["bidding_revenue"] > 0
        assert stats["mediated_revenue"] > 0
        assert 0 <= stats["bidding_revenue_ratio"] <= 1

    def test_compute_waterfall_stats_empty(self):
        stats = MAXRevenueMapper.compute_waterfall_stats([])
        assert stats["total_networks"] == 0
        assert stats["bidding_revenue_ratio"] == 0.0

    def test_compute_waterfall_stats_top_network(self, sample_waterfall):
        stats = MAXRevenueMapper.compute_waterfall_stats(sample_waterfall)
        assert "top_network" in stats
        assert "network" in stats["top_network"]

    def test_compute_waterfall_stats_avg_ecpm(self, sample_waterfall):
        stats = MAXRevenueMapper.compute_waterfall_stats(sample_waterfall)
        assert stats["avg_ecpm"] > 0


class TestMAXRevenueMapperNetworkStats:
    def test_compute_network_stats(self, sample_performances):
        stats = MAXRevenueMapper.compute_network_stats(sample_performances)
        assert "applovin" in stats
        assert "admob" in stats
        assert stats["applovin"]["revenue"] > 0
        assert stats["applovin"]["impressions"] > 0
        assert stats["applovin"]["ecpm"] > 0

    def test_compute_network_stats_empty(self):
        stats = MAXRevenueMapper.compute_network_stats([])
        assert stats == {}

    def test_compute_network_stats_revenue_share(self, sample_performances):
        stats = MAXRevenueMapper.compute_network_stats(sample_performances)
        total_share = sum(s["revenue_share"] for s in stats.values())
        assert abs(total_share - 1.0) < 0.001


# ═══════════════════════════════════════════════════════════════
# Validator
# ═══════════════════════════════════════════════════════════════


class TestValidationResult:
    def test_default_valid(self):
        result = ValidationResult()
        assert result.is_valid is True
        assert result.errors == []
        assert result.warnings == []

    def test_add_error(self):
        result = ValidationResult()
        result.add_error("test error")
        assert result.is_valid is False
        assert len(result.errors) == 1

    def test_add_warning(self):
        result = ValidationResult()
        result.add_warning("test warning")
        assert result.is_valid is True
        assert len(result.warnings) == 1

    def test_multiple_errors(self):
        result = ValidationResult()
        result.add_error("e1")
        result.add_error("e2")
        result.add_error("e3")
        assert len(result.errors) == 3
        assert result.is_valid is False

    def test_to_dict(self):
        result = ValidationResult()
        result.add_error("test error")
        result.add_warning("test warning")
        d = result.to_dict()
        assert d["is_valid"] is False
        assert d["error_count"] == 1
        assert d["warning_count"] == 1


class TestMAXRevenueEventValidator:
    def test_valid_event(self):
        event = MAXRevenueEvent(
            event_id="max_imp_001",
            ad_unit_id="adunit_rewarded",
            revenue=0.015,
            timestamp="2026-07-24T00:00:00",
            date="2026-07-24",
        )
        result = MAXRevenueEventValidator.validate(event)
        assert result.is_valid is True

    def test_missing_event_id(self):
        event = MAXRevenueEvent(
            event_id="",
            ad_unit_id="adunit_rewarded",
            timestamp="2026-07-24T00:00:00",
        )
        result = MAXRevenueEventValidator.validate(event)
        assert result.is_valid is False

    def test_missing_ad_unit_id(self):
        event = MAXRevenueEvent(
            event_id="max_imp_001",
            ad_unit_id="",
            timestamp="2026-07-24T00:00:00",
        )
        result = MAXRevenueEventValidator.validate(event)
        assert result.is_valid is False

    def test_negative_revenue(self):
        event = MAXRevenueEvent(
            event_id="max_imp_001",
            ad_unit_id="adunit_rewarded",
            timestamp="2026-07-24T00:00:00",
            revenue=-1.0,
        )
        result = MAXRevenueEventValidator.validate(event)
        assert result.is_valid is False

    def test_missing_timestamp(self):
        event = MAXRevenueEvent(
            event_id="max_imp_001",
            ad_unit_id="adunit_rewarded",
        )
        result = MAXRevenueEventValidator.validate(event)
        assert result.is_valid is False

    def test_empty_date_warning(self):
        event = MAXRevenueEvent(
            event_id="max_imp_001",
            ad_unit_id="adunit_rewarded",
            timestamp="2026-07-24T00:00:00",
            date="",
        )
        result = MAXRevenueEventValidator.validate(event)
        assert len(result.warnings) >= 1

    def test_high_revenue_warning(self):
        event = MAXRevenueEvent(
            event_id="max_imp_001",
            ad_unit_id="adunit_rewarded",
            timestamp="2026-07-24T00:00:00",
            revenue=2000.0,
        )
        result = MAXRevenueEventValidator.validate(event)
        assert len(result.warnings) >= 1

    def test_validate_batch(self):
        events = [
            MAXRevenueEvent(event_id="e1", ad_unit_id="au1", timestamp="2026-07-24"),
            MAXRevenueEvent(event_id="", ad_unit_id="au1", timestamp="2026-07-24"),
        ]
        results = MAXRevenueEventValidator.validate_batch(events)
        assert results[0].is_valid is True
        assert results[1].is_valid is False

    def test_filter_valid(self):
        events = [
            MAXRevenueEvent(event_id="e1", ad_unit_id="au1", timestamp="2026-07-24"),
            MAXRevenueEvent(event_id="", ad_unit_id="au1", timestamp="2026-07-24"),
        ]
        valid = MAXRevenueEventValidator.filter_valid(events)
        assert len(valid) == 1


class TestMAXPerformanceValidator:
    def test_valid_performance(self):
        perf = MAXPerformance(
            ad_unit_id="adunit_rewarded",
            date="2026-07-24",
            impressions=1000,
            revenue=15.0,
            ecpm=15.0,
            fill_rate=0.83,
            show_rate=0.95,
            requests=1200,
            fills=1000,
            dau=5000,
            arpdau=0.003,
        )
        result = MAXPerformanceValidator.validate(perf)
        assert result.is_valid is True

    def test_missing_ad_unit_id(self):
        perf = MAXPerformance(
            ad_unit_id="",
            date="2026-07-24",
        )
        result = MAXPerformanceValidator.validate(perf)
        assert result.is_valid is False

    def test_missing_date(self):
        perf = MAXPerformance(ad_unit_id="adunit_rewarded")
        result = MAXPerformanceValidator.validate(perf)
        assert result.is_valid is False

    def test_negative_impressions(self):
        perf = MAXPerformance(
            ad_unit_id="adunit_rewarded",
            date="2026-07-24",
            impressions=-1,
        )
        result = MAXPerformanceValidator.validate(perf)
        assert result.is_valid is False

    def test_negative_revenue(self):
        perf = MAXPerformance(
            ad_unit_id="adunit_rewarded",
            date="2026-07-24",
            revenue=-1.0,
        )
        result = MAXPerformanceValidator.validate(perf)
        assert result.is_valid is False

    def test_negative_ecpm(self):
        perf = MAXPerformance(
            ad_unit_id="adunit_rewarded",
            date="2026-07-24",
            ecpm=-1.0,
        )
        result = MAXPerformanceValidator.validate(perf)
        assert result.is_valid is False

    def test_high_ecpm_warning(self):
        perf = MAXPerformance(
            ad_unit_id="adunit_rewarded",
            date="2026-07-24",
            ecpm=600.0,
        )
        result = MAXPerformanceValidator.validate(perf)
        assert len(result.warnings) >= 1

    def test_fill_rate_out_of_range(self):
        perf = MAXPerformance(
            ad_unit_id="adunit_rewarded",
            date="2026-07-24",
            fill_rate=1.5,
        )
        result = MAXPerformanceValidator.validate(perf)
        assert result.is_valid is False

    def test_show_rate_out_of_range(self):
        perf = MAXPerformance(
            ad_unit_id="adunit_rewarded",
            date="2026-07-24",
            show_rate=-0.1,
        )
        result = MAXPerformanceValidator.validate(perf)
        assert result.is_valid is False

    def test_fills_exceed_requests_warning(self):
        perf = MAXPerformance(
            ad_unit_id="adunit_rewarded",
            date="2026-07-24",
            requests=100,
            fills=200,
        )
        result = MAXPerformanceValidator.validate(perf)
        assert len(result.warnings) >= 1

    def test_impressions_exceed_fills_warning(self):
        perf = MAXPerformance(
            ad_unit_id="adunit_rewarded",
            date="2026-07-24",
            fills=100,
            impressions=200,
        )
        result = MAXPerformanceValidator.validate(perf)
        assert len(result.warnings) >= 1

    def test_negative_dau(self):
        perf = MAXPerformance(
            ad_unit_id="adunit_rewarded",
            date="2026-07-24",
            dau=-1,
        )
        result = MAXPerformanceValidator.validate(perf)
        assert result.is_valid is False

    def test_negative_arpdau(self):
        perf = MAXPerformance(
            ad_unit_id="adunit_rewarded",
            date="2026-07-24",
            arpdau=-1.0,
        )
        result = MAXPerformanceValidator.validate(perf)
        assert result.is_valid is False

    def test_negative_requests(self):
        perf = MAXPerformance(
            ad_unit_id="adunit_rewarded",
            date="2026-07-24",
            requests=-1,
        )
        result = MAXPerformanceValidator.validate(perf)
        assert result.is_valid is False

    def test_validate_batch(self):
        perfs = [
            MAXPerformance(ad_unit_id="au1", date="2026-07-24"),
            MAXPerformance(ad_unit_id="", date="2026-07-24"),
        ]
        results = MAXPerformanceValidator.validate_batch(perfs)
        assert results[0].is_valid is True
        assert results[1].is_valid is False

    def test_filter_valid(self):
        perfs = [
            MAXPerformance(ad_unit_id="au1", date="2026-07-24"),
            MAXPerformance(ad_unit_id="", date="2026-07-24"),
        ]
        valid = MAXPerformanceValidator.filter_valid(perfs)
        assert len(valid) == 1


class TestMAXRevenueSnapshotValidator:
    def test_valid_snapshot(self):
        snap = MAXRevenueSnapshot(
            product_id="P04",
            date="2026-07-24",
            total_revenue=150.0,
            total_impressions=10000,
            ecpm=15.0,
            fill_rate=0.83,
            dau=5000,
            arpdau=0.03,
        )
        result = MAXRevenueSnapshotValidator.validate(snap)
        assert result.is_valid is True

    def test_missing_product_id(self):
        snap = MAXRevenueSnapshot(date="2026-07-24")
        result = MAXRevenueSnapshotValidator.validate(snap)
        assert result.is_valid is False

    def test_missing_date(self):
        snap = MAXRevenueSnapshot(product_id="P04")
        result = MAXRevenueSnapshotValidator.validate(snap)
        assert result.is_valid is False

    def test_negative_revenue(self):
        snap = MAXRevenueSnapshot(
            product_id="P04",
            date="2026-07-24",
            total_revenue=-1.0,
        )
        result = MAXRevenueSnapshotValidator.validate(snap)
        assert result.is_valid is False

    def test_negative_impressions(self):
        snap = MAXRevenueSnapshot(
            product_id="P04",
            date="2026-07-24",
            total_impressions=-1,
        )
        result = MAXRevenueSnapshotValidator.validate(snap)
        assert result.is_valid is False

    def test_negative_ecpm(self):
        snap = MAXRevenueSnapshot(
            product_id="P04",
            date="2026-07-24",
            ecpm=-1.0,
        )
        result = MAXRevenueSnapshotValidator.validate(snap)
        assert result.is_valid is False

    def test_fill_rate_out_of_range(self):
        snap = MAXRevenueSnapshot(
            product_id="P04",
            date="2026-07-24",
            fill_rate=1.5,
        )
        result = MAXRevenueSnapshotValidator.validate(snap)
        assert result.is_valid is False

    def test_negative_dau(self):
        snap = MAXRevenueSnapshot(
            product_id="P04",
            date="2026-07-24",
            dau=-1,
        )
        result = MAXRevenueSnapshotValidator.validate(snap)
        assert result.is_valid is False

    def test_negative_arpdau(self):
        snap = MAXRevenueSnapshot(
            product_id="P04",
            date="2026-07-24",
            arpdau=-1.0,
        )
        result = MAXRevenueSnapshotValidator.validate(snap)
        assert result.is_valid is False

    def test_validate_or_none_none(self):
        result = MAXRevenueSnapshotValidator.validate_or_none(None)
        assert result.is_valid is False
        assert len(result.errors) >= 1

    def test_validate_or_none_valid(self):
        snap = MAXRevenueSnapshot(
            product_id="P04",
            date="2026-07-24",
        )
        result = MAXRevenueSnapshotValidator.validate_or_none(snap)
        assert result.is_valid is True


class TestMAXWaterfallValidator:
    def test_valid_waterfall(self):
        entry = MAXWaterfallEntry(
            ad_unit_id="adunit_rewarded",
            network=MAXNetwork.APPLOVIN,
            impressions=1000,
            revenue=15.0,
            ecpm=15.0,
        )
        result = MAXWaterfallValidator.validate(entry)
        assert result.is_valid is True

    def test_missing_ad_unit_id(self):
        entry = MAXWaterfallEntry(ad_unit_id="")
        result = MAXWaterfallValidator.validate(entry)
        assert result.is_valid is False

    def test_negative_impressions(self):
        entry = MAXWaterfallEntry(
            ad_unit_id="adunit_rewarded",
            impressions=-1,
        )
        result = MAXWaterfallValidator.validate(entry)
        assert result.is_valid is False

    def test_negative_revenue(self):
        entry = MAXWaterfallEntry(
            ad_unit_id="adunit_rewarded",
            revenue=-1.0,
        )
        result = MAXWaterfallValidator.validate(entry)
        assert result.is_valid is False

    def test_negative_ecpm(self):
        entry = MAXWaterfallEntry(
            ad_unit_id="adunit_rewarded",
            ecpm=-1.0,
        )
        result = MAXWaterfallValidator.validate(entry)
        assert result.is_valid is False

    def test_bidding_negative_win_rate(self):
        entry = MAXWaterfallEntry(
            ad_unit_id="adunit_rewarded",
            is_bidding=True,
            win_rate=-0.5,
        )
        result = MAXWaterfallValidator.validate(entry)
        assert result.is_valid is False

    def test_filter_valid(self):
        entries = [
            MAXWaterfallEntry(ad_unit_id="au1", impressions=100),
            MAXWaterfallEntry(ad_unit_id="", impressions=100),
        ]
        valid = MAXWaterfallValidator.filter_valid(entries)
        assert len(valid) == 1


class TestMAXAdUnitValidator:
    def test_valid_ad_unit(self):
        unit = MAXAdUnit(
            ad_unit_id="adunit_rewarded",
            name="P04_Rewarded",
            app_id="P04",
        )
        result = MAXAdUnitValidator.validate(unit)
        assert result.is_valid is True

    def test_missing_ad_unit_id(self):
        unit = MAXAdUnit(name="P04_Rewarded")
        result = MAXAdUnitValidator.validate(unit)
        assert result.is_valid is False

    def test_missing_name(self):
        unit = MAXAdUnit(ad_unit_id="adunit_rewarded")
        result = MAXAdUnitValidator.validate(unit)
        assert result.is_valid is False

    def test_empty_app_id_warning(self):
        unit = MAXAdUnit(
            ad_unit_id="adunit_rewarded",
            name="P04_Rewarded",
        )
        result = MAXAdUnitValidator.validate(unit)
        assert len(result.warnings) >= 1


# ═══════════════════════════════════════════════════════════════
# Exceptions
# ═══════════════════════════════════════════════════════════════


class TestMAXExceptions:
    def test_max_error(self):
        err = MAXError("base error")
        assert str(err) == "base error"
        assert isinstance(err, Exception)

    def test_max_auth_error(self):
        err = MAXAuthError("auth failed")
        assert str(err) == "auth failed"
        assert isinstance(err, MAXError)

    def test_max_api_error(self):
        err = MAXAPIError("api error", error_code=500, error_type="server_error")
        assert str(err) == "api error"
        assert err.error_code == 500
        assert err.error_type == "server_error"

    def test_max_rate_limit_error(self):
        err = MAXRateLimitError("rate limited", retry_after=60)
        assert str(err) == "rate limited"
        assert err.retry_after == 60

    def test_max_validation_error(self):
        err = MAXValidationError("validation failed")
        assert str(err) == "validation failed"
        assert isinstance(err, MAXError)

    def test_max_data_not_found_error(self):
        err = MAXDataNotFoundError("data not found")
        assert str(err) == "data not found"
        assert isinstance(err, MAXError)

    def test_max_connection_error(self):
        err = MAXConnectionError("connection failed")
        assert str(err) == "connection failed"
        assert isinstance(err, MAXError)

    def test_max_config_error(self):
        err = MAXConfigError("config invalid")
        assert str(err) == "config invalid"
        assert isinstance(err, MAXError)

    def test_exception_hierarchy(self):
        assert issubclass(MAXAuthError, MAXError)
        assert issubclass(MAXAPIError, MAXError)
        assert issubclass(MAXRateLimitError, MAXError)
        assert issubclass(MAXValidationError, MAXError)
        assert issubclass(MAXDataNotFoundError, MAXError)
        assert issubclass(MAXConnectionError, MAXError)
        assert issubclass(MAXConfigError, MAXError)


# ═══════════════════════════════════════════════════════════════
# MAXConnector
# ═══════════════════════════════════════════════════════════════


class TestMAXConnectorLifecycle:
    def test_connect(self, connector_config):
        conn = MAXConnector(connector_config)
        assert conn.connect() is True
        assert conn.is_connected is True

    def test_authenticate(self, connector_config):
        conn = MAXConnector(connector_config)
        conn.connect()
        assert conn.authenticate() is True
        assert conn.is_authenticated is True

    def test_disconnect(self, max_connector):
        max_connector.disconnect()
        assert max_connector.is_connected is False

    def test_health_check_healthy(self, max_connector):
        assert max_connector.health_check() == ConnectorHealth.HEALTHY

    def test_health_check_not_connected(self, connector_config):
        conn = MAXConnector(connector_config)
        assert conn.health_check() == ConnectorHealth.UNHEALTHY

    def test_lifecycle_full(self, connector_config):
        conn = MAXConnector(connector_config)
        assert conn.connect() is True
        assert conn.authenticate() is True
        assert conn.is_connected is True
        assert conn.is_authenticated is True
        conn.disconnect()
        assert conn.is_connected is False


class TestMAXConnectorSync:
    def test_sync_all(self, max_connector):
        result = max_connector.sync_all(product_id="P04")
        assert result["revenue_events"] > 0
        assert result["performances"] > 0
        assert result["waterfall"] > 0
        assert result["has_snapshot"] is True
        assert result["last_sync_at"] != ""

    def test_sync_revenue_events(self, max_connector):
        events = max_connector.sync_revenue_events()
        assert len(events) > 0
        assert len(max_connector.revenue_events) > 0

    def test_sync_performance(self, max_connector):
        perfs = max_connector.sync_performance(product_id="P04")
        assert len(perfs) > 0
        assert len(max_connector.performances) > 0

    def test_sync_waterfall(self, max_connector):
        entries = max_connector.sync_waterfall()
        assert len(entries) > 0
        assert len(max_connector.waterfall) > 0

    def test_last_sync_at_updated(self, max_connector):
        max_connector.sync_all(product_id="P04")
        assert max_connector.last_sync_at != ""


class TestMAXConnectorBuildSnapshot:
    def test_build_revenue_snapshot(self, max_connector):
        max_connector.sync_all(product_id="P04")
        snapshot = max_connector.build_revenue_snapshot(product_id="P04")
        assert snapshot is not None
        assert snapshot.product_id == "P04"
        assert snapshot.total_revenue > 0
        assert snapshot.total_impressions > 0

    def test_build_snapshots_by_date(self, max_connector):
        max_connector.sync_all(product_id="P04")
        snapshots = max_connector.build_snapshots_by_date(product_id="P04")
        assert len(snapshots) >= 1

    def test_build_snapshot_by_network(self, max_connector):
        max_connector.sync_all(product_id="P04")
        by_network = max_connector.build_snapshot_by_network(product_id="P04")
        assert "applovin" in by_network
        assert "admob" in by_network

    def test_build_snapshot_no_sync(self, max_connector):
        max_connector._performances = []
        snapshot = max_connector.build_revenue_snapshot(product_id="P04")
        assert snapshot is not None  # auto-syncs


class TestMAXConnectorFetchOverrides:
    def test_fetch_revenue_curve(self, max_connector):
        max_connector.sync_all(product_id="P04")
        curve = max_connector.fetch_revenue_curve(product_id="P04")
        assert curve is not None
        assert curve.platform == DataSource.MAX
        assert curve.cohort_size > 0
        assert curve.predicted_ltv > 0

    def test_fetch_revenue_curve_no_data(self, max_connector):
        """当 client 无数据时，fetch_revenue_curve 返回 None."""
        # Mock the client to return empty data
        max_connector._client._mock_performances = []
        curve = max_connector.fetch_revenue_curve(product_id="P04")
        assert curve is None


class TestMAXConnectorCollectEvents:
    def test_collect_events(self, max_connector):
        max_connector.sync_all(product_id="P04")
        events = max_connector.collect_events(product_id="P04")
        assert len(events) >= 2  # Revenue + ARPU
        sources = {e.source for e in events}
        assert DataSource.MAX in sources

    def test_collect_events_revenue(self, max_connector):
        max_connector.sync_all(product_id="P04")
        events = max_connector.collect_events(product_id="P04")
        revenue_events = [e for e in events if e.event_type == MetricType.REVENUE]
        assert len(revenue_events) >= 1

    def test_collect_events_arpu(self, max_connector):
        max_connector.sync_all(product_id="P04")
        events = max_connector.collect_events(product_id="P04")
        arpu_events = [e for e in events if e.event_type == MetricType.ARPU]
        assert len(arpu_events) >= 1

    def test_collect_events_revenue_metrics(self, max_connector):
        max_connector.sync_all(product_id="P04")
        events = max_connector.collect_events(product_id="P04")
        revenue_events = [e for e in events if e.event_type == MetricType.REVENUE]
        assert len(revenue_events) >= 1
        event = revenue_events[0]
        assert "ad_revenue" in event.metrics
        assert "ecpm" in event.metrics
        assert "arpdau" in event.metrics


class TestMAXConnectorAnalytics:
    def test_get_network_stats(self, max_connector):
        max_connector.sync_all(product_id="P04")
        stats = max_connector.get_network_stats()
        assert len(stats) > 0
        assert "applovin" in stats

    def test_get_waterfall_stats(self, max_connector):
        max_connector.sync_all(product_id="P04")
        stats = max_connector.get_waterfall_stats()
        assert stats["total_networks"] > 0
        assert "bidding_networks" in stats
        assert "mediated_networks" in stats

    def test_get_ecpm_trend(self, max_connector):
        max_connector.sync_all(product_id="P04")
        trend = max_connector.get_ecpm_trend(days=7)
        assert len(trend) >= 1
        for entry in trend:
            assert "date" in entry
            assert "ecpm" in entry
            assert "revenue" in entry


class TestMAXConnectorProperties:
    def test_revenue_events_property(self, max_connector):
        max_connector.sync_revenue_events()
        assert len(max_connector.revenue_events) > 0

    def test_performances_property(self, max_connector):
        max_connector.sync_performance("P04")
        assert len(max_connector.performances) > 0

    def test_waterfall_property(self, max_connector):
        max_connector.sync_waterfall()
        assert len(max_connector.waterfall) > 0

    def test_snapshot_property(self, max_connector):
        max_connector.sync_all("P04")
        assert max_connector.snapshot is not None

    def test_last_sync_at_property(self, max_connector):
        max_connector.sync_all("P04")
        assert max_connector.last_sync_at != ""


class TestMAXConnectorSummary:
    def test_get_summary(self, max_connector):
        max_connector.sync_all(product_id="P04")
        summary = max_connector.get_summary()
        assert summary["revenue_events_count"] > 0
        assert summary["performances_count"] > 0
        assert summary["waterfall_count"] > 0
        assert summary["has_snapshot"] is True

    def test_get_summary_network_stats(self, max_connector):
        max_connector.sync_all(product_id="P04")
        summary = max_connector.get_summary()
        assert "network_stats" in summary
        assert len(summary["network_stats"]) > 0

    def test_get_summary_waterfall_stats(self, max_connector):
        max_connector.sync_all(product_id="P04")
        summary = max_connector.get_summary()
        assert "waterfall_stats" in summary
        assert summary["waterfall_stats"]["total_networks"] > 0


class TestMAXConnectorEdgeCases:
    def test_sync_without_product_id(self, max_connector):
        result = max_connector.sync_all()
        assert result["revenue_events"] > 0

    def test_build_snapshot_before_sync(self, max_connector):
        max_connector._performances = []
        snapshot = max_connector.build_revenue_snapshot(product_id="P04")
        assert snapshot is not None

    def test_empty_data_summary(self, max_connector):
        max_connector._revenue_events = []
        max_connector._performances = []
        max_connector._waterfall = []
        max_connector._snapshot = None
        summary = max_connector.get_summary()
        assert summary["revenue_events_count"] == 0
        assert summary["performances_count"] == 0

    def test_build_snapshot_empty_performances(self, max_connector):
        max_connector._performances = []
        snapshot = max_connector.build_revenue_snapshot(product_id="P04")
        assert snapshot is not None  # auto-syncs


# ═══════════════════════════════════════════════════════════════
# Integration Tests
# ═══════════════════════════════════════════════════════════════


class TestIntegrationClientToMapper:
    def test_client_performance_to_snapshot(self, mock_client):
        perfs = mock_client.fetch_performance()
        snap = MAXRevenueMapper.build_snapshot(
            performances=perfs,
            product_id="P04",
        )
        assert snap is not None
        assert snap.total_revenue > 0
        assert snap.total_impressions > 0
        result = MAXRevenueSnapshotValidator.validate(snap)
        assert result.is_valid is True

    def test_client_events_to_performance(self, mock_client):
        events = mock_client.fetch_revenue_events()
        valid = MAXRevenueEventValidator.filter_valid(events)
        assert len(valid) == len(events)

    def test_client_waterfall_mapped(self, mock_client):
        waterfall = mock_client.fetch_waterfall()
        valid = MAXWaterfallValidator.filter_valid(waterfall)
        assert len(valid) == len(waterfall)


class TestIntegrationDataToSnapshot:
    def test_performance_to_snapshot_flow(self, mock_client):
        perfs = mock_client.fetch_performance()
        events = mock_client.fetch_revenue_events()
        waterfall = mock_client.fetch_waterfall()

        snap = MAXRevenueMapper.build_snapshot(
            performances=perfs,
            revenue_events=events,
            waterfall=waterfall,
            product_id="P04",
        )

        assert snap is not None
        assert snap.total_revenue > 0
        assert snap.total_impressions > 0
        assert snap.ecpm > 0
        assert snap.dau > 0
        assert snap.arpdau > 0
        assert "rewarded" in snap.by_format
        assert "applovin" in snap.by_network
        assert "US" in snap.by_country

        result = MAXRevenueSnapshotValidator.validate(snap)
        assert result.is_valid is True

    def test_events_aggregate_to_snapshot_flow(self, mock_client):
        events = mock_client.fetch_revenue_events()
        perfs = MAXRevenueMapper.aggregate_events_to_performance(
            events=events,
            product_id="P04",
        )
        snap = MAXRevenueMapper.build_snapshot(
            performances=perfs,
            product_id="P04",
        )
        assert snap is not None
        assert snap.total_revenue > 0
        assert snap.total_impressions > 0


class TestIntegrationConnectorToFramework:
    def test_connector_to_growth_events(self, max_connector):
        max_connector.sync_all(product_id="P04")
        events = max_connector.collect_events(product_id="P04")

        assert len(events) > 0
        for event in events:
            assert event.source == DataSource.MAX
            assert event.product_id == "P04"
            assert isinstance(event.metrics, dict)

    def test_connector_to_revenue_curve(self, max_connector):
        max_connector.sync_all(product_id="P04")
        curve = max_connector.fetch_revenue_curve(product_id="P04")
        assert curve is not None
        assert curve.platform == DataSource.MAX
        assert curve.predicted_ltv > 0

    def test_connector_ecpm_trend(self, max_connector):
        max_connector.sync_all(product_id="P04")
        trend = max_connector.get_ecpm_trend(days=7)
        assert len(trend) >= 1
        for entry in trend:
            assert entry["ecpm"] >= 0


class TestIntegrationEndToEnd:
    def test_full_flow(self, max_connector):
        # 1. Connect & authenticate
        assert max_connector.is_connected is True
        assert max_connector.is_authenticated is True

        # 2. Sync all data
        sync_result = max_connector.sync_all(product_id="P04")
        assert sync_result["revenue_events"] > 0
        assert sync_result["performances"] > 0
        assert sync_result["waterfall"] > 0

        # 3. Build revenue snapshot
        snapshot = max_connector.build_revenue_snapshot(product_id="P04")
        assert snapshot is not None
        assert snapshot.product_id == "P04"
        assert snapshot.total_revenue > 0
        assert snapshot.arpdau > 0

        # 4. Get analytics
        network_stats = max_connector.get_network_stats()
        assert len(network_stats) > 0

        waterfall_stats = max_connector.get_waterfall_stats()
        assert waterfall_stats["total_networks"] > 0

        ecpm_trend = max_connector.get_ecpm_trend()
        assert len(ecpm_trend) >= 1

        # 5. Collect Growth Data Events
        growth_events = max_connector.collect_events(product_id="P04")
        assert len(growth_events) >= 2

        # 6. Summary
        summary = max_connector.get_summary()
        assert summary["revenue_events_count"] > 0

    def test_reality_layer_workflow(self, max_connector):
        """模拟完整 Reality Layer 数据流:
        MAX → Connector → MAXRevenueSnapshot → Reality Layer → UserValueSnapshot.ad_revenue
        """
        max_connector.sync_all(product_id="P04")

        # Step 1: Build MAXRevenueSnapshot
        snapshot = max_connector.build_revenue_snapshot(product_id="P04")
        assert snapshot is not None
        assert snapshot.ad_revenue_metrics is not None

        # Step 2: Convert to GrowthDataEvent for Reality Layer
        events = max_connector.collect_events(product_id="P04")
        revenue_events = [e for e in events if e.event_type == MetricType.REVENUE]
        assert len(revenue_events) >= 1

        revenue_event = revenue_events[0]
        assert "ad_revenue" in revenue_event.metrics
        assert "ecpm" in revenue_event.metrics
        assert "arpdau" in revenue_event.metrics

        # Step 3: Revenue curve for LTV prediction
        curve = max_connector.fetch_revenue_curve(product_id="P04")
        assert curve is not None
        assert curve.predicted_ltv > 0

    def test_mock_mode_consistency(self, max_connector):
        """验证 mock 模式下多次同步数据一致性."""
        max_connector.sync_all(product_id="P04")
        snap1 = max_connector.build_revenue_snapshot(product_id="P04")

        # Re-sync and rebuild
        max_connector.sync_all(product_id="P04")
        snap2 = max_connector.build_revenue_snapshot(product_id="P04")

        assert snap1 is not None
        assert snap2 is not None
        assert snap1.product_id == snap2.product_id
        assert snap1.total_revenue == snap2.total_revenue

    def test_network_snapshot_consistency(self, max_connector):
        """验证按网络拆分后总和与整体一致."""
        max_connector.sync_all(product_id="P04")
        by_network = max_connector.build_snapshot_by_network(product_id="P04")

        total_revenue = sum(s.total_revenue for s in by_network.values())
        snapshot = max_connector.build_revenue_snapshot(product_id="P04")

        assert snapshot is not None
        assert abs(total_revenue - snapshot.total_revenue) < 0.01

    def test_ad_revenue_metrics(self, max_connector):
        """验证 MAXRevenueSnapshot.ad_revenue_metrics 属性."""
        max_connector.sync_all(product_id="P04")
        snapshot = max_connector.build_revenue_snapshot(product_id="P04")
        assert snapshot is not None
        metrics = snapshot.ad_revenue_metrics
        assert metrics is not None
        assert "ad_revenue" in metrics
        assert "ecpm" in metrics
        assert "arpdau" in metrics
        assert metrics["ad_revenue"] == snapshot.total_revenue

    def test_hybrid_ltv_workflow(self, max_connector):
        """模拟 Hybrid LTV 数据流:
        MAX Revenue + Adjust Revenue → UserValueSnapshot
        """
        max_connector.sync_all(product_id="P04")

        # Build MAX ad revenue snapshot
        max_snapshot = max_connector.build_revenue_snapshot(product_id="P04")
        assert max_snapshot is not None

        # Simulate combined UserValueSnapshot
        ad_revenue = max_snapshot.total_revenue
        iap_revenue = 500.0  # Simulated from Adjust
        total_revenue = ad_revenue + iap_revenue

        assert ad_revenue > 0
        assert total_revenue > iap_revenue
        assert total_revenue > ad_revenue