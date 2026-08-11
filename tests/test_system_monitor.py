"""系统监控模块测试 — SystemMonitor.

验证:
  1. 系统健康概览 (get_system_health)
  2. 告警检测 (get_alerts) — 成功率/审批积压/文件大小/文件过期
  3. 子系统统计 (GrowthLoop/LiveOps/ChurnAlert/ApprovalQueue)
  4. 文件监控 (_get_file_stats)
  5. API 端点 (/api/monitor/*, /healthz, /readyz)
  6. Dashboard 概览 (get_dashboard_overview)
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.market_ops.workspace.system_monitor import (
    SystemMonitor,
    ALERT_PENDING_APPROVAL_THRESHOLD,
    ALERT_SUCCESS_RATE_THRESHOLD,
    ALERT_JSONL_SIZE_MB_THRESHOLD,
    ALERT_STALE_HOURS_THRESHOLD,
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def _write_jsonl(path: Path, records: list[dict]) -> None:
    """写入 JSONL 文件."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _make_cycle(
    cycle_number: int = 1,
    actions_planned: int = 5,
    actions_executed: int = 5,
    success: bool = True,
    completed_at: str = "",
) -> dict:
    """构造 GrowthLoop cycle 记录."""
    execution_results = [
        {
            "result_id": f"res_{i}",
            "action_id": f"exec_{i}",
            "status": "completed" if success else "failed",
            "success": success,
            "dry_run": True,
            "executed_at": completed_at or datetime.now(timezone.utc).isoformat(),
            "is_terminal": True,
        }
        for i in range(actions_executed)
    ]
    return {
        "loop_id": "loop_test",
        "cycle_number": cycle_number,
        "started_at": completed_at,
        "completed_at": completed_at,
        "duration_ms": 10,
        "signal_ids": [f"sig_{i}" for i in range(actions_planned)],
        "actions_planned": actions_planned,
        "actions_executed": actions_executed,
        "actions_skipped": 0,
        "actions_rolled_back": 0,
        "execution_results": execution_results,
    }


def _make_approval_record(
    status: str = "pending",
    executed: bool = False,
    created_at: str = "",
    game_id: str = "test_game",
) -> dict:
    """构造 CEO 审批记录."""
    return {
        "game_id": game_id,
        "opportunity_id": f"{game_id}:test",
        "action": "测试动作",
        "decision_type": "approve",
        "expected_value": 0.5,
        "confidence": 0.9,
        "risk": 0.45,
        "urgency": 0.95,
        "reason": "测试",
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "executed": executed,
        "queued": True,
        "status": status,
    }


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def workspace_env(tmp_path: Path, monkeypatch):
    """设置 Workspace 测试环境."""
    monkeypatch.setenv("WORKSPACE_DATA_PROVIDER", "mock")

    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    from src.market_ops.workspace import app as app_module
    monkeypatch.setattr(app_module, "_PROJECT_ROOT", tmp_path)

    # 重置单例缓存
    for fn_name in ["_get_shared_message_bus", "_get_churn_alert_bridge"]:
        fn = getattr(app_module, fn_name)
        for attr in ["_instance", "_registry"]:
            if hasattr(fn, attr):
                delattr(fn, attr)

    from src.market_ops.workspace import real_provider as rp
    monkeypatch.setattr(rp, "_real_provider", None)

    from src.market_ops.workspace import aggregator as agg_module
    agg_module._aggregator = None

    return {"data_dir": data_dir, "tmp_path": tmp_path}


@pytest.fixture
def client(workspace_env):
    """FastAPI TestClient."""
    from src.market_ops.workspace.app import app
    return TestClient(app)


# ═══════════════════════════════════════════════════════════════
# 1. 系统健康概览
# ═══════════════════════════════════════════════════════════════


