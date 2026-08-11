"""E13.7.4.1 Agent Scheduler — 生产调度器.

Agent Scheduler 不是简单的 sleep 循环，而是基于 Job 模型的调度系统:

Job 类型:
  - Reality Observation (每 5 分钟): 获取 Meta Ads / Adjust 数据
  - Growth Analysis (每小时): 素材疲劳检测、异常检测
  - Strategy Review (每天): 模式记忆、策略记忆更新

特性:
  - 优先级排序
  - 启用/禁用
  - 上次执行时间追踪
  - 错过调度补偿
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable


class JobPriority(int, Enum):
    """Job 优先级."""
    CRITICAL = 0      # 必须先执行 (如: 数据获取)
    HIGH = 1           # 高优先级 (如: 疲劳检测)
    MEDIUM = 2         # 中优先级 (如: 策略更新)
    LOW = 3            # 低优先级 (如: 报告生成)


class JobStatus(str, Enum):
    """Job 执行状态."""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    DISABLED = "disabled"


@dataclass
class AgentJob:
    """Agent 调度任务.

    Attributes:
        name: 任务名称
        interval_seconds: 执行间隔 (秒)
        handler: 执行函数
        priority: 优先级
        enabled: 是否启用
        status: 当前状态
        last_run_at: 上次执行时间
        next_run_at: 下次执行时间
        run_count: 执行次数
        error_count: 错误次数
        max_retries: 最大重试次数
        timeout_seconds: 超时时间
        metadata: 扩展元数据
    """
    name: str = ""
    interval_seconds: float = 300.0
    handler: Callable[[], Any] | None = None
    priority: JobPriority = JobPriority.MEDIUM
    enabled: bool = True
    status: JobStatus = JobStatus.IDLE
    last_run_at: str = ""
    next_run_at: str = ""
    run_count: int = 0
    error_count: int = 0
    max_retries: int = 1
    timeout_seconds: float = 120.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_due(self) -> bool:
        """检查是否到了执行时间."""
        if not self.enabled:
            return False
        if not self.next_run_at:
            return True
        return datetime.now(timezone.utc).isoformat() >= self.next_run_at

    @property
    def missed_schedule(self) -> bool:
        """检查是否错过了调度."""
        if not self.next_run_at or not self.last_run_at:
            return False
        next_run = datetime.fromisoformat(self.next_run_at)
        return datetime.now(timezone.utc) > next_run

    def schedule_next(self) -> None:
        """计算下次执行时间."""
        now = datetime.now(timezone.utc)
        self.next_run_at = (
            datetime.fromtimestamp(now.timestamp() + self.interval_seconds)
            .isoformat()
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "interval_seconds": self.interval_seconds,
            "priority": self.priority.value,
            "enabled": self.enabled,
            "status": self.status.value,
            "last_run_at": self.last_run_at,
            "next_run_at": self.next_run_at,
            "run_count": self.run_count,
            "error_count": self.error_count,
            "is_due": self.is_due,
        }


@dataclass
class AgentScheduler:
    """Agent 调度器 — 管理定期任务的执行.

    用法:
        scheduler = AgentScheduler()
        scheduler.register_job(AgentJob(
            name="reality_observation",
            interval_seconds=300,
            handler=observe_reality,
            priority=JobPriority.CRITICAL,
        ))
        scheduler.start()  # 后台线程
        scheduler.stop()
    """

    def __init__(self):
        self._jobs: dict[str, AgentJob] = {}
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._check_interval = 1.0  # 每秒检查一次

    # ── Properties ────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def job_count(self) -> int:
        return len(self._jobs)

    # ── Job 管理 ──────────────────────────────────────────────

    def register_job(self, job: AgentJob) -> None:
        """注册一个调度任务."""
        with self._lock:
            job.schedule_next()
            self._jobs[job.name] = job

    def unregister_job(self, name: str) -> None:
        """注销一个调度任务."""
        with self._lock:
            self._jobs.pop(name, None)

    def get_job(self, name: str) -> AgentJob | None:
        """获取任务."""
        return self._jobs.get(name)

    def enable_job(self, name: str) -> None:
        """启用任务."""
        job = self._jobs.get(name)
        if job:
            job.enabled = True
            job.schedule_next()

    def disable_job(self, name: str) -> None:
        """禁用任务."""
        job = self._jobs.get(name)
        if job:
            job.enabled = False
            job.status = JobStatus.DISABLED

    def list_jobs(self) -> list[AgentJob]:
        """列出所有任务."""
        return list(self._jobs.values())

    def get_due_jobs(self) -> list[AgentJob]:
        """获取到期任务 (按优先级排序)."""
        with self._lock:
            due = [j for j in self._jobs.values() if j.is_due and j.enabled]
            return sorted(due, key=lambda j: j.priority.value)

    # ── 执行 ──────────────────────────────────────────────────

    def execute_job(self, job: AgentJob) -> bool:
        """执行单个任务.

        Returns:
            bool: 是否成功
        """
        if not job.handler:
            return False

        job.status = JobStatus.RUNNING
        job.run_count += 1

        try:
            job.handler()
            job.status = JobStatus.COMPLETED
            job.last_run_at = datetime.now(timezone.utc).isoformat()
            job.schedule_next()
            return True
        except Exception:
            job.error_count += 1
            if job.error_count <= job.max_retries:
                job.status = JobStatus.IDLE
            else:
                job.status = JobStatus.FAILED
            return False

    def execute_once(self) -> int:
        """执行所有到期任务一次.

        Returns:
            int: 执行的任务数
        """
        due_jobs = self.get_due_jobs()
        count = 0
        for job in due_jobs:
            self.execute_job(job)
            count += 1
        return count

    # ── 调度循环 ──────────────────────────────────────────────

    def start(self) -> None:
        """启动调度器 (后台线程)."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """停止调度器."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

    def _scheduler_loop(self) -> None:
        """调度器主循环."""
        while self._running:
            try:
                self.execute_once()
            except Exception:
                pass
            time.sleep(self._check_interval)

    # ── 统计 ──────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """获取调度器统计."""
        jobs = self.list_jobs()
        return {
            "running": self._running,
            "job_count": len(jobs),
            "enabled_jobs": sum(1 for j in jobs if j.enabled),
            "running_jobs": sum(1 for j in jobs if j.status == JobStatus.RUNNING),
            "failed_jobs": sum(1 for j in jobs if j.status == JobStatus.FAILED),
            "jobs": [j.to_dict() for j in jobs],
        }

    def reset(self) -> None:
        """重置调度器."""
        self.stop()
        self._jobs.clear()


