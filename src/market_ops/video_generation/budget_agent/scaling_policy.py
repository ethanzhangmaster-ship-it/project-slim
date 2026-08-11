"""Scaling Policy - 扩量策略"""
from dataclasses import dataclass
from typing import Dict, Any, List


@dataclass
class ScalingAction:
    """扩量动作"""
    action: str = ""
    creative_id: str = ""
    campaign_id: str = ""
    old_budget: float = 0.0
    new_budget: float = 0.0
    reason: str = ""
    confidence: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "creative_id": self.creative_id,
            "campaign_id": self.campaign_id,
            "old_budget": round(self.old_budget, 2),
            "new_budget": round(self.new_budget, 2),
            "reason": self.reason,
            "confidence": round(self.confidence, 2),
        }


class ScalingPolicy:
    """扩量策略"""
    
    def evaluate(self, creative_data: Dict[str, Any]) -> ScalingAction:
        """评估扩量"""
        creative_id = creative_data.get("creative_id", "")
        campaign_id = creative_data.get("campaign_id", "")
        roas = creative_data.get("roas", 0.0)
        d3_roas = creative_data.get("d3_roas", 0.0)
        confidence = creative_data.get("confidence", 0.0)
        current_budget = creative_data.get("current_budget", 0.0)
        target_roas = creative_data.get("target_roas", 1.5)
        
        # 检查扩量条件
        if d3_roas >= target_roas and confidence >= 0.8:
            return self._scale_up(creative_id, campaign_id, current_budget, roas, confidence)
        
        # 检查缩减条件
        elif roas < target_roas * 0.5:
            return self._scale_down(creative_id, campaign_id, current_budget, roas, confidence)
        
        return ScalingAction(
            action="no_change",
            creative_id=creative_id,
            campaign_id=campaign_id,
            old_budget=current_budget,
            new_budget=current_budget,
            reason="Performance meets expectations",
            confidence=confidence,
        )
    
    def _scale_up(self, creative_id: str, campaign_id: str, current: float, roas: float, confidence: float) -> ScalingAction:
        """扩量"""
        if confidence >= 0.9:
            new_budget = min(current * 2, 1000)
            return ScalingAction(
                action="scale_up_2x",
                creative_id=creative_id,
                campaign_id=campaign_id,
                old_budget=current,
                new_budget=new_budget,
                reason=f"High confidence ({confidence:.2f}) + ROAS {roas:.2f} - doubling budget",
                confidence=confidence,
            )
        else:
            new_budget = min(current * 1.5, 500)
            return ScalingAction(
                action="scale_up_1.5x",
                creative_id=creative_id,
                campaign_id=campaign_id,
                old_budget=current,
                new_budget=new_budget,
                reason=f"Good confidence ({confidence:.2f}) + ROAS {roas:.2f} - increasing by 50%",
                confidence=confidence,
            )
    
    def _scale_down(self, creative_id: str, campaign_id: str, current: float, roas: float, confidence: float) -> ScalingAction:
        """缩减"""
        new_budget = max(current * 0.5, 50)
        return ScalingAction(
            action="scale_down",
            creative_id=creative_id,
            campaign_id=campaign_id,
            old_budget=current,
            new_budget=new_budget,
            reason=f"Low ROAS ({roas:.2f}) - reducing by 50%",
            confidence=confidence,
        )
    
    def evaluate_demo(self) -> ScalingAction:
        """演示扩量评估"""
        data = {
            "creative_id": "creative_001",
            "campaign_id": "US_iOS_meta",
            "roas": 2.1,
            "d3_roas": 1.8,
            "confidence": 0.88,
            "current_budget": 200.0,
            "target_roas": 1.5,
        }
        return self.evaluate(data)
