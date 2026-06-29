from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.dynamic_payback import DynamicPaybackBuilder


@dataclass(slots=True)
class UserQualityResult:
    markdown_path: Path
    json_path: Path
    passed: bool


class UserQualityBuilder:
    """Builds a standalone user-quality signal layer from available project metrics."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> UserQualityResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self.build_payload(report_date)

        markdown_path = output_dir / f"user_quality_{suffix}.md"
        json_path = output_dir / f"user_quality_{suffix}.json"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return UserQualityResult(markdown_path=markdown_path, json_path=json_path, passed=bool(payload["passed"]))

    def build_payload(self, report_date: date) -> dict[str, Any]:
        suffix = report_date.strftime("%Y%m%d")
        path = self._settings.active_output_dir / f"dynamic_payback_{suffix}.json"
        if not path.exists():
            DynamicPaybackBuilder(self._settings).build(report_date)
        payback_payload = _load_json(path)
        items = [_quality_item(item) for item in payback_payload.get("items") or []]
        high = [item for item in items if item["quality_status"] == "high_quality"]
        mixed = [item for item in items if item["quality_status"] == "mixed_quality"]
        blocked = [item for item in items if item["quality_status"] == "quality_data_gap"]
        return {
            "report_date": report_date.isoformat(),
            "mode": "user_quality_layer",
            "passed": True,
            "source": str(path),
            "rules": {
                "signal_only": True,
                "missing_fields_do_not_imply_low_quality": True,
                "used_metrics": ["current_d7", "current_cpi", "current_retention_d1", "current_arpu", "current_arppu"],
            },
            "summary": {
                "project_count": len(items),
                "high_quality_count": len(high),
                "mixed_quality_count": len(mixed),
                "quality_data_gap_count": len(blocked),
                "missing_quality_field_count": sum(len(item["missing_quality_fields"]) for item in items),
            },
            "items": items,
        }

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        lines = [
            f"# User Quality Layer | {payload['report_date']}",
            "",
            "- Mode: user_quality_layer",
            "- Purpose: expose CPI, retention, ARPU/ARPPU, and payback quality as a standalone signal layer.",
            "- Boundary: signal only; Decision Engine still owns final actions.",
            "",
            "## Summary",
            "",
            f"- Projects: {summary['project_count']}",
            f"- High quality: {summary['high_quality_count']}",
            f"- Mixed quality: {summary['mixed_quality_count']}",
            f"- Quality data gap: {summary['quality_data_gap_count']}",
            f"- Missing quality fields: {summary['missing_quality_field_count']}",
            "",
            "## Projects",
            "",
        ]
        if not payload["items"]:
            lines.append("- None.")
        for item in payload["items"]:
            missing = ", ".join(item["missing_quality_fields"]) if item["missing_quality_fields"] else "none"
            lines.append(
                f"- {item['project']} | {item['quality_status']} | score={item['quality_score']} | "
                f"D7={item['current_d7']} | CPI={item['current_cpi']} | D1={item['current_retention_d1']} | missing={missing}"
            )
        lines.append("")
        return "\n".join(lines)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _quality_item(item: dict[str, Any]) -> dict[str, Any]:
    current_d7 = float(item.get("current_d7") or 0.0)
    dynamic_d7 = float(item.get("dynamic_break_even_d7") or 0.0)
    cpi = float(item.get("current_cpi") or 0.0)
    retention = float(item.get("current_retention_d1") or 0.0)
    arpu = float(item.get("current_arpu") or 0.0)
    arppu = float(item.get("current_arppu") or 0.0)
    confidence = float(item.get("confidence") or 0.0)
    missing = list(item.get("missing_quality_fields") or [])

    payback_score = _ratio_score(current_d7, dynamic_d7)
    retention_score = _clamp(retention / 0.20) if retention else 0.0
    arpu_score = _clamp(arpu / 4.0) if arpu else 0.0
    cpi_score = _clamp(1.0 - max(cpi - 4.0, 0.0) / 4.0) if cpi else 0.0
    quality_score = round((payback_score * 0.35) + (retention_score * 0.25) + (arpu_score * 0.20) + (cpi_score * 0.10) + (confidence * 0.10), 4)

    if cpi == 0.0 or retention == 0.0:
        status = "quality_data_gap"
    elif quality_score >= 0.72 and current_d7 >= dynamic_d7:
        status = "high_quality"
    else:
        status = "mixed_quality"

    return {
        "project": item.get("project", ""),
        "quality_status": status,
        "quality_score": quality_score,
        "current_d7": round(current_d7, 4),
        "dynamic_break_even_d7": round(dynamic_d7, 4),
        "current_cpi": round(cpi, 4),
        "current_retention_d1": round(retention, 4),
        "current_arpu": round(arpu, 4),
        "current_arppu": round(arppu, 4),
        "confidence": round(confidence, 4),
        "quality_signals": list(item.get("quality_signals") or []),
        "missing_quality_fields": missing,
    }


def _ratio_score(value: float, target: float) -> float:
    if target <= 0:
        return 0.0
    return _clamp(value / target)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
