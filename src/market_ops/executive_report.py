from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from statistics import median
from typing import Any

from market_ops.config import Settings
from market_ops.google_creative_resolver import GoogleCreativeResolver
from market_ops.models import AdsPerformanceRow, CreativeAssetRow, RevenueBreakdownRow, RevenueRow
from market_ops.payback_targets import PaybackTargetsBuilder, ProjectTargets


FACEBOOK_LABELS = {"facebook", "meta", "fb"}
GOOGLE_LABELS = {"google", "adwords", "google ads"}
CHANNEL_REVENUE_ANOMALY_THRESHOLD = 0.20
CREATIVE_MIN_EFFECTIVE_SPEND = 100
CREATIVE_MIN_EFFECTIVE_INSTALLS = 30
CREATIVE_STOP_LOSS_SPEND = 150
CREATIVE_STOP_LOSS_ROI = 0.35
CREATIVE_SCALE_ROI = 1.15


@dataclass(slots=True)
class ConfidenceScore:
    module: str
    score: int
    level: str
    risk_level: str
    status: str
    reasons: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AnomalyItem:
    anomaly_type: str
    scope: str
    severity: str
    message: str


@dataclass(slots=True)
class ClosedLoopAction:
    problem: str
    reason: str
    action: str
    owner: str
    due_date: date
    verification_metric: str


@dataclass(slots=True)
class ExecutiveMetric:
    label: str
    current: float
    previous: float
    change: str


@dataclass(slots=True)
class ExecutiveProjectItem:
    project: str
    spend: float
    revenue: float
    roi: float
    payback_gate: str
    profit_split: str
    structure_confidence_level: str
    risk_judgement: str
    suggested_action: str
    confidence_level: str
    confidence_note: str
    action: ClosedLoopAction


@dataclass(slots=True)
class ExecutiveCampaignItem:
    project: str
    channel: str
    campaign: str
    country: str
    spend: float
    revenue: float
    roi: float
    payback_gate: str
    scope_priority: int
    risk_judgement: str
    suggested_action: str
    confidence_level: str
    scope_note: str
    action: ClosedLoopAction


@dataclass(slots=True)
class ExecutiveCreativeItem:
    project: str
    channel: str
    creative_id: str
    creative_name: str
    spend: float
    installs: float
    revenue: float
    roi: float
    ctr: float
    sample_status: str
    risk_judgement: str
    suggested_action: str
    confidence_level: str
    action: ClosedLoopAction


@dataclass(slots=True)
class BreakdownCreativeCandidate:
    project: str
    channel: str
    creative_id: str
    creative_name: str
    spend: float
    revenue: float
    installs: float
    ctr: float
    resolution_quality: str
    sample_status: str


@dataclass(slots=True)
class ExecutiveReport:
    title: str
    period_label: str
    report_date: date
    summary_lines: list[str]
    business_metrics: list[ExecutiveMetric]
    confidence_scores: list[ConfidenceScore]
    project_items: list[ExecutiveProjectItem]
    campaign_items: list[ExecutiveCampaignItem]
    creative_items: list[ExecutiveCreativeItem]
    anomalies: list[AnomalyItem]
    next_actions: list[ClosedLoopAction]
    max_risk: str
    max_opportunity: str
    data_confidence_line: str


