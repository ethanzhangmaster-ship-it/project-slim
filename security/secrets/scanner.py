"""
EP0.1.2 — SecretScanner: detect hardcoded secrets in source code.

Scans Python files for patterns like:
    API_KEY = "sk-..."
    TOKEN = "ghp_..."
    PASSWORD = "..."
    PRIVATE_KEY = "-----BEGIN..."
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass
class SecretFinding:
    path: str
    line: int
    match: str
    severity: str  # "high" | "medium" | "low"


@dataclass
class ScanReport:
    findings: List[SecretFinding] = field(default_factory=list)
    files_scanned: int = 0
    total_lines: int = 0

    @property
    def is_clean(self) -> bool:
        return len(self.findings) == 0

    def to_markdown(self) -> str:
        if self.is_clean:
            return "# Security Scan\n\n✅ No hardcoded secrets detected.\n"

        lines = ["# Security Scan Report", ""]
        lines.append(f"❌ **{len(self.findings)} issue(s)** found in "
                     f"{self.files_scanned} files ({self.total_lines} lines).\n")
        for f in self.findings:
            lines.append(
                f"- `{f.path}:{f.line}` [{f.severity}] `...{f.match[-30:]}`"
            )
        return "\n".join(lines)


# Patterns that indicate potential hardcoded secrets
_SECRET_PATTERNS: list[tuple[str, str, str]] = [
    # (regex, name, severity)
    (r'(?i)(api[_-]?key|apikey)\s*[:=]\s*["\'][A-Za-z0-9_\-]{20,}', "API_KEY assignment", "high"),
    (r'(?i)(secret|token|password|passwd)\s*[:=]\s*["\'][^\s]{8,}', "TOKEN/PASSWORD", "high"),
    (r'(?i)private[_-]?key\s*[:=]\s*["\']-----BEGIN', "PRIVATE_KEY", "high"),
    (r'(?i)bearer\s+["\'][A-Za-z0-9_\-\.]{20,}', "Bearer token inline", "high"),
    (r'(?i)(access[_-]?token|auth[_-]?token)\s*[:=]\s*["\'][A-Za-z0-9_\-\.]{16,}', "Access token", "high"),
    (r'(?i)(client[_-]?secret)\s*[:=]\s*["\'][A-Za-z0-9_\-]{16,}', "Client secret", "high"),
    (r'(?i)(sdk[_-]?key)\s*[:=]\s*["\'][A-Za-z0-9_\-]{16,}', "SDK key", "medium"),
    (r'(?i)(webhook[_-]?url)\s*[:=]\s*["\']https?://[^\s]{20,}', "Webhook URL", "medium"),
    (r'(?i)(connection[_-]?string)\s*[:=]\s*["\']', "Connection string", "high"),
    (r'(?i)(app[_-]?secret)\s*[:=]\s*["\'][A-Za-z0-9_\-]{16,}', "App secret", "high"),
]

# Files / directories to skip
_SKIP_GLOBS = [
    "*.pyc",
    "__pycache__",
    ".git",
    ".pytest_cache",
    ".pytest_tmp",
    ".workbuddy",
    "venv",
    "envs",
    ".venv",
    "node_modules",
    "*.egg-info",
]

# Fake / placeholder values to ignore
_BENIGN_VALUES = [
    "YOUR_",
    "your_",
    "xxx",
    "XXX",
    "AAA_",
    "BBB_",
    "placeholder",
    "example",
    "change_me",
    "changeme",
    "REPLACE_",
    "dummy",
    "test_key",
    "fake",
    "sk-test",
    "ghp_example",
]


class SecretScanner:
    """Scan Python files for hardcoded secrets."""

    def scan(self, *directories: str) -> ScanReport:
        report = ScanReport()

        for directory in directories:
            root = Path(directory)
            if not root.is_dir():
                continue

            for pyfile in root.rglob("*.py"):
                if self._should_skip(pyfile):
                    continue

                report.files_scanned += 1
                try:
                    lines = pyfile.read_text(encoding="utf-8", errors="replace").split("\n")
                except Exception:
                    continue

                report.total_lines += len(lines)

                for lineno, raw_line in enumerate(lines, start=1):
                    line = raw_line.strip()
                    if not line or line.startswith("#"):
                        continue

                    for pattern, name, severity in _SECRET_PATTERNS:
                        m = re.search(pattern, line)
                        if m:
                            if self._is_benign(m.group(0)):
                                continue
                            report.findings.append(
                                SecretFinding(
                                    path=str(pyfile.relative_to(root)),
                                    line=lineno,
                                    match=m.group(0),
                                    severity=severity,
                                )
                            )

        return report

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _should_skip(path: Path) -> bool:
        parts = path.parts
        for part in parts:
            if part in ("__pycache__", ".git", ".pytest_cache", ".pytest_tmp", ".workbuddy", "venv", ".venv", "node_modules", "envs"):
                return True
        return False

    @staticmethod
    def _is_benign(text: str) -> bool:
        lower = text.lower()
        # Skip lines that contain common placeholder markers
        for marker in _BENIGN_VALUES:
            if marker.lower() in lower:
                return True
        return False
