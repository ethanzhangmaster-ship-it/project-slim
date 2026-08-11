"""Performance Metrics - 创意表现指标统计"""
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime


@dataclass
class PerformanceMetric:
    """创意表现指标"""
    creative_id: str = ""
    date: str = ""
    ctr: float = 0.0  # Click Through Rate (%)
    ipm: float = 0.0  # Installs Per Mille
    cvr: float = 0.0  # Conversion Rate (%)
    purchase_rate: float = 0.0  # Purchase Rate (%)
    roas_d7: float = 0.0  # 7-Day ROAS
    spend: float = 0.0  # Total spend
    impressions: int = 0
    clicks: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "date": self.date,
            "ctr": round(self.ctr, 2),
            "ipm": round(self.ipm, 1),
            "cvr": round(self.cvr, 2),
            "purchase_rate": round(self.purchase_rate, 2),
            "roas_d7": round(self.roas_d7, 2),
            "spend": round(self.spend, 2),
            "impressions": self.impressions,
            "clicks": self.clicks,
        }
    
    def is_winner(self, threshold: Dict[str, float] = None) -> bool:
        """判断是否为 winner"""
        default_threshold = {"ctr": 3.0, "ipm": 50, "purchase_rate": 2.0, "roas_d7": 1.2}
        threshold = threshold or default_threshold
        
        return (
            self.ctr >= threshold.get("ctr", 3.0)
            and self.ipm >= threshold.get("ipm", 50)
        )


@dataclass
class CreativePerformance:
    """创意综合表现"""
    creative_id: str = ""
    avg_ctr: float = 0.0
    avg_ipm: float = 0.0
    avg_purchase_rate: float = 0.0
    avg_roas_d7: float = 0.0
    total_spend: float = 0.0
    total_impressions: int = 0
    days_tracked: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "avg_ctr": round(self.avg_ctr, 2),
            "avg_ipm": round(self.avg_ipm, 1),
            "avg_purchase_rate": round(self.avg_purchase_rate, 2),
            "avg_roas_d7": round(self.avg_roas_d7, 2),
            "total_spend": round(self.total_spend, 2),
            "total_impressions": self.total_impressions,
            "days_tracked": self.days_tracked,
        }


class PerformanceMetricsCollector:
    """表现指标收集器"""
    
    def __init__(self):
        self._metrics: List[PerformanceMetric] = []
        self._by_creative: Dict[str, List[PerformanceMetric]] = {}
    
    def record(self, metric: PerformanceMetric):
        """记录表现指标"""
        self._metrics.append(metric)
        
        if metric.creative_id not in self._by_creative:
            self._by_creative[metric.creative_id] = []
        self._by_creative[metric.creative_id].append(metric)
    
    def get_creative_performance(self, creative_id: str) -> Optional[CreativePerformance]:
        """获取创意综合表现"""
        metrics = self._by_creative.get(creative_id, [])
        if not metrics:
            return None
        
        return CreativePerformance(
            creative_id=creative_id,
            avg_ctr=sum(m.ctr for m in metrics) / len(metrics),
            avg_ipm=sum(m.ipm for m in metrics) / len(metrics),
            avg_purchase_rate=sum(m.purchase_rate for m in metrics) / len(metrics),
            avg_roas_d7=sum(m.roas_d7 for m in metrics) / len(metrics),
            total_spend=sum(m.spend for m in metrics),
            total_impressions=sum(m.impressions for m in metrics),
            days_tracked=len(metrics),
        )
    
    def get_winners(self, limit: int = 10) -> List[CreativePerformance]:
        """获取 winner 列表"""
        performances = []
        for creative_id in self._by_creative:
            perf = self.get_creative_performance(creative_id)
            if perf and perf.avg_ctr >= 3.0:
                performances.append(perf)
        
        return sorted(performances, key=lambda p: p.avg_ctr, reverse=True)[:limit]
    
    def get_fatigued_creatives(self, days: int = 7, ctr_drop: float = 0.5) -> List[str]:
        """获取疲劳创意（CTR 下降超过阈值）"""
        fatigued = []
        
        for creative_id, metrics in self._by_creative.items():
            if len(metrics) < 2:
                continue
            
            recent = sorted(metrics, key=lambda m: m.date)[-days:]
            if len(recent) >= 2:
                early_avg = sum(m.ctr for m in recent[:len(recent)//2]) / (len(recent)//2)
                late_avg = sum(m.ctr for m in recent[len(recent)//2:]) / (len(recent) - len(recent)//2)
                
                if early_avg > 0 and late_avg / early_avg < ctr_drop:
                    fatigued.append(creative_id)
        
        return fatigued
    
    def get_daily_summary(self, date: str = None) -> Dict[str, Any]:
        """获取每日汇总"""
        date = date or datetime.now().strftime("%Y-%m-%d")
        daily = [m for m in self._metrics if m.date == date]
        
        if not daily:
            return {"date": date, "count": 0}
        
        return {
            "date": date,
            "count": len(daily),
            "avg_ctr": round(sum(m.ctr for m in daily) / len(daily), 2),
            "avg_ipm": round(sum(m.ipm for m in daily) / len(daily), 1),
            "avg_purchase_rate": round(sum(m.purchase_rate for m in daily) / len(daily), 2),
            "total_spend": round(sum(m.spend for m in daily), 2),
            "total_impressions": sum(m.impressions for m in daily),
        }
