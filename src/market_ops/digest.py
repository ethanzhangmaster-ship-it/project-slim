from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from statistics import mean
from typing import Any

import requests
from bs4 import BeautifulSoup

from market_ops.clients.adjust import AdjustClient
from market_ops.clients.feishu_sheets import FeishuSheetsClient
from market_ops.config import Settings
from market_ops.google_creative_resolver import GoogleCreativeResolver
from market_ops.models import ActionItem, AdsPerformanceRow, CreativeAssetRow, RevenueBreakdownRow, RevenueRow, WeeklyReport


@dataclass(slots=True)
class MetricItem:
    label: str
    value: str


@dataclass(slots=True)
class ProjectDigestItem:
    game: str
    spend: float
    spend_change: str
    project_roi: float
    paid_roi_net: float | None
    avg_roas: float
    avg_cpi: float
    total_revenue: float
    top_channel: str
    risk_segment: str
    best_day: str
    top_creative: str
    judgement: str
    detail_ready: bool
    recovery_overview: str = ""
    recovery_change: str = ""
    actual_recovery: str = ""
    forecast_recovery: str = ""
    forecast_analysis: str = ""
    payback_forecast: str = ""
    forecast_recommendation: str = ""
    cohort_age_summary: str = ""
    forecast_confidence: str = ""
    pending_validation: str = ""
    needs_validation: bool = False
    segment_diagnostics: list[str] = field(default_factory=list)
    confidence_level: str = ""
    risk_judgement: str = ""
    suggested_action: str = ""
    problem: str = ""
    reason: str = ""
    action_owner: str = ""
    action_due_date: str = ""
    verification_metric: str = ""
    payback_gate: str = ""
    profit_split: str = ""
    structure_confidence_note: str = ""


@dataclass(slots=True)
class RecoveryCurveRow:
    date: date
    spend: float
    roi_by_day: dict[int, float]
    ratio_by_key: dict[str, float]
    store_type: str = ""
    network: str = ""


@dataclass(slots=True)
class RecoveryAnalysis:
    overview: str
    change: str
    actual_summary: str = ""
    forecast_summary: str = ""
    payback_summary: str = ""
    analysis_summary: str = ""
    recommendation: str = ""
    forecast_error: str = ""
    forecast_accuracy: str = ""
    drift_alert: str = ""
    cohort_oldest_age_days: int | None = None
    cohort_newest_age_days: int | None = None
    forecast_confidence: str = ""
    pending_validation: str = ""
    needs_validation: bool = False
    validation_reason: str = ""
    forecast_accuracy_rows: list[str] = field(default_factory=list)
    history_validation_rows: list[str] = field(default_factory=list)
    bias_summary: str = ""
    bias_correction_factor: float | None = None
    actual_curve: dict[int, float] = field(default_factory=dict)
    forecast_curve: dict[int, float] = field(default_factory=dict)
    payback_day: float | None = None


@dataclass(slots=True)
class CreativeDigestItem:
    asset_id: str
    creative_type: str
    roas: float
    ctr: float
    status: str
    game: str = ""
    channel: str = ""
    spend: float = 0.0
    installs: float = 0.0
    revenue: float = 0.0
    sample_status: str = ""
    confidence_level: str = ""
    risk_judgement: str = ""
    suggested_action: str = ""
    problem: str = ""
    reason: str = ""
    action_owner: str = ""
    action_due_date: str = ""
    verification_metric: str = ""


@dataclass(slots=True)
class CampaignDigestItem:
    game: str
    channel: str
    campaign: str
    country: str
    spend: float
    revenue: float
    roi: float
    payback_gate: str = ""
    confidence_level: str = ""
    risk_judgement: str = ""
    suggested_action: str = ""
    problem: str = ""
    reason: str = ""
    action_owner: str = ""
    action_due_date: str = ""
    verification_metric: str = ""
    scope_note: str = ""
    segment_scope: str = ""


@dataclass(slots=True)
class BreakdownCreativeSignal:
    project_key: str
    project_name: str
    channel: str
    creative_id: str
    creative_name: str
    identity_mode: str
    resolution_quality: str
    spend: float
    revenue: float
    installs: float = 0.0

    @property
    def roi(self) -> float:
        return self.revenue / self.spend if self.spend else 0.0


@dataclass(slots=True)
class WeeklyDigest:
    title: str
    report_date: date
    company_metrics: list[MetricItem]
    company_highlights: list[str]
    project_items: list[ProjectDigestItem]
    creative_items: list[CreativeDigestItem]
    creative_notes: list[str]
    next_actions: list[str]
    company_confidence_lines: list[str] = field(default_factory=list)
    anomaly_lines: list[str] = field(default_factory=list)
    campaign_items: list[CampaignDigestItem] = field(default_factory=list)
    action_refinement_notes: list[str] = field(default_factory=list)
    forecast_accuracy_lines: list[str] = field(default_factory=list)
    forecast_bias_lines: list[str] = field(default_factory=list)


class CompanyOverviewProvider:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def load(self) -> str:
        markdown_path = self._settings.company_overview_markdown
        if markdown_path and markdown_path.exists():
            text = markdown_path.read_text(encoding="utf-8")
            if self._is_usable(text):
                return self._truncate(text)

        if self._settings.company_overview_url:
            text = self._load_from_url(self._settings.company_overview_url)
            if self._is_usable(text):
                return self._truncate(text)

        return ""

    def _load_from_url(self, url: str) -> str:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.extract()
        lines = [line.strip() for line in soup.get_text("\n").splitlines() if line.strip()]
        return "\n".join(lines)

    @staticmethod
    def _truncate(text: str, max_chars: int = 700) -> str:
        compact = re.sub(r"^# .+\n*", "", text.strip(), flags=re.MULTILINE)
        compact = re.sub(r"\n{3,}", "\n\n", compact).strip()
        return compact[:max_chars] + ("..." if len(compact) > max_chars else "")

    @classmethod
    def _is_usable(cls, text: str) -> bool:
        cleaned = text.strip()
        if not cleaned:
            return False
        if cls._looks_like_placeholder(cleaned):
            return False
        return len(cleaned) >= 20

    @staticmethod
    def _looks_like_placeholder(text: str) -> bool:
        lowered = text.lower()
        placeholder_signals = [
            "gemini 网页",
            "粘贴到这里",
            "建议控制在",
            "可参考格式",
            "xxx",
            "公司总体数据情况",
        ]
        return sum(signal in lowered for signal in placeholder_signals) >= 2