class TestSystemHealth:
    """get_system_health 测试."""

    def test_empty_data_dir_returns_healthy(self, tmp_path):
        """无数据时返回 healthy (无告警)."""
        monitor = SystemMonitor(data_dir=str(tmp_path))
        health = monitor.get_system_health()
        assert health["status"] == "healthy"
        assert health["alerts_count"] == 0
        assert health["critical_alerts"] == 0
        assert health["warning_alerts"] == 0

    def test_health_contains_subsystems(self, tmp_path):
        """健康概览包含子系统统计."""
        monitor = SystemMonitor(data_dir=str(tmp_path))
        health = monitor.get_system_health()
        assert "subsystems" in health
        assert "growth_loop" in health["subsystems"]
        assert "liveops" in health["subsystems"]
        assert "churn_alert" in health["subsystems"]
        assert "approval_queue" in health["subsystems"]

    def test_health_contains_data_files(self, tmp_path):
        """健康概览包含数据文件监控."""
        monitor = SystemMonitor(data_dir=str(tmp_path))
        health = monitor.get_system_health()
        assert "data_files" in health
        assert "growth_loop_history" in health["data_files"]
        assert "liveops_executions" in health["data_files"]

    def test_degraded_when_warning_alerts(self, tmp_path):
        """有 warning 告警时状态为 degraded.

        构造 success_rate 在 [0.5, 0.8) 之间 → 触发 warning (非 critical).
        5 个 execution_results: 3 成功 + 2 失败 → 0.6.
        """
        data_dir = tmp_path / "data"
        gl_path = data_dir / "growth_loop" / "cycle_history.jsonl"
        # 直接构造混合成功率的 cycle (success_rate=0.6 → warning)
        cycle = _make_cycle(success=True, actions_executed=5)
        # 把后 2 个 result 改为失败 → 3/5 = 0.6
        for er in cycle["execution_results"][3:]:
            er["success"] = False
            er["status"] = "failed"
        _write_jsonl(gl_path, [cycle])

        monitor = SystemMonitor(data_dir=str(data_dir))
        health = monitor.get_system_health()
        assert health["status"] == "degraded"
        assert health["warning_alerts"] > 0
        assert health["critical_alerts"] == 0

    def test_critical_when_low_success_rate(self, tmp_path):
        """成功率低于 50% 时状态为 critical."""
        data_dir = tmp_path / "data"
        gl_path = data_dir / "growth_loop" / "cycle_history.jsonl"
        # 构造成功率 0% 的 cycle
        _write_jsonl(gl_path, [_make_cycle(success=False)])

        monitor = SystemMonitor(data_dir=str(data_dir))
        alerts = monitor.get_alerts()
        # success_rate=0 < 0.5 → critical
        gl_alert = next(a for a in alerts if a["alert_id"] == "gl_low_success_rate")
        assert gl_alert["severity"] == "critical"


# ═══════════════════════════════════════════════════════════════
# 2. 告警检测
# ═══════════════════════════════════════════════════════════════


