from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class AgentInteraction:
    interaction_id: str
    agent_type: str
    action: str
    input: Dict[str, Any] = field(default_factory=dict)
    output: Dict[str, Any] = field(default_factory=dict)
    success: bool = False
    timestamp: datetime = field(default_factory=datetime.now)


class AgentMemory:
    def __init__(self):
        self.interactions: Dict[str, AgentInteraction] = {}
        self.agent_history: Dict[str, List[str]] = {}

    def record(self, interaction: AgentInteraction) -> None:
        self.interactions[interaction.interaction_id] = interaction
        
        if interaction.agent_type not in self.agent_history:
            self.agent_history[interaction.agent_type] = []
        self.agent_history[interaction.agent_type].append(interaction.interaction_id)

    def get(self, interaction_id: str) -> Optional[AgentInteraction]:
        return self.interactions.get(interaction_id)

    def get_by_agent(self, agent_type: str) -> List[AgentInteraction]:
        ids = self.agent_history.get(agent_type, [])
        return [self.interactions[id] for id in ids[-100:]]

    def get_success_rate(self, agent_type: str) -> float:
        interactions = self.get_by_agent(agent_type)
        if not interactions:
            return 0.5
        
        successes = sum(1 for i in interactions if i.success)
        return successes / len(interactions)

    def store(self, data: Dict[str, Any]) -> AgentInteraction:
        interaction = AgentInteraction(
            interaction_id=f"interaction_{hash(str(data)) % 10000:04d}",
            agent_type=data.get("agent", ""),
            action=data.get("action", ""),
            success=data.get("result") == "success",
        )
        self.record(interaction)
        return interaction

    def retrieve(self, agent_type: str) -> List[AgentInteraction]:
        return self.get_by_agent(agent_type)

    def record_demo(self) -> AgentInteraction:
        interaction = AgentInteraction(
            interaction_id="interaction_001",
            agent_type="ua",
            action="create_campaign",
            input={"name": "US_WITCH_WINNER_001", "budget": 500},
            output={"campaign_id": "campaign_001", "status": "created"},
            success=True,
        )
        self.record(interaction)
        return interaction
