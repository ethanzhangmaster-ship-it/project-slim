"""Allocation Engine - 预算分配引擎"""
from dataclasses import dataclass
from typing import Dict, Any, List


@dataclass
class AllocationItem:
    """分配项"""
    campaign_id: str = ""
    allocation: float = 0.0
    percentage: float = 0.0
    priority: int = 0
    reason: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "allocation": round(self.allocation, 2),
            "percentage": round(self.percentage, 2),
            "priority": self.priority,
            "reason": self.reason,
        }


class AllocationEngine:
    """预算分配引擎"""
    
    def allocate(self, total_budget: float, campaigns: List[Dict[str, Any]]) -> List[AllocationItem]:
        """分配预算"""
        if not campaigns:
            return []
        
        # 计算优先级分数
        scored_campaigns = []
        for campaign in campaigns:
            score = self._calculate_priority(campaign)
            scored_campaigns.append((campaign, score))
        
        # 按优先级排序
        scored_campaigns.sort(key=lambda x: x[1], reverse=True)
        
        # 分配预算
        allocations = []
        remaining_budget = total_budget
        
        for i, (campaign, score) in enumerate(scored_campaigns):
            campaign_id = campaign.get("campaign_id", "")
            
            # 根据优先级分配
            if i == 0 and score > 0.7:
                # Top performer
                allocation = min(remaining_budget * 0.4, campaign.get("max_budget", remaining_budget))
                reason = "Top performer - 40% allocation"
            elif i <= 2 and score > 0.5:
                # Strong performers
                allocation = min(remaining_budget * 0.25, campaign.get("max_budget", remaining_budget))
                reason = "Strong performer - 25% allocation"
            else:
                allocation = min(remaining_budget * 0.15, campaign.get("max_budget", remaining_budget))
                reason = "Balanced allocation"
            
            allocation = max(allocation, campaign.get("min_budget", 0))
            percentage = (allocation / total_budget) * 100
            
            allocations.append(AllocationItem(
                campaign_id=campaign_id,
                allocation=allocation,
                percentage=percentage,
                priority=i + 1,
                reason=reason,
            ))
            
            remaining_budget -= allocation
            
            if remaining_budget <= 0:
                break
        
        return allocations
    
    def _calculate_priority(self, campaign: Dict[str, Any]) -> float:
        """计算优先级"""
        score = 0.0
        
        # ROAS
        roas = campaign.get("roas", 0.0)
        score += min(roas / 3, 0.35)
        
        # CTR
        ctr = campaign.get("ctr", 0.0)
        score += min(ctr / 10, 0.25)
        
        # Confidence
        confidence = campaign.get("confidence", 0.0)
        score += confidence * 0.2
        
        # Trend
        trend = campaign.get("trend", "stable")
        if trend == "up":
            score += 0.2
        
        return min(score, 1.0)
    
    def allocate_demo(self) -> List[AllocationItem]:
        """演示预算分配"""
        campaigns = [
            {"campaign_id": "c001", "roas": 2.3, "ctr": 5.8, "confidence": 0.92, "trend": "up", "min_budget": 100, "max_budget": 500},
            {"campaign_id": "c002", "roas": 1.8, "ctr": 4.2, "confidence": 0.85, "trend": "stable", "min_budget": 50, "max_budget": 300},
            {"campaign_id": "c003", "roas": 1.2, "ctr": 3.1, "confidence": 0.70, "trend": "stable", "min_budget": 50, "max_budget": 200},
            {"campaign_id": "c004", "roas": 0.8, "ctr": 1.5, "confidence": 0.50, "trend": "down", "min_budget": 50, "max_budget": 150},
        ]
        
        return self.allocate(1000.0, campaigns)
