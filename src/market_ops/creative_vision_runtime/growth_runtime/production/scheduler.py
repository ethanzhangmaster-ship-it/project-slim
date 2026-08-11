"""E15.0.4 Production Scheduler — 生产级调度器.

负责:
  - 每小时: 拉取数据 → 分析 → 生成动作 → 执行
  - 多产品并行调度
  - 失败重试
  - 健康状态集成

E15.0.8 升级: 支持 RedisStateManager 分布式锁，避免多实例并发.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from ..storage.redis_state import RedisStateManager

logger = logging.getLogger(__name__)


class SchedulerState(str, Enum):
    """调度器状态."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class ProductionScheduler:
    """生产调度器 — 管理周期性的增长循环.

    用法:
        scheduler = ProductionScheduler(interval_minutes=60)
        scheduler.on_tick = my_tick_handler
        scheduler.start()

    E15.0.8 分布式锁:
        redis = RedisStateManager()
        redis.connect()
        scheduler = ProductionScheduler(redis=redis)
        scheduler.tick()  # 自动获取/释放分布式锁
    """

    def __init__(
        self,
        interval_minutes: int = 60,
        max_retries: int = 3,
        retry_delay_seconds: int = 30,
        redis: "RedisStateManager | None" = None,
        scheduler_name: str = "default",
    ):
        self._interval_minutes = interval_minutes
        self._max_retries = max_retries
        self._retry_delay_seconds = retry_delay_seconds
        self._redis = redis
        self._scheduler_name = scheduler_name
        self._state: SchedulerState = SchedulerState.IDLE
        self._on_tick: Callable[[], dict[str, Any]] | None = None
        self._on_error: Callable[[Exception], None] | None = None

        self._tick_count: int = 0
        self._success_count: int = 0
        self._failure_count: int = 0
        self._last_tick_time: str = ""
        self._last_result: dict[str, Any] = {}
        self._started_at: str = ""
        self._errors: list[dict[str, Any]] = []

    # ── Properties ───────────────────────────────────────────

    @property
    def state(self) -> SchedulerState:
        return self._state

    @property
    def is_running(self) -> bool:
        return self._state == SchedulerState.RUNNING

    @property
    def tick_count(self) -> int:
        return self._tick_count

    @property
    def success_rate(self) -> float:
        total = self._success_count + self._failure_count
        if total == 0:
            return 1.0
        return self._success_count / total

    # ── Callbacks ────────────────────────────────────────────

    def on_tick(self, handler: Callable[[], dict[str, Any]]) -> None:
        """注册 tick 回调 (每次调度周期执行)."""
        self._on_tick = handler

    def on_error(self, handler: Callable[[Exception], None]) -> None:
        """注册错误回调."""
        self._on_error = handler

    # ── Lifecycle ────────────────────────────────────────────

    def start(self) -> None:
        """启动调度器."""
        self._state = SchedulerState.RUNNING
        self._started_at = datetime.now(timezone.utc).isoformat()

    def pause(self) -> None:
        """暂停调度器."""
        if self._state == SchedulerState.RUNNING:
            self._state = SchedulerState.PAUSED

    def resume(self) -> None:
        """恢复调度器."""
        if self._state == SchedulerState.PAUSED:
            self._state = SchedulerState.RUNNING

    def stop(self) -> None:
        """停止调度器."""
        self._state = SchedulerState.STOPPED

    # ── Tick ─────────────────────────────────────────────────

    def tick(self) -> dict[str, Any]:
        """执行一次调度周期.

        流程:
          1. 检查是否应该执行
          2. 获取分布式锁 (E15.0.8 Redis)
          3. 执行回调 (带重试)
          4. 记录结果
          5. 释放锁

        Returns:
            执行结果
        """
        if self._state != SchedulerState.RUNNING:
            return {"status": "skipped", "reason": f"Scheduler is {self._state.value}"}

        # E15.0.8: 获取分布式锁
        lock_acquired = False
        if self._redis is not None:
            lock_acquired = self._redis.acquire_scheduler_lock(
                self._scheduler_name,
                ttl=self._interval_minutes * 60 + 300,  # interval + 5min buffer
            )
            if not lock_acquired:
                holder = self._redis.get_lock_holder(self._scheduler_name)
                return {
                    "status": "skipped",
                    "reason": f"Lock held by {holder}",
                }

        self._tick_count += 1
        self._last_tick_time = datetime.now(timezone.utc).isoformat()

        if self._on_tick is None:
            if lock_acquired:
                self._redis.release_scheduler_lock(self._scheduler_name)
            return {"status": "skipped", "reason": "No tick handler registered"}

        last_error = None
        try:
            for attempt in range(1, self._max_retries + 1):
                try:
                    result = self._on_tick()
                    self._success_count += 1
                    self._last_result = result
                    return {
                        "status": "success",
                        "attempt": attempt,
                        "result": result,
                        "tick": self._tick_count,
                    }
                except Exception as e:
                    last_error = e
                    self._errors.append({
                        "tick": self._tick_count,
                        "attempt": attempt,
                        "error": str(e),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                    if self._on_error:
                        self._on_error(e)
                    if attempt < self._max_retries:
                        time.sleep(self._retry_delay_seconds)

            self._failure_count += 1
            self._state = SchedulerState.ERROR
            return {
                "status": "error",
                "attempts": self._max_retries,
                "error": str(last_error),
                "tick": self._tick_count,
            }
        finally:
            # E15.0.8: 释放分布式锁
            if lock_acquired:
                try:
                    self._redis.release_scheduler_lock(self._scheduler_name)
                except Exception as e:
                    logger.warning(f"Failed to release scheduler lock: {e}")

    def should_tick(self) -> bool:
        """检查是否应该执行下一次 tick."""
        if self._state != SchedulerState.RUNNING:
            return False
        if not self._last_tick_time:
            return True
        try:
            last = datetime.fromisoformat(self._last_tick_time)
            next_tick = last + timedelta(minutes=self._interval_minutes)
            return datetime.now(timezone.utc) >= next_tick
        except (ValueError, TypeError):
            return True

    # ── Statistics ───────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """获取调度器统计."""
        return {
            "state": self._state.value,
            "started_at": self._started_at,
            "tick_count": self._tick_count,
            "success_count": self._success_count,
            "failure_count": self._failure_count,
            "success_rate": self.success_rate,
            "last_tick_time": self._last_tick_time,
            "interval_minutes": self._interval_minutes,
            "recent_errors": self._errors[-5:],
        }

    def get_uptime_seconds(self) -> float:
        """获取运行时间 (秒)."""
        if not self._started_at:
            return 0.0
        try:
            start = datetime.fromisoformat(self._started_at)
            return (datetime.now(timezone.utc) - start).total_seconds()
        except (ValueError, TypeError):
            return 0.0

    def reset(self) -> None:
        """重置调度器."""
        self._state = SchedulerState.IDLE
        self._tick_count = 0
        self._success_count = 0
        self._failure_count = 0
        self._last_tick_time = ""
        self._last_result = {}
        self._started_at = ""
        self._errors.clear()