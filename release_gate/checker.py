"""
EP0.4 — Regression Gate: merge-gate checks.

Before any merge/release, this gate must be GREEN.
Runs: pytest → security scan → verdict.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class GateStatus(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


@dataclass
class GateReport:
    status: GateStatus = GateStatus.RED
    checks: list[dict] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        lines = ["# Regression Gate", ""]
        lines.append(f"**Status**: `{self.status.value}`\n")
        for check in self.checks:
            icon = "✅" if check["passed"] else "❌"
            lines.append(f"{icon} **{check['name']}**: {check['detail']}")
        if self.messages:
            lines.append("\n---\n")
            for msg in self.messages:
                lines.append(f"- {msg}")
        return "\n".join(lines)


class RegressionGate:
    """Pre-merge / pre-release quality gate.

    Usage::

        gate = RegressionGate(project_root=".")
        report = gate.check()
        if report.status != GateStatus.GREEN:
            sys.exit(1)
    """

    def __init__(self, project_root: str = "."):
        self.root = Path(project_root)

    def check(self) -> GateReport:
        report = GateReport()

        # Check 1: pytest
        ok, detail = self._run_pytest()
        report.checks.append({"name": "pytest", "passed": ok, "detail": detail})

        # Check 2: security scan
        ok2, detail2 = self._run_security_scan()
        report.checks.append({"name": "security_scan", "passed": ok2, "detail": detail2})

        passed = sum(1 for c in report.checks if c["passed"])
        total = len(report.checks)

        if passed == total:
            report.status = GateStatus.GREEN
        elif passed >= total - 1:
            report.status = GateStatus.YELLOW
        else:
            report.status = GateStatus.RED

        return report

    def _run_pytest(self) -> tuple[bool, str]:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=line"],
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=300,
            )
            ok = result.returncode == 0
            last_line = result.stdout.strip().split("\n")[-1] if result.stdout.strip() else "no output"
            return ok, last_line[:120]
        except Exception as e:
            return False, str(e)[:120]

    def _run_security_scan(self) -> tuple[bool, str]:
        try:
            result = subprocess.run(
                [
                    sys.executable, "-c",
                    "from security.secrets.scanner import SecretScanner; "
                    "r = SecretScanner().scan('src', 'operation', 'monetization'); "
                    "print('clean' if r.is_clean else f'{len(r.findings)} finding(s)')",
                ],
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=60,
            )
            ok = result.returncode == 0 and "clean" in result.stdout
            detail = result.stdout.strip()[:120] or result.stderr.strip()[:120]
            return ok, detail
        except Exception as e:
            return False, str(e)[:120]


def gate_check() -> GateReport:
    """Convenience: run gate from current directory."""
    return RegressionGate().check()