class ExecutiveReportBuilder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._default_project_key = self._project_key(settings.default_game_name)
        self._trusted_project_keys = set(settings.trusted_detail_project_keys or {self._default_project_key})

    def build(
        self,
        period: str,
        report_date: date,
        ads_rows: list[AdsPerformanceRow],
        creative_rows: list[CreativeAssetRow],
        revenue_rows: list[RevenueRow],
        revenue_breakdown_rows: list[RevenueBreakdownRow] | None = None,
        market_digest: Any | None = None,
    ) -> ExecutiveReport:
        current_start, current_end, previous_start, previous_end, period_label = self._period_bounds(period, report_date)
        current_revenue_rows = [row for row in revenue_rows if current_start <= row.date <= current_end]
        previous_revenue_rows = [row for row in revenue_rows if previous_start <= row.date <= previous_end]
        current_breakdown_rows = [row for row in (revenue_breakdown_rows or []) if current_start <= row.date <= current_end]
        previous_breakdown_rows = [row for row in (revenue_breakdown_rows or []) if previous_start <= row.date <= previous_end]
        current_creative_rows = [row for row in creative_rows if row.spend > 0 or row.installs > 0 or row.revenue_value > 0 or row.roas > 0]
        current_ads_rows = [row for row in ads_rows if current_start <= row.date <= current_end]
        payback_targets_map = self._load_payback_targets_map(report_date)

        business_metrics = self._build_business_metrics(current_revenue_rows, previous_revenue_rows)
        confidence_scores = self._build_confidence_scores(
            current_revenue_rows,
            current_breakdown_rows,
            current_creative_rows,
        )
        anomalies = self._build_anomalies(
            current_revenue_rows=current_revenue_rows,
            current_breakdown_rows=current_breakdown_rows,
            current_creative_rows=current_creative_rows,
            current_ads_rows=current_ads_rows,
            confidence_scores=confidence_scores,
        )
        if market_digest is not None and getattr(market_digest, "project_items", None):
            project_items = self._build_project_items_from_digest(market_digest)
        else:
            project_items = self._build_project_items(
                current_revenue_rows=current_revenue_rows,
                previous_revenue_rows=previous_revenue_rows,
                current_breakdown_rows=current_breakdown_rows,
                previous_breakdown_rows=previous_breakdown_rows,
                confidence_scores=confidence_scores,
                report_date=report_date,
                payback_targets_map=payback_targets_map,
            )
        if market_digest is not None and getattr(market_digest, "campaign_items", None):
            campaign_items = self._build_campaign_items_from_digest(market_digest)
        else:
            campaign_items = self._build_campaign_items(
                current_breakdown_rows=current_breakdown_rows,
                confidence_scores=confidence_scores,
                report_date=report_date,
                payback_targets_map=payback_targets_map,
            )
        creative_items = self._build_creative_items(
            current_creative_rows=current_creative_rows,
            current_breakdown_rows=current_breakdown_rows,
            confidence_scores=confidence_scores,
            report_date=report_date,
        )

        next_actions = self._collect_next_actions(project_items, campaign_items, creative_items)
        max_risk = self._build_max_risk(project_items, campaign_items, anomalies)
        max_opportunity = self._build_max_opportunity(project_items, campaign_items, creative_items, confidence_scores)
        data_confidence_line = self._build_confidence_line(confidence_scores)
        summary_lines = self._build_summary_lines(
            business_metrics=business_metrics,
            current_breakdown_rows=current_breakdown_rows,
            max_risk=max_risk,
            max_opportunity=max_opportunity,
            next_actions=next_actions,
            data_confidence_line=data_confidence_line,
            confidence_scores=confidence_scores,
            market_digest=market_digest,
        )

        title = (
            f"管理层决策周报 | {report_date.isoformat()}"
            if period == "weekly"
            else f"管理层决策月报 | {report_date.isoformat()}"
        )
        return ExecutiveReport(
            title=title,
            period_label=period_label,
            report_date=report_date,
            summary_lines=summary_lines,
            business_metrics=business_metrics,
            confidence_scores=confidence_scores,
            project_items=project_items,
            campaign_items=campaign_items,
            creative_items=creative_items,
            anomalies=anomalies,
            next_actions=next_actions,
            max_risk=max_risk,
            max_opportunity=max_opportunity,
            data_confidence_line=data_confidence_line,
        )

    def save_markdown(self, report: ExecutiveReport, output_dir: Path, period: str) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"executive_report_{period}_{report.report_date.strftime('%Y%m%d')}.md"
        lines = [self.render_markdown(report).rstrip()]
        growth_lines = self._load_growth_priority_lines(report.report_date)
        if growth_lines:
            lines.extend(["", "## \u589e\u957f\u673a\u4f1a", ""])
            lines.extend(f"- {line}" for line in growth_lines)
        path.write_text(chr(10).join(lines) + chr(10), encoding="utf-8")
        return path

    def render_markdown(self, report: ExecutiveReport) -> str:
        lines = [f"# {report.title}", "", f"- 周窗口：{report.period_label}", ""]

        lines.extend(["## 第一层：管理层摘要", ""])
        lines.extend(f"- {line}" for line in report.summary_lines)

        lines.extend(["", "## 第二层：项目分析", ""])
        project_items = report.project_items[:3]
        if project_items:
            for item in project_items:
                lines.extend(
                    [
                        f"- {item.project}",
                        f"- 花费 `{item.spend:.0f}`；收入 `{item.revenue:.0f}`；ROI `{item.roi:.2f}`",
                        f"- 回本门槛：{item.payback_gate}",
                        f"- 盈亏拆分：{item.profit_split}",
                        f"- 风险判断：{item.risk_judgement}",
                        f"- 建议动作：{item.suggested_action}",
                        f"- 数据可信度：{item.confidence_level}；{item.confidence_note}",
                        f"- 闭环：问题={item.action.problem}；原因={item.action.reason}；行动={item.action.action}；负责人={item.action.owner}；截止时间={item.action.due_date.isoformat()}；验证指标={item.action.verification_metric}",
                    ]
                )
        else:
            lines.append("- 当前没有可用项目数据。")

        lines.extend(["", "## 第三层：投放分析", ""])
        campaign_items = report.campaign_items[:5]
        if campaign_items:
            for item in campaign_items:
                lines.extend(
                    [
                        f"- {item.project} / {item.channel} / {item.campaign}",
                        f"- 国家 `{item.country}`；花费 `{item.spend:.0f}`；收入 `{item.revenue:.0f}`；ROI `{item.roi:.2f}`",
                        f"- 回本门槛：{item.payback_gate}",
                        f"- 定位层说明：{item.scope_note}",
                        f"- 风险判断：{item.risk_judgement}",
                        f"- 建议动作：{item.suggested_action}",
                        f"- 数据可信度：{item.confidence_level}",
                        f"- 闭环：问题={item.action.problem}；原因={item.action.reason}；行动={item.action.action}；负责人={item.action.owner}；截止时间={item.action.due_date.isoformat()}；验证指标={item.action.verification_metric}",
                    ]
                )
        else:
            lines.append("- 当前没有可用 Campaign 数据。")

        lines.extend(["", "## 第四层：素材分析", ""])
        creative_items = report.creative_items[:6]
        if creative_items:
            for item in creative_items:
                lines.extend(
                    [
                        f"- {item.project} / {item.channel} / {item.creative_id or item.creative_name}",
                        f"- 花费 `{item.spend:.0f}`；安装 `{item.installs:.0f}`；收入 `{item.revenue:.0f}`；ROI `{item.roi:.2f}`；CTR `{item.ctr:.3f}`",
                        f"- 样本状态：{item.sample_status}",
                        f"- 风险判断：{item.risk_judgement}",
                        f"- 建议动作：{item.suggested_action}",
                        f"- 数据可信度：{item.confidence_level}",
                        f"- 闭环：问题={item.action.problem}；原因={item.action.reason}；行动={item.action.action}；负责人={item.action.owner}；截止时间={item.action.due_date.isoformat()}；验证指标={item.action.verification_metric}",
                    ]
                )
        else:
            lines.append("- 当前没有可用 Creative 数据。")

        lines.extend(["", "## 风险清单", ""])
        if report.anomalies:
            lines.extend(
                f"- [{item.severity}] {item.anomaly_type} | {item.scope} | {item.message}"
                for item in report.anomalies[:8]
            )
        else:
            lines.append("- 本期未发现需要升级处理的异常。")

        lines.extend(["", "## 数据可信度", ""])
        for item in report.confidence_scores:
            reason_text = "；".join(item.reasons) if item.reasons else "当前无明显缺口"
            lines.append(
                f"- {item.module}：{item.score}分 | {item.level} | 风险={item.risk_level} | {item.status} | {reason_text}"
            )

        lines.append("")
        return "\n".join(lines)

    def build_card(self, report: ExecutiveReport) -> dict[str, Any]:
        summary_content = "\n".join(f"- {line}" for line in report.summary_lines)

        project_lines = []
        for item in report.project_items[:3]:
            project_lines.append(
                f"- **{item.project}**\n花费 `{item.spend:.0f}` / 收入 `{item.revenue:.0f}` / ROI `{item.roi:.2f}`\n回本门槛：{item.payback_gate}\n盈亏拆分：{item.profit_split}\n风险：{item.risk_judgement}\n动作：{item.suggested_action}\n问题={item.action.problem}\n原因={item.action.reason}\n行动={item.action.action}\n负责人={item.action.owner}\n截止时间={item.action.due_date.isoformat()}\n验证指标={item.action.verification_metric}"
            )
        if not project_lines:
            project_lines.append("- 当前没有可用项目数据。")

        campaign_lines = []
        for item in report.campaign_items[:5]:
            campaign_lines.append(
                f"- **{item.project} / {item.channel} / {item.campaign}**\n国家 `{item.country}` / 花费 `{item.spend:.0f}` / 收入 `{item.revenue:.0f}` / ROI `{item.roi:.2f}`\n回本门槛：{item.payback_gate}\n定位层说明：{item.scope_note}\n风险：{item.risk_judgement}\n动作：{item.suggested_action}\n问题={item.action.problem}\n原因={item.action.reason}\n行动={item.action.action}\n负责人={item.action.owner}\n截止时间={item.action.due_date.isoformat()}\n验证指标={item.action.verification_metric}"
            )
        if not campaign_lines:
            campaign_lines.append("- 当前没有可用 Campaign 数据。")

        creative_lines = []
        for item in report.creative_items[:6]:
            creative_lines.append(
                f"- **{item.project} / {item.channel} / {item.creative_id or item.creative_name}**\n花费 `{item.spend:.0f}` / 安装 `{item.installs:.0f}` / ROI `{item.roi:.2f}` / CTR `{item.ctr:.3f}`\n样本：{item.sample_status}\n风险：{item.risk_judgement}\n动作：{item.suggested_action}\n问题={item.action.problem}\n原因={item.action.reason}\n行动={item.action.action}\n负责人={item.action.owner}\n截止时间={item.action.due_date.isoformat()}\n验证指标={item.action.verification_metric}"
            )
        if not creative_lines:
            creative_lines.append("- 当前没有可用 Creative 数据。")

        confidence_lines = []
        for item in report.confidence_scores:
            reason_text = "；".join(item.reasons) if item.reasons else "当前无明显缺口"
            confidence_lines.append(
                f"- {item.module}：{item.score}分 | {item.level} | 风险={item.risk_level} | {reason_text}"
            )

        risk_lines = []
        for item in report.anomalies[:6]:
            risk_lines.append(f"- [{item.severity}] {item.anomaly_type} | {item.scope} | {item.message}")
        if not risk_lines:
            risk_lines.append("- 本期未发现需要升级处理的异常。")

        elements = [
            self._section("\u7b2c\u4e00\u9875\uff1a\u7ba1\u7406\u5c42\u6458\u8981", summary_content),
            {"tag": "hr"},
        ]
        growth_priority_lines = self._load_growth_priority_lines(report.report_date, limit=4)
        if growth_priority_lines:
            elements.extend([
                self._section("\u589e\u957f\u673a\u4f1a", "\n".join(f"- {line}" for line in growth_priority_lines)),
                {"tag": "hr"},
            ])
        elements.extend([
            self._section("\u6570\u636e\u53ef\u4fe1\u5ea6", "\n".join(confidence_lines)),
            {"tag": "hr"},
            self._section("\u7b2c\u4e8c\u5c42\uff1a\u9879\u76ee\u5206\u6790", "\n".join(project_lines)),
            {"tag": "hr"},
            self._section("\u7b2c\u4e09\u5c42\uff1a\u6295\u653e\u5206\u6790", "\n".join(campaign_lines)),
            {"tag": "hr"},
            self._section("\u7b2c\u56db\u5c42\uff1a\u7d20\u6750\u5206\u6790", "\n".join(creative_lines)),
            {"tag": "hr"},
            self._section("\u98ce\u9669\u6e05\u5355", "\n".join(risk_lines)),
        ])
        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": "orange",
                "title": {"tag": "plain_text", "content": report.title},
            },
            "elements": elements,
        }

    def _load_growth_priority_lines(self, report_date: date, limit: int = 6) -> list[str]:
        path = self._settings.active_output_dir / f"growth_priorities_{report_date.strftime('%Y%m%d')}.json"
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []

        summary = payload.get("summary") or {}
        lines = [
            (
                f"\u589e\u957f\u4f18\u5148\u7ea7\u8bc6\u522b\u5bf9\u8c61 {summary.get('total_items', 0)} \u4e2a\uff1b"
                f"\u589e\u957f\u5019\u9009 {summary.get('scale_candidates', 0)} \u4e2a\uff1b"
                f"\u5c40\u90e8\u7a81\u7834 {summary.get('local_breakthroughs', 0)} \u4e2a\uff1b"
                f"\u9700\u4fee\u590d/\u964d\u6743 {summary.get('repair_or_downweight', 0)} \u4e2a\u3002"
            )
        ]
        for item in (payload.get("top_growth_candidates") or [])[: max(0, limit - 1)]:
            entity_type = str(item.get("entity_type") or "")
            entity_id = str(item.get("entity_id") or "")
            project = str(item.get("project") or "")
            scope = str(item.get("scope") or "")
            stage = str(item.get("growth_stage") or "")
            action = str(item.get("recommended_action") or "")
            budget_change = str(item.get("budget_change") or "")
            try:
                roi = float(item.get("roi") or 0.0)
            except (TypeError, ValueError):
                roi = 0.0
            try:
                spend = float(item.get("spend") or 0.0)
            except (TypeError, ValueError):
                spend = 0.0
            lines.append(
                f"{project} / {entity_type}:{entity_id} / {scope}\uff1a{stage}\uff0cROI {roi:.2f}\uff0c\u82b1\u8d39 {spend:.0f}\uff0c\u5efa\u8bae{action}\uff08{budget_change}\uff09\u3002"
            )
        return lines[:limit]

    def _build_business_metrics(
        self,
        current_rows: list[RevenueRow],
        previous_rows: list[RevenueRow],
    ) -> list[ExecutiveMetric]:
        current_revenue = sum(row.total_revenue for row in current_rows)
        previous_revenue = sum(row.total_revenue for row in previous_rows)
        current_spend = sum(row.total_cost for row in current_rows)
        previous_spend = sum(row.total_cost for row in previous_rows)
        current_profit = current_revenue - current_spend
        previous_profit = previous_revenue - previous_spend
        current_roi = current_revenue / current_spend if current_spend else 0.0
        previous_roi = previous_revenue / previous_spend if previous_spend else 0.0
        return [
            ExecutiveMetric("本周收入", current_revenue, previous_revenue, self._pct_change(current_revenue, previous_revenue)),
            ExecutiveMetric("本周净利润", current_profit, previous_profit, self._pct_change(current_profit, previous_profit)),
            ExecutiveMetric("本周总花费", current_spend, previous_spend, self._pct_change(current_spend, previous_spend)),
            ExecutiveMetric("ROI", current_roi, previous_roi, self._pct_change(current_roi, previous_roi)),
        ]

    def _build_confidence_scores(
        self,
        current_revenue_rows: list[RevenueRow],
        current_breakdown_rows: list[RevenueBreakdownRow],
        current_creative_rows: list[CreativeAssetRow],
    ) -> list[ConfidenceScore]:
        spend_revenue_sum = sum(row.total_cost for row in current_revenue_rows)
        spend_breakdown_sum = sum(row.cost for row in current_breakdown_rows)
        revenue_sum = sum(row.total_revenue for row in current_revenue_rows)
        revenue_breakdown_sum = sum(row.total_revenue_gross for row in current_breakdown_rows)

        spend_conf = self._score_from_gap(
            module="花费",
            left_value=spend_revenue_sum,
            right_value=spend_breakdown_sum,
            empty_message="缺少 Adjust breakdown 花费明细，无法交叉校验。",
        )
        revenue_conf = self._score_from_gap(
            module="收入",
            left_value=revenue_sum,
            right_value=revenue_breakdown_sum,
            empty_message="缺少 Adjust breakdown 收入明细，无法交叉校验。",
        )

        roi_reasons: list[str] = []
        roi_score = min(spend_conf.score, revenue_conf.score)
        if spend_revenue_sum <= 0 or revenue_sum <= 0:
            roi_reasons.append("收入或花费为空，ROI 只可作为观察值。")
            roi_score = min(roi_score, 45)
        if spend_conf.level == "低" or revenue_conf.level == "低":
            roi_reasons.append("ROI 依赖的收入或花费可信度偏低。")
            roi_score = min(roi_score, 55)
        roi_conf = self._score_object("ROI", roi_score, roi_reasons)

        fb_rows = [row for row in current_creative_rows if self._normalize_channel(row.channel) == "Facebook"]
        google_rows = [row for row in current_creative_rows if self._normalize_channel(row.channel) == "Google"]
        breakdown_candidates = self._collect_breakdown_creative_candidates(
            current_breakdown_rows=current_breakdown_rows,
            current_creative_rows=current_creative_rows,
        )
        fb_breakdown = [item for item in breakdown_candidates if item.channel == "Facebook"]
        google_breakdown = [item for item in breakdown_candidates if item.channel == "Google"]
        fb_conf = self._creative_confidence("Facebook素材", fb_rows, "Facebook", fb_breakdown)
        google_conf = self._creative_confidence("Google素材", google_rows, "Google", google_breakdown)
        structure_conf = self._company_structure_confidence(current_breakdown_rows, spend_conf, revenue_conf)
        return [spend_conf, revenue_conf, roi_conf, structure_conf, fb_conf, google_conf]

    def _build_anomalies(
        self,
        *,
        current_revenue_rows: list[RevenueRow],
        current_breakdown_rows: list[RevenueBreakdownRow],
        current_creative_rows: list[CreativeAssetRow],
        current_ads_rows: list[AdsPerformanceRow],
        confidence_scores: list[ConfidenceScore],
    ) -> list[AnomalyItem]:
        anomalies: list[AnomalyItem] = []
        score_map = {item.module: item for item in confidence_scores}
        for module in ("花费", "收入", "ROI"):
            item = score_map[module]
            if item.level == "低":
                anomalies.append(
                    AnomalyItem("数据源不一致", module, "高", "当前跨源校验未通过，不能输出强结论。")
                )

        if current_breakdown_rows:
            costs = [row.cost for row in current_breakdown_rows if row.cost > 0]
            median_cost = median(costs) if costs else 0.0
            grouped_revenue = self._group_breakdown_for_revenue_anomaly(current_breakdown_rows)
            for item in grouped_revenue:
                if item["cost"] > 0 and item["revenue"] <= 0:
                    anomalies.append(
                        AnomalyItem(
                            "收入缺失",
                            item["scope"],
                            "高",
                            "同一项目/渠道/国家/Campaign 聚合后有花费但收入为0，需确认归因是否完整。",
                        )
                    )
            for row in current_breakdown_rows:
                if median_cost > 0 and row.cost > median_cost * 5:
                    anomalies.append(
                        AnomalyItem("花费异常", f"{row.game}/{row.partner}/{row.country}", "中", f"单段花费显著高于中位数，当前花费={row.cost:.0f}。")
                    )

        for row in current_creative_rows:
            if row.spend > 0 and row.ctr <= 0:
                anomalies.append(
                    AnomalyItem("CTR为0", f"{row.game}/{self._normalize_channel(row.channel)}/{row.asset_id or row.creative_name}", "中", "素材已有花费但 CTR 为0。")
                )
            if row.roas < 0:
                anomalies.append(
                    AnomalyItem("ROI异常", f"{row.game}/{self._normalize_channel(row.channel)}/{row.asset_id or row.creative_name}", "高", "素材 ROI 为负值，需校对源字段。")
                )

        for row in current_ads_rows:
            if row.spend > 0 and row.roas <= 0 and row.clicks > 0:
                anomalies.append(
                    AnomalyItem("ROI异常", f"{row.game}/{self._normalize_channel(row.channel)}/{row.country}", "中", "投放有点击和花费，但 ROAS 为0。")
                )
        return anomalies[:20]

    @classmethod
    def _group_breakdown_for_revenue_anomaly(cls, rows: list[RevenueBreakdownRow]) -> list[dict[str, Any]]:
        buckets: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        for row in rows:
            channel = cls._normalize_channel(str(getattr(row, "partner", "") or ""))
            key = (
                str(getattr(row, "game", "") or ""),
                channel,
                str(getattr(row, "country", "") or "Global"),
                str(getattr(row, "campaign", "") or getattr(row, "campaign_id", "") or ""),
            )
            bucket = buckets.setdefault(
                key,
                {
                    "scope": "/".join(part for part in key if part),
                    "cost": 0.0,
                    "revenue": 0.0,
                },
            )
            bucket["cost"] += float(getattr(row, "cost", 0.0) or 0.0)
            bucket["revenue"] += float(getattr(row, "total_revenue_gross", 0.0) or 0.0)
        return list(buckets.values())

    def _build_project_items(
        self,
        *,
        current_revenue_rows: list[RevenueRow],
        previous_revenue_rows: list[RevenueRow],
        current_breakdown_rows: list[RevenueBreakdownRow],
        previous_breakdown_rows: list[RevenueBreakdownRow],
        confidence_scores: list[ConfidenceScore],
        report_date: date,
        payback_targets_map: dict[str, ProjectTargets],
    ) -> list[ExecutiveProjectItem]:
        previous_revenue_map = defaultdict(lambda: {"revenue": 0.0, "cost": 0.0})
        for row in previous_revenue_rows:
            previous_revenue_map[row.game]["revenue"] += row.total_revenue
            previous_revenue_map[row.game]["cost"] += row.total_cost

        current_revenue_map = defaultdict(lambda: {"revenue": 0.0, "cost": 0.0})
        for row in current_revenue_rows:
            current_revenue_map[row.game]["revenue"] += row.total_revenue
            current_revenue_map[row.game]["cost"] += row.total_cost

        breakdown_by_project = defaultdict(list)
        for row in current_breakdown_rows:
            breakdown_by_project[row.game].append(row)
        previous_breakdown_by_project = defaultdict(list)
        for row in previous_breakdown_rows:
            previous_breakdown_by_project[row.game].append(row)

        roi_conf = next((item for item in confidence_scores if item.module == "ROI"), None)
        items: list[ExecutiveProjectItem] = []
        for project, metrics in sorted(current_revenue_map.items(), key=lambda item: item[1]["revenue"], reverse=True):
            project_breakdowns = breakdown_by_project.get(project, [])
            current_cost = sum(row.cost for row in project_breakdowns) if project_breakdowns else metrics["cost"]
            current_revenue = (
                sum(row.total_revenue_gross for row in project_breakdowns)
                if project_breakdowns
                else metrics["revenue"]
            )
            if current_cost <= 0:
                continue
            previous_project_breakdowns = previous_breakdown_by_project.get(project, [])
            previous = previous_revenue_map[project]
            previous_revenue = (
                sum(row.total_revenue_gross for row in previous_project_breakdowns)
                if previous_project_breakdowns
                else previous["revenue"]
            )
            roi = current_revenue / current_cost if current_cost else 0.0
            weak_channel = self._worst_channel(project_breakdowns)
            risk = self._project_risk_judgement(
                roi=roi,
                previous_revenue=previous_revenue,
                current_revenue=current_revenue,
                roi_confidence=roi_conf.level if roi_conf else "中",
                payback_target=payback_targets_map.get(self._project_key(project)),
            )
            action_text = self._project_action_text(
                roi,
                roi_conf.level if roi_conf else "中",
                weak_channel,
                payback_targets_map.get(self._project_key(project)),
            )
            payback_gate = self._project_payback_gate(payback_targets_map.get(self._project_key(project)))
            action = ClosedLoopAction(
                problem=f"{project} 当前总收入ROI={roi:.2f}",
                reason=self._project_reason(
                    project,
                    roi,
                    previous_revenue,
                    current_revenue,
                    weak_channel,
                    payback_targets_map.get(self._project_key(project)),
                ),
                action=action_text,
                owner=self._resolve_owner("项目", project),
                due_date=report_date + timedelta(days=self._settings.default_task_due_days),
                verification_metric=self._project_verification_metric(roi, roi_conf.level if roi_conf else "中", payback_targets_map.get(self._project_key(project))),
            )
            structure_level, structure_note = self._project_structure_gate(project_breakdowns)
            items.append(
                ExecutiveProjectItem(
                    project=project,
                    spend=current_cost,
                    revenue=current_revenue,
                    roi=roi,
                    payback_gate=payback_gate,
                    profit_split=self._project_profit_split(project_breakdowns, structure_level, structure_note),
                    structure_confidence_level=structure_level,
                    risk_judgement=risk,
                    suggested_action=action_text,
                    confidence_level=roi_conf.level if roi_conf else "中",
                    confidence_note=(
                        f"ROI可信度={roi_conf.level if roi_conf else '中'}；结构可信度={structure_level}。{structure_note}"
                        if roi_conf else f"结构可信度={structure_level}。{structure_note}"
                    ),
                    action=action,
                )
            )
        return items[:8]

    def _build_project_items_from_digest(self, digest: Any) -> list[ExecutiveProjectItem]:
        items: list[ExecutiveProjectItem] = []
        for item in getattr(digest, "project_items", [])[:8]:
            roi_value = item.project_roi
            payback_target = self._load_payback_targets_map(digest.report_date).get(self._project_key(item.game))
            risk_text = self._project_risk_judgement(
                roi=getattr(item, "paid_roi_net", roi_value) or roi_value,
                previous_revenue=0.0,
                current_revenue=item.total_revenue,
                roi_confidence=item.confidence_level or "中",
                payback_target=payback_target,
            )
            weak_target = self._project_action_target_from_digest_item(item)
            action_text = (getattr(item, "suggested_action", "") or "").strip() or self._project_action_text(
                getattr(item, "paid_roi_net", roi_value) or roi_value,
                item.confidence_level or "中",
                weak_target,
                payback_target,
            )
            problem_metric_label = "付费净ROI" if getattr(item, "paid_roi_net", None) is not None else "总收入ROI"
            action = ClosedLoopAction(
                problem=item.problem or f"{item.game} 当前{problem_metric_label}={roi_value:.2f}",
                reason=item.reason or f"{item.game} 当前判断沿用市场版项目结论。",
                action=(getattr(item, "suggested_action", "") or "").strip() or action_text,
                owner=item.action_owner or self._resolve_owner("项目", item.game),
                due_date=date.fromisoformat(item.action_due_date) if item.action_due_date else date.today(),
                verification_metric=item.verification_metric or "沿用市场版验证指标",
            )
            items.append(
                ExecutiveProjectItem(
                    project=item.game,
                    spend=item.spend,
                    revenue=item.total_revenue,
                    roi=roi_value,
                    payback_gate=item.payback_gate,
                    profit_split=getattr(item, "profit_split", "") or "待补盈利拆分",
                    structure_confidence_level="中",
                    risk_judgement=risk_text,
                    suggested_action=action_text,
                    confidence_level=item.confidence_level or "中",
                    confidence_note="老板版项目段复用市场版已过门禁项目口径。",
                    action=action,
                )
            )
        return items

    @staticmethod
    def _project_action_target_from_digest_item(item: Any) -> str:
        candidates = [
            str(getattr(item, "risk_segment", "") or "").strip(),
            str(getattr(item, "top_channel", "") or "").strip(),
        ]
        for candidate in candidates:
            if candidate and "待补可信项目明细" not in candidate:
                return candidate
        segment_lines = list(getattr(item, "segment_diagnostics", []) or [])
        for line in segment_lines:
            match = re.search(r"`([^`]+)`", str(line or ""))
            if match:
                return match.group(1).strip()
        return "低效渠道"

    def _build_campaign_items(
        self,
        *,
        current_breakdown_rows: list[RevenueBreakdownRow],
        confidence_scores: list[ConfidenceScore],
        report_date: date,
        payback_targets_map: dict[str, ProjectTargets],
    ) -> list[ExecutiveCampaignItem]:
        buckets: dict[tuple[str, str, str], dict[str, float | str]] = defaultdict(
            lambda: {"cost": 0.0, "revenue": 0.0, "country": "", "store": ""}
        )
        project_segments: dict[str, set[str]] = defaultdict(set)
        for row in current_breakdown_rows:
            campaign_name = (row.campaign or row.campaign_id or "").strip()
            if not campaign_name:
                continue
            channel = self._normalize_channel(row.partner)
            key = (row.game, channel, campaign_name)
            project_segments[row.game].add(
                f"{self._normalize_store(str(getattr(row, 'store', '') or ''))} / {channel}"
            )
            buckets[key]["cost"] += row.cost
            buckets[key]["revenue"] += row.total_revenue_gross
            if not buckets[key]["country"]:
                buckets[key]["country"] = row.country or "All"
            if not buckets[key]["store"]:
                buckets[key]["store"] = self._normalize_store(str(getattr(row, "store", "") or ""))

        roi_conf = next((item for item in confidence_scores if item.module == "ROI"), None)
        items: list[ExecutiveCampaignItem] = []
        ranked = sorted(buckets.items(), key=lambda item: item[1]["cost"], reverse=True)
        for (project, channel, campaign), metrics in ranked[:12]:
            spend = metrics["cost"]
            revenue = metrics["revenue"]
            roi = revenue / spend if spend else 0.0
            payback_target = payback_targets_map.get(self._project_key(project))
            store = str(metrics.get("store") or "")
            segment_target = self._segment_payback_target(payback_target, store, channel)
            payback_gate = self._payback_gate(payback_target, segment_target)
            if roi_conf and roi_conf.level == "低":
                risk = "低可信度，仅观察"
                suggested_action = "先校对收入归因，不直接动预算"
            elif segment_target and self._segment_current_below_floor(segment_target):
                if roi >= 1:
                    risk = "Campaign短期ROI可保留，但商店+渠道D7低于历史回本保底线"
                    suggested_action = "保留观察，不新增预算，等待组合D7修复"
                else:
                    risk = "商店+渠道D7低于历史可回本保底线，该 Campaign 暂不承接新增预算"
                    suggested_action = "限额验证并排查成本、国家和素材结构"
            elif payback_target and (payback_target.recovery_targets.get("D7").floor if payback_target.recovery_targets.get("D7") else None) and (payback_target.current_recovery.get("D7") or 0.0) < payback_target.recovery_targets["D7"].floor:
                if roi >= 1:
                    risk = "Campaign短期ROI可保留，但项目D7低于历史回本保底线"
                    suggested_action = "保留观察，不新增预算，等待项目D7修复"
                else:
                    risk = "项目D7低于历史可回本保底线，该 campaign 暂不承接新增预算"
                    suggested_action = "限额验证并排查成本、国家和素材结构"
            elif roi < 1:
                risk = "7日累计总收入ROI低于1，需结合商店+渠道历史保底线和成熟回收验证"
                suggested_action = "控量验证，不按单日波动一刀切停投；若满样本仍低回收再降权复核"
            else:
                risk = "可保留"
                suggested_action = "保留并观察扩量空间"
            action = ClosedLoopAction(
                problem=f"{project}/{channel}/{campaign} Campaign ROI={roi:.2f}",
                reason=self._campaign_reason(project, roi, payback_target, segment_target),
                action=suggested_action,
                owner=self._resolve_owner("投放", project),
                due_date=report_date + timedelta(days=self._settings.default_task_due_days),
                verification_metric=self._campaign_verification_metric(roi, payback_target, segment_target),
            )
            items.append(
                ExecutiveCampaignItem(
                    project=project,
                    channel=channel,
                    campaign=campaign,
                    country=str(metrics["country"] or "All"),
                    spend=spend,
                    revenue=revenue,
                    roi=roi,
                    payback_gate=payback_gate,
                    scope_priority=2 if len(project_segments.get(project, set())) > 1 else 1,
                    risk_judgement=risk,
                    suggested_action=suggested_action,
                    confidence_level=roi_conf.level if roi_conf else "中",
                    scope_note=(
                        "当前项目只有单一主投组合，Campaign层是唯一可用定位层"
                        if len(project_segments.get(project, set())) <= 1
                        else "当前项目存在多个主投组合，Campaign层可用于正常对比定位"
                    ),
                    action=action,
                )
            )
        return items[:6]

    def _build_campaign_items_from_digest(self, digest: Any) -> list[ExecutiveCampaignItem]:
        items: list[ExecutiveCampaignItem] = []
        for item in getattr(digest, "campaign_items", [])[:6]:
            action = ClosedLoopAction(
                problem=item.problem or f"{item.game}/{item.channel}/{item.campaign} Campaign ROI={item.roi:.2f}",
                reason=item.reason or "沿用市场版 campaign 结论。",
                action=item.suggested_action,
                owner=item.action_owner or self._resolve_owner("投放", item.game),
                due_date=date.fromisoformat(item.action_due_date) if item.action_due_date else date.today(),
                verification_metric=item.verification_metric or "沿用市场版验证指标",
            )
            items.append(
                ExecutiveCampaignItem(
                    project=item.game,
                    channel=item.channel,
                    campaign=item.campaign,
                    country=getattr(item, "country", "All"),
                    spend=item.spend,
                    revenue=item.revenue,
                    roi=item.roi,
                    payback_gate=item.payback_gate,
                    scope_priority=2 if "正常对比定位" in (getattr(item, "scope_note", "") or "") else 1,
                    risk_judgement=item.risk_judgement,
                    suggested_action=item.suggested_action,
                    confidence_level=item.confidence_level or "中",
                    scope_note=getattr(item, "scope_note", "") or "Campaign层用于当前项目定位",
                    action=action,
                )
            )
        return items

    def _build_creative_items(
        self,
        *,
        current_creative_rows: list[CreativeAssetRow],
        current_breakdown_rows: list[RevenueBreakdownRow],
        confidence_scores: list[ConfidenceScore],
        report_date: date,
    ) -> list[ExecutiveCreativeItem]:
        fb_conf = next((item for item in confidence_scores if item.module == "Facebook素材"), None)
        google_conf = next((item for item in confidence_scores if item.module == "Google素材"), None)
        fallback_low = bool(fb_conf and fb_conf.level == "低" and google_conf and google_conf.level == "低")
        items: list[ExecutiveCreativeItem] = []
        seen_keys: set[tuple[str, str, str, str]] = set()
        ranked = sorted(
            current_creative_rows,
            key=lambda row: (self._creative_revenue(row), row.spend, row.installs),
            reverse=True,
        )
        breakdown_candidates = self._collect_breakdown_creative_candidates(
            current_breakdown_rows=current_breakdown_rows,
            current_creative_rows=current_creative_rows,
        )
        direct_channels = {
            self._normalize_channel(row.channel)
            for row in ranked
            if self._normalize_channel(row.channel) in {"Facebook", "Google"}
        }

        def append_item(item: ExecutiveCreativeItem) -> None:
            key = (
                str(item.project or "").strip(),
                str(item.channel or "").strip(),
                str(item.creative_id or "").strip(),
                str(item.creative_name or "").strip(),
            )
            if key in seen_keys:
                return
            seen_keys.add(key)
            items.append(item)

        for row in ranked[:15]:
            append_item(
                self._build_executive_creative_item_from_row(
                    row=row,
                    report_date=report_date,
                    fallback_low=fallback_low,
                    fb_conf=fb_conf,
                    google_conf=google_conf,
                )
            )

        needs_breakdown_supplement = not ranked or "Google" not in direct_channels
        if needs_breakdown_supplement:
            for item in breakdown_candidates[:15]:
                if ranked and item.channel != "Google":
                    continue
                append_item(
                    self._build_executive_creative_item_from_breakdown(
                        item=item,
                        report_date=report_date,
                        fallback_low=fallback_low,
                        fb_conf=fb_conf,
                        google_conf=google_conf,
                    )
                )
        def _item_rank(item: ExecutiveCreativeItem) -> tuple[int, int, int, float, float]:
            sample_rank = 1 if item.sample_status == "有效样本" else 0
            confidence_rank = 0 if item.confidence_level == "低" else 1
            identified_rank = 0 if item.project in {"未知项目", "", None} or item.channel in {"未知渠道", "", None} else 1
            roi = item.roi if item.sample_status == "有效样本" else min(item.roi, 1.0)
            return sample_rank, confidence_rank, identified_rank, roi, item.spend

        items.sort(key=_item_rank, reverse=True)
        top_items = items[:6]
        if "Google" not in {item.channel for item in top_items} and "Google" not in direct_channels:
            google_candidate = next((item for item in breakdown_candidates if item.channel == "Google"), None)
            if google_candidate is not None:
                google_item = self._build_executive_creative_item_from_breakdown(
                    item=google_candidate,
                    report_date=report_date,
                    fallback_low=fallback_low,
                    fb_conf=fb_conf,
                    google_conf=google_conf,
                )
                top_items = [item for item in top_items if not (
                    item.project == google_item.project
                    and item.channel == google_item.channel
                    and item.creative_id == google_item.creative_id
                    and item.creative_name == google_item.creative_name
                )]
                top_items = top_items[:5] + [google_item]
        return top_items[:6]

    def _build_executive_creative_item_from_row(
        self,
        *,
        row: CreativeAssetRow,
        report_date: date,
        fallback_low: bool,
        fb_conf: ConfidenceScore | None,
        google_conf: ConfidenceScore | None,
    ) -> ExecutiveCreativeItem:
        channel = self._normalize_channel(row.channel)
        sample_status = "有效样本" if row.spend >= CREATIVE_MIN_EFFECTIVE_SPEND or row.installs >= CREATIVE_MIN_EFFECTIVE_INSTALLS else "观察样本"
        confidence = fb_conf if channel == "Facebook" else google_conf if channel == "Google" else None
        if confidence is None and fallback_low:
            confidence = self._score_object("素材", 40, ["当前主素材渠道可信度偏低，不能输出强结论。"])
        revenue = self._creative_revenue(row)
        roi = revenue / row.spend if row.spend else row.roas
        risk, suggested_action = self._creative_risk_and_action(
            roi=roi,
            sample_status=sample_status,
            confidence=confidence,
        )
        action = ClosedLoopAction(
            problem=f"{row.game}/{channel}/{row.asset_id or row.creative_name} 当前素材代理ROI={roi:.2f}",
            reason="素材结论必须建立在7日累计样本门槛和归因可信度之上，不按单日波动直接关闭或加量。",
            action=suggested_action,
            owner=self._resolve_owner("素材", row.game),
            due_date=report_date + timedelta(days=self._settings.default_task_due_days),
            verification_metric=f"素材7日累计花费≥{CREATIVE_MIN_EFFECTIVE_SPEND}或安装≥{CREATIVE_MIN_EFFECTIVE_INSTALLS}后，结合ROI与商店+渠道回收门槛判断加量/降权",
        )
        return ExecutiveCreativeItem(
            project=row.game,
            channel=channel,
            creative_id=row.asset_id,
            creative_name=row.creative_name or row.ad_name or row.asset_id,
            spend=row.spend,
            installs=row.installs,
            revenue=revenue,
            roi=roi,
            ctr=row.ctr,
            sample_status=sample_status,
            risk_judgement=risk,
            suggested_action=suggested_action,
            confidence_level=confidence.level if confidence else "中",
            action=action,
        )

    def _build_executive_creative_item_from_breakdown(
        self,
        *,
        item: BreakdownCreativeCandidate,
        report_date: date,
        fallback_low: bool,
        fb_conf: ConfidenceScore | None,
        google_conf: ConfidenceScore | None,
    ) -> ExecutiveCreativeItem:
        confidence = fb_conf if item.channel == "Facebook" else google_conf if item.channel == "Google" else None
        if confidence is None and fallback_low:
            confidence = self._score_object("素材", 40, ["当前主素材渠道可信度偏低，不能输出强结论。"])
        roi = item.revenue / item.spend if item.spend else 0.0
        risk, suggested_action = self._creative_risk_and_action(
            roi=roi,
            sample_status=item.sample_status,
            confidence=confidence,
        )
        reason = "素材结论来自 Adjust breakdown 素材信号。"
        if item.channel == "Google" and item.resolution_quality.startswith("proxy"):
            reason = "Google 当前主要是代理素材归因，可用于方向判断，但不等同于官方 creative id。"
        action = ClosedLoopAction(
            problem=f"{item.project}/{item.channel}/{item.creative_id or item.creative_name} 当前素材代理ROI={roi:.2f}",
            reason=reason,
            action=suggested_action,
            owner=self._resolve_owner("素材", item.project),
            due_date=report_date + timedelta(days=self._settings.default_task_due_days),
            verification_metric=f"素材7日累计花费≥{CREATIVE_MIN_EFFECTIVE_SPEND}或安装≥{CREATIVE_MIN_EFFECTIVE_INSTALLS}后，结合ROI与商店+渠道回收门槛判断加量/降权",
        )
        return ExecutiveCreativeItem(
            project=item.project,
            channel=item.channel,
            creative_id=item.creative_id,
            creative_name=item.creative_name,
            spend=item.spend,
            installs=item.installs,
            revenue=item.revenue,
            roi=roi,
            ctr=item.ctr,
            sample_status=item.sample_status,
            risk_judgement=risk,
            suggested_action=suggested_action,
            confidence_level=confidence.level if confidence else "中",
            action=action,
        )

    @staticmethod
    def _creative_risk_and_action(
        *,
        roi: float,
        sample_status: str,
        confidence: ConfidenceScore | None,
    ) -> tuple[str, str]:
        if confidence and confidence.level == "低":
            return "低可信度，仅观察", "先补齐归因或源字段，再决定是否复制"
        if sample_status == "观察样本":
            return "样本不足，不能直接认定为优质或低效素材", "继续小额验证，先跑够7日累计样本"
        if roi >= CREATIVE_SCALE_ROI:
            return "已形成正向素材候选信号", "保留观察，待素材归因和组合回收复核后小幅加量测试"
        if roi < CREATIVE_STOP_LOSS_ROI:
            return "有效样本持续低回收", "归因复核后降权或关闭，避免继续亏损"
        return "当前未证明有效", "限额观察，不新增预算"

    def _collect_next_actions(
        self,
        project_items: list[ExecutiveProjectItem],
        campaign_items: list[ExecutiveCampaignItem],
        creative_items: list[ExecutiveCreativeItem],
    ) -> list[ClosedLoopAction]:
        actions: list[ClosedLoopAction] = []
        seen: set[tuple[str, str]] = set()
        for item in project_items[:2]:
            key = (item.action.owner, item.action.action)
            if key not in seen:
                actions.append(item.action)
                seen.add(key)
        for item in campaign_items[:2]:
            key = (item.action.owner, item.action.action)
            if key not in seen:
                actions.append(item.action)
                seen.add(key)
        for item in creative_items[:2]:
            key = (item.action.owner, item.action.action)
            if key not in seen:
                actions.append(item.action)
                seen.add(key)
        return actions[:4]

    def _build_max_risk(
        self,
        project_items: list[ExecutiveProjectItem],
        campaign_items: list[ExecutiveCampaignItem],
        anomalies: list[AnomalyItem],
    ) -> str:
        ranked_projects = sorted(
            project_items,
            key=self._project_risk_score,
            reverse=True,
        )
        if ranked_projects:
            weakest_project = ranked_projects[0]
            reason = self._risk_reason_suffix(weakest_project.risk_judgement, weakest_project.suggested_action)
            return f"{weakest_project.project}：{weakest_project.risk_judgement}{reason}"
        severe = next((item for item in anomalies if item.severity == "高"), None)
        if severe is not None:
            return f"{severe.scope}：{severe.message}"
        ranked_campaigns = sorted(
            campaign_items,
            key=lambda item: (-item.scope_priority, -(item.spend or 0.0), item.roi),
        )
        risk_campaign = next((item for item in ranked_campaigns if "亏损" in item.risk_judgement), None)
        if risk_campaign is not None:
            return f"{risk_campaign.project}/{risk_campaign.channel}/{risk_campaign.campaign}：{risk_campaign.risk_judgement}"
        return "当前未发现需要立即升级处理的高风险段。"

    def _build_max_opportunity(
        self,
        project_items: list[ExecutiveProjectItem],
        campaign_items: list[ExecutiveCampaignItem],
        creative_items: list[ExecutiveCreativeItem],
        confidence_scores: list[ConfidenceScore],
    ) -> str:
        roi_conf = next((item for item in confidence_scores if item.module == "ROI"), None)
        fb_conf = next((item for item in confidence_scores if item.module == "Facebook素材"), None)
        google_conf = next((item for item in confidence_scores if item.module == "Google素材"), None)
        if roi_conf and roi_conf.level == "低":
            return "当前 ROI 可信度偏低，暂不输出强机会判断。"
        if fb_conf and fb_conf.level == "低":
            return "本期暂无高确定性的放量机会，先稳住已验证组合。"
        if google_conf and google_conf.level == "低":
            return "本期暂无高确定性的放量机会，先稳住已验证组合。"
        for project in sorted(project_items, key=lambda x: (self._project_opportunity_priority(x), x.roi, x.revenue), reverse=True):
            risk_text = project.risk_judgement or ""
            action_text = project.suggested_action or ""
            if any(flag in risk_text for flag in ("亏损", "未达回本门槛", "未达历史保底线", "回收未达回本门槛")):
                continue
            if any(flag in action_text for flag in ("压缩", "排查", "拉回", "不承接新增预算")):
                continue
            if "维持预算" in action_text:
                return f"{project.project}：当前总收入ROI={project.roi:.2f}，当前先守住已验证回收，等样本更成熟后再判断是否扩量。"
            return f"{project.project}：当前总收入ROI={project.roi:.2f}，回收与动作口径允许继续验证增量空间。"
        ranked_campaigns = sorted(
            campaign_items,
            key=lambda item: (-item.scope_priority, -(item.spend or 0.0), -(item.roi or 0.0)),
        )
        campaign = next(
            (
                item
                for item in ranked_campaigns
                if item.roi >= 1.1
                and "可保留" in (item.risk_judgement or "")
                and not any(flag in (item.suggested_action or "") for flag in ("压缩", "排查", "不承接新增预算"))
            ),
            None,
        )
        if campaign is not None:
            reason = campaign.scope_note or "当前在可用 Campaign 中具备更高的定位优先级"
            return f"{campaign.project}/{campaign.channel}/{campaign.campaign}：当前Campaign ROI={campaign.roi:.2f}，可保留验证；原因：{reason}。"
        creative_low = bool(
            (fb_conf and fb_conf.level == "低")
            or (google_conf and google_conf.level == "低")
        )
        if not creative_low:
            creative = next(
                (
                    item
                    for item in creative_items
                    if item.sample_status == "有效样本"
                    and item.roi >= 1.0
                    and "低可信度" not in (item.risk_judgement or "")
                ),
                None,
            )
            if creative is not None:
                return f"{creative.project}/{creative.channel}/{creative.creative_id or creative.creative_name}：素材已通过样本门槛，且当前结论可信度={creative.confidence_level}。"
        return "本期暂无高确定性的放量机会，先稳住已验证组合。"

    def _build_confidence_line(self, confidence_scores: list[ConfidenceScore]) -> str:
        core_levels = {
            item.module: item.level
            for item in confidence_scores
            if item.module in {"花费", "收入", "ROI", "公司盈利结构", "Facebook素材", "Google素材"}
        }
        business_levels = [core_levels.get(name, "中") for name in ("花费", "收入", "ROI")]
        creative_levels = [core_levels.get(name, "低") for name in ("Facebook素材", "Google素材")]
        structure_level = core_levels.get("公司盈利结构", "低")
        business_text = "可直接决策" if all(level == "高" for level in business_levels) else "先复核后决策"
        structure_text = "可直接判断盈利结构" if structure_level == "高" else "结构结论需保守"
        creative_text = "素材结论先保守使用" if any(level == "低" for level in creative_levels) else "素材结论可用于方向判断"
        return f"数据可信度：经营指标={business_text}；公司结构={structure_text}；素材={creative_text}"

    def _build_summary_lines(
        self,
        *,
        business_metrics: list[ExecutiveMetric],
        current_breakdown_rows: list[RevenueBreakdownRow],
        max_risk: str,
        max_opportunity: str,
        next_actions: list[ClosedLoopAction],
        data_confidence_line: str,
        confidence_scores: list[ConfidenceScore],
        market_digest: Any | None = None,
    ) -> list[str]:
        revenue_metric = business_metrics[0]
        profit_metric = business_metrics[1]
        spend_metric = business_metrics[2]
        roi_metric = business_metrics[3]
        lines = [
            f"本周收入 {revenue_metric.current:.0f}，较上周 {revenue_metric.change}；净利润 {profit_metric.current:.0f}，较上周 {profit_metric.change}；总花费 {spend_metric.current:.0f}，整体仍处于收缩投放、保利润阶段。",
            f"最大风险项目：{max_risk}",
        ]
        structure_conf = next((item for item in confidence_scores if item.module == "公司盈利结构"), None)
        profit_line = self._build_profitability_summary_line(current_breakdown_rows, structure_conf)
        risk_game = self._extract_summary_game_name(max_risk)
        market_watch_item = self._market_watch_from_digest(market_digest, exclude_game=risk_game)
        if market_watch_item or max_opportunity or profit_line:
            merged = f"当前可保留观察项目：{market_watch_item or max_opportunity}" if (market_watch_item or max_opportunity) else "当前可保留观察项目：暂无"
            merged = merged.rstrip("。")
            if profit_line:
                merged = f"{merged}；{profit_line.rstrip('。')}"
            lines.append(merged)
        market_action_lines = self._summary_actions_from_market_digest(market_digest, data_confidence_line)
        if market_action_lines:
            lines.append("下周重点动作：" + "；".join(market_action_lines[:2]))
        else:
            summary_actions = self._select_summary_actions(next_actions, data_confidence_line)
            if summary_actions:
                lines.append(
                    "下周重点动作：" + "；".join(self._summary_action_groups(summary_actions[:2]))
                )
        lines.append(data_confidence_line)
        return lines[:6]

    def _select_summary_actions(
        self,
        actions: list[ClosedLoopAction],
        data_confidence_line: str,
    ) -> list[ClosedLoopAction]:
        if not actions:
            return []
        if "素材结论先保守使用" in data_confidence_line or "素材=低" in data_confidence_line:
            filtered = [item for item in actions if "复制" not in (item.action or "")]
            if filtered:
                return filtered
        return actions

    @staticmethod
    def _summary_action_groups(actions: list[ClosedLoopAction]) -> list[str]:
        return [ExecutiveReportBuilder._summary_action_text(item) for item in actions]

    @staticmethod
    def _summary_action_text(item: ClosedLoopAction) -> str:
        owner = item.owner or "待定负责人"
        target = ExecutiveReportBuilder._summary_action_target(item.problem)
        verb = ExecutiveReportBuilder._summary_action_verb(item.action)
        goal = ExecutiveReportBuilder._summary_action_goal(item.verification_metric)
        summary = f"{owner}：{verb} {target}".strip()
        if goal:
            summary += f"（目标：{goal}）"
        return summary

    @staticmethod
    def _summary_action_body(item: ClosedLoopAction) -> str:
        target = ExecutiveReportBuilder._summary_action_target(item.problem)
        action_text = (item.action or "").strip().rstrip("。")
        if target:
            return f"{target} {action_text}"
        return action_text

    def _market_watch_from_digest(self, market_digest: Any | None, exclude_game: str = "") -> str:
        if market_digest is None:
            return ""
        candidates = [item for item in getattr(market_digest, "project_items", []) if getattr(item, "game", "")]
        if exclude_game:
            filtered = [item for item in candidates if self._project_key(getattr(item, "game", "")) != self._project_key(exclude_game)]
            if filtered:
                candidates = filtered
        if not candidates:
            return ""
        best = max(
            candidates,
            key=lambda item: (
                getattr(item, "paid_roi_net", None) if getattr(item, "paid_roi_net", None) is not None else getattr(item, "project_roi", 0.0),
                getattr(item, "project_roi", 0.0),
            ),
        )
        actual_d7 = self._extract_curve_value(getattr(best, "actual_recovery", ""), 7) or self._extract_curve_value(getattr(best, "actual_recovery", ""), 3)
        gate_floor = self._extract_first_number(getattr(best, "payback_gate", ""))
        if actual_d7 is not None:
            if gate_floor is not None and actual_d7 >= gate_floor:
                return f"{best.game}：实际D7 {actual_d7:.2f}，已高于当前历史保底线，先维持预算观察。"
            return f"{best.game}：实际D7 {actual_d7:.2f}，先继续观察后续成熟回收。"
        return f"{best.game}：先继续观察后续成熟回收。"

    @staticmethod
    def _extract_summary_game_name(summary_text: str) -> str:
        text = str(summary_text or "").strip()
        if not text:
            return ""
        for marker in ("：", ":"):
            if marker in text:
                return text.split(marker, 1)[0].strip()
        return text

    @staticmethod
    def _extract_curve_value(summary: str, day: int) -> float | None:
        match = re.search(rf"(?:D{day}|{day}D)\s+([0-9.]+)", summary or "")
        if not match:
            return None
        try:
            return float(match.group(1))
        except ValueError:
            return None

    @staticmethod
    def _extract_first_number(text: str) -> float | None:
        match = re.search(r"(\d+\.\d+|\d+)", str(text or ""))
        if not match:
            return None
        try:
            return float(match.group(1))
        except ValueError:
            return None

    def _summary_actions_from_market_digest(self, market_digest: Any | None, data_confidence_line: str) -> list[str]:
        if market_digest is None:
            return []
        actions = [str(action or "").strip() for action in getattr(market_digest, "next_actions", []) if str(action or "").strip()]
        if not actions:
            return []
        if "素材结论先保守使用" in data_confidence_line or "素材=低" in data_confidence_line:
            filtered = [action for action in actions if not action.startswith("复制素材")]
            if filtered:
                actions = filtered
        lines: list[str] = []
        for action in actions:
            rendered = self._summary_action_from_market_line(action)
            if rendered:
                lines.append(rendered)
        return lines

    def _primary_management_loop(self, actions: list[ClosedLoopAction]) -> str:
        if not actions:
            return ""
        action = actions[0]
        target = self._summary_action_target(action.problem)
        owner = action.owner or "待定负责人"
        due = action.due_date.isoformat() if action.due_date else "待定"
        metric = self._summary_action_goal(action.verification_metric)
        return f"管理闭环：{target} 由 {owner} 负责，{due} 前完成，本轮以 {metric} 为验收标准。"

    def _summary_action_from_market_line(self, action: str) -> str:
        text = str(action or "").strip().rstrip("。")
        if not text:
            return ""
        action_type, _, remainder = text.partition("：")
        owner = self._extract_market_action_field(text, "负责人")
        target = remainder.split("。", 1)[0].strip() if remainder else text
        if "；" in target:
            target = target.split("；", 1)[0].strip()
        kpi = self._extract_market_action_field(text, "KPI")
        verb_map = {
            "减量": "压缩",
            "暂停": "暂停",
            "加码": "加码",
            "限额验证": "限额验证",
            "口径复核": "复核",
            "复制素材": "复制",
        }
        verb = verb_map.get(action_type.strip(), action_type.strip() or "处理")
        summary = f"{owner or '待定负责人'}：{verb} {target}".strip()
        if kpi:
            summary += f"（目标：{self._summary_action_goal(kpi)}）"
        return summary

    @staticmethod
    def _extract_market_action_field(text: str, field_name: str) -> str:
        match = re.search(rf"{re.escape(field_name)}：([^；]+)", text)
        return match.group(1).strip() if match else ""

    @staticmethod
    def _project_risk_priority(item: ExecutiveProjectItem) -> int:
        normalized = f"{item.risk_judgement} {item.suggested_action}"
        if "项目级明细未接入" in normalized or "回收来源未接入" in normalized:
            return 4
        if "低可信度" in normalized or "低可信" in normalized:
            return 1
        if "未达回本门槛" in normalized or "未达历史保底线" in normalized or "低于保底线" in normalized:
            return 5
        if "亏损" in normalized:
            return 4
        if "回收偏弱" in normalized:
            return 3
        if "收入走弱" in normalized:
            return 2
        text = f"{item.risk_judgement} {item.suggested_action}"
        if "低可信度" in text:
            return 1
        if "未达回本门槛" in text or "未达历史保底线" in text or "低于保底线" in text:
            return 5
        if "亏损" in text:
            return 4
        if "回收偏弱" in text:
            return 3
        if "收入走弱" in text:
            return 2
        return 0

    @classmethod
    def _project_risk_score(cls, item: ExecutiveProjectItem) -> float:
        base = cls._project_risk_priority(item)
        scale = max(float(item.spend or 0.0), float(item.revenue or 0.0))
        return base * 1_000_000.0 + scale

    @staticmethod
    def _risk_reason_suffix(risk_text: str, action_text: str) -> str:
        if not action_text:
            return ""
        if "低可信度" in (risk_text or ""):
            return "；当前先校对数据口径，不直接据此做强动作。"
        if any(flag in (risk_text or "") for flag in ("未达回本门槛", "未达历史保底线", "低于保底线", "亏损", "回收偏弱")):
            return f"；当前动作：{action_text}"
        return ""

    @staticmethod
    def _project_opportunity_priority(item: ExecutiveProjectItem) -> int:
        text = f"{item.risk_judgement} {item.suggested_action}"
        if "低可信度" in text:
            return 0
        if "维持预算" in text:
            return 3
        if "验证增量" in text or "观察" in text:
            return 2
        if "可保留" in text:
            return 1
        return 0

    @staticmethod
    def _summary_action_target(problem: str) -> str:
        text = (problem or "").strip()
        if not text:
            return ""
        for marker in (" 当前 ROI=", " ROI=", " 当前总收入ROI=", " 当前付费净ROI=", " Campaign ROI=", " 当前素材代理ROI="):
            if marker in text:
                text = text.split(marker, 1)[0].strip()
                break
        return text

    @staticmethod
    def _summary_action_verb(action_text: str) -> str:
        text = (action_text or "").strip()
        if "暂停" in text:
            return "暂停"
        if "控制" in text:
            return "控制"
        if "压缩" in text or "减量" in text:
            return "压缩"
        if "拉回" in text or "排查" in text or "修复" in text:
            return "修复"
        if "放量" in text or "加码" in text:
            return "加码"
        if "验证" in text:
            return "验证"
        return "处理"

    @staticmethod
    def _summary_action_goal(metric: str) -> str:
        text = (metric or "").strip().rstrip("。")
        replacements = [
            ("至少回到", "回到"),
            ("尽快接近", "接近"),
            ("以上后再考虑补量", "后再补量"),
            ("以上，再决定是否恢复测试", "后再复核"),
            ("以上，再讨论是否放量", "后再复核是否提高验证预算"),
        ]
        for source, target in replacements:
            text = text.replace(source, target)
        return text

    def _build_profitability_summary_line(self, rows: list[RevenueBreakdownRow], structure_conf: ConfidenceScore | None = None) -> str:
        if not rows:
            return ""
        if structure_conf and structure_conf.level == "低":
            reason = "；".join(structure_conf.reasons) if structure_conf.reasons else "当前结构可信度不足"
            return f"公司盈利结构当前可信度不足（{reason}）"
        by_store: dict[str, dict[str, float]] = defaultdict(lambda: {"cost": 0.0, "revenue": 0.0})
        by_channel: dict[str, dict[str, float]] = defaultdict(lambda: {"cost": 0.0, "revenue": 0.0})
        for row in rows:
            store = self._normalize_store(str(getattr(row, "store", "") or ""))
            channel = self._normalize_channel(str(getattr(row, "partner", "") or ""))
            by_store[store]["revenue"] += float(row.total_revenue_gross or 0.0)
            by_channel[channel]["revenue"] += float(row.total_revenue_gross or 0.0)
            if row.cost > 0:
                by_store[store]["cost"] += float(row.cost or 0.0)
                by_channel[channel]["cost"] += float(row.cost or 0.0)
        if not by_store and not by_channel:
            return ""
        best_store = max(by_store.items(), key=lambda item: ((item[1]["revenue"] / item[1]["cost"]) if item[1]["cost"] else -1.0, item[1]["cost"])) if by_store else None
        weak_channel = min(by_channel.items(), key=lambda item: ((item[1]["revenue"] / item[1]["cost"]) if item[1]["cost"] else 999.0, -item[1]["cost"])) if by_channel else None
        parts: list[str] = []
        if best_store:
            store_roi = best_store[1]["revenue"] / best_store[1]["cost"] if best_store[1]["cost"] else 0.0
            if store_roi >= 1.0:
                parts.append(f"赚钱主要来自 {best_store[0]}（ROI {store_roi:.2f}）")
            else:
                parts.append(f"当前相对较优的商店是 {best_store[0]}（ROI {store_roi:.2f}）")
        if weak_channel:
            channel_roi = weak_channel[1]["revenue"] / weak_channel[1]["cost"] if weak_channel[1]["cost"] else 0.0
            anomaly_note = self._channel_anomaly_note(rows, weak_channel[0])
            if anomaly_note:
                parts.append(f"当前需优先复核的渠道是 {weak_channel[0]}（ROI {channel_roi:.2f}，{anomaly_note}）")
            else:
                parts.append(f"当前相对偏弱渠道是 {weak_channel[0]}（ROI {channel_roi:.2f}）")
        return "；".join(parts) + "。"

    @classmethod
    def _channel_anomaly_note(cls, rows: list[RevenueBreakdownRow], channel: str) -> str:
        total_cost, zero_revenue_cost = cls._channel_zero_revenue_cost_after_grouping(rows, channel)
        if total_cost > 0 and zero_revenue_cost / total_cost >= CHANNEL_REVENUE_ANOMALY_THRESHOLD:
            return "存在较高占比有花费无收入明细，先复核归因再下强结论"
        return ""

    @classmethod
    def _channel_zero_revenue_cost_after_grouping(cls, rows: list[RevenueBreakdownRow], channel: str) -> tuple[float, float]:
        buckets: dict[tuple[str, str, str, str, str, str], dict[str, float]] = {}
        for row in rows or []:
            row_channel = cls._normalize_channel(str(getattr(row, "partner", "") or ""))
            if row_channel != channel:
                continue
            key = (
                str(getattr(row, "game", "") or ""),
                cls._normalize_store(str(getattr(row, "store", "") or "")),
                str(getattr(row, "country", "") or "Global"),
                str(getattr(row, "campaign", "") or getattr(row, "campaign_id", "") or ""),
                str(getattr(row, "adgroup", "") or getattr(row, "adgroup_id", "") or ""),
                str(getattr(row, "creative_name", "") or getattr(row, "creative_id", "") or ""),
            )
            bucket = buckets.setdefault(key, {"cost": 0.0, "revenue": 0.0})
            bucket["cost"] += float(getattr(row, "cost", 0.0) or 0.0)
            bucket["revenue"] += float(getattr(row, "total_revenue_gross", 0.0) or 0.0)
        total_cost = sum(float(item["cost"] or 0.0) for item in buckets.values())
        zero_revenue_cost = sum(
            float(item["cost"] or 0.0)
            for item in buckets.values()
            if float(item["cost"] or 0.0) > 0 and float(item["revenue"] or 0.0) <= 0
        )
        return total_cost, zero_revenue_cost

    def _company_structure_confidence(
        self,
        rows: list[RevenueBreakdownRow],
        spend_conf: ConfidenceScore,
        revenue_conf: ConfidenceScore,
    ) -> ConfidenceScore:
        reasons: list[str] = []
        score = min(spend_conf.score, revenue_conf.score)
        scoped = [row for row in rows if float(getattr(row, "cost", 0.0) or 0.0) > 0]
        if not scoped:
            return self._score_object("公司盈利结构", 35, ["缺少 Adjust breakdown 结构明细"])
        if spend_conf.level == "低" or revenue_conf.level == "低":
            reasons.append("花费或收入校验未通过，不能直接判断商店和渠道结构。")
            score = min(score, 45)
        stores = {
            self._normalize_store(str(getattr(row, "store", "") or ""))
            for row in scoped
        }
        channels = {
            self._normalize_channel(str(getattr(row, "partner", "") or ""))
            for row in scoped
        }
        if not stores or not channels:
            reasons.append("缺少可用的商店或渠道结构字段。")
            score = min(score, 40)
        elif len(stores) < 2 and len(channels) < 2:
            reasons.append("当前只有单一商店和单一渠道结构，只能做有限判断。")
            score = min(score, 68)
        elif len(stores) < 2:
            reasons.append("当前只有单一商店结构，最赚钱商店判断有限。")
            score = min(score, 72)
        elif len(channels) < 2:
            reasons.append("当前只有单一渠道结构，最弱渠道判断有限。")
            score = min(score, 72)
        else:
            reasons.append("商店和渠道结构完整，可输出结构结论。")
        return self._score_object("公司盈利结构", score, reasons)

    def _project_profit_split(self, rows: list[RevenueBreakdownRow], structure_level: str = "高", structure_note: str = "") -> str:
        if not rows:
            return "待补商店/渠道盈利拆分"
        if structure_level == "低":
            return f"项目盈利结构当前可信度不足：{structure_note or '暂不输出商店/渠道强结论'}"
        if structure_level == "中":
            return f"项目盈利结构当前可信度有限：{structure_note or '仅作观察，不输出强结论'}"
        by_store: dict[str, dict[str, float]] = defaultdict(lambda: {"cost": 0.0, "revenue": 0.0})
        by_channel: dict[str, dict[str, float]] = defaultdict(lambda: {"cost": 0.0, "revenue": 0.0})
        for row in rows:
            cost = float(getattr(row, "cost", 0.0) or 0.0)
            revenue = float(getattr(row, "total_revenue_gross", 0.0) or 0.0)
            store = self._normalize_store(str(getattr(row, "store", "") or ""))
            channel = self._normalize_channel(str(getattr(row, "partner", "") or ""))
            by_store[store]["revenue"] += revenue
            by_channel[channel]["revenue"] += revenue
            if cost > 0:
                by_store[store]["cost"] += cost
                by_channel[channel]["cost"] += cost

        good_stores = []
        weak_stores = []
        for name, metrics in by_store.items():
            roi = metrics["revenue"] / metrics["cost"] if metrics["cost"] else 0.0
            target = good_stores if roi >= 1 else weak_stores
            target.append(f"{name} {roi:.2f}")
        good_channels = []
        weak_channels = []
        for name, metrics in by_channel.items():
            roi = metrics["revenue"] / metrics["cost"] if metrics["cost"] else 0.0
            target = good_channels if roi >= 1 else weak_channels
            target.append(f"{name} {roi:.2f}")

        store_text = f"商店总收入ROI≥1={', '.join(good_stores) or '无'}；商店总收入ROI<1={', '.join(weak_stores) or '无'}"
        channel_text = f"渠道总收入ROI≥1={', '.join(good_channels) or '无'}；渠道总收入ROI<1={', '.join(weak_channels) or '无'}"
        return f"{store_text}；{channel_text}"

    def _project_structure_gate(self, rows: list[RevenueBreakdownRow]) -> tuple[str, str]:
        scoped = [row for row in rows if float(getattr(row, "cost", 0.0) or 0.0) > 0]
        if not scoped:
            return ("低", "缺少项目级 breakdown 结构明细")
        stores = {self._normalize_store(str(getattr(row, "store", "") or "")) for row in scoped}
        channels = {self._normalize_channel(str(getattr(row, "partner", "") or "")) for row in scoped}
        if not stores or not channels:
            return ("低", "缺少项目级商店或渠道字段")
        if len(stores) < 2 and len(channels) < 2:
            return ("中", "当前只有单商店单渠道结构")
        if len(stores) < 2:
            return ("中", "当前只有单商店多渠道结构，无法判断商店差异")
        if len(channels) < 2:
            return ("中", "当前只有多商店单渠道结构，无法判断渠道差异")
        return ("高", "项目级商店和渠道结构完整")

    @staticmethod
    def _normalize_store(value: str) -> str:
        normalized = (value or "").strip().lower()
        mapping = {"app_store": "iOS", "google_play": "Android", "amazon": "Amazon"}
        return mapping.get(normalized, value or "未知商店")

    def _score_from_gap(
        self,
        *,
        module: str,
        left_value: float,
        right_value: float,
        empty_message: str,
    ) -> ConfidenceScore:
        reasons: list[str] = []
        if left_value <= 0 or right_value <= 0:
            reasons.append(empty_message)
            return self._score_object(module, 40, reasons)
        gap = abs(left_value - right_value) / max(left_value, right_value)
        if gap <= 0.05:
            reasons.append("跨源合计偏差在5%以内。")
            return self._score_object(module, 92, reasons)
        if gap <= 0.15:
            reasons.append(f"跨源合计偏差约{gap:.1%}，可用于方向判断。")
            return self._score_object(module, 72, reasons)
        reasons.append(f"跨源合计偏差约{gap:.1%}，需先校对口径。")
        return self._score_object(module, 48, reasons)

    def _creative_confidence(
        self,
        module: str,
        rows: list[CreativeAssetRow],
        channel: str,
        breakdown_candidates: list[BreakdownCreativeCandidate] | None = None,
    ) -> ConfidenceScore:
        reasons: list[str] = []
        breakdown_candidates = breakdown_candidates or []
        if not rows:
            if breakdown_candidates:
                proxy_count = sum(1 for item in breakdown_candidates if item.resolution_quality.startswith("proxy"))
                resolved_count = len(breakdown_candidates) - proxy_count
                if channel == "Facebook":
                    reasons.append("Facebook 官方素材库当前为空，但 Adjust breakdown 已带出可用素材标识。")
                    if proxy_count:
                        reasons.append("其中部分素材仍为代理层标识，适合方向判断，不适合做过强结论。")
                    score = 78 if resolved_count else 62
                    return self._score_object(module, score, reasons)
                reasons.append("Google 官方素材库当前为空，当前素材判断来自 Adjust breakdown。")
                if resolved_count:
                    reasons.append("已有一部分 Google 素材可直接解析到素材层。")
                if proxy_count:
                    reasons.append("仍有部分 Google 花费落在来源/广告组/Campaign 代理层。")
                score = 72 if resolved_count and not proxy_count else 64 if resolved_count else 58
                return self._score_object(module, score, reasons)
            reasons.append(f"{channel} 当前没有进入 creative 分析链路的素材明细。")
            return self._score_object(module, 30, reasons)
        qualified = [row for row in rows if row.asset_id or row.creative_name or row.ad_id or row.ad_name]
        proxy_rows = [row for row in rows if (row.creative_type or "").strip().lower() == "proxy_ad"]
        if len(qualified) < len(rows):
            reasons.append("部分素材缺少 creative/ad 标识，只能做部分归因。")
        if proxy_rows:
            reasons.append("当前素材来源含 ad 级代理归因，可用于方向判断，但不等同于真实 creative id 归因。")
        if channel == "Google" and not self._settings.using_google_creative_source:
            if self._settings.using_tecdo_creative_source and proxy_rows:
                reasons.append("Google 当前未接入官方素材接口凭证，但 TecDo ad 级代理素材源已接入。")
                score = 68 if len(qualified) == len(rows) else 62
                return self._score_object(module, score, reasons)
            reasons.append("Google 当前未接入官方素材接口凭证。")
            return self._score_object(module, 45, reasons)
        if channel == "Facebook" and not self._settings.using_meta_creative_source:
            if self._settings.using_tecdo_creative_source and proxy_rows:
                reasons.append("Facebook 当前未接入官方素材接口凭证，但 TecDo ad 级代理素材源已接入。")
                score = 72 if len(qualified) == len(rows) else 65
                return self._score_object(module, score, reasons)
            reasons.append("Facebook 当前未接入官方素材接口凭证。")
            return self._score_object(module, 55, reasons)
        score = 90 if len(qualified) == len(rows) else 72
        if score >= 80:
            reasons.append("素材标识完整，可直接进入素材判断。")
        return self._score_object(module, score, reasons)

    def _collect_breakdown_creative_candidates(
        self,
        *,
        current_breakdown_rows: list[RevenueBreakdownRow],
        current_creative_rows: list[CreativeAssetRow],
    ) -> list[BreakdownCreativeCandidate]:
        resolver = GoogleCreativeResolver(current_creative_rows)
        grouped: dict[tuple[str, str, str, str], BreakdownCreativeCandidate] = {}
        for row in current_breakdown_rows:
            if row.cost <= 0:
                continue
            channel = self._normalize_channel(getattr(row, "partner", "") or "")
            if channel not in {"Facebook", "Google"}:
                continue
            identity = self._resolve_breakdown_creative_identity(row=row, channel=channel, resolver=resolver)
            if identity is None:
                continue
            creative_id, creative_name, resolution_quality = identity
            key = (row.game, channel, creative_id, creative_name)
            if key not in grouped:
                grouped[key] = BreakdownCreativeCandidate(
                    project=row.game,
                    channel=channel,
                    creative_id=creative_id,
                    creative_name=creative_name,
                    spend=0.0,
                    revenue=0.0,
                    installs=0.0,
                    ctr=0.0,
                    resolution_quality=resolution_quality,
                    sample_status="观察样本",
                )
            item = grouped[key]
            item.spend += float(row.cost or 0.0)
            item.revenue += float(row.total_revenue_gross or 0.0)
        candidates = list(grouped.values())
        for item in candidates:
            if item.spend >= 50 or item.installs >= 20:
                item.sample_status = "有效样本"
        candidates.sort(key=lambda item: ((item.revenue / item.spend) if item.spend else 0.0, item.spend, item.revenue), reverse=True)
        return candidates

    def _resolve_breakdown_creative_identity(
        self,
        *,
        row: RevenueBreakdownRow,
        channel: str,
        resolver: GoogleCreativeResolver,
    ) -> tuple[str, str, str] | None:
        creative_id = str(getattr(row, "creative_id", "") or "").strip()
        creative_name = str(getattr(row, "creative_name", "") or "").strip()
        if channel == "Google":
            resolved = resolver.resolve(row)
            if resolved is None:
                return None
            return resolved.identity_id, resolved.identity_name, resolved.resolution_quality
        if self._is_valid_breakdown_creative_id(creative_id, creative_name):
            return creative_id or creative_name, creative_name or creative_id, "resolved"
        return None

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

    @staticmethod
    def _score_object(module: str, score: int, reasons: list[str]) -> ConfidenceScore:
        if score >= 85:
            level = "高"
            risk = "低"
            status = "可直接用于决策"
        elif score >= 60:
            level = "中"
            risk = "中"
            status = "可用于方向判断"
        else:
            level = "低"
            risk = "高"
            status = "仅观察，不输出强结论"
        return ConfidenceScore(module=module, score=score, level=level, risk_level=risk, status=status, reasons=reasons)

    def _project_risk_judgement(self, *, roi: float, previous_revenue: float, current_revenue: float, roi_confidence: str, payback_target: ProjectTargets | None) -> str:
        if roi_confidence == "低":
            if payback_target is None:
                return "项目总收入口径可看，但项目级回收来源未接入"
            return "跨源口径仍需复核，当前仅保留观察"
        if payback_target:
            current_d7 = payback_target.current_recovery.get("D7") or 0.0
            d7_floor = (payback_target.recovery_targets.get("D7").floor if payback_target.recovery_targets.get("D7") else None)
            if d7_floor and current_d7 < d7_floor:
                return f"回收未达历史保底线，当前 D7={current_d7:.2f} 低于历史保底线 {d7_floor:.2f}"
            if d7_floor and current_d7 >= d7_floor:
                return "D7 高于历史保底线，但预测可信度仍低，继续观察后续成熟回收"
        if roi < 1:
            return "短期付费净ROI未过线，仅作为预警，不能单独作为停投或加量依据"
        if roi < 1.3:
            return "短期付费净ROI偏弱，需先看项目历史保底线和成熟回收"
        if previous_revenue > 0 and current_revenue < previous_revenue * 0.9:
            return "收入走弱，需先查回收质量"
        return "当前可保留，但不代表可直接放量"

    def _project_action_text(self, roi: float, roi_confidence: str, weak_channel: str, payback_target: ProjectTargets | None) -> str:
        if roi_confidence == "低":
            if payback_target is None:
                return "先补项目级明细或回收来源，再决定具体预算动作"
            return "先校对收入与花费口径，再决定是否调整预算"
        if payback_target:
            current_d7 = payback_target.current_recovery.get("D7") or 0.0
            d7_floor = (payback_target.recovery_targets.get("D7").floor if payback_target.recovery_targets.get("D7") else None)
            if d7_floor and current_d7 < d7_floor:
                return f"限额验证并修复低效组合，先把 D7 回收拉回历史保底线 {d7_floor:.2f}，再复核是否提高验证预算"
            if d7_floor and current_d7 >= d7_floor:
                return "维持观察，不新增预算，等 D30/更成熟回收确认后再讨论验证预算"
        if roi < 1:
            return f"控量验证{weak_channel or '低效渠道'}并排查付费回收"
        if roi < 1.3:
            return f"先控量观察{weak_channel or '低效渠道'}，整体预算以稳为主"
        return "维持预算，先看是否还能稳定放量"

    def _project_reason(self, project: str, roi: float, previous_revenue: float, current_revenue: float, weak_channel: str, payback_target: ProjectTargets | None) -> str:
        if payback_target and payback_target.findings:
            return payback_target.findings[0]
        if roi < 1:
            return f"{project} 当前短期付费净ROI偏弱，需结合历史回本门槛判断，弱项主要集中在{weak_channel or '低效渠道'}。"
        if previous_revenue > 0 and current_revenue < previous_revenue:
            return f"{project} 收入较上期走弱，当前不能只看表面 ROI。"
        return f"{project} 当前仍需先验证增量质量，再决定是否真正加码。"

    @staticmethod
    def _project_verification_metric(roi: float, roi_confidence: str, payback_target: ProjectTargets | None) -> str:
        if roi_confidence == "低":
            return "先把跨源 ROI 偏差压到15%以内"
        if payback_target:
            d7_floor = (payback_target.recovery_targets.get("D7").floor if payback_target.recovery_targets.get("D7") else None)
            d30_floor = (payback_target.recovery_targets.get("D30").floor if payback_target.recovery_targets.get("D30") else None)
            if d7_floor and d30_floor:
                return f"D7 回到历史保底线 {d7_floor:.2f}，且 D30 接近历史保底线 {d30_floor:.2f}"
        if roi < 1:
            return "先看3日ROAS和后续成熟回收是否改善，再考虑是否调整预算"
        return "放量期 ROI 不低于当前基线"

    def _project_payback_gate(self, payback_target: ProjectTargets | None) -> str:
        return self._payback_gate(payback_target, None)

    @staticmethod
    def _segment_payback_target(payback_target: ProjectTargets | None, store: str, channel: str):
        if not payback_target:
            return None
        key = f"{ExecutiveReportBuilder._normalize_store(store)} / {ExecutiveReportBuilder._normalize_channel(channel)}"
        segment = getattr(payback_target, "segment_targets", {}).get(key)
        if not segment:
            return None
        if segment.profitable_samples < 3:
            return None
        return segment

    @staticmethod
    def _segment_current_below_floor(segment_target) -> bool:
        d7_floor = segment_target.recovery_targets.get("D7").floor if segment_target.recovery_targets.get("D7") else None
        current_d7 = segment_target.current_recovery.get("D7") or 0.0
        return bool(d7_floor and current_d7 and current_d7 < d7_floor)

    def _payback_gate(self, payback_target: ProjectTargets | None, segment_target=None) -> str:
        if not payback_target:
            return "暂无项目回本门槛"
        if segment_target is not None:
            parts = []
            d7_current = segment_target.current_recovery.get("D7")
            d7_floor = segment_target.recovery_targets.get("D7").floor if segment_target.recovery_targets.get("D7") else None
            d30_floor = segment_target.recovery_targets.get("D30").floor if segment_target.recovery_targets.get("D30") else None
            if d7_current is not None and d7_floor is not None:
                parts.append(f"{segment_target.key}组合级D7 `{d7_current:.2f}` / 历史保底线 `{d7_floor:.2f}`")
            if d30_floor is not None:
                parts.append(f"组合级D30历史保底线 `{d30_floor:.2f}`")
            parts.append("D7按延迟缓冲取数：cohort至少满9天后才做强判断")
            return " | ".join(parts) if parts else f"{segment_target.key}组合级门槛样本不足"
        d7_current = payback_target.current_recovery.get("D7")
        d7_floor = payback_target.recovery_targets.get("D7").floor if payback_target.recovery_targets.get("D7") else None
        d30_floor = payback_target.recovery_targets.get("D30").floor if payback_target.recovery_targets.get("D30") else None
        cpi_ceiling = payback_target.cpi_guardrail.ceiling
        retention_floor = payback_target.retention_guardrail.floor
        parts = []
        if d7_current is not None and d7_floor is not None:
            parts.append(f"项目级参考D7 `{d7_current:.2f}` / 历史保底线 `{d7_floor:.2f}`")
        if d30_floor is not None:
            parts.append(f"项目级D30历史保底线 `{d30_floor:.2f}`")
        dynamic_line = self._dynamic_payback_line(payback_target.project)
        if dynamic_line:
            parts.append(dynamic_line)
        if cpi_ceiling is not None:
            parts.append(f"CPI上限 `{cpi_ceiling:.2f}`")
        if retention_floor is not None:
            parts.append(f"D1留存底线 `{retention_floor:.2f}`")
        if parts:
            parts.append("D7按延迟缓冲取数：cohort至少满9天后才做强判断")
        return "；".join(parts) if parts else "暂无可用门槛"

    def _load_payback_targets_map(self, report_date: date) -> dict[str, ProjectTargets]:
        try:
            targets, _ = PaybackTargetsBuilder(self._settings).build_targets_data(report_date)
        except Exception:
            return {}
        return {item.project: item for item in targets}

    def _dynamic_payback_line(self, project: str) -> str:
        active = self._settings.active_output_dir
        candidates = sorted(active.glob("dynamic_payback_*.json"), reverse=True)
        for path in candidates:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            for item in payload.get("items") or []:
                if str(item.get("project") or "") != str(project or ""):
                    continue
                return (
                    f"动态线 D7 `{float(item.get('dynamic_break_even_d7') or 0):.2f}` / "
                    f"D30 `{float(item.get('dynamic_break_even_d30') or 0):.2f}` / "
                    f"置信度 `{float(item.get('confidence') or 0):.2f}`"
                )
        return ""

    def _campaign_reason(self, project: str, roi: float, payback_target: ProjectTargets | None, segment_target=None) -> str:
        if segment_target is not None:
            d7_floor = segment_target.recovery_targets.get("D7").floor if segment_target.recovery_targets.get("D7") else None
            current_d7 = segment_target.current_recovery.get("D7")
            if d7_floor and current_d7:
                return f"{segment_target.key} 组合级 D7 `{current_d7:.2f}` 对比历史可回本保底线 `{d7_floor:.2f}`，比项目级线更适合作为该 Campaign 预算判断依据。"
        if payback_target and payback_target.findings:
            return payback_target.findings[0]
        if roi < 1:
            return f"{project} 当前该 campaign 仍未跨过回本线。"
        return f"{project} 当前该 campaign 已过线，但仍需结合商店+渠道历史保底线控制节奏。"

    def _campaign_verification_metric(self, roi: float, payback_target: ProjectTargets | None, segment_target=None) -> str:
        if segment_target is not None:
            d7_floor = segment_target.recovery_targets.get("D7").floor if segment_target.recovery_targets.get("D7") else None
            d30_floor = segment_target.recovery_targets.get("D30").floor if segment_target.recovery_targets.get("D30") else None
            if d7_floor and d30_floor:
                return f"{segment_target.key} 组合级D7回到历史保底线 {d7_floor:.2f}，且D30接近组合级历史保底线 {d30_floor:.2f}；D7样本至少满9天后再确认"
        if payback_target:
            d7_floor = payback_target.recovery_targets.get("D7").floor if payback_target.recovery_targets.get("D7") else None
            d30_floor = payback_target.recovery_targets.get("D30").floor if payback_target.recovery_targets.get("D30") else None
            if d7_floor and d30_floor:
                return f"项目级D7回到历史保底线 {d7_floor:.2f}，且D30接近历史保底线 {d30_floor:.2f}；无组合样本时仅作参考"
        if roi < 1:
            return "先看3日ROAS和后续成熟回收是否改善，再决定是否提高验证预算"
        return "放量期 ROI 不低于当前 campaign 基线"

    def _resolve_owner(self, track: str, project: str) -> str:
        if track == "素材":
            return self._settings.task_owner_rules.get("by_action_type", {}).get("复制素材", "牟耕")
        if track == "投放":
            return self._settings.task_owner_rules.get("by_action_type", {}).get("减量", "林凯")
        by_game = self._settings.task_owner_rules.get("by_game", {})
        if project in by_game:
            return by_game[project]
        return "姜会伟"

    @staticmethod
    def _worst_channel(rows: list[RevenueBreakdownRow]) -> str:
        buckets: dict[str, dict[str, float]] = defaultdict(lambda: {"cost": 0.0, "revenue": 0.0})
        for row in rows:
            if row.cost <= 0:
                continue
            channel = ExecutiveReportBuilder._normalize_channel(row.partner)
            buckets[channel]["cost"] += row.cost
            buckets[channel]["revenue"] += row.total_revenue_gross
        if not buckets:
            return ""
        weakest = min(
            buckets.items(),
            key=lambda item: (item[1]["revenue"] / item[1]["cost"]) if item[1]["cost"] else 999,
        )
        return weakest[0]

    @staticmethod
    def _creative_revenue(row: CreativeAssetRow) -> float:
        if row.revenue_value > 0:
            return row.revenue_value
        if row.spend > 0 and row.roas > 0:
            return row.spend * row.roas
        return 0.0

    @staticmethod
    def _normalize_channel(value: str) -> str:
        lowered = (value or "").strip().lower()
        if lowered in FACEBOOK_LABELS:
            return "Facebook"
        if lowered in GOOGLE_LABELS:
            return "Google"
        return (value or "").strip() or "Unknown"

    @staticmethod
    def _period_bounds(period: str, report_date: date) -> tuple[date, date, date, date, str]:
        if period == "monthly":
            current_start = report_date.replace(day=1)
            current_end = report_date
            current_days = (current_end - current_start).days + 1
            prev_month_end = current_start - timedelta(days=1)
            prev_month_start = prev_month_end.replace(day=1)
            previous_start = prev_month_start
            previous_end = min(prev_month_end, previous_start + timedelta(days=current_days - 1))
            period_label = f"{current_start.isoformat()} 至 {current_end.isoformat()}"
            return current_start, current_end, previous_start, previous_end, period_label

        current_end = report_date
        current_start = report_date - timedelta(days=6)
        previous_end = current_start - timedelta(days=1)
        previous_start = previous_end - timedelta(days=6)
        period_label = f"{current_start.isoformat()} 至 {current_end.isoformat()}（上周四到本周三）"
        return current_start, current_end, previous_start, previous_end, period_label

    @staticmethod
    def _project_key(name: str) -> str:
        cleaned = (name or "").strip()
        if not cleaned:
            return ""
        match = re.search(r"\bP0*([0-9]+)\b", cleaned.upper())
        if match:
            return f"P{int(match.group(1)):02d}"
        return cleaned

    @staticmethod
    def _pct_change(current: float, previous: float) -> str:
        if previous == 0:
            return "新增" if current else "0.0%"
        return f"{((current - previous) / previous):+.1%}"

    @staticmethod
    def _section(title: str, content: str) -> dict[str, Any]:
        return {"tag": "div", "text": {"tag": "lark_md", "content": f"**{title}**\n{content}"}}
