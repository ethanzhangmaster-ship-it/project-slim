"""Creative Attribution Engine - 创意归因引擎"""
from dataclasses import dataclass
from typing import Dict, Any, List


@dataclass
class AttributionInput:
    """归因输入数据"""
    creative_id: str = ""
    campaign: str = ""
    spend: float = 0.0
    installs: int = 0
    purchases: int = 0
    revenue: float = 0.0
    d7_roas: float = 0.0
    d3_roas: float = 0.0
    ctr: float = 0.0
    cvr: float = 0.0


@dataclass
class AttributionResult:
    """归因结果"""
    creative_id: str = ""
    quality_score: float = 0.0
    revenue_contribution: float = 0.0
    incremental_lift: float = 0.0
    winner_probability: float = 0.0
    efficiency_score: float = 0.0
    roi: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "creative": self.creative_id,
            "quality_score": round(self.quality_score, 2),
            "revenue_contribution": round(self.revenue_contribution, 2),
            "incremental_lift": round(self.incremental_lift, 2),
            "winner_probability": round(self.winner_probability, 2),
            "efficiency_score": round(self.efficiency_score, 2),
            "roi": round(self.roi, 2),
        }


class CreativeAttributionEngine:
    """创意归因引擎"""
    
    def __init__(self):
        self._history: Dict[str, List[AttributionInput]] = {}
    
    def track(self, data: AttributionInput):
        """追踪创意表现"""
        if data.creative_id not in self._history:
            self._history[data.creative_id] = []
        self._history[data.creative_id].append(data)
    
    def attribute(self, creative_id: str) -> AttributionResult:
        """计算归因结果"""
        history = self._history.get(creative_id, [])
        
        if not history:
            return AttributionResult(creative_id=creative_id)
        
        latest = history[-1]
        
        # 计算效率分数
        efficiency = self._calculate_efficiency(latest)
        
        # 计算质量分数（基于 CTR 和 CVR）
        quality_score = self._calculate_quality_score(latest)
        
        # 计算增量提升
        incremental_lift = self._calculate_incremental_lift(latest, history)
        
        # 计算赢家概率
        winner_prob = self._calculate_winner_probability(latest)
        
        return AttributionResult(
            creative_id=creative_id,
            quality_score=quality_score,
            revenue_contribution=latest.revenue,
            incremental_lift=incremental_lift,
            winner_probability=winner_prob,
            efficiency_score=efficiency,
            roi=latest.revenue / max(latest.spend, 1),
        )
    
    def _calculate_efficiency(self, data: AttributionInput) -> float:
        """计算效率分数"""
        efficiency = 0.0
        
        # 基于 ROAS
        if data.d7_roas > 0:
            efficiency += min(data.d7_roas / 3, 0.4)
        
        # 基于 IPM (Installs Per Mille)
        if data.spend > 0:
            ipm = (data.installs / data.spend) * 1000
            efficiency += min(ipm / 500, 0.3)
        
        # 基于 Purchase Rate
        if data.installs > 0:
            purchase_rate = (data.purchases / data.installs) * 100
            efficiency += min(purchase_rate / 15, 0.3)
        
        return min(efficiency, 1.0)
    
    def _calculate_quality_score(self, data: AttributionInput) -> float:
        """计算质量分数"""
        score = 0.0
        
        # CTR 分量
        score += min(data.ctr / 10, 0.4)
        
        # CVR 分量
        score += min(data.cvr / 50, 0.4)
        
        # 收入稳定分量
        if data.revenue > 0 and data.spend > 0:
            score += min(data.revenue / (data.spend * 2), 0.2)
        
        return min(score, 1.0)
    
    def _calculate_incremental_lift(self, latest: AttributionInput, history: List[AttributionInput]) -> float:
        """计算增量提升"""
        if len(history) < 2:
            return 0.3  # 默认值
        
        prev = history[-2]
        
        revenue_lift = 0.0
        if prev.revenue > 0:
            revenue_lift = (latest.revenue - prev.revenue) / prev.revenue
        
        spend_lift = 0.0
        if prev.spend > 0:
            spend_lift = (latest.spend - prev.spend) / prev.spend
        
        # 增量提升 = 收入增长 - 成本增长
        incremental = revenue_lift - spend_lift
        return max(0.0, min(incremental + 0.5, 1.0))
    
    def _calculate_winner_probability(self, data: AttributionInput) -> float:
        """计算赢家概率"""
        prob = 0.0
        
        # ROAS 阈值
        if data.d7_roas >= 1.5:
            prob += 0.4
        elif data.d7_roas >= 1.0:
            prob += 0.2
        
        # 收入贡献
        if data.revenue > data.spend * 1.5:
            prob += 0.3
        
        # 质量分数
        prob += min(data.ctr / 15, 0.3)
        
        return min(prob, 1.0)
    
    def attribute_demo(self) -> AttributionResult:
        """演示归因"""
        data = AttributionInput(
            creative_id="creative_001",
            campaign="US_ios_meta",
            spend=500,
            installs=1200,
            purchases=80,
            revenue=2300,
            d7_roas=0.62,
            d3_roas=0.85,
            ctr=5.8,
            cvr=4.2,
        )
        self.track(data)
        return self.attribute("creative_001")
