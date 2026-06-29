from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.approval_feedback_gate import ApprovalFeedbackGateBuilder
from market_ops.config import Settings
from market_ops.discovery_approval_state import (
    approval_is_rejected,
    approval_is_unblocked,
    approval_resolution_state,
    discovery_approval_input_path,
    load_discovery_approval_inputs,
    seed_discovery_approval_input_csv,
)
from market_ops.discovery_execution_packets import DiscoveryExecutionPacketsBuilder
from market_ops.discovery_experiment_cards import DiscoveryExperimentCardsBuilder
from market_ops.discovery_slot_status_board import DiscoverySlotStatusBoardBuilder


EXPECTED_MANUAL_APPROVAL_BLOCKERS = {
    "manual_discovery_test_plan_setup_required",
    "platform_write_disabled",
    "platform_credentials_missing",
    "approval_required",
    "operation_not_supported",
}


@dataclass(slots=True)
class DiscoveryApprovalPacketResult:
    markdown_path: Path
    json_path: Path
    csv_path: Path
    input_csv_path: Path
    passed: bool


class DiscoveryApprovalPacketBuilder:
    """Builds a discovery-specific approval surface that turns slot blockers into a guided manual approval flow."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> DiscoveryApprovalPacketResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self.build_payload(report_date)

        markdown_path = output_dir / f"discovery_approval_packet_{suffix}.md"
        json_path = output_dir / f"discovery_approval_packet_{suffix}.json"
        csv_path = output_dir / f"discovery_approval_packet_{suffix}.csv"
        input_csv_path = discovery_approval_input_path(output_dir, report_date)
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._write_csv(csv_path, payload["packets"])
        seed_discovery_approval_input_csv(input_csv_path, payload["packets"])
        return DiscoveryApprovalPacketResult(
            markdown_path=markdown_path,
            json_path=json_path,
            csv_path=csv_path,
            input_csv_path=input_csv_path,
            passed=bool(payload["passed"]),
        )

    def build_payload(self, report_date: date) -> dict[str, Any]:
        approval_payload = ApprovalFeedbackGateBuilder(self._settings).build_payload(report_date)
        status_payload = DiscoverySlotStatusBoardBuilder(self._settings).build_payload(report_date)
        execution_payload = DiscoveryExecutionPacketsBuilder(self._settings).build_payload(report_date)
        cards_payload = DiscoveryExperimentCardsBuilder(self._settings).build_payload(report_date)
        approval_input = load_discovery_approval_inputs(discovery_approval_input_path(self._settings.active_output_dir, report_date))

        rows_by_experiment: dict[str, list[dict[str, Any]]] = {}
        for row in status_payload.get("rows") or []:
            experiment_id = str(row.get("experiment_id") or "")
            if not experiment_id:
                continue
            rows_by_experiment.setdefault(experiment_id, []).append(row)

        execution_index = {str(item.get("experiment_id") or ""): item for item in execution_payload.get("packets") or []}
        card_index = {str(item.get("experiment_id") or ""): item for item in cards_payload.get("cards") or []}

        packets = [
            _approval_packet(
                item=item,
                rows=rows_by_experiment.get(str(item.get("experiment_id") or ""), []),
                execution_packet=execution_index.get(str(item.get("experiment_id") or ""), {}),
                card=card_index.get(str(item.get("experiment_id") or ""), {}),
                approval_input=approval_input.get(str(item.get("approval_id") or ""), {}),
                index=index,
            )
            for index, item in enumerate(_discovery_items(approval_payload.get("approval_items") or []), start=1)
        ]

        return {
            "report_date": report_date.isoformat(),
            "mode": "discovery_approval_packet",
            "passed": True,
            "rules": {
                "signal_only": True,
                "approval_gated": True,
                "no_platform_write": True,
                "manual_execution_only": True,
                "canonical_human_input": str(self._settings.active_output_dir / f"discovery_slot_result_input_{report_date.strftime('%Y%m%d')}.csv"),
                "manual_approval_input_file": str(discovery_approval_input_path(self._settings.active_output_dir, report_date)),
            },
            "summary": {
                "packet_count": len(packets),
                "approval_blocked_count": sum(1 for item in packets if item.get("approval_status") == "approval_blocked"),
                "manual_approval_ready_count": sum(1 for item in packets if item.get("approval_resolution_state") == "ready_for_manual_approval_decision"),
                "unexpected_blocker_count": sum(1 for item in packets if item.get("approval_resolution_state") == "unexpected_blockers"),
                "approved_for_manual_execution_count": sum(1 for item in packets if item.get("manual_approval_state") == "approved_for_manual_execution"),
                "rejected_count": sum(1 for item in packets if item.get("manual_approval_state") == "approval_rejected"),
                "pending_input_count": sum(1 for item in packets if item.get("manual_approval_state") == "approval_pending_input"),
                "slot_count": sum(len(item.get("slots") or []) for item in packets),
                "slot_approval_blocked_count": sum(int((item.get("status_breakdown") or {}).get("approval_blocked") or 0) for item in packets),
                "slot_ready_to_execute_count": sum(int((item.get("status_breakdown") or {}).get("ready_to_execute") or 0) for item in packets),
                "slot_awaiting_result_count": sum(int((item.get("status_breakdown") or {}).get("awaiting_result") or 0) for item in packets),
                "slot_learned_count": sum(int((item.get("status_breakdown") or {}).get("learned") or 0) for item in packets),
                "decision_waiting_packet_count": sum(1 for item in packets if item.get("decision_waiting")),
            },
            "packets": packets,
        }

    @staticmethod
    def _write_csv(path: Path, packets: list[dict[str, Any]]) -> None:
        fieldnames = [
            "approval_packet_id",
            "approval_id",
            "approval_status",
            "approval_resolution_state",
            "target",
            "slot_id",
            "slot_status",
            "change_focus",
            "variant_name",
            "baseline_anchor_preview",
            "approval_blockers",
            "execution_instruction",
            "next_after_approval",
            "manual_input_file",
        ]
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for packet in packets:
                for slot in packet.get("slots") or []:
                    writer.writerow(
                        {
                            "approval_packet_id": packet.get("approval_packet_id", ""),
                            "approval_id": packet.get("approval_id", ""),
                            "approval_status": packet.get("approval_status", ""),
                            "approval_resolution_state": packet.get("approval_resolution_state", ""),
                            "target": packet.get("target", ""),
                            "slot_id": slot.get("slot_id", ""),
                            "slot_status": slot.get("slot_status", ""),
                            "change_focus": slot.get("change_focus", ""),
                            "variant_name": slot.get("variant_name", ""),
                            "baseline_anchor_preview": slot.get("baseline_anchor_preview", ""),
                            "approval_blockers": " | ".join(packet.get("approval_blockers") or []),
                            "execution_instruction": slot.get("execution_instruction", ""),
                            "next_after_approval": slot.get("next_after_approval", ""),
                            "manual_input_file": packet.get("slot_manual_input_file", ""),
                        }
                    )

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload.get("summary") or {}
        lines = [
            f"# Discovery Approval Packet | {payload['report_date']}",
            "",
            "- Mode: discovery_approval_packet",
            "- Purpose: resolve discovery approval blockers into a manual approval and execution path.",
            "- Boundary: signal-only, approval-gated, no platform write.",
            f"- Canonical slot input: {(payload.get('rules') or {}).get('canonical_human_input', '')}",
            f"- Manual approval input: {(payload.get('rules') or {}).get('manual_approval_input_file', '')}",
            "",
            "## Summary",
            "",
            f"- Packets: {summary.get('packet_count', 0)}",
            f"- Approval blocked: {summary.get('approval_blocked_count', 0)}",
            f"- Manual approval ready: {summary.get('manual_approval_ready_count', 0)}",
            f"- Unexpected blockers: {summary.get('unexpected_blocker_count', 0)}",
            f"- Approved for manual execution: {summary.get('approved_for_manual_execution_count', 0)}",
            f"- Rejected: {summary.get('rejected_count', 0)}",
            f"- Pending approval input: {summary.get('pending_input_count', 0)}",
            f"- Slots: {summary.get('slot_count', 0)}",
            f"- Slot approval blocked: {summary.get('slot_approval_blocked_count', 0)}",
            f"- Slot ready to execute: {summary.get('slot_ready_to_execute_count', 0)}",
            f"- Slot awaiting result: {summary.get('slot_awaiting_result_count', 0)}",
            f"- Slot learned: {summary.get('slot_learned_count', 0)}",
            f"- Decision-waiting packets: {summary.get('decision_waiting_packet_count', 0)}",
            "",
            "## Packets",
            "",
        ]
        if not payload.get("packets"):
            lines.append("- None.")
        for item in payload.get("packets") or []:
            blockers = ", ".join(item.get("approval_blockers") or []) or "none"
            breakdown = item.get("status_breakdown") or {}
            lines.append(f"### {item['approval_packet_id']} | {item['target']}")
            lines.append(f"- Approval status: {item['approval_status']}")
            lines.append(f"- Manual approval state: {item['approval_resolution_state']}")
            lines.append(f"- Manual input state: {item['manual_approval_state']}")
            lines.append(f"- Requested execution: {item['requested_execution']}")
            lines.append(f"- Blockers: {blockers}")
            lines.append(
                f"- Slot breakdown: blocked={breakdown.get('approval_blocked', 0)} | ready={breakdown.get('ready_to_execute', 0)} | "
                f"awaiting_result={breakdown.get('awaiting_result', 0)} | learned={breakdown.get('learned', 0)}"
            )
            lines.append(
                f"- Decision unlock impact: waiting={item.get('decision_waiting')} | "
                f"matched_decisions={item.get('decision_wait_match_count', 0)} | "
                f"slots_to_resolve={', '.join(item.get('fastest_unlock_slot_ids') or []) or 'none'}"
            )
            impacted_targets = [
                f"{target.get('entity_type')}:{target.get('entity_id')} ({target.get('decision')})"
                for target in list(item.get("decision_wait_targets") or [])[:5]
                if str(target.get("entity_id") or "").strip()
            ]
            lines.append(f"- Reopened decisions: {', '.join(impacted_targets) or 'none'}")
            lines.append(f"- Slot input file: {item['slot_manual_input_file']}")
            lines.append(f"- Result template file: {item['result_template_file']}")
            lines.append(f"- Baselines: {', '.join(item.get('baseline_asset_preview') or []) or 'none'}")
            lines.append(f"- Controls fixed: {', '.join(item.get('control_dimensions') or []) or 'none'}")
            lines.append("- Unblock checklist:")
            for step in item.get("unblock_checklist") or []:
                lines.append(f"  - {step}")
            lines.append("- Slots:")
            for slot in item.get("slots") or []:
                missing = ", ".join(slot.get("missing_evidence") or []) or "none"
                lines.append(
                    f"  - {slot['slot_id']} | {slot['slot_status']} | {slot['variant_name']} | "
                    f"focus={slot['change_focus']} | unlocks={slot.get('decision_wait_match_count', 0)} | baseline={slot['baseline_anchor_preview']} | "
                    f"next={slot['next_after_approval']} | missing={missing}"
                )
            lines.append("")
        return "\n".join(lines)


def _discovery_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in items if int(item.get("slot_packet_count") or 0) > 0]


def _approval_packet(
    *,
    item: dict[str, Any],
    rows: list[dict[str, Any]],
    execution_packet: dict[str, Any],
    card: dict[str, Any],
    approval_input: dict[str, str],
    index: int,
) -> dict[str, Any]:
    slots = [_approval_slot(row, execution_packet) for row in rows]
    slots.sort(
        key=lambda slot: (
            -int(slot.get("decision_wait_match_count") or 0),
            str(slot.get("slot_id") or ""),
        )
    )
    status_breakdown = {
        status: sum(1 for slot in slots if str(slot.get("slot_status") or "") == status)
        for status in ("approval_blocked", "ready_to_execute", "awaiting_result", "learned", "in_review")
    }
    resolution_state = _approval_resolution_state(item)
    slot_input = _first_non_empty([slot.get("manual_input_file", "") for slot in slots], str(item.get("manual_input_file") or ""))
    decision_wait_entity_ids = _unique(
        [
            str(entity_id)
            for slot in slots
            for entity_id in list(slot.get("decision_wait_entity_ids") or [])
            if str(entity_id).strip()
        ]
    )
    decision_wait_targets = _unique_targets(
        [
            dict(target)
            for slot in slots
            for target in list(slot.get("decision_wait_targets") or [])
            if isinstance(target, dict)
        ]
    )
    return {
        "approval_packet_id": f"discovery_approval_{index:03d}",
        "approval_id": item.get("approval_id", ""),
        "experiment_id": item.get("experiment_id", ""),
        "target": item.get("target", ""),
        "approval_status": item.get("approval_status", ""),
        "approval_priority": item.get("approval_priority", ""),
        "approval_resolution_state": resolution_state,
        "manual_approval_state": approval_resolution_state(approval_input),
        "manual_approval_decision": str(approval_input.get("approval_decision") or ""),
        "manual_approved_by": str(approval_input.get("approved_by") or ""),
        "manual_approval_note": str(approval_input.get("approval_note") or ""),
        "requested_execution": item.get("requested_execution", ""),
        "approval_blockers": list(item.get("approval_blockers") or []),
        "slot_manual_input_file": slot_input,
        "result_template_file": item.get("result_template_file", ""),
        "baseline_asset_preview": list(item.get("baseline_asset_preview") or []),
        "control_dimensions": list(item.get("control_dimensions") or []),
        "variant_plan_summary": item.get("variant_plan_summary", "") or card.get("variant_plan_summary", ""),
        "learning_goal": item.get("learning_goal", "") or card.get("learning_goal", ""),
        "next_learning_step": item.get("next_learning_step", ""),
        "status_breakdown": status_breakdown,
        "unblock_checklist": _unblock_checklist(item, resolution_state, slot_input),
        "decision_waiting": any(bool(slot.get("decision_waiting")) for slot in slots),
        "decision_wait_match_count": len(decision_wait_entity_ids),
        "decision_wait_entity_ids": decision_wait_entity_ids[:20],
        "decision_wait_targets": decision_wait_targets[:20],
        "fastest_unlock_slot_ids": [
            str(slot.get("slot_id") or "")
            for slot in slots
            if int(slot.get("decision_wait_match_count") or 0) > 0
        ][:5],
        "slots": slots,
    }


def _approval_slot(row: dict[str, Any], execution_packet: dict[str, Any]) -> dict[str, Any]:
    slot_id = str(row.get("slot_id") or "")
    return {
        "slot_id": slot_id,
        "slot_status": row.get("slot_status", ""),
        "variant_name": row.get("variant_name", ""),
        "change_focus": row.get("change_focus", ""),
        "baseline_anchor_preview": row.get("baseline_anchor_preview", ""),
        "missing_evidence": list(row.get("missing_evidence") or []),
        "decision_waiting": bool(row.get("decision_waiting")),
        "decision_wait_match_count": int(row.get("decision_wait_match_count") or 0),
        "decision_wait_entity_ids": list(row.get("decision_wait_entity_ids") or [])[:20],
        "decision_wait_targets": list(row.get("decision_wait_targets") or [])[:10],
        "execution_instruction": _execution_instruction(execution_packet, slot_id),
        "next_after_approval": _next_after_approval(row),
        "manual_input_file": row.get("manual_input_file", ""),
    }


def _approval_resolution_state(item: dict[str, Any]) -> str:
    blockers = {str(value) for value in item.get("approval_blockers") or [] if str(value).strip()}
    if not blockers:
        return "approval_unblocked"
    if blockers.issubset(EXPECTED_MANUAL_APPROVAL_BLOCKERS):
        return "ready_for_manual_approval_decision"
    return "unexpected_blockers"


def _unblock_checklist(item: dict[str, Any], resolution_state: str, slot_input: str) -> list[str]:
    checklist = [
        "Approval here authorizes manual discovery setup only; it does not enable platform writes.",
    ]
    if resolution_state == "ready_for_manual_approval_decision":
        checklist.append("Treat connector and platform-write blockers as expected manual-only constraints for this discovery test.")
    else:
        checklist.append("Review whether any blocker is unexpected before approving manual execution.")
    checklist.append("Confirm the test direction, variant count, and fixed controls before any slot is created.")
    checklist.append(f"After approval, create the planned variants manually and update slot rows in {slot_input}.")
    checklist.append("Only after a slot is executed should execution_status, slot_result_summary, and success be filled.")
    for step in list(item.get("setup_instructions") or [])[:3]:
        if step not in checklist:
            checklist.append(str(step))
    return checklist


def _execution_instruction(execution_packet: dict[str, Any], slot_id: str) -> str:
    for slot in execution_packet.get("slot_packets") or []:
        if str(slot.get("slot_id") or "") == slot_id:
            return str(slot.get("recommended_operator_action") or "")
    return ""


def _next_after_approval(row: dict[str, Any]) -> str:
    status = str(row.get("slot_status") or "")
    if status == "approval_blocked":
        return "Create the planned variant manually, then set execution_status."
    if status == "ready_to_execute":
        return "Execute the planned variant and update execution_status."
    if status == "awaiting_result":
        return "Capture slot_result_summary and success for the executed slot."
    if status == "learned":
        return "Review whether the learned direction should expand or stop."
    return "Review missing evidence and continue the next discovery step."


def _first_non_empty(items: list[str], fallback: str) -> str:
    for item in items:
        value = str(item or "").strip()
        if value:
            return value
    return str(fallback or "")


def _unique(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        if item and item not in result:
            result.append(item)
    return result


def _unique_targets(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for item in items:
        key = (
            str(item.get("entity_type") or ""),
            str(item.get("entity_id") or ""),
            str(item.get("project") or ""),
            str(item.get("scope") or ""),
            str(item.get("decision") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(
            {
                "entity_type": key[0],
                "entity_id": key[1],
                "project": key[2],
                "scope": key[3],
                "decision": key[4],
            }
        )
    return result
