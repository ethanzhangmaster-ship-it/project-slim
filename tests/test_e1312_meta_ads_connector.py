"""E13.1.2 Meta Ads Connector — 测试套件.

预计: models 30, client 40, mapper 40, adapter 60, validator 30, integration 40
Total: ~240 tests
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

# Ensure src is on path
sys.path.insert(0, "src")

from market_ops.creative_vision_runtime.growth_runtime.connectors.meta_ads import (
    # Enums
    MetaAccountStatus,
    MetaCampaignObjective,
    MetaCampaignStatus,
    MetaInsightAction,
    MetaInsightLevel,
    # Models
    CreativeFatigueSignal,
    MetaAccount,
    MetaAdSet,
    MetaAPIResponse,
    MetaCampaign,
    MetaCreative,
    MetaPerformance,
    ScalingOpportunity,
    # Client
    MetaAdsClient,
    # Adapter
    MetaAdsConnector,
    # Mapper
    MetaMetricsMapper,
    # Validator
    CreativeFatigueValidator,
    MetaAccountValidator,
    MetaCampaignValidator,
    MetaCreativeValidator,
    MetaPerformanceValidator,
    ScalingOpportunityValidator,
    ValidationResult,
    # Exceptions
    MetaAdsError,
    MetaAPIError,
    MetaAuthError,
    MetaConfigError,
    MetaConnectionError,
    MetaDataNotFoundError,
    MetaRateLimitError,
    MetaValidationError,
)
from market_ops.creative_vision_runtime.growth_runtime.connectors.models import (
    CampaignMetrics,
    ConnectorConfig,
    ConnectorHealth,
    CreativeMetrics,
    DataSource,
    GrowthDataEvent,
    MetricType,
)


# ═══════════════════════════════════════════════════════════════
# Test Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def mock_client():
    """创建已连接的 mock MetaAdsClient."""
    client = MetaAdsClient(use_mock=True, ad_account_id="act_test123")
    client.connect()
    return client


@pytest.fixture
def connected_connector():
    """创建已连接并认证的 MetaAdsConnector."""
    config = ConnectorConfig(
        connector_type=DataSource.META_ADS,
        account_id="act_test123",
    )
    connector = MetaAdsConnector(config)
    connector.connect()
    connector.authenticate()
    return connector


@pytest.fixture
def sample_performance():
    """创建样本 MetaPerformance."""
    return MetaPerformance(
        campaign_id="c_123",
        adset_id="as_123",
        creative_id="cr_123",
        account_id="act_123",
        date_start="2026-07-20",
        date_stop="2026-07-20",
        spend=500.0,
        revenue=750.0,
        roas=1.5,
        impressions=20000,
        clicks=500,
        ctr=0.025,
        cpm=25.0,
        cpc=1.0,
        installs=100,
        cpi=5.0,
        frequency=2.0,
        reach=18000,
        unique_clicks=450,
    )


@pytest.fixture
def sample_raw_insight():
    """创建样本 Meta API 原始响应."""
    return {
        "campaign_id": "c_test",
        "adset_id": "as_test",
        "ad_id": "cr_test",
        "account_id": "act_test",
        "date_start": "2026-07-20",
        "date_stop": "2026-07-20",
        "spend": "500.00",
        "impressions": "20000",
        "clicks": "500",
        "reach": "18000",
        "frequency": "2.0",
        "cpm": "25.0",
        "cpc": "1.0",
        "ctr": "0.025",
        "unique_clicks": "450",
        "actions": [
            {"action_type": "mobile_app_install", "value": "100"},
            {"action_type": "purchase", "value": "10"},
        ],
        "action_values": [
            {"action_type": "purchase", "value": "750.00"},
        ],
        "cost_per_action_type": [
            {"action_type": "mobile_app_install", "value": "5.0"},
            {"action_type": "purchase", "value": "50.0"},
        ],
        "quality_ranking": "above_average",
        "engagement_rate_ranking": "average",
        "conversion_rate_ranking": "above_average",
    }


# ═══════════════════════════════════════════════════════════════
# 1. Models Tests (~30)
# ═══════════════════════════════════════════════════════════════


class TestMetaAccount:
    """MetaAccount 模型测试."""

    def test_create_default(self):
        acc = MetaAccount()
        assert acc.account_id == ""
        assert acc.currency == "USD"
        assert acc.is_active is False

    def test_create_with_fields(self):
        acc = MetaAccount(
            account_id="act_123",
            name="Test Account",
            currency="EUR",
            status=MetaAccountStatus.ACTIVE,
        )
        assert acc.account_id == "act_123"
        assert acc.currency == "EUR"
        assert acc.is_active is True

    def test_to_dict(self):
        acc = MetaAccount(
            account_id="act_123",
            name="Test",
            balance=100.5,
            amount_spent=50.3,
        )
        d = acc.to_dict()
        assert d["account_id"] == "act_123"
        assert d["balance"] == 100.5
        assert d["amount_spent"] == 50.3
        assert "fetched_at" in d

    def test_status_active(self):
        acc = MetaAccount(account_id="a", status=MetaAccountStatus.ACTIVE)
        assert acc.is_active is True

    def test_status_disabled(self):
        acc = MetaAccount(account_id="a", status=MetaAccountStatus.DISABLED)
        assert acc.is_active is False


class TestMetaCampaign:
    """MetaCampaign 模型测试."""

    def test_create_default(self):
        camp = MetaCampaign()
        assert camp.campaign_id == ""
        assert camp.is_active is False

    def test_create_with_values(self):
        camp = MetaCampaign(
            campaign_id="c_1",
            name="Test Campaign",
            objective=MetaCampaignObjective.APP_INSTALLS,
            status=MetaCampaignStatus.ACTIVE,
            daily_budget=100.0,
        )
        assert camp.campaign_id == "c_1"
        assert camp.daily_budget == 100.0
        assert camp.is_active is True
        assert camp.is_paused is False

    def test_is_paused(self):
        camp = MetaCampaign(campaign_id="c_1", status=MetaCampaignStatus.PAUSED)
        assert camp.is_paused is True
        assert camp.is_active is False

    def test_to_dict(self):
        camp = MetaCampaign(
            campaign_id="c_1",
            name="Test",
            objective=MetaCampaignObjective.CONVERSIONS,
            daily_budget=200.0,
            lifetime_budget=5000.0,
        )
        d = camp.to_dict()
        assert d["campaign_id"] == "c_1"
        assert d["objective"] == "CONVERSIONS"
        assert d["daily_budget"] == 200.0
        assert d["lifetime_budget"] == 5000.0


class TestMetaAdSet:
    """MetaAdSet 模型测试."""

    def test_create_default(self):
        adset = MetaAdSet()
        assert adset.adset_id == ""
        assert adset.daily_budget == 0.0

    def test_create_with_targeting(self):
        adset = MetaAdSet(
            adset_id="as_1",
            campaign_id="c_1",
            targeting={"age_min": 18, "age_max": 35},
        )
        assert adset.targeting["age_min"] == 18

    def test_to_dict(self):
        adset = MetaAdSet(adset_id="as_1", campaign_id="c_1", daily_budget=50.0)
        d = adset.to_dict()
        assert d["adset_id"] == "as_1"
        assert d["daily_budget"] == 50.0


class TestMetaCreative:
    """MetaCreative 模型测试."""

    def test_create_default(self):
        cr = MetaCreative()
        assert cr.creative_id == ""
        assert cr.media_type == "unknown"

    def test_is_video(self):
        cr = MetaCreative(creative_id="cr_1", video_url="https://example.com/v.mp4")
        assert cr.is_video is True
        assert cr.is_image is False
        assert cr.media_type == "video"

    def test_is_image(self):
        cr = MetaCreative(creative_id="cr_1", image_url="https://example.com/img.jpg")
        assert cr.is_image is True
        assert cr.is_video is False
        assert cr.media_type == "image"

    def test_media_type_unknown(self):
        cr = MetaCreative(creative_id="cr_1")
        assert cr.media_type == "unknown"

    def test_to_dict(self):
        cr = MetaCreative(
            creative_id="cr_1",
            name="Test Creative",
            video_url="https://example.com/v.mp4",
            call_to_action="INSTALL_MOBILE_APP",
        )
        d = cr.to_dict()
        assert d["creative_id"] == "cr_1"
        assert d["video_url"] == "https://example.com/v.mp4"


class TestMetaPerformance:
    """MetaPerformance 模型测试."""

    def test_create_default(self):
        perf = MetaPerformance()
        assert perf.spend == 0.0
        assert perf.impressions == 0
        assert perf.is_profitable is False
        assert perf.is_fatigued is False

    def test_is_profitable(self):
        perf = MetaPerformance(spend=100, revenue=150, roas=1.5)
        assert perf.is_profitable is True

    def test_is_not_profitable(self):
        perf = MetaPerformance(spend=100, revenue=80, roas=0.8)
        assert perf.is_profitable is False

    def test_is_fatigued(self):
        perf = MetaPerformance(frequency=4.0, ctr=0.01)
        assert perf.is_fatigued is True

    def test_is_not_fatigued(self):
        perf = MetaPerformance(frequency=2.0, ctr=0.03)
        assert perf.is_fatigued is False

    def test_has_scaling_potential(self):
        perf = MetaPerformance(roas=2.0, impressions=5000)
        assert perf.has_scaling_potential is True

    def test_no_scaling_potential_low_roas(self):
        perf = MetaPerformance(roas=1.2, impressions=5000)
        assert perf.has_scaling_potential is False

    def test_ctr_trend_rising(self):
        perf = MetaPerformance(ctr=0.03)
        assert perf.ctr_trend_indicator == "rising"

    def test_ctr_trend_stable(self):
        perf = MetaPerformance(ctr=0.015)
        assert perf.ctr_trend_indicator == "stable"

    def test_ctr_trend_declining(self):
        perf = MetaPerformance(ctr=0.005)
        assert perf.ctr_trend_indicator == "declining"

    def test_to_dict(self):
        perf = MetaPerformance(
            campaign_id="c_1",
            spend=500.0,
            revenue=750.0,
            roas=1.5,
            impressions=20000,
            clicks=500,
            ctr=0.025,
            installs=100,
            cpi=5.0,
            actions={"mobile_app_install": 100},
            action_values={"purchase": 750.0},
            cost_per_action_type={"mobile_app_install": 5.0},
        )
        d = perf.to_dict()
        assert d["campaign_id"] == "c_1"
        assert d["spend"] == 500.0
        assert d["roas"] == 1.5
        assert d["installs"] == 100
        assert "actions" not in d  # actions not in to_dict output


class TestMetaAPIResponse:
    """MetaAPIResponse 模型测试."""

    def test_success_response(self):
        resp = MetaAPIResponse(success=True, data=[{"id": "1"}])
        assert resp.is_error is False
        assert resp.has_more is False

    def test_error_response(self):
        resp = MetaAPIResponse(success=False, error_message="Auth failed")
        assert resp.is_error is True

    def test_pagination(self):
        resp = MetaAPIResponse(paging={"next": "url"})
        assert resp.has_more is True

    def test_pagination_no_next(self):
        resp = MetaAPIResponse(paging={})
        assert resp.has_more is False

    def test_to_dict(self):
        resp = MetaAPIResponse(
            data=[{"id": "1"}, {"id": "2"}],
            rate_limit_remaining=199,
            request_id="req-123",
        )
        d = resp.to_dict()
        assert d["data_count"] == 2
        assert d["rate_limit_remaining"] == 199


class TestCreativeFatigueSignal:
    """CreativeFatigueSignal 模型测试."""

    def test_create_default(self):
        signal = CreativeFatigueSignal()
        assert signal.fatigue_level == "low"
        assert signal.is_fatigued is False

    def test_is_fatigued_high(self):
        signal = CreativeFatigueSignal(fatigue_level="high")
        assert signal.is_fatigued is True

    def test_is_fatigued_critical(self):
        signal = CreativeFatigueSignal(fatigue_level="critical")
        assert signal.is_fatigued is True

    def test_is_fatigued_low(self):
        signal = CreativeFatigueSignal(fatigue_level="low")
        assert signal.is_fatigued is False

    def test_to_dict(self):
        signal = CreativeFatigueSignal(
            creative_id="cr_1",
            current_ctr=0.015,
            current_frequency=3.5,
            fatigue_score=0.65,
            fatigue_level="high",
            recommendation="Replace creative within 48 hours",
        )
        d = signal.to_dict()
        assert d["creative_id"] == "cr_1"
        assert d["fatigue_level"] == "high"
        assert d["fatigue_score"] == 0.65


class TestScalingOpportunity:
    """ScalingOpportunity 模型测试."""

    def test_create_default(self):
        opp = ScalingOpportunity()
        assert opp.is_viable is False

    def test_is_viable(self):
        opp = ScalingOpportunity(
            confidence=0.7,
            suggested_budget_increase_pct=20.0,
        )
        assert opp.is_viable is True

    def test_is_not_viable_low_confidence(self):
        opp = ScalingOpportunity(
            confidence=0.3,
            suggested_budget_increase_pct=20.0,
        )
        assert opp.is_viable is False

    def test_is_not_viable_no_increase(self):
        opp = ScalingOpportunity(
            confidence=0.7,
            suggested_budget_increase_pct=0.0,
        )
        assert opp.is_viable is False

    def test_to_dict(self):
        opp = ScalingOpportunity(
            campaign_id="c_1",
            current_daily_budget=100.0,
            suggested_daily_budget=130.0,
            confidence=0.7,
        )
        d = opp.to_dict()
        assert d["campaign_id"] == "c_1"
        assert d["current_daily_budget"] == 100.0
        assert d["suggested_daily_budget"] == 130.0


# ═══════════════════════════════════════════════════════════════
# 2. Client Tests (~40)
# ═══════════════════════════════════════════════════════════════


class TestMetaAdsClientInit:
    """MetaAdsClient 初始化测试."""

    def test_create_mock_client(self):
        client = MetaAdsClient(use_mock=True)
        assert client._use_mock is True
        assert client.is_connected is False
        assert client.is_authenticated is False

    def test_auto_mock_when_no_token(self):
        client = MetaAdsClient(access_token="")
        assert client._use_mock is True

    def test_real_mode_with_token(self):
        client = MetaAdsClient(access_token="real_token", use_mock=False)
        assert client._use_mock is False


class TestMetaAdsClientConnect:
    """MetaAdsClient 连接测试."""

    def test_connect_mock(self):
        client = MetaAdsClient(use_mock=True)
        client.connect()
        assert client.is_connected is True

    def test_connect_seeds_mock_data(self):
        client = MetaAdsClient(use_mock=True, ad_account_id="act_test")
        client.connect()
        assert len(client._mock_campaigns) > 0
        assert len(client._mock_adsets) > 0
        assert len(client._mock_creatives) > 0
        assert len(client._mock_performances) > 0

    def test_connect_without_token_raises(self):
        client = MetaAdsClient(use_mock=False, access_token="some_token")
        client._use_mock = False  # Force non-mock mode
        client._access_token = ""  # Clear token to trigger error
        with pytest.raises(MetaConfigError):
            client.connect()

    def test_disconnect(self):
        client = MetaAdsClient(use_mock=True)
        client.connect()
        client.disconnect()
        assert client.is_connected is False
        assert client.is_authenticated is False

    def test_authenticate_mock(self):
        client = MetaAdsClient(use_mock=True)
        client.connect()
        assert client.authenticate() is True
        assert client.is_authenticated is True

    def test_authenticate_no_token(self):
        client = MetaAdsClient(use_mock=False, access_token="some_token")
        client._use_mock = False
        client._access_token = ""
        with pytest.raises(MetaAuthError):
            client.authenticate()


class TestMetaAdsClientAccounts:
    """MetaAdsClient 账户操作测试."""

    def test_get_accounts(self, mock_client):
        accounts = mock_client.get_accounts()
        assert len(accounts) >= 1
        assert accounts[0].account_id == "act_test123"

    def test_get_account_exists(self, mock_client):
        acc = mock_client.get_account("act_test123")
        assert acc.account_id == "act_test123"
        assert acc.name == "Test Ad Account"

    def test_get_account_not_found(self, mock_client):
        with pytest.raises(MetaDataNotFoundError):
            mock_client.get_account("nonexistent")

    def test_get_accounts_without_connect(self):
        client = MetaAdsClient(use_mock=True)
        with pytest.raises(MetaConnectionError):
            client.get_accounts()


class TestMetaAdsClientCampaigns:
    """MetaAdsClient 广告系列操作测试."""

    def test_get_campaigns(self, mock_client):
        campaigns = mock_client.get_campaigns()
        assert len(campaigns) == 3

    def test_get_campaigns_by_account(self, mock_client):
        campaigns = mock_client.get_campaigns(account_id="act_test123")
        assert len(campaigns) == 3

    def test_get_campaigns_by_wrong_account(self, mock_client):
        campaigns = mock_client.get_campaigns(account_id="act_other")
        assert len(campaigns) == 0

    def test_get_campaign_exists(self, mock_client):
        camp = mock_client.get_campaign("c_act_test123_1")
        assert camp.campaign_id == "c_act_test123_1"
        assert camp.objective == MetaCampaignObjective.APP_INSTALLS
        assert camp.is_active is True

    def test_get_campaign_not_found(self, mock_client):
        with pytest.raises(MetaDataNotFoundError):
            mock_client.get_campaign("nonexistent")


class TestMetaAdsClientAdSets:
    """MetaAdsClient 广告组操作测试."""

    def test_get_adsets(self, mock_client):
        adsets = mock_client.get_adsets()
        assert len(adsets) == 6  # 3 campaigns * 2 adsets

    def test_get_adsets_by_campaign(self, mock_client):
        adsets = mock_client.get_adsets(campaign_id="c_act_test123_1")
        assert len(adsets) == 2

    def test_get_adset_exists(self, mock_client):
        adset = mock_client.get_adset("as_c_act_test123_1_1")
        assert adset.adset_id == "as_c_act_test123_1_1"
        assert adset.optimization_goal == "APP_INSTALLS"

    def test_get_adset_not_found(self, mock_client):
        with pytest.raises(MetaDataNotFoundError):
            mock_client.get_adset("nonexistent")


class TestMetaAdsClientCreatives:
    """MetaAdsClient 创意操作测试."""

    def test_get_creatives(self, mock_client):
        creatives = mock_client.get_creatives()
        assert len(creatives) == 12  # 3*2*2

    def test_get_creatives_by_account(self, mock_client):
        creatives = mock_client.get_creatives(account_id="act_test123")
        assert len(creatives) == 12

    def test_get_creative_exists(self, mock_client):
        cr = mock_client.get_creative("cr_as_c_act_test123_1_1_1")
        assert cr.creative_id == "cr_as_c_act_test123_1_1_1"
        assert cr.is_video is True

    def test_get_creative_not_found(self, mock_client):
        with pytest.raises(MetaDataNotFoundError):
            mock_client.get_creative("nonexistent")


class TestMetaAdsClientInsights:
    """MetaAdsClient 洞察数据测试."""

    def test_get_campaign_insights(self, mock_client):
        insights = mock_client.get_campaign_insights()
        assert len(insights) > 0
        assert all(isinstance(p, MetaPerformance) for p in insights)

    def test_get_campaign_insights_by_campaign(self, mock_client):
        insights = mock_client.get_campaign_insights(campaign_id="c_act_test123_1")
        assert len(insights) > 0
        for p in insights:
            assert p.campaign_id == "c_act_test123_1"

    def test_get_campaign_insights_date_range(self, mock_client):
        insights = mock_client.get_campaign_insights(
            date_from="2026-07-20",
            date_to="2026-07-22",
        )
        for p in insights:
            assert p.date_start >= "2026-07-20"
            assert p.date_stop <= "2026-07-22"

    def test_get_creative_insights(self, mock_client):
        insights = mock_client.get_creative_insights(creative_id="cr_as_c_act_test123_1_1_1")
        for p in insights:
            assert p.creative_id == "cr_as_c_act_test123_1_1_1"

    def test_get_adset_insights(self, mock_client):
        insights = mock_client.get_adset_insights(adset_id="as_c_act_test123_1_1")
        for p in insights:
            assert p.adset_id == "as_c_act_test123_1_1"

    def test_insights_have_metrics(self, mock_client):
        insights = mock_client.get_campaign_insights()
        perf = insights[0]
        assert perf.spend > 0
        assert perf.impressions > 0
        assert perf.clicks > 0
        assert perf.installs > 0

    def test_insights_have_actions(self, mock_client):
        insights = mock_client.get_campaign_insights()
        perf = insights[0]
        assert "mobile_app_install" in perf.actions
        assert perf.actions["mobile_app_install"] > 0


class TestMetaAdsClientPagination:
    """MetaAdsClient 分页测试."""

    def test_build_paginated_response_full(self, mock_client):
        data = [{"id": str(i)} for i in range(50)]
        resp = mock_client._build_paginated_response(data, page_size=25)
        assert resp.success is True
        assert len(resp.data) == 25
        assert resp.has_more is True

    def test_build_paginated_response_last_page(self, mock_client):
        data = [{"id": str(i)} for i in range(10)]
        resp = mock_client._build_paginated_response(data, page_size=25)
        assert len(resp.data) == 10
        assert resp.has_more is False

    def test_build_paginated_response_with_after(self, mock_client):
        data = [{"id": str(i)} for i in range(50)]
        resp = mock_client._build_paginated_response(data, page_size=25, after="25")
        assert len(resp.data) == 25
        assert resp.data[0]["id"] == "25"


class TestMetaAdsClientSummary:
    """MetaAdsClient get_summary 测试."""

    def test_get_summary(self, mock_client):
        summary = mock_client.get_summary()
        assert summary["connected"] is True
        assert summary["authenticated"] is False
        assert summary["use_mock"] is True
        assert summary["campaigns_count"] == 3
        assert summary["adsets_count"] == 6
        assert summary["creatives_count"] == 12
        assert summary["performances_count"] > 0


# ═══════════════════════════════════════════════════════════════
# 3. Metrics Mapper Tests (~40)
# ═══════════════════════════════════════════════════════════════


class TestMetaMetricsMapperFieldMapping:
    """MetaMetricsMapper 字段映射测试."""

    def test_map_insight_basic_fields(self, sample_raw_insight):
        perf = MetaMetricsMapper.map_insight(sample_raw_insight)
        assert perf.campaign_id == "c_test"
        assert perf.adset_id == "as_test"
        assert perf.creative_id == "cr_test"
        assert perf.date_start == "2026-07-20"
        assert perf.date_stop == "2026-07-20"

    def test_map_insight_spend(self, sample_raw_insight):
        perf = MetaMetricsMapper.map_insight(sample_raw_insight)
        assert perf.spend == 500.0

    def test_map_insight_impressions(self, sample_raw_insight):
        perf = MetaMetricsMapper.map_insight(sample_raw_insight)
        assert perf.impressions == 20000

    def test_map_insight_clicks(self, sample_raw_insight):
        perf = MetaMetricsMapper.map_insight(sample_raw_insight)
        assert perf.clicks == 500

    def test_map_insight_reach(self, sample_raw_insight):
        perf = MetaMetricsMapper.map_insight(sample_raw_insight)
        assert perf.reach == 18000

    def test_map_insight_frequency(self, sample_raw_insight):
        perf = MetaMetricsMapper.map_insight(sample_raw_insight)
        assert perf.frequency == 2.0

    def test_map_insight_cpm(self, sample_raw_insight):
        perf = MetaMetricsMapper.map_insight(sample_raw_insight)
        assert perf.cpm == 25.0

    def test_map_insight_cpc(self, sample_raw_insight):
        perf = MetaMetricsMapper.map_insight(sample_raw_insight)
        assert perf.cpc == 1.0

    def test_map_insight_ctr_preserved(self, sample_raw_insight):
        perf = MetaMetricsMapper.map_insight(sample_raw_insight)
        assert perf.ctr == 0.025


class TestMetaMetricsMapperActions:
    """MetaMetricsMapper actions 映射测试."""

    def test_map_installs(self, sample_raw_insight):
        perf = MetaMetricsMapper.map_insight(sample_raw_insight)
        assert perf.installs == 100

    def test_map_purchases(self, sample_raw_insight):
        perf = MetaMetricsMapper.map_insight(sample_raw_insight)
        assert perf.purchases == 10

    def test_actions_dict(self, sample_raw_insight):
        perf = MetaMetricsMapper.map_insight(sample_raw_insight)
        assert perf.actions["mobile_app_install"] == 100
        assert perf.actions["purchase"] == 10

    def test_action_values_revenue(self, sample_raw_insight):
        perf = MetaMetricsMapper.map_insight(sample_raw_insight)
        assert perf.revenue == 750.0

    def test_action_values_dict(self, sample_raw_insight):
        perf = MetaMetricsMapper.map_insight(sample_raw_insight)
        assert perf.action_values["purchase"] == 750.0

    def test_cost_per_action_cpi(self, sample_raw_insight):
        perf = MetaMetricsMapper.map_insight(sample_raw_insight)
        assert perf.cost_per_action_type["mobile_app_install"] == 5.0

    def test_cost_per_action_cpa(self, sample_raw_insight):
        perf = MetaMetricsMapper.map_insight(sample_raw_insight)
        assert perf.cpa == 50.0


class TestMetaMetricsMapperDerivedMetrics:
    """MetaMetricsMapper 派生指标计算测试."""

    def test_compute_ctr_from_clicks_and_impressions(self):
        raw = {"spend": 100, "impressions": 10000, "clicks": 200, "date_start": "2026-07-20", "date_stop": "2026-07-20"}
        perf = MetaMetricsMapper.map_insight(raw)
        assert perf.ctr == pytest.approx(0.02)

    def test_compute_cpm_from_spend(self):
        raw = {"spend": 100, "impressions": 50000, "date_start": "2026-07-20", "date_stop": "2026-07-20"}
        perf = MetaMetricsMapper.map_insight(raw)
        assert perf.cpm == pytest.approx(2.0)

    def test_compute_cpc_from_spend_and_clicks(self):
        raw = {"spend": 200, "clicks": 100, "date_start": "2026-07-20", "date_stop": "2026-07-20"}
        perf = MetaMetricsMapper.map_insight(raw)
        assert perf.cpc == pytest.approx(2.0)

    def test_compute_cpi_from_spend_and_installs(self):
        raw = {
            "spend": 500, "date_start": "2026-07-20", "date_stop": "2026-07-20",
            "actions": [{"action_type": "mobile_app_install", "value": 100}],
        }
        perf = MetaMetricsMapper.map_insight(raw)
        assert perf.cpi == pytest.approx(5.0)

    def test_compute_roas(self):
        raw = {
            "spend": 500, "date_start": "2026-07-20", "date_stop": "2026-07-20",
            "action_values": [{"action_type": "purchase", "value": 750}],
        }
        perf = MetaMetricsMapper.map_insight(raw)
        assert perf.roas == pytest.approx(1.5)

    def test_compute_cpa(self):
        raw = {
            "spend": 500, "date_start": "2026-07-20", "date_stop": "2026-07-20",
            "actions": [{"action_type": "purchase", "value": 10}],
        }
        perf = MetaMetricsMapper.map_insight(raw)
        assert perf.cpa == pytest.approx(50.0)

    def test_ctr_zero_when_no_impressions(self):
        raw = {"spend": 100, "date_start": "2026-07-20", "date_stop": "2026-07-20"}
        perf = MetaMetricsMapper.map_insight(raw)
        assert perf.ctr == 0.0

    def test_cpi_zero_when_no_installs(self):
        raw = {"spend": 100, "date_start": "2026-07-20", "date_stop": "2026-07-20"}
        perf = MetaMetricsMapper.map_insight(raw)
        assert perf.cpi == 0.0


class TestMetaMetricsMapperRanking:
    """MetaMetricsMapper ranking 字段测试."""

    def test_quality_ranking(self, sample_raw_insight):
        perf = MetaMetricsMapper.map_insight(sample_raw_insight)
        assert perf.quality_ranking == "above_average"

    def test_engagement_rate_ranking(self, sample_raw_insight):
        perf = MetaMetricsMapper.map_insight(sample_raw_insight)
        assert perf.engagement_rate_ranking == "average"

    def test_conversion_rate_ranking(self, sample_raw_insight):
        perf = MetaMetricsMapper.map_insight(sample_raw_insight)
        assert perf.conversion_rate_ranking == "above_average"


class TestMetaMetricsMapperBatch:
    """MetaMetricsMapper 批量映射测试."""

    def test_map_insights_batch(self, sample_raw_insight):
        results = MetaMetricsMapper.map_insights_batch([sample_raw_insight, sample_raw_insight])
        assert len(results) == 2
        assert all(isinstance(p, MetaPerformance) for p in results)

    def test_map_insights_batch_empty(self):
        results = MetaMetricsMapper.map_insights_batch([])
        assert results == []


class TestMetaMetricsMapperEdgeCases:
    """MetaMetricsMapper 边缘情况测试."""

    def test_empty_raw_data(self):
        perf = MetaMetricsMapper.map_insight({})
        assert perf.campaign_id == ""
        assert perf.spend == 0.0

    def test_null_values(self):
        raw = {
            "spend": None, "impressions": None, "clicks": None,
            "date_start": "2026-07-20", "date_stop": "2026-07-20",
        }
        perf = MetaMetricsMapper.map_insight(raw)
        assert perf.spend == 0.0

    def test_string_numeric_values(self):
        raw = {
            "spend": "123.45", "impressions": "10000",
            "date_start": "2026-07-20", "date_stop": "2026-07-20",
        }
        perf = MetaMetricsMapper.map_insight(raw)
        assert perf.spend == 123.45
        assert perf.impressions == 10000

    def test_omni_purchase_maps_to_purchases(self):
        raw = {
            "date_start": "2026-07-20", "date_stop": "2026-07-20",
            "actions": [{"action_type": "omni_purchase", "value": "5"}],
        }
        perf = MetaMetricsMapper.map_insight(raw)
        assert perf.purchases == 5

    def test_social_fields(self):
        raw = {
            "social_spend": "50.0", "social_impressions": "5000",
            "date_start": "2026-07-20", "date_stop": "2026-07-20",
        }
        perf = MetaMetricsMapper.map_insight(raw)
        assert perf.social_spend == 50.0
        assert perf.social_impressions == 5000

    def test_app_custom_event_action(self):
        raw = {
            "date_start": "2026-07-20", "date_stop": "2026-07-20",
            "actions": [{"action_type": "app_custom_event", "value": "20"}],
        }
        perf = MetaMetricsMapper.map_insight(raw)
        assert perf.actions["app_custom_event"] == 20


# ═══════════════════════════════════════════════════════════════
# 4. Validator Tests (~30)
# ═══════════════════════════════════════════════════════════════


class TestValidationResult:
    """ValidationResult 测试."""

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
        assert result.is_valid is True  # warning doesn't invalidate
        assert len(result.warnings) == 1

    def test_to_dict(self):
        result = ValidationResult()
        result.add_error("err1")
        result.add_warning("warn1")
        d = result.to_dict()
        assert d["is_valid"] is False
        assert d["error_count"] == 1
        assert d["warning_count"] == 1


class TestMetaPerformanceValidator:
    """MetaPerformanceValidator 测试."""

    def test_valid_performance(self, sample_performance):
        result = MetaPerformanceValidator.validate(sample_performance)
        assert result.is_valid is True

    def test_missing_date_start(self):
        perf = MetaPerformance(spend=100)
        result = MetaPerformanceValidator.validate(perf)
        assert result.is_valid is False
        assert any("date_start" in e for e in result.errors)

    def test_missing_date_stop(self):
        perf = MetaPerformance(spend=100, date_start="2026-07-20")
        result = MetaPerformanceValidator.validate(perf)
        assert result.is_valid is False
        assert any("date_stop" in e for e in result.errors)

    def test_negative_spend(self):
        perf = MetaPerformance(spend=-10, date_start="2026-07-20", date_stop="2026-07-20")
        result = MetaPerformanceValidator.validate(perf)
        assert result.is_valid is False
        assert any("spend" in e for e in result.errors)

    def test_negative_roas(self):
        perf = MetaPerformance(spend=100, roas=-1.0, date_start="2026-07-20", date_stop="2026-07-20")
        result = MetaPerformanceValidator.validate(perf)
        assert result.is_valid is False
        assert any("roas" in e for e in result.errors)

    def test_high_roas_warning(self):
        perf = MetaPerformance(spend=100, roas=150.0, date_start="2026-07-20", date_stop="2026-07-20")
        result = MetaPerformanceValidator.validate(perf)
        assert result.is_valid is True
        assert any("roas" in w for w in result.warnings)

    def test_negative_ctr(self):
        perf = MetaPerformance(ctr=-0.1, date_start="2026-07-20", date_stop="2026-07-20")
        result = MetaPerformanceValidator.validate(perf)
        assert result.is_valid is False
        assert any("ctr" in e for e in result.errors)

    def test_high_ctr_warning(self):
        perf = MetaPerformance(ctr=1.5, date_start="2026-07-20", date_stop="2026-07-20")
        result = MetaPerformanceValidator.validate(perf)
        assert result.is_valid is True
        assert any("ctr" in w for w in result.warnings)

    def test_negative_impressions(self):
        perf = MetaPerformance(impressions=-100, date_start="2026-07-20", date_stop="2026-07-20")
        result = MetaPerformanceValidator.validate(perf)
        assert result.is_valid is False
        assert any("impressions" in e for e in result.errors)

    def test_negative_clicks(self):
        perf = MetaPerformance(clicks=-10, date_start="2026-07-20", date_stop="2026-07-20")
        result = MetaPerformanceValidator.validate(perf)
        assert result.is_valid is False
        assert any("clicks" in e for e in result.errors)

    def test_clicks_exceed_impressions(self):
        perf = MetaPerformance(clicks=100, impressions=50, date_start="2026-07-20", date_stop="2026-07-20")
        result = MetaPerformanceValidator.validate(perf)
        assert any("clicks" in w for w in result.warnings)

    def test_negative_installs(self):
        perf = MetaPerformance(installs=-5, date_start="2026-07-20", date_stop="2026-07-20")
        result = MetaPerformanceValidator.validate(perf)
        assert result.is_valid is False
        assert any("installs" in e for e in result.errors)

    def test_installs_exceed_clicks(self):
        perf = MetaPerformance(clicks=10, installs=20, date_start="2026-07-20", date_stop="2026-07-20")
        result = MetaPerformanceValidator.validate(perf)
        assert any("installs" in w for w in result.warnings)

    def test_negative_frequency(self):
        perf = MetaPerformance(frequency=-1.0, date_start="2026-07-20", date_stop="2026-07-20")
        result = MetaPerformanceValidator.validate(perf)
        assert result.is_valid is False
        assert any("frequency" in e for e in result.errors)

    def test_negative_cpm(self):
        perf = MetaPerformance(cpm=-5.0, date_start="2026-07-20", date_stop="2026-07-20")
        result = MetaPerformanceValidator.validate(perf)
        assert result.is_valid is False
        assert any("cpm" in e for e in result.errors)

    def test_negative_cpi(self):
        perf = MetaPerformance(cpi=-1.0, date_start="2026-07-20", date_stop="2026-07-20")
        result = MetaPerformanceValidator.validate(perf)
        assert result.is_valid is False
        assert any("cpi" in e for e in result.errors)

    def test_validate_batch(self):
        perfs = [
            MetaPerformance(spend=100, date_start="2026-07-20", date_stop="2026-07-20"),
            MetaPerformance(spend=200, date_start="2026-07-21", date_stop="2026-07-21"),
        ]
        results = MetaPerformanceValidator.validate_batch(perfs)
        assert len(results) == 2
        assert all(r.is_valid for r in results)

    def test_validate_or_raise_valid(self, sample_performance):
        MetaPerformanceValidator.validate_or_raise(sample_performance)  # no exception

    def test_validate_or_raise_invalid(self):
        perf = MetaPerformance(spend=-10, date_start="2026-07-20", date_stop="2026-07-20")
        with pytest.raises(MetaValidationError):
            MetaPerformanceValidator.validate_or_raise(perf)


class TestMetaCampaignValidator:
    """MetaCampaignValidator 测试."""

    def test_valid_campaign(self):
        camp = MetaCampaign(campaign_id="c_1", name="Test", daily_budget=100)
        result = MetaCampaignValidator.validate(camp)
        assert result.is_valid is True

    def test_missing_campaign_id(self):
        camp = MetaCampaign(name="Test")
        result = MetaCampaignValidator.validate(camp)
        assert result.is_valid is False
        assert any("campaign_id" in e for e in result.errors)

    def test_missing_name(self):
        camp = MetaCampaign(campaign_id="c_1")
        result = MetaCampaignValidator.validate(camp)
        assert result.is_valid is False
        assert any("name" in e for e in result.errors)

    def test_negative_daily_budget(self):
        camp = MetaCampaign(campaign_id="c_1", name="Test", daily_budget=-100)
        result = MetaCampaignValidator.validate(camp)
        assert result.is_valid is False
        assert any("daily_budget" in e for e in result.errors)

    def test_negative_lifetime_budget(self):
        camp = MetaCampaign(campaign_id="c_1", name="Test", lifetime_budget=-500)
        result = MetaCampaignValidator.validate(camp)
        assert result.is_valid is False
        assert any("lifetime_budget" in e for e in result.errors)


class TestMetaAccountValidator:
    """MetaAccountValidator 测试."""

    def test_valid_account(self):
        acc = MetaAccount(account_id="act_1", name="Test")
        result = MetaAccountValidator.validate(acc)
        assert result.is_valid is True

    def test_missing_account_id(self):
        acc = MetaAccount(name="Test")
        result = MetaAccountValidator.validate(acc)
        assert result.is_valid is False

    def test_missing_name(self):
        acc = MetaAccount(account_id="act_1")
        result = MetaAccountValidator.validate(acc)
        assert result.is_valid is False

    def test_negative_balance_warning(self):
        acc = MetaAccount(account_id="act_1", name="Test", balance=-100)
        result = MetaAccountValidator.validate(acc)
        assert result.is_valid is True
        assert any("balance" in w for w in result.warnings)


class TestMetaCreativeValidator:
    """MetaCreativeValidator 测试."""

    def test_valid_creative(self):
        cr = MetaCreative(creative_id="cr_1", name="Test", video_url="https://example.com/v.mp4")
        result = MetaCreativeValidator.validate(cr)
        assert result.is_valid is True

    def test_missing_creative_id(self):
        cr = MetaCreative(name="Test")
        result = MetaCreativeValidator.validate(cr)
        assert result.is_valid is False

    def test_missing_name(self):
        cr = MetaCreative(creative_id="cr_1")
        result = MetaCreativeValidator.validate(cr)
        assert result.is_valid is False

    def test_no_media_url_warning(self):
        cr = MetaCreative(creative_id="cr_1", name="Test")
        result = MetaCreativeValidator.validate(cr)
        assert result.is_valid is True
        assert any("image_url" in w or "video_url" in w for w in result.warnings)


class TestCreativeFatigueValidator:
    """CreativeFatigueValidator 测试."""

    def test_valid_signal(self):
        signal = CreativeFatigueSignal(
            creative_id="cr_1",
            current_ctr=0.02,
            current_frequency=2.0,
            fatigue_score=0.5,
            fatigue_level="medium",
        )
        result = CreativeFatigueValidator.validate(signal)
        assert result.is_valid is True

    def test_missing_creative_id(self):
        signal = CreativeFatigueSignal(fatigue_level="low")
        result = CreativeFatigueValidator.validate(signal)
        assert result.is_valid is False

    def test_ctr_out_of_range(self):
        signal = CreativeFatigueSignal(creative_id="cr_1", current_ctr=1.5, fatigue_level="low")
        result = CreativeFatigueValidator.validate(signal)
        assert result.is_valid is False

    def test_negative_frequency(self):
        signal = CreativeFatigueSignal(creative_id="cr_1", current_frequency=-1.0, fatigue_level="low")
        result = CreativeFatigueValidator.validate(signal)
        assert result.is_valid is False

    def test_negative_fatigue_score(self):
        signal = CreativeFatigueSignal(creative_id="cr_1", fatigue_score=-0.1, fatigue_level="low")
        result = CreativeFatigueValidator.validate(signal)
        assert result.is_valid is False

    def test_invalid_fatigue_level(self):
        signal = CreativeFatigueSignal(creative_id="cr_1", fatigue_level="invalid")
        result = CreativeFatigueValidator.validate(signal)
        assert result.is_valid is False


class TestScalingOpportunityValidator:
    """ScalingOpportunityValidator 测试."""

    def test_valid_opportunity(self):
        opp = ScalingOpportunity(
            campaign_id="c_1",
            current_daily_budget=100,
            suggested_daily_budget=130,
            confidence=0.7,
        )
        result = ScalingOpportunityValidator.validate(opp)
        assert result.is_valid is True

    def test_missing_campaign_id(self):
        opp = ScalingOpportunity(confidence=0.7)
        result = ScalingOpportunityValidator.validate(opp)
        assert result.is_valid is False

    def test_negative_current_budget(self):
        opp = ScalingOpportunity(
            campaign_id="c_1",
            current_daily_budget=-100,
            suggested_daily_budget=130,
            confidence=0.7,
        )
        result = ScalingOpportunityValidator.validate(opp)
        assert result.is_valid is False

    def test_negative_suggested_budget(self):
        opp = ScalingOpportunity(
            campaign_id="c_1",
            suggested_daily_budget=-50,
            confidence=0.7,
        )
        result = ScalingOpportunityValidator.validate(opp)
        assert result.is_valid is False

    def test_confidence_out_of_range(self):
        opp = ScalingOpportunity(
            campaign_id="c_1",
            confidence=1.5,
        )
        result = ScalingOpportunityValidator.validate(opp)
        assert result.is_valid is False


# ═══════════════════════════════════════════════════════════════
# 5. Adapter Tests (~60)
# ═══════════════════════════════════════════════════════════════


class TestMetaAdsConnectorLifecycle:
    """MetaAdsConnector 生命周期测试."""

    def test_connect(self, connected_connector):
        assert connected_connector.is_connected is True

    def test_authenticate(self, connected_connector):
        assert connected_connector.is_authenticated is True

    def test_disconnect(self, connected_connector):
        connected_connector.disconnect()
        assert connected_connector.is_connected is False

    def test_health_check_healthy(self, connected_connector):
        health = connected_connector.health_check()
        assert health == ConnectorHealth.HEALTHY

    def test_health_check_unhealthy_before_connect(self):
        config = ConnectorConfig(connector_type=DataSource.META_ADS)
        connector = MetaAdsConnector(config)
        health = connector.health_check()
        assert health == ConnectorHealth.UNHEALTHY

    def test_name(self, connected_connector):
        assert connected_connector.name == "MetaAdsConnector"

    def test_source(self, connected_connector):
        assert connected_connector.source == DataSource.META_ADS


class TestMetaAdsConnectorSync:
    """MetaAdsConnector 同步测试."""

    def test_sync_campaigns(self, connected_connector):
        campaigns = connected_connector.sync_campaigns()
        assert len(campaigns) == 3
        assert all(isinstance(c, MetaCampaign) for c in campaigns)

    def test_sync_creatives(self, connected_connector):
        creatives = connected_connector.sync_creatives()
        assert len(creatives) == 12

    def test_sync_performance(self, connected_connector):
        perfs = connected_connector.sync_performance()
        assert len(perfs) > 0
        assert all(isinstance(p, MetaPerformance) for p in perfs)

    def test_sync_performance_date_range(self, connected_connector):
        perfs = connected_connector.sync_performance(
            date_from="2026-07-20",
            date_to="2026-07-22",
        )
        for p in perfs:
            assert p.date_start >= "2026-07-20"
            assert p.date_stop <= "2026-07-22"

    def test_sync_all(self, connected_connector):
        result = connected_connector.sync_all()
        assert result["accounts"] >= 0
        assert result["campaigns"] == 3
        assert result["creatives"] == 12
        assert result["performances"] > 0
        assert "last_sync_at" in result

    def test_sync_all_sets_last_sync_at(self, connected_connector):
        connected_connector.sync_all()
        assert connected_connector.last_sync_at != ""


class TestMetaAdsConnectorFetchCampaigns:
    """MetaAdsConnector fetch_campaigns 测试."""

    def test_fetch_campaigns(self, connected_connector):
        campaigns = connected_connector.fetch_campaigns(product_id="P04")
        assert len(campaigns) > 0
        assert all(isinstance(c, CampaignMetrics) for c in campaigns)
        for c in campaigns:
            assert c.platform == DataSource.META_ADS
            assert c.product_id == "P04"

    def test_fetch_campaigns_date_filter(self, connected_connector):
        campaigns = connected_connector.fetch_campaigns(
            product_id="P04",
            date_from="2026-07-20",
            date_to="2026-07-22",
        )
        for c in campaigns:
            assert c.date >= "2026-07-20"
            assert c.date <= "2026-07-22"

    def test_fetch_campaigns_has_metrics(self, connected_connector):
        campaigns = connected_connector.fetch_campaigns(product_id="P04")
        for c in campaigns:
            assert c.spend > 0
            assert c.impressions > 0
            assert c.installs > 0


class TestMetaAdsConnectorFetchCreatives:
    """MetaAdsConnector fetch_creatives 测试."""

    def test_fetch_creatives(self, connected_connector):
        creatives = connected_connector.fetch_creatives()
        assert len(creatives) > 0
        assert all(isinstance(c, CreativeMetrics) for c in creatives)
        for c in creatives:
            assert c.platform == DataSource.META_ADS

    def test_fetch_creatives_has_frequency(self, connected_connector):
        creatives = connected_connector.fetch_creatives()
        for c in creatives:
            assert c.frequency >= 0


class TestMetaAdsConnectorCollectEvents:
    """MetaAdsConnector collect_events 测试."""

    def test_collect_events(self, connected_connector):
        events = connected_connector.collect_events(product_id="P04")
        assert len(events) > 0
        assert all(isinstance(e, GrowthDataEvent) for e in events)

    def test_collect_events_source(self, connected_connector):
        events = connected_connector.collect_events(product_id="P04")
        for e in events:
            assert e.source == DataSource.META_ADS

    def test_collect_events_has_metrics(self, connected_connector):
        events = connected_connector.collect_events(product_id="P04")
        for e in events:
            assert "spend" in e.metrics
            assert "revenue" in e.metrics
            assert "roas" in e.metrics
            assert "impressions" in e.metrics
            assert "clicks" in e.metrics
            assert "installs" in e.metrics

    def test_collect_events_has_ids(self, connected_connector):
        events = connected_connector.collect_events(product_id="P04")
        for e in events:
            assert e.event_id != ""
            assert e.campaign_id != ""

    def test_collect_events_date_filter(self, connected_connector):
        events = connected_connector.collect_events(
            product_id="P04",
            date_from="2026-07-22",
            date_to="2026-07-24",
        )
        for e in events:
            assert e.date >= "2026-07-22"
            assert e.date <= "2026-07-24"


class TestMetaAdsConnectorFatigueDetection:
    """MetaAdsConnector 疲劳检测测试."""

    def test_detect_fatigue(self, connected_connector):
        signals = connected_connector.detect_fatigue()
        assert isinstance(signals, list)
        # With mock data, fatigue signals depend on period comparison
        for s in signals:
            assert isinstance(s, CreativeFatigueSignal)
            assert s.creative_id != ""

    def test_detect_fatigue_has_levels(self, connected_connector):
        signals = connected_connector.detect_fatigue()
        for s in signals:
            assert s.fatigue_level in ("low", "medium", "high", "critical")
            assert s.recommendation != ""

    def test_detect_fatigue_has_score(self, connected_connector):
        signals = connected_connector.detect_fatigue()
        for s in signals:
            assert 0.0 <= s.fatigue_score <= 1.0

    def test_fatigue_signals_property(self, connected_connector):
        connected_connector.detect_fatigue()
        signals = connected_connector.fatigue_signals
        assert isinstance(signals, list)


class TestMetaAdsConnectorScalingDetection:
    """MetaAdsConnector 扩量检测测试."""

    def test_detect_scaling_opportunities(self, connected_connector):
        opps = connected_connector.detect_scaling_opportunities()
        assert isinstance(opps, list)
        for o in opps:
            assert isinstance(o, ScalingOpportunity)
            assert o.campaign_id != ""

    def test_detect_scaling_with_custom_thresholds(self, connected_connector):
        opps = connected_connector.detect_scaling_opportunities(
            min_roas=1.0,
            min_impressions=100,
        )
        assert len(opps) > 0

    def test_detect_scaling_strict_thresholds(self, connected_connector):
        opps = connected_connector.detect_scaling_opportunities(
            min_roas=10.0,
            min_impressions=1000000,
        )
        assert len(opps) == 0

    def test_scaling_opportunity_has_budget(self, connected_connector):
        opps = connected_connector.detect_scaling_opportunities(min_roas=1.0)
        for o in opps:
            assert o.suggested_daily_budget > 0
            assert o.suggested_budget_increase_pct > 0
            assert 0.0 <= o.confidence <= 1.0

    def test_scaling_opportunities_property(self, connected_connector):
        connected_connector.detect_scaling_opportunities()
        opps = connected_connector.scaling_opportunities
        assert isinstance(opps, list)


class TestMetaAdsConnectorProperties:
    """MetaAdsConnector 属性测试."""

    def test_campaigns_property(self, connected_connector):
        connected_connector.sync_campaigns()
        camps = connected_connector.campaigns
        assert len(camps) == 3

    def test_performances_property(self, connected_connector):
        connected_connector.sync_performance()
        perfs = connected_connector.performances
        assert len(perfs) > 0

    def test_last_sync_at(self, connected_connector):
        assert connected_connector.last_sync_at == ""
        connected_connector.sync_all()
        assert connected_connector.last_sync_at != ""


class TestMetaAdsConnectorSummary:
    """MetaAdsConnector get_summary 测试."""

    def test_get_summary(self, connected_connector):
        connected_connector.sync_all()
        summary = connected_connector.get_summary()
        assert "client_summary" in summary
        assert "campaigns_count" in summary
        assert summary["campaigns_count"] == 3
        assert summary["creatives_count"] == 12
        assert summary["performances_count"] > 0


class TestMetaAdsConnectorEdgeCases:
    """MetaAdsConnector 边缘情况测试."""

    def test_sync_campaigns_filters_by_account(self):
        """Connector 按 account_id 过滤 campaigns."""
        config = ConnectorConfig(
            connector_type=DataSource.META_ADS,
            account_id="act_test123",
        )
        connector = MetaAdsConnector(config)
        connector.connect()
        connector.authenticate()
        campaigns = connector.sync_campaigns()
        assert len(campaigns) == 3
        for c in campaigns:
            assert c.account_id == "act_test123"

    def test_collect_events_date_range_outside_data(self, connected_connector):
        events = connected_connector.collect_events(
            product_id="P04",
            date_from="2020-01-01",
            date_to="2020-01-02",
        )
        assert len(events) == 0

    def test_health_check_degraded_without_auth(self):
        config = ConnectorConfig(connector_type=DataSource.META_ADS)
        connector = MetaAdsConnector(config)
        connector.connect()
        # Not authenticated
        health = connector.health_check()
        assert health == ConnectorHealth.DEGRADED

    def test_info_updated_after_connect(self):
        config = ConnectorConfig(connector_type=DataSource.META_ADS)
        connector = MetaAdsConnector(config)
        connector.connect()
        assert connector.info.status.value == "connected"


# ═══════════════════════════════════════════════════════════════
# 6. Integration Tests (~40)
# ═══════════════════════════════════════════════════════════════


class TestIntegrationDailySync:
    """集成测试: 每日同步场景."""

    def test_full_daily_sync_flow(self, connected_connector):
        """模拟每日 08:00 同步流程."""
        # Step 1: Sync all data
        result = connected_connector.sync_all()
        assert result["campaigns"] == 3
        assert result["creatives"] == 12
        assert result["performances"] > 0

        # Step 2: Collect events
        events = connected_connector.collect_events(product_id="P04")
        assert len(events) > 0

        # Step 3: Verify event structure
        for event in events:
            d = event.to_dict()
            assert "event_id" in d
            assert "event_type" in d
            assert "source" in d
            assert "metrics" in d

    def test_sync_to_event_pipeline(self, connected_connector):
        """验证 Sync → Event 数据管线."""
        connected_connector.sync_all()
        events = connected_connector.collect_events(product_id="P04")

        # Each performance should generate an event
        perfs = connected_connector.performances
        assert len(events) == len(perfs)

    def test_campaign_metrics_match_performance(self, connected_connector):
        """验证 CampaignMetrics 与 MetaPerformance 数据一致性."""
        connected_connector.sync_performance()
        perfs = connected_connector.performances

        campaigns = connected_connector.fetch_campaigns(product_id="P04")
        for cm in campaigns:
            matching = [p for p in perfs if p.campaign_id == cm.campaign_id and p.date_start == cm.date]
            if matching:
                p = matching[0]
                assert cm.spend == pytest.approx(p.spend)
                assert cm.impressions == p.impressions
                assert cm.clicks == p.clicks


class TestIntegrationCreativeFatigue:
    """集成测试: 创意疲劳场景."""

    def test_end_to_end_fatigue_flow(self, connected_connector):
        """模拟创意疲劳检测端到端流程."""
        # Sync data
        connected_connector.sync_all()

        # Detect fatigue
        signals = connected_connector.detect_fatigue()
        assert isinstance(signals, list)

        # Verify signal structure
        for signal in signals:
            # Each signal has a valid fatigue level
            assert signal.fatigue_level in ("low", "medium", "high", "critical")
            # Each signal has a recommendation
            assert signal.recommendation != ""
            # Each signal has a score
            assert 0.0 <= signal.fatigue_score <= 1.0

    def test_fatigue_signal_includes_ctr_change(self, connected_connector):
        """疲劳信号包含 CTR 变化."""
        connected_connector.sync_all()
        signals = connected_connector.detect_fatigue()
        for signal in signals:
            assert hasattr(signal, "ctr_change")
            assert hasattr(signal, "frequency_change")
            assert hasattr(signal, "cpm_change")

    def test_fatigue_level_recommendation_mapping(self, connected_connector):
        """疲劳等级与建议映射关系."""
        connected_connector.sync_all()
        signals = connected_connector.detect_fatigue()

        for signal in signals:
            if signal.fatigue_level == "low":
                assert "monitoring" in signal.recommendation.lower()
            elif signal.fatigue_level == "critical":
                assert "pause" in signal.recommendation.lower() or "immediately" in signal.recommendation.lower()


class TestIntegrationScalingOpportunity:
    """集成测试: 预算扩量场景."""

    def test_end_to_end_scaling_flow(self, connected_connector):
        """模拟预算扩量端到端流程."""
        connected_connector.sync_all()

        opps = connected_connector.detect_scaling_opportunities()
        for opp in opps:
            assert opp.campaign_id != ""
            assert opp.current_roas > 0
            assert opp.suggested_daily_budget > 0
            assert opp.confidence >= 0.0
            assert opp.reason != ""

    def test_scaling_opportunity_roas_threshold(self, connected_connector):
        """扩量机会 ROAS 阈值."""
        connected_connector.sync_all()

        # All opportunities should have ROAS >= threshold
        opps = connected_connector.detect_scaling_opportunities(min_roas=1.5)
        for opp in opps:
            assert opp.current_roas >= 1.5

    def test_viable_opportunities(self, connected_connector):
        """可执行的扩量机会."""
        connected_connector.sync_all()
        opps = connected_connector.detect_scaling_opportunities(min_roas=1.0, min_impressions=100)

        viable = [o for o in opps if o.is_viable]
        for o in viable:
            assert o.confidence > 0.5
            assert o.suggested_budget_increase_pct > 0


class TestIntegrationMapperToAdapter:
    """集成测试: Mapper → Adapter 数据链路."""

    def test_raw_insight_to_growth_event(self, sample_raw_insight):
        """验证 Raw Insight → MetaPerformance → GrowthDataEvent 链路."""
        # Map raw insight
        perf = MetaMetricsMapper.map_insight(sample_raw_insight)

        # Create GrowthDataEvent from performance
        event = GrowthDataEvent(
            event_type=MetricType.SPEND,
            source=DataSource.META_ADS,
            product_id="P04",
            date=perf.date_start,
            metrics={
                "spend": perf.spend,
                "revenue": perf.revenue,
                "roas": perf.roas,
                "impressions": perf.impressions,
                "clicks": perf.clicks,
                "installs": perf.installs,
            },
            campaign_id=perf.campaign_id,
        )

        assert event.metrics["spend"] == 500.0
        assert event.metrics["installs"] == 100
        assert event.metrics["roas"] == pytest.approx(1.5)

    def test_mapper_output_validates(self, sample_raw_insight):
        """Mapper 输出通过 Validator."""
        perf = MetaMetricsMapper.map_insight(sample_raw_insight)
        result = MetaPerformanceValidator.validate(perf)
        assert result.is_valid is True


class TestIntegrationConnectorToFramework:
    """集成测试: Connector → E13.1.1 Framework."""

    def test_connector_implements_base_interface(self, connected_connector):
        """验证 MetaAdsConnector 实现了 E13.1.1 BaseConnector 接口."""
        from market_ops.creative_vision_runtime.growth_runtime.connectors.base import BaseConnector
        assert isinstance(connected_connector, BaseConnector)

    def test_fetch_campaigns_returns_standard_format(self, connected_connector):
        """fetch_campaigns 返回 E13.1.1 标准 CampaignMetrics."""
        campaigns = connected_connector.fetch_campaigns(product_id="P04")
        assert len(campaigns) > 0
        for c in campaigns:
            assert isinstance(c, CampaignMetrics)
            d = c.to_dict()
            assert "campaign_id" in d
            assert "platform" in d
            assert "spend" in d

    def test_fetch_creatives_returns_standard_format(self, connected_connector):
        """fetch_creatives 返回 E13.1.1 标准 CreativeMetrics."""
        creatives = connected_connector.fetch_creatives()
        for c in creatives:
            assert isinstance(c, CreativeMetrics)
            d = c.to_dict()
            assert "creative_id" in d
            assert "frequency" in d

    def test_collect_events_returns_standard_format(self, connected_connector):
        """collect_events 返回 E13.1.1 标准 GrowthDataEvent."""
        events = connected_connector.collect_events(product_id="P04")
        for e in events:
            assert isinstance(e, GrowthDataEvent)
            d = e.to_dict()
            assert "event_id" in d
            assert "event_type" in d
            assert "source" in d
            assert "metrics" in d


class TestIntegrationEndToEnd:
    """端到端集成测试."""

    def test_full_meta_to_growth_os_pipeline(self, connected_connector):
        """完整 Meta Ads → Growth OS 数据管线."""
        # 1. Connect & authenticate
        assert connected_connector.is_connected
        assert connected_connector.is_authenticated

        # 2. Sync all data
        sync_result = connected_connector.sync_all()
        assert sync_result["campaigns"] > 0
        assert sync_result["performances"] > 0

        # 3. Fetch standardized campaigns
        campaigns = connected_connector.fetch_campaigns(product_id="P04")
        assert len(campaigns) > 0

        # 4. Collect Growth Events
        events = connected_connector.collect_events(product_id="P04")
        assert len(events) > 0

        # 5. Detect fatigue
        fatigue = connected_connector.detect_fatigue()
        assert isinstance(fatigue, list)

        # 6. Detect scaling opportunities
        scaling = connected_connector.detect_scaling_opportunities(min_roas=1.0, min_impressions=100)
        assert isinstance(scaling, list)

        # 7. Health check
        health = connected_connector.health_check()
        assert health == ConnectorHealth.HEALTHY

    def test_scenario_creative_fatigue_to_evolution(self, connected_connector):
        """场景: Creative Fatigue → E11 Creative Evolution."""
        # Simulate: detect fatigue, generate events for E11
        connected_connector.sync_all()
        fatigue_signals = connected_connector.detect_fatigue()

        # Generate Growth Events for fatigued creatives
        for signal in fatigue_signals:
            if signal.is_fatigued:
                event = GrowthDataEvent(
                    event_type=MetricType.CTR,
                    source=DataSource.META_ADS,
                    product_id="P04",
                    date=signal.date,
                    metrics={
                        "creative_id": signal.creative_id,
                        "fatigue_level": signal.fatigue_level,
                        "fatigue_score": signal.fatigue_score,
                        "ctr_change": signal.ctr_change,
                        "frequency_change": signal.frequency_change,
                        "recommendation": signal.recommendation,
                    },
                    creative_id=signal.creative_id,
                    campaign_id=signal.campaign_id,
                )
                assert event.metrics["fatigue_level"] in ("high", "critical")

    def test_scenario_budget_scaling_to_resource_controller(self, connected_connector):
        """场景: 预算扩量 → E12.6.2 Resource Controller."""
        connected_connector.sync_all()
        opportunities = connected_connector.detect_scaling_opportunities(
            min_roas=1.0,
            min_impressions=100,
        )

        # Generate events for viable opportunities
        for opp in opportunities:
            if opp.is_viable:
                event = GrowthDataEvent(
                    event_type=MetricType.ROAS,
                    source=DataSource.META_ADS,
                    product_id="P04",
                    date=opp.date,
                    metrics={
                        "campaign_id": opp.campaign_id,
                        "current_roas": opp.current_roas,
                        "suggested_budget": opp.suggested_daily_budget,
                        "budget_increase_pct": opp.suggested_budget_increase_pct,
                        "confidence": opp.confidence,
                    },
                    campaign_id=opp.campaign_id,
                )
                assert event.metrics["confidence"] > 0.5
                assert event.metrics["budget_increase_pct"] > 0


class TestIntegrationExceptions:
    """异常处理集成测试."""

    def test_exception_hierarchy(self):
        """验证异常继承关系."""
        assert issubclass(MetaAuthError, MetaAdsError)
        assert issubclass(MetaAPIError, MetaAdsError)
        assert issubclass(MetaRateLimitError, MetaAdsError)
        assert issubclass(MetaValidationError, MetaAdsError)
        assert issubclass(MetaDataNotFoundError, MetaAdsError)
        assert issubclass(MetaConnectionError, MetaAdsError)
        assert issubclass(MetaConfigError, MetaAdsError)

    def test_api_error_with_code(self):
        err = MetaAPIError("API error", error_code=400, error_type="OAuthException")
        assert err.error_code == 400
        assert err.error_type == "OAuthException"

    def test_rate_limit_error_with_retry(self):
        err = MetaRateLimitError("Rate limited", retry_after=120)
        assert err.retry_after == 120

    def test_connector_handles_connection_error(self):
        """Connector 优雅处理未连接错误."""
        config = ConnectorConfig(connector_type=DataSource.META_ADS)
        connector = MetaAdsConnector(config)
        # Don't connect, try to sync - should raise MetaConnectionError
        with pytest.raises(MetaConnectionError):
            connector.sync_campaigns()


class TestIntegrationEnums:
    """枚举值测试."""

    def test_meta_campaign_objective_values(self):
        assert MetaCampaignObjective.APP_INSTALLS.value == "APP_INSTALLS"
        assert MetaCampaignObjective.CONVERSIONS.value == "CONVERSIONS"
        assert MetaCampaignObjective.REACH.value == "REACH"

    def test_meta_campaign_status_values(self):
        assert MetaCampaignStatus.ACTIVE.value == "ACTIVE"
        assert MetaCampaignStatus.PAUSED.value == "PAUSED"

    def test_meta_account_status_values(self):
        assert MetaAccountStatus.ACTIVE.value == "ACTIVE"
        assert MetaAccountStatus.DISABLED.value == "DISABLED"

    def test_meta_insight_level_values(self):
        assert MetaInsightLevel.CAMPAIGN.value == "campaign"
        assert MetaInsightLevel.AD.value == "ad"

    def test_meta_insight_action_values(self):
        assert MetaInsightAction.MOBILE_APP_INSTALL.value == "mobile_app_install"
        assert MetaInsightAction.PURCHASE.value == "purchase"