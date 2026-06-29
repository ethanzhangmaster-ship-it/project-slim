from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.approval_feedback_gate import ApprovalFeedbackGateBuilder
from market_ops.config import Settings
from market_ops.discovery_approval_state import (
    approval_is_rejected,
    approval_is_unblocked,
    discovery_approval_input_path,
    load_discovery_approval_inputs,
)


@dataclass(slots=True)
class ExperimentResultIngestionResult:
    markdown_path: Path
    json_path: Path
    template_csv_path: Path
    input_csv_path: Path
    passed: bool


class ExperimentResultIngestionBuilder:
    """Reads manual experiment result rows and produces learning-ready evidence."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> ExperimentResultIngestionResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self.build_payload(report_date)

        markdown_path = output_dir / f"experiment_result_ingestion_{suffix}.md"
        json_path = output_dir / f"experiment_result_ingestion_{suffix}.json"
        template_csv_path = output_dir / f"experiment_result_template_{suffix}.csv"
        input_csv_path = output_dir / f"experiment_result_input_{suffix}.csv"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._write_template_csv(template_csv_path, payload["result_rows"])
        self._seed_manual_input_csv(input_csv_path, payload["result_rows"])
        return ExperimentResultIngestionResult(
            markdown_path=markdown_path,
            json_path=json_path,
            template_csv_path=template_csv_path,
            input_csv_path=input_csv_path,
            passed=bool(payload["passed"]),
        )

    def build_payload(self, report_date: date) -> dict[str, Any]:
        suffix = report_date.strftime("%Y%m%d")
        output_dir = self._settings.active_output_dir
        gate_payload = ApprovalFeedbackGateBuilder(self._settings).build_payload(report_date)
        manual_results = _load_manual_results(output_dir / f"experiment_result_input_{suffix}.csv")
        slot_manual_results = _load_slot_manual_results(output_dir / f"discovery_slot_result_input_{suffix}.csv")
        approval_inputs = load_discovery_approval_inputs(discovery_approval_input_path(output_dir, report_date))

        result_rows = [
            _result_row(
                item,
                manual_results.get(f"experiment::{str(item.get('experiment_id') or '')}")
                or manual_results.get(str(item.get("approval_id") or "")),
                slot_manual_results.get(str(item.get("approval_id") or ""), []),
                approval_inputs.get(str(item.get("approval_id") or ""), {}),
                index,
            )
            for index, item in enumerate(gate_payload.get("approval_items") or [], start=1)
        ]
        closed = [item for item in result_rows if item["result_state"] == "closed"]
        needs_input = [item for item in result_rows if item["result_state"] == "needs_manual_input"]
        blocked = [item for item in result_rows if item["result_state"] == "approval_blocked"]

        return {
            "report_date": report_date.isoformat(),
            "mode": "manual_result_ingestion",
            "passed": True,
            "rules": {
                "no_tracker_mutation": True,
                "manual_input_file": str(output_dir / f"experiment_result_input_{suffix}.csv"),
                "template_file": str(output_dir / f"experiment_result_template_{suffix}.csv"),
                "slot_manual_input_file": str(output_dir / f"discovery_slot_result_input_{suffix}.csv"),
                "manual_approval_input_file": str(discovery_approval_input_path(output_dir, report_date)),
            },
            "summary": {
                "result_row_count": len(result_rows),
                "closed_result_count": len(closed),
                "needs_manual_input_count": len(needs_input),
                "approval_blocked_count": len(blocked),
                "critical_learning_result_row_count": sum(
                    1 for item in result_rows if str(item.get("result_priority") or "") == "critical_learning_blocker"
                ),
            },
            "result_rows": result_rows,
            "learning_evidence": [_learning_evidence(item) for item in closed],
        }

    @staticmethod
    def _write_template_csv(path: Path, rows: list[dict[str, Any]]) -> None:
        fieldnames = _csv_fieldnames()
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for item in rows:
                writer.writerow({field: item.get(field, "") for field in fieldnames})

    @staticmethod
    def _seed_manual_input_csv(path: Path, rows: list[dict[str, Any]]) -> None:
        fieldnames = _csv_fieldnames()
        if path.exists():
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                existing_rows = [dict(row) for row in reader]
            row_index: dict[str, dict[str, str]] = {}
            for row in existing_rows:
                approval_id = str(row.get("approval_id") or "")
                experiment_id = str(row.get("experiment_id") or "")
                if approval_id:
                    row_index[approval_id] = row
                if experiment_id:
                    row_index[f"experiment::{experiment_id}"] = row
            identity_fields = {"approval_id", "experiment_id", "hypothesis_id", "target"}
            discovery_only_fields = {
                "discovery_test_slot",
                "baseline_asset_group",
                "variant_plan_summary",
                "slot_execution_plan",
                "slot_learning_question",
                "slot_result_summary",
            }
            with path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                for item in rows:
                    existing = (
                        row_index.get(f"experiment::{str(item.get('experiment_id') or '')}")
                        or row_index.get(str(item.get("approval_id") or ""))
                        or {}
                    )
                    writer.writerow(
                        _seed_manual_row(
                            item,
                            existing,
                            fieldnames=fieldnames,
                            identity_fields=identity_fields,
                            discovery_only_fields=discovery_only_fields,
                        )
                    )
            return
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for item in rows:
                writer.writerow(
                    _seed_manual_row(
                        item,
                        {},
                        fieldnames=fieldnames,
                        identity_fields={"approval_id", "experiment_id", "hypothesis_id", "target"},
                        discovery_only_fields={
                            "discovery_test_slot",
                            "baseline_asset_group",
                            "variant_plan_summary",
                            "slot_execution_plan",
                            "slot_learning_question",
                            "slot_result_summary",
                        },
                    )
                )

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        lines = [
            f"# Experiment Result Ingestion | {payload['report_date']}",
            "",
            "- Mode: manual_result_ingestion",
            "- Purpose: turn approved experiment outcomes into learning-ready evidence.",
            "- Boundary: no tracker mutation; manual result input is read from the configured CSV when present.",
            "",
            "## Summary",
            "",
            f"- Result rows: {summary['result_row_count']}",
            f"- Closed results: {summary['closed_result_count']}",
            f"- Needs manual input: {summary['needs_manual_input_count']}",
            f"- Approval blocked: {summary['approval_blocked_count']}",
            f"- Critical learning rows: {summary['critical_learning_result_row_count']}",
            f"- Manual input file: {payload['rules']['manual_input_file']}",
            f"- Template file: {payload['rules']['template_file']}",
            "",
            "## Rows",
            "",
        ]
        if not payload["result_rows"]:
            lines.append("- None.")
        for item in payload["result_rows"][:50]:
            required_fields = ", ".join(item.get("required_result_fields") or []) or "none"
            recommended_fields = ", ".join(item.get("recommended_result_fields") or []) or "none"
            lines.append(
                f"- {item['approval_id']} | {item['result_state']} | {item['target']} | "
                f"priority={item.get('result_priority') or 'standard'} | success={item['success']} | "
                f"missing={', '.join(item['missing_result_fields']) or 'none'} | required={required_fields} | "
                f"recommended={recommended_fields}"
            )
        lines.append("")
        return "\n".join(lines)


def _csv_fieldnames() -> list[str]:
    return [
            "approval_id",
            "experiment_id",
            "hypothesis_id",
            "target",
            "execution_status",
            "actual_result_note",
            "success",
            "post_action_roi_or_roas",
            "post_action_ctr",
            "post_action_cpi",
            "created_variant_count",
            "linked_new_creative_ids",
            "winner_variant_type",
            "winner_baseline_asset",
            "discovery_test_slot",
            "baseline_asset_group",
            "variant_plan_summary",
            "slot_execution_plan",
            "slot_learning_question",
            "slot_result_summary",
            "learning_note",
            "captured_cpi",
            "captured_retention_d1",
            "captured_arpu",
            "captured_arppu",
            "captured_payback_d7",
            "captured_fatigue_evidence",
            "evidence_source_link",
    ]


def _seed_manual_row(
    item: dict[str, Any],
    existing: dict[str, str],
    *,
    fieldnames: list[str],
    identity_fields: set[str],
    discovery_only_fields: set[str],
) -> dict[str, Any]:
    manual_capture_fields = {
        "execution_status",
        "actual_result_note",
        "success",
        "post_action_roi_or_roas",
        "post_action_ctr",
        "post_action_cpi",
        "created_variant_count",
        "linked_new_creative_ids",
        "winner_variant_type",
        "winner_baseline_asset",
        "slot_result_summary",
        "learning_note",
        "captured_cpi",
        "captured_retention_d1",
        "captured_arpu",
        "captured_arppu",
        "captured_payback_d7",
        "captured_fatigue_evidence",
        "evidence_source_link",
    }
    merged = {field: "" for field in fieldnames}
    is_discovery = bool(str(item.get("discovery_test_slot") or "").strip())
    for field in fieldnames:
        if field in identity_fields:
            merged[field] = item.get(field, "")
            continue
        existing_value = existing.get(field, "")
        if str(existing_value).strip():
            merged[field] = existing_value
            continue
        if field in manual_capture_fields:
            merged[field] = ""
            continue
        if field in discovery_only_fields and not is_discovery:
            merged[field] = ""
            continue
        merged[field] = item.get(field, "")
    return merged


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _load_manual_results(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        index: dict[str, dict[str, str]] = {}
        for row in reader:
            approval_id = str(row.get("approval_id") or "")
            experiment_id = str(row.get("experiment_id") or "")
            payload = dict(row)
            if approval_id:
                index[approval_id] = payload
            if experiment_id:
                index[f"experiment::{experiment_id}"] = payload
        return index


def _load_slot_manual_results(path: Path) -> dict[str, list[dict[str, str]]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        index: dict[str, list[dict[str, str]]] = {}
        for row in reader:
            approval_id = str(row.get("approval_id") or "").strip()
            if not approval_id:
                continue
            index.setdefault(approval_id, []).append(dict(row))
        return index


def _result_row(
    approval: dict[str, Any],
    manual: dict[str, str] | None,
    slot_manual_rows: list[dict[str, str]] | None,
    approval_input: dict[str, str] | None,
    index: int,
) -> dict[str, Any]:
    manual = manual or {}
    slot_manual_rows = slot_manual_rows or []
    approval_input = approval_input or {}
    is_discovery = str(approval.get("source") or "") == "discovery_backlog" or str(approval.get("experiment_id") or "").startswith("discovery_plan_")
    default_discovery_slot = ""
    default_baseline_group = ""
    default_variant_plan_summary = ""
    default_slot_execution_plan = ""
    default_slot_learning_question = ""
    if is_discovery:
        default_discovery_slot = str(approval.get("test_type") or "")
        default_baseline_group = ",".join(list(approval.get("baseline_creative_ids") or []) or list(approval.get("baseline_creative_names") or []))
        default_variant_plan_summary = str(approval.get("variant_plan_summary") or "")
        if not default_variant_plan_summary:
            if default_discovery_slot == "winner_image_to_motion_test":
                default_variant_plan_summary = "motion_variants_planned"
            elif default_discovery_slot == "winner_hook_clone_test":
                default_variant_plan_summary = "hook_or_cta_variants_planned"
        default_slot_execution_plan, default_slot_learning_question = _discovery_slot_defaults(approval)
    slot_rollup = _slot_rollup(slot_manual_rows)
    slot_packets = _merge_slot_packets(
        list(approval.get("slot_packets") or []),
        slot_manual_rows,
    )
    parent_close_fields = [
        "created_variant_count",
        "linked_new_creative_ids",
        "learning_note",
    ] if is_discovery else []
    row = {
        "result_id": f"result_{index:03d}",
        "approval_id": approval.get("approval_id", ""),
        "approval_status": _effective_approval_status(str(approval.get("approval_status") or ""), approval_input),
        "manual_approval_state": _manual_approval_state(approval_input),
        "manual_approval_decision": str(approval_input.get("approval_decision") or ""),
        "manual_approval_note": str(approval_input.get("approval_note") or ""),
        "experiment_id": approval.get("experiment_id", ""),
        "hypothesis_id": approval.get("hypothesis_id", ""),
        "target": approval.get("target", ""),
        "execution_status": str(manual.get("execution_status") or slot_rollup.get("execution_status") or ""),
        "actual_result_note": str(manual.get("actual_result_note") or slot_rollup.get("actual_result_note") or ""),
        "success": _parse_success(manual.get("success") or slot_rollup.get("success")),
        "post_action_roi_or_roas": str(manual.get("post_action_roi_or_roas") or slot_rollup.get("post_action_roi_or_roas") or ""),
        "post_action_ctr": str(manual.get("post_action_ctr") or slot_rollup.get("post_action_ctr") or ""),
        "post_action_cpi": str(manual.get("post_action_cpi") or slot_rollup.get("post_action_cpi") or ""),
        "created_variant_count": str(manual.get("created_variant_count") or ""),
        "linked_new_creative_ids": str(manual.get("linked_new_creative_ids") or ""),
        "winner_variant_type": str(manual.get("winner_variant_type") or ""),
        "winner_baseline_asset": str(manual.get("winner_baseline_asset") or ""),
        "discovery_test_slot": str(manual.get("discovery_test_slot") or default_discovery_slot) if is_discovery else "",
        "baseline_asset_group": str(manual.get("baseline_asset_group") or default_baseline_group) if is_discovery else "",
        "variant_plan_summary": str(manual.get("variant_plan_summary") or default_variant_plan_summary) if is_discovery else "",
        "slot_execution_plan": str(manual.get("slot_execution_plan") or default_slot_execution_plan) if is_discovery else "",
        "slot_learning_question": str(manual.get("slot_learning_question") or default_slot_learning_question) if is_discovery else "",
        "slot_result_summary": str(manual.get("slot_result_summary") or slot_rollup.get("slot_result_summary") or ""),
        "learning_note": str(manual.get("learning_note") or ""),
        "captured_cpi": str(manual.get("captured_cpi") or ""),
        "captured_retention_d1": str(manual.get("captured_retention_d1") or ""),
        "captured_arpu": str(manual.get("captured_arpu") or ""),
        "captured_arppu": str(manual.get("captured_arppu") or ""),
        "captured_payback_d7": str(manual.get("captured_payback_d7") or ""),
        "captured_fatigue_evidence": str(manual.get("captured_fatigue_evidence") or ""),
        "evidence_source_link": str(manual.get("evidence_source_link") or ""),
        "required_result_fields": list(approval.get("required_result_fields") or []),
        "recommended_result_fields": list(approval.get("recommended_result_fields") or []),
        "result_priority": approval.get("approval_priority", ""),
        "slot_packet_count": len(slot_packets),
        "slot_packets": slot_packets,
        "manual_input_file": _parent_manual_input_file(approval),
        "slot_manual_input_file": _slot_manual_input_file(approval),
        "result_template_file": approval.get("result_template_file", ""),
        "next_learning_step": approval.get("next_learning_step", ""),
        "project": approval.get("project", ""),
        "channel": approval.get("channel", ""),
        "country": approval.get("country", ""),
        "test_type": approval.get("test_type", ""),
        "learning_goal": approval.get("learning_goal", ""),
        "baseline_creative_names": list(approval.get("baseline_creative_names") or []),
        "baseline_creative_ids": list(approval.get("baseline_creative_ids") or []),
        "baseline_asset_preview": list(approval.get("baseline_asset_preview") or []),
        "baseline_asset_type": approval.get("baseline_asset_type", ""),
        "variant_count_target": int(approval.get("variant_count_target") or 0),
        "control_dimensions": list(approval.get("control_dimensions") or []),
        "primary_test_axis": approval.get("primary_test_axis", ""),
        "winner_material_asset_count": int(approval.get("winner_material_asset_count") or 0),
        "discovery_prioritized_change_focuses": list(approval.get("discovery_prioritized_change_focuses") or []),
        "winner_structure_bias": list(approval.get("winner_structure_bias") or []),
        "structural_test_rationale": str(approval.get("structural_test_rationale") or ""),
        "parent_close_fields": parent_close_fields,
    }
    row["missing_result_fields"] = _missing_result_fields(row)
    row["parent_close_missing_fields"] = _parent_close_missing_fields(row)
    if row["approval_status"] in {"approval_blocked", "approval_rejected"}:
        row["result_state"] = "approval_blocked"
    elif not row["missing_result_fields"] and row["success"] is not None:
        row["result_state"] = "closed"
    else:
        row["result_state"] = "needs_manual_input"
    row["parent_close_state"] = _parent_close_state(row)
    return row


def _discovery_slot_defaults(approval: dict[str, Any]) -> tuple[str, str]:
    variant_count = int(approval.get("variant_count_target") or 0)
    if variant_count <= 0:
        return "", ""
    baseline_preview = list(approval.get("baseline_asset_preview") or [])
    test_type = str(approval.get("test_type") or "")
    project = str(approval.get("project") or "")
    channel = str(approval.get("channel") or "")
    country = str(approval.get("country") or "")
    primary_test_axis = str(approval.get("primary_test_axis") or "")
    naming_prefix = _slug("_".join(part for part in (project, channel, country, test_type) if part))
    focus_options = (
        ["light_motion", "camera_push", "text_motion", "cta_motion"]
        if test_type == "winner_image_to_motion_test"
        else ["hook_rewrite", "hook_reorder", "cta_swap", "subtitle_density", "urgency_angle", "benefit_angle"]
    )
    slot_plan_parts: list[str] = []
    learning_question_parts: list[str] = []
    for slot_number in range(1, variant_count + 1):
        slot_id = f"slot_{slot_number:02d}"
        variant_name = f"{naming_prefix}_v{slot_number:02d}"
        change_focus = focus_options[(slot_number - 1) % len(focus_options)]
        baseline_anchor = baseline_preview[(slot_number - 1) % len(baseline_preview)] if baseline_preview else ""
        slot_plan_parts.append(f"{slot_id}:{variant_name}[{change_focus}]")
        learning_question_parts.append(
            f"{slot_id}:Did {change_focus} improve {primary_test_axis} performance versus baseline {baseline_anchor}?"
        )
    return " | ".join(slot_plan_parts), " | ".join(learning_question_parts)


def _slug(value: str) -> str:
    slug = "".join(char.lower() if char.isalnum() else "_" for char in str(value or "")).strip("_")
    return "_".join(part for part in slug.split("_") if part) or "discovery_variant"


def _missing_result_fields(row: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for field in row.get("required_result_fields") or []:
        if field == "success":
            if row.get("success") is None:
                missing.append(field)
        elif not str(row.get(field) or "").strip():
            missing.append(field)
    return missing


def _parent_close_missing_fields(row: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for field in row.get("parent_close_fields") or []:
        if not str(row.get(field) or "").strip():
            missing.append(field)
    return missing


def _parent_close_state(row: dict[str, Any]) -> str:
    approval_status = str(row.get("approval_status") or "")
    if approval_status in {"approval_blocked", "approval_rejected"}:
        return "approval_blocked"
    if str(row.get("result_state") or "") != "closed":
        return "awaiting_slot_outcomes"
    slot_packets = list(row.get("slot_packets") or [])
    if slot_packets and any(not _slot_packet_closed(packet) for packet in slot_packets):
        return "awaiting_slot_outcomes"
    if row.get("parent_close_missing_fields"):
        return "needs_parent_close"
    return "closed"


def _parse_success(value: Any) -> bool | None:
    text = str(value or "").strip().lower()
    if text in {"true", "1", "yes", "y", "success", "passed"}:
        return True
    if text in {"false", "0", "no", "n", "failed", "fail"}:
        return False
    return None


def _slot_rollup(rows: list[dict[str, str]]) -> dict[str, str]:
    if not rows:
        return {}
    ordered = sorted(rows, key=lambda row: str(row.get("slot_id") or ""))
    execution_values = [str(row.get("execution_status") or "").strip() for row in ordered if str(row.get("execution_status") or "").strip()]
    note_values = [str(row.get("actual_result_note") or "").strip() for row in ordered if str(row.get("actual_result_note") or "").strip()]
    ctr_values = [str(row.get("post_action_ctr") or "").strip() for row in ordered if str(row.get("post_action_ctr") or "").strip()]
    cpi_values = [str(row.get("post_action_cpi") or "").strip() for row in ordered if str(row.get("post_action_cpi") or "").strip()]
    roi_values = [str(row.get("post_action_roi_or_roas") or "").strip() for row in ordered if str(row.get("post_action_roi_or_roas") or "").strip()]
    summary_parts: list[str] = []
    success_values: list[bool] = []
    for row in ordered:
        slot_id = str(row.get("slot_id") or "").strip()
        slot_note = str(row.get("slot_result_note") or "").strip()
        slot_success = _parse_success(row.get("success"))
        if slot_success is True:
            success_values.append(True)
        elif slot_success is False:
            success_values.append(False)
        if slot_id and slot_note:
            label = "win" if slot_success is True else ("loss" if slot_success is False else "mixed")
            summary_parts.append(f"{slot_id}:{label}:{slot_note}")
    success_rollup = ""
    if success_values:
        success_rollup = "true" if any(success_values) else "false"
    return {
        "execution_status": "executed" if execution_values else "",
        "actual_result_note": " | ".join(note_values),
        "success": success_rollup,
        "slot_result_summary": " | ".join(summary_parts),
        "post_action_ctr": " | ".join(ctr_values),
        "post_action_cpi": " | ".join(cpi_values),
        "post_action_roi_or_roas": " | ".join(roi_values),
    }


def _merge_slot_packets(base_packets: list[dict[str, Any]], slot_manual_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    manual_index = {
        str(row.get("slot_id") or "").strip(): dict(row)
        for row in slot_manual_rows
        if str(row.get("slot_id") or "").strip()
    }
    seen_slot_ids: set[str] = set()
    for packet in base_packets:
        slot_id = str(packet.get("slot_id") or "").strip()
        seen_slot_ids.add(slot_id)
        merged.append(_merge_slot_packet(packet, manual_index.get(slot_id, {})))
    for slot_id, manual_row in manual_index.items():
        if slot_id in seen_slot_ids:
            continue
        merged.append(_merge_slot_packet({"slot_id": slot_id}, manual_row))
    merged.sort(key=lambda item: str(item.get("slot_id") or ""))
    return merged


def _merge_slot_packet(packet: dict[str, Any], manual_row: dict[str, str]) -> dict[str, Any]:
    merged = dict(packet)
    if not manual_row:
        return merged
    execution_status = str(manual_row.get("execution_status") or "").strip()
    success_raw = str(manual_row.get("success") or "").strip()
    slot_result_note = str(manual_row.get("slot_result_note") or "").strip()
    slot_result_summary = (
        str(manual_row.get("slot_result_summary") or "").strip()
        or _format_slot_result_summary(
            slot_id=str(merged.get("slot_id") or manual_row.get("slot_id") or "").strip(),
            success=success_raw,
            note=slot_result_note,
        )
    )
    if execution_status:
        merged["execution_status"] = execution_status
    if success_raw:
        merged["success"] = success_raw
        merged["slot_success"] = success_raw
    if slot_result_note:
        merged["slot_result_note"] = slot_result_note
    if slot_result_summary:
        merged["slot_result_summary"] = slot_result_summary
    for field in (
        "actual_result_note",
        "post_action_ctr",
        "post_action_cpi",
        "post_action_roi_or_roas",
        "variant_name",
        "change_focus",
        "learning_question",
    ):
        value = str(manual_row.get(field) or "").strip()
        if value:
            merged[field] = value
    return merged


def _format_slot_result_summary(*, slot_id: str, success: str, note: str) -> str:
    if not slot_id or not note:
        return ""
    success_value = _parse_success(success)
    if success_value is True:
        label = "win"
    elif success_value is False:
        label = "loss"
    else:
        label = "mixed"
    return f"{slot_id}:{label}:{note}"


def _slot_packet_closed(packet: dict[str, Any]) -> bool:
    if not str(packet.get("execution_status") or "").strip():
        return False
    if not str(packet.get("slot_result_summary") or "").strip():
        return False
    return _parse_success(packet.get("success")) is not None


def _parent_manual_input_file(approval: dict[str, Any]) -> str:
    slot_like_path = str(approval.get("manual_input_file") or "")
    if "discovery_slot_result_input_" in slot_like_path:
        return slot_like_path.replace("discovery_slot_result_input_", "experiment_result_input_")
    return slot_like_path


def _slot_manual_input_file(approval: dict[str, Any]) -> str:
    slot_like_path = str(approval.get("manual_input_file") or "")
    if "experiment_result_input_" in slot_like_path:
        return slot_like_path.replace("experiment_result_input_", "discovery_slot_result_input_")
    return slot_like_path


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


def _learning_evidence(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "hypothesis_id": row.get("hypothesis_id", ""),
        "experiment_id": row.get("experiment_id", ""),
        "approval_id": row.get("approval_id", ""),
        "target": row.get("target", ""),
        "actual_signal": row.get("actual_result_note", ""),
        "success": row.get("success"),
        "post_metrics": {
            "post_action_roi_or_roas": row.get("post_action_roi_or_roas", ""),
            "post_action_ctr": row.get("post_action_ctr", ""),
            "post_action_cpi": row.get("post_action_cpi", ""),
            "created_variant_count": row.get("created_variant_count", ""),
            "linked_new_creative_ids": row.get("linked_new_creative_ids", ""),
            "winner_variant_type": row.get("winner_variant_type", ""),
            "winner_baseline_asset": row.get("winner_baseline_asset", ""),
            "discovery_test_slot": row.get("discovery_test_slot", ""),
            "baseline_asset_group": row.get("baseline_asset_group", ""),
            "variant_plan_summary": row.get("variant_plan_summary", ""),
            "slot_execution_plan": row.get("slot_execution_plan", ""),
            "slot_learning_question": row.get("slot_learning_question", ""),
            "slot_result_summary": row.get("slot_result_summary", ""),
            "learning_note": row.get("learning_note", ""),
            "discovery_prioritized_change_focuses": row.get("discovery_prioritized_change_focuses", []),
            "winner_structure_bias": row.get("winner_structure_bias", []),
            "structural_test_rationale": row.get("structural_test_rationale", ""),
            "captured_cpi": row.get("captured_cpi", ""),
            "captured_retention_d1": row.get("captured_retention_d1", ""),
            "captured_arpu": row.get("captured_arpu", ""),
            "captured_arppu": row.get("captured_arppu", ""),
            "captured_payback_d7": row.get("captured_payback_d7", ""),
            "captured_fatigue_evidence": row.get("captured_fatigue_evidence", ""),
            "evidence_source_link": row.get("evidence_source_link", ""),
        },
        "source": "experiment_result_ingestion",
    }
