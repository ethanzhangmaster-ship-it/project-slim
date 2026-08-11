from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class PortfolioAllocation:
    campaign_id: str
    platform: str
    audience: Dict[str, str] = field(default_factory=dict)
    allocation_percent: float = 0.0
    budget: float = 0.0
    expected_roas: float = 0.0
    priority: int = 5


class PortfolioOptimizer:
    def __init__(self):
        self.risk_weights = {
            "low": 0.3,
            "medium": 0.5,
            "high": 0.7,
        }

    def optimize(self, campaigns: List[Dict[str, Any]], total_budget: float) -> List[PortfolioAllocation]:
        allocations = []
        
        scored_campaigns = []
        for campaign in campaigns:
            score = self._calculate_score(campaign)
            scored_campaigns.append((campaign, score))
        
        scored_campaigns.sort(key=lambda x: x[1], reverse=True)
        
        total_score = sum(score for _, score in scored_campaigns)
        if total_score == 0:
            total_score = 1
        
        for i, (campaign, score) in enumerate(scored_campaigns):
            allocation = score / total_score
            allocation_percent = min(allocation * 100, 40)
            budget = total_budget * allocation_percent / 100
            
            allocations.append(PortfolioAllocation(
                campaign_id=campaign.get("campaign_id", ""),
                platform=campaign.get("platform", ""),
                audience=campaign.get("audience", {}),
                allocation_percent=round(allocation_percent, 1),
                budget=round(budget, 2),
                expected_roas=campaign.get("roas", 0),
                priority=i + 1,
            ))
        
        remainder = total_budget - sum(a.budget for a in allocations)
        if allocations:
            allocations[0].budget += remainder
        
        return allocations

    def _calculate_score(self, campaign: Dict[str, Any]) -> float:
        roas = campaign.get("roas", 0.0)
        confidence = campaign.get("confidence", 0.5)
        risk = campaign.get("risk", "medium")
        
        roas_score = min(roas / 2.0, 1.0)
        risk_score = self.risk_weights.get(risk, 0.5)
        
        return roas_score * 0.5 + confidence * 0.3 + risk_score * 0.2

    def optimize_demo(self) -> List[PortfolioAllocation]:
        campaigns = [
            {"campaign_id": "c1", "platform": "meta", "roas": 3.2, "confidence": 0.88, "risk": "low"},
            {"campaign_id": "c2", "platform": "google", "roas": 2.5, "confidence": 0.75, "risk": "medium"},
            {"campaign_id": "c3", "platform": "asa", "roas": 1.8, "confidence": 0.8, "risk": "high"},
            {"campaign_id": "c4", "platform": "tiktok", "roas": 2.0, "confidence": 0.6, "risk": "medium"},
        ]
        return self.optimize(campaigns, 10000)
