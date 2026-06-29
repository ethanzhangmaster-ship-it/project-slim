from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.discovery_execution_packets import DiscoveryExecutionPacketsBuilder
from market_ops.experiment_result_ingestion import ExperimentResultIngestionBuilder


@dataclass(slots=True)
class DiscoveryLearningPacketsResult:
    markdown_path: Path
    json_path: Path
    passed: bool


class DiscoveryLearningPacketsBuilder:
    """Builds learning-ready packets that bind discovery execution slots to result capture and learning questions."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> DiscoveryLearningPacketsResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self.build_payload(report_date)

        markdown_path = output_dir / f"discovery_learning_packets_{suffix}.md"
        json_path = output_dir / f"discovery_learning_packets_{suffix}.json"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return DiscoveryLearningPacketsResult(markdown_path=markdown_path, json_path=json_path, passed=bool(payload["passed"]))

    def build_payload(self, report_date: date) -> dict[str, Any]:
        packets_payload = DiscoveryExecutionPacketsBuilder(self._settings).build_payload(report_date)
        result_payload = ExperimentResultIngestionBuilder(self._settings).build_payload(report_date)
        result_index = {
            str(item.get("experiment_id") or ""): item
            for item in result_payload.get("result_rows") or []
            if str(item.get("experiment_id") or "").strip()
        }
        learning_packets = [
            _learning_packet(packet, result_index.get(str(packet.get("experiment_id") or ""), {}), index)
            for index, packet in enumerate(packets_payload.get("packets") or [], start=1)
        ]
        return {
            "report_date": report_date.isoformat(),
            "mode": "discovery_learning_packets",
            "passed": True,
            "rules": {
                "signal_only": True,
                "approval_gated": True,
                "manual_result_capture_required": True,
                "learning_promotes_only_after_closed_results": True,
            },
            "summary": {
                "packet_count": len(learning_packets),
                "slot_question_count": sum(len(item.get("slot_learning_packets") or []) for item in learning_packets),
            },
            "packets": learning_packets,
        }

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload.get("summary") or {}
        lines = [
            f"# Discovery Learning Packets | {payload['report_date']}",
            "",
            "- Mode: discovery_learning_packets",
            "- Purpose: bind discovery execution slots to learning questions and result capture fields.",
            "- Boundary: signal-only, approval-gated, no platform write.",
            "",
            "## Summary",
            "",
            f"- Packets: {summary.get('packet_count', 0)}",
            f"- Slot learning packets: {summary.get('slot_question_count', 0)}",
            "",
            "## Packets",
            "",
        ]
        if not payload.get("packets"):
            lines.append("- None.")
        for item in payload.get("packets") or []:
            lines.append(f"### {item['learning_packet_id']} | {item['target']}")
            lines.append(f"- Learning goal: {item['learning_goal']}")
            lines.append(f"- Why this test first: {item.get('structural_test_rationale') or 'none'}")
            lines.append(f"- Prioritized focuses: {', '.join(item.get('discovery_prioritized_change_focuses') or []) or 'none'}")
            lines.append(f"- Result defaults: slot_plan={item['result_defaults'].get('slot_execution_plan','')}")
            lines.append(f"- Result capture format: {item.get('result_capture_format', '')}")
            lines.append("- Slot learning packets:")
            for slot in item.get("slot_learning_packets") or []:
                lines.append(
                    f"  - {slot['slot_id']} | {slot['variant_name']} | question={slot['learning_question']} | "
                    f"summary_field={slot['result_summary_field']}"
                )
            lines.append("")
        return "\n".join(lines)


def _learning_packet(packet: dict[str, Any], result_row: dict[str, Any], index: int) -> dict[str, Any]:
    slot_packets = _effective_slot_packets(packet, result_row)
    slot_learning_packets = [_slot_learning_packet(packet, slot) for slot in slot_packets]
    slot_plan = " | ".join(
        f"{slot.get('slot_id')}:{slot.get('variant_name')}[{slot.get('change_focus')}]"
        for slot in slot_packets
    )
    learning_questions = " | ".join(f"{slot.get('slot_id')}:{slot.get('learning_question')}" for slot in slot_learning_packets)
    return {
        "learning_packet_id": f"discovery_learning_{index:03d}",
        "packet_id": packet.get("packet_id", ""),
        "experiment_id": packet.get("experiment_id", ""),
        "approval_id": packet.get("approval_id", ""),
        "target": packet.get("target", ""),
        "learning_goal": _learning_goal(packet),
        "approval_status": result_row.get("approval_status", "") or packet.get("approval_status", ""),
        "slot_learning_packets": slot_learning_packets,
        "structural_test_rationale": str(result_row.get("structural_test_rationale") or ""),
        "winner_structure_bias": list(result_row.get("winner_structure_bias") or []),
        "discovery_prioritized_change_focuses": list(result_row.get("discovery_prioritized_change_focuses") or []),
        "result_defaults": {
            "slot_execution_plan": str(result_row.get("slot_execution_plan") or slot_plan),
            "slot_learning_question": str(result_row.get("slot_learning_question") or learning_questions),
            "slot_result_summary": result_row.get("slot_result_summary", ""),
        },
        "required_result_fields": [
            "slot_execution_plan",
            "slot_learning_question",
            "slot_result_summary",
            "learning_note",
            "created_variant_count",
            "linked_new_creative_ids",
        ],
        "result_capture_format": "Use slot_result_summary entries like slot_01:win:CTR +18% and slot_02:loss:CPI worsened.",
    }


def _slot_learning_packet(packet: dict[str, Any], slot: dict[str, Any]) -> dict[str, Any]:
    focus = str(slot.get("change_focus") or "")
    axis = str(slot.get("planned_test_axis") or "")
    baseline = str(slot.get("baseline_anchor") or "")
    question = f"Did {focus} improve {axis} performance versus baseline {baseline}?"
    return {
        "slot_id": slot.get("slot_id", ""),
        "variant_name": slot.get("variant_name", ""),
        "change_focus": focus,
        "planned_test_axis": axis,
        "baseline_anchor": baseline,
        "learning_question": question,
        "execution_status": str(slot.get("execution_status") or ""),
        "slot_result_summary": str(slot.get("slot_result_summary") or ""),
        "slot_success": slot.get("slot_success", slot.get("success")),
        "actual_result_note": str(slot.get("actual_result_note") or ""),
        "result_summary_field": "slot_result_summary",
        "linked_slot_plan_field": "slot_execution_plan",
    }


def _learning_goal(packet: dict[str, Any]) -> str:
    axis = str(packet.get("primary_test_axis") or "")
    target = str(packet.get("target") or "")
    return f"Learn whether {axis or 'the planned discovery axis'} is reusable for {target}."


def _effective_slot_packets(packet: dict[str, Any], result_row: dict[str, Any]) -> list[dict[str, Any]]:
    base_slots = [dict(item) for item in packet.get("slot_packets") or []]
    result_slots = {
        str(item.get("slot_id") or "").strip(): dict(item)
        for item in result_row.get("slot_packets") or []
        if str(item.get("slot_id") or "").strip()
    }
    merged_slots: list[dict[str, Any]] = []
    seen_slot_ids: set[str] = set()
    for base_slot in base_slots:
        slot_id = str(base_slot.get("slot_id") or "").strip()
        seen_slot_ids.add(slot_id)
        merged_slots.append(_merge_slot_learning_packet(base_slot, result_slots.get(slot_id, {})))
    for slot_id, result_slot in result_slots.items():
        if slot_id in seen_slot_ids:
            continue
        merged_slots.append(_merge_slot_learning_packet({}, result_slot))
    merged_slots.sort(key=lambda item: str(item.get("slot_id") or ""))
    return merged_slots


def _merge_slot_learning_packet(base_slot: dict[str, Any], result_slot: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base_slot)
    for field in (
        "slot_id",
        "variant_name",
        "change_focus",
        "learning_question",
        "execution_status",
        "slot_result_summary",
        "slot_success",
        "success",
        "actual_result_note",
    ):
        value = result_slot.get(field)
        if value is None:
            continue
        if isinstance(value, str):
            if value.strip():
                merged[field] = value
        else:
            merged[field] = value
    return merged
