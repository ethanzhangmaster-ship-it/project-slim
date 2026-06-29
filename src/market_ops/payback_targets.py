from __future__ import annotations

import csv
import json
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
import re
from typing import Any

from market_ops.clients.adjust import AdjustClient
from market_ops.config import Settings


PROJECTS = ("P02", "P04", "P07")
RECOVERY_METRICS = ("D0", "D1", "D3", "D7", "D30", "D60", "D90", "D120")
CURRENT_METRICS = ("D0", "D1", "D3", "D7")
MATURE_AGE_DAYS = 120
MIN_SECONDARY_SAMPLE = 5
MIN_SEGMENT_PROFITABLE_SAMPLE = 3
RECOVERY_DELAY_BUFFER_DAYS = {"D0": 1, "D1": 2, "D3": 4, "D7": 9, "D30": 32}


@dataclass(slots=True)
class RecoveryTarget:
    floor: float | None
    target: float | None
    strong: float | None


@dataclass(slots=True)
class SecondaryGuardrail:
    label: str
    direction: str
    floor: float | None = None
    ceiling: float | None = None
    target: float | None = None
    sample_count: int = 0
    confidence: str = "low"
    note: str = ""


@dataclass(slots=True)
class SegmentTargets:
    project: str
    store: str
    channel: str
    current_recovery: dict[str, float]
    recovery_targets: dict[str, RecoveryTarget]
    mature_samples: int
    profitable_samples: int
    current_sample_age_days: int
    data_status: str

    @property
    def key(self) -> str:
        return _segment_key(self.store, self.channel)


@dataclass(slots=True)
class ProjectTargets:
    project: str
    mature_weeks: int
    profitable_weeks: int
    current_recovery: dict[str, float]
    recovery_targets: dict[str, RecoveryTarget]
    profitable_median_multiplier: float | None
    profitable_p75_multiplier: float | None
    current_required_multiplier: float | None
    current_ads_roas: float | None
    current_cpi: float | None
    current_retention_d1: float | None
    current_arpu: float | None
    current_arppu: float | None
    cpi_guardrail: SecondaryGuardrail
    retention_guardrail: SecondaryGuardrail
    arpu_guardrail: SecondaryGuardrail
    arppu_guardrail: SecondaryGuardrail
    segment_targets: dict[str, SegmentTargets]
    findings: list[str]


