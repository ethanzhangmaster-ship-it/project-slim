"""Kill Rule - 止损规则"""
from dataclasses import dataclass
from typing import Dict, Any, List


@dataclass
class KillDecision:
    """止损决策"""
    creative_id: str = ""
    should_kill: bool = False
    reason: str = ""
    confidence: float = 0.0
    metrics: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metrics is None:
            self.metrics = {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "should_kill": self.should_kill,
            "reason": self.reason,
            "confidence": round(self.confidence, 2),
            "metrics": {k: round(v, 2) if isinstance(v, float) else v for k, v in self.metrics.items()},
        }


class KillRuleEngine:
    """止损规则引擎"""
    
    def evaluate(self, creative_data: Dict[str, Any]) -> KillDecision:
        """评估是否止损"""
        creative_id = creative_data.get("creative_id", "")
        spend = creative_data.get("spend", 0.0)
        ctr = creative_data.get("ctr", 0.0)
        cvr = creative_data.get("cvr", 0.0)
        purchases = creative_data.get("purchases", 0)
        roas = creative_data.get("roas", 0.0)
        confidence = creative_data.get("confidence", 0.0)
        
        metrics = {
            "spend": spend,
            "ctr": ctr,
            "cvr": cvr,
            "purchases": purchases,
            "roas": roas,
        }
        
        # 规则 1: 高花费但无购买
        if spend >= 300 and purchases == 0:
            return KillDecision(
                creative_id=creative_id,
                should_kill=True,
                reason=f"Spend ${spend:.0f} with 0 purchases",
                confidence=min(0.95, confidence + 0.1),
                metrics=metrics,
            )
        
        # 规则 2: 极低 CTR
        if spend >= 100 and ctr < 1.0:
            return KillDecision(
                creative_id=creative_id,
                should_kill=True,
                reason=f"CTR {ctr:.2f}% below threshold",
                confidence=min(0.90, confidence),
                metrics=metrics,
            )
        
        # 规则 3: 极低 CVR
        if spend >= 150 and cvr < 1.0:
            return KillDecision(
                creative_id=creative_id,
                should_kill=True,
                reason=f"CVR {cvr:.2f}% below threshold",
                confidence=min(0.85, confidence),
                metrics=metrics,
            )
        
        # 规则 4: 极低 ROAS
        if spend >= 200 and roas < 0.3:
            return KillDecision(
                creative_id=creative_id,
                should_kill=True,
                reason=f"ROAS {roas:.2f} below 0.3 threshold",
                confidence=min(0.90, confidence),
                metrics=metrics,
            )
        
        # 规则 5: CTR 下降超过 40%
        prev_ctr = creative_data.get("previous_ctr", ctr)
        if prev_ctr > 0 and ctr / prev_ctr < 0.6:
            return KillDecision(
                creative_id=creative_id,
                should_kill=True,
                reason=f"CTR dropped by {((1 - ctr/prev_ctr) * 100):.0f}%",
                confidence=min(0.85, confidence),
                metrics=metrics,
            )
        
        return KillDecision(
            creative_id=creative_id,
            should_kill=False,
            reason="Performance within acceptable range",
            confidence=confidence,
            metrics=metrics,
        )
    
    def batch_evaluate(self, creatives: List[Dict[str, Any]]) -> List[KillDecision]:
        """批量评估"""
        decisions = []
        for creative in creatives:
            decisions.append(self.evaluate(creative))
        return decisions
    
    def evaluate_demo(self) -> KillDecision:
        """演示止损评估"""
        data = {
            "creative_id": "creative_bad_001",
            "spend": 300.0,
            "ctr": 0.8,
            "cvr": 0.5,
            "purchases": 0,
            "roas": 0.1,
            "confidence": 0.50,
            "previous_ctr": 2.0,
        }
        return self.evaluate(data)
