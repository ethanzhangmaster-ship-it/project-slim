from __future__ import annotations

import csv
import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from statistics import median
from typing import Any, Iterable

from market_ops.clients.adjust import AdjustClient
from market_ops.config import Settings
from market_ops.pipeline import DataRepository


ACTIVE_PROJECTS = {"P02", "P04", "P07"}
PAID_CHANNELS = {"Facebook", "Google", "Apple Search", "Applovin", "Unity Ads"}
PAYBACK_TARGET_DAY = 120
PAYBACK_CURRENT_DAY = 7


@dataclass(slots=True)
class SegmentMetrics:
    project: str
    level: str
    store: str = ""
    channel: str = ""
    country: str = ""
    campaign: str = ""
    campaign_id: str = ""
    adgroup: str = ""
    adgroup_id: str = ""
    creative_name: str = ""
    creative_id: str = ""
    source_name: str = ""
    source_id: str = ""
    cost: float = 0.0
    gross_revenue: float = 0.0
    net_revenue: float = 0.0

    @property
    def gross_roi(self) -> float:
        return self.gross_revenue / self.cost if self.cost else 0.0

    @property
    def net_roi(self) -> float:
        return self.net_revenue / self.cost if self.cost else 0.0

    @property
    def net_profit(self) -> float:
        return self.net_revenue - self.cost

    @property
    def status(self) -> str:
        if not self.cost:
            return "非付费收入"
        if self.net_roi >= 1.0:
            return "赚钱"
        if self.net_roi >= 0.9:
            return "接近回本"
        return "亏损"


@dataclass(slots=True)
class PaybackMetrics:
    project: str
    store: str
    channel: str
    current_cost: float
    current_d0: float
    current_d1: float
    current_d3: float
    current_d7: float
    mature_rows: int
    historical_median_d7: float
    historical_median_d120: float
    historical_median_d120_over_d7: float
    predicted_d120: float
    estimated_payback_day: float | None

    @property
    def status(self) -> str:
        if self.predicted_d120 >= 1.0:
            return "预计可回本"
        return "预计难回本"