class PaybackTargetsBuilder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build_targets_data(self, report_date: date) -> tuple[list[ProjectTargets], dict[str, Any]]:
        suffix = report_date.strftime("%Y%m%d")
        output_dir = self._settings.output_dir
        history_path, history_source_date = _resolve_payback_input_path(
            output_dir,
            "payback_cycle_weekly_history",
            report_date,
        )
        summary_path, summary_source_date = _resolve_payback_input_path(
            output_dir,
            "payback_cycle_summary",
            report_date,
        )
        ads_path = output_dir / "normalized" / "ads_performance.csv"
        revenue_path = output_dir / "normalized" / "adjust_revenue.csv"

        history_rows = _read_csv(history_path)
        summary_rows = _read_csv(summary_path)
        ads_rows = _read_csv(ads_path)
        revenue_rows = _read_csv(revenue_path)
        current_recovery = self._load_current_adjust_recovery(report_date)
        segment_targets = self._load_segment_targets(report_date)

        targets = self._build_targets(report_date, history_rows, summary_rows, ads_rows, revenue_rows, current_recovery, segment_targets)
        source_dates = {
            "history": history_source_date.isoformat(),
            "summary": summary_source_date.isoformat(),
            "current_recovery": report_date.isoformat() if current_recovery else "",
            "store_channel_segments": report_date.isoformat() if segment_targets else "",
        }
        self_check = self._self_check(report_date, targets, summary_rows, source_dates)
        return targets, self_check

    def build(self, report_date: date) -> dict[str, Path]:
        suffix = report_date.strftime("%Y%m%d")
        output_dir = self._settings.output_dir
        active_output_dir = self._settings.active_output_dir
        targets, self_check = self.build_targets_data(report_date)

        active_output_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = active_output_dir / f"payback_targets_{suffix}.md"
        csv_path = output_dir / f"payback_targets_{suffix}.csv"
        json_path = active_output_dir / f"payback_targets_self_check_{suffix}.json"

        markdown_path.write_text(self._render_markdown(report_date, targets, self_check), encoding="utf-8")
        _write_csv(csv_path, targets)
        json_path.write_text(json.dumps(self_check, ensure_ascii=False, indent=2), encoding="utf-8")
        return {
            "summary": markdown_path,
            "csv": csv_path,
            "self_check": json_path,
        }

    def _build_targets(
        self,
        report_date: date,
        history_rows: list[dict[str, str]],
        summary_rows: list[dict[str, str]],
        ads_rows: list[dict[str, str]],
        revenue_rows: list[dict[str, str]],
        current_recovery_by_project: dict[str, dict[str, float]] | None = None,
        segment_targets_by_project: dict[str, dict[str, SegmentTargets]] | None = None,
    ) -> list[ProjectTargets]:
        summary_by_project = {row["project"]: row for row in summary_rows if row.get("project")}
        weekly_ads = _aggregate_weekly_ads(ads_rows)
        weekly_revenue = _aggregate_weekly_revenue(revenue_rows)
        ads_confidence = _detect_ads_confidence(report_date, ads_rows)
        trusted_projects = self._settings.trusted_detail_project_keys
        current_recovery_by_project = current_recovery_by_project or {}
        segment_targets_by_project = segment_targets_by_project or {}

        result: list[ProjectTargets] = []
        for project in PROJECTS:
            history = [row for row in history_rows if row.get("project") == project]
            mature = [row for row in history if _to_float(row.get("newest_age")) >= MATURE_AGE_DAYS]
            profitable = [row for row in mature if _to_float(row.get("D120")) >= 1.0]
            if project not in summary_by_project:
                continue
            summary = summary_by_project[project]
            current_week_start = (report_date - timedelta(days=6)).isoformat()
            ads_trusted = project in trusted_projects
            current_ad = weekly_ads.get((project, current_week_start), {}) if ads_trusted else {}
            current_revenue = weekly_revenue.get((project, current_week_start), {})

            recovery_targets: dict[str, RecoveryTarget] = {}
            for metric in RECOVERY_METRICS:
                values = [_to_float(row.get(metric)) for row in profitable if _to_float(row.get(metric)) > 0]
                recovery_targets[metric] = RecoveryTarget(
                    floor=_quantile(values, 0.25),
                    target=_quantile(values, 0.50),
                    strong=_quantile(values, 0.75),
                )

            profitable_multipliers = [
                _to_float(row.get("D120")) / _to_float(row.get("D7"))
                for row in profitable
                if _to_float(row.get("D120")) > 0 and _to_float(row.get("D7")) > 0
            ]
            current_recovery = {
                metric: _to_float(summary.get(f"current_{metric}"))
                for metric in CURRENT_METRICS
            }
            if project in current_recovery_by_project:
                for metric, value in current_recovery_by_project[project].items():
                    if metric in CURRENT_METRICS:
                        current_recovery[metric] = value
            current_d7 = current_recovery.get("D7", 0.0)
            current_required_multiplier = (1.0 / current_d7) if current_d7 > 0 else None

            joined_secondary = _join_profitable_secondary(project, profitable, weekly_ads, weekly_revenue) if ads_trusted else []
            cpi_values = [item["cpi"] for item in joined_secondary if item["cpi"]]
            retention_values = [item["retention_d1"] for item in joined_secondary if item["retention_d1"]]
            arpu_values = [item["arpu"] for item in joined_secondary if item["arpu"]]
            arppu_values = [item["arppu"] for item in joined_secondary if item["arppu"]]

            if ads_trusted:
                cpi_guardrail = _build_cpi_guardrail(cpi_values, ads_confidence.get(project, "low"))
                retention_guardrail = _build_retention_guardrail(retention_values, ads_confidence.get(project, "low"))
            else:
                cpi_guardrail = _blocked_guardrail(
                    label="CPI",
                    direction="max",
                    note="无可信项目级投放明细，当前不能建立硬 CPI 门槛",
                )
                retention_guardrail = _blocked_guardrail(
                    label="D1 retention",
                    direction="min",
                    note="无可信项目级投放明细，当前不能建立硬 D1 留存门槛",
                )
            arpu_guardrail = _build_floor_guardrail("ARPU", arpu_values, "medium", "项目整体 ARPU，只作变现质量辅助信号")
            arppu_guardrail = _build_floor_guardrail("ARPPU", arppu_values, "low", "ARPPU 波动较大，只能做弱参考")

            findings = _build_findings(
                project=project,
                current_recovery=current_recovery,
                recovery_targets=recovery_targets,
                current_required_multiplier=current_required_multiplier,
                profitable_median_multiplier=_quantile(profitable_multipliers, 0.50),
                current_cpi=current_ad.get("cpi"),
                current_retention_d1=current_ad.get("retention_d1"),
                current_arpu=current_revenue.get("arpu"),
                cpi_guardrail=cpi_guardrail,
                retention_guardrail=retention_guardrail,
                arpu_guardrail=arpu_guardrail,
                ads_trusted=ads_trusted,
            )

            result.append(
                ProjectTargets(
                    project=project,
                    mature_weeks=len(mature),
                    profitable_weeks=len(profitable),
                    current_recovery=current_recovery,
                    recovery_targets=recovery_targets,
                    profitable_median_multiplier=_quantile(profitable_multipliers, 0.50),
                    profitable_p75_multiplier=_quantile(profitable_multipliers, 0.75),
                    current_required_multiplier=current_required_multiplier,
                    current_ads_roas=current_ad.get("ads_roas"),
                    current_cpi=current_ad.get("cpi"),
                    current_retention_d1=current_ad.get("retention_d1"),
                    current_arpu=current_revenue.get("arpu"),
                    current_arppu=current_revenue.get("arppu"),
                    cpi_guardrail=cpi_guardrail,
                    retention_guardrail=retention_guardrail,
                    arpu_guardrail=arpu_guardrail,
                    arppu_guardrail=arppu_guardrail,
                    segment_targets=segment_targets_by_project.get(project, {}),
                    findings=findings,
                )
            )
        return result

    def _self_check(
        self,
        report_date: date,
        targets: list[ProjectTargets],
        summary_rows: list[dict[str, str]],
        source_dates: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        issues: list[str] = []
        warnings: list[str] = []
        summary_projects = sorted(row.get("project") for row in summary_rows if row.get("project") in PROJECTS)
        target_projects = sorted(item.project for item in targets)
        if summary_projects != list(PROJECTS):
            issues.append(f"summary projects mismatch: {summary_projects}")
        if target_projects != list(PROJECTS):
            issues.append(f"target projects mismatch: {target_projects}")
        for item in targets:
            d7_floor = item.recovery_targets["D7"].floor
            d30_floor = item.recovery_targets["D30"].floor
            if d7_floor is None or d30_floor is None:
                issues.append(f"{item.project} missing D7/D30 recovery floor")
            if item.cpi_guardrail.confidence == "blocked":
                warnings.append(f"{item.project} CPI guardrail blocked: no trusted project detail")
            elif item.cpi_guardrail.confidence == "low":
                warnings.append(f"{item.project} CPI guardrail low confidence")
            if item.retention_guardrail.confidence == "blocked":
                warnings.append(f"{item.project} retention guardrail blocked: no trusted project detail")
            elif item.retention_guardrail.confidence == "low":
                warnings.append(f"{item.project} retention guardrail low confidence")
        return {
            "passed": not issues,
            "report_date": report_date.isoformat(),
            "projects": target_projects,
            "source_dates": source_dates or {},
            "issues": issues,
            "warnings": warnings,
        }

    def _load_current_adjust_recovery(self, report_date: date) -> dict[str, dict[str, float]]:
        try:
            if self._settings.adjust_api_token:
                client = AdjustClient(self._settings.adjust_api_token)
            elif self._settings.adjust_dashboard_config_path and self._settings.adjust_dashboard_config_path.exists():
                client = AdjustClient.from_dashboard_config(self._settings.adjust_dashboard_config_path)
            else:
                return {}
            raw_rows = client.fetch_recovery_cohort_rows(
                start_date=(report_date - timedelta(days=6)).isoformat(),
                end_date=report_date.isoformat(),
                dimensions="app,app_token,day",
                day_suffixes=(0, 2, 6),
            )
        except Exception:
            return {}

        buckets: dict[str, dict[str, float]] = defaultdict(lambda: {"cost": 0.0, "D0": 0.0, "D3": 0.0, "D7": 0.0})
        for row in raw_rows:
            project = _project_key(row.get("app", ""))
            if project not in PROJECTS:
                continue
            cost = _to_float(row.get("cost"))
            if cost <= 0:
                continue
            buckets[project]["cost"] += cost
            buckets[project]["D0"] += cost * _to_float(row.get("roas_d0"))
            buckets[project]["D3"] += cost * _to_float(row.get("roas_d2"))
            buckets[project]["D7"] += cost * _to_float(row.get("roas_d6"))

        result: dict[str, dict[str, float]] = {}
        for project, values in buckets.items():
            cost = values["cost"]
            if cost <= 0:
                continue
            result[project] = {
                "D0": values["D0"] / cost,
                "D1": values["D0"] / cost,
                "D3": values["D3"] / cost,
                "D7": values["D7"] / cost,
            }
        return result

    def _load_segment_targets(self, report_date: date) -> dict[str, dict[str, SegmentTargets]]:
        try:
            if self._settings.adjust_api_token:
                client = AdjustClient(self._settings.adjust_api_token)
            elif self._settings.adjust_dashboard_config_path and self._settings.adjust_dashboard_config_path.exists():
                client = AdjustClient.from_dashboard_config(self._settings.adjust_dashboard_config_path)
            else:
                return {}
            rows = client.fetch_recovery_cohort_rows(
                start_date=(report_date - timedelta(days=210)).isoformat(),
                end_date=report_date.isoformat(),
                dimensions="app,app_token,store_type,network,day",
                day_suffixes=(0, 2, 6, 29, 119),
            )
        except Exception:
            return {}

        current_start = report_date - timedelta(days=15)
        current_end = report_date - timedelta(days=RECOVERY_DELAY_BUFFER_DAYS["D7"])
        history_groups: dict[tuple[str, str, str, date], list[dict[str, Any]]] = defaultdict(list)
        current_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
        for raw in rows:
            day = _parse_date(str(raw.get("day") or ""))
            if not day:
                continue
            project = _project_key(str(raw.get("app") or ""))
            if project not in PROJECTS:
                continue
            store = _normalize_store(str(raw.get("store_type") or ""))
            channel = _normalize_channel(str(raw.get("network") or ""))
            if channel in {"Unknown", "All"}:
                continue
            cost = _to_float(raw.get("cost"))
            if cost <= 0:
                continue
            age = (report_date - day).days
            if age >= MATURE_AGE_DAYS:
                history_groups[(project, store, channel, day)].append(raw)
            if current_start <= day <= current_end:
                current_groups[(project, store, channel)].append(raw)

        history_summaries: dict[tuple[str, str, str], list[dict[str, float]]] = defaultdict(list)
        for (project, store, channel, _day), group_rows in history_groups.items():
            summary = _aggregate_recovery_rows(group_rows)
            if summary["cost"] > 0:
                history_summaries[(project, store, channel)].append(summary)

        result: dict[str, dict[str, SegmentTargets]] = defaultdict(dict)
        for key, history in history_summaries.items():
            project, store, channel = key
            current_rows = current_groups.get(key, [])
            current_summary = _aggregate_recovery_rows(current_rows) if current_rows else {"cost": 0.0}
            current_age = max(
                ((report_date - _parse_date(str(row.get("day") or "") or report_date.isoformat())).days for row in current_rows if _parse_date(str(row.get("day") or ""))),
                default=0,
            )
            profitable = [row for row in history if row.get("D120", 0.0) >= 1.0]
            recovery_targets: dict[str, RecoveryTarget] = {}
            for metric in RECOVERY_METRICS:
                values = [row.get(metric, 0.0) for row in profitable if row.get(metric, 0.0) > 0]
                recovery_targets[metric] = RecoveryTarget(
                    floor=_quantile(values, 0.25),
                    target=_quantile(values, 0.50),
                    strong=_quantile(values, 0.75),
                )
            data_status = "组合级"
            if len(profitable) < MIN_SEGMENT_PROFITABLE_SAMPLE:
                data_status = "组合样本不足"
            if not current_rows:
                data_status = f"{data_status}；当前D7待成熟"
            segment = SegmentTargets(
                project=project,
                store=store,
                channel=channel,
                current_recovery={metric: float(current_summary.get(metric, 0.0) or 0.0) for metric in CURRENT_METRICS},
                recovery_targets=recovery_targets,
                mature_samples=len(history),
                profitable_samples=len(profitable),
                current_sample_age_days=current_age,
                data_status=data_status,
            )
            result[project][segment.key] = segment
        return {project: dict(items) for project, items in result.items()}

    def _render_markdown(self, report_date: date, targets: list[ProjectTargets], self_check: dict[str, Any]) -> str:
        lines = [
            f"# Payback Target Report | {report_date.isoformat()}",
            "",
            "- 口径：只用 `newest_age >= 120` 的成熟周样本，定义 `D120 >= 1.0` 为历史可回本周。",
            "- 目标线定义：`保底线=P25`，`目标线=中位数`，`强势线=P75`。",
            "- 主指标优先看 Adjust cohort 回收；CPI/留存/ARPU 只作为辅助护栏，不替代回收判断。",
            "",
        ]
        for item in targets:
            lines.extend(self._render_project(item))
        lines.extend(["", "## Self Check", ""])
        lines.append(f"- Result: {'pass' if self_check['passed'] else 'fail'}")
        if self_check["issues"]:
            lines.extend(f"- Issue: {issue}" for issue in self_check["issues"])
        if self_check["warnings"]:
            lines.extend(f"- Warning: {warning}" for warning in self_check["warnings"])
        if not self_check["issues"] and not self_check["warnings"]:
            lines.append("- No issues.")
        lines.append("")
        return "\n".join(lines)

    def _render_project(self, item: ProjectTargets) -> list[str]:
        lines = [
            f"## {item.project}",
            "",
            f"- 成熟周样本 `{item.mature_weeks}`，其中可回本周 `{item.profitable_weeks}`。",
            f"- 当前若想在 D120 回本，D120/D7 需要做到 `{_fmt(item.current_required_multiplier)}`；历史可回本周中位数是 `{_fmt(item.profitable_median_multiplier)}`。",
            "",
            "| Metric | Current | Floor | Target | Strong |",
            "|---|---:|---:|---:|---:|",
        ]
        for metric in CURRENT_METRICS:
            target = item.recovery_targets[metric]
            lines.append(
                f"| {metric} | {_fmt(item.current_recovery.get(metric))} | {_fmt(target.floor)} | {_fmt(target.target)} | {_fmt(target.strong)} |"
            )
        for metric in ("D30", "D60", "D90", "D120"):
            target = item.recovery_targets[metric]
            lines.append(
                f"| {metric} milestone | - | {_fmt(target.floor)} | {_fmt(target.target)} | {_fmt(target.strong)} |"
            )

        lines.extend(["", "辅助护栏：", f"- CPI ceiling: {_guardrail_text(item.cpi_guardrail, item.current_cpi)}"])
        lines.append(f"- D1 retention floor: {_guardrail_text(item.retention_guardrail, item.current_retention_d1)}")
        lines.append(f"- ARPU floor: {_guardrail_text(item.arpu_guardrail, item.current_arpu)}")
        lines.append(f"- ARPPU floor: {_guardrail_text(item.arppu_guardrail, item.current_arppu)}")
        lines.extend(["", "商店+渠道回收门槛："])
        if item.segment_targets:
            lines.extend([
                "| 商店 | 渠道 | 样本 | Current D7 | D7 Floor | D30 Floor | 口径 |",
                "|---|---|---:|---:|---:|---:|---|",
            ])
            for segment in sorted(item.segment_targets.values(), key=lambda row: (row.store, row.channel)):
                sample_ready = segment.profitable_samples >= MIN_SEGMENT_PROFITABLE_SAMPLE
                d7_floor = segment.recovery_targets.get("D7").floor if sample_ready and segment.recovery_targets.get("D7") else None
                d30_floor = segment.recovery_targets.get("D30").floor if sample_ready and segment.recovery_targets.get("D30") else None
                lines.append(
                    f"| {segment.store} | {segment.channel} | {segment.profitable_samples}/{segment.mature_samples} | "
                    f"{_fmt(segment.current_recovery.get('D7'))} | {_fmt(d7_floor)} | {_fmt(d30_floor)} | {segment.data_status} |"
                )
        else:
            lines.append("- 暂无可用商店+渠道门槛，当前只能使用项目级参考线。")
        lines.append("")
        lines.extend(f"- {finding}" for finding in item.findings)
        lines.append("")
        return lines


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _resolve_payback_input_path(output_dir: Path, prefix: str, report_date: date) -> tuple[Path, date]:
    exact = output_dir / f"{prefix}_{report_date.strftime('%Y%m%d')}.csv"
    if exact.exists():
        return exact, report_date

    candidates: list[tuple[date, Path]] = []
    for path in output_dir.glob(f"{prefix}_*.csv"):
        match = re.search(r"_(\d{8})\.csv$", path.name)
        if not match:
            continue
        source_date = datetime.strptime(match.group(1), "%Y%m%d").date()
        if source_date <= report_date:
            candidates.append((source_date, path))
    if not candidates:
        raise FileNotFoundError(f"No payback input found for {prefix} on or before {report_date.isoformat()}")
    source_date, path = max(candidates, key=lambda item: item[0])
    return path, source_date


def _write_csv(path: Path, targets: list[ProjectTargets]) -> None:
    fields = [
        "project",
        "mature_weeks",
        "profitable_weeks",
        "current_D0",
        "current_D1",
        "current_D3",
        "current_D7",
        "floor_D0",
        "floor_D1",
        "floor_D3",
        "floor_D7",
        "floor_D30",
        "floor_D60",
        "floor_D90",
        "floor_D120",
        "current_required_D120_over_D7",
        "median_profitable_D120_over_D7",
        "current_cpi",
        "current_retention_d1",
        "current_arpu",
        "segment_gates",
        "cpi_confidence",
        "retention_confidence",
        "arpu_confidence",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in targets:
            writer.writerow(
                {
                    "project": item.project,
                    "mature_weeks": item.mature_weeks,
                    "profitable_weeks": item.profitable_weeks,
                    "current_D0": _fmt(item.current_recovery.get("D0")),
                    "current_D1": _fmt(item.current_recovery.get("D1")),
                    "current_D3": _fmt(item.current_recovery.get("D3")),
                    "current_D7": _fmt(item.current_recovery.get("D7")),
                    "floor_D0": _fmt(item.recovery_targets["D0"].floor),
                    "floor_D1": _fmt(item.recovery_targets["D1"].floor),
                    "floor_D3": _fmt(item.recovery_targets["D3"].floor),
                    "floor_D7": _fmt(item.recovery_targets["D7"].floor),
                    "floor_D30": _fmt(item.recovery_targets["D30"].floor),
                    "floor_D60": _fmt(item.recovery_targets["D60"].floor),
                    "floor_D90": _fmt(item.recovery_targets["D90"].floor),
                    "floor_D120": _fmt(item.recovery_targets["D120"].floor),
                    "current_required_D120_over_D7": _fmt(item.current_required_multiplier),
                    "median_profitable_D120_over_D7": _fmt(item.profitable_median_multiplier),
                    "current_cpi": _fmt(item.current_cpi),
                    "current_retention_d1": _fmt(item.current_retention_d1),
                    "current_arpu": _fmt(item.current_arpu),
                    "segment_gates": _segment_gate_summary(item.segment_targets),
                    "cpi_confidence": item.cpi_guardrail.confidence,
                    "retention_confidence": item.retention_guardrail.confidence,
                    "arpu_confidence": item.arpu_guardrail.confidence,
                }
            )


def _aggregate_weekly_ads(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, float]]:
    buckets: dict[tuple[str, str], dict[str, float]] = defaultdict(
        lambda: {"spend": 0.0, "cpi_num": 0.0, "roas_num": 0.0, "ret_num": 0.0, "ret_den": 0.0}
    )
    for row in rows:
        project = _project_key(row.get("game", ""))
        if project not in PROJECTS:
            continue
        day = _parse_date(row.get("date", ""))
        if not day:
            continue
        week_start = _week_start(day).isoformat()
        key = (project, week_start)
        spend = _to_float(row.get("spend"))
        cpi = _to_float(row.get("cpi"))
        roas = _to_float(row.get("roas"))
        retention_d1 = _to_float(row.get("retention_d1"))
        buckets[key]["spend"] += spend
        buckets[key]["cpi_num"] += spend * cpi
        buckets[key]["roas_num"] += spend * roas
        if retention_d1 > 0:
            buckets[key]["ret_num"] += spend * retention_d1
            buckets[key]["ret_den"] += spend
    result: dict[tuple[str, str], dict[str, float]] = {}
    for key, bucket in buckets.items():
        spend = bucket["spend"]
        result[key] = {
            "spend": spend,
            "cpi": (bucket["cpi_num"] / spend) if spend else 0.0,
            "ads_roas": (bucket["roas_num"] / spend) if spend else 0.0,
            "retention_d1": (bucket["ret_num"] / bucket["ret_den"]) if bucket["ret_den"] else 0.0,
        }
    return result


def _aggregate_weekly_revenue(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, float]]:
    buckets: dict[tuple[str, str], dict[str, list[float]]] = defaultdict(
        lambda: {"arpu": [], "arppu": [], "ltv": []}
    )
    for row in rows:
        project = _project_key(row.get("game", ""))
        if project not in PROJECTS:
            continue
        day = _parse_date(row.get("date", ""))
        if not day:
            continue
        week_start = _week_start(day).isoformat()
        key = (project, week_start)
        for field in ("arpu", "arppu", "ltv"):
            value = _to_float(row.get(field))
            if value > 0:
                buckets[key][field].append(value)
    result: dict[tuple[str, str], dict[str, float]] = {}
    for key, bucket in buckets.items():
        result[key] = {
            "arpu": statistics.median(bucket["arpu"]) if bucket["arpu"] else 0.0,
            "arppu": statistics.median(bucket["arppu"]) if bucket["arppu"] else 0.0,
            "ltv": statistics.median(bucket["ltv"]) if bucket["ltv"] else 0.0,
        }
    return result


