from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.google_creative_resolver import GoogleCreativeResolver
from market_ops.models import RevenueBreakdownRow
from market_ops.pipeline import DataRepository


GENERIC_GOOGLE_PREFIXES = (
    "display",
    "search",
    "youtube",
    "video",
    "image",
)


@dataclass(slots=True)
class GoogleCreativeRepairRow:
    project: str
    store: str
    channel: str
    campaign_id: str
    campaign: str
    adgroup_id: str
    adgroup: str
    source_id: str
    source_name: str
    creative_id: str
    creative_name: str
    status: str
    paid_rows: int
    cost: float
    gross_revenue: float
    gross_roi: float
    countries: str
    recommendation: str


class GoogleCreativeRepairAuditBuilder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._repo = DataRepository(settings)
        self._google_resolver = GoogleCreativeResolver(self._repo.load_creative_library())

    def build(self, report_date: date) -> dict[str, Path]:
        report_date = _align_to_wednesday(report_date)
        window_start = report_date - timedelta(days=6)
        rows = self._repo.load_adjust_revenue_breakdown(window_start, report_date)
        google_rows = [row for row in rows if row.cost > 0 and _is_google(row)]

        output_dir = self._settings.output_dir
        active_output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        active_output_dir.mkdir(parents=True, exist_ok=True)

        suffix = report_date.strftime("%Y%m%d")
        summary_path = active_output_dir / f"google_creative_repair_audit_{suffix}.md"
        json_path = active_output_dir / f"google_creative_repair_audit_{suffix}.json"
        csv_path = output_dir / f"google_creative_repair_segments_{suffix}.csv"

        segments = self._aggregate_segments(google_rows)
        payload = self._build_payload(window_start, report_date, google_rows, segments)

        self._write_csv(csv_path, segments)
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        summary_path.write_text(self._render_markdown(payload), encoding="utf-8")
        return {"summary": summary_path, "json": json_path, "segments": csv_path}

    def _aggregate_segments(self, google_rows: list[RevenueBreakdownRow]) -> list[GoogleCreativeRepairRow]:
        grouped: dict[tuple[str, str, str, str, str, str, str, str, str, str, str], dict[str, Any]] = {}
        for row in google_rows:
            resolved = self._google_resolver.resolve(row)
            resolved_creative_id = str((resolved.asset_id if resolved else "") or (resolved.identity_id if resolved else "") or row.creative_id or "").strip()
            resolved_creative_name = str((resolved.creative_name if resolved else "") or (resolved.identity_name if resolved else "") or row.creative_name or row.creative_id or "").strip()
            resolution_quality = str(resolved.resolution_quality if resolved else "").strip()
            key = (
                row.game,
                row.store,
                row.partner,
                row.campaign_id,
                row.campaign,
                row.adgroup_id,
                row.adgroup,
                row.source_id,
                row.source_name,
                resolved_creative_id,
                resolved_creative_name,
            )
            bucket = grouped.setdefault(
                key,
                {
                    "game": row.game,
                    "store": row.store,
                    "partner": row.partner,
                    "campaign_id": row.campaign_id,
                    "campaign": row.campaign,
                    "adgroup_id": row.adgroup_id,
                    "adgroup": row.adgroup,
                    "source_id": row.source_id,
                    "source_name": row.source_name,
                    "creative_id": resolved_creative_id,
                    "creative_name": resolved_creative_name,
                    "resolution_quality": resolution_quality,
                    "paid_rows": 0,
                    "cost": 0.0,
                    "gross_revenue": 0.0,
                    "countries": set(),
                },
            )
            bucket["paid_rows"] += 1
            bucket["cost"] += row.cost
            bucket["gross_revenue"] += row.total_revenue_gross
            if row.country:
                bucket["countries"].add(row.country)

        items: list[GoogleCreativeRepairRow] = []
        for item in sorted(grouped.values(), key=lambda row: row["cost"], reverse=True):
            creative_value = str(item["creative_id"] or item["creative_name"] or "").strip()
            resolution_quality = str(item.get("resolution_quality") or "").strip()
            status = "placeholder" if not resolution_quality or _is_generic_google_creative(creative_value) else resolution_quality
            recommendation = (
                "用 source_id / adgroup_id 补 Google 素材标识映射，恢复到素材 ID 层"
                if status == "placeholder"
                else "当前已可直接作为素材级标识"
            )
            items.append(
                GoogleCreativeRepairRow(
                    project=_project_key(item["game"]),
                    store=_normalize_store(item["store"]),
                    channel="Google",
                    campaign_id=str(item["campaign_id"] or "").strip(),
                    campaign=str(item["campaign"] or "").strip(),
                    adgroup_id=str(item["adgroup_id"] or "").strip(),
                    adgroup=str(item["adgroup"] or "").strip(),
                    source_id=str(item["source_id"] or "").strip(),
                    source_name=str(item["source_name"] or "").strip(),
                    creative_id=str(item["creative_id"] or "").strip(),
                    creative_name=str(item["creative_name"] or "").strip(),
                    status=status,
                    paid_rows=int(item["paid_rows"]),
                    cost=float(item["cost"]),
                    gross_revenue=float(item["gross_revenue"]),
                    gross_roi=(float(item["gross_revenue"]) / float(item["cost"])) if item["cost"] else 0.0,
                    countries=", ".join(sorted(item["countries"])[:8]),
                    recommendation=recommendation,
                )
            )
        return items

    def _build_payload(
        self,
        window_start: date,
        report_date: date,
        google_rows: list[RevenueBreakdownRow],
        segments: list[GoogleCreativeRepairRow],
    ) -> dict[str, Any]:
        total_cost = sum(row.cost for row in google_rows)
        placeholder_segments = [row for row in segments if row.status == "placeholder"]
        resolved_segments = [row for row in segments if row.status != "placeholder"]
        placeholder_cost = sum(row.cost for row in placeholder_segments)
        resolved_cost = sum(row.cost for row in resolved_segments)
        return {
            "report_date": report_date.isoformat(),
            "window_label": f"{window_start.isoformat()} ~ {report_date.isoformat()}",
            "paid_rows": len(google_rows),
            "paid_cost": round(total_cost, 2),
            "resolver_ready": True,
            "live_google_source_ready": False,
            "placeholder_segment_count": len(placeholder_segments),
            "placeholder_cost": round(placeholder_cost, 2),
            "placeholder_cost_share": round((placeholder_cost / total_cost) if total_cost else 0.0, 4),
            "resolved_segment_count": len(resolved_segments),
            "resolved_cost": round(resolved_cost, 2),
            "resolved_cost_share": round((resolved_cost / total_cost) if total_cost else 0.0, 4),
            "top_placeholder_segments": [asdict(row) for row in placeholder_segments[:20]],
            "top_resolved_segments": [asdict(row) for row in resolved_segments[:20]],
            "summary": [
                f"本周 Google 付费花费：{total_cost:.2f}",
                f"占位素材花费占比：{(placeholder_cost / total_cost):.1%}" if total_cost else "占位素材花费占比：0.0%",
                "当前优先使用 TecDo/API 素材身份映射回补 Adjust 占位值。",
                "当前最可用的修复键是 source_id + adgroup_id + campaign_id。",
            ],
        }

    def _render_markdown(self, payload: dict[str, Any]) -> str:
        lines = [
            f"# Google 素材修复审计 | {payload['report_date']}",
            "",
            f"- 周窗口：{payload['window_label']}",
            f"- Google 付费明细行数：{payload['paid_rows']}",
            f"- Google 总花费：{payload['paid_cost']:.2f}",
            f"- Google 素材修复链路：{'已接入' if payload.get('resolver_ready') else '未接入'}",
            f"- Google 官方素材接口：{'可用' if payload.get('live_google_source_ready') else '不可用'}",
            f"- 占位素材段数：{payload['placeholder_segment_count']}",
            f"- 占位素材花费：{payload['placeholder_cost']:.2f} ({payload['placeholder_cost_share']:.1%})",
            f"- 已识别素材花费：{payload['resolved_cost']:.2f} ({payload['resolved_cost_share']:.1%})",
            "",
            "## 结论",
            "",
        ]
        for item in payload.get("summary") or []:
            lines.append(f"- {item}")

        lines.extend(
            [
                "",
                "## 占位素材重点段",
                "",
                "| Project | Campaign ID | Adgroup ID | Source ID | Creative | Spend | Gross ROI | Recommendation |",
                "|---|---|---|---|---|---:|---:|---|",
            ]
        )
        for row in payload.get("top_placeholder_segments") or []:
            lines.append(
                f"| {row['project']} | {row['campaign_id'] or '-'} | {row['adgroup_id'] or '-'} | {row['source_id'] or '-'} | "
                f"{row['creative_id'] or row['creative_name'] or '-'} | {row['cost']:.2f} | {row['gross_roi']:.2f} | {row['recommendation']} |"
            )

        lines.extend(
            [
                "",
                "## 已识别素材重点段",
                "",
                "| Project | Campaign ID | Adgroup ID | Source ID | Creative | Spend | Gross ROI | Countries |",
                "|---|---|---|---|---|---:|---:|---|",
            ]
        )
        rows = payload.get("top_resolved_segments") or []
        if not rows:
            lines.append("| - | - | - | - | - | 0 | 0 | - |")
        for row in rows:
            lines.append(
                f"| {row['project']} | {row['campaign_id'] or '-'} | {row['adgroup_id'] or '-'} | {row['source_id'] or '-'} | "
                f"{row['creative_id'] or row['creative_name'] or '-'} | {row['cost']:.2f} | {row['gross_roi']:.2f} | {row['countries'] or '-'} |"
            )
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _write_csv(path: Path, rows: list[GoogleCreativeRepairRow]) -> None:
        fieldnames = [
            "project",
            "store",
            "channel",
            "campaign_id",
            "campaign",
            "adgroup_id",
            "adgroup",
            "source_id",
            "source_name",
            "creative_id",
            "creative_name",
            "status",
            "paid_rows",
            "cost",
            "gross_revenue",
            "gross_roi",
            "countries",
            "recommendation",
        ]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(asdict(row))


def _align_to_wednesday(value: date) -> date:
    return value - timedelta(days=(value.weekday() - 2) % 7)


def _is_google(row: RevenueBreakdownRow) -> bool:
    return "google" in str(row.partner or "").lower()


def _is_generic_google_creative(value: str) -> bool:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return True
    return normalized.startswith(GENERIC_GOOGLE_PREFIXES)


def _project_key(name: str) -> str:
    upper = str(name or "").upper()
    if "P02" in upper:
        return "P02"
    if "P04" in upper:
        return "P04"
    if "P07" in upper:
        return "P07"
    return str(name or "").strip()


def _normalize_store(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized == "google_play":
        return "Android"
    if normalized == "app_store":
        return "iOS"
    return str(value or "").strip() or "unknown"
