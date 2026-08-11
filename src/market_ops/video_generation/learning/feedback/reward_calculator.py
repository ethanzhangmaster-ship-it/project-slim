"""Reward Calculator - 奖励计算器"""
from dataclasses import dataclass
from typing import Dict, Any, List


@dataclass
class RewardScore:
    """奖励分数"""
    creative_id: str = ""
    reward: float = 0.0
    roas_component: float = 0.0
    purchase_component: float = 0.0
    retention_component: float = 0.0
    cost_component: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "reward": round(self.reward, 2),
            "roas_component": round(self.roas_component, 2),
            "purchase_component": round(self.purchase_component, 2),
            "retention_component": round(self.retention_component, 2),
            "cost_component": round(self.cost_component, 2),
        }


class RewardCalculator:
    """奖励计算器
    
    Reward = ROAS + Purchase Rate + Retention - Cost
    """
    
    def __init__(self):
        self._history: Dict[str, RewardScore] = {}
    
    def calculate(
        self,
        creative_id: str,
        roas: float = 0.0,
        purchase_rate: float = 0.0,
        retention: float = 0.0,
        cost: float = 0.0,
    ) -> RewardScore:
        """计算奖励
        
        Args:
            creative_id: 创意 ID
            roas: Return On Ad Spend
            purchase_rate: Purchase Rate (%)
            retention: 7-day Retention (%)
            cost: Cost per 1000 impressions ($)
        
        Returns:
            RewardScore
        """
        # 标准化各指标
        roas_norm = min(roas / 3, 0.4)
        purchase_norm = min(purchase_rate / 10, 0.3)
        retention_norm = min(retention / 50, 0.2)
        cost_norm = min(cost / 10, 0.1)
        
        # 计算奖励
        reward = roas_norm + purchase_norm + retention_norm - cost_norm
        
        score = RewardScore(
            creative_id=creative_id,
            reward=max(0.0, min(1.0, reward)),
            roas_component=roas_norm,
            purchase_component=purchase_norm,
            retention_component=retention_norm,
            cost_component=cost_norm,
        )
        
        self._history[creative_id] = score
        return score
    
    def calculate_from_performance(self, performance: Dict[str, Any]) -> RewardScore:
        """从表现数据计算奖励"""
        return self.calculate(
            creative_id=performance.get("creative_id", ""),
            roas=performance.get("roas", 0.0),
            purchase_rate=performance.get("purchase_rate", 0.0),
            retention=performance.get("retention", 0.0),
            cost=performance.get("cost", 0.0),
        )
    
    def get_top_rewards(self, limit: int = 5) -> List[RewardScore]:
        """获取最高奖励"""
        return sorted(self._history.values(), key=lambda r: r.reward, reverse=True)[:limit]
    
    def calculate_demo(self) -> RewardScore:
        """生成演示数据"""
        return self.calculate(
            creative_id="creative_A",
            roas=2.1,
            purchase_rate=4.5,
            retention=35.0,
            cost=2.5,
        )