def _detect_ads_confidence(report_date: date, rows: list[dict[str, str]]) -> dict[str, str]:
    current_week_start = (report_date - timedelta(days=6)).isoformat()
    daily_signatures: dict[str, list[tuple[str, float, float, float]]] = defaultdict(list)
    for row in rows:
        project = _project_key(row.get("game", ""))
        if project not in PROJECTS:
            continue
        day = row.get("date", "")
        if not day:
            continue
        if _week_start(_parse_date(day)).isoformat() != current_week_start:
            continue
        daily_signatures[project].append(
            (
                day,
                round(_to_float(row.get("spend")), 4),
                round(_to_float(row.get("cpi")), 4),
                round(_to_float(row.get("retention_d1")), 4),
            )
        )
    result = {project: "medium" for project in PROJECTS}
    for left in PROJECTS:
        for right in PROJECTS:
            if left >= right:
                continue
            if daily_signatures[left] and daily_signatures[left] == daily_signatures[right]:
                result[left] = "low"
                result[right] = "low"
    return result


def _join_profitable_secondary(
    project: str,
    profitable_rows: list[dict[str, str]],
    weekly_ads: dict[tuple[str, str], dict[str, float]],
    weekly_revenue: dict[tuple[str, str], dict[str, float]],
) -> list[dict[str, float | None]]:
    joined: list[dict[str, float | None]] = []
    for row in profitable_rows:
        key = (project, row["week_start"])
        ads = weekly_ads.get(key)
        revenue = weekly_revenue.get(key)
        if not ads:
            continue
        joined.append(
            {
                "cpi": ads.get("cpi") or None,
                "ads_roas": ads.get("ads_roas") or None,
                "retention_d1": ads.get("retention_d1") or None,
                "arpu": revenue.get("arpu") if revenue else None,
                "arppu": revenue.get("arppu") if revenue else None,
            }
        )
    return joined


