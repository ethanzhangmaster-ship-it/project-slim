"""Incremental Lift Calculator - 增量提升计算器"""
from dataclasses import dataclass
from typing import Dict, Any, List


@dataclass
class LiftResult:
    """增量提升结果"""
    creative_id: str = ""
    incremental_lift: float = 0.0
    baseline_revenue: float = 0.0
    incremental_revenue: float = 0.0
    cannibalization: float = 0.0
    net_lift: float = 0.0
    significance: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "incremental_lift": round(self.incremental_lift, 2),
            "baseline_revenue": round(self.baseline_revenue, 2),
            "incremental_revenue": round(self.incremental_revenue, 2),
            "cannibalization": round(self.cannibalization, 2),
            "net_lift": round(self.net_lift, 2),
            "significance": round(self.significance, 2),
        }


class IncrementalLiftCalculator:
    """增量提升计算器"""
    
    def __init__(self):
        self._results: Dict[str, LiftResult] = {}
    
    def calculate(
        self,
        creative_id: str,
        treatment_revenue: float,
        control_revenue: float,
        treatment_spend: float,
        control_spend: float,
        sample_size: int = 1000,
    ) -> LiftResult:
        """计算增量提升"""
        # 计算基线收入
        baseline_revenue = control_revenue
        
        # 计算增量收入
        incremental_revenue = treatment_revenue - control_revenue
        
        # 计算增量提升率
        if control_revenue > 0:
            incremental_lift = incremental_revenue / control_revenue
        else:
            incremental_lift = 0.0
        
        # 计算蚕食
        cannibalization = self._calculate_cannibalization(treatment_revenue, control_revenue)
        
        # 计算净提升
        net_lift = incremental_lift - cannibalization
        
        # 计算显著性
        significance = self._calculate_significance(sample_size, incremental_lift)
        
        result = LiftResult(
            creative_id=creative_id,
            incremental_lift=incremental_lift,
            baseline_revenue=baseline_revenue,
            incremental_revenue=incremental_revenue,
            cannibalization=cannibalization,
            net_lift=net_lift,
            significance=significance,
        )
        
        self._results[creative_id] = result
        return result
    
    def _calculate_cannibalization(self, treatment: float, control: float) -> float:
        """计算蚕食"""
        total = treatment + control
        if total == 0:
            return 0.0
        
        # 假设 10-15% 的蚕食率
        return min(treatment / total * 0.15, 0.1)
    
    def _calculate_significance(self, sample_size: int, lift: float) -> float:
        """计算显著性"""
        # 基于样本量和提升幅度计算
        sample_factor = min(sample_size / 5000, 1.0)
        lift_factor = min(abs(lift) * 2, 1.0)
        
        return sample_factor * lift_factor
    
    def get_lift(self, creative_id: str) -> LiftResult:
        """获取增量提升"""
        return self._results.get(creative_id, LiftResult(creative_id=creative_id))
    
    def calculate_demo(self) -> LiftResult:
        """演示增量提升计算"""
        return self.calculate(
            creative_id="creative_001",
            treatment_revenue=2300,
            control_revenue=1750,
            treatment_spend=500,
            control_spend=500,
            sample_size=5000,
        )
