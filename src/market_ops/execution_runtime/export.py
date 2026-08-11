"""E10.1 Execution Runtime — Export Module.

Outputs:
  1. execution_tasks.json     — all execution tasks
  2. execution_results.json   — task execution outcomes
  3. approval_requests.json   — human approval records
  4. execution_events.json    — audit trail event log
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_ops.execution_runtime.schemas import (
    ExecutionTask, ExecutionResult, ApprovalRequest, ExecutionEvent,
)


class ExecutionExporter:
    """Standalone export module for E10.1 Execution Runtime outputs.

    Usage:
        exporter = ExecutionExporter(output_dir="output/execution_runtime")
        paths = exporter.export_all(tasks, results, approvals, events)
    """

    def __init__(
        self,
        output_dir: str | Path = "output/execution_runtime",
    ) -> None:
        self._output_dir = Path(output_dir)

    def ensure_output_dir(self) -> Path:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        return self._output_dir

    # ── File 1: execution_tasks.json ───────────────────────

    def export_tasks(
        self,
        tasks: list[ExecutionTask],
        filename: str = "execution_tasks.json",
    ) -> Path:
        """Export all execution tasks."""
        path = self._output_dir / filename
        self.ensure_output_dir()

        by_status: dict[str, int] = {}
        for t in tasks:
            by_status[t.status] = by_status.get(t.status, 0) + 1

        data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_tasks": len(tasks),
            "by_status": by_status,
            "tasks": [t.to_dict() for t in tasks],
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path

    # ── File 2: execution_results.json ─────────────────────

    def export_results(
        self,
        results: list[ExecutionResult],
        filename: str = "execution_results.json",
    ) -> Path:
        """Export execution results."""
        path = self._output_dir / filename
        self.ensure_output_dir()

        succeeded = sum(1 for r in results if r.status == "COMPLETED")
        failed = sum(1 for r in results if r.status == "FAILED")

        data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_results": len(results),
            "succeeded": succeeded,
            "failed": failed,
            "results": [r.to_dict() for r in results],
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path

    # ── File 3: approval_requests.json ─────────────────────

    def export_approvals(
        self,
        approvals: list[ApprovalRequest],
        filename: str = "approval_requests.json",
    ) -> Path:
        """Export approval requests."""
        path = self._output_dir / filename
        self.ensure_output_dir()

        pending = sum(1 for a in approvals if a.status == "PENDING")
        approved = sum(1 for a in approvals if a.status == "APPROVED")
        rejected = sum(1 for a in approvals if a.status == "REJECTED")

        data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_requests": len(approvals),
            "by_status": {
                "PENDING": pending,
                "APPROVED": approved,
                "REJECTED": rejected,
            },
            "requests": [a.to_dict() for a in approvals],
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path

    # ── File 4: execution_events.json ──────────────────────

    def export_events(
        self,
        events: list[ExecutionEvent],
        filename: str = "execution_events.json",
    ) -> Path:
        """Export execution events (audit trail)."""
        path = self._output_dir / filename
        self.ensure_output_dir()

        by_type: dict[str, int] = {}
        for e in events:
            by_type[e.event_type] = by_type.get(e.event_type, 0) + 1

        data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_events": len(events),
            "by_type": by_type,
            "events": [e.to_dict() for e in events],
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path

    # ── Batch Export ───────────────────────────────────────

    def export_all(
        self,
        tasks: list[ExecutionTask],
        results: list[ExecutionResult],
        approvals: list[ApprovalRequest],
        events: list[ExecutionEvent],
    ) -> dict[str, str]:
        """Export all 4 output files.

        Returns:
            {file_category: full_path}
        """
        return {
            "execution_tasks": str(self.export_tasks(tasks)),
            "execution_results": str(self.export_results(results)),
            "approval_requests": str(self.export_approvals(approvals)),
            "execution_events": str(self.export_events(events)),
        }

    # ── Summary ────────────────────────────────────────────

    def get_export_summary(self, paths: dict[str, str]) -> dict[str, Any]:
        """Get summary of exported files with sizes."""
        summary = {}
        for category, path_str in paths.items():
            p = Path(path_str)
            if p.exists():
                summary[category] = {
                    "path": path_str,
                    "size_kb": round(p.stat().st_size / 1024, 1),
                }
            else:
                summary[category] = {"path": path_str, "status": "missing"}
        return summary