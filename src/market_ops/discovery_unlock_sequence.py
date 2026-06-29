from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.discovery_approval_packet import DiscoveryApprovalPacketBuilder
from market_ops.discovery_slot_operator_packet import DiscoverySlotOperatorPacketBuilder


@dataclass(slots=True)
class DiscoveryUnlockSequenceResult:
    markdown_path: Path
    json_path: Path
    passed: bool


class DiscoveryUnlockSequenceBuilder:
    """Builds a ranked operator sequence for unlocking blocked discovery decisions."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> DiscoveryUnlockSequenceResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self.build_payload(report_date)

        markdown_path = output_dir / f"discovery_unlock_sequence_{suffix}.md"
        json_path = output_dir / f"discovery_unlock_sequence_{suffix}.json"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return DiscoveryUnlockSequenceResult(markdown_path=markdown_path, json_path=json_path, passed=bool(payload["passed"]))

    def build_payload(self, report_date: date) -> dict[str, Any]:
        approval_payload = DiscoveryApprovalPacketBuilder(self._settings).build_payload(report_date)
        operator_payload = DiscoverySlotOperatorPacketBuilder(self._settings).build_payload(report_date)

        operator_index = {
            str(item.get("approval_id") or ""): item
            for item in operator_payload.get("packets") or []
            if str(item.get("approval_id") or "").strip()
        }

        sequences = [
            _unlock_sequence(item, operator_index.get(str(item.get("approval_id") or ""), {}), index)
            for index, item in enumerate(approval_payload.get("packets") or [], start=1)
            if item.get("decision_waiting")
        ]
        sequences.sort(
            key=lambda item: (
                -int(item.get("decision_wait_match_count") or 0),
                -int(item.get("unlock_slot_count") or 0),
                str(item.get("approval_id") or ""),
            )
        )

        return {
            "report_date": report_date.isoformat(),
            "mode": "discovery_unlock_sequence",
            "passed": True,
            "rules": {
                "signal_only": True,
                "approval_gated": True,
                "no_platform_write": True,
                "purpose": "Rank discovery approvals and slots by how many current decisions they can reopen.",
            },
            "summary": {
                "sequence_count": len(sequences),
                "decision_waiting_approvals": sum(1 for item in sequences if item.get("decision_wait_match_count")),
                "total_reopened_decision_targets": sum(len(item.get("reopened_decision_targets") or []) for item in sequences),
                "total_unlock_slots": sum(int(item.get("unlock_slot_count") or 0) for item in sequences),
            },
            "sequences": sequences,
        }

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload.get("summary") or {}
        lines = [
            f"# Discovery Unlock Sequence | {payload['report_date']}",
            "",
            "- Mode: discovery_unlock_sequence",
            "- Purpose: show the approval and slot order that can reopen the most currently blocked decisions first.",
            "- Boundary: signal-only, approval-gated, no platform write.",
            "",
            "## Summary",
            "",
            f"- Sequences: {summary.get('sequence_count', 0)}",
            f"- Decision-waiting approvals: {summary.get('decision_waiting_approvals', 0)}",
            f"- Reopened decision targets: {summary.get('total_reopened_decision_targets', 0)}",
            f"- Unlock slots: {summary.get('total_unlock_slots', 0)}",
            "",
            "## Ranked Sequence",
            "",
        ]
        if not payload.get("sequences"):
            lines.append("- None.")
        for item in payload.get("sequences") or []:
            lines.append(f"### {item['sequence_id']} | {item['approval_id']} | {item['target']}")
            lines.append(f"- Manual approval state: {item['manual_approval_state']}")
            lines.append(f"- Matched decisions: {item['decision_wait_match_count']}")
            lines.append(f"- Unlock order: {' -> '.join(item.get('unlock_order') or []) or 'none'}")
            targets = [
                f"{target.get('entity_type')}:{target.get('entity_id')} ({target.get('decision')})"
                for target in list(item.get("reopened_decision_targets") or [])[:8]
                if str(target.get("entity_id") or "").strip()
            ]
            lines.append(f"- Reopened decisions: {', '.join(targets) or 'none'}")
            lines.append("- Slot priorities:")
            for slot in item.get("slots") or []:
                targets = [
                    f"{target.get('entity_type')}:{target.get('entity_id')}"
                    for target in list(slot.get("reopened_decision_targets") or [])[:5]
                    if str(target.get("entity_id") or "").strip()
                ]
                lines.append(
                    f"  - {slot['slot_id']} | {slot['slot_status']} | focus={slot['change_focus']} | "
                    f"unlocks={slot.get('decision_wait_match_count', 0)} | next={slot['next_step']} | "
                    f"targets={', '.join(targets) or 'none'}"
                )
            lines.append("")
        return "\n".join(lines)


def _unlock_sequence(approval_packet: dict[str, Any], operator_packet: dict[str, Any], index: int) -> dict[str, Any]:
    slots = list(operator_packet.get("slots") or approval_packet.get("slots") or [])
    slots = sorted(
        slots,
        key=lambda item: (
            -int(item.get("decision_wait_match_count") or 0),
            str(item.get("slot_id") or ""),
        ),
    )
    reopened_targets = _unique_targets(
        [
            dict(target)
            for slot in slots
            for target in list(slot.get("decision_wait_targets") or [])
            if isinstance(target, dict)
        ]
    )
    sequence_slots = [
        {
            "slot_id": str(slot.get("slot_id") or ""),
            "slot_status": str(slot.get("slot_status") or ""),
            "change_focus": str(slot.get("change_focus") or ""),
            "decision_wait_match_count": int(slot.get("decision_wait_match_count") or 0),
            "next_step": str(slot.get("next_operator_step") or slot.get("next_after_approval") or ""),
            "reopened_decision_targets": list(slot.get("decision_wait_targets") or [])[:10],
        }
        for slot in slots
    ]
    unlock_order = [
        str(slot.get("slot_id") or "")
        for slot in sequence_slots
        if int(slot.get("decision_wait_match_count") or 0) > 0
    ][:8]
    return {
        "sequence_id": f"unlock_sequence_{index:03d}",
        "approval_id": approval_packet.get("approval_id", ""),
        "experiment_id": approval_packet.get("experiment_id", ""),
        "target": approval_packet.get("target", ""),
        "manual_approval_state": approval_packet.get("manual_approval_state", ""),
        "manual_approval_input_file": operator_packet.get("manual_approval_input_file", ""),
        "slot_manual_input_file": operator_packet.get("slot_manual_input_file", approval_packet.get("slot_manual_input_file", "")),
        "decision_wait_match_count": int(approval_packet.get("decision_wait_match_count") or 0),
        "reopened_decision_targets": reopened_targets[:20],
        "unlock_slot_count": len(unlock_order),
        "unlock_order": unlock_order,
        "slots": sequence_slots[:12],
    }


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
