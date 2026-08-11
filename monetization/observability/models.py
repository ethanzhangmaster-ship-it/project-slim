"""
E14.5 — Observability data contracts (Lean, stdlib-only)
========================================================

Pure dataclasses + stdlib. No DB, no web framework, no external service.
Every object here serialises to a flat dict so it can be streamed as JSONL
into Grafana / Datadog / CloudWatch / Loki later without re-parsing.

Five modules consume these:
  * health.py   -> HealthSnapshot / FleetHealthReport
  * explain.py  -> DecisionTrace
  * alerts.py   -> (reuses runtime Alert) + alert rules
  * report.py   -> DailyReport (+ 4 SubReports)
  * export.py   -> MetricsBundle
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# Health vocabulary
# --------------------------------------------------------------------------- #
HEALTH_HEALTHY = "healthy"
HEALTH_DEGRADED = "degraded"
HEALTH_UNHEALTHY = "unhealthy"
HEALTH_ISOLATED = "isolated"          # crash-looped / removed from fleet

RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"


@dataclass
class HealthSnapshot:
    """Per-game health, the smallest unit the operator reads."""
    game_id: str
    status: str                        # HEALTH_* vocabulary
    risk: str                          # RISK_* vocabulary
    score: float                       # 0..100 composite
    cycle_success_rate: float = 0.0
    failure_rate: float = 0.0
    rollback_rate: float = 0.0
    latency_ms: float = 0.0
    provider_health: float = 100.0    # MAX / RemoteConfig delivery health 0..100
    execution_disabled: bool = False
    consecutive_rollbacks: int = 0
    cycles_run: int = 0
    issues: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "game_id": self.game_id,
            "status": self.status,
            "risk": self.risk,
            "score": round(self.score, 2),
            "cycle_success_rate": round(self.cycle_success_rate, 4),
            "failure_rate": round(self.failure_rate, 4),
            "rollback_rate": round(self.rollback_rate, 4),
            "latency_ms": round(self.latency_ms, 2),
            "provider_health": round(self.provider_health, 2),
            "execution_disabled": self.execution_disabled,
            "consecutive_rollbacks": self.consecutive_rollbacks,
            "cycles_run": self.cycles_run,
            "issues": self.issues,
        }


@dataclass
class FleetHealthReport:
    """Aggregate snapshot of the whole fleet at one moment."""
    generated_at: str = field(default_factory=_now)
    games: List[HealthSnapshot] = field(default_factory=list)

    def to_dict(self) -> dict:
        n = len(self.games)
        return {
            "generated_at": self.generated_at,
            "fleet_size": n,
            "healthy": sum(1 for g in self.games if g.status == HEALTH_HEALTHY),
            "degraded": sum(1 for g in self.games if g.status == HEALTH_DEGRADED),
            "unhealthy": sum(1 for g in self.games if g.status == HEALTH_UNHEALTHY),
            "isolated": sum(1 for g in self.games if g.status == HEALTH_ISOLATED),
            "mean_score": round(sum(g.score for g in self.games) / n, 2) if n else 0.0,
            "games": [g.to_dict() for g in self.games],
        }


# --------------------------------------------------------------------------- #
# Explainability
# --------------------------------------------------------------------------- #
@dataclass
class DecisionTrace:
    """One auditable decision: WHAT was done and WHY (a human-readable chain)."""
    game_id: str
    decision: str                       # strategy_type, e.g. bid_floor_adjust
    action: str                         # execute | experiment | block
    reason_chain: List[str]             # ordered, human-readable rationale
    final_action: str                   # executed | rolled_back | blocked | ...
    confidence: float = 0.0
    risk: str = RISK_LOW
    priority: float = 0.0
    day: int = 0
    opportunity_id: str = ""
    timestamp: str = field(default_factory=_now)

    def to_dict(self) -> dict:
        return {
            "game_id": self.game_id,
            "decision": self.decision,
            "action": self.action,
            "reason_chain": self.reason_chain,
            "final_action": self.final_action,
            "confidence": round(self.confidence, 3),
            "risk": self.risk,
            "priority": round(self.priority, 3),
            "day": self.day,
            "opportunity_id": self.opportunity_id,
            "timestamp": self.timestamp,
        }


# --------------------------------------------------------------------------- #
# Daily operator report
# --------------------------------------------------------------------------- #
@dataclass
class SubReport:
    title: str
    lines: List[str]

    def to_dict(self) -> dict:
        return {"title": self.title, "lines": self.lines}


@dataclass
class DailyReport:
    date: str
    summary: str
    ua_action: SubReport
    monetization: SubReport
    experiment: SubReport
    risk: SubReport

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "summary": self.summary,
            "ua_action": self.ua_action.to_dict(),
            "monetization": self.monetization.to_dict(),
            "experiment": self.experiment.to_dict(),
            "risk": self.risk.to_dict(),
        }

    def to_markdown(self) -> str:
        out = [f"# Daily Operation Report — {self.date}", "", self.summary, ""]
        for sub in (self.ua_action, self.monetization, self.experiment, self.risk):
            out.append(f"## {sub.title}")
            for ln in sub.lines:
                out.append(f"- {ln}")
            out.append("")
        return "\n".join(out).rstrip() + "\n"


# --------------------------------------------------------------------------- #
# Metrics export bundle
# --------------------------------------------------------------------------- #
@dataclass
class MetricsBundle:
    generated_at: str
    health: FleetHealthReport
    decision_events: List[dict]
    alerts: List[dict]

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at,
            "health": self.health.to_dict(),
            "decision_events": self.decision_events,
            "alerts": self.alerts,
        }


__all__ = [
    "HealthSnapshot", "FleetHealthReport",
    "HEALTH_HEALTHY", "HEALTH_DEGRADED", "HEALTH_UNHEALTHY", "HEALTH_ISOLATED",
    "RISK_LOW", "RISK_MEDIUM", "RISK_HIGH",
    "DecisionTrace", "SubReport", "DailyReport", "MetricsBundle",
]
