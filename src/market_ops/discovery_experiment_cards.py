from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.approval_feedback_gate import ApprovalFeedbackGateBuilder
from market_ops.config import Settings
from market_ops.experiment_result_ingestion import ExperimentResultIngestionBuilder


@dataclass(slots=True)
class DiscoveryExperimentCardsResult:
    markdown_path: Path
    json_path: Path
    passed: bool


class DiscoveryExperimentCardsBuilder:
    """Builds approval-gated experiment cards for discovery-stage creative tests."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> DiscoveryExperimentCardsResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self.build_payload(report_date)

        markdown_path = output_dir / f"discovery_experiment_cards_{suffix}.md"
        json_path = output_dir / f"discovery_experiment_cards_{suffix}.json"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return DiscoveryExperimentCardsResult(markdown_path=markdown_path, json_path=json_path, passed=bool(payload["passed"]))

    def build_payload(self, report_date: date) -> dict[str, Any]:
        suffix = report_date.strftime("%Y%m%d")
        output_dir = self._settings.active_output_dir
        approval_payload = ApprovalFeedbackGateBuilder(self._settings).build_payload(report_date)
        result_payload = ExperimentResultIngestionBuilder(self._settings).build_payload(report_date)
        result_index = {
            str(item.get("experiment_id") or ""): item
            for item in result_payload.get("result_rows") or []
            if str(item.get("experiment_id") or "").strip()
        }
        cards = [
            _card(
                approval=item,
                result_row=result_index.get(str(item.get("experiment_id") or ""), {}),
                manual_input_file=str(output_dir / f"experiment_result_input_{suffix}.csv"),
                slot_manual_input_file=str(output_dir / f"discovery_slot_result_input_{suffix}.csv"),
                template_file=str(output_dir / f"experiment_result_template_{suffix}.csv"),
                index=index,
            )
            for index, item in enumerate(approval_payload.get("approval_items") or [], start=1)
            if _is_discovery_item(item)
        ]
        return {
            "report_date": report_date.isoformat(),
            "mode": "discovery_experiment_cards",
            "passed": True,
            "rules": {
                "signal_only": True,
                "approval_gated": True,
                "no_platform_write": True,
                "manual_result_capture_required": True,
            },
            "summary": {
                "card_count": len(cards),
                "approval_blocked_count": sum(1 for item in cards if item["approval_status"] == "approval_blocked"),
                "needs_manual_input_count": sum(1 for item in cards if item["result_state"] != "closed"),
            },
            "cards": cards,
        }

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload.get("summary") or {}
        lines = [
            f"# Discovery Experiment Cards | {payload['report_date']}",
            "",
            "- Mode: discovery_experiment_cards",
            "- Purpose: convert discovery experiments into auditable, execution-ready, result-capture-ready cards.",
            "- Boundary: signal-only, approval-gated, no platform write.",
            "",
            "## Summary",
            "",
            f"- Cards: {summary.get('card_count', 0)}",
            f"- Approval blocked: {summary.get('approval_blocked_count', 0)}",
            f"- Needs manual input: {summary.get('needs_manual_input_count', 0)}",
            "",
            "## Cards",
            "",
        ]
        if not payload.get("cards"):
            lines.append("- None.")
        for item in payload.get("cards") or []:
            lines.append(f"### {item['card_id']} | {item['target']}")
            lines.append(f"- Status: approval={item['approval_status']} | result={item['result_state']}")
            lines.append(f"- Learning goal: {item['learning_goal']}")
            lines.append(f"- Variant brief: {item['variant_plan_summary']}")
            lines.append(f"- Why this test first: {item.get('structural_test_rationale') or item.get('discovery_pattern_prior_reason') or 'none'}")
            lines.append(f"- Prioritized focuses: {', '.join(item.get('discovery_prioritized_change_focuses') or []) or 'none'}")
            lines.append(f"- Baseline preview: {', '.join(item['baseline_asset_preview']) or 'none'}")
            lines.append(f"- Controls fixed: {', '.join(item['control_dimensions']) or 'none'}")
            lines.append(f"- Parent manual input file: {item['manual_input_file']}")
            lines.append(f"- Slot manual input file: {item['slot_manual_input_file']}")
            lines.append(f"- Template file: {item['template_file']}")
            if item.get("setup_instructions"):
                lines.append("- Setup:")
                for step in item["setup_instructions"]:
                    lines.append(f"  - {step}")
            if item.get("review_checklist"):
                lines.append("- Review checklist:")
                for step in item["review_checklist"]:
                    lines.append(f"  - {step}")
            if item.get("result_capture_fields"):
                lines.append(f"- Required result fields: {', '.join(item['result_capture_fields'])}")
            if item.get("recommended_result_fields"):
                lines.append(f"- Recommended result fields: {', '.join(item['recommended_result_fields'])}")
            lines.append("")
        return "\n".join(lines)


def _is_discovery_item(item: dict[str, Any]) -> bool:
    return str(item.get("experiment_id") or "").startswith("discovery_plan_") or str(item.get("source") or "") == "discovery_backlog"


def _card(
    *,
    approval: dict[str, Any],
    result_row: dict[str, Any],
    manual_input_file: str,
    slot_manual_input_file: str,
    template_file: str,
    index: int,
) -> dict[str, Any]:
    target = str(approval.get("target") or "")
    test_type = str(approval.get("test_type") or "")
    variant_count_target = int(approval.get("variant_count_target") or 0)
    control_dimensions = list(approval.get("control_dimensions") or [])
    review_checklist = [
        "Confirm baseline assets exist and are the intended winner controls.",
        f"Confirm only the planned axis changes: {_allowed_change_summary(test_type)}.",
        "Confirm targeting and budget remain fixed across the test window.",
        "After execution, first fill execution_status, actual_result_note, success, and slot_result_summary to unlock learning.",
        "Then add CTR, CPI, ROI/ROAS, variant count, and learning note as recommended enrichments.",
    ]
    return {
        "card_id": f"discovery_card_{index:03d}",
        "experiment_id": approval.get("experiment_id", ""),
        "approval_id": approval.get("approval_id", ""),
        "target": target,
        "project": approval.get("project", ""),
        "channel": approval.get("channel", ""),
        "country": approval.get("country", ""),
        "approval_status": approval.get("approval_status", ""),
        "result_state": result_row.get("result_state", "needs_manual_input"),
        "test_type": test_type,
        "learning_goal": approval.get("learning_goal", ""),
        "variant_count_target": variant_count_target,
        "variant_plan_summary": str(approval.get("variant_plan_summary") or _fallback_variant_plan_summary(test_type, variant_count_target)),
        "primary_test_axis": approval.get("primary_test_axis", ""),
        "control_dimensions": control_dimensions,
        "allowed_change_summary": _allowed_change_summary(test_type),
        "structural_test_rationale": approval.get("structural_test_rationale", ""),
        "winner_structure_bias": list(approval.get("winner_structure_bias") or []),
        "discovery_prioritized_change_focuses": list(approval.get("discovery_prioritized_change_focuses") or []),
        "discovery_pattern_prior_reason": approval.get("discovery_pattern_prior_reason", ""),
        "baseline_asset_type": approval.get("baseline_asset_type", ""),
        "baseline_asset_preview": list(approval.get("baseline_asset_preview") or []),
        "baseline_creative_names": list(approval.get("baseline_creative_names") or []),
        "baseline_creative_ids": list(approval.get("baseline_creative_ids") or []),
        "winner_material_asset_count": int(approval.get("winner_material_asset_count") or 0),
        "setup_instructions": list(approval.get("setup_instructions") or []),
        "review_checklist": review_checklist,
        "result_capture_fields": list(approval.get("required_result_fields") or []),
        "recommended_result_fields": list(approval.get("recommended_result_fields") or []),
        "manual_input_file": manual_input_file,
        "slot_manual_input_file": slot_manual_input_file,
        "template_file": template_file,
        "result_capture_defaults": {
            "discovery_test_slot": result_row.get("discovery_test_slot", ""),
            "baseline_asset_group": result_row.get("baseline_asset_group", ""),
            "variant_plan_summary": result_row.get("variant_plan_summary", ""),
        },
        "result_priority": approval.get("approval_priority", ""),
        "next_learning_step": approval.get("next_learning_step", ""),
    }


def _allowed_change_summary(test_type: str) -> str:
    if test_type == "winner_image_to_motion_test":
        return "motion treatment only"
    if test_type == "winner_hook_clone_test":
        return "hook or CTA only"
    return "planned discovery axis only"


def _fallback_variant_plan_summary(test_type: str, variant_count_target: int) -> str:
    if test_type == "winner_image_to_motion_test":
        return f"{variant_count_target} motion variants planned" if variant_count_target > 0 else "motion variants planned"
    if test_type == "winner_hook_clone_test":
        return f"{variant_count_target} hook or CTA variants planned" if variant_count_target > 0 else "hook or CTA variants planned"
    return "discovery variants planned"