class TestAlerts:
    """get_alerts 测试."""

    def test_no_alerts_when_healthy(self, tmp_path):
        """无数据时无告警."""
        monitor = SystemMonitor(data_dir=str(tmp_path))
        assert monitor.get_alerts() == []

    def test_growth_loop_low_success_rate_alert(self, tmp_path):
        """GrowthLoop 成功率低于阈值触发告警."""
        data_dir = tmp_path / "data"
        gl_path = data_dir / "growth_loop" / "cycle_history.jsonl"
        # 一半成功一半失败
        cycles = [
            _make_cycle(cycle_number=1, success=True),
            _make_cycle(cycle_number=2, success=False),
        ]
        _write_jsonl(gl_path, cycles)

        monitor = SystemMonitor(data_dir=str(data_dir))
        alerts = monitor.get_alerts()
        gl_alerts = [a for a in alerts if a["category"] == "growth_loop"]
        assert len(gl_alerts) == 1
        assert gl_alerts[0]["alert_id"] == "gl_low_success_rate"
        assert gl_alerts[0]["current_value"] < ALERT_SUCCESS_RATE_THRESHOLD

    def test_approval_backlog_alert(self, tmp_path):
        """审批积压超过阈值触发告警."""
        data_dir = tmp_path / "data"
        aq_path = data_dir / "ceo" / "approval_queue.jsonl"
        # 构造超过阈值的 pending 记录
        records = [
            _make_approval_record(status="pending", executed=False, game_id=f"g{i}")
            for i in range(ALERT_PENDING_APPROVAL_THRESHOLD + 5)
        ]
        _write_jsonl(aq_path, records)

        monitor = SystemMonitor(data_dir=str(data_dir))
        alerts = monitor.get_alerts()
        approval_alerts = [a for a in alerts if a["category"] == "approval"]
        assert len(approval_alerts) == 1
        assert approval_alerts[0]["alert_id"] == "approval_backlog"
        assert approval_alerts[0]["current_value"] >= ALERT_PENDING_APPROVAL_THRESHOLD

    def test_file_stale_alert(self, tmp_path):
        """文件过期触发 info 告警."""
        data_dir = tmp_path / "data"
        gl_path = data_dir / "growth_loop" / "cycle_history.jsonl"
        # 构造一个过期文件 (mtime 无法直接设置, 但 hours_since_update 由 mtime 计算)
        # 写入文件后修改 mtime 为 25 小时前
        old_time = (datetime.now(timezone.utc) - timedelta(hours=25)).timestamp()
        _write_jsonl(gl_path, [_make_cycle()])
        import os
        os.utime(gl_path, (old_time, old_time))

        monitor = SystemMonitor(data_dir=str(data_dir))
        alerts = monitor.get_alerts()
        stale_alerts = [a for a in alerts if a["alert_id"].startswith("file_stale_")]
        assert len(stale_alerts) >= 1
        assert stale_alerts[0]["severity"] == "info"
        assert stale_alerts[0]["threshold"] == ALERT_STALE_HOURS_THRESHOLD

    def test_alert_contains_suggestion(self, tmp_path):
        """每条告警包含修复建议."""
        data_dir = tmp_path / "data"
        gl_path = data_dir / "growth_loop" / "cycle_history.jsonl"
        _write_jsonl(gl_path, [_make_cycle(success=False)])

        monitor = SystemMonitor(data_dir=str(data_dir))
        alerts = monitor.get_alerts()
        for alert in alerts:
            assert "suggestion" in alert
            assert len(alert["suggestion"]) > 0


# ═══════════════════════════════════════════════════════════════
# 3. 子系统统计
# ═══════════════════════════════════════════════════════════════


