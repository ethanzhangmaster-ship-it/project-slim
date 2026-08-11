from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from market_ops.decision_engine import (
    DECISION_ENUM,
    DECISION_WEIGHTS,
    DecisionEngineBuilder,
    _clamp,
    _norm,
    _project_key,
)


class TestClamp:
    def test_within_range(self):
        assert _clamp(0.5) == 0.5
        assert _clamp(0.0) == 0.0
        assert _clamp(1.0) == 1.0

    def test_below_range(self):
        assert _clamp(-0.5) == 0.0
        assert _clamp(-100) == 0.0

    def test_above_range(self):
        assert _clamp(1.5) == 1.0
        assert _clamp(100) == 1.0

    def test_custom_range(self):
        assert _clamp(0.5, 0.2, 0.8) == 0.5
        assert _clamp(0.1, 0.2, 0.8) == 0.2
        assert _clamp(0.9, 0.2, 0.8) == 0.8


class TestProjectKey:
    def test_extracts_p_code(self):
        assert _project_key("P04 Witch") == "P04"
        assert _project_key("p02 Mermaid") == "P02"

    def test_fallback_upper(self):
        result = _project_key("dragon")
        assert result == "DRAGON"


class TestNorm:
    def test_normalizes(self):
        result = _norm("iOS / Facebook")
        assert "ios" in result
        assert "facebook" in result

    def test_empty(self):
        assert _norm("") == ""
        assert _norm(None) == ""


class TestDecisionWeights:
    def test_weights_sum(self):
        """Weights do NOT need to sum to 1.0, just verify keys exist."""
        assert "growth" in DECISION_WEIGHTS
        assert "roi_payback" in DECISION_WEIGHTS
        assert "fatigue_risk" in DECISION_WEIGHTS
        assert DECISION_WEIGHTS["growth"] > 0
        assert DECISION_WEIGHTS["fatigue_risk"] < 0

    def test_decision_enum_complete(self):
        expected = {
            "small_scale_up",
            "hold",
            "repair",
            "downweight",
            "pause_or_review",
            "data_blocked",
        }
        assert DECISION_ENUM == expected


