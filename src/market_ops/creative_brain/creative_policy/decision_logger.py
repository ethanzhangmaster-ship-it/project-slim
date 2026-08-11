"""V4.3 Decision Logger — audit trail for all policy decisions.

Records:
  - Why KILL?
  - Why GENERATE?
  - Why EXPLORE?
  - Policy version at time of decision
  - Risk overrides

All logs saved for future learning and audit.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .schemas import DecisionLog, PolicyAction


class DecisionLogger:
    """Log all policy decisions for audit and learning."""

    def __init__(self) -> None:
        self._logs: list[DecisionLog] = []
        self._daily_count: dict[str, int] = {}  # action → count

    def log(self, creative_id: str, action: PolicyAction,
            reason: str, evidence: dict[str, Any],
            policy_version: str = "",
            overridden_by_risk: bool = False,
            overridden_reason: str = "") -> DecisionLog:
        """Log a single decision."""
        log_entry = DecisionLog(
            timestamp=datetime.now().isoformat(),
            creative_id=creative_id,
            action=action,
            reason=reason,
            evidence=evidence,
            policy_version=policy_version,
            overridden_by_risk=overridden_by_risk,
            overridden_reason=overridden_reason,
        )
        self._logs.append(log_entry)
        action_key = action.value
        self._daily_count[action_key] = self._daily_count.get(action_key, 0) + 1
        return log_entry

    def get_logs(self, action: PolicyAction | None = None,
                 limit: int = 100) -> list[DecisionLog]:
        """Get recent logs, optionally filtered by action."""
        if action:
            return [l for l in self._logs[-limit:] if l.action == action]
        return self._logs[-limit:]

    def get_kill_reasons(self) -> list[dict[str, Any]]:
        """Get all KILL decisions with reasons."""
        kill_logs = [l for l in self._logs if l.action == PolicyAction.KILL]
        return [
            {
                "creative_id": l.creative_id,
                "reason": l.reason,
                "timestamp": l.timestamp,
                "overridden_by_risk": l.overridden_by_risk,
            }
            for l in kill_logs
        ]

    def get_daily_summary(self) -> dict[str, Any]:
        """Get daily decision summary."""
        return {
            "total_decisions": len(self._logs),
            "action_counts": dict(self._daily_count),
            "generate_count": self._daily_count.get("generate", 0),
            "retest_count": self._daily_count.get("retest", 0),
            "adapt_count": self._daily_count.get("adapt", 0),
            "kill_count": self._daily_count.get("kill", 0),
            "risk_overrides": sum(
                1 for l in self._logs if l.overridden_by_risk
            ),
        }

    def get_all_logs(self) -> list[DecisionLog]:
        """Get all logs (for persistence)."""
        return list(self._logs)

    def reset_daily(self) -> None:
        """Reset daily counters."""
        self._daily_count = {}

    def export_logs(self) -> list[dict[str, Any]]:
        """Export all logs as dicts."""
        return [l.to_dict() for l in self._logs]