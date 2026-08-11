"""E13.1.1 — Growth Data Connector Framework Test Suite。

覆盖:
  - TestDataSource:            数据源枚举测试 (6)
  - TestMetricType:            指标类型枚举测试 (5)
  - TestDataGranularity:       粒度枚举测试 (3)
  - TestConnectorStatus:       连接器状态枚举测试 (3)
  - TestConnectorHealth:       健康状态枚举测试 (3)
  - TestCampaignMetrics:       广告系列指标测试 (14)
  - TestAdSetMetrics:          广告组指标测试 (5)
  - TestCreativeMetrics:       创意指标测试 (8)
  - TestUserRevenueCurve:      收入曲线测试 (6)
  - TestRetentionCurve:        留存曲线测试 (5)
  - TestGameplayMetrics:       游戏指标测试 (4)
  - TestGrowthDataEvent:       统一事件测试 (10)
  - TestConnectorConfig:       连接器配置测试 (6)
  - TestConnectorInfo:         连接器信息测试 (7)
  - TestBaseConnector:         抽象基类测试 (35)
  - TestConnectorRegistry:     注册表测试 (30)

总计: 150 tests
"""

from __future__ import annotations

import time
from typing import Any

import pytest

from market_ops.creative_vision_runtime.growth_runtime.connectors import (
    AdSetMetrics,
    BaseConnector,
    CampaignMetrics,
    ConnectorConfig,
    ConnectorHealth,
    ConnectorInfo,
    ConnectorRegistry,
    ConnectorStatus,
    CreativeMetrics,
    DataGranularity,
    DataSource,
    GameplayMetrics,
    GrowthDataEvent,
    MetricType,
    RetentionCurve,
    UserRevenueCurve,
)


# ═══════════════════════════════════════════════════════════════
# Test Enums
# ═══════════════════════════════════════════════════════════════


class TestDataSource:
    """数据源枚举测试。"""

    def test_all_sources_defined(self):
        assert len(DataSource) == 13

    def test_source_values(self):
        assert DataSource.META_ADS.value == "meta_ads"
        assert DataSource.GOOGLE_ADS.value == "google_ads"
        assert DataSource.ASA.value == "asa"
        assert DataSource.ADJUST.value == "adjust"
        assert DataSource.FIREBASE.value == "firebase"
        assert DataSource.APP_STORE.value == "app_store"

    def test_source_from_string(self):
        assert DataSource("meta_ads") == DataSource.META_ADS
        assert DataSource("adjust") == DataSource.ADJUST
        assert DataSource("firebase") == DataSource.FIREBASE

    def test_source_equality(self):
        assert DataSource.META_ADS == DataSource.META_ADS
        assert DataSource.META_ADS != DataSource.GOOGLE_ADS

    def test_source_in_set(self):
        ad_sources = {DataSource.META_ADS, DataSource.GOOGLE_ADS, DataSource.ASA}
        assert DataSource.META_ADS in ad_sources
        assert DataSource.ADJUST not in ad_sources

    def test_source_is_string_compatible(self):
        assert isinstance(DataSource.META_ADS.value, str)


class TestMetricType:
    """指标类型枚举测试。"""

    def test_all_metrics_defined(self):
        assert len(MetricType) == 19

    def test_key_metric_values(self):
        assert MetricType.SPEND.value == "spend"
        assert MetricType.REVENUE.value == "revenue"
        assert MetricType.ROAS.value == "roas"
        assert MetricType.RETENTION.value == "retention"
        assert MetricType.LTV.value == "ltv"

    def test_metric_from_string(self):
        assert MetricType("spend") == MetricType.SPEND
        assert MetricType("ltv") == MetricType.LTV
        assert MetricType("payer_rate") == MetricType.PAYER_RATE

    def test_metric_type_is_str_enum(self):
        assert issubclass(MetricType, str)

    def test_comparison_works(self):
        meta = MetricType.SPEND
        assert meta == MetricType.SPEND
        assert meta != MetricType.REVENUE


class TestDataGranularity:
    """粒度枚举测试。"""

    def test_all_granularities(self):
        assert len(DataGranularity) == 5

    def test_granularity_values(self):
        assert DataGranularity.HOURLY.value == "hourly"
        assert DataGranularity.DAILY.value == "daily"
        assert DataGranularity.WEEKLY.value == "weekly"
        assert DataGranularity.MONTHLY.value == "monthly"
        assert DataGranularity.LIFETIME.value == "lifetime"


class TestConnectorStatus:
    """连接器状态枚举测试。"""

    def test_all_statuses(self):
        assert len(ConnectorStatus) == 7

    def test_initial_status(self):
        assert ConnectorStatus.UNINITIALIZED.value == "uninitialized"

    def test_operational_statuses(self):
        ops = {ConnectorStatus.CONNECTED, ConnectorStatus.INITIALIZING}
        assert ConnectorStatus.CONNECTED in ops


class TestConnectorHealth:
    """健康状态枚举测试。"""

    def test_all_health_states(self):
        assert len(ConnectorHealth) == 4

    def test_health_values(self):
        assert ConnectorHealth.HEALTHY.value == "healthy"
        assert ConnectorHealth.DEGRADED.value == "degraded"
        assert ConnectorHealth.UNHEALTHY.value == "unhealthy"
        assert ConnectorHealth.UNKNOWN.value == "unknown"


# ═══════════════════════════════════════════════════════════════
# Test CampaignMetrics
# ═══════════════════════════════════════════════════════════════


