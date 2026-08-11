"""P4.4 least-privilege multi-agent proposal arbitration."""
from dataclasses import dataclass
from typing import Dict, List, Set

from .fleet import AgentRole


PERMISSIONS: Dict[AgentRole, Set[str]] = {
    AgentRole.STRATEGY: {"propose_strategy", "read_all"},
    AgentRole.GROWTH: {"propose_budget", "read_growth"},
    AgentRole.PRODUCT: {"propose_product", "read_product"},
    AgentRole.UA: {"propose_campaign", "read_ads"},
    AgentRole.ASO: {"propose_store", "read_store"},
    AgentRole.MONETIZATION: {"propose_monetization", "read_revenue"},
    AgentRole.CREATIVE: {"propose_creative", "read_creative"},
    AgentRole.DATA_ANALYST: {"propose_analysis", "read_metrics", "generate_reports"},
    AgentRole.PLAYER_SUPPORT: {"propose_support", "read_tickets", "manage_faq"},
    AgentRole.MARKET_INTELLIGENCE: {"propose_market", "read_market", "generate_opportunities"},
}


@dataclass(frozen=True)
class AgentProposal:
    role: AgentRole
    game_id: str
    resource: str
    action: str
    priority: float
    confidence: float
    requested_budget: float = 0.0


class MultiAgentGovernor:
    def __init__(self): self.human_takeover = False

    def authorize(self, role: AgentRole, capability: str) -> bool:
        return capability in PERMISSIONS.get(role, set())

    def arbitrate(self, proposals: List[AgentProposal], budget: float) -> List[AgentProposal]:
        if self.human_takeover: return []
        winners = {}
        for proposal in sorted(proposals, key=lambda p: (-p.priority, -p.confidence, p.role.value, p.action)):
            key = (proposal.game_id, proposal.resource)
            winners.setdefault(key, proposal)
        selected, spent = [], 0.0
        for proposal in winners.values():
            if spent + proposal.requested_budget <= budget:
                selected.append(proposal); spent += proposal.requested_budget
        return selected

    def takeover(self, authorized: bool) -> bool:
        if not authorized: return False
        self.human_takeover = True; return True

    def release(self, authorized: bool) -> bool:
        if not authorized: return False
        self.human_takeover = False; return True


__all__ = ["PERMISSIONS", "AgentProposal", "MultiAgentGovernor"]
