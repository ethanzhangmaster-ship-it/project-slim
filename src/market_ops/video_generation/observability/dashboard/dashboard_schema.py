"""Dashboard Schema - 仪表板数据结构定义"""
from dataclasses import dataclass, field
from typing import Dict, List, Any
from datetime import datetime


@dataclass
class GenerationSummary:
    """生成统计摘要"""
    total: int = 0
    success: int = 0
    failed: int = 0
    success_rate: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total": self.total,
            "success": self.success,
            "failed": self.failed,
            "success_rate": round(self.success_rate, 3),
        }


@dataclass
class QueueSummary:
    """队列状态摘要"""
    pending: int = 0
    processing: int = 0
    retrying: int = 0
    dead_letter: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "pending": self.pending,
            "processing": self.processing,
            "retrying": self.retrying,
            "dead_letter": self.dead_letter,
        }


@dataclass
class CostSummary:
    """成本摘要"""
    total: float = 0.0
    avg_cost: float = 0.0
    success_cost: float = 0.0
    failed_cost: float = 0.0
    budget_remaining: float = 0.0
    budget_usage_percent: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total": round(self.total, 2),
            "avg_cost": round(self.avg_cost, 3),
            "success_cost": round(self.success_cost, 3),
            "failed_cost": round(self.failed_cost, 3),
            "budget_remaining": round(self.budget_remaining, 2),
            "budget_usage_percent": round(self.budget_usage_percent, 1),
        }


@dataclass
class PlatformSummary:
    """平台统计摘要"""
    platform: str = ""
    count: int = 0
    cost: float = 0.0
    avg_cost: float = 0.0
    success_rate: float = 0.0
    avg_time: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "platform": self.platform,
            "count": self.count,
            "cost": round(self.cost, 2),
            "avg_cost": round(self.avg_cost, 3),
            "success_rate": round(self.success_rate, 3),
            "avg_time": round(self.avg_time, 1),
        }


@dataclass
class DailyDashboard:
    """每日仪表板数据"""
    date: str = ""
    generation: GenerationSummary = field(default_factory=GenerationSummary)
    queue: QueueSummary = field(default_factory=QueueSummary)
    cost: CostSummary = field(default_factory=CostSummary)
    platforms: List[PlatformSummary] = field(default_factory=list)
    top_creatives: List[Dict[str, Any]] = field(default_factory=list)
    alerts: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "generation": self.generation.to_dict(),
            "queue": self.queue.to_dict(),
            "cost": self.cost.to_dict(),
            "platforms": [p.to_dict() for p in self.platforms],
            "top_creatives": self.top_creatives,
            "alerts": self.alerts,
        }