def _aggregate_recovery_rows(rows: list[dict[str, Any]]) -> dict[str, float]:
    totals = {"cost": 0.0, "D0": 0.0, "D1": 0.0, "D3": 0.0, "D7": 0.0, "D30": 0.0, "D60": 0.0, "D90": 0.0, "D120": 0.0}
    for row in rows:
        cost = _to_float(row.get("cost"))
        if cost <= 0:
            continue
        totals["cost"] += cost
        totals["D0"] += cost * _to_float(row.get("roas_d0"))
        totals["D1"] += cost * (_to_float(row.get("roas_d1")) or _to_float(row.get("roas_d0")))
        totals["D3"] += cost * _to_float(row.get("roas_d2") or row.get("roas_d3"))
        totals["D7"] += cost * _to_float(row.get("roas_d6") or row.get("roas_d7"))
        totals["D30"] += cost * _to_float(row.get("roas_d29"))
        totals["D60"] += cost * _to_float(row.get("roas_d59"))
        totals["D90"] += cost * _to_float(row.get("roas_d89"))
        totals["D120"] += cost * _to_float(row.get("roas_d119") or row.get("roas_d120"))
    cost = totals["cost"]
    if cost <= 0:
        return totals
    return {key: (value / cost if key != "cost" else value) for key, value in totals.items()}