class TestCampaignMetrics:
    """广告系列指标测试。"""

    def test_default_creation(self):
        cm = CampaignMetrics()
        assert cm.campaign_id == ""
        assert cm.campaign_name == ""
        assert cm.platform == DataSource.META_ADS
        assert cm.spend == 0.0
        assert cm.revenue == 0.0
        assert cm.fetched_at != ""

    def test_full_creation(self):
        cm = CampaignMetrics(
            campaign_id="c_001",
            campaign_name="Test Campaign",
            platform=DataSource.GOOGLE_ADS,
            product_id="p04",
            spend=500.0,
            revenue=750.0,
            roas=1.5,
            impressions=10000,
            clicks=500,
            ctr=0.05,
            cpm=50.0,
            cpc=1.0,
            installs=200,
            cpi=2.5,
            cpa=3.0,
            date="2026-07-24",
        )
        assert cm.campaign_id == "c_001"
        assert cm.campaign_name == "Test Campaign"
        assert cm.platform == DataSource.GOOGLE_ADS
        assert cm.product_id == "p04"
        assert cm.spend == 500.0
        assert cm.revenue == 750.0
        assert cm.roas == 1.5
        assert cm.impressions == 10000
        assert cm.clicks == 500
        assert cm.ctr == 0.05
        assert cm.cpm == 50.0
        assert cm.cpc == 1.0
        assert cm.installs == 200
        assert cm.cpi == 2.5
        assert cm.cpa == 3.0
        assert cm.date == "2026-07-24"

    def test_is_profitable_true(self):
        cm = CampaignMetrics(roas=1.5)
        assert cm.is_profitable is True

    def test_is_profitable_false(self):
        cm = CampaignMetrics(roas=0.8)
        assert cm.is_profitable is False

    def test_is_profitable_breakeven(self):
        cm = CampaignMetrics(roas=1.0)
        assert cm.is_profitable is False  # > 1.0, not >=

    def test_engagement_rate_normal(self):
        cm = CampaignMetrics(impressions=10000, clicks=500)
        assert cm.engagement_rate == 0.05

    def test_engagement_rate_zero_impressions(self):
        cm = CampaignMetrics(impressions=0, clicks=500)
        assert cm.engagement_rate == 0.0

    def test_engagement_rate_zero_clicks(self):
        cm = CampaignMetrics(impressions=10000, clicks=0)
        assert cm.engagement_rate == 0.0

    def test_to_dict(self):
        cm = CampaignMetrics(
            campaign_id="c_001",
            campaign_name="Test",
            platform=DataSource.META_ADS,
            product_id="p04",
            spend=100.0,
            revenue=200.0,
            roas=2.0,
            impressions=5000,
            clicks=250,
            ctr=0.05,
            cpm=20.0,
            cpc=0.4,
            installs=100,
            cpi=1.0,
            cpa=1.5,
            date="2026-07-24",
        )
        d = cm.to_dict()
        assert d["campaign_id"] == "c_001"
        assert d["campaign_name"] == "Test"
        assert d["platform"] == "meta_ads"
        assert d["product_id"] == "p04"
        assert d["spend"] == 100.0
        assert d["revenue"] == 200.0
        assert d["roas"] == 2.0
        assert d["impressions"] == 5000
        assert d["clicks"] == 250
        assert d["ctr"] == 0.05
        assert d["cpm"] == 20.0
        assert d["cpc"] == 0.4
        assert d["installs"] == 100
        assert d["cpi"] == 1.0
        assert d["cpa"] == 1.5
        assert d["date"] == "2026-07-24"
        assert d["granularity"] == "daily"
        assert "fetched_at" in d

    def test_to_dict_rounds_floats(self):
        cm = CampaignMetrics(spend=100.123456, roas=1.56789)
        d = cm.to_dict()
        assert d["spend"] == 100.1235
        assert d["roas"] == 1.5679

    def test_default_granularity(self):
        cm = CampaignMetrics()
        assert cm.granularity == DataGranularity.DAILY

    def test_custom_granularity(self):
        cm = CampaignMetrics(granularity=DataGranularity.HOURLY)
        assert cm.granularity == DataGranularity.HOURLY

    def test_mutable_dataclass(self):
        cm = CampaignMetrics(campaign_id="c_001")
        cm.campaign_id = "c_002"
        assert cm.campaign_id == "c_002"


# ═══════════════════════════════════════════════════════════════
# Test AdSetMetrics
# ═══════════════════════════════════════════════════════════════


class TestAdSetMetrics:
    """广告组指标测试。"""

    def test_default_creation(self):
        am = AdSetMetrics()
        assert am.adset_id == ""
        assert am.adset_name == ""
        assert am.campaign_id == ""
        assert am.platform == DataSource.META_ADS

    def test_full_creation(self):
        am = AdSetMetrics(
            adset_id="as_001",
            adset_name="Test AdSet",
            campaign_id="c_001",
            platform=DataSource.GOOGLE_ADS,
            product_id="p04",
            spend=200.0,
            revenue=300.0,
            roas=1.5,
            impressions=5000,
            clicks=200,
            ctr=0.04,
            installs=80,
            cpi=2.5,
            date="2026-07-24",
        )
        assert am.adset_id == "as_001"
        assert am.adset_name == "Test AdSet"
        assert am.campaign_id == "c_001"
        assert am.platform == DataSource.GOOGLE_ADS
        assert am.product_id == "p04"
        assert am.spend == 200.0
        assert am.revenue == 300.0
        assert am.roas == 1.5
        assert am.impressions == 5000
        assert am.clicks == 200
        assert am.ctr == 0.04
        assert am.installs == 80
        assert am.cpi == 2.5
        assert am.date == "2026-07-24"

    def test_to_dict(self):
        am = AdSetMetrics(
            adset_id="as_001",
            adset_name="Test",
            campaign_id="c_001",
            platform=DataSource.META_ADS,
            product_id="p04",
            spend=100.0,
            revenue=150.0,
            roas=1.5,
            impressions=3000,
            clicks=150,
            ctr=0.05,
            installs=60,
            cpi=1.67,
            date="2026-07-24",
        )
        d = am.to_dict()
        assert d["adset_id"] == "as_001"
        assert d["adset_name"] == "Test"
        assert d["campaign_id"] == "c_001"
        assert d["platform"] == "meta_ads"
        assert d["spend"] == 100.0
        assert d["revenue"] == 150.0
        assert d["roas"] == 1.5
        assert d["installs"] == 60
        assert d["cpi"] == 1.67
        assert "fetched_at" in d

    def test_fetched_at_auto_generated(self):
        am = AdSetMetrics()
        assert am.fetched_at != ""

    def test_two_instances_different_fetched_at(self):
        am1 = AdSetMetrics()
        time.sleep(0.01)
        am2 = AdSetMetrics()
        assert am1.fetched_at != am2.fetched_at


# ═══════════════════════════════════════════════════════════════
# Test CreativeMetrics
# ═══════════════════════════════════════════════════════════════


class TestCreativeMetrics:
    """创意指标测试。"""

    def test_default_creation(self):
        cm = CreativeMetrics()
        assert cm.creative_id == ""
        assert cm.creative_name == ""
        assert cm.frequency == 0.0
        assert cm.ctr_trend == 0.0

    def test_full_creation(self):
        cm = CreativeMetrics(
            creative_id="cr_001",
            creative_name="Test Creative",
            adset_id="as_001",
            campaign_id="c_001",
            platform=DataSource.META_ADS,
            product_id="p04",
            spend=100.0,
            impressions=5000,
            clicks=200,
            ctr=0.04,
            installs=50,
            revenue=200.0,
            roas=2.0,
            frequency=3.5,
            ctr_trend=-0.25,
            date="2026-07-24",
        )
        assert cm.creative_id == "cr_001"
        assert cm.creative_name == "Test Creative"
        assert cm.adset_id == "as_001"
        assert cm.campaign_id == "c_001"
        assert cm.platform == DataSource.META_ADS
        assert cm.product_id == "p04"
        assert cm.spend == 100.0
        assert cm.impressions == 5000
        assert cm.clicks == 200
        assert cm.ctr == 0.04
        assert cm.installs == 50
        assert cm.revenue == 200.0
        assert cm.roas == 2.0
        assert cm.frequency == 3.5
        assert cm.ctr_trend == -0.25
        assert cm.date == "2026-07-24"

    def test_is_fatigued_true(self):
        cm = CreativeMetrics(frequency=3.5, ctr_trend=-0.25)
        assert cm.is_fatigued() is True

    def test_is_fatigued_false_low_frequency(self):
        cm = CreativeMetrics(frequency=2.0, ctr_trend=-0.25)
        assert cm.is_fatigued() is False

    def test_is_fatigued_false_high_ctr(self):
        cm = CreativeMetrics(frequency=3.5, ctr_trend=-0.10)
        assert cm.is_fatigued() is False

    def test_is_fatigued_custom_thresholds(self):
        cm = CreativeMetrics(frequency=2.5, ctr_trend=-0.15)
        assert cm.is_fatigued(freq_threshold=2.0, ctr_drop_threshold=-0.10) is True

    def test_to_dict(self):
        cm = CreativeMetrics(
            creative_id="cr_001",
            creative_name="Test",
            platform=DataSource.META_ADS,
            spend=100.0,
            impressions=5000,
            clicks=200,
            ctr=0.04,
            installs=50,
            revenue=200.0,
            roas=2.0,
            frequency=3.5,
            ctr_trend=-0.25,
            date="2026-07-24",
        )
        d = cm.to_dict()
        assert d["creative_id"] == "cr_001"
        assert d["creative_name"] == "Test"
        assert d["platform"] == "meta_ads"
        assert d["spend"] == 100.0
        assert d["impressions"] == 5000
        assert d["clicks"] == 200
        assert d["ctr"] == 0.04
        assert d["installs"] == 50
        assert d["revenue"] == 200.0
        assert d["roas"] == 2.0
        assert d["frequency"] == 3.5
        assert d["ctr_trend"] == -0.25
        assert d["date"] == "2026-07-24"
        assert "fetched_at" in d

    def test_roas_field(self):
        cm = CreativeMetrics(revenue=200.0, spend=100.0, roas=2.0)
        assert cm.roas == 2.0


