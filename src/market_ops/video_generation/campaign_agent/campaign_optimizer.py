from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime


@dataclass
class OptimizationResult:
    campaign_id: str
    action: str
    old_budget: float = 0.0
    new_budget: float = 0.0
    reason: str = ""
    confidence: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


class CampaignOptimizer:
    def __init__(self):
        self.target_roas = 2.0
        self.target_cpi = 2.5
        self.min_spend_for_decision = 100.0

    def optimize(self, campaign_id: str, metrics: Dict[str, Any]) -> OptimizationResult:
        spend = metrics.get("spend", 0.0)
        roas = metrics.get("roas", 0.0)
        cpi = metrics.get("cpi", float("inf"))
        purchases = metrics.get("purchases", 0)
        current_budget = metrics.get("current_budget", 0.0)
        confidence = metrics.get("confidence", 0.5)

        if spend < self.min_spend_for_decision:
            return OptimizationResult(
                campaign_id=campaign_id,
                action="maintain",
                old_budget=current_budget,
                new_budget=current_budget,
                reason=f"Insufficient spend ({spend:.0f}) for decision",
                confidence=0.5,
            )

        if roas > self.target_roas and confidence > 0.8:
            new_budget = current_budget * 1.3
            return OptimizationResult(
                campaign_id=campaign_id,
                action="scale_up",
                old_budget=current_budget,
                new_budget=round(new_budget, 2),
                reason=f"ROAS {roas:.1f} > target {self.target_roas}, confidence {confidence:.2f}",
                confidence=confidence,
            )

        if spend > 300 and purchases == 0:
            new_budget = current_budget * 0.2
            return OptimizationResult(
                campaign_id=campaign_id,
                action="kill",
                old_budget=current_budget,
                new_budget=round(new_budget, 2),
                reason=f"Spend ${spend:.0f} with 0 purchases",
                confidence=0.9,
            )

        if cpi > self.target_cpi * 2:
            new_budget = current_budget * 0.8
            return OptimizationResult(
                campaign_id=campaign_id,
                action="scale_down",
                old_budget=current_budget,
                new_budget=round(new_budget, 2),
                reason=f"CPI ${cpi:.2f} > target {self.target_cpi * 2}",
                confidence=0.75,
            )

        return OptimizationResult(
            campaign_id=campaign_id,
            action="maintain",
            old_budget=current_budget,
            new_budget=current_budget,
            reason="Metrics within range",
            confidence=0.6,
        )

    def optimize_demo(self) -> OptimizationResult:
        metrics = {
            "spend": 500.0,
            "roas": 3.2,
            "cpi": 1.8,
            "purchases": 45,
            "current_budget": 500.0,
            "confidence": 0.88,
        }
        return self.optimize("campaign_001", metrics)