# ═══════════════════════════════════════════════════════════════
# Factory Functions
# ═══════════════════════════════════════════════════════════════


def create_default_jobs() -> list[AgentJob]:
    """创建默认生产调度任务.

    默认三个任务:
      - Reality Observation: 每 5 分钟拉取实时数据
      - Growth Analysis: 每小时执行增长诊断
      - Strategy Review: 每天执行战略复盘
    """
    return [
        AgentJob(
            name="reality_observation",
            interval_seconds=300,
            handler=None,
            priority=JobPriority.CRITICAL,
            metadata={"description": "Pull real-time Meta Ads and Adjust data"},
        ),
        AgentJob(
            name="growth_analysis",
            interval_seconds=3600,
            handler=None,
            priority=JobPriority.HIGH,
            metadata={"description": "Creative fatigue, campaign decay, audience saturation"},
        ),
        AgentJob(
            name="strategy_review",
            interval_seconds=86400,
            handler=None,
            priority=JobPriority.MEDIUM,
            metadata={"description": "Daily strategic review: winners, losers, budget adjustment"},
        ),
    ]


def create_scheduler(with_default_jobs: bool = True) -> AgentScheduler:
    """创建默认调度器."""
    scheduler = AgentScheduler()
    if with_default_jobs:
        for job in create_default_jobs():
            scheduler.register_job(job)
    return scheduler