class TestClassifyDecision:
    def _make_settings(self):
        from market_ops.config import Settings
        from pathlib import Path
        return Settings(
            ai_provider="mock",
            openai_api_key=None,
            openai_model="gpt-4.1-mini",
            openai_base_url=None,
            feishu_app_id=None,
            feishu_app_secret=None,
            feishu_bitable_app_token=None,
            ads_performance_table_id=None,
            creative_library_table_id=None,
            adjust_revenue_table_id=None,
            action_tracker_table_id=None,
            meeting_reports_table_id=None,
            bitable_kpi_overview_table_id=None,
            bitable_project_analysis_table_id=None,
            bitable_campaign_detail_table_id=None,
            bitable_creative_analysis_table_id=None,
            bitable_decision_distribution_table_id=None,
            bitable_action_tracking_table_id=None,
            bitable_video_creative_table_id=None,
            feishu_overview_url=None,
            feishu_daily_data_url=None,
            feishu_roi_url=None,
            project_sheet_sources=[],
            feishu_creative_url=None,
            feishu_adjust_url=None,
            feishu_action_tracker_url=None,
            feishu_action_tracker_sheet_title=None,
            feishu_meeting_reports_url=None,
            feishu_meeting_reports_sheet_title=None,
            meta_access_token=None,
            meta_ad_account_id=None,
            meta_api_version="v22.0",
            meta_creative_lookback_days=7,
            google_ads_developer_token=None,
            google_ads_client_id=None,
            google_ads_client_secret=None,
            google_ads_refresh_token=None,
            google_ads_customer_id=None,
            google_ads_login_customer_id=None,
            google_ads_creative_lookback_days=7,
            creative_action_min_spend=50.0,
            creative_action_min_roi=1.0,
            adjust_api_token=None,
            adjust_dashboard_config_path=None,
            feishu_bot_webhook=None,
            feishu_market_webhook=None,
            feishu_boss_webhook=None,
            allow_boss_send=False,
            feishu_event_verification_token=None,
            feishu_event_encrypt_key=None,
            feishu_event_path="/feishu/events",
            feishu_detail_trigger_keywords=["详细"],
            feishu_detail_allowed_chat_ids=[],
            company_overview_url=None,
            company_overview_markdown=None,
            ads_performance_csv=None,
            creative_library_csv=None,
            adjust_revenue_csv=None,
            geo_performance_csv=None,
            action_tracker_csv=None,
            meeting_reports_csv=None,
            output_dir=Path("output"),
            default_task_owner="TBD",
            default_task_due_days=7,
            default_game_name="P04 Witch",
            task_owner_rules={},
        )

    def _classify(self, **overrides):
        raw = {
            "entity_type": "project",
            "entity_id": "p04",
            "recommended_action": "",
            "budget_change": "",
            "roi": 1.0,
            "risk_priority": 0.2,
            "growth_priority": 0.5,
            "growth_stage": "growth",
        }
        # Pop non-raw params from overrides before merging into raw
        quality_level = overrides.pop("quality_level", "high")
        attribution_level = overrides.pop("attribution_level", "high")
        lifecycle_stage = overrides.pop("lifecycle_stage", "unknown")
        strategy_signal = overrides.pop("strategy_signal", {"blocked_by_guardrail": False})
        final_growth = overrides.pop("final_growth", 0.5)
        final_risk = overrides.pop("final_risk", 0.2)
        raw.update(overrides)
        return DecisionEngineBuilder._classify_decision(
            raw=raw,
            final_growth=final_growth,
            final_risk=final_risk,
            quality_level=quality_level,
            attribution_level=attribution_level,
            lifecycle_stage=lifecycle_stage,
            strategy_signal=strategy_signal,
        )

    def test_small_scale_up(self):
        result = self._classify(
            final_growth=0.65,
            final_risk=0.3,
            budget_change="+20%",
            recommended_action="扩量",
        )
        assert result == "small_scale_up"

    def test_hold(self):
        result = self._classify(final_growth=0.3, final_risk=0.2)
        assert result == "hold"

    def test_pause_or_review(self):
        result = self._classify(
            recommended_action="暂停",
            risk_priority=0.9,
            roi=0.2,
        )
        assert result == "pause_or_review"

    def test_downweight(self):
        result = self._classify(
            recommended_action="降权",
            risk_priority=0.75,
            roi=0.5,
        )
        assert result == "downweight"

    def test_repair(self):
        result = self._classify(
            recommended_action="修复",
            risk_priority=0.6,
            final_growth=0.3,
        )
        assert result == "repair"

    def test_data_blocked_low_confidence(self):
        result = self._classify(
            final_growth=0.5,
            final_risk=0.5,
            quality_level="low",
            attribution_level="low",
            growth_priority=0.7,
            budget_change="+10%",
            entity_type="creative",
        )
        assert result == "data_blocked"

    def test_data_blocked_lifecycle_gap(self):
        result = self._classify(
            final_growth=0.5,
            final_risk=0.5,
            growth_priority=0.6,
            budget_change="+10%",
            lifecycle_stage="data_gap",
            strategy_signal={"blocked_by_guardrail": False},
        )
        assert result == "data_blocked"

    def test_fatigue_risk_repair(self):
        result = self._classify(
            final_growth=0.65,
            final_risk=0.5,
            lifecycle_stage="fatigue_risk",
            budget_change="+5%",
            strategy_signal={"blocked_by_guardrail": False},
        )
        assert result == "repair"

    def test_strategy_guardrail_blocked_growth(self):
        result = self._classify(
            final_growth=0.5,
            final_risk=0.5,
            growth_priority=0.6,
            budget_change="+5%",
            strategy_signal={"blocked_by_guardrail": True},
        )
        assert result == "data_blocked"


class TestQualitySignal:
    def test_passed_high(self):
        payload = {
            "passed": True,
            "modules": [
                {"module": "花费", "level": "高"},
                {"module": "收入", "level": "高"},
            ],
            "top_risks": [],
        }
        score, level, notes = DecisionEngineBuilder._quality_signal(payload)
        assert score == 0.85
        assert level == "high"

    def test_failed_low(self):
        payload = {
            "passed": False,
            "modules": [],
            "top_risks": [{"message": "data missing"}],
        }
        score, level, notes = DecisionEngineBuilder._quality_signal(payload)
        assert score == 0.25
        assert level == "low"
        assert len(notes) == 1

    def test_passed_medium(self):
        payload = {
            "passed": True,
            "modules": [
                {"module": "花费", "level": "中"},
                {"module": "收入", "level": "中"},
            ],
            "top_risks": [],
        }
        score, level, _ = DecisionEngineBuilder._quality_signal(payload)
        assert level in ("medium", "low")


class TestAttributionSignal:
    def test_creative_ready(self):
        attr = {"readiness": {"creative_analysis_ready": True}}
        source = {}
        score, level, notes = DecisionEngineBuilder._attribution_signal(attr, source)
        assert level == "high"
        assert score == 0.85

    def test_campaign_ready(self):
        attr = {"readiness": {"campaign_analysis_ready": True}}
        source = {}
        score, level, _ = DecisionEngineBuilder._attribution_signal(attr, source)
        assert level == "medium"

    def test_source_ready(self):
        attr = {"readiness": {}}
        source = {"summary": {"meta_can_run_now": True}}
        score, level, _ = DecisionEngineBuilder._attribution_signal(attr, source)
        assert level == "medium"

    def test_not_ready(self):
        attr = {"readiness": {}, "warnings": ["no data"]}
        source = {"blockers": ["no key"]}
        score, level, notes = DecisionEngineBuilder._attribution_signal(attr, source)
        assert level == "low"
        assert len(notes) > 0
