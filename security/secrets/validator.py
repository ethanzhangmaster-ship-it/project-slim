"""
EP0.1.3 — EnvironmentValidator: startup gate for required env vars.

Before the Growth OS boots, this MUST pass or the system refuses to start.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class EnvCheckResult:
    key: str
    present: bool
    description: str = ""


@dataclass
class EnvValidationReport:
    results: List[EnvCheckResult] = field(default_factory=list)

    @property
    def all_present(self) -> bool:
        return all(r.present for r in self.results)

    @property
    def missing(self) -> List[str]:
        return [r.key for r in self.results if not r.present]

    def to_lines(self) -> List[str]:
        lines = ["Environment Validation:"]
        for r in self.results:
            status = "✓" if r.present else "✗"
            desc = f" — {r.description}" if r.description else ""
            lines.append(f"  [{status}] {r.key}{desc}")
        return lines


class EnvironmentValidator:
    """Startup env-var check gate.

    Usage::

        ev = EnvironmentValidator()
        ev.require("META_TOKEN", "Meta Ads API access token")
        ev.require("ADJUST_TOKEN", "Adjust attribution API key")
        ev.require("PLAY_SERVICE_ACCOUNT", "Google Play service account JSON path")
        report = ev.validate()
        if not report.all_present:
            raise SystemExit("Missing required env vars")
    """

    def __init__(self, secret_manager=None):
        self._secret_manager = secret_manager
        self._required: List[tuple[str, str]] = []

    def require(self, key: str, description: str = "") -> None:
        """Declare a required env var."""
        self._required.append((key, description))

    def validate(self) -> EnvValidationReport:
        report = EnvValidationReport()
        for key, desc in self._required:
            if self._secret_manager:
                present = self._secret_manager.exists(key)
            else:
                import os
                present = key in os.environ and os.environ[key] != ""
            report.results.append(
                EnvCheckResult(key=key, present=present, description=desc)
            )
        return report

    def validate_or_exit(self) -> EnvValidationReport:
        report = self.validate()
        if not report.all_present:
            for line in report.to_lines():
                print(line)
            print(f"\n❌ Missing {len(report.missing)} required env vars. Aborting.")
            raise SystemExit(1)
        return report