class ProfitabilityAuditBuilder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._repo = DataRepository(settings)

    def build(self, report_date: date) -> dict[str, Path]:
        report_date = _align_to_wednesday(report_date)
        window_start = report_date - timedelta(days=6)
        output_dir = self._settings.output_dir
        active_output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        active_output_dir.mkdir(parents=True, exist_ok=True)

        breakdown_rows = self._repo.load_adjust_revenue_breakdown(window_start, report_date)
        segments = self._build_profit_segments(breakdown_rows, window_start, report_date)
        payback_error = ""
        try:
            paybacks = self._build_store_channel_paybacks(report_date)
        except Exception as exc:
            paybacks = []
            payback_error = str(exc)

        suffix = report_date.strftime("%Y%m%d")
        segment_path = output_dir / f"profitability_paid_segments_{suffix}.csv"
        payback_path = output_dir / f"profitability_store_channel_payback_{suffix}.csv"
        markdown_path = active_output_dir / f"profitability_audit_summary_{suffix}.md"
        json_path = active_output_dir / f"profitability_audit_self_check_{suffix}.json"

        _write_segments_csv(segment_path, segments)
        _write_paybacks_csv(payback_path, paybacks)
        self_check = self._self_check(breakdown_rows, segments, paybacks, window_start, report_date, payback_error)
        json_path.write_text(json.dumps(self_check, ensure_ascii=False, indent=2), encoding="utf-8")
        markdown_path.write_text(
            self._render_markdown(window_start, report_date, segments, paybacks, self_check),
            encoding="utf-8",
        )
        return {
            "summary": markdown_path,
            "segments": segment_path,
            "payback": payback_path,
            "self_check": json_path,
        }

    def _build_profit_segments(self, rows: list[Any], window_start: date, report_date: date) -> list[SegmentMetrics]:
        current_rows = [
            row
            for row in rows
            if window_start <= row.date <= report_date and _project_key(row.game) in ACTIVE_PROJECTS
        ]
        buckets: dict[tuple[str, str, str, str, str, str, str, str, str, str, str, str], SegmentMetrics] = {}

        def add(
            row: Any,
            level: str,
            store: str = "",
            channel: str = "",
            country: str = "",
            campaign: str = "",
            campaign_id: str = "",
            adgroup: str = "",
            adgroup_id: str = "",
            creative_name: str = "",
            creative_id: str = "",
            source_name: str = "",
            source_id: str = "",
        ) -> None:
            project = _project_key(row.game)
            key = (
                project,
                level,
                store,
                channel,
                country,
                campaign,
                campaign_id,
                adgroup,
                adgroup_id,
                creative_name,
                creative_id,
                source_name or source_id,
            )
            if key not in buckets:
                buckets[key] = SegmentMetrics(
                    project=project,
                    level=level,
                    store=store,
                    channel=channel,
                    country=country,
                    campaign=campaign,
                    campaign_id=campaign_id,
                    adgroup=adgroup,
                    adgroup_id=adgroup_id,
                    creative_name=creative_name,
                    creative_id=creative_id,
                    source_name=source_name,
                    source_id=source_id,
                )
            item = buckets[key]
            item.cost += row.cost
            item.gross_revenue += row.total_revenue_gross
            item.net_revenue += _net_revenue(row.store, row.iap_revenue_gross, row.ad_revenue)

        for row in current_rows:
            store = _normalize_store(row.store)
            channel = _normalize_channel(row.partner)
            country = row.country or "Global"
            campaign = (getattr(row, "campaign", "") or "").strip()
            campaign_id = (getattr(row, "campaign_id", "") or "").strip()
            adgroup = (getattr(row, "adgroup", "") or "").strip()
            adgroup_id = (getattr(row, "adgroup_id", "") or "").strip()
            creative_name = (getattr(row, "creative_name", "") or "").strip()
            creative_id = (getattr(row, "creative_id", "") or "").strip()
            source_name = (getattr(row, "source_name", "") or "").strip()
            source_id = (getattr(row, "source_id", "") or "").strip()
            add(row, "项目整体")
            add(row, "商店", store=store)
            add(row, "国家", country=country)
            add(row, "商店+国家", store=store, country=country)
            if row.cost > 0 and channel in PAID_CHANNELS:
                add(row, "纯投放渠道", channel=channel)
                add(row, "纯投放商店+渠道", store=store, channel=channel)
                add(row, "纯投放国家", channel=channel, country=country)
                add(row, "纯投放商店+渠道+国家", store=store, channel=channel, country=country)
                if campaign:
                    add(row, "纯投放Campaign", channel=channel, campaign=campaign, campaign_id=campaign_id)
                    add(row, "纯投放国家+Campaign", channel=channel, country=country, campaign=campaign, campaign_id=campaign_id)
                if adgroup:
                    add(row, "纯投放广告组", channel=channel, adgroup=adgroup, adgroup_id=adgroup_id)
                    add(row, "纯投放国家+广告组", channel=channel, country=country, adgroup=adgroup, adgroup_id=adgroup_id)
                if creative_id or creative_name:
                    add(
                        row,
                        "纯投放素材",
                        channel=channel,
                        creative_name=creative_name,
                        creative_id=creative_id,
                    )
                    add(
                        row,
                        "纯投放国家+素材",
                        channel=channel,
                        country=country,
                        creative_name=creative_name,
                        creative_id=creative_id,
                    )
                if source_name or source_id:
                    add(row, "纯投放Source", channel=channel, source_name=source_name, source_id=source_id)

        return sorted(
            buckets.values(),
            key=lambda item: (
                item.project,
                _level_rank(item.level),
                -(item.cost or item.net_revenue),
                item.store,
                item.channel,
                item.country,
                item.campaign,
                item.campaign_id,
                item.adgroup,
                item.adgroup_id,
                item.creative_name,
                item.creative_id,
                item.source_name,
            ),
        )

    def _build_store_channel_paybacks(self, report_date: date) -> list[PaybackMetrics]:
        if not self._settings.adjust_dashboard_config_path or not self._settings.adjust_dashboard_config_path.exists():
            return []

        client = AdjustClient.from_dashboard_config(self._settings.adjust_dashboard_config_path)
        history_start = report_date - timedelta(days=210)
        rows = client.fetch_recovery_cohort_rows(
            history_start.isoformat(),
            report_date.isoformat(),
            dimensions="app,app_token,store_type,network,day",
            day_suffixes=(0, 1, 3, 7, 119, 120),
        )

        current_start = report_date - timedelta(days=6)
        current_rows = [_recovery_row(row) for row in rows if current_start <= _row_day(row) <= report_date]
        history_rows = [
            _recovery_row(row)
            for row in rows
            if _row_day(row) <= report_date - timedelta(days=PAYBACK_TARGET_DAY)
        ]

        current_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
        history_day_groups: dict[tuple[str, str, str, date], list[dict[str, Any]]] = defaultdict(list)
        for row in current_rows:
            key = (row["project"], row["store"], row["channel"])
            if row["project"] in ACTIVE_PROJECTS and row["channel"] in PAID_CHANNELS and (row["cost"] > 0 or row["revenue_total_d7"] > 0):
                current_groups[key].append(row)
        for row in history_rows:
            key = (row["project"], row["store"], row["channel"], row["day"])
            if row["project"] in ACTIVE_PROJECTS and row["channel"] in PAID_CHANNELS and (row["cost"] > 0 or row["revenue_total_d120"] > 0):
                history_day_groups[key].append(row)

        results: list[PaybackMetrics] = []
        for key, group_rows in current_groups.items():
            project, store, channel = key
            current_cost = sum(row["cost"] for row in group_rows)
            if current_cost <= 0:
                continue
            history_groups = [
                rows
                for history_key, rows in history_day_groups.items()
                if history_key[:3] == key
            ]
            history_summaries = [_aggregate_recovery_group(rows) for rows in history_groups]
            current_summary = _aggregate_recovery_group(group_rows)
            current_d7 = current_summary["d7"]
            ratios = [
                row["d120"] / row["d7"]
                for row in history_summaries
                if row.get("d7", 0) > 0 and row.get("d120", 0) > 0
            ]
            history_d7_values = [row["d7"] for row in history_summaries if row.get("d7", 0) > 0]
            history_d120_values = [row["d120"] for row in history_summaries if row.get("d120", 0) > 0]
            multiplier = median(ratios) if ratios else 0.0
            predicted_d120 = current_d7 * multiplier if multiplier else 0.0
            results.append(
                PaybackMetrics(
                    project=project,
                    store=store,
                    channel=channel,
                    current_cost=current_cost,
                    current_d0=current_summary["d0"],
                    current_d1=current_summary["d1"],
                    current_d3=current_summary["d3"],
                    current_d7=current_d7,
                    mature_rows=len(history_summaries),
                    historical_median_d7=median(history_d7_values) if history_d7_values else 0.0,
                    historical_median_d120=median(history_d120_values) if history_d120_values else 0.0,
                    historical_median_d120_over_d7=multiplier,
                    predicted_d120=predicted_d120,
                    estimated_payback_day=_estimate_payback_day(current_d7, predicted_d120),
                )
            )
        return sorted(results, key=lambda item: (item.project, item.store, item.channel))

    def _self_check(
        self,
        breakdown_rows: list[Any],
        segments: list[SegmentMetrics],
        paybacks: list[PaybackMetrics],
        window_start: date,
        report_date: date,
        payback_error: str = "",
    ) -> dict[str, Any]:
        current_rows = [
            row
            for row in breakdown_rows
            if window_start <= row.date <= report_date and _project_key(row.game) in ACTIVE_PROJECTS
        ]
        raw_cost = round(sum(row.cost for row in current_rows), 2)
        project_cost = round(sum(row.cost for row in segments if row.level == "项目整体"), 2)
        channel_labels = {row.channel for row in segments if row.channel}
        issues: list[str] = []
        if raw_cost != project_cost:
            issues.append(f"项目整体花费合计不一致: raw={raw_cost}, grouped={project_cost}")
        if "Meta" in channel_labels:
            issues.append("渠道命名仍出现 Meta，应统一为 Facebook")
        if any(row.level.startswith("纯投放") and row.cost <= 0 for row in segments):
            issues.append("纯投放层出现 cost<=0 的行")
        paid_country_rows = [row for row in segments if row.level == "纯投放国家" and row.cost > 0]
        warnings: list[str] = []
        if not paybacks:
            warnings.append("未生成商店+渠道回本周期")
        if payback_error:
            warnings.append(f"回本周期接口异常：{payback_error[:180]}")
        if paid_country_rows and all(row.country == "Global" for row in paid_country_rows):
            warnings.append("当前 Adjust API 返回的付费国家维度只有 Global，国家赚钱/亏钱暂不能判断")
        return {
            "passed": not issues,
            "window": f"{window_start.isoformat()} ~ {report_date.isoformat()}",
            "raw_cost": raw_cost,
            "project_grouped_cost": project_cost,
            "payback_rows": len(paybacks),
            "issues": issues,
            "warnings": warnings,
        }

    def _render_markdown(
        self,
        window_start: date,
        report_date: date,
        segments: list[SegmentMetrics],
        paybacks: list[PaybackMetrics],
        self_check: dict[str, Any],
    ) -> str:
        lines = [
            f"# 盈利归因校对表 | {report_date.isoformat()}",
            "",
            f"- 数据窗口：{window_start.isoformat()} 至 {report_date.isoformat()}（上周四到本周三）",
            "- 口径说明：项目/商店/国家层包含 Adjust 归因到该维度的全部收入；纯投放层只保留有花费的付费渠道。",
            "- 净收入算法：iOS 内购按 70%，Google Play 内购按 85%，Amazon 内购按 80%，广告收入按 100%。",
            "- 回本周期说明：商店+渠道回本用 Adjust Cohort ROAS，当前 D7 乘历史 D120/D7 中位数估算 D120。",
            "",
            "## 结论先看",
            "",
        ]
        for project in sorted(ACTIVE_PROJECTS):
            lines.extend(self._project_takeaways(project, segments, paybacks))
        lines.extend(["", "## 项目 / 商店赚钱情况", ""])
        lines.extend(_table_for_segments([row for row in segments if row.level in {"项目整体", "商店"}]))
        lines.extend(["", "## 纯投放渠道赚钱情况", ""])
        lines.extend(_table_for_segments([row for row in segments if row.level in {"纯投放渠道", "纯投放商店+渠道"}]))
        lines.extend(["", "## 主要国家赚钱情况（按花费排序 Top 20）", ""])
        country_rows = [row for row in segments if row.level == "纯投放国家" and row.cost > 0]
        if country_rows and all(row.country == "Global" for row in country_rows):
            lines.append("- 当前数据源只返回 Global，不能判断具体国家赚钱/亏钱；需要改用 Adjust 国家 CSV 或单独 geo 维度拉取。")
        else:
            lines.extend(_table_for_segments(sorted(country_rows, key=lambda row: row.cost, reverse=True)[:20]))
        lines.extend(["", "## Top Campaign（按花费排序 Top 20）", ""])
        lines.extend(_table_for_segments(sorted([row for row in segments if row.level == "纯投放Campaign" and row.cost > 0], key=lambda row: row.cost, reverse=True)[:20]))
        lines.extend(["", "## Top 广告组（按花费排序 Top 20）", ""])
        lines.extend(_table_for_segments(sorted([row for row in segments if row.level == "纯投放广告组" and row.cost > 0], key=lambda row: row.cost, reverse=True)[:20]))
        lines.extend(["", "## Top 素材ID（按花费排序 Top 20）", ""])
        lines.extend(_table_for_segments(sorted([row for row in segments if row.level == "纯投放素材" and row.cost > 0], key=lambda row: row.cost, reverse=True)[:20]))
        lines.extend(["", "## 商店+渠道回本周期", ""])
        lines.extend(_table_for_paybacks(paybacks))
        lines.extend(["", "## 自检", ""])
        lines.append(f"- 结果：{'通过' if self_check['passed'] else '失败'}")
        lines.append(f"- 原始花费合计：{self_check['raw_cost']:.2f}")
        lines.append(f"- 项目分组合计：{self_check['project_grouped_cost']:.2f}")
        lines.append(f"- 回本周期行数：{self_check['payback_rows']}")
        if self_check["issues"]:
            lines.extend(f"- 问题：{issue}" for issue in self_check["issues"])
        else:
            lines.append("- 未发现口径自检问题。")
        for warning in self_check.get("warnings", []):
            lines.append(f"- 可信度提示：{warning}")
        lines.append("")
        return "\n".join(lines)

    def _project_takeaways(self, project: str, segments: list[SegmentMetrics], paybacks: list[PaybackMetrics]) -> list[str]:
        overall = next((row for row in segments if row.project == project and row.level == "项目整体"), None)
        stores = [row for row in segments if row.project == project and row.level == "商店" and row.cost > 0]
        channels = [row for row in segments if row.project == project and row.level == "纯投放渠道" and row.cost > 0]
        countries = [row for row in segments if row.project == project and row.level == "纯投放国家" and row.cost > 0]
        campaigns = [row for row in segments if row.project == project and row.level == "纯投放Campaign" and row.cost > 0]
        adgroups = [row for row in segments if row.project == project and row.level == "纯投放广告组" and row.cost > 0]
        creatives = [row for row in segments if row.project == project and row.level == "纯投放素材" and row.cost > 0]
        project_paybacks = [row for row in paybacks if row.project == project]

        lines = [f"### {project}", ""]
        if overall:
            lines.append(
                f"- 项目整体：净 ROI {overall.net_roi:.2f}，净利润 {overall.net_profit:.0f}，判断：{overall.status}。"
            )
        if stores:
            weak_stores = ", ".join(f"{row.store} 净ROI {row.net_roi:.2f}" for row in stores if row.net_roi < 1)
            good_stores = ", ".join(f"{row.store} 净ROI {row.net_roi:.2f}" for row in stores if row.net_roi >= 1)
            lines.append(f"- 商店：赚钱={good_stores or '无'}；不赚钱={weak_stores or '无'}。")
        if channels:
            weak_channels = ", ".join(f"{row.channel} 净ROI {row.net_roi:.2f}" for row in channels if row.net_roi < 1)
            good_channels = ", ".join(f"{row.channel} 净ROI {row.net_roi:.2f}" for row in channels if row.net_roi >= 1)
            lines.append(f"- 纯投放渠道：赚钱={good_channels or '无'}；不赚钱={weak_channels or '无'}。")
        if countries:
            if all(row.country == "Global" for row in countries):
                lines.append("- 国家：当前数据源未返回国家拆分，暂不能判断哪个国家赚钱/亏钱。")
            else:
                good_country = max(countries, key=lambda row: (row.net_roi >= 1, row.net_profit, row.cost))
                weak_country = min(countries, key=lambda row: (row.net_roi, -row.cost))
                lines.append(
                    f"- 国家：当前最好是 {good_country.country}（净ROI {good_country.net_roi:.2f}），最差是 {weak_country.country}（净ROI {weak_country.net_roi:.2f}）。"
                )
        if campaigns:
            top_campaign = max(campaigns, key=lambda row: (row.net_profit, row.cost))
            weak_campaign = min(campaigns, key=lambda row: (row.net_roi, -row.cost))
            lines.append(
                f"- Campaign：当前最好是 `{top_campaign.campaign}`（ID `{top_campaign.campaign_id or '-'}`，净ROI {top_campaign.net_roi:.2f}），最弱是 `{weak_campaign.campaign}`（ID `{weak_campaign.campaign_id or '-'}`，净ROI {weak_campaign.net_roi:.2f}）。"
            )
        if adgroups:
            top_adgroup = max(adgroups, key=lambda row: (row.net_profit, row.cost))
            weak_adgroup = min(adgroups, key=lambda row: (row.net_roi, -row.cost))
            lines.append(
                f"- 广告组：当前最好是 `{top_adgroup.adgroup}`（ID `{top_adgroup.adgroup_id or '-'}`，净ROI {top_adgroup.net_roi:.2f}），最弱是 `{weak_adgroup.adgroup}`（ID `{weak_adgroup.adgroup_id or '-'}`，净ROI {weak_adgroup.net_roi:.2f}）。"
            )
        if creatives:
            top_creative = max(creatives, key=lambda row: (row.net_profit, row.cost))
            weak_creative = min(creatives, key=lambda row: (row.net_roi, -row.cost))
            lines.append(
                f"- 素材ID：当前最好是 `{top_creative.creative_id or top_creative.creative_name or '-'}`（名称 `{top_creative.creative_name or '-'}`，净ROI {top_creative.net_roi:.2f}），最弱是 `{weak_creative.creative_id or weak_creative.creative_name or '-'}`（名称 `{weak_creative.creative_name or '-'}`，净ROI {weak_creative.net_roi:.2f}）。"
            )
        if project_paybacks:
            payback_text = "; ".join(
                f"{row.store}/{row.channel} D7 {row.current_d7:.0%} -> 预测D120 {row.predicted_d120:.0%}，{_payback_text(row)}"
                for row in project_paybacks
            )
            lines.append(f"- 回本周期：{payback_text}。")
        lines.append("")
        return lines