class TestSubsystemStats:
    """子系统统计测试."""

    def test_growth_loop_stats(self, tmp_path):
        """GrowthLoop 统计正确."""
        data_dir = tmp_path / "data"
        gl_path = data_dir / "growth_loop" / "cycle_history.jsonl"
        cycles = [
            _make_cycle(cycle_number=1, actions_planned=10, actions_executed=10, success=True),
            _make_cycle(cycle_number=2, actions_planned=5, actions_executed=5, success=True),
        ]
        _write_jsonl(gl_path, cycles)

        monitor = SystemMonitor(data_dir=str(data_dir))
        stats = monitor._get_growth_loop_stats()
        assert stats["total_cycles"] == 2
        assert stats["total_actions_planned"] == 15
        assert stats["total_actions_executed"] == 15
        assert stats["success_rate"] == 1.0
        assert stats["latest_cycle"]["cycle_number"] == 2

    def test_growth_loop_empty(self, tmp_path):
        """无 GrowthLoop 数据时返回空统计."""
        monitor = SystemMonitor(data_dir=str(tmp_path))
        stats = monitor._get_growth_loop_stats()
        assert stats["total_cycles"] == 0
        assert stats["success_rate"] == 0.0

    def test_liveops_stats_dedup(self, tmp_path):
        """LiveOps 统计按 execution_id 去重."""
        data_dir = tmp_path / "data"
        lo_path = data_dir / "liveops" / "campaign_executions.jsonl"
        # 同一 execution_id 两条记录 (blocked → completed)
        records = [
            {"execution_id": "exec_1", "status": "blocked", "game_id": "g1"},
            {"execution_id": "exec_1", "status": "completed", "game_id": "g1"},
            {"execution_id": "exec_2", "status": "completed", "game_id": "g2"},
        ]
        _write_jsonl(lo_path, records)

        monitor = SystemMonitor(data_dir=str(data_dir))
        stats = monitor._get_liveops_stats()
        # 去重后 2 条
        assert stats["total_executions"] == 2
        assert stats["completed"] == 2
        assert stats["blocked"] == 0  # exec_1 最新状态是 completed
        assert stats["success_rate"] == 1.0

    def test_churn_alert_stats(self, tmp_path):
        """ChurnAlert 响应统计."""
        data_dir = tmp_path / "data"
        cr_path = data_dir / "growth" / "churn_responses.jsonl"
        records = [
            {"response_id": "gr_1", "status": "executed"},
            {"response_id": "gr_2", "status": "rolled_back"},
            {"response_id": "gr_2", "status": "executed"},  # 覆盖
        ]
        _write_jsonl(cr_path, records)

        monitor = SystemMonitor(data_dir=str(data_dir))
        stats = monitor._get_churn_alert_stats()
        # 去重后 2 条
        assert stats["total_responses"] == 2
        assert stats["executed"] == 2  # gr_1 executed + gr_2 最新 executed
        assert stats["rolled_back"] == 0

    def test_approval_queue_stats(self, tmp_path):
        """审批队列统计."""
        data_dir = tmp_path / "data"
        aq_path = data_dir / "ceo" / "approval_queue.jsonl"
        old_time = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
        records = [
            _make_approval_record(status="pending", executed=False, created_at=old_time, game_id="g1"),
            _make_approval_record(status="pending", executed=False, created_at=old_time, game_id="g2"),
            _make_approval_record(status="approved", executed=True, game_id="g3"),
        ]
        _write_jsonl(aq_path, records)

        monitor = SystemMonitor(data_dir=str(data_dir))
        stats = monitor._get_approval_queue_stats()
        assert stats["ceo_pending"] == 2
        assert stats["liveops_pending"] == 0
        assert stats["total_pending"] == 2
        assert stats["oldest_ceo_pending_hours"] >= 4  # 约 5 小时


# ═══════════════════════════════════════════════════════════════
# 4. 文件监控
# ═══════════════════════════════════════════════════════════════


class TestFileStats:
    """_get_file_stats 测试."""

    def test_file_stats_exists(self, tmp_path):
        """文件存在时返回正确统计."""
        data_dir = tmp_path / "data"
        gl_path = data_dir / "growth_loop" / "cycle_history.jsonl"
        _write_jsonl(gl_path, [_make_cycle(), _make_cycle()])

        monitor = SystemMonitor(data_dir=str(data_dir))
        stats = monitor._get_file_stats()
        gl_stats = stats["growth_loop_history"]
        assert gl_stats["exists"] is True
        assert gl_stats["record_count"] == 2
        # size_mb 经 round(2) 后小文件可能为 0.0, 仅校验非负
        assert gl_stats["size_mb"] >= 0
        assert gl_stats["last_modified"] != ""

    def test_file_stats_not_exists(self, tmp_path):
        """文件不存在时 exists=False."""
        monitor = SystemMonitor(data_dir=str(tmp_path))
        stats = monitor._get_file_stats()
        lo_stats = stats["liveops_executions"]
        assert lo_stats["exists"] is False
        assert lo_stats["record_count"] == 0
        assert lo_stats["size_mb"] == 0.0

    def test_all_monitored_files_tracked(self, tmp_path):
        """所有监控文件都被追踪."""
        monitor = SystemMonitor(data_dir=str(tmp_path))
        stats = monitor._get_file_stats()
        expected_files = {
            "growth_loop_history", "liveops_executions", "churn_responses",
            "churn_audit", "ceo_approval_queue", "ceo_execution_memory",
            "ceo_execution_experience", "operator_runs",
        }
        assert set(stats.keys()) == expected_files


