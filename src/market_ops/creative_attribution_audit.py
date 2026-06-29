from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.google_creative_resolver import GoogleCreativeResolver
from market_ops.models import RevenueBreakdownRow
from market_ops.pipeline import DataRepository


GENERIC_CREATIVE_VALUES = {
    "",
    "-",
    "ad",
    "all",
    "app",
    "asset",
    "banner",
    "creative",
    "display",
    "image",
    "search",
    "unknown",
    "video",
}


@dataclass(slots=True)
class CoverageMetric:
    field_name: str
    paid_rows: int
    paid_cost: float
    filled_rows: int
    filled_cost: float

    @property
    def row_coverage_pct(self) -> float:
        return self.filled_rows / self.paid_rows if self.paid_rows else 0.0

    @property
    def cost_coverage_pct(self) -> float:
        return self.filled_cost / self.paid_cost if self.paid_cost else 0.0


@dataclass(slots=True)
class ChannelCoverage:
    project: str
    store: str
    channel: str
    paid_rows: int
    paid_cost: float
    campaign_coverage_pct: float
    campaign_id_coverage_pct: float
    adgroup_coverage_pct: float
    adgroup_id_coverage_pct: float
    creative_name_coverage_pct: float
    creative_id_coverage_pct: float
    creative_resolved_coverage_pct: float
    source_name_coverage_pct: float
    source_id_coverage_pct: float
    distinct_campaigns: int
    distinct_adgroups: int
    distinct_creatives: int
    distinct_sources: int
    note: str


@dataclass(slots=True)
class TopEntity:
    level: str
    project: str
    store: str
    channel: str
    entity_id: str
    entity_name: str
    paid_rows: int
    cost: float
    gross_revenue: float
    gross_roi: float
    sample_countries: str