def _align_to_wednesday(value: date) -> date:
    return value - timedelta(days=(value.weekday() - 2) % 7)


def _project_key(name: str) -> str:
    cleaned = (name or "").strip()
    match = re.search(r"\bP0*([0-9]+)\b", cleaned.upper())
    if match:
        return f"P{int(match.group(1)):02d}"
    return cleaned


def _normalize_store(value: str) -> str:
    normalized = (value or "").strip().lower()
    mapping = {"app_store": "iOS", "google_play": "Android", "amazon": "Amazon"}
    return mapping.get(normalized, value or "未知商店")


def _normalize_channel(value: str) -> str:
    normalized = (value or "").strip().lower()
    if "google" in normalized:
        return "Google"
    if "facebook" in normalized or "instagram" in normalized or "off-facebook" in normalized:
        return "Facebook"
    if "apple" in normalized and "search" in normalized:
        return "Apple Search"
    if "applovin" in normalized:
        return "Applovin"
    if "unity" in normalized:
        return "Unity Ads"
    if "organic" in normalized:
        return "Organic"
    return value or "未知渠道"


def _net_revenue(store: str, iap_revenue_gross: float, ad_revenue: float) -> float:
    normalized = _normalize_store(store)
    rate = {
        "iOS": 0.70,
        "Android": 0.85,
        "Amazon": 0.80,
    }.get(normalized, 0.80)
    return iap_revenue_gross * rate + ad_revenue


