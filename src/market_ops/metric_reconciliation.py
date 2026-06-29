from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.digest import WeeklyDigestBuilder
from market_ops.models import RevenueBreakdownRow
from market_ops.pipeline import DataRepository


ACTIVE_PROJECTS = {"P02", "P04", "P07"}


@dataclass(slots=True)
class MetricTrace:
    scope: str
    metric: str
    display_value: str
    raw_value: float | None
    rounded_value: float | int | None
    source: str
    date_window: str
    filters: str
    formula: str
    notes: str = ""


class WeeklyMetricReconciliationBuilder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._repository = DataRepository(settings)
        self._digest_builder = WeeklyDigestBuilder(settings)

    def build(self, report_date: date) -> dict[str, Path]:
        report_date = self._align_to_wednesday(report_date)
        window_start = report_date - timedelta(days=6)
        previous_start = window_start - timedelta(days=7)
        previous_end = window_start - timedelta(days=1)
        date_window = f"{window_start.isoformat()} ~ {report_date.isoformat()}"

        ads_rows = self._repository.load_ads_performance()
        revenue_rows = self._repository.load_adjust_revenue()
        breakdown_rows = self._repository.load_adjust_revenue_breakdown(window_start, report_date)
        digest_path = self._settings.active_output_dir / f"weekly_digest_{report_date.strftime('%Y%m%d')}.md"

        current_total_ads, current_detail_ads = self._digest_builder._split_window_ads(ads_rows, window_start, report_date)
        previous_total_ads, previous_detail_ads = self._digest_builder._split_window_ads(ads_rows, previous_start, previous_end)

        active_games = {
            row.game
            for row in current_total_ads + current_detail_ads
            if row.game
        }
        current_revenue = [row for row in revenue_rows if window_start <= row.date <= report_date]
        previous_revenue = [row for row in revenue_rows if previous_start <= row.date <= previous_end]
        current_spend = sum(row.total_cost for row in current_revenue)
        previous_spend = sum(row.total_cost for row in previous_revenue)
        current_revenue_total = sum(row.total_revenue for row in current_revenue)
        previous_revenue_total = sum(row.total_revenue for row in previous_revenue)
        current_roi = current_revenue_total / current_spend if current_spend else 0.0
        previous_roi = previous_revenue_total / previous_spend if previous_spend else 0.0
        trusted_detail_rows = self._digest_builder._trusted_detail_rows(current_detail_ads)
        trusted_detail_projects = {
            self._digest_builder._project_key(row.game)
            for row in trusted_detail_rows
            if row.game
        }

        traces: list[MetricTrace] = [
            MetricTrace(
                scope="公司",
                metric="本周花费",
                display_value=f"{round(current_spend):.0f}",
                raw_value=current_spend,
                rounded_value=round(current_spend),
                source="output/normalized/adjust_revenue.csv -> total_cost",
                date_window=date_window,
                filters="排除黑名单 Adjust App；公司层按 Adjust 全量收入口径",
                formula="sum(total_cost)",
                notes=f"上周窗口 {previous_start.isoformat()} ~ {previous_end.isoformat()} 原始值 {previous_spend:.4f}",
            ),
            MetricTrace(
                scope="公司",
                metric="整体收入",
                display_value=f"{round(current_revenue_total):.0f}",
                raw_value=current_revenue_total,
                rounded_value=round(current_revenue_total),
                source="output/normalized/adjust_revenue.csv -> total_revenue",
                date_window=date_window,
                filters="排除黑名单 Adjust App；公司层按 Adjust 全量收入口径",
                formula="sum(total_revenue)",
                notes=f"上周窗口 {previous_start.isoformat()} ~ {previous_end.isoformat()} 原始值 {previous_revenue_total:.4f}",
            ),
            MetricTrace(
                scope="公司",
                metric="公司总收入ROI",
                display_value=f"{current_roi:.2f}",
                raw_value=current_roi,
                rounded_value=round(current_roi, 2),
                source="output/normalized/adjust_revenue.csv -> total_revenue / total_cost",
                date_window=date_window,
                filters="排除黑名单 Adjust App；公司层按 Adjust 全量收入口径",
                formula="sum(total_revenue) / sum(total_cost)",
                notes=f"上周 ROI 原始值 {previous_roi:.6f}",
            ),
            MetricTrace(
                scope="公司",
                metric="主投渠道",
                display_value=self._digest_builder._top_channel(trusted_detail_rows or current_detail_ads),
                raw_value=None,
                rounded_value=None,
                source="output/normalized/ads_performance.csv -> channel / spend",
                date_window=date_window,
                filters="只看非 All 明细；优先使用可信项目明细",
                formula="argmax(sum(spend) by channel)",
                notes=f"可信项目={','.join(sorted(trusted_detail_projects)) or '无'}",
            ),
        ]

        grouped_breakdown: dict[str, list[RevenueBreakdownRow]] = {}
        for row in breakdown_rows:
            if row.cost <= 0:
                continue
            project = self._digest_builder._project_key(row.game)
            grouped_breakdown.setdefault(project, []).append(row)

        grouped_total_ads: dict[str, list[Any]] = {}
        grouped_detail_ads: dict[str, list[Any]] = {}
        grouped_prev_total_ads: dict[str, list[Any]] = {}
        grouped_revenue: dict[str, list[Any]] = {}
        grouped_prev_revenue: dict[str, list[Any]] = {}
        grouped_names: dict[str, set[str]] = {}

        for row in ads_rows:
            project = self._digest_builder._project_key(row.game)
            grouped_names.setdefault(project, set()).add(row.game)
            if window_start <= row.date <= report_date:
                if self._digest_builder._is_total_row(row):
                    grouped_total_ads.setdefault(project, []).append(row)
                else:
                    grouped_detail_ads.setdefault(project, []).append(row)
            elif previous_start <= row.date <= previous_end:
                if self._digest_builder._is_total_row(row):
                    grouped_prev_total_ads.setdefault(project, []).append(row)

        for row in revenue_rows:
            project = self._digest_builder._project_key(row.game)
            grouped_names.setdefault(project, set()).add(row.game)
            if window_start <= row.date <= report_date:
                grouped_revenue.setdefault(project, []).append(row)
            elif previous_start <= row.date <= previous_end:
                grouped_prev_revenue.setdefault(project, []).append(row)

        for project in sorted(ACTIVE_PROJECTS):
            current_revenue_rows = grouped_revenue.get(project, [])
            previous_revenue_rows = grouped_prev_revenue.get(project, [])
            summary_rows = grouped_total_ads.get(project) or grouped_detail_ads.get(project, [])
            spend_raw = sum(row.total_cost for row in current_revenue_rows)
            previous_spend_raw = sum(row.total_cost for row in previous_revenue_rows)
            if spend_raw == 0:
                spend_raw = sum(row.spend for row in summary_rows)
            if previous_spend_raw == 0:
                spend_raw = sum(row.spend for row in summary_rows)
            total_revenue_raw = sum(row.total_revenue for row in current_revenue_rows)
            total_revenue_roi_raw = total_revenue_raw / spend_raw if spend_raw else 0.0
            paid_roi_net_raw = self._digest_builder._paid_roi_net(grouped_breakdown.get(project, []))
            display_name = self._digest_builder._project_display_name(project, grouped_names.get(project, set()))
            detail_ready = bool(grouped_detail_ads.get(project)) and project in self._settings.trusted_detail_project_keys
            spend_change = self._digest_builder._pct_change(spend_raw, previous_spend_raw)

            traces.extend(
                [
                    MetricTrace(
                        scope=display_name,
                        metric="花费",
                        display_value=f"{round(spend_raw):.0f}",
                        raw_value=spend_raw,
                        rounded_value=round(spend_raw),
                        source="output/normalized/adjust_revenue.csv -> total_cost",
                        date_window=date_window,
                        filters=f"project_key={project}",
                        formula="sum(total_cost); 若该窗口 Adjust cost=0，则回退到 ads_performance 汇总 spend",
                        notes=f"较上周 {spend_change}",
                    ),
                    MetricTrace(
                        scope=display_name,
                        metric="总收入",
                        display_value=f"{round(total_revenue_raw):.0f}",
                        raw_value=total_revenue_raw,
                        rounded_value=round(total_revenue_raw),
                        source="output/normalized/adjust_revenue.csv -> total_revenue",
                        date_window=date_window,
                        filters=f"project_key={project}",
                        formula="sum(total_revenue)",
                    ),
                    MetricTrace(
                        scope=display_name,
                        metric="总收入ROI",
                        display_value=f"{total_revenue_roi_raw:.2f}",
                        raw_value=total_revenue_roi_raw,
                        rounded_value=round(total_revenue_roi_raw, 2),
                        source="output/normalized/adjust_revenue.csv",
                        date_window=date_window,
                        filters=f"project_key={project}",
                        formula="sum(total_revenue) / sum(total_cost)",
                        notes="这是项目总收入口径，不等于付费净ROI",
                    ),
                    MetricTrace(
                        scope=display_name,
                        metric="付费净ROI",
                        display_value="暂无" if paid_roi_net_raw is None else f"{paid_roi_net_raw:.2f}",
                        raw_value=paid_roi_net_raw,
                        rounded_value=None if paid_roi_net_raw is None else round(paid_roi_net_raw, 2),
                        source="Adjust revenue breakdown（API 或 Downloads 下 revenue_breakdown_day_*.csv）",
                        date_window=date_window,
                        filters=f"project_key={project} and cost>0",
                        formula="sum(iap_gross * store_net_rate + ad_revenue) / sum(cost)",
                        notes=f"detail_ready={'YES' if detail_ready else 'NO'}",
                    ),
                ]
            )

        checks = self._run_checks(traces)

        suffix = report_date.strftime("%Y%m%d")
        md_path = self._settings.active_output_dir / f"weekly_metric_reconciliation_{suffix}.md"
        json_path = self._settings.active_output_dir / f"weekly_metric_reconciliation_{suffix}.json"
        md_path.write_text(self._render_markdown(report_date, digest_path, traces, checks), encoding="utf-8")
        json_path.write_text(
            json.dumps(
                {
                    "report_date": report_date.isoformat(),
                    "digest_path": str(digest_path),
                    "checks": checks,
                    "traces": [asdict(item) for item in traces],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"markdown": md_path, "json": json_path}

    @staticmethod
    def _align_to_wednesday(value: date) -> date:
        return value - timedelta(days=(value.weekday() - 2) % 7)

    @staticmethod
    def _run_checks(traces: list[MetricTrace]) -> dict[str, Any]:
        issues: list[str] = []
        required = {
            ("公司", "本周花费"),
            ("公司", "整体收入"),
            ("公司", "公司总收入ROI"),
            ("P04 Witch", "花费"),
            ("P04 Witch", "总收入"),
            ("P04 Witch", "总收入ROI"),
            ("P02 Mermaid", "花费"),
            ("P02 Mermaid", "总收入"),
            ("P02 Mermaid", "总收入ROI"),
            ("P07 Vampire", "花费"),
            ("P07 Vampire", "总收入"),
            ("P07 Vampire", "总收入ROI"),
        }
        seen = {(item.scope, item.metric) for item in traces}
        missing = sorted(required - seen)
        if missing:
            issues.append("缺少关键对账项: " + ", ".join(f"{scope}/{metric}" for scope, metric in missing))
        return {"passed": not issues, "issues": issues}

    @staticmethod
    def _render_markdown(report_date: date, digest_path: Path, traces: list[MetricTrace], checks: dict[str, Any]) -> str:
        lines = [
            f"# 周报数字对账表 | {report_date.isoformat()}",
            "",
            f"- 对账目标文件：[{digest_path.name}]({digest_path.resolve().as_posix()})",
            f"- 自检结果：{'通过' if checks.get('passed') else '失败'}",
        ]
        for issue in checks.get("issues", []):
            lines.append(f"- 问题：{issue}")
        lines.extend(
            [
                "",
                "## 公司层",
                "",
                "| 指标 | 展示值 | 原始值 | 四舍五入后 | 来源 | 日期窗口 | 筛选条件 | 公式 | 备注 |",
                "|---|---:|---:|---:|---|---|---|---|---|",
            ]
        )
        for item in [row for row in traces if row.scope == "公司"]:
            lines.append(
                "| "
                + " | ".join(
                    [
                        item.metric,
                        item.display_value,
                        "" if item.raw_value is None else f"{item.raw_value:.6f}",
                        "" if item.rounded_value is None else str(item.rounded_value),
                        item.source,
                        item.date_window,
                        item.filters,
                        item.formula,
                        item.notes or "-",
                    ]
                )
                + " |"
            )

        for scope in ["P04 Witch", "P02 Mermaid", "P07 Vampire"]:
            rows = [row for row in traces if row.scope == scope]
            if not rows:
                continue
            lines.extend(
                [
                    "",
                    f"## {scope}",
                    "",
                    "| 指标 | 展示值 | 原始值 | 四舍五入后 | 来源 | 日期窗口 | 筛选条件 | 公式 | 备注 |",
                    "|---|---:|---:|---:|---|---|---|---|---|",
                ]
            )
            for item in rows:
                raw_text = ""
                if item.raw_value is not None:
                    raw_text = f"{item.raw_value:.6f}" if isinstance(item.raw_value, float) else str(item.raw_value)
                lines.append(
                    "| "
                    + " | ".join(
                        [
                            item.metric,
                            item.display_value,
                            raw_text,
                            "" if item.rounded_value is None else str(item.rounded_value),
                            item.source,
                            item.date_window,
                            item.filters,
                            item.formula,
                            item.notes or "-",
                        ]
                    )
                    + " |"
                )
        lines.extend(
            [
                "",
                "## 说明",
                "",
                "- 公司层和项目层花费、收入、总收入ROI都优先使用 Adjust 标准化收入表。",
                "- 项目层付费净ROI使用 Adjust revenue breakdown 口径，只统计 cost > 0 的付费明细。",
                "- 四舍五入显示差 1 的情况，通常来自原始值先累计后再显示为整数。",
                "",
            ]
        )
        return "\n".join(lines)
