from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime


@dataclass
class GrowthOpportunity:
    opportunity_id: str
    type: str
    target: str
    reason: str
    potential_impact: float
    confidence: float
    budget_needed: float = 0.0
    priority: str = "medium"
    timestamp: datetime = field(default_factory=datetime.now)


class OpportunityDetector:
    def __init__(self):
        self.opportunity_types = {
            "new_audience": self._detect_new_audience,
            "creative_gap": self._detect_creative_gap,
            "platform_expansion": self._detect_platform_expansion,
            "budget_reallocation": self._detect_budget_reallocation,
        }

    def detect(self, data: Dict[str, Any]) -> List[GrowthOpportunity]:
        opportunities = []
        
        for opp_type, detector in self.opportunity_types.items():
            result = detector(data)
            if result:
                opportunities.extend(result)
        
        opportunities.sort(key=lambda x: x.potential_impact * x.confidence, reverse=True)
        return opportunities[:10]

    def _detect_new_audience(self, data: Dict[str, Any]) -> List[GrowthOpportunity]:
        opportunities = []
        audience_data = data.get("audience_data", {})
        
        for segment, metrics in audience_data.items():
            match_score = metrics.get("match_score", 0.0)
            historical_success = metrics.get("historical_success", 0.0)
            
            if match_score > 0.8 and historical_success < 0.3:
                opportunities.append(GrowthOpportunity(
                    opportunity_id=f"opp_aud_{hash(segment) % 10000:04d}",
                    type="new_audience",
                    target=segment,
                    reason=f"High match score {match_score:.2f}, low historical testing",
                    potential_impact=match_score * 0.5,
                    confidence=0.85,
                    budget_needed=300.0,
                    priority="high",
                ))
        
        return opportunities

    def _detect_creative_gap(self, data: Dict[str, Any]) -> List[GrowthOpportunity]:
        opportunities = []
        creative_data = data.get("creative_data", {})
        
        for creative_id, metrics in creative_data.items():
            fatigue_score = metrics.get("fatigue_score", 0.0)
            roas = metrics.get("roas", 0.0)
            
            if roas > 2.0 and fatigue_score > 0.6:
                opportunities.append(GrowthOpportunity(
                    opportunity_id=f"opp_creative_{hash(creative_id) % 10000:04d}",
                    type="creative_gap",
                    target=creative_id,
                    reason=f"High ROAS {roas:.1f} but fatigued (score {fatigue_score:.2f})",
                    potential_impact=(1 - fatigue_score) * 0.4,
                    confidence=0.9,
                    budget_needed=200.0,
                    priority="high",
                ))
        
        return opportunities

    def _detect_platform_expansion(self, data: Dict[str, Any]) -> List[GrowthOpportunity]:
        opportunities = []
        platform_data = data.get("platform_data", {})
        active_platforms = data.get("active_platforms", ["meta"])
        
        for platform, metrics in platform_data.items():
            if platform not in active_platforms:
                opportunity_score = metrics.get("opportunity_score", 0.0)
                if opportunity_score > 0.7:
                    opportunities.append(GrowthOpportunity(
                        opportunity_id=f"opp_platform_{hash(platform) % 10000:04d}",
                        type="platform_expansion",
                        target=platform,
                        reason=f"Untapped platform with opportunity score {opportunity_score:.2f}",
                        potential_impact=opportunity_score * 0.6,
                        confidence=0.7,
                        budget_needed=500.0,
                        priority="medium",
                    ))
        
        return opportunities

    def _detect_budget_reallocation(self, data: Dict[str, Any]) -> List[GrowthOpportunity]:
        opportunities = []
        campaign_data = data.get("campaign_data", {})
        
        top_performers = []
        low_performers = []
        
        for campaign_id, metrics in campaign_data.items():
            roas = metrics.get("roas", 0.0)
            budget = metrics.get("budget", 0.0)
            
            if roas > 2.5:
                top_performers.append((campaign_id, roas, budget))
            elif roas < 1.0 and budget > 200:
                low_performers.append((campaign_id, roas, budget))
        
        if top_performers and low_performers:
            top = sorted(top_performers, key=lambda x: x[1], reverse=True)[0]
            low = sorted(low_performers, key=lambda x: x[1])[0]
            
            reallocate_amount = min(low[2] * 0.5, 300)
            
            opportunities.append(GrowthOpportunity(
                opportunity_id=f"opp_budget_{hash(top[0]) % 10000:04d}",
                type="budget_reallocation",
                target=f"{low[0]} → {top[0]}",
                reason=f"Reallocate from underperforming ({low[1]:.1f} ROAS) to top performer ({top[1]:.1f} ROAS)",
                potential_impact=(top[1] - low[1]) / top[1] * 0.3,
                confidence=0.8,
                budget_needed=reallocate_amount,
                priority="high",
            ))
        
        return opportunities

    def detect_demo(self) -> List[GrowthOpportunity]:
        data = {
            "audience_data": {
                "US_Female_35-44": {"match_score": 0.91, "historical_success": 0.15},
                "DE_Female_25-34": {"match_score": 0.85, "historical_success": 0.2},
            },
            "creative_data": {
                "creative_A": {"fatigue_score": 0.68, "roas": 3.2},
            },
            "platform_data": {
                "tiktok": {"opportunity_score": 0.78},
            },
            "active_platforms": ["meta", "google"],
            "campaign_data": {
                "campaign_001": {"roas": 3.5, "budget": 500},
                "campaign_002": {"roas": 0.8, "budget": 400},
            },
        }
        return self.detect(data)
