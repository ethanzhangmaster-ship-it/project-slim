"""E15.0.2 Data Contract — UnifiedGrowthEvent / EventAggregator Tests."""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import pytest
from market_ops.creative_vision_runtime.growth_runtime.contracts import (
    UnifiedGrowthEvent,
    EventSource,
    EventType,
    EventAggregator,
)


# ═══════════════════════════════════════════════════════════════════
# EventSource Enum
# ═══════════════════════════════════════════════════════════════════


class TestEventSource:
    def test_meta_value(self):
        assert EventSource.META.value == "meta"

    def test_adjust_value(self):
        assert EventSource.ADJUST.value == "adjust"

    def test_max_value(self):
        assert EventSource.MAX.value == "max"

    def test_store_value(self):
        assert EventSource.STORE.value == "store"

    def test_internal_value(self):
        assert EventSource.INTERNAL.value == "internal"

    def test_str_representation(self):
        assert str(EventSource.META) == "EventSource.META"

    def test_enum_members_count(self):
        assert len(EventSource) == 5

    def test_from_string_meta(self):
        assert EventSource("meta") == EventSource.META

    def test_from_string_adjust(self):
        assert EventSource("adjust") == EventSource.ADJUST

    def test_from_string_max(self):
        assert EventSource("max") == EventSource.MAX

    def test_from_string_store(self):
        assert EventSource("store") == EventSource.STORE

    def test_from_string_internal(self):
        assert EventSource("internal") == EventSource.INTERNAL


# ═══════════════════════════════════════════════════════════════════
# EventType Enum
# ═══════════════════════════════════════════════════════════════════


class TestEventType:
    def test_install_value(self):
        assert EventType.INSTALL.value == "install"

    def test_purchase_value(self):
        assert EventType.PURCHASE.value == "purchase"

    def test_revenue_value(self):
        assert EventType.REVENUE.value == "revenue"

    def test_ad_spend_value(self):
        assert EventType.AD_SPEND.value == "ad_spend"

    def test_creative_result_value(self):
        assert EventType.CREATIVE_RESULT.value == "creative_result"

    def test_campaign_result_value(self):
        assert EventType.CAMPAIGN_RESULT.value == "campaign_result"

    def test_experiment_result_value(self):
        assert EventType.EXPERIMENT_RESULT.value == "experiment_result"

    def test_enum_members_count(self):
        assert len(EventType) == 7

    def test_from_string_install(self):
        assert EventType("install") == EventType.INSTALL

    def test_from_string_purchase(self):
        assert EventType("purchase") == EventType.PURCHASE

    def test_from_string_revenue(self):
        assert EventType("revenue") == EventType.REVENUE

    def test_from_string_ad_spend(self):
        assert EventType("ad_spend") == EventType.AD_SPEND

    def test_from_string_creative_result(self):
        assert EventType("creative_result") == EventType.CREATIVE_RESULT

    def test_from_string_campaign_result(self):
        assert EventType("campaign_result") == EventType.CAMPAIGN_RESULT

    def test_from_string_experiment_result(self):
        assert EventType("experiment_result") == EventType.EXPERIMENT_RESULT


# ═══════════════════════════════════════════════════════════════════
# UnifiedGrowthEvent — Creation
# ═══════════════════════════════════════════════════════════════════


class TestUnifiedGrowthEventCreation:
    def test_default_creation(self):
        event = UnifiedGrowthEvent()
        assert event.event_id.startswith("evt_")
        assert event.game_id == ""
        assert event.source == EventSource.INTERNAL
        assert event.event_type == EventType.AD_SPEND
        assert event.metrics == {}
        assert event.campaign_id == ""
        assert event.creative_id == ""
        assert event.platform == ""
        assert event.raw_data == {}
        assert event.metadata == {}

    def test_creation_with_fields(self):
        event = UnifiedGrowthEvent(
            game_id="P04",
            source=EventSource.META,
            event_type=EventType.CAMPAIGN_RESULT,
            campaign_id="camp_123",
            creative_id="cr_456",
            platform="facebook",
            metrics={"spend": 100.0, "revenue": 250.0},
        )
        assert event.game_id == "P04"
        assert event.source == EventSource.META
        assert event.event_type == EventType.CAMPAIGN_RESULT
        assert event.campaign_id == "camp_123"
        assert event.creative_id == "cr_456"
        assert event.platform == "facebook"
        assert event.metrics == {"spend": 100.0, "revenue": 250.0}

    def test_event_id_is_unique(self):
        e1 = UnifiedGrowthEvent()
        e2 = UnifiedGrowthEvent()
        assert e1.event_id != e2.event_id

    def test_event_id_prefix(self):
        event = UnifiedGrowthEvent()
        assert event.event_id.startswith("evt_")

    def test_event_id_length(self):
        event = UnifiedGrowthEvent()
        # evt_ + 12 hex chars
        assert len(event.event_id) == 16

    def test_timestamp_is_isoformat(self):
        event = UnifiedGrowthEvent()
        assert "T" in event.timestamp
        assert "+" in event.timestamp or "Z" in event.timestamp

    def test_creation_with_metadata(self):
        event = UnifiedGrowthEvent(
            game_id="P04",
            metadata={"env": "prod", "version": "1.0"},
        )
        assert event.metadata == {"env": "prod", "version": "1.0"}

    def test_creation_with_raw_data(self):
        event = UnifiedGrowthEvent(
            game_id="P04",
            raw_data={"api_response": {"status": "ok"}},
        )
        assert event.raw_data == {"api_response": {"status": "ok"}}


