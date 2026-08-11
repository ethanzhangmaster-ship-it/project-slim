"""
EP0.11.7 — AgentHealth: runtime health gate for the AI game operation OS.

Every production agent declares the secrets/tokens it needs to operate.
``AgentHealth.check(agent)`` verifies token availability and returns a status:

* ``HEALTHY``   — all required AND optional tokens present
* ``DEGRADED``  — all required tokens present, but some optional tokens missing
* ``BLOCKED``   — at least one REQUIRED token missing  (must NOT run)

``AgentHealth.status()`` returns the worst-case platform state across every
registered agent. A single BLOCKED agent pulls the whole platform to BLOCKED,
because launching an agent without its required credentials corrupts data and
can leak half-configured runs.

Usage::

    sm = SecretManager(credentials_dir="credentials")
    health = AgentHealth(secret_manager=sm)

    health.register({
        "name": "aso_intelligence",
        "required_tokens": ["MAX_REPORT_KEY"],
        "optional_tokens": ["OPENAI_API_KEY"],
    })

    result = health.check({"name": "aso_intelligence",
                           "required_tokens": ["MAX_REPORT_KEY"]})
    if result.state == AgentState.BLOCKED:
        raise SystemExit(f"{result.agent} blocked: missing {result.missing_tokens}")

    platform = health.status()     # HealthStatus(state=AgentState.HEALTHY, ...)
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class AgentState(str, Enum):
    """Health state of a single agent (or the whole platform)."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"

    @property
    def is_runnable(self) -> bool:
        """BLOCKED agents must never be launched."""
        return self is not AgentState.BLOCKED


class AgentConfig:
    """Normalized description of an agent's token requirements."""

    def __init__(
        self,
        name: str,
        required_tokens: Optional[List[str]] = None,
        optional_tokens: Optional[List[str]] = None,
        description: str = "",
    ):
        self.name = name
        self.required_tokens: List[str] = list(required_tokens or [])
        self.optional_tokens: List[str] = list(optional_tokens or [])
        self.description = description

    @classmethod
    def from_any(cls, agent: Any) -> "AgentConfig":
        """Accept a dict, an AgentConfig, or any object with the attrs."""
        if isinstance(agent, AgentConfig):
            return agent
        if isinstance(agent, dict):
            return cls(
                name=agent["name"],
                required_tokens=agent.get("required_tokens"),
                optional_tokens=agent.get("optional_tokens"),
                description=agent.get("description", ""),
            )
        # object-style: read attributes with safe fallbacks
        return cls(
            name=getattr(agent, "name", ""),
            required_tokens=getattr(agent, "required_tokens", None),
            optional_tokens=getattr(agent, "optional_tokens", None),
            description=getattr(agent, "description", ""),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "required_tokens": self.required_tokens,
            "optional_tokens": self.optional_tokens,
            "description": self.description,
        }


@dataclass
class AgentCheckResult:
    """Outcome of a single agent health check."""

    agent: str
    state: AgentState
    missing_tokens: List[str] = field(default_factory=list)
    degraded_reasons: List[str] = field(default_factory=list)
    checked_at: float = field(default_factory=time.time)

    @property
    def is_blocked(self) -> bool:
        return self.state is AgentState.BLOCKED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent": self.agent,
            "state": self.state.value,
            "missing_tokens": self.missing_tokens,
            "degraded_reasons": self.degraded_reasons,
            "checked_at": self.checked_at,
        }


@dataclass
class HealthStatus:
    """Aggregate platform health."""

    state: AgentState
    agents_total: int
    healthy: int
    degraded: int
    blocked: int
    blocked_agents: List[str] = field(default_factory=list)
    details: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def is_runnable(self) -> bool:
        return self.state is not AgentState.BLOCKED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state.value,
            "agents_total": self.agents_total,
            "healthy": self.healthy,
            "degraded": self.degraded,
            "blocked": self.blocked,
            "blocked_agents": self.blocked_agents,
            "details": self.details,
        }


class AgentHealth:
    """Token-aware health gate for all production agents."""

    def __init__(self, secret_manager: Optional[Any] = None):
        """
        :param secret_manager: optional SecretManager-compatible object exposing
            ``exists(key) -> bool``. When ``None``, plain ``os.environ`` is used.
        """
        self._secret_manager = secret_manager
        self._agents: List[AgentConfig] = []

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, agent: Any) -> "AgentHealth":
        """Register an agent (dict / AgentConfig / object)."""
        self._agents.append(AgentConfig.from_any(agent))
        return self

    def register_many(self, agents: List[Any]) -> "AgentHealth":
        for a in agents:
            self.register(a)
        return self

    @property
    def agents(self) -> List[AgentConfig]:
        return list(self._agents)

    # ------------------------------------------------------------------
    # Token resolution
    # ------------------------------------------------------------------

    def _token_present(self, key: str) -> bool:
        if self._secret_manager is not None:
            try:
                return bool(self._secret_manager.exists(key))
            except Exception:
                return False
        val = os.environ.get(key)
        return val is not None and val != ""

    # ------------------------------------------------------------------
    # Single-agent check
    # ------------------------------------------------------------------

    def check(self, agent: Any) -> AgentCheckResult:
        """Check one agent's tokens and return its state."""
        cfg = AgentConfig.from_any(agent)

        missing_required: List[str] = []
        missing_optional: List[str] = []

        for tok in cfg.required_tokens:
            if not self._token_present(tok):
                missing_required.append(tok)
        for tok in cfg.optional_tokens:
            if not self._token_present(tok):
                missing_optional.append(tok)

        if missing_required:
            state = AgentState.BLOCKED
            reasons = [f"missing required token: {t}" for t in missing_required]
        elif missing_optional:
            state = AgentState.DEGRADED
            reasons = [f"missing optional token: {t}" for t in missing_optional]
        else:
            state = AgentState.HEALTHY
            reasons = []

        return AgentCheckResult(
            agent=cfg.name,
            state=state,
            missing_tokens=missing_required,
            degraded_reasons=reasons,
        )

    # ------------------------------------------------------------------
    # Aggregate
    # ------------------------------------------------------------------

    def check_all(self) -> List[AgentCheckResult]:
        """Check every registered agent."""
        return [self.check(a) for a in self._agents]

    def status(self) -> HealthStatus:
        """Aggregate health across registered agents (worst-case wins)."""
        results = self.check_all()
        if not results:
            return HealthStatus(
                state=AgentState.HEALTHY,
                agents_total=0,
                healthy=0,
                degraded=0,
                blocked=0,
                blocked_agents=[],
                details=[],
            )

        healthy = degraded = blocked = 0
        blocked_agents: List[str] = []
        worst = AgentState.HEALTHY
        details: List[Dict[str, Any]] = []

        for r in results:
            if r.state is AgentState.BLOCKED:
                blocked += 1
                blocked_agents.append(r.agent)
                worst = AgentState.BLOCKED
            elif r.state is AgentState.DEGRADED:
                degraded += 1
                if worst is AgentState.HEALTHY:
                    worst = AgentState.DEGRADED
            else:
                healthy += 1
            details.append(r.to_dict())

        return HealthStatus(
            state=worst,
            agents_total=len(results),
            healthy=healthy,
            degraded=degraded,
            blocked=blocked,
            blocked_agents=blocked_agents,
            details=details,
        )

    def blocked_agents(self) -> List[str]:
        """Names of all registered agents currently BLOCKED."""
        return [r.agent for r in self.check_all() if r.is_blocked]
