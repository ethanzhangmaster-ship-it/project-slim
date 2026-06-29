from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.action_layer import ActionLayerBuilder
from market_ops.causal_learning import CausalLearningBuilder
from market_ops.config import Settings
from market_ops.decision_engine import DecisionEngineBuilder
from market_ops.discovery_approval_state import (
    approval_is_rejected,
    approval_is_unblocked,
    discovery_approval_input_path,
    load_discovery_approval_inputs,
)
from market_ops.experiment_manager import ExperimentPlanBuilder


@dataclass(slots=True)
class ExperimentExecutionQueueResult:
    markdown_path: Path
    json_path: Path
    csv_path: Path
    passed: bool


class ExperimentExecutionQueueBuilder:
    """Builds a dry-run queue for experiments that need execution or result capture."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> ExperimentExecutionQueueResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self.build_payload(report_date)

        markdown_path = output_dir / f"experiment_execution_queue_{suffix}.md"
        json_path = output_dir / f"experiment_execution_queue_{suffix}.json"
        csv_path = output_dir / f"experiment_execution_queue_{suffix}.csv"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._write_csv(csv_path, payload["queue_items"])
        return ExperimentExecutionQueueResult(markdown_path=markdown_path, json_path=json_path, csv_path=csv_path, passed=bool(payload["passed"]))

    def build_payload(self, report_date: date) -> dict[str, Any]:
        suffix = report_date.strftime("%Y%m%d")
        output_dir = self._settings.active_output_dir
        experiment_payload = _load_or_build(output_dir / f"experiment_plan_{suffix}.json", lambda: ExperimentPlanBuilder(self._settings).build(report_date))
        causal_payload = _load_or_build(output_dir / f"causal_learning_{suffix}.json", lambda: CausalLearningBuilder(self._settings).build(report_date))
        action_payload = _load_or_build(output_dir / f"action_layer_{suffix}.json", lambda: ActionLayerBuilder(self._settings).build(report_date))
        decision_payload = _load_or_build(output_dir / f"decision_engine_{suffix}.json", lambda: DecisionEngineBuilder(self._settings).build(report_date))
        discovery_approval_inputs = load_discovery_approval_inputs(discovery_approval_input_path(output_dir, report_date))

        action_index = _index_action_intents(action_payload.get("execution_intents") or [])
        causal_index = {item.get("experiment_id"): item for item in causal_payload.get("hypotheses") or []}
        decision_wait_index = _decision_wait_index(decision_payload.get("items") or [])
        items = [
            _queue_item(
                experiment,
                causal_index.get(experiment.get("experiment_id")) or {},
                action_index,
                decision_wait_index,
                discovery_approval_inputs.get(_discovery_approval_id(experiment), {}),
                index,
            )
            for index, experiment in enumerate(experiment_payload.get("experiments") or [], start=1)
        ]
        items = [item for item in items if item]
        platform_blocked = [item for item in items if item["queue_status"] == "platform_write_blocked"]
        manual_approval_required = [item for item in items if item["queue_status"] == "manual_approval_required"]
        manual_execution = [item for item in items if item["queue_status"] == "manual_execution_required"]
        manual_execution_approved = [item for item in items if item["queue_status"] == "manual_execution_approved"]
        waiting_result = [item for item in items if item["queue_status"] == "waiting_result_capture"]
        completed = [item for item in items if item["queue_status"] == "completed"]
        discovery_learning_blockers = [item for item in items if item.get("learning_priority_label") == "critical_learning_blocker"]

        return {
            "report_date": report_date.isoformat(),
            "mode": "dry_run_experiment_execution_queue",
            "passed": True,
            "rules": {
                "no_platform_write": True,
                "requires_human_approval": True,
                "records_execution_gap": "Queue status separates execution blockers from outcome-capture blockers.",
                "manual_discovery_approval_input_file": str(discovery_approval_input_path(output_dir, report_date)),
            },
            "summary": {
                "queue_item_count": len(items),
                "platform_write_blocked_count": len(platform_blocked),
                "manual_approval_required_count": len(manual_approval_required),
                "manual_execution_required_count": len(manual_execution),
                "manual_execution_approved_count": len(manual_execution_approved),
                "waiting_result_capture_count": len(waiting_result),
                "completed_count": len(completed),
                "critical_learning_blocker_count": len(discovery_learning_blockers),
            },
            "queue_items": items,
        }

    @staticmethod
    def _write_csv(path: Path, items: list[dict[str, Any]]) -> None:
        fieldnames = [
            "queue_id",
            "queue_status",
            "experiment_id",
            "experiment_type",
            "target",
            "linked_decision",
            "matched_intent_id",
            "platform",
            "operation",
            "owner",
            "blocked_reasons",
            "result_capture_required",
            "approval_ids",
            "required_result_fields",
            "manual_input_file",
            "result_template_file",
            "next_learning_step",
            "slot_packet_count",
            "learning_priority_label",
            "decision_waiting",
            "decision_wait_match_count",
        ]
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for item in items:
                row = {field: item.get(field, "") for field in fieldnames}
                row["blocked_reasons"] = " | ".join(item.get("blocked_reasons") or [])
                row["approval_ids"] = " | ".join(item.get("approval_ids") or [])
                row["required_result_fields"] = " | ".join(item.get("required_result_fields") or [])
                writer.writerow(row)

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        lines = [
            f"# Experiment Execution Queue | {payload['report_date']}",
            "",
            "- Mode: dry_run_experiment_execution_queue",
            "- Purpose: convert experiments and causal hypotheses into an auditable execution/result-capture queue.",
            "- Boundary: no platform writes; queue items require human approval or manual execution.",
            "",
            "## Summary",
            "",
            f"- Queue items: {summary['queue_item_count']}",
            f"- Platform write blocked: {summary['platform_write_blocked_count']}",
            f"- Manual approval required: {summary['manual_approval_required_count']}",
            f"- Manual execution required: {summary['manual_execution_required_count']}",
            f"- Manual execution approved: {summary['manual_execution_approved_count']}",
            f"- Waiting result capture: {summary['waiting_result_capture_count']}",
            f"- Completed: {summary['completed_count']}",
            f"- Critical learning blockers: {summary['critical_learning_blocker_count']}",
            "",
            "## Queue",
            "",
        ]
        if not payload["queue_items"]:
            lines.append("- None.")
        for item in payload["queue_items"][:50]:
            reasons = ", ".join(item["blocked_reasons"]) if item["blocked_reasons"] else "none"
            approval_ids = ",".join(item.get("approval_ids") or []) or "none"
            decision_wait = "yes" if item.get("decision_waiting") else "no"
            lines.append(
                f"- {item['queue_id']} | {item['queue_status']} | {item['experiment_type']} | "
                f"{item['target']} | intent={item['matched_intent_id'] or 'none'} | approvals={approval_ids} | "
                f"priority={item.get('learning_priority_label') or 'standard'} | decision_wait={decision_wait} | blocked={reasons}"
            )
        lines.append("")
        return "\n".join(lines)


def _load_or_build(path: Path, builder: Any) -> dict[str, Any]:
    if not path.exists():
        builder()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _index_action_intents(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(items, key=lambda item: str(item.get("target") or ""), reverse=True)


def _queue_item(
    experiment: dict[str, Any],
    causal: dict[str, Any],
    action_intents: list[dict[str, Any]],
    decision_wait_index: dict[str, list[dict[str, Any]]],
    discovery_approval_input: dict[str, str],
    index: int,
) -> dict[str, Any]:
    target = str(experiment.get("target") or "")
    target_l = target.lower()
    experiment_type = str(experiment.get("experiment_type") or "")
    experiment_source = str(experiment.get("source") or "")
    matched_intent = _match_action_intent(target, action_intents)
    intent_target = str(matched_intent.get("target") or "").lower()
    source_action = matched_intent.get("source_action") or {} if intent_target == target_l else {}
    blocked_reasons = list(matched_intent.get("blocked_reasons") or [])
    causal_state = str(causal.get("causal_state") or "")
    if causal_state in {"validated", "invalidated"}:
        queue_status = "completed"
        result_capture_required = False
    elif experiment_source == "local_winner_prior" or str(experiment.get("linked_decision") or "") == "proactive_local_winner_test":
        queue_status = "manual_execution_required"
        result_capture_required = True
        matched_intent = {}
        blocked_reasons = ["manual_winner_material_test_setup_required"]
    elif experiment_source == "discovery_backlog" or experiment_type == "discovery_creative_test_plan":
        queue_status, blocked_reasons = _discovery_queue_status(blocked_reasons, discovery_approval_input)
        result_capture_required = True
    elif experiment_type == "evidence_capture":
        queue_status = "manual_execution_required"
        result_capture_required = True
        matched_intent = {}
        blocked_reasons = ["manual_evidence_capture_required"]
    elif "platform_write_disabled" in blocked_reasons:
        queue_status = "platform_write_blocked"
        result_capture_required = True
    elif not matched_intent:
        queue_status = "manual_execution_required"
        result_capture_required = True
        blocked_reasons.append("no_matching_action_intent")
    else:
        queue_status = "waiting_result_capture"
        result_capture_required = True

    approval_ids = [str(value) for value in source_action.get("approval_ids") or [] if str(value).strip()]
    required_result_fields = _unique([str(value) for value in source_action.get("required_result_fields") or [] if str(value).strip()])
    slot_packets = list(source_action.get("slot_packets") or [])
    active_discovery_pattern_keys = _unique([str(value) for value in source_action.get("active_discovery_pattern_keys") or [] if str(value).strip()])
    active_discovery_change_focuses = _unique([str(value) for value in source_action.get("active_discovery_change_focuses") or [] if str(value).strip()])
    decision_wait_matches = _decision_wait_matches(experiment, decision_wait_index)
    learning_priority_label = _learning_priority_label(experiment_source, experiment_type, slot_packets, source_action, decision_wait_matches)

    return {
        "queue_id": f"queue_{index:03d}",
        "queue_status": queue_status,
        "experiment_id": experiment.get("experiment_id", ""),
        "hypothesis_id": causal.get("hypothesis_id", ""),
        "experiment_type": experiment_type,
        "target": target,
        "linked_decision": experiment.get("linked_decision", ""),
        "intervention": experiment.get("change", ""),
        "source": experiment_source,
        "creative_id": experiment.get("creative_id", ""),
        "creative_name": experiment.get("creative_name", ""),
        "success_metrics": list(experiment.get("success_metrics") or []),
        "rollback_metrics": list(experiment.get("rollback_metrics") or []),
        "matched_intent_id": matched_intent.get("intent_id", ""),
        "platform": matched_intent.get("platform", "unknown"),
        "operation": matched_intent.get("operation", ""),
        "owner": experiment.get("owner", ""),
        "blocked_reasons": blocked_reasons,
        "result_capture_required": result_capture_required,
        "manual_approval_state": _manual_approval_state(discovery_approval_input),
        "manual_approval_decision": str(discovery_approval_input.get("approval_decision") or ""),
        "manual_approval_note": str(discovery_approval_input.get("approval_note") or ""),
        "approval_ids": approval_ids,
        "required_result_fields": required_result_fields,
        "manual_input_file": source_action.get("manual_input_file", ""),
        "result_template_file": source_action.get("result_template_file", ""),
        "next_learning_step": source_action.get("next_learning_step", ""),
        "slot_packet_count": len(slot_packets),
        "slot_packets": slot_packets,
        "active_discovery_change_focuses": active_discovery_change_focuses,
        "active_discovery_pattern_keys": active_discovery_pattern_keys,
        "decision_waiting": bool(decision_wait_matches),
        "decision_wait_match_count": len(decision_wait_matches),
        "decision_wait_entity_ids": [str(item.get("entity_id") or "") for item in decision_wait_matches[:10] if str(item.get("entity_id") or "").strip()],
        "decision_wait_contextual_pattern_keys": _unique(
            [
                str(key)
                for item in decision_wait_matches[:10]
                for key in list(item.get("playbook_candidate_contextual_pattern_keys") or [])
                if str(key).strip()
            ]
        ),
        "learning_priority_label": learning_priority_label,
        "missing_evidence": list(causal.get("missing_evidence") or []),
        "setup_instructions": _setup_instructions(experiment),
        "project": experiment.get("project", ""),
        "channel": experiment.get("channel", ""),
        "country": experiment.get("country", ""),
        "test_type": experiment.get("test_type", ""),
        "learning_goal": experiment.get("learning_goal", ""),
        "baseline_creative_names": list(experiment.get("baseline_creative_names") or []),
        "baseline_creative_ids": list(experiment.get("baseline_creative_ids") or []),
        "baseline_asset_preview": list(experiment.get("baseline_asset_preview") or []),
        "baseline_asset_type": experiment.get("baseline_asset_type", ""),
        "variant_count_target": int(experiment.get("variant_count_target") or 0),
        "control_dimensions": list(experiment.get("control_dimensions") or []),
        "primary_test_axis": experiment.get("primary_test_axis", ""),
        "variant_plan_summary": experiment.get("variant_plan_summary", ""),
        "winner_material_asset_count": int(experiment.get("winner_material_asset_count") or 0),
        "discovery_prioritized_change_focuses": list(experiment.get("discovery_prioritized_change_focuses") or []),
        "winner_structure_bias": list(experiment.get("winner_structure_bias") or []),
        "structural_test_rationale": experiment.get("structural_test_rationale", ""),
    }


def _match_action_intent(target: str, intents: list[dict[str, Any]]) -> dict[str, Any]:
    target_l = target.lower()
    target_parts = [part.strip().lower() for part in target.split("/") if part.strip()]
    best: dict[str, Any] = {}
    best_score = 0
    for intent in intents:
        intent_target = str(intent.get("target") or "").lower()
        intent_project = str(intent.get("project") or "").lower()
        score = 0
        if intent_target and intent_target in target_l:
            score += 3
        if intent_project and intent_project in target_l:
            score += 2
        score += sum(1 for part in target_parts if part and (part in intent_target or part in intent_project))
        if score > best_score:
            best = intent
            best_score = score
    return best if best_score > 0 else {}


def _setup_instructions(experiment: dict[str, Any]) -> list[str]:
    source = str(experiment.get("source") or "")
    experiment_type = str(experiment.get("experiment_type") or "")
    creative_name = str(experiment.get("creative_name") or experiment.get("creative_id") or "").strip()
    if source == "local_winner_prior":
        if "image" in str(experiment.get("hypothesis") or "").lower():
            return [
                f"Use {creative_name} as the baseline winner material.",
                "Create one motion or light-animation variant from the baseline image.",
                "Keep targeting constant and compare CTR/CPI against the baseline winner direction.",
            ]
        return [
            f"Use {creative_name} as the baseline winner material.",
            "Create a controlled variant by changing only the first 3 seconds, subtitle density, or CTA.",
            "Keep audience and budget stable so the test isolates the creative driver.",
        ]
    if source == "discovery_backlog" or experiment_type == "discovery_creative_test_plan":
        baseline_names = list(experiment.get("baseline_creative_names") or [])
        preview_assets = ", ".join(baseline_names[:3]) if baseline_names else creative_name or "the winner backlog"
        test_type = str(experiment.get("test_type") or "")
        variant_target = int(experiment.get("variant_count_target") or 0)
        target_text = f"Create at least {variant_target} controlled variants." if variant_target > 0 else "Create controlled variants."
        control_dimensions = list(experiment.get("control_dimensions") or [])
        control_text = ", ".join(control_dimensions) if control_dimensions else "targeting_constant, budget_constant"
        if test_type == "winner_image_to_motion_test":
            return [
                f"Use these winner images as baselines: {preview_assets}.",
                target_text,
                f"Keep these controls fixed: {control_text}.",
                "Compare CTR, CPI, and post-action ROI to decide whether image-to-motion is a reusable pattern.",
            ]
        return [
            f"Use these winner videos as baselines: {preview_assets}.",
            target_text,
            f"Keep these controls fixed: {control_text}.",
            "Compare CTR, CPI, and post-action ROI to decide whether the winner hook is reusable.",
        ]
    if experiment_type == "evidence_capture":
        return ["Capture the missing quality, payback, fatigue, and attribution fields before making a budget decision."]
    return []


def _learning_priority_label(
    experiment_source: str,
    experiment_type: str,
    slot_packets: list[dict[str, Any]],
    source_action: dict[str, Any],
    decision_wait_matches: list[dict[str, Any]],
) -> str:
    if decision_wait_matches and (experiment_source == "discovery_backlog" or experiment_type == "discovery_creative_test_plan"):
        return "critical_learning_blocker"
    if slot_packets and str(source_action.get("next_learning_step") or "") == "resolve_approval_and_capture_slot_results":
        return "critical_learning_blocker"
    if experiment_source == "discovery_backlog" or experiment_type == "discovery_creative_test_plan":
        return "high_learning_priority"
    if experiment_source == "local_winner_prior":
        return "winner_material_priority"
    if experiment_type == "evidence_capture":
        return "evidence_fill_priority"
    return "standard"


def _discovery_queue_status(blocked_reasons: list[str], approval_input: dict[str, str]) -> tuple[str, list[str]]:
    reasons = _unique(["manual_discovery_test_plan_setup_required", *blocked_reasons])
    if approval_is_rejected(approval_input):
        return "manual_execution_required", _unique(["manual_discovery_approval_rejected", *reasons])
    if approval_is_unblocked(approval_input):
        reasons = [
            reason
            for reason in reasons
            if reason
            not in {
                "manual_discovery_test_plan_setup_required",
                "platform_write_disabled",
                "platform_credentials_missing",
                "approval_required",
                "operation_not_supported",
            }
        ]
        return "manual_execution_approved", reasons
    return "manual_approval_required", reasons


def _manual_approval_state(approval_input: dict[str, str]) -> str:
    if approval_is_unblocked(approval_input):
        return "approved_for_manual_execution"
    if approval_is_rejected(approval_input):
        return "approval_rejected"
    return "approval_pending_input"


def _discovery_approval_id(experiment: dict[str, Any]) -> str:
    experiment_id = str(experiment.get("experiment_id") or "")
    test_type = str(experiment.get("test_type") or "")
    if experiment_id == "discovery_plan_p04_witch_winner_hook_clone_test_facebook_global" or test_type == "winner_hook_clone_test":
        return "approval_013"
    if experiment_id == "discovery_plan_p04_witch_winner_image_to_motion_test_facebook_global" or test_type == "winner_image_to_motion_test":
        return "approval_014"
    return ""


def _decision_wait_index(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        for key in [
            *list(item.get("playbook_candidate_contextual_pattern_keys") or []),
            *list(item.get("playbook_candidate_pattern_keys") or []),
        ]:
            token = str(key or "").strip()
            if token:
                index.setdefault(token, []).append(item)
    return index


def _decision_wait_matches(experiment: dict[str, Any], decision_wait_index: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    candidate_keys = [
        *list(experiment.get("discovery_pattern_prioritized_keys") or []),
        *list(experiment.get("active_discovery_contextual_pattern_keys") or []),
    ]
    for key in candidate_keys:
        token = str(key or "").strip()
        if not token:
            continue
        for item in decision_wait_index.get(token, []):
            if item not in matches:
                matches.append(item)
    return matches


def _unique(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        if item and item not in result:
            result.append(item)
    return result
