"""E11.2.4 — Adjust Worker (Polling Loop)。

将 AdjustConnector 包装为持续运行的 Worker。
负责定时拉取 Adjust 收入数据并发布事件。

事件流：
  Adjust API → AdjustConnector.poll()
  → PERFORMANCE_UPDATED
  → LifecycleWorker.on_performance_updated()
  → WINNER_DETECTED / ASSET_FAILED

Usage:
    worker = AdjustWorker(connector)
    worker.run_once()    # 执行一次
    worker.run_loop()    # 持续轮询（仅测试用）
"""

from __future__ import annotations

import logging
import time
from datetime import datetime

from ..connectors.adjust_connector import AdjustConnector

logger = logging.getLogger(__name__)


class AdjustWorker:
    """Adjust 数据拉取 Worker。

    定时调用 AdjustConnector，将收入数据注入事件总线。

    Attributes:
        run_count:       累计运行次数
        total_published: 累计发布事件数
    """

    def __init__(
        self,
        connector: AdjustConnector,
        poll_interval_seconds: float = 86400.0,  # 默认每天
    ) -> None:
        self._connector = connector
        self._poll_interval = poll_interval_seconds

        self.run_count: int = 0
        self.total_published: int = 0
        self.last_run_at: datetime | None = None
        self._running = False

    # ── Public API ───────────────────────────────────────

    def run_once(self) -> dict:
        """执行一次拉取。

        Returns:
            {"published": int, "duration": float}
        """
        started = datetime.now()

        self.run_count += 1
        events = self._connector.poll()

        self.total_published += len(events)
        self.last_run_at = datetime.now()

        duration = (datetime.now() - started).total_seconds()

        logger.info(
            f"AdjustWorker: run #{self.run_count}, "
            f"{len(events)} records, {duration:.1f}s"
        )

        return {
            "published": len(events),
            "duration": round(duration, 1),
        }

    def run_loop(self, max_runs: int = 0) -> None:
        """持续轮询（仅测试用，生产环境使用 RuntimeDaemon）。

        Args:
            max_runs: 最大运行次数（0 = 无限）
        """
        self._running = True
        runs = 0

        while self._running:
            if max_runs > 0 and runs >= max_runs:
                break

            self.run_once()
            runs += 1

            if self._running:
                time.sleep(self._poll_interval)

        self._running = False

    def stop(self) -> None:
        """停止轮询。"""
        self._running = False

    def is_connected(self) -> bool:
        return self._connector.is_connected()

    def __repr__(self) -> str:
        return (
            f"AdjustWorker(runs={self.run_count}, "
            f"published={self.total_published})"
        )