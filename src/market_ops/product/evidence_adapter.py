"""Adapter from the trusted Decision Engine contract to growth-loop evidence."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any


DECISION_TO_OUTCOME = {"small_scale_up": "WINNER", "pause_or_review": "FAILED", "downweight": "FAILED", "repair": "INCONCLUSIVE", "hold": "PROMISING"}


@dataclass(frozen=True, slots=True)
class EvidenceBatch:
    results: list[dict[str, Any]]
    total_budget: float
    skipped: list[dict[str, str]]


def assert_fresh(payload: dict[str, Any], *, as_of: date, max_age_days: int = 7) -> None:
    """Reject stale decision reports before they can create any execution task."""
    raw_date = str(payload.get("report_date") or "")
    try:
        report_date = date.fromisoformat(raw_date)
    except ValueError as exc:
        raise ValueError("Decision report has no valid report_date") from exc
    age = (as_of - report_date).days
    if age < 0:
        raise ValueError("Decision report date is in the future")
    if age > max_age_days:
        raise ValueError(f"Decision report is stale ({age} days old; maximum is {max_age_days})")


def assert_performance_coverage_fresh(path: Path, *, as_of: date, max_age_days: int = 2) -> None:
    """Reject execution planning when the underlying performance coverage is stale.

    File modification time is intentionally ignored: a successful sync of an
    old spreadsheet must not make old spend look actionable.
    """
    if not path.exists():
        raise ValueError(f"Performance data source is missing: {path}")
    with path.open(encoding="utf-8-sig", newline="") as stream:
        dates = [str(row.get("date") or "") for row in csv.DictReader(stream)]
    valid_dates: list[date] = []
    for raw in dates:
        try:
            valid_dates.append(date.fromisoformat(raw))
        except ValueError:
            continue
    if not valid_dates:
        raise ValueError("Performance data source has no valid date coverage")
    latest = max(valid_dates)
    age = (as_of - latest).days
    if age < 0:
        raise ValueError("Performance data coverage is in the future")
    if age > max_age_days:
        raise ValueError(f"Performance data coverage is stale ({age} days old; maximum is {max_age_days})")


def from_decision_engine(payload: dict[str, Any]) -> EvidenceBatch:
    """Translate only trusted creative decisions into the growth-loop contract.

    Data-blocked entries never become actions. Non-creative entities are
    excluded because they do not identify a safely executable creative.
    """
    results: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for item in payload.get("items") or []:
        entity_id = str(item.get("entity_id") or "").strip()
        decision = str(item.get("decision") or "").strip()
        entity_type = str(item.get("entity_type") or "").strip().lower()
        if entity_type != "creative":
            skipped.append({"entity_id": entity_id, "reason": "not_a_creative"})
        elif not entity_id:
            skipped.append({"entity_id": "", "reason": "missing_entity_id"})
        elif decision not in DECISION_TO_OUTCOME:
            skipped.append({"entity_id": entity_id, "reason": f"decision_not_actionable:{decision or 'missing'}"})
        else:
            positives = [str(value) for value in (item.get("top_positive_signals") or [])[:3]]
            negatives = [str(value) for value in (item.get("top_negative_signals") or [])[:2]]
            results.append({"experiment_id": f"decision-engine:{payload.get('report_date', 'unknown')}:{entity_id}", "creative_id": entity_id, "decision": DECISION_TO_OUTCOME[decision], "confidence": float(item.get("confidence") or 0.0), "budget_before": float(item.get("spend") or 0.0), "reason": "; ".join(positives + negatives)})
    return EvidenceBatch(results=results, total_budget=sum(float(item["budget_before"]) for item in results), skipped=skipped)
