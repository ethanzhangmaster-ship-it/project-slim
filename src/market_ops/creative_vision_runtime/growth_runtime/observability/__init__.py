"""E15.0.11 Observability Stack — 可观测性层.

让 Execution Runtime 具备自我感知能力:
  - Events:      全链路事件采集与发布
  - Metrics:     Counter / Gauge / Histogram 指标收集
  - Logger:      结构化 JSON 日志
  - Tracer:      分布式 Trace 上下文
  - Alerts:      阈值告警引擎
  - Dashboard:   系统状态聚合 API

架构位置:
  Execution Runtime → Observability → External Monitoring (Prometheus/Grafana)
"""

from .events import (
    EventBus,
    ExecutionEvent,
    ExecutionEventType,
)
from .metrics import (
    Counter,
    Gauge,
    Histogram,
    MetricsCollector,
)
from .logger import ExecutionLogger
from .tracer import (
    Span,
    SpanStatus,
    TraceContext,
    TraceManager,
)
from .alerts import (
    AlertEngine,
    AlertRule,
    AlertSeverity,
    AlertState,
)
from .dashboard import DashboardAggregator
from .wiring import (
    wire_observability,
    create_observability_hooks,
)

__all__ = [
    # Events
    "EventBus",
    "ExecutionEvent",
    "ExecutionEventType",
    # Metrics
    "Counter",
    "Gauge",
    "Histogram",
    "MetricsCollector",
    # Logger
    "ExecutionLogger",
    # Tracer
    "Span",
    "SpanStatus",
    "TraceContext",
    "TraceManager",
    # Alerts
    "AlertEngine",
    "AlertRule",
    "AlertSeverity",
    "AlertState",
    # Dashboard
    "DashboardAggregator",
    # Wiring
    "wire_observability",
    "create_observability_hooks",
]