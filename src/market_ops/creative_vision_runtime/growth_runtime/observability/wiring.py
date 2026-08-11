"""E15.0.11 Wiring — 可观测性集成.

将可观测性组件 (EventBus + MetricsCollector + ExecutionLogger + TraceManager + AlertEngine)
一键接入 ExecutionRouter，实现零侵入的可观测性增强。

核心设计:
  - wire_observability():     将可观测性组件接入 ExecutionRouter 的 hook 系统
  - create_observability_hooks(): 创建标准化的 pre/post/audit hook 集

用法:
    from execution.adapter_router import ExecutionRouter
    from observability import wire_observability, EventBus, MetricsCollector, ExecutionLogger

    router = ExecutionRouter(registry)
    ob = wire_observability(router)

    # 执行动作后自动采集:
    #   - 事件 (EventBus)
    #   - 指标 (MetricsCollector)
    #   - 日志 (ExecutionLogger)
    #   - 追踪 (TraceManager)

    result = router.execute(action)
    print(ob.dashboard.get_dashboard())
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from .alerts import AlertEngine, AlertRule, default_alert_rules
from .dashboard import DashboardAggregator
from .events import EventBus, ExecutionEvent, ExecutionEventType
from .logger import ExecutionLogger
from .metrics import MetricsCollector
from .tracer import Span, SpanStatus, TraceContext, TraceManager


# ═══════════════════════════════════════════════════════════════
# GrowthAction / AdapterExecutionResult 协议定义
# ═══════════════════════════════════════════════════════════════


class GrowthActionProtocol(Protocol):
    """GrowthAction 协议 — 避免循环导入."""
    action_id: str
    game_id: str
    action_type: Any  # ActionType enum
    target: str
    parameters: dict[str, Any]
    metadata: dict[str, Any]


class AdapterResultProtocol(Protocol):
    """AdapterExecutionResult 协议."""
    success: bool
    status: Any  # AdapterResultStatus enum
    adapter_name: str
    duration_ms: float
    error: str
    external_id: str


# ═══════════════════════════════════════════════════════════════
# Observability Context
# ═══════════════════════════════════════════════════════════════


@dataclass
class ObservabilityContext:
    """E15.0.11 可观测性上下文 — 汇聚所有组件.

    Attributes:
        bus:       事件总线
        metrics:   指标收集器
        logger:    结构化日志器
        tracer:    追踪管理器
        alerts:    告警引擎
        dashboard: 仪表盘聚合器
    """

    bus: EventBus = field(default_factory=EventBus)
    metrics: MetricsCollector = field(default_factory=MetricsCollector)
    logger: ExecutionLogger = field(default_factory=ExecutionLogger)
    tracer: TraceManager = field(default_factory=TraceManager)
    alerts: AlertEngine = field(default_factory=lambda: AlertEngine(rules=default_alert_rules()))
    dashboard: DashboardAggregator | None = None

    def __post_init__(self):
        # 让 AlertEngine 共享同一个 MetricsCollector
        if self.alerts._collector is not self.metrics:
            self.alerts._collector = self.metrics

        # 创建 Dashboard
        self.dashboard = DashboardAggregator(
            bus=self.bus,
            metrics=self.metrics,
            alerts=self.alerts,
            tracer=self.tracer,
        )

    def stats(self) -> dict[str, Any]:
        return {
            "events": self.bus.stats(),
            "metrics": self.metrics.snapshot()["summary"],
            "logs": self.logger.stats(),
            "traces": self.tracer.stats(),
            "alerts": self.alerts.stats(),
        }

    def __repr__(self) -> str:
        return (
            f"ObservabilityContext(events={self.bus}, metrics={self.metrics}, "
            f"traces={self.tracer}, alerts={self.alerts})"
        )


# ═══════════════════════════════════════════════════════════════
# Hook Factory
# ═══════════════════════════════════════════════════════════════


def create_observability_hooks(
    bus: EventBus,
    metrics: MetricsCollector,
    logger: ExecutionLogger,
    tracer: TraceManager,
) -> dict[str, Any]:
    """创建标准化的可观测性 hook 集.

    Returns:
        dict 包含:
          - pre_hook:     执行前 hook (记录开始事件, 开始 Span)
          - post_hook:    执行后 hook (记录完成事件, 更新指标)
          - audit_hook:   审计 hook (记录日志)
          - trace_starter: 创建 Trace 上下文的工厂函数
    """

    def pre_hook(action: GrowthActionProtocol) -> None:
        """执行前 hook — 记录事件 + 开始追踪."""
        trace_ctx = TraceContext()
        span = tracer.start_span(trace_ctx, f"execute_{action.action_type.value}",
                                 action_id=action.action_id,
                                 game_id=action.game_id,
                                 target=action.target)

        bus.emit_typed(
            ExecutionEventType.EXECUTION_STARTED,
            action_id=action.action_id,
            game_id=action.game_id,
            trace_id=trace_ctx.trace_id,
            action_type=action.action_type.value,
            target=action.target,
        )

        logger.log_execution_started(
            action.action_id,
            adapter=action.action_type.value,
            target=action.target,
        )

        # 存储 span 到 metadata 以便 post_hook 结束
        action.metadata["_ob_span"] = span
        action.metadata["_ob_trace_ctx"] = trace_ctx

    def post_hook(action: GrowthActionProtocol, result: AdapterResultProtocol) -> None:
        """执行后 hook — 记录事件 + 更新指标 + 结束 Span."""
        # 结束 Span
        span: Span | None = action.metadata.pop("_ob_span", None)
        if span is not None:
            if result.success:
                tracer.finish_span(span, SpanStatus.SUCCESS)
            else:
                tracer.fail_span(span, result.error)

        # 记录指标
        metrics.increment("execution_total")
        if result.success:
            metrics.increment("execution_success")
            bus.emit_typed(
                ExecutionEventType.EXECUTION_SUCCESS,
                action_id=action.action_id,
                game_id=action.game_id,
                adapter=result.adapter_name,
                duration_ms=result.duration_ms,
                external_id=result.external_id,
            )
            logger.log_execution_success(
                action.action_id,
                adapter=result.adapter_name,
                duration_ms=result.duration_ms,
                external_id=result.external_id,
            )
        else:
            metrics.increment("execution_failed")
            bus.emit_typed(
                ExecutionEventType.EXECUTION_FAILED,
                action_id=action.action_id,
                game_id=action.game_id,
                adapter=result.adapter_name,
                error=result.error,
            )
            logger.log_execution_failed(
                action.action_id,
                adapter=result.adapter_name,
                error=result.error,
            )

        # 记录耗时
        if result.duration_ms > 0:
            metrics.observe("execution_duration_ms", result.duration_ms)
            metrics.observe(
                "adapter_latency_ms",
                result.duration_ms,
                labels={"adapter": result.adapter_name},
            )

        # 按适配器统计
        metrics.increment(
            "adapter_total",
            labels={"adapter": result.adapter_name},
        )
        if result.success:
            metrics.increment(
                "adapter_success",
                labels={"adapter": result.adapter_name},
            )

    def audit_hook(action: GrowthActionProtocol, result: AdapterResultProtocol) -> None:
        """审计 hook — 记录完整审计日志."""
        logger.info(
            "AUDIT_EXECUTION",
            action_id=action.action_id,
            action_type=action.action_type.value,
            game_id=action.game_id,
            target=action.target,
            success=result.success,
            adapter=result.adapter_name,
            duration_ms=result.duration_ms,
            external_id=result.external_id,
            error=result.error,
        )

    def trace_starter() -> TraceContext:
        """创建新的 Trace 上下文."""
        return tracer.start_trace()

    return {
        "pre_hook": pre_hook,
        "post_hook": post_hook,
        "audit_hook": audit_hook,
        "trace_starter": trace_starter,
    }


# ═══════════════════════════════════════════════════════════════
# Wire Function
# ═══════════════════════════════════════════════════════════════


def wire_observability(
    router: Any,  # ExecutionRouter
    ctx: ObservabilityContext | None = None,
) -> ObservabilityContext:
    """将可观测性组件一键接入 ExecutionRouter.

    将 pre_hook / post_hook / audit_hook 注册到 Router 的 hook 系统，
    实现零侵入的可观测性增强。

    Args:
        router: ExecutionRouter 实例
        ctx:    可观测性上下文 (None 则自动创建)

    Returns:
        ObservabilityContext: 可观测性上下文

    用法:
        from execution.adapter_router import ExecutionRouter
        from observability import wire_observability

        router = ExecutionRouter(registry)
        ob = wire_observability(router)

        # 所有后续执行都会自动采集可观测性数据
        result = router.execute(action)
        print(ob.dashboard.get_dashboard())
    """
    if ctx is None:
        ctx = ObservabilityContext()

    hooks = create_observability_hooks(
        bus=ctx.bus,
        metrics=ctx.metrics,
        logger=ctx.logger,
        tracer=ctx.tracer,
    )

    router.register_pre_hook(hooks["pre_hook"])
    router.register_post_hook(hooks["post_hook"])
    router.register_audit_hook(hooks["audit_hook"])

    return ctx


__all__ = [
    "ObservabilityContext",
    "create_observability_hooks",
    "wire_observability",
]