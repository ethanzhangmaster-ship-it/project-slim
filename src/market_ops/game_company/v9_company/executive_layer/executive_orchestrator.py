from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime


@dataclass
class ExecutiveCycle:
    cycle_id: str
    date: str
    phase: str = "init"
    divisions: List[str] = field(default_factory=list)
    outputs: List[Dict[str, Any]] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "date": self.date,
            "phase": self.phase,
            "divisions": self.divisions,
            "outputs": self.outputs,
            "issues": self.issues,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
        }


@dataclass
class ExecutiveSummary:
    summary_id: str
    period: str = "daily"
    kpi_snapshot: Dict[str, Any] = field(default_factory=dict)
    highlights: List[str] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary_id": self.summary_id,
            "period": self.period,
            "kpi_snapshot": self.kpi_snapshot,
            "highlights": self.highlights,
            "blockers": self.blockers,
            "next_steps": self.next_steps,
            "generated_at": self.generated_at.isoformat(),
        }


@dataclass
class DivisionCoordination:
    coordination_id: str
    from_division: str = ""
    to_division: str = ""
    topic: str = ""
    status: str = "pending"
    deliverables: List[str] = field(default_factory=list)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "coordination_id": self.coordination_id,
            "from_division": self.from_division,
            "to_division": self.to_division,
            "topic": self.topic,
            "status": self.status,
            "deliverables": self.deliverables,
            "updated_at": self.updated_at.isoformat(),
        }


class ExecutiveOrchestrator:
    def __init__(self):
        self._cycles: List[ExecutiveCycle] = []
        self._current_cycle: Optional[ExecutiveCycle] = None
        self._priorities: List[str] = []
        self._resource_allocation: Dict[str, float] = {}
        self._coordination_log: List[DivisionCoordination] = []

    def run_executive_cycle(self) -> ExecutiveCycle:
        date_str = datetime.now().strftime("%Y-%m-%d")
        cycle_id = f"exec_cycle_{date_str}"
        cycle = ExecutiveCycle(
            cycle_id=cycle_id,
            date=date_str,
            phase="running",
            divisions=["product", "ua", "creative", "monetization", "tech"],
            start_time=datetime.now(),
        )
        self._current_cycle = cycle

        cycle.outputs = [
            {"division": "product", "output": "Roadmap v3.2 finalized"},
            {"division": "ua", "output": "Budget reallocation approved"},
            {"division": "creative", "output": "5 new concepts queued"},
        ]
        cycle.issues = ["Creative pipeline bottleneck", "iOS attribution gap"]

        cycle.phase = "completed"
        cycle.end_time = datetime.now()
        self._cycles.append(cycle)
        self._current_cycle = None
        return cycle

    def coordinate_divisions(self) -> List[DivisionCoordination]:
        coordinations = [
            DivisionCoordination(
                coordination_id="coord_001",
                from_division="product",
                to_division="creative",
                topic="New level asset requirements",
                status="in_progress",
                deliverables=["Asset brief", "Style guide"],
            ),
            DivisionCoordination(
                coordination_id="coord_002",
                from_division="ua",
                to_division="monetization",
                topic="Campaign LTV feedback loop",
                status="pending",
                deliverables=["Cohort report", "ROI analysis"],
            ),
        ]
        self._coordination_log.extend(coordinations)
        return coordinations

    def get_executive_summary(self) -> ExecutiveSummary:
        return ExecutiveSummary(
            summary_id=f"summary_{datetime.now().strftime('%Y%m%d')}",
            period="daily",
            kpi_snapshot={
                "revenue": 125000,
                "dau": 45000,
                "ad_spend": 42000,
                "roas": 1.85,
            },
            highlights=["Campaign ROI +18%", "New feature retention +5%"],
            blockers=["iOS review delay", "Creative pipeline bottleneck"],
            next_steps=["Escalate review issue", "Approve contractor budget"],
        )

    def set_priorities(self, priorities: List[str]) -> None:
        self._priorities = priorities

    def allocate_resources(self, allocation: Dict[str, float]) -> Dict[str, float]:
        self._resource_allocation.update(allocation)
        return dict(self._resource_allocation)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_cycles": len(self._cycles),
            "total_coordinations": len(self._coordination_log),
            "current_priorities": len(self._priorities),
            "allocated_departments": len(self._resource_allocation),
        }
