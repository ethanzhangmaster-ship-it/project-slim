from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from market_ops.digest import (
    CompanyOverviewProvider,
    MetricItem,
    ProjectDigestItem,
    RecoveryAnalysis,
    WeeklyDigest,
    WeeklyDigestBuilder,
)


def _make_settings():
    from market_ops.config import Settings
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


class TestMetricItem:
    def test_create(self):
        item = MetricItem(label="本周花费", value="5000 (+10%)")
        assert item.label == "本周花费"
        assert item.value == "5000 (+10%)"


class TestProjectDigestItem:
    def test_create_minimal(self):
        item = ProjectDigestItem(
            game="P04 Witch",
            spend=5000.0,
            spend_change="+10%",
            project_roi=1.2,
            paid_roi_net=0.9,
            avg_roas=1.5,
            avg_cpi=2.0,
            total_revenue=6000.0,
            top_channel="Facebook",
            risk_segment="mid",
            best_day="Monday",
            top_creative="cr_001",
            judgement="继续观察",
            detail_ready=True,
        )
        assert item.game == "P04 Witch"
        assert item.spend == 5000.0
        assert item.detail_ready is True


class TestRecoveryAnalysis:
    def test_defaults(self):
        analysis = RecoveryAnalysis(overview="D7 0.80", change="+0.05")
        assert analysis.overview == "D7 0.80"
        assert analysis.payback_day is None


class TestWeeklyDigest:
    def test_create(self):
        digest = WeeklyDigest(
            title="Test",
            report_date=date(2026, 6, 23),
            company_metrics=[MetricItem("花费", "5000")],
            company_highlights=["Good week"],
            project_items=[],
            creative_items=[],
            creative_notes=[],
            next_actions=[],
        )
        assert digest.title == "Test"
        assert len(digest.company_metrics) == 1


class TestPctChange:
    def test_positive(self):
        from market_ops.digest import WeeklyDigestBuilder as WDB
        result = WDB._pct_change(120, 100)
        assert "+20.0%" in result

    def test_negative(self):
        from market_ops.digest import WeeklyDigestBuilder as WDB
        result = WDB._pct_change(80, 100)
        assert "-20.0%" in result

    def test_zero_previous(self):
        from market_ops.digest import WeeklyDigestBuilder as WDB
        result = WDB._pct_change(100, 0)
        assert "可比基数" in result


class TestIsTotalRow:
    def test_total(self):
        from market_ops.digest import WeeklyDigestBuilder as WDB
        from market_ops.models import AdsPerformanceRow
        row = AdsPerformanceRow(
            date=date(2026, 6, 23),
            game="P04",
            country="All",
            channel="All",
            ad_id="",
            creative_id="",
            spend=100.0,
            clicks=10,
            ctr=0.01,
            cpi=1.0,
            roas=1.5,
            retention_d1=0.1,
            retention_d7=0.05,
            retention_d30=0.02,
        )
        assert WDB._is_total_row(row) is True

    def test_not_total(self):
        from market_ops.digest import WeeklyDigestBuilder as WDB
        from market_ops.models import AdsPerformanceRow
        row = AdsPerformanceRow(
            date=date(2026, 6, 23),
            game="P04",
            country="US",
            channel="Facebook",
            ad_id="a1",
            creative_id="c1",
            spend=50.0,
            clicks=5,
            ctr=0.02,
            cpi=2.0,
            roas=1.0,
            retention_d1=0.1,
            retention_d7=0.05,
            retention_d30=0.02,
        )
        assert WDB._is_total_row(row) is False


class TestWeightedRoiCurve:
    def test_basic(self):
        from market_ops.digest import RecoveryCurveRow, WeeklyDigestBuilder as WDB
        rows = [
            RecoveryCurveRow(
                date=date(2026, 6, 20),
                spend=100.0,
                roi_by_day={7: 0.5, 14: 0.8},
                ratio_by_key={},
            ),
            RecoveryCurveRow(
                date=date(2026, 6, 21),
                spend=50.0,
                roi_by_day={7: 0.4, 14: 0.9},
                ratio_by_key={},
            ),
        ]
        curve = WDB._weighted_roi_curve(rows)
        # Weighted: D7 = (100*0.5 + 50*0.4)/150 = 70/150 ≈ 0.4667
        assert abs(curve[7] - 0.4667) < 0.01
        # D14 = (100*0.8 + 50*0.9)/150 = 125/150 ≈ 0.8333
        assert abs(curve[14] - 0.8333) < 0.01

    def test_empty(self):
        from market_ops.digest import WeeklyDigestBuilder as WDB
        curve = WDB._weighted_roi_curve([])
        assert curve == {}


class TestEstimatePaybackDay:
    def test_crosses_1(self):
        from market_ops.digest import WeeklyDigestBuilder as WDB
        curve = {7: 0.5, 14: 1.2}
        result = WDB._estimate_payback_day(curve)
        assert "天" in result

    def test_not_crossed(self):
        from market_ops.digest import WeeklyDigestBuilder as WDB
        curve = {7: 0.3, 30: 0.6}
        result = WDB._estimate_payback_day(curve)
        assert "未回本" in result

    def test_empty(self):
        from market_ops.digest import WeeklyDigestBuilder as WDB
        result = WDB._estimate_payback_day({})
        assert "暂无" in result


class TestRenderMarkdown:
    def test_basic(self):
        settings = _make_settings()
        digest = WeeklyDigest(
            title="Test | 2026-06-23",
            report_date=date(2026, 6, 23),
            company_metrics=[MetricItem("本周花费", "5000 (+10%)")],
            company_highlights=["Good"],
            project_items=[],
            creative_items=[],
            creative_notes=[],
            next_actions=["Action 1"],
        )
        builder = WeeklyDigestBuilder(settings)
        md = builder.render_markdown(digest)
        assert "Test" in md
        assert "5000" in md
        assert "Action 1" in md
        assert "公司总体数据情况" in md


class TestCompanyOverviewProvider:
    def test_is_usable_valid(self):
        text = "This is a valid company overview with more than twenty characters here."
        assert CompanyOverviewProvider._is_usable(text) is True

    def test_is_usable_too_short(self):
        assert CompanyOverviewProvider._is_usable("Short") is False

    def test_is_usable_placeholder(self):
        text = "Gemini 网页 请把数据粘贴到这里 xxx 建议控制在"
        assert CompanyOverviewProvider._is_usable(text) is False

    def test_looks_like_placeholder(self):
        text = "Gemini 网页 请粘贴到这里 xxx 建议控制在 公司总体数据情况"
        assert CompanyOverviewProvider._looks_like_placeholder(text) is True

    def test_not_placeholder(self):
        text = "Our company revenue grew 20% this quarter."
        assert CompanyOverviewProvider._looks_like_placeholder(text) is False

    def test_truncate(self):
        long_text = "A" * 1000
        result = CompanyOverviewProvider._truncate(long_text, max_chars=100)
        assert len(result) <= 103  # 100 + "..."
        assert result.endswith("...")
