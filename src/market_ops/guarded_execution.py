from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.action_layer import ActionLayerBuilder
from market_ops.config import Settings


CONNECTOR_METHODS = {
    "meta_ads": {
        "increase_budget_cap": "MetaAdsConnector.increase_budget_cap",
        "decrease_budget_or_bid": "MetaAdsConnector.decrease_budget_or_bid",
        "pause_candidate_review": "MetaAdsConnector.pause_candidate_review",
    },
    "google_ads": {
        "increase_budget_cap": "GoogleAdsConnector.increase_budget_cap",
        "decrease_budget_or_bid": "GoogleAdsConnector.decrease_budget_or_bid",
        "pause_candidate_review": "GoogleAdsConnector.pause_candidate_review",
    },
}


@dataclass(slots=True)
class GuardedExecutionResult:
    markdown_path: Path
    json_path: Path
    csv_path: Path
    passed: bool


class GuardedExecutionBuilder:
    """Builds execution attempts without calling ad-platform write APIs."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> GuardedExecutionResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self.build_payload(report_date)

        markdown_path = output_dir / f"guarded_execution_{suffix}.md"
        json_path = output_dir / f"guarded_execution_{suffix}.json"
        csv_path = output_dir / f"guarded_execution_{suffix}.csv"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._write_csv(csv_path, payload["attempts"])
        return GuardedExecutionResult(markdown_path=markdown_path, json_path=json_path, csv_path=csv_path, passed=bool(payload["passed"]))

    def build_payload(self, report_date: date) -> dict[str, Any]:
        suffix = report_date.strftime("%Y%m%d")
        action_path = self._settings.active_output_dir / f"action_layer_{suffix}.json"
        if not action_path.exists():
            ActionLayerBuilder(self._settings).build(report_date)
        action_payload = _load_json(action_path)

        attempts = [_attempt(item, index) for index, item in enumerate(action_payload.get("execution_intents") or [], start=1)]
        blocked = [item for item in attempts if item["attempt_status"] == "blocked"]
        dry_run_ready = [item for item in attempts if item["attempt_status"] == "dry_run_ready"]
        executed = [item for item in attempts if item["attempt_status"] == "executed"]
        return {
            "report_date": report_date.isoformat(),
            "mode": "guarded_dry_run_execution",
            "passed": True,
            "rules": {
                "no_platform_write": True,
                "connector_calls_disabled": True,
                "execution_requires_empty_blockers": True,
                "execution_requires_connector_method": True,
            },
            "summary": {
                "attempt_count": len(attempts),
                "blocked_count": len(blocked),
                "dry_run_ready_count": len(dry_run_ready),
                "executed_count": len(executed),
            },
            "attempts": attempts,
        }

    @staticmethod
    def _write_csv(path: Path, attempts: list[dict[str, Any]]) -> None:
        fieldnames = [
            "attempt_id",
            "attempt_status",
            "intent_id",
            "platform",
            "operation",
            "target",
            "connector_method",
            "blockers",
        ]
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for item in attempts:
                row = {field: item.get(field, "") for field in fieldnames}
                row["blockers"] = " | ".join(item.get("blockers") or [])
                writer.writerow(row)

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        lines = [
            f"# Guarded Execution | {payload['report_date']}",
            "",
            "- Mode: guarded_dry_run_execution",
            "- Purpose: map execution intents to future connector calls while keeping writes disabled.",
            "",
            "## Summary",
            "",
            f"- Attempts: {summary['attempt_count']}",
            f"- Blocked: {summary['blocked_count']}",
            f"- Dry-run ready: {summary['dry_run_ready_count']}",
            f"- Executed: {summary['executed_count']}",
            "",
            "## Attempts",
            "",
        ]
        if not payload["attempts"]:
            lines.append("- None.")
        for item in payload["attempts"][:50]:
            blockers = ", ".join(item["blockers"]) if item["blockers"] else "none"
            lines.append(
                f"- {item['attempt_id']} | {item['attempt_status']} | {item['platform']} | "
                f"{item['operation']} | {item['target']} | connector={item['connector_method'] or 'none'} | blockers={blockers}"
            )
        lines.append("")
        return "\n".join(lines)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _attempt(intent: dict[str, Any], index: int) -> dict[str, Any]:
    platform = str(intent.get("platform") or "")
    operation = str(intent.get("operation") or "")
    connector_method = (CONNECTOR_METHODS.get(platform) or {}).get(operation, "")
    blockers = _unique(list(intent.get("blocked_reasons") or []))
    if not connector_method and operation != "hold_no_write":
        blockers.append("connector_method_missing")
    blockers = _unique(blockers)
    if blockers:
        status = "blocked"
    elif intent.get("platform_write_ready"):
        status = "dry_run_ready"
    else:
        status = "blocked"
        blockers.append("platform_write_not_ready")

    return {
        "attempt_id": f"exec_{index:03d}",
        "attempt_status": status,
        "intent_id": intent.get("intent_id", ""),
        "platform": platform,
        "operation": operation,
        "target": intent.get("target", ""),
        "project": intent.get("project", ""),
        "connector_method": connector_method,
        "parameters": intent.get("parameters") or {},
        "rollback_conditions": list(intent.get("rollback_conditions") or []),
        "blockers": _unique(blockers),
        "source_intent": intent,
    }


def _unique(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        if item and item not in result:
            result.append(item)
    return result
