from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from typing import Any


DISCOVERY_APPROVAL_INPUT_FIELDS = [
    "approval_id",
    "experiment_id",
    "target",
    "approval_decision",
    "approved_for_manual_execution",
    "approved_variant_count",
    "approval_note",
    "approved_by",
    "approval_timestamp",
]


def discovery_approval_input_path(output_dir: Path, report_date: date) -> Path:
    return output_dir / f"discovery_approval_input_{report_date.strftime('%Y%m%d')}.csv"


def load_discovery_approval_inputs(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        result: dict[str, dict[str, str]] = {}
        for row in reader:
            approval_id = str(row.get("approval_id") or "").strip()
            if approval_id:
                result[approval_id] = dict(row)
        return result


def seed_discovery_approval_input_csv(path: Path, packets: list[dict[str, Any]]) -> None:
    existing = load_discovery_approval_inputs(path)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=DISCOVERY_APPROVAL_INPUT_FIELDS)
        writer.writeheader()
        for packet in packets:
            approval_id = str(packet.get("approval_id") or "")
            row = {
                "approval_id": approval_id,
                "experiment_id": packet.get("experiment_id", ""),
                "target": packet.get("target", ""),
                "approval_decision": "",
                "approved_for_manual_execution": "",
                "approved_variant_count": "",
                "approval_note": "",
                "approved_by": "",
                "approval_timestamp": "",
            }
            preserved = existing.get(approval_id, {})
            for field in DISCOVERY_APPROVAL_INPUT_FIELDS:
                if field in {"approval_id", "experiment_id", "target"}:
                    continue
                value = str(preserved.get(field) or "").strip()
                if value:
                    row[field] = value
            writer.writerow(row)


def approval_is_unblocked(row: dict[str, str] | None) -> bool:
    row = row or {}
    approved_flag = _parse_bool(row.get("approved_for_manual_execution"))
    if approved_flag is True:
        return True
    decision = str(row.get("approval_decision") or "").strip().lower()
    return decision in {"approved", "approve", "yes", "y", "pass", "passed"}


def approval_is_rejected(row: dict[str, str] | None) -> bool:
    row = row or {}
    approved_flag = _parse_bool(row.get("approved_for_manual_execution"))
    if approved_flag is False:
        return True
    decision = str(row.get("approval_decision") or "").strip().lower()
    return decision in {"rejected", "reject", "no", "n", "blocked", "deny", "denied"}


def approval_resolution_state(row: dict[str, str] | None) -> str:
    if approval_is_unblocked(row):
        return "approved_for_manual_execution"
    if approval_is_rejected(row):
        return "approval_rejected"
    return "approval_pending_input"


def _parse_bool(value: Any) -> bool | None:
    text = str(value or "").strip().lower()
    if text in {"true", "1", "yes", "y", "approved"}:
        return True
    if text in {"false", "0", "no", "n", "rejected"}:
        return False
    return None
