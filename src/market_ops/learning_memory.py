from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.action_feedback import ActionFeedbackBuilder
from market_ops.config import Settings


@dataclass(slots=True)
class LearningMemoryResult:
    markdown_path: Path
    json_path: Path
    passed: bool


class LearningMemoryBuilder:
    """Converts action feedback and experiment outcomes into durable growth learnings."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> LearningMemoryResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self.build_payload(report_date)

        markdown_path = output_dir / f"learning_memory_{suffix}.md"
        json_path = output_dir / f"learning_memory_{suffix}.json"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return LearningMemoryResult(markdown_path=markdown_path, json_path=json_path, passed=bool(payload["passed"]))

    def build_payload(self, report_date: date) -> dict[str, Any]:
        from market_ops.experiment_manager import ExperimentPlanBuilder
        from market_ops.experiment_result_ingestion import ExperimentResultIngestionBuilder

        feedback_payload = ActionFeedbackBuilder(self._settings).build_payload(report_date)
        experiment_payload = ExperimentPlanBuilder(self._settings).build_payload(report_date)
        result_payload = ExperimentResultIngestionBuilder(self._settings).build_payload(report_date)
        experiment_index = {
            str(item.get("experiment_id") or ""): item
            for item in experiment_payload.get("experiments") or []
            if str(item.get("experiment_id") or "").strip()
        }

        action_records = [self._action_learning_record(item) for item in feedback_payload.get("items") or []]
        experiment_records: list[dict[str, Any]] = []
        for item in result_payload.get("result_rows") or []:
            experiment = experiment_index.get(str(item.get("experiment_id") or ""), {})
            experiment_record = self._experiment_learning_record(item, experiment)
            experiment_records.append(experiment_record)
            experiment_records.extend(self._discovery_slot_learning_records(item, experiment))
        records = action_records + experiment_records
        closed = [item for item in records if item["learning_state"] == "closed"]
        needs_outcome = [item for item in records if item["learning_state"] == "needs_outcome"]
        needs_confirmation = [item for item in records if item["learning_state"] == "needs_execution_confirmation"]
        return {
            "report_date": report_date.isoformat(),
            "mode": "non_mutating_learning_memory",
            "passed": True,
            "source": {
                "action_feedback": feedback_payload.get("source"),
                "experiment_result_ingestion": result_payload.get("rules", {}).get("manual_input_file", ""),
            },
            "summary": {
                "record_count": len(records),
                "action_record_count": len(action_records),
                "experiment_record_count": len(experiment_records),
                "closed_learning_count": len(closed),
                "needs_outcome_count": len(needs_outcome),
                "needs_execution_confirmation_count": len(needs_confirmation),
            },
            "records": records,
            "closed_learnings": closed,
            "learning_gaps": needs_confirmation + needs_outcome,
        }

    @staticmethod
    def _action_learning_record(item: dict[str, Any]) -> dict[str, Any]:
        raw = item.get("raw_action") or {}
        status = str((item.get("actual_result") or {}).get("status") or "")
        note = str((item.get("actual_result") or {}).get("latest_note") or "")
        success = item.get("success")
        target = str(item.get("target") or "")
        action = str(item.get("action") or "")
        acceptance_metric = str((item.get("expected_result") or {}).get("acceptance_metric") or "")
        due_date = str((item.get("expected_result") or {}).get("due_date") or "")

        if success is True or success is False:
            learning_state = "closed"
        elif _looks_pending(status):
            learning_state = "needs_execution_confirmation"
        else:
            learning_state = "needs_outcome"

        return {
            "learning_id": f"learn_{item.get('action_id', '')}",
            "action_id": item.get("action_id", ""),
            "source_type": "action_feedback",
            "learning_state": learning_state,
            "action_type": action,
            "project": _project_from_text(target),
            "target": target,
            "hypothesis": _hypothesis(action, target, acceptance_metric),
            "expected_signal": _expected_signal(acceptance_metric),
            "actual_signal": note,
            "success": success,
            "due_date": due_date,
            "confidence": _confidence(learning_state, note, acceptance_metric),
            "growth_memory_tags": _memory_tags(action, target, acceptance_metric, note),
            "missing_fields": _missing_fields(learning_state, action, acceptance_metric),
            "next_update_required": _next_update_required(learning_state, acceptance_metric),
            "source_record": raw,
        }

    @staticmethod
    def _experiment_learning_record(result_row: dict[str, Any], experiment: dict[str, Any]) -> dict[str, Any]:
        target = str(result_row.get("target") or experiment.get("target") or "")
        actual_signal = str(result_row.get("actual_result_note") or "")
        success = result_row.get("success")
        result_state = str(result_row.get("result_state") or "")
        if result_state == "closed" and success is not None:
            learning_state = "closed"
        elif result_state == "approval_blocked":
            learning_state = "needs_execution_confirmation"
        elif str(result_row.get("execution_status") or "").strip():
            learning_state = "needs_outcome"
        else:
            learning_state = "needs_execution_confirmation"

        expected_metrics = list(experiment.get("success_metrics") or [])
        expected_signal = {
            "success_metrics": expected_metrics,
            "rollback_metrics": list(experiment.get("rollback_metrics") or []),
            "variant_count_target": int(experiment.get("variant_count_target") or 0),
            "primary_test_axis": str(experiment.get("primary_test_axis") or ""),
            "control_dimensions": list(experiment.get("control_dimensions") or []),
            "baseline_asset_preview": list(experiment.get("baseline_asset_preview") or []),
        }
        post_metrics = {
            "post_action_roi_or_roas": result_row.get("post_action_roi_or_roas", ""),
            "post_action_ctr": result_row.get("post_action_ctr", ""),
            "post_action_cpi": result_row.get("post_action_cpi", ""),
            "created_variant_count": result_row.get("created_variant_count", ""),
            "linked_new_creative_ids": result_row.get("linked_new_creative_ids", ""),
            "winner_variant_type": result_row.get("winner_variant_type", ""),
            "winner_baseline_asset": result_row.get("winner_baseline_asset", ""),
            "discovery_test_slot": result_row.get("discovery_test_slot", ""),
            "baseline_asset_group": result_row.get("baseline_asset_group", ""),
            "variant_plan_summary": result_row.get("variant_plan_summary", ""),
            "slot_execution_plan": result_row.get("slot_execution_plan", ""),
            "slot_learning_question": result_row.get("slot_learning_question", ""),
            "slot_result_summary": result_row.get("slot_result_summary", ""),
            "learning_note": result_row.get("learning_note", ""),
            "captured_cpi": result_row.get("captured_cpi", ""),
            "captured_retention_d1": result_row.get("captured_retention_d1", ""),
            "captured_arpu": result_row.get("captured_arpu", ""),
            "captured_arppu": result_row.get("captured_arppu", ""),
            "captured_payback_d7": result_row.get("captured_payback_d7", ""),
            "captured_fatigue_evidence": result_row.get("captured_fatigue_evidence", ""),
            "evidence_source_link": result_row.get("evidence_source_link", ""),
        }
        action_type = str(experiment.get("experiment_type") or "experiment")
        acceptance_metric = " | ".join(expected_metrics)
        winner_structure_bias = list(result_row.get("winner_structure_bias") or experiment.get("winner_structure_bias") or [])
        discovery_prioritized_change_focuses = list(
            result_row.get("discovery_prioritized_change_focuses") or experiment.get("discovery_prioritized_change_focuses") or []
        )
        structural_test_rationale = str(
            result_row.get("structural_test_rationale") or experiment.get("structural_test_rationale") or ""
        )
        baseline_asset_type = str(result_row.get("baseline_asset_type") or experiment.get("baseline_asset_type") or "")
        return {
            "learning_id": f"learn_{result_row.get('experiment_id', '')}",
            "action_id": result_row.get("experiment_id", ""),
            "source_type": "experiment_result_ingestion",
            "learning_state": learning_state,
            "action_type": action_type,
            "project": _project_from_text(target),
            "target": target,
            "hypothesis": str(experiment.get("hypothesis") or ""),
            "expected_signal": expected_signal,
            "actual_signal": actual_signal,
            "success": success,
            "due_date": "",
            "confidence": _experiment_confidence(learning_state, success, actual_signal, post_metrics),
            "growth_memory_tags": _experiment_memory_tags(experiment, result_row),
            "missing_fields": list(result_row.get("missing_result_fields") or []),
            "next_update_required": _experiment_next_update_required(learning_state, result_row),
            "source_record": {
                "experiment": experiment,
                "result_row": result_row,
            },
            "experiment_id": result_row.get("experiment_id", ""),
            "hypothesis_id": result_row.get("hypothesis_id", ""),
            "approval_id": result_row.get("approval_id", ""),
            "post_metrics": post_metrics,
            "linked_decision": experiment.get("linked_decision", ""),
            "source": experiment.get("source", ""),
            "creative_id": experiment.get("creative_id", ""),
            "creative_name": experiment.get("creative_name", ""),
            "project_channel": experiment.get("channel", ""),
            "project_country": experiment.get("country", ""),
            "test_type": experiment.get("test_type", ""),
            "learning_goal": experiment.get("learning_goal", ""),
            "variant_count_target": int(experiment.get("variant_count_target") or 0),
            "primary_test_axis": str(experiment.get("primary_test_axis") or ""),
            "control_dimensions": list(experiment.get("control_dimensions") or []),
            "baseline_asset_preview": list(experiment.get("baseline_asset_preview") or []),
            "acceptance_metric": acceptance_metric,
            "baseline_asset_type": baseline_asset_type,
            "winner_structure_bias": winner_structure_bias,
            "structural_test_rationale": structural_test_rationale,
            "discovery_prioritized_change_focuses": discovery_prioritized_change_focuses,
            "structure_context": _structure_context(winner_structure_bias, baseline_asset_type),
            "structure_signature": _structure_signature(winner_structure_bias, baseline_asset_type),
        }

    @staticmethod
    def _discovery_slot_learning_records(result_row: dict[str, Any], experiment: dict[str, Any]) -> list[dict[str, Any]]:
        discovery_slot = str(result_row.get("discovery_test_slot") or "")
        slot_plan = str(result_row.get("slot_execution_plan") or "")
        slot_questions = str(result_row.get("slot_learning_question") or "")
        if not discovery_slot or not slot_plan or not slot_questions:
            return []

        target = str(result_row.get("target") or experiment.get("target") or "")
        question_index = _slot_question_index(slot_questions)
        summary_index = _slot_summary_index(str(result_row.get("slot_result_summary") or ""))
        records: list[dict[str, Any]] = []
        for slot in _parse_slot_execution_plan(slot_plan):
            slot_id = str(slot.get("slot_id") or "")
            variant_name = str(slot.get("variant_name") or "")
            change_focus = str(slot.get("change_focus") or "")
            question = question_index.get(slot_id, "")
            slot_summary = summary_index.get(slot_id, {})
            actual_signal = str(slot_summary.get("summary") or "")
            slot_success = _slot_success(actual_signal, result_row.get("success"), slot_summary)
            learning_state = _slot_learning_state(result_row, actual_signal, slot_success)
            slot_missing_fields = _slot_missing_fields(learning_state, actual_signal, slot_success)
            winner_structure_bias = list(result_row.get("winner_structure_bias") or experiment.get("winner_structure_bias") or [])
            discovery_prioritized_change_focuses = list(
                result_row.get("discovery_prioritized_change_focuses") or experiment.get("discovery_prioritized_change_focuses") or []
            )
            structural_test_rationale = str(
                result_row.get("structural_test_rationale") or experiment.get("structural_test_rationale") or ""
            )
            baseline_asset_type = str(result_row.get("baseline_asset_type") or experiment.get("baseline_asset_type") or "")
            records.append(
                {
                    "learning_id": f"learn_slot_{result_row.get('experiment_id', '')}_{slot_id}",
                    "action_id": f"{result_row.get('experiment_id', '')}:{slot_id}",
                    "source_type": "discovery_slot_result_ingestion",
                    "learning_state": learning_state,
                    "action_type": "discovery_slot_test",
                    "project": _project_from_text(target),
                    "target": f"{target} / {variant_name}",
                    "parent_target": target,
                    "hypothesis": question,
                    "expected_signal": {
                        "slot_id": slot_id,
                        "variant_name": variant_name,
                        "change_focus": change_focus,
                        "primary_test_axis": str(experiment.get("primary_test_axis") or ""),
                        "baseline_asset_preview": list(experiment.get("baseline_asset_preview") or []),
                    },
                    "actual_signal": actual_signal,
                    "success": slot_success,
                    "due_date": "",
                    "confidence": _slot_confidence(learning_state, actual_signal, slot_success),
                    "growth_memory_tags": _slot_memory_tags(experiment, result_row, change_focus),
                    "missing_fields": slot_missing_fields,
                    "next_update_required": _slot_next_update_required(learning_state, actual_signal, slot_success),
                    "source_record": {
                        "experiment": experiment,
                        "result_row": result_row,
                    },
                    "experiment_id": result_row.get("experiment_id", ""),
                    "hypothesis_id": result_row.get("hypothesis_id", ""),
                    "approval_id": result_row.get("approval_id", ""),
                    "post_metrics": {
                        "slot_execution_plan": slot_plan,
                        "slot_learning_question": question,
                        "slot_result_summary": actual_signal,
                        "slot_outcome_label": str(slot_summary.get("outcome_label") or ""),
                        "change_focus": change_focus,
                        "variant_name": variant_name,
                        "discovery_test_slot": discovery_slot,
                        "variant_plan_summary": result_row.get("variant_plan_summary", ""),
                        "baseline_asset_group": result_row.get("baseline_asset_group", ""),
                        "post_action_roi_or_roas": result_row.get("post_action_roi_or_roas", ""),
                        "post_action_ctr": result_row.get("post_action_ctr", ""),
                        "post_action_cpi": result_row.get("post_action_cpi", ""),
                        "baseline_asset_type": baseline_asset_type,
                        "winner_structure_bias": winner_structure_bias,
                        "structural_test_rationale": structural_test_rationale,
                        "discovery_prioritized_change_focuses": discovery_prioritized_change_focuses,
                        "structure_context": _structure_context(winner_structure_bias, baseline_asset_type),
                        "structure_signature": _structure_signature(winner_structure_bias, baseline_asset_type),
                    },
                    "linked_decision": experiment.get("linked_decision", ""),
                    "source": experiment.get("source", ""),
                    "creative_id": experiment.get("creative_id", ""),
                    "creative_name": variant_name,
                    "project_channel": experiment.get("channel", ""),
                    "project_country": experiment.get("country", ""),
                    "test_type": experiment.get("test_type", ""),
                    "learning_goal": question,
                    "variant_count_target": int(experiment.get("variant_count_target") or 0),
                    "primary_test_axis": str(experiment.get("primary_test_axis") or ""),
                    "control_dimensions": list(experiment.get("control_dimensions") or []),
                    "baseline_asset_preview": list(experiment.get("baseline_asset_preview") or []),
                    "acceptance_metric": question,
                    "slot_id": slot_id,
                    "variant_name": variant_name,
                    "change_focus": change_focus,
                    "baseline_asset_type": baseline_asset_type,
                    "winner_structure_bias": winner_structure_bias,
                    "structural_test_rationale": structural_test_rationale,
                    "discovery_prioritized_change_focuses": discovery_prioritized_change_focuses,
                    "structure_context": _structure_context(winner_structure_bias, baseline_asset_type),
                    "structure_signature": _structure_signature(winner_structure_bias, baseline_asset_type),
                    "pattern_memory_state": _slot_pattern_memory_state(result_row, learning_state),
                    "reusable_pattern_key": _slot_reusable_pattern_key(experiment, result_row, change_focus),
                    "parent_experiment_id": result_row.get("experiment_id", ""),
                }
            )
        return records

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        lines = [
            f"# Learning Memory | {payload['report_date']}",
            "",
            "- Mode: non_mutating_learning_memory",
            "- Purpose: preserve action outcomes as growth memory without changing the action tracker.",
            "",
            "## Summary",
            "",
            f"- Records: {summary['record_count']}",
            f"- Action records: {summary['action_record_count']}",
            f"- Experiment records: {summary['experiment_record_count']}",
            f"- Closed learnings: {summary['closed_learning_count']}",
            f"- Needs execution confirmation: {summary['needs_execution_confirmation_count']}",
            f"- Needs outcome: {summary['needs_outcome_count']}",
            "",
            "## Closed Learnings",
            "",
        ]
        if not payload["closed_learnings"]:
            lines.append("- None yet.")
        for item in payload["closed_learnings"][:30]:
            lines.append(f"- {item['learning_id']} | success={item['success']} | {item['hypothesis']}")

        lines.extend(["", "## Learning Gaps", ""])
        if not payload["learning_gaps"]:
            lines.append("- None.")
        for item in payload["learning_gaps"][:30]:
            missing = ", ".join(item["missing_fields"]) if item["missing_fields"] else "none"
            lines.append(f"- {item['learning_id']} | {item['learning_state']} | missing={missing} | {item['next_update_required']}")
        lines.append("")
        return "\n".join(lines)


def _looks_pending(status: str) -> bool:
    return any(token in status for token in ("待", "确认", "寰", "Draft"))


def _project_from_text(text: str) -> str:
    match = re.search(r"\bP0*([0-9]+)\b", text.upper())
    if match:
        return f"P{int(match.group(1)):02d}"
    return ""


def _hypothesis(action: str, target: str, acceptance_metric: str) -> str:
    action_l = action.lower()
    if "creative" in action_l or "素材" in action or "绱犳潗" in action:
        return f"Creative action on {target} should improve the target creative signal: {acceptance_metric}"
    if "budget" in action_l or "预算" in action or "鍑忛噺" in action or "闄愰" in action:
        return f"Budget action on {target} should improve payback or reduce inefficient spend: {acceptance_metric}"
    return f"Action on {target} should satisfy: {acceptance_metric}"


def _expected_signal(acceptance_metric: str) -> dict[str, Any]:
    text = acceptance_metric or ""
    metrics: dict[str, Any] = {"raw": text}
    roi_match = re.search(r"(?:ROI|ROAS)\D*([0-9]+(?:\.[0-9]+)?)", text, re.IGNORECASE)
    ctr_match = re.search(r"CTR", text, re.IGNORECASE)
    variant_match = re.search(r"([0-9]+)\s*(?:个|涓)", text)
    if roi_match:
        metrics["roi_or_roas_threshold"] = float(roi_match.group(1))
    if ctr_match:
        metrics["requires_ctr_check"] = True
    if variant_match:
        metrics["variant_count_target"] = int(variant_match.group(1))
    return metrics


def _confidence(learning_state: str, note: str, acceptance_metric: str) -> str:
    if learning_state == "closed" and note:
        return "high"
    if learning_state == "needs_outcome" and acceptance_metric:
        return "medium"
    return "low"


def _memory_tags(action: str, target: str, acceptance_metric: str, note: str) -> list[str]:
    text = " ".join([action, target, acceptance_metric, note])
    tags: list[str] = []
    mapping = {
        "creative": ("creative", "素材", "绱犳潗", "CTR"),
        "budget": ("budget", "预算", "棰勭畻", "ROAS", "ROI"),
        "scale": ("scale", "扩", "鎵", "加码"),
        "downweight": ("downweight", "降", "减", "鍑忛噺"),
        "fatigue": ("fatigue", "疲劳", "鐤插姵", "CTR下降"),
        "payback": ("payback", "回收", "回本", "ROI", "ROAS"),
    }
    for tag, tokens in mapping.items():
        if any(token in text for token in tokens):
            tags.append(tag)
    return tags or ["general"]


def _missing_fields(learning_state: str, action: str, acceptance_metric: str) -> list[str]:
    if learning_state == "closed":
        return []
    fields = ["execution_status", "actual_result_note"]
    expected = _expected_signal(acceptance_metric)
    if expected.get("requires_ctr_check"):
        fields.append("post_action_ctr")
    if expected.get("roi_or_roas_threshold") is not None:
        fields.append("post_action_roi_or_roas")
    if expected.get("variant_count_target") is not None:
        fields.append("created_variant_count")
    if "creative" in action.lower() or "素材" in action or "绱犳潗" in action:
        fields.append("linked_new_creative_ids")
    return fields


def _next_update_required(learning_state: str, acceptance_metric: str) -> str:
    if learning_state == "closed":
        return "No update required; ready for causal memory review."
    if learning_state == "needs_execution_confirmation":
        return "Confirm whether the action was executed, then add actual outcome metrics."
    expected = _expected_signal(acceptance_metric)
    if expected.get("roi_or_roas_threshold") is not None:
        return "Add post-action ROI/ROAS and mark whether it passed the threshold."
    if expected.get("requires_ctr_check"):
        return "Add new creative IDs and post-action CTR comparison."
    return "Add actual result note and pass/fail status."


def _experiment_confidence(
    learning_state: str,
    success: bool | None,
    actual_signal: str,
    post_metrics: dict[str, Any],
) -> str:
    if learning_state == "closed" and success is not None and any(str(value).strip() for value in post_metrics.values()):
        return "high"
    if learning_state == "needs_outcome" and (actual_signal or any(str(value).strip() for value in post_metrics.values())):
        return "medium"
    return "low"


def _experiment_memory_tags(experiment: dict[str, Any], result_row: dict[str, Any]) -> list[str]:
    tags = ["experiment"]
    experiment_type = str(experiment.get("experiment_type") or "")
    source = str(experiment.get("source") or "")
    text = " ".join(
        [
            experiment_type,
            source,
            str(result_row.get("winner_variant_type") or ""),
            str(result_row.get("learning_note") or ""),
            str(result_row.get("target") or ""),
        ]
    ).lower()
    if "creative" in experiment_type:
        tags.append("creative")
    if "winner" in source:
        tags.append("winner_prior")
    if "discovery" in source or "discovery_" in experiment_type:
        tags.append("discovery")
    if "hook" in text:
        tags.append("hook")
    if "motion" in text or "image_to_motion" in text:
        tags.append("motion")
    if any(str(result_row.get(field) or "").strip() for field in ("captured_payback_d7", "post_action_roi_or_roas")):
        tags.append("payback")
    if any(str(result_row.get(field) or "").strip() for field in ("captured_fatigue_evidence", "post_action_ctr", "post_action_cpi")):
        tags.append("creative_signal")
    return tags


def _experiment_next_update_required(learning_state: str, result_row: dict[str, Any]) -> str:
    if learning_state == "closed":
        return "No update required; ready for causal memory review."
    if learning_state == "needs_execution_confirmation":
        return "Confirm experiment execution, then add baseline, variant, and post-metric evidence."
    missing = list(result_row.get("missing_result_fields") or [])
    if any(field in missing for field in ("post_action_roi_or_roas", "post_action_ctr", "post_action_cpi")):
        return "Add post-action performance metrics and mark success=true/false."
    return "Complete the missing result fields and add the learning note."


def _parse_slot_execution_plan(value: str) -> list[dict[str, str]]:
    slots: list[dict[str, str]] = []
    for item in [part.strip() for part in str(value or "").split("|") if part.strip()]:
        if ":" not in item:
            continue
        slot_id, remainder = item.split(":", 1)
        variant_name = remainder.strip()
        change_focus = ""
        if "[" in remainder and remainder.endswith("]"):
            base, focus = remainder.rsplit("[", 1)
            variant_name = base.strip()
            change_focus = focus[:-1].strip()
        slots.append(
            {
                "slot_id": slot_id.strip(),
                "variant_name": variant_name,
                "change_focus": change_focus,
            }
        )
    return slots


def _slot_question_index(value: str) -> dict[str, str]:
    index: dict[str, str] = {}
    for item in [part.strip() for part in str(value or "").split("|") if part.strip()]:
        if ":" not in item:
            continue
        slot_id, question = item.split(":", 1)
        index[slot_id.strip()] = question.strip()
    return index


def _parse_slot_outcome(value: Any) -> bool | None:
    text = str(value or "").strip().lower()
    if text in {"true", "1", "yes", "y", "success", "passed", "win", "won"}:
        return True
    if text in {"false", "0", "no", "n", "failed", "fail", "loss", "lost"}:
        return False
    return None


def _slot_summary_index(value: str) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for item in [part.strip() for part in str(value or "").split("|") if part.strip()]:
        match = re.match(r"^(slot_\d+)\s*[:=]\s*(.+)$", item, re.IGNORECASE)
        if not match:
            continue
        slot_id = str(match.group(1) or "").strip()
        remainder = str(match.group(2) or "").strip()
        outcome_label = ""
        summary = remainder
        structured = re.match(r"^([a-zA-Z_]+)\s*[:=-]\s*(.+)$", remainder)
        if structured:
            candidate = str(structured.group(1) or "").strip()
            parsed = _parse_slot_outcome(candidate)
            if parsed is not None:
                outcome_label = candidate
                summary = str(structured.group(2) or "").strip()
        parsed_success = _parse_slot_outcome(outcome_label) if outcome_label else _parse_slot_outcome(remainder)
        index[slot_id] = {
            "slot_id": slot_id,
            "outcome_label": outcome_label,
            "summary": summary,
            "success": parsed_success,
        }
    return index


def _slot_success(actual_signal: str, parent_success: bool | None, slot_summary: dict[str, Any]) -> bool | None:
    parsed_success = slot_summary.get("success")
    if parsed_success is not None:
        return bool(parsed_success)
    text = str(actual_signal or "").strip().lower()
    if not text:
        return None
    if any(token in text for token in ("won", "winner", "improved", "beat", "success", "passed", "lift", "positive")):
        return True
    if any(token in text for token in ("lost", "worse", "failed", "drop", "decline", "negative")):
        return False
    return parent_success if parent_success is not None and text else None


def _slot_learning_state(result_row: dict[str, Any], actual_signal: str, slot_success: bool | None) -> str:
    if actual_signal and slot_success is not None:
        return "closed"
    if str(result_row.get("execution_status") or "").strip():
        return "needs_outcome"
    return "needs_execution_confirmation"


def _slot_missing_fields(learning_state: str, actual_signal: str, success: bool | None) -> list[str]:
    if learning_state == "closed" and actual_signal and success is not None:
        return []
    fields = ["slot_result_summary"]
    if learning_state == "needs_execution_confirmation":
        fields.insert(0, "execution_status")
    if success is None:
        fields.append("success")
    return fields


def _slot_confidence(learning_state: str, actual_signal: str, success: bool | None) -> str:
    if learning_state == "closed" and actual_signal and success is not None:
        return "high"
    if actual_signal:
        return "medium"
    return "low"


def _slot_memory_tags(experiment: dict[str, Any], result_row: dict[str, Any], change_focus: str) -> list[str]:
    tags = ["experiment", "discovery", "discovery_slot"]
    if _slot_pattern_memory_state(result_row, "closed") == "pattern_memory_closed":
        tags.append("discovery_pattern_memory")
    elif str(result_row.get("result_state") or "") != "approval_blocked":
        tags.append("discovery_pattern_candidate")
    text = " ".join(
        [
            str(experiment.get("test_type") or ""),
            str(experiment.get("primary_test_axis") or ""),
            str(result_row.get("discovery_test_slot") or ""),
            change_focus,
        ]
    ).lower()
    if "hook" in text or "cta" in text or "subtitle" in text or "urgency" in text or "benefit" in text:
        tags.append("hook")
    if "motion" in text:
        tags.append("motion")
    return tags


def _slot_next_update_required(learning_state: str, actual_signal: str, success: bool | None) -> str:
    if learning_state == "closed" and actual_signal and success is not None:
        return "No update required; ready for slot-level causal review."
    if learning_state == "needs_execution_confirmation":
        return "Confirm slot execution, then record slot-level outcome summary in the format slot_01:win:CTR +18% or slot_02:loss:CPI worsened."
    return "Add slot_result_summary with explicit win/loss markers, for example slot_01:win:CTR +18%."


def _slot_pattern_memory_state(result_row: dict[str, Any], learning_state: str) -> str:
    if learning_state != "closed":
        return "awaiting_slot_evidence"
    if str(result_row.get("result_state") or "") == "closed":
        return "pattern_memory_closed"
    return "ready_for_pattern_memory"


def _slot_reusable_pattern_key(experiment: dict[str, Any], result_row: dict[str, Any], change_focus: str) -> str:
    project = _project_from_text(result_row.get("target") or experiment.get("target") or "") or "unknown_project"
    channel = str(experiment.get("channel") or "unknown_channel").strip() or "unknown_channel"
    country = str(experiment.get("country") or "unknown_country").strip() or "unknown_country"
    test_type = str(result_row.get("discovery_test_slot") or experiment.get("test_type") or "unknown_test").strip() or "unknown_test"
    focus = str(change_focus or "unspecified_change").strip() or "unspecified_change"
    tokens = [project, channel, country, test_type, focus]
    return ":".join(_key_token(token) for token in tokens if str(token).strip())


def _key_token(value: Any) -> str:
    token = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")
    return token or "unknown"


def _structure_context(winner_structure_bias: list[dict[str, Any]], baseline_asset_type: str = "") -> dict[str, Any]:
    context: dict[str, Any] = {}
    if baseline_asset_type:
        context["asset_type"] = baseline_asset_type
    recommended_focuses: list[str] = []
    for item in winner_structure_bias:
        bias_type = str(item.get("bias_type") or "").strip()
        if not bias_type:
            continue
        recommended_focus = str(item.get("recommended_focus") or "").strip()
        if recommended_focus:
            recommended_focuses.append(recommended_focus)
        context[bias_type] = {
            "value": str(item.get("value") or ""),
            "count": int(item.get("count") or 0),
            "recommended_focus": recommended_focus,
        }
    if recommended_focuses:
        context["recommended_focuses"] = recommended_focuses
    return context


def _structure_signature(winner_structure_bias: list[dict[str, Any]], baseline_asset_type: str = "") -> str:
    ordered_tokens: list[str] = []
    if baseline_asset_type:
        ordered_tokens.append(f"asset_type={baseline_asset_type}")
    bias_index = {
        str(item.get("bias_type") or "").strip(): str(item.get("value") or "").strip()
        for item in winner_structure_bias
        if str(item.get("bias_type") or "").strip()
    }
    preferred_order = ["orientation", "aspect_ratio", "duration_bucket"]
    for key in preferred_order:
        value = bias_index.pop(key, "")
        if value:
            ordered_tokens.append(f"{key}={value}")
    for key in sorted(bias_index):
        value = bias_index.get(key, "")
        if value:
            ordered_tokens.append(f"{key}={value}")
    return " | ".join(ordered_tokens)