# ═══════════════════════════════════════════════════════════════════
# UnifiedGrowthEvent — Factory Methods
# ═══════════════════════════════════════════════════════════════════


class TestFromMetaInsight:
    def test_basic(self):
        event = UnifiedGrowthEvent.from_meta_insight(
            game_id="P04",
            campaign_id="camp_001",
            impressions=10000,
            clicks=500,
            spend=150.0,
            revenue=300.0,
            roas=2.0,
        )
        assert event.game_id == "P04"
        assert event.source == EventSource.META
        assert event.event_type == EventType.CAMPAIGN_RESULT
        assert event.campaign_id == "camp_001"
        assert event.platform == "facebook"
        assert event.metrics["impressions"] == 10000
        assert event.metrics["clicks"] == 500
        assert event.metrics["spend"] == 150.0
        assert event.metrics["revenue"] == 300.0
        assert event.metrics["roas"] == 2.0
        assert event.metrics["ctr"] == 0.05
        assert event.metrics["cpa"] == 0.3

    def test_ctr_with_zero_impressions(self):
        event = UnifiedGrowthEvent.from_meta_insight(
            game_id="P04",
            campaign_id="camp_001",
            impressions=0,
            clicks=0,
            spend=0.0,
            revenue=0.0,
            roas=0.0,
        )
        assert event.metrics["ctr"] == 0.0

    def test_cpa_with_zero_clicks(self):
        event = UnifiedGrowthEvent.from_meta_insight(
            game_id="P04",
            campaign_id="camp_001",
            impressions=1000,
            clicks=0,
            spend=100.0,
            revenue=0.0,
            roas=0.0,
        )
        assert event.metrics["cpa"] == 0.0

    def test_extra_kwargs_in_raw_data(self):
        event = UnifiedGrowthEvent.from_meta_insight(
            game_id="P04",
            campaign_id="camp_001",
            impressions=1000,
            clicks=100,
            spend=50.0,
            revenue=100.0,
            roas=2.0,
            extra_field="hello",
            another_field=42,
        )
        assert event.raw_data["extra_field"] == "hello"
        assert event.raw_data["another_field"] == 42

    def test_ctr_precision(self):
        event = UnifiedGrowthEvent.from_meta_insight(
            game_id="P04",
            campaign_id="camp_001",
            impressions=333,
            clicks=111,
            spend=50.0,
            revenue=100.0,
            roas=2.0,
        )
        assert event.metrics["ctr"] == pytest.approx(0.3333, rel=1e-3)


class TestFromAdjustInstall:
    def test_basic(self):
        event = UnifiedGrowthEvent.from_adjust_install(
            game_id="P04",
            installs=150,
            campaign_id="camp_002",
        )
        assert event.game_id == "P04"
        assert event.source == EventSource.ADJUST
        assert event.event_type == EventType.INSTALL
        assert event.campaign_id == "camp_002"
        assert event.platform == "adjust"
        assert event.metrics["installs"] == 150

    def test_without_campaign_id(self):
        event = UnifiedGrowthEvent.from_adjust_install(
            game_id="P04",
            installs=50,
        )
        assert event.campaign_id == ""
        assert event.metrics["installs"] == 50

    def test_extra_kwargs_in_raw_data(self):
        event = UnifiedGrowthEvent.from_adjust_install(
            game_id="P04",
            installs=10,
            campaign_id="camp_003",
            device_type="ios",
            country="US",
        )
        assert event.raw_data["device_type"] == "ios"
        assert event.raw_data["country"] == "US"

    def test_zero_installs(self):
        event = UnifiedGrowthEvent.from_adjust_install(
            game_id="P04",
            installs=0,
        )
        assert event.metrics["installs"] == 0