# ═══════════════════════════════════════════════════════════════
# Test UserRevenueCurve
# ═══════════════════════════════════════════════════════════════


class TestUserRevenueCurve:
    """用户收入曲线测试。"""

    def test_default_creation(self):
        urc = UserRevenueCurve()
        assert urc.product_id == ""
        assert urc.platform == DataSource.ADJUST
        assert urc.cohort_date == ""
        assert urc.d0_revenue == 0.0
        assert urc.d365_revenue == 0.0
        assert urc.predicted_ltv == 0.0
        assert urc.ltv_confidence == 0.0
        assert urc.cohort_size == 0

    def test_full_creation(self):
        urc = UserRevenueCurve(
            product_id="p04",
            platform=DataSource.ADJUST,
            cohort_date="2026-01-01",
            d0_revenue=0.5,
            d1_revenue=0.3,
            d7_revenue=1.2,
            d30_revenue=3.5,
            d60_revenue=5.0,
            d90_revenue=6.0,
            d120_revenue=7.0,
            d180_revenue=8.0,
            d365_revenue=10.0,
            predicted_ltv=12.0,
            ltv_confidence=0.85,
            cohort_size=5000,
        )
        assert urc.product_id == "p04"
        assert urc.d0_revenue == 0.5
        assert urc.d1_revenue == 0.3
        assert urc.d7_revenue == 1.2
        assert urc.d30_revenue == 3.5
        assert urc.d60_revenue == 5.0
        assert urc.d90_revenue == 6.0
        assert urc.d120_revenue == 7.0
        assert urc.d180_revenue == 8.0
        assert urc.d365_revenue == 10.0
        assert urc.predicted_ltv == 12.0
        assert urc.ltv_confidence == 0.85
        assert urc.cohort_size == 5000

    def test_total_realized_revenue(self):
        urc = UserRevenueCurve(
            d0_revenue=0.5,
            d1_revenue=0.3,
            d7_revenue=1.2,
            d30_revenue=3.5,
            d60_revenue=5.0,
            d90_revenue=6.0,
            d120_revenue=7.0,
            d180_revenue=8.0,
            d365_revenue=10.0,
        )
        expected = 0.5 + 0.3 + 1.2 + 3.5 + 5.0 + 6.0 + 7.0 + 8.0 + 10.0
        assert urc.total_realized_revenue == expected

    def test_to_dict(self):
        urc = UserRevenueCurve(
            product_id="p04",
            cohort_date="2026-01-01",
            d7_revenue=1.2,
            d30_revenue=3.5,
            predicted_ltv=12.0,
            ltv_confidence=0.85,
            cohort_size=5000,
        )
        d = urc.to_dict()
        assert d["product_id"] == "p04"
        assert d["platform"] == "adjust"
        assert d["cohort_date"] == "2026-01-01"
        assert d["d7_revenue"] == 1.2
        assert d["d30_revenue"] == 3.5
        assert d["predicted_ltv"] == 12.0
        assert d["ltv_confidence"] == 0.85
        assert d["cohort_size"] == 5000
        assert "fetched_at" in d

    def test_to_dict_rounds_revenue(self):
        urc = UserRevenueCurve(d0_revenue=0.12345678)
        d = urc.to_dict()
        assert d["d0_revenue"] == 0.123457

    def test_default_platform_adjust(self):
        urc = UserRevenueCurve()
        assert urc.platform == DataSource.ADJUST


# ═══════════════════════════════════════════════════════════════
# Test RetentionCurve
# ═══════════════════════════════════════════════════════════════


class TestRetentionCurve:
    """留存曲线测试。"""

    def test_default_creation(self):
        rc = RetentionCurve()
        assert rc.product_id == ""
        assert rc.platform == DataSource.ADJUST
        assert rc.d1_retention == 0.0
        assert rc.d7_retention == 0.0
        assert rc.d30_retention == 0.0
        assert rc.payer_rate == 0.0
        assert rc.cohort_size == 0

    def test_full_creation(self):
        rc = RetentionCurve(
            product_id="p04",
            platform=DataSource.APPSFLYER,
            cohort_date="2026-01-01",
            d1_retention=0.45,
            d3_retention=0.35,
            d7_retention=0.25,
            d14_retention=0.18,
            d30_retention=0.12,
            d60_retention=0.08,
            d90_retention=0.05,
            payer_rate=0.03,
            cohort_size=5000,
        )
        assert rc.product_id == "p04"
        assert rc.platform == DataSource.APPSFLYER
        assert rc.d1_retention == 0.45
        assert rc.d3_retention == 0.35
        assert rc.d7_retention == 0.25
        assert rc.d14_retention == 0.18
        assert rc.d30_retention == 0.12
        assert rc.d60_retention == 0.08
        assert rc.d90_retention == 0.05
        assert rc.payer_rate == 0.03
        assert rc.cohort_size == 5000

    def test_to_dict(self):
        rc = RetentionCurve(
            product_id="p04",
            cohort_date="2026-01-01",
            d1_retention=0.45,
            d7_retention=0.25,
            d30_retention=0.12,
            payer_rate=0.03,
            cohort_size=5000,
        )
        d = rc.to_dict()
        assert d["product_id"] == "p04"
        assert d["platform"] == "adjust"
        assert d["cohort_date"] == "2026-01-01"
        assert d["d1_retention"] == 0.45
        assert d["d7_retention"] == 0.25
        assert d["d30_retention"] == 0.12
        assert d["payer_rate"] == 0.03
        assert d["cohort_size"] == 5000
        assert "fetched_at" in d

    def test_to_dict_rounds(self):
        rc = RetentionCurve(d1_retention=0.123456)
        d = rc.to_dict()
        assert d["d1_retention"] == 0.1235

    def test_all_retention_phases(self):
        rc = RetentionCurve(
            d1_retention=0.45,
            d3_retention=0.35,
            d7_retention=0.25,
            d14_retention=0.18,
            d30_retention=0.12,
            d60_retention=0.08,
            d90_retention=0.05,
        )
        assert rc.d1_retention > rc.d3_retention > rc.d7_retention
        assert rc.d7_retention > rc.d30_retention > rc.d90_retention


# ═══════════════════════════════════════════════════════════════
# Test GameplayMetrics
# ═══════════════════════════════════════════════════════════════