def _level_rank(level: str) -> int:
    order = {
        "项目整体": 0,
        "商店": 1,
        "纯投放渠道": 2,
        "纯投放商店+渠道": 3,
        "国家": 4,
        "纯投放国家": 5,
        "商店+国家": 6,
        "纯投放商店+渠道+国家": 7,
        "纯投放Campaign": 8,
        "纯投放国家+Campaign": 9,
        "纯投放广告组": 10,
        "纯投放国家+广告组": 11,
        "纯投放素材": 12,
        "纯投放国家+素材": 13,
        "纯投放Source": 14,
    }
    return order.get(level, 99)


def _row_day(row: dict[str, Any]) -> date:
    value = str(row.get("day") or row.get("date") or "")
    match = re.search(r"\d{4}-\d{2}-\d{2}", value)
    if not match:
        raise ValueError(f"Unsupported Adjust day value: {value!r}")
    year, month, day = (int(part) for part in match.group(0).split("-"))
    return date(year, month, day)


def _to_float(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    if isinstance(value, list):
        value = value[0] if value else 0
    text = str(value).replace(",", "").replace("%", "").strip()
    if not text:
        return 0.0
    return float(text)


def _recovery_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "project": _project_key(str(row.get("app") or "")),
        "store": _normalize_store(str(row.get("store_type") or "")),
        "channel": _normalize_channel(str(row.get("network") or "")),
        "day": _row_day(row),
        "cost": _to_float(row.get("cost")),
        "revenue_total_d0": _to_float(row.get("revenue_total_d0")),
        "revenue_total_d1": _to_float(row.get("revenue_total_d1")),
        "revenue_total_d3": _to_float(row.get("revenue_total_d3")),
        "revenue_total_d7": _to_float(row.get("revenue_total_d7")),
        "revenue_total_d120": _to_float(row.get("revenue_total_d119") or row.get("revenue_total_d120") or row.get("revenue_total_d99")),
    }


