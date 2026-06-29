from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.experiment_execution_queue import ExperimentExecutionQueueBuilder


@dataclass(slots=True)
class ApprovalFeedbackGateResult:
    markdown_path: Path
    json_path: Path
    csv_path: Path
    passed: bool


class ApprovalFeedbackGateBuilder:
    """Builds the approval and result-capture contract for media-buyer experiments."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> ApprovalFeedbackGateResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self.build_payload(report_date)

        markdown_path = output_dir / f"approval_feedback_gate_{suffix}.md"
        json_path = output_dir / f"approval_feedback_gate_{suffix}.json"
        csv_path = output_dir / f"approval_feedback_gate_{suffix}.csv"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._write_csv(csv_path, payload["approval_items"])
        return ApprovalFeedbackGateResult(markdown_path=markdown_path, json_path=json_path, csv_path=csv_path, passed=bool(payload["passed"]))

    def build_payload(self, report_date: date) -> dict[str, Any]:
        queue_payload = ExperimentExecutionQueueBuilder(self._settings).build_payload(report_date)

        approval_items = [_approval_item(item, index) for index, item in enumerate(queue_payload.get("queue_items") or [], start=1)]
        approval_items.sort(key=_approval_sort_key)
        approval_blocked = [item for item in approval_items if item["approval_status"] == "approval_blocked"]
        ready_for_manual = [item for item in approval_items if item["approval_status"] == "ready_for_manual_approval"]
        ready_for_manual_execution = [item for item in approval_items if item["approval_status"] == "ready_for_manual_execution"]
        awaiting_result = [item for item in approval_items if item["approval_status"] == "awaiting_result_capture"]
        closed = [item for item in approval_items if item["approval_status"] == "closed"]
        critical_learning_blockers = [item for item in approval_items if item.get("approval_priority") == "critical_learning_blocker"]

        return {
            "report_date": report_date.isoformat(),
            "mode": "approval_and_feedback_gate",
            "passed": True,
            "rules": {
                "no_platform_write": True,
                "no_tracker_mutation": True,
                "approval_required_before_execution": True,
                "result_capture_required_for_learning": True,
            },
            "summary": {
                "approval_item_count": len(approval_items),
                "approval_blocked_count": len(approval_blocked),
                "ready_for_manual_approval_count": len(ready_for_manual),
                "ready_for_manual_execution_count": len(ready_for_manual_execution),
                "awaiting_result_capture_count": len(awaiting_result),
                "closed_count": len(closed),
                "critical_learning_blocker_count": len(critical_learning_blockers),
            },
            "approval_items": approval_items,
            "result_capture_template": _result_capture_template(),
        }

    @staticmethod
    def _write_csv(path: Path, items: list[dict[str, Any]]) -> None:
        fieldnames = [
            "approval_id",
            "approval_status",
            "queue_id",
            "experiment_id",
            "target",
            "requested_execution",
            "approval_blockers",
            "required_result_fields",
            "learning_close_condition",
            "approval_priority",
            "decision_waiting",
            "decision_wait_match_count",
            "manual_input_file",
            "result_template_file",
            "next_learning_step",
            "approval_ids",
            "slot_packet_count",
            "recommended_result_fields",
        ]
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for item in items:
                row = {field: item.get(field, "") for field in fieldnames}
                row["approval_blockers"] = " | ".join(item.get("approval_blockers") or [])
                row["required_result_fields"] = " | ".join(item.get("required_result_fields") or [])
                row["approval_ids"] = " | ".join(item.get("approval_ids") or [])
                row["recommended_result_fields"] = " | ".join(item.get("recommended_result_fields") or [])
                writer.writerow(row)

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        lines = [
            f"# Approval Feedback Gate | {payload['report_date']}",
            "",
            "- Mode: approval_and_feedback_gate",
            "- Purpose: define what must be approved and what must be captured after execution for the AI to learn.",
            "- Boundary: no platform write and no tracker mutation.",
            "",
            "## Summary",
            "",
            f"- Approval items: {summary['approval_item_count']}",
            f"- Approval blocked: {summary['approval_blocked_count']}",
            f"- Ready for manual approval: {summary['ready_for_manual_approval_count']}",
            f"- Ready for manual execution: {summary['ready_for_manual_execution_count']}",
            f"- Awaiting result capture: {summary['awaiting_result_capture_count']}",
            f"- Closed: {summary['closed_count']}",
            f"- Critical learning blockers: {summary['critical_learning_blocker_count']}",
            "",
            "## Approval Items",
            "",
        ]
        if not payload["approval_items"]:
            lines.append("- None.")
        for item in payload["approval_items"][:50]:
            blockers = ", ".join(item["approval_blockers"]) if item["approval_blockers"] else "none"
            fields = ", ".join(item["required_result_fields"]) if item["required_result_fields"] else "none"
            recommended = ", ".join(item.get("recommended_result_fields") or []) or "none"
            approval_ids = ",".join(item.get("approval_ids") or []) or item["approval_id"]
            decision_wait = "yes" if item.get("decision_waiting") else "no"
            lines.append(
                f"- {item['approval_id']} | {item['approval_status']} | {item['target']} | "
                f"priority={item.get('approval_priority') or 'standard'} | approvals={approval_ids} | "
                f"decision_wait={decision_wait} | blockers={blockers} | result_fields={fields} | recommended={recommended}"
            )

        lines.extend(["", "## Result Capture Template", ""])
        for field in payload["result_capture_template"]:
            lines.append(f"- {field['field']}: {field['purpose']}")
        lines.append("")
        return "\n".join(lines)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _approval_item(item: dict[str, Any], index: int) -> dict[str, Any]:
    queue_status = str(item.get("queue_status") or "")
    blockers = list(item.get("blocked_reasons") or [])
    approval_blockers = [blocker for blocker in blockers if blocker != "manual_evidence_capture_required"]
    required_fields = _required_result_fields(item)
    if queue_status == "completed":
        approval_status = "closed"
    elif queue_status == "waiting_result_capture":
        approval_status = "awaiting_result_capture"
    elif queue_status == "manual_execution_approved":
        approval_status = "ready_for_manual_execution"
    elif _manual_approval_state(item) == "approved_for_manual_execution":
        approval_status = "ready_for_manual_approval"
    elif approval_blockers:
        approval_status = "approval_blocked"
    else:
        approval_status = "ready_for_manual_approval"

    slot_packets = list(item.get("slot_packets") or [])
    approval_ids = [str(value) for value in item.get("approval_ids") or [] if str(value).strip()]
    required_fields = _unique([*required_fields, *[str(value) for value in item.get("required_result_fields") or [] if str(value).strip()]])
    recommended_fields = _recommended_result_fields(item)
    approval_priority = _approval_priority(item, approval_status, slot_packets)
    next_learning_step = str(item.get("next_learning_step") or "")
    close_condition = _learning_close_condition(item, slot_packets, required_fields)

    return {
        "approval_id": f"approval_{index:03d}",
        "approval_status": approval_status,
        "approval_priority": approval_priority,
        "queue_id": item.get("queue_id", ""),
        "experiment_id": item.get("experiment_id", ""),
        "hypothesis_id": item.get("hypothesis_id", ""),
        "target": item.get("target", ""),
        "requested_execution": item.get("intervention", ""),
        "platform": item.get("platform", "unknown"),
        "operation": item.get("operation", ""),
        "source": item.get("source", ""),
        "creative_id": item.get("creative_id", ""),
        "creative_name": item.get("creative_name", ""),
        "matched_intent_id": item.get("matched_intent_id", ""),
        "approval_blockers": approval_blockers,
        "manual_requirements": blockers,
        "manual_approval_state": _manual_approval_state(item),
        "manual_approval_decision": str(item.get("manual_approval_decision") or ""),
        "manual_approval_note": str(item.get("manual_approval_note") or ""),
        "setup_instructions": list(item.get("setup_instructions") or []),
        "approval_ids": approval_ids,
        "manual_input_file": item.get("manual_input_file", ""),
        "result_template_file": item.get("result_template_file", ""),
        "next_learning_step": next_learning_step,
        "decision_waiting": bool(item.get("decision_waiting")),
        "decision_wait_match_count": int(item.get("decision_wait_match_count") or 0),
        "decision_wait_entity_ids": list(item.get("decision_wait_entity_ids") or []),
        "decision_wait_contextual_pattern_keys": list(item.get("decision_wait_contextual_pattern_keys") or []),
        "project": item.get("project", ""),
        "channel": item.get("channel", ""),
        "country": item.get("country", ""),
        "test_type": item.get("test_type", ""),
        "learning_goal": item.get("learning_goal", ""),
        "baseline_creative_names": list(item.get("baseline_creative_names") or []),
        "baseline_creative_ids": list(item.get("baseline_creative_ids") or []),
        "baseline_asset_preview": list(item.get("baseline_asset_preview") or []),
        "baseline_asset_type": item.get("baseline_asset_type", ""),
        "variant_count_target": int(item.get("variant_count_target") or 0),
        "control_dimensions": list(item.get("control_dimensions") or []),
        "primary_test_axis": item.get("primary_test_axis", ""),
        "variant_plan_summary": item.get("variant_plan_summary", ""),
        "winner_material_asset_count": int(item.get("winner_material_asset_count") or 0),
        "discovery_prioritized_change_focuses": list(item.get("discovery_prioritized_change_focuses") or []),
        "winner_structure_bias": list(item.get("winner_structure_bias") or []),
        "structural_test_rationale": item.get("structural_test_rationale", ""),
        "slot_packet_count": len(slot_packets),
        "slot_packets": slot_packets,
        "active_discovery_change_focuses": list(item.get("active_discovery_change_focuses") or []),
        "active_discovery_pattern_keys": list(item.get("active_discovery_pattern_keys") or []),
        "required_result_fields": required_fields,
        "recommended_result_fields": recommended_fields,
        "success_metrics": list(item.get("success_metrics") or []),
        "rollback_metrics": list(item.get("rollback_metrics") or []),
        "learning_close_condition": close_condition,
        "result_capture_required": bool(item.get("result_capture_required", True)),
    }


def _required_result_fields(item: dict[str, Any]) -> list[str]:
    if _is_discovery_slot_learning_item(item):
        return [
            "execution_status",
            "actual_result_note",
            "success",
            "slot_result_summary",
        ]
    fields = ["execution_status", "actual_result_note", "success"]
    for field in item.get("missing_evidence") or []:
        if field in {"execution_confirmation", "actual_result_note"}:
            continue
        if field not in fields:
            fields.append(field)
    if "post_action_roi_or_roas" not in fields:
        fields.append("post_action_roi_or_roas")
    if str(item.get("experiment_type") or "") == "creative_copy_test":
        for field in ("post_action_ctr", "created_variant_count", "linked_new_creative_ids"):
            if field not in fields:
                fields.append(field)
    if str(item.get("source") or "") == "local_winner_prior":
        for field in ("post_action_cpi", "winner_variant_type", "winner_baseline_asset", "learning_note"):
            if field not in fields:
                fields.append(field)
    if str(item.get("experiment_type") or "") == "discovery_creative_test_plan" or str(item.get("source") or "") == "discovery_backlog":
        for field in (
            "post_action_ctr",
            "post_action_cpi",
            "created_variant_count",
            "linked_new_creative_ids",
            "winner_variant_type",
            "discovery_test_slot",
            "baseline_asset_group",
            "variant_plan_summary",
            "slot_execution_plan",
            "slot_learning_question",
            "slot_result_summary",
            "learning_note",
        ):
            if field not in fields:
                fields.append(field)
    if str(item.get("experiment_type") or "") == "evidence_capture":
        for field in (
            "captured_cpi",
            "captured_retention_d1",
            "captured_arpu",
            "captured_arppu",
            "captured_payback_d7",
            "captured_fatigue_evidence",
            "evidence_source_link",
        ):
            if field not in fields:
                fields.append(field)
    return fields


def _recommended_result_fields(item: dict[str, Any]) -> list[str]:
    if _is_discovery_slot_learning_item(item):
        return [
            "post_action_roi_or_roas",
            "post_action_ctr",
            "post_action_cpi",
            "created_variant_count",
            "linked_new_creative_ids",
            "winner_variant_type",
            "discovery_test_slot",
            "baseline_asset_group",
            "variant_plan_summary",
            "slot_execution_plan",
            "slot_learning_question",
            "learning_note",
        ]
    return []


def _is_discovery_slot_learning_item(item: dict[str, Any]) -> bool:
    return bool(item.get("slot_packets")) and (
        str(item.get("experiment_type") or "") == "discovery_creative_test_plan"
        or str(item.get("source") or "") == "discovery_backlog"
    )


def _approval_priority(item: dict[str, Any], approval_status: str, slot_packets: list[dict[str, Any]]) -> str:
    if item.get("learning_priority_label") == "critical_learning_blocker" or (
        slot_packets and approval_status in {"approval_blocked", "awaiting_result_capture", "ready_for_manual_approval", "ready_for_manual_execution"}
    ):
        return "critical_learning_blocker"
    if item.get("learning_priority_label") == "high_learning_priority":
        return "high_learning_priority"
    return "standard"


def _learning_close_condition(item: dict[str, Any], slot_packets: list[dict[str, Any]], required_fields: list[str]) -> str:
    if slot_packets:
        slot_ids = ", ".join(str(packet.get("slot_id") or "") for packet in slot_packets if str(packet.get("slot_id") or "").strip())
        recommended = _recommended_result_fields(item)
        recommended_text = f" Recommended enrichments: {', '.join(recommended)}." if recommended else ""
        return (
            "Approve execution, then capture slot-level outcomes for "
            f"{slot_ids or 'all slots'} with {', '.join(required_fields)} so reusable discovery patterns can be learned."
            f"{recommended_text}"
        )
    return "Set execution_status, actual_result_note, post metrics, and success=true/false."


def _manual_approval_state(item: dict[str, Any]) -> str:
    return str(item.get("manual_approval_state") or "")


def _approval_sort_key(item: dict[str, Any]) -> tuple[int, int, str]:
    priority_rank = {
        "critical_learning_blocker": 0,
        "high_learning_priority": 1,
        "standard": 2,
    }.get(str(item.get("approval_priority") or "standard"), 2)
    status_rank = {
        "approval_blocked": 0,
        "ready_for_manual_approval": 1,
        "ready_for_manual_execution": 2,
        "awaiting_result_capture": 3,
        "closed": 4,
    }.get(str(item.get("approval_status") or "closed"), 4)
    return (priority_rank, status_rank, str(item.get("target") or ""))


def _unique(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        if item and item not in result:
            result.append(item)
    return result


def _result_capture_template() -> list[dict[str, str]]:
    return [
        {"field": "approval_id", "purpose": "Links a manual approval/result row back to this gate."},
        {"field": "execution_status", "purpose": "One of executed, skipped, failed_to_execute."},
        {"field": "actual_result_note", "purpose": "Human-readable result note with date and context."},
        {"field": "success", "purpose": "true or false after checking success and rollback metrics."},
        {"field": "post_action_roi_or_roas", "purpose": "ROI/ROAS after the experiment window."},
        {"field": "post_action_ctr", "purpose": "CTR after the experiment window when relevant."},
        {"field": "post_action_cpi", "purpose": "CPI after the experiment window when relevant."},
        {"field": "created_variant_count", "purpose": "Number of creative variants created for creative tests."},
        {"field": "linked_new_creative_ids", "purpose": "New creative IDs generated by the test."},
        {"field": "winner_variant_type", "purpose": "Variant style used for winner-material tests, for example first3s_swap or image_to_motion."},
        {"field": "winner_baseline_asset", "purpose": "The original winner asset used as the control in the test."},
        {"field": "discovery_test_slot", "purpose": "Pattern-level discovery slot, for example hook_clone_facebook_global."},
        {"field": "baseline_asset_group", "purpose": "Comma-separated baseline creative IDs or names grouped into this discovery test."},
        {"field": "variant_plan_summary", "purpose": "Short note describing the planned variants, for example 3 hook variants or 2 motion variants."},
        {"field": "slot_execution_plan", "purpose": "Optional compact summary of slot names or slot focuses executed in this discovery test."},
        {"field": "slot_learning_question", "purpose": "Optional question the test was meant to answer, for example whether hook_rewrite beats cta_swap."},
        {"field": "slot_result_summary", "purpose": "Optional compact slot-level outcome summary, for example v01 won CTR and v03 improved CPI."},
        {"field": "learning_note", "purpose": "What the team learned about why the winner did or did not replicate."},
        {"field": "captured_cpi", "purpose": "CPI evidence captured for data-blocked lifecycle decisions."},
        {"field": "captured_retention_d1", "purpose": "D1 retention evidence captured for data-blocked lifecycle decisions."},
        {"field": "captured_arpu", "purpose": "ARPU evidence captured for data-blocked lifecycle decisions."},
        {"field": "captured_payback_d7", "purpose": "D7 payback evidence captured for data-blocked lifecycle decisions."},
        {"field": "captured_fatigue_evidence", "purpose": "Fatigue evidence or refreshed trend note for data-blocked lifecycle decisions."},
        {"field": "evidence_source_link", "purpose": "Local file, Feishu sheet, or source path proving the captured evidence."},
    ]