class TestGameplayMetrics:
    """游戏内指标测试。"""

    def test_default_creation(self):
        gm = GameplayMetrics()
        assert gm.product_id == ""
        assert gm.platform == DataSource.FIREBASE
        assert gm.dau == 0
        assert gm.mau == 0
        assert gm.sessions == 0
        assert gm.avg_session_duration == 0.0
        assert gm.sessions_per_user == 0.0
        assert gm.tutorial_completion_rate == 0.0

    def test_full_creation(self):
        gm = GameplayMetrics(
            product_id="p04",
            platform=DataSource.FIREBASE,
            dau=5000,
            mau=50000,
            sessions=15000,
            avg_session_duration=300.5,
            sessions_per_user=3.0,
            tutorial_completion_rate=0.85,
            level1_completion=0.75,
            level5_completion=0.40,
            level10_completion=0.15,
            key_events=500,
            date="2026-07-24",
        )
        assert gm.product_id == "p04"
        assert gm.platform == DataSource.FIREBASE
        assert gm.dau == 5000
        assert gm.mau == 50000
        assert gm.sessions == 15000
        assert gm.avg_session_duration == 300.5
        assert gm.sessions_per_user == 3.0
        assert gm.tutorial_completion_rate == 0.85
        assert gm.level1_completion == 0.75
        assert gm.level5_completion == 0.40
        assert gm.level10_completion == 0.15
        assert gm.key_events == 500
        assert gm.date == "2026-07-24"

    def test_to_dict(self):
        gm = GameplayMetrics(
            product_id="p04",
            dau=5000,
            mau=50000,
            sessions=15000,
            avg_session_duration=300.0,
            sessions_per_user=3.0,
            tutorial_completion_rate=0.85,
            date="2026-07-24",
        )
        d = gm.to_dict()
        assert d["product_id"] == "p04"
        assert d["platform"] == "firebase"
        assert d["dau"] == 5000
        assert d["mau"] == 50000
        assert d["sessions"] == 15000
        assert d["avg_session_duration"] == 300.0
        assert d["sessions_per_user"] == 3.0
        assert d["tutorial_completion_rate"] == 0.85
        assert d["date"] == "2026-07-24"
        assert "fetched_at" in d

    def test_default_firebase_platform(self):
        gm = GameplayMetrics()
        assert gm.platform == DataSource.FIREBASE


# ═══════════════════════════════════════════════════════════════
# Test GrowthDataEvent
# ═══════════════════════════════════════════════════════════════


class TestGrowthDataEvent:
    """统一增长数据事件测试。"""

    def test_default_creation(self):
        event = GrowthDataEvent()
        assert event.event_id != ""
        assert event.event_type == MetricType.SPEND
        assert event.source == DataSource.META_ADS
        assert event.product_id == ""
        assert event.date == ""
        assert event.metrics == {}
        assert event.campaign_id == ""
        assert event.adset_id == ""
        assert event.creative_id == ""
        assert event.raw_data == {}
        assert event.timestamp != ""

    def test_full_creation(self):
        event = GrowthDataEvent(
            event_type=MetricType.ROAS,
            source=DataSource.ADJUST,
            product_id="p04",
            date="2026-07-24",
            metrics={"roas": 1.5, "revenue": 750.0},
            campaign_id="c_001",
            adset_id="as_001",
            creative_id="cr_001",
            raw_data={"raw_source": "adjust_api"},
        )
        assert event.event_type == MetricType.ROAS
        assert event.source == DataSource.ADJUST
        assert event.product_id == "p04"
        assert event.date == "2026-07-24"
        assert event.metrics == {"roas": 1.5, "revenue": 750.0}
        assert event.campaign_id == "c_001"
        assert event.adset_id == "as_001"
        assert event.creative_id == "cr_001"
        assert event.raw_data == {"raw_source": "adjust_api"}

    def test_event_id_is_unique(self):
        e1 = GrowthDataEvent()
        e2 = GrowthDataEvent()
        assert e1.event_id != e2.event_id

    def test_to_dict(self):
        event = GrowthDataEvent(
            event_type=MetricType.SPEND,
            source=DataSource.META_ADS,
            product_id="p04",
            date="2026-07-24",
            metrics={"spend": 500.0},
            campaign_id="c_001",
        )
        d = event.to_dict()
        assert d["event_type"] == "spend"
        assert d["source"] == "meta_ads"
        assert d["product_id"] == "p04"
        assert d["date"] == "2026-07-24"
        assert d["metrics"] == {"spend": 500.0}
        assert d["campaign_id"] == "c_001"
        assert "event_id" in d
        assert "timestamp" in d

    def test_from_campaign_metrics(self):
        cm = CampaignMetrics(
            campaign_id="c_001",
            platform=DataSource.GOOGLE_ADS,
            product_id="p04",
            spend=500.0,
            revenue=750.0,
            roas=1.5,
            impressions=10000,
            clicks=500,
            installs=200,
            date="2026-07-24",
        )
        event = GrowthDataEvent.from_campaign_metrics(cm)
        assert event.event_type == MetricType.SPEND
        assert event.source == DataSource.GOOGLE_ADS
        assert event.product_id == "p04"
        assert event.date == "2026-07-24"
        assert event.campaign_id == "c_001"
        assert event.metrics["spend"] == 500.0
        assert event.metrics["revenue"] == 750.0
        assert event.metrics["roas"] == 1.5
        assert event.metrics["impressions"] == 10000
        assert event.metrics["clicks"] == 500
        assert event.metrics["installs"] == 200

    def test_from_retention(self):
        rc = RetentionCurve(
            product_id="p04",
            platform=DataSource.ADJUST,
            cohort_date="2026-01-01",
            d1_retention=0.45,
            d7_retention=0.25,
            d30_retention=0.12,
            payer_rate=0.03,
        )
        event = GrowthDataEvent.from_retention(rc)
        assert event.event_type == MetricType.RETENTION
        assert event.source == DataSource.ADJUST
        assert event.product_id == "p04"
        assert event.date == "2026-01-01"
        assert event.metrics["d1_retention"] == 0.45
        assert event.metrics["d7_retention"] == 0.25
        assert event.metrics["d30_retention"] == 0.12
        assert event.metrics["payer_rate"] == 0.03

    def test_from_campaign_metrics_preserves_platform(self):
        cm = CampaignMetrics(platform=DataSource.ASA)
        event = GrowthDataEvent.from_campaign_metrics(cm)
        assert event.source == DataSource.ASA

    def test_from_retention_preserves_platform(self):
        rc = RetentionCurve(platform=DataSource.APPSFLYER)
        event = GrowthDataEvent.from_retention(rc)
        assert event.source == DataSource.APPSFLYER

    def test_event_metrics_dict_is_mutable(self):
        event = GrowthDataEvent(metrics={"spend": 100.0})
        event.metrics["revenue"] = 200.0
        assert event.metrics == {"spend": 100.0, "revenue": 200.0}

    def test_raw_data_is_stored(self):
        event = GrowthDataEvent(raw_data={"api_response": {"status": "ok"}})
        assert event.raw_data == {"api_response": {"status": "ok"}}


# ═══════════════════════════════════════════════════════════════
# Test ConnectorConfig
# ═══════════════════════════════════════════════════════════════


