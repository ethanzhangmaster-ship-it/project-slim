from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum


class GrowthMode(Enum):
    SCALE = "scale"
    EXPLORE = "explore"
    OPTIMIZE = "optimize"
    DEFEND = "defend"


@dataclass
class StrategyResult:
    strategy_id: str
    mode: GrowthMode
    actions: List[Dict[str, Any]] = field(default_factory=list)
    budget_allocation: Dict[str, float] = field(default_factory=dict)
    confidence: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


class StrategyEngine:
    def __init__(self):
        self.mode_strategies = {
            GrowthMode.SCALE: self._generate_scale_strategy,
            GrowthMode.EXPLORE: self._generate_explore_strategy,
            GrowthMode.OPTIMIZE: self._generate_optimize_strategy,
            GrowthMode.DEFEND: self._generate_defend_strategy,
        }

    def generate(self, data: Dict[str, Any]) -> StrategyResult:
        mode = self._determine_mode(data)
        generator = self.mode_strategies[mode]
        actions = generator(data)
        
        return StrategyResult(
            strategy_id=f"strat_{hash(str(data)) % 10000:04d}",
            mode=mode,
            actions=actions,
            budget_allocation=self._calculate_budget_allocation(mode, data),
            confidence=self._calculate_confidence(data),
        )

    def _determine_mode(self, data: Dict[str, Any]) -> GrowthMode:
        roas = data.get("roas", 0.0)
        target_roas = data.get("target_roas", 1.0)
        confidence = data.get("confidence", 0.5)
        roas_trend = data.get("roas_trend", 0.0)
        cost_trend = data.get("cost_trend", 0.0)

        if roas >= target_roas and confidence > 0.8:
            return GrowthMode.SCALE
        
        if roas_trend < -0.1 or cost_trend > 0.15:
            return GrowthMode.DEFEND
        
        if roas < target_roas * 0.8:
            return GrowthMode.OPTIMIZE
        
        return GrowthMode.EXPLORE

    def _generate_scale_strategy(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [
            {
                "action": "budget_increase",
                "percentage": "+30%",
                "reason": "ROAS exceeds target with high confidence",
                "priority": 1,
            },
            {
                "action": "creative_mutation",
                "target": "winner_creatives",
                "count": 30,
                "reason": "Expand winning DNA",
                "priority": 2,
            },
            {
                "action": "audience_expansion",
                "target": "similar_segments",
                "reason": "Scale to high LTV audiences",
                "priority": 3,
            },
        ]

    def _generate_explore_strategy(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [
            {
                "action": "new_audience_test",
                "segments": 5,
                "reason": "Explore untapped opportunities",
                "priority": 1,
            },
            {
                "action": "creative_experimentation",
                "count": 50,
                "reason": "Discover new hooks",
                "priority": 2,
            },
            {
                "action": "platform_test",
                "target": "new_platform",
                "reason": "Expand to new channels",
                "priority": 3,
            },
        ]

    def _generate_optimize_strategy(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [
            {
                "action": "pause_underperforming",
                "threshold": {"roas": "<1.0", "cpi": ">5.0"},
                "reason": "Cut waste",
                "priority": 1,
            },
            {
                "action": "budget_reallocation",
                "from": "low_roas",
                "to": "high_roas",
                "percentage": 50,
                "reason": "Shift to winners",
                "priority": 2,
            },
            {
                "action": "bid_optimization",
                "reason": "Improve efficiency",
                "priority": 3,
            },
        ]

    def _generate_defend_strategy(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [
            {
                "action": "reduce_spend",
                "percentage": "-20%",
                "reason": "Protect margin",
                "priority": 1,
            },
            {
                "action": "increase_testing",
                "count": 30,
                "reason": "Find efficient creatives",
                "priority": 2,
            },
            {
                "action": "creative_refresh",
                "target": "fatigued",
                "reason": "Combat ad fatigue",
                "priority": 3,
            },
        ]

    def _calculate_budget_allocation(self, mode: GrowthMode, data: Dict[str, Any]) -> Dict[str, float]:
        if mode == GrowthMode.SCALE:
            return {"winners": 70, "testing": 20, "exploration": 10}
        elif mode == GrowthMode.EXPLORE:
            return {"exploration": 50, "testing": 30, "core": 20}
        elif mode == GrowthMode.OPTIMIZE:
            return {"optimization": 60, "testing": 30, "maintenance": 10}
        elif mode == GrowthMode.DEFEND:
            return {"protection": 60, "testing": 30, "reduction": 10}
        return {}

    def _calculate_confidence(self, data: Dict[str, Any]) -> float:
        roas = data.get("roas", 0.0)
        target = data.get("target_roas", 1.0)
        confidence = data.get("confidence", 0.5)
        
        if roas >= target:
            return min(0.95, confidence * 0.95)
        elif roas >= target * 0.8:
            return min(0.8, confidence * 0.8)
        else:
            return min(0.6, confidence * 0.6)

    def generate_demo(self) -> StrategyResult:
        data = {
            "roas": 2.5,
            "target_roas": 2.0,
            "confidence": 0.88,
            "roas_trend": 0.05,
            "cost_trend": -0.02,
        }
        return self.generate(data)
