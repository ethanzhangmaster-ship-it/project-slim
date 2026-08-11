"""E10.1 Export Service — JSON contract export for downstream consumers.

Transforms ExecutionRecord, PerformanceSnapshot, and LearningSignal
into version-tagged JSON payloads suitable for E9.9.5 Learning Layer
or external API gateways.

No real platform API calls. No imports from E9.9.5 decision layer.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from market_ops.execution_runtime.schemas import (
    ExecutionRecord,
    PerformanceSnapshot,
    LearningSignal,
    ContractVersion,
)
from market_ops.execution_runtime.contract_schema import SchemaValidator


class ExportService:
    """Export runtime artifacts as versioned JSON contracts.

    Usage:
        service = ExportService(output_dir="output/execution_runtime")
        payload = service.export_execution(record)
        service.write(payload, "execution_record.json")
    """

    def __init__(
        self,
        output_dir: str | Path = "output/execution_runtime",
        validator: SchemaValidator | None = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.validator = validator or SchemaValidator()
        self._ensure_dir()

    def export_execution(self, record: ExecutionRecord) -> dict[str, Any]:
        """Export an ExecutionRecord as a versioned JSON payload.

        Args:
            record: The execution record to export.

        Returns:
            Dict with schema version and record data.
        """
        data = record.to_dict()
        errors = self.validator.validate_execution(data)
        if errors:
            return self._error_payload(errors)

        return {
            "schema": ContractVersion.EXECUTION,
            "record": data,
        }

    def export_snapshot(self, snapshot: PerformanceSnapshot) -> dict[str, Any]:
        """Export a PerformanceSnapshot as a versioned JSON payload.

        Args:
            snapshot: The performance snapshot to export.

        Returns:
            Dict with schema version and snapshot data.
        """
        data = snapshot.to_dict()
        errors = self.validator.validate_performance(data)
        if errors:
            return self._error_payload(errors)

        return {
            "schema": ContractVersion.PERFORMANCE,
            "snapshot": data,
        }

    def export_feedback(self, signal: LearningSignal) -> dict[str, Any]:
        """Export a LearningSignal as a versioned JSON payload.

        Args:
            signal: The learning signal to export.

        Returns:
            Dict with schema version and signal data.
        """
        data = signal.to_dict()
        errors = self.validator.validate_feedback(data)
        if errors:
            return self._error_payload(errors)

        return {
            "schema": ContractVersion.FEEDBACK,
            "signal": data,
        }

    def write(self, payload: dict[str, Any], filename: str) -> Path:
        """Write a JSON payload to the output directory.

        Args:
            payload: The data to serialize.
            filename: Target file name.

        Returns:
            Path to the written file.
        """
        self._ensure_dir()
        path = self.output_dir / filename
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    def _ensure_dir(self) -> None:
        """Create output directory if it does not exist."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _error_payload(errors: list[str]) -> dict[str, Any]:
        """Build an error payload for validation failures."""
        return {
            "schema": "error",
            "errors": errors,
        }
