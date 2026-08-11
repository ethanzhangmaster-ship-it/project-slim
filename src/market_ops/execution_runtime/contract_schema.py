"""E10.1 Contract Schema — Schema version and validation for JSON exports.

Provides frozen contract identifiers and lightweight validation
rules so consumers can detect breaking changes.

No real platform API calls. No imports from E9.9.5 decision layer.
"""

from __future__ import annotations

from typing import Any

from market_ops.execution_runtime.schemas import ContractVersion


class SchemaValidator:
    """Lightweight validator for exported JSON contracts.

    Usage:
        validator = SchemaValidator()
        errors = validator.validate_execution(record_dict)
        assert len(errors) == 0
    """

    REQUIRED_EXECUTION_FIELDS = {
        "record_id", "task_id", "action_type", "final_status",
        "start_time", "end_time",
    }

    REQUIRED_PERFORMANCE_FIELDS = {
        "snapshot_id", "task_id", "impressions", "clicks",
        "spend", "revenue", "roas", "status",
    }

    REQUIRED_FEEDBACK_FIELDS = {
        "signal_id", "task_id", "feedback_type", "confidence",
        "recommendation", "metrics",
    }

    def validate_execution(self, data: dict[str, Any]) -> list[str]:
        """Validate an ExecutionRecord dict.

        Returns:
            List of missing-field error messages (empty if valid).
        """
        missing = self.REQUIRED_EXECUTION_FIELDS - set(data.keys())
        return [f"Missing required field: {f}" for f in missing]

    def validate_performance(self, data: dict[str, Any]) -> list[str]:
        """Validate a PerformanceSnapshot dict.

        Returns:
            List of missing-field error messages (empty if valid).
        """
        missing = self.REQUIRED_PERFORMANCE_FIELDS - set(data.keys())
        return [f"Missing required field: {f}" for f in missing]

    def validate_feedback(self, data: dict[str, Any]) -> list[str]:
        """Validate a LearningSignal dict.

        Returns:
            List of missing-field error messages (empty if valid).
        """
        missing = self.REQUIRED_FEEDBACK_FIELDS - set(data.keys())
        return [f"Missing required field: {f}" for f in missing]


__all__ = ["ContractVersion", "SchemaValidator"]
