"""GrowthLoopScheduler 定时调度器单元测试.

覆盖:
  1. 生命周期: start → status → stop
  2. 幂等保护: 重复 start / 空闲 stop
  3. 文件锁: acquire / release / 并发互斥 / 僵尸锁清理
  4. trigger_now: 空闲触发 / 运行中跳过 / 未运行跳过
  5. 状态构建: _build_status_dict 字段完整性
  6. 状态持久化: save_state / load_state 往返
  7. interval 下限保护 (最小 0.01h)
  8. 错误隔离: cycle 失败不影响后续调度
  9. _execute_cycle: mock Orchestrator 成功/失败
  10. API 端点: /api/loop/scheduler/{start,stop,status,trigger}

设计原则:
  - 全部使用 tmp_path, 绝不污染 data/
  - 用 mock 替换 GrowthLoopOrchestrator, 避免真实 cycle 执行
  - 不启动真实后台线程 (run_immediately=False + 极短 timeout 或直接测内部方法)
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# 确保路径
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_PROJECT_ROOT / "src"))
sys.path.insert(0, str(_PROJECT_ROOT / "scripts"))

from src.market_ops.workspace.growth_loop_scheduler import (
    GrowthLoopScheduler,
    timedelta_from_hours,
    _now_iso,
    _now_utc,
)


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────


@pytest.fixture
def tmp_scheduler(tmp_path: Path) -> GrowthLoopScheduler:
    """使用临时目录的调度器实例."""
    data_dir = tmp_path / "data" / "growth_loop"
    return GrowthLoopScheduler(
        data_dir=str(data_dir),
        project_root=str(tmp_path),
    )


@pytest.fixture
def mock_cycle_result():
    """构造一个模拟的 CycleResult."""
    mock = MagicMock()
    mock.cycle_number = 42
    mock.actions = [MagicMock(), MagicMock()]
    mock.execution_results = [
        {"success": True, "dry_run": True},
        {"success": True, "dry_run": True},
    ]
    mock.evaluated_count = 5
    mock.pending_created = 2
    return mock


# ──────────────────────────────────────────────
# 1. 生命周期测试
# ──────────────────────────────────────────────


class TestSchedulerLifecycle:
    """调度器启动/停止/状态."""

    def test_initial_status_not_running(self, tmp_scheduler: GrowthLoopScheduler):
        """新建调度器: running=False."""
        status = tmp_scheduler.get_status()
        assert status["running"] is False
        assert status["cycle_in_progress"] is False
        assert status["total_scheduled_cycles"] == 0
        assert status["last_error"] == ""

    def test_start_with_immediate_off(self, tmp_scheduler: GrowthLoopScheduler):
        """start(run_immediately=False): running=True, next_cycle_at 在未来."""
        result = tmp_scheduler.start(
            interval_hours=6.0,
            dry_run=True,
            run_immediately=False,
        )
        assert result["started"] is True
        assert result["running"] is True
        assert result["interval_hours"] == 6.0
        assert result["dry_run"] is True
        assert result["next_cycle_at"] != ""

        # 清理: 停止线程
        tmp_scheduler.stop(timeout=1.0)

    def test_start_with_immediate_on(self, tmp_scheduler: GrowthLoopScheduler):
        """start(run_immediately=True): next_cycle_at ≈ now."""
        result = tmp_scheduler.start(
            interval_hours=1.0,
            dry_run=True,
            run_immediately=True,
        )
        assert result["started"] is True
        assert result["next_cycle_at"] != ""

        # next_cycle_at 应该是当前时间附近
        next_dt = datetime.fromisoformat(result["next_cycle_at"])
        now = _now_utc()
        delta = abs((next_dt - now).total_seconds())
        assert delta < 5  # 5 秒内

        tmp_scheduler.stop(timeout=1.0)

    def test_start_idempotent(self, tmp_scheduler: GrowthLoopScheduler):
        """重复 start: 第二次返回 already_running."""
        tmp_scheduler.start(interval_hours=6.0, run_immediately=False)
        result2 = tmp_scheduler.start(interval_hours=6.0, run_immediately=False)
        assert result2.get("already_running") is True
        assert result2["running"] is True

        tmp_scheduler.stop(timeout=1.0)

    def test_stop_when_not_running(self, tmp_scheduler: GrowthLoopScheduler):
        """未运行时 stop: 返回 not_running."""
        result = tmp_scheduler.stop()
        assert result.get("not_running") is True

    def test_stop_after_start(self, tmp_scheduler: GrowthLoopScheduler):
        """start → stop: 最终 running=False."""
        tmp_scheduler.start(interval_hours=6.0, run_immediately=False)
        result = tmp_scheduler.stop(timeout=2.0)
        assert result.get("stopped") is True
        assert result["running"] is False
        assert tmp_scheduler.get_status()["running"] is False


# ──────────────────────────────────────────────
# 2. interval 下限保护
# ──────────────────────────────────────────────


class TestIntervalProtection:
    """interval_hours 下限保护."""

    def test_interval_minimum_floor(self, tmp_scheduler: GrowthLoopScheduler):
        """interval_hours < 0.01 被钳制到 0.01."""
        tmp_scheduler.start(interval_hours=0.001, run_immediately=False)
        status = tmp_scheduler.get_status()
        assert status["interval_hours"] == 0.01
        tmp_scheduler.stop(timeout=1.0)

    def test_interval_normal_value(self, tmp_scheduler: GrowthLoopScheduler):
        """正常 interval 原样保留."""
        tmp_scheduler.start(interval_hours=12.0, run_immediately=False)
        assert tmp_scheduler.get_status()["interval_hours"] == 12.0
        tmp_scheduler.stop(timeout=1.0)


# ──────────────────────────────────────────────
# 3. 文件锁测试
# ──────────────────────────────────────────────


class TestFileLock:
    """文件锁 acquire / release / 并发互斥 / 僵尸锁."""

    def test_acquire_and_release(self, tmp_scheduler: GrowthLoopScheduler):
        """acquire → lock 文件存在; release → 文件消失."""
        assert not tmp_scheduler.lock_path.exists()

        acquired = tmp_scheduler._acquire_lock()
        assert acquired is True
        assert tmp_scheduler.lock_path.exists()

        # lock 内容包含 pid
        content = json.loads(tmp_scheduler.lock_path.read_text(encoding="utf-8"))
        assert "pid" in content
        assert "acquired_at" in content

        tmp_scheduler._release_lock()
        assert not tmp_scheduler.lock_path.exists()

    def test_concurrent_lock_fails(self, tmp_scheduler: GrowthLoopScheduler):
        """已持锁时, 第二次 acquire 返回 False."""
        tmp_scheduler._acquire_lock()
        acquired2 = tmp_scheduler._acquire_lock()
        assert acquired2 is False

        tmp_scheduler._release_lock()

    def test_stale_lock_cleanup(self, tmp_scheduler: GrowthLoopScheduler):
        """超过 1 小时的僵尸锁被自动清理."""
        # 手动创建一个过期的 lock 文件
        tmp_scheduler.lock_path.parent.mkdir(parents=True, exist_ok=True)
        old_time = time.time() - 3700  # 1 小时前
        tmp_scheduler.lock_path.write_text(
            json.dumps({"pid": 99999, "acquired_at": _now_iso()}),
            encoding="utf-8",
        )
        # 修改 mtime 为 3700 秒前
        os.utime(str(tmp_scheduler.lock_path), (old_time, old_time))

        # acquire 应清理僵尸锁并成功获取
        acquired = tmp_scheduler._acquire_lock()
        assert acquired is True

        tmp_scheduler._release_lock()

    def test_release_when_no_lock(self, tmp_scheduler: GrowthLoopScheduler):
        """无锁时 release 不报错 (幂等)."""
        # 不应抛异常
        tmp_scheduler._release_lock()
        assert not tmp_scheduler.lock_path.exists()


# ──────────────────────────────────────────────
# 4. trigger_now 测试
# ──────────────────────────────────────────────


class TestTriggerNow:
    """trigger_now 立即触发."""

    def test_trigger_when_not_running(self, tmp_scheduler: GrowthLoopScheduler):
        """调度器未运行时 trigger: skipped."""
        result = tmp_scheduler.trigger_now()
        assert result["status"] == "skipped"
        assert result["reason"] == "scheduler_not_running"

    def test_trigger_when_cycle_in_progress(self, tmp_scheduler: GrowthLoopScheduler):
        """cycle 执行中 trigger: skipped."""
        tmp_scheduler.start(interval_hours=6.0, run_immediately=False)
        # 模拟 cycle 正在执行
        tmp_scheduler._cycle_in_progress = True

        result = tmp_scheduler.trigger_now()
        assert result["status"] == "skipped"
        assert result["reason"] == "cycle_in_progress"

        tmp_scheduler._cycle_in_progress = False
        tmp_scheduler.stop(timeout=1.0)


# ──────────────────────────────────────────────
# 5. 状态构建测试
# ──────────────────────────────────────────────


class TestStatusDict:
    """_build_status_dict 字段完整性."""

    def test_status_contains_all_fields(self, tmp_scheduler: GrowthLoopScheduler):
        """状态 dict 包含所有必需字段."""
        status = tmp_scheduler.get_status()
        expected_keys = {
            "running", "cycle_in_progress", "interval_hours",
            "dry_run", "fetch_meta_ads", "started_at",
            "last_cycle_at", "next_cycle_at",
            "total_scheduled_cycles", "total_successful_cycles",
            "total_failed_cycles", "last_error", "last_cycle_result",
        }
        assert expected_keys.issubset(set(status.keys()))

    def test_status_extra_fields_merged(self, tmp_scheduler: GrowthLoopScheduler):
        """_build_status_dict 合并额外字段."""
        status = tmp_scheduler._build_status_dict(custom_field="test_value")
        assert status["custom_field"] == "test_value"


# ──────────────────────────────────────────────
# 6. 状态持久化测试
# ──────────────────────────────────────────────


class TestStatePersistence:
    """save_state / load_state 往返."""

    def test_save_and_load_state(self, tmp_scheduler: GrowthLoopScheduler):
        """save → load: 数据一致."""
        tmp_scheduler._interval_hours = 4.5
        tmp_scheduler._dry_run = False
        tmp_scheduler._total_successful_cycles = 7
        tmp_scheduler._last_error = "test_error"

        tmp_scheduler.save_state()
        assert tmp_scheduler.state_path.exists()

        loaded = tmp_scheduler.load_state()
        assert loaded is not None
        assert loaded["interval_hours"] == 4.5
        assert loaded["dry_run"] is False
        assert loaded["total_successful_cycles"] == 7
        assert loaded["last_error"] == "test_error"
        assert "saved_at" in loaded

    def test_load_state_when_no_file(self, tmp_scheduler: GrowthLoopScheduler):
        """无状态文件时 load: 返回 None."""
        assert tmp_scheduler.load_state() is None

    def test_load_state_corrupt_file(self, tmp_scheduler: GrowthLoopScheduler):
        """损坏的状态文件: load 返回 None."""
        tmp_scheduler.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_scheduler.state_path.write_text("{invalid json", encoding="utf-8")
        assert tmp_scheduler.load_state() is None


# ──────────────────────────────────────────────
# 7. _execute_cycle mock 测试
# ──────────────────────────────────────────────


class TestExecuteCycle:
    """_execute_cycle 核心执行逻辑 (mock Orchestrator)."""

    def test_execute_cycle_success(
        self, tmp_scheduler: GrowthLoopScheduler, mock_cycle_result
    ):
        """mock Orchestrator.run_cycle 返回成功: status=completed."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.run_cycle.return_value = mock_cycle_result
        mock_orchestrator.state = MagicMock()

        with patch(
            "scripts.growth_loop_orchestrator.GrowthLoopOrchestrator",
            return_value=mock_orchestrator,
        ):
            tmp_scheduler._dry_run = True
            result = tmp_scheduler._execute_cycle()

        assert result["status"] == "completed"
        assert result["cycle_number"] == 42
        assert result["dry_run"] is True
        assert result["actions_planned"] == 2
        assert result["actions_executed"] == 2
        assert result["actions_succeeded"] == 2
        assert result["success_rate"] == 1.0
        assert "duration_seconds" in result

    def test_execute_cycle_import_failure(self, tmp_scheduler: GrowthLoopScheduler):
        """Orchestrator 导入失败: status=failed."""
        # 让 import 失败
        with patch.dict("sys.modules", {"scripts.growth_loop_orchestrator": None}):
            tmp_scheduler._dry_run = True
            result = tmp_scheduler._execute_cycle()

        assert result["status"] == "failed"
        assert "import_failed" in result.get("error", "")

    def test_execute_cycle_orchestrator_exception(
        self, tmp_scheduler: GrowthLoopScheduler
    ):
        """Orchestrator.run_cycle 抛异常: status=failed."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.run_cycle.side_effect = RuntimeError("test crash")
        mock_orchestrator.state = MagicMock()

        with patch(
            "scripts.growth_loop_orchestrator.GrowthLoopOrchestrator",
            return_value=mock_orchestrator,
        ):
            tmp_scheduler._dry_run = True
            result = tmp_scheduler._execute_cycle()

        assert result["status"] == "failed"
        assert "test crash" in result.get("error", "")

    def test_execute_cycle_with_fetch_meta_ads_no_credentials(
        self, tmp_scheduler: GrowthLoopScheduler, mock_cycle_result
    ):
        """fetch_meta_ads=True 但未配置凭证: 跳过拉取, cycle 正常执行."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.run_cycle.return_value = mock_cycle_result
        mock_orchestrator.state = MagicMock()

        mock_fetcher = MagicMock()
        mock_fetcher.return_value.is_configured.return_value = False

        with patch(
            "scripts.growth_loop_orchestrator.GrowthLoopOrchestrator",
            return_value=mock_orchestrator,
        ), patch(
            "src.market_ops.workspace.meta_ads_fetcher.MetaAdsDataFetcher",
            mock_fetcher,
        ):
            tmp_scheduler._dry_run = True
            tmp_scheduler._fetch_meta_ads = True
            result = tmp_scheduler._execute_cycle()

        assert result["status"] == "completed"
        assert result.get("meta_ads_data", {}).get("fetch_error") == "credentials_not_configured"