class TestFromAdjustRevenue:
    def test_basic(self):
        event = UnifiedGrowthEvent.from_adjust_revenue(
            game_id="P04",
            revenue=500.0,
            purchases=10,
            campaign_id="camp_004",
        )
        assert event.game_id == "P04"
        assert event.source == EventSource.ADJUST
        assert event.event_type == EventType.REVENUE
        assert event.campaign_id == "camp_004"
        assert event.platform == "adjust"
        assert event.metrics["revenue"] == 500.0
        assert event.metrics["purchases"] == 10
        assert event.metrics["arpu"] == 50.0

    def test_arpu_with_zero_purchases(self):
        event = UnifiedGrowthEvent.from_adjust_revenue(
            game_id="P04",
            revenue=100.0,
            purchases=0,
        )
        assert event.metrics["arpu"] == 0.0

    def test_without_campaign_id(self):
        event = UnifiedGrowthEvent.from_adjust_revenue(
            game_id="P04",
            revenue=200.0,
            purchases=5,
        )
        assert event.campaign_id == ""

    def test_extra_kwargs_in_raw_data(self):
        event = UnifiedGrowthEvent.from_adjust_revenue(
            game_id="P04",
            revenue=300.0,
            purchases=6,
            currency="USD",
            store="apple",
        )
        assert event.raw_data["currency"] == "USD"
        assert event.raw_data["store"] == "apple"

    def test_zero_revenue(self):
        event = UnifiedGrowthEvent.from_adjust_revenue(
            game_id="P04",
            revenue=0.0,
            purchases=0,
        )
        assert event.metrics["revenue"] == 0.0
        assert event.metrics["purchases"] == 0
        assert event.metrics["arpu"] == 0.0


class TestFromCreativeResult:
    def test_basic(self):
        event = UnifiedGrowthEvent.from_creative_result(
            game_id="P04",
            creative_id="cr_abc",
            campaign_id="camp_xyz",
            impressions=5000,
            clicks=200,
            spend=80.0,
            revenue=160.0,
        )
        assert event.game_id == "P04"
        assert event.source == EventSource.META
        assert event.event_type == EventType.CREATIVE_RESULT
        assert event.creative_id == "cr_abc"
        assert event.campaign_id == "camp_xyz"
        assert event.platform == "facebook"
        assert event.metrics["impressions"] == 5000
        assert event.metrics["clicks"] == 200
        assert event.metrics["spend"] == 80.0
        assert event.metrics["revenue"] == 160.0
        assert event.metrics["roas"] == 2.0
        assert event.metrics["ctr"] == 0.04

    def test_roas_with_zero_spend(self):
        event = UnifiedGrowthEvent.from_creative_result(
            game_id="P04",
            creative_id="cr_abc",
            campaign_id="camp_xyz",
            impressions=1000,
            clicks=50,
            spend=0.0,
            revenue=100.0,
        )
        assert event.metrics["roas"] == 0.0

    def test_ctr_with_zero_impressions(self):
        event = UnifiedGrowthEvent.from_creative_result(
            game_id="P04",
            creative_id="cr_abc",
            campaign_id="camp_xyz",
            impressions=0,
            clicks=0,
            spend=0.0,
            revenue=0.0,
        )
        assert event.metrics["ctr"] == 0.0

    def test_extra_kwargs_in_raw_data(self):
        event = UnifiedGrowthEvent.from_creative_result(
            game_id="P04",
            creative_id="cr_abc",
            campaign_id="camp_xyz",
            impressions=1000,
            clicks=100,
            spend=50.0,
            revenue=100.0,
            creative_name="video_01",
            ad_format="video",
        )
        assert event.raw_data["creative_name"] == "video_01"
        assert event.raw_data["ad_format"] == "video"


class TestFromAdSpend:
    def test_basic(self):
        event = UnifiedGrowthEvent.from_ad_spend(
            game_id="P04",
            spend=200.0,
            campaign_id="camp_005",
        )
        assert event.game_id == "P04"
        assert event.source == EventSource.META
        assert event.event_type == EventType.AD_SPEND
        assert event.campaign_id == "camp_005"
        assert event.metrics["spend"] == 200.0

    def test_without_campaign_id(self):
        event = UnifiedGrowthEvent.from_ad_spend(
            game_id="P04",
            spend=75.0,
        )
        assert event.campaign_id == ""

    def test_custom_source(self):
        event = UnifiedGrowthEvent.from_ad_spend(
            game_id="P04",
            spend=100.0,
            source=EventSource.MAX,
        )
        assert event.source == EventSource.MAX

    def test_extra_kwargs_in_raw_data(self):
        event = UnifiedGrowthEvent.from_ad_spend(
            game_id="P04",
            spend=50.0,
            campaign_id="camp_006",
            account_id="act_123",
        )
        assert event.raw_data["account_id"] == "act_123"

    def test_zero_spend(self):
        event = UnifiedGrowthEvent.from_ad_spend(
            game_id="P04",
            spend=0.0,
        )
        assert event.metrics["spend"] == 0.0


# ═══════════════════════════════════════════════════════════════════
# UnifiedGrowthEvent — Properties
# ═══════════════════════════════════════════════════════════════════


