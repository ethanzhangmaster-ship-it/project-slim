"""E11.2.4 — Facebook Worker (Polling Loop)。

将 FacebookConnector 包装为持续运行的 Worker。
负责定时拉取 Facebook 广告数据并发布事件。

事件流：
  Facebook Graph API → FacebookConnector.poll()
  → FACEBOOK_CREATIVE_CREATED
  → BindingWorker.on_facebook_synced()
  → ASSET_MATCHED

Usage:
    worker = FacebookWorker(connector)
    worker.run_once()    # 执行一次
    worker.run_loop()    # 持续轮询（仅测试用）
"""

from __future__ import annotations

import logging
import time
from datetime import datetime

from ..connectors.facebook_connector import FacebookConnector

logger = logging.getLogger(__name__)


class FacebookWorker:
    """Facebook 数据拉取 Worker。

    定时调用 FacebookConnector，将新广告数据注入事件总线。

    Attributes:
        run_count:       累计运行次数
        total_published: 累计发布事件数
    """

    def __init__(
        self,
        connector: FacebookConnector,
        poll_interval_seconds: float = 3600.0,  # 默认每小时
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
            {"published": int, "total_ads": int, "duration": float}
        """
        started = datetime.now()

        self.run_count += 1
        events = self._connector.poll()

        self.total_published += len(events)
        self.last_run_at = datetime.now()

        duration = (datetime.now() - started).total_seconds()

        logger.info(
            f"FacebookWorker: run #{self.run_count}, "
            f"{len(events)} creatives, {duration:.1f}s"
        )

        return {
            "published": len(events),
            "total_ads": len(events),
            "duration": round(duration, 1),
        }

    def run_once_insights(self) -> dict:
        """执行一次成效数据拉取。

        Returns:
            {"published": int, "duration": float}
        """
        started = datetime.now()
        events = self._connector.poll_insights()
        duration = (datetime.now() - started).total_seconds()

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
            f"FacebookWorker(runs={self.run_count}, "
            f"published={self.total_published})"
        )