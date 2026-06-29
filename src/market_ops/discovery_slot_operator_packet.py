from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.discovery_approval_state import discovery_approval_input_path
from market_ops.discovery_experiment_cards import DiscoveryExperimentCardsBuilder
from market_ops.discovery_execution_packets import DiscoveryExecutionPacketsBuilder
from market_ops.discovery_learning_packets import DiscoveryLearningPacketsBuilder
from market_ops.discovery_result_capture_packets import DiscoveryResultCapturePacketsBuilder
from market_ops.discovery_slot_status_board import DiscoverySlotStatusBoardBuilder


@dataclass(slots=True)
class DiscoverySlotOperatorPacketResult:
    markdown_path: Path
    json_path: Path
    passed: bool


class DiscoverySlotOperatorPacketBuilder:
    """Builds an operator-facing guided packet for discovery slot execution and result capture."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> DiscoverySlotOperatorPacketResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self.build_payload(report_date)

        markdown_path = output_dir / f"discovery_slot_operator_packet_{suffix}.md"
        json_path = output_dir / f"discovery_slot_operator_packet_{suffix}.json"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return DiscoverySlotOperatorPacketResult(markdown_path=markdown_path, json_path=json_path, passed=bool(payload["passed"]))

    def build_payload(self, report_date: date) -> dict[str, Any]:
        cards_payload = DiscoveryExperimentCardsBuilder(self._settings).build_payload(report_date)
        execution_payload = DiscoveryExecutionPacketsBuilder(self._settings).build_payload(report_date)
        learning_payload = DiscoveryLearningPacketsBuilder(self._settings).build_payload(report_date)
        capture_payload = DiscoveryResultCapturePacketsBuilder(self._settings).build_payload(report_date)
        status_payload = DiscoverySlotStatusBoardBuilder(self._settings).build_payload(report_date)

        card_index = {str(item.get("experiment_id") or ""): item for item in cards_payload.get("cards") or []}
        execution_index = {str(item.get("experiment_id") or ""): item for item in execution_payload.get("packets") or []}
        learning_index = {str(item.get("experiment_id") or ""): item for item in learning_payload.get("packets") or []}
        rows_by_experiment: dict[str, list[dict[str, Any]]] = {}
        for row in status_payload.get("rows") or []:
            experiment_id = str(row.get("experiment_id") or "")
            if not experiment_id:
                continue
            rows_by_experiment.setdefault(experiment_id, []).append(row)

        packets = [
            _operator_packet(
                capture_packet=item,
                rows=rows_by_experiment.get(str(item.get("experiment_id") or ""), []),
                card=card_index.get(str(item.get("experiment_id") or ""), {}),
                execution_packet=execution_index.get(str(item.get("experiment_id") or ""), {}),
                learning_packet=learning_index.get(str(item.get("experiment_id") or ""), {}),
                index=index,
            )
            for index, item in enumerate(capture_payload.get("packets") or [], start=1)
        ]

        return {
            "report_date": report_date.isoformat(),
            "mode": "discovery_slot_operator_packet",
            "passed": True,
            "rules": {
                "signal_only": True,
                "approval_gated": True,
                "no_platform_write": True,
                "canonical_human_input": str(self._settings.active_output_dir / f"discovery_slot_result_input_{report_date.strftime('%Y%m%d')}.csv"),
                "manual_approval_input_file": str(discovery_approval_input_path(self._settings.active_output_dir, report_date)),
            },
            "summary": {
                "packet_count": len(packets),
                "slot_count": sum(len(item.get("slots") or []) for item in packets),
                "approval_blocked_count": sum(int((item.get("status_breakdown") or {}).get("approval_blocked") or 0) for item in packets),
                "ready_to_execute_count": sum(int((item.get("status_breakdown") or {}).get("ready_to_execute") or 0) for item in packets),
                "awaiting_result_count": sum(int((item.get("status_breakdown") or {}).get("awaiting_result") or 0) for item in packets),
                "learned_count": sum(int((item.get("status_breakdown") or {}).get("learned") or 0) for item in packets),
                "approval_pending_input_count": sum(1 for item in packets if item.get("manual_approval_state") == "approval_pending_input"),
                "approved_for_manual_execution_count": sum(1 for item in packets if item.get("manual_approval_state") == "approved_for_manual_execution"),
                "approval_rejected_count": sum(1 for item in packets if item.get("manual_approval_state") == "approval_rejected"),
                "decision_waiting_packet_count": sum(1 for item in packets if item.get("decision_waiting")),
            },
            "packets": packets,
        }

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload.get("summary") or {}
        lines = [
            f"# Discovery Slot Operator Packet | {payload['report_date']}",
            "",
            "- Mode: discovery_slot_operator_packet",
            "- Purpose: compress discovery slot execution, result capture, and learning context into one guided operator surface.",
            "- Boundary: signal-only, approval-gated, no platform write.",
            f"- Manual approval input: {(payload.get('rules') or {}).get('manual_approval_input_file', '')}",
            f"- Canonical human input: {(payload.get('rules') or {}).get('canonical_human_input', '')}",
            "",
            "## Summary",
            "",
            f"- Packets: {summary.get('packet_count', 0)}",
            f"- Slots: {summary.get('slot_count', 0)}",
            f"- Approval blocked: {summary.get('approval_blocked_count', 0)}",
            f"- Ready to execute: {summary.get('ready_to_execute_count', 0)}",
            f"- Awaiting result: {summary.get('awaiting_result_count', 0)}",
            f"- Learned: {summary.get('learned_count', 0)}",
            f"- Pending approval input: {summary.get('approval_pending_input_count', 0)}",
            f"- Approved for manual execution: {summary.get('approved_for_manual_execution_count', 0)}",
            f"- Approval rejected: {summary.get('approval_rejected_count', 0)}",
            f"- Decision-waiting packets: {summary.get('decision_waiting_packet_count', 0)}",
            "",
            "## Packets",
            "",
        ]
        if not payload.get("packets"):
            lines.append("- None.")
        for item in payload.get("packets") or []:
            breakdown = item.get("status_breakdown") or {}
            lines.append(f"### {item['operator_packet_id']} | {item['target']}")
            lines.append(f"- Approval: {item['approval_status']}")
            lines.append(f"- Manual approval state: {item['manual_approval_state']}")
            lines.append(f"- Next human surface: {item['next_human_surface']}")
            lines.append(
                f"- Status breakdown: blocked={breakdown.get('approval_blocked', 0)} | ready={breakdown.get('ready_to_execute', 0)} | "
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
            lines.append(f"- Manual approval input file: {item['manual_approval_input_file']}")
            lines.append(f"- Slot input file: {item['slot_manual_input_file']}")
            lines.append(f"- Result template file: {item['result_template_file']}")
            lines.append(f"- Variant brief: {item['variant_plan_summary']}")
            lines.append("- Checklist:")
            for step in item.get("operator_checklist") or []:
                lines.append(f"  - {step}")
            lines.append("- Slots:")
            for slot in item.get("slots") or []:
                missing = ", ".join(slot.get("missing_evidence") or []) or "none"
                lines.append(
                    f"  - {slot['slot_id']} | {slot['slot_status']} | {slot['variant_name']} | "
                    f"focus={slot['change_focus']} | unlocks={slot.get('decision_wait_match_count', 0)} | baseline={slot['baseline_anchor_preview']} | next={slot['next_operator_step']} | missing={missing}"
                )
            lines.append("")
        return "\n".join(lines)


def _operator_packet(
    *,
    capture_packet: dict[str, Any],
    rows: list[dict[str, Any]],
    card: dict[str, Any],
    execution_packet: dict[str, Any],
    learning_packet: dict[str, Any],
    index: int,
) -> dict[str, Any]:
    slots = [_operator_slot(row, execution_packet, learning_packet) for row in rows]
    slots.sort(
        key=lambda slot: (
            -int(slot.get("decision_wait_match_count") or 0),
            str(slot.get("slot_id") or ""),
        )
    )
    status_breakdown = {
        status: sum(1 for item in slots if str(item.get("slot_status") or "") == status)
        for status in ("approval_blocked", "ready_to_execute", "awaiting_result", "learned", "in_review")
    }
    manual_approval_input_file = _first_manual_approval_input(rows)
    manual_approval_state = _packet_manual_approval_state(rows)
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
        "operator_packet_id": f"operator_packet_{index:03d}",
        "approval_id": capture_packet.get("approval_id", ""),
        "experiment_id": capture_packet.get("experiment_id", ""),
        "target": capture_packet.get("target", ""),
        "approval_status": _packet_approval_status(rows, capture_packet),
        "manual_approval_state": manual_approval_state,
        "manual_approval_decision": _packet_manual_approval_decision(rows),
        "manual_approval_note": _packet_manual_approval_note(rows),
        "manual_approval_input_file": manual_approval_input_file,
        "next_human_surface": _next_human_surface(manual_approval_state, manual_approval_input_file, str(capture_packet.get("slot_manual_input_file", ""))),
        "slot_manual_input_file": capture_packet.get("slot_manual_input_file", ""),
        "result_template_file": capture_packet.get("result_template_file", ""),
        "variant_plan_summary": card.get("variant_plan_summary", ""),
        "learning_goal": card.get("learning_goal", ""),
        "operator_checklist": _operator_checklist(card, capture_packet, manual_approval_state, manual_approval_input_file),
        "status_breakdown": status_breakdown,
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


def _operator_slot(row: dict[str, Any], execution_packet: dict[str, Any], learning_packet: dict[str, Any]) -> dict[str, Any]:
    slot_id = str(row.get("slot_id") or "")
    slot_instruction = _execution_instruction(execution_packet, slot_id)
    return {
        "slot_id": slot_id,
        "slot_status": row.get("slot_status", ""),
        "variant_name": row.get("variant_name", ""),
        "change_focus": row.get("change_focus", ""),
        "learning_question": row.get("learning_question", ""),
        "baseline_anchor_preview": row.get("baseline_anchor_preview", ""),
        "required_fields": list(row.get("required_fields") or []),
        "recommended_fields": list(row.get("recommended_fields") or []),
        "missing_evidence": list(row.get("missing_evidence") or []),
        "decision_waiting": bool(row.get("decision_waiting")),
        "decision_wait_match_count": int(row.get("decision_wait_match_count") or 0),
        "decision_wait_entity_ids": list(row.get("decision_wait_entity_ids") or [])[:20],
        "decision_wait_targets": list(row.get("decision_wait_targets") or [])[:10],
        "slot_result_example": row.get("slot_result_example", ""),
        "next_operator_step": _next_operator_step(row),
        "execution_instruction": slot_instruction,
        "learning_binding": _learning_binding(learning_packet, slot_id),
        "manual_input_file": row.get("manual_input_file", ""),
    }


def _operator_checklist(
    card: dict[str, Any],
    capture_packet: dict[str, Any],
    manual_approval_state: str,
    manual_approval_input_file: str,
) -> list[str]:
    checklist: list[str] = []
    if manual_approval_state == "approved_for_manual_execution":
        checklist.append("Work from the slot input file first; approval is already resolved for manual execution.")
    elif manual_approval_state == "approval_rejected":
        checklist.append("Review the rejection reason in the discovery approval input before changing any slot plan.")
    else:
        checklist.append(f"Work from the discovery approval input first: {manual_approval_input_file}.")
        checklist.append("Do not treat any slot as executable until manual approval is explicitly filled.")
    checklist.extend(
        [
            "Keep targeting and budget fixed so the slot isolates the planned creative change only.",
            "After execution, fill execution_status, slot_result_summary, and success for the exact slot row.",
            "Then add actual_result_note, CTR, CPI, and ROI/ROAS as recommended enrichments.",
        ]
    )
    for item in list(card.get("setup_instructions") or [])[:2]:
        if item not in checklist:
            checklist.append(str(item))
    next_step = str(capture_packet.get("next_learning_step") or "").strip()
    if next_step:
        checklist.append(f"Current bottleneck: {next_step}.")
    return checklist


def _execution_instruction(execution_packet: dict[str, Any], slot_id: str) -> str:
    for slot in execution_packet.get("slot_packets") or []:
        if str(slot.get("slot_id") or "") == slot_id:
            return str(slot.get("recommended_operator_action") or "")
    return ""


def _learning_binding(learning_packet: dict[str, Any], slot_id: str) -> dict[str, Any]:
    for slot in learning_packet.get("slot_learning_packets") or []:
        if str(slot.get("slot_id") or "") == slot_id:
            return {
                "learning_question": slot.get("learning_question", ""),
                "result_summary_field": slot.get("result_summary_field", ""),
                "linked_slot_plan_field": slot.get("linked_slot_plan_field", ""),
            }
    return {}


def _next_operator_step(row: dict[str, Any]) -> str:
    status = str(row.get("slot_status") or "")
    if status == "approval_blocked":
        return "Resolve approval blocker, then create the planned variant."
    if status == "ready_to_execute":
        return "Create and launch the planned variant, then update execution_status."
    if status == "awaiting_result":
        return "Fill slot_result_summary and success for the executed slot."
    if status == "learned":
        return "Review the learned pattern and decide whether to expand or retire the slot direction."
    return "Review missing evidence and continue the next discovery step."


def _packet_approval_status(rows: list[dict[str, Any]], capture_packet: dict[str, Any]) -> str:
    for row in rows:
        status = str(row.get("approval_status") or "").strip()
        if status:
            return status
    return str(capture_packet.get("approval_status") or "")


def _packet_manual_approval_state(rows: list[dict[str, Any]]) -> str:
    for row in rows:
        state = str(row.get("manual_approval_state") or "").strip()
        if state:
            return state
    return "approval_pending_input"


def _packet_manual_approval_decision(rows: list[dict[str, Any]]) -> str:
    for row in rows:
        decision = str(row.get("manual_approval_decision") or "").strip()
        if decision:
            return decision
    return ""


def _packet_manual_approval_note(rows: list[dict[str, Any]]) -> str:
    for row in rows:
        note = str(row.get("manual_approval_note") or "").strip()
        if note:
            return note
    return ""


def _first_manual_approval_input(rows: list[dict[str, Any]]) -> str:
    for row in rows:
        path = str(row.get("parent_manual_input_file") or "").strip()
        if path:
            return path
    return ""


def _next_human_surface(manual_approval_state: str, manual_approval_input_file: str, slot_manual_input_file: str) -> str:
    if manual_approval_state == "approved_for_manual_execution":
        return slot_manual_input_file or manual_approval_input_file
    return manual_approval_input_file or slot_manual_input_file


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
