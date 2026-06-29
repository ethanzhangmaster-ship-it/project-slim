from __future__ import annotations

import json
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from market_ops.models import (
    ActionItem,
    AdsPerformanceRow,
    AnalysisSection,
    CreativeAssetRow,
    DailySyncReport,
    DecisionItem,
    RevenueBreakdownRow,
    RevenueRow,
    TaskSyncUpdate,
    WeeklyReport,
)


class TestAdsPerformanceRow:
    def test_create_and_serialize(self):
        row = AdsPerformanceRow(
            date=date(2026, 6, 23),
            game="P04 Witch",
            country="US",
            channel="Facebook",
            ad_id="ad_123",
            creative_id="cr_456",
            spend=100.0,
            clicks=50,
            ctr=0.05,
            cpi=2.0,
            roas=1.5,
            retention_d1=0.3,
            retention_d7=0.15,
            retention_d30=0.05,
        )
        d = asdict(row)
        assert d["game"] == "P04 Witch"
        assert d["spend"] == 100.0
        assert d["date"] == date(2026, 6, 23)

    def test_default_values(self):
        row = AdsPerformanceRow(
            date=date(2026, 1, 1),
            game="P02",
            country="All",
            channel="All",
            ad_id="",
            creative_id="",
            spend=0.0,
            clicks=0,
            ctr=0.0,
            cpi=0.0,
            roas=0.0,
            retention_d1=0.0,
            retention_d7=0.0,
            retention_d30=0.0,
        )
        assert row.spend == 0.0


class TestCreativeAssetRow:
    def test_all_fields(self):
        row = CreativeAssetRow(
            asset_id="asset_001",
            creative_type="video",
            video_path="/videos/test.mp4",
            game="P04 Witch",
            country="US",
            channel="Facebook",
            ctr=0.03,
            cvr=0.02,
            roas=2.5,
            spend=500.0,
            status="active",
            hook_type="cta",
            duration=15.0,
            creative_name="Test Creative",
            campaign="camp_01",
            campaign_id="c001",
            adgroup="ag_01",
            adgroup_id="ag001",
            ad_id="ad001",
            ad_name="Test Ad",
            source_name="meta",
            source_id="s001",
            installs=100.0,
            conversions=20.0,
            revenue_value=1250.0,
        )
        d = asdict(row)
        assert d["asset_id"] == "asset_001"
        assert d["hook_type"] == "cta"
        assert d["duration"] == 15.0
        assert d["status"] == "active"

    def test_defaults(self):
        row = CreativeAssetRow(
            asset_id="a1",
            creative_type="image",
            video_path="",
            game="P02",
            country="CN",
            channel="Google",
            ctr=0.0,
            cvr=0.0,
            roas=0.0,
            spend=0.0,
            status="paused",
        )
        assert row.hook_type == ""
        assert row.duration == 0.0
        assert row.creative_name == ""


class TestRevenueRow:
    def test_create(self):
        row = RevenueRow(
            game="P04 Witch",
            date=date(2026, 6, 23),
            total_revenue=10000.0,
            ltv=5.0,
            arpu=2.0,
            arppu=10.0,
            total_cost=5000.0,
        )
        assert row.ltv == 5.0
        assert row.total_cost == 5000.0


class TestRevenueBreakdownRow:
    def test_create(self):
        row = RevenueBreakdownRow(
            game="P04 Witch",
            date=date(2026, 6, 23),
            store="iOS",
            partner="adjust",
            country="US",
            cost=500.0,
            iap_revenue_gross=1200.0,
            ad_revenue=300.0,
            total_revenue_gross=1500.0,
        )
        assert row.store == "iOS"
        assert row.total_revenue_gross == 1500.0


class TestDecisionItem:
    def test_create(self):
        item = DecisionItem(
            recommendation_type="scale",
            target="P04 / iOS / Facebook",
            owner="Bob",
            kpi_target="ROI > 1.0",
            estimated_impact="+15% revenue",
            reason="Strong ROAS",
        )
        d = asdict(item)
        assert d["recommendation_type"] == "scale"
        assert d["owner"] == "Bob"


class TestActionItem:
    def test_create(self):
        item = ActionItem(
            task_id="task_001",
            source_meeting="Weekly 20260623",
            action_type="加码",
            title="加码：P04 Witch Facebook",
            owner="Alice",
            status="pending",
            acceptance_metric="ROI >= 1.0",
            due_date=date(2026, 6, 30),
            description="Increase budget by 20%",
        )
        d = asdict(item)
        assert d["action_type"] == "加码"
        assert d["latest_note"] == ""


class TestAnalysisSection:
    def test_create(self):
        section = AnalysisSection(
            title="Growth Analysis",
            conclusions=["Revenue up 10%"],
            highlights=["Strong Facebook performance"],
            recommendations=["Scale Facebook budget"],
            raw_output={"data": [1, 2, 3]},
        )
        assert len(section.conclusions) == 1
        assert len(section.recommendations) == 1


class TestWeeklyReport:
    def test_to_dict(self):
        report = WeeklyReport(
            meeting_name="Weekly 20260623",
            report_date=date(2026, 6, 23),
            growth_analysis=AnalysisSection(
                title="Growth", conclusions=[], highlights=[], recommendations=[], raw_output={}
            ),
            creative_analysis=AnalysisSection(
                title="Creative", conclusions=[], highlights=[], recommendations=[], raw_output={}
            ),
            revenue_analysis=AnalysisSection(
                title="Revenue", conclusions=[], highlights=[], recommendations=[], raw_output={}
            ),
            decisions=[],
            draft_actions=[],
        )
        d = report.to_dict()
        assert d["meeting_name"] == "Weekly 20260623"
        assert "growth_analysis" in d
        assert isinstance(d, dict)

    def test_roundtrip_json(self):
        report = WeeklyReport(
            meeting_name="Test",
            report_date=date(2026, 6, 23),
            growth_analysis=AnalysisSection(
                title="G", conclusions=["c1"], highlights=["h1"], recommendations=["r1"], raw_output={}
            ),
            creative_analysis=AnalysisSection(
                title="C", conclusions=[], highlights=[], recommendations=[], raw_output={}
            ),
            revenue_analysis=AnalysisSection(
                title="R", conclusions=[], highlights=[], recommendations=[], raw_output={}
            ),
            decisions=[
                DecisionItem(
                    recommendation_type="hold",
                    target="P04",
                    owner="Alice",
                    kpi_target="ROI > 1",
                    estimated_impact="neutral",
                    reason="stable",
                )
            ],
            draft_actions=[],
        )
        d = report.to_dict()
        # Should be JSON serializable
        json_str = json.dumps(d, default=str)
        assert "Test" in json_str
        assert "Alice" in json_str


class TestTaskSyncUpdate:
    def test_create(self):
        update = TaskSyncUpdate(
            task_id="t1",
            previous_status="pending",
            new_status="done",
            latest_note="Completed",
        )
        d = asdict(update)
        assert d["new_status"] == "done"


class TestDailySyncReport:
    def test_create(self):
        report = DailySyncReport(
            as_of_date=date(2026, 6, 23),
            total_tasks=10,
            updated_tasks=[],
            overdue_tasks=[],
        )
        assert report.total_tasks == 10
