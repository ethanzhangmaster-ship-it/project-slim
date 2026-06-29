from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.decision_engine import DecisionEngineBuilder
from market_ops.experiment_result_ingestion import ExperimentResultIngestionBuilder
from market_ops.growth_playbook import GrowthPlaybookBuilder


@dataclass(slots=True)
class LearningEvidenceQueueResult:
    markdown_path: Path
    json_path: Path
    csv_path: Path
    passed: bool


class LearningEvidenceQueueBuilder:
    """Prioritizes missing evidence needed to convert candidates into reusable learning."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> LearningEvidenceQueueResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self.build_payload(report_date)

        markdown_path = output_dir / f"learning_evidence_queue_{suffix}.md"
        json_path = output_dir / f"learning_evidence_queue_{suffix}.json"
        csv_path = output_dir / f"learning_evidence_queue_{suffix}.csv"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._write_csv(csv_path, payload["queue_items"])
        return LearningEvidenceQueueResult(markdown_path=markdown_path, json_path=json_path, csv_path=csv_path, passed=bool(payload["passed"]))

    def build_payload(self, report_date: date) -> dict[str, Any]:
        suffix = report_date.strftime("%Y%m%d")
        output_dir = self._settings.active_output_dir
        result_payload = json.loads(
            ExperimentResultIngestionBuilder(self._settings).build(report_date).json_path.read_text(encoding="utf-8")
        )
        playbook_payload = json.loads(
            GrowthPlaybookBuilder(self._settings).build(report_date).json_path.read_text(encoding="utf-8")
        )
        decision_payload = json.loads(
            DecisionEngineBuilder(self._settings).build(report_date).json_path.read_text(encoding="utf-8")
        )
        result_index = _index_result_rows(result_payload.get("result_rows") or [])
        decision_wait_index = _decision_wait_index(decision_payload.get("items") or [])
        manual_input_file = str(output_dir / f"experiment_result_input_{suffix}.csv")
        slot_manual_input_file = str(output_dir / f"discovery_slot_result_input_{suffix}.csv")
        result_template_file = str(output_dir / f"experiment_result_template_{suffix}.csv")
        queue_items = [
            _queue_item(candidate, result_index, decision_wait_index, index, manual_input_file, slot_manual_input_file, result_template_file)
            for index, candidate in enumerate(playbook_payload.get("candidate_rules") or [], start=1)
        ]
        queue_items = [item for item in queue_items if item["queue_status"] != "closed"]
        queue_items.sort(
            key=lambda item: (
                item["priority_rank"],
                -int(item.get("decision_wait_match_count") or 0),
                item["missing_field_count"],
                item["candidate_id"],
            )
        )

        return {
            "report_date": report_date.isoformat(),
            "mode": "learning_evidence_queue",
            "passed": True,
            "rules": {
                "no_tracker_mutation": True,
                "signal_only": True,
                "source_result_template": result_template_file,
                "manual_input_file": manual_input_file,
                "slot_manual_input_file": slot_manual_input_file,
                "manual_approval_input_file": str(output_dir / f"discovery_approval_input_{suffix}.csv"),
                "promotion_rule": "Only closed result evidence can promote a playbook candidate into a reusable decision rule.",
            },
            "summary": {
                "queue_item_count": len(queue_items),
                "critical_count": sum(1 for item in queue_items if item["priority"] == "critical"),
                "high_count": sum(1 for item in queue_items if item["priority"] == "high"),
                "medium_count": sum(1 for item in queue_items if item["priority"] == "medium"),
                "execution_confirmation_needed_count": sum(1 for item in queue_items if "execution_confirmation" in item["missing_evidence"]),
                "post_metric_needed_count": sum(1 for item in queue_items if any(_is_metric_field(field) for field in item["missing_evidence"])),
                "evidence_capture_needed_count": sum(1 for item in queue_items if any(field.startswith("captured_") for field in item["missing_evidence"])),
                "decision_waiting_count": sum(1 for item in queue_items if item.get("decision_waiting")),
            },
            "queue_items": queue_items,
            "next_updates": [_next_update(item) for item in queue_items[:30]],
        }

    @staticmethod
    def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
        fields = [
            "evidence_id",
            "priority",
            "queue_status",
            "candidate_id",
            "source_hypothesis_id",
            "experiment_id",
            "approval_id",
            "target",
            "experiment_type",
            "decision_waiting",
            "decision_wait_match_count",
            "missing_evidence",
            "required_template_fields",
            "recommended_template_fields",
            "manual_input_file",
            "result_template_file",
        ]
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for item in rows:
                row = dict(item)
                row["missing_evidence"] = " | ".join(item.get("missing_evidence") or [])
                row["required_template_fields"] = " | ".join(item.get("required_template_fields") or [])
                row["recommended_template_fields"] = " | ".join(item.get("recommended_template_fields") or [])
                writer.writerow({field: row.get(field, "") for field in fields})

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        lines = [
            f"# Learning Evidence Queue | {payload['report_date']}",
            "",
            "- Mode: learning_evidence_queue",
            "- Boundary: no tracker mutation, no platform writes; this queue only tells us what evidence is missing.",
            f"- Manual input file: {payload['rules']['manual_input_file']}",
            f"- Slot manual input file: {payload['rules']['slot_manual_input_file']}",
            f"- Result template: {payload['rules']['source_result_template']}",
            "",
            "## Summary",
            "",
            f"- Queue items: {summary['queue_item_count']}",
            f"- Critical: {summary['critical_count']}",
            f"- High: {summary['high_count']}",
            f"- Medium: {summary['medium_count']}",
            f"- Needs execution confirmation: {summary['execution_confirmation_needed_count']}",
            f"- Needs post metrics: {summary['post_metric_needed_count']}",
            f"- Needs captured quality/payback/fatigue evidence: {summary['evidence_capture_needed_count']}",
            f"- Waiting on Decision Engine reuse: {summary['decision_waiting_count']}",
            "",
            "## Top Evidence Items",
            "",
        ]
        if not payload["queue_items"]:
            lines.append("- None. All candidate rules have closed evidence.")
        for item in payload["queue_items"][:50]:
            missing = ", ".join(item["missing_evidence"]) if item["missing_evidence"] else "none"
            input_file = item.get("manual_input_file") or "none"
            decision_wait = "yes" if item.get("decision_waiting") else "no"
            lines.append(
                f"- {item['evidence_id']} | {item['priority']} | {item['target']} | "
                f"approval={item['approval_id'] or 'none'} | decision_wait={decision_wait} | missing={missing} | input={input_file}"
            )

        lines.extend(["", "## Next Updates", ""])
        if not payload["next_updates"]:
            lines.append("- None.")
        for item in payload["next_updates"]:
            fields = ", ".join(item["required_template_fields"]) if item["required_template_fields"] else "none"
            recommended = ", ".join(item.get("recommended_template_fields") or []) or "none"
            lines.append(f"- {item['evidence_id']} | {item['required_update']} | fields={fields} | recommended={recommended}")
        lines.append("")
        return "\n".join(lines)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _index_result_rows(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for row in rows:
        hypothesis_id = str(row.get("hypothesis_id") or "")
        if hypothesis_id:
            index[hypothesis_id] = row
        experiment_id = str(row.get("experiment_id") or "")
        if experiment_id and experiment_id not in index:
            index[experiment_id] = row
    return index


def _queue_item(
    candidate: dict[str, Any],
    result_index: dict[str, dict[str, Any]],
    decision_wait_index: dict[str, list[dict[str, Any]]],
    index: int,
    manual_input_file: str,
    slot_manual_input_file: str,
    result_template_file: str,
) -> dict[str, Any]:
    result_row = _resolve_result_row(candidate, result_index)
    result_row = result_row or {}
    missing = _merged_missing_fields(candidate, result_row)
    decision_wait_matches = _decision_wait_matches(candidate, decision_wait_index)
    priority = _priority(candidate, result_row, missing, decision_wait_matches)
    return {
        "evidence_id": f"evidence_{index:03d}",
        "priority": priority,
        "priority_rank": {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(priority, 3),
        "queue_status": "closed" if not missing else "needs_evidence",
        "candidate_id": candidate.get("candidate_id", ""),
        "source_hypothesis_id": candidate.get("source_hypothesis_id", ""),
        "experiment_id": candidate.get("source_experiment_id", result_row.get("experiment_id", "")),
        "approval_id": result_row.get("approval_id", ""),
        "target": candidate.get("target_signature", result_row.get("target", "")),
        "target_project": candidate.get("target_project", ""),
        "experiment_type": candidate.get("experiment_type", ""),
        "parent_experiment_id": candidate.get("parent_experiment_id", ""),
        "slot_id": candidate.get("slot_id", ""),
        "variant_name": candidate.get("variant_name", ""),
        "change_focus": candidate.get("change_focus", ""),
        "primary_test_axis": candidate.get("primary_test_axis", ""),
        "reusable_pattern_key": candidate.get("reusable_pattern_key", ""),
        "causal_state": candidate.get("causal_state", ""),
        "result_state": result_row.get("result_state", "missing_result_row"),
        "approval_status": result_row.get("approval_status", ""),
        "missing_evidence": missing,
        "missing_field_count": len(missing),
        "decision_waiting": bool(decision_wait_matches),
        "decision_wait_match_count": len(decision_wait_matches),
        "decision_wait_entity_ids": [str(item.get("entity_id") or "") for item in decision_wait_matches[:10] if str(item.get("entity_id") or "").strip()],
        "decision_wait_targets": [_decision_wait_target(item) for item in decision_wait_matches[:10]],
        "decision_wait_contextual_pattern_keys": _unique(
            [
                str(key)
                for item in decision_wait_matches[:10]
                for key in list(item.get("playbook_candidate_contextual_pattern_keys") or [])
                if str(key).strip()
            ]
        ),
        "required_template_fields": _template_fields(candidate, missing),
        "recommended_template_fields": _recommended_template_fields(candidate),
        "manual_input_file": _manual_input_file(candidate, result_row, manual_input_file, slot_manual_input_file),
        "result_template_file": result_template_file if result_row else "",
    }


def _merged_missing_fields(candidate: dict[str, Any], result_row: dict[str, Any]) -> list[str]:
    fields: list[str] = []
    slot_candidate = _is_slot_candidate(candidate)
    candidate_missing = list(candidate.get("missing_evidence") or [])
    row_missing = (
        _slot_missing_fields(candidate, result_row)
        if slot_candidate
        else list(result_row.get("missing_result_fields") or [])
    )
    for field in candidate_missing + row_missing:
        field = str(field or "").strip()
        if field and field not in fields:
            fields.append(field)
    if result_row and result_row.get("result_state") == "approval_blocked" and "approval_unblocked" not in fields:
        fields.insert(0, "approval_unblocked")
    if _manual_discovery_approval_resolved(result_row):
        fields = [field for field in fields if field != "approval_unblocked"]
    return fields


def _priority(
    candidate: dict[str, Any],
    result_row: dict[str, Any],
    missing: list[str],
    decision_wait_matches: list[dict[str, Any]],
) -> str:
    experiment_type = str(candidate.get("experiment_type") or "")
    if result_row.get("result_state") == "approval_blocked":
        if decision_wait_matches:
            return "critical"
        return "critical"
    if experiment_type == "discovery_slot_test":
        if decision_wait_matches and ("execution_confirmation" in missing or "execution_status" in missing or "slot_result_summary" in missing or "success" in missing):
            return "critical"
        if "execution_confirmation" in missing or "execution_status" in missing:
            return "high"
        if "slot_result_summary" in missing or "success" in missing:
            return "high"
        return "medium"
    if experiment_type == "evidence_capture" and any(field.startswith("captured_") for field in missing):
        return "critical"
    if "execution_confirmation" in missing or "execution_status" in missing:
        return "high"
    if any(_is_metric_field(field) for field in missing):
        return "high"
    return "medium"


def _template_fields(candidate: dict[str, Any], missing: list[str]) -> list[str]:
    if _is_slot_candidate(candidate):
        preferred = ["execution_status", "slot_result_summary", "success"]
        fields: list[str] = []
        for field in preferred:
            if field in missing and field not in fields:
                fields.append(field)
        return fields
    mapping = {
        "execution_confirmation": "execution_status",
        "post_action_roi_or_roas": "post_action_roi_or_roas",
        "post_action_ctr": "post_action_ctr",
        "actual_result_note": "actual_result_note",
        "success": "success",
        "created_variant_count": "created_variant_count",
        "linked_new_creative_ids": "linked_new_creative_ids",
        "captured_cpi": "captured_cpi",
        "captured_retention_d1": "captured_retention_d1",
        "captured_arpu": "captured_arpu",
        "captured_arppu": "captured_arppu",
        "captured_payback_d7": "captured_payback_d7",
        "captured_fatigue_evidence": "captured_fatigue_evidence",
        "evidence_source_link": "evidence_source_link",
    }
    fields: list[str] = []
    for field in missing:
        template_field = mapping.get(field, field)
        if template_field and template_field != "approval_unblocked" and template_field not in fields:
            fields.append(template_field)
    return fields


def _recommended_template_fields(candidate: dict[str, Any]) -> list[str]:
    if _is_slot_candidate(candidate):
        return [
            "actual_result_note",
            "post_action_roi_or_roas",
            "post_action_ctr",
            "post_action_cpi",
            "created_variant_count",
            "linked_new_creative_ids",
            "winner_variant_type",
            "learning_note",
        ]
    return []


def _next_update(item: dict[str, Any]) -> dict[str, Any]:
    missing = item.get("missing_evidence") or []
    if "approval_unblocked" in missing:
        required = "Resolve approval blocker before this evidence can close learning."
    elif item.get("experiment_type") == "discovery_slot_test":
        required = "Update the discovery slot input row with execution_status, slot_result_summary, and success for this slot."
    elif any(field.startswith("captured_") for field in missing):
        required = "Fill quality, payback, and fatigue evidence in the experiment result input CSV."
    elif "execution_confirmation" in missing or "execution_status" in missing:
        required = "Confirm execution status and add result note."
    else:
        required = "Fill post-action metrics and success flag."
    return {
        "evidence_id": item.get("evidence_id", ""),
        "candidate_id": item.get("candidate_id", ""),
        "target": item.get("target", ""),
        "required_update": required,
        "required_template_fields": item.get("required_template_fields", []),
        "recommended_template_fields": item.get("recommended_template_fields", []),
    }


def _is_metric_field(field: str) -> bool:
    field_l = str(field or "").lower()
    return any(token in field_l for token in ("roi", "roas", "ctr", "cpi", "retention", "arpu", "arppu", "payback"))


def _resolve_result_row(candidate: dict[str, Any], result_index: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    for key in (
        str(candidate.get("source_hypothesis_id") or ""),
        str(candidate.get("source_experiment_id") or ""),
        str(candidate.get("parent_experiment_id") or ""),
    ):
        if key and key in result_index:
            return result_index[key]
    return None


def _is_slot_candidate(candidate: dict[str, Any]) -> bool:
    return str(candidate.get("experiment_type") or "") == "discovery_slot_test"


def _manual_input_file(
    candidate: dict[str, Any],
    result_row: dict[str, Any],
    manual_input_file: str,
    slot_manual_input_file: str,
) -> str:
    if not result_row:
        return ""
    if _is_slot_candidate(candidate):
        return slot_manual_input_file
    return manual_input_file


def _slot_missing_fields(candidate: dict[str, Any], result_row: dict[str, Any]) -> list[str]:
    if not result_row:
        return []
    ordered = ["execution_status", "slot_result_summary", "success"]
    slot_id = str(candidate.get("slot_id") or "").strip()
    if not slot_id:
        missing = {str(field or "").strip() for field in list(result_row.get("missing_result_fields") or []) if str(field or "").strip()}
        return [field for field in ordered if field in missing]
    slot_packet = _slot_packet(result_row, slot_id)
    if not slot_packet:
        return list(ordered)
    missing: list[str] = []
    if not str(slot_packet.get("execution_status") or "").strip():
        missing.append("execution_status")
    if not str(slot_packet.get("slot_result_summary") or "").strip():
        missing.append("slot_result_summary")
    if _parse_success(slot_packet.get("success")) is None:
        missing.append("success")
    return missing


def _slot_packet(result_row: dict[str, Any], slot_id: str) -> dict[str, Any]:
    for packet in result_row.get("slot_packets") or []:
        if str(packet.get("slot_id") or "").strip() == slot_id:
            return dict(packet)
    return {}


def _parse_success(value: Any) -> bool | None:
    text = str(value or "").strip().lower()
    if text in {"true", "1", "yes", "y", "success", "passed", "win", "won"}:
        return True
    if text in {"false", "0", "no", "n", "failed", "fail", "loss", "lost"}:
        return False
    return None


def _manual_discovery_approval_resolved(result_row: dict[str, Any]) -> bool:
    return str(result_row.get("approval_status") or "") == "approved_for_manual_execution"


def _decision_wait_index(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        for key in list(item.get("playbook_candidate_contextual_pattern_keys") or []):
            token = str(key or "").strip()
            if token:
                index.setdefault(token, []).append(item)
    return index


def _decision_wait_matches(candidate: dict[str, Any], decision_wait_index: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    keys = [
        str(candidate.get("contextual_pattern_key") or "").strip(),
        str(candidate.get("reusable_pattern_key") or "").strip(),
    ]
    for key in keys:
        if not key:
            continue
        for item in decision_wait_index.get(key, []):
            if item not in matches:
                matches.append(item)
    return matches


def _decision_wait_target(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "entity_type": str(item.get("entity_type") or ""),
        "entity_id": str(item.get("entity_id") or ""),
        "project": str(item.get("project") or ""),
        "scope": str(item.get("scope") or ""),
        "decision": str(item.get("decision") or ""),
    }


def _unique(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        if item and item not in result:
            result.append(item)
    return result
