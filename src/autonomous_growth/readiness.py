from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping, Optional

from .models import AgentConfig, ReadinessReport


class ProductionReadinessGate:
    """Deterministic startup gate. Production is fail-closed."""

    def __init__(self, root: str = ".", environ: Optional[Mapping[str, str]] = None):
        self.root = Path(root)
        self.environ = dict(os.environ if environ is None else environ)
        if environ is None:
            self.environ.update({k: v for k, v in self._load_env_file().items()
                                 if k not in self.environ})

    def check(self, config: AgentConfig) -> ReadinessReport:
        blockers = list(config.validate())
        checks = {
            "project_root": (self.root / "pyproject.toml").is_file(),
            "tests_present": (self.root / "tests").is_dir(),
            "data_writable": self._writable(self.root / "data"),
            "logs_writable": self._writable(self.root / "logs"),
            "dry_run_default": config.mode != "production",
        }
        for name, passed in checks.items():
            if not passed and name != "dry_run_default":
                blockers.append(f"readiness check failed: {name}")
        missing = [name for name in config.required_env
                   if self._missing_or_placeholder(self.environ.get(name, ""))]
        if config.mode == "production" and missing:
            blockers.append("missing production environment: " + ", ".join(sorted(missing)))
        if config.mode == "production" and not config.require_approval_in_production:
            blockers.append("production requires approval gate")
        if config.mode == "production":
            for name in ("PLAY_SERVICE_ACCOUNT_JSON", "APPSTORE_P8_PATH"):
                value = self.environ.get(name, "")
                if name in config.required_env and value:
                    path = Path(value)
                    if not path.is_absolute(): path = self.root / path
                    if not path.is_file(): blockers.append(f"credential file not found: {name}")
        warnings = [] if config.required_env else ["no provider credentials declared"]
        return ReadinessReport(not blockers, checks, blockers, warnings, False)

    def _load_env_file(self) -> dict:
        out = {}
        path = self.root / ".env"
        if not path.is_file(): return out
        try:
            for raw in path.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line: continue
                key, value = line.split("=", 1)
                out[key.strip()] = value.strip().strip('"').strip("'")
        except OSError:
            return {}
        return out

    @staticmethod
    def _missing_or_placeholder(value: str) -> bool:
        text = str(value or "").strip().lower()
        return not text or text.startswith("your_") or text in {"changeme", "xxx"}

    @staticmethod
    def _writable(path: Path) -> bool:
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".launchforge_write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return True
        except OSError:
            return False
