"""E13.7.4.1 Production Growth Runtime — 生产运行时核心.

ProductionGrowthRuntime 是 E13.7.4 的核心运行时，将 GrowthAgent 从
"run_cycle()" 升级为完整的生产自主运行系统:

  LifecycleManager → Scheduler → GrowthAgent Loop → RuntimeState

架构:
  ┌─────────────────────┐
  │ Lifecycle Manager   │  ← 启动/暂停/停止/安全模式
  └─────────┬───────────┘
            ↓
  ┌─────────────────────┐
  │ Scheduler           │  ← 5min / 1hr / 24hr 定时任务
  └─────────┬───────────┘
            ↓
  ┌─────────────────────┐
  │ GrowthAgent Loop    │  ← Observe → Reason → Plan → Execute → Learn
  └─────────┬───────────┘
            ↓
  Runtime State + Event Bus + Health + Memory + Report

用法:
    agent = create_growth_agent(with_real_adapters=True)
    runtime = ProductionGrowthRuntime(agent=agent)
    runtime.start()
    runtime.run_cycle(metrics)
    runtime.stop()
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from ..agent_core import GrowthAgent, create_growth_agent
from ..agent_health import AgentHealthMonitor, HealthStatus
from ..agent_models import AgentGoal, AgentPhase
from ..agent_policy import AgentPolicy, create_default_policy
from ..agent_reporter import AgentReporter, DailyReport
from ..production_memory import ProductionMemory

from .agent_scheduler import AgentScheduler, create_scheduler
from .lifecycle_manager import LifecycleManager, create_lifecycle_manager
from .runtime_events import EventBus, RuntimeEvent, RuntimeEventType
from .runtime_state import RuntimeState, RuntimeStatus


# ═══════════════════════════════════════════════════════════════
# Production Growth Runtime
# ═══════════════════════════════════════════════════════════════


class ProductionGrowthRuntime:
    """Production Growth Runtime — 生产级自主增长运行时.

    将 GrowthAgent 封装为生产就绪的自主运行系统:
      - 生命周期管理 (启动/暂停/停止/安全模式)
      - 调度系统 (定时数据采集/分析/复盘)
      - 策略执行 (三级安全策略)
      - 健康监控 (自动检测异常并切换安全模式)
      - 事件系统 (下游模块订阅)
      - 生产记忆 (长期循环记录)
      - 报告生成 (每日/每周报告)

    用法:
        agent = create_growth_agent(with_real_adapters=True)
        runtime = ProductionGrowthRuntime(agent=agent)
        runtime.start()
        runtime.run_cycle(metrics)
        report = runtime.generate_daily_report()
        runtime.stop()
    """

    # 安全模式: 最大连续错误数
    MAX_CONSECUTIVE_ERRORS = 3

    def __init__(
        self,
        agent: GrowthAgent | None = None,
        policy: AgentPolicy | None = None,
        state: RuntimeState | None = None,
        event_bus: EventBus | None = None,
        lifecycle: LifecycleManager | None = None,
        scheduler: AgentScheduler | None = None,
        health_monitor: AgentHealthMonitor | None = None,
        memory: ProductionMemory | None = None,
        reporter: AgentReporter | None = None,
    ):
        # 核心 Agent
        self._agent = agent or create_growth_agent()

        # 策略
        self._policy = policy or create_default_policy()

        # 状态
        self._state = state or RuntimeState()
        self._event_bus = event_bus or EventBus()

        # 生命周期
        self._lifecycle = lifecycle or create_lifecycle_manager(
            state=self._state,
            event_bus=self._event_bus,
        )

        # 调度器
        self._scheduler = scheduler or create_scheduler(with_default_jobs=True)

        # 健康监控
        self._health = health_monitor or AgentHealthMonitor()

        # 生产记忆
        self._memory = memory or ProductionMemory()

        # 报告
        self._reporter = reporter or AgentReporter(
            memory=self._memory,
        )

        # 控制
        self._running = False
        self._lock = threading.Lock()

        # 注册事件处理器
        self._setup_event_handlers()

    # ── Properties ────────────────────────────────────────────

    @property
    def status(self) -> RuntimeStatus:
        return self._state.status

    @property
    def is_running(self) -> bool:
        return self._state.status == RuntimeStatus.RUNNING

    @property
    def agent(self) -> GrowthAgent:
        return self._agent

    @property
    def policy(self) -> AgentPolicy:
        return self._policy

    @property
    def state(self) -> RuntimeState:
        return self._state

    @property
    def event_bus(self) -> EventBus:
        return self._event_bus

    @property
    def memory(self) -> ProductionMemory:
        return self._memory

    @property
    def health(self) -> AgentHealthMonitor:
        return self._health

    # ── 事件处理 ──────────────────────────────────────────────

    def _setup_event_handlers(self) -> None:
        """注册内部事件处理器."""
        # 健康监控: 跟踪成功/失败
        self._event_bus.subscribe(
            RuntimeEventType.CYCLE_COMPLETED,
            lambda e: self._health.record_success(),
        )
        self._event_bus.subscribe(
            RuntimeEventType.CYCLE_FAILED,
            lambda e: self._health.record_failure(),
        )

    # ── 生命周期 ──────────────────────────────────────────────

    def start(self) -> bool:
        """启动 Runtime.

        CREATED → INITIALIZING → LOADING_MEMORY → CONNECTING_TOOLS → RUNNING

        Returns:
            bool: 是否成功
        """
        if not self._policy.enabled:
            return False

        # 注册生命周期钩子
        self._lifecycle.on_load_memory(lambda: None)  # 默认: 无操作
        self._lifecycle.on_connect_tools(lambda: None)  # 默认: 无操作

        # 启动
        if not self._lifecycle.start():
            return False

        # 启动调度器
        self._scheduler.start()

        self._running = True
        return True

    def pause(self) -> bool:
        """暂停 Runtime."""
        return self._lifecycle.pause()

    def resume(self) -> bool:
        """恢复 Runtime."""
        return self._lifecycle.resume()

    def stop(self) -> bool:
        """停止 Runtime."""
        self._running = False
        self._scheduler.stop()
        return self._lifecycle.stop()

    def enter_safe_mode(self, reason: str = "") -> bool:
        """进入安全模式."""
        return self._lifecycle.enter_safe_mode(reason)

    def exit_safe_mode(self) -> bool:
        """退出安全模式."""
        return self._lifecycle.exit_safe_mode()

    # ── 主循环 ────────────────────────────────────────────────

    def run_cycle(
        self,
        metrics: dict[str, Any] | None = None,
        goals: list[AgentGoal] | None = None,
    ) -> dict[str, Any]:
        """执行一次完整的生产循环.

        Observe → Reason → Plan → Execute → Learn → Record

        Args:
            metrics: 当前指标数据
            goals: 外部目标

        Returns:
            dict: 循环结果摘要
        """
        if not self._policy.enabled:
            return {"error": "Policy disabled", "success": False}

        if self._state.status == RuntimeStatus.SAFE_MODE:
            return self._restricted_cycle(metrics)

        cycle_start = datetime.now(timezone.utc)
        cycle_id = f"{cycle_start.strftime('%Y%m%d')}_{self._state.cycle_count + 1:03d}"
        self._state.record_cycle_start()

        self._event_bus.emit(
            RuntimeEventType.CYCLE_STARTED,
            source="runtime",
            data={"cycle_id": cycle_id},
        )

        try:
            # 1. 观察
            self._event_bus.emit(
                RuntimeEventType.OBSERVATION_COMPLETED,
                source="runtime",
                data={"metrics": metrics},
            )

            # 2. 执行 Agent 循环
            agent_summary = self._agent.run_cycle(
                metrics=metrics,
                external_goals=goals,
            )

            cycle_success = "error" not in agent_summary
            duration = (datetime.now(timezone.utc) - cycle_start).total_seconds()

            if cycle_success:
                self._state.record_cycle_success(duration)
                self._event_bus.emit(
                    RuntimeEventType.CYCLE_COMPLETED,
                    source="runtime",
                    data={
                        "cycle_id": cycle_id,
                        "duration_seconds": round(duration, 2),
                        "agent_summary": agent_summary,
                    },
                )
            else:
                self._state.record_cycle_failure(duration)
                self._event_bus.emit(
                    RuntimeEventType.CYCLE_FAILED,
                    source="runtime",
                    data={
                        "cycle_id": cycle_id,
                        "duration_seconds": round(duration, 2),
                        "error": agent_summary.get("error", "unknown"),
                    },
                )

            # 3. 记录生产记忆
            self._memory.create_record(
                cycle_id=cycle_id,
                observation=metrics or {},
                reasoning={"agent_summary": agent_summary},
                decision={},
                result={"success": cycle_success},
                learning={},
                success=cycle_success,
                duration_seconds=round(duration, 2),
            )

            # 4. 健康检查
            self._health.record_cycle(
                duration_seconds=duration,
            )

            # 5. 自动安全模式检测
            if self._state.consecutive_errors >= self.MAX_CONSECUTIVE_ERRORS:
                self.enter_safe_mode(
                    reason=f"Consecutive errors: {self._state.consecutive_errors}"
                )

            return {
                "cycle_id": cycle_id,
                "success": cycle_success,
                "duration_seconds": round(duration, 2),
                "status": self._state.status.value,
                **agent_summary,
            }

        except Exception as e:
            duration = (datetime.now(timezone.utc) - cycle_start).total_seconds()
            self._state.record_cycle_failure(duration)

            self._event_bus.emit(
                RuntimeEventType.CYCLE_FAILED,
                source="runtime",
                data={"cycle_id": cycle_id},
                error=str(e),
            )

            self._event_bus.emit(
                RuntimeEventType.ERROR_OCCURRED,
                source="runtime",
                error=str(e),
            )

            # 自动安全模式
            if self._state.consecutive_errors >= self.MAX_CONSECUTIVE_ERRORS:
                self.enter_safe_mode(reason=str(e))

            return {
                "cycle_id": cycle_id,
                "success": False,
                "error": str(e),
                "duration_seconds": round(duration, 2),
                "status": self._state.status.value,
            }

    def _restricted_cycle(self, metrics: dict[str, Any] | None = None) -> dict[str, Any]:
        """安全模式下的受限循环 (只读不写)."""
        return {
            "cycle_id": f"safe_{self._state.cycle_count + 1:03d}",
            "success": True,
            "mode": "safe_mode",
            "restricted": True,
            "message": "Running in safe mode: read-only, no autonomous actions",
            "metrics": metrics,
            "status": RuntimeStatus.SAFE_MODE.value,
        }

    # ── 策略检查 ──────────────────────────────────────────────

    def check_action(
        self,
        action_type: str,
        params: dict[str, Any] | None = None,
    ) -> bool:
        """检查动作是否被策略允许."""
        return self._policy.is_allowed(action_type, params)

    def check_budget(
        self,
        current_spend: float,
        proposed_spend: float,
    ) -> tuple[bool, str]:
        """检查预算是否超限."""
        return self._policy.check_budget_limit(current_spend, proposed_spend)

    # ── 报告 ──────────────────────────────────────────────────

    def generate_daily_report(self, date: str | None = None) -> DailyReport:
        """生成每日增长报告."""
        records = self._memory.get_by_date(date or "")
        self._reporter.update_health(self._health.get_latest())
        return self._reporter.generate_daily_report(date=date, records=records)

    def generate_report_text(self, date: str | None = None) -> str:
        """生成每日报告文本."""
        report = self.generate_daily_report(date)
        return report.to_text()

    # ── 统计 ──────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """获取 Runtime 完整统计."""
        return {
            "runtime": self._state.to_dict(),
            "health": self._health.stats(),
            "memory": self._memory.stats(),
            "scheduler": self._scheduler.stats(),
            "agent": self._agent.stats(),
            "events": self._event_bus.event_count(),
            "policy": self._policy.to_dict(),
        }

    def reset(self) -> None:
        """重置 Runtime."""
        self.stop()
        self._state.reset()
        self._health.reset()
        self._memory.clear()
        self._scheduler.reset()
        self._agent.reset()
        self._event_bus.clear()
        self._running = False


# ═══════════════════════════════════════════════════════════════
# Factory Functions
# ═══════════════════════════════════════════════════════════════


def create_production_runtime(
    with_real_adapters: bool = False,
    execution_mode: str = "mock",
) -> ProductionGrowthRuntime:
    """创建默认生产 Runtime.

    Args:
        with_real_adapters: 是否使用真实 Adapter
        execution_mode: 执行模式

    Returns:
        ProductionGrowthRuntime: 预配置的生产 Runtime
    """
    agent = create_growth_agent(
        with_real_adapters=with_real_adapters,
        execution_mode=execution_mode,
    )
    return ProductionGrowthRuntime(agent=agent)