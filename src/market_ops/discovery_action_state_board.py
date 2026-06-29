from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.discovery_action_queue import DiscoveryActionQueueBuilder
from market_ops.discovery_learning_state_board import DiscoveryLearningStateBoardBuilder
from market_ops.discovery_slot_operator_packet import DiscoverySlotOperatorPacketBuilder
from market_ops.experiment_result_ingestion import ExperimentResultIngestionBuilder


@dataclass(slots=True)
class DiscoveryActionStateBoardResult:
    markdown_path: Path
    json_path: Path
    passed: bool


class DiscoveryActionStateBoardBuilder:
    """Map discovery action queue items to their current workflow state and next transition."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> DiscoveryActionStateBoardResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self.build_payload(report_date)

        markdown_path = output_dir / f"discovery_action_state_board_{suffix}.md"
        json_path = output_dir / f"discovery_action_state_board_{suffix}.json"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return DiscoveryActionStateBoardResult(
            markdown_path=markdown_path,
            json_path=json_path,
            passed=bool(payload["passed"]),
        )

    def build_payload(self, report_date: date) -> dict[str, Any]:
        queue_payload = DiscoveryActionQueueBuilder(self._settings).build_payload(report_date)
        operator_payload = DiscoverySlotOperatorPacketBuilder(self._settings).build_payload(report_date)
        learning_payload = DiscoveryLearningStateBoardBuilder(self._settings).build_payload(report_date)
        result_payload = ExperimentResultIngestionBuilder(self._settings).build_payload(report_date)

        operator_index = {
            str(packet.get("approval_id") or ""): {
                "packet": packet,
                "slots": {
                    str(slot.get("slot_id") or ""): slot
                    for slot in packet.get("slots") or []
                    if str(slot.get("slot_id") or "").strip()
                },
            }
            for packet in operator_payload.get("packets") or []
            if str(packet.get("approval_id") or "").strip()
        }
        learning_index = {
            str(packet.get("approval_id") or ""): {
                "packet": packet,
                "slots": {
                    str(slot.get("slot_id") or ""): slot
                    for slot in packet.get("slot_states") or []
                    if str(slot.get("slot_id") or "").strip()
                },
            }
            for packet in learning_payload.get("packets") or []
            if str(packet.get("approval_id") or "").strip()
        }
        result_index = {
            str(item.get("approval_id") or ""): item
            for item in result_payload.get("result_rows") or []
            if str(item.get("approval_id") or "").strip()
        }

        items = [
            _state_item(
                action=action,
                operator_binding=operator_index.get(str(action.get("approval_id") or ""), {}),
                learning_binding=learning_index.get(str(action.get("approval_id") or ""), {}),
                result_row=result_index.get(str(action.get("approval_id") or ""), {}),
            )
            for action in queue_payload.get("actions") or []
        ]
        items.sort(
            key=lambda item: (
                int(item.get("queue_rank") or 0),
                int(item.get("slot_rank") or 0),
                str(item.get("approval_id") or ""),
            )
        )

        return {
            "report_date": report_date.isoformat(),
            "mode": "discovery_action_state_board",
            "passed": True,
            "rules": {
                "signal_only": True,
                "approval_gated": True,
                "manual_execution_only": True,
                "no_platform_write": True,
                "purpose": "Track each discovery action from approval to execution, result capture, and learning closure.",
            },
            "summary": {
                "item_count": len(items),
                "awaiting_approval_input_count": sum(1 for item in items if item.get("action_state") == "awaiting_approval_input"),
                "blocked_by_approval_count": sum(1 for item in items if item.get("action_state") == "blocked_by_approval"),
                "ready_to_execute_count": sum(1 for item in items if item.get("action_state") == "ready_to_execute"),
                "awaiting_result_capture_count": sum(1 for item in items if item.get("action_state") == "awaiting_result_capture"),
                "ready_for_learning_review_count": sum(1 for item in items if item.get("action_state") == "ready_for_learning_review"),
                "ready_for_pattern_memory_close_count": sum(1 for item in items if item.get("action_state") == "ready_for_pattern_memory_close"),
                "awaiting_parent_result_close_count": sum(1 for item in items if item.get("action_state") == "awaiting_parent_result_close"),
                "closed_count": sum(1 for item in items if item.get("action_state") == "closed"),
                "rejected_count": sum(1 for item in items if item.get("action_state") == "approval_rejected"),
            },
            "items": items,
        }

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload.get("summary") or {}
        lines = [
            f"# Discovery Action State Board | {payload['report_date']}",
            "",
            "- Mode: discovery_action_state_board",
            "- Purpose: show the current state and next transition for every discovery action item.",
            "- Boundary: signal-only, approval-gated, manual execution only, no platform write.",
            "",
            "## Summary",
            "",
            f"- Items: {summary.get('item_count', 0)}",
            f"- Awaiting approval input: {summary.get('awaiting_approval_input_count', 0)}",
            f"- Blocked by approval: {summary.get('blocked_by_approval_count', 0)}",
            f"- Ready to execute: {summary.get('ready_to_execute_count', 0)}",
            f"- Awaiting result capture: {summary.get('awaiting_result_capture_count', 0)}",
            f"- Ready for learning review: {summary.get('ready_for_learning_review_count', 0)}",
            f"- Ready for pattern memory close: {summary.get('ready_for_pattern_memory_close_count', 0)}",
            f"- Awaiting parent result close: {summary.get('awaiting_parent_result_close_count', 0)}",
            f"- Closed: {summary.get('closed_count', 0)}",
            f"- Rejected: {summary.get('rejected_count', 0)}",
            "",
            "## Items",
            "",
        ]
        if not payload.get("items"):
            lines.append("- None.")
        else:
            lines.extend(
                [
                    "| Queue | Type | State | Approval | Slot | Next transition |",
                    "|---:|---|---|---|---|---|",
                ]
            )
            for item in payload.get("items") or []:
                lines.append(
                    f"| {item['queue_rank']} | {item['action_type']} | {item['action_state']} | {item['approval_id']} | "
                    f"{item['slot_id'] or '-'} | {item['next_transition']} |"
                )
        lines.append("")
        return "\n".join(lines)


def _state_item(
    *,
    action: dict[str, Any],
    operator_binding: dict[str, Any],
    learning_binding: dict[str, Any],
    result_row: dict[str, Any],
) -> dict[str, Any]:
    approval_id = str(action.get("approval_id") or "")
    slot_id = str(action.get("slot_id") or "")
    action_type = str(action.get("action_type") or "")
    operator_slot = dict((operator_binding.get("slots") or {}).get(slot_id) or {})
    operator_packet = dict(operator_binding.get("packet") or {})
    learning_packet = dict(learning_binding.get("packet") or {})
    learning_slot = dict((learning_binding.get("slots") or {}).get(slot_id) or {})
    action_state = _action_state(
        action_type=action_type,
        manual_approval_state=str(result_row.get("manual_approval_state") or ""),
        slot_status=str(operator_slot.get("slot_status") or ""),
        learning_state=str(learning_packet.get("learning_state") or ""),
        slot_learning_state=str(learning_slot.get("slot_learning_state") or ""),
        parent_result_state=str(result_row.get("result_state") or ""),
        parent_close_state=str(result_row.get("parent_close_state") or ""),
    )
    return {
        "action_id": action.get("action_id", ""),
        "queue_rank": int(action.get("queue_rank") or 0),
        "slot_rank": int(action.get("slot_rank") or 0),
        "action_type": action_type,
        "approval_id": approval_id,
        "experiment_id": action.get("experiment_id", ""),
        "target": action.get("target", ""),
        "slot_id": slot_id,
        "priority_label": action.get("priority_label", ""),
        "action_state": action_state,
        "manual_approval_state": str(result_row.get("manual_approval_state") or ""),
        "approval_status": str(result_row.get("approval_status") or operator_packet.get("approval_status") or ""),
        "slot_status": str(operator_slot.get("slot_status") or ""),
        "learning_state": str(learning_packet.get("learning_state") or ""),
        "slot_learning_state": str(learning_slot.get("slot_learning_state") or ""),
        "slot_result_summary": str(learning_slot.get("slot_result_summary") or ""),
        "slot_success": learning_slot.get("slot_success"),
        "parent_result_state": str(result_row.get("result_state") or ""),
        "parent_close_state": str(result_row.get("parent_close_state") or ""),
        "parent_close_missing_fields": list(result_row.get("parent_close_missing_fields") or []),
        "parent_success": result_row.get("success"),
        "human_surface": action.get("human_surface", ""),
        "human_work_item": action.get("human_work_item", ""),
        "next_transition": _next_transition(
            action_state=action_state,
            action_type=action_type,
            manual_approval_state=str(result_row.get("manual_approval_state") or ""),
            operator_slot=operator_slot,
            learning_packet=learning_packet,
            learning_slot=learning_slot,
            result_row=result_row,
        ),
        "blocking_reason": _blocking_reason(
            action_state=action_state,
            manual_approval_state=str(result_row.get("manual_approval_state") or ""),
            operator_slot=operator_slot,
            result_row=result_row,
        ),
        "learning_question": str((operator_slot.get("learning_binding") or {}).get("learning_question") or ""),
        "missing_evidence": list(operator_slot.get("missing_evidence") or []),
        "decision_wait_match_count": int(action.get("decision_wait_match_count") or 0),
        "reopened_decision_targets": list(action.get("reopened_decision_targets") or [])[:10],
    }


def _action_state(
    *,
    action_type: str,
    manual_approval_state: str,
    slot_status: str,
    learning_state: str,
    slot_learning_state: str,
    parent_result_state: str,
    parent_close_state: str,
) -> str:
    if action_type == "approval_input":
        if manual_approval_state == "approved_for_manual_execution":
            return "closed"
        if manual_approval_state == "approval_rejected":
            return "approval_rejected"
        return "awaiting_approval_input"
    if manual_approval_state == "approval_rejected":
        return "approval_rejected"
    if slot_status == "approval_blocked":
        return "blocked_by_approval"
    if action_type == "create_variant":
        if slot_status == "ready_to_execute":
            return "ready_to_execute"
        if slot_status == "awaiting_result":
            return "awaiting_result_capture"
        if slot_status == "learned":
            if learning_state == "ready_for_pattern_memory":
                return "ready_for_pattern_memory_close"
            if learning_state == "pattern_memory_closed":
                return "closed"
            return "ready_for_learning_review"
    if action_type == "capture_result":
        if slot_learning_state == "closed":
            if learning_state == "ready_for_pattern_memory":
                return "ready_for_pattern_memory_close"
            if learning_state == "pattern_memory_closed":
                return "closed"
            return "ready_for_learning_review"
        return "awaiting_result_capture"
    if action_type == "review_learning":
        if learning_state == "pattern_memory_closed":
            return "closed"
        if learning_state == "ready_for_pattern_memory":
            return "ready_for_pattern_memory_close"
        return "ready_for_learning_review"
    if action_type == "close_parent_result":
        if manual_approval_state == "approval_pending_input":
            return "blocked_by_approval"
        if parent_close_state == "closed" or learning_state == "pattern_memory_closed":
            return "closed"
        if parent_close_state == "needs_parent_close":
            return "awaiting_parent_result_close"
        if learning_state == "ready_for_pattern_memory":
            return "ready_for_pattern_memory_close"
        return "ready_for_learning_review"
    if slot_status == "learned":
        return "ready_for_learning_review"
    return "blocked_by_approval"


def _next_transition(
    *,
    action_state: str,
    action_type: str,
    manual_approval_state: str,
    operator_slot: dict[str, Any],
    learning_packet: dict[str, Any],
    learning_slot: dict[str, Any],
    result_row: dict[str, Any],
) -> str:
    if action_state == "awaiting_approval_input":
        return "Fill approval_decision and approved_by in the discovery approval input."
    if action_state == "approval_rejected":
        return "Review the rejected experiment direction before reopening any slot."
    if action_state == "blocked_by_approval":
        if action_type == "close_parent_result":
            return "Resolve approval input first before parent result closure can begin."
        return "Resolve approval input first so the slot can move into execution."
    if action_state == "ready_to_execute":
        return str(operator_slot.get("next_operator_step") or "Create and launch the planned variant, then update execution_status.")
    if action_state == "awaiting_result_capture":
        return "Fill slot_result_summary and success for the executed slot in the slot input file."
    if action_state == "ready_for_learning_review":
        if action_type == "close_parent_result":
            return "Wait until slot execution and win/loss capture are complete before closing the parent result row."
        if str(learning_slot.get("slot_learning_state") or "") == "closed":
            return "Review the learned outcome and decide whether this slot direction should expand or retire."
        return str(learning_packet.get("next_update_required") or "Review the learning outcome and decide whether the slot direction should expand or retire.")
    if action_state == "ready_for_pattern_memory_close":
        return str(learning_packet.get("next_update_required") or "Close the parent result row fields so pattern memory can be promoted.")
    if action_state == "awaiting_parent_result_close":
        missing = list(result_row.get("parent_close_missing_fields") or [])
        if missing:
            return f"Fill {', '.join(missing)} in the parent result row."
        return "Fill created_variant_count, linked_new_creative_ids, and learning_note in the parent result row."
    if action_state == "closed":
        if action_type == "approval_input":
            return "Approval is resolved; move to the next queued slot action."
        if str(result_row.get("parent_close_state") or "") == "closed":
            return "No update required; this action is already absorbed into learning closure."
        return "No update required."
    return str(operator_slot.get("next_operator_step") or "")


def _blocking_reason(
    *,
    action_state: str,
    manual_approval_state: str,
    operator_slot: dict[str, Any],
    result_row: dict[str, Any],
) -> str:
    if action_state == "awaiting_approval_input":
        return "manual_approval_pending"
    if action_state == "approval_rejected":
        return "manual_approval_rejected"
    if action_state == "blocked_by_approval":
        missing = list(operator_slot.get("missing_evidence") or [])
        if action_state == "blocked_by_approval" and manual_approval_state == "approval_pending_input":
            return "approval_unblocked_missing"
        if "approval_unblocked" in missing:
            return "approval_unblocked_missing"
        return "approval_gate_not_cleared"
    if action_state == "awaiting_result_capture":
        missing = list(operator_slot.get("missing_evidence") or [])
        if "slot_result_summary" in missing or "success" in missing:
            return "slot_result_fields_missing"
        return "result_capture_pending"
    if action_state == "awaiting_parent_result_close":
        return "parent_result_fields_missing"
    if action_state == "ready_for_pattern_memory_close" and str(result_row.get("parent_close_state") or "") != "needs_parent_close":
        return "parent_result_row_not_closed"
    return ""
