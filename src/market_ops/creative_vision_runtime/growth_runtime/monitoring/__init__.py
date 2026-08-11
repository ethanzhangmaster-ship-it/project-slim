"""E15.0.5 Monitoring — 指标采集与报警.

监控指标:
  - Agent: decision_count, success_rate, failure_rate
  - Execution: action_success, rollback_count, approval_waiting
  - Business: spend, revenue, ROAS, LTV

报警:
  - ROAS 下降 30%
  - Connector 失败
  - 执行异常
  - 预算异常
"""

from .metrics import GrowthMetrics, MetricsCollector
from .alerts import AlertManager, AlertRule, AlertSeverity, Alert

__all__ = [
    "GrowthMetrics",
    "MetricsCollector",
    "AlertManager",
    "AlertRule",
    "AlertSeverity",
    "Alert",
]