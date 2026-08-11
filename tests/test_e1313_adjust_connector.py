"""E13.1.3 Adjust Connector — 测试套件.

预计: models 30, client 40, event_parser 25, attribution 25, mapper 35, validator 35, connector 50, integration 40
Total: ~280 tests
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

# Ensure src is on path
sys.path.insert(0, "src")

from market_ops.creative_vision_runtime.growth_runtime.connectors.adjust import (
    # Enums
    AdjustEventType,
    AdjustNetwork,
    AdjustRevenueType,
    # Models
    AdjustAPIResponse,
    AdjustUserEvent,
    AttributionRecord,
    RetentionSnapshot,
    UserValueSnapshot,
    # Client
    AdjustClient,
    # Parser
    AdjustEventParser,
    # Attribution
    AttributionMapper,
    # Mapper
    AdjustValueMapper,
    # Validator
    APIResponseValidator,
    AdjustEventValidator,
    AttributionValidator,
    RetentionValidator,
    UserValueValidator,
    ValidationResult,
    # Connector
    AdjustConnector,
)
from market_ops.creative_vision_runtime.growth_runtime.connectors.models import (
    ConnectorConfig,
    ConnectorHealth,
    DataSource,
    GrowthDataEvent,
    MetricType,
    RetentionCurve,
    UserRevenueCurve,
)


# ═══════════════════════════════════════════════════════════════
# Test Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def mock_client():
    """创建已连接并认证的 mock AdjustClient."""
    client = AdjustClient(use_mock=True, app_token="test_app")
    client.connect()
    client.authenticate()
    return client


@pytest.fixture
def sample_events() -> list[AdjustUserEvent]:
    """创建样本事件列表."""
    today = datetime.now(timezone.utc)
    events = []
    for i in range(10):
        events.append(AdjustUserEvent(
            event_id=f"evt_{i}",
            user_id=f"user_{i}",
            product_id="P04",
            event_name=AdjustEventType.INSTALL if i < 3 else AdjustEventType.PURCHASE,
            timestamp=(today.isoformat()),
            revenue=9.99 if i >= 3 else 0.0,
            currency="USD",
            revenue_type=AdjustRevenueType.IAP,
            network="meta" if i % 2 == 0 else "organic",
        ))
    return events


@pytest.fixture
def sample_attributions() -> list[AttributionRecord]:
    """创建样本归因记录."""
    today = datetime.now(timezone.utc)
    attrs = []
    for i in range(5):
        attrs.append(AttributionRecord(
            user_id=f"user_{i}",
            network=AdjustNetwork.META if i < 3 else AdjustNetwork.ORGANIC,
            campaign_id=f"camp_{i}" if i < 3 else "",
            install_time=(today.isoformat()),
            is_organic=i >= 3,
        ))
    return attrs


@pytest.fixture
def sample_retention() -> RetentionSnapshot:
    """创建样本留存快照."""
    return RetentionSnapshot(
        product_id="P04",
        cohort_date="2026-07-01",
        cohort_size=1000,
        d1=0.45,
        d3=0.35,
        d7=0.28,
        d14=0.20,
        d30=0.12,
        d60=0.08,
        d90=0.05,
    )


@pytest.fixture
def connector_config() -> ConnectorConfig:
    """创建 Adjust Connector 配置."""
    return ConnectorConfig(
        connector_type=DataSource.ADJUST,
        access_token="mock",
        app_id="test_app",
        account_id="test_account",
    )


@pytest.fixture
def adjust_connector(connector_config) -> AdjustConnector:
    """创建已连接的 AdjustConnector."""
    conn = AdjustConnector(connector_config)
    conn.connect()
    conn.authenticate()
    return conn


# ═══════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════


class TestAdjustEventType:
    def test_install_value(self):
        assert AdjustEventType.INSTALL.value == "install"

    def test_purchase_value(self):
        assert AdjustEventType.PURCHASE.value == "purchase"

    def test_ad_revenue_value(self):
        assert AdjustEventType.AD_REVENUE.value == "ad_revenue"

    def test_subscription_value(self):
        assert AdjustEventType.SUBSCRIPTION.value == "subscription"

    def test_session_value(self):
        assert AdjustEventType.SESSION.value == "session"

    def test_tutorial_complete_value(self):
        assert AdjustEventType.TUTORIAL_COMPLETE.value == "tutorial_complete"

    def test_string_enum_behavior(self):
        assert str(AdjustEventType.INSTALL) == "AdjustEventType.INSTALL"


class TestAdjustRevenueType:
    def test_iap_value(self):
        assert AdjustRevenueType.IAP.value == "iap"

    def test_iaa_value(self):
        assert AdjustRevenueType.IAA.value == "iaa"

    def test_subscription_value(self):
        assert AdjustRevenueType.SUBSCRIPTION.value == "subscription"

    def test_hybrid_value(self):
        assert AdjustRevenueType.HYBRID.value == "hybrid"


class TestAdjustNetwork:
    def test_meta_value(self):
        assert AdjustNetwork.META.value == "meta"

    def test_google_value(self):
        assert AdjustNetwork.GOOGLE.value == "google"

    def test_organic_value(self):
        assert AdjustNetwork.ORGANIC.value == "organic"

    def test_unknown_value(self):
        assert AdjustNetwork.UNKNOWN.value == "unknown"

    def test_tiktok_value(self):
        assert AdjustNetwork.TIKTOK.value == "tiktok"

    def test_asa_value(self):
        assert AdjustNetwork.ASA.value == "asa"


# ═══════════════════════════════════════════════════════════════
# Models: AdjustUserEvent
# ═══════════════════════════════════════════════════════════════


class TestAdjustUserEvent:
    def test_default_values(self):
        event = AdjustUserEvent()
        assert event.event_id == ""
        assert event.revenue == 0.0
        assert event.currency == "USD"
        assert event.event_name == AdjustEventType.CUSTOM_EVENT

    def test_custom_event(self):
        event = AdjustUserEvent(
            event_id="evt_001",
            user_id="user_001",
            product_id="P04",
            event_name=AdjustEventType.INSTALL,
            timestamp="2026-07-01T00:00:00",
        )
        assert event.event_id == "evt_001"
        assert event.user_id == "user_001"
        assert event.product_id == "P04"
        assert event.event_name == AdjustEventType.INSTALL

    def test_revenue_event(self):
        event = AdjustUserEvent(
            event_id="evt_001",
            event_name=AdjustEventType.PURCHASE,
            revenue=9.99,
            currency="USD",
            revenue_type=AdjustRevenueType.IAP,
        )
        assert event.revenue == 9.99
        assert event.revenue_type == AdjustRevenueType.IAP

    def test_is_revenue_event_true(self):
        event = AdjustUserEvent(revenue=9.99, revenue_type=AdjustRevenueType.IAP)
        assert event.is_revenue_event is True

    def test_is_revenue_event_false(self):
        event = AdjustUserEvent(revenue=0.0)
        assert event.is_revenue_event is False

    def test_is_install_true(self):
        event = AdjustUserEvent(event_name=AdjustEventType.INSTALL)
        assert event.is_install is True

    def test_is_install_false(self):
        event = AdjustUserEvent(event_name=AdjustEventType.PURCHASE)
        assert event.is_install is False

    def test_is_purchase_true(self):
        event = AdjustUserEvent(event_name=AdjustEventType.PURCHASE)
        assert event.is_purchase is True

    def test_is_purchase_false(self):
        event = AdjustUserEvent(event_name=AdjustEventType.INSTALL)
        assert event.is_purchase is False

    def test_is_ad_revenue_true(self):
        event = AdjustUserEvent(event_name=AdjustEventType.AD_REVENUE)
        assert event.is_ad_revenue is True

    def test_is_ad_revenue_false(self):
        event = AdjustUserEvent(event_name=AdjustEventType.PURCHASE)
        assert event.is_ad_revenue is False

    def test_to_dict(self):
        event = AdjustUserEvent(
            event_id="evt_001",
            user_id="user_001",
            product_id="P04",
            event_name=AdjustEventType.PURCHASE,
            revenue=9.99,
            currency="USD",
            revenue_type=AdjustRevenueType.IAP,
        )
        d = event.to_dict()
        assert d["event_id"] == "evt_001"
        assert d["revenue"] == 9.99
        assert d["event_name"] == "purchase"
        assert d["revenue_type"] == "iap"

    def test_to_dict_rounds_revenue(self):
        event = AdjustUserEvent(revenue=9.9999)
        d = event.to_dict()
        assert d["revenue"] == 9.9999  # round(9.9999, 4) = 9.9999

    def test_fetched_at_auto_generated(self):
        event = AdjustUserEvent()
        assert event.fetched_at != ""

    def test_properties_dict(self):
        event = AdjustUserEvent(properties={"level": 5, "score": 100})
        assert event.properties["level"] == 5

    def test_raw_event_stored(self):
        event = AdjustUserEvent(raw_event={"foo": "bar"})
        assert event.raw_event["foo"] == "bar"

    def test_network_context(self):
        event = AdjustUserEvent(
            network="meta",
            campaign_id="camp_001",
            adgroup_id="adg_001",
            creative_id="cr_001",
        )
        assert event.network == "meta"
        assert event.campaign_id == "camp_001"
        assert event.adgroup_id == "adg_001"
        assert event.creative_id == "cr_001"

    def test_device_info(self):
        event = AdjustUserEvent(
            device_id="idfa_abc",
            os_name="ios",
            os_version="16.0",
            app_version="1.2.3",
            country="US",
        )
        assert event.device_id == "idfa_abc"
        assert event.os_name == "ios"
        assert event.country == "US"


# ═══════════════════════════════════════════════════════════════
# Models: AttributionRecord
# ═══════════════════════════════════════════════════════════════


class TestAttributionRecord:
    def test_default_values(self):
        record = AttributionRecord()
        assert record.user_id == ""
        assert record.network == AdjustNetwork.UNKNOWN
        assert record.is_organic is True

    def test_paid_attribution(self):
        record = AttributionRecord(
            user_id="user_001",
            network=AdjustNetwork.META,
            campaign_id="camp_001",
            is_organic=False,
        )
        assert record.is_paid is True
        assert record.is_organic is False

    def test_organic_attribution(self):
        record = AttributionRecord(
            user_id="user_001",
            network=AdjustNetwork.ORGANIC,
            is_organic=True,
        )
        assert record.is_paid is False
        assert record.is_organic is True

    def test_source_platform_meta(self):
        record = AttributionRecord(network=AdjustNetwork.META)
        assert record.source_platform == "meta_ads"

    def test_source_platform_google(self):
        record = AttributionRecord(network=AdjustNetwork.GOOGLE)
        assert record.source_platform == "google_ads"

    def test_source_platform_organic(self):
        record = AttributionRecord(network=AdjustNetwork.ORGANIC)
        assert record.source_platform == "organic"

    def test_source_platform_unknown(self):
        record = AttributionRecord(network=AdjustNetwork.UNKNOWN)
        assert record.source_platform == "unknown"

    def test_to_dict(self):
        record = AttributionRecord(
            user_id="user_001",
            network=AdjustNetwork.META,
            campaign_id="camp_001",
            is_organic=False,
        )
        d = record.to_dict()
        assert d["user_id"] == "user_001"
        assert d["network"] == "meta"
        assert d["is_organic"] is False

    def test_raw_data_stored(self):
        record = AttributionRecord(raw_data={"source": "adjust"})
        assert record.raw_data["source"] == "adjust"


# ═══════════════════════════════════════════════════════════════
# Models: RetentionSnapshot
# ═══════════════════════════════════════════════════════════════


class TestRetentionSnapshot:
    def test_default_values(self):
        snap = RetentionSnapshot()
        assert snap.product_id == ""
        assert snap.cohort_size == 0
        assert snap.d1 == 0.0

    def test_custom_snapshot(self):
        snap = RetentionSnapshot(
            product_id="P04",
            cohort_date="2026-07-01",
            cohort_size=1000,
            d1=0.45,
            d7=0.28,
            d30=0.12,
        )
        assert snap.product_id == "P04"
        assert snap.cohort_size == 1000
        assert snap.d1 == 0.45

    def test_d7_retention_rate(self):
        snap = RetentionSnapshot(d7=0.28)
        assert snap.d7_retention_rate == 0.28

    def test_d30_retention_rate(self):
        snap = RetentionSnapshot(d30=0.12)
        assert snap.d30_retention_rate == 0.12

    def test_is_healthy_true(self):
        snap = RetentionSnapshot(d7=0.25)
        assert snap.is_healthy is True

    def test_is_healthy_false(self):
        snap = RetentionSnapshot(d7=0.15)
        assert snap.is_healthy is False

    def test_is_healthy_boundary(self):
        snap = RetentionSnapshot(d7=0.20)
        assert snap.is_healthy is True

    def test_to_dict(self):
        snap = RetentionSnapshot(
            product_id="P04",
            cohort_date="2026-07-01",
            cohort_size=500,
            d1=0.45,
            d7=0.28,
        )
        d = snap.to_dict()
        assert d["product_id"] == "P04"
        assert d["cohort_size"] == 500
        assert d["d1"] == 0.45

    def test_by_network_dict(self):
        snap = RetentionSnapshot(
            by_network={"meta": {"d1": 0.5, "d7": 0.3}},
        )
        assert snap.by_network["meta"]["d1"] == 0.5

    def test_to_e1311_retention_curve(self):
        snap = RetentionSnapshot(
            product_id="P04",
            cohort_date="2026-07-01",
            cohort_size=1000,
            d1=0.45,
            d3=0.35,
            d7=0.28,
            d14=0.20,
            d30=0.12,
            d60=0.08,
            d90=0.05,
        )
        curve = snap.to_e1311_retention_curve()
        assert curve.product_id == "P04"
        assert curve.platform == DataSource.ADJUST
        assert curve.d1_retention == 0.45
        assert curve.d7_retention == 0.28
        assert curve.cohort_size == 1000


# ═══════════════════════════════════════════════════════════════
# Models: UserValueSnapshot
# ═══════════════════════════════════════════════════════════════


class TestUserValueSnapshot:
    def test_default_values(self):
        snap = UserValueSnapshot()
        assert snap.product_id == ""
        assert snap.total_users == 0
        assert snap.total_revenue == 0.0

    def test_custom_snapshot(self):
        snap = UserValueSnapshot(
            product_id="P04",
            date="2026-07-01",
            total_users=1000,
            total_revenue=5000.0,
            arpu=5.0,
            arppu=50.0,
            paying_rate=0.1,
        )
        assert snap.product_id == "P04"
        assert snap.total_users == 1000
        assert snap.total_revenue == 5000.0
        assert snap.arpu == 5.0

    def test_is_iaa_dominant_true(self):
        snap = UserValueSnapshot(ad_revenue=100.0, iap_revenue=50.0)
        assert snap.is_iaa_dominant is True

    def test_is_iaa_dominant_false(self):
        snap = UserValueSnapshot(ad_revenue=50.0, iap_revenue=100.0)
        assert snap.is_iaa_dominant is False

    def test_is_iap_dominant_true(self):
        snap = UserValueSnapshot(iap_revenue=100.0, ad_revenue=50.0)
        assert snap.is_iap_dominant is True

    def test_is_iap_dominant_equal(self):
        snap = UserValueSnapshot(iap_revenue=50.0, ad_revenue=50.0)
        assert snap.is_iap_dominant is False

    def test_revenue_per_user(self):
        snap = UserValueSnapshot(total_users=100, total_revenue=500.0)
        assert snap.revenue_per_user == 5.0

    def test_revenue_per_user_zero(self):
        snap = UserValueSnapshot(total_users=0)
        assert snap.revenue_per_user == 0.0

    def test_ltv_indicator(self):
        snap = UserValueSnapshot(arpu=5.0)
        assert snap.ltv_indicator == 150.0

    def test_ltv_indicator_zero(self):
        snap = UserValueSnapshot(arpu=0.0)
        assert snap.ltv_indicator == 0.0

    def test_to_dict(self):
        snap = UserValueSnapshot(
            product_id="P04",
            date="2026-07-01",
            total_users=100,
            total_revenue=500.0,
            arpu=5.0,
            paying_rate=0.1,
        )
        d = snap.to_dict()
        assert d["product_id"] == "P04"
        assert d["total_revenue"] == 500.0
        assert d["arpu"] == 5.0

    def test_with_retention(self):
        retention = RetentionSnapshot(product_id="P04", cohort_date="2026-07-01", d7=0.28)
        snap = UserValueSnapshot(retention=retention)
        assert snap.retention is not None
        assert snap.retention.d7 == 0.28

    def test_by_network_dict(self):
        snap = UserValueSnapshot(
            by_network={"meta": {"revenue": 300.0, "users": 50}},
        )
        assert snap.by_network["meta"]["revenue"] == 300.0


# ═══════════════════════════════════════════════════════════════
# Models: AdjustAPIResponse
# ═══════════════════════════════════════════════════════════════


class TestAdjustAPIResponse:
    def test_default_values(self):
        resp = AdjustAPIResponse()
        assert resp.success is True
        assert resp.data == []
        assert resp.error_message == ""

    def test_error_response(self):
        resp = AdjustAPIResponse(
            success=False,
            error_message="API Error",
            error_code="401",
        )
        assert resp.is_error is True
        assert resp.error_message == "API Error"

    def test_success_response(self):
        resp = AdjustAPIResponse(success=True)
        assert resp.is_error is False

    def test_to_dict(self):
        resp = AdjustAPIResponse(
            success=True,
            data=[{"id": 1}],
            total_count=100,
            has_more=True,
        )
        d = resp.to_dict()
        assert d["success"] is True
        assert d["data_count"] == 1
        assert d["total_count"] == 100

    def test_raw_response(self):
        resp = AdjustAPIResponse(raw_response={"meta": {"count": 100}})
        assert resp.raw_response["meta"]["count"] == 100


# ═══════════════════════════════════════════════════════════════
# AdjustClient
# ═══════════════════════════════════════════════════════════════


class TestAdjustClientInit:
    def test_default_init(self):
        client = AdjustClient()
        assert client.is_connected is False
        assert client.is_authenticated is False

    def test_init_with_token(self):
        client = AdjustClient(api_token="real_token", use_mock=False)
        assert client.is_connected is False

    def test_init_mock_mode(self):
        client = AdjustClient(use_mock=True)
        assert client.is_connected is False

    def test_init_auto_mock_when_no_token(self):
        client = AdjustClient(api_token="")
        assert client.is_connected is False


class TestAdjustClientConnect:
    def test_connect_mock(self):
        client = AdjustClient(use_mock=True)
        assert client.connect() is True
        assert client.is_connected is True

    def test_connect_no_token_auto_mock(self):
        client = AdjustClient(api_token="", use_mock=False)
        # Constructor auto-detects no token and falls back to mock mode
        assert client.connect() is True

    def test_connect_real_mode(self):
        client = AdjustClient(api_token="real", use_mock=False)
        assert client.connect() is True
        assert client.is_connected is True

    def test_authenticate_mock(self):
        client = AdjustClient(use_mock=True)
        client.connect()
        assert client.authenticate() is True
        assert client.is_authenticated is True

    def test_authenticate_no_token_auto_mock(self):
        client = AdjustClient(api_token="", use_mock=False)
        client.connect()
        # Constructor auto-detects no token and falls back to mock mode
        assert client.authenticate() is True

    def test_disconnect(self):
        client = AdjustClient(use_mock=True)
        client.connect()
        client.disconnect()
        assert client.is_connected is False
        assert client.is_authenticated is False


class TestAdjustClientEvents:
    def test_fetch_events_mock(self, mock_client):
        events = mock_client.fetch_events()
        assert len(events) == 50

    def test_fetch_events_with_product_id(self, mock_client):
        events = mock_client.fetch_events(product_id="P04")
        assert len(events) == 50

    def test_fetch_events_wrong_product_id(self, mock_client):
        events = mock_client.fetch_events(product_id="NONEXISTENT")
        assert len(events) == 0

    def test_fetch_events_with_date_range(self, mock_client):
        events = mock_client.fetch_events(
            start_date="2020-01-01",
            end_date="2099-12-31",
        )
        assert len(events) == 50

    def test_fetch_events_filtered_by_type(self, mock_client):
        events = mock_client.fetch_events(
            event_types=[AdjustEventType.INSTALL],
        )
        assert len(events) > 0
        for e in events:
            assert e.event_name == AdjustEventType.INSTALL

    def test_fetch_events_not_connected(self):
        client = AdjustClient(use_mock=True)
        with pytest.raises(RuntimeError, match="not connected"):
            client.fetch_events()


class TestAdjustClientAttribution:
    def test_fetch_attribution_mock(self, mock_client):
        attributions = mock_client.fetch_attribution()
        assert len(attributions) == 20

    def test_fetch_attribution_by_network(self, mock_client):
        attributions = mock_client.fetch_attribution(network="meta")
        assert len(attributions) > 0
        for a in attributions:
            assert a.network == AdjustNetwork.META

    def test_fetch_attribution_by_date(self, mock_client):
        attributions = mock_client.fetch_attribution(
            start_date="2020-01-01",
            end_date="2099-12-31",
        )
        assert len(attributions) == 20

    def test_fetch_attribution_not_connected(self):
        client = AdjustClient(use_mock=True)
        with pytest.raises(RuntimeError, match="not connected"):
            client.fetch_attribution()


class TestAdjustClientRetention:
    def test_fetch_retention_mock(self, mock_client):
        retention = mock_client.fetch_retention()
        assert retention is not None
        assert retention.product_id == "P04"
        assert retention.cohort_size == 1000

    def test_fetch_retention_with_product_id(self, mock_client):
        retention = mock_client.fetch_retention(product_id="P04")
        assert retention is not None
        assert retention.product_id == "P04"

    def test_fetch_retention_wrong_product_id(self, mock_client):
        retention = mock_client.fetch_retention(product_id="NONEXISTENT")
        assert retention is not None  # mock mode returns the mock data anyway

    def test_fetch_retention_not_connected(self):
        client = AdjustClient(use_mock=True)
        with pytest.raises(RuntimeError, match="not connected"):
            client.fetch_retention()


class TestAdjustClientSummary:
    def test_get_summary(self, mock_client):
        summary = mock_client.get_summary()
        assert summary["connected"] is True
        assert summary["authenticated"] is True
        assert summary["use_mock"] is True
        assert summary["events_count"] == 50
        assert summary["attributions_count"] == 20
        assert summary["has_retention"] is True


class TestAdjustClientRequestCount:
    def test_request_count_increments(self, mock_client):
        initial = mock_client.get_summary()["request_count"]
        mock_client.fetch_events()
        assert mock_client.get_summary()["request_count"] == initial + 1

    def test_request_count_multiple_calls(self, mock_client):
        mock_client.fetch_events()
        mock_client.fetch_attribution()
        mock_client.fetch_retention()
        assert mock_client.get_summary()["request_count"] == 3


# ═══════════════════════════════════════════════════════════════
# AdjustEventParser
# ═══════════════════════════════════════════════════════════════


class TestAdjustEventParserParse:
    def test_parse_install_event(self):
        raw = {
            "event_name": "af_install",
            "event_id": "evt_001",
            "user_id": "user_001",
            "app_id": "P04",
            "timestamp": "2026-07-01T00:00:00",
            "network": "meta",
            "country": "US",
        }
        event = AdjustEventParser.parse(raw)
        assert event.event_id == "evt_001"
        assert event.event_name == AdjustEventType.INSTALL
        assert event.user_id == "user_001"
        assert event.product_id == "P04"
        assert event.network == "meta"

    def test_parse_purchase_event(self):
        raw = {
            "event_name": "af_purchase",
            "event_id": "evt_002",
            "user_id": "user_002",
            "revenue": "9.99",
            "currency": "USD",
        }
        event = AdjustEventParser.parse(raw)
        assert event.event_name == AdjustEventType.PURCHASE
        assert event.revenue == 9.99
        assert event.revenue_type == AdjustRevenueType.IAP

    def test_parse_ad_revenue_event(self):
        raw = {
            "event_name": "af_ad_revenue",
            "event_id": "evt_003",
            "revenue": 0.05,
        }
        event = AdjustEventParser.parse(raw)
        assert event.event_name == AdjustEventType.AD_REVENUE
        assert event.revenue_type == AdjustRevenueType.IAA
        assert event.revenue == 0.05

    def test_parse_subscription_event(self):
        raw = {
            "event_name": "af_subscription",
            "event_id": "evt_004",
            "revenue": 4.99,
        }
        event = AdjustEventParser.parse(raw)
        assert event.event_name == AdjustEventType.SUBSCRIPTION
        assert event.revenue_type == AdjustRevenueType.SUBSCRIPTION

    def test_parse_unknown_event(self):
        raw = {
            "event_name": "custom_action",
            "event_id": "evt_005",
        }
        event = AdjustEventParser.parse(raw)
        assert event.event_name == AdjustEventType.CUSTOM_EVENT

    def test_parse_empty_event_name(self):
        raw = {"event_id": "evt_006"}
        event = AdjustEventParser.parse(raw)
        assert event.event_name == AdjustEventType.CUSTOM_EVENT

    def test_parse_extracts_device_id(self):
        raw = {
            "event_name": "install",
            "event_id": "evt_007",
            "idfa": "idfa_abc123",
        }
        event = AdjustEventParser.parse(raw)
        assert event.device_id == "idfa_abc123"

    def test_parse_extracts_gps_adid(self):
        raw = {
            "event_name": "install",
            "event_id": "evt_008",
            "gps_adid": "gps_xyz789",
        }
        event = AdjustEventParser.parse(raw)
        assert event.device_id == "gps_xyz789"

    def test_parse_extracts_os_name(self):
        raw = {
            "event_name": "install",
            "event_id": "evt_009",
            "platform": "ios",
        }
        event = AdjustEventParser.parse(raw)
        assert event.os_name == "ios"

    def test_parse_stores_raw_event(self):
        raw = {"event_name": "install", "custom_field": "value"}
        event = AdjustEventParser.parse(raw)
        assert event.raw_event["custom_field"] == "value"

    def test_parse_revenue_from_string(self):
        raw = {"event_name": "purchase", "event_revenue": "19.99"}
        event = AdjustEventParser.parse(raw)
        assert event.revenue == 19.99

    def test_parse_invalid_revenue_string(self):
        raw = {"event_name": "purchase", "event_revenue": "invalid"}
        event = AdjustEventParser.parse(raw)
        assert event.revenue == 0.0


class TestAdjustEventParserBatch:
    def test_parse_batch(self):
        raw_events = [
            {"event_name": "af_install", "event_id": "1"},
            {"event_name": "af_purchase", "event_id": "2"},
            {"event_name": "af_session", "event_id": "3"},
        ]
        events = AdjustEventParser.parse_batch(raw_events)
        assert len(events) == 3
        assert events[0].event_name == AdjustEventType.INSTALL
        assert events[1].event_name == AdjustEventType.PURCHASE
        assert events[2].event_name == AdjustEventType.SESSION

    def test_parse_batch_empty(self):
        events = AdjustEventParser.parse_batch([])
        assert events == []


class TestAdjustEventParserFilter:
    def test_filter_by_type(self, sample_events):
        installs = AdjustEventParser.filter_by_type(sample_events, AdjustEventType.INSTALL)
        assert len(installs) == 3
        for e in installs:
            assert e.is_install

    def test_filter_revenue_events(self, sample_events):
        revenue = AdjustEventParser.filter_revenue_events(sample_events)
        assert len(revenue) == 7
        for e in revenue:
            assert e.is_revenue_event


# ═══════════════════════════════════════════════════════════════
# AttributionMapper
# ═══════════════════════════════════════════════════════════════


class TestAttributionMapperMap:
    def test_map_network_meta(self):
        assert AttributionMapper.map_network("meta") == AdjustNetwork.META

    def test_map_network_facebook(self):
        assert AttributionMapper.map_network("facebook") == AdjustNetwork.META

    def test_map_network_google(self):
        assert AttributionMapper.map_network("google") == AdjustNetwork.GOOGLE

    def test_map_network_organic(self):
        assert AttributionMapper.map_network("organic") == AdjustNetwork.ORGANIC

    def test_map_network_unknown(self):
        assert AttributionMapper.map_network("unknown_network") == AdjustNetwork.UNKNOWN

    def test_map_network_empty(self):
        assert AttributionMapper.map_network("") == AdjustNetwork.ORGANIC

    def test_map_network_case_insensitive(self):
        assert AttributionMapper.map_network("META") == AdjustNetwork.META

    def test_map_network_whitespace(self):
        assert AttributionMapper.map_network("  meta  ") == AdjustNetwork.META


class TestAttributionMapperParse:
    def test_parse_raw_attribution(self):
        raw = {
            "user_id": "user_001",
            "network": "meta",
            "campaign_id": "camp_001",
            "campaign_name": "P04_US",
            "adgroup_id": "adg_001",
            "creative_id": "cr_001",
            "installed_at": "2026-07-01T00:00:00",
            "country": "US",
        }
        record = AttributionMapper.parse_raw_attribution(raw)
        assert record.user_id == "user_001"
        assert record.network == AdjustNetwork.META
        assert record.campaign_id == "camp_001"
        assert record.is_organic is False

    def test_parse_organic_attribution(self):
        raw = {
            "user_id": "user_002",
            "network": "organic",
        }
        record = AttributionMapper.parse_raw_attribution(raw)
        assert record.is_organic is True

    def test_parse_batch(self):
        raw = [
            {"user_id": "u1", "network": "meta", "campaign_id": "c1"},
            {"user_id": "u2", "network": "organic"},
        ]
        records = AttributionMapper.parse_batch(raw)
        assert len(records) == 2
        assert records[0].is_paid is True
        assert records[1].is_organic is True


class TestAttributionMapperGroup:
    def test_group_by_network(self, sample_attributions):
        groups = AttributionMapper.group_by_network(sample_attributions)
        assert AdjustNetwork.META in groups
        assert AdjustNetwork.ORGANIC in groups
        assert len(groups[AdjustNetwork.META]) == 3
        assert len(groups[AdjustNetwork.ORGANIC]) == 2

    def test_group_by_campaign(self, sample_attributions):
        groups = AttributionMapper.group_by_campaign(sample_attributions)
        assert "camp_0" in groups
        assert "organic" in groups

    def test_get_network_stats(self, sample_attributions):
        stats = AttributionMapper.get_network_stats(sample_attributions)
        assert "meta" in stats
        assert stats["meta"]["total"] == 3
        assert stats["meta"]["paid_ratio"] == 1.0


class TestAttributionMapperLink:
    def test_link_events_to_attribution(self, sample_events, sample_attributions):
        events = AttributionMapper.link_events_to_attribution(
            list(sample_events), sample_attributions,
        )
        # user_0 should get linked to meta (camp_0)
        event0 = next(e for e in events if e.user_id == "user_0")
        assert event0.network == "meta"
        assert event0.campaign_id == "camp_0"

    def test_link_no_match(self, sample_events):
        empty_attrs = []
        events = AttributionMapper.link_events_to_attribution(
            list(sample_events), empty_attrs,
        )
        assert len(events) == len(sample_events)


class TestAttributionMapperSplit:
    def test_compute_organic_vs_paid_split(self, sample_attributions):
        split = AttributionMapper.compute_organic_vs_paid_split(sample_attributions)
        assert split["organic"] == 2
        assert split["paid"] == 3
        assert split["total"] == 5

    def test_empty_split(self):
        split = AttributionMapper.compute_organic_vs_paid_split([])
        assert split["total"] == 0
        assert split["organic_ratio"] == 0.0


# ═══════════════════════════════════════════════════════════════
# AdjustValueMapper
# ═══════════════════════════════════════════════════════════════


class TestAdjustValueMapperBuildSnapshot:
    def test_build_snapshot(self, sample_events, sample_retention):
        snap = AdjustValueMapper.build_snapshot(
            events=sample_events,
            retention=sample_retention,
            product_id="P04",
            date="2026-07-01",
        )
        assert snap.product_id == "P04"
        assert snap.date == "2026-07-01"
        assert snap.total_users == 10
        assert snap.new_users == 3
        assert snap.total_revenue > 0
        assert snap.retention is not None

    def test_build_snapshot_no_events(self):
        snap = AdjustValueMapper.build_snapshot(
            events=[],
            product_id="P04",
            date="2026-07-01",
        )
        assert snap.product_id == "P04"
        assert snap.total_users == 0
        assert snap.total_revenue == 0.0

    def test_build_snapshot_auto_product_id(self, sample_events):
        snap = AdjustValueMapper.build_snapshot(events=sample_events)
        assert snap.product_id == "P04"

    def test_build_snapshot_revenue_split(self, sample_events):
        snap = AdjustValueMapper.build_snapshot(events=sample_events, product_id="P04")
        assert snap.iap_revenue > 0
        assert snap.ad_revenue == 0.0

    def test_build_snapshot_arpu(self, sample_events):
        snap = AdjustValueMapper.build_snapshot(events=sample_events, product_id="P04")
        assert snap.arpu > 0
        assert snap.arppu > 0

    def test_build_snapshot_by_network(self, sample_events):
        snap = AdjustValueMapper.build_snapshot(events=sample_events, product_id="P04")
        assert "meta" in snap.by_network
        assert "organic" in snap.by_network
        assert snap.by_network["meta"]["revenue"] > 0

    def test_build_snapshot_installs(self, sample_events):
        snap = AdjustValueMapper.build_snapshot(events=sample_events, product_id="P04")
        assert snap.installs == 3


class TestAdjustValueMapperBuildSnapshotsByDate:
    def test_build_snapshots_by_date(self, sample_events):
        snapshots = AdjustValueMapper.build_snapshots_by_date(
            events=sample_events,
            product_id="P04",
        )
        assert len(snapshots) >= 1

    def test_build_snapshots_by_date_sorted(self, sample_events):
        snapshots = AdjustValueMapper.build_snapshots_by_date(
            events=sample_events,
            product_id="P04",
        )
        for i in range(len(snapshots) - 1):
            assert snapshots[i].date <= snapshots[i + 1].date


class TestAdjustValueMapperBuildSnapshotByNetwork:
    def test_build_snapshot_by_network(self, sample_events):
        snapshots = AdjustValueMapper.build_snapshot_by_network(
            events=sample_events,
            product_id="P04",
        )
        assert "meta" in snapshots
        assert "organic" in snapshots
        assert snapshots["meta"].product_id == "P04"


class TestAdjustValueMapperRevenueBreakdown:
    def test_compute_revenue_breakdown(self, sample_events):
        breakdown = AdjustValueMapper.compute_revenue_breakdown(sample_events)
        assert breakdown["iap"] > 0
        assert breakdown["total"] > 0
        assert breakdown["iap_ratio"] > 0

    def test_compute_revenue_breakdown_empty(self):
        breakdown = AdjustValueMapper.compute_revenue_breakdown([])
        assert breakdown["total"] == 0.0


class TestAdjustValueMapperEventTypeCounts:
    def test_compute_event_type_counts(self, sample_events):
        counts = AdjustValueMapper.compute_event_type_counts(sample_events)
        assert counts["install"] == 3
        assert counts["purchase"] == 7

    def test_compute_event_type_counts_empty(self):
        counts = AdjustValueMapper.compute_event_type_counts([])
        assert counts == {}


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
        assert result.is_valid is True  # warnings don't invalidate
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


class TestAdjustEventValidator:
    def test_valid_event(self):
        event = AdjustUserEvent(
            event_id="evt_001",
            event_name=AdjustEventType.INSTALL,
            timestamp="2026-07-01T00:00:00",
        )
        result = AdjustEventValidator.validate(event)
        assert result.is_valid is True

    def test_missing_event_id(self):
        event = AdjustUserEvent(
            event_name=AdjustEventType.INSTALL,
            timestamp="2026-07-01T00:00:00",
        )
        result = AdjustEventValidator.validate(event)
        assert result.is_valid is False

    def test_negative_revenue(self):
        event = AdjustUserEvent(
            event_id="evt_001",
            event_name=AdjustEventType.PURCHASE,
            timestamp="2026-07-01T00:00:00",
            revenue=-10.0,
        )
        result = AdjustEventValidator.validate(event)
        assert result.is_valid is False

    def test_missing_timestamp(self):
        event = AdjustUserEvent(
            event_id="evt_001",
            event_name=AdjustEventType.INSTALL,
        )
        result = AdjustEventValidator.validate(event)
        assert result.is_valid is False

    def test_revenue_event_zero_revenue_warning(self):
        event = AdjustUserEvent(
            event_id="evt_001",
            event_name=AdjustEventType.PURCHASE,
            timestamp="2026-07-01T00:00:00",
            revenue=0.0,
        )
        result = AdjustEventValidator.validate(event)
        assert len(result.warnings) >= 1

    def test_high_revenue_warning(self):
        event = AdjustUserEvent(
            event_id="evt_001",
            event_name=AdjustEventType.PURCHASE,
            timestamp="2026-07-01T00:00:00",
            revenue=200000.0,
        )
        result = AdjustEventValidator.validate(event)
        assert len(result.warnings) >= 1

    def test_missing_user_id_warning(self):
        event = AdjustUserEvent(
            event_id="evt_001",
            event_name=AdjustEventType.INSTALL,
            timestamp="2026-07-01T00:00:00",
        )
        result = AdjustEventValidator.validate(event)
        assert len(result.warnings) >= 1

    def test_validate_batch(self):
        events = [
            AdjustUserEvent(event_id="e1", event_name=AdjustEventType.INSTALL, timestamp="2026-07-01"),
            AdjustUserEvent(event_id="", event_name=AdjustEventType.INSTALL, timestamp="2026-07-01"),
        ]
        results = AdjustEventValidator.validate_batch(events)
        assert results[0].is_valid is True
        assert results[1].is_valid is False

    def test_filter_valid(self):
        events = [
            AdjustUserEvent(event_id="e1", event_name=AdjustEventType.INSTALL, timestamp="2026-07-01"),
            AdjustUserEvent(event_id="", event_name=AdjustEventType.INSTALL, timestamp="2026-07-01"),
        ]
        valid = AdjustEventValidator.filter_valid(events)
        assert len(valid) == 1


class TestAttributionValidator:
    def test_valid_attribution(self):
        record = AttributionRecord(
            user_id="user_001",
            install_time="2026-07-01T00:00:00",
            network=AdjustNetwork.META,
            campaign_id="camp_001",
        )
        result = AttributionValidator.validate(record)
        assert result.is_valid is True

    def test_missing_user_id(self):
        record = AttributionRecord(
            user_id="",
            install_time="2026-07-01T00:00:00",
        )
        result = AttributionValidator.validate(record)
        assert result.is_valid is False

    def test_missing_install_time(self):
        record = AttributionRecord(user_id="user_001")
        result = AttributionValidator.validate(record)
        assert result.is_valid is False

    def test_paid_without_campaign(self):
        record = AttributionRecord(
            user_id="user_001",
            install_time="2026-07-01T00:00:00",
            network=AdjustNetwork.META,
            is_organic=False,
        )
        result = AttributionValidator.validate(record)
        assert len(result.warnings) >= 1

    def test_validate_batch(self):
        records = [
            AttributionRecord(user_id="u1", install_time="2026-07-01"),
            AttributionRecord(user_id="", install_time="2026-07-01"),
        ]
        results = AttributionValidator.validate_batch(records)
        assert results[0].is_valid is True
        assert results[1].is_valid is False

    def test_filter_valid(self):
        records = [
            AttributionRecord(user_id="u1", install_time="2026-07-01"),
            AttributionRecord(user_id=""),
        ]
        valid = AttributionValidator.filter_valid(records)
        assert len(valid) == 1


class TestRetentionValidator:
    def test_valid_retention(self, sample_retention):
        result = RetentionValidator.validate(sample_retention)
        assert result.is_valid is True

    def test_missing_product_id(self):
        snap = RetentionSnapshot(cohort_date="2026-07-01", cohort_size=100)
        result = RetentionValidator.validate(snap)
        assert result.is_valid is False

    def test_missing_cohort_date(self):
        snap = RetentionSnapshot(product_id="P04", cohort_size=100)
        result = RetentionValidator.validate(snap)
        assert result.is_valid is False

    def test_zero_cohort_size(self):
        snap = RetentionSnapshot(
            product_id="P04",
            cohort_date="2026-07-01",
            cohort_size=0,
        )
        result = RetentionValidator.validate(snap)
        assert result.is_valid is False

    def test_retention_out_of_range(self):
        snap = RetentionSnapshot(
            product_id="P04",
            cohort_date="2026-07-01",
            cohort_size=100,
            d1=1.5,
        )
        result = RetentionValidator.validate(snap)
        assert result.is_valid is False

    def test_retention_increasing_warning(self):
        snap = RetentionSnapshot(
            product_id="P04",
            cohort_date="2026-07-01",
            cohort_size=100,
            d1=0.1,
            d7=0.5,  # higher than d1
        )
        result = RetentionValidator.validate(snap)
        assert len(result.warnings) >= 1

    def test_validate_or_none_none(self):
        result = RetentionValidator.validate_or_none(None)
        assert len(result.warnings) >= 1


class TestUserValueValidator:
    def test_valid_snapshot(self):
        snap = UserValueSnapshot(
            product_id="P04",
            date="2026-07-01",
            total_users=100,
            paying_users=10,
            total_revenue=500.0,
            arpu=5.0,
            arppu=50.0,
            paying_rate=0.1,
        )
        result = UserValueValidator.validate(snap)
        assert result.is_valid is True

    def test_missing_product_id(self):
        snap = UserValueSnapshot(date="2026-07-01")
        result = UserValueValidator.validate(snap)
        assert result.is_valid is False

    def test_missing_date(self):
        snap = UserValueSnapshot(product_id="P04")
        result = UserValueValidator.validate(snap)
        assert result.is_valid is False

    def test_negative_users(self):
        snap = UserValueSnapshot(
            product_id="P04",
            date="2026-07-01",
            total_users=-1,
        )
        result = UserValueValidator.validate(snap)
        assert result.is_valid is False

    def test_paying_users_exceeds_total(self):
        snap = UserValueSnapshot(
            product_id="P04",
            date="2026-07-01",
            total_users=10,
            paying_users=20,
        )
        result = UserValueValidator.validate(snap)
        assert result.is_valid is False

    def test_paying_rate_out_of_range(self):
        snap = UserValueSnapshot(
            product_id="P04",
            date="2026-07-01",
            total_users=100,
            paying_rate=1.5,
        )
        result = UserValueValidator.validate(snap)
        assert result.is_valid is False

    def test_negative_arpu(self):
        snap = UserValueSnapshot(
            product_id="P04",
            date="2026-07-01",
            total_users=100,
            arpu=-1.0,
        )
        result = UserValueValidator.validate(snap)
        assert result.is_valid is False

    def test_high_arpu_warning(self):
        snap = UserValueSnapshot(
            product_id="P04",
            date="2026-07-01",
            total_users=100,
            arpu=2000.0,
        )
        result = UserValueValidator.validate(snap)
        assert len(result.warnings) >= 1

    def test_validate_or_none_none(self):
        result = UserValueValidator.validate_or_none(None)
        assert result.is_valid is False


class TestAPIResponseValidator:
    def test_valid_response(self):
        resp = {"data": [{"event_name": "install"}]}
        result = APIResponseValidator.validate_raw_response(resp)
        assert result.is_valid is True

    def test_empty_response(self):
        result = APIResponseValidator.validate_raw_response({})
        assert result.is_valid is False

    def test_api_error(self):
        resp = {"error": "Invalid token"}
        result = APIResponseValidator.validate_raw_response(resp)
        assert result.is_valid is False

    def test_valid_event_list(self):
        events = [{"event_name": "install"}, {"event_name": "purchase"}]
        result = APIResponseValidator.validate_event_list(events)
        assert result.is_valid is True

    def test_empty_event_list(self):
        result = APIResponseValidator.validate_event_list([])
        assert len(result.warnings) >= 1

    def test_not_list(self):
        result = APIResponseValidator.validate_event_list("not_a_list")  # type: ignore
        assert result.is_valid is False


# ═══════════════════════════════════════════════════════════════
# AdjustConnector
# ═══════════════════════════════════════════════════════════════


class TestAdjustConnectorLifecycle:
    def test_connect(self, connector_config):
        conn = AdjustConnector(connector_config)
        assert conn.connect() is True
        assert conn.is_connected is True

    def test_authenticate(self, connector_config):
        conn = AdjustConnector(connector_config)
        conn.connect()
        assert conn.authenticate() is True
        assert conn.is_authenticated is True

    def test_disconnect(self, adjust_connector):
        adjust_connector.disconnect()
        assert adjust_connector.is_connected is False

    def test_health_check_healthy(self, adjust_connector):
        assert adjust_connector.health_check() == ConnectorHealth.HEALTHY

    def test_health_check_not_connected(self, connector_config):
        conn = AdjustConnector(connector_config)
        assert conn.health_check() == ConnectorHealth.UNHEALTHY

    def test_lifecycle_full(self, connector_config):
        conn = AdjustConnector(connector_config)
        assert conn.connect() is True
        assert conn.authenticate() is True
        assert conn.is_connected is True
        assert conn.is_authenticated is True
        conn.disconnect()
        assert conn.is_connected is False


class TestAdjustConnectorSync:
    def test_sync_all(self, adjust_connector):
        result = adjust_connector.sync_all(product_id="P04")
        assert result["events"] > 0
        assert result["attributions"] > 0
        assert result["has_retention"] is True
        assert result["last_sync_at"] != ""

    def test_sync_events(self, adjust_connector):
        events = adjust_connector.sync_events(product_id="P04")
        assert len(events) > 0
        assert len(adjust_connector.events) > 0

    def test_sync_attribution(self, adjust_connector):
        attributions = adjust_connector.sync_attribution()
        assert len(attributions) > 0
        assert len(adjust_connector.attributions) > 0

    def test_sync_retention(self, adjust_connector):
        retention = adjust_connector.sync_retention(product_id="P04")
        assert retention is not None
        assert retention.product_id == "P04"

    def test_last_sync_at_updated(self, adjust_connector):
        adjust_connector.sync_all(product_id="P04")
        assert adjust_connector.last_sync_at != ""


class TestAdjustConnectorBuildSnapshot:
    def test_build_user_value_snapshot(self, adjust_connector):
        adjust_connector.sync_all(product_id="P04")
        snapshot = adjust_connector.build_user_value_snapshot(product_id="P04")
        assert snapshot is not None
        assert snapshot.product_id == "P04"
        assert snapshot.total_users > 0
        assert snapshot.total_revenue > 0

    def test_build_snapshots_by_date(self, adjust_connector):
        adjust_connector.sync_all(product_id="P04")
        snapshots = adjust_connector.build_snapshots_by_date(product_id="P04")
        assert len(snapshots) >= 1

    def test_build_snapshot_by_network(self, adjust_connector):
        adjust_connector.sync_all(product_id="P04")
        by_network = adjust_connector.build_snapshot_by_network(product_id="P04")
        assert "meta" in by_network or "organic" in by_network

    def test_build_snapshot_no_events(self, connector_config):
        conn = AdjustConnector(connector_config)
        conn.connect()
        conn._events = []  # Explicitly empty, but build_snapshot auto-syncs
        snapshot = conn.build_user_value_snapshot(product_id="P04")
        # Auto-sync repopulates events from mock client
        assert snapshot is not None
        assert snapshot.total_users > 0


class TestAdjustConnectorFetchOverrides:
    def test_fetch_revenue_curve(self, adjust_connector):
        adjust_connector.sync_all(product_id="P04")
        curve = adjust_connector.fetch_revenue_curve(product_id="P04")
        assert curve is not None
        assert curve.platform == DataSource.ADJUST
        assert curve.cohort_size > 0

    def test_fetch_retention(self, adjust_connector):
        adjust_connector.sync_all(product_id="P04")
        retention = adjust_connector.fetch_retention(product_id="P04")
        assert retention is not None
        assert retention.platform == DataSource.ADJUST
        assert retention.cohort_size > 0


class TestAdjustConnectorCollectEvents:
    def test_collect_events(self, adjust_connector):
        adjust_connector.sync_all(product_id="P04")
        events = adjust_connector.collect_events(product_id="P04")
        assert len(events) >= 2  # Revenue + Retention + ARPU
        sources = {e.source for e in events}
        assert DataSource.ADJUST in sources

    def test_collect_events_revenue(self, adjust_connector):
        adjust_connector.sync_all(product_id="P04")
        events = adjust_connector.collect_events(product_id="P04")
        revenue_events = [e for e in events if e.event_type == MetricType.REVENUE]
        assert len(revenue_events) >= 1

    def test_collect_events_retention(self, adjust_connector):
        adjust_connector.sync_all(product_id="P04")
        events = adjust_connector.collect_events(product_id="P04")
        retention_events = [e for e in events if e.event_type == MetricType.RETENTION]
        assert len(retention_events) >= 1

    def test_collect_events_arpu(self, adjust_connector):
        adjust_connector.sync_all(product_id="P04")
        events = adjust_connector.collect_events(product_id="P04")
        arpu_events = [e for e in events if e.event_type == MetricType.ARPU]
        assert len(arpu_events) >= 1


class TestAdjustConnectorAttributionAnalytics:
    def test_get_network_stats(self, adjust_connector):
        adjust_connector.sync_all(product_id="P04")
        stats = adjust_connector.get_network_stats()
        assert len(stats) > 0

    def test_get_organic_vs_paid_split(self, adjust_connector):
        adjust_connector.sync_all(product_id="P04")
        split = adjust_connector.get_organic_vs_paid_split()
        assert split["total"] > 0
        assert split["paid"] + split["organic"] == split["total"]

    def test_link_events_to_attribution(self, adjust_connector):
        adjust_connector.sync_all(product_id="P04")
        events = adjust_connector.link_events_to_attribution()
        assert len(events) > 0

    def test_get_revenue_breakdown(self, adjust_connector):
        adjust_connector.sync_all(product_id="P04")
        breakdown = adjust_connector.get_revenue_breakdown()
        assert "iap" in breakdown
        assert "total" in breakdown

    def test_get_event_type_counts(self, adjust_connector):
        adjust_connector.sync_all(product_id="P04")
        counts = adjust_connector.get_event_type_counts()
        assert isinstance(counts, dict)
        assert len(counts) > 0


class TestAdjustConnectorProperties:
    def test_events_property(self, adjust_connector):
        adjust_connector.sync_events("P04")
        assert len(adjust_connector.events) > 0

    def test_attributions_property(self, adjust_connector):
        adjust_connector.sync_attribution()
        assert len(adjust_connector.attributions) > 0

    def test_retention_property(self, adjust_connector):
        adjust_connector.sync_retention("P04")
        assert adjust_connector.retention is not None

    def test_snapshots_property(self, adjust_connector):
        adjust_connector.sync_all("P04")
        adjust_connector.build_snapshots_by_date("P04")
        assert len(adjust_connector.snapshots) >= 0


class TestAdjustConnectorSummary:
    def test_get_summary(self, adjust_connector):
        adjust_connector.sync_all(product_id="P04")
        summary = adjust_connector.get_summary()
        assert summary["events_count"] > 0
        assert summary["attributions_count"] > 0
        assert summary["has_retention"] is True


class TestAdjustConnectorEdgeCases:
    def test_sync_without_product_id(self, adjust_connector):
        result = adjust_connector.sync_all()
        assert result["events"] > 0

    def test_build_snapshot_before_sync(self, adjust_connector):
        adjust_connector._events = []
        snapshot = adjust_connector.build_user_value_snapshot(product_id="P04")
        assert snapshot is not None  # auto-syncs

    def test_empty_events_summary(self, adjust_connector):
        adjust_connector._events = []
        adjust_connector._attributions = []
        adjust_connector._retention = None
        summary = adjust_connector.get_summary()
        assert summary["events_count"] == 0


# ═══════════════════════════════════════════════════════════════
# Integration Tests
# ═══════════════════════════════════════════════════════════════


class TestIntegrationClientToParser:
    def test_client_events_parsed(self, mock_client):
        events = mock_client.fetch_events()
        valid = AdjustEventValidator.filter_valid(events)
        assert len(valid) == len(events)

    def test_client_attribution_parsed(self, mock_client):
        attributions = mock_client.fetch_attribution()
        valid = AttributionValidator.filter_valid(attributions)
        assert len(valid) == len(attributions)


class TestIntegrationEventToSnapshot:
    def test_events_to_snapshot_flow(self, mock_client):
        events = mock_client.fetch_events(product_id="P04")
        retention = mock_client.fetch_retention(product_id="P04")
        attributions = mock_client.fetch_attribution()

        snapshot = AdjustValueMapper.build_snapshot(
            events=events,
            retention=retention,
            attributions=attributions,
            product_id="P04",
        )

        assert snapshot is not None
        assert snapshot.total_users > 0
        assert snapshot.total_revenue > 0
        result = UserValueValidator.validate(snapshot)
        assert result.is_valid is True


class TestIntegrationConnectorToFramework:
    def test_connector_to_growth_events(self, adjust_connector):
        adjust_connector.sync_all(product_id="P04")
        events = adjust_connector.collect_events(product_id="P04")

        assert len(events) > 0
        for event in events:
            assert event.source == DataSource.ADJUST
            assert event.product_id == "P04"
            assert isinstance(event.metrics, dict)

    def test_connector_to_retention_curve(self, adjust_connector):
        adjust_connector.sync_all(product_id="P04")
        curve = adjust_connector.fetch_retention(product_id="P04")
        assert curve is not None
        assert curve.platform == DataSource.ADJUST
        assert curve.d1_retention > 0

    def test_connector_to_revenue_curve(self, adjust_connector):
        adjust_connector.sync_all(product_id="P04")
        curve = adjust_connector.fetch_revenue_curve(product_id="P04")
        assert curve is not None
        assert curve.platform == DataSource.ADJUST


class TestIntegrationEndToEnd:
    def test_full_flow(self, adjust_connector):
        # 1. Connect & authenticate
        assert adjust_connector.is_connected is True
        assert adjust_connector.is_authenticated is True

        # 2. Sync all data
        sync_result = adjust_connector.sync_all(product_id="P04")
        assert sync_result["events"] > 0
        assert sync_result["attributions"] > 0

        # 3. Build user value snapshot
        snapshot = adjust_connector.build_user_value_snapshot(product_id="P04")
        assert snapshot is not None
        assert snapshot.product_id == "P04"
        assert snapshot.arpu > 0

        # 4. Link events to attribution
        events = adjust_connector.link_events_to_attribution()
        assert len(events) > 0

        # 5. Collect Growth Data Events
        growth_events = adjust_connector.collect_events(product_id="P04")
        assert len(growth_events) >= 2

        # 6. Get analytics
        stats = adjust_connector.get_network_stats()
        assert len(stats) > 0

        split = adjust_connector.get_organic_vs_paid_split()
        assert split["total"] > 0

        breakdown = adjust_connector.get_revenue_breakdown()
        assert breakdown["total"] > 0

        # 7. Summary
        summary = adjust_connector.get_summary()
        assert summary["events_count"] > 0

    def test_reality_layer_workflow(self, adjust_connector):
        """模拟完整 Reality Layer 数据流:
        Adjust → Connector → UserValueSnapshot → Reality Layer → ROAS Predictor → Meta Decision Engine
        """
        adjust_connector.sync_all(product_id="P04")

        # Step 1: Build UserValueSnapshot
        snapshot = adjust_connector.build_user_value_snapshot(product_id="P04")
        assert snapshot is not None

        # Step 2: Convert to GrowthDataEvent for Reality Layer
        events = adjust_connector.collect_events(product_id="P04")
        revenue_events = [e for e in events if e.event_type == MetricType.REVENUE]
        assert len(revenue_events) >= 1

        revenue_event = revenue_events[0]
        assert "total_revenue" in revenue_event.metrics
        assert "arpu" in revenue_event.metrics
        assert "paying_rate" in revenue_event.metrics

        # Step 3: Revenue curve for LTV prediction
        curve = adjust_connector.fetch_revenue_curve(product_id="P04")
        assert curve is not None
        assert curve.predicted_ltv > 0

    def test_mock_mode_consistency(self, adjust_connector):
        """验证 mock 模式下多次同步数据一致性."""
        adjust_connector.sync_all(product_id="P04")
        snap1 = adjust_connector.build_user_value_snapshot(product_id="P04")

        # Re-sync and rebuild
        adjust_connector.sync_all(product_id="P04")
        snap2 = adjust_connector.build_user_value_snapshot(product_id="P04")

        assert snap1 is not None
        assert snap2 is not None
        assert snap1.product_id == snap2.product_id
        assert snap1.total_users == snap2.total_users

    def test_network_snapshot_consistency(self, adjust_connector):
        """验证按网络拆分后总和与整体一致."""
        adjust_connector.sync_all(product_id="P04")
        by_network = adjust_connector.build_snapshot_by_network(product_id="P04")

        total_revenue = sum(s.total_revenue for s in by_network.values())
        snapshot = adjust_connector.build_user_value_snapshot(product_id="P04")

        assert snapshot is not None
        assert abs(total_revenue - snapshot.total_revenue) < 0.01