"""Growth Loop 定时调度器 — 7×24 无人值守运行。

GrowthLoopScheduler 在后台线程中周期性触发 GrowthLoopOrchestrator.run_cycle，
实现 GrowthLoop 的自主运行 (autonomous mode)。

核心能力:
  - 周期性触发: 按 interval_hours 间隔自动运行 cycle
  - 并发保护: 文件锁防止多实例同时运行
  - 断点续跑: 复用 LoopPersistence, 启动时恢复 loop_state
  - 优雅停止: stop() 等待当前 cycle 完成后退出
  - 状态查询: get_status() 返回调度器运行状态
  - 错误隔离: 单次 cycle 失败不影响后续调度

调度流程:
  start(interval_hours=6.0, dry_run=True, fetch_meta_ads=False)
    → 后台线程启动
    → 等待 interval_hours (或立即触发首次)
    → 获取文件锁
    → 实例化 GrowthLoopOrchestrator (自动恢复 LoopState)
    → run_cycle()
    → 更新 LoopState.mode=autonomous, next_cycle_at
    → 释放锁
    → 等待下一个 interval
    → 循环直到 stop()

持久化:
  - data/growth_loop/scheduler_state.json — 调度器状态
  - data/growth_loop/scheduler.lock — 文件锁
  - data/growth_loop/loop_state.json — LoopState (由 Orchestrator 维护)
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now_utc().isoformat()


class GrowthLoopScheduler:
    """GrowthLoop 定时调度器。

    在后台线程中周期性触发 GrowthLoop cycle。
    线程安全: 内部使用 threading.Lock 保护状态。
    并发保护: 文件锁防止多进程/多实例同时运行 cycle。
    """

    LOCK_FILE = "scheduler.lock"
    STATE_FILE = "scheduler_state.json"

    def __init__(
        self,
        data_dir: str = "data/growth_loop",
        project_root: str | None = None,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.data_dir / self.LOCK_FILE
        self.state_path = self.data_dir / self.STATE_FILE

        # project_root 用于定位 scripts 目录
        if project_root:
            self.project_root = Path(project_root)
        else:
            # 从 data_dir 推断: data/growth_loop → 上两级
            self.project_root = self.data_dir.parent.parent

        # 线程安全锁
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        # 调度配置
        self._interval_hours: float = 6.0
        self._dry_run: bool = True
        self._fetch_meta_ads: bool = False
        self._run_immediately: bool = True

        # 运行状态
        self._running: bool = False
        self._cycle_in_progress: bool = False
        self._last_cycle_result: dict[str, Any] = {}
        self._last_cycle_at: str = ""
        self._next_cycle_at: str = ""
        self._last_error: str = ""
        self._total_scheduled_cycles: int = 0
        self._total_successful_cycles: int = 0
        self._total_failed_cycles: int = 0
        self._started_at: str = ""

    # ──────────────────────────────────────
    # 公开 API
    # ──────────────────────────────────────

    def start(
        self,
        interval_hours: float = 6.0,
        dry_run: bool = True,
        fetch_meta_ads: bool = False,
        run_immediately: bool = True,
    ) -> dict[str, Any]:
        """启动调度器。

        Args:
            interval_hours: 调度间隔 (小时), 最小 0.01 (约 36 秒)
            dry_run: 是否 dry-run 模式
            fetch_meta_ads: 是否拉取真实 Meta Ads 数据
            run_immediately: 是否立即执行首次 cycle

        Returns:
            调度器状态 dict
        """
        with self._lock:
            if self._running:
                return self._build_status_dict(already_running=True)

            self._interval_hours = max(interval_hours, 0.01)
            self._dry_run = dry_run
            self._fetch_meta_ads = fetch_meta_ads
            self._run_immediately = run_immediately
            self._stop_event.clear()
            self._running = True
            self._started_at = _now_iso()
            self._total_scheduled_cycles = 0
            self._total_successful_cycles = 0
            self._total_failed_cycles = 0
            self._last_error = ""

            # 计算首次执行时间
            if run_immediately:
                self._next_cycle_at = _now_iso()
            else:
                self._next_cycle_at = self._compute_next_cycle_time()

            # 启动后台线程
            self._thread = threading.Thread(
                target=self._run_loop,
                name="GrowthLoopScheduler",
                daemon=True,
            )
            self._thread.start()

            logger.info(
                "Scheduler started: interval=%.2fh dry_run=%s fetch_meta_ads=%s immediate=%s",
                self._interval_hours, self._dry_run, self._fetch_meta_ads, run_immediately,
            )

            return self._build_status_dict(started=True)

    def stop(self, timeout: float = 30.0) -> dict[str, Any]:
        """停止调度器。

        Args:
            timeout: 等待线程结束的超时时间 (秒)

        Returns:
            调度器状态 dict
        """
        with self._lock:
            if not self._running:
                return self._build_status_dict(not_running=True)

            self._stop_event.set()
            self._running = False
            thread = self._thread

        # 在锁外等待线程结束, 避免死锁
        if thread and thread.is_alive():
            thread.join(timeout=timeout)

        with self._lock:
            self._thread = None
            self._next_cycle_at = ""
            self._cycle_in_progress = False

        logger.info("Scheduler stopped")
        return self._build_status_dict(stopped=True)

    def trigger_now(self) -> dict[str, Any]:
        """立即触发一次 cycle (不影响调度节奏)。

        Returns:
            触发结果
        """
        with self._lock:
            if self._cycle_in_progress:
                return {"status": "skipped", "reason": "cycle_in_progress"}
            if not self._running:
                return {"status": "skipped", "reason": "scheduler_not_running"}

        # 在后台执行
        result = self._execute_cycle()
        return result

    def get_status(self) -> dict[str, Any]:
        """获取调度器状态。"""
        with self._lock:
            return self._build_status_dict()

    # ──────────────────────────────────────
    # 内部实现
    # ──────────────────────────────────────

    def _run_loop(self) -> None:
        """后台线程主循环。"""
        logger.info("Scheduler loop started")

        while not self._stop_event.is_set():
            # 等待到执行时间
            now = _now_utc()
            if self._next_cycle_at:
                try:
                    next_dt = datetime.fromisoformat(self._next_cycle_at)
                    wait_seconds = (next_dt - now).total_seconds()
                except (ValueError, TypeError):
                    wait_seconds = 0
            else:
                wait_seconds = 0

            if wait_seconds > 0:
                # 分段等待, 支持快速响应 stop
                slept = 0.0
                while slept < wait_seconds and not self._stop_event.is_set():
                    sleep_chunk = min(1.0, wait_seconds - slept)
                    time.sleep(sleep_chunk)
                    slept += sleep_chunk

            if self._stop_event.is_set():
                break

            # 执行 cycle
            try:
                with self._lock:
                    self._cycle_in_progress = True
                    self._total_scheduled_cycles += 1

                result = self._execute_cycle_with_lock()

                with self._lock:
                    self._cycle_in_progress = False
                    if result.get("status") == "completed":
                        self._total_successful_cycles += 1
                        self._last_cycle_result = result
                        self._last_error = ""
                    else:
                        self._total_failed_cycles += 1
                        self._last_error = result.get("error", "unknown")

                    self._last_cycle_at = _now_iso()

            except Exception as exc:
                logger.exception("Scheduler cycle failed")
                with self._lock:
                    self._cycle_in_progress = False
                    self._total_failed_cycles += 1
                    self._last_error = str(exc)
                    self._last_cycle_at = _now_iso()

            # 计算下一次执行时间
            if not self._stop_event.is_set():
                with self._lock:
                    self._next_cycle_at = self._compute_next_cycle_time()

        logger.info("Scheduler loop exited")

    def _execute_cycle_with_lock(self) -> dict[str, Any]:
        """获取文件锁后执行 cycle。"""
        # 尝试获取文件锁
        lock_acquired = False
        try:
            lock_acquired = self._acquire_lock()
            if not lock_acquired:
                logger.warning("Lock not acquired, skipping cycle (another instance running)")
                return {
                    "status": "skipped",
                    "reason": "lock_busy",
                    "error": "另一个实例正在运行",
                }

            return self._execute_cycle()

        finally:
            if lock_acquired:
                self._release_lock()

    def _execute_cycle(self) -> dict[str, Any]:
        """执行一次 GrowthLoop cycle。

        复用 /api/loop/trigger 的核心逻辑。
        """
        import sys as _sys

        scripts_dir = str(self.project_root / "scripts")
        if scripts_dir not in _sys.path:
            _sys.path.insert(0, scripts_dir)

        try:
            from scripts.growth_loop_orchestrator import GrowthLoopOrchestrator
        except ImportError as exc:
            logger.error("GrowthLoopOrchestrator import failed: %s", exc)
            return {"status": "failed", "error": f"import_failed: {exc}"}

        # 可选: 拉取真实 Meta Ads 数据
        loop_input = None
        meta_data_info: dict = {}
        if self._fetch_meta_ads:
            try:
                from src.market_ops.workspace.meta_ads_fetcher import MetaAdsDataFetcher
                fetcher = MetaAdsDataFetcher()
                if not fetcher.is_configured():
                    logger.warning("fetch_meta_ads=true but Meta credentials not configured")
                    meta_data_info = {"fetch_error": "credentials_not_configured"}
                else:
                    loop_input = fetcher.fetch(days=7)
                    if loop_input.fetch_error:
                        meta_data_info = {"fetch_error": loop_input.fetch_error}
                    else:
                        meta_data_info = {
                            "creatives_fetched": loop_input.creative_count,
                            "signals_generated": len(loop_input.signals),
                        }
            except Exception as exc:
                logger.exception("Meta Ads fetch failed in scheduler")
                meta_data_info = {"fetch_error": str(exc)}

        # 构建 Orchestrator
        kwargs: dict = {
            "data_dir": str(self.data_dir),
            "dry_run": self._dry_run,
        }

        if loop_input and not loop_input.fetch_error:
            if loop_input.reality_scores:
                kwargs["reality_scores"] = loop_input.reality_scores
            if loop_input.game_id_resolver:
                kwargs["game_id_resolver"] = loop_input.game_id_resolver

        # Live 模式注入 MetaAdsPlatformAdapter
        if not self._dry_run and loop_input and not loop_input.fetch_error:
            try:
                from scripts.meta_ads_adapter import MetaAdsPlatformAdapter
                from market_ops.execution_runtime.adapters.facebook import FacebookClient
                client = FacebookClient()
                kwargs["adapter"] = MetaAdsPlatformAdapter(client)
            except Exception as exc:
                logger.warning("MetaAdsPlatformAdapter injection failed: %s", exc)

        try:
            orchestrator = GrowthLoopOrchestrator(**kwargs)
            start_time = time.time()

            # 更新 LoopState 为 autonomous 模式
            orchestrator.state.mode = "autonomous"
            orchestrator.state.interval_hours = self._interval_hours

            # 构造 run_cycle 参数
            cycle_kwargs: dict = {}
            if loop_input and not loop_input.fetch_error:
                cycle_kwargs["signals"] = loop_input.signals if loop_input.signals else None
                cycle_kwargs["current_metrics"] = loop_input.current_metrics
                cycle_kwargs["previous_metrics"] = loop_input.previous_metrics
                cycle_kwargs["creative_to_adset_map"] = loop_input.creative_to_adset_map
                cycle_kwargs["current_budgets"] = loop_input.current_budgets

                def post_metrics_provider(pending: Any) -> dict[str, float]:
                    cid = getattr(pending, "creative_id", "")
                    return loop_input.current_metrics.get(cid, {})

                cycle_kwargs["post_metrics_provider"] = post_metrics_provider

            result = orchestrator.run_cycle(**cycle_kwargs)
            duration = round(time.time() - start_time, 2)

            actions = getattr(result, "actions", [])
            execution_results = getattr(result, "execution_results", [])
            success_count = sum(
                1 for e in execution_results
                if (isinstance(e, dict) and e.get("success"))
                or (not isinstance(e, dict) and getattr(e, "success", False))
            )

            response = {
                "status": "completed",
                "cycle_number": getattr(result, "cycle_number", 0),
                "dry_run": self._dry_run,
                "fetch_meta_ads": self._fetch_meta_ads,
                "duration_seconds": duration,
                "actions_planned": len(actions),
                "actions_executed": len(execution_results),
                "actions_succeeded": success_count,
                "success_rate": round(success_count / max(len(execution_results), 1), 2),
                "evaluated_count": getattr(result, "evaluated_count", 0),
                "pending_created": getattr(result, "pending_created", 0),
            }

            if meta_data_info:
                response["meta_ads_data"] = meta_data_info

            logger.info(
                "Scheduled cycle #%s completed: %d actions, %.1fs",
                response["cycle_number"], response["actions_planned"], duration,
            )
            return response

        except Exception as exc:
            logger.exception("Scheduled cycle execution failed")
            return {"status": "failed", "error": str(exc)}

    def _compute_next_cycle_time(self) -> str:
        """计算下一次 cycle 执行时间。"""
        next_dt = _now_utc() + timedelta_from_hours(self._interval_hours)
        return next_dt.isoformat()

    # ──────────────────────────────────────
    # 文件锁
    # ──────────────────────────────────────

    def _acquire_lock(self) -> bool:
        """尝试获取文件锁 (非阻塞)。

        使用原子性文件创建实现: 如果 lock 文件已存在则失败。
        """
        try:
            # O_CREAT | O_EXCL: 原子性创建, 文件已存在则失败
            fd = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            lock_content = {
                "pid": os.getpid(),
                "thread": threading.current_thread().name,
                "acquired_at": _now_iso(),
            }
            os.write(fd, json.dumps(lock_content).encode("utf-8"))
            os.close(fd)
            return True
        except FileExistsError:
            # 检查锁是否过期 (超过 1 小时视为僵尸锁)
            try:
                stat = self.lock_path.stat()
                age = time.time() - stat.st_mtime
                if age > 3600:
                    logger.warning("Removing stale lock (age=%.0fs)", age)
                    self.lock_path.unlink(missing_ok=True)
                    return self._acquire_lock()
            except OSError:
                pass
            return False
        except OSError as exc:
            logger.error("Lock acquire failed: %s", exc)
            return False

    def _release_lock(self) -> None:
        """释放文件锁。"""
        try:
            self.lock_path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Lock release failed: %s", exc)

    # ──────────────────────────────────────
    # 状态构建
    # ──────────────────────────────────────

    def _build_status_dict(self, **extra: Any) -> dict[str, Any]:
        """构建调度器状态 dict。"""
        status = {
            "running": self._running,
            "cycle_in_progress": self._cycle_in_progress,
            "interval_hours": self._interval_hours,
            "dry_run": self._dry_run,
            "fetch_meta_ads": self._fetch_meta_ads,
            "started_at": self._started_at,
            "last_cycle_at": self._last_cycle_at,
            "next_cycle_at": self._next_cycle_at,
            "total_scheduled_cycles": self._total_scheduled_cycles,
            "total_successful_cycles": self._total_successful_cycles,
            "total_failed_cycles": self._total_failed_cycles,
            "last_error": self._last_error,
            "last_cycle_result": self._last_cycle_result if self._last_cycle_result else None,
        }
        status.update(extra)
        return status

    def save_state(self) -> None:
        """保存调度器状态到文件 (用于跨重启恢复)。"""
        state = self._build_status_dict()
        state["saved_at"] = _now_iso()
        try:
            self.state_path.write_text(
                json.dumps(state, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.warning("Failed to save scheduler state: %s", exc)

    def load_state(self) -> dict[str, Any] | None:
        """从文件加载调度器状态。"""
        if not self.state_path.exists():
            return None
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load scheduler state: %s", exc)
            return None


def timedelta_from_hours(hours: float):
    """小时数转 timedelta。"""
    from datetime import timedelta
    return timedelta(hours=hours)
