from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.payback_targets import PaybackTargetsBuilder, ProjectTargets


@dataclass(slots=True)
class DynamicPaybackResult:
    markdown_path: Path
    json_path: Path
    csv_path: Path
    passed: bool


class DynamicPaybackBuilder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> DynamicPaybackResult:
        suffix = report_date.strftime("%Y%m%d")
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        payload = self.build_payload(report_date)
        markdown_path = output_dir / f"dynamic_payback_{suffix}.md"
        json_path = output_dir / f"dynamic_payback_{suffix}.json"
        csv_path = output_dir / f"dynamic_payback_{suffix}.csv"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._write_csv(csv_path, payload["items"])
        return DynamicPaybackResult(markdown_path, json_path, csv_path, True)

    def build_payload(self, report_date: date) -> dict[str, Any]:
        try:
            targets, self_check = PaybackTargetsBuilder(self._settings).build_targets_data(report_date)
        except Exception as exc:
            targets, self_check = [], {"passed": False, "error": str(exc)}
        items = [self._build_item(item) for item in targets]
        return {
            "report_date": report_date.isoformat(),
            "source": "payback_targets + existing user quality metrics",
            "rules": {
                "static_line": "historical profitable floor remains visible",
                "dynamic_line": "adjusted by CPI, D1 retention, ARPU/ARPPU availability and current D7",
                "missing_fields": ["session_duration", "ad_views_per_user", "first_purchase_rate"],
            },
            "self_check": self_check,
            "summary": {
                "project_count": len(items),
                "high_confidence_count": sum(1 for item in items if item["confidence"] >= 0.7),
                "gap_fields": ["Session 时长", "广告观看次数", "首次付费率"],
            },
            "items": items,
        }

    @staticmethod
    def _build_item(target: ProjectTargets) -> dict[str, Any]:
        d7_static = _target_floor(target, "D7")
        d30_static = _target_floor(target, "D30")
        current_d7 = target.current_recovery.get("D7")
        cpi_factor = _ratio_factor_lower_is_better(target.current_cpi, target.cpi_guardrail.ceiling)
        retention_factor = _ratio_factor_higher_is_better(target.current_retention_d1, target.retention_guardrail.floor)
        arpu_factor = _ratio_factor_higher_is_better(target.current_arpu, target.arpu_guardrail.floor)
        available = sum(value is not None for value in (target.current_cpi, target.current_retention_d1, target.current_arpu, current_d7))
        adjustment = 1.0
        for factor in (cpi_factor, retention_factor, arpu_factor):
            adjustment *= factor
        dynamic_d7 = (d7_static or current_d7 or 0.0) * adjustment
        dynamic_d30 = (d30_static or 0.0) * adjustment if d30_static is not None else 0.0
        confidence = min(0.85, 0.35 + available * 0.10 + min(target.profitable_weeks, 8) * 0.025)
        judgement = "observe"
        if current_d7 and dynamic_d7 and current_d7 >= dynamic_d7 and confidence >= 0.65:
            judgement = "dynamic_line_pass"
        elif current_d7 and dynamic_d7 and current_d7 < dynamic_d7:
            judgement = "dynamic_line_gap"
        return {
            "project": target.project,
            "static_break_even_d7": round(d7_static or 0.0, 4),
            "static_break_even_d30": round(d30_static or 0.0, 4),
            "dynamic_break_even_d7": round(dynamic_d7, 4),
            "dynamic_break_even_d30": round(dynamic_d30, 4),
            "current_d7": round(current_d7 or 0.0, 4),
            "current_cpi": round(target.current_cpi or 0.0, 4),
            "current_retention_d1": round(target.current_retention_d1 or 0.0, 4),
            "current_arpu": round(target.current_arpu or 0.0, 4),
            "current_arppu": round(target.current_arppu or 0.0, 4),
            "confidence": round(confidence, 4),
            "judgement": judgement,
            "quality_signals": [
                f"CPI={target.current_cpi:.2f}" if target.current_cpi is not None else "CPI 缺失",
                f"D1留存={target.current_retention_d1:.2%}" if target.current_retention_d1 is not None else "D1留存缺失",
                f"ARPU={target.current_arpu:.2f}" if target.current_arpu is not None else "ARPU 缺失",
                f"ARPPU={target.current_arppu:.2f}" if target.current_arppu is not None else "ARPPU 缺失",
            ],
            "missing_quality_fields": ["Session 时长", "广告观看次数", "首次付费率"],
        }

    @staticmethod
    def _write_csv(path: Path, items: list[dict[str, Any]]) -> None:
        fieldnames = [
            "project",
            "static_break_even_d7",
            "static_break_even_d30",
            "dynamic_break_even_d7",
            "dynamic_break_even_d30",
            "current_d7",
            "current_cpi",
            "current_retention_d1",
            "current_arpu",
            "current_arppu",
            "confidence",
            "judgement",
            "quality_signals",
            "missing_quality_fields",
        ]
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for item in items:
                row = {field: item.get(field, "") for field in fieldnames}
                row["quality_signals"] = "；".join(item.get("quality_signals") or [])
                row["missing_quality_fields"] = "；".join(item.get("missing_quality_fields") or [])
                writer.writerow(row)

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        lines = [
            f"# 动态回本模型 | {payload['report_date']}",
            "",
            "- 保留静态历史保底线，同时输出动态 D7/D30 参考线和置信度。",
            "- 当前已接入：D1/D7 retention、CPI、ARPU/ARPPU。Session、广告观看次数、首次付费率列为缺口，不参与判断。",
            "",
            "## 概览",
            "",
            f"- 项目数：{summary['project_count']}",
            f"- 高置信度项目：{summary['high_confidence_count']}",
            f"- 用户质量缺口：{'、'.join(summary['gap_fields'])}",
            "",
            "## 项目动态线",
            "",
        ]
        if not payload["items"]:
            lines.append("- 暂无。")
        else:
            lines.extend(
                [
                    "| 项目 | 当前 D7 | 静态 D7 | 动态 D7 | 静态 D30 | 动态 D30 | CPI | D1留存 | ARPU | 置信度 | 判断 |",
                    "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
                ]
            )
            for item in payload["items"]:
                lines.append(
                    f"| {item['project']} | {item['current_d7']:.2f} | {item['static_break_even_d7']:.2f} | {item['dynamic_break_even_d7']:.2f} | "
                    f"{item['static_break_even_d30']:.2f} | {item['dynamic_break_even_d30']:.2f} | {item['current_cpi']:.2f} | "
                    f"{item['current_retention_d1']:.2%} | {item['current_arpu']:.2f} | {item['confidence']:.2f} | {item['judgement']} |"
                )
        lines.append("")
        return "\n".join(lines)


def _target_floor(target: ProjectTargets, metric: str) -> float | None:
    value = target.recovery_targets.get(metric)
    return value.floor if value else None


def _ratio_factor_lower_is_better(current: float | None, ceiling: float | None) -> float:
    if current is None or not ceiling or ceiling <= 0:
        return 1.0
    if current <= ceiling:
        return 0.95
    return min(1.2, 1.0 + (current - ceiling) / ceiling * 0.25)


def _ratio_factor_higher_is_better(current: float | None, floor: float | None) -> float:
    if current is None or not floor or floor <= 0:
        return 1.0
    if current >= floor:
        return 0.95
    return min(1.2, 1.0 + (floor - current) / floor * 0.25)