class TestConnectorConfig:
    """连接器配置测试。"""

    def test_default_creation(self):
        config = ConnectorConfig()
        assert config.connector_type == DataSource.META_ADS
        assert config.api_version == ""
        assert config.base_url == ""
        assert config.auth_type == "oauth2"
        assert config.access_token == ""
        assert config.refresh_token == ""
        assert config.api_key == ""
        assert config.max_requests_per_minute == 60
        assert config.max_requests_per_hour == 1000
        assert config.retry_max_attempts == 3
        assert config.retry_backoff_seconds == 1.0
        assert config.connect_timeout == 10.0
        assert config.read_timeout == 30.0
        assert config.account_id == ""
        assert config.accounts == []
        assert config.lookback_days == 90
        assert config.default_granularity == DataGranularity.DAILY

    def test_full_creation(self):
        config = ConnectorConfig(
            connector_type=DataSource.GOOGLE_ADS,
            api_version="v15",
            base_url="https://googleads.googleapis.com",
            auth_type="oauth2",
            access_token="token_123",
            refresh_token="refresh_456",
            max_requests_per_minute=120,
            max_requests_per_hour=2000,
            retry_max_attempts=5,
            retry_backoff_seconds=2.0,
            connect_timeout=15.0,
            read_timeout=45.0,
            account_id="acc_001",
            accounts=["acc_001", "acc_002"],
            lookback_days=180,
            default_granularity=DataGranularity.HOURLY,
            extra={"region": "us"},
        )
        assert config.connector_type == DataSource.GOOGLE_ADS
        assert config.api_version == "v15"
        assert config.base_url == "https://googleads.googleapis.com"
        assert config.auth_type == "oauth2"
        assert config.access_token == "token_123"
        assert config.refresh_token == "refresh_456"
        assert config.max_requests_per_minute == 120
        assert config.max_requests_per_hour == 2000
        assert config.retry_max_attempts == 5
        assert config.retry_backoff_seconds == 2.0
        assert config.connect_timeout == 15.0
        assert config.read_timeout == 45.0
        assert config.account_id == "acc_001"
        assert config.accounts == ["acc_001", "acc_002"]
        assert config.lookback_days == 180
        assert config.default_granularity == DataGranularity.HOURLY
        assert config.extra == {"region": "us"}

    def test_to_dict(self):
        config = ConnectorConfig(
            connector_type=DataSource.META_ADS,
            api_version="v18",
            base_url="https://graph.facebook.com",
            max_requests_per_minute=60,
            max_requests_per_hour=1000,
            retry_max_attempts=3,
            connect_timeout=10.0,
            read_timeout=30.0,
            account_id="acc_001",
            accounts=["acc_001"],
            lookback_days=90,
        )
        d = config.to_dict()
        assert d["connector_type"] == "meta_ads"
        assert d["api_version"] == "v18"
        assert d["base_url"] == "https://graph.facebook.com"
        assert d["max_requests_per_minute"] == 60
        assert d["max_requests_per_hour"] == 1000
        assert d["retry_max_attempts"] == 3
        assert d["connect_timeout"] == 10.0
        assert d["read_timeout"] == 30.0
        assert d["account_id"] == "acc_001"
        assert d["accounts"] == ["acc_001"]
        assert d["lookback_days"] == 90

    def test_to_dict_excludes_sensitive_data(self):
        config = ConnectorConfig(
            access_token="secret_token",
            refresh_token="secret_refresh",
            api_key="secret_key",
            app_id="secret_app",
            app_secret="secret_secret",
        )
        d = config.to_dict()
        assert "access_token" not in d
        assert "refresh_token" not in d
        assert "api_key" not in d
        assert "app_id" not in d
        assert "app_secret" not in d

    def test_extra_fields_are_stored(self):
        config = ConnectorConfig(extra={"custom_field": "custom_value"})
        assert config.extra["custom_field"] == "custom_value"

    def test_default_accounts_is_empty_list(self):
        config = ConnectorConfig()
        assert isinstance(config.accounts, list)
        assert config.accounts == []


# ═══════════════════════════════════════════════════════════════
# Test ConnectorInfo
# ═══════════════════════════════════════════════════════════════


class TestConnectorInfo:
    """连接器信息测试。"""

    def test_default_creation(self):
        info = ConnectorInfo()
        assert info.connector_id != ""
        assert info.name == ""
        assert info.source == DataSource.META_ADS
        assert info.status == ConnectorStatus.UNINITIALIZED
        assert info.health == ConnectorHealth.UNKNOWN
        assert info.total_requests == 0
        assert info.successful_requests == 0
        assert info.failed_requests == 0
        assert info.requests_this_minute == 0
        assert info.requests_this_hour == 0
        assert info.is_rate_limited is False

    def test_full_creation(self):
        info = ConnectorInfo(
            name="MetaAdsConnector",
            source=DataSource.META_ADS,
            status=ConnectorStatus.CONNECTED,
            health=ConnectorHealth.HEALTHY,
            total_requests=100,
            successful_requests=95,
            failed_requests=5,
            last_success_at="2026-07-24T08:00:00Z",
            last_error_at="2026-07-24T07:00:00Z",
            last_error_message="Rate limit exceeded",
            requests_this_minute=30,
            requests_this_hour=500,
            is_rate_limited=False,
        )
        assert info.name == "MetaAdsConnector"
        assert info.source == DataSource.META_ADS
        assert info.status == ConnectorStatus.CONNECTED
        assert info.health == ConnectorHealth.HEALTHY
        assert info.total_requests == 100
        assert info.successful_requests == 95
        assert info.failed_requests == 5
        assert info.last_success_at == "2026-07-24T08:00:00Z"
        assert info.last_error_at == "2026-07-24T07:00:00Z"
        assert info.last_error_message == "Rate limit exceeded"
        assert info.requests_this_minute == 30
        assert info.requests_this_hour == 500
        assert info.is_rate_limited is False

    def test_success_rate_perfect(self):
        info = ConnectorInfo(total_requests=100, successful_requests=100)
        assert info.success_rate == 1.0

    def test_success_rate_partial(self):
        info = ConnectorInfo(total_requests=100, successful_requests=75)
        assert info.success_rate == 0.75

    def test_success_rate_zero_requests(self):
        info = ConnectorInfo(total_requests=0, successful_requests=0)
        assert info.success_rate == 1.0

    def test_to_dict(self):
        info = ConnectorInfo(
            name="TestConnector",
            source=DataSource.META_ADS,
            status=ConnectorStatus.CONNECTED,
            health=ConnectorHealth.HEALTHY,
            total_requests=100,
            successful_requests=95,
            failed_requests=5,
        )
        d = info.to_dict()
        assert d["name"] == "TestConnector"
        assert d["source"] == "meta_ads"
        assert d["status"] == "connected"
        assert d["health"] == "healthy"
        assert d["total_requests"] == 100
        assert d["successful_requests"] == 95
        assert d["failed_requests"] == 5
        assert d["success_rate"] == 0.95
        assert d["is_rate_limited"] is False
        assert "connector_id" in d
        assert "created_at" in d

    def test_connector_id_is_unique(self):
        info1 = ConnectorInfo()
        info2 = ConnectorInfo()
        assert info1.connector_id != info2.connector_id


# ═══════════════════════════════════════════════════════════════
# Test BaseConnector — Concrete Implementation
# ═══════════════════════════════════════════════════════════════


class _TestConnector(BaseConnector):
    """测试用具体连接器实现."""

    def _do_connect(self) -> None:
        pass

    def _do_disconnect(self) -> None:
        pass

    def _do_authenticate(self) -> None:
        pass

    def _do_health_check(self) -> ConnectorHealth:
        return ConnectorHealth.HEALTHY