# ──────────────────────────────────────────────
# 8. _execute_cycle_with_lock 测试
# ──────────────────────────────────────────────


class TestExecuteCycleWithLock:
    """_execute_cycle_with_lock 文件锁集成."""

    def test_lock_acquired_and_released(
        self, tmp_scheduler: GrowthLoopScheduler, mock_cycle_result
    ):
        """执行成功后锁被释放."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.run_cycle.return_value = mock_cycle_result
        mock_orchestrator.state = MagicMock()

        with patch(
            "scripts.growth_loop_orchestrator.GrowthLoopOrchestrator",
            return_value=mock_orchestrator,
        ):
            tmp_scheduler._dry_run = True
            result = tmp_scheduler._execute_cycle_with_lock()

        assert result["status"] == "completed"
        # 锁应该已被释放
        assert not tmp_scheduler.lock_path.exists()

    def test_lock_busy_skips_cycle(self, tmp_scheduler: GrowthLoopScheduler):
        """锁被占用时: status=skipped, reason=lock_busy."""
        # 预先占用锁
        tmp_scheduler._acquire_lock()

        result = tmp_scheduler._execute_cycle_with_lock()
        assert result["status"] == "skipped"
        assert result["reason"] == "lock_busy"

        tmp_scheduler._release_lock()


# ──────────────────────────────────────────────
# 9. _compute_next_cycle_time 测试
# ──────────────────────────────────────────────


class TestComputeNextCycleTime:
    """下一次 cycle 时间计算."""

    def test_next_cycle_time_in_future(self, tmp_scheduler: GrowthLoopScheduler):
        """next_cycle_at 在 now + interval 之后."""
        tmp_scheduler._interval_hours = 6.0
        before = _now_utc()
        next_iso = tmp_scheduler._compute_next_cycle_time()
        after = _now_utc()

        next_dt = datetime.fromisoformat(next_iso)
        # 应该在 6 小时后
        expected_min = before + timedelta(hours=5.99)
        expected_max = after + timedelta(hours=6.01)
        assert expected_min < next_dt < expected_max

    def test_next_cycle_time_small_interval(self, tmp_scheduler: GrowthLoopScheduler):
        """小 interval (0.01h ≈ 36秒) 正常计算."""
        tmp_scheduler._interval_hours = 0.01
        next_iso = tmp_scheduler._compute_next_cycle_time()
        next_dt = datetime.fromisoformat(next_iso)
        now = _now_utc()
        delta = (next_dt - now).total_seconds()
        assert 30 < delta < 40  # 约 36 秒


# ──────────────────────────────────────────────
# 10. 辅助函数测试
# ──────────────────────────────────────────────


class TestHelperFunctions:
    """模块级辅助函数."""

    def test_now_utc_returns_timezone_aware(self):
        """_now_utc 返回带时区的 datetime."""
        dt = _now_utc()
        assert dt.tzinfo is not None

    def test_now_iso_returns_valid_iso(self):
        """_now_iso 返回可解析的 ISO 字符串."""
        iso = _now_iso()
        dt = datetime.fromisoformat(iso)
        assert dt is not None

    def test_timedelta_from_hours(self):
        """timedelta_from_hours 正确转换."""
        td = timedelta_from_hours(6.0)
        assert td == timedelta(hours=6.0)


# ──────────────────────────────────────────────
# 11. API 端点测试
# ──────────────────────────────────────────────


class TestSchedulerAPI:
    """调度器 HTTP API 端点测试."""

    @pytest.fixture
    def api_client(self, tmp_path: Path, monkeypatch):
        """FastAPI TestClient + 临时数据目录."""
        # 创建临时数据目录结构
        data_dir = tmp_path / "data"
        growth_loop_dir = data_dir / "growth_loop"
        ceo_dir = data_dir / "ceo"
        ceo_audit_dir = ceo_dir / "audit"
        game_reality_dir = ceo_dir / "game_reality"

        for d in [growth_loop_dir, ceo_audit_dir, game_reality_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # 创建空 cycle_history
        (growth_loop_dir / "cycle_history.jsonl").write_text("", encoding="utf-8")

        # Monkeypatch app.py 路径
        from src.market_ops.workspace import app as app_module

        monkeypatch.setattr(app_module, "_PROJECT_ROOT", tmp_path)
        monkeypatch.setattr(
            app_module, "_GROWTH_LOOP_HISTORY",
            growth_loop_dir / "cycle_history.jsonl",
        )

        # 重置 scheduler 单例
        if hasattr(app_module._get_scheduler, "_instance"):
            del app_module._get_scheduler._instance

        # 重置 aggregator 单例
        from src.market_ops.workspace import aggregator as agg_module
        agg_module._aggregator = None

        from src.market_ops.workspace.app import app
        return TestClient(app)

    def test_get_scheduler_status_initial(self, api_client: TestClient):
        """GET /api/loop/scheduler/status: 初始 running=False."""
        resp = api_client.get("/api/loop/scheduler/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["running"] is False
        assert data["total_scheduled_cycles"] == 0

    def test_start_scheduler_api(self, api_client: TestClient):
        """POST /api/loop/scheduler/start: 启动成功."""
        resp = api_client.post(
            "/api/loop/scheduler/start",
            json={
                "interval_hours": 6.0,
                "dry_run": True,
                "run_immediately": False,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["started"] is True
        assert data["running"] is True

        # 清理: 停止调度器
        api_client.post("/api/loop/scheduler/stop")

    def test_stop_scheduler_api(self, api_client: TestClient):
        """POST /api/loop/scheduler/stop: 停止成功."""
        # 先启动
        api_client.post(
            "/api/loop/scheduler/start",
            json={"interval_hours": 6.0, "run_immediately": False},
        )
        # 再停止
        resp = api_client.post("/api/loop/scheduler/stop")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("stopped") is True
        assert data["running"] is False

    def test_stop_when_not_running_api(self, api_client: TestClient):
        """POST /api/loop/scheduler/stop (未运行): not_running."""
        resp = api_client.post("/api/loop/scheduler/stop")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("not_running") is True

    def test_trigger_when_not_running_api(self, api_client: TestClient):
        """POST /api/loop/scheduler/trigger (未运行): skipped."""
        resp = api_client.post("/api/loop/scheduler/trigger")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "skipped"
        assert data["reason"] == "scheduler_not_running"

    def test_start_with_invalid_interval_clamped(self, api_client: TestClient):
        """interval_hours=0.001 被钳制到 0.01."""
        resp = api_client.post(
            "/api/loop/scheduler/start",
            json={"interval_hours": 0.001, "run_immediately": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["interval_hours"] == 0.01

        api_client.post("/api/loop/scheduler/stop")

    def test_start_idempotent_api(self, api_client: TestClient):
        """重复 start: 第二次返回 already_running."""
        api_client.post(
            "/api/loop/scheduler/start",
            json={"interval_hours": 6.0, "run_immediately": False},
        )
        resp2 = api_client.post(
            "/api/loop/scheduler/start",
            json={"interval_hours": 6.0, "run_immediately": False},
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2.get("already_running") is True

        api_client.post("/api/loop/scheduler/stop")
