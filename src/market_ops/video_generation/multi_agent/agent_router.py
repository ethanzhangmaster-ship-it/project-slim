from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class AgentRequest:
    request_id: str
    agent_type: str
    action: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    priority: int = 5


@dataclass
class AgentResponse:
    request_id: str
    agent_type: str
    status: str
    result: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class AgentRouter:
    def __init__(self):
        self.agents = {
            "ceo": ["make_decision", "set_strategy", "review_results"],
            "creative": ["generate", "optimize", "mutate", "evaluate"],
            "ua": ["create_campaign", "optimize_budget", "adjust_bid", "monitor"],
            "finance": ["calculate_roi", "predict_ltv", "optimize_payback", "control_cashflow"],
            "aso": ["analyze", "optimize_keywords", "update_screenshots"],
            "analytics": ["collect_data", "analyze", "generate_report"],
        }

    def route(self, request) -> AgentResponse:
        if isinstance(request, dict):
            agent_type = request.get("type", request.get("agent_type", ""))
            action = request.get("action", "")
            parameters = request.get("parameters", {})
            request_id = request.get("request_id", "req_000")
        else:
            agent_type = request.agent_type
            action = request.action
            parameters = request.parameters
            request_id = request.request_id
        
        if agent_type not in self.agents:
            return AgentResponse(
                request_id=request_id,
                agent_type=agent_type,
                status="failed",
                result={"error": f"Unknown agent type: {agent_type}"},
            )

        if action not in self.agents[agent_type]:
            return AgentResponse(
                request_id=request_id,
                agent_type=agent_type,
                status="failed",
                result={"error": f"Action {action} not supported by {agent_type}"},
            )

        return AgentResponse(
            request_id=request_id,
            agent_type=agent_type,
            status="routed",
            result={
                "agent": agent_type,
                "action": action,
                "parameters": parameters,
                "message": f"Request routed to {agent_type} agent for {action}",
            },
        )

    def get_agent_actions(self, agent_type: str) -> List[str]:
        return self.agents.get(agent_type, [])

    def route_demo(self) -> AgentResponse:
        request = AgentRequest(
            request_id="req_001",
            agent_type="ua",
            action="create_campaign",
            parameters={"name": "US_WITCH_WINNER_001", "budget": 500},
            priority=1,
        )
        return self.route(request)