def _aggregate_recovery_group(rows: Iterable[dict[str, Any]]) -> dict[str, float]:
    rows = list(rows)
    spend = sum(row["cost"] for row in rows)
    if spend <= 0:
        return {"cost": 0.0, "d0": 0.0, "d1": 0.0, "d3": 0.0, "d7": 0.0, "d120": 0.0}
    return {
        "cost": spend,
        "d0": sum(row["revenue_total_d0"] for row in rows) / spend,
        "d1": sum(row["revenue_total_d1"] for row in rows) / spend,
        "d3": sum(row["revenue_total_d3"] for row in rows) / spend,
        "d7": sum(row["revenue_total_d7"] for row in rows) / spend,
        "d120": sum(row["revenue_total_d120"] for row in rows) / spend,
    }


def _estimate_payback_day(current_d7: float, predicted_d120: float) -> float | None:
    if current_d7 >= 1.0:
        return float(PAYBACK_CURRENT_DAY)
    if predicted_d120 < 1.0 or predicted_d120 <= current_d7:
        return None
    progress = (1.0 - current_d7) / (predicted_d120 - current_d7)
    return PAYBACK_CURRENT_DAY + progress * (PAYBACK_TARGET_DAY - PAYBACK_CURRENT_DAY)


def _fmt_float(value: float, digits: int = 2) -> str:
    if math.isfinite(value):
        return f"{value:.{digits}f}"
    return "0.00"


