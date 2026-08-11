"""Performance Feedback - 表现反馈"""
from dataclasses import dataclass
from typing import Dict, Any, Optional, List


@dataclass
class PerformanceData:
    """表现数据"""
    creative_id: str = ""
    spend: float = 0.0
    impressions: int = 0
    clicks: int = 0
    installs: int = 0
    purchases: int = 0
    revenue: float = 0.0
    platform: str = ""
    date: str = ""
    
    @property
    def ctr(self) -> float:
        if self.impressions == 0:
            return 0.0
        return (self.clicks / self.impressions) * 100
    
    @property
    def ipm(self) -> float:
        if self.impressions == 0:
            return 0.0
        return (self.installs / self.impressions) * 1000
    
    @property
    def purchase_rate(self) -> float:
        if self.installs == 0:
            return 0.0
        return (self.purchases / self.installs) * 100
    
    @property
    def roas(self) -> float:
        if self.spend == 0:
            return 0.0
        return self.revenue / self.spend
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "spend": round(self.spend, 2),
            "impressions": self.impressions,
            "clicks": self.clicks,
            "installs": self.installs,
            "purchases": self.purchases,
            "revenue": round(self.revenue, 2),
            "platform": self.platform,
            "date": self.date,
            "ctr": round(self.ctr, 2),
            "ipm": round(self.ipm, 2),
            "purchase_rate": round(self.purchase_rate, 2),
            "roas": round(self.roas, 2),
        }


@dataclass
class FeedbackResult:
    """反馈结果"""
    creative_id: str = ""
    reward: float = 0.0
    performance: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.performance is None:
            self.performance = {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.creative_id,
            "reward": round(self.reward, 2),
            "performance": self.performance,
        }


class PerformanceFeedback:
    """表现反馈系统"""
    
    def __init__(self):
        self._feedback_history: Dict[str, PerformanceData] = {}
    
    def collect(
        self,
        creative_id: str,
        spend: float = 0.0,
        impressions: int = 0,
        clicks: int = 0,
        installs: int = 0,
        purchases: int = 0,
        revenue: float = 0.0,
        platform: str = "",
        date: str = "",
    ) -> PerformanceData:
        """收集表现数据"""
        data = PerformanceData(
            creative_id=creative_id,
            spend=spend,
            impressions=impressions,
            clicks=clicks,
            installs=installs,
            purchases=purchases,
            revenue=revenue,
            platform=platform,
            date=date,
        )
        
        self._feedback_history[creative_id] = data
        return data
    
    def get_feedback(self, creative_id: str) -> FeedbackResult:
        """获取反馈"""
        if creative_id not in self._feedback_history:
            return FeedbackResult(creative_id=creative_id)
        
        performance = self._feedback_history[creative_id]
        
        # 计算 reward
        reward = self._calculate_reward(performance)
        
        return FeedbackResult(
            creative_id=creative_id,
            reward=reward,
            performance=performance.to_dict(),
        )
    
    def _calculate_reward(self, performance: PerformanceData) -> float:
        """计算奖励"""
        reward = 0.0
        
        # ROAS component
        if performance.roas > 0:
            reward += min(performance.roas / 3, 0.5)
        
        # Purchase Rate component
        reward += min(performance.purchase_rate / 20, 0.3)
        
        # Retention component (simulated from IPM/CTR correlation)
        ipm_quality = min(performance.ipm / 100, 0.2)
        reward += ipm_quality
        
        # Cost penalty
        if performance.spend > 0:
            cost_efficiency = performance.revenue / max(performance.spend, 1)
            if cost_efficiency < 1:
                reward -= min((1 - cost_efficiency) * 0.2, 0.1)
        
        return max(0.0, min(1.0, reward))
    
    def batch_collect(self, data_list: List[Dict[str, Any]]) -> List[PerformanceData]:
        """批量收集"""
        results = []
        for data in data_list:
            result = self.collect(
                creative_id=data.get("creative_id", ""),
                spend=data.get("spend", 0.0),
                impressions=data.get("impressions", 0),
                clicks=data.get("clicks", 0),
                installs=data.get("installs", 0),
                purchases=data.get("purchases", 0),
                revenue=data.get("revenue", 0.0),
                platform=data.get("platform", ""),
                date=data.get("date", ""),
            )
            results.append(result)
        return results
    
    def get_top_performers(self, limit: int = 5) -> List[FeedbackResult]:
        """获取最佳表现"""
        results = []
        for creative_id in self._feedback_history:
            results.append(self.get_feedback(creative_id))
        
        return sorted(results, key=lambda r: r.reward, reverse=True)[:limit]
    
    def collect_demo(self) -> FeedbackResult:
        """生成演示数据"""
        self.collect(
            creative_id="creative_001",
            spend=500.0,
            impressions=50000,
            clicks=2900,
            installs=830,
            purchases=34,
            revenue=1050.0,
            platform="Meta",
            date="2024-01-15",
        )
        
        return self.get_feedback("creative_001")
