from __future__ import annotations

import hashlib
from typing import Any, Callable, Dict, Iterable, Optional

from .models import AgentConfig, AgentRun, AgentStatus
from .readiness import ProductionReadinessGate


class AutonomousGrowthAgent:
    """Safety envelope around the existing DailyOperatorPipeline."""

    def __init__(self, operator: Callable[..., Any], config: Optional[AgentConfig] = None,
                 readiness: Optional[ProductionReadinessGate] = None):
        self.operator = operator
        self.config = config or AgentConfig()
        self.readiness = readiness or ProductionReadinessGate()
        self.consecutive_failures = 0
        self._completed: Dict[str, AgentRun] = {}

    @property
    def circuit_open(self) -> bool:
        return self.consecutive_failures >= self.config.max_consecutive_failures

    def run(self, business_date: str, game_ids: Iterable[str], *,
            proposed_actions: int = 0, requested_budget: float = 0.0,
            confidence: float = 1.0, approval_present: bool = False) -> AgentRun:
        games = list(dict.fromkeys(game_ids or []))
        key = f"{business_date}|{','.join(games)}|{self.config.mode}"
        run_id = "p4_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
        if run_id in self._completed:
            return self._completed[run_id]
        if self.circuit_open:
            return AgentRun(run_id, business_date, AgentStatus.CIRCUIT_OPEN,
                            len(games), reason="consecutive failure threshold reached")
        report = self.readiness.check(self.config)
        blockers = list(report.blockers)
        if len(games) > self.config.max_games:
            blockers.append("game limit exceeded")
        if proposed_actions > self.config.max_actions:
            blockers.append("action limit exceeded")
        if requested_budget > self.config.max_daily_budget:
            blockers.append("daily budget exceeded")
        if confidence < self.config.min_confidence:
            blockers.append("confidence below autonomous threshold")
        if self.config.mode == "production" and self.config.require_approval_in_production and not approval_present:
            blockers.append("production approval missing")
        if blockers:
            return AgentRun(run_id, business_date, AgentStatus.BLOCKED, len(games),
                            proposed_actions, reason="; ".join(blockers))
        try:
            result = self.operator(business_date=business_date, game_ids=games,
                                   mode=self.config.mode, run_id=run_id)
            real = bool((result or {}).get("real_api_called", False)) if isinstance(result, dict) else False
            executed = proposed_actions if self.config.mode == "production" else 0
            run = AgentRun(run_id, business_date, AgentStatus.COMPLETED, len(games),
                           proposed_actions, executed, requested_budget if executed else 0.0,
                           output=dict(result or {}) if isinstance(result, dict) else {},
                           real_api_called=real)
            self.consecutive_failures = 0
            self._completed[run_id] = run
            return run
        except Exception as exc:
            self.consecutive_failures += 1
            return AgentRun(run_id, business_date, AgentStatus.FAILED, len(games),
                            proposed_actions, reason=f"operator failed: {type(exc).__name__}")

    def reset_circuit(self, *, authorized: bool = False) -> bool:
        if not authorized:
            return False
        self.consecutive_failures = 0
        return True
