"""Cohort Analyzer - 队列分析器"""
from dataclasses import dataclass
from typing import Dict, Any, List
from collections import defaultdict


@dataclass
class CohortData:
    """队列数据"""
    cohort_id: str = ""
    date: str = ""
    installs: int = 0
    d1_retention: float = 0.0
    d7_retention: float = 0.0
    d1_purchases: int = 0
    d7_purchases: int = 0
    d1_revenue: float = 0.0
    d7_revenue: float = 0.0
    creative_ids: List[str] = None
    
    def __post_init__(self):
        if self.creative_ids is None:
            self.creative_ids = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "cohort_id": self.cohort_id,
            "date": self.date,
            "installs": self.installs,
            "d1_retention": round(self.d1_retention, 2),
            "d7_retention": round(self.d7_retention, 2),
            "d1_purchases": self.d1_purchases,
            "d7_purchases": self.d7_purchases,
            "d1_revenue": round(self.d1_revenue, 2),
            "d7_revenue": round(self.d7_revenue, 2),
            "creative_count": len(self.creative_ids),
        }


@dataclass
class CohortAnalysis:
    """队列分析结果"""
    cohort_id: str = ""
    avg_d1_retention: float = 0.0
    avg_d7_retention: float = 0.0
    avg_ltv: float = 0.0
    cohort_quality: float = 0.0
    trend: str = "stable"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "cohort_id": self.cohort_id,
            "avg_d1_retention": round(self.avg_d1_retention, 2),
            "avg_d7_retention": round(self.avg_d7_retention, 2),
            "avg_ltv": round(self.avg_ltv, 2),
            "cohort_quality": round(self.cohort_quality, 2),
            "trend": self.trend,
        }


class CohortAnalyzer:
    """队列分析器"""
    
    def __init__(self):
        self._cohorts: Dict[str, List[CohortData]] = {}
    
    def add_cohort(self, data: CohortData):
        """添加队列数据"""
        if data.cohort_id not in self._cohorts:
            self._cohorts[data.cohort_id] = []
        self._cohorts[data.cohort_id].append(data)
    
    def analyze(self, cohort_id: str) -> CohortAnalysis:
        """分析队列"""
        cohorts = self._cohorts.get(cohort_id, [])
        
        if not cohorts:
            return CohortAnalysis(cohort_id=cohort_id)
        
        # 计算平均值
        avg_d1 = sum(c.d1_retention for c in cohorts) / len(cohorts)
        avg_d7 = sum(c.d7_retention for c in cohorts) / len(cohorts)
        avg_ltv = sum(c.d7_revenue for c in cohorts) / max(sum(c.installs for c in cohorts), 1)
        
        # 计算队列质量
        quality = self._calculate_cohort_quality(avg_d1, avg_d7, avg_ltv)
        
        # 检测趋势
        trend = self._detect_trend(cohorts)
        
        return CohortAnalysis(
            cohort_id=cohort_id,
            avg_d1_retention=avg_d1,
            avg_d7_retention=avg_d7,
            avg_ltv=avg_ltv,
            cohort_quality=quality,
            trend=trend,
        )
    
    def _calculate_cohort_quality(self, d1: float, d7: float, ltv: float) -> float:
        """计算队列质量"""
        score = 0.0
        
        # D1 Retention
        score += min(d1 / 40, 0.3)
        
        # D7 Retention
        score += min(d7 / 20, 0.3)
        
        # LTV
        score += min(ltv / 5, 0.4)
        
        return min(score, 1.0)
    
    def _detect_trend(self, cohorts: List[CohortData]) -> str:
        """检测趋势"""
        if len(cohorts) < 2:
            return "stable"
        
        recent = cohorts[-3:]
        earlier = cohorts[:-3] if len(cohorts) > 3 else cohorts[:-1]
        
        recent_d7 = sum(c.d7_retention for c in recent) / len(recent)
        earlier_d7 = sum(c.d7_retention for c in earlier) / len(earlier) if earlier else recent_d7
        
        if earlier_d7 == 0:
            return "stable"
        
        change = (recent_d7 - earlier_d7) / earlier_d7
        
        if change > 0.1:
            return "up"
        elif change < -0.1:
            return "down"
        else:
            return "stable"
    
    def analyze_by_creative(self, creative_id: str) -> CohortAnalysis:
        """按创意分析队列"""
        all_cohorts = []
        for cohort_list in self._cohorts.values():
            for cohort in cohort_list:
                if creative_id in cohort.creative_ids:
                    all_cohorts.append(cohort)
        
        if not all_cohorts:
            return CohortAnalysis(cohort_id=f"creative_{creative_id}")
        
        avg_d1 = sum(c.d1_retention for c in all_cohorts) / len(all_cohorts)
        avg_d7 = sum(c.d7_retention for c in all_cohorts) / len(all_cohorts)
        avg_ltv = sum(c.d7_revenue for c in all_cohorts) / max(sum(c.installs for c in all_cohorts), 1)
        
        return CohortAnalysis(
            cohort_id=f"creative_{creative_id}",
            avg_d1_retention=avg_d1,
            avg_d7_retention=avg_d7,
            avg_ltv=avg_ltv,
            cohort_quality=self._calculate_cohort_quality(avg_d1, avg_d7, avg_ltv),
            trend=self._detect_trend(all_cohorts),
        )
    
    def analyze_demo(self) -> CohortAnalysis:
        """演示队列分析"""
        for i in range(7):
            self.add_cohort(CohortData(
                cohort_id="US_iOS",
                date=f"2024-01-{str(i+1).zfill(2)}",
                installs=500 + i * 50,
                d1_retention=35 + i * 0.5,
                d7_retention=18 + i * 0.3,
                d1_purchases=20 + i * 2,
                d7_purchases=45 + i * 3,
                d1_revenue=150 + i * 15,
                d7_revenue=450 + i * 40,
                creative_ids=["creative_001", "creative_002"],
            ))
        
        return self.analyze("US_iOS")