class _FailingConnector(BaseConnector):
    """测试用连接失败连接器."""

    def _do_connect(self) -> None:
        raise ConnectionError("Simulated connection failure")

    def _do_disconnect(self) -> None:
        pass

    def _do_authenticate(self) -> None:
        pass

    def _do_health_check(self) -> ConnectorHealth:
        raise RuntimeError("Simulated health check failure")


class _FailingAuthConnector(BaseConnector):
    """测试用连接成功但认证失败连接器."""

    def _do_connect(self) -> None:
        pass

    def _do_disconnect(self) -> None:
        pass

    def _do_authenticate(self) -> None:
        raise RuntimeError("Simulated auth failure")

    def _do_health_check(self) -> ConnectorHealth:
        return ConnectorHealth.HEALTHY


class _DataConnector(BaseConnector):
    """测试用数据连接器."""

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self._campaigns: list[CampaignMetrics] = []
        self._retention: RetentionCurve | None = None
        self._revenue_curve: UserRevenueCurve | None = None
        self._gameplay: GameplayMetrics | None = None

    def _do_connect(self) -> None:
        pass

    def _do_disconnect(self) -> None:
        pass

    def _do_authenticate(self) -> None:
        pass

    def _do_health_check(self) -> ConnectorHealth:
        return ConnectorHealth.HEALTHY

    def fetch_campaigns(
        self, product_id: str = "", date_from: str = "", date_to: str = "",
    ) -> list[CampaignMetrics]:
        return self._campaigns

    def fetch_retention(
        self, product_id: str = "", cohort_date: str = "",
    ) -> RetentionCurve | None:
        return self._retention

    def fetch_revenue_curve(
        self, product_id: str = "", cohort_date: str = "",
    ) -> UserRevenueCurve | None:
        return self._revenue_curve

    def fetch_gameplay(
        self, product_id: str = "", date: str = "",
    ) -> GameplayMetrics | None:
        return self._gameplay


class TestBaseConnector:
    """抽象基类测试。"""

    def test_abstract_class(self):
        assert BaseConnector in BaseConnector.__mro__

    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            BaseConnector(ConnectorConfig())  # type: ignore[abstract]

    # ── Properties ──────────────────────────────────────────

    def test_config_property(self):
        config = ConnectorConfig(connector_type=DataSource.META_ADS)
        connector = _TestConnector(config)
        assert connector.config is config
        assert connector.config.connector_type == DataSource.META_ADS

    def test_info_property(self):
        connector = _TestConnector(ConnectorConfig())
        assert isinstance(connector.info, ConnectorInfo)
        assert connector.info.name == "_TestConnector"
        assert connector.info.source == DataSource.META_ADS

    def test_is_connected_initial(self):
        connector = _TestConnector(ConnectorConfig())
        assert connector.is_connected is False

    def test_is_authenticated_initial(self):
        connector = _TestConnector(ConnectorConfig())
        assert connector.is_authenticated is False

    def test_name_property(self):
        connector = _TestConnector(ConnectorConfig())
        assert connector.name == "_TestConnector"

    def test_source_property(self):
        config = ConnectorConfig(connector_type=DataSource.GOOGLE_ADS)
        connector = _TestConnector(config)
        assert connector.source == DataSource.GOOGLE_ADS

    # ── Connect Lifecycle ───────────────────────────────────

    def test_connect_success(self):
        connector = _TestConnector(ConnectorConfig())
        result = connector.connect()
        assert result is True
        assert connector.is_connected is True
        assert connector.info.status == ConnectorStatus.CONNECTED
        assert connector.info.last_success_at != ""

    def test_connect_failure(self):
        connector = _FailingConnector(ConnectorConfig())
        result = connector.connect()
        assert result is False
        assert connector.is_connected is False
        assert connector.info.status == ConnectorStatus.ERROR
        assert "Simulated connection failure" in connector.info.last_error_message
        assert connector.info.last_error_at != ""

    def test_connect_twice(self):
        connector = _TestConnector(ConnectorConfig())
        connector.connect()
        assert connector.connect() is True

    # ── Disconnect Lifecycle ────────────────────────────────

    def test_disconnect(self):
        connector = _TestConnector(ConnectorConfig())
        connector.connect()
        assert connector.is_connected is True
        connector.disconnect()
        assert connector.is_connected is False
        assert connector.is_authenticated is False
        assert connector.info.status == ConnectorStatus.DISCONNECTED

    def test_disconnect_when_not_connected(self):
        connector = _TestConnector(ConnectorConfig())
        connector.disconnect()
        assert connector.is_connected is False

    # ── Authenticate Lifecycle ──────────────────────────────

    def test_authenticate_when_connected(self):
        connector = _TestConnector(ConnectorConfig())
        connector.connect()
        result = connector.authenticate()
        assert result is True
        assert connector.is_authenticated is True

    def test_authenticate_when_not_connected(self):
        connector = _TestConnector(ConnectorConfig())
        result = connector.authenticate()
        assert result is False
        assert connector.is_authenticated is False

    def test_authenticate_failure(self):
        connector = _FailingAuthConnector(ConnectorConfig())
        connector.connect()
        result = connector.authenticate()
        assert result is False
        assert connector.is_authenticated is False
        assert connector.info.status == ConnectorStatus.AUTH_EXPIRED

    # ── Health Check ────────────────────────────────────────

    def test_health_check_connected(self):
        connector = _TestConnector(ConnectorConfig())
        connector.connect()
        health = connector.health_check()
        assert health == ConnectorHealth.HEALTHY
        assert connector.info.health == ConnectorHealth.HEALTHY

    def test_health_check_not_connected(self):
        connector = _TestConnector(ConnectorConfig())
        health = connector.health_check()
        assert health == ConnectorHealth.UNHEALTHY
        assert connector.info.health == ConnectorHealth.UNHEALTHY

    def test_health_check_exception(self):
        connector = _FailingConnector(ConnectorConfig())
        connector.connect()
        health = connector.health_check()
        assert health == ConnectorHealth.UNHEALTHY

    # ── Rate Limiting ───────────────────────────────────────

    def test_rate_limit_within_bounds(self):
        config = ConnectorConfig(max_requests_per_minute=100, max_requests_per_hour=1000)
        connector = _TestConnector(config)
        connector.connect()
        assert connector._check_rate_limit() is True

    def test_rate_limit_exceeded_minute(self):
        config = ConnectorConfig(max_requests_per_minute=5, max_requests_per_hour=1000)
        connector = _TestConnector(config)
        connector.connect()
        connector._last_request_time = time.time()
        connector._info.requests_this_minute = 5
        assert connector._check_rate_limit() is False
        assert connector.info.is_rate_limited is True
        assert connector.info.status == ConnectorStatus.RATE_LIMITED

    def test_rate_limit_exceeded_hour(self):
        config = ConnectorConfig(max_requests_per_minute=100, max_requests_per_hour=5)
        connector = _TestConnector(config)
        connector.connect()
        connector._last_request_time = time.time()
        connector._info.requests_this_hour = 5
        assert connector._check_rate_limit() is False
        assert connector.info.is_rate_limited is True

    def test_rate_limit_reset_after_minute(self):
        config = ConnectorConfig(max_requests_per_minute=5, max_requests_per_hour=1000)
        connector = _TestConnector(config)
        connector.connect()
        connector._info.requests_this_minute = 5
        connector._last_request_time = time.time() - 61.0
        assert connector._check_rate_limit() is True
        assert connector.info.requests_this_minute == 0

    # ── Record Request ──────────────────────────────────────

    def test_record_request_success(self):
        connector = _TestConnector(ConnectorConfig())
        connector._record_request(success=True)
        assert connector.info.total_requests == 1
        assert connector.info.successful_requests == 1
        assert connector.info.failed_requests == 0
        assert connector.info.requests_this_minute == 1
        assert connector.info.requests_this_hour == 1
        assert connector.info.last_success_at != ""

    def test_record_request_failure(self):
        connector = _TestConnector(ConnectorConfig())
        connector._record_request(success=False)
        assert connector.info.total_requests == 1
        assert connector.info.successful_requests == 0
        assert connector.info.failed_requests == 1
        assert connector.info.last_error_at != ""

    def test_record_request_increments(self):
        connector = _TestConnector(ConnectorConfig())
        connector._record_request(success=True)
        connector._record_request(success=True)
        connector._record_request(success=False)
        assert connector.info.total_requests == 3
        assert connector.info.successful_requests == 2
        assert connector.info.failed_requests == 1

    # ── Retry ───────────────────────────────────────────────

    def test_retry_success_first_attempt(self):
        connector = _TestConnector(ConnectorConfig())
        connector.connect()

        def succeed():
            return "ok"

        result = connector._retry(succeed)
        assert result == "ok"
        assert connector.info.successful_requests >= 1

    def test_retry_success_after_failure(self):
        config = ConnectorConfig(retry_max_attempts=3, retry_backoff_seconds=0.01)
        connector = _TestConnector(config)
        connector.connect()

        call_count = {"count": 0}

        def fail_twice():
            call_count["count"] += 1
            if call_count["count"] < 3:
                raise RuntimeError("fail")
            return "ok"

        result = connector._retry(fail_twice)
        assert result == "ok"
        assert call_count["count"] == 3

    def test_retry_exhausted(self):
        config = ConnectorConfig(retry_max_attempts=2, retry_backoff_seconds=0.01)
        connector = _TestConnector(config)
        connector.connect()

        def always_fail():
            raise RuntimeError("always fail")

        with pytest.raises(RuntimeError, match="always fail"):
            connector._retry(always_fail)

    # ── Default Fetch Methods ───────────────────────────────

    def test_default_fetch_campaigns_empty(self):
        connector = _TestConnector(ConnectorConfig())
        connector.connect()
        assert connector.fetch_campaigns() == []

    def test_default_fetch_adsets_empty(self):
        connector = _TestConnector(ConnectorConfig())
        connector.connect()
        assert connector.fetch_adsets() == []

    def test_default_fetch_creatives_empty(self):
        connector = _TestConnector(ConnectorConfig())
        connector.connect()
        assert connector.fetch_creatives() == []

    def test_default_fetch_revenue_curve_none(self):
        connector = _TestConnector(ConnectorConfig())
        connector.connect()
        assert connector.fetch_revenue_curve() is None

    def test_default_fetch_retention_none(self):
        connector = _TestConnector(ConnectorConfig())
        connector.connect()
        assert connector.fetch_retention() is None

    def test_default_fetch_gameplay_none(self):
        connector = _TestConnector(ConnectorConfig())
        connector.connect()
        assert connector.fetch_gameplay() is None

    # ── Get Summary ─────────────────────────────────────────

    def test_get_summary(self):
        connector = _TestConnector(ConnectorConfig())
        connector.connect()
        summary = connector.get_summary()
        assert "connected" in summary
        assert summary["connected"] is True
        assert "authenticated" in summary
        assert "connector_id" in summary
        assert "config" in summary

    def test_get_summary_disconnected(self):
        connector = _TestConnector(ConnectorConfig())
        summary = connector.get_summary()
        assert summary["connected"] is False
        assert summary["authenticated"] is False