def _segment_key(store: str, channel: str) -> str:
    return f"{_normalize_store(store)} / {_normalize_channel(channel)}"


def _normalize_store(value: str) -> str:
    normalized = (value or "").strip().lower()
    mapping = {
        "app_store": "iOS",
        "ios": "iOS",
        "google_play": "Android",
        "android": "Android",
        "amazon": "Amazon",
    }
    return mapping.get(normalized, value or "未知商店")


def _normalize_channel(value: str) -> str:
    normalized = (value or "").strip().lower()
    if "google" in normalized:
        return "Google"
    if "facebook" in normalized or "instagram" in normalized or "meta" in normalized or "off-facebook" in normalized:
        return "Facebook"
    if "apple" in normalized or "asa" in normalized:
        return "Apple Search"
    if "applovin" in normalized:
        return "Applovin"
    if "unity" in normalized:
        return "Unity Ads"
    if "tiktok" in normalized or "bytedance" in normalized:
        return "TikTok"
    return value or "Unknown"


def _segment_gate_summary(segments: dict[str, SegmentTargets]) -> str:
    parts: list[str] = []
    for segment in sorted(segments.values(), key=lambda row: (row.store, row.channel)):
        sample_ready = segment.profitable_samples >= MIN_SEGMENT_PROFITABLE_SAMPLE
        d7_floor = segment.recovery_targets.get("D7").floor if sample_ready and segment.recovery_targets.get("D7") else None
        d30_floor = segment.recovery_targets.get("D30").floor if sample_ready and segment.recovery_targets.get("D30") else None
        parts.append(
            f"{segment.key}:D7={_fmt(d7_floor)},D30={_fmt(d30_floor)},sample={segment.profitable_samples}/{segment.mature_samples},status={segment.data_status}"
        )
    return "; ".join(parts)


