"""Alert System"""
from typing import Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Alert:
    alert_id: str = ""
    level: str = "info"
    message: str = ""
    platform: str = ""
    timestamp: str = ""
    action: str = ""
    resolved: bool = False

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class AlertManager:
    """告警管理器"""

    _thresholds = {
        "failure_rate": 30,
        "avg_latency": 60,
        "platform_unavailable": 0,
    }

    def __init__(self):
        self._alerts: List[Alert] = []

    def check_and_alert(self, metrics: Dict[str, Any]) -> List[Alert]:
        new_alerts = []

        for platform, p_metrics in metrics.get("platforms", {}).items():
            failure_rate = p_metrics.get("failure_rate", 0)
            avg_latency = p_metrics.get("avg_latency", 0)

            if failure_rate > self._thresholds["failure_rate"]:
                alert = Alert(
                    alert_id=f"alert_{platform}_failure",
                    level="critical",
                    message=f"{platform} failure rate {failure_rate}% exceeds threshold {self._thresholds['failure_rate']}%",
                    platform=platform,
                    action="switch_to_alternative",
                )
                new_alerts.append(alert)

            if avg_latency > self._thresholds["avg_latency"]:
                alert = Alert(
                    alert_id=f"alert_{platform}_latency",
                    level="warning",
                    message=f"{platform} avg latency {avg_latency}s exceeds threshold {self._thresholds['avg_latency']}s",
                    platform=platform,
                    action="monitor_closely",
                )
                new_alerts.append(alert)

        self._alerts.extend(new_alerts)
        return new_alerts

    def get_alerts(self, level: str = None, resolved: bool = False) -> List[Alert]:
        alerts = self._alerts
        if level:
            alerts = [a for a in alerts if a.level == level]
        if not resolved:
            alerts = [a for a in alerts if not a.resolved]
        return alerts

    def resolve_alert(self, alert_id: str):
        for alert in self._alerts:
            if alert.alert_id == alert_id:
                alert.resolved = True

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_alerts": len(self._alerts),
            "critical": sum(1 for a in self._alerts if a.level == "critical" and not a.resolved),
            "warning": sum(1 for a in self._alerts if a.level == "warning" and not a.resolved),
            "info": sum(1 for a in self._alerts if a.level == "info" and not a.resolved),
        }

    def clear_all(self):
        self._alerts = []
