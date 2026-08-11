from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List


class AgentStatus(str, Enum):
    READY = "ready"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CIRCUIT_OPEN = "circuit_open"


@dataclass
class AgentConfig:
    mode: str = "dry_run"
    max_games: int = 25
    max_actions: int = 20
    max_daily_budget: float = 1000.0
    min_confidence: float = 0.7
    max_consecutive_failures: int = 3
    require_approval_in_production: bool = True
    required_env: List[str] = field(default_factory=list)

    def validate(self) -> List[str]:
        errors = []
        if self.mode not in ("simulation", "dry_run", "production"):
            errors.append("mode must be simulation, dry_run, or production")
        if self.max_games < 1 or self.max_actions < 1:
            errors.append("max_games and max_actions must be positive")
        if self.max_daily_budget < 0:
            errors.append("max_daily_budget must be non-negative")
        if not 0.0 <= self.min_confidence <= 1.0:
            errors.append("min_confidence must be within [0, 1]")
        if self.max_consecutive_failures < 1:
            errors.append("max_consecutive_failures must be positive")
        return errors


@dataclass
class ReadinessReport:
    ready: bool
    checks: Dict[str, bool] = field(default_factory=dict)
    blockers: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    real_api_called: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {"ready": self.ready, "checks": dict(self.checks),
                "blockers": list(self.blockers), "warnings": list(self.warnings),
                "real_api_called": False}


@dataclass
class AgentRun:
    run_id: str
    business_date: str
    status: AgentStatus
    games_requested: int = 0
    actions_proposed: int = 0
    actions_executed: int = 0
    spend_authorized: float = 0.0
    reason: str = ""
    output: Dict[str, Any] = field(default_factory=dict)
    real_api_called: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {"run_id": self.run_id, "business_date": self.business_date,
                "status": self.status.value, "games_requested": self.games_requested,
                "actions_proposed": self.actions_proposed,
                "actions_executed": self.actions_executed,
                "spend_authorized": self.spend_authorized, "reason": self.reason,
                "output": dict(self.output), "real_api_called": self.real_api_called}
