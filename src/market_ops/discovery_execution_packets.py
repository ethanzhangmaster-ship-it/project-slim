from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.discovery_test_plans import DiscoveryTestPlansBuilder


@dataclass(slots=True)
class DiscoveryExecutionPacketsResult:
    markdown_path: Path
    json_path: Path
    passed: bool


class DiscoveryExecutionPacketsBuilder:
    """Builds slot-level execution packets from structured discovery test plans."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> DiscoveryExecutionPacketsResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self.build_payload(report_date)

        markdown_path = output_dir / f"discovery_execution_packets_{suffix}.md"
        json_path = output_dir / f"discovery_execution_packets_{suffix}.json"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return DiscoveryExecutionPacketsResult(markdown_path=markdown_path, json_path=json_path, passed=bool(payload["passed"]))

    def build_payload(self, report_date: date) -> dict[str, Any]:
        plans_payload = DiscoveryTestPlansBuilder(self._settings).build_payload(report_date)
        packets = [
            _packet(plan, index)
            for index, plan in enumerate(plans_payload.get("plans") or [], start=1)
        ]
        return {
            "report_date": report_date.isoformat(),
            "mode": "discovery_execution_packets",
            "passed": True,
            "rules": {
                "signal_only": True,
                "approval_gated": True,
                "no_platform_write": True,
                "manual_execution_required": True,
            },
            "summary": {
                "packet_count": len(packets),
                "slot_count": sum(len(item.get("slot_packets") or []) for item in packets),
                "approval_blocked_count": sum(1 for item in packets if item.get("approval_status") == "approval_blocked"),
            },
            "packets": packets,
        }

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload.get("summary") or {}
        lines = [
            f"# Discovery Execution Packets | {payload['report_date']}",
            "",
            "- Mode: discovery_execution_packets",
            "- Purpose: turn discovery test plans into slot-level execution task packets.",
            "- Boundary: signal-only, approval-gated, no platform write.",
            "",
            "## Summary",
            "",
            f"- Packets: {summary.get('packet_count', 0)}",
            f"- Slot packets: {summary.get('slot_count', 0)}",
            f"- Approval blocked: {summary.get('approval_blocked_count', 0)}",
            "",
            "## Packets",
            "",
        ]
        if not payload.get("packets"):
            lines.append("- None.")
        for item in payload.get("packets") or []:
            lines.append(f"### {item['packet_id']} | {item['target']}")
            lines.append(f"- Status: approval={item['approval_status']} | intent={item['intent_status']}")
            lines.append(f"- Naming rule: {item['naming_rule']}")
            lines.append(f"- Allowed change: {item['allowed_change_summary']}")
            lines.append(f"- Manual result file: {item['manual_result_file']}")
            lines.append("- Slot packets:")
            for slot in item.get("slot_packets") or []:
                lines.append(
                    f"  - {slot['slot_id']} | {slot['variant_name']} | focus={slot['change_focus']} | "
                    f"baseline={slot['baseline_anchor']} | action={slot['recommended_operator_action']}"
                )
            lines.append("")
        return "\n".join(lines)


def _packet(plan: dict[str, Any], index: int) -> dict[str, Any]:
    slot_packets = [_slot_packet(plan, slot) for slot in plan.get("variant_slots") or []]
    return {
        "packet_id": f"exec_packet_{index:03d}",
        "plan_id": plan.get("plan_id", ""),
        "card_id": plan.get("card_id", ""),
        "experiment_id": plan.get("experiment_id", ""),
        "approval_id": plan.get("approval_id", ""),
        "target": plan.get("target", ""),
        "approval_status": plan.get("approval_status", ""),
        "intent_id": plan.get("intent_id", ""),
        "intent_status": plan.get("intent_status", ""),
        "variant_count_target": int(plan.get("variant_count_target") or 0),
        "primary_test_axis": plan.get("primary_test_axis", ""),
        "control_dimensions": list(plan.get("control_dimensions") or []),
        "naming_rule": plan.get("naming_rule", ""),
        "allowed_change_summary": (plan.get("execution_constraints") or {}).get("allowed_change_summary", ""),
        "manual_result_file": "output\\active\\experiment_result_input_20260610.csv",
        "slot_packets": slot_packets,
    }


def _slot_packet(plan: dict[str, Any], slot: dict[str, Any]) -> dict[str, Any]:
    return {
        "slot_id": slot.get("slot_id", ""),
        "variant_name": slot.get("variant_name", ""),
        "change_focus": slot.get("change_focus", ""),
        "baseline_anchor": slot.get("baseline_anchor", ""),
        "must_hold_constant": list(slot.get("must_hold_constant") or []),
        "planned_test_axis": slot.get("planned_test_axis", ""),
        "recommended_operator_action": _recommended_operator_action(plan, slot),
        "result_capture_hint": "Fill execution_status, actual_result_note, success, CTR, CPI, ROI/ROAS, created_variant_count, linked_new_creative_ids, learning_note, and slot_result_summary using slot_XX:win|loss:summary format.",
    }


def _recommended_operator_action(plan: dict[str, Any], slot: dict[str, Any]) -> str:
    target = str(plan.get("target") or "")
    variant_name = str(slot.get("variant_name") or "")
    focus = str(slot.get("change_focus") or "")
    return f"Create variant {variant_name} for {target} using focus {focus} while keeping targeting and budget fixed."
