"""E13.7.4.1 Runtime State — 生产运行状态管理.

RuntimeState 管理 ProductionGrowthRuntime 的完整运行状态:
  - 生命周期状态 (CREATED → RUNNING → STOPPED)
  - 循环计数和计时
  - 活跃 Job 追踪
  - 错误计数和恢复
  - 当前指标快照
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class RuntimeStatus(str, Enum):
    """Runtime 生命周期状态.

    CREATED → INITIALIZING → LOADING_MEMORY → CONNECTING_TOOLS → RUNNING
    RUNNING → PAUSED → RUNNING
    RUNNING → SAFE_MODE → RUNNING
    RUNNING → STOPPING → STOPPED
    RUNNING → FAILED
    FAILED → SAFE_MODE
    """
    CREATED = "created"
    INITIALIZING = "initializing"
    LOADING_MEMORY = "loading_memory"
    CONNECTING_TOOLS = "connecting_tools"
    RUNNING = "running"
    PAUSED = "paused"
    SAFE_MODE = "safe_mode"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


# 状态转换图
VALID_TRANSITIONS: dict[RuntimeStatus, set[RuntimeStatus]] = {
    RuntimeStatus.CREATED: {RuntimeStatus.INITIALIZING},
    RuntimeStatus.INITIALIZING: {RuntimeStatus.LOADING_MEMORY, RuntimeStatus.FAILED},
    RuntimeStatus.LOADING_MEMORY: {RuntimeStatus.CONNECTING_TOOLS, RuntimeStatus.FAILED},
    RuntimeStatus.CONNECTING_TOOLS: {RuntimeStatus.RUNNING, RuntimeStatus.FAILED},
    RuntimeStatus.RUNNING: {
        RuntimeStatus.PAUSED,
        RuntimeStatus.SAFE_MODE,
        RuntimeStatus.STOPPING,
        RuntimeStatus.FAILED,
    },
    RuntimeStatus.PAUSED: {RuntimeStatus.RUNNING, RuntimeStatus.STOPPING, RuntimeStatus.FAILED},
    RuntimeStatus.SAFE_MODE: {RuntimeStatus.RUNNING, RuntimeStatus.STOPPING, RuntimeStatus.FAILED},
    RuntimeStatus.STOPPING: {RuntimeStatus.STOPPED, RuntimeStatus.FAILED},
    RuntimeStatus.STOPPED: set(),
    RuntimeStatus.FAILED: {RuntimeStatus.SAFE_MODE, RuntimeStatus.STOPPING},
}


@dataclass
class RuntimeState:
    """Runtime 运行状态 — 管理的完整状态快照.

    Attributes:
        status: 当前生命周期状态
        cycle_count: 总循环次数
        successful_cycles: 成功循环次数
        failed_cycles: 失败循环次数
        last_cycle_at: 最后循环时间
        last_cycle_duration: 最后循环耗时 (秒)
        active_jobs: 活跃的 Job 名称列表
        error_count: 累计错误次数
        consecutive_errors: 连续错误次数
        metrics_snapshot: 当前指标快照
        started_at: Runtime 启动时间
        uptime_seconds: 运行时长
        metadata: 扩展元数据
    """
    status: RuntimeStatus = RuntimeStatus.CREATED
    cycle_count: int = 0
    successful_cycles: int = 0
    failed_cycles: int = 0
    last_cycle_at: str = ""
    last_cycle_duration: float = 0.0
    active_jobs: list[str] = field(default_factory=list)
    error_count: int = 0
    consecutive_errors: int = 0
    metrics_snapshot: dict[str, Any] = field(default_factory=dict)
    started_at: str = ""
    uptime_seconds: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── 状态转换 ──────────────────────────────────────────────

    def can_transition(self, target: RuntimeStatus) -> bool:
        """检查状态转换是否合法."""
        return target in VALID_TRANSITIONS.get(self.status, set())

    def transition(self, target: RuntimeStatus) -> bool:
        """执行状态转换.

        Returns:
            bool: 转换是否成功
        """
        if not self.can_transition(target):
            return False
        self.status = target
        return True

    # ── 循环追踪 ──────────────────────────────────────────────

    def record_cycle_start(self) -> None:
        """记录循环开始."""
        self.cycle_count += 1

    def record_cycle_success(self, duration_seconds: float = 0) -> None:
        """记录成功循环."""
        self.successful_cycles += 1
        self.last_cycle_at = datetime.now(timezone.utc).isoformat()
        self.last_cycle_duration = duration_seconds
        self.consecutive_errors = 0

    def record_cycle_failure(self, duration_seconds: float = 0) -> None:
        """记录失败循环."""
        self.failed_cycles += 1
        self.error_count += 1
        self.consecutive_errors += 1
        self.last_cycle_at = datetime.now(timezone.utc).isoformat()
        self.last_cycle_duration = duration_seconds

    # ── 指标 ──────────────────────────────────────────────────

    def update_metrics(self, metrics: dict[str, Any]) -> None:
        """更新指标快照."""
        self.metrics_snapshot.update(metrics)

    def update_uptime(self) -> None:
        """更新运行时长."""
        if self.started_at:
            started = datetime.fromisoformat(self.started_at)
            self.uptime_seconds = (
                datetime.now(timezone.utc) - started
            ).total_seconds()

    # ── Job 管理 ──────────────────────────────────────────────

    def register_job(self, job_name: str) -> None:
        """注册一个活跃 Job."""
        if job_name not in self.active_jobs:
            self.active_jobs.append(job_name)

    def unregister_job(self, job_name: str) -> None:
        """注销一个 Job."""
        if job_name in self.active_jobs:
            self.active_jobs.remove(job_name)

    # ── 快照 ──────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        self.update_uptime()
        return {
            "status": self.status.value,
            "cycle_count": self.cycle_count,
            "successful_cycles": self.successful_cycles,
            "failed_cycles": self.failed_cycles,
            "success_rate": (
                self.successful_cycles / max(self.cycle_count, 1)
            ),
            "last_cycle_at": self.last_cycle_at,
            "last_cycle_duration": self.last_cycle_duration,
            "active_jobs": self.active_jobs,
            "error_count": self.error_count,
            "consecutive_errors": self.consecutive_errors,
            "metrics_snapshot": self.metrics_snapshot,
            "started_at": self.started_at,
            "uptime_seconds": self.uptime_seconds,
            "metadata": self.metadata,
        }

    def reset(self) -> None:
        """重置状态."""
        self.status = RuntimeStatus.CREATED
        self.cycle_count = 0
        self.successful_cycles = 0
        self.failed_cycles = 0
        self.last_cycle_at = ""
        self.last_cycle_duration = 0.0
        self.active_jobs.clear()
        self.error_count = 0
        self.consecutive_errors = 0
        self.metrics_snapshot.clear()
        self.started_at = ""
        self.uptime_seconds = 0.0
        self.metadata.clear()


def create_runtime_state() -> RuntimeState:
    """创建默认运行时状态."""
    return RuntimeState()