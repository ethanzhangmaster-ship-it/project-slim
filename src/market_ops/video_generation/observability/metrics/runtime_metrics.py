"""Runtime Metrics - 运行指标统计"""
from dataclasses import dataclass, field
from typing import Dict, List, Any
from datetime import datetime


@dataclass
class RuntimeMetrics:
    """运行时指标"""
    date: str = ""
    generation_count: int = 0
    success_count: int = 0
    failed_count: int = 0
    success_rate: float = 0.0
    failure_rate: float = 0.0
    avg_generation_time: float = 0.0
    queue_latency: float = 0.0
    worker_utilization: float = 0.0
    max_workers: int = 0
    active_workers: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "generation_count": self.generation_count,
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "success_rate": round(self.success_rate, 3),
            "failure_rate": round(self.failure_rate, 3),
            "avg_generation_time": round(self.avg_generation_time, 1),
            "queue_latency": round(self.queue_latency, 1),
            "worker_utilization": round(self.worker_utilization, 3),
            "max_workers": self.max_workers,
            "active_workers": self.active_workers,
        }


class RuntimeMetricsCollector:
    """运行时指标收集器"""
    
    def __init__(self):
        self._metrics: List[RuntimeMetrics] = []
        self._current: RuntimeMetrics = RuntimeMetrics(date=datetime.now().strftime("%Y-%m-%d"))
    
    def record_generation(self, success: bool, duration: float = 0.0):
        """记录一次生成"""
        self._current.generation_count += 1
        if success:
            self._current.success_count += 1
        else:
            self._current.failed_count += 1
        
        # 更新平均生成时间
        if duration > 0:
            n = self._current.generation_count
            self._current.avg_generation_time = (
                (self._current.avg_generation_time * (n - 1) + duration) / n
            )
    
    def record_worker_stats(self, active: int, max_workers: int):
        """记录 worker 状态"""
        self._current.active_workers = active
        self._current.max_workers = max_workers
        self._current.worker_utilization = active / max_workers if max_workers > 0 else 0.0
    
    def record_queue_latency(self, latency: float):
        """记录队列延迟"""
        self._current.queue_latency = latency
    
    def finalize(self) -> RuntimeMetrics:
        """完成当前统计周期"""
        total = self._current.generation_count
        self._current.success_rate = self._current.success_count / total if total > 0 else 0.0
        self._current.failure_rate = self._current.failed_count / total if total > 0 else 0.0
        
        self._metrics.append(self._current)
        return self._current
    
    def get_current(self) -> RuntimeMetrics:
        """获取当前指标"""
        return self._current
    
    def get_history(self, days: int = 7) -> List[RuntimeMetrics]:
        """获取历史指标"""
        return self._metrics[-days:]
    
    def get_summary(self) -> Dict[str, Any]:
        """获取摘要"""
        return self._current.to_dict()
