"""
E13.4.4 — Autonomous Monetization Agent
========================================

The capstone Decision Orchestrator that closes the E13 control loop:

    Observe -> Analyze -> Plan -> Experiment/Execute -> Evaluate -> Learn -> Repeat

Modules:
    models.py      AgentState / Opportunity / AgentAction / Plan / Report
    guardrails.py  hard safety limits (daily caps, param ceilings, risk blocks)
    policy.py      decides observe / experiment / execute / block
    planner.py     Opportunity -> auditable Plan (Policy + Guardrails)
    scheduler.py   when to run (daily scan + event triggers)
    controller.py  MonetizationAgent: the loop that wires E13.3.1-E13.4.3
"""
from monetization.agent.models import (
    AgentAction, AgentCycleResult, AgentReport, AgentState, GuardrailConfig,
    Opportunity, Plan, PolicyConfig,
)
from monetization.agent.guardrails import Guardrails
from monetization.agent.policy import Policy
from monetization.agent.planner import Planner
from monetization.agent.scheduler import Scheduler
from monetization.agent.controller import MonetizationAgent
from monetization.agent.game_config import GameConfig
from monetization.agent.registry import (
    GameFactoryOS, GameRegistry, MultiGameReport, build_game_agent,
)

__all__ = [
    "AgentState", "Opportunity", "AgentAction", "Plan", "AgentCycleResult",
    "AgentReport", "GuardrailConfig", "PolicyConfig", "Guardrails", "Policy",
    "Planner", "Scheduler", "MonetizationAgent", "GameConfig", "GameRegistry",
    "GameFactoryOS", "MultiGameReport", "build_game_agent",
]
