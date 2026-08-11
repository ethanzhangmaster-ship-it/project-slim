"""E5.2 Real Debate Engine — Entry point."""

from .agent_base import DebateAgent, AgentPersonality, RiskTolerance
from .argument_graph import ArgumentGraph, Argument, ArgumentRelation, ArgumentState
from .debate_memory import DebateMemory, DebateOutcome, AgentMemory
from .consensus_engine import ConsensusEngine
from .agents import (
    MarketAgent, GameplayAgent, UAAgent, ProducerAgent, InvestorAgent,
)

__all__ = [
    "DebateAgent", "AgentPersonality", "RiskTolerance",
    "ArgumentGraph", "Argument", "ArgumentRelation", "ArgumentState",
    "DebateMemory", "DebateOutcome", "AgentMemory",
    "ConsensusEngine",
    "MarketAgent", "GameplayAgent", "UAAgent", "ProducerAgent", "InvestorAgent",
]