def _build_cpi_guardrail(values: list[float], confidence: str) -> SecondaryGuardrail:
    if len(values) < MIN_SECONDARY_SAMPLE:
        return SecondaryGuardrail(
            label="CPI",
            direction="max",
            sample_count=len(values),
            confidence="low",
            note="历史可回本周样本太少，暂不设硬性 CPI 线",
        )
    return SecondaryGuardrail(
        label="CPI",
        direction="max",
        ceiling=_quantile(values, 0.75),
        target=_quantile(values, 0.50),
        sample_count=len(values),
        confidence=confidence,
        note="P75 作为风险上限，超过后多数样本开始难回本",
    )


def _build_retention_guardrail(values: list[float], confidence: str) -> SecondaryGuardrail:
    if len(values) < MIN_SECONDARY_SAMPLE:
        return SecondaryGuardrail(
            label="D1 retention",
            direction="min",
            sample_count=len(values),
            confidence="low",
            note="历史可回本周样本太少，暂不设硬性 D1 留存线",
        )
    return SecondaryGuardrail(
        label="D1 retention",
        direction="min",
        floor=_quantile(values, 0.25),
        target=_quantile(values, 0.50),
        sample_count=len(values),
        confidence=confidence,
        note="P25 作为保底线，低于它时回收一般会变弱",
    )


