from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.pipeline import DataRepository


@dataclass(slots=True)
class GoogleRevenueAttributionAuditResult:
    markdown_path: Path
    json_path: Path
    csv_path: Path
    passed: bool


class GoogleRevenueAttributionAuditBuilder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._repo = DataRepository(settings)

    def build(self, report_date: date) -> GoogleRevenueAttributionAuditResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self.build_payload(report_date)

        markdown_path = output_dir / f"google_revenue_attribution_audit_{suffix}.md"
        json_path = output_dir / f"google_revenue_attribution_audit_{suffix}.json"
        csv_path = self._settings.output_dir / f"google_revenue_zero_segments_{suffix}.csv"

        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._write_csv(csv_path, payload.get("zero_revenue_segments", []))

        return GoogleRevenueAttributionAuditResult(
            markdown_path=markdown_path,
            json_path=json_path,
            csv_path=csv_path,
            passed=bool(payload.get("passed")),
        )

    def build_payload(self, report_date: date) -> dict[str, Any]:
        window_start = report_date - timedelta(days=6)
        rows = [
            row
            for row in self._repo.load_adjust_revenue_breakdown(window_start, report_date)
            if self._normalize_channel(str(getattr(row, "partner", "") or "")) == "Google"
        ]
        paid_rows = [row for row in rows if float(getattr(row, "cost", 0.0) or 0.0) > 0]
        segment_rows = self._aggregate_segments(rows)
        zero_segments = [
            item
            for item in segment_rows
            if float(item.get("cost") or 0.0) > 0 and float(item.get("revenue") or 0.0) <= 0
        ]
        positive_segments = [
            item
            for item in segment_rows
            if float(item.get("cost") or 0.0) > 0 and float(item.get("revenue") or 0.0) > 0
        ]
        total_cost = sum(float(getattr(row, "cost", 0.0) or 0.0) for row in rows)
        total_revenue = sum(float(getattr(row, "total_revenue_gross", 0.0) or 0.0) for row in rows)
        zero_cost = sum(float(item.get("cost") or 0.0) for item in zero_segments)
        zero_cost_share = (zero_cost / total_cost) if total_cost else 0.0

        zero_segments = sorted(zero_segments, key=lambda item: float(item["cost"]), reverse=True)[:30]
        top_revenue_segments = sorted(positive_segments, key=lambda item: float(item["revenue"]), reverse=True)[:15]
        passed = zero_cost_share < 0.20
        risk_level = "高" if zero_cost_share >= 0.50 else "中" if zero_cost_share >= 0.20 else "低"
        conclusion = (
            "Google 本周存在较高占比有花费无收入细分段，当前 Google 深层 ROI 只能作为归因复核优先级，不能作为强停投依据。"
            if not passed
            else "Google 本周聚合后有花费无收入占比可控，当前 Google ROI 可作为方向判断。"
        )

        return {
            "report_date": report_date.isoformat(),
            "window_start": window_start.isoformat(),
            "window_end": report_date.isoformat(),
            "passed": passed,
            "risk_level": risk_level,
            "conclusion": conclusion,
            "summary": {
                "google_rows": len(rows),
                "google_paid_rows": len(paid_rows),
                "google_total_cost": round(total_cost, 4),
                "google_total_revenue": round(total_revenue, 4),
                "google_gross_roi": round((total_revenue / total_cost) if total_cost else 0.0, 4),
                "zero_revenue_segments": len(zero_segments),
                "zero_revenue_cost": round(zero_cost, 4),
                "zero_revenue_cost_share": round(zero_cost_share, 4),
            },
            "zero_revenue_segments": zero_segments,
            "positive_revenue_segments": top_revenue_segments,
        }

    def _aggregate_segments(self, rows: list[Any]) -> list[dict[str, Any]]:
        buckets: dict[tuple[str, str, str, str, str, str, str], dict[str, Any]] = {}
        for row in rows:
            key = (
                str(getattr(row, "game", "") or ""),
                self._normalize_store(str(getattr(row, "store", "") or "")),
                str(getattr(row, "country", "") or "Global"),
                str(getattr(row, "campaign_id", "") or ""),
                str(getattr(row, "campaign", "") or ""),
                str(getattr(row, "adgroup_id", "") or ""),
                str(getattr(row, "creative_id", "") or getattr(row, "creative_name", "") or ""),
            )
            bucket = buckets.setdefault(
                key,
                {
                    "project": key[0],
                    "store": key[1],
                    "country": key[2],
                    "campaign_id": key[3],
                    "campaign": key[4],
                    "adgroup_id": key[5],
                    "creative_id": key[6],
                    "cost": 0.0,
                    "revenue": 0.0,
                    "rows": 0,
                    "paid_rows": 0,
                    "revenue_rows": 0,
                    "dates": set(),
                    "source_ids": set(),
                    "source_names": set(),
                },
            )
            cost = float(getattr(row, "cost", 0.0) or 0.0)
            revenue = float(getattr(row, "total_revenue_gross", 0.0) or 0.0)
            bucket["cost"] += cost
            bucket["revenue"] += revenue
            bucket["rows"] += 1
            if cost > 0:
                bucket["paid_rows"] += 1
            if revenue > 0:
                bucket["revenue_rows"] += 1
            bucket["dates"].add(getattr(row, "date", None).isoformat() if getattr(row, "date", None) else "")
            source_id = str(getattr(row, "source_id", "") or "").strip()
            source_name = str(getattr(row, "source_name", "") or "").strip()
            if source_id:
                bucket["source_ids"].add(source_id)
            if source_name:
                bucket["source_names"].add(source_name)
        result: list[dict[str, Any]] = []
        for bucket in buckets.values():
            cost = float(bucket["cost"])
            revenue = float(bucket["revenue"])
            result.append(
                {
                    "project": bucket["project"],
                    "store": bucket["store"],
                    "country": bucket["country"],
                    "campaign_id": bucket["campaign_id"],
                    "campaign": bucket["campaign"],
                    "adgroup_id": bucket["adgroup_id"],
                    "creative_id": bucket["creative_id"],
                    "cost": round(cost, 4),
                    "revenue": round(revenue, 4),
                    "roi": round((revenue / cost) if cost else 0.0, 4),
                    "rows": int(bucket["rows"]),
                    "paid_rows": int(bucket["paid_rows"]),
                    "revenue_rows": int(bucket["revenue_rows"]),
                    "dates": ", ".join(sorted(item for item in bucket["dates"] if item)),
                    "source_ids": ", ".join(sorted(bucket["source_ids"])) or "unknown",
                    "source_names": ", ".join(sorted(bucket["source_names"])) or "unknown",
                }
            )
        return result

    @staticmethod
    def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = [
            "project",
            "store",
            "country",
            "campaign_id",
            "campaign",
            "adgroup_id",
            "creative_id",
            "cost",
            "revenue",
            "roi",
            "rows",
            "paid_rows",
            "revenue_rows",
            "dates",
            "source_ids",
            "source_names",
        ]
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: row.get(field, "") for field in fieldnames})

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        lines = [
            f"# Google 收入归因异常审计 | {payload['report_date']}",
            "",
            f"- 周窗口：{payload['window_start']} ~ {payload['window_end']}",
            f"- 状态：{'通过' if payload['passed'] else '需复核'}",
            f"- 风险等级：{payload['risk_level']}",
            f"- 结论：{payload['conclusion']}",
            "",
            "## Google 总览",
            "",
            f"- 付费明细行数：{summary['google_paid_rows']}",
            f"- 总花费：{summary['google_total_cost']:.2f}",
            f"- 总收入：{summary['google_total_revenue']:.2f}",
            f"- 总收入ROI：{summary['google_gross_roi']:.2f}",
            f"- 有花费无收入细分段：{summary['zero_revenue_segments']}",
            f"- 有花费无收入花费：{summary['zero_revenue_cost']:.2f} ({summary['zero_revenue_cost_share']:.1%})",
            "",
            "## 需要优先复核的 Google 零收入段",
            "",
            "| Project | Store | Country | Campaign | Adgroup | Creative | Cost | Revenue | ROI | Rows | Dates |",
            "|---|---|---|---|---|---|---:|---:|---:|---:|---|",
        ]
        for item in payload.get("zero_revenue_segments", [])[:15]:
            lines.append(
                "| {project} | {store} | {country} | {campaign} | {adgroup_id} | {creative_id} | {cost:.2f} | {revenue:.2f} | {roi:.2f} | {rows} | {dates} |".format(
                    **item
                )
            )
        if not payload.get("zero_revenue_segments"):
            lines.append("| - | - | - | - | - | - | 0.00 | 0.00 | 0.00 | 0 | - |")
        lines.extend(["", "## Google 有收入段参考", "", "| Project | Campaign | Cost | Revenue | ROI | Rows |", "|---|---|---:|---:|---:|---:|"])
        for item in payload.get("positive_revenue_segments", [])[:10]:
            lines.append(
                "| {project} | {campaign} | {cost:.2f} | {revenue:.2f} | {roi:.2f} | {rows} |".format(
                    **item
                )
            )
        if not payload.get("positive_revenue_segments"):
            lines.append("| - | - | 0.00 | 0.00 | 0.00 | 0 |")
        lines.extend(
            [
                "",
                "## 使用规则",
                "",
                "- 本审计按同一 Project / Store / Country / Campaign / Adgroup / Creative 聚合所有 Adjust 行后再判断，不按单行 cost/revenue 直接判 0。",
                "- 当有花费无收入花费占比 >=20% 时，Google 深层 ROI 只作为归因复核优先级，不作为强停投结论。",
                "- 如果 Adjust 后台应用/渠道层有收入，但深层分组为 0，先修数据同步或字段映射，不直接下预算结论。",
                "",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _normalize_channel(value: str) -> str:
        lowered = (value or "").strip().lower()
        if "google" in lowered:
            return "Google"
        if "facebook" in lowered or "meta" in lowered or "instagram" in lowered or "off-facebook" in lowered:
            return "Facebook"
        return value.strip() or "Unknown"

    @staticmethod
    def _normalize_store(value: str) -> str:
        lowered = (value or "").strip().lower()
        mapping = {"app_store": "iOS", "google_play": "Android", "amazon": "Amazon"}
        return mapping.get(lowered, value.strip() or "Unknown")