class WeeklyDigestBuilder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._overview_provider = CompanyOverviewProvider(settings)
        self._feishu_client = None
        self._adjust_client = None
        if settings.feishu_app_id and settings.feishu_app_secret:
            self._feishu_client = FeishuSheetsClient(settings.feishu_app_id, settings.feishu_app_secret)
        if settings.adjust_api_token:
            try:
                self._adjust_client = AdjustClient(settings.adjust_api_token)
            except Exception:
                self._adjust_client = None
        elif settings.adjust_dashboard_config_path and settings.adjust_dashboard_config_path.exists():
            try:
                self._adjust_client = AdjustClient.from_dashboard_config(settings.adjust_dashboard_config_path)
            except Exception:
                self._adjust_client = None

    def build(
        self,
        report: WeeklyReport,
        ads_rows: list[AdsPerformanceRow],
        creative_rows: list[CreativeAssetRow],
        revenue_rows: list[RevenueRow],
        revenue_breakdown_rows: list[RevenueBreakdownRow] | None = None,
    ) -> WeeklyDigest:
        google_resolver = GoogleCreativeResolver(creative_rows)
        company_metrics, company_highlights = self._build_company_summary(
            report_date=report.report_date,
            ads_rows=ads_rows,
            revenue_rows=revenue_rows,
        )

        overview_text = self._overview_provider.load()
        if overview_text:
            company_highlights = [line.lstrip("- ").strip() for line in overview_text.splitlines() if line.strip()]

        recovery_map = self._load_project_recovery_map(report.report_date)
        project_items = self._build_project_items(
            report_date=report.report_date,
            ads_rows=ads_rows,
            creative_rows=creative_rows,
            revenue_rows=revenue_rows,
            revenue_breakdown_rows=revenue_breakdown_rows or [],
            recovery_map=recovery_map,
            google_resolver=google_resolver,
        )
        creative_items, creative_notes = self._build_creative_digest(
            creative_rows,
            revenue_breakdown_rows or [],
            report.report_date,
            google_resolver,
        )
        next_actions = self._build_next_actions(report.draft_actions[:3], project_items)

        return WeeklyDigest(
            title=f"{report.meeting_name} | {report.report_date.isoformat()}",
            report_date=report.report_date,
            company_metrics=company_metrics,
            company_highlights=company_highlights,
            project_items=project_items,
            creative_items=creative_items,
            creative_notes=creative_notes,
            next_actions=next_actions,
        )

    def save_markdown(self, digest: WeeklyDigest, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"weekly_digest_{digest.report_date.strftime('%Y%m%d')}.md"
        path.write_text(self.render_markdown(digest), encoding="utf-8")
        return path

    def render_markdown(self, digest: WeeklyDigest) -> str:
        lines = [
            f"# {digest.title}",
            "",
            "## 1. 公司总体数据情况",
            "",
        ]
        lines.extend(f"- {metric.label} {metric.value}" for metric in digest.company_metrics)
        lines.extend(f"- {item}" for item in digest.company_highlights)

        lines.extend(["", "## 2. 每个项目的投放数据情况分析", ""])
        if digest.project_items:
            for item in digest.project_items:
                if item.detail_ready:
                    lines.append(
                        f"- {item.game}：近7天花费 {item.spend:.0f}，较上周 {item.spend_change}，7天 ROI {item.project_roi:.2f}，"
                        f"平均 ROAS {item.avg_roas:.2f}，平均 CPI {item.avg_cpi:.2f}，总收入 {item.total_revenue:.0f}。"
                    )
                    lines.append(
                        f"- {item.game}：当前主投渠道 {item.top_channel}，风险段 {item.risk_segment}，"
                        f"最佳单日为 {item.best_day}，当前最值得继续看的素材是 {item.top_creative}。"
                    )
                else:
                    lines.append(
                        f"- {item.game}：近7天花费 {item.spend:.0f}，较上周 {item.spend_change}，"
                        f"7天 ROI {item.project_roi:.2f}，总收入 {item.total_revenue:.0f}。"
                    )
                    lines.append(f"- {item.game}：当前已接入 Adjust 项目总览，渠道/平台/素材明细待补飞书接入。")
                lines.append(f"- {item.game}：本周判断是{item.judgement}")
        else:
            lines.append("- 当前周窗内没有可用投放数据。")

        lines.extend(["", "## 3. 最近的素材分析情况", ""])
        if digest.creative_items:
            for item in digest.creative_items:
                lines.append(
                    f"- {item.asset_id}：类型={item.creative_type}，ROAS={item.roas:.2f}，CTR={item.ctr:.3f}，状态={item.status}"
                )
            lines.extend(f"- {item}" for item in digest.creative_notes)
        else:
            lines.append("- 当前没有可用素材数据。")

        lines.extend(["", "## 本周建议动作", ""])
        if digest.next_actions:
            lines.extend(f"- {item}" for item in digest.next_actions)
        else:
            lines.append("- 本周没有新增建议动作。")
        lines.append("")
        return "\n".join(lines)

    def build_card(self, digest: WeeklyDigest) -> dict[str, Any]:
        elements: list[dict[str, Any]] = []
        elements.append(self._section_title("1. 公司总体数据情况"))
        elements.append(self._metric_fields(digest.company_metrics[:4]))
        if digest.company_highlights:
            elements.append(self._markdown_block("\n".join(f"- {item}" for item in digest.company_highlights)))

        elements.append({"tag": "hr"})
        elements.append(self._section_title("2. 每个项目的投放数据情况分析"))
        if digest.project_items:
            for item in digest.project_items:
                if item.detail_ready:
                    elements.append(
                        self._markdown_block(
                            f"**{item.game}**\n"
                            f"- 花费 `{item.spend:.0f}`，较上周 `{item.spend_change}`\n"
                            f"- 7天 ROI `{item.project_roi:.2f}`，平均 ROAS `{item.avg_roas:.2f}`，平均 CPI `{item.avg_cpi:.2f}`，总收入 `{item.total_revenue:.0f}`\n"
                            f"- 主投渠道 `{item.top_channel}`，风险段 `{item.risk_segment}`\n"
                            f"- 最佳单日 `{item.best_day}`\n"
                            f"- 优先素材 `{item.top_creative}`\n"
                            f"- 判断：{item.judgement}"
                        )
                    )
                else:
                    elements.append(
                        self._markdown_block(
                            f"**{item.game}**\n"
                            f"- 花费 `{item.spend:.0f}`，较上周 `{item.spend_change}`\n"
                            f"- 7天 ROI `{item.project_roi:.2f}`，总收入 `{item.total_revenue:.0f}`\n"
                            f"- 当前已接入 Adjust 项目总览，渠道/平台/素材明细待补飞书接入\n"
                            f"- 判断：{item.judgement}"
                        )
                    )
        else:
            elements.append(self._markdown_block("- 当前周窗内没有可用投放数据。"))

        elements.append({"tag": "hr"})
        elements.append(self._section_title("3. 最近的素材分析情况"))
        if digest.creative_items:
            creative_fields: list[dict[str, Any]] = []
            for item in digest.creative_items:
                creative_fields.append(
                    {
                        "is_short": True,
                        "text": {
                            "tag": "lark_md",
                            "content": (
                                f"**{item.asset_id}**\n"
                                f"类型：{item.creative_type}\n"
                                f"ROAS：`{item.roas:.2f}`\n"
                                f"CTR：`{item.ctr:.3f}`\n"
                                f"状态：{item.status}"
                            ),
                        },
                    }
                )
            elements.append({"tag": "div", "fields": creative_fields})
            if digest.creative_notes:
                elements.append(self._markdown_block("\n".join(f"- {item}" for item in digest.creative_notes)))
        else:
            elements.append(self._markdown_block("- 当前没有可用素材数据。"))

        elements.append({"tag": "hr"})
        elements.append(self._section_title("本周建议动作"))
        if digest.next_actions:
            elements.append(self._markdown_block("\n".join(f"- {item}" for item in digest.next_actions)))
        else:
            elements.append(self._markdown_block("- 本周没有新增建议动作。"))

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": "turquoise",
                "title": {"tag": "plain_text", "content": digest.title},
            },
            "elements": elements,
        }

    def _build_company_summary(
        self,
        report_date: date,
        ads_rows: list[AdsPerformanceRow],
        revenue_rows: list[RevenueRow],
    ) -> tuple[list[MetricItem], list[str]]:
        window_start = report_date - timedelta(days=6)
        previous_start = window_start - timedelta(days=7)
        previous_end = window_start - timedelta(days=1)

        current_total_ads, current_detail_ads = self._split_window_ads(ads_rows, window_start, report_date)
        previous_total_ads, previous_detail_ads = self._split_window_ads(ads_rows, previous_start, previous_end)
        active_games = {row.game for row in current_total_ads + current_detail_ads if row.game}
        trusted_detail_rows = self._trusted_detail_rows(current_detail_ads)
        trusted_detail_projects = {self._project_key(row.game) for row in trusted_detail_rows if row.game}

        current_summary_rows = current_total_ads or current_detail_ads
        previous_summary_rows = previous_total_ads or previous_detail_ads
        current_detail_rows = current_detail_ads or current_summary_rows

        company_sheet_summary = self._load_company_sheet_summary(report_date)
        current_revenue = [row for row in revenue_rows if window_start <= row.date <= report_date]
        previous_revenue = [row for row in revenue_rows if previous_start <= row.date <= previous_end]
        current_adjust_spend = sum(row.total_cost for row in current_revenue)
        previous_adjust_spend = sum(row.total_cost for row in previous_revenue)

        if current_adjust_spend or previous_adjust_spend:
            current_spend = current_adjust_spend
            previous_spend = previous_adjust_spend
            signal_rows = trusted_detail_rows or current_detail_ads
            top_channel = self._top_channel(signal_rows) if signal_rows else company_sheet_summary["top_channel"] if company_sheet_summary is not None else "n/a"
            weakest_segment = (
                self._weakest_segment(signal_rows)
                if signal_rows
                else company_sheet_summary["weakest_segment"]
                if company_sheet_summary is not None
                else "暂无可判定风险段"
            )
            company_scope = "company"
        elif company_sheet_summary is not None:
            current_spend = company_sheet_summary["current_spend"]
            previous_spend = company_sheet_summary["previous_spend"]
            top_channel = company_sheet_summary["top_channel"]
            weakest_segment = company_sheet_summary["weakest_segment"]
            company_scope = "company"
        else:
            current_revenue = self._aligned_revenue_rows(revenue_rows, window_start, report_date, active_games)
            previous_revenue = self._aligned_revenue_rows(revenue_rows, previous_start, previous_end, active_games)
            current_spend = sum(row.spend for row in current_summary_rows)
            previous_spend = sum(row.spend for row in previous_summary_rows)
            signal_rows = trusted_detail_rows or current_detail_rows
            top_channel = self._top_channel(signal_rows)
            weakest_segment = self._weakest_segment(signal_rows)
            company_scope = "active_projects"

        current_revenue_total = sum(row.total_revenue for row in current_revenue)
        previous_revenue_total = sum(row.total_revenue for row in previous_revenue)
        current_roi = current_revenue_total / current_spend if current_spend else 0.0
        previous_roi = previous_revenue_total / previous_spend if previous_spend else 0.0

        spend_change = self._pct_change(current_spend, previous_spend)
        revenue_change = self._pct_change(current_revenue_total, previous_revenue_total)
        roi_change = self._pct_change(current_roi, previous_roi)

        top_growth_game = self._top_growth_game(current_revenue, previous_revenue, current_summary_rows, previous_summary_rows)
        focus_line = self._focus_line(current_roi, weakest_segment)

        metrics = [
            MetricItem("本周花费", f"{current_spend:.0f} ({spend_change})"),
            MetricItem("整体收入", f"{current_revenue_total:.0f} ({revenue_change})"),
            MetricItem("公司总收入ROI", f"{current_roi:.2f} ({roi_change})"),
            MetricItem("主投渠道", top_channel),
        ]

        highlights: list[str] = []
        active_revenue_projects = {
            self._project_key(row.game)
            for row in current_revenue
            if row.total_cost > 0 or self._project_key(row.game) in trusted_detail_projects
        }
        coverage_note = self._coverage_note(trusted_detail_projects, active_revenue_projects, company_scope)
        if coverage_note:
            highlights.append(coverage_note)
        highlights.extend(
            [
                f"主要增长来自 {top_growth_game}。",
                f"当前最需要压缩的低效段是 {weakest_segment}。",
                f"下周重点关注：{focus_line}",
            ]
        )
        return metrics, highlights

    def _build_project_items(
        self,
        report_date: date,
        ads_rows: list[AdsPerformanceRow],
        creative_rows: list[CreativeAssetRow],
        revenue_rows: list[RevenueRow],
        revenue_breakdown_rows: list[RevenueBreakdownRow],
        recovery_map: dict[str, RecoveryAnalysis],
        google_resolver: GoogleCreativeResolver,
    ) -> list[ProjectDigestItem]:
        window_start = report_date - timedelta(days=6)
        previous_start = window_start - timedelta(days=7)
        previous_end = window_start - timedelta(days=1)

        grouped_total: dict[str, list[AdsPerformanceRow]] = defaultdict(list)
        grouped_detail: dict[str, list[AdsPerformanceRow]] = defaultdict(list)
        grouped_previous_total: dict[str, list[AdsPerformanceRow]] = defaultdict(list)
        grouped_previous_detail: dict[str, list[AdsPerformanceRow]] = defaultdict(list)
        grouped_revenue: dict[str, list[RevenueRow]] = defaultdict(list)
        grouped_previous_revenue: dict[str, list[RevenueRow]] = defaultdict(list)
        grouped_creatives: dict[str, list[CreativeAssetRow]] = defaultdict(list)
        grouped_breakdown: dict[str, list[RevenueBreakdownRow]] = defaultdict(list)
        grouped_paid_breakdown: dict[str, list[RevenueBreakdownRow]] = defaultdict(list)
        grouped_names: dict[str, set[str]] = defaultdict(set)

        for row in ads_rows:
            project_key = self._project_key(row.game)
            if row.game:
                grouped_names[project_key].add(row.game)
            if window_start <= row.date <= report_date:
                if self._is_total_row(row):
                    grouped_total[project_key].append(row)
                else:
                    grouped_detail[project_key].append(row)
            elif previous_start <= row.date <= previous_end:
                if self._is_total_row(row):
                    grouped_previous_total[project_key].append(row)
                else:
                    grouped_previous_detail[project_key].append(row)

        for row in revenue_rows:
            project_key = self._project_key(row.game)
            if row.game:
                grouped_names[project_key].add(row.game)
            if window_start <= row.date <= report_date:
                grouped_revenue[project_key].append(row)
            elif previous_start <= row.date <= previous_end:
                grouped_previous_revenue[project_key].append(row)

        for row in creative_rows:
            project_key = self._project_key(row.game)
            grouped_creatives[project_key].append(row)
            if row.game:
                grouped_names[project_key].add(row.game)

        for row in revenue_breakdown_rows:
            if not (window_start <= row.date <= report_date):
                continue
            project_key = self._project_key(row.game)
            grouped_breakdown[project_key].append(row)
            if row.game:
                grouped_names[project_key].add(row.game)
            if row.cost <= 0:
                continue
            grouped_paid_breakdown[project_key].append(row)

        active_games: set[str] = set()
        for project_key, rows in grouped_revenue.items():
            if sum(row.total_cost for row in rows) > 0:
                active_games.add(project_key)
        for project_key, rows in grouped_total.items():
            if sum(row.spend for row in rows) > 0:
                active_games.add(project_key)
        for project_key, rows in grouped_detail.items():
            if sum(row.spend for row in rows) > 0:
                active_games.add(project_key)

        items: list[ProjectDigestItem] = []
        for game in active_games:
            summary_rows = grouped_total.get(game) or grouped_detail.get(game, [])
            detail_rows = grouped_detail.get(game) or summary_rows
            previous_rows = grouped_previous_total.get(game) or grouped_previous_detail.get(game, [])
            current_revenue_rows = grouped_revenue.get(game, [])
            previous_revenue_rows = grouped_previous_revenue.get(game, [])
            spend = sum(row.total_cost for row in current_revenue_rows)
            previous_spend = sum(row.total_cost for row in previous_revenue_rows)
            if spend == 0:
                spend = sum(row.spend for row in summary_rows)
            if previous_spend == 0:
                previous_spend = sum(row.spend for row in previous_rows)

            total_revenue = sum(row.total_revenue for row in current_revenue_rows)
            project_roi = total_revenue / spend if spend else 0.0
            detail_ready = bool(detail_rows) and game in self._settings.trusted_detail_project_keys
            reliable_rows = summary_rows if detail_ready else []
            avg_roas = mean(row.roas for row in reliable_rows) if reliable_rows else project_roi
            cpi_values = [row.cpi for row in reliable_rows if row.cpi]
            avg_cpi = mean(cpi_values) if cpi_values else 0.0
            spend_change = self._pct_change(spend, previous_spend)
            top_channel = self._top_channel(detail_rows) if detail_ready else "待补可信项目明细"
            risk_segment = self._weakest_segment(detail_rows) if detail_ready else "待补可信项目明细"
            best_day = self._best_day(reliable_rows) if detail_ready else "待补可信项目明细"
            project_breakdown_rows = grouped_breakdown.get(game, [])
            paid_project_breakdown_rows = grouped_paid_breakdown.get(game, [])
            top_creative = self._top_creative(
                grouped_creatives.get(game, []),
                project_breakdown_rows,
                project_key=game,
                project_name=self._project_display_name(game, grouped_names.get(game, set())),
                google_resolver=google_resolver,
            )
            paid_roi_net = self._paid_roi_net(paid_project_breakdown_rows)
            judgement = self._project_action_judgement_paid_v2(project_roi, risk_segment, top_creative, detail_ready, paid_roi_net)
            display_name = self._project_display_name(game, grouped_names.get(game, set()))
            recovery = recovery_map.get(game) or recovery_map.get(display_name) or RecoveryAnalysis("", "")

            items.append(
                ProjectDigestItem(
                    game=display_name,
                    spend=spend,
                    spend_change=spend_change,
                    project_roi=project_roi,
                    paid_roi_net=paid_roi_net,
                    avg_roas=avg_roas,
                    avg_cpi=avg_cpi,
                    total_revenue=total_revenue,
                    top_channel=top_channel,
                    risk_segment=risk_segment,
                    best_day=best_day,
                    top_creative=top_creative,
                    judgement=self._merge_project_judgement(judgement, recovery),
                    detail_ready=detail_ready,
                    recovery_overview=recovery.overview,
                    recovery_change=recovery.change,
                    actual_recovery=recovery.actual_summary,
                    forecast_recovery=recovery.forecast_summary,
                    forecast_analysis=recovery.analysis_summary,
                    payback_forecast=recovery.payback_summary,
                    forecast_recommendation=recovery.recommendation,
                    profit_split=self._project_profit_split(project_breakdown_rows),
                    structure_confidence_note=self._project_structure_note(project_breakdown_rows),
                )
            )

        return sorted(items, key=lambda item: item.spend, reverse=True)

    def _load_project_recovery_map(self, report_date: date) -> dict[str, RecoveryAnalysis]:
        result = self._load_adjust_project_recovery_map(report_date)
        if not self._feishu_client:
            return result
        current_start = report_date - timedelta(days=6)
        previous_end = current_start - timedelta(days=1)
        previous_start = previous_end - timedelta(days=6)
        for source in self._iter_recovery_sources():
            project_key = self._project_key(source["game"])
            if project_key in result or source["game"] in result:
                continue
            try:
                sheet_id = self._select_overall_roi_sheet_id(source["roi_url"])
                rows = self._read_recovery_curve_rows(source["roi_url"], sheet_id)
            except Exception:
                continue
            current_rows = [row for row in rows if current_start <= row.date <= report_date]
            previous_rows = [row for row in rows if previous_start <= row.date <= previous_end]
            analysis = self._build_recovery_analysis(current_rows, previous_rows)
            if not analysis:
                continue
            result[project_key] = analysis
            result[source["game"]] = analysis
        return result

    def _load_adjust_project_recovery_map(self, report_date: date) -> dict[str, RecoveryAnalysis]:
        if not self._adjust_client:
            return {}

        current_start = report_date - timedelta(days=6)
        previous_end = current_start - timedelta(days=1)
        previous_start = previous_end - timedelta(days=6)
        history_start = previous_start - timedelta(days=210)
        try:
            raw_rows = self._adjust_client.fetch_recovery_cohort_rows(
                start_date=history_start.isoformat(),
                end_date=report_date.isoformat(),
            )
        except Exception:
            return {}

        rows_by_game: dict[str, list[RecoveryCurveRow]] = defaultdict(list)
        for raw_row in raw_rows:
            game = str(raw_row.get("app") or "").strip()
            if not game or self._is_blacklisted_adjust_app(game):
                continue
            row_date = self._parse_recovery_date([raw_row.get("day")])
            if row_date is None:
                continue
            spend = self._parse_numeric(raw_row.get("cost"))
            if spend <= 0:
                continue

            roi_by_day: dict[int, float] = {}
            for display_day, metric_suffix in self._adjust_recovery_day_mapping().items():
                roi_value = self._extract_adjust_roi(raw_row, spend, metric_suffix)
                if roi_value > 0:
                    roi_by_day[display_day] = roi_value
            if not roi_by_day:
                continue

            rows_by_game[game].append(
                RecoveryCurveRow(
                    date=row_date,
                    spend=spend,
                    roi_by_day=roi_by_day,
                    ratio_by_key=self._build_adjust_ratio_map(roi_by_day),
                )
            )

        result: dict[str, RecoveryAnalysis] = {}
        for game, rows in rows_by_game.items():
            current_rows = [row for row in rows if current_start <= row.date <= report_date]
            previous_rows = [row for row in rows if previous_start <= row.date <= previous_end]
            history_rows = [row for row in rows if row.date < previous_start]
            analysis = self._build_recovery_analysis(
                current_rows,
                previous_rows,
                history_rows=history_rows,
                as_of_date=date.today(),
            )
            if not analysis:
                continue
            project_key = self._project_key(game)
            result[project_key] = analysis
            result[game] = analysis
        return result

    def _iter_recovery_sources(self) -> list[dict[str, str]]:
        sources: list[dict[str, str]] = []
        if self._settings.feishu_daily_data_url:
            sources.append(
                {
                    "game": self._settings.default_game_name,
                    "roi_url": self._settings.feishu_roi_url or self._settings.feishu_daily_data_url,
                }
            )
        for item in self._settings.project_sheet_sources:
            game = str(item.get("game") or "").strip()
            roi_url = str(item.get("roi_url") or item.get("daily_url") or "").strip()
            if not game or not roi_url:
                continue
            sources.append({"game": game, "roi_url": roi_url})
        deduped: dict[tuple[str, str], dict[str, str]] = {}
        for item in sources:
            deduped[(item["game"], item["roi_url"])] = item
        return list(deduped.values())

    def _select_overall_roi_sheet_id(self, url: str) -> str:
        sheets = self._feishu_client.list_sheets(url)
        roi_sheets = [sheet for sheet in sheets if "ROI" in str(sheet["title"]).upper()]
        if not roi_sheets:
            raise ValueError("No ROI sheet found.")

        def score(sheet: dict[str, Any]) -> tuple[int, int]:
            title = str(sheet["title"]).upper()
            segment_hit = sum(token in title for token in ("FB", "GG", "GP", "IOS", "AND", "ANDROID", "GOOGLE", "FACEBOOK"))
            overall_bonus = 1 if segment_hit == 0 else 0
            return (overall_bonus, -segment_hit)

        best = max(roi_sheets, key=score)
        return str(best["sheet_id"])

    def _read_recovery_curve_rows(self, url: str, sheet_id: str) -> list[RecoveryCurveRow]:
        values = self._feishu_client.read_values(url, "A1:AZ800", sheet_id=sheet_id)
        if not values:
            return []
        headers = values[0]
        spend_index = self._detect_recovery_spend_index(headers)
        roi_indices: dict[int, int] = {}
        ratio_indices: dict[str, int] = {}
        for index, header in enumerate(headers):
            header_text = str(header or "")
            upper = header_text.upper()
            if "ROI" in upper and "/" not in upper:
                numbers = [int(item) for item in re.findall(r"\d+", header_text)]
                if numbers:
                    day = numbers[0]
                    if day in {2, 3, 4, 5, 6, 7, 14, 21, 30, 40, 50, 60, 70, 80, 90, 100}:
                        roi_indices[day] = index
            ratio_match = re.search(r"(\d+)\s*/\s*(\d+)", header_text)
            if ratio_match:
                ratio_indices[f"{ratio_match.group(1)}/{ratio_match.group(2)}"] = index

        rows: list[RecoveryCurveRow] = []
        for raw_row in values[1:]:
            row_date = self._parse_recovery_date(raw_row[:4])
            if row_date is None:
                continue
            spend = self._parse_numeric(raw_row[spend_index] if spend_index is not None and len(raw_row) > spend_index else None)
            if spend <= 0:
                continue
            roi_by_day = {
                day: self._parse_rate_value(raw_row[index] if len(raw_row) > index else None)
                for day, index in roi_indices.items()
                if self._parse_rate_value(raw_row[index] if len(raw_row) > index else None) > 0
            }
            if not roi_by_day:
                continue
            ratio_by_key = {
                key: self._parse_numeric(raw_row[index] if len(raw_row) > index else None)
                for key, index in ratio_indices.items()
                if self._parse_numeric(raw_row[index] if len(raw_row) > index else None) > 0
            }
            rows.append(
                RecoveryCurveRow(
                    date=row_date,
                    spend=spend,
                    roi_by_day=roi_by_day,
                    ratio_by_key=ratio_by_key,
                )
            )
        return rows

    def _build_recovery_analysis(
        self,
        current_rows: list[RecoveryCurveRow],
        previous_rows: list[RecoveryCurveRow],
        history_rows: list[RecoveryCurveRow] | None = None,
        as_of_date: date | None = None,
    ) -> RecoveryAnalysis | None:
        if not current_rows:
            return None
        history_rows = history_rows or []
        as_of_date = as_of_date or date.today()
        current_curve = self._smooth_roi_curve(self._weighted_roi_curve(current_rows))
        if not current_curve:
            return None
        current_ratios = self._weighted_ratio_curve(current_rows)
        previous_curve = self._smooth_roi_curve(self._weighted_roi_curve(previous_rows))
        previous_ratios = self._weighted_ratio_curve(previous_rows)
        current_spend = sum(row.spend for row in current_rows)

        long_day = max((day for day in current_curve if day >= 7), default=max(current_curve))
        payback_text = self._estimate_payback_day(current_curve)
        long_roi = current_curve.get(long_day, 0.0)
        if long_roi >= 1:
            profit_text = f"按D{long_day} ROI {long_roi:.2f} 测算，利润空间约 {current_spend * (long_roi - 1):.0f}"
        else:
            profit_text = f"按D{long_day} ROI {long_roi:.2f} 测算，距回本还差约 {current_spend * (1 - long_roi):.0f}"

        key_days = [day for day in (3, 7, 14, 30, 60) if day in current_curve]
        curve_text = " / ".join(f"D{day} {current_curve[day]:.2f}" for day in key_days[:4])
        overview = f"{curve_text}；{payback_text}；{profit_text}"

        change = ""
        if previous_curve:
            compare_days = [day for day in (3, 7, 14, 30, 60) if day in current_curve and day in previous_curve]
            compare_parts = [f"D{day} {current_curve[day]:.2f}({current_curve[day] - previous_curve[day]:+.2f})" for day in compare_days[:3]]
            for ratio_key in ("3/2", "7/2", "14/7", "30/7", "60/30", "90/60"):
                if ratio_key in current_ratios and ratio_key in previous_ratios:
                    compare_parts.append(f"{ratio_key} {current_ratios[ratio_key]:.2f}({current_ratios[ratio_key] - previous_ratios[ratio_key]:+.2f})")
                    if len(compare_parts) >= 5:
                        break
            reason = self._infer_recovery_change_reason(current_curve, previous_curve, current_ratios, previous_ratios, current_rows, previous_rows)
            change = " / ".join(compare_parts) + f"；{reason}"
        return RecoveryAnalysis(overview=overview, change=change)

    @staticmethod
    def _weighted_roi_curve(rows: list[RecoveryCurveRow]) -> dict[int, float]:
        values: dict[int, float] = {}
        all_days = sorted({day for row in rows for day in row.roi_by_day})
        for day in all_days:
            valid_rows = [row for row in rows if day in row.roi_by_day]
            total_spend = sum(row.spend for row in valid_rows)
            if total_spend <= 0:
                continue
            values[day] = sum(row.spend * row.roi_by_day[day] for row in valid_rows) / total_spend
        return values

    @staticmethod
    def _weighted_ratio_curve(rows: list[RecoveryCurveRow]) -> dict[str, float]:
        values: dict[str, float] = {}
        all_keys = sorted({key for row in rows for key in row.ratio_by_key})
        for key in all_keys:
            valid_rows = [row for row in rows if key in row.ratio_by_key]
            total_spend = sum(row.spend for row in valid_rows)
            if total_spend <= 0:
                continue
            values[key] = sum(row.spend * row.ratio_by_key[key] for row in valid_rows) / total_spend
        return values

    @staticmethod
    def _estimate_payback_day(curve: dict[int, float]) -> str:
        points = sorted((day, value) for day, value in curve.items() if value > 0)
        if not points:
            return "暂无可用回本曲线"
        for index, (day, value) in enumerate(points):
            if value < 1:
                continue
            if index == 0:
                return f"预计 {day} 天内回本"
            prev_day, prev_value = points[index - 1]
            if value == prev_value:
                return f"预计约 {day:.1f} 天回本"
            day_estimate = prev_day + (1 - prev_value) * (day - prev_day) / (value - prev_value)
            return f"预计约 {day_estimate:.1f} 天回本"
        return f"D{points[-1][0]} 仍未回本"

    @staticmethod
    def _infer_recovery_change_reason(
        current_curve: dict[int, float],
        previous_curve: dict[int, float],
        current_ratios: dict[str, float],
        previous_ratios: dict[str, float],
        current_rows: list[RecoveryCurveRow],
        previous_rows: list[RecoveryCurveRow],
    ) -> str:
        early_days = [day for day in (2, 3, 7) if day in current_curve and day in previous_curve]
        late_days = [day for day in (14, 21, 30, 60) if day in current_curve and day in previous_curve]
        early_delta = mean(current_curve[day] - previous_curve[day] for day in early_days) if early_days else 0.0
        late_delta = mean(current_curve[day] - previous_curve[day] for day in late_days) if late_days else 0.0
        current_spend = sum(row.spend for row in current_rows)
        previous_spend = sum(row.spend for row in previous_rows)
        spend_delta = ((current_spend - previous_spend) / previous_spend) if previous_spend else 0.0

        if early_delta <= -0.05 and late_delta <= -0.05:
            reason = "前中段回收同步变弱，优先排查流量质量、素材首付费承接和版本变现深度。"
        elif early_delta <= -0.05 and late_delta > -0.02:
            reason = "前段回收变弱但长尾相对稳定，更像前端买量质量或素材点击后转化下滑。"
        elif early_delta > 0.03 and late_delta <= -0.03:
            reason = "短期回收更快但中后段走弱，说明前端被拉高，但长尾价值释放不足。"
        elif early_delta > 0.03 and late_delta > 0.03:
            reason = "前中段回收同步改善，说明本周投放流量质量和后续变现承接都在提升。"
        else:
            reason = "整体回收变化不大，更多像正常波动，继续观察后续版本和素材贡献。"

        if spend_delta > 0.15 and early_delta < 0:
            reason += " 同期有明显放量，存在放量稀释回收质量的可能。"
        if "14/7" in current_ratios and "14/7" in previous_ratios and current_ratios["14/7"] < previous_ratios["14/7"] - 0.1:
            reason += " 7日后的长尾释放也在变弱。"
        return reason

    @staticmethod
    def _merge_project_judgement(judgement: str, recovery: RecoveryAnalysis) -> str:
        parts = [judgement]
        if recovery.overview:
            parts.append(f"回收横向：{recovery.overview}")
        if recovery.change:
            parts.append(f"回收纵向：{recovery.change}")
        return "；".join(part for part in parts if part)

    @staticmethod
    def _detect_recovery_spend_index(headers: list[Any]) -> int | None:
        for index, header in enumerate(headers[:5]):
            header_text = str(header or "")
            if "$" in header_text or "cost" in header_text.lower():
                return index
        return 2 if len(headers) > 2 else None

    @staticmethod
    def _parse_recovery_date(values: list[Any]) -> date | None:
        for value in values:
            if isinstance(value, (int, float)) and float(value) > 20000:
                return date(1899, 12, 30) + timedelta(days=int(float(value)))
            text = str(value or "").strip()
            match = re.search(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", text)
            if match:
                return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        return None

    @staticmethod
    def _parse_rate_value(value: Any) -> float:
        text = str(value or "").strip()
        if not text:
            return 0.0
        cleaned = text.replace("$", "").replace(",", "").strip()
        try:
            numeric = float(cleaned.replace("%", ""))
        except ValueError:
            return 0.0
        return numeric / 100.0 if "%" in cleaned else numeric

    def _build_creative_digest(
        self,
        creative_rows: list[CreativeAssetRow],
        revenue_breakdown_rows: list[RevenueBreakdownRow],
        report_date: date,
        google_resolver: GoogleCreativeResolver,
    ) -> tuple[list[CreativeDigestItem], list[str]]:
        breakdown_signals = self._collect_breakdown_creative_signals(
            revenue_breakdown_rows,
            report_date,
            google_resolver=google_resolver,
        )
        if breakdown_signals:
            return self._build_breakdown_creative_digest(breakdown_signals)

        ranked = sorted(creative_rows, key=lambda row: (row.roas, row.ctr, row.spend), reverse=True)
        top_assets = ranked[:3]
        items = [
            CreativeDigestItem(
                asset_id=row.asset_id,
                creative_type=row.creative_type or row.hook_type or "未标记",
                roas=row.roas,
                ctr=row.ctr,
                status=row.status,
            )
            for row in top_assets
        ]
        if not creative_rows:
            return [], []

        hook_counts: dict[str, int] = defaultdict(int)
        low_quality_count = 0
        paid_test_count = 0
        for row in creative_rows:
            hook_key = row.hook_type or row.creative_type or "Unknown"
            hook_counts[hook_key] += 1
            if row.spend > 0 and row.roas == 0:
                low_quality_count += 1
            if row.roas > 0 or "有付费" in row.status or "Roas>30%" in row.status:
                paid_test_count += 1

        dominant_hook = max(hook_counts, key=hook_counts.get)
        notes = [
            f"本周最值得继续放大的素材方向是 `{dominant_hook}`。",
            f"本周共监测到 {len(creative_rows)} 条素材，其中已有正向付费验证的素材 {paid_test_count} 条。",
            f"当前有 {low_quality_count} 条素材已有花费但尚未跑出回收，建议先复核归因并降低优先级，不直接作为停测结论。",
        ]
        return items, notes

    def _format_action_line(self, action: ActionItem) -> str:
        owner = action.owner or self._settings.default_task_owner
        prefix = f"{action.action_type}："
        title = action.title[len(prefix) :] if action.title.startswith(prefix) else action.title
        return (
            f"{action.action_type}：{title}。"
            f"负责人：{owner}；截止时间：{action.due_date.isoformat()}；KPI：{action.acceptance_metric}"
        )

    def _build_next_actions(self, draft_actions: list[ActionItem], project_items: list[ProjectDigestItem]) -> list[str]:
        lines: list[str] = []
        for action in draft_actions:
            matched_project = next((item for item in project_items if item.game and item.game in action.title), None)
            if matched_project and action.action_type == "加码" and "付费净 ROI" in matched_project.judgement:
                owner = action.owner or self._settings.default_task_owner
                lines.append(
                    f"优化回本：{matched_project.game}。负责人：{owner}；截止时间：{action.due_date.isoformat()}；"
                    "KPI：先把付费净 ROI 拉到 1.00 以上，再评估是否补量"
                )
                continue
            lines.append(self._format_action_line(action))
        return lines

    @staticmethod
    def _section_title(text: str) -> dict[str, Any]:
        return {"tag": "div", "text": {"tag": "lark_md", "content": f"**{text}**"}}

    @staticmethod
    def _markdown_block(text: str) -> dict[str, Any]:
        return {"tag": "div", "text": {"tag": "lark_md", "content": text}}

    @staticmethod
    def _metric_fields(metrics: list[MetricItem]) -> dict[str, Any]:
        fields = [
            {
                "is_short": True,
                "text": {"tag": "lark_md", "content": f"**{metric.label}**\n{metric.value}"},
            }
            for metric in metrics
        ]
        return {"tag": "div", "fields": fields}

    @staticmethod
    def _is_total_row(row: AdsPerformanceRow) -> bool:
        return row.country == "All" and row.channel == "All"

    def _split_window_ads(
        self,
        ads_rows: list[AdsPerformanceRow],
        start_date: date,
        end_date: date,
    ) -> tuple[list[AdsPerformanceRow], list[AdsPerformanceRow]]:
        total_rows: list[AdsPerformanceRow] = []
        detail_rows: list[AdsPerformanceRow] = []
        for row in ads_rows:
            if not (start_date <= row.date <= end_date):
                continue
            if self._is_total_row(row):
                total_rows.append(row)
            else:
                detail_rows.append(row)
        return total_rows, detail_rows

    def _trusted_detail_rows(self, rows: list[AdsPerformanceRow]) -> list[AdsPerformanceRow]:
        trusted_projects = self._settings.trusted_detail_project_keys
        return [row for row in rows if self._project_key(row.game) in trusted_projects]

    @staticmethod
    def _aligned_revenue_rows(
        revenue_rows: list[RevenueRow],
        start_date: date,
        end_date: date,
        active_games: set[str],
    ) -> list[RevenueRow]:
        rows = [row for row in revenue_rows if start_date <= row.date <= end_date]
        if active_games:
            rows = [row for row in rows if row.game in active_games]
        return rows

    def _coverage_note(
        self,
        trusted_detail_projects: set[str],
        active_revenue_projects: set[str],
        company_scope: str,
    ) -> str:
        if company_scope == "company":
            if trusted_detail_projects and active_revenue_projects and trusted_detail_projects != active_revenue_projects:
                revenue_list = "、".join(sorted(active_revenue_projects)[:6])
                revenue_suffix = " 等项目" if len(active_revenue_projects) > 6 else ""
                detail_list = "、".join(sorted(trusted_detail_projects)[:4])
                detail_suffix = " 等项目" if len(trusted_detail_projects) > 4 else ""
                return (
                    f"项目段已按 Adjust 项目口径覆盖 {revenue_list}{revenue_suffix}；"
                    f"其中仅 {detail_list}{detail_suffix} 已接入可信飞书明细。"
                )
            if active_revenue_projects:
                revenue_list = "、".join(sorted(active_revenue_projects)[:6])
                revenue_suffix = " 等项目" if len(active_revenue_projects) > 6 else ""
                return f"项目段已按 Adjust 项目口径覆盖 {revenue_list}{revenue_suffix}。"
            return "公司段按 Adjust 公司整体口径统计。"
        if trusted_detail_projects and active_revenue_projects and trusted_detail_projects != active_revenue_projects:
            game_list = "、".join(sorted(trusted_detail_projects)[:4])
            suffix = " 等项目" if len(trusted_detail_projects) > 4 else ""
            return f"当前公司段按已接入投放项目口径统计，当前覆盖 {game_list}{suffix}。"
        return ""

    @staticmethod
    def _project_key(name: str) -> str:
        cleaned = (name or "").strip()
        if not cleaned:
            return ""
        code_match = re.search(r"\bP0*([0-9]+)\b", cleaned.upper())
        if code_match:
            return f"P{int(code_match.group(1)):02d}"
        simplified = re.sub(r"(?i)\bamazon\b", "", cleaned)
        simplified = re.sub(r"\s+", " ", simplified).strip(" -")
        return simplified or cleaned

    def _project_display_name(self, project_key: str, names: set[str]) -> str:
        if not names:
            return project_key or "未命名项目"

        def score(name: str) -> tuple[int, int, int]:
            return (
                1 if re.search(r"\bP0*[0-9]+\b", name.upper()) else 0,
                1 if "amazon" not in name.lower() else 0,
                len(name),
            )

        return max(names, key=score)

    def _load_company_sheet_summary(self, report_date: date) -> dict[str, Any] | None:
        if not self._feishu_client or not self._settings.feishu_overview_url:
            return None
        try:
            base_rows = self._load_company_metric_rows("基础数据-发行-市场部门", value_index=1, aux_index=3)
            roi_rows = self._load_company_metric_rows("ROI-发行-市场部门", value_index=5)
            breakdown_rows = self._load_company_breakdown_rows(report_date)
        except Exception:
            return None

        if not base_rows:
            return None

        window_start = report_date - timedelta(days=6)
        previous_start = window_start - timedelta(days=7)
        previous_end = window_start - timedelta(days=1)

        current_base = [row for row in base_rows if window_start <= row["date"] <= report_date]
        previous_base = [row for row in base_rows if previous_start <= row["date"] <= previous_end]
        if not current_base:
            return None

        current_spend = sum(row["value"] for row in current_base)
        previous_spend = sum(row["value"] for row in previous_base)

        top_channel = "n/a"
        weakest_segment = "暂无可判定风险段"
        if breakdown_rows:
            current_breakdowns = [row for row in breakdown_rows if window_start <= row["date"] <= report_date]
            spend_by_breakdown: dict[str, float] = defaultdict(float)
            roi_by_breakdown: dict[str, list[float]] = defaultdict(list)
            for row in current_breakdowns:
                spend_by_breakdown[row["label"]] += row["spend"]
                roi_by_breakdown[row["label"]].append(row["roi"])
            if spend_by_breakdown:
                top_channel = max(spend_by_breakdown, key=spend_by_breakdown.get)
            if roi_by_breakdown:
                weakest_segment = min(roi_by_breakdown, key=lambda key: mean(roi_by_breakdown[key]))

        return {
            "current_spend": current_spend,
            "previous_spend": previous_spend,
            "top_channel": top_channel,
            "weakest_segment": weakest_segment,
        }

    def _load_company_metric_rows(
        self,
        sheet_title: str,
        *,
        value_index: int,
        aux_index: int | None = None,
    ) -> list[dict[str, Any]]:
        if not self._feishu_client or not self._settings.feishu_overview_url:
            return []
        sheet_id = self._feishu_client.find_sheet_id_by_title(self._settings.feishu_overview_url, sheet_title)
        values = self._feishu_client.read_values(self._settings.feishu_overview_url, "A1:Q500", sheet_id=sheet_id)
        rows: list[dict[str, Any]] = []
        for row in values[1:]:
            if not row:
                continue
            row_date = self._parse_cn_date(row[0] if len(row) > 0 else None)
            if row_date is None:
                continue
            value = self._parse_numeric(row[value_index] if len(row) > value_index else None)
            aux_value = self._parse_numeric(row[aux_index] if aux_index is not None and len(row) > aux_index else None)
            rows.append({"date": row_date, "value": value, "aux": aux_value})
        return rows

    def _load_company_breakdown_rows(self, report_date: date) -> list[dict[str, Any]]:
        if not self._feishu_client or not self._settings.feishu_overview_url:
            return []

        sheets = self._feishu_client.list_sheets(self._settings.feishu_overview_url)
        base_sheets = {
            sheet["title"]: sheet["sheet_id"]
            for sheet in sheets
            if str(sheet["title"]).startswith("基础数据-") and str(sheet["title"]) != "基础数据-发行-市场部门"
        }
        roi_sheets = {
            sheet["title"]: sheet["sheet_id"]
            for sheet in sheets
            if str(sheet["title"]).startswith("ROI-") and str(sheet["title"]) != "ROI-发行-市场部门"
        }

        rows: list[dict[str, Any]] = []
        for title, sheet_id in base_sheets.items():
            label = title.replace("基础数据-", "")
            base_values = self._feishu_client.read_values(self._settings.feishu_overview_url, "A1:G500", sheet_id=sheet_id)
            roi_sheet_id = roi_sheets.get(f"ROI-{label}")
            roi_values = (
                self._feishu_client.read_values(self._settings.feishu_overview_url, "A1:G500", sheet_id=roi_sheet_id)
                if roi_sheet_id
                else []
            )
            roi_map = {
                row_date: self._parse_numeric(row[5] if len(row) > 5 else None) / 100.0
                for row in roi_values[1:]
                if (row_date := self._parse_cn_date(row[0] if row else None)) is not None
            }
            for row in base_values[1:]:
                if not row:
                    continue
                row_date = self._parse_cn_date(row[0] if len(row) > 0 else None)
                if row_date is None:
                    continue
                rows.append(
                    {
                        "date": row_date,
                        "label": label,
                        "spend": self._parse_numeric(row[1] if len(row) > 1 else None),
                        "roi": roi_map.get(row_date, self._parse_numeric(row[5] if len(row) > 5 else None) / 100.0),
                    }
                )
        return rows

    @staticmethod
    def _parse_cn_date(value: Any) -> date | None:
        text = str(value or "").strip()
        match = re.match(r"(\d{4})/(\d{1,2})/(\d{1,2})", text)
        if not match:
            return None
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))

    @staticmethod
    def _parse_numeric(value: Any) -> float:
        text = str(value or "").replace("$", "").replace(",", "").replace("%", "").strip()
        if not text or text.lower() == "none":
            return 0.0
        return float(text)

    @staticmethod
    def _is_blacklisted_adjust_app(game: str) -> bool:
        blocked_names = (
            "Mergeland - Merge Dragons and Build dragon home",
            "Merge Legend",
            "Merge Legend Amazon",
            "Test App",
            "Placeholder",
        )
        normalized = (game or "").strip()
        return any(name in normalized for name in blocked_names)

    @staticmethod
    def _adjust_recovery_day_mapping() -> dict[int, int]:
        return {
            1: 0,
            2: 1,
            3: 2,
            4: 3,
            5: 4,
            6: 5,
            7: 6,
            14: 13,
            21: 20,
            30: 29,
            60: 59,
            100: 99,
        }

    def _extract_adjust_roi(self, row: dict[str, Any], spend: float, metric_suffix: int) -> float:
        if spend <= 0:
            return 0.0
        iap_revenue = self._parse_numeric(row.get(f"revenue_total_d{metric_suffix}"))
        ad_revenue = self._parse_numeric(row.get(f"ad_revenue_total_d{metric_suffix}"))
        roas_value = self._parse_numeric(row.get(f"roas_d{metric_suffix}"))
        if iap_revenue <= 0 and roas_value > 0:
            iap_revenue = roas_value * spend
        iap_factor = self._adjust_client.iap_revenue_factor if self._adjust_client else 1.0
        total_revenue = iap_revenue * iap_factor + ad_revenue
        return total_revenue / spend if total_revenue > 0 else 0.0

    @staticmethod
    def _build_adjust_ratio_map(roi_by_day: dict[int, float]) -> dict[str, float]:
        ratio_pairs = ((3, 2), (7, 2), (14, 7), (30, 7), (60, 30), (100, 60))
        ratios: dict[str, float] = {}
        for high_day, low_day in ratio_pairs:
            high_value = roi_by_day.get(high_day)
            low_value = roi_by_day.get(low_day)
            if high_value and low_value:
                ratios[f"{high_day}/{low_day}"] = high_value / low_value
        return ratios

    @staticmethod
    def _top_channel(rows: list[AdsPerformanceRow]) -> str:
        if not rows:
            return "n/a"
        spend_by_channel: dict[str, float] = defaultdict(float)
        for row in rows:
            spend_by_channel[row.channel or "Unknown"] += row.spend
        return max(spend_by_channel, key=spend_by_channel.get)

    @staticmethod
    def _pct_change(current: float, previous: float) -> str:
        if previous == 0:
            return "无上周可比基数"
        delta = (current - previous) / previous
        return f"{delta:+.1%}"

    @staticmethod
    def _top_growth_game(
        current_revenue_rows: list[RevenueRow],
        previous_revenue_rows: list[RevenueRow],
        current_ads_rows: list[AdsPerformanceRow],
        previous_ads_rows: list[AdsPerformanceRow],
    ) -> str:
        current_by_game: dict[str, float] = defaultdict(float)
        previous_by_game: dict[str, float] = defaultdict(float)
        for row in current_revenue_rows:
            current_by_game[row.game] += row.total_revenue
        for row in previous_revenue_rows:
            previous_by_game[row.game] += row.total_revenue

        if current_by_game or previous_by_game:
            candidates = set(current_by_game) | set(previous_by_game)
            growth_by_game = {
                game: current_by_game.get(game, 0.0) - previous_by_game.get(game, 0.0)
                for game in candidates
            }
            return max(growth_by_game, key=growth_by_game.get)

        current_spend_by_game: dict[str, float] = defaultdict(float)
        previous_spend_by_game: dict[str, float] = defaultdict(float)
        for row in current_ads_rows:
            current_spend_by_game[row.game] += row.spend
        for row in previous_ads_rows:
            previous_spend_by_game[row.game] += row.spend
        if current_spend_by_game or previous_spend_by_game:
            candidates = set(current_spend_by_game) | set(previous_spend_by_game)
            growth_by_game = {
                game: current_spend_by_game.get(game, 0.0) - previous_spend_by_game.get(game, 0.0)
                for game in candidates
            }
            return max(growth_by_game, key=growth_by_game.get)
        return "当前主力项目"

    @staticmethod
    def _weakest_segment(ads_rows: list[AdsPerformanceRow]) -> str:
        scored_rows = [row for row in ads_rows if row.spend > 0]
        if not scored_rows:
            return "暂无可判定风险段"

        roas_by_segment: dict[str, list[float]] = defaultdict(list)
        spend_by_segment: dict[str, float] = defaultdict(float)
        for row in scored_rows:
            segment = "/".join(part for part in [row.country, row.channel] if part and part != "All") or "总体"
            roas_by_segment[segment].append(row.roas)
            spend_by_segment[segment] += row.spend

        def segment_score(segment: str) -> tuple[float, float]:
            return (mean(roas_by_segment[segment]), -spend_by_segment[segment])

        return min(roas_by_segment, key=segment_score)

    @staticmethod
    def _best_day(rows: list[AdsPerformanceRow]) -> str:
        if not rows:
            return "暂无最佳单日"
        best_row = max(rows, key=lambda row: row.roas)
        return f"{best_row.date.isoformat()}（ROAS {best_row.roas:.2f}）"

    def _collect_breakdown_creative_signals(
        self,
        rows: list[RevenueBreakdownRow],
        report_date: date | None,
        *,
        project_filter: str = "",
        google_resolver: GoogleCreativeResolver,
    ) -> list[BreakdownCreativeSignal]:
        grouped: dict[tuple[str, str, str, str], BreakdownCreativeSignal] = {}
        window_start = report_date - timedelta(days=6) if report_date is not None else None
        for row in rows:
            row_cost = float(getattr(row, "cost", 0.0) or 0.0)
            row_revenue = float(getattr(row, "total_revenue_gross", 0.0) or 0.0)
            row_installs = float(getattr(row, "installs", 0.0) or 0.0)
            if row_cost <= 0 and row_revenue <= 0 and row_installs <= 0:
                continue
            if report_date is not None and window_start is not None and not (window_start <= row.date <= report_date):
                continue
            project_key = self._project_key(row.game)
            if project_filter and project_key != project_filter:
                continue
            channel = self._normalize_breakdown_channel(getattr(row, "partner", "") or "")
            identity = self._resolve_breakdown_creative_identity(
                row=row,
                channel=channel,
                google_resolver=google_resolver,
            )
            if identity is None:
                continue
            identity_id, identity_name, identity_mode, resolution_quality = identity
            key = (project_key, channel, identity_id, identity_name)
            if key not in grouped:
                grouped[key] = BreakdownCreativeSignal(
                    project_key=project_key,
                    project_name=str(getattr(row, "game", "") or "").strip(),
                    channel=channel,
                    creative_id=identity_id,
                    creative_name=identity_name,
                    identity_mode=identity_mode,
                    resolution_quality=resolution_quality,
                    spend=0.0,
                    revenue=0.0,
            )
            item = grouped[key]
            item.spend += row_cost
            item.revenue += row_revenue
            item.installs += row_installs
        return sorted(
            [item for item in grouped.values() if item.spend > 0],
            key=lambda item: (item.roi, item.spend, item.revenue),
            reverse=True,
        )

    def _build_breakdown_creative_digest(
        self,
        signals: list[BreakdownCreativeSignal],
    ) -> tuple[list[CreativeDigestItem], list[str]]:
        valid_sample_signals = [item for item in signals if item.spend >= 50 or item.installs >= 20]
        ranked_valid_sample_signals = sorted(
            valid_sample_signals,
            key=lambda item: (item.roi, item.spend, item.revenue),
            reverse=True,
        )
        ranked_observation_signals = sorted(
            [item for item in signals if item.spend < 50],
            key=lambda item: (item.spend, item.revenue, item.roi),
            reverse=True,
        )
        ranked_all_signals = ranked_valid_sample_signals + ranked_observation_signals
        top_assets = ranked_all_signals[:3]
        if "Google" not in {item.channel for item in top_assets}:
            google_candidate = next((item for item in ranked_all_signals if item.channel == "Google"), None)
            if google_candidate is not None:
                filtered = [
                    item
                    for item in top_assets
                    if not (
                        item.project_key == google_candidate.project_key
                        and item.channel == google_candidate.channel
                        and item.creative_id == google_candidate.creative_id
                        and item.creative_name == google_candidate.creative_name
                    )
                ]
                top_assets = filtered[:2] + [google_candidate]
        items = [
            CreativeDigestItem(
                asset_id=item.creative_id,
                creative_type=self._breakdown_creative_type_label(item),
                roas=item.roi,
                ctr=0.0,
                status=f"花费 {item.spend:.0f} / 收入 {item.revenue:.0f}",
                game=item.project_name,
                channel=item.channel,
                spend=item.spend,
                installs=item.installs,
                revenue=item.revenue,
            )
            for item in top_assets
        ]
        if not signals:
            return [], []

        channel_counts: dict[str, int] = defaultdict(int)
        positive_count = 0
        low_roi_count = 0
        resolved_count = 0
        proxy_count = 0
        for item in signals:
            channel_counts[item.channel] += 1
            if item.roi >= 1:
                positive_count += 1
            if item.spend > 0 and item.roi < 0.3:
                low_roi_count += 1
            if item.resolution_quality.startswith("resolved"):
                resolved_count += 1
            elif item.resolution_quality.startswith("proxy"):
                proxy_count += 1

        dominant_channel = max(channel_counts, key=channel_counts.get)
        notes = [
            (
                f"本周达到最低样本门槛（花费≥50 或 安装≥20）的素材候选共有 {len(valid_sample_signals)} 条；"
                "未过门槛的素材统一只作为观察样本，不直接下复制结论。"
            ),
            f"当前素材层以 `{dominant_channel}` 渠道代理广告层样本为主，可继续观察已验证回收的方向。",
            f"本周按 Adjust 素材明细共识别到 {len(signals)} 条有效素材，其中已过 1.00 ROI 的素材 {positive_count} 条。",
            f"当前有 {low_roi_count} 条素材已有花费但总收入 ROI 仍低于 0.30，建议先复核归因并降低优先级，不直接作为停测结论。",
        ]
        google_proxy_candidate = next(
            (item for item in ranked_all_signals if item.channel == "Google" and item.resolution_quality.startswith("proxy")),
            None,
        )
        if google_proxy_candidate is not None:
            notes.append(
                "Google 侧当前补充保留 1 条代理素材观察项，"
                f"对象为 `{google_proxy_candidate.creative_id}`，"
                "仅用于方向判断，不直接作为复制依据。"
            )
        return items, notes

    @staticmethod
    def _normalize_breakdown_channel(value: str) -> str:
        normalized = (value or "").strip().lower()
        if "google" in normalized:
            return "Google"
        if "facebook" in normalized or "instagram" in normalized or "off-facebook" in normalized or "meta" in normalized:
            return "Facebook"
        return value or "未知渠道"

    @staticmethod
    def _is_valid_breakdown_creative_id(creative_id: str, creative_name: str) -> bool:
        creative_id_key = (creative_id or "").strip().lower()
        creative_name_key = (creative_name or "").strip().lower()
        invalid_values = {"", "-", "display", "youtube youtubevideos", "search googlesearch", "unknown", "(not set)", "nan", "none"}
        if creative_id_key in invalid_values:
            return False
        if creative_name_key in invalid_values:
            return False
        return True

    def _resolve_breakdown_creative_identity(
        self,
        *,
        row: RevenueBreakdownRow,
        channel: str,
        google_resolver: GoogleCreativeResolver,
    ) -> tuple[str, str, str, str] | None:
        creative_id = str(getattr(row, "creative_id", "") or "").strip()
        creative_name = str(getattr(row, "creative_name", "") or "").strip()
        if channel == "Google":
            resolved = google_resolver.resolve(row)
            if resolved is None:
                return None
            return (
                resolved.identity_id,
                resolved.identity_name,
                resolved.identity_mode,
                resolved.resolution_quality,
            )
        if self._is_valid_breakdown_creative_id(creative_id, creative_name):
            return creative_id or creative_name, creative_name or creative_id, "creative_id", "resolved"
        return None

    def _top_creative(
        self,
        rows: list[CreativeAssetRow],
        revenue_breakdown_rows: list[RevenueBreakdownRow] | None = None,
        *,
        project_key: str = "",
        project_name: str = "",
        google_resolver: GoogleCreativeResolver | None = None,
    ) -> str:
        if revenue_breakdown_rows and google_resolver is not None:
            breakdown_signals = self._collect_breakdown_creative_signals(
                revenue_breakdown_rows,
                None,
                project_filter=project_key,
                google_resolver=google_resolver,
            )
            if breakdown_signals:
                best_signal = max(
                    breakdown_signals,
                    key=lambda item: (item.roi, item.spend, item.revenue),
                )
                identity_label = self._signal_identity_label(best_signal)
                display_project = project_name or best_signal.project_name or project_key
                if display_project:
                    return f"{best_signal.creative_id}（{identity_label} / {display_project}）"
                return f"{best_signal.creative_id}（{identity_label}）"
        if not rows:
            return "暂无明确优胜素材"
        best_row = max(rows, key=lambda row: (row.roas, row.ctr, row.spend))
        creative_type = best_row.hook_type or best_row.creative_type or "未标记"
        return f"{best_row.asset_id}（{creative_type}）"

    @staticmethod
    def _signal_identity_label(signal: BreakdownCreativeSignal) -> str:
        if signal.resolution_quality == "resolved_api":
            return f"{signal.channel} / API素材"
        if signal.resolution_quality == "resolved":
            return signal.channel
        if signal.identity_mode == "source_proxy":
            return f"{signal.channel} / 来源代理"
        if signal.identity_mode == "adgroup_proxy":
            return f"{signal.channel} / 广告组代理"
        if signal.identity_mode == "campaign_proxy":
            return f"{signal.channel} / Campaign代理"
        return f"{signal.channel} / 代理素材"

    def _project_profit_split(self, rows: list[RevenueBreakdownRow]) -> str:
        if not rows:
            return "待补商店/渠道盈利拆分"
        by_store: dict[str, dict[str, float]] = defaultdict(lambda: {"cost": 0.0, "revenue": 0.0})
        by_channel: dict[str, dict[str, float]] = defaultdict(lambda: {"cost": 0.0, "revenue": 0.0})
        for row in rows:
            cost = float(getattr(row, "cost", 0.0) or 0.0)
            revenue = float(getattr(row, "total_revenue_gross", 0.0) or 0.0)
            store = self._normalize_store(str(getattr(row, "store", "") or ""))
            channel = self._normalize_breakdown_channel(getattr(row, "partner", "") or "")
            by_store[store]["revenue"] += revenue
            by_channel[channel]["revenue"] += revenue
            if cost > 0:
                by_store[store]["cost"] += cost
                by_channel[channel]["cost"] += cost
        good_stores = []
        weak_stores = []
        for name, metrics in by_store.items():
            roi = metrics["revenue"] / metrics["cost"] if metrics["cost"] else 0.0
            (good_stores if roi >= 1 else weak_stores).append(f"{name} {roi:.2f}")
        good_channels = []
        weak_channels = []
        for name, metrics in by_channel.items():
            roi = metrics["revenue"] / metrics["cost"] if metrics["cost"] else 0.0
            (good_channels if roi >= 1 else weak_channels).append(f"{name} {roi:.2f}")
        return (
            f"商店赚钱={', '.join(good_stores) or '无'}；商店偏弱={', '.join(weak_stores) or '无'}；"
            f"渠道赚钱={', '.join(good_channels) or '无'}；渠道偏弱={', '.join(weak_channels) or '无'}"
        )

    def _project_structure_note(self, rows: list[RevenueBreakdownRow]) -> str:
        scoped = [row for row in rows if float(getattr(row, "cost", 0.0) or 0.0) > 0]
        if not scoped:
            return "项目盈利结构当前可信度不足：缺少项目级 breakdown 结构明细"
        stores = {self._normalize_store(str(getattr(row, "store", "") or "")) for row in scoped}
        channels = {self._normalize_breakdown_channel(getattr(row, "partner", "") or "") for row in scoped}
        if not stores or not channels:
            return "项目盈利结构当前可信度不足：缺少项目级商店或渠道字段"
        if len(stores) < 2 and len(channels) < 2:
            return "项目盈利结构当前可信度有限：当前只有单商店单渠道结构，暂不输出商店/渠道强结论"
        if len(stores) < 2:
            return "项目盈利结构当前可信度有限：当前只有单商店多渠道结构，无法判断商店差异"
        if len(channels) < 2:
            return "项目盈利结构当前可信度有限：当前只有多商店单渠道结构，无法判断渠道差异"
        return ""

    @staticmethod
    def _normalize_store(value: str) -> str:
        normalized = (value or "").strip().lower()
        mapping = {"app_store": "iOS", "google_play": "Android", "amazon": "Amazon"}
        return mapping.get(normalized, value or "未知商店")

    def _breakdown_creative_type_label(self, item: BreakdownCreativeSignal) -> str:
        return f"{item.project_key} / {self._signal_identity_label(item)}"

    @staticmethod
    def _focus_line(current_roi: float, risk_segment: str) -> str:
        if current_roi >= 1:
            return f"继续复制高回收素材，同时压缩 {risk_segment} 的低效预算。"
        return f"先控制 {risk_segment} 的低回收花费，再补充可复制的高回收素材测试。"

    @staticmethod
    def _project_action_judgement(
        avg_roas: float,
        risk_segment: str,
        top_creative: str,
        detail_ready: bool,
        paid_roi_net: float | None = None,
    ) -> str:
        if not detail_ready:
            if avg_roas >= 1:
                return "当前项目总回收已过线，可以继续看量，但渠道与素材细分仍待补接。"
            if avg_roas >= 0.3:
                return "当前项目总回收尚可，先保持观察，待补齐渠道细分后再做更细的加减量决策。"
            return "当前项目总回收偏弱，建议先控量，并尽快补齐飞书渠道明细。"
        if avg_roas >= 0.3:
            return f"可以谨慎加预算，但只放在已验证回收的组合，同时继续复制 {top_creative}。"
        if avg_roas >= 0.1:
            return f"暂时不宜激进放量，先稳住预算，并优先处理 {risk_segment}。"
        return f"应先收预算，再补素材测试，尤其先处理 {risk_segment}。"
    @staticmethod
    def _project_action_judgement_paid(
        avg_roas: float,
        risk_segment: str,
        top_creative: str,
        detail_ready: bool,
        paid_roi_net: float | None = None,
    ) -> str:
        if not detail_ready:
            if avg_roas >= 1:
                return "当前项目总回收已过线，可以继续看量，但渠道与素材细分仍待补接。"
            if avg_roas >= 0.3:
                return "当前项目总回收尚可，先保持观察，待补齐渠道细分后再做更细的加减量决策。"
            return "当前项目总回收偏弱，建议先控量，并尽快补齐飞书渠道明细。"
        if paid_roi_net is not None and paid_roi_net < 1:
            if paid_roi_net >= 0.6:
                return (
                    f"按付费净 ROI 口径看仍未回本（{paid_roi_net:.2f}），暂时不建议加量，"
                    f"先在小额预算下继续验证，同时继续复制 {top_creative}。"
                )
            return f"按付费净 ROI 口径看回本偏弱（{paid_roi_net:.2f}），应先控量，并优先处理 {risk_segment}。"
        if avg_roas >= 1:
            return f"可以只在已验证回收的组合上小幅补量，同时继续复制 {top_creative}。"
        if avg_roas >= 0.3:
            return f"可以只在已验证回收的组合上小幅测试，但暂不建议直接放量，同时继续复制 {top_creative}。"
        if avg_roas >= 0.1:
            return f"暂时不宜激进放量，先稳住预算，并优先处理 {risk_segment}。"
        return f"应先收预算，再补素材测试，尤其先处理 {risk_segment}。"

    @classmethod
    def _paid_roi_net(cls, rows: list[RevenueBreakdownRow]) -> float | None:
        if not rows:
            return None
        total_cost = sum(row.cost for row in rows if row.cost > 0)
        if total_cost <= 0:
            return None
        total_net_revenue = sum(cls._net_total_revenue(row) for row in rows if row.cost > 0)
        return total_net_revenue / total_cost if total_cost else None

    @classmethod
    def _net_total_revenue(cls, row: RevenueBreakdownRow) -> float:
        return row.iap_revenue_gross * cls._net_iap_rate(row.store) + row.ad_revenue

    @staticmethod
    def _net_iap_rate(store: str) -> float:
        store_key = (store or "").strip().lower()
        if "amazon" in store_key:
            return 0.8
        if any(keyword in store_key for keyword in ("google", "android", "play")):
            return 0.85
        if any(keyword in store_key for keyword in ("ios", "apple", "itunes", "app_store")):
            return 0.7
        return 0.7

    @staticmethod
    def _project_action_judgement_paid_v2(
        avg_roas: float,
        risk_segment: str,
        top_creative: str,
        detail_ready: bool,
        paid_roi_net: float | None = None,
    ) -> str:
        if paid_roi_net is not None and paid_roi_net < 1:
            if paid_roi_net >= 0.6:
                return (
                    f"按付费净 ROI 口径看仍未回本（{paid_roi_net:.2f}），暂时不建议加量，"
                    f"先在小额预算下继续验证，同时继续复制 {top_creative}。"
                )
            return f"按付费净 ROI 口径看回本偏弱（{paid_roi_net:.2f}），应先控量，并优先处理 {risk_segment}。"
        if not detail_ready:
            if avg_roas >= 1:
                return "当前项目总回收已过线，可以继续看量，但渠道与素材细分仍待补接。"
            if avg_roas >= 0.3:
                return "当前项目总回收尚可，先保持观察，待补齐渠道细分后再做更细的加减量决策。"
            return "当前项目总回收偏弱，建议先控量，并尽快补齐飞书渠道明细。"
        if avg_roas >= 1:
            return f"可以只在已验证回收的组合上小幅补量，同时继续复制 {top_creative}。"
        if avg_roas >= 0.3:
            return f"可以只在已验证回收的组合上小幅测试，但暂不建议直接放量，同时继续复制 {top_creative}。"
        if avg_roas >= 0.1:
            return f"暂时不宜激进放量，先稳住预算，并优先处理 {risk_segment}。"
        return f"应先收预算，再补素材测试，尤其先处理 {risk_segment}。"
