"""Decision Agent - 决策代理"""
from dataclasses import dataclass
from typing import Dict, Any, List


@dataclass
class Decision:
    """决策"""
    decision_id: str = ""
    type: str = ""
    action: str = ""
    target: str = ""
    parameters: Dict[str, Any] = None
    confidence: float = 0.0
    reason: str = ""
    
    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "type": self.type,
            "action": self.action,
            "target": self.target,
            "parameters": {k: round(v, 2) if isinstance(v, float) else v for k, v in self.parameters.items()},
            "confidence": round(self.confidence, 2),
            "reason": self.reason,
        }


class DecisionAgent:
    """决策代理"""
    
    def __init__(self):
        self._counter = 0
    
    def make_decision(self, context: Dict[str, Any]) -> List[Decision]:
        """做出决策"""
        decisions = []
        
        # 基于表现数据做出决策
        performance = context.get("performance", {})
        campaign_data = context.get("campaigns", [])
        
        # 检查每个创意
        for creative in context.get("creatives", []):
            creative_decisions = self._evaluate_creative(creative)
            decisions.extend(creative_decisions)
        
        # 检查每个活动
        for campaign in campaign_data:
            campaign_decisions = self._evaluate_campaign(campaign)
            decisions.extend(campaign_decisions)
        
        return decisions
    
    def _evaluate_creative(self, creative: Dict[str, Any]) -> List[Decision]:
        """评估创意"""
        decisions = []
        creative_id = creative.get("creative_id", "")
        roas = creative.get("roas", 0.0)
        ctr = creative.get("ctr", 0.0)
        confidence = creative.get("confidence", 0.0)
        spend = creative.get("spend", 0.0)
        
        # 扩量决策
        if roas >= 1.5 and confidence >= 0.8:
            self._counter += 1
            decisions.append(Decision(
                decision_id=f"decision_{self._counter:04d}",
                type="scale",
                action="increase_budget",
                target=creative_id,
                parameters={"current_budget": spend, "new_budget": min(spend * 1.5, 1000)},
                confidence=min(confidence, 0.95),
                reason=f"High ROAS ({roas:.2f}) + high confidence ({confidence:.2f})",
            ))
        
        # 止损决策
        elif spend >= 300 and roas < 0.3:
            self._counter += 1
            decisions.append(Decision(
                decision_id=f"decision_{self._counter:04d}",
                type="kill",
                action="pause_creative",
                target=creative_id,
                parameters={"spend": spend, "roas": roas},
                confidence=min(confidence + 0.1, 0.95),
                reason=f"Low ROAS ({roas:.2f}) after ${spend:.0f} spend",
            ))
        
        return decisions
    
    def _evaluate_campaign(self, campaign: Dict[str, Any]) -> List[Decision]:
        """评估活动"""
        decisions = []
        campaign_id = campaign.get("campaign_id", "")
        trend = campaign.get("trend", "stable")
        roas = campaign.get("roas", 0.0)
        
        if trend == "up" and roas >= 1.2:
            self._counter += 1
            decisions.append(Decision(
                decision_id=f"decision_{self._counter:04d}",
                type="optimize",
                action="increase_bid",
                target=campaign_id,
                parameters={"increase_percent": 10},
                confidence=0.85,
                reason=f"Upward trend + good ROAS ({roas:.2f})",
            ))
        
        return decisions
    
    def make_decision_demo(self) -> List[Decision]:
        """演示决策"""
        context = {
            "creatives": [
                {"creative_id": "c001", "roas": 2.3, "ctr": 5.8, "confidence": 0.92, "spend": 200},
                {"creative_id": "c002", "roas": 0.2, "ctr": 0.8, "confidence": 0.40, "spend": 350},
            ],
            "campaigns": [
                {"campaign_id": "camp_001", "trend": "up", "roas": 1.8},
            ],
        }
        
        return self.make_decision(context)