# ═══════════════════════════════════════════════════════════════
# Test ConnectorRegistry
# ═══════════════════════════════════════════════════════════════


class TestConnectorRegistry:
    """连接器注册表测试。"""

    def make_meta_connector(self) -> _TestConnector:
        return _TestConnector(ConnectorConfig(connector_type=DataSource.META_ADS))

    def make_adjust_connector(self) -> _DataConnector:
        return _DataConnector(ConnectorConfig(connector_type=DataSource.ADJUST))

    def make_firebase_connector(self) -> _DataConnector:
        return _DataConnector(ConnectorConfig(connector_type=DataSource.FIREBASE))

    # ── Registration ────────────────────────────────────────

    def test_initial_empty(self):
        registry = ConnectorRegistry()
        assert registry.connector_count == 0
        assert registry.sources == []

    def test_register_single(self):
        registry = ConnectorRegistry()
        connector = self.make_meta_connector()
        result = registry.register(connector)
        assert result is True
        assert registry.connector_count == 1
        assert registry.sources == [DataSource.META_ADS]

    def test_register_multiple(self):
        registry = ConnectorRegistry()
        registry.register(self.make_meta_connector())
        registry.register(self.make_adjust_connector())
        registry.register(self.make_firebase_connector())
        assert registry.connector_count == 3

    def test_register_duplicate_source_replaces(self):
        registry = ConnectorRegistry()
        c1 = self.make_meta_connector()
        c2 = _TestConnector(ConnectorConfig(connector_type=DataSource.META_ADS))
        registry.register(c1)
        registry.register(c2)
        assert registry.connector_count == 1
        assert registry.get(DataSource.META_ADS) is c2

    def test_unregister_existing(self):
        registry = ConnectorRegistry()
        connector = self.make_meta_connector()
        registry.register(connector)
        result = registry.unregister(DataSource.META_ADS)
        assert result is True
        assert registry.connector_count == 0

    def test_unregister_nonexistent(self):
        registry = ConnectorRegistry()
        result = registry.unregister(DataSource.META_ADS)
        assert result is False

    # ── Get ─────────────────────────────────────────────────

    def test_get_existing(self):
        registry = ConnectorRegistry()
        connector = self.make_meta_connector()
        registry.register(connector)
        assert registry.get(DataSource.META_ADS) is connector

    def test_get_nonexistent(self):
        registry = ConnectorRegistry()
        assert registry.get(DataSource.META_ADS) is None

    def test_get_all(self):
        registry = ConnectorRegistry()
        c1 = self.make_meta_connector()
        c2 = self.make_adjust_connector()
        registry.register(c1)
        registry.register(c2)
        all_connectors = registry.get_all()
        assert len(all_connectors) == 2
        assert c1 in all_connectors
        assert c2 in all_connectors

    def test_get_healthy(self):
        registry = ConnectorRegistry()
        c1 = self.make_meta_connector()
        c2 = self.make_adjust_connector()
        registry.register(c1)
        registry.register(c2)
        c1.connect()
        c1.health_check()
        assert len(registry.get_healthy()) == 1

    def test_get_connected(self):
        registry = ConnectorRegistry()
        c1 = self.make_meta_connector()
        c2 = self.make_adjust_connector()
        registry.register(c1)
        registry.register(c2)
        c1.connect()
        assert len(registry.get_connected()) == 1

    # ── Lifecycle ───────────────────────────────────────────

    def test_connect_all(self):
        registry = ConnectorRegistry()
        registry.register(self.make_meta_connector())
        registry.register(self.make_adjust_connector())
        results = registry.connect_all()
        assert results[DataSource.META_ADS] is True
        assert results[DataSource.ADJUST] is True
        assert len(registry.get_connected()) == 2

    def test_connect_all_with_failure(self):
        registry = ConnectorRegistry()
        registry.register(self.make_meta_connector())
        registry.register(_FailingConnector(ConnectorConfig(connector_type=DataSource.ADJUST)))
        results = registry.connect_all()
        assert results[DataSource.META_ADS] is True
        assert results[DataSource.ADJUST] is False
        assert len(registry.get_connected()) == 1

    def test_disconnect_all(self):
        registry = ConnectorRegistry()
        registry.register(self.make_meta_connector())
        registry.register(self.make_adjust_connector())
        registry.connect_all()
        registry.disconnect_all()
        assert len(registry.get_connected()) == 0

    def test_health_check_all(self):
        registry = ConnectorRegistry()
        registry.register(self.make_meta_connector())
        registry.register(self.make_adjust_connector())
        registry.connect_all()
        results = registry.health_check_all()
        assert results[DataSource.META_ADS] == ConnectorHealth.HEALTHY
        assert results[DataSource.ADJUST] == ConnectorHealth.HEALTHY

    # ── Data Collection ─────────────────────────────────────

    def test_collect_campaign_data(self):
        registry = ConnectorRegistry()
        dc = self.make_meta_connector()
        dc._connector_type = DataSource.META_ADS
        registry.register(_DataConnector(ConnectorConfig(connector_type=DataSource.META_ADS)))
        registry.connect_all()
        events = registry.collect_campaign_data()
        assert isinstance(events, list)

    def test_collect_campaign_data_with_data(self):
        registry = ConnectorRegistry()
        dc = _DataConnector(ConnectorConfig(connector_type=DataSource.META_ADS))
        dc._campaigns = [
            CampaignMetrics(
                campaign_id="c_001",
                platform=DataSource.META_ADS,
                product_id="p04",
                spend=100.0,
                revenue=200.0,
                roas=2.0,
                impressions=5000,
                clicks=250,
                installs=100,
                date="2026-07-24",
            )
        ]
        registry.register(dc)
        registry.connect_all()
        events = registry.collect_campaign_data(product_id="p04")
        assert len(events) == 1
        assert events[0].campaign_id == "c_001"
        assert events[0].metrics["spend"] == 100.0

    def test_collect_campaign_data_filters_non_ad_sources(self):
        registry = ConnectorRegistry()
        ad = _DataConnector(ConnectorConfig(connector_type=DataSource.META_ADS))
        ad._campaigns = [CampaignMetrics(campaign_id="c_001", platform=DataSource.META_ADS)]
        adjust = _DataConnector(ConnectorConfig(connector_type=DataSource.ADJUST))
        adjust._campaigns = [CampaignMetrics(campaign_id="c_002", platform=DataSource.ADJUST)]
        registry.register(ad)
        registry.register(adjust)
        registry.connect_all()
        events = registry.collect_campaign_data()
        # Only ad platform connectors should be collected
        assert len(events) == 1
        assert events[0].campaign_id == "c_001"

    def test_collect_revenue_data(self):
        registry = ConnectorRegistry()
        adjust = _DataConnector(ConnectorConfig(connector_type=DataSource.ADJUST))
        adjust._retention = RetentionCurve(
            product_id="p04",
            d1_retention=0.45,
            d7_retention=0.25,
            d30_retention=0.12,
            payer_rate=0.03,
        )
        registry.register(adjust)
        registry.connect_all()
        events = registry.collect_revenue_data(product_id="p04")
        assert len(events) == 1
        assert events[0].event_type == MetricType.RETENTION
        assert events[0].metrics["d1_retention"] == 0.45

    def test_collect_revenue_data_filters_non_attribution_sources(self):
        registry = ConnectorRegistry()
        meta = _DataConnector(ConnectorConfig(connector_type=DataSource.META_ADS))
        meta._retention = RetentionCurve(product_id="p04")
        adjust = _DataConnector(ConnectorConfig(connector_type=DataSource.ADJUST))
        adjust._retention = RetentionCurve(product_id="p04")
        registry.register(meta)
        registry.register(adjust)
        registry.connect_all()
        events = registry.collect_revenue_data()
        # Only attribution connectors should be collected
        assert len(events) == 1

    def test_collect_all(self):
        registry = ConnectorRegistry()
        meta = _DataConnector(ConnectorConfig(connector_type=DataSource.META_ADS))
        meta._campaigns = [CampaignMetrics(campaign_id="c_001", platform=DataSource.META_ADS)]
        adjust = _DataConnector(ConnectorConfig(connector_type=DataSource.ADJUST))
        adjust._retention = RetentionCurve(product_id="p04")
        registry.register(meta)
        registry.register(adjust)
        registry.connect_all()
        events = registry.collect_all(product_id="p04")
        assert len(events) == 2

    # ── Query ───────────────────────────────────────────────

    def test_get_connector_info(self):
        registry = ConnectorRegistry()
        connector = self.make_meta_connector()
        registry.register(connector)
        info = registry.get_connector_info(DataSource.META_ADS)
        assert info is not None
        assert info.name == "_TestConnector"

    def test_get_connector_info_nonexistent(self):
        registry = ConnectorRegistry()
        assert registry.get_connector_info(DataSource.META_ADS) is None

    def test_get_all_info(self):
        registry = ConnectorRegistry()
        registry.register(self.make_meta_connector())
        registry.register(self.make_adjust_connector())
        all_info = registry.get_all_info()
        assert len(all_info) == 2
        assert all(isinstance(info, ConnectorInfo) for info in all_info)

    def test_get_status_summary(self):
        registry = ConnectorRegistry()
        registry.register(self.make_meta_connector())
        registry.register(self.make_adjust_connector())
        summary = registry.get_status_summary()
        assert summary["total_connectors"] == 2
        assert "connected" in summary
        assert "healthy" in summary
        assert "unhealthy" in summary
        assert "sources" in summary
        assert "connectors" in summary

    def test_get_summary(self):
        registry = ConnectorRegistry()
        registry.register(self.make_meta_connector())
        summary = registry.get_summary()
        assert summary["connector_count"] == 1
        assert "sources" in summary
        assert "status" in summary

    # ── Edge Cases ──────────────────────────────────────────

    def test_collect_data_on_empty_registry(self):
        registry = ConnectorRegistry()
        assert registry.collect_all() == []
        assert registry.collect_campaign_data() == []
        assert registry.collect_revenue_data() == []

    def test_collect_data_with_disconnected_connectors(self):
        registry = ConnectorRegistry()
        dc = _DataConnector(ConnectorConfig(connector_type=DataSource.META_ADS))
        dc._campaigns = [CampaignMetrics(campaign_id="c_001", platform=DataSource.META_ADS)]
        registry.register(dc)
        # Don't connect — should collect nothing
        events = registry.collect_campaign_data()
        assert events == []

    def test_unregister_disconnects(self):
        registry = ConnectorRegistry()
        connector = self.make_meta_connector()
        registry.register(connector)
        connector.connect()
        assert connector.is_connected is True
        registry.unregister(DataSource.META_ADS)
        assert connector.is_connected is False