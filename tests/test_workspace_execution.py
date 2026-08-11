"""Workspace 执行层测试 — 审批 API + 触发 Loop + SSE + RealDataProvider.

测试覆盖:
  1. 审批 API: approve/reject (404, 成功, 重复决议)
  2. 触发 Loop API: dry_run 模式
  3. SSE 端点: content-type 和响应格式
  4. Memory 端点: 数据结构和摘要
  5. RealDataProvider: agents, games, tasks, decisions

设计原则:
  - 全部使用 tmp_path, 绝不污染 data/
  - 用 monkeypatch 替换 DecisionValidator 路径
  - 用 mock 替换 GrowthLoopOrchestrator.run_cycle
  - FastAPI TestClient 测试 HTTP 端点
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ── Fixtures ────────────────────────────────────────────────


@pytest.fixture
def workspace_env(tmp_path: Path, monkeypatch):
    """设置 Workspace 测试环境: real provider + 临时数据目录."""
    # 使用 real provider
    monkeypatch.setenv("WORKSPACE_DATA_PROVIDER", "real")

    # 创建临时数据目录结构
    data_dir = tmp_path / "data"
    growth_loop_dir = data_dir / "growth_loop"
    ceo_dir = data_dir / "ceo"
    ceo_audit_dir = ceo_dir / "audit"
    game_reality_dir = ceo_dir / "game_reality"
    workspace_dir = data_dir / "workspace"

    for d in [growth_loop_dir, ceo_audit_dir, game_reality_dir, workspace_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # 创建最小的测试数据
    _create_test_approval_queue(ceo_dir / "approval_queue.jsonl")
    _create_test_cycle_history(growth_loop_dir / "cycle_history.jsonl")
    _create_test_game_reality(game_reality_dir)
    _create_test_company_snapshot(ceo_dir / "company_snapshot.jsonl")

    # Monkeypatch real_provider 的路径常量
    from src.market_ops.workspace import real_provider as rp

    monkeypatch.setattr(rp, "GROWTH_LOOP_HISTORY", growth_loop_dir / "cycle_history.jsonl")
    monkeypatch.setattr(rp, "CEO_DECISIONS_AUDIT", ceo_audit_dir / "decisions.jsonl")
    monkeypatch.setattr(rp, "CEO_APPROVAL_QUEUE", ceo_dir / "approval_queue.jsonl")
    monkeypatch.setattr(rp, "GAME_REALITY_DIR", game_reality_dir)
    monkeypatch.setattr(rp, "COMPANY_SNAPSHOT", ceo_dir / "company_snapshot.jsonl")

    # 重置单例
    monkeypatch.setattr(rp, "_real_provider", None)

    # Monkeypatch app.py 的路径
    from src.market_ops.workspace import app as app_module

    monkeypatch.setattr(app_module, "_PROJECT_ROOT", tmp_path)

    # 重置 bridge 单例 (避免 collaboration 事件源从旧数据目录读取, 污染 SSE 事件源测试)
    if hasattr(app_module._get_data_numerical_bridge, "_instance"):
        monkeypatch.delattr(app_module._get_data_numerical_bridge, "_instance")
    if hasattr(app_module._get_numerical_data_bridge, "_instance"):
        monkeypatch.delattr(app_module._get_numerical_data_bridge, "_instance")
    monkeypatch.setattr(
        app_module, "_EXECUTION_MEMORY", ceo_dir / "execution_memory.jsonl"
    )
    monkeypatch.setattr(
        app_module, "_EXECUTION_EXPERIENCE", ceo_dir / "execution_experience.jsonl"
    )
    monkeypatch.setattr(
        app_module, "_OPERATOR_MEMORY", ceo_dir / "operator_memory.jsonl"
    )

    return {
        "data_dir": data_dir,
        "approval_queue": ceo_dir / "approval_queue.jsonl",
        "audit_dir": ceo_audit_dir,
    }


@pytest.fixture
def client(workspace_env):
    """FastAPI TestClient — 自动注入 real provider."""
    from src.market_ops.workspace.app import app
    # 重置 aggregator 单例以使用新的 provider
    from src.market_ops.workspace import aggregator as agg_module
    agg_module._aggregator = None
    return TestClient(app)


def _create_test_approval_queue(path: Path) -> None:
    """创建测试用 approval_queue.jsonl (2 条 pending 决策)."""
    records = [
        {
            "audit_id": "dec_test_001",
            "decision_id": "dec_test_001",
            "game_id": "cooking_fever_x",
            "action": "update_budget",
            "reason": "ROAS 下降, 建议降低预算",
            "confidence": 0.75,
            "status": "pending",
            "queued": True,
            "executed": False,
            "inputs": {
                "opportunity_type": "budget_optimization",
                "expected_value": 150.0,
                "simulation": {"expected_revenue_change": 0.05, "expected_roas_change": 0.03},
            },
            "timestamp": "2026-08-07T10:00:00Z",
        },
        {
            "audit_id": "dec_test_002",
            "decision_id": "dec_test_002",
            "game_id": "merge_monster",
            "action": "pause_campaign",
            "reason": "Creative 疲劳, 建议暂停",
            "confidence": 0.82,
            "status": "pending",
            "queued": True,
            "executed": False,
            "inputs": {
                "opportunity_type": "creative_fatigue",
                "expected_value": 200.0,
                "simulation": {"expected_revenue_change": -0.02, "expected_roas_change": 0.08},
            },
            "timestamp": "2026-08-07T11:00:00Z",
        },
    ]
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _create_test_cycle_history(path: Path) -> None:
    """创建测试用 cycle_history.jsonl (1 个 cycle)."""
    record = {
        "cycle_number": 1,
        "loop_id": "test_loop",
        "started_at": "2026-08-07T10:00:00Z",
        "completed_at": "2026-08-07T10:05:00Z",
        "actions_planned": 2,
        "actions_executed": 2,
        "actions_rolled_back": 0,
        "actions": [
            {
                "action_id": "act_001",
                "action_type": "update_budget",
                "status": "completed",
                "executed_at": "2026-08-07T10:02:00Z",
                "created_at": "2026-08-07T10:01:00Z",
                "expected_impact": {"strategy_type": "budget_increase", "metric": "cooking_fever_x"},
                "reason": "提升 ROAS",
                "approval_level": 0,
                "risk_level": "low",
            },
            {
                "action_id": "act_002",
                "action_type": "pause_campaign",
                "status": "pending",
                "created_at": "2026-08-07T10:03:00Z",
                "expected_impact": {"strategy_type": "pause_fatigued", "metric": "merge_monster"},
                "reason": "暂停疲劳创意",
                "approval_level": 1,
                "risk_level": "medium",
            },
        ],
        "execution_results": [
            {
                "action_id": "act_001",
                "success": True,
                "dry_run": False,
                "status": "completed",
                "executed_at": "2026-08-07T10:02:00Z",
            },
        ],
    }
    with path.open("w", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _create_test_game_reality(game_dir: Path) -> None:
    """创建测试用 game_reality 数据 (2 个游戏)."""
    games = {
        "cooking_fever_x": {
            "game_id": "cooking_fever_x",
            "health_score": 0.55,
            "metrics": {
                "dau": 38000,
                "revenue_total": 1390.0,
                "spend": 620.0,
                "roas": 2.24,
                "retention_d1": 0.42,
                "retention_d7": 0.18,
                "retention_d30": 0.08,
                "arppu": 0.5,
                "player_ltv": 3.5,
            },
            "signals": [{"signal_type": "release_state", "raw": {"status": "published"}}],
        },
        "merge_monster": {
            "game_id": "merge_monster",
            "health_score": 0.52,
            "metrics": {
                "dau": 5000,
                "revenue_total": 93.0,
                "spend": 62.0,
                "roas": 1.50,
                "retention_d1": 0.35,
                "retention_d7": 0.12,
                "retention_d30": 0.04,
                "arppu": 0.3,
                "player_ltv": 2.1,
            },
            "signals": [{"signal_type": "release_state", "raw": {"status": "published"}}],
        },
    }
    for game_id, snapshot in games.items():
        path = game_dir / f"{game_id}.jsonl"
        with path.open("w", encoding="utf-8") as f:
            f.write(json.dumps(snapshot, ensure_ascii=False) + "\n")


def _create_test_company_snapshot(path: Path) -> None:
    """创建测试用 company_snapshot.jsonl."""
    snapshot = {
        "date": "2026-08-07",
        "active_games": 2,
        "total_games": 2,
        "total_dau": 43000,
        "total_revenue": 1483.0,
        "total_spend": 682.0,
    }
    with path.open("w", encoding="utf-8") as f:
        f.write(json.dumps(snapshot, ensure_ascii=False) + "\n")


# ── 1. 审批 API 测试 ────────────────────────────────────────


class TestApprovalAPI:
    """审批 API 端点测试."""

    def test_approve_nonexistent_returns_404(self, client, workspace_env):
        """不存在的 decision_id 应返回 404."""
        resp = client.post(
            "/api/decisions/nonexistent_id/approve",
            json={"approver": "test_admin"},
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_reject_nonexistent_returns_404(self, client, workspace_env):
        """不存在的 decision_id 应返回 404."""
        resp = client.post(
            "/api/decisions/nonexistent_id/reject",
            json={"approver": "test_admin"},
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_approve_pending_decision_succeeds(self, client, workspace_env):
        """批准 pending 决策应成功."""
        resp = client.post(
            "/api/decisions/dec_test_001/approve",
            json={"approver": "test_admin"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["approver"] == "test_admin"
        assert data["decision_id"] == "dec_test_001"

    def test_reject_pending_decision_succeeds(self, client, workspace_env):
        """驳回 pending 决策应成功."""
        resp = client.post(
            "/api/decisions/dec_test_002/reject",
            json={"approver": "test_admin", "reason": "风险过高"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "rejected"
        assert data["decision_id"] == "dec_test_002"

    def test_double_approve_returns_404(self, client, workspace_env):
        """已决议的决策再次 approve 应返回 404."""
        # 第一次 approve 成功
        resp1 = client.post(
            "/api/decisions/dec_test_001/approve",
            json={"approver": "test_admin"},
        )
        assert resp1.status_code == 200

        # 第二次 approve 应失败 (已决议)
        resp2 = client.post(
            "/api/decisions/dec_test_001/approve",
            json={"approver": "test_admin"},
        )
        assert resp2.status_code == 404

    def test_approve_after_reject_returns_404(self, client, workspace_env):
        """已驳回的决策再次 approve 应返回 404."""
        # 先 reject
        resp1 = client.post(
            "/api/decisions/dec_test_002/reject",
            json={"approver": "test_admin"},
        )
        assert resp1.status_code == 200

        # 再 approve 应失败
        resp2 = client.post(
            "/api/decisions/dec_test_002/approve",
            json={"approver": "test_admin"},
        )
        assert resp2.status_code == 404

    def test_approval_writes_resolution_to_queue(self, client, workspace_env):
        """审批后应在 approval_queue.jsonl 中追加 resolution 行."""
        client.post(
            "/api/decisions/dec_test_001/approve",
            json={"approver": "test_admin"},
        )

        # 读取 approval_queue.jsonl 验证 resolution 行
        queue_path = workspace_env["approval_queue"]
        lines = queue_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 3  # 2 条原始 + 1 条 resolution

        resolution = json.loads(lines[-1])
        assert resolution["audit_id"] == "dec_test_001"
        assert resolution["status"] == "approved"
        assert resolution["kind"] == "resolution"


# ── 2. 触发 GrowthLoop API 测试 ─────────────────────────────


class TestLoopTriggerAPI:
    """触发 GrowthLoop API 端点测试."""

    def test_trigger_loop_dry_run_success(self, client, workspace_env):
        """dry_run 模式触发 Loop 应成功."""
        # Mock GrowthLoopOrchestrator
        mock_result = MagicMock()
        mock_result.cycle_number = 99
        mock_result.actions = [{"id": "act_1"}]
        mock_result.execution_results = [{"id": "act_1", "success": True}]
        mock_result.evaluated_count = 0
        mock_result.pending_created = 0

        mock_orchestrator = MagicMock()
        mock_orchestrator.run_cycle.return_value = mock_result

        with patch(
            "scripts.growth_loop_orchestrator.GrowthLoopOrchestrator",
            return_value=mock_orchestrator,
        ):
            # 确保 scripts 在 path 中
            if "scripts" not in str(sys.path):
                sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

            resp = client.post(
                "/api/loop/trigger",
                json={"dry_run": True, "days": 7},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["cycle_number"] == 99
        assert data["dry_run"] is True
        assert data["actions_planned"] == 1
        assert data["actions_executed"] == 1
        mock_orchestrator.run_cycle.assert_called_once()

    def test_trigger_loop_returns_duration(self, client, workspace_env):
        """触发 Loop 应返回执行耗时."""
        mock_result = MagicMock()
        mock_result.cycle_number = 1
        mock_result.actions = []
        mock_result.execution_results = []
        mock_result.evaluated_count = 0
        mock_result.pending_created = 0

        with patch(
            "scripts.growth_loop_orchestrator.GrowthLoopOrchestrator.run_cycle",
            return_value=mock_result,
        ):
            resp = client.post(
                "/api/loop/trigger",
                json={"dry_run": True},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "duration_seconds" in data
        assert isinstance(data["duration_seconds"], float)
        assert data["duration_seconds"] >= 0


# ── 3. SSE 端点测试 ─────────────────────────────────────────


class TestSSEEndpoint:
    """SSE 实时事件流端点测试.

    注意: SSE 是无限流式响应, TestClient 会阻塞.
    因此直接测试生成器逻辑, 不通过 HTTP 请求.
    """

    def test_sse_generator_produces_event_data(self, workspace_env):
        """SSE 生成器应产生 'data: {...}\\n\\n' 格式的消息."""
        import asyncio
        from src.market_ops.workspace.real_provider import get_real_provider

        provider = get_real_provider()
        events = provider.get_events(limit=5)

        if not events:
            pytest.skip("No events available for SSE test")

        # 模拟 SSE 生成器逻辑
        latest = events[0]
        sse_message = f"data: {json.dumps(latest.to_dict(), ensure_ascii=False)}\n\n"

        assert sse_message.startswith("data: ")
        assert sse_message.endswith("\n\n")
        # 验证 data 部分是合法 JSON
        data_json = sse_message[6:].strip()
        parsed = json.loads(data_json)
        assert "id" in parsed
        assert "message" in parsed

    def test_sse_endpoint_registered_in_app(self, client, workspace_env):
        """SSE 端点应在 FastAPI app 中注册."""
        from src.market_ops.workspace.app import app

        routes = [r.path for r in app.routes]
        assert "/api/events/stream" in routes

        # 找到 SSE 路由, 验证 methods
        sse_route = next(r for r in app.routes if r.path == "/api/events/stream")
        assert "GET" in sse_route.methods


class TestSSEMultiSource:
    """SSE 多事件源收集测试 — 验证 _collect_sse_events 聚合逻辑."""

    def test_collect_sse_events_returns_list(self, workspace_env):
        """_collect_sse_events 应返回事件列表."""
        from src.market_ops.workspace.app import _collect_sse_events

        events = _collect_sse_events(limit=20)
        assert isinstance(events, list)

    def test_collect_sse_events_has_unified_format(self, workspace_env):
        """每个事件应有统一格式 (id, timestamp, source, event_type, message)."""
        from src.market_ops.workspace.app import _collect_sse_events

        events = _collect_sse_events(limit=10)
        for ev in events:
            assert "id" in ev
            assert "timestamp" in ev
            assert "source" in ev
            assert "event_type" in ev
            assert "message" in ev
            assert "agent_name" in ev
            assert "data" in ev
            assert ev["source"] in ("workspace", "collaboration", "ceo_memory")

    def test_collect_sse_events_sorted_by_time_desc(self, workspace_env):
        """事件应按时间倒序排列."""
        from src.market_ops.workspace.app import _collect_sse_events

        events = _collect_sse_events(limit=20)
        for i in range(len(events) - 1):
            assert events[i]["timestamp"] >= events[i + 1]["timestamp"]

    def test_collect_sse_events_respects_limit(self, workspace_env):
        """应尊重 limit 参数."""
        from src.market_ops.workspace.app import _collect_sse_events

        events = _collect_sse_events(limit=5)
        assert len(events) <= 5

    def test_collect_sse_events_includes_workspace_source(self, workspace_env):
        """应包含 workspace 事件源."""
        from src.market_ops.workspace.app import _collect_sse_events

        events = _collect_sse_events(limit=20)
        sources = {ev["source"] for ev in events}
        # workspace 事件源应存在 (mock 或 real provider 都有事件)
        assert "workspace" in sources or len(events) == 0

    def test_sse_generator_emits_id_and_event_fields(self, workspace_env):
        """SSE 生成器应产生含 id: 和 event: 字段的消息."""
        import asyncio
        from src.market_ops.workspace.app import _collect_sse_events

        events = _collect_sse_events(limit=5)
        if not events:
            pytest.skip("No events for SSE generator test")

        # 模拟 SSE 生成器的单条消息格式
        ev = events[0]
        eid = ev["id"]
        payload = json.dumps(ev, ensure_ascii=False)
        sse_message = f"id: {eid}\nevent: {ev['source']}\ndata: {payload}\n\n"

        assert sse_message.startswith(f"id: {eid}")
        assert "event: " in sse_message
        assert "data: " in sse_message
        assert sse_message.endswith("\n\n")
        # 验证 data 部分是合法 JSON
        data_line = [l for l in sse_message.split("\n") if l.startswith("data: ")][0]
        parsed = json.loads(data_line[6:])
        assert parsed["id"] == eid
        assert "source" in parsed


# ── 4. Memory 端点测试 ──────────────────────────────────────


class TestMemoryEndpoint:
    """Memory 端点测试."""

    def test_memory_returns_correct_structure(self, client, workspace_env):
        """Memory 端点应返回正确的数据结构."""
        resp = client.get("/api/memory?limit=10")
        assert resp.status_code == 200
        data = resp.json()

        assert "execution_memory" in data
        assert "execution_experience" in data
        assert "operator_memory" in data
        assert "summary" in data

        summary = data["summary"]
        assert "total_executions" in summary
        assert "successful_executions" in summary
        assert "success_rate" in summary
        assert "total_experiences" in summary
        assert "positive_rewards" in summary
        assert "positive_rate" in summary
        assert "operator_logs" in summary

    def test_memory_handles_missing_files(self, client, workspace_env):
        """Memory 端点应在数据文件不存在时返回空列表."""
        resp = client.get("/api/memory?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        # 测试环境没有创建 execution_memory 等文件, 应返回空列表
        assert data["execution_memory"] == []
        assert data["execution_experience"] == []
        assert data["operator_memory"] == []
        assert data["summary"]["total_executions"] == 0
        assert data["summary"]["success_rate"] == 0.0


# ── 5. RealDataProvider 测试 ─────────────────────────────────


class TestRealDataProvider:
    """RealDataProvider 数据接入测试."""

    def test_get_agents_returns_default_organization(self, workspace_env):
        """Agent 列表应返回默认组织 (10 个 Agent, 含 DataAnalyst + PlayerSupport)."""
        from src.market_ops.workspace.real_provider import get_real_provider

        provider = get_real_provider()
        agents = provider.get_agents()

        # 首次调用会创建默认组织并持久化 (10 角色: supervisor/ua/creative/monetization/product/liveops/designer/numerical/data_analyst/player_support)
        assert len(agents) == 10
        # Agent ID 是 UUID, 检查 name 或 department 包含 supervisor
        agent_names = [a.name.lower() for a in agents]
        assert any("supervisor" in name for name in agent_names)

    def test_get_games_returns_active_games(self, workspace_env):
        """游戏列表应返回有真实数据的游戏."""
        from src.market_ops.workspace.real_provider import get_real_provider

        provider = get_real_provider()
        games = provider.get_games()

        assert len(games) == 2  # cooking_fever_x + merge_monster
        game_ids = [g.id for g in games]
        assert "cooking_fever_x" in game_ids
        assert "merge_monster" in game_ids

        # 验证 KPI 字段
        cooking = next(g for g in games if g.id == "cooking_fever_x")
        assert cooking.dau == 38000
        assert cooking.revenue == 1390.0
        assert cooking.roas == 2.24
        assert cooking.health_score == 55  # 0.55 * 100

    def test_get_tasks_returns_real_actions(self, workspace_env):
        """任务列表应从 GrowthLoop cycle_history 读取真实 actions."""
        from src.market_ops.workspace.real_provider import get_real_provider

        provider = get_real_provider()
        tasks = provider.get_tasks()

        assert len(tasks) == 2  # 1 个 cycle, 2 个 actions
        assert any(t.id == "act_001" for t in tasks)
        assert any(t.id == "act_002" for t in tasks)

        # 验证任务状态映射
        act_001 = next(t for t in tasks if t.id == "act_001")
        assert act_001.status == "completed"  # 有 executed_at
        assert act_001.agent_name == "GrowthLoop Engine"

    def test_get_decisions_returns_pending_and_resolved(self, workspace_env):
        """决策列表应返回 pending 和已决议的决策."""
        from src.market_ops.workspace.real_provider import get_real_provider

        provider = get_real_provider()
        decisions = provider.get_decisions()

        # 2 条 pending (approval_queue 中没有 resolution 行)
        assert len(decisions) == 2
        # 所有决策都应有非空 status
        assert all(d.status for d in decisions)
        # 验证决策 ID 正确
        decision_ids = {d.id for d in decisions}
        assert "dec_test_001" in decision_ids
        assert "dec_test_002" in decision_ids

    def test_get_kpi_aggregates_from_company_snapshot(self, workspace_env):
        """KPI 应从 company_snapshot 读取聚合数据."""
        from src.market_ops.workspace.real_provider import get_real_provider

        provider = get_real_provider()
        kpi = provider.get_kpi()

        assert kpi.games == 2
        assert kpi.total_dau == 43000
        assert kpi.total_revenue == 1483.0
        assert kpi.ai_tasks == 2  # 2 个真实 tasks

    def test_get_events_from_cycle_history(self, workspace_env):
        """事件流应从 cycle_history 读取 cycle 事件."""
        from src.market_ops.workspace.real_provider import get_real_provider

        provider = get_real_provider()
        events = provider.get_events(limit=50)

        # 1 个 cycle 产生: start + exec result + end = 至少 3 个事件
        assert len(events) >= 3
        # 应按时间倒序
        timestamps = [e.timestamp for e in events if e.timestamp]
        assert timestamps == sorted(timestamps, reverse=True)


# ── 6. 健康检查测试 ─────────────────────────────────────────


class TestHealthCheck:
    """健康检查端点测试."""

    def test_healthz_returns_ok(self, client, workspace_env):
        """健康检查应返回健康状态 (healthy/degraded/critical)."""
        resp = client.get("/healthz")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("healthy", "degraded", "critical")
        assert data["service"] == "ai-game-studio-workspace"