class TestProperties:
    def test_roas(self):
        event = UnifiedGrowthEvent(metrics={"roas": 3.5})
        assert event.roas == 3.5

    def test_roas_default_zero(self):
        event = UnifiedGrowthEvent()
        assert event.roas == 0.0

    def test_spend(self):
        event = UnifiedGrowthEvent(metrics={"spend": 150.0})
        assert event.spend == 150.0

    def test_spend_default_zero(self):
        event = UnifiedGrowthEvent()
        assert event.spend == 0.0

    def test_revenue(self):
        event = UnifiedGrowthEvent(metrics={"revenue": 300.0})
        assert event.revenue == 300.0

    def test_revenue_default_zero(self):
        event = UnifiedGrowthEvent()
        assert event.revenue == 0.0

    def test_impressions(self):
        event = UnifiedGrowthEvent(metrics={"impressions": 8000})
        assert event.impressions == 8000

    def test_impressions_default_zero(self):
        event = UnifiedGrowthEvent()
        assert event.impressions == 0

    def test_clicks(self):
        event = UnifiedGrowthEvent(metrics={"clicks": 300})
        assert event.clicks == 300

    def test_clicks_default_zero(self):
        event = UnifiedGrowthEvent()
        assert event.clicks == 0

    def test_ctr(self):
        event = UnifiedGrowthEvent(metrics={"ctr": 0.05})
        assert event.ctr == 0.05

    def test_ctr_default_zero(self):
        event = UnifiedGrowthEvent()
        assert event.ctr == 0.0

    def test_installs(self):
        event = UnifiedGrowthEvent(metrics={"installs": 120})
        assert event.installs == 120

    def test_installs_default_zero(self):
        event = UnifiedGrowthEvent()
        assert event.installs == 0

    def test_has_creative_data_true(self):
        event = UnifiedGrowthEvent(creative_id="cr_123")
        assert event.has_creative_data is True

    def test_has_creative_data_false(self):
        event = UnifiedGrowthEvent()
        assert event.has_creative_data is False

    def test_has_creative_data_empty_string(self):
        event = UnifiedGrowthEvent(creative_id="")
        assert event.has_creative_data is False

    def test_has_campaign_data_true(self):
        event = UnifiedGrowthEvent(campaign_id="camp_123")
        assert event.has_campaign_data is True

    def test_has_campaign_data_false(self):
        event = UnifiedGrowthEvent()
        assert event.has_campaign_data is False

    def test_has_campaign_data_empty_string(self):
        event = UnifiedGrowthEvent(campaign_id="")
        assert event.has_campaign_data is False


# ═══════════════════════════════════════════════════════════════════
# UnifiedGrowthEvent — Validation
# ═══════════════════════════════════════════════════════════════════


class TestValidation:
    def test_valid_event(self):
        event = UnifiedGrowthEvent(
            game_id="P04",
            event_type=EventType.CAMPAIGN_RESULT,
            metrics={"spend": 100.0},
        )
        assert event.is_valid() is True
        assert event.validate() == []

    def test_missing_game_id(self):
        event = UnifiedGrowthEvent(
            game_id="",
            event_type=EventType.INSTALL,
            metrics={"installs": 10},
        )
        errors = event.validate()
        assert "game_id is required" in errors
        assert event.is_valid() is False

    def test_missing_event_type(self):
        event = UnifiedGrowthEvent(
            game_id="P04",
            event_type="",  # type: ignore
            metrics={"spend": 50.0},
        )
        errors = event.validate()
        assert "event_type is required" in errors
        assert event.is_valid() is False

    def test_empty_metrics(self):
        event = UnifiedGrowthEvent(
            game_id="P04",
            event_type=EventType.AD_SPEND,
            metrics={},
        )
        errors = event.validate()
        assert "metrics cannot be empty" in errors
        assert event.is_valid() is False

    def test_multiple_errors(self):
        event = UnifiedGrowthEvent(
            game_id="",
            event_type="",  # type: ignore
            metrics={},
        )
        errors = event.validate()
        assert len(errors) == 3
        assert "game_id is required" in errors
        assert "event_type is required" in errors
        assert "metrics cannot be empty" in errors

    def test_is_valid_true(self):
        event = UnifiedGrowthEvent(
            game_id="game",
            event_type=EventType.REVENUE,
            metrics={"revenue": 1.0},
        )
        assert event.is_valid() is True

    def test_is_valid_false_on_empty_game_id(self):
        event = UnifiedGrowthEvent(
            game_id="",
            event_type=EventType.REVENUE,
            metrics={"revenue": 1.0},
        )
        assert event.is_valid() is False

    def test_is_valid_false_on_empty_metrics(self):
        event = UnifiedGrowthEvent(
            game_id="game",
            event_type=EventType.REVENUE,
            metrics={},
        )
        assert event.is_valid() is False


# ═══════════════════════════════════════════════════════════════════
# UnifiedGrowthEvent — Serialization
# ═══════════════════════════════════════════════════════════════════


