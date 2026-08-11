"""E13.7.4.3 Agent Health Monitor — 健康监控系统.

Health Monitor 持续监控 Agent 运行状态:
    ProductionGrowthAgent
            ↓
    HealthMonitor.check()
            ↓
    HEALTHY / WARNING / DEGRADED / SAFE_MODE / FAILED
            ↓
    AlertManager.send() / HealthPolicy.apply()

模块:
  - health_models: 核心数据模型 (HealthStatus, HealthSnapshot, HealthRule, Alert, etc.)
  - health_metrics: 指标采集器 (Runtime / Decision / Execution / Tool)
  - health_rules: 健康规则集 (9 条默认规则)
  - health_monitor: 核心监控器 (HealthMonitor, 规则评估与状态聚合)
  - alert_manager: 告警管理器 (AlertManager, 告警生命周期)
  - health_policy: 安全模式策略 (HealthPolicy, Safe Mode 行为约束)

与 E13.7.4.2 Policy 的关系:
  Health Policy (本层) → 决定 Agent 运行模式 (整体降级)
  Agent Policy (E13.7.4.2) → 决定单次动作能否执行 (逐动作检查)
"""

from .health_models import (
    # Enums
    HealthStatus,
    HealthMetricCategory,
    AlertLevel,
    AlertType,
    # Data
    MetricDefinition,
    RuntimeHealth,
    DecisionHealth,
    ExecutionHealth,
    ToolHealth,
    HealthSnapshot,
    HealthRule,
    HealthRuleResult,
    HealthEvaluation,
    Alert,
    SafeModePolicy,
    # Helpers
    HEALTH_STATUS_SEVERITY,
    most_severe_status,
)

from .health_metrics import (
    RuntimeMetricsCollector,
    DecisionMetricsCollector,
    ExecutionMetricsCollector,
    ToolMetricsCollector,
    MetricsCollector,
)

from .health_rules import (
    build_default_health_rules,
)

from .health_monitor import (
    HealthMonitor,
    create_health_monitor,
)

from .alert_manager import (
    AlertManager,
    create_alert_manager,
)

from .health_policy import (
    HealthPolicy,
    DEFAULT_SAFE_MODE_POLICY,
    create_health_policy,
)

__all__ = [
    # Enums
    "HealthStatus",
    "HealthMetricCategory",
    "AlertLevel",
    "AlertType",
    # Models
    "MetricDefinition",
    "RuntimeHealth",
    "DecisionHealth",
    "ExecutionHealth",
    "ToolHealth",
    "HealthSnapshot",
    "HealthRule",
    "HealthRuleResult",
    "HealthEvaluation",
    "Alert",
    "SafeModePolicy",
    # Helpers
    "HEALTH_STATUS_SEVERITY",
    "most_severe_status",
    # Metrics
    "RuntimeMetricsCollector",
    "DecisionMetricsCollector",
    "ExecutionMetricsCollector",
    "ToolMetricsCollector",
    "MetricsCollector",
    # Rules
    "build_default_health_rules",
    # Monitor
    "HealthMonitor",
    "create_health_monitor",
    # Alert
    "AlertManager",
    "create_alert_manager",
    # Policy
    "HealthPolicy",
    "DEFAULT_SAFE_MODE_POLICY",
    "create_health_policy",
]