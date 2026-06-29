from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.discovery_learning_packets import DiscoveryLearningPacketsBuilder
from market_ops.experiment_result_ingestion import ExperimentResultIngestionBuilder


@dataclass(slots=True)
class DiscoveryLearningStateBoardResult:
    markdown_path: Path
    json_path: Path
    passed: bool


class DiscoveryLearningStateBoardBuilder:
    """Builds an explicit discovery learning state board from approval, slot, and result evidence."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> DiscoveryLearningStateBoardResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self.build_payload(report_date)

        markdown_path = output_dir / f"discovery_learning_state_board_{suffix}.md"
        json_path = output_dir / f"discovery_learning_state_board_{suffix}.json"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return DiscoveryLearningStateBoardResult(markdown_path=markdown_path, json_path=json_path, passed=bool(payload["passed"]))

    def build_payload(self, report_date: date) -> dict[str, Any]:
        learning_payload = DiscoveryLearningPacketsBuilder(self._settings).build_payload(report_date)
        result_payload = ExperimentResultIngestionBuilder(self._settings).build_payload(report_date)
        result_index = {
            str(item.get("experiment_id") or ""): item
            for item in result_payload.get("result_rows") or []
            if str(item.get("experiment_id") or "").strip()
        }
        packets = [
            _state_packet(packet, result_index.get(str(packet.get("experiment_id") or ""), {}), index)
            for index, packet in enumerate(learning_payload.get("packets") or [], start=1)
        ]
        return {
            "report_date": report_date.isoformat(),
            "mode": "discovery_learning_state_board",
            "passed": True,
            "rules": {
                "signal_only": True,
                "approval_gated": True,
                "manual_result_capture_required": True,
                "pattern_memory_requires_closed_parent_and_slot_outcomes": True,
            },
            "summary": {
                "packet_count": len(packets),
                "awaiting_approval_count": sum(1 for item in packets if item.get("learning_state") == "awaiting_approval"),
                "awaiting_execution_count": sum(1 for item in packets if item.get("learning_state") == "awaiting_execution"),
                "awaiting_result_count": sum(1 for item in packets if item.get("learning_state") == "awaiting_result"),
                "ready_for_pattern_memory_count": sum(1 for item in packets if item.get("learning_state") == "ready_for_pattern_memory"),
                "pattern_memory_closed_count": sum(1 for item in packets if item.get("learning_state") == "pattern_memory_closed"),
                "slot_count": sum(len(item.get("slot_states") or []) for item in packets),
            },
            "packets": packets,
        }

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload.get("summary") or {}
        lines = [
            f"# Discovery Learning State Board | {payload['report_date']}",
            "",
            "- Mode: discovery_learning_state_board",
            "- Purpose: separate executed discovery work from discovery knowledge that is actually ready to become reusable pattern memory.",
            "- Boundary: signal-only, approval-gated, no platform write.",
            "",
            "## Summary",
            "",
            f"- Packets: {summary.get('packet_count', 0)}",
            f"- Awaiting approval: {summary.get('awaiting_approval_count', 0)}",
            f"- Awaiting execution: {summary.get('awaiting_execution_count', 0)}",
            f"- Awaiting result: {summary.get('awaiting_result_count', 0)}",
            f"- Ready for pattern memory: {summary.get('ready_for_pattern_memory_count', 0)}",
            f"- Pattern memory closed: {summary.get('pattern_memory_closed_count', 0)}",
            f"- Slots: {summary.get('slot_count', 0)}",
            "",
            "## Packets",
            "",
        ]
        if not payload.get("packets"):
            lines.append("- None.")
        for item in payload.get("packets") or []:
            lines.append(f"### {item['learning_state_packet_id']} | {item['target']}")
            lines.append(f"- Learning state: {item['learning_state']}")
            lines.append(f"- Parent result state: {item['parent_result_state']}")
            lines.append(f"- Parent success: {item['parent_success']}")
            lines.append(f"- Learning close signal: {item['learning_close_signal']}")
            lines.append(f"- Next update: {item['next_update_required']}")
            lines.append("- Slot states:")
            for slot in item.get("slot_states") or []:
                lines.append(
                    f"  - {slot['slot_id']} | {slot['slot_learning_state']} | focus={slot['change_focus']} | "
                    f"success={slot['slot_success']} | summary={slot['slot_result_summary'] or 'missing'}"
                )
            lines.append("")
        return "\n".join(lines)


def _state_packet(packet: dict[str, Any], result_row: dict[str, Any], index: int) -> dict[str, Any]:
    slot_states = [_slot_state(item) for item in packet.get("slot_learning_packets") or []]
    learning_state = _packet_learning_state(packet, result_row, slot_states)
    return {
        "learning_state_packet_id": f"discovery_learning_state_{index:03d}",
        "learning_packet_id": packet.get("learning_packet_id", ""),
        "experiment_id": packet.get("experiment_id", ""),
        "approval_id": packet.get("approval_id", ""),
        "target": packet.get("target", ""),
        "learning_goal": packet.get("learning_goal", ""),
        "approval_status": packet.get("approval_status", ""),
        "parent_result_state": str(result_row.get("result_state") or ""),
        "parent_success": result_row.get("success"),
        "parent_result_summary": str(result_row.get("slot_result_summary") or ""),
        "parent_learning_note": str(result_row.get("learning_note") or ""),
        "learning_state": learning_state,
        "learning_close_signal": _learning_close_signal(learning_state, result_row, slot_states),
        "next_update_required": _next_update_required(learning_state, result_row, slot_states),
        "slot_states": slot_states,
    }


def _slot_state(slot: dict[str, Any]) -> dict[str, Any]:
    slot_summary = str(slot.get("slot_result_summary") or "")
    slot_success = _parse_success(slot.get("slot_success"))
    slot_learning_state = _slot_learning_state(slot_summary, slot_success)
    return {
        "slot_id": slot.get("slot_id", ""),
        "variant_name": slot.get("variant_name", ""),
        "change_focus": slot.get("change_focus", ""),
        "slot_result_summary": slot_summary,
        "slot_success": slot_success,
        "slot_learning_state": slot_learning_state,
    }


def _packet_learning_state(packet: dict[str, Any], result_row: dict[str, Any], slot_states: list[dict[str, Any]]) -> str:
    approval_status = str(packet.get("approval_status") or "")
    if approval_status in {"approval_blocked", "approval_rejected"}:
        return "awaiting_approval"
    if any(item.get("slot_learning_state") == "awaiting_execution" for item in slot_states):
        return "awaiting_execution"
    if any(item.get("slot_learning_state") == "awaiting_result" for item in slot_states):
        return "awaiting_result"
    parent_closed = str(result_row.get("result_state") or "") == "closed"
    if not parent_closed:
        return "ready_for_pattern_memory"
    return "pattern_memory_closed"


def _learning_close_signal(learning_state: str, result_row: dict[str, Any], slot_states: list[dict[str, Any]]) -> str:
    if learning_state == "awaiting_approval":
        return "Manual discovery approval is still unresolved."
    if learning_state == "awaiting_execution":
        return "At least one approved slot still has no execution_status."
    if learning_state == "awaiting_result":
        return "At least one executed slot still has no win/loss result summary."
    if learning_state == "ready_for_pattern_memory":
        return "All slot outcomes are present; parent result row still needs closure fields before memory can close."
    closed_slots = sum(1 for item in slot_states if item.get("slot_learning_state") == "closed")
    return f"All {closed_slots} slot outcomes and the parent result row are closed; reusable discovery memory can be promoted."


def _next_update_required(learning_state: str, result_row: dict[str, Any], slot_states: list[dict[str, Any]]) -> str:
    if learning_state == "awaiting_approval":
        return "Resolve discovery approval input first."
    if learning_state == "awaiting_execution":
        return "Execute the approved slot variants and update execution_status in the slot input file."
    if learning_state == "awaiting_result":
        return "Fill slot_result_note or success for the executed slots so win/loss summaries can be formed."
    if learning_state == "ready_for_pattern_memory":
        return "Use the parent result row to finalize created_variant_count, linked_new_creative_ids, and learning_note."
    return "No update required; ready for pattern-memory and causal promotion."


def _slot_learning_state(slot_summary: str, slot_success: bool | None) -> str:
    if slot_summary and slot_success is not None:
        return "closed"
    if slot_summary and slot_success is None:
        return "awaiting_result"
    return "awaiting_execution"


def _parse_success(value: Any) -> bool | None:
    text = str(value or "").strip().lower()
    if text in {"true", "1", "yes", "y", "success", "passed", "win", "won"}:
        return True
    if text in {"false", "0", "no", "n", "failed", "fail", "loss", "lost"}:
        return False
    return None