def _fmt_money(value: float) -> str:
    return f"{value:.0f}"


def _payback_text(row: PaybackMetrics) -> str:
    if row.estimated_payback_day is None:
        return "预计120天内难回本"
    return f"预计约{row.estimated_payback_day:.0f}天回本"


def _write_segments_csv(path: Path, rows: list[SegmentMetrics]) -> None:
    fields = [
        "project",
        "level",
        "store",
        "channel",
        "country",
        "campaign",
        "campaign_id",
        "adgroup",
        "adgroup_id",
        "creative_name",
        "creative_id",
        "source_name",
        "source_id",
        "cost",
        "gross_revenue",
        "net_revenue",
        "gross_roi",
        "net_roi",
        "net_profit",
        "status",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "project": row.project,
                    "level": row.level,
                    "store": row.store,
                    "channel": row.channel,
                    "country": row.country,
                    "campaign": row.campaign,
                    "campaign_id": row.campaign_id,
                    "adgroup": row.adgroup,
                    "adgroup_id": row.adgroup_id,
                    "creative_name": row.creative_name,
                    "creative_id": row.creative_id,
                    "source_name": row.source_name,
                    "source_id": row.source_id,
                    "cost": _fmt_float(row.cost),
                    "gross_revenue": _fmt_float(row.gross_revenue),
                    "net_revenue": _fmt_float(row.net_revenue),
                    "gross_roi": _fmt_float(row.gross_roi),
                    "net_roi": _fmt_float(row.net_roi),
                    "net_profit": _fmt_float(row.net_profit),
                    "status": row.status,
                }
            )