class TestToDict:
    def test_basic(self):
        event = UnifiedGrowthEvent(
            game_id="P04",
            source=EventSource.META,
            event_type=EventType.CAMPAIGN_RESULT,
            campaign_id="camp_001",
            creative_id="cr_001",
            platform="facebook",
            metrics={"spend": 100.0, "revenue": 200.0},
            metadata={"key": "val"},
        )
        d = event.to_dict()
        assert d["game_id"] == "P04"
        assert d["source"] == "meta"
        assert d["event_type"] == "campaign_result"
        assert d["campaign_id"] == "camp_001"
        assert d["creative_id"] == "cr_001"
        assert d["platform"] == "facebook"
        assert d["metrics"] == {"spend": 100.0, "revenue": 200.0}
        assert d["metadata"] == {"key": "val"}
        assert "event_id" in d
        assert "timestamp" in d

    def test_default_event(self):
        event = UnifiedGrowthEvent()
        d = event.to_dict()
        assert d["game_id"] == ""
        assert d["source"] == "internal"
        assert d["event_type"] == "ad_spend"
        assert d["metrics"] == {}
        assert d["campaign_id"] == ""
        assert d["creative_id"] == ""
        assert d["platform"] == ""
        assert d["metadata"] == {}

    def test_source_is_string_value(self):
        event = UnifiedGrowthEvent(source=EventSource.ADJUST)
        d = event.to_dict()
        assert d["source"] == "adjust"
        assert isinstance(d["source"], str)

    def test_event_type_is_string_value(self):
        event = UnifiedGrowthEvent(event_type=EventType.INSTALL)
        d = event.to_dict()
        assert d["event_type"] == "install"
        assert isinstance(d["event_type"], str)

    def test_does_not_include_raw_data(self):
        event = UnifiedGrowthEvent(raw_data={"secret": "xxx"})
        d = event.to_dict()
        assert "raw_data" not in d


class TestToAgentInput:
    def test_basic(self):
        event = UnifiedGrowthEvent(
            game_id="P04",
            source=EventSource.META,
            event_type=EventType.CREATIVE_RESULT,
            campaign_id="camp_001",
            creative_id="cr_001",
            metrics={"spend": 100.0, "revenue": 200.0},
        )
        d = event.to_agent_input()
        assert d["game_id"] == "P04"
        assert d["source"] == "meta"
        assert d["event_type"] == "creative_result"
        assert d["campaign_id"] == "camp_001"
        assert d["creative_id"] == "cr_001"
        assert d["metrics"] == {"spend": 100.0, "revenue": 200.0}
        assert "timestamp" in d

    def test_no_event_id_in_output(self):
        event = UnifiedGrowthEvent(game_id="P04")
        d = event.to_agent_input()
        assert "event_id" not in d

    def test_no_platform_in_output(self):
        event = UnifiedGrowthEvent(game_id="P04", platform="facebook")
        d = event.to_agent_input()
        assert "platform" not in d

    def test_no_metadata_in_output(self):
        event = UnifiedGrowthEvent(game_id="P04", metadata={"k": "v"})
        d = event.to_agent_input()
        assert "metadata" not in d

    def test_no_raw_data_in_output(self):
        event = UnifiedGrowthEvent(game_id="P04", raw_data={"k": "v"})
        d = event.to_agent_input()
        assert "raw_data" not in d

    def test_source_is_string_value(self):
        event = UnifiedGrowthEvent(
            game_id="P04", source=EventSource.ADJUST
        )
        d = event.to_agent_input()
        assert d["source"] == "adjust"

    def test_event_type_is_string_value(self):
        event = UnifiedGrowthEvent(
            game_id="P04", event_type=EventType.REVENUE
        )
        d = event.to_agent_input()
        assert d["event_type"] == "revenue"


# ═══════════════════════════════════════════════════════════════════
# EventAggregator
# ═══════════════════════════════════════════════════════════════════


