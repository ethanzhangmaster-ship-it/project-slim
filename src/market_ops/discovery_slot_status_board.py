from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.discovery_approval_state import (
    approval_is_rejected,
    approval_is_unblocked,
    discovery_approval_input_path,
    load_discovery_approval_inputs,
)
from market_ops.discovery_result_capture_packets import DiscoveryResultCapturePacketsBuilder
from market_ops.discovery_execution_packets import DiscoveryExecutionPacketsBuilder
from market_ops.discovery_learning_packets import DiscoveryLearningPacketsBuilder
from market_ops.discovery_test_plans import DiscoveryTestPlansBuilder
from market_ops.discovery_experiment_cards import DiscoveryExperimentCardsBuilder
from market_ops.experiment_result_ingestion import ExperimentResultIngestionBuilder
from market_ops.learning_evidence_queue import LearningEvidenceQueueBuilder


@dataclass(slots=True)
class DiscoverySlotStatusBoardResult:
    markdown_path: Path
    json_path: Path
    passed: bool


class DiscoverySlotStatusBoardBuilder:
    """Builds an operator-facing status board for discovery slots and their learning progress."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> DiscoverySlotStatusBoardResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self.build_payload(report_date)

        markdown_path = output_dir / f"discovery_slot_status_board_{suffix}.md"
        json_path = output_dir / f"discovery_slot_status_board_{suffix}.json"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return DiscoverySlotStatusBoardResult(markdown_path=markdown_path, json_path=json_path, passed=bool(payload["passed"]))

    def build_payload(self, report_date: date) -> dict[str, Any]:
        cards_payload = DiscoveryExperimentCardsBuilder(self._settings).build_payload(report_date)
        plans_payload = DiscoveryTestPlansBuilder(self._settings).build_payload(report_date)
        execution_payload = DiscoveryExecutionPacketsBuilder(self._settings).build_payload(report_date)
        learning_payload = DiscoveryLearningPacketsBuilder(self._settings).build_payload(report_date)
        capture_payload = DiscoveryResultCapturePacketsBuilder(self._settings).build_payload(report_date)
        evidence_payload = LearningEvidenceQueueBuilder(self._settings).build_payload(report_date)
        result_payload = ExperimentResultIngestionBuilder(self._settings).build_payload(report_date)
        manual_approval_input_file = discovery_approval_input_path(self._settings.active_output_dir, report_date)
        approval_input = load_discovery_approval_inputs(manual_approval_input_file)

        card_index = {str(item.get("experiment_id") or ""): item for item in cards_payload.get("cards") or []}
        plan_index = {str(item.get("experiment_id") or ""): item for item in plans_payload.get("plans") or []}
        execution_index = {str(item.get("experiment_id") or ""): item for item in execution_payload.get("packets") or []}
        learning_index = {str(item.get("experiment_id") or ""): item for item in learning_payload.get("packets") or []}
        result_index = {str(item.get("experiment_id") or ""): item for item in result_payload.get("result_rows") or []}
        evidence_by_slot = {
            (str(item.get("experiment_id") or ""), str(item.get("slot_id") or "")): item
            for item in evidence_payload.get("queue_items") or []
            if str(item.get("experiment_type") or "") == "discovery_slot_test"
        }

        rows: list[dict[str, Any]] = []
        for capture_packet in capture_payload.get("packets") or []:
            experiment_id = str(capture_packet.get("experiment_id") or "")
            card = card_index.get(experiment_id, {})
            plan = plan_index.get(experiment_id, {})
            execution_packet = execution_index.get(experiment_id, {})
            learning_packet = learning_index.get(experiment_id, {})
            result_row = result_index.get(experiment_id, {})
            for slot in capture_packet.get("slot_capture_packets") or []:
                slot_id = str(slot.get("slot_id") or "")
                evidence = evidence_by_slot.get((experiment_id, slot_id), {})
                rows.append(
                    _slot_row(
                        capture_packet=capture_packet,
                        slot=slot,
                        card=card,
                        plan=plan,
                        execution_packet=execution_packet,
                        learning_packet=learning_packet,
                        result_row=result_row,
                        evidence=evidence,
                        approval_input=approval_input.get(str(capture_packet.get("approval_id") or ""), {}),
                        manual_approval_input_file=str(manual_approval_input_file),
                    )
                )

        return {
            "report_date": report_date.isoformat(),
            "mode": "discovery_slot_status_board",
            "passed": True,
            "rules": {
                "signal_only": True,
                "approval_gated": True,
                "no_platform_write": True,
                "slot_manual_input_file": str(self._settings.active_output_dir / f"discovery_slot_result_input_{report_date.strftime('%Y%m%d')}.csv"),
                "manual_approval_input_file": str(manual_approval_input_file),
            },
            "summary": {
                "slot_count": len(rows),
                "approval_blocked_count": sum(1 for item in rows if item.get("slot_status") == "approval_blocked"),
                "ready_to_execute_count": sum(1 for item in rows if item.get("slot_status") == "ready_to_execute"),
                "awaiting_result_count": sum(1 for item in rows if item.get("slot_status") == "awaiting_result"),
                "learned_count": sum(1 for item in rows if item.get("slot_status") == "learned"),
                "decision_waiting_slot_count": sum(1 for item in rows if item.get("decision_waiting")),
            },
            "rows": rows,
        }

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload.get("summary") or {}
        lines = [
            f"# Discovery Slot Status Board | {payload['report_date']}",
            "",
            "- Mode: discovery_slot_status_board",
            "- Purpose: show each discovery slot as an operator-facing execution and learning state row.",
            "- Boundary: signal-only, approval-gated, no platform write.",
            f"- Slot input file: {(payload.get('rules') or {}).get('slot_manual_input_file', '')}",
            "",
            "## Summary",
            "",
            f"- Slots: {summary.get('slot_count', 0)}",
            f"- Approval blocked: {summary.get('approval_blocked_count', 0)}",
            f"- Ready to execute: {summary.get('ready_to_execute_count', 0)}",
            f"- Awaiting result: {summary.get('awaiting_result_count', 0)}",
            f"- Learned: {summary.get('learned_count', 0)}",
            f"- Decision-waiting slots: {summary.get('decision_waiting_slot_count', 0)}",
            "",
            "## Slots",
            "",
        ]
        if not payload.get("rows"):
            lines.append("- None.")
        for item in payload.get("rows") or []:
            required = ", ".join(item.get("required_fields") or []) or "none"
            missing = ", ".join(item.get("missing_evidence") or []) or "none"
            lines.append(
                f"- {item['approval_id']} / {item['slot_id']} | {item['slot_status']} | {item['target']} | "
                f"focus={item['change_focus']} | unlocks={item.get('decision_wait_match_count', 0)} | required={required} | missing={missing}"
            )
        lines.append("")
        return "\n".join(lines)


def _slot_row(
    *,
    capture_packet: dict[str, Any],
    slot: dict[str, Any],
    card: dict[str, Any],
    plan: dict[str, Any],
    execution_packet: dict[str, Any],
    learning_packet: dict[str, Any],
    result_row: dict[str, Any],
    evidence: dict[str, Any],
    approval_input: dict[str, str],
    manual_approval_input_file: str,
) -> dict[str, Any]:
    approval_status = _effective_approval_status(
        str(capture_packet.get("approval_status") or card.get("approval_status") or ""),
        approval_input,
    )
    required_fields = list(slot.get("required_fields") or [])
    result_state = str(result_row.get("result_state") or "")
    slot_packet = _slot_result_packet(result_row, str(slot.get("slot_id") or ""))
    missing_evidence = _slot_missing_evidence(approval_status, slot_packet, required_fields)
    slot_status = _slot_status(approval_status, missing_evidence, slot_packet, result_state)
    return {
        "approval_id": capture_packet.get("approval_id", ""),
        "experiment_id": capture_packet.get("experiment_id", ""),
        "target": capture_packet.get("target", ""),
        "slot_id": slot.get("slot_id", ""),
        "slot_status": slot_status,
        "approval_status": approval_status,
        "manual_approval_state": _manual_approval_state(approval_input),
        "manual_approval_decision": str(approval_input.get("approval_decision") or ""),
        "manual_approval_note": str(approval_input.get("approval_note") or ""),
        "result_state": result_state,
        "slot_result_state": _slot_result_state(slot_packet, required_fields),
        "change_focus": slot.get("change_focus", ""),
        "variant_name": slot.get("variant_name", ""),
        "learning_question": slot.get("learning_question", ""),
        "required_fields": required_fields,
        "recommended_fields": list(slot.get("recommended_fields") or []),
        "missing_evidence": missing_evidence,
        "slot_result_example": slot.get("slot_result_example", ""),
        "decision_waiting": bool(slot.get("decision_waiting")),
        "decision_wait_match_count": int(slot.get("decision_wait_match_count") or 0),
        "decision_wait_entity_ids": list(slot.get("decision_wait_entity_ids") or [])[:20],
        "decision_wait_targets": list(slot.get("decision_wait_targets") or [])[:10],
        "resolution_priority_rank": int(slot.get("decision_wait_match_count") or 0),
        "manual_input_file": evidence.get("manual_input_file", "") or capture_packet.get("slot_manual_input_file", ""),
        "parent_manual_input_file": manual_approval_input_file,
        "result_template_file": capture_packet.get("result_template_file", ""),
        "variant_plan_summary": plan.get("variant_plan_summary", "") or card.get("variant_plan_summary", ""),
        "baseline_anchor_preview": _baseline_anchor(slot, plan, execution_packet),
        "execution_packet_id": execution_packet.get("packet_id", ""),
        "learning_packet_id": learning_packet.get("learning_packet_id", ""),
        "next_learning_step": capture_packet.get("next_learning_step", ""),
    }


def _slot_status(approval_status: str, missing_evidence: list[str], slot_packet: dict[str, Any], result_state: str) -> str:
    missing = {str(item or "").strip() for item in missing_evidence if str(item or "").strip()}
    if approval_status in {"approval_blocked", "approval_rejected"} or "approval_unblocked" in missing:
        return "approval_blocked"
    if _slot_result_state(slot_packet, []) == "closed":
        return "learned"
    if "execution_status" in missing:
        return "ready_to_execute"
    if "slot_result_summary" in missing or "success" in missing:
        return "awaiting_result"
    if result_state == "closed" and not missing:
        return "learned"
    return "in_review"


def _slot_missing_evidence(
    approval_status: str,
    slot_packet: dict[str, Any],
    required_fields: list[str],
) -> list[str]:
    missing: list[str] = []
    if approval_status not in {"approved_for_manual_execution"}:
        missing.append("approval_unblocked")
    for field in required_fields:
        if field == "success":
            if _parse_success(slot_packet.get("success")) is None:
                missing.append(field)
        elif not str(slot_packet.get(field) or "").strip():
            missing.append(field)
    return missing


def _slot_result_packet(result_row: dict[str, Any], slot_id: str) -> dict[str, Any]:
    for packet in result_row.get("slot_packets") or []:
        if str(packet.get("slot_id") or "") == slot_id:
            return dict(packet)
    return {}


def _slot_result_state(slot_packet: dict[str, Any], required_fields: list[str]) -> str:
    if not slot_packet:
        return "missing"
    checks = required_fields or ["execution_status", "slot_result_summary", "success"]
    missing = _slot_missing_evidence("approved_for_manual_execution", slot_packet, checks)
    if missing:
        return "open"
    return "closed"


def _parse_success(value: Any) -> bool | None:
    text = str(value or "").strip().lower()
    if text in {"true", "1", "yes", "y", "success", "passed", "win", "won"}:
        return True
    if text in {"false", "0", "no", "n", "failed", "fail", "loss", "lost"}:
        return False
    return None


def _baseline_anchor(slot: dict[str, Any], plan: dict[str, Any], execution_packet: dict[str, Any]) -> str:
    anchor = str(slot.get("baseline_anchor") or "").strip()
    if anchor:
        return anchor
    slot_id = str(slot.get("slot_id") or "").strip()
    for packet_slot in execution_packet.get("slot_packets") or []:
        if str(packet_slot.get("slot_id") or "").strip() != slot_id:
            continue
        packet_anchor = str(packet_slot.get("baseline_anchor") or "").strip()
        if packet_anchor:
            return packet_anchor
    preview = list(plan.get("baseline_asset_preview") or [])
    return preview[0] if preview else ""


def _effective_approval_status(base_status: str, approval_input: dict[str, str]) -> str:
    if approval_is_unblocked(approval_input):
        return "approved_for_manual_execution"
    if approval_is_rejected(approval_input):
        return "approval_rejected"
    return base_status


def _manual_approval_state(approval_input: dict[str, str]) -> str:
    if approval_is_unblocked(approval_input):
        return "approved_for_manual_execution"
    if approval_is_rejected(approval_input):
        return "approval_rejected"
    return "approval_pending_input"
