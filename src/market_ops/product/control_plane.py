from __future__ import annotations

import csv
import importlib.util
import json
import os
import platform
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .closed_loop import GrowthLoop
from .platform_write_readiness import facebook_write_readiness


@dataclass(slots=True)
class Check:
    name: str
    status: str
    message: str
    required: bool = True


@dataclass(slots=True)
class SystemSnapshot:
    generated_at: str
    status: str
    version: str
    mode: str
    offline_mode: bool = False
    checks: list[Check] = field(default_factory=list)
    capabilities: dict[str, str] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ControlPlane:
    """Stable operator view over readiness, loop state and safety gates."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or Path.cwd()).resolve()
        load_dotenv(self.root / ".env", override=False)
        self.output_dir = self.root / "output" / "active"
        self.loop = GrowthLoop(self.output_dir / "growth_loop.sqlite3")

    def snapshot(self) -> SystemSnapshot:
        mode, offline = self._mode(), self._offline_mode()
        write_gate = facebook_write_readiness(self.output_dir / "campaign_bindings.json")
        checks = [
            self._python_check(), self._path_check("source", self.root / "src" / "market_ops"),
            self._path_check("output", self.output_dir, create=True), self._module_check("dotenv", "configuration"),
            self._module_check("requests", "platform connectors"), self._module_check("cv2", "visual intelligence"),
            *self._configuration_checks(mode), self._write_gate_check(write_gate),
        ]
        status = "blocked" if any(c.required and c.status == "fail" for c in checks) else ("degraded" if any(c.status == "warn" for c in checks) else "ready")
        publish = self._publish_capability(write_gate)
        return SystemSnapshot(
            generated_at=datetime.now(timezone.utc).isoformat(), status=status, version="1.0.0", mode=mode, offline_mode=offline, checks=checks,
            capabilities={"observe": "ready", "recommend": "ready" if status != "blocked" else "blocked", "generate": self._capability("OPENAI_API_KEY", "LOVART_API_KEY"), "publish": publish, "notify": self._capability("FEISHU_BOT_WEBHOOK", "FEISHU_MARKET_WEBHOOK")},
            metrics={**self._metrics(), "platform_write": write_gate.to_dict()},
        )

    def loop_overview(self) -> dict[str, Any]: return self.loop.overview()
    def cycle(self, cycle_id: str) -> dict[str, Any] | None: return self.loop.cycle(cycle_id)

    def write_snapshot(self) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        target = self.output_dir / "system_snapshot.json"
        target.write_text(json.dumps(self.snapshot().to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return target

    def run_safe_command(self, command: str, report_date: str = "latest") -> int:
        allowed = {"sync": ["sync-feishu-sources", "--print-summary"], "preview": ["card-preview", "--report-date", report_date], "audit": ["report-audit", "--report-date", report_date], "health": ["health-check", "--report-date", report_date], "closure": ["closure-status", "--report-date", report_date]}
        if command not in allowed: raise ValueError(f"Unsupported safe command: {command}")
        return subprocess.run([sys.executable, "-m", "market_ops.cli", *allowed[command]], cwd=self.root, check=False).returncode

    @staticmethod
    def _python_check() -> Check:
        ok = sys.version_info >= (3, 10)
        return Check("python", "pass" if ok else "fail", f"{platform.python_implementation()} {platform.python_version()}")

    @staticmethod
    def _path_check(name: str, path: Path, create: bool = False) -> Check:
        if create:
            try: path.mkdir(parents=True, exist_ok=True)
            except OSError as exc: return Check(name, "fail", str(exc))
        return Check(name, "pass" if path.exists() else "fail", str(path))

    @staticmethod
    def _module_check(module: str, label: str) -> Check:
        found = importlib.util.find_spec(module) is not None
        return Check(label, "pass" if found else "fail", f"{module} {'available' if found else 'missing'}")

    @staticmethod
    def _capability(*variables: str) -> str: return "configured" if any(os.getenv(name) for name in variables) else "not_configured"

    @staticmethod
    def _publish_capability(write_gate: Any) -> str:
        token = os.getenv("META_ACCESS_TOKEN") or os.getenv("FACEBOOK_ACCESS_TOKEN")
        account = os.getenv("META_AD_ACCOUNT_ID") or os.getenv("FACEBOOK_AD_ACCOUNT_ID")
        if not token:
            return "not_configured"
        if not account:
            return "configured"
        return "ready" if write_gate.ready else "approval_required"

    @staticmethod
    def _mode() -> str:
        if ControlPlane._offline_mode(): return "offline"
        if os.getenv("ADS_PERFORMANCE_CSV"): return "local"
        if os.getenv("FEISHU_APP_ID"): return "connected"
        return "unconfigured"

    @staticmethod
    def _offline_mode() -> bool:
        return all(not os.environ.get(name) for name in ("OPENAI_API_KEY", "LOVART_API_KEY", "META_ACCESS_TOKEN", "FEISHU_BOT_WEBHOOK", "FEISHU_MARKET_WEBHOOK", "GOOGLE_ADS_CLIENT_ID"))

    @staticmethod
    def _write_gate_check(gate: Any) -> Check:
        return Check("Meta write gate", "pass" if gate.ready else "warn", "ready" if gate.ready else "; ".join(gate.reasons), False)

    def _configuration_checks(self, mode: str) -> list[Check]:
        if mode == "local":
            source = Path(os.getenv("ADS_PERFORMANCE_CSV", ""))
            if not source.is_absolute():
                source = self.root / source
            if not source.exists(): return [Check("data source", "warn", str(source), False)]
            max_age = int(os.getenv("MARKET_OPS_MAX_DATA_AGE_HOURS", "48"))
            age = (datetime.now(timezone.utc) - datetime.fromtimestamp(source.stat().st_mtime, timezone.utc)).total_seconds() / 3600
            latest_data_date = max((str(row.get("date") or "") for row in csv.DictReader(source.open(encoding="utf-8-sig"))), default="")
            coverage_age = (datetime.now(timezone.utc).date() - datetime.fromisoformat(latest_data_date).date()).days if latest_data_date else None
            status = "pass" if age <= max_age and (coverage_age is None or coverage_age * 24 <= max_age) else "warn"
            coverage = f"; coverage ends {latest_data_date} ({coverage_age}d old)" if latest_data_date else ""
            return [Check("data freshness", status, f"{source.name}: refreshed {age:.1f}h ago (limit {max_age}h){coverage}", False)]
        if mode == "connected":
            secret = bool(os.getenv("FEISHU_APP_SECRET"))
            return [Check("Feishu credentials", "pass" if secret else "fail", "configured" if secret else "secret missing")]
        return [Check("data source", "warn", "No local or connected data source selected", False)]

    def _metrics(self) -> dict[str, Any]:
        reports = list(self.output_dir.glob("*.md")) if self.output_dir.exists() else []
        latest = max((p.stat().st_mtime for p in reports), default=None)
        return {"active_reports": len(reports), "latest_report_at": datetime.fromtimestamp(latest, timezone.utc).isoformat() if latest else None, "loop": self.loop_overview()}

    def diagnostic_report(self) -> dict[str, Any]:
        names = {"OPENAI_API_KEY": "creative generation", "LOVART_API_KEY": "creative generation", "META_ACCESS_TOKEN": "ad publishing", "FEISHU_BOT_WEBHOOK": "notifications", "FEISHU_MARKET_WEBHOOK": "market notifications", "GOOGLE_ADS_CLIENT_ID": "Google Ads integration"}
        missing = [name for name in names if not os.environ.get(name)]
        return {"mode": self._mode(), "offline_mode": self._offline_mode(), "missing_credentials": missing, "blocked_capabilities": list(dict.fromkeys(names[name] for name in missing)), "recommendations": [f"Set {name} to enable {names[name]}" for name in missing]}
