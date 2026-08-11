from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime


@dataclass
class CEOInput:
    goal: Dict[str, Any] = field(default_factory=dict)
    current_state: Dict[str, Any] = field(default_factory=dict)
    market_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CEOStrategy:
    strategy_id: str
    actions: List[Dict[str, Any]] = field(default_factory=list)
    overall_recommendation: str = ""
    confidence: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


class CEOAgent:
    def __init__(self):
        self.strategy_generators = {
            "scale": self._generate_scale_strategy,
            "optimize": self._generate_optimize_strategy,
            "explore": self._generate_explore_strategy,
            "defend": self._generate_defend_strategy,
        }

    def make_decision(self, input_data) -> CEOStrategy:
        if isinstance(input_data, dict):
            input_data = CEOInput(**input_data)
        
        current_roas = input_data.current_state.get("roas", 0.0)
        target_roas = input_data.goal.get("target_roas", 1.0)
        budget = input_data.goal.get("budget", 0)
        spend = input_data.current_state.get("spend", 0)

        if current_roas >= target_roas and spend < budget * 0.8:
            strategy_type = "scale"
        elif current_roas < target_roas * 0.8:
            strategy_type = "optimize"
        elif spend < budget * 0.5:
            strategy_type = "explore"
        else:
            strategy_type = "defend"

        generator = self.strategy_generators[strategy_type]
        actions = generator(input_data)

        return CEOStrategy(
            strategy_id=f"strategy_{hash(str(input_data)) % 10000:04d}",
            actions=actions,
            overall_recommendation=self._generate_summary(actions),
            confidence=self._calculate_confidence(input_data),
        )

    def _generate_scale_strategy(self, input_data: CEOInput) -> List[Dict[str, Any]]:
        return [
            {
                "action": "scale_ios_meta",
                "budget_change": "+30%",
                "reason": "Highest LTV segment",
                "priority": 1,
            },
            {
                "action": "creative_mutation",
                "target": "winner_creatives",
                "reason": "Expand winning DNA",
                "priority": 2,
            },
            {
                "action": "audience_expansion",
                "target": "similar_segments",
                "reason": "Scale to similar audiences",
                "priority": 3,
            },
        ]

    def _generate_optimize_strategy(self, input_data: CEOInput) -> List[Dict[str, Any]]:
        return [
            {
                "action": "pause_underperforming",
                "reason": "ROAS below target",
                "priority": 1,
            },
            {
                "action": "budget_reallocation",
                "from": "low_roas",
                "to": "high_roas",
                "reason": "Shift to winners",
                "priority": 2,
            },
            {
                "action": "creative_testing",
                "count": 20,
                "reason": "Find new winners",
                "priority": 3,
            },
        ]

    def _generate_explore_strategy(self, input_data: CEOInput) -> List[Dict[str, Any]]:
        return [
            {
                "action": "new_audience_test",
                "segments": 5,
                "reason": "Explore untapped segments",
                "priority": 1,
            },
            {
                "action": "platform_expansion",
                "target": "tiktok",
                "reason": "Untapped platform opportunity",
                "priority": 2,
            },
            {
                "action": "creative_experimentation",
                "count": 50,
                "reason": "Discover new hooks",
                "priority": 3,
            },
        ]

    def _generate_defend_strategy(self, input_data: CEOInput) -> List[Dict[str, Any]]:
        return [
            {
                "action": "pause_google_android",
                "reason": "Payback too long",
                "priority": 1,
            },
            {
                "action": "reduce_spend",
                "percentage": "-20%",
                "reason": "Protect cashflow",
                "priority": 2,
            },
            {
                "action": "increase_testing",
                "reason": "Find efficient creatives",
                "priority": 3,
            },
        ]

    def _generate_summary(self, actions: List[Dict[str, Any]]) -> str:
        if not actions:
            return "No actions recommended"
        
        priorities = sorted(actions, key=lambda x: x.get("priority", 99))
        return f"Top action: {priorities[0].get('action', '')} - {priorities[0].get('reason', '')}"

    def _calculate_confidence(self, input_data: CEOInput) -> float:
        roas = input_data.current_state.get("roas", 0.0)
        target = input_data.goal.get("target_roas", 1.0)
        data_quality = input_data.current_state.get("data_quality", 0.8)
        
        if roas >= target:
            return min(0.95, data_quality * 0.95)
        elif roas >= target * 0.8:
            return min(0.85, data_quality * 0.85)
        else:
            return min(0.7, data_quality * 0.7)

    def make_decision_demo(self) -> CEOStrategy:
        input_data = CEOInput(
            goal={
                "period": "30_days",
                "budget": 100000,
                "target_roas": 1.2,
                "target_payback": 180,
            },
            current_state={
                "revenue": 50000,
                "spend": 60000,
                "roas": 0.83,
                "data_quality": 0.9,
            },
        )
        return self.make_decision(input_data)
