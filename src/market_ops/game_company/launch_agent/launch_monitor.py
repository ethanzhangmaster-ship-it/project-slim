from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class MonitorResult:
    monitor_id: str
    launch_id: str
    metrics: Dict[str, float] = field(default_factory=dict)
    status: str = "monitoring"
    recommendations: List[str] = field(default_factory=list)


class LaunchMonitor:
    def __init__(self):
        self.monitors: Dict[str, MonitorResult] = {}

    def monitor(self, launch_id: str, metrics: Dict[str, float]) -> MonitorResult:
        status = "monitoring"
        recommendations = []

        cpi = metrics.get("cpi", 2.5)
        if cpi > 4.0:
            recommendations.append("Reduce bid or pause campaign")
        
        roas = metrics.get("roas", 0.0)
        if roas < 1.0:
            recommendations.append("Optimize creative or targeting")
        
        installs = metrics.get("installs", 0)
        if installs < 100:
            recommendations.append("Increase budget or expand targeting")

        if not recommendations:
            status = "healthy"

        result = MonitorResult(
            monitor_id=f"monitor_{hash(launch_id + str(metrics)) % 10000:04d}",
            launch_id=launch_id,
            metrics=metrics,
            status=status,
            recommendations=recommendations,
        )

        self.monitors[result.monitor_id] = result
        return result

    def get_summary(self, launch_id: str) -> Dict[str, Any]:
        monitors = [m for m in self.monitors.values() if m.launch_id == launch_id]
        if not monitors:
            return {"status": "no_data"}
        
        latest = monitors[-1]
        return {
            "status": latest.status,
            "metrics": latest.metrics,
            "recommendations": latest.recommendations,
        }

    def monitor_demo(self) -> MonitorResult:
        metrics = {"cpi": 2.3, "roas": 1.5, "installs": 500, "ctr": 0.035, "cvr": 0.04}
        return self.monitor("launch_0001", metrics)
