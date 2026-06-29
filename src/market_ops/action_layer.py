from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.ai_media_buyer_plan import AiMediaBuyerPlanBuilder
from market_ops.config import Settings
from market_ops.platform_write_readiness import PlatformWriteReadinessBuilder, readiness_for_intent


@dataclass(slots=True)
class ActionLayerResult:
    markdown_path: Path
    json_path: Path
    csv_path: Path
    passed: bool


class ActionLayerBuilder:
    """Builds audited execution intents without calling ad-platform write APIs."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> ActionLayerResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self.build_payload(report_date)

        markdown_path = output_dir / f"action_layer_{suffix}.md"
        json_path = output_dir / f"action_layer_{suffix}.json"
        csv_path = output_dir / f"action_layer_{suffix}.csv"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._write_csv(csv_path, payload["execution_intents"])
        return ActionLayerResult(markdown_path=markdown_path, json_path=json_path, csv_path=csv_path, passed=bool(payload["passed"]))

    def build_payload(self, report_date: date) -> dict[str, Any]:
        plan_payload = AiMediaBuyerPlanBuilder(self._settings).build_payload(report_date)
        readiness_payload = PlatformWriteReadinessBuilder(self._settings).build_payload(report_date)
        intents = [
            self._intent(item, index, readiness_payload)
            for index, item in enumerate(plan_payload.get("actions") or [], start=1)
        ]
        executable = [item for item in intents if item["execution_status"] == "ready_for_approval"]
        blocked = [item for item in intents if item["execution_status"] == "blocked"]
        return {
            "report_date": report_date.isoformat(),
            "mode": "dry_run_execution_intent",
            "passed": True,
            "rules": {
                "no_platform_write": True,
                "no_budget_change": True,
                "requires_human_approval": True,
                "decision_engine_only": "Action Layer only translates approved Decision Engine outputs into execution intents.",
            },
            "platform_write_readiness": {
                "global_write_enabled": readiness_payload.get("global_write_enabled", False),
                "ready_platforms": (readiness_payload.get("summary") or {}).get("ready_platforms", []),
            },
            "summary": {
                "intent_count": len(intents),
                "ready_for_approval_count": len(executable),
                "blocked_count": len(blocked),
                "platform_write_enabled": bool(readiness_payload.get("global_write_enabled")),
            },
            "execution_intents": intents,
        }

    def _intent(self, action: dict[str, Any], index: int, readiness_payload: dict[str, Any]) -> dict[str, Any]:
        action_type = str(action.get("action_type") or "")
        target = str(action.get("target") or "")
        platform = _infer_platform(target, str(action.get("project") or ""))
        operation = _operation(action_type)
        readiness = readiness_for_intent(readiness_payload, platform, operation)
        blocked_reasons = _blocked_reasons(action, platform, operation, readiness)
        status = "blocked" if blocked_reasons else "ready_for_approval"
        return {
            "intent_id": f"act_{index:03d}",
            "execution_status": status,
            "mode": "dry_run",
            "platform": platform,
            "operation": operation,
            "action_type": action_type,
            "target": target,
            "project": str(action.get("project") or ""),
            "parameters": _parameters(action, operation),
            "approval_required": True,
            "platform_write_enabled": bool(readiness.get("platform_write_enabled")),
            "platform_write_ready": bool(readiness.get("platform_write_ready")),
            "blocked_reasons": blocked_reasons,
            "supported_operations": list(readiness.get("supported_operations") or []),
            "rollback_conditions": list(action.get("rollback_conditions") or []),
            "evidence": list(action.get("evidence") or []),
            "confidence": str(action.get("confidence") or "low"),
            "source_action": action,
        }

    @staticmethod
    def _write_csv(path: Path, intents: list[dict[str, Any]]) -> None:
        fieldnames = [
            "intent_id",
            "execution_status",
            "mode",
            "platform",
            "operation",
            "action_type",
            "target",
            "project",
            "approval_required",
            "platform_write_enabled",
            "blocked_reasons",
            "confidence",
        ]
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for item in intents:
                row = {field: item.get(field, "") for field in fieldnames}
                row["blocked_reasons"] = " | ".join(item.get("blocked_reasons") or [])
                writer.writerow(row)

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        lines = [
            f"# Action Layer | {payload['report_date']}",
            "",
            "- Mode: dry_run_execution_intent",
            "- Platform write: disabled",
            "- Purpose: translate media-buyer decisions into auditable execution intents.",
            "",
            "## Summary",
            "",
            f"- Intents: {summary['intent_count']}",
            f"- Ready for approval: {summary['ready_for_approval_count']}",
            f"- Blocked: {summary['blocked_count']}",
            f"- Platform write enabled: {summary['platform_write_enabled']}",
            "",
            "## Execution Intents",
            "",
        ]
        if not payload["execution_intents"]:
            lines.append("- None.")
        else:
            lines.extend(
                [
                    "| Intent | Status | Platform | Operation | Target | Approval | Blocked reasons |",
                    "|---|---|---|---|---|---|---|",
                ]
            )
            for item in payload["execution_intents"]:
                reasons = "<br>".join(item.get("blocked_reasons") or [])
                lines.append(
                    f"| {item['intent_id']} | {item['execution_status']} | {item['platform']} | {item['operation']} | "
                    f"{item['target']} | {item['approval_required']} | {reasons} |"
                )
        lines.append("")
        return "\n".join(lines)


def _infer_platform(target: str, project: str) -> str:
    text = f"{target} {project}".lower()
    if "facebook" in text or re.search(r"\bp[0-9].*-(and|ios)-purchase", text):
        return "meta_ads"
    if "google" in text:
        return "google_ads"
    if "apple search" in text or "asa" in text:
        return "apple_search_ads"
    return "unknown"


def _operation(action_type: str) -> str:
    return {
        "scale_budget": "increase_budget_cap",
        "downweight_campaign": "decrease_budget_or_bid",
        "pause_candidate_review": "pause_candidate_review",
        "copy_creative_pattern": "create_creative_test_plan",
        "repair_structure": "create_repair_task",
        "hold_budget": "hold_no_write",
    }.get(action_type, "review_only")


def _parameters(action: dict[str, Any], operation: str) -> dict[str, Any]:
    max_change = float(action.get("max_change_pct") or 0.0)
    params: dict[str, Any] = {
        "max_change_pct": max_change,
        "priority": action.get("priority", 0.0),
        "recommendation": action.get("recommendation", ""),
    }
    if operation == "increase_budget_cap":
        params["budget_change_direction"] = "increase"
    elif operation == "decrease_budget_or_bid":
        params["budget_change_direction"] = "decrease"
    elif operation == "create_creative_test_plan":
        variant_count = int(action.get("variant_count_target") or 0)
        params["variant_count"] = variant_count if variant_count > 0 else 3
        params["primary_test_axis"] = str(action.get("primary_test_axis") or "")
        params["control_dimensions"] = list(action.get("control_dimensions") or [])
        params["baseline_asset_preview"] = list(action.get("baseline_asset_preview") or [])
    return params


def _blocked_reasons(action: dict[str, Any], platform: str, operation: str, readiness: dict[str, Any]) -> list[str]:
    reasons = list(readiness.get("blockers") or [])
    if platform == "unknown":
        reasons.append("platform_not_inferred")
    if operation in {"increase_budget_cap", "decrease_budget_or_bid"} and float(action.get("max_change_pct") or 0.0) <= 0:
        reasons.append("missing_budget_change_pct")
    if not action.get("approval_required"):
        reasons.append("approval_required_missing")
    if not action.get("rollback_conditions"):
        reasons.append("rollback_conditions_missing")
    return _unique(reasons)


def _unique(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        if item and item not in result:
            result.append(item)
    return result
