"""Alert Manager - 告警管理器"""
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum


class AlertSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertType(str, Enum):
    COST_SPIKE = "COST_SPIKE"
    QUALITY_DROP = "QUALITY_DROP"
    CREATIVE_FATIGUE = "CREATIVE_FATIGUE"
    SUCCESS_RATE_DROP = "SUCCESS_RATE_DROP"
    QUEUE_BACKLOG = "QUEUE_BACKLOG"
    PLATFORM_FAILURE = "PLATFORM_FAILURE"
    WORKER_CRASH = "WORKER_CRASH"


@dataclass
class Alert:
    """告警"""
    alert_id: str = ""
    alert_type: AlertType = AlertType.COST_SPIKE
    severity: AlertSeverity = AlertSeverity.MEDIUM
    message: str = ""
    metric: str = ""
    current_value: float = 0.0
    threshold_value: float = 0.0
    action: str = ""
    created_at: str = ""
    resolved: bool = False
    resolved_at: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "type": self.alert_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "metric": self.metric,
            "current_value": round(self.current_value, 3),
            "threshold_value": round(self.threshold_value, 3),
            "action": self.action,
            "created_at": self.created_at,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at,
        }


class AlertManager:
    """告警管理器"""
    
    def __init__(self):
        self._alerts: List[Alert] = []
        self._alert_counter = 0
    
    def create_alert(
        self,
        alert_type: AlertType,
        severity: AlertSeverity,
        message: str,
        metric: str = "",
        current_value: float = 0.0,
        threshold_value: float = 0.0,
        action: str = "",
    ) -> Alert:
        """创建告警"""
        self._alert_counter += 1
        alert_id = f"alert_{self._alert_counter:04d}"
        
        alert = Alert(
            alert_id=alert_id,
            alert_type=alert_type,
            severity=severity,
            message=message,
            metric=metric,
            current_value=current_value,
            threshold_value=threshold_value,
            action=action,
            created_at=datetime.now().isoformat(),
        )
        
        self._alerts.append(alert)
        return alert
    
    def resolve_alert(self, alert_id: str) -> bool:
        """解决告警"""
        for alert in self._alerts:
            if alert.alert_id == alert_id:
                alert.resolved = True
                alert.resolved_at = datetime.now().isoformat()
                return True
        return False
    
    def get_active_alerts(self) -> List[Alert]:
        """获取活跃告警"""
        return [a for a in self._alerts if not a.resolved]
    
    def get_alerts_by_severity(self, severity: AlertSeverity) -> List[Alert]:
        """按严重级别获取告警"""
        return [a for a in self._alerts if a.severity == severity]
    
    def get_alerts_by_type(self, alert_type: AlertType) -> List[Alert]:
        """按类型获取告警"""
        return [a for a in self._alerts if a.alert_type == alert_type]
    
    def has_active_critical(self) -> bool:
        """是否有活跃严重告警"""
        return any(
            a.severity == AlertSeverity.CRITICAL and not a.resolved
            for a in self._alerts
        )
    
    def get_summary(self) -> Dict[str, Any]:
        """获取告警摘要"""
        active = self.get_active_alerts()
        return {
            "total": len(self._alerts),
            "active": len(active),
            "resolved": len([a for a in self._alerts if a.resolved]),
            "critical": len([a for a in active if a.severity == AlertSeverity.CRITICAL]),
            "high": len([a for a in active if a.severity == AlertSeverity.HIGH]),
            "medium": len([a for a in active if a.severity == AlertSeverity.MEDIUM]),
            "low": len([a for a in active if a.severity == AlertSeverity.LOW]),
        }
