from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.experiment_result_ingestion import ExperimentResultIngestionBuilder
from market_ops.discovery_slot_operator_packet import DiscoverySlotOperatorPacketBuilder
from market_ops.discovery_unlock_operator_handoff import DiscoveryUnlockOperatorHandoffBuilder


@dataclass(slots=True)
class DiscoveryActionQueueResult:
    markdown_path: Path
    json_path: Path
    passed: bool


class DiscoveryActionQueueBuilder:
    """Build a standardized manual action queue for discovery approvals, slot creation, and result capture."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> DiscoveryActionQueueResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self.build_payload(report_date)

        markdown_path = output_dir / f"discovery_action_queue_{suffix}.md"
        json_path = output_dir / f"discovery_action_queue_{suffix}.json"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return DiscoveryActionQueueResult(
            markdown_path=markdown_path,
            json_path=json_path,
            passed=bool(payload["passed"]),
        )

    def build_payload(self, report_date: date) -> dict[str, Any]:
        handoff_payload = DiscoveryUnlockOperatorHandoffBuilder(self._settings).build_payload(report_date)
        operator_payload = DiscoverySlotOperatorPacketBuilder(self._settings).build_payload(report_date)
        result_payload = ExperimentResultIngestionBuilder(self._settings).build_payload(report_date)

        operator_index = {
            str(item.get("approval_id") or ""): item
            for item in operator_payload.get("packets") or []
            if str(item.get("approval_id") or "").strip()
        }
        result_index = {
            str(item.get("approval_id") or ""): item
            for item in result_payload.get("result_rows") or []
            if str(item.get("approval_id") or "").strip()
        }

        actions = [
            action
            for handoff in handoff_payload.get("handoffs") or []
            for action in _action_items(
                handoff=handoff,
                operator_packet=operator_index.get(str(handoff.get("approval_id") or ""), {}),
                result_row=result_index.get(str(handoff.get("approval_id") or ""), {}),
            )
        ]
        actions.sort(
            key=lambda item: (
                int(item.get("queue_rank") or 0),
                int(item.get("slot_rank") or 0),
                str(item.get("approval_id") or ""),
                str(item.get("slot_id") or ""),
            )
        )

        return {
            "report_date": report_date.isoformat(),
            "mode": "discovery_action_queue",
            "passed": True,
            "rules": {
                "signal_only": True,
                "approval_gated": True,
                "manual_execution_only": True,
                "no_platform_write": True,
                "purpose": "Standardize the exact ordered human actions needed to unlock discovery learning and reopen blocked decisions.",
            },
            "summary": {
                "action_count": len(actions),
                "approval_input_count": sum(1 for item in actions if item.get("action_type") == "approval_input"),
                "create_variant_count": sum(1 for item in actions if item.get("action_type") == "create_variant"),
                "capture_result_count": sum(1 for item in actions if item.get("action_type") == "capture_result"),
                "review_learning_count": sum(1 for item in actions if item.get("action_type") == "review_learning"),
                "close_parent_result_count": sum(1 for item in actions if item.get("action_type") == "close_parent_result"),
                "critical_count": sum(1 for item in actions if item.get("priority_label") == "critical_learning_blocker"),
            },
            "actions": actions,
        }

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload.get("summary") or {}
        lines = [
            f"# Discovery Action Queue | {payload['report_date']}",
            "",
            "- Mode: discovery_action_queue",
            "- Purpose: convert discovery unlock handoffs into the exact ordered human action queue.",
            "- Boundary: signal-only, approval-gated, manual execution only, no platform write.",
            "",
            "## Summary",
            "",
            f"- Actions: {summary.get('action_count', 0)}",
            f"- Approval inputs: {summary.get('approval_input_count', 0)}",
            f"- Create variant: {summary.get('create_variant_count', 0)}",
            f"- Capture result: {summary.get('capture_result_count', 0)}",
            f"- Review learning: {summary.get('review_learning_count', 0)}",
            f"- Close parent result: {summary.get('close_parent_result_count', 0)}",
            f"- Critical learning blockers: {summary.get('critical_count', 0)}",
            "",
            "## Ordered Actions",
            "",
        ]
        if not payload.get("actions"):
            lines.append("- None.")
        else:
            lines.extend(
                [
                    "| Queue | Type | Priority | Approval | Slot | Human surface | Work item |",
                    "|---:|---|---|---|---|---|---|",
                ]
            )
            for item in payload.get("actions") or []:
                lines.append(
                    f"| {item['queue_rank']} | {item['action_type']} | {item['priority_label']} | {item['approval_id']} | "
                    f"{item['slot_id'] or '-'} | {item['human_surface']} | {item['human_work_item']} |"
                )
        lines.append("")
        return "\n".join(lines)


def _action_items(*, handoff: dict[str, Any], operator_packet: dict[str, Any], result_row: dict[str, Any]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    approval_id = str(handoff.get("approval_id") or "")
    experiment_id = str(handoff.get("experiment_id") or "")
    target = str(handoff.get("target") or "")
    priority_label = "critical_learning_blocker" if int(handoff.get("decision_wait_match_count") or 0) > 0 else "standard"
    manual_approval_input_file = str(handoff.get("manual_approval_input_file") or "")
    slot_manual_input_file = str(handoff.get("slot_manual_input_file") or "")
    parent_manual_input_file = str(result_row.get("manual_input_file") or "")
    decision_wait_match_count = int(handoff.get("decision_wait_match_count") or 0)

    queue_rank = 1
    if handoff.get("approval_step_required"):
        actions.append(
            {
                "action_id": f"{approval_id}_approval_input",
                "queue_rank": queue_rank,
                "slot_rank": 0,
                "action_type": "approval_input",
                "priority_label": priority_label,
                "approval_id": approval_id,
                "experiment_id": experiment_id,
                "target": target,
                "slot_id": "",
                "human_surface": manual_approval_input_file,
                "human_work_item": str(handoff.get("approval_next_step") or ""),
                "decision_wait_match_count": decision_wait_match_count,
                "manual_state": str(handoff.get("manual_approval_state") or ""),
                "reopened_decision_targets": list(handoff.get("reopened_decision_targets") or [])[:10],
            }
        )
        queue_rank += 1

    operator_slots = {
        str(item.get("slot_id") or ""): item
        for item in operator_packet.get("slots") or []
        if str(item.get("slot_id") or "").strip()
    }

    for slot_index, slot in enumerate(handoff.get("slot_execution_order") or [], start=1):
        slot_id = str(slot.get("slot_id") or "")
        slot_status = str(slot.get("slot_status") or "")
        operator_slot = operator_slots.get(slot_id, {})
        action_type = _slot_action_type(slot_status)
        human_surface = slot_manual_input_file if action_type in {"create_variant", "capture_result", "review_learning"} else manual_approval_input_file
        human_work_item = str(slot.get("human_work_item") or "")
        if operator_slot.get("execution_instruction") and action_type == "create_variant":
            human_work_item = f"{human_work_item} {str(operator_slot.get('execution_instruction') or '').strip()}".strip()
        actions.append(
            {
                "action_id": f"{approval_id}_{slot_id}_{action_type}",
                "queue_rank": queue_rank + slot_index - 1,
                "slot_rank": slot_index,
                "action_type": action_type,
                "priority_label": priority_label,
                "approval_id": approval_id,
                "experiment_id": experiment_id,
                "target": target,
                "slot_id": slot_id,
                "human_surface": human_surface,
                "human_work_item": human_work_item,
                "decision_wait_match_count": int(slot.get("decision_wait_match_count") or 0),
                "slot_status": slot_status,
                "change_focus": str(slot.get("change_focus") or ""),
                "next_step": str(slot.get("next_step") or ""),
                "learning_binding": dict(operator_slot.get("learning_binding") or {}),
                "reopened_decision_targets": list(slot.get("reopened_decision_targets") or [])[:10],
            }
        )

    actions.append(
        {
            "action_id": f"{approval_id}_close_parent_result",
            "queue_rank": queue_rank + len(handoff.get("slot_execution_order") or []),
            "slot_rank": 999,
            "action_type": "close_parent_result",
            "priority_label": priority_label,
            "approval_id": approval_id,
            "experiment_id": experiment_id,
            "target": target,
            "slot_id": "",
            "human_surface": parent_manual_input_file or slot_manual_input_file,
            "human_work_item": (
                "After slot execution and win/loss capture are present, close the parent result row by filling "
                "created_variant_count, linked_new_creative_ids, and learning_note."
            ),
            "decision_wait_match_count": decision_wait_match_count,
            "parent_result_state": str(result_row.get("result_state") or ""),
            "parent_result_required_fields": [
                "created_variant_count",
                "linked_new_creative_ids",
                "learning_note",
            ],
            "reopened_decision_targets": list(handoff.get("reopened_decision_targets") or [])[:10],
        }
    )

    return actions


def _slot_action_type(slot_status: str) -> str:
    if slot_status == "awaiting_result":
        return "capture_result"
    if slot_status == "learned":
        return "review_learning"
    return "create_variant"