def _blocked_guardrail(label: str, direction: str, note: str) -> SecondaryGuardrail:
    return SecondaryGuardrail(
        label=label,
        direction=direction,
        sample_count=0,
        confidence="blocked",
        note=note,
    )


def _build_floor_guardrail(label: str, values: list[float], default_confidence: str, note: str) -> SecondaryGuardrail:
    if len(values) < MIN_SECONDARY_SAMPLE:
        return SecondaryGuardrail(
            label=label,
            direction="min",
            sample_count=len(values),
            confidence="low",
            note=f"{note}；历史可回本周样本太少，暂不设硬线",
        )
    return SecondaryGuardrail(
        label=label,
        direction="min",
        floor=_quantile(values, 0.25),
        target=_quantile(values, 0.50),
        sample_count=len(values),
        confidence=default_confidence,
        note=note,
    )


def _build_findings(
    project: str,
    current_recovery: dict[str, float],
    recovery_targets: dict[str, RecoveryTarget],
    current_required_multiplier: float | None,
    profitable_median_multiplier: float | None,
    current_cpi: float | None,
    current_retention_d1: float | None,
    current_arpu: float | None,
    cpi_guardrail: SecondaryGuardrail,
    retention_guardrail: SecondaryGuardrail,
    arpu_guardrail: SecondaryGuardrail,
    ads_trusted: bool,
) -> list[str]:
    findings: list[str] = []
    d7_floor = recovery_targets["D7"].floor
    d7_target = recovery_targets["D7"].target
    if d7_floor and current_recovery["D7"] < d7_floor:
        findings.append(
            f"D7 实际回收 `{_fmt(current_recovery['D7'])}` 低于历史可回本保底线 `{_fmt(d7_floor)}`，当前批次先天偏弱。"
        )
    elif d7_target and current_recovery["D7"] < d7_target:
        findings.append(
            f"D7 实际回收 `{_fmt(current_recovery['D7'])}` 只到保底线附近，还没到历史可回本中位线 `{_fmt(d7_target)}`。"
        )
    else:
        findings.append(
            f"D7 实际回收 `{_fmt(current_recovery['D7'])}` 已达到历史可回本目标带，可继续看后续放量质量。"
        )

    if current_required_multiplier and profitable_median_multiplier:
        if current_required_multiplier > profitable_median_multiplier * 1.2:
            findings.append(
                f"按当前 D7，要在 D120 回本需要后续长尾做到 `{_fmt(current_required_multiplier)}` 倍；这高于历史可回本中位数 `{_fmt(profitable_median_multiplier)}`，要求偏苛刻。"
            )
        else:
            findings.append(
                f"按当前 D7，要在 D120 回本需要后续长尾做到 `{_fmt(current_required_multiplier)}` 倍；仍在历史可回本样本区间内。"
            )

    if cpi_guardrail.ceiling and current_cpi:
        if current_cpi > cpi_guardrail.ceiling:
            findings.append(
                f"CPI `{_fmt(current_cpi)}` 高于历史可回本周的风险上限 `{_fmt(cpi_guardrail.ceiling)}`，成本端有压力。"
            )
        elif cpi_guardrail.confidence != "low":
            findings.append(
                f"CPI `{_fmt(current_cpi)}` 还在历史可回本周范围内，成本不是第一矛盾。"
            )
    if retention_guardrail.floor and current_retention_d1:
        if current_retention_d1 < retention_guardrail.floor:
            findings.append(
                f"D1 留存 `{_fmt(current_retention_d1)}` 低于保底线 `{_fmt(retention_guardrail.floor)}`，需要关注首日流量质量和产品承接。"
            )
    if arpu_guardrail.floor and current_arpu:
        if current_arpu < arpu_guardrail.floor:
            findings.append(
                f"项目整体 ARPU `{_fmt(current_arpu)}` 低于历史可回本保底线 `{_fmt(arpu_guardrail.floor)}`，变现质量在走弱。"
            )
    if not ads_trusted:
        findings.append("当前缺少可信项目级投放明细，CPI 和 D1 留存先不作为硬门槛。")

    if project == "P04":
        findings.append("P04 这类慢回本项目，核心不是只看 D0，而是 D7 必须先回到 0.32 以上，否则后面长尾通常补不回来。")
    elif project == "P02":
        findings.append("P02 的关键是 D7 至少站上 0.35，且 D30 要尽快接近 0.70；否则很容易卡在接近回本但过不了线。")
    elif project == "P07":
        findings.append("P07 项目级回收 historically 可以很强，但纯付费渠道目前仍亏，不能只因为项目总回收高就直接加量。")
    return findings


