from dataclasses import dataclass, field
from typing import List, Dict, Any
from datetime import datetime


@dataclass
class CampaignOptimization:
    campaign_id: str
    channel: str
    budget_change_pct: float
    bid_change_pct: float
    target_cpi: float
    expected_installs: int
    notes: str = ""
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class UARecommendation:
    recommendation_id: str
    priority: str
    action: str
    expected_impact: float
    confidence: float
    details: Dict[str, Any] = field(default_factory=dict)


class UABrain:
    """用户获取大脑，负责优化广告投放活动。"""

    def __init__(self):
        self.campaigns: List[Dict[str, Any]] = []
        self.history: List[Dict[str, Any]] = []

    def optimize_campaigns(self, campaigns: List[Dict[str, Any]]) -> List[CampaignOptimization]:
        """基于表现数据优化广告活动。"""
        optimizations = []
        for campaign in campaigns:
            cpi = campaign.get("cpi", 0.0)
            roas = campaign.get("roas", 0.0)

            if roas > 1.5 and cpi < 2.0:
                budget_change = 20.0
                bid_change = 10.0
                notes = "表现优秀，建议扩量"
            elif roas < 0.8:
                budget_change = -15.0
                bid_change = -10.0
                notes = "ROAS 偏低，建议缩减预算"
            else:
                budget_change = 5.0
                bid_change = 0.0
                notes = "表现平稳，小幅测试"

            opt = CampaignOptimization(
                campaign_id=campaign.get("id", "unknown"),
                channel=campaign.get("channel", "unknown"),
                budget_change_pct=budget_change,
                bid_change_pct=bid_change,
                target_cpi=max(cpi * 0.9, 0.5),
                expected_installs=int(campaign.get("installs", 0) * (1 + budget_change / 100)),
                notes=notes,
            )
            optimizations.append(opt)
        self.history.extend([{"action": "optimize", "data": o.__dict__} for o in optimizations])
        return optimizations

    def allocate_budget(self, total_budget: float, channel_performance: Dict[str, float]) -> Dict[str, float]:
        """根据渠道表现分配预算。"""
        total_score = sum(channel_performance.values()) or 1.0
        allocation = {}
        for channel, score in channel_performance.items():
            allocation[channel] = round(total_budget * (score / total_score), 2)
        return allocation

    def analyze_performance(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """分析用户获取整体表现。"""
        cpi = metrics.get("cpi", 0.0)
        roas = metrics.get("roas", 0.0)
        retention_d1 = metrics.get("retention_d1", 0.0)

        status = "healthy"
        if roas < 1.0:
            status = "critical"
        elif roas < 1.2:
            status = "warning"

        return {
            "status": status,
            "cpi_trend": "improving" if cpi < 1.5 else "stable" if cpi < 2.5 else "concerning",
            "retention_quality": "high" if retention_d1 > 0.4 else "medium" if retention_d1 > 0.25 else "low",
            "score": round(roas * 50 + (2.0 - cpi) * 20 + retention_d1 * 100, 2),
            "analyzed_at": datetime.now().isoformat(),
        }

    def suggest_scaling(self, campaign_data: List[Dict[str, Any]]) -> List[UARecommendation]:
        """建议哪些活动值得放大投放。"""
        recommendations = []
        for data in campaign_data:
            roas = data.get("roas", 0.0)
            installs = data.get("installs", 0)
            if roas > 1.5 and installs > 1000:
                rec = UARecommendation(
                    recommendation_id=f"scale_{data['id']}",
                    priority="high",
                    action="increase_budget",
                    expected_impact=round(roas * 0.15, 2),
                    confidence=0.85,
                    details={"current_budget": data.get("budget", 0), "suggested_increase_pct": 30},
                )
                recommendations.append(rec)
        return recommendations