class TestEventAggregator:
    def test_aggregate_empty_list(self):
        agg = EventAggregator()
        result = agg.aggregate([], game_id="P04")
        assert result["game_id"] == "P04"
        assert result["event_count"] == 0

    def test_aggregate_empty_list_default_game_id(self):
        agg = EventAggregator()
        result = agg.aggregate([])
        assert result["game_id"] == ""
        assert result["event_count"] == 0

    def test_aggregate_single_event(self):
        agg = EventAggregator()
        event = UnifiedGrowthEvent(
            game_id="P04",
            source=EventSource.META,
            event_type=EventType.CAMPAIGN_RESULT,
            campaign_id="camp_001",
            metrics={"spend": 100.0, "revenue": 200.0, "impressions": 1000, "clicks": 50, "installs": 10},
        )
        result = agg.aggregate([event], game_id="P04")
        assert result["game_id"] == "P04"
        assert result["event_count"] == 1
        assert result["total_spend"] == 100.0
        assert result["total_revenue"] == 200.0
        assert result["total_installs"] == 10
        assert result["total_impressions"] == 1000
        assert result["total_clicks"] == 50
        assert result["roas"] == 2.0
        assert result["ctr"] == 0.05

    def test_aggregate_multiple_events(self):
        agg = EventAggregator()
        e1 = UnifiedGrowthEvent(
            game_id="P04",
            source=EventSource.META,
            event_type=EventType.CAMPAIGN_RESULT,
            campaign_id="camp_001",
            metrics={"spend": 100.0, "revenue": 200.0, "installs": 5},
        )
        e2 = UnifiedGrowthEvent(
            game_id="P04",
            source=EventSource.META,
            event_type=EventType.CAMPAIGN_RESULT,
            campaign_id="camp_001",
            metrics={"spend": 50.0, "revenue": 100.0, "installs": 3},
        )
        result = agg.aggregate([e1, e2], game_id="P04")
        assert result["event_count"] == 2
        assert result["total_spend"] == 150.0
        assert result["total_revenue"] == 300.0
        assert result["total_installs"] == 8

    def test_aggregate_roas_zero_spend(self):
        agg = EventAggregator()
        event = UnifiedGrowthEvent(
            game_id="P04",
            metrics={"spend": 0.0, "revenue": 100.0},
        )
        result = agg.aggregate([event], game_id="P04")
        assert result["roas"] == 0.0

    def test_aggregate_ctr_zero_impressions(self):
        agg = EventAggregator()
        event = UnifiedGrowthEvent(
            game_id="P04",
            metrics={"impressions": 0, "clicks": 0},
        )
        result = agg.aggregate([event], game_id="P04")
        assert result["ctr"] == 0.0

    def test_aggregate_by_source(self):
        agg = EventAggregator()
        e1 = UnifiedGrowthEvent(
            game_id="P04",
            source=EventSource.META,
            event_type=EventType.CAMPAIGN_RESULT,
            campaign_id="camp_001",
            metrics={"spend": 100.0},
        )
        e2 = UnifiedGrowthEvent(
            game_id="P04",
            source=EventSource.ADJUST,
            event_type=EventType.INSTALL,
            metrics={"installs": 10},
        )
        e3 = UnifiedGrowthEvent(
            game_id="P04",
            source=EventSource.META,
            event_type=EventType.CREATIVE_RESULT,
            campaign_id="camp_001",
            creative_id="cr_001",
            metrics={"spend": 50.0},
        )
        result = agg.aggregate([e1, e2, e3], game_id="P04")
        assert result["by_source"] == {"meta": 2, "adjust": 1}

    def test_aggregate_by_type(self):
        agg = EventAggregator()
        e1 = UnifiedGrowthEvent(
            game_id="P04",
            source=EventSource.ADJUST,
            event_type=EventType.INSTALL,
            metrics={"installs": 10},
        )
        e2 = UnifiedGrowthEvent(
            game_id="P04",
            source=EventSource.ADJUST,
            event_type=EventType.INSTALL,
            metrics={"installs": 5},
        )
        e3 = UnifiedGrowthEvent(
            game_id="P04",
            source=EventSource.ADJUST,
            event_type=EventType.REVENUE,
            metrics={"revenue": 100.0},
        )
        result = agg.aggregate([e1, e2, e3], game_id="P04")
        assert result["by_type"] == {"install": 2, "revenue": 1}

    def test_aggregate_campaigns(self):
        agg = EventAggregator()
        e1 = UnifiedGrowthEvent(
            game_id="P04",
            source=EventSource.META,
            event_type=EventType.CAMPAIGN_RESULT,
            campaign_id="camp_001",
            metrics={"spend": 100.0, "revenue": 200.0, "installs": 5},
        )
        e2 = UnifiedGrowthEvent(
            game_id="P04",
            source=EventSource.META,
            event_type=EventType.CAMPAIGN_RESULT,
            campaign_id="camp_002",
            metrics={"spend": 50.0, "revenue": 75.0, "installs": 3},
        )
        e3 = UnifiedGrowthEvent(
            game_id="P04",
            source=EventSource.META,
            event_type=EventType.CAMPAIGN_RESULT,
            campaign_id="camp_001",
            metrics={"spend": 30.0, "revenue": 60.0, "installs": 2},
        )
        result = agg.aggregate([e1, e2, e3], game_id="P04")
        campaigns = result["campaigns"]
        assert len(campaigns) == 2
        assert campaigns["camp_001"]["spend"] == 130.0
        assert campaigns["camp_001"]["revenue"] == 260.0
        assert campaigns["camp_001"]["installs"] == 7
        assert campaigns["camp_002"]["spend"] == 50.0
        assert campaigns["camp_002"]["revenue"] == 75.0
        assert campaigns["camp_002"]["installs"] == 3

    def test_aggregate_creatives(self):
        agg = EventAggregator()
        e1 = UnifiedGrowthEvent(
            game_id="P04",
            source=EventSource.META,
            event_type=EventType.CREATIVE_RESULT,
            campaign_id="camp_001",
            creative_id="cr_001",
            metrics={"spend": 100.0, "revenue": 200.0, "impressions": 1000},
        )
        e2 = UnifiedGrowthEvent(
            game_id="P04",
            source=EventSource.META,
            event_type=EventType.CREATIVE_RESULT,
            campaign_id="camp_001",
            creative_id="cr_001",
            metrics={"spend": 50.0, "revenue": 100.0, "impressions": 500},
        )
        e3 = UnifiedGrowthEvent(
            game_id="P04",
            source=EventSource.META,
            event_type=EventType.CREATIVE_RESULT,
            campaign_id="camp_001",
            creative_id="cr_002",
            metrics={"spend": 30.0, "revenue": 50.0, "impressions": 300},
        )
        result = agg.aggregate([e1, e2, e3], game_id="P04")
        creatives = result["creatives"]
        assert len(creatives) == 2
        assert creatives["cr_001"]["spend"] == 150.0
        assert creatives["cr_001"]["revenue"] == 300.0
        assert creatives["cr_001"]["impressions"] == 1500
        assert creatives["cr_002"]["spend"] == 30.0
        assert creatives["cr_002"]["revenue"] == 50.0
        assert creatives["cr_002"]["impressions"] == 300

    def test_aggregate_skips_events_without_campaign_id(self):
        agg = EventAggregator()
        e1 = UnifiedGrowthEvent(
            game_id="P04",
            source=EventSource.META,
            event_type=EventType.CAMPAIGN_RESULT,
            campaign_id="camp_001",
            metrics={"spend": 100.0},
        )
        e2 = UnifiedGrowthEvent(
            game_id="P04",
            source=EventSource.ADJUST,
            event_type=EventType.INSTALL,
            metrics={"installs": 10},
        )
        result = agg.aggregate([e1, e2], game_id="P04")
        campaigns = result["campaigns"]
        assert "camp_001" in campaigns
        assert len(campaigns) == 1

    def test_aggregate_skips_events_without_creative_id(self):
        agg = EventAggregator()
        e1 = UnifiedGrowthEvent(
            game_id="P04",
            source=EventSource.META,
            event_type=EventType.CREATIVE_RESULT,
            campaign_id="camp_001",
            creative_id="cr_001",
            metrics={"spend": 50.0},
        )
        e2 = UnifiedGrowthEvent(
            game_id="P04",
            source=EventSource.META,
            event_type=EventType.CAMPAIGN_RESULT,
            campaign_id="camp_001",
            metrics={"spend": 30.0},
        )
        result = agg.aggregate([e1, e2], game_id="P04")
        creatives = result["creatives"]
        assert "cr_001" in creatives
        assert len(creatives) == 1

    def test_aggregate_rounds_totals(self):
        agg = EventAggregator()
        event = UnifiedGrowthEvent(
            game_id="P04",
            metrics={"spend": 100.123, "revenue": 200.456},
        )
        result = agg.aggregate([event], game_id="P04")
        assert result["total_spend"] == 100.12
        assert result["total_revenue"] == 200.46

    def test_aggregate_roas_rounding(self):
        agg = EventAggregator()
        event = UnifiedGrowthEvent(
            game_id="P04",
            metrics={"spend": 3.0, "revenue": 10.0},
        )
        result = agg.aggregate([event], game_id="P04")
        assert result["roas"] == pytest.approx(3.3333, rel=1e-3)

    def test_aggregate_ctr_rounding(self):
        agg = EventAggregator()
        event = UnifiedGrowthEvent(
            game_id="P04",
            metrics={"impressions": 3, "clicks": 1},
        )
        result = agg.aggregate([event], game_id="P04")
        assert result["ctr"] == pytest.approx(0.3333, rel=1e-3)

    def test_aggregate_mixed_sources_and_types(self):
        agg = EventAggregator()
        events = [
            UnifiedGrowthEvent(
                game_id="P04",
                source=EventSource.META,
                event_type=EventType.CAMPAIGN_RESULT,
                campaign_id="camp_a",
                metrics={"spend": 100.0, "revenue": 200.0, "installs": 5},
            ),
            UnifiedGrowthEvent(
                game_id="P04",
                source=EventSource.ADJUST,
                event_type=EventType.INSTALL,
                campaign_id="camp_a",
                metrics={"installs": 10},
            ),
            UnifiedGrowthEvent(
                game_id="P04",
                source=EventSource.MAX,
                event_type=EventType.REVENUE,
                metrics={"revenue": 50.0},
            ),
            UnifiedGrowthEvent(
                game_id="P04",
                source=EventSource.META,
                event_type=EventType.CREATIVE_RESULT,
                campaign_id="camp_a",
                creative_id="cr_x",
                metrics={"spend": 30.0, "revenue": 60.0, "impressions": 500},
            ),
        ]
        result = agg.aggregate(events, game_id="P04")
        assert result["event_count"] == 4
        assert result["total_spend"] == 130.0
        assert result["total_revenue"] == 310.0
        assert result["total_installs"] == 15
        assert result["total_impressions"] == 500
        assert result["by_source"] == {"meta": 2, "adjust": 1, "max": 1}
        assert result["by_type"] == {
            "campaign_result": 1,
            "install": 1,
            "revenue": 1,
            "creative_result": 1,
        }
        assert len(result["campaigns"]) == 1
        assert len(result["creatives"]) == 1


