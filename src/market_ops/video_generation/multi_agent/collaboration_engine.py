from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class CollaborationResult:
    collaboration_id: str
    participants: List[str]
    decisions: List[Dict[str, Any]] = field(default_factory=list)
    conflicts: int = 0
    resolved_conflicts: int = 0
    status: str = "in_progress"
    timestamp: datetime = field(default_factory=datetime.now)


class CollaborationEngine:
    def __init__(self):
        self.agent_priorities = {
            "ceo": 1,
            "finance": 2,
            "ua": 3,
            "creative": 4,
            "aso": 5,
            "analytics": 6,
        }

    def collaborate(self, agents: List[str], request: Dict[str, Any]) -> CollaborationResult:
        collaboration_id = f"collab_{hash(str(agents)) % 10000:04d}"
        decisions = []
        conflicts = 0

        for agent in agents:
            decision = self._get_agent_decision(agent, request)
            decisions.append(decision)
            if decision.get("conflict", False):
                conflicts += 1

        resolved_conflicts = conflicts if len(agents) > 1 else 0

        return CollaborationResult(
            collaboration_id=collaboration_id,
            participants=agents,
            decisions=decisions,
            conflicts=conflicts,
            resolved_conflicts=resolved_conflicts,
            status="completed",
        )

    def _get_agent_decision(self, agent: str, request: Dict[str, Any]) -> Dict[str, Any]:
        decisions = {
            "ua": {
                "agent": "ua",
                "decision": "Scale Meta",
                "budget_change": "+50%",
                "reason": "High ROAS segment",
                "conflict": False,
            },
            "finance": {
                "agent": "finance",
                "decision": "Don't expand",
                "budget_change": "0%",
                "reason": "Cashflow pressure",
                "conflict": True,
            },
            "ceo": {
                "agent": "ceo",
                "decision": "Compromise",
                "budget_change": "+15%",
                "reason": "Balance growth and cashflow",
                "conflict": False,
            },
            "creative": {
                "agent": "creative",
                "decision": "Generate mutations",
                "count": 20,
                "reason": "Support expansion",
                "conflict": False,
            },
            "aso": {
                "agent": "aso",
                "decision": "Optimize store listing",
                "reason": "Prepare for increased traffic",
                "conflict": False,
            },
            "analytics": {
                "agent": "analytics",
                "decision": "Monitor closely",
                "frequency": "hourly",
                "reason": "Track expansion impact",
                "conflict": False,
            },
        }
        
        return decisions.get(agent, {"agent": agent, "decision": "No decision", "conflict": False})

    def collaborate_demo(self) -> CollaborationResult:
        agents = ["ua", "finance", "ceo"]
        request = {"action": "scale_campaign", "current_budget": 500, "roas": 2.8}
        return self.collaborate(agents, request)
