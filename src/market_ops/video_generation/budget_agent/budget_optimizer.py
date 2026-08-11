"""Budget Optimizer - 预算优化器"""
from dataclasses import dataclass
from typing import Dict, Any, List


@dataclass
class BudgetRequest:
    """预算请求"""
    campaign_id: str = ""
    current_budget: float = 0.0
    target_roas: float = 1.5
    min_budget: float = 50.0
    max_budget: float = 1000.0
    performance_data: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.performance_data is None:
            self.performance_data = {}


@dataclass
class BudgetDecision:
    """预算决策"""
    campaign_id: str = ""
    new_budget: float = 0.0
    old_budget: float = 0.0
    change: float = 0.0
    change_percent: float = 0.0
    reason: str = ""
    confidence: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "new_budget": round(self.new_budget, 2),
            "old_budget": round(self.old_budget, 2),
            "change": round(self.change, 2),
            "change_percent": round(self.change_percent, 2),
            "reason": self.reason,
            "confidence": round(self.confidence, 2),
        }


class BudgetOptimizer:
    """预算优化器"""
    
    def optimize(self, request: BudgetRequest) -> BudgetDecision:
        """优化预算"""
        current = request.current_budget
        roas = request.performance_data.get("roas", 0.0)
        ctr = request.performance_data.get("ctr", 0.0)
        confidence = request.performance_data.get("confidence", 0.0)
        
        # 计算新预算
        new_budget, reason = self._calculate_new_budget(
            current, roas, ctr, confidence,
            request.target_roas,
            request.min_budget,
            request.max_budget,
        )
        
        change = new_budget - current
        change_percent = (change / current) * 100 if current > 0 else 0
        
        return BudgetDecision(
            campaign_id=request.campaign_id,
            new_budget=new_budget,
            old_budget=current,
            change=change,
            change_percent=change_percent,
            reason=reason,
            confidence=min(confidence, 0.95),
        )
    
    def _calculate_new_budget(
        self,
        current: float,
        roas: float,
        ctr: float,
        confidence: float,
        target_roas: float,
        min_budget: float,
        max_budget: float,
    ) -> tuple:
        """计算新预算"""
        new_budget = current
        reason = "No change"
        
        # 自动扩量条件
        if roas >= target_roas and confidence >= 0.8:
            # 逐步扩量
            if roas >= target_roas * 1.5:
                new_budget = min(current * 2, max_budget)
                reason = "ROAS exceeds target by 50% - doubling budget"
            elif roas >= target_roas * 1.2:
                new_budget = min(current * 1.5, max_budget)
                reason = "ROAS exceeds target by 20% - increasing budget by 50%"
            else:
                new_budget = min(current * 1.25, max_budget)
                reason = "ROAS meets target - increasing budget by 25%"
        
        # 自动缩减条件
        elif roas < target_roas * 0.5:
            new_budget = max(current * 0.5, min_budget)
            reason = "ROAS below 50% of target - reducing budget by 50%"
        
        elif ctr < 1.0:
            new_budget = max(current * 0.75, min_budget)
            reason = "Low CTR - reducing budget by 25%"
        
        return new_budget, reason
    
    def optimize_demo(self) -> BudgetDecision:
        """演示预算优化"""
        request = BudgetRequest(
            campaign_id="US_iOS_meta",
            current_budget=200.0,
            target_roas=1.5,
            min_budget=50.0,
            max_budget=1000.0,
            performance_data={"roas": 2.3, "ctr": 5.8, "confidence": 0.92},
        )
        return self.optimize(request)