# ═══════════════════════════════════════════════════════════════════
# Edge Cases
# ═══════════════════════════════════════════════════════════════════


class TestEdgeCases:
    def test_zero_spend_property(self):
        event = UnifiedGrowthEvent(metrics={"spend": 0.0})
        assert event.spend == 0.0

    def test_zero_impressions_property(self):
        event = UnifiedGrowthEvent(metrics={"impressions": 0})
        assert event.impressions == 0

    def test_zero_clicks_property(self):
        event = UnifiedGrowthEvent(metrics={"clicks": 0})
        assert event.clicks == 0

    def test_zero_revenue_property(self):
        event = UnifiedGrowthEvent(metrics={"revenue": 0.0})
        assert event.revenue == 0.0

    def test_empty_metrics_properties_default(self):
        event = UnifiedGrowthEvent()
        assert event.roas == 0.0
        assert event.spend == 0.0
        assert event.revenue == 0.0
        assert event.impressions == 0
        assert event.clicks == 0
        assert event.ctr == 0.0
        assert event.installs == 0

    def test_missing_optional_fields(self):
        event = UnifiedGrowthEvent(game_id="P04", event_type=EventType.INSTALL, metrics={"installs": 1})
        assert event.campaign_id == ""
        assert event.creative_id == ""
        assert event.platform == ""
        assert event.metadata == {}
        assert event.raw_data == {}

    def test_large_numbers(self):
        event = UnifiedGrowthEvent(
            metrics={
                "impressions": 10_000_000,
                "clicks": 500_000,
                "spend": 1_000_000.0,
                "revenue": 2_500_000.0,
            }
        )
        assert event.impressions == 10_000_000
        assert event.clicks == 500_000
        assert event.spend == 1_000_000.0
        assert event.revenue == 2_500_000.0

    def test_negative_spend(self):
        event = UnifiedGrowthEvent(metrics={"spend": -50.0})
        assert event.spend == -50.0

    def test_negative_revenue(self):
        event = UnifiedGrowthEvent(metrics={"revenue": -100.0})
        assert event.revenue == -100.0

    def test_float_impressions(self):
        event = UnifiedGrowthEvent(metrics={"impressions": 1000.5})
        assert event.impressions == 1000.5

    def test_aggregate_with_zero_metrics_events(self):
        agg = EventAggregator()
        e1 = UnifiedGrowthEvent(
            game_id="P04",
            metrics={"spend": 0.0, "revenue": 0.0, "installs": 0},
        )
        e2 = UnifiedGrowthEvent(
            game_id="P04",
            metrics={"spend": 0.0, "revenue": 0.0, "installs": 0},
        )
        result = agg.aggregate([e1, e2], game_id="P04")
        assert result["total_spend"] == 0.0
        assert result["total_revenue"] == 0.0
        assert result["total_installs"] == 0
        assert result["roas"] == 0.0

    def test_aggregate_missing_metrics_keys(self):
        agg = EventAggregator()
        event = UnifiedGrowthEvent(
            game_id="P04",
            metrics={},
        )
        result = agg.aggregate([event], game_id="P04")
        assert result["total_spend"] == 0.0
        assert result["total_revenue"] == 0.0
        assert result["total_installs"] == 0
        assert result["total_impressions"] == 0
        assert result["total_clicks"] == 0

    def test_aggregate_negative_values(self):
        agg = EventAggregator()
        e1 = UnifiedGrowthEvent(
            game_id="P04",
            metrics={"spend": -100.0, "revenue": -50.0},
        )
        result = agg.aggregate([e1], game_id="P04")
        assert result["total_spend"] == -100.0
        assert result["total_revenue"] == -50.0

    def test_aggregate_structure_keys(self):
        agg = EventAggregator()
        event = UnifiedGrowthEvent(
            game_id="P04",
            source=EventSource.META,
            event_type=EventType.CAMPAIGN_RESULT,
            metrics={"spend": 10.0},
        )
        result = agg.aggregate([event], game_id="P04")
        expected_keys = {
            "game_id",
            "event_count",
            "total_spend",
            "total_revenue",
            "total_installs",
            "total_impressions",
            "total_clicks",
            "roas",
            "ctr",
            "by_source",
            "by_type",
            "campaigns",
            "creatives",
        }
        assert set(result.keys()) == expected_keys

    def test_aggregate_empty_events_structure(self):
        agg = EventAggregator()
        result = agg.aggregate([], game_id="P04")
        # Empty list returns a minimal dict
        assert "event_count" in result
        assert result["event_count"] == 0