"""E13.7.5 Agent Orchestrator — 自主循环编排器.

Agent Orchestrator 是 E13.7 的最高层编排器，管理完整的自主增长循环:
  - 调度: 定时或事件驱动触发 Agent 循环
  - 编排: 协调 Observe → Reason → Plan → Execute → Learn
  - 监控: 跟踪循环状态和性能
  - 恢复: 错误处理和自动恢复
  - 报告: 生成循环摘要报告

核心循环:
  while True:
      observe() → analyze() → decide() → execute() → evaluate() → learn()

连接:
  Orchestrator → GrowthAgent → All E13.x Components

用法:
    orchestrator = AgentOrchestrator(agent=growth_agent)
    orchestrator.run_once(metrics)  # 单次执行
    orchestrator.run_loop(interval_minutes=60)  # 持续循环
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .agent_core import GrowthAgent, create_growth_agent
from .agent_models import (
    AgentGoal,
    AgentPhase,
    AgentProfile,
    GoalPriority,
    GoalStatus,
    Observation,
)
from .agent_tools import ToolResult


# ═══════════════════════════════════════════════════════════════
# Orchestrator Models
# ═══════════════════════════════════════════════════════════════


class OrchestratorState(str, Enum):
    """编排器状态."""
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    RECOVERING = "recovering"


class CycleTrigger(str, Enum):
    """循环触发方式."""
    SCHEDULED = "scheduled"         # 定时触发
    METRICS_CHANGE = "metrics_change"  # 指标变化触发
    MANUAL = "manual"               # 手动触发
    ALERT = "alert"                 # 告警触发
    RECOVERY = "recovery"           # 恢复触发


@dataclass
class CycleResult:
    """单次循环结果.

    Attributes:
        cycle_id: 循环 ID
        cycle_number: 循环编号
        trigger: 触发方式
        started_at: 开始时间
        completed_at: 完成时间
        duration_seconds: 持续时间
        success: 是否成功
        observation_count: 观察数量
        insight_count: 洞察数量
        plan_count: 计划数量
        execution_count: 执行数量
        lesson_count: 经验教训数量
        error: 错误信息
        agent_summary: Agent 循环摘要
    """
    cycle_id: str = ""
    cycle_number: int = 0
    trigger: CycleTrigger = CycleTrigger.MANUAL
    started_at: str = ""
    completed_at: str = ""
    duration_seconds: float = 0.0
    success: bool = True
    observation_count: int = 0
    insight_count: int = 0
    plan_count: int = 0
    execution_count: int = 0
    lesson_count: int = 0
    error: str = ""
    agent_summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "cycle_number": self.cycle_number,
            "trigger": self.trigger.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "success": self.success,
            "observation_count": self.observation_count,
            "insight_count": self.insight_count,
            "plan_count": self.plan_count,
            "execution_count": self.execution_count,
            "lesson_count": self.lesson_count,
            "error": self.error,
            "agent_summary": self.agent_summary,
        }


@dataclass
class OrchestratorReport:
    """编排器运行报告.

    Attributes:
        total_cycles: 总循环数
        successful_cycles: 成功循环数
        failed_cycles: 失败循环数
        total_insights: 总洞察数
        total_plans: 总计划数
        total_executions: 总执行数
        total_lessons: 总经验教训数
        total_duration_seconds: 总运行时间
        avg_cycle_duration: 平均循环时间
        state: 当前状态
        last_cycle_at: 最后循环时间
    """
    total_cycles: int = 0
    successful_cycles: int = 0
    failed_cycles: int = 0
    total_insights: int = 0
    total_plans: int = 0
    total_executions: int = 0
    total_lessons: int = 0
    total_duration_seconds: float = 0.0
    avg_cycle_duration: float = 0.0
    state: str = "stopped"
    last_cycle_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_cycles": self.total_cycles,
            "successful_cycles": self.successful_cycles,
            "failed_cycles": self.failed_cycles,
            "success_rate": (
                self.successful_cycles / self.total_cycles
                if self.total_cycles > 0 else 0.0
            ),
            "total_insights": self.total_insights,
            "total_plans": self.total_plans,
            "total_executions": self.total_executions,
            "total_lessons": self.total_lessons,
            "total_duration_seconds": self.total_duration_seconds,
            "avg_cycle_duration": self.avg_cycle_duration,
            "state": self.state,
            "last_cycle_at": self.last_cycle_at,
        }


# ═══════════════════════════════════════════════════════════════
# Agent Orchestrator
# ═══════════════════════════════════════════════════════════════


class AgentOrchestrator:
    """Agent 编排器 — 管理完整的自主增长循环.

    职责:
      1. 循环调度: 定时或事件驱动触发 Agent 循环
      2. 流程编排: 确保 Observe → Reason → Plan → Execute → Learn 的正确顺序
      3. 状态监控: 跟踪循环状态和系统性能
      4. 错误恢复: 自动处理异常和重试
      5. 报告生成: 汇总循环结果

    用法:
        orchestrator = AgentOrchestrator(agent=growth_agent)
        result = orchestrator.run_once(metrics={"spend": 17000, "roas": 0.53})
        report = orchestrator.generate_report()
    """

    # 最大连续错误数
    MAX_CONSECUTIVE_ERRORS = 3
    # 错误恢复冷却时间 (秒)
    ERROR_COOLDOWN_SECONDS = 60

    def __init__(
        self,
        agent: GrowthAgent | None = None,
        max_cycles: int = 1000,
        error_cooldown_seconds: float = 60.0,
    ):
        self._agent = agent or create_growth_agent()
        self._state = OrchestratorState.STOPPED
        self._max_cycles = max_cycles
        self._error_cooldown_seconds = error_cooldown_seconds

        # 循环历史
        self._cycles: list[CycleResult] = []
        self._cycle_count: int = 0
        self._consecutive_errors: int = 0
        self._last_error_at: str = ""

        # 默认目标
        self._default_goals: list[AgentGoal] = []

    # ── Properties ────────────────────────────────────────────

    @property
    def state(self) -> OrchestratorState:
        return self._state

    @property
    def agent(self) -> GrowthAgent:
        return self._agent

    @property
    def cycle_count(self) -> int:
        return self._cycle_count

    # ── 单次循环 ──────────────────────────────────────────────

    def run_once(
        self,
        metrics: dict[str, Any] | None = None,
        goals: list[AgentGoal] | None = None,
        trigger: CycleTrigger = CycleTrigger.MANUAL,
    ) -> CycleResult:
        """执行一次完整的 Agent 循环.

        Args:
            metrics: 当前指标数据
            goals: 目标列表
            trigger: 触发方式

        Returns:
            CycleResult: 循环结果
        """
        cycle_id = f"cycle_{self._cycle_count + 1}"
        started_at = datetime.now(timezone.utc)

        if self._state == OrchestratorState.STOPPED:
            self._state = OrchestratorState.RUNNING

        result = CycleResult(
            cycle_id=cycle_id,
            cycle_number=self._cycle_count + 1,
            trigger=trigger,
            started_at=started_at.isoformat(),
        )

        try:
            # 使用活动目标或默认目标
            active_goals = goals or self._default_goals or self._agent.get_active_goals()

            # 执行 Agent 循环
            agent_summary = self._agent.run_cycle(
                metrics=metrics,
                external_goals=active_goals if active_goals else None,
            )

            completed_at = datetime.now(timezone.utc)
            duration = (completed_at - started_at).total_seconds()

            result.completed_at = completed_at.isoformat()
            result.duration_seconds = round(duration, 2)
            result.success = "error" not in agent_summary
            result.observation_count = agent_summary.get("observation_count", 0)
            result.insight_count = agent_summary.get("insight_count", 0)
            result.plan_count = agent_summary.get("plan_count", 0)
            result.execution_count = agent_summary.get("execution_count", 0)
            result.lesson_count = agent_summary.get("lesson_count", 0)
            result.agent_summary = agent_summary

            self._consecutive_errors = 0

        except Exception as e:
            completed_at = datetime.now(timezone.utc)
            duration = (completed_at - started_at).total_seconds()

            result.completed_at = completed_at.isoformat()
            result.duration_seconds = round(duration, 2)
            result.success = False
            result.error = str(e)

            self._consecutive_errors += 1
            self._last_error_at = completed_at.isoformat()

            if self._consecutive_errors >= self.MAX_CONSECUTIVE_ERRORS:
                self._state = OrchestratorState.ERROR

        self._cycle_count += 1
        self._cycles.append(result)

        return result

    # ── 持续循环 ──────────────────────────────────────────────

    def run_loop(
        self,
        interval_minutes: int = 60,
        max_cycles: int | None = None,
        metrics_provider: callable | None = None,
        goal_provider: callable | None = None,
    ) -> None:
        """启动持续自主循环.

        while True:
            observe → analyze → decide → execute → evaluate → learn

        Args:
            interval_minutes: 循环间隔 (分钟)
            max_cycles: 最大循环数 (None = 无限)
            metrics_provider: 指标数据提供函数 (callable → dict)
            goal_provider: 目标提供函数 (callable → list[AgentGoal])
        """
        self._state = OrchestratorState.RUNNING
        max_cycles = max_cycles or self._max_cycles

        try:
            for i in range(max_cycles):
                if self._state == OrchestratorState.PAUSED:
                    break

                # 获取指标
                metrics = None
                if metrics_provider:
                    try:
                        metrics = metrics_provider()
                    except Exception:
                        pass

                # 获取目标
                goals = None
                if goal_provider:
                    try:
                        goals = goal_provider()
                    except Exception:
                        pass

                # 执行循环
                trigger = CycleTrigger.SCHEDULED
                result = self.run_once(metrics=metrics, goals=goals, trigger=trigger)

                # 错误恢复
                if not result.success and self._state == OrchestratorState.ERROR:
                    self._recover()

                if self._state == OrchestratorState.PAUSED:
                    break

                # 等待间隔
                if i < max_cycles - 1:
                    time.sleep(interval_minutes * 60)

        except KeyboardInterrupt:
            self._state = OrchestratorState.STOPPED
        finally:
            if self._state == OrchestratorState.RUNNING:
                self._state = OrchestratorState.STOPPED

    # ── 控制 ──────────────────────────────────────────────────

    def start(self) -> None:
        """启动编排器."""
        if self._state == OrchestratorState.STOPPED:
            self._state = OrchestratorState.RUNNING

    def pause(self) -> None:
        """暂停编排器."""
        self._state = OrchestratorState.PAUSED

    def resume(self) -> None:
        """恢复编排器."""
        if self._state == OrchestratorState.PAUSED:
            self._state = OrchestratorState.RUNNING

    def stop(self) -> None:
        """停止编排器."""
        self._state = OrchestratorState.STOPPED

    def _recover(self) -> None:
        """错误恢复."""
        self._state = OrchestratorState.RECOVERING

        # 冷却等待
        if self._last_error_at:
            last_error = datetime.fromisoformat(self._last_error_at)
            elapsed = (datetime.now(timezone.utc) - last_error).total_seconds()
            if elapsed < self._error_cooldown_seconds:
                time.sleep(self._error_cooldown_seconds - elapsed)

        self._consecutive_errors = 0
        self._state = OrchestratorState.RUNNING

    # ── 目标管理 ──────────────────────────────────────────────

    def set_default_goals(self, goals: list[AgentGoal]) -> None:
        """设置默认目标."""
        self._default_goals = goals

    def add_default_goal(self, goal: AgentGoal) -> None:
        """添加默认目标."""
        self._default_goals.append(goal)

    def clear_default_goals(self) -> None:
        """清除默认目标."""
        self._default_goals.clear()

    # ── 报告 ──────────────────────────────────────────────────

    def generate_report(self) -> OrchestratorReport:
        """生成运行报告."""
        total = len(self._cycles)
        successful = sum(1 for c in self._cycles if c.success)
        failed = total - successful

        total_duration = sum(c.duration_seconds for c in self._cycles)
        avg_duration = total_duration / total if total > 0 else 0

        return OrchestratorReport(
            total_cycles=total,
            successful_cycles=successful,
            failed_cycles=failed,
            total_insights=sum(c.insight_count for c in self._cycles),
            total_plans=sum(c.plan_count for c in self._cycles),
            total_executions=sum(c.execution_count for c in self._cycles),
            total_lessons=sum(c.lesson_count for c in self._cycles),
            total_duration_seconds=round(total_duration, 2),
            avg_cycle_duration=round(avg_duration, 2),
            state=self._state.value,
            last_cycle_at=(
                self._cycles[-1].completed_at if self._cycles else ""
            ),
        )

    def get_cycle_history(self, n: int = 20) -> list[CycleResult]:
        """获取最近循环历史."""
        return self._cycles[-n:]

    def get_last_cycle(self) -> CycleResult | None:
        """获取最后一次循环结果."""
        return self._cycles[-1] if self._cycles else None

    def get_agent_stats(self) -> dict[str, Any]:
        """获取 Agent 统计."""
        return self._agent.stats()

    # ── 重置 ──────────────────────────────────────────────────

    def reset(self) -> None:
        """重置编排器."""
        self._state = OrchestratorState.STOPPED
        self._cycles.clear()
        self._cycle_count = 0
        self._consecutive_errors = 0
        self._last_error_at = ""
        self._agent.reset()


# ═══════════════════════════════════════════════════════════════
# Factory Functions
# ═══════════════════════════════════════════════════════════════


def create_orchestrator(
    profile: AgentProfile | None = None,
    with_default_goals: bool = True,
) -> AgentOrchestrator:
    """创建默认编排器.

    Args:
        profile: Agent 配置
        with_default_goals: 是否创建默认目标

    Returns:
        AgentOrchestrator: 预配置的编排器
    """
    agent = create_growth_agent(profile=profile)
    orchestrator = AgentOrchestrator(agent=agent)

    if with_default_goals:
        orchestrator.set_default_goals([
            AgentGoal(
                title="Daily Performance Monitoring",
                description="监控每日广告表现指标",
                priority=GoalPriority.HIGH,
                success_criteria="ROAS > 0.8",
                target_metric="roas",
                target_value=0.8,
            ),
            AgentGoal(
                title="Creative Fatigue Detection",
                description="检测并响应素材疲劳",
                priority=GoalPriority.MEDIUM,
                success_criteria="Fatigue < 0.7",
                target_metric="creative_fatigue",
                target_value=0.3,
            ),
            AgentGoal(
                title="Budget Optimization",
                description="根据 ROAS 优化预算分配",
                priority=GoalPriority.HIGH,
                success_criteria="Budget efficiency improved",
                target_metric="roas",
                target_value=1.0,
            ),
        ])

    return orchestrator