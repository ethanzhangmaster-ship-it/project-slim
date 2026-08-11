"""Revenue Mapper - 收入映射器"""
from dataclasses import dataclass
from typing import Dict, Any, List


@dataclass
class RevenueMapping:
    """收入映射"""
    creative_id: str = ""
    total_revenue: float = 0.0
    organic_revenue: float = 0.0
    paid_revenue: float = 0.0
    attributable_revenue: float = 0.0
    cannibalization_rate: float = 0.0
    roi: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "total_revenue": round(self.total_revenue, 2),
            "organic_revenue": round(self.organic_revenue, 2),
            "paid_revenue": round(self.paid_revenue, 2),
            "attributable_revenue": round(self.attributable_revenue, 2),
            "cannibalization_rate": round(self.cannibalization_rate, 2),
            "roi": round(self.roi, 2),
        }


class RevenueMapper:
    """收入映射器"""
    
    def __init__(self):
        self._mappings: Dict[str, RevenueMapping] = {}
    
    def map_revenue(
        self,
        creative_id: str,
        total_revenue: float,
        organic_revenue: float,
        paid_revenue: float,
        spend: float = 0.0,
    ) -> RevenueMapping:
        """映射收入"""
        # 计算可归因收入
        attributable = paid_revenue * 0.85  # 85% 归因率
        
        # 计算蚕食率
        cannibalization = 0.0
        if total_revenue > 0:
            cannibalization = min(organic_revenue / total_revenue * 0.3, 0.2)
        
        # 计算 ROI
        roi = attributable / max(spend, 1) if spend > 0 else 0.0
        
        mapping = RevenueMapping(
            creative_id=creative_id,
            total_revenue=total_revenue,
            organic_revenue=organic_revenue,
            paid_revenue=paid_revenue,
            attributable_revenue=attributable,
            cannibalization_rate=cannibalization,
            roi=roi,
        )
        
        self._mappings[creative_id] = mapping
        return mapping
    
    def get_mapping(self, creative_id: str) -> RevenueMapping:
        """获取映射"""
        return self._mappings.get(creative_id, RevenueMapping(creative_id=creative_id))
    
    def get_top_revenue_creatives(self, limit: int = 5) -> List[RevenueMapping]:
        """获取收入最高的创意"""
        return sorted(
            self._mappings.values(),
            key=lambda m: m.attributable_revenue,
            reverse=True
        )[:limit]
    
    def map_demo(self) -> RevenueMapping:
        """演示收入映射"""
        return self.map_revenue(
            creative_id="creative_001",
            total_revenue=5000,
            organic_revenue=1500,
            paid_revenue=3500,
            spend=1200,
        )
