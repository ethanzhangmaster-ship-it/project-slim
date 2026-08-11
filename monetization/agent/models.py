"""
E13.4.4 — Module 0: Agent Data Models
======================================

Data contracts for the Autonomous Monetization Agent. This is the capstone
orchestrator that ties E13.3.1 (Reality) → E13.3.2 (Strategy) → E13.2.9
(Simulator) → E13.4.3 (Intelligence) → E13.3.3 (Executor) → E13.4.2
(Experiment) → E13.4.1 (Memory) into ONE closed control loop.

The agent is a *Decision Orchestrator* (not a chat-bot LLM agent). It has
explicit, inspectable state and a deterministic policy. No LLM, no external
API, no RL — pure-Python Lean architecture, consistent with the rest of E13.

Agent loop (user-defined):
    Observe -> Analyze -> Plan -> Experiment/Execute -> Evaluate -> Learn -> Repeat
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

from monetization.intelligence.strategy_prior import StrategyPriorEngine
from monetization.learning.decision_store import DecisionStore


# --------------------------------------------------------------------------- #
# Action vocabulary (the four moves the agent can make)
# --------------------------------------------------------------------------- #
ACTION_OBSERVE = "observe"
ACTION_EXPERIMENT = "experiment"
ACTION_EXECUTE = "execute"
ACTION_BLOCK = "block"
AGENT_ACTIONS = (ACTION_OBSERVE, ACTION_EXPERIMENT, ACTION_EXECUTE, ACTION_BLOCK)

# Agent stages (the explicit state machine the controller walks through)
STAGE_IDLE = "idle"
STAGE_OBSERVE = "observe"
STAGE_ANALYZE = "analyze"
STAGE_PLAN = "plan"
STAGE_ACT = "act"
STAGE_EVALUATE = "evaluate"
STAGE_LEARN = "learn"


# --------------------------------------------------------------------------- #
# Opportunity (thin, compatible with E13.3.2 StrategyEngine + E13.4.3 ranker)
# --------------------------------------------------------------------------- #
@dataclass
class Opportunity:
    """A monetization problem detected by the Reality Engine.

    Compatible with E13.3.2 StrategyEngine.process_opportunity (needs
    .id / .type / .segment) and E13.4.3 build_feature/rank (needs .type /
    .segment / .metrics / .id).
    """
    id: str
    type: str                       # ecpm_drop | fill_drop | ad_frequency_issue | revenue_drop
    segment: dict                   # {country, platform, ad_format, network}
    metrics: dict = field(default_factory=dict)
    severity: float = 0.5          # 0..1 issue urgency (drives policy urgency)
    forced_risk: str = ""          # optional override ("high") = reality detected retention crash

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Tunable configs
# --------------------------------------------------------------------------- #
@dataclass
class GuardrailConfig:
    """Hard safety limits. The agent may never cross these."""
    max_bid_change_pct: float = 25.0       # single action may not move a param > 25%
    max_executions_per_day: int = 3        # per-game daily execution cap
    max_experiments_per_day: int = 5       # per-game daily experiment cap
    retention_drop_block_pct: float = 5.0  # D1 retention <= -5% -> auto-stop (block)
    allow_high_risk_execute: bool = False  # high-retention-risk actions are NEVER executed


@dataclass
class PolicyConfig:
    """Thresholds that turn signals into a discrete action."""
    execute_prior: float = 0.70            # min historical success rate to auto-execute
    execute_conf: float = 0.70             # min fused confidence to auto-execute
    severe_severity: float = 0.60          # issue severity above which we act (not just watch)
    unknown_samples: int = 0               # strategy with <= this many samples is "unknown"
    min_local_samples: int = 1             # act on a (strategy, segment) only after this many local trials


# --------------------------------------------------------------------------- #
# Runtime state
# --------------------------------------------------------------------------- #
@dataclass
class AgentState:
    """The agent's explicit, inspectable state at any moment."""
    cycle_id: str = ""
    day: int = 0
    current_stage: str = STAGE_IDLE
    active_opportunities: List[str] = field(default_factory=list)
    running_experiments: List[str] = field(default_factory=list)
    pending_decisions: List[str] = field(default_factory=list)
    risk_level: str = "normal"             # normal | elevated | critical
    executions_today: int = 0
    experiments_today: int = 0
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- #
# A single decision the agent made for one opportunity
# --------------------------------------------------------------------------- #
@dataclass
class AgentAction:
    opportunity_id: str
    strategy_type: str
    action: str                           # observe | experiment | execute | block
    priority: float                       # fused probability / urgency
    reason: str
    # ---- the signals the policy saw (full audit trail) ----
    prior_mean: float = 0.5
    prior_samples: int = 0
    confidence: float = 0.0
    risk: str = "low"
    simulation_revenue_delta: float = 0.0
    retention_delta: float = 0.0
    severity: float = 0.0
    day: int = 0
    # ---- outcome (filled after the action runs) ----
    result_status: str = ""               # executed | rolled_back | pending | exp_completed | blocked
    result_summary: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Plan produced by the Planner for one opportunity
# --------------------------------------------------------------------------- #
@dataclass
class Plan:
    opportunity_id: str
    recommended_action: str
    strategy_type: str
    priority: float
    rationale: str
    policy_inputs: dict = field(default_factory=dict)
    downgraded_by_guardrail: str = ""     # "" or reason if guardrails changed the action

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Per-cycle result + full report
# --------------------------------------------------------------------------- #
@dataclass
class AgentCycleResult:
    cycle_id: str
    day: int
    opportunities: int
    n_observe: int = 0
    n_experiment: int = 0
    n_execute: int = 0
    n_block: int = 0
    actions: List[AgentAction] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["actions"] = [a.to_dict() for a in self.actions]
        return d


@dataclass
class AgentReport:
    cycles: int = 0
    opportunities: int = 0
    experiments: int = 0
    executions: int = 0                 # agent-dispatched execute decisions
    executed_actually: int = 0          # reached executor 'executed' (mock)
    pending_human: int = 0              # executor 'pending' (manual_review)
    rollbacks: int = 0
    blocks: int = 0
    observes: int = 0
    strategy_improvement_pct: float = 0.0
    per_day: List[AgentCycleResult] = field(default_factory=list)
    guardrail_violations: List[dict] = field(default_factory=list)
    actions: List[AgentAction] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["per_day"] = [c.to_dict() for c in self.per_day]
        d["actions"] = [a.to_dict() for a in self.actions]
        return d


__all__ = [
    "Opportunity", "GuardrailConfig", "PolicyConfig", "AgentState",
    "AgentAction", "Plan", "AgentCycleResult", "AgentReport",
    "ACTION_OBSERVE", "ACTION_EXPERIMENT", "ACTION_EXECUTE", "ACTION_BLOCK",
    "AGENT_ACTIONS", "STAGE_IDLE", "STAGE_OBSERVE", "STAGE_ANALYZE",
    "STAGE_PLAN", "STAGE_ACT", "STAGE_EVALUATE", "STAGE_LEARN",
]