def _write_paybacks_csv(path: Path, rows: list[PaybackMetrics]) -> None:
    fields = [
        "project",
        "store",
        "channel",
        "current_cost",
        "current_D0",
        "current_D1",
        "current_D3",
        "current_D7",
        "mature_rows",
        "historical_median_D7",
        "historical_median_D120",
        "historical_median_D120_over_D7",
        "predicted_D120",
        "estimated_payback_day",
        "status",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "project": row.project,
                    "store": row.store,
                    "channel": row.channel,
                    "current_cost": _fmt_float(row.current_cost),
                    "current_D0": _fmt_float(row.current_d0, 4),
                    "current_D1": _fmt_float(row.current_d1, 4),
                    "current_D3": _fmt_float(row.current_d3, 4),
                    "current_D7": _fmt_float(row.current_d7, 4),
                    "mature_rows": row.mature_rows,
                    "historical_median_D7": _fmt_float(row.historical_median_d7, 4),
                    "historical_median_D120": _fmt_float(row.historical_median_d120, 4),
                    "historical_median_D120_over_D7": _fmt_float(row.historical_median_d120_over_d7, 4),
                    "predicted_D120": _fmt_float(row.predicted_d120, 4),
                    "estimated_payback_day": "" if row.estimated_payback_day is None else _fmt_float(row.estimated_payback_day, 1),
                    "status": row.status,
                }
            )


