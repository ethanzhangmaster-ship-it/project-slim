from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class Conflict:
    conflict_id: str
    agents: List[str]
    issue: str
    positions: Dict[str, str] = field(default_factory=dict)
    severity: str = "medium"


@dataclass
class Consensus:
    conflict_id: str
    resolution: str
    agreement: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    implemented: bool = False


class ConflictResolver:
    def __init__(self):
        self.resolution_strategies = {
            "budget_conflict": self._resolve_budget_conflict,
            "priority_conflict": self._resolve_priority_conflict,
            "strategy_conflict": self._resolve_strategy_conflict,
        }

    def detect(self, decisions: List[Dict[str, Any]]) -> Optional[Conflict]:
        budget_changes = {}
        for decision in decisions:
            agent = decision.get("agent", "")
            budget_change = decision.get("budget_change", "0%")
            if budget_change != "0%":
                budget_changes[agent] = budget_change

        if len(budget_changes) >= 2:
            values = [self._parse_percent(v) for v in budget_changes.values()]
            if any(v > 0 for v in values) and any(v <= 0 for v in values):
                return Conflict(
                    conflict_id=f"conflict_{hash(str(decisions)) % 1000:03d}",
                    agents=list(budget_changes.keys()),
                    issue="budget_conflict",
                    positions=budget_changes,
                    severity="high",
                )

        return None

    def resolve(self, conflict) -> Consensus:
        if isinstance(conflict, dict):
            conflict = Conflict(
                conflict_id=conflict.get("conflict_id", f"conflict_{hash(str(conflict)) % 1000:03d}"),
                agents=conflict.get("agents", []),
                issue=conflict.get("issue", "unknown"),
                positions=self._parse_positions(conflict.get("positions", [])),
            )
        
        resolver = self.resolution_strategies.get(conflict.issue, self._resolve_default)
        return resolver(conflict)
    
    def _parse_positions(self, positions) -> Dict[str, str]:
        if isinstance(positions, list):
            result = {}
            for p in positions:
                if isinstance(p, dict):
                    result[p.get("agent", "")] = p.get("proposal", "")
            return result
        return positions

    def _resolve_budget_conflict(self, conflict: Conflict) -> Consensus:
        positions = conflict.positions
        
        ua_change = self._parse_percent(positions.get("ua", "0%"))
        finance_change = self._parse_percent(positions.get("finance", "0%"))

        if ua_change > 0 and finance_change <= 0:
            compromise = ua_change * 0.3
            resolution = f"Increase {compromise:.0f}% instead of {ua_change:.0f}%"
            
            return Consensus(
                conflict_id=conflict.conflict_id,
                resolution=resolution,
                agreement={
                    "budget_change": f"+{compromise:.0f}%",
                    "reason": "Balance growth and cashflow",
                },
                confidence=0.85,
            )

        return self._resolve_default(conflict)

    def _resolve_priority_conflict(self, conflict: Conflict) -> Consensus:
        return Consensus(
            conflict_id=conflict.conflict_id,
            resolution="CEO decision prevails",
            agreement={"priority": "ceo_decision"},
            confidence=0.9,
        )

    def _resolve_strategy_conflict(self, conflict: Conflict) -> Consensus:
        return Consensus(
            conflict_id=conflict.conflict_id,
            resolution="Test both strategies",
            agreement={"action": "A/B test", "duration": "7 days"},
            confidence=0.75,
        )

    def _resolve_default(self, conflict: Conflict) -> Consensus:
        return Consensus(
            conflict_id=conflict.conflict_id,
            resolution="Escalate to human",
            agreement={"action": "escalate"},
            confidence=0.5,
        )

    def _parse_percent(self, value: str) -> float:
        try:
            return float(value.replace("%", ""))
        except ValueError:
            return 0.0

    def resolve_demo(self) -> Consensus:
        conflict = Conflict(
            conflict_id="conflict_001",
            agents=["ua", "finance"],
            issue="budget_conflict",
            positions={"ua": "+50%", "finance": "0%"},
            severity="high",
        )
        return self.resolve(conflict)
