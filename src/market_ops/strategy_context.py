from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.config import Settings


@dataclass(slots=True)
class StrategyContextResult:
    markdown_path: Path
    json_path: Path
    passed: bool


class StrategyContextBuilder:
    """Builds the human strategy input layer for the AI Media Buyer loop."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> StrategyContextResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self.build_payload(report_date)

        markdown_path = output_dir / f"strategy_context_{suffix}.md"
        json_path = output_dir / f"strategy_context_{suffix}.json"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._ensure_example()
        return StrategyContextResult(markdown_path=markdown_path, json_path=json_path, passed=bool(payload["passed"]))

    def build_payload(self, report_date: date) -> dict[str, Any]:
        workspace_root = self._settings.output_dir.parent
        input_path = workspace_root / "input" / "strategy_context.json"
        raw = _load_json(input_path) if input_path.exists() else {}
        priorities = [_normalize_priority(item, index) for index, item in enumerate(raw.get("priorities") or [], start=1)]
        guardrails = [str(item).strip() for item in raw.get("guardrails") or [] if str(item).strip()]
        missing_fields = _missing_fields(raw, priorities)
        active_priorities = [item for item in priorities if item["status"] == "active"]
        return {
            "report_date": report_date.isoformat(),
            "mode": "strategy_context_signal",
            "passed": True,
            "source_file": str(input_path),
            "strategy_input_ready": bool(active_priorities) and not missing_fields,
            "rules": {
                "signal_only": True,
                "human_owned_strategy": True,
                "decision_engine_owns_actions": True,
                "example_file_is_not_active_strategy": True,
            },
            "summary": {
                "priority_count": len(priorities),
                "active_priority_count": len(active_priorities),
                "guardrail_count": len(guardrails),
                "missing_field_count": len(missing_fields),
            },
            "priorities": priorities,
            "guardrails": guardrails,
            "missing_fields": missing_fields,
            "suggested_template_file": str(workspace_root / "input" / "strategy_context.example.json"),
        }

    def _ensure_example(self) -> None:
        path = self._settings.output_dir.parent / "input" / "strategy_context.example.json"
        if path.exists():
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        example = {
            "owner": "human_strategy",
            "updated_at": "YYYY-MM-DD",
            "priorities": [
                {
                    "name": "US female Merge IAA exploration",
                    "status": "active",
                    "project": "P04 Witch",
                    "audience": "female",
                    "genre": "Merge",
                    "country": "United States",
                    "platform": "Meta",
                    "monetization": "IAA",
                    "objective": "maximize learning speed before ROI scaling",
                    "priority_weight": 1.0,
                    "notes": "Example only. Copy to strategy_context.json and edit before activation.",
                }
            ],
            "guardrails": [
                "Do not scale when lifecycle_stage=data_gap.",
                "Discovery priorities optimize learning speed before ROI.",
                "All platform writes require approval until write readiness passes.",
            ],
        }
        path.write_text(json.dumps(example, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        lines = [
            f"# Strategy Context | {payload['report_date']}",
            "",
            "- Mode: strategy_context_signal",
            "- Boundary: human-owned strategy input only; this layer does not emit actions.",
            f"- Source file: {payload['source_file']}",
            f"- Strategy input ready: {payload['strategy_input_ready']}",
            "",
            "## Summary",
            "",
            f"- Priorities: {summary['priority_count']}",
            f"- Active priorities: {summary['active_priority_count']}",
            f"- Guardrails: {summary['guardrail_count']}",
            f"- Missing fields: {summary['missing_field_count']}",
            "",
        ]
        if payload["missing_fields"]:
            lines.extend(["## Missing Strategy Input", ""])
            lines.extend(f"- {item}" for item in payload["missing_fields"])
            lines.append(f"- Template: {payload['suggested_template_file']}")
            lines.append("")
        lines.extend(["## Priorities", ""])
        if not payload["priorities"]:
            lines.append("- None.")
        for item in payload["priorities"]:
            lines.append(
                f"- {item['name']} | {item['status']} | project={item['project']} | "
                f"country={item['country']} | platform={item['platform']} | objective={item['objective']}"
            )
        lines.extend(["", "## Guardrails", ""])
        if not payload["guardrails"]:
            lines.append("- None.")
        lines.extend(f"- {item}" for item in payload["guardrails"])
        lines.append("")
        return "\n".join(lines)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _normalize_priority(item: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "priority_id": str(item.get("priority_id") or f"strategy_{index:03d}"),
        "name": str(item.get("name") or f"strategy_{index:03d}").strip(),
        "status": str(item.get("status") or "draft").strip(),
        "project": str(item.get("project") or "").strip(),
        "audience": str(item.get("audience") or "").strip(),
        "genre": str(item.get("genre") or "").strip(),
        "country": str(item.get("country") or "").strip(),
        "platform": str(item.get("platform") or "").strip(),
        "monetization": str(item.get("monetization") or "").strip(),
        "objective": str(item.get("objective") or "").strip(),
        "priority_weight": float(item.get("priority_weight") or 1.0),
        "notes": str(item.get("notes") or "").strip(),
    }


def _missing_fields(raw: dict[str, Any], priorities: list[dict[str, Any]]) -> list[str]:
    missing: list[str] = []
    if not raw:
        return ["input/strategy_context.json is missing"]
    if not priorities:
        missing.append("priorities")
    for item in priorities:
        if item["status"] != "active":
            continue
        for field in ("name", "project", "country", "platform", "objective"):
            if not item.get(field):
                missing.append(f"{item['priority_id']}.{field}")
    return missing
