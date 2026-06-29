from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.experiment_result_ingestion import ExperimentResultIngestionBuilder
from market_ops.guarded_execution import GuardedExecutionBuilder


@dataclass(slots=True)
class RollbackMonitorResult:
    markdown_path: Path
    json_path: Path
    csv_path: Path
    passed: bool


class RollbackMonitorBuilder:
    """Builds rollback monitoring signals without executing rollback actions."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> RollbackMonitorResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self.build_payload(report_date)

        markdown_path = output_dir / f"rollback_monitor_{suffix}.md"
        json_path = output_dir / f"rollback_monitor_{suffix}.json"
        csv_path = output_dir / f"rollback_monitor_{suffix}.csv"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._write_csv(csv_path, payload["monitors"])
        return RollbackMonitorResult(markdown_path=markdown_path, json_path=json_path, csv_path=csv_path, passed=bool(payload["passed"]))

    def build_payload(self, report_date: date) -> dict[str, Any]:
        suffix = report_date.strftime("%Y%m%d")
        output_dir = self._settings.active_output_dir
        execution_path = output_dir / f"guarded_execution_{suffix}.json"
        result_path = output_dir / f"experiment_result_ingestion_{suffix}.json"
        if not execution_path.exists():
            GuardedExecutionBuilder(self._settings).build(report_date)
        if not result_path.exists():
            ExperimentResultIngestionBuilder(self._settings).build(report_date)
        execution_payload = _load_json(execution_path)
        result_payload = _load_json(result_path)

        result_index = _index_results(result_payload.get("result_rows") or [])
        monitors = [
            _monitor(item, result_index.get(str(item.get("target") or "")), index)
            for index, item in enumerate(execution_payload.get("attempts") or [], start=1)
        ]
        rollback_required = [item for item in monitors if item["monitor_status"] == "rollback_required"]
        monitoring = [item for item in monitors if item["monitor_status"] == "monitoring"]
        passed = [item for item in monitors if item["monitor_status"] == "passed"]
        not_started = [item for item in monitors if item["monitor_status"] == "not_started"]
        return {
            "report_date": report_date.isoformat(),
            "mode": "rollback_monitor_signal",
            "passed": True,
            "rules": {
                "no_rollback_execution": True,
                "signal_only": True,
                "requires_closed_result": "Rollback can only be evaluated after an executed result row exists.",
            },
            "summary": {
                "monitor_count": len(monitors),
                "rollback_required_count": len(rollback_required),
                "monitoring_count": len(monitoring),
                "passed_count": len(passed),
                "not_started_count": len(not_started),
            },
            "monitors": monitors,
        }

    @staticmethod
    def _write_csv(path: Path, monitors: list[dict[str, Any]]) -> None:
        fieldnames = [
            "monitor_id",
            "monitor_status",
            "attempt_id",
            "target",
            "operation",
            "rollback_signal",
            "missing_evidence",
        ]
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for item in monitors:
                row = {field: item.get(field, "") for field in fieldnames}
                row["missing_evidence"] = " | ".join(item.get("missing_evidence") or [])
                writer.writerow(row)

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        lines = [
            f"# Rollback Monitor | {payload['report_date']}",
            "",
            "- Mode: rollback_monitor_signal",
            "- Purpose: detect whether executed media-buyer actions should be rolled back.",
            "- Boundary: signal only; no rollback execution.",
            "",
            "## Summary",
            "",
            f"- Monitors: {summary['monitor_count']}",
            f"- Rollback required: {summary['rollback_required_count']}",
            f"- Monitoring: {summary['monitoring_count']}",
            f"- Passed: {summary['passed_count']}",
            f"- Not started: {summary['not_started_count']}",
            "",
            "## Monitors",
            "",
        ]
        if not payload["monitors"]:
            lines.append("- None.")
        for item in payload["monitors"][:50]:
            missing = ", ".join(item["missing_evidence"]) if item["missing_evidence"] else "none"
            lines.append(
                f"- {item['monitor_id']} | {item['monitor_status']} | {item['target']} | "
                f"signal={item['rollback_signal']} | missing={missing}"
            )
        lines.append("")
        return "\n".join(lines)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _index_results(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for item in items:
        target = str(item.get("target") or "")
        if target:
            index[target] = item
    return index


def _monitor(attempt: dict[str, Any], result: dict[str, Any] | None, index: int) -> dict[str, Any]:
    result = result or {}
    missing = list(result.get("missing_result_fields") or [])
    if attempt.get("attempt_status") != "executed":
        status = "not_started"
        signal = "execution_not_started"
        missing_evidence = ["executed_attempt"] + missing
    elif result.get("result_state") != "closed":
        status = "monitoring"
        signal = "waiting_for_result"
        missing_evidence = missing or ["closed_result"]
    elif result.get("success") is False:
        status = "rollback_required"
        signal = "result_failed"
        missing_evidence = []
    else:
        status = "passed"
        signal = "result_passed"
        missing_evidence = []

    return {
        "monitor_id": f"rollback_{index:03d}",
        "monitor_status": status,
        "attempt_id": attempt.get("attempt_id", ""),
        "intent_id": attempt.get("intent_id", ""),
        "target": attempt.get("target", ""),
        "operation": attempt.get("operation", ""),
        "rollback_conditions": list(attempt.get("rollback_conditions") or []),
        "rollback_signal": signal,
        "missing_evidence": missing_evidence,
        "source_result": result,
    }
