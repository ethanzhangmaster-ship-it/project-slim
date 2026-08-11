"""E13.5 — Health Agent (Vitals Monitor).

The sensing brain of the Play Runtime. It reads an app's Vitals (crash rate,
ANR rate, optional D1 retention) through the ``PlayConnector`` (so the
three-tier gate is inherited — SIMULATE/SHADOW never write, PRODUCTION real
READ), scores them against a ``HealthPolicy``, and can halt a bad rollout.

It is the natural counterpart to the Release Agent: wire
``HealthAgent.read_vitals_dict`` as the Release Agent's ``metrics_provider``
and the staged rollout will automatically HOLD on missing data and HALT on a
violated gate.

Lean rule: pure Python, deterministic, JSONL audit, no LLM.
READ-only against the console (never mutates state); the only write it can
trigger is a RELEASE-radius halt, which is hard-gated by ``unlock_release()``
exactly like the Release Agent.

Recommendations:
  healthy  — every gate passes with margin
  watch    — a metric is within 80% of a threshold (eyes up, don't halt)
  halt     — a gate is violated (rollout should be stopped)
  no_data  — vitals unreadable / not yet populated
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from operation.publishing_factory.play_runtime.connector import PlayConnector
from operation.publishing_factory.play_runtime.health_audit import append as health_append
from operation.publishing_factory.play_runtime.models import (
    BlastRadius, GateStage, PlayResult,
)


# Provisioning of D1 retention is optional; default policy does not gate on it.
@dataclass
class HealthPolicy:
    """Tunable Vitals thresholds (rates are PERCENT, 0–100)."""
    max_crash_rate: float = 1.0        # % of users crashing
    max_anr_rate: float = 0.5          # % of users hitting ANR
    min_d1_retention: float = 0.0      # 0 == do not gate on retention
    watch_band: float = 0.8            # flag when metric >= threshold*band
    window_days: int = 7               # lookback window for the read


@dataclass
class HealthReport:
    """One health evaluation result for a package."""
    package_name: str
    recommendation: str           # healthy / watch / halt / no_data
    crash_rate: Optional[float]
    anr_rate: Optional[float]
    d1_retention: Optional[float]
    reasons: List[str] = field(default_factory=list)
    read_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "package_name": self.package_name,
            "recommendation": self.recommendation,
            "crash_rate": self.crash_rate,
            "anr_rate": self.anr_rate,
            "d1_retention": self.d1_retention,
            "reasons": list(self.reasons),
            "read_at": self.read_at,
        }


@dataclass
class ReleaseRiskScore:
    """E15.2 — quantified release risk for a package (0 = safe, 100 = on fire).

    Factors (each contributes to the total, capped at 100):
      * crash_rate vs policy.max_crash_rate  (up to 50 pts)
      * anr_rate   vs policy.max_anr_rate    (up to 30 pts)
      * missing data                          (flat 20 pts — flying blind)
    Levels: low (<25) / medium (25-49) / high (50-74) / critical (>=75)
    """
    package_name: str
    score: float
    level: str
    factors: Dict[str, float] = field(default_factory=dict)
    reasons: List[str] = field(default_factory=list)
    computed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "package_name": self.package_name,
            "score": self.score,
            "level": self.level,
            "factors": dict(self.factors),
            "reasons": list(self.reasons),
            "computed_at": self.computed_at,
        }


class HealthAgent:
    """Vitals monitor over a PlayConnector.

    ``vitals_provider`` lets callers inject the raw read (e.g. an offline
    cache or a test double). If omitted, the agent reads through the
    connector (``read_vitals`` → ``GooglePlayRealClient.get_vitals``).
    """

    def __init__(self,
                 connector: PlayConnector,
                 policy: Optional[HealthPolicy] = None,
                 vitals_provider: Optional[Callable[[str, int], Optional[Dict]]] = None):
        self.connector = connector
        self.policy = policy or HealthPolicy()
        self.vitals_provider = vitals_provider  # (pkg, window) -> dict | None

    # ------------------------------------------------------------------ #
    # vitals acquisition
    def read_vitals(self, package_name: str,
                    window_days: Optional[int] = None) -> Optional[Dict]:
        w = window_days or self.policy.window_days
        if self.vitals_provider is not None:
            return self.vitals_provider(package_name, w)
        res = self.connector.read_vitals(package_name, window_days=w)
        if not res.ok:
            return None
        return res.data or None

    def read_vitals_dict(self, package_name: str,
                         window_days: Optional[int] = None) -> Optional[Dict]:
        """Adapter for ``ReleaseAgent.metrics_provider``.

        Returns ``{"crash_rate", "anr_rate", "d1_retention"}`` (the exact keys
        the Release Agent's health gate consumes) or ``None`` when unreadable.
        """
        v = self.read_vitals(package_name, window_days=window_days)
        if not v:
            return None
        return {
            "crash_rate": v.get("crash_rate"),
            "anr_rate": v.get("anr_rate"),
            "d1_retention": v.get("d1_retention"),
        }

    # ------------------------------------------------------------------ #
    # scoring
    def _score(self, crash: Optional[float], anr: Optional[float],
               d1: Optional[float]) -> tuple:
        """(recommendation, reasons[]) given raw values."""
        reasons: List[str] = []
        if crash is None and anr is None and d1 is None:
            return "no_data", ["vitals unreadable / not populated"]
        if crash is not None:
            if crash > self.policy.max_crash_rate:
                return "halt", [
                    f"crash_rate {crash:.2f}% > {self.policy.max_crash_rate:.2f}%"]
            if crash >= self.policy.max_crash_rate * self.policy.watch_band:
                reasons.append(
                    f"crash_rate {crash:.2f}% near limit "
                    f"({self.policy.max_crash_rate:.2f}%)")
        if anr is not None:
            if anr > self.policy.max_anr_rate:
                return "halt", [
                    f"anr_rate {anr:.2f}% > {self.policy.max_anr_rate:.2f}%"]
            if anr >= self.policy.max_anr_rate * self.policy.watch_band:
                reasons.append(
                    f"anr_rate {anr:.2f}% near limit "
                    f"({self.policy.max_anr_rate:.2f}%)")
        if self.policy.min_d1_retention > 0 and d1 is not None:
            if d1 < self.policy.min_d1_retention:
                return "halt", [
                    f"d1_retention {d1:.3f} < "
                    f"{self.policy.min_d1_retention:.3f}"]
        if reasons:
            return "watch", reasons
        return "healthy", ["all gates passed"]

    # ------------------------------------------------------------------ #
    # evaluate (no write)
    def evaluate(self, package_name: str,
                 window_days: Optional[int] = None) -> HealthReport:
        v = self.read_vitals(package_name, window_days=window_days)
        crash = float(v.get("crash_rate")) if v and v.get("crash_rate") is not None else None
        anr = float(v.get("anr_rate")) if v and v.get("anr_rate") is not None else None
        d1 = float(v.get("d1_retention")) if v and v.get("d1_retention") is not None else None
        rec, reasons = self._score(crash, anr, d1)
        return HealthReport(
            package_name=package_name, recommendation=rec,
            crash_rate=crash, anr_rate=anr, d1_retention=d1,
            reasons=reasons)

    # ------------------------------------------------------------------ #
    # E15.2 release risk scoring
    def evaluate_release_risk(self, package_name: str,
                              window_days: Optional[int] = None,
                              snapshot: Optional[Any] = None) -> ReleaseRiskScore:
        """Quantify release risk 0-100 for ``package_name``.

        ``snapshot`` (a PlayRealitySnapshot) can be supplied to score from
        already-collected Reality data without another API read.
        """
        if snapshot is not None:
            crash = getattr(snapshot, "crash_rate", None)
            anr = getattr(snapshot, "anr_rate", None)
        else:
            v = self.read_vitals(package_name, window_days=window_days) or {}
            crash = v.get("crash_rate")
            anr = v.get("anr_rate")

        factors: Dict[str, float] = {}
        reasons: List[str] = []
        score = 0.0

        if crash is None and anr is None:
            factors["missing_data"] = 20.0
            reasons.append("vitals unavailable — flying blind")
            score += 20.0
        else:
            if crash is not None:
                crash = float(crash)
                # ratio 1.0 == at threshold -> 25 pts; 2x threshold -> 50 pts cap
                ratio = crash / self.policy.max_crash_rate if self.policy.max_crash_rate else 0.0
                pts = min(50.0, ratio * 25.0)
                factors["crash"] = round(pts, 2)
                score += pts
                if ratio >= 1.0:
                    reasons.append(
                        f"crash_rate {crash:.2f}% >= limit "
                        f"{self.policy.max_crash_rate:.2f}%")
            else:
                factors["crash_missing"] = 10.0
                reasons.append("crash_rate unavailable")
                score += 10.0
            if anr is not None:
                anr = float(anr)
                ratio = anr / self.policy.max_anr_rate if self.policy.max_anr_rate else 0.0
                pts = min(30.0, ratio * 15.0)
                factors["anr"] = round(pts, 2)
                score += pts
                if ratio >= 1.0:
                    reasons.append(
                        f"anr_rate {anr:.2f}% >= limit "
                        f"{self.policy.max_anr_rate:.2f}%")
            else:
                factors["anr_missing"] = 10.0
                reasons.append("anr_rate unavailable")
                score += 10.0

        score = round(min(100.0, score), 2)
        if score >= 75:
            level = "critical"
        elif score >= 50:
            level = "high"
        elif score >= 25:
            level = "medium"
        else:
            level = "low"
        if not reasons:
            reasons.append("all stability signals within limits")

        return ReleaseRiskScore(
            package_name=package_name, score=score, level=level,
            factors=factors, reasons=reasons)

    # ------------------------------------------------------------------ #
    # actions
    def halt_if_critical(self, package_name: str, *,
                         apply: bool = False) -> PlayResult:
        """Halt the rollout ONLY when the current vitals violate a gate.

        This is a RELEASE-radius op, so even with ``apply=True`` the
        connector refuses unless ``unlock_release()`` has been called — the
        same hard lock as the Release Agent. Returns the connector result.
        """
        report = self.evaluate(package_name)
        if report.recommendation != "halt":
            return PlayResult(
                op="halt_rollout", package_name=package_name,
                radius=BlastRadius.RELEASE, stage=GateStage.BLOCKED,
                real_api_called=False, ok=False,
                detail=f"refused halt: {report.recommendation} "
                       f"({'; '.join(report.reasons)})")
        return self.connector.halt_rollout(package_name, "production", apply=apply)

    # ------------------------------------------------------------------ #
    # daily sweep
    def run_daily(self, packages: List[str], *,
                  apply: bool = False,
                  window_days: Optional[int] = None) -> List[Dict[str, Any]]:
        """Evaluate every package; halt the critical ones when ``apply``.

        Each evaluation is persisted to the health JSONL audit so the morning
        briefing can show the latest board without re-calling the API. The
        connector's own gate still enforces the RELEASE unlock, so even
        ``apply=True`` is safe against an unlocked connector.
        """
        out: List[Dict[str, Any]] = []
        for pkg in packages:
            report = self.evaluate(pkg, window_days=window_days)
            health_append(report)
            executed: Optional[PlayResult] = None
            if apply and report.recommendation == "halt":
                executed = self.halt_if_critical(pkg, apply=True)
            out.append({
                **report.to_dict(),
                "action_taken": (
                    "halted" if (executed and executed.ok)
                    else "halt_failed" if executed is not None
                    else report.recommendation),
                "executed": (executed.to_dict() if executed else None),
            })
        return out


__all__ = ["HealthAgent", "HealthPolicy", "HealthReport", "ReleaseRiskScore"]
