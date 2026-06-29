from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.discovery_approval_packet import DiscoveryApprovalPacketBuilder
from market_ops.discovery_slot_operator_packet import DiscoverySlotOperatorPacketBuilder
from market_ops.discovery_unlock_sequence import DiscoveryUnlockSequenceBuilder


@dataclass(slots=True)
class DiscoveryUnlockOperatorHandoffResult:
    markdown_path: Path
    json_path: Path
    passed: bool


class DiscoveryUnlockOperatorHandoffBuilder:
    """Build an operator-facing handoff that turns unlock ranking into ordered manual actions."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> DiscoveryUnlockOperatorHandoffResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self.build_payload(report_date)

        markdown_path = output_dir / f"discovery_unlock_operator_handoff_{suffix}.md"
        json_path = output_dir / f"discovery_unlock_operator_handoff_{suffix}.json"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return DiscoveryUnlockOperatorHandoffResult(
            markdown_path=markdown_path,
            json_path=json_path,
            passed=bool(payload["passed"]),
        )

    def build_payload(self, report_date: date) -> dict[str, Any]:
        unlock_payload = DiscoveryUnlockSequenceBuilder(self._settings).build_payload(report_date)
        operator_payload = DiscoverySlotOperatorPacketBuilder(self._settings).build_payload(report_date)
        approval_payload = DiscoveryApprovalPacketBuilder(self._settings).build_payload(report_date)

        operator_index = {
            str(item.get("approval_id") or ""): item
            for item in operator_payload.get("packets") or []
            if str(item.get("approval_id") or "").strip()
        }
        approval_index = {
            str(item.get("approval_id") or ""): item
            for item in approval_payload.get("packets") or []
            if str(item.get("approval_id") or "").strip()
        }

        handoffs = [
            _handoff_item(
                sequence=sequence,
                operator_packet=operator_index.get(str(sequence.get("approval_id") or ""), {}),
                approval_packet=approval_index.get(str(sequence.get("approval_id") or ""), {}),
                index=index,
            )
            for index, sequence in enumerate(unlock_payload.get("sequences") or [], start=1)
        ]
        handoffs.sort(
            key=lambda item: (
                -int(item.get("decision_wait_match_count") or 0),
                -int(item.get("slot_count") or 0),
                str(item.get("approval_id") or ""),
            )
        )

        return {
            "report_date": report_date.isoformat(),
            "mode": "discovery_unlock_operator_handoff",
            "passed": True,
            "rules": {
                "signal_only": True,
                "approval_gated": True,
                "manual_execution_only": True,
                "no_platform_write": True,
                "purpose": "Translate ranked unlock sequences into the exact human approval and slot-result work order.",
            },
            "summary": {
                "handoff_count": len(handoffs),
                "decision_waiting_handoffs": sum(1 for item in handoffs if item.get("decision_wait_match_count")),
                "approval_input_step_count": sum(1 for item in handoffs if item.get("approval_step_required")),
                "slot_execution_step_count": sum(len(item.get("slot_execution_order") or []) for item in handoffs),
                "reopened_decision_target_count": sum(len(item.get("reopened_decision_targets") or []) for item in handoffs),
            },
            "handoffs": handoffs,
        }

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload.get("summary") or {}
        lines = [
            f"# Discovery Unlock Operator Handoff | {payload['report_date']}",
            "",
            "- Mode: discovery_unlock_operator_handoff",
            "- Purpose: convert ranked discovery unlock signals into the exact manual approval and slot-result work order.",
            "- Boundary: signal-only, approval-gated, manual execution only, no platform write.",
            "",
            "## Summary",
            "",
            f"- Handoffs: {summary.get('handoff_count', 0)}",
            f"- Decision-waiting handoffs: {summary.get('decision_waiting_handoffs', 0)}",
            f"- Approval input steps: {summary.get('approval_input_step_count', 0)}",
            f"- Slot execution steps: {summary.get('slot_execution_step_count', 0)}",
            f"- Reopened decision targets: {summary.get('reopened_decision_target_count', 0)}",
            "",
            "## Handoffs",
            "",
        ]
        if not payload.get("handoffs"):
            lines.append("- None.")
        for item in payload.get("handoffs") or []:
            lines.append(f"### {item['handoff_id']} | {item['approval_id']} | {item['target']}")
            lines.append(f"- Manual approval state: {item['manual_approval_state']}")
            lines.append(f"- Next human surface: {item['next_human_surface']}")
            lines.append(f"- Approval input file: {item['manual_approval_input_file'] or 'none'}")
            lines.append(f"- Slot input file: {item['slot_manual_input_file'] or 'none'}")
            lines.append(
                f"- Unlock impact: matched_decisions={item['decision_wait_match_count']} | "
                f"slot_count={item['slot_count']} | approval_step_required={item['approval_step_required']}"
            )
            lines.append(f"- Approval next step: {item['approval_next_step']}")
            reopened = [
                f"{target.get('entity_type')}:{target.get('entity_id')} ({target.get('decision')})"
                for target in list(item.get("reopened_decision_targets") or [])[:8]
                if str(target.get("entity_id") or "").strip()
            ]
            lines.append(f"- Reopened decisions: {', '.join(reopened) or 'none'}")
            lines.append("- Ordered slot work:")
            for slot in item.get("slot_execution_order") or []:
                reopened_targets = [
                    f"{target.get('entity_type')}:{target.get('entity_id')}"
                    for target in list(slot.get("reopened_decision_targets") or [])[:5]
                    if str(target.get("entity_id") or "").strip()
                ]
                lines.append(
                    f"  - {slot['slot_id']} | {slot['slot_status']} | focus={slot['change_focus']} | "
                    f"work={slot['human_work_item']} | next={slot['next_step']} | unlocks={slot['decision_wait_match_count']} | "
                    f"targets={', '.join(reopened_targets) or 'none'}"
                )
            lines.append("")
        return "\n".join(lines)


def _handoff_item(
    *,
    sequence: dict[str, Any],
    operator_packet: dict[str, Any],
    approval_packet: dict[str, Any],
    index: int,
) -> dict[str, Any]:
    manual_approval_state = str(
        operator_packet.get("manual_approval_state")
        or approval_packet.get("manual_approval_state")
        or sequence.get("manual_approval_state")
        or ""
    )
    manual_approval_input_file = str(
        operator_packet.get("manual_approval_input_file")
        or sequence.get("manual_approval_input_file")
        or ""
    )
    slot_manual_input_file = str(
        operator_packet.get("slot_manual_input_file")
        or sequence.get("slot_manual_input_file")
        or approval_packet.get("slot_manual_input_file")
        or ""
    )
    approval_step_required = manual_approval_state != "approved_for_manual_execution"
    slot_rows = [
        _slot_work_item(slot, approval_step_required)
        for slot in sequence.get("slots") or []
    ]
    return {
        "handoff_id": f"unlock_handoff_{index:03d}",
        "approval_id": str(sequence.get("approval_id") or ""),
        "experiment_id": str(sequence.get("experiment_id") or ""),
        "target": str(sequence.get("target") or ""),
        "manual_approval_state": manual_approval_state or "approval_pending_input",
        "approval_step_required": approval_step_required,
        "approval_next_step": _approval_next_step(manual_approval_state, manual_approval_input_file, slot_manual_input_file),
        "next_human_surface": _next_human_surface(manual_approval_state, manual_approval_input_file, slot_manual_input_file),
        "manual_approval_input_file": manual_approval_input_file,
        "slot_manual_input_file": slot_manual_input_file,
        "decision_wait_match_count": int(sequence.get("decision_wait_match_count") or 0),
        "slot_count": len(slot_rows),
        "unlock_order": list(sequence.get("unlock_order") or []),
        "reopened_decision_targets": list(sequence.get("reopened_decision_targets") or [])[:20],
        "slot_execution_order": slot_rows[:12],
    }


def _slot_work_item(slot: dict[str, Any], approval_step_required: bool) -> dict[str, Any]:
    slot_status = str(slot.get("slot_status") or "")
    next_step = str(slot.get("next_step") or "")
    if approval_step_required and slot_status == "approval_blocked":
        human_work_item = "Fill approval decision first, then create this variant."
    elif slot_status == "approval_blocked":
        human_work_item = "Create the planned variant after confirming approval state."
    elif slot_status == "ready_to_execute":
        human_work_item = "Launch the planned variant and update execution_status."
    elif slot_status == "awaiting_result":
        human_work_item = "Fill slot_result_summary and success for this slot."
    elif slot_status == "learned":
        human_work_item = "Review the learned outcome and decide expand vs retire."
    else:
        human_work_item = next_step or "Review the current blocker and continue the next step."
    return {
        "slot_id": str(slot.get("slot_id") or ""),
        "slot_status": slot_status,
        "change_focus": str(slot.get("change_focus") or ""),
        "decision_wait_match_count": int(slot.get("decision_wait_match_count") or 0),
        "next_step": next_step,
        "human_work_item": human_work_item,
        "reopened_decision_targets": list(slot.get("reopened_decision_targets") or [])[:10],
    }


def _approval_next_step(manual_approval_state: str, manual_approval_input_file: str, slot_manual_input_file: str) -> str:
    if manual_approval_state == "approved_for_manual_execution":
        return f"Work from the slot input file: {slot_manual_input_file or 'none'}."
    if manual_approval_state == "approval_rejected":
        return f"Review the rejection note in: {manual_approval_input_file or 'none'}."
    return f"Fill the approval decision in: {manual_approval_input_file or 'none'}."


def _next_human_surface(manual_approval_state: str, manual_approval_input_file: str, slot_manual_input_file: str) -> str:
    if manual_approval_state == "approved_for_manual_execution":
        return slot_manual_input_file or manual_approval_input_file
    return manual_approval_input_file or slot_manual_input_file
