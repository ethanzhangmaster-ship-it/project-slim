from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class GrowthTactic:
    tactic_id: str
    name: str
    action: str
    target: str
    budget: float = 0.0
    expected_impact: float = 0.0
    confidence: float = 0.0
    priority: int = 5


class GrowthStrategy:
    def __init__(self):
        self.tactic_templates = {
            "scale_winners": self._scale_winners_tactic,
            "audience_expansion": self._audience_expansion_tactic,
            "creative_refresh": self._creative_refresh_tactic,
            "platform_expansion": self._platform_expansion_tactic,
            "bid_optimization": self._bid_optimization_tactic,
        }

    def generate(self, data: Dict[str, Any]) -> List[GrowthTactic]:
        tactics = []

        winners = data.get("winners", [])
        if winners:
            tactics.append(self._scale_winners_tactic(winners))

        opportunities = data.get("opportunities", [])
        for opp in opportunities[:3]:
            if opp.get("type") == "audience":
                tactics.append(self._audience_expansion_tactic(opp))
            elif opp.get("type") == "platform":
                tactics.append(self._platform_expansion_tactic(opp))

        fatigued = data.get("fatigued_creatives", [])
        if fatigued:
            tactics.append(self._creative_refresh_tactic(fatigued))

        tactics.sort(key=lambda x: x.priority)
        return tactics

    def _scale_winners_tactic(self, winners: List[Dict[str, Any]]) -> GrowthTactic:
        top_winner = winners[0]
        return GrowthTactic(
            tactic_id=f"tactic_scale_{hash(top_winner.get('creative_id', '')) % 1000:03d}",
            name="Scale Top Winners",
            action="increase_budget",
            target=top_winner.get("creative_id", ""),
            budget=top_winner.get("budget", 0) * 0.3,
            expected_impact=0.3,
            confidence=top_winner.get("confidence", 0.8),
            priority=1,
        )

    def _audience_expansion_tactic(self, opportunity: Dict[str, Any]) -> GrowthTactic:
        return GrowthTactic(
            tactic_id=f"tactic_audience_{hash(opportunity.get('target', '')) % 1000:03d}",
            name="Audience Expansion",
            action="test_new_segment",
            target=opportunity.get("target", ""),
            budget=opportunity.get("budget", 300),
            expected_impact=opportunity.get("potential_impact", 0.2),
            confidence=opportunity.get("confidence", 0.7),
            priority=2,
        )

    def _creative_refresh_tactic(self, fatigued: List[Dict[str, Any]]) -> GrowthTactic:
        return GrowthTactic(
            tactic_id="tactic_refresh_001",
            name="Creative Refresh",
            action="mutate_fatigued",
            target=f"{len(fatigued)} creatives",
            budget=200 * len(fatigued),
            expected_impact=0.15,
            confidence=0.85,
            priority=3,
        )

    def _platform_expansion_tactic(self, opportunity: Dict[str, Any]) -> GrowthTactic:
        return GrowthTactic(
            tactic_id=f"tactic_platform_{hash(opportunity.get('target', '')) % 1000:03d}",
            name="Platform Expansion",
            action="launch_on_platform",
            target=opportunity.get("target", ""),
            budget=opportunity.get("budget", 500),
            expected_impact=opportunity.get("potential_impact", 0.25),
            confidence=opportunity.get("confidence", 0.6),
            priority=4,
        )

    def _bid_optimization_tactic(self, data: Dict[str, Any]) -> GrowthTactic:
        return GrowthTactic(
            tactic_id="tactic_bid_001",
            name="Bid Optimization",
            action="adjust_bids",
            target="underperforming campaigns",
            expected_impact=0.1,
            confidence=0.75,
            priority=5,
        )

    def generate_demo(self) -> List[GrowthTactic]:
        data = {
            "winners": [{"creative_id": "creative_A", "budget": 500, "confidence": 0.88}],
            "opportunities": [
                {"type": "audience", "target": "US_Female_35-44", "budget": 300, "potential_impact": 0.25, "confidence": 0.85},
                {"type": "platform", "target": "tiktok", "budget": 500, "potential_impact": 0.3, "confidence": 0.7},
            ],
            "fatigued_creatives": [{"creative_id": "creative_X"}, {"creative_id": "creative_Y"}],
        }
        return self.generate(data)
