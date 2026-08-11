"""Metrics Collector"""
from typing import Dict, Any
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class PlatformMetrics:
    platform: str = ""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_latency: float = 0.0
    avg_cost: float = 0.0
    last_error: str = ""


class MetricsCollector:
    """指标收集器"""

    def __init__(self):
        self._metrics: Dict[str, PlatformMetrics] = {}
        self._start_time = datetime.now()

    def record_request(self, platform: str, success: bool, latency: float = 0.0, cost: float = 0.0, error: str = ""):
        if platform not in self._metrics:
            self._metrics[platform] = PlatformMetrics(platform=platform)

        metrics = self._metrics[platform]
        metrics.total_requests += 1
        if success:
            metrics.successful_requests += 1
        else:
            metrics.failed_requests += 1
            metrics.last_error = error

        if latency > 0:
            metrics.avg_latency = (metrics.avg_latency * (metrics.total_requests - 1) + latency) / metrics.total_requests
        if cost > 0:
            metrics.avg_cost = (metrics.avg_cost * (metrics.total_requests - 1) + cost) / metrics.total_requests

    def get_platform_metrics(self, platform: str) -> PlatformMetrics:
        return self._metrics.get(platform, PlatformMetrics(platform=platform))

    def get_all_metrics(self) -> Dict[str, PlatformMetrics]:
        return self._metrics

    def get_aggregated_stats(self) -> Dict[str, Any]:
        total_requests = sum(m.total_requests for m in self._metrics.values())
        successful_requests = sum(m.successful_requests for m in self._metrics.values())
        failed_requests = sum(m.failed_requests for m in self._metrics.values())

        return {
            "total_requests": total_requests,
            "success_rate": round(successful_requests / total_requests * 100, 1) if total_requests > 0 else 0,
            "failure_rate": round(failed_requests / total_requests * 100, 1) if total_requests > 0 else 0,
            "platforms": {
                p: {
                    "success_rate": round(m.successful_requests / m.total_requests * 100, 1) if m.total_requests > 0 else 0,
                    "avg_latency": round(m.avg_latency, 2),
                    "avg_cost": round(m.avg_cost, 2),
                }
                for p, m in self._metrics.items()
            },
        }

    def reset(self):
        self._metrics.clear()
        self._start_time = datetime.now()