def _table_for_segments(rows: list[SegmentMetrics]) -> list[str]:
    if not rows:
        return ["- 暂无数据。"]
    lines = [
        "| 项目 | 层级 | 商店 | 渠道 | 国家 | Campaign | 广告组 | 素材ID | 素材名称 | 花费 | 总收入ROI | 净ROI | 净利润 | 判断 |",
        "|---|---|---|---|---|---|---|---|---|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    row.project,
                    row.level,
                    row.store or "-",
                    row.channel or "-",
                    row.country or "-",
                    (f"{row.campaign} ({row.campaign_id})" if row.campaign or row.campaign_id else "-"),
                    (f"{row.adgroup} ({row.adgroup_id})" if row.adgroup or row.adgroup_id else "-"),
                    row.creative_id or "-",
                    row.creative_name or "-",
                    _fmt_money(row.cost),
                    _fmt_float(row.gross_roi),
                    _fmt_float(row.net_roi),
                    _fmt_money(row.net_profit),
                    row.status,
                ]
            )
            + " |"
        )
    return lines


def _table_for_paybacks(rows: list[PaybackMetrics]) -> list[str]:
    if not rows:
        return ["- 暂无数据。"]
    lines = ["| 项目 | 商店 | 渠道 | 花费 | D7实际 | 历史D120中位数 | 预测D120 | 回本预估 | 判断 |", "|---|---|---|---:|---:|---:|---:|---|---|"]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    row.project,
                    row.store,
                    row.channel,
                    _fmt_money(row.current_cost),
                    f"{row.current_d7:.0%}",
                    f"{row.historical_median_d120:.0%}",
                    f"{row.predicted_d120:.0%}",
                    _payback_text(row),
                    row.status,
                ]
            )
            + " |"
        )
    return lines
