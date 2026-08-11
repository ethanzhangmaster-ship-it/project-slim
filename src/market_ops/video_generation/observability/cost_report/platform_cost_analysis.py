"""Platform Cost Analysis - 平台成本分析"""
from dataclasses import dataclass, field
from typing import Dict, List, Any
from datetime import datetime


@dataclass
class PlatformCost:
    """单个平台成本"""
    platform: str = ""
    count: int = 0
    cost: float = 0.0
    avg_cost: float = 0.0
    success_rate: float = 0.0
    avg_time: float = 0.0
    efficiency_score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "platform": self.platform,
            "count": self.count,
            "cost": round(self.cost, 2),
            "avg_cost": round(self.avg_cost, 3),
            "success_rate": round(self.success_rate, 3),
            "avg_time": round(self.avg_time, 1),
            "efficiency_score": round(self.efficiency_score, 1),
        }


@dataclass
class PlatformCostAnalysis:
    """平台成本分析报告"""
    date: str = ""
    platforms: List[PlatformCost] = field(default_factory=list)
    total_cost: float = 0.0
    total_count: int = 0
    recommendation: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "platforms": [p.to_dict() for p in self.platforms],
            "total_cost": round(self.total_cost, 2),
            "total_count": self.total_count,
            "recommendation": self.recommendation,
        }


class PlatformCostAnalyzer:
    """平台成本分析器"""
    
    def __init__(self):
        self._threshold_efficiency = 1.0
    
    def analyze(
        self,
        platform_data: List[Dict[str, Any]],
        date: str = None,
    ) -> PlatformCostAnalysis:
        """分析平台成本效率"""
        date = date or datetime.now().strftime("%Y-%m-%d")
        
        platforms = []
        total_cost = 0.0
        total_count = 0
        
        for data in platform_data:
            count = data.get("count", 0)
            cost = data.get("cost", 0.0)
            avg_cost = cost / count if count > 0 else 0.0
            
            # 效率评分 = 成功率 / 平均成本
            success_rate = data.get("success_rate", 0.0)
            efficiency = (success_rate / avg_cost * 100) if avg_cost > 0 else 0.0
            
            platform = PlatformCost(
                platform=data.get("platform", ""),
                count=count,
                cost=cost,
                avg_cost=avg_cost,
                success_rate=success_rate,
                avg_time=data.get("avg_time", 0.0),
                efficiency_score=efficiency,
            )
            platforms.append(platform)
            total_cost += cost
            total_count += count
        
        # 生成推荐
        recommendation = self._generate_recommendation(platforms)
        
        return PlatformCostAnalysis(
            date=date,
            platforms=sorted(platforms, key=lambda p: p.efficiency_score, reverse=True),
            total_cost=total_cost,
            total_count=total_count,
            recommendation=recommendation,
        )
    
    def _generate_recommendation(self, platforms: List[PlatformCost]) -> str:
        """生成平台分配建议"""
        if not platforms:
            return "No data available"
        
        # 找出效率最高和最低的平台
        best = max(platforms, key=lambda p: p.efficiency_score)
        worst = min(platforms, key=lambda p: p.efficiency_score)
        
        if best.efficiency_score > worst.efficiency_score * 2:
            return f"Increase {best.platform} allocation by 20%, reduce {worst.platform}"
        
        return f"Maintain current distribution, {best.platform} is most efficient"
    
    def to_markdown_table(self, analysis: PlatformCostAnalysis) -> str:
        """输出 Markdown 表格"""
        lines = [
            "## Platform Cost Analysis",
            "",
            f"**Date:** {analysis.date}",
            "",
            "| Platform | Count | Cost | Avg | Rate | Time | Efficiency |",
            "|----------|-------|------|-----|------|------|------------|",
        ]
        for p in analysis.platforms:
            lines.append(
                f"| {p.platform} | {p.count} | ${p.cost:.2f} | ${p.avg_cost:.3f} | "
                f"{p.success_rate*100:.0f}% | {p.avg_time:.0f}s | {p.efficiency_score:.1f} |"
            )
        
        lines.extend([
            "",
            f"**Total:** {analysis.total_count} videos, ${analysis.total_cost:.2f}",
            "",
            f"**Recommendation:** {analysis.recommendation}",
        ])
        
        return "\n".join(lines)
