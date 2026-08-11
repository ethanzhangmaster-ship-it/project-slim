from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
import random


class UAActionType(Enum):
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    PAUSE = "pause"
    RESUME = "resume"
    BID_ADJUST = "bid_adjust"
    BUDGET_REALLOCATE = "budget_reallocate"
    TARGETING_UPDATE = "targeting_update"
    CREATIVE_REFRESH = "creative_refresh"


@dataclass
class UAAction:
    action_type: UAActionType
    campaign_id: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    confidence: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_type": self.action_type.value,
            "campaign_id": self.campaign_id,
            "parameters": self.parameters,
            "reason": self.reason,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class CampaignHealth:
    campaign_id: str
    health_score: float = 0.0
    roas: float = 0.0
    spend: float = 0.0
    revenue: float = 0.0
    ctr: float = 0.0
    cvr: float = 0.0
    cpi: float = 0.0
    status: str = "unknown"
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "health_score": self.health_score,
            "roas": self.roas,
            "spend": self.spend,
            "revenue": self.revenue,
            "ctr": self.ctr,
            "cvr": self.cvr,
            "cpi": self.cpi,
            "status": self.status,
            "issues": self.issues,
            "recommendations": self.recommendations,
        }


@dataclass
class UARecommendation:
    recommendation_id: str
    campaign_id: str
    action: UAActionType
    parameters: Dict[str, Any] = field(default_factory=dict)
    expected_impact: float = 0.0
    confidence: float = 0.0
    reason: str = ""
    priority: int = 5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "campaign_id": self.campaign_id,
            "action": self.action.value,
            "parameters": self.parameters,
            "expected_impact": self.expected_impact,
            "confidence": self.confidence,
            "reason": self.reason,
            "priority": self.priority,
        }


class UAController:
    def __init__(self):
        self._campaigns: Dict[str, CampaignHealth] = {}
        self._recommendations: List[UARecommendation] = []
        self._actions: List[UAAction] = []

    def register_campaign(self, campaign_id: str, initial_health: CampaignHealth = None):
        health = initial_health or CampaignHealth(campaign_id=campaign_id)
        self._campaigns[campaign_id] = health

    def get_campaign_health(self, campaign_id: str) -> Optional[CampaignHealth]:
        return self._campaigns.get(campaign_id)

    def optimize(self) -> List[UARecommendation]:
        recommendations = []
        for campaign_id, health in self._campaigns.items():
            if health.roas > 1.5:
                rec = UARecommendation(
                    recommendation_id=f"rec_{campaign_id}_scale",
                    campaign_id=campaign_id,
                    action=UAActionType.SCALE_UP,
                    parameters={"budget_change": 0.3},
                    expected_impact=health.revenue * 0.3,
                    confidence=0.85,
                    reason=f"ROAS {health.roas:.2f} is above target",
                    priority=1,
                )
                recommendations.append(rec)
            elif health.roas < 0.8:
                rec = UARecommendation(
                    recommendation_id=f"rec_{campaign_id}_reduce",
                    campaign_id=campaign_id,
                    action=UAActionType.SCALE_DOWN,
                    parameters={"budget_change": -0.3},
                    expected_impact=-health.spend * 0.3,
                    confidence=0.9,
                    reason=f"ROAS {health.roas:.2f} is below target",
                    priority=1,
                )
                recommendations.append(rec)

        self._recommendations.extend(recommendations)
        return recommendations

    def scale_campaign(self, campaign_id: str, action: str, percent: float = 30) -> UAAction:
        action_type = UAActionType.SCALE_UP if action == "increase" else UAActionType.SCALE_DOWN
        ua_action = UAAction(
            action_type=action_type,
            campaign_id=campaign_id,
            parameters={"percent": percent},
            reason=f"Manual scale {action}",
            confidence=1.0,
        )
        self._actions.append(ua_action)
        return ua_action

    def get_recommendations(self, campaign_id: str = None) -> List[UARecommendation]:
        if campaign_id:
            return [r for r in self._recommendations if r.campaign_id == campaign_id]
        return list(self._recommendations)

    def execute_action(self, action: UAAction) -> Dict[str, Any]:
        result = {
            "action": action.to_dict(),
            "status": "executed",
            "timestamp": datetime.now().isoformat(),
        }
        self._actions.append(action)
        return result

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_campaigns": len(self._campaigns),
            "total_recommendations": len(self._recommendations),
            "total_actions": len(self._actions),
            "healthy_campaigns": sum(1 for h in self._campaigns.values() if h.health_score > 70),
        }