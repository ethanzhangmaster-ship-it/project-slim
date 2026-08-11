from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from enum import Enum


class AgentStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    WAITING = "waiting"
    SUCCESS = "success"
    FAILED = "failed"
    PAUSED = "paused"


@dataclass
class AgentState:
    agent_id: str
    agent_type: str
    name: str
    status: AgentStatus = AgentStatus.IDLE
    current_task: str = ""
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_runtime_seconds: float = 0.0
    last_heartbeat: Optional[datetime] = None
    current_cost: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgentMonitor:
    def __init__(self):
        self._agents: Dict[str, AgentState] = {}
        self._history: Dict[str, List[Dict[str, Any]]] = {}

    def register_agent(self, agent_id: str, agent_type: str, name: str) -> AgentState:
        state = AgentState(
            agent_id=agent_id,
            agent_type=agent_type,
            name=name,
        )
        self._agents[agent_id] = state
        self._history[agent_id] = []
        return state

    def update_status(
        self,
        agent_id: str,
        status: AgentStatus,
        task: str = "",
        cost: float = 0.0,
    ) -> bool:
        agent = self._agents.get(agent_id)
        if not agent:
            return False

        old_status = agent.status
        agent.status = status
        agent.last_heartbeat = datetime.now()

        if task:
            agent.current_task = task

        if cost > 0:
            agent.current_cost += cost

        if status == AgentStatus.SUCCESS:
            agent.tasks_completed += 1
        elif status == AgentStatus.FAILED:
            agent.tasks_failed += 1

        self._history[agent_id].append({
            "timestamp": datetime.now().isoformat(),
            "old_status": old_status.value,
            "new_status": status.value,
            "task": task,
        })

        return True

    def heartbeat(self, agent_id: str, cost: float = 0.0) -> bool:
        agent = self._agents.get(agent_id)
        if not agent:
            return False
        agent.last_heartbeat = datetime.now()
        if cost > 0:
            agent.current_cost += cost
        return True

    def get_agent(self, agent_id: str) -> Optional[AgentState]:
        return self._agents.get(agent_id)

    def get_agents_by_status(self, status: AgentStatus) -> List[AgentState]:
        return [a for a in self._agents.values() if a.status == status]

    def get_active_agents(self) -> List[AgentState]:
        return [
            a for a in self._agents.values()
            if a.status in (AgentStatus.RUNNING, AgentStatus.WAITING)
        ]

    def get_stale_agents(self, timeout_seconds: int = 300) -> List[AgentState]:
        now = datetime.now()
        stale = []
        for agent in self._agents.values():
            if agent.last_heartbeat is None:
                continue
            if (now - agent.last_heartbeat).total_seconds() > timeout_seconds:
                if agent.status == AgentStatus.RUNNING:
                    stale.append(agent)
        return stale

    def get_agent_history(self, agent_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        history = self._history.get(agent_id, [])
        return history[-limit:]

    def get_summary(self) -> Dict[str, Any]:
        total = len(self._agents)
        running = len(self.get_agents_by_status(AgentStatus.RUNNING))
        failed = len(self.get_agents_by_status(AgentStatus.FAILED))
        waiting = len(self.get_agents_by_status(AgentStatus.WAITING))
        completed = sum(a.tasks_completed for a in self._agents.values())
        total_cost = sum(a.current_cost for a in self._agents.values())

        by_type: Dict[str, int] = {}
        for agent in self._agents.values():
            by_type[agent.agent_type] = by_type.get(agent.agent_type, 0) + 1

        return {
            "total_agents": total,
            "running": running,
            "failed": failed,
            "waiting": waiting,
            "idle": total - running - failed - waiting,
            "total_tasks_completed": completed,
            "total_cost": round(total_cost, 2),
            "agents_by_type": by_type,
        }

    def get_dashboard(self) -> Dict[str, Any]:
        summary = self.get_summary()
        active = self.get_active_agents()
        stale = self.get_stale_agents()

        return {
            "summary": summary,
            "active_agents": [a.name for a in active],
            "stale_agents": [a.name for a in stale],
            "timestamp": datetime.now().isoformat(),
        }
