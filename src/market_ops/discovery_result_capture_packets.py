from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.discovery_learning_packets import DiscoveryLearningPacketsBuilder
from market_ops.experiment_result_ingestion import ExperimentResultIngestionBuilder
from market_ops.learning_evidence_queue import LearningEvidenceQueueBuilder


@dataclass(slots=True)
class DiscoveryResultCapturePacketsResult:
    markdown_path: Path
    json_path: Path
    csv_path: Path
    passed: bool


class DiscoveryResultCapturePacketsBuilder:
    """Builds slot-level result-capture packets so discovery learning can be closed with low ambiguity."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> DiscoveryResultCapturePacketsResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self.build_payload(report_date)

        markdown_path = output_dir / f"discovery_result_capture_packets_{suffix}.md"
        json_path = output_dir / f"discovery_result_capture_packets_{suffix}.json"
        csv_path = output_dir / f"discovery_slot_result_input_{suffix}.csv"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._write_slot_csv(csv_path, payload["packets"])
        return DiscoveryResultCapturePacketsResult(markdown_path=markdown_path, json_path=json_path, csv_path=csv_path, passed=bool(payload["passed"]))

    def build_payload(self, report_date: date) -> dict[str, Any]:
        learning_payload = DiscoveryLearningPacketsBuilder(self._settings).build_payload(report_date)
        result_payload = ExperimentResultIngestionBuilder(self._settings).build_payload(report_date)
        evidence_payload = LearningEvidenceQueueBuilder(self._settings).build_payload(report_date)
        result_index = {
            str(item.get("experiment_id") or ""): item
            for item in result_payload.get("result_rows") or []
            if str(item.get("experiment_id") or "").strip()
        }
        evidence_by_slot = {
            (str(item.get("experiment_id") or ""), str(item.get("slot_id") or "")): item
            for item in evidence_payload.get("queue_items") or []
            if str(item.get("experiment_type") or "") == "discovery_slot_test"
        }

        packets = [
            _capture_packet(
                packet,
                result_index.get(str(packet.get("experiment_id") or ""), {}),
                evidence_by_slot,
                index,
            )
            for index, packet in enumerate(learning_payload.get("packets") or [], start=1)
        ]
        return {
            "report_date": report_date.isoformat(),
            "mode": "discovery_result_capture_packets",
            "passed": True,
            "rules": {
                "signal_only": True,
                "approval_gated": True,
                "manual_result_capture_required": True,
                "no_platform_write": True,
                "slot_rows_roll_up_parent_result": True,
                "slot_manual_input_file": str(self._settings.active_output_dir / f"discovery_slot_result_input_{report_date.strftime('%Y%m%d')}.csv"),
            },
            "summary": {
                "packet_count": len(packets),
                "slot_capture_count": sum(len(item.get("slot_capture_packets") or []) for item in packets),
                "critical_packet_count": sum(1 for item in packets if item.get("capture_priority") == "critical_learning_blocker"),
                "decision_waiting_packet_count": sum(1 for item in packets if item.get("decision_waiting")),
                "decision_waiting_slot_count": sum(
                    1
                    for item in packets
                    for slot in item.get("slot_capture_packets") or []
                    if slot.get("decision_waiting")
                ),
            },
            "packets": packets,
        }

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload.get("summary") or {}
        lines = [
            f"# Discovery Result Capture Packets | {payload['report_date']}",
            "",
            "- Mode: discovery_result_capture_packets",
            "- Purpose: turn each discovery slot into an explicit result-capture task.",
            "- Boundary: signal-only, approval-gated, no platform write.",
            "",
            "## Summary",
            "",
            f"- Packets: {summary.get('packet_count', 0)}",
            f"- Slot capture packets: {summary.get('slot_capture_count', 0)}",
            f"- Critical packets: {summary.get('critical_packet_count', 0)}",
            f"- Decision-waiting packets: {summary.get('decision_waiting_packet_count', 0)}",
            f"- Decision-waiting slots: {summary.get('decision_waiting_slot_count', 0)}",
            "",
            "## Packets",
            "",
        ]
        if not payload.get("packets"):
            lines.append("- None.")
        for item in payload.get("packets") or []:
            lines.append(f"### {item['capture_packet_id']} | {item['target']}")
            lines.append(f"- Priority: {item['capture_priority']}")
            lines.append(f"- Parent result row: {item['parent_result_row_id'] or 'missing'}")
            lines.append(f"- Parent result state: {item.get('parent_result_state') or 'missing'}")
            lines.append(f"- Required parent fields: {', '.join(item.get('required_parent_fields') or []) or 'none'}")
            lines.append(f"- Parent fields auto-rollup from slot rows: {', '.join(item.get('slot_rollup_parent_fields') or []) or 'none'}")
            lines.append(f"- Parent fields still require parent-row input: {', '.join(item.get('manual_parent_fields') or []) or 'none'}")
            lines.append(f"- Recommended enrichments: {', '.join(item.get('recommended_parent_fields') or []) or 'none'}")
            lines.append(f"- Parent manual input file: {item['manual_input_file']}")
            lines.append(f"- Slot manual input file: {item['slot_manual_input_file']}")
            lines.append(f"- Result template file: {item['result_template_file']}")
            lines.append(f"- Why this test first: {item.get('structural_test_rationale') or 'none'}")
            lines.append(f"- Prioritized focuses: {', '.join(item.get('discovery_prioritized_change_focuses') or []) or 'none'}")
            lines.append(
                f"- Decision unlock impact: waiting={item.get('decision_waiting')} | "
                f"matched_decisions={item.get('decision_wait_match_count', 0)} | "
                f"slots_to_resolve={', '.join(item.get('fastest_unlock_slot_ids') or []) or 'none'}"
            )
            lines.append(f"- Parent next step: {item['parent_next_step']}")
            lines.append("- Slot capture packets:")
            for slot in item.get("slot_capture_packets") or []:
                lines.append(
                    f"  - {slot['slot_id']} | {slot['variant_name']} | focus={slot['change_focus']} | "
                    f"required={', '.join(slot.get('required_fields') or [])} | "
                    f"rolls_up={', '.join(slot.get('rollup_to_parent_fields') or [])} | "
                    f"unlocks={slot.get('decision_wait_match_count', 0)} | example={slot['slot_result_example']}"
                )
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _write_slot_csv(path: Path, packets: list[dict[str, Any]]) -> None:
        fieldnames = [
            "approval_id",
            "experiment_id",
            "target",
            "slot_id",
            "variant_name",
            "change_focus",
            "learning_question",
            "execution_status",
            "success",
            "slot_result_note",
            "actual_result_note",
            "post_action_ctr",
            "post_action_cpi",
            "post_action_roi_or_roas",
        ]
        existing_index: dict[tuple[str, str], dict[str, str]] = {}
        if path.exists():
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    key = (str(row.get("approval_id") or ""), str(row.get("slot_id") or ""))
                    existing_index[key] = dict(row)
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for packet in packets:
                for slot in packet.get("slot_capture_packets") or []:
                    base = {
                        "approval_id": packet.get("approval_id", ""),
                        "experiment_id": packet.get("experiment_id", ""),
                        "target": packet.get("target", ""),
                        "slot_id": slot.get("slot_id", ""),
                        "variant_name": slot.get("variant_name", ""),
                        "change_focus": slot.get("change_focus", ""),
                        "learning_question": slot.get("learning_question", ""),
                        "execution_status": "",
                        "success": "",
                        "slot_result_note": "",
                        "actual_result_note": "",
                        "post_action_ctr": "",
                        "post_action_cpi": "",
                        "post_action_roi_or_roas": "",
                    }
                    existing = existing_index.get((base["approval_id"], base["slot_id"]), {})
                    for field in fieldnames:
                        if field in {"approval_id", "experiment_id", "target", "slot_id", "variant_name", "change_focus", "learning_question"}:
                            continue
                        value = str(existing.get(field) or "").strip()
                        if value:
                            base[field] = value
                    writer.writerow(base)


def _capture_packet(
    packet: dict[str, Any],
    result_row: dict[str, Any],
    evidence_by_slot: dict[tuple[str, str], dict[str, Any]],
    index: int,
) -> dict[str, Any]:
    experiment_id = str(packet.get("experiment_id") or "")
    slot_capture_packets = [
        _slot_capture_packet(
            packet,
            slot,
            evidence_by_slot.get((experiment_id, str(slot.get("slot_id") or "")), {}),
        )
        for slot in packet.get("slot_learning_packets") or []
    ]
    slot_capture_packets.sort(
        key=lambda item: (
            -int(item.get("decision_wait_match_count") or 0),
            str(item.get("slot_id") or ""),
        )
    )
    decision_wait_entity_ids = _unique(
        [
            str(entity_id)
            for slot in slot_capture_packets
            for entity_id in list(slot.get("decision_wait_entity_ids") or [])
            if str(entity_id).strip()
        ]
    )
    return {
        "capture_packet_id": f"discovery_capture_{index:03d}",
        "learning_packet_id": packet.get("learning_packet_id", ""),
        "experiment_id": packet.get("experiment_id", ""),
        "approval_id": packet.get("approval_id", ""),
        "target": packet.get("target", ""),
        "approval_status": packet.get("approval_status", ""),
        "capture_priority": "critical_learning_blocker",
        "parent_result_row_id": result_row.get("result_id", ""),
        "parent_result_state": result_row.get("result_state", ""),
        "required_parent_fields": [
            "execution_status",
            "actual_result_note",
            "success",
            "slot_result_summary",
        ],
        "slot_rollup_parent_fields": [
            "execution_status",
            "actual_result_note",
            "success",
            "slot_result_summary",
            "post_action_ctr",
            "post_action_cpi",
            "post_action_roi_or_roas",
        ],
        "manual_parent_fields": [
            "created_variant_count",
            "linked_new_creative_ids",
            "learning_note",
        ],
        "recommended_parent_fields": [
            "post_action_roi_or_roas",
            "post_action_ctr",
            "post_action_cpi",
            "created_variant_count",
            "linked_new_creative_ids",
            "learning_note",
        ],
        "slot_capture_packets": slot_capture_packets,
        "manual_input_file": result_row.get("manual_input_file", ""),
        "parent_manual_input_file": result_row.get("manual_input_file", ""),
        "slot_manual_input_file": _slot_manual_input_file(result_row),
        "result_template_file": result_row.get("result_template_file", ""),
        "result_defaults": dict(packet.get("result_defaults") or {}),
        "structural_test_rationale": str(packet.get("structural_test_rationale") or result_row.get("structural_test_rationale") or ""),
        "winner_structure_bias": list(packet.get("winner_structure_bias") or result_row.get("winner_structure_bias") or []),
        "discovery_prioritized_change_focuses": list(packet.get("discovery_prioritized_change_focuses") or result_row.get("discovery_prioritized_change_focuses") or []),
        "next_learning_step": result_row.get("next_learning_step", ""),
        "parent_next_step": _parent_next_step(result_row),
        "decision_waiting": any(bool(slot.get("decision_waiting")) for slot in slot_capture_packets),
        "decision_wait_match_count": len(decision_wait_entity_ids),
        "decision_wait_entity_ids": decision_wait_entity_ids[:20],
        "decision_waiting_slot_count": sum(1 for slot in slot_capture_packets if slot.get("decision_waiting")),
        "fastest_unlock_slot_ids": [
            str(slot.get("slot_id") or "")
            for slot in slot_capture_packets
            if int(slot.get("decision_wait_match_count") or 0) > 0
        ][:5],
    }


def _slot_capture_packet(packet: dict[str, Any], slot: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    slot_id = str(slot.get("slot_id") or "")
    focus = str(slot.get("learning_question") or "")
    variant_name = str(slot.get("variant_name") or "")
    return {
        "slot_id": slot_id,
        "variant_name": variant_name,
        "change_focus": _change_focus_from_question(focus),
        "required_fields": ["execution_status", "slot_result_summary", "success"],
        "recommended_fields": ["actual_result_note", "post_action_ctr", "post_action_cpi", "post_action_roi_or_roas"],
        "rollup_to_parent_fields": [
            "execution_status",
            "actual_result_note",
            "success",
            "slot_result_summary",
            "post_action_ctr",
            "post_action_cpi",
            "post_action_roi_or_roas",
        ],
        "slot_result_example": f"{slot_id}:win:CTR +18%" if slot_id else "slot_01:win:CTR +18%",
        "learning_question": focus,
        "decision_waiting": bool(evidence.get("decision_waiting")),
        "decision_wait_match_count": int(evidence.get("decision_wait_match_count") or 0),
        "decision_wait_entity_ids": list(evidence.get("decision_wait_entity_ids") or [])[:20],
        "decision_wait_targets": list(evidence.get("decision_wait_targets") or [])[:10],
        "decision_wait_contextual_pattern_keys": list(evidence.get("decision_wait_contextual_pattern_keys") or [])[:10],
        "recommended_resolution_order": (
            "resolve_first" if int(evidence.get("decision_wait_match_count") or 0) > 0 else "normal_queue"
        ),
    }


def _change_focus_from_question(question: str) -> str:
    text = str(question or "")
    if text.startswith("Did "):
        text = text[4:]
    return text.split(" improve ", 1)[0].strip()


def _slot_manual_input_file(result_row: dict[str, Any]) -> str:
    slot_manual_input = str(result_row.get("slot_manual_input_file") or "")
    if slot_manual_input:
        return slot_manual_input
    manual_input = str(result_row.get("manual_input_file") or "")
    if not manual_input:
        return ""
    return manual_input.replace("experiment_result_input_", "discovery_slot_result_input_")


def _parent_next_step(result_row: dict[str, Any]) -> str:
    state = str(result_row.get("result_state") or "")
    if state == "approval_blocked":
        return "Resolve discovery approval input first, then execute slot variants before filling the parent result row."
    return (
        "Use the slot result input file to capture execution_status, success, slot_result_note, and post metrics per slot. "
        "Then fill the parent result row only for created_variant_count, linked_new_creative_ids, and learning_note if still missing."
    )


def _unique(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        if item and item not in result:
            result.append(item)
    return result