# ═══════════════════════════════════════════════════════════════
# 5. API 端点
# ═══════════════════════════════════════════════════════════════


class TestMonitorAPI:
    """监控 API 端点测试."""

    def test_healthz_returns_200(self, client):
        """/healthz 返回 200 且含监控字段."""
        resp = client.get("/healthz")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("healthy", "degraded", "critical")
        assert data["service"] == "ai-game-studio-workspace"
        assert "alerts_count" in data
        assert "critical_alerts" in data
        assert "warning_alerts" in data

    def test_readyz_returns_200_when_healthy(self, client):
        """/readyz 在 healthy 时返回 200."""
        resp = client.get("/readyz")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ready"

    def test_monitor_overview_returns_200(self, client):
        """/api/monitor/overview 返回 200."""
        resp = client.get("/api/monitor/overview")
        assert resp.status_code == 200
        data = resp.json()
        assert "health" in data
        assert "alerts" in data
        assert "growth_loop" in data
        assert "liveops" in data
        assert "churn_alert" in data
        assert "approval_queue" in data
        assert "data_files" in data

    def test_monitor_health_endpoint(self, client):
        """/api/monitor/health 返回健康详情."""
        resp = client.get("/api/monitor/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "subsystems" in data
        assert "alerts_count" in data

    def test_monitor_alerts_endpoint(self, client):
        """/api/monitor/alerts 返回告警列表."""
        resp = client.get("/api/monitor/alerts")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_monitor_files_endpoint(self, client):
        """/api/monitor/files 返回文件监控."""
        resp = client.get("/api/monitor/files")
        assert resp.status_code == 200
        data = resp.json()
        assert "growth_loop_history" in data
        assert "liveops_executions" in data

    def test_monitor_growth_loop_endpoint(self, client):
        """/api/monitor/growth-loop 返回 GrowthLoop 统计."""
        resp = client.get("/api/monitor/growth-loop")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_cycles" in data
        assert "success_rate" in data

    def test_monitor_liveops_endpoint(self, client):
        """/api/monitor/liveops 返回 LiveOps 统计."""
        resp = client.get("/api/monitor/liveops")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_executions" in data
        assert "success_rate" in data

    def test_monitor_approval_queue_endpoint(self, client):
        """/api/monitor/approval-queue 返回审批队列统计."""
        resp = client.get("/api/monitor/approval-queue")
        assert resp.status_code == 200
        data = resp.json()
        assert "ceo_pending" in data
        assert "liveops_pending" in data
        assert "total_pending" in data


# ═══════════════════════════════════════════════════════════════
# 6. Dashboard 概览
# ═══════════════════════════════════════════════════════════════


class TestDashboardOverview:
    """get_dashboard_overview 测试."""

    def test_overview_contains_all_sections(self, tmp_path):
        """概览包含所有部分."""
        monitor = SystemMonitor(data_dir=str(tmp_path))
        overview = monitor.get_dashboard_overview()
        assert "health" in overview
        assert "alerts" in overview
        assert "growth_loop" in overview
        assert "liveops" in overview
        assert "churn_alert" in overview
        assert "approval_queue" in overview
        assert "data_files" in overview
        assert "timestamp" in overview

    def test_overview_health_matches_alerts(self, tmp_path):
        """概览的 health 与 alerts 一致."""
        data_dir = tmp_path / "data"
        gl_path = data_dir / "growth_loop" / "cycle_history.jsonl"
        _write_jsonl(gl_path, [_make_cycle(success=False)])

        monitor = SystemMonitor(data_dir=str(data_dir))
        overview = monitor.get_dashboard_overview()
        # health.alerts_count 应等于 len(alerts)
        assert overview["health"]["alerts_count"] == len(overview["alerts"])
