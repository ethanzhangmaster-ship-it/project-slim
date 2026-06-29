from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any


@dataclass(slots=True)
class AdsPerformanceRow:
    date: date
    game: str
    country: str
    channel: str
    ad_id: str
    creative_id: str
    spend: float
    clicks: int
    ctr: float
    cpi: float
    roas: float
    retention_d1: float
    retention_d7: float
    retention_d30: float


@dataclass(slots=True)
class CreativeAssetRow:
    asset_id: str
    creative_type: str
    video_path: str
    game: str
    country: str
    channel: str
    ctr: float
    cvr: float
    roas: float
    spend: float
    status: str
    hook_type: str = ""
    duration: float = 0.0
    creative_name: str = ""
    campaign: str = ""
    campaign_id: str = ""
    adgroup: str = ""
    adgroup_id: str = ""
    ad_id: str = ""
    ad_name: str = ""
    source_name: str = ""
    source_id: str = ""
    installs: float = 0.0
    conversions: float = 0.0
    revenue_value: float = 0.0


@dataclass(slots=True)
class RevenueRow:
    game: str
    date: date
    total_revenue: float
    ltv: float
    arpu: float
    arppu: float
    total_cost: float = 0.0


@dataclass(slots=True)
class RevenueBreakdownRow:
    game: str
    date: date
    store: str
    partner: str
    country: str
    cost: float
    iap_revenue_gross: float
    ad_revenue: float
    total_revenue_gross: float
    campaign: str = ""
    campaign_id: str = ""
    adgroup: str = ""
    adgroup_id: str = ""
    creative_name: str = ""
    creative_id: str = ""
    source_name: str = ""
    source_id: str = ""
    installs: float = 0.0


@dataclass(slots=True)
class DecisionItem:
    recommendation_type: str
    target: str
    owner: str
    kpi_target: str
    estimated_impact: str
    reason: str


@dataclass(slots=True)
class ActionItem:
    task_id: str
    source_meeting: str
    action_type: str
    title: str
    owner: str
    status: str
    acceptance_metric: str
    due_date: date
    description: str
    latest_note: str = ""
    record_id: str | None = None


@dataclass(slots=True)
class AnalysisSection:
    title: str
    conclusions: list[str]
    highlights: list[str]
    recommendations: list[str]
    raw_output: dict[str, Any]


@dataclass(slots=True)
class WeeklyReport:
    meeting_name: str
    report_date: date
    growth_analysis: AnalysisSection
    creative_analysis: AnalysisSection
    revenue_analysis: AnalysisSection
    decisions: list[DecisionItem]
    draft_actions: list[ActionItem]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TaskSyncUpdate:
    task_id: str
    previous_status: str
    new_status: str
    latest_note: str


@dataclass(slots=True)
class DailySyncReport:
    as_of_date: date
    total_tasks: int
    updated_tasks: list[TaskSyncUpdate]
    overdue_tasks: list[ActionItem]