def _guardrail_text(guardrail: SecondaryGuardrail, current_value: float | None) -> str:
    if guardrail.confidence == "blocked":
        return f"blocked | sample={guardrail.sample_count} | {guardrail.note}"
    if guardrail.direction == "max":
        if guardrail.ceiling is None:
            return f"insufficient | sample={guardrail.sample_count} | {guardrail.note}"
        return (
            f"current={_fmt(current_value)} | ceiling={_fmt(guardrail.ceiling)} | "
            f"target={_fmt(guardrail.target)} | confidence={guardrail.confidence} | {guardrail.note}"
        )
    if guardrail.floor is None:
        return f"insufficient | sample={guardrail.sample_count} | {guardrail.note}"
    return (
        f"current={_fmt(current_value)} | floor={_fmt(guardrail.floor)} | "
        f"target={_fmt(guardrail.target)} | confidence={guardrail.confidence} | {guardrail.note}"
    )


def _project_key(value: str) -> str:
    match = re.search(r"\bP0*([0-9]+)\b", (value or "").upper())
    return f"P{int(match.group(1)):02d}" if match else (value or "")


def _parse_date(value: str) -> date | None:
    text = (value or "").strip()
    if not text:
        return None
    return datetime.strptime(text, "%Y-%m-%d").date()


def _week_start(value: date) -> date:
    return value - timedelta(days=(value.weekday() - 3) % 7)


def _quantile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * quantile
    left = int(position)
    right = min(left + 1, len(ordered) - 1)
    fraction = position - left
    return ordered[left] * (1 - fraction) + ordered[right] * fraction


def _to_float(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    if isinstance(value, list):
        value = value[0] if value else 0
    return float(str(value).replace(",", "").strip())


def _fmt(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.2f}"
