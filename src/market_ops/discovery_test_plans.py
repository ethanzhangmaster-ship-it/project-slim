from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.action_layer import ActionLayerBuilder
from market_ops.config import Settings
from market_ops.discovery_experiment_cards import DiscoveryExperimentCardsBuilder


@dataclass(slots=True)
class DiscoveryTestPlansResult:
    markdown_path: Path
    json_path: Path
    passed: bool


class DiscoveryTestPlansBuilder:
    """Builds structured discovery test plans from approval-gated experiment cards."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> DiscoveryTestPlansResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self.build_payload(report_date)

        markdown_path = output_dir / f"discovery_test_plans_{suffix}.md"
        json_path = output_dir / f"discovery_test_plans_{suffix}.json"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return DiscoveryTestPlansResult(markdown_path=markdown_path, json_path=json_path, passed=bool(payload["passed"]))

    def build_payload(self, report_date: date) -> dict[str, Any]:
        cards_payload = DiscoveryExperimentCardsBuilder(self._settings).build_payload(report_date)
        action_payload = ActionLayerBuilder(self._settings).build_payload(report_date)
        intent_index = {
            str(item.get("target") or ""): item
            for item in action_payload.get("execution_intents") or []
            if str(item.get("target") or "").strip()
        }
        plans = [
            _plan(card, intent_index.get(str(card.get("target") or ""), {}), index)
            for index, card in enumerate(cards_payload.get("cards") or [], start=1)
        ]
        return {
            "report_date": report_date.isoformat(),
            "mode": "discovery_test_plans",
            "passed": True,
            "rules": {
                "signal_only": True,
                "approval_gated": True,
                "no_platform_write": True,
                "variant_naming_rule": "project_channel_country_testtype_vXX",
            },
            "summary": {
                "plan_count": len(plans),
                "slot_count": sum(len(item.get("variant_slots") or []) for item in plans),
            },
            "plans": plans,
        }

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload.get("summary") or {}
        lines = [
            f"# Discovery Test Plans | {payload['report_date']}",
            "",
            "- Mode: discovery_test_plans",
            "- Purpose: convert discovery cards into structured variant-slot plans.",
            "- Boundary: signal-only, approval-gated, no platform write.",
            "",
            "## Summary",
            "",
            f"- Plans: {summary.get('plan_count', 0)}",
            f"- Variant slots: {summary.get('slot_count', 0)}",
            "",
            "## Plans",
            "",
        ]
        if not payload.get("plans"):
            lines.append("- None.")
        for item in payload.get("plans") or []:
            lines.append(f"### {item['plan_id']} | {item['target']}")
            lines.append(f"- Axis: {item['primary_test_axis']}")
            lines.append(f"- Why this test first: {item.get('structural_test_rationale') or 'none'}")
            lines.append(f"- Prioritized focuses: {', '.join(item.get('discovery_prioritized_change_focuses') or []) or 'none'}")
            lines.append(f"- Variant target: {item['variant_count_target']}")
            lines.append(f"- Naming rule: {item['naming_rule']}")
            lines.append(f"- Controls fixed: {', '.join(item['control_dimensions']) or 'none'}")
            lines.append(f"- Baseline preview: {', '.join(item['baseline_asset_preview']) or 'none'}")
            lines.append("- Slots:")
            for slot in item.get("variant_slots") or []:
                lines.append(f"  - {slot['slot_id']} | {slot['variant_name']} | {slot['change_focus']} | control={slot['baseline_anchor']}")
            lines.append("")
        return "\n".join(lines)


def _plan(card: dict[str, Any], intent: dict[str, Any], index: int) -> dict[str, Any]:
    project = str(card.get("project") or "")
    channel = str(card.get("channel") or "")
    country = str(card.get("country") or "")
    test_type = str(card.get("test_type") or "")
    variant_count_target = int(card.get("variant_count_target") or 0)
    naming_prefix = _slug("_".join(part for part in (project, channel, country, test_type) if part))
    slots = [
        _variant_slot(card, slot_index + 1, naming_prefix)
        for slot_index in range(max(variant_count_target, 0))
    ]
    return {
        "plan_id": f"discovery_plan_card_{index:03d}",
        "card_id": card.get("card_id", ""),
        "experiment_id": card.get("experiment_id", ""),
        "approval_id": card.get("approval_id", ""),
        "target": card.get("target", ""),
        "project": project,
        "channel": channel,
        "country": country,
        "test_type": test_type,
        "approval_status": card.get("approval_status", ""),
        "intent_id": intent.get("intent_id", ""),
        "intent_status": intent.get("execution_status", ""),
        "variant_count_target": variant_count_target,
        "primary_test_axis": card.get("primary_test_axis", ""),
        "control_dimensions": list(card.get("control_dimensions") or []),
        "baseline_asset_preview": list(card.get("baseline_asset_preview") or []),
        "baseline_creative_ids": list(card.get("baseline_creative_ids") or []),
        "variant_plan_summary": card.get("variant_plan_summary", ""),
        "structural_test_rationale": card.get("structural_test_rationale", ""),
        "discovery_prioritized_change_focuses": list(card.get("discovery_prioritized_change_focuses") or []),
        "naming_rule": f"{naming_prefix}_vXX",
        "variant_slots": slots,
        "execution_constraints": {
            "allowed_change_summary": card.get("allowed_change_summary", ""),
            "controls_fixed": list(card.get("control_dimensions") or []),
            "approval_required": True,
            "manual_result_capture_required": True,
        },
    }


def _variant_slot(card: dict[str, Any], slot_number: int, naming_prefix: str) -> dict[str, Any]:
    test_type = str(card.get("test_type") or "")
    baseline_preview = list(card.get("baseline_asset_preview") or [])
    baseline_anchor = baseline_preview[(slot_number - 1) % len(baseline_preview)] if baseline_preview else ""
    focus_options = list(card.get("discovery_prioritized_change_focuses") or [])
    if not focus_options:
        if test_type == "winner_image_to_motion_test":
            focus_options = ["light_motion", "camera_push", "text_motion", "cta_motion"]
        else:
            focus_options = ["hook_rewrite", "hook_reorder", "cta_swap", "subtitle_density", "urgency_angle", "benefit_angle"]
    change_focus = focus_options[(slot_number - 1) % len(focus_options)]
    return {
        "slot_id": f"slot_{slot_number:02d}",
        "variant_name": f"{naming_prefix}_v{slot_number:02d}",
        "change_focus": change_focus,
        "baseline_anchor": baseline_anchor,
        "must_hold_constant": list(card.get("control_dimensions") or []),
        "planned_test_axis": card.get("primary_test_axis", ""),
    }


def _slug(value: str) -> str:
    slug = "".join(char.lower() if char.isalnum() else "_" for char in str(value or "")).strip("_")
    return "_".join(part for part in slug.split("_") if part) or "discovery_variant"
