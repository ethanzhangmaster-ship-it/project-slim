"""Threshold Policy - 异常检测阈值策略"""
from dataclasses import dataclass, field
from typing import Dict, List, Any


@dataclass
class ThresholdPolicy:
    """阈值策略配置"""
    cost_multiplier: float = 1.5
    qa_drop_percent: float = 0.3
    ctr_drop_percent: float = 0.5
    success_rate_min: float = 0.90
    queue_latency_max: float = 300.0
    failure_rate_max: float = 0.10
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "cost_multiplier": self.cost_multiplier,
            "qa_drop_percent": self.qa_drop_percent,
            "ctr_drop_percent": self.ctr_drop_percent,
            "success_rate_min": self.success_rate_min,
            "queue_latency_max": self.queue_latency_max,
            "failure_rate_max": self.failure_rate_max,
        }


class ThresholdManager:
    """阈值管理器"""
    
    def __init__(self, policy: ThresholdPolicy = None):
        self.policy = policy or ThresholdPolicy()
        self._baseline: Dict[str, float] = {}
    
    def set_baseline(self, metric: str, value: float):
        """设置基线值"""
        self._baseline[metric] = value
    
    def get_baseline(self, metric: str) -> float:
        """获取基线值"""
        return self._baseline.get(metric, 0.0)
    
    def check_cost_spike(self, current_cost: float, baseline_cost: float = None) -> bool:
        """检查成本异常"""
        baseline = baseline_cost or self.get_baseline("avg_cost")
        if baseline <= 0:
            return False
        return current_cost > baseline * self.policy.cost_multiplier
    
    def check_qa_drop(self, current_qa: float, baseline_qa: float = None) -> bool:
        """检查 QA 分数下降"""
        baseline = baseline_qa or self.get_baseline("qa_score")
        if baseline <= 0:
            return False
        return current_qa < baseline * (1 - self.policy.qa_drop_percent)
    
    def check_ctr_drop(self, current_ctr: float, baseline_ctr: float = None) -> bool:
        """检查 CTR 下降（创意疲劳）"""
        baseline = baseline_ctr or self.get_baseline("ctr")
        if baseline <= 0:
            return False
        return current_ctr < baseline * (1 - self.policy.ctr_drop_percent)
    
    def check_success_rate(self, success_rate: float) -> bool:
        """检查成功率"""
        return success_rate < self.policy.success_rate_min
    
    def check_queue_latency(self, latency: float) -> bool:
        """检查队列延迟"""
        return latency > self.policy.queue_latency_max
    
    def check_failure_rate(self, failure_rate: float) -> bool:
        """检查失败率"""
        return failure_rate > self.policy.failure_rate_max
