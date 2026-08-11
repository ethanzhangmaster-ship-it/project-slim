"""E11.2.4 — RuntimeDaemon（持续运行的服务守护进程）。

将 AssetRuntime 从"手动调用"升级为"持续运行的服务"。

编排 6 个 Worker 的完整生命周期：
  - EagleScannerWorker:     每小时扫描 Eagle 库
  - FacebookWorker:         每小时拉取 Facebook 新广告
  - AdjustWorker:           每天拉取 Adjust 收入数据
  - BindingWorker:          事件驱动（无需单独轮询）
  - MaterializerWorker:     事件驱动（无需单独轮询）
  - LifecycleWorker:        事件驱动（无需单独轮询）

Daily Growth Loop（每天凌晨 2:00 执行）:
  1. Eagle Scan
  2. Facebook Sync
  3. Asset Binding（事件链自动触发）
  4. Adjust Revenue Sync
  5. Lifecycle Update
  6. Winner Discovery

Usage:
    daemon = RuntimeDaemon(runtime)
    daemon.run_once()      # 执行一次完整管线
    daemon.run_daily()     # 执行每日循环（阻塞）
    daemon.start()         # 启动守护进程（while True）
    daemon.stop()          # 停止守护进程
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .runtime import AssetRuntime
from .events.asset_events import AssetEvent, AssetEventType
from .connectors.facebook_connector import FacebookConnector
from .connectors.adjust_connector import AdjustConnector
from .workers.facebook_worker import FacebookWorker
from .workers.adjust_worker import AdjustWorker

logger = logging.getLogger(__name__)


class RunReport:
    """单次运行报告。"""

    def __init__(self) -> None:
        self.started_at: str = ""
        self.completed_at: str = ""
        self.eagle_scan: dict[str, int] = {}
        self.facebook_sync: dict[str, int] = {}
        self.adjust_sync: dict[str, int] = {}
        self.event_bus: dict[str, Any] = {}
        self.errors: list[str] = []
        self.elapsed_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "eagle_scan": self.eagle_scan,
            "facebook_sync": self.facebook_sync,
            "adjust_sync": self.adjust_sync,
            "event_bus": self.event_bus,
            "errors": self.errors,
            "elapsed_seconds": round(self.elapsed_seconds, 1),
        }


class RuntimeDaemon:
    """Creative Asset Runtime 守护进程。

    编排 6 个 Worker 的持续运行。

    Usage:
        runtime = AssetRuntime(...)
        daemon = RuntimeDaemon(runtime)
        daemon.run_once()  # 单次执行
    """

    # 默认轮询间隔（秒）
    DEFAULT_EAGLE_INTERVAL = 3600       # 每小时
    DEFAULT_FACEBOOK_INTERVAL = 3600    # 每小时
    DEFAULT_ADJUST_INTERVAL = 86400     # 每天

    def __init__(
        self,
        runtime: AssetRuntime,
        facebook_connector: FacebookConnector | None = None,
        adjust_connector: AdjustConnector | None = None,
        report_dir: str = "data/runtime/reports",
    ) -> None:
        self._runtime = runtime

        # Connectors
        self._facebook_connector = facebook_connector
        self._adjust_connector = adjust_connector

        # Workers
        self._facebook_worker = (
            FacebookWorker(facebook_connector)
            if facebook_connector else None
        )
        self._adjust_worker = (
            AdjustWorker(adjust_connector)
            if adjust_connector else None
        )

        # Report
        self._report_dir = Path(report_dir)
        self._report_dir.mkdir(parents=True, exist_ok=True)

        # State
        self._running = False
        self._run_count = 0
        self._last_report: RunReport | None = None

    # ── Public API ───────────────────────────────────────

    def run_once(self) -> RunReport:
        """执行一次完整管线。

        流程：
          1. Eagle Scan → 发现新素材
          2. Facebook Sync → 拉取新广告
          3. (事件链自动触发: Binding → Materialize → Lifecycle)
          4. Adjust Sync → 拉取收入数据
          5. (事件链自动触发: Performance → Winner Detection)

        Returns:
            RunReport
        """
        report = RunReport()
        report.started_at = datetime.now().isoformat()
        started = datetime.now()

        self._run_count += 1
        logger.info(f"RuntimeDaemon: run #{self._run_count} started")

        try:
            # Phase 1: Eagle Scan
            scan_result = self._runtime.run_eagle_scan_only()
            report.eagle_scan = {
                "total": scan_result.get("total", 0),
                "new": scan_result.get("new_count", scan_result.get("discovered", 0)),
                "changed": scan_result.get("changed_count", 0),
                "removed": scan_result.get("removed_count", 0),
            }

            # Phase 2: Facebook Sync
            if self._facebook_worker:
                fb_result = self._facebook_worker.run_once()
                report.facebook_sync = fb_result

            # Phase 3: Adjust Sync
            if self._adjust_worker:
                adj_result = self._adjust_worker.run_once()
                report.adjust_sync = adj_result

            # 事件总线统计
            report.event_bus = self._runtime.event_bus.get_stats()

            # 重试失败事件
            retried = self._runtime.event_bus.retry_failed()
            if retried > 0:
                logger.info(f"RuntimeDaemon: retried {retried} failed events")

        except Exception as e:
            report.errors.append(f"{type(e).__name__}: {e}")
            logger.error(f"RuntimeDaemon error: {e}")

        report.elapsed_seconds = (datetime.now() - started).total_seconds()
        report.completed_at = datetime.now().isoformat()

        self._last_report = report
        self._save_report(report)

        logger.info(
            f"RuntimeDaemon: run #{self._run_count} completed "
            f"({report.elapsed_seconds:.1f}s)"
        )
        return report

    def run_daily(self) -> None:
        """执行一次每日循环（阻塞，生产环境由 cron 调度）。"""
        self.run_once()
        summary = self._runtime.get_status().get("lifecycle_summary", "")
        logger.info(f"Daily loop completed\n{summary}")

    def start(
        self,
        eagle_interval: float | None = None,
        facebook_interval: float | None = None,
        adjust_interval: float | None = None,
        daily_at: str = "02:00",
    ) -> None:
        """启动守护进程（阻塞）。

        Args:
            eagle_interval:    Eagle 扫描间隔（秒），默认 3600
            facebook_interval: Facebook 拉取间隔（秒），默认 3600
            adjust_interval:   Adjust 拉取间隔（秒），默认 86400
            daily_at:          每日完整管线时间（HH:MM），默认 "02:00"
        """
        self._running = True
        eagle_interval = eagle_interval or self.DEFAULT_EAGLE_INTERVAL
        facebook_interval = facebook_interval or self.DEFAULT_FACEBOOK_INTERVAL
        adjust_interval = adjust_interval or self.DEFAULT_ADJUST_INTERVAL

        last_eagle = 0.0
        last_facebook = 0.0
        last_adjust = 0.0
        last_daily_check = ""

        logger.info("RuntimeDaemon: started")

        while self._running:
            now = time.time()
            now_str = datetime.now().strftime("%H:%M")

            # 每日完整管线
            if now_str == daily_at and last_daily_check != now_str:
                last_daily_check = now_str
                self.run_daily()

            # Eagle 扫描
            if now - last_eagle >= eagle_interval:
                self._runtime.run_eagle_scan_only()
                last_eagle = now

            # Facebook 同步
            if self._facebook_worker and now - last_facebook >= facebook_interval:
                self._facebook_worker.run_once()
                last_facebook = now

            # Adjust 同步
            if self._adjust_worker and now - last_adjust >= adjust_interval:
                self._adjust_worker.run_once()
                last_adjust = now

            # 重试失败事件
            self._runtime.event_bus.retry_failed()

            time.sleep(60)  # 每分钟检查一次

        logger.info("RuntimeDaemon: stopped")

    def stop(self) -> None:
        """停止守护进程。"""
        self._running = False
        if self._facebook_worker:
            self._facebook_worker.stop()
        if self._adjust_worker:
            self._adjust_worker.stop()
        self._runtime.shutdown()

    def get_status(self) -> dict[str, Any]:
        """获取守护进程状态。"""
        status = self._runtime.get_status()
        status.update({
            "daemon_running": self._running,
            "daemon_run_count": self._run_count,
            "facebook_connected": (
                self._facebook_connector.is_connected()
                if self._facebook_connector else False
            ),
            "adjust_connected": (
                self._adjust_connector.is_connected()
                if self._adjust_connector else False
            ),
            "last_report": self._last_report.to_dict() if self._last_report else None,
        })
        return status

    @property
    def report(self) -> RunReport | None:
        return self._last_report

    # ── Internal ────────────────────────────────────────

    def _save_report(self, report: RunReport) -> None:
        report_path = self._report_dir / f"run_{self._run_count:04d}.json"
        try:
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Failed to save report: {e}")

    def __repr__(self) -> str:
        return (
            f"RuntimeDaemon(runs={self._run_count}, "
            f"running={self._running})"
        )