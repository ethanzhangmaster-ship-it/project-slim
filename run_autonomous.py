"""7×24 无人值守守护进程入口 — AI Game Studio OS.

一键启动后端服务 + GrowthLoop 定时调度器, 实现 7×24 自主运行.

启动流程:
  1. 启动 uvicorn 后端 (FastAPI app)
  2. 后端就绪后, 调用 /api/loop/scheduler/start 启动调度器
  3. 调度器在后台线程周期性触发 GrowthLoop cycle
  4. Ctrl+C 优雅停止: 先停调度器, 再停后端

用法:
    # 默认: dry-run 模式, 6 小时间隔, 不拉取 Meta Ads
    python run_autonomous.py

    # 自定义间隔 (小时)
    python run_autonomous.py --interval 4.0

    # 真实执行模式 (需配置 META_ACCESS_TOKEN)
    python run_autonomous.py --live --interval 6.0

    # 自定义端口
    python run_autonomous.py --port 8000

    # 仅启动后端, 不自动启动调度器
    python run_autonomous.py --no-scheduler

运维说明:
    - 后端启动后, 调度器也可通过 API 手动控制:
        POST /api/loop/scheduler/start
        POST /api/loop/scheduler/stop
        GET  /api/loop/scheduler/status
        POST /api/loop/scheduler/trigger
    - 调度器状态持久化到 data/growth_loop/scheduler_state.json
    - 文件锁 data/growth_loop/scheduler.lock 防止多实例冲突
    - 单次 cycle 失败不影响后续调度 (错误隔离)
"""
from __future__ import annotations

import argparse
import logging
import signal
import sys
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

logger = logging.getLogger("autonomous")


def start_backend(port: int, host: str) -> "uvicorn.Server":  # type: ignore[name-defined]
    """启动 uvicorn 后端服务 (非阻塞, 返回 server 实例)."""
    import uvicorn
    from src.market_ops.workspace.app import app

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=False,
    )
    server = uvicorn.Server(config)

    # 在后台线程运行 server, 避免阻塞主线程
    server_thread = threading.Thread(
        target=server.run,
        name="uvicorn-server",
        daemon=True,
    )
    server_thread.start()
    logger.info("Backend started at http://%s:%d", host, port)
    return server


def wait_for_backend(url: str, timeout: float = 30.0) -> bool:
    """等待后端就绪 (轮询 /healthz)."""
    import urllib.request
    import urllib.error

    health_url = f"{url}/healthz"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(health_url, timeout=2)
            return True
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.5)
    return False


def start_scheduler_via_api(
    url: str,
    interval_hours: float,
    dry_run: bool,
    fetch_meta_ads: bool,
) -> dict:
    """通过 API 启动调度器."""
    import json
    import urllib.request

    payload = json.dumps({
        "interval_hours": interval_hours,
        "dry_run": dry_run,
        "fetch_meta_ads": fetch_meta_ads,
        "run_immediately": True,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{url}/api/loop/scheduler/start",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def stop_scheduler_via_api(url: str) -> None:
    """通过 API 停止调度器."""
    import urllib.request
    try:
        req = urllib.request.Request(
            f"{url}/api/loop/scheduler/stop",
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def main() -> int:
    parser = argparse.ArgumentParser(
        description="7×24 无人值守守护进程: uvicorn 后端 + GrowthLoop 调度器",
    )
    parser.add_argument(
        "--port", type=int, default=8080,
        help="后端端口 (默认 8080)",
    )
    parser.add_argument(
        "--host", default="0.0.0.0",
        help="后端监听地址 (默认 0.0.0.0)",
    )
    parser.add_argument(
        "--interval", type=float, default=6.0,
        help="调度器间隔小时 (默认 6.0)",
    )
    parser.add_argument(
        "--live", action="store_true",
        help="真实执行模式 (默认 dry-run)",
    )
    parser.add_argument(
        "--fetch-meta-ads", action="store_true",
        help="拉取真实 Meta Ads 数据 (需配置凭据)",
    )
    parser.add_argument(
        "--no-scheduler", action="store_true",
        help="仅启动后端, 不自动启动调度器",
    )
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="日志级别 (默认 INFO)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    base_url = f"http://127.0.0.1:{args.port}"

    # ── 1. 启动后端 ──
    logger.info("=" * 60)
    logger.info("AI Game Studio OS — 7×24 无人值守模式启动")
    logger.info("=" * 60)
    logger.info("Backend: %s", base_url)
    logger.info("Scheduler: %s", "disabled" if args.no_scheduler else f"interval={args.interval}h dry_run={not args.live}")

    server = start_backend(port=args.port, host=args.host)

    # ── 2. 等待后端就绪 ──
    logger.info("Waiting for backend to be ready...")
    if not wait_for_backend(base_url, timeout=30):
        logger.error("Backend failed to start within 30s")
        return 1
    logger.info("Backend is ready")

    # ── 3. 启动调度器 ──
    if not args.no_scheduler:
        logger.info("Starting GrowthLoop scheduler...")
        try:
            result = start_scheduler_via_api(
                url=base_url,
                interval_hours=args.interval,
                dry_run=not args.live,
                fetch_meta_ads=args.fetch_meta_ads,
            )
            if result.get("started") or result.get("running"):
                logger.info("Scheduler started: %s", result)
            elif result.get("already_running"):
                logger.info("Scheduler already running: %s", result)
            else:
                logger.warning("Scheduler start response: %s", result)
        except Exception as exc:
            logger.error("Failed to start scheduler: %s", exc)
            logger.error("You can start it manually via API: POST /api/loop/scheduler/start")

    # ── 4. 主循环: 等待退出信号 ──
    logger.info("-" * 60)
    logger.info("Autonomous mode is running. Press Ctrl+C to stop.")
    logger.info("-" * 60)

    stop_event = threading.Event()

    def _signal_handler(signum, frame):
        logger.info("Received signal %d, shutting down...", signum)
        stop_event.set()

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    try:
        while not stop_event.is_set():
            stop_event.wait(timeout=1.0)
    except KeyboardInterrupt:
        pass

    # ── 5. 优雅停止 ──
    logger.info("=" * 60)
    logger.info("Shutting down...")
    logger.info("=" * 60)

    if not args.no_scheduler:
        logger.info("Stopping scheduler...")
        stop_scheduler_via_api(base_url)
        logger.info("Scheduler stopped")

    logger.info("Stopping backend...")
    server.should_exit = True
    logger.info("Backend stopped")

    logger.info("Goodbye.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
