from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class BoardDecision:
    decision_id: str
    topic: str
    decision: str
    options: List[str] = field(default_factory=list)
    reasoning: str = ""
    confidence: float = 0.0
    implemented: bool = False
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Consensus:
    decision_id: str
    decision: str
    options: List[str] = field(default_factory=list)
    confidence: float = 0.0


class DecisionBoard:
    def __init__(self):
        self.decisions: Dict[str, BoardDecision] = {}
        self.pending_topics: List[str] = []
        self.resolution_strategies = {
            "resource_allocation": self._resolve_resource,
            "project_priority": self._resolve_priority,
        }

    def resolve(self, conflict) -> Consensus:
        if isinstance(conflict, dict):
            options = conflict.get("options", [])
            context = conflict.get("context", {})
            issue = conflict.get("issue", "unknown")
        else:
            options = conflict.options
            context = conflict.context
            issue = conflict.issue

        resolver = self.resolution_strategies.get(issue, self._resolve_default)
        decision = resolver(options, context)

        return Consensus(
            decision_id=f"consensus_{hash(str(conflict)) % 10000:04d}",
            decision=decision,
            options=options,
            confidence=self._calculate_confidence(context),
        )

    def _resolve_resource(self, options: List[str], context: Dict[str, Any]) -> str:
        return options[0] if options else "No decision"

    def _resolve_priority(self, options: List[str], context: Dict[str, Any]) -> str:
        return max(options, key=lambda x: 1 if "High" in x else 0)

    def _resolve_default(self, options: List[str], context: Dict[str, Any]) -> str:
        return options[0] if options else "No decision"

    def make_decision(self, topic: str, options: List[str], context: Dict[str, Any]) -> BoardDecision:
        decision = self._evaluate_options(options, context)
        
        board_decision = BoardDecision(
            decision_id=f"decision_{hash(topic) % 10000:04d}",
            topic=topic,
            decision=decision,
            options=options,
            reasoning=self._generate_reasoning(topic, decision, context),
            confidence=self._calculate_confidence(context),
        )
        
        self.decisions[topic] = board_decision
        
        if topic in self.pending_topics:
            self.pending_topics.remove(topic)
        
        return board_decision

    def _evaluate_options(self, options: List[str], context: Dict[str, Any]) -> str:
        market_score = context.get("market_score", 50)
        financial_score = context.get("financial_score", 50)
        risk_score = context.get("risk_score", 50)
        
        scores = {}
        
        for option in options:
            score = 0
            if "launch" in option.lower():
                if market_score > 70 and financial_score > 60:
                    score += 30
            elif "pause" in option.lower() or "hold" in option.lower():
                if risk_score < 50:
                    score += 25
            elif "kill" in option.lower():
                if financial_score < 40:
                    score += 30
            elif "continue" in option.lower():
                score += 20
            
            scores[option] = score
        
        return max(scores, key=scores.get) if scores else options[0]

    def _generate_reasoning(self, topic: str, decision: str, context: Dict[str, Any]) -> str:
        reasons = []
        
        if "launch" in decision.lower():
            reasons.append("Market opportunity score is high")
            reasons.append("Financial projections meet targets")
        elif "pause" in decision.lower():
            reasons.append("Risk factors need further evaluation")
            reasons.append("Market conditions uncertain")
        elif "kill" in decision.lower():
            reasons.append("Financial performance below expectations")
            reasons.append("Better opportunities available")
        
        return "; ".join(reasons)

    def _calculate_confidence(self, context: Dict[str, Any]) -> float:
        factors = [
            context.get("market_score", 50) / 100,
            context.get("financial_score", 50) / 100,
            context.get("team_confidence", 50) / 100,
        ]
        return round(sum(factors) / len(factors), 2)

    def add_pending(self, topic: str) -> None:
        if topic not in self.pending_topics:
            self.pending_topics.append(topic)

    def get_pending(self) -> List[str]:
        return self.pending_topics.copy()

    def make_decision_demo(self) -> BoardDecision:
        return self.make_decision(
            topic="Launch Merge Cozy",
            options=["Launch", "Pause", "Kill", "Continue Development"],
            context={"market_score": 85, "financial_score": 72, "risk_score": 45, "team_confidence": 80},
        )
