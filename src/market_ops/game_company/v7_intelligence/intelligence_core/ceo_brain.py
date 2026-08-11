from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum

from .company_state_model import CompanyStateModel


class DecisionType(Enum):
    CREATE_PROJECT = "create_project"
    SCALE_PROJECT = "scale_project"
    KILL_PROJECT = "kill_project"
    SHIFT_STRATEGY = "shift_strategy"
    INCREASE_UA = "increase_ua"
    REDUCE_SPEND = "reduce_spend"
    ENTER_MARKET = "enter_market"
    HOLD = "hold"
    INVEST_MORE = "invest_more"
    DIVERSIFY = "diversify"


@dataclass
class CEODecision:
    decision_type: DecisionType
    reason: str = ""
    confidence: float = 0.0
    priority: int = 5
    target_project: Optional[str] = None
    budget_change: Optional[float] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_type": self.decision_type.value,
            "reason": self.reason,
            "confidence": self.confidence,
            "priority": self.priority,
            "target_project": self.target_project,
            "budget_change": self.budget_change,
            "parameters": self.parameters,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class CompanyState:
    revenue: float = 0.0
    cash: float = 0.0
    projects: List[Dict[str, Any]] = field(default_factory=list)
    market: str = ""
    users: int = 0
    competitors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "revenue": self.revenue,
            "cash": self.cash,
            "projects": self.projects,
            "market": self.market,
            "users": self.users,
            "competitors": self.competitors,
        }


class CEOBrain:
    def __init__(self):
        self._decision_history: List[CEODecision] = []
        self._strategy_rules: List[Dict[str, Any]] = []
        self._load_default_rules()

    def _load_default_rules(self):
        self._strategy_rules = [
            {
                "name": "scale_if_roi_positive",
                "condition": lambda s: s.finance.roas > 1.5 and s.market.market_growth_rate > 0,
                "decision": DecisionType.SCALE_PROJECT,
                "priority": 1,
            },
            {
                "name": "kill_if_roi_negative",
                "condition": lambda s: s.finance.roas < 0.8,
                "decision": DecisionType.KILL_PROJECT,
                "priority": 1,
            },
            {
                "name": "reduce_spend_if_runway_low",
                "condition": lambda s: s.finance.runway_months < 3,
                "decision": DecisionType.REDUCE_SPEND,
                "priority": 1,
            },
            {
                "name": "create_new_if_cash_healthy",
                "condition": lambda s: s.finance.cash > 500000 and s.products.active_games < 5,
                "decision": DecisionType.CREATE_PROJECT,
                "priority": 2,
            },
            {
                "name": "diversify_if_single_dependency",
                "condition": lambda s: s.products.active_games == 1 and s.finance.revenue > 100000,
                "decision": DecisionType.DIVERSIFY,
                "priority": 3,
            },
        ]

    def evaluate(self, state: CompanyStateModel) -> List[CEODecision]:
        decisions = []
        for rule in self._strategy_rules:
            try:
                if rule["condition"](state):
                    decisions.append(CEODecision(
                        decision_type=rule["decision"],
                        reason=f"Triggered rule: {rule['name']}",
                        confidence=0.7,
                        priority=rule["priority"],
                    ))
            except Exception:
                continue

        if not decisions:
            decisions.append(CEODecision(
                decision_type=DecisionType.HOLD,
                reason="No rules triggered, maintaining current strategy",
                confidence=0.5,
                priority=5,
            ))

        self._decision_history.extend(decisions)
        return sorted(decisions, key=lambda d: d.priority)

    def decide(self, state: CompanyStateModel) -> CEODecision:
        decisions = self.evaluate(state)
        return decisions[0] if decisions else CEODecision(
            decision_type=DecisionType.HOLD,
            reason="No decision available",
            confidence=0.0,
            priority=10,
        )

    def analyze_project(self, state: CompanyStateModel, project_name: str) -> CEODecision:
        for project in state.products.projects:
            if project.get("name") == project_name:
                roi = project.get("roi", 0)
                if roi > 1.5:
                    return CEODecision(
                        decision_type=DecisionType.SCALE_PROJECT,
                        reason=f"Project {project_name} has strong ROI {roi}",
                        confidence=0.85,
                        priority=1,
                        target_project=project_name,
                        budget_change=project.get("budget", 0) * 0.3,
                    )
                elif roi < 0.8:
                    return CEODecision(
                        decision_type=DecisionType.KILL_PROJECT,
                        reason=f"Project {project_name} ROI too low: {roi}",
                        confidence=0.9,
                        priority=1,
                        target_project=project_name,
                    )
                else:
                    return CEODecision(
                        decision_type=DecisionType.HOLD,
                        reason=f"Project {project_name} ROI acceptable: {roi}",
                        confidence=0.6,
                        priority=3,
                        target_project=project_name,
                    )
        return CEODecision(
            decision_type=DecisionType.HOLD,
            reason=f"Project {project_name} not found",
            confidence=0.0,
            priority=10,
        )

    def get_decision_history(self, limit: int = 50) -> List[CEODecision]:
        return self._decision_history[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        total = len(self._decision_history)
        by_type = {}
        for d in self._decision_history:
            by_type[d.decision_type.value] = by_type.get(d.decision_type.value, 0) + 1
        return {
            "total_decisions": total,
            "decisions_by_type": by_type,
            "avg_confidence": sum(d.confidence for d in self._decision_history) / total if total > 0 else 0,
        }
