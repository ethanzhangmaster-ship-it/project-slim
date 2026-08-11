from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class PaybackDecision:
    campaign_id: str
    decision: str
    payback_period_days: float
    target_payback: float
    confidence: float
    reason: str = ""
    recommended_action: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


class PaybackOptimizer:
    def __init__(self):
        self.target_payback = 180
        self.confidence_threshold = 0.8

    def evaluate(self, campaign_data: Dict[str, Any]) -> PaybackDecision:
        cpi = campaign_data.get("cpi", 0.0)
        d30_ltv = campaign_data.get("d30_ltv", 0.0)
        d90_ltv = campaign_data.get("d90_ltv", 0.0)
        d180_ltv = campaign_data.get("d180_ltv", 0.0)
        confidence = campaign_data.get("confidence", 0.5)

        if cpi > 0:
            if d180_ltv > 0:
                payback_days = (cpi / d180_ltv) * 180
            elif d90_ltv > 0:
                payback_days = (cpi / d90_ltv) * 90
            elif d30_ltv > 0:
                payback_days = (cpi / d30_ltv) * 30
            else:
                payback_days = float("inf")
        else:
            payback_days = float("inf")

        if payback_days < self.target_payback * 0.8 and confidence > self.confidence_threshold:
            decision = "SCALE"
            recommended_action = "Increase budget by 30%"
            reason = f"Payback {payback_days:.0f} days < target {self.target_payback} days"
        elif payback_days < self.target_payback * 1.2:
            decision = "HOLD"
            recommended_action = "Monitor and optimize"
            reason = f"Payback {payback_days:.0f} days near target"
        else:
            decision = "KILL"
            recommended_action = "Pause or reduce spend"
            reason = f"Payback {payback_days:.0f} days > target {self.target_payback} days"

        return PaybackDecision(
            campaign_id=campaign_data.get("campaign_id", ""),
            decision=decision,
            payback_period_days=round(payback_days, 1),
            target_payback=self.target_payback,
            confidence=confidence,
            reason=reason,
            recommended_action=recommended_action,
        )

    def decide(self, data: Dict[str, Any]) -> Dict[str, Any]:
        d30_payback = data.get("d30_payback", float("inf"))
        confidence = data.get("confidence", 0.5)
        
        if d30_payback < self.target_payback * 0.8 and confidence > self.confidence_threshold:
            return {"action": "SCALE", "reason": f"Payback {d30_payback} days < target"}
        elif d30_payback < self.target_payback * 1.2:
            return {"action": "HOLD", "reason": f"Payback near target"}
        else:
            return {"action": "KILL", "reason": f"Payback {d30_payback} days > target"}

    def evaluate_demo(self) -> PaybackDecision:
        data = {
            "campaign_id": "campaign_001",
            "cpi": 2.0,
            "d30_ltv": 1.5,
            "d90_ltv": 2.8,
            "d180_ltv": 3.5,
            "confidence": 0.86,
        }
        return self.evaluate(data)
