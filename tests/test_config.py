from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure src is on path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from market_ops.config import (
    Settings,
    _project_key_from_name,
    _optional_path,
    _list_from_env,
    _int_list_from_env,
    _id_list_from_env,
    _owner_rules_from_env,
    _project_sheet_sources_from_env,
    _tecdo_media_accounts_from_env,
    load_settings,
)


class TestProjectKeyFromName:
    def test_extracts_p_number(self):
        assert _project_key_from_name("P04 Witch") == "P04"
        assert _project_key_from_name("p2 mermaid") == "P02"
        assert _project_key_from_name("P007 Dragon") == "P07"

    def test_fallback_no_p_number(self):
        result = _project_key_from_name("Dragon Game")
        assert "Dragon Game" in result or result

    def test_empty_string(self):
        assert _project_key_from_name("") == ""
        assert _project_key_from_name("   ") == ""

    def test_amazon_stripped(self):
        result = _project_key_from_name("P04 Amazon Witch")
        # The function extracts the P number, so "Amazon" is stripped
        # Along with any "amazon" prefix. The result should be just the key.
        assert "amazon" not in result.lower()
        assert result == "P04"


class TestHelpers:
    def test_optional_path_none(self):
        assert _optional_path(None) is None
        assert _optional_path("") is None

    def test_optional_path_valid(self):
        p = _optional_path("C:/tmp")
        assert isinstance(p, Path)
        # On Windows, pathlib normalizes to backslashes
        assert str(p) == "C:\\tmp"

    def test_list_from_env_empty(self):
        assert _list_from_env(None) == []
        assert _list_from_env("") == []

    def test_list_from_env_values(self):
        assert _list_from_env("a, b, c") == ["a", "b", "c"]

    def test_int_list_from_env(self):
        assert _int_list_from_env(None, [1]) == [1]
        assert _int_list_from_env("3,5,7", [1]) == [3, 5, 7]

    def test_id_list_from_env_multiline(self):
        assert _id_list_from_env("abc\ndef") == ["abc", "def"]
        assert _id_list_from_env("abc,def") == ["abc", "def"]

    def test_owner_rules_from_env_empty(self):
        assert _owner_rules_from_env(None) == {}
        assert _owner_rules_from_env("invalid json") == {}

    def test_owner_rules_from_env_valid(self):
        payload = '{"by_game": {"P04": "Alice"}, "by_action_type": {"加码": "Bob"}}'
        result = _owner_rules_from_env(payload)
        assert result["by_game"] == {"P04": "Alice"}

    def test_project_sheet_sources_from_env(self):
        payload = '[{"game": "P04", "daily_url": "http://a", "roi_url": "http://b"}]'
        result = _project_sheet_sources_from_env(payload)
        assert len(result) == 1
        assert result[0]["game"] == "P04"

    def test_tecdo_media_accounts_from_env(self):
        payload = '[{"mediaPlatform": 1, "mediaAccountId": "123"}]'
        result = _tecdo_media_accounts_from_env(payload)
        assert len(result) == 1
        assert result[0]["mediaPlatform"] == 1


class TestSettingsDefaults:
    def test_settings_default_values(self):
        """Test that Settings can be created with minimal required fields."""
        s = Settings(
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
            tecdo_app_id=None,
            tecdo_app_secret=None,
            tecdo_base_url="https://open-power.tec-do.cn",
            tecdo_media_accounts=[],
            tecdo_media_account_ids=[],
            tecdo_probe_platforms=[1, 2],
            tecdo_creative_lookback_days=7,
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
        assert s.ai_provider == "mock"
        assert s.default_task_owner == "TBD"
        assert s.default_game_name == "P04 Witch"

    def test_using_csv_false_by_default(self):
        s = Settings(
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
            tecdo_app_id=None,
            tecdo_app_secret=None,
            tecdo_base_url="https://open-power.tec-do.cn",
            tecdo_media_accounts=[],
            tecdo_media_account_ids=[],
            tecdo_probe_platforms=[1, 2],
            tecdo_creative_lookback_days=7,
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
        assert s.using_csv is False

    def test_active_output_dir(self):
        s = Settings(
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
            tecdo_app_id=None,
            tecdo_app_secret=None,
            tecdo_base_url="https://open-power.tec-do.cn",
            tecdo_media_accounts=[],
            tecdo_media_account_ids=[],
            tecdo_probe_platforms=[1, 2],
            tecdo_creative_lookback_days=7,
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
        assert s.active_output_dir == Path("output") / "active"
        assert s.archive_output_dir == Path("output") / "archive"

    def test_tecdo_effective_media_accounts_from_ids(self):
        s = Settings(
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
            tecdo_app_id=None,
            tecdo_app_secret=None,
            tecdo_base_url="https://open-power.tec-do.cn",
            tecdo_media_accounts=[],
            tecdo_media_account_ids=["111", "222"],
            tecdo_probe_platforms=[1, 2],
            tecdo_creative_lookback_days=7,
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
        accounts = s.tecdo_effective_media_accounts
        assert len(accounts) == 4  # 2 ids * 2 platforms
        assert accounts[0]["mediaPlatform"] == 1


class TestLoadSettingsEnvOverride:
    def test_load_settings_with_env(self):
        with patch.dict(os.environ, {
            "AI_PROVIDER": "openai",
            "DEFAULT_TASK_OWNER": "Alice",
            "ALLOW_BOSS_SEND": "1",
            "CREATIVE_ACTION_MIN_SPEND": "100",
        }, clear=True):
            # Patch load_dotenv to no-op
            with patch("market_ops.config.load_dotenv"):
                s = load_settings()
                assert s.ai_provider == "openai"
                assert s.default_task_owner == "Alice"
                assert s.allow_boss_send is True
                assert s.creative_action_min_spend == 100.0

    def test_load_settings_allow_boss_send_variants(self):
        for val in ("1", "true", "yes", "on"):
            with patch.dict(os.environ, {"ALLOW_BOSS_SEND": val}, clear=True):
                with patch("market_ops.config.load_dotenv"):
                    s = load_settings()
                    assert s.allow_boss_send is True, f"Failed for {val}"

        with patch.dict(os.environ, {"ALLOW_BOSS_SEND": "0"}, clear=True):
            with patch("market_ops.config.load_dotenv"):
                s = load_settings()
                assert s.allow_boss_send is False
