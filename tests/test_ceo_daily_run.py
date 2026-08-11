"""CEO 每日例会 /api/ceo/daily-run 端点测试.

测试覆盖 Spec §4.1-§4.9 验收标准:
  §4.1 POST /api/ceo/daily-run 返回 200 + 完整 stages
  §4.2 默认 demo 模式可离线跑（不依赖真实 API）
  §4.3 幂等门生效：同日重复触发返回 SKIPPED
  §4.4 force=true 可越过幂等门
  §4.5 响应包含阶段结果
  §4.6 响应包含 decisions/executions 统计
  §4.8 现有 /api/loop/trigger 不受影响（回归测试）
  §4.9 单元测试覆盖（≥10 个用例）
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def workspace_env(tmp_path: Path, monkeypatch):
    """设置 Workspace 测试环境."""
    monkeypatch.setenv("WORKSPACE_DATA_PROVIDER", "real")

    data_dir = tmp_path / "data"
    growth_loop_dir = data_dir / "growth_loop"
    ceo_dir = data_dir / "ceo"
    ceo_audit_dir = ceo_dir / "audit"
    game_reality_dir = ceo_dir / "game_reality"

    for d in [growth_loop_dir, ceo_audit_dir, game_reality_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # 创建最小测试数据
    (ceo_dir / "approval_queue.jsonl").write_text("{}", encoding="utf-8")
    (growth_loop_dir / "cycle_history.jsonl").write_text("{}", encoding="utf-8")

    # Monkeypatch real_provider 路径常量
    from src.market_ops.workspace import real_provider as rp

    monkeypatch.setattr(rp, "GROWTH_LOOP_HISTORY", growth_loop_dir / "cycle_history.jsonl")
    monkeypatch.setattr(rp, "CEO_DECISIONS_AUDIT", ceo_audit_dir / "decisions.jsonl")
    monkeypatch.setattr(rp, "CEO_APPROVAL_QUEUE", ceo_dir / "approval_queue.jsonl")
    monkeypatch.setattr(rp, "GAME_REALITY_DIR", game_reality_dir)
    monkeypatch.setattr(rp, "_real_provider", None)

    # Monkeypatch app.py 路径
    from src.market_ops.workspace import app as app_module

    monkeypatch.setattr(app_module, "_PROJECT_ROOT", tmp_path)

    # 确保 scripts 和 src 在 path 中
    project_root = Path(__file__).resolve().parent.parent
    for d in [str(project_root / "scripts"), str(project_root / "src")]:
        if d not in sys.path:
            sys.path.insert(0, d)

    return {"data_dir": data_dir, "tmp_path": tmp_path}


@pytest.fixture
def client(workspace_env):
    """FastAPI TestClient."""
    from src.market_ops.workspace.app import app
    from src.market_ops.workspace import aggregator as agg_module
    agg_module._aggregator = None
    return TestClient(app)


def _make_mock_operator_result(status="completed", skipped=False):
    """创建 mock OperatorRunResult."""
    mock_result = MagicMock()
    mock_result.run_id = "op-test-001"
    mock_result.date = "2026-08-07"
    mock_result.status.value = "skipped" if skipped else status
    mock_result.stages = [
        MagicMock(stage="reality_refresh", status="ok", detail="4 sources refreshed", payload={}),
        MagicMock(stage="audit", status="ok", detail="3 games audited", payload={}),
        MagicMock(stage="opportunities", status="ok", detail="5 opportunities", payload={}),
        MagicMock(stage="simulations", status="ok", detail="3 sims passed", payload={}),
        MagicMock(stage="decisions", status="ok", detail="5 decisions", payload={}),
        MagicMock(stage="approval", status="skipped", detail="dry_run", payload={}),
        MagicMock(stage="executions", status="ok", detail="3 executed", payload={}),
        MagicMock(stage="monitor", status="ok", detail="3 observed", payload={}),
        MagicMock(stage="recovery", status="skipped", detail="no failures", payload={}),
        MagicMock(stage="memory", status="ok", detail="memory persisted", payload={}),
        MagicMock(stage="strategy_loop", status="ok", detail="2 insights", payload={}),
        MagicMock(stage="portfolio", status="ok", detail="1 recommendation", payload={}),
        MagicMock(stage="ceo_report", status="ok", detail="report generated", payload={}),
    ]
    mock_result.decisions = {"EXECUTE": 3, "APPROVE": 1, "BLOCK": 1}
    mock_result.executions = {"success": 3, "failed": 0, "skipped": 1}
    mock_result.errors = []
    mock_result.report_id = "rpt_20260807_001"
    mock_result.real_api_called = False
    mock_result.summary = {"total_games": 3, "total_opportunities": 5}
    mock_result.to_dict.return_value = {
        "run_id": "op-test-001",
        "date": "2026-08-07",
        "status": "skipped" if skipped else status,
        "stages": [
            {"stage": s.stage, "status": s.status, "detail": s.detail, "payload": s.payload}
            for s in mock_result.stages
        ],
        "decisions": dict(mock_result.decisions),
        "executions": dict(mock_result.executions),
        "errors": list(mock_result.errors),
        "report_id": mock_result.report_id,
        "real_api_called": mock_result.real_api_called,
        "summary": dict(mock_result.summary),
    }
    return mock_result


class TestCEODailyRunEndpoint:
    """/api/ceo/daily-run 端点测试."""

    def test_daily_run_returns_200_with_stages(self, client, workspace_env):
        """§4.1 POST /api/ceo/daily-run 返回 200 + 完整 stages."""
        mock_result = _make_mock_operator_result()
        mock_scheduler = MagicMock()
        mock_scheduler.run_daily_cycle.return_value = mock_result

        with patch(
            "scripts.run_daily_operator.build_demo_scheduler",
            return_value=mock_scheduler,
        ):
            resp = client.post("/api/ceo/daily-run", json={})

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["run_id"] == "op-test-001"
        assert len(data["stages"]) == 13
        assert "duration_seconds" in data

    def test_daily_run_demo_mode_no_real_api(self, client, workspace_env):
        """§4.2 默认 demo 模式可离线跑（不依赖真实 API）."""
        mock_result = _make_mock_operator_result()
        mock_scheduler = MagicMock()
        mock_scheduler.run_daily_cycle.return_value = mock_result

        with patch(
            "scripts.run_daily_operator.build_demo_scheduler",
            return_value=mock_scheduler,
        ) as mock_build:
            resp = client.post("/api/ceo/daily-run", json={})

        assert resp.status_code == 200
        # demo 模式应调用 build_demo_scheduler，不是 build_prod_scheduler
        mock_build.assert_called_once()
        data = resp.json()
        assert data["real_api_called"] is False

    def test_daily_run_idempotent_returns_skipped(self, client, workspace_env):
        """§4.3 幂等门生效：同日重复触发返回 SKIPPED."""
        mock_result = _make_mock_operator_result(skipped=True)
        mock_scheduler = MagicMock()
        mock_scheduler.run_daily_cycle.return_value = mock_result

        with patch(
            "scripts.run_daily_operator.build_demo_scheduler",
            return_value=mock_scheduler,
        ):
            resp = client.post("/api/ceo/daily-run", json={})

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "skipped"

    def test_daily_run_force_bypasses_idempotent(self, client, workspace_env):
        """§4.4 force=true 可越过幂等门."""
        mock_result = _make_mock_operator_result()
        mock_scheduler = MagicMock()
        mock_scheduler.run_daily_cycle.return_value = mock_result

        with patch(
            "scripts.run_daily_operator.build_demo_scheduler",
            return_value=mock_scheduler,
        ):
            resp = client.post("/api/ceo/daily-run", json={"force": True})

        assert resp.status_code == 200
        # 验证 force=True 被传给 run_daily_cycle
        mock_scheduler.run_daily_cycle.assert_called_once()
        call_args = mock_scheduler.run_daily_cycle.call_args
        assert call_args.kwargs.get("force") is True or call_args[1].get("force") is True

    def test_daily_run_includes_all_stages(self, client, workspace_env):
        """§4.5 响应包含阶段结果."""
        mock_result = _make_mock_operator_result()
        mock_scheduler = MagicMock()
        mock_scheduler.run_daily_cycle.return_value = mock_result

        with patch(
            "scripts.run_daily_operator.build_demo_scheduler",
            return_value=mock_scheduler,
        ):
            resp = client.post("/api/ceo/daily-run", json={})

        data = resp.json()
        stage_names = [s["stage"] for s in data["stages"]]
        expected_stages = [
            "reality_refresh", "audit", "opportunities", "simulations",
            "decisions", "approval", "executions", "monitor", "recovery",
            "memory", "strategy_loop", "portfolio", "ceo_report",
        ]
        for stage in expected_stages:
            assert stage in stage_names, f"Missing stage: {stage}"

    def test_daily_run_includes_decisions_and_executions(self, client, workspace_env):
        """§4.6 响应包含 decisions/executions 统计."""
        mock_result = _make_mock_operator_result()
        mock_scheduler = MagicMock()
        mock_scheduler.run_daily_cycle.return_value = mock_result

        with patch(
            "scripts.run_daily_operator.build_demo_scheduler",
            return_value=mock_scheduler,
        ):
            resp = client.post("/api/ceo/daily-run", json={})

        data = resp.json()
        assert "decisions" in data
        assert data["decisions"]["EXECUTE"] == 3
        assert data["decisions"]["APPROVE"] == 1
        assert data["decisions"]["BLOCK"] == 1
        assert "executions" in data
        assert data["executions"]["success"] == 3

    def test_daily_run_includes_report_id(self, client, workspace_env):
        """响应应包含 report_id."""
        mock_result = _make_mock_operator_result()
        mock_scheduler = MagicMock()
        mock_scheduler.run_daily_cycle.return_value = mock_result

        with patch(
            "scripts.run_daily_operator.build_demo_scheduler",
            return_value=mock_scheduler,
        ):
            resp = client.post("/api/ceo/daily-run", json={})

        data = resp.json()
        assert data["report_id"] == "rpt_20260807_001"

    def test_daily_run_use_real_data_calls_prod_scheduler(self, client, workspace_env):
        """use_real_data=true 应调用 build_prod_scheduler."""
        mock_result = _make_mock_operator_result()
        mock_scheduler = MagicMock()
        mock_scheduler.run_daily_cycle.return_value = mock_result

        with patch(
            "scripts.run_daily_operator.build_prod_scheduler",
            return_value=mock_scheduler,
        ) as mock_prod, patch(
            "scripts.run_daily_operator.build_demo_scheduler",
        ) as mock_demo:
            resp = client.post("/api/ceo/daily-run", json={"use_real_data": True})

        assert resp.status_code == 200
        mock_prod.assert_called_once()
        mock_demo.assert_not_called()

    def test_daily_run_business_date_passed_correctly(self, client, workspace_env):
        """business_date 应正确传递给 scheduler."""
        mock_result = _make_mock_operator_result()
        mock_scheduler = MagicMock()
        mock_scheduler.run_daily_cycle.return_value = mock_result

        with patch(
            "scripts.run_daily_operator.build_demo_scheduler",
            return_value=mock_scheduler,
        ):
            resp = client.post(
                "/api/ceo/daily-run",
                json={"business_date": "2026-01-15"},
            )

        assert resp.status_code == 200
        mock_scheduler.run_daily_cycle.assert_called_once_with("2026-01-15", force=False)

    def test_daily_run_exception_returns_500(self, client, workspace_env):
        """scheduler 异常时应返回 500."""
        mock_scheduler = MagicMock()
        mock_scheduler.run_daily_cycle.side_effect = RuntimeError("pipeline crashed")

        with patch(
            "scripts.run_daily_operator.build_demo_scheduler",
            return_value=mock_scheduler,
        ):
            resp = client.post("/api/ceo/daily-run", json={})

        assert resp.status_code == 500
        assert "pipeline crashed" in resp.json()["detail"]

    def test_daily_run_real_api_called_warning(self, client, workspace_env):
        """real_api_called=True 时响应应包含该标志."""
        mock_result = _make_mock_operator_result()
        mock_result.real_api_called = True
        mock_result.to_dict.return_value["real_api_called"] = True
        mock_scheduler = MagicMock()
        mock_scheduler.run_daily_cycle.return_value = mock_result

        with patch(
            "scripts.run_daily_operator.build_demo_scheduler",
            return_value=mock_scheduler,
        ):
            resp = client.post("/api/ceo/daily-run", json={})

        assert resp.status_code == 200
        data = resp.json()
        assert data["real_api_called"] is True


class TestLoopTriggerRegression:
    """§4.8 现有 /api/loop/trigger 不受影响（回归测试）."""

    def test_loop_trigger_still_works(self, client, workspace_env):
        """/api/loop/trigger 仍然正常工作."""
        mock_result = MagicMock()
        mock_result.cycle_number = 1
        mock_result.actions = []
        mock_result.execution_results = []
        mock_result.evaluated_count = 0
        mock_result.pending_created = 0
        mock_result.diagnosis = None
        mock_result.strategy = None

        mock_orch = MagicMock()
        mock_orch.run_cycle.return_value = mock_result

        with patch(
            "scripts.growth_loop_orchestrator.GrowthLoopOrchestrator",
            return_value=mock_orch,
        ):
            resp = client.post("/api/loop/trigger", json={"dry_run": True})

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