class CreativeAttributionAuditBuilder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._repo = DataRepository(settings)
        self._google_resolver = GoogleCreativeResolver(self._repo.load_creative_library())

    def build(self, report_date: date) -> dict[str, Path]:
        report_date = _align_to_wednesday(report_date)
        window_start = report_date - timedelta(days=6)
        rows = self._repo.load_adjust_revenue_breakdown(window_start, report_date)
        paid_rows = [row for row in rows if row.cost > 0]

        output_dir = self._settings.output_dir
        active_output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        active_output_dir.mkdir(parents=True, exist_ok=True)

        suffix = report_date.strftime("%Y%m%d")
        summary_path = active_output_dir / f"creative_attribution_audit_{suffix}.md"
        json_path = active_output_dir / f"creative_attribution_audit_{suffix}.json"
        coverage_path = output_dir / f"creative_attribution_coverage_{suffix}.csv"
        top_entities_path = output_dir / f"creative_attribution_top_entities_{suffix}.csv"

        overall_metrics = self._build_overall_metrics(paid_rows)
        channel_coverage = self._build_channel_coverage(paid_rows)
        top_entities = self._build_top_entities(rows)
        samples = self._build_samples(paid_rows)
        readiness = self._build_readiness(channel_coverage)
        payload = self._build_payload(
            window_start=window_start,
            report_date=report_date,
            raw_rows=len(rows),
            paid_rows=paid_rows,
            overall_metrics=overall_metrics,
            channel_coverage=channel_coverage,
            top_entities=top_entities,
            samples=samples,
            readiness=readiness,
        )

        self._write_coverage_csv(coverage_path, channel_coverage)
        self._write_top_entities_csv(top_entities_path, top_entities)
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        summary_path.write_text(self._render_markdown(payload), encoding="utf-8")
        return {
            "summary": summary_path,
            "json": json_path,
            "coverage": coverage_path,
            "top_entities": top_entities_path,
        }

    def _build_overall_metrics(self, paid_rows: list[RevenueBreakdownRow]) -> list[CoverageMetric]:
        return [
            self._coverage_metric(paid_rows, "campaign", lambda row: row.campaign),
            self._coverage_metric(paid_rows, "campaign_id", lambda row: row.campaign_id),
            self._coverage_metric(paid_rows, "adgroup", lambda row: row.adgroup),
            self._coverage_metric(paid_rows, "adgroup_id", lambda row: row.adgroup_id),
            self._coverage_metric(paid_rows, "creative_name", lambda row: row.creative_name),
            self._coverage_metric(paid_rows, "creative_id", lambda row: row.creative_id),
            self._coverage_metric(
                paid_rows,
                "creative_resolved",
                lambda row: self._resolved_creative_identity(row) is not None,
            ),
            self._coverage_metric(paid_rows, "source_name", lambda row: row.source_name),
            self._coverage_metric(paid_rows, "source_id", lambda row: row.source_id),
        ]

    def _coverage_metric(
        self,
        paid_rows: list[RevenueBreakdownRow],
        field_name: str,
        extractor,
    ) -> CoverageMetric:
        paid_cost = sum(row.cost for row in paid_rows)
        filled_rows = 0
        filled_cost = 0.0
        for row in paid_rows:
            value = extractor(row)
            if isinstance(value, bool):
                filled = value
            else:
                filled = bool(str(value or "").strip())
            if filled:
                filled_rows += 1
                filled_cost += row.cost
        return CoverageMetric(
            field_name=field_name,
            paid_rows=len(paid_rows),
            paid_cost=paid_cost,
            filled_rows=filled_rows,
            filled_cost=filled_cost,
        )

    def _build_channel_coverage(self, paid_rows: list[RevenueBreakdownRow]) -> list[ChannelCoverage]:
        grouped: dict[tuple[str, str, str], list[RevenueBreakdownRow]] = defaultdict(list)
        for row in paid_rows:
            key = (_project_key(row.game), _normalize_store(row.store), _normalize_channel(row.partner))
            grouped[key].append(row)

        items: list[ChannelCoverage] = []
        for (project, store, channel), rows in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1], item[0][2])):
            paid_cost = sum(row.cost for row in rows)
            if paid_cost <= 0:
                continue
            campaign_ids = {str(row.campaign_id).strip() for row in rows if str(row.campaign_id).strip()}
            adgroup_ids = {str(row.adgroup_id).strip() for row in rows if str(row.adgroup_id).strip()}
            creative_keys = {
                self._resolved_entity_key(row)
                for row in rows
                if self._resolved_entity_key(row)
            }
            source_ids = {str(row.source_id).strip() for row in rows if str(row.source_id).strip()}
            creative_resolved_rows = sum(
                1 for row in rows if self._resolved_creative_identity(row) is not None
            )
            note = self._coverage_note(channel=channel, rows=rows, creative_resolved_rows=creative_resolved_rows)
            items.append(
                ChannelCoverage(
                    project=project,
                    store=store,
                    channel=channel,
                    paid_rows=len(rows),
                    paid_cost=paid_cost,
                    campaign_coverage_pct=_ratio(sum(1 for row in rows if str(row.campaign).strip()), len(rows)),
                    campaign_id_coverage_pct=_ratio(sum(1 for row in rows if str(row.campaign_id).strip()), len(rows)),
                    adgroup_coverage_pct=_ratio(sum(1 for row in rows if str(row.adgroup).strip()), len(rows)),
                    adgroup_id_coverage_pct=_ratio(sum(1 for row in rows if str(row.adgroup_id).strip()), len(rows)),
                    creative_name_coverage_pct=_ratio(sum(1 for row in rows if str(row.creative_name).strip()), len(rows)),
                    creative_id_coverage_pct=_ratio(sum(1 for row in rows if str(row.creative_id).strip()), len(rows)),
                    creative_resolved_coverage_pct=_ratio(creative_resolved_rows, len(rows)),
                    source_name_coverage_pct=_ratio(sum(1 for row in rows if str(row.source_name).strip()), len(rows)),
                    source_id_coverage_pct=_ratio(sum(1 for row in rows if str(row.source_id).strip()), len(rows)),
                    distinct_campaigns=len(campaign_ids),
                    distinct_adgroups=len(adgroup_ids),
                    distinct_creatives=len(creative_keys),
                    distinct_sources=len(source_ids),
                    note=note,
                )
            )
        return sorted(items, key=lambda item: (item.project, -item.paid_cost, item.store, item.channel))

    def _coverage_note(
        self,
        channel: str,
        rows: list[RevenueBreakdownRow],
        creative_resolved_rows: int,
    ) -> str:
        if not rows:
            return "当前没有付费样本"
        if creative_resolved_rows == len(rows):
            if channel == "Google":
                return "Google 已可按解析后素材身份进入创意分析"
            return "创意 ID 当前可直接用于分析"
        if creative_resolved_rows == 0:
            generic_ids = {
                str(row.creative_id or row.creative_name or "").strip()
                for row in rows
                if str(row.creative_id or row.creative_name or "").strip()
            }
            generic_text = ", ".join(sorted(list(generic_ids))[:3]) or "none"
            return f"创意字段当前是占位值（{generic_text}）"
        if channel == "Google":
            return "Google 创意字段仍有部分是通用占位值，需补素材标识映射"
        return "创意字段仍不完整，先不要直接下创意级动作"

    def _build_top_entities(self, rows: list[RevenueBreakdownRow]) -> list[TopEntity]:
        entities: list[TopEntity] = []
        entities.extend(self._aggregate_entities(rows, "campaign", "campaign_id", "campaign", limit=30))
        entities.extend(self._aggregate_entities(rows, "adgroup", "adgroup_id", "adgroup", limit=30))
        entities.extend(
            self._aggregate_entities(
                rows,
                "creative",
                "creative_id",
                "creative_name",
                limit=40,
            )
        )
        return entities

    def _aggregate_entities(
        self,
        rows: list[RevenueBreakdownRow],
        level: str,
        id_field: str,
        name_field: str,
        limit: int,
    ) -> list[TopEntity]:
        grouped: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
        for row in rows:
            if level == "creative":
                resolved = self._resolved_creative_identity(row)
                if resolved is None:
                    continue
                entity_id = resolved["entity_id"]
                entity_name = resolved["entity_name"]
            else:
                entity_id = str(getattr(row, id_field) or "").strip()
                entity_name = str(getattr(row, name_field) or "").strip()
            if level != "creative" and not (entity_id or entity_name):
                continue
            key = (
                _project_key(row.game),
                _normalize_store(row.store),
                _normalize_channel(row.partner),
                entity_id,
                entity_name,
            )
            bucket = grouped.setdefault(
                key,
                {
                    "project": _project_key(row.game),
                    "store": _normalize_store(row.store),
                    "channel": _normalize_channel(row.partner),
                    "entity_id": entity_id,
                    "entity_name": entity_name,
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

        top_rows = sorted(
            [item for item in grouped.values() if item["cost"] > 0],
            key=lambda item: item["cost"],
            reverse=True,
        )[:limit]
        return [
            TopEntity(
                level=level,
                project=item["project"],
                store=item["store"],
                channel=item["channel"],
                entity_id=item["entity_id"],
                entity_name=item["entity_name"],
                paid_rows=item["paid_rows"],
                cost=item["cost"],
                gross_revenue=item["gross_revenue"],
                gross_roi=item["gross_revenue"] / item["cost"] if item["cost"] else 0.0,
                sample_countries=", ".join(sorted(item["countries"])[:5]),
            )
            for item in top_rows
        ]

    def _build_samples(self, paid_rows: list[RevenueBreakdownRow]) -> dict[str, list[dict[str, str]]]:
        samples: dict[str, list[dict[str, str]]] = {}
        for channel in ("Facebook", "Google"):
            rows = [row for row in paid_rows if _normalize_channel(row.partner) == channel]
            channel_samples: list[dict[str, str]] = []
            for row in rows:
                resolved = self._resolved_creative_identity(row) or {}
                channel_samples.append(
                    {
                        "project": _project_key(row.game),
                        "store": _normalize_store(row.store),
                        "channel": channel,
                        "country": row.country,
                        "campaign_id": row.campaign_id,
                        "campaign": row.campaign,
                        "adgroup_id": row.adgroup_id,
                        "adgroup": row.adgroup,
                        "creative_id": row.creative_id,
                        "creative_name": row.creative_name,
                        "resolved_creative_id": resolved.get("entity_id", ""),
                        "resolved_creative_name": resolved.get("entity_name", ""),
                        "source_id": row.source_id,
                        "source_name": row.source_name,
                    }
                )
                if len(channel_samples) >= 5:
                    break
            samples[channel] = channel_samples
        return samples

    def _build_readiness(self, channel_coverage: list[ChannelCoverage]) -> dict[str, Any]:
        campaign_ready = all(item.campaign_id_coverage_pct >= 0.95 for item in channel_coverage) if channel_coverage else False
        adgroup_ready = all(item.adgroup_id_coverage_pct >= 0.95 for item in channel_coverage) if channel_coverage else False
        creative_ready_channels = [
            {
                "project": item.project,
                "store": item.store,
                "channel": item.channel,
                "creative_resolved_coverage_pct": round(item.creative_resolved_coverage_pct, 4),
                "note": item.note,
                "ready": item.creative_resolved_coverage_pct >= 0.8,
            }
            for item in channel_coverage
        ]
        creative_ready = all(entry["ready"] for entry in creative_ready_channels) if creative_ready_channels else False
        return {
            "campaign_analysis_ready": campaign_ready,
            "adgroup_analysis_ready": adgroup_ready,
            "creative_analysis_ready": creative_ready,
            "google_creative_status": (
                "partial"
                if any(entry["channel"] == "Google" and not entry["ready"] for entry in creative_ready_channels)
                else "ready"
            ),
            "channel_details": creative_ready_channels,
        }

    def _build_payload(
        self,
        window_start: date,
        report_date: date,
        raw_rows: int,
        paid_rows: list[RevenueBreakdownRow],
        overall_metrics: list[CoverageMetric],
        channel_coverage: list[ChannelCoverage],
        top_entities: list[TopEntity],
        samples: dict[str, list[dict[str, str]]],
        readiness: dict[str, Any],
    ) -> dict[str, Any]:
        paid_cost = sum(row.cost for row in paid_rows)
        issues: list[str] = []
        warnings: list[str] = []
        if not paid_rows:
            issues.append("本周窗口内没有找到带花费的 Adjust 明细。")
        if not any(metric.field_name == "creative_id" and metric.filled_rows for metric in overall_metrics):
            issues.append("所有付费明细的 creative_id 都为空。")
        google_rows = [row for row in paid_rows if _normalize_channel(row.partner) == "Google"]
        if google_rows:
            google_resolved = sum(1 for row in google_rows if self._resolved_creative_identity(row) is not None)
            if google_resolved < len(google_rows):
                warnings.append(
                    "Google 创意字段还没有完全解析到素材 ID 层，当前仍有一部分花费落在通用占位值上。"
                )
        return {
            "passed": not issues,
            "window_start": window_start.isoformat(),
            "report_date": report_date.isoformat(),
            "window_label": f"{window_start.isoformat()} ~ {report_date.isoformat()}",
            "raw_rows": raw_rows,
            "paid_rows": len(paid_rows),
            "paid_cost": round(paid_cost, 2),
            "active_projects": sorted({_project_key(row.game) for row in paid_rows}),
            "overall_metrics": [asdict(item) | {
                "row_coverage_pct": round(item.row_coverage_pct, 4),
                "cost_coverage_pct": round(item.cost_coverage_pct, 4),
            } for item in overall_metrics],
            "channel_coverage": [asdict(item) for item in channel_coverage],
            "top_entities": [asdict(item) for item in top_entities],
            "samples": samples,
            "readiness": readiness,
            "issues": issues,
            "warnings": warnings,
        }

    def _render_markdown(self, payload: dict[str, Any]) -> str:
        lines = [
            f"# 创意归因审计 | {payload['report_date']}",
            "",
            f"- 周窗口：{payload['window_label']}",
            f"- 原始 Adjust 明细行数：{payload['raw_rows']}",
            f"- 有付费明细行数：{payload['paid_rows']}",
            f"- 有付费总花费：{payload['paid_cost']:.2f}",
            f"- 活跃项目：{', '.join(payload['active_projects']) or '-'}",
            "",
            "## 结论",
            "",
        ]

        if payload["issues"]:
            for issue in payload["issues"]:
                lines.append(f"- 阻塞：{issue}")
        else:
            readiness = payload["readiness"]
            lines.append(
                f"- Campaign 级分析：{'可用' if readiness['campaign_analysis_ready'] else '不可用'}"
            )
            lines.append(
                f"- Adgroup 级分析：{'可用' if readiness['adgroup_analysis_ready'] else '不可用'}"
            )
            lines.append(
                f"- Creative 级分析：{'可用' if readiness['creative_analysis_ready'] else '部分可用'}"
            )
        for warning in payload["warnings"]:
            lines.append(f"- 提示：{warning}")

        lines.extend(
            [
                "",
                "## 字段覆盖率",
                "",
                "| Field | Filled Rows | Row Coverage | Spend Coverage |",
                "|---|---:|---:|---:|",
            ]
        )
        for metric in payload["overall_metrics"]:
            lines.append(
                f"| {metric['field_name']} | {metric['filled_rows']} / {metric['paid_rows']} | "
                f"{metric['row_coverage_pct']:.1%} | {metric['cost_coverage_pct']:.1%} |"
            )

        lines.extend(
            [
                "",
                "## 项目 / 商店 / 渠道覆盖率",
                "",
                "| Project | Store | Channel | Paid Rows | Spend | Campaign ID | Adgroup ID | Creative ID | Creative Resolved | Distinct Creatives | Note |",
                "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
            ]
        )
        for item in payload["channel_coverage"]:
            lines.append(
                f"| {item['project']} | {item['store']} | {item['channel']} | {item['paid_rows']} | "
                f"{item['paid_cost']:.2f} | {item['campaign_id_coverage_pct']:.1%} | "
                f"{item['adgroup_id_coverage_pct']:.1%} | {item['creative_id_coverage_pct']:.1%} | "
                f"{item['creative_resolved_coverage_pct']:.1%} | {item['distinct_creatives']} | {item['note']} |"
            )

        lines.extend(["", "## 渠道样例", ""])
        for channel, samples in payload["samples"].items():
            lines.append(f"### {channel}")
            if not samples:
                lines.append("- 无样例")
                lines.append("")
                continue
            for sample in samples:
                lines.append(
                    "- "
                    + " | ".join(
                        [
                            f"{sample['project']}/{sample['store']}",
                            sample["country"] or "-",
                            f"campaign={sample['campaign_id'] or sample['campaign'] or '-'}",
                            f"adgroup={sample['adgroup_id'] or sample['adgroup'] or '-'}",
                            f"creative={sample['creative_id'] or sample['creative_name'] or '-'}",
                            f"source={sample['source_id'] or sample['source_name'] or '-'}",
                        ]
                    )
                )
            lines.append("")

        for level in ("campaign", "adgroup", "creative"):
            rows = [row for row in payload["top_entities"] if row["level"] == level][:15]
            lines.extend(
                [
                    f"## Top {level.title()}",
                    "",
                    "| Project | Store | Channel | ID | Name | Spend | Gross ROI | Countries |",
                    "|---|---|---|---|---|---:|---:|---|",
                ]
            )
            if not rows:
                lines.append("| - | - | - | - | - | 0 | 0 | - |")
            for row in rows:
                lines.append(
                    f"| {row['project']} | {row['store']} | {row['channel']} | {row['entity_id'] or '-'} | "
                    f"{row['entity_name'] or '-'} | {row['cost']:.2f} | {row['gross_roi']:.2f} | "
                    f"{row['sample_countries'] or '-'} |"
                )
            lines.append("")

        return "\n".join(lines).rstrip() + "\n"

    @staticmethod
    def _write_coverage_csv(path: Path, rows: list[ChannelCoverage]) -> None:
        fieldnames = [
            "project",
            "store",
            "channel",
            "paid_rows",
            "paid_cost",
            "campaign_coverage_pct",
            "campaign_id_coverage_pct",
            "adgroup_coverage_pct",
            "adgroup_id_coverage_pct",
            "creative_name_coverage_pct",
            "creative_id_coverage_pct",
            "creative_resolved_coverage_pct",
            "source_name_coverage_pct",
            "source_id_coverage_pct",
            "distinct_campaigns",
            "distinct_adgroups",
            "distinct_creatives",
            "distinct_sources",
            "note",
        ]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(asdict(row))

    @staticmethod
    def _write_top_entities_csv(path: Path, rows: list[TopEntity]) -> None:
        fieldnames = [
            "level",
            "project",
            "store",
            "channel",
            "entity_id",
            "entity_name",
            "paid_rows",
            "cost",
            "gross_revenue",
            "gross_roi",
            "sample_countries",
        ]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(asdict(row))

    @staticmethod
    def _entity_key(entity_id: str, entity_name: str) -> str:
        key = str(entity_id or "").strip()
        if key:
            return key
        return str(entity_name or "").strip()

    def _resolved_creative_identity(self, row: RevenueBreakdownRow) -> dict[str, str] | None:
        channel = _normalize_channel(row.partner)
        if channel == "Google":
            resolved = self._google_resolver.resolve(row)
            if resolved is None:
                return None
            entity_id = str(resolved.asset_id or resolved.identity_id or "").strip()
            entity_name = str(resolved.creative_name or resolved.identity_name or entity_id).strip()
            if not self._entity_key(entity_id, entity_name):
                return None
            return {"entity_id": entity_id, "entity_name": entity_name}
        entity_id = str(row.creative_id or "").strip()
        entity_name = str(row.creative_name or "").strip()
        if not self._is_resolved_creative(entity_id, entity_name):
            return None
        return {
            "entity_id": entity_id or entity_name,
            "entity_name": entity_name or entity_id,
        }

    def _resolved_entity_key(self, row: RevenueBreakdownRow) -> str:
        resolved = self._resolved_creative_identity(row)
        if resolved is None:
            return ""
        return self._entity_key(resolved["entity_id"], resolved["entity_name"])

    @classmethod
    def _is_resolved_creative(cls, creative_id: str, creative_name: str) -> bool:
        id_text = str(creative_id or "").strip()
        name_text = str(creative_name or "").strip()
        if not id_text and not name_text:
            return False
        if cls._is_generic_creative_value(id_text) and cls._is_generic_creative_value(name_text):
            return False
        return True

    @staticmethod
    def _is_generic_creative_value(value: str) -> bool:
        text = re.sub(r"\s+", " ", str(value or "").strip()).lower()
        if text in GENERIC_CREATIVE_VALUES:
            return True
        if re.fullmatch(r"(display|video|image|search)( [0-9]+)?", text):
            return True
        return False


def _align_to_wednesday(value: date) -> date:
    return value - timedelta(days=(value.weekday() - 2) % 7)


def _project_key(name: str) -> str:
    cleaned = (name or "").strip()
    match = re.search(r"\bP0*([0-9]+)\b", cleaned.upper())
    if match:
        return f"P{int(match.group(1)):02d}"
    return cleaned or "UNKNOWN"


def _normalize_store(value: str) -> str:
    normalized = (value or "").strip().lower()
    mapping = {
        "app_store": "iOS",
        "google_play": "Android",
        "amazon": "Amazon",
    }
    return mapping.get(normalized, (value or "unknown").strip() or "unknown")


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
        return "Unity"
    if "tiktok" in normalized:
        return "TikTok"
    return (value or "unknown").strip() or "unknown"


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0
