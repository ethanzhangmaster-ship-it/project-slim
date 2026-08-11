"""Creative Metrics - 创意指标统计"""
from dataclasses import dataclass, field
from typing import Dict, List, Any
from datetime import datetime


@dataclass
class CreativeMetric:
    """单个创意指标"""
    creative_id: str = ""
    generated_at: str = ""
    platform: str = ""
    qa_score: float = 0.0
    visual_score: float = 0.0
    hook_score: float = 0.0
    conversion_score: float = 0.0
    passed_qa: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "generated_at": self.generated_at,
            "platform": self.platform,
            "qa_score": round(self.qa_score, 1),
            "visual_score": round(self.visual_score, 1),
            "hook_score": round(self.hook_score, 1),
            "conversion_score": round(self.conversion_score, 1),
            "passed_qa": self.passed_qa,
        }


@dataclass
class CreativeDailyMetrics:
    """每日创意指标汇总"""
    date: str = ""
    creative_generated: int = 0
    creative_pass_qa: int = 0
    creative_rejected: int = 0
    winner_count: int = 0
    avg_qa_score: float = 0.0
    avg_visual_score: float = 0.0
    avg_hook_score: float = 0.0
    avg_conversion_score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "creative_generated": self.creative_generated,
            "creative_pass_qa": self.creative_pass_qa,
            "creative_rejected": self.creative_rejected,
            "winner_count": self.winner_count,
            "avg_qa_score": round(self.avg_qa_score, 1),
            "avg_visual_score": round(self.avg_visual_score, 1),
            "avg_hook_score": round(self.avg_hook_score, 1),
            "avg_conversion_score": round(self.avg_conversion_score, 1),
        }


class CreativeMetricsCollector:
    """创意指标收集器"""
    
    def __init__(self):
        self._creatives: List[CreativeMetric] = []
        self._daily: CreativeDailyMetrics = CreativeDailyMetrics(
            date=datetime.now().strftime("%Y-%m-%d")
        )
    
    def record_creative(self, metric: CreativeMetric):
        """记录一个创意的 QA 结果"""
        self._creatives.append(metric)
        self._daily.creative_generated += 1
        
        if metric.passed_qa:
            self._daily.creative_pass_qa += 1
        else:
            self._daily.creative_rejected += 1
        
        # 更新平均分
        n = self._daily.creative_generated
        self._daily.avg_qa_score = self._update_avg(self._daily.avg_qa_score, metric.qa_score, n)
        self._daily.avg_visual_score = self._update_avg(self._daily.avg_visual_score, metric.visual_score, n)
        self._daily.avg_hook_score = self._update_avg(self._daily.avg_hook_score, metric.hook_score, n)
        self._daily.avg_conversion_score = self._update_avg(
            self._daily.avg_conversion_score, metric.conversion_score, n
        )
    
    def record_winner(self, creative_id: str):
        """记录一个 winner"""
        self._daily.winner_count += 1
    
    def _update_avg(self, current: float, new: float, n: int) -> float:
        """更新移动平均"""
        return (current * (n - 1) + new) / n if n > 0 else new
    
    def get_daily_metrics(self) -> CreativeDailyMetrics:
        """获取每日指标"""
        return self._daily
    
    def get_creatives(self, passed_only: bool = False) -> List[CreativeMetric]:
        """获取创意列表"""
        if passed_only:
            return [c for c in self._creatives if c.passed_qa]
        return self._creatives
    
    def get_top_creatives(self, metric: str = "qa_score", limit: int = 10) -> List[CreativeMetric]:
        """获取 top 创意"""
        sorted_creatives = sorted(
            self._creatives,
            key=lambda c: getattr(c, metric, 0),
            reverse=True,
        )
        return sorted_creatives[:limit]
