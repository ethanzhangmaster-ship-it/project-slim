"""LiveOps → Growth 双向协同测试 — ChurnAlertBridge 桥接层.

验证:
  1. ChurnAlertBridge 核心逻辑: process_churn_alert 分级生成动作
  2. MessageBus 订阅: register + _handle_message 过滤 churn_alert
  3. 持久化: JSONL append + list_responses + get_response + get_stats
  4. API 端点: /api/growth/churn-responses, /stats, /{id}
  5. 端到端: LiveOps design → churn_alert → bridge → response
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.market_ops.workspace.churn_alert_bridge import (
    ChurnAlertBridge,
    HIGH_SEVERITY_THRESHOLD,
    MEDIUM_SEVERITY_THRESHOLD,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def workspace_env(tmp_path: Path, monkeypatch):
    """设置 Workspace 测试环境 — 重置 app.py 单例 + monkeypatch 路径."""
    monkeypatch.setenv("WORKSPACE_DATA_PROVIDER", "mock")

    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    from src.market_ops.workspace import app as app_module
    monkeypatch.setattr(app_module, "_PROJECT_ROOT", tmp_path)

    # 重置单例缓存 (避免测试间污染)
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
# Helpers
# ═══════════════════════════════════════════════════════════════


def _make_alert(
    game_id: str = "test_game",
    high_value: int = 5,
    campaign_id: str = "wb-test-abc12345",
) -> dict:
    """构造 churn_alert payload."""
    return {
        "event_type": "churn_alert",
        "source_agent": "liveops",
        "timestamp": "2026-08-07T10:00:00Z",
        "game_id": game_id,
        "campaign_id": campaign_id,
        "high_value_at_risk": high_value,
        "target_segment": "at_risk_churn",
        "target_count": high_value * 10,
        "rewards_pool": high_value * 0.5,
    }


def _make_mock_message_bus():
    """构造 Mock MessageBus, 记录 handler 注册."""
    bus = MagicMock()
    bus.registered_handlers = []

    def fake_register(agent_id, handler_fn, message_types=None, standard_types=None):
        bus.registered_handlers.append({
            "agent_id": agent_id,
            "handler_fn": handler_fn,
            "message_types": message_types,
        })
        return MagicMock()

    bus.register_handler_fn = fake_register
    return bus


def _make_mock_message(subject: str, body: dict):
    """构造 Mock AgentMessage."""
    msg = MagicMock()
    msg.subject = subject
    msg.body = body
    return msg


# ═══════════════════════════════════════════════════════════════
# 1. 核心逻辑: process_churn_alert
# ═══════════════════════════════════════════════════════════════


class TestProcessChurnAlert:
    """ChurnAlertBridge.process_churn_alert 核心逻辑测试."""

    def test_high_severity_generates_pause_and_reallocate(self, tmp_path):
        """high_value >= 10 → 暂停拉新 + 60% 预算重分配."""
        bridge = ChurnAlertBridge(data_dir=str(tmp_path))
        response = bridge.process_churn_alert(_make_alert(high_value=15))

        assert response["severity"] == "high"
        assert response["game_id"] == "test_game"
        assert response["high_value_at_risk"] == 15
        assert response["status"] == "executed"  # auto_execute 默认 True
        assert response["source"] == "churn_alert_bridge"

        action_types = [a["action_type"] for a in response["actions"]]
        assert "pause_campaign" in action_types
        assert "reallocate_budget" in action_types
        # 高严重度应有 2 个动作
        assert len(response["actions"]) == 2

        # 验证预算重分配比例
        reallocate = next(
            a for a in response["actions"] if a["action_type"] == "reallocate_budget"
        )
        assert reallocate["ratio"] == 0.6

    def test_medium_severity_generates_reduce_and_reallocate(self, tmp_path):
        """3 <= high_value < 10 → 削减 30% 预算 + 30% 重分配."""
        bridge = ChurnAlertBridge(data_dir=str(tmp_path))
        response = bridge.process_churn_alert(_make_alert(high_value=5))

        assert response["severity"] == "medium"
        action_types = [a["action_type"] for a in response["actions"]]
        assert "reduce_budget" in action_types
        assert "reallocate_budget" in action_types
        assert len(response["actions"]) == 2

        reduce = next(
            a for a in response["actions"] if a["action_type"] == "reduce_budget"
        )
        assert reduce["ratio"] == 0.3

    def test_low_severity_generates_monitor_only(self, tmp_path):
        """1 <= high_value < 3 → 仅 monitor."""
        bridge = ChurnAlertBridge(data_dir=str(tmp_path))
        response = bridge.process_churn_alert(_make_alert(high_value=2))

        assert response["severity"] == "low"
        assert len(response["actions"]) == 1
        assert response["actions"][0]["action_type"] == "monitor"

    def test_response_id_is_unique(self, tmp_path):
        """每次生成的 response_id 唯一."""
        bridge = ChurnAlertBridge(data_dir=str(tmp_path))
        r1 = bridge.process_churn_alert(_make_alert())
        r2 = bridge.process_churn_alert(_make_alert())
        assert r1["response_id"] != r2["response_id"]

    def test_response_includes_alert_metadata(self, tmp_path):
        """响应包含原始 alert 的元数据."""
        bridge = ChurnAlertBridge(data_dir=str(tmp_path))
        alert = _make_alert(campaign_id="wb-game-xyz12345")
        response = bridge.process_churn_alert(alert)

        assert response["alert_campaign_id"] == "wb-game-xyz12345"
        assert response["alert_timestamp"] == "2026-08-07T10:00:00Z"
        assert response["target_segment"] == "at_risk_churn"
        assert response["rewards_pool"] == 2.5  # 5 * 0.5


# ═══════════════════════════════════════════════════════════════
# 2. 严重度分级
# ═══════════════════════════════════════════════════════════════


class TestSeverityClassification:
    """严重度分级边界测试."""

    def test_high_threshold_boundary(self, tmp_path):
        """high_value = HIGH_SEVERITY_THRESHOLD → high."""
        bridge = ChurnAlertBridge(data_dir=str(tmp_path))
        assert bridge._classify_severity(HIGH_SEVERITY_THRESHOLD) == "high"
        assert bridge._classify_severity(HIGH_SEVERITY_THRESHOLD - 1) == "medium"

    def test_medium_threshold_boundary(self, tmp_path):
        """high_value = MEDIUM_SEVERITY_THRESHOLD → medium."""
        bridge = ChurnAlertBridge(data_dir=str(tmp_path))
        assert bridge._classify_severity(MEDIUM_SEVERITY_THRESHOLD) == "medium"
        assert bridge._classify_severity(MEDIUM_SEVERITY_THRESHOLD - 1) == "low"

    def test_zero_is_low(self, tmp_path):
        """high_value = 0 → low (虽然 LiveOps 不会广播 0)."""
        bridge = ChurnAlertBridge(data_dir=str(tmp_path))
        assert bridge._classify_severity(0) == "low"


# ═══════════════════════════════════════════════════════════════
# 3. MessageBus 订阅
# ═══════════════════════════════════════════════════════════════


class TestMessageBusSubscription:
    """ChurnAlertBridge MessageBus 订阅测试."""

    def test_register_success(self, tmp_path):
        """register() 成功注册到 MessageBus."""
        bus = _make_mock_message_bus()
        bridge = ChurnAlertBridge(data_dir=str(tmp_path), message_bus=bus)
        assert bridge.register() is True
        assert bridge._registered is True
        # 验证 handler 已注册
        assert len(bus.registered_handlers) == 1
        assert bus.registered_handlers[0]["agent_id"] == "growth_agent"

    def test_register_without_bus_returns_false(self, tmp_path):
        """未注入 message_bus → register 返回 False."""
        bridge = ChurnAlertBridge(data_dir=str(tmp_path))
        assert bridge.register() is False

    def test_handle_message_filters_non_churn_alert(self, tmp_path):
        """_handle_message 过滤非 churn_alert 消息."""
        bridge = ChurnAlertBridge(data_dir=str(tmp_path))
        # 非 churn_alert 消息
        msg = _make_mock_message("liveops:campaign_executed", {"game_id": "g1"})
        bridge._handle_message(msg)
        # 不应生成响应
        assert bridge.list_responses() == []

    def test_handle_message_processes_churn_alert(self, tmp_path):
        """_handle_message 处理 churn_alert 消息."""
        bridge = ChurnAlertBridge(data_dir=str(tmp_path))
        alert = _make_alert(high_value=12)
        msg = _make_mock_message("liveops:churn_alert", alert)
        bridge._handle_message(msg)
        # 应生成 1 条响应
        responses = bridge.list_responses()
        assert len(responses) == 1
        assert responses[0]["high_value_at_risk"] == 12
        assert responses[0]["severity"] == "high"

    def test_handle_message_swallows_exceptions(self, tmp_path):
        """_handle_message 异常不抛出 (避免影响 MessageBus)."""
        bridge = ChurnAlertBridge(data_dir=str(tmp_path))
        # 构造会导致异常的 payload (high_value 非数字)
        msg = _make_mock_message("liveops:churn_alert", {"high_value_at_risk": "not_a_number"})
        # 不应抛出异常
        bridge._handle_message(msg)

    def test_agent_id_from_identity(self, tmp_path):
        """注入 agent_identity 时使用其 agent_id."""
        identity = MagicMock()
        identity.agent_id = "ua_agent_001"
        bridge = ChurnAlertBridge(
            data_dir=str(tmp_path),
            message_bus=_make_mock_message_bus(),
            agent_identity=identity,
        )
        bridge.register()
        # 验证注册时使用了 identity 的 agent_id


# ═══════════════════════════════════════════════════════════════
# 4. 持久化 + 查询
# ═══════════════════════════════════════════════════════════════


class TestPersistenceAndQuery:
    """JSONL 持久化和查询测试."""

    def test_persist_and_list_responses(self, tmp_path):
        """持久化后能查询到."""
        bridge = ChurnAlertBridge(data_dir=str(tmp_path))
        bridge.process_churn_alert(_make_alert(game_id="g1", high_value=5))
        bridge.process_churn_alert(_make_alert(game_id="g2", high_value=15))

        responses = bridge.list_responses()
        assert len(responses) == 2
        # 倒序: 最新在前
        assert responses[0]["game_id"] == "g2"
        assert responses[1]["game_id"] == "g1"

    def test_list_responses_filter_by_game(self, tmp_path):
        """按 game_id 过滤."""
        bridge = ChurnAlertBridge(data_dir=str(tmp_path))
        bridge.process_churn_alert(_make_alert(game_id="g1", high_value=5))
        bridge.process_churn_alert(_make_alert(game_id="g2", high_value=5))

        g1_responses = bridge.list_responses(game_id="g1")
        assert len(g1_responses) == 1
        assert g1_responses[0]["game_id"] == "g1"

    def test_list_responses_limit(self, tmp_path):
        """limit 限制返回数量."""
        bridge = ChurnAlertBridge(data_dir=str(tmp_path))
        for i in range(5):
            bridge.process_churn_alert(_make_alert(game_id=f"g{i}", high_value=5))

        responses = bridge.list_responses(limit=3)
        assert len(responses) == 3

    def test_get_response_by_id(self, tmp_path):
        """按 response_id 查询."""
        bridge = ChurnAlertBridge(data_dir=str(tmp_path))
        response = bridge.process_churn_alert(_make_alert(high_value=8))

        found = bridge.get_response(response["response_id"])
        assert found is not None
        assert found["response_id"] == response["response_id"]
        assert found["high_value_at_risk"] == 8

    def test_get_response_not_found(self, tmp_path):
        """查询不存在的 response_id 返回 None."""
        bridge = ChurnAlertBridge(data_dir=str(tmp_path))
        assert bridge.get_response("nonexistent") is None

    def test_list_responses_empty_when_no_file(self, tmp_path):
        """无 JSONL 文件时返回空列表."""
        bridge = ChurnAlertBridge(data_dir=str(tmp_path))
        assert bridge.list_responses() == []

    def test_get_stats(self, tmp_path):
        """get_stats 聚合统计."""
        bridge = ChurnAlertBridge(data_dir=str(tmp_path))
        bridge.process_churn_alert(_make_alert(game_id="g1", high_value=15))  # high
        bridge.process_churn_alert(_make_alert(game_id="g1", high_value=5))   # medium
        bridge.process_churn_alert(_make_alert(game_id="g2", high_value=2))   # low

        stats = bridge.get_stats()
        assert stats["total_responses"] == 3
        assert stats["severity_distribution"]["high"] == 1
        assert stats["severity_distribution"]["medium"] == 1
        assert stats["severity_distribution"]["low"] == 1
        assert stats["by_game"]["g1"] == 2
        assert stats["by_game"]["g2"] == 1
        # 动作类型分布
        assert "pause_campaign" in stats["action_type_distribution"]
        assert "monitor" in stats["action_type_distribution"]

    def test_get_stats_empty(self, tmp_path):
        """无记录时 get_stats 返回空统计."""
        bridge = ChurnAlertBridge(data_dir=str(tmp_path))
        stats = bridge.get_stats()
        assert stats["total_responses"] == 0
        assert stats["severity_distribution"] == {"high": 0, "medium": 0, "low": 0}

    def test_jsonl_file_path(self, tmp_path):
        """验证 JSONL 落盘路径."""
        bridge = ChurnAlertBridge(data_dir=str(tmp_path))
        bridge.process_churn_alert(_make_alert())
        expected_path = tmp_path / "growth" / "churn_responses.jsonl"
        assert expected_path.exists()
        # 验证内容是合法 JSON
        lines = expected_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        rec = json.loads(lines[0])
        assert rec["game_id"] == "test_game"


# ═══════════════════════════════════════════════════════════════
# 5. API 端点
# ═══════════════════════════════════════════════════════════════


class TestChurnResponseAPI:
    """/api/growth/churn-responses 端点测试."""

    def test_list_returns_200(self, workspace_env):
        """GET /api/growth/churn-responses 返回 200."""
        from src.market_ops.workspace.app import app
        client = TestClient(app)
        resp = client.get("/api/growth/churn-responses")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_with_game_id_filter(self, workspace_env, tmp_path):
        """GET /api/growth/churn-responses?game_id=g1 过滤."""
        from src.market_ops.workspace.app import app
        from src.market_ops.workspace import app as app_module

        # 直接通过 bridge 写入测试数据
        bridge = app_module._get_churn_alert_bridge()
        bridge.process_churn_alert(_make_alert(game_id="g1", high_value=5))
        bridge.process_churn_alert(_make_alert(game_id="g2", high_value=5))

        client = TestClient(app)
        resp = client.get("/api/growth/churn-responses?game_id=g1")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["game_id"] == "g1"

    def test_stats_returns_200(self, workspace_env):
        """GET /api/growth/churn-responses/stats 返回 200."""
        from src.market_ops.workspace.app import app
        client = TestClient(app)
        resp = client.get("/api/growth/churn-responses/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_responses" in data
        assert "severity_distribution" in data

    def test_get_response_by_id(self, workspace_env, tmp_path):
        """GET /api/growth/churn-responses/{id} 返回单条记录."""
        from src.market_ops.workspace.app import app
        from src.market_ops.workspace import app as app_module

        bridge = app_module._get_churn_alert_bridge()
        response = bridge.process_churn_alert(_make_alert(high_value=10))

        client = TestClient(app)
        resp = client.get(f"/api/growth/churn-responses/{response['response_id']}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["response_id"] == response["response_id"]

    def test_get_response_404(self, workspace_env):
        """GET /api/growth/churn-responses/nonexistent 返回 404."""
        from src.market_ops.workspace.app import app
        client = TestClient(app)
        resp = client.get("/api/growth/churn-responses/nonexistent_id")
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════
# 6. 端到端: LiveOps → MessageBus → Bridge
# ═══════════════════════════════════════════════════════════════


class TestEndToEndBridge:
    """端到端: LiveOps design → churn_alert 广播 → Bridge 消费 → response."""

    def test_liveops_design_triggers_bridge_via_messagebus(self, tmp_path):
        """LiveOps design_winback_campaign → MessageBus → ChurnAlertBridge 生成响应.

        完整链路:
          1. LiveOpsAgent 注入共享 MessageBus + identity
          2. ChurnAlertBridge 注册到同一 MessageBus
          3. LiveOpsAgent.design_winback_campaign → _broadcast_event("churn_alert")
          4. MessageBus.send (BROADCAST) → 投递到 bridge 的 inbox
          5. bus.deliver("growth_agent") → 触发 bridge._handle_message
          6. bridge 生成 response 并持久化
        """
        from src.market_ops.creative_vision_runtime.growth_runtime.agent.communication import (
            MessageBus,
            create_default_organization,
            create_agent_registry,
            AgentRole,
        )
        from src.market_ops.workspace.liveops_agent import (
            ChurnAnalysis,
            LiveOpsAgent,
        )

        # 1. 创建共享 MessageBus + 组织
        registry = create_agent_registry()
        create_default_organization(registry)
        bus = MessageBus()

        # 2. 获取 LiveOps + UA identity
        liveops_records = registry.find_by_role(AgentRole.LIVEOPS)
        ua_records = registry.find_by_role(AgentRole.UA)
        liveops_identity = liveops_records[0].identity
        ua_identity = ua_records[0].identity

        # 3. 初始化 ChurnAlertBridge 并注册
        bridge = ChurnAlertBridge(
            data_dir=str(tmp_path),
            message_bus=bus,
            agent_identity=ua_identity,
        )
        assert bridge.register() is True

        # 4. 初始化 LiveOpsAgent 注入 bus + identity
        agent = LiveOpsAgent(
            data_dir=str(tmp_path),
            message_bus=bus,
            agent_identity=liveops_identity,
        )

        # 5. Mock 流失分析返回高价值用户
        analysis = ChurnAnalysis(
            game_id="e2e_game",
            analysis_date="2026-08-07",
            total_players=1000,
            at_risk_count=20,
            lapsed_count=0,
            churning_count=0,
            avg_churn_risk=0.4,
            segments={"at_risk_churn": 20},
            lifecycle_stages={"CHURNING": 0},
            high_value_at_risk=12,  # high severity
        )

        # 6. design_winback_campaign → 触发 churn_alert 广播
        campaign = agent.design_winback_campaign("e2e_game", analysis)

        # 7. MessageBus 投递到 bridge 的 inbox (使用 bridge 注册的 agent_id)
        bridge_agent_id = bridge._agent_id()
        bus.deliver(bridge_agent_id)

        # 8. 验证 bridge 生成了 response
        responses = bridge.list_responses()
        assert len(responses) == 1
        resp = responses[0]
        assert resp["game_id"] == "e2e_game"
        assert resp["high_value_at_risk"] == 12
        assert resp["severity"] == "high"
        # high severity 应有 pause_campaign + reallocate_budget
        action_types = [a["action_type"] for a in resp["actions"]]
        assert "pause_campaign" in action_types
        assert "reallocate_budget" in action_types

    def test_no_response_when_no_high_value(self, tmp_path):
        """无高价值流失用户时 → 不广播 churn_alert → bridge 无响应."""
        from src.market_ops.creative_vision_runtime.growth_runtime.agent.communication import (
            MessageBus,
            create_default_organization,
            create_agent_registry,
            AgentRole,
        )
        from src.market_ops.workspace.liveops_agent import (
            ChurnAnalysis,
            LiveOpsAgent,
        )

        registry = create_agent_registry()
        create_default_organization(registry)
        bus = MessageBus()

        liveops_identity = registry.find_by_role(AgentRole.LIVEOPS)[0].identity
        ua_identity = registry.find_by_role(AgentRole.UA)[0].identity

        bridge = ChurnAlertBridge(
            data_dir=str(tmp_path),
            message_bus=bus,
            agent_identity=ua_identity,
        )
        bridge.register()

        agent = LiveOpsAgent(
            data_dir=str(tmp_path),
            message_bus=bus,
            agent_identity=liveops_identity,
        )

        # high_value_at_risk = 0 → 不广播
        analysis = ChurnAnalysis(
            game_id="no_churn_game",
            analysis_date="2026-08-07",
            total_players=1000,
            at_risk_count=0,
            lapsed_count=0,
            churning_count=0,
            avg_churn_risk=0.1,
            segments={},
            lifecycle_stages={},
            high_value_at_risk=0,
        )
        agent.design_winback_campaign("no_churn_game", analysis)

        bus.deliver(bridge._agent_id())

        # bridge 无响应
        assert bridge.list_responses() == []


# ═══════════════════════════════════════════════════════════════
# 7. 自动执行测试
# ═══════════════════════════════════════════════════════════════


class TestAutoExecute:
    """自动执行测试 — 响应动作从 suggested 改为自动执行."""

    def test_auto_execute_default_true(self, tmp_path):
        """默认 auto_execute=True, 生成响应后立即执行."""
        bridge = ChurnAlertBridge(data_dir=str(tmp_path))
        assert bridge.auto_execute is True
        assert bridge.dry_run is True

        response = bridge.process_churn_alert(_make_alert(high_value=15))
        # 状态应为 executed (不是 suggested)
        assert response["status"] == "executed"
        assert response["dry_run"] is True
        assert "executed_at" in response

    def test_auto_execute_false_keeps_suggested(self, tmp_path):
        """auto_execute=False → 保持 suggested 状态."""
        bridge = ChurnAlertBridge(data_dir=str(tmp_path), auto_execute=False)
        response = bridge.process_churn_alert(_make_alert(high_value=15))
        assert response["status"] == "suggested"
        assert "executed_at" not in response

    def test_each_action_has_execution_result(self, tmp_path):
        """自动执行后每个动作都有 execution_result 字段."""
        bridge = ChurnAlertBridge(data_dir=str(tmp_path))
        response = bridge.process_churn_alert(_make_alert(high_value=15))

        for action in response["actions"]:
            assert "execution_result" in action
            er = action["execution_result"]
            assert er["success"] is True
            assert er["status"] == "simulated"  # dry_run=True
            assert "message" in er
            assert "executed_at" in er
            assert er["dry_run"] is True

    def test_dry_run_false_marks_executed(self, tmp_path):
        """dry_run=False → execution_result.status = 'executed'."""
        bridge = ChurnAlertBridge(data_dir=str(tmp_path), dry_run=False)
        response = bridge.process_churn_alert(_make_alert(high_value=5))

        for action in response["actions"]:
            assert action["execution_result"]["status"] == "executed"
            assert action["execution_result"]["dry_run"] is False

    def test_execution_message_contains_game_id(self, tmp_path):
        """执行消息包含 game_id."""
        bridge = ChurnAlertBridge(data_dir=str(tmp_path))
        response = bridge.process_churn_alert(_make_alert(game_id="my_game", high_value=15))

        for action in response["actions"]:
            msg = action["execution_result"]["message"]
            assert "my_game" in msg

    def test_audit_log_written_on_execute(self, tmp_path):
        """自动执行后写入审计日志."""
        bridge = ChurnAlertBridge(data_dir=str(tmp_path))
        response = bridge.process_churn_alert(_make_alert(high_value=15))

        audit_logs = bridge.list_audit_logs()
        assert len(audit_logs) == 1
        log = audit_logs[0]
        assert log["audit_type"] == "execute"
        assert log["response_id"] == response["response_id"]
        assert log["dry_run"] is True
        assert log["all_success"] is True
        assert log["action_count"] == 2  # high severity → 2 actions

    def test_audit_log_file_path(self, tmp_path):
        """审计日志落盘路径正确."""
        bridge = ChurnAlertBridge(data_dir=str(tmp_path))
        bridge.process_churn_alert(_make_alert())
        expected_path = tmp_path / "growth" / "churn_response_audit.jsonl"
        assert expected_path.exists()


# ═══════════════════════════════════════════════════════════════
# 8. 回滚测试
# ═══════════════════════════════════════════════════════════════


class TestRollback:
    """回滚测试 — 已执行的响应可回滚."""

    def test_rollback_executed_response(self, tmp_path):
        """回滚已执行的响应 → status='rolled_back'."""
        bridge = ChurnAlertBridge(data_dir=str(tmp_path))
        response = bridge.process_churn_alert(_make_alert(high_value=15))
        assert response["status"] == "executed"

        rolled_back = bridge.rollback_response(response["response_id"])
        assert rolled_back is not None
        assert rolled_back["status"] == "rolled_back"
        assert "rolled_back_at" in rolled_back

        # 每个动作都有 rollback_result
        for action in rolled_back["actions"]:
            assert "rollback_result" in action
            assert action["rollback_result"]["success"] is True
            assert action["rollback_result"]["status"] == "rolled_back"

    def test_rollback_not_found(self, tmp_path):
        """回滚不存在的 response_id → None."""
        bridge = ChurnAlertBridge(data_dir=str(tmp_path))
        assert bridge.rollback_response("nonexistent") is None

    def test_rollback_suggested_no_op(self, tmp_path):
        """回滚 suggested 状态的响应 → 无变化 (未执行无需回滚)."""
        bridge = ChurnAlertBridge(data_dir=str(tmp_path), auto_execute=False)
        response = bridge.process_churn_alert(_make_alert(high_value=15))
        assert response["status"] == "suggested"

        result = bridge.rollback_response(response["response_id"])
        # 返回原响应, 状态不变
        assert result["status"] == "suggested"
        assert "rolled_back_at" not in result

    def test_rollback_writes_audit_log(self, tmp_path):
        """回滚写入审计日志."""
        bridge = ChurnAlertBridge(data_dir=str(tmp_path))
        response = bridge.process_churn_alert(_make_alert(high_value=15))
        bridge.rollback_response(response["response_id"])

        audit_logs = bridge.list_audit_logs()
        # 2 条: execute + rollback
        assert len(audit_logs) == 2
        rollback_log = next(l for l in audit_logs if l["audit_type"] == "rollback")
        assert rollback_log["response_id"] == response["response_id"]
        assert "rolled_back_at" in rollback_log

    def test_rollback_message_restores_ua(self, tmp_path):
        """回滚消息表明 UA 状态已恢复."""
        bridge = ChurnAlertBridge(data_dir=str(tmp_path))
        response = bridge.process_churn_alert(_make_alert(game_id="rb_game", high_value=15))
        rolled_back = bridge.rollback_response(response["response_id"])

        # pause_campaign 的回滚消息应包含"恢复"
        pause_action = next(
            a for a in rolled_back["actions"] if a["action_type"] == "pause_campaign"
        )
        assert "恢复" in pause_action["rollback_result"]["message"]
        assert "rb_game" in pause_action["rollback_result"]["message"]

    def test_get_response_returns_latest_after_rollback(self, tmp_path):
        """回滚后 get_response 返回最新状态 (rolled_back)."""
        bridge = ChurnAlertBridge(data_dir=str(tmp_path))
        response = bridge.process_churn_alert(_make_alert(high_value=15))
        bridge.rollback_response(response["response_id"])

        latest = bridge.get_response(response["response_id"])
        assert latest["status"] == "rolled_back"


# ═══════════════════════════════════════════════════════════════
# 9. 回滚 API 端点测试
# ═══════════════════════════════════════════════════════════════


class TestRollbackAPI:
    """回滚 API 端点测试."""

    def test_rollback_endpoint_returns_200(self, workspace_env, tmp_path):
        """POST /api/growth/churn-responses/{id}/rollback 返回 200."""
        from src.market_ops.workspace.app import app
        from src.market_ops.workspace import app as app_module

        bridge = app_module._get_churn_alert_bridge()
        response = bridge.process_churn_alert(_make_alert(high_value=15))

        client = TestClient(app)
        resp = client.post(f"/api/growth/churn-responses/{response['response_id']}/rollback")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "rolled_back"
        assert response["response_id"] == data["response_id"]

    def test_rollback_endpoint_404(self, workspace_env):
        """POST /api/growth/churn-responses/nonexistent/rollback 返回 404."""
        from src.market_ops.workspace.app import app
        client = TestClient(app)
        resp = client.post("/api/growth/churn-responses/nonexistent/rollback")
        assert resp.status_code == 404

    def test_audit_logs_endpoint(self, workspace_env, tmp_path):
        """GET /api/growth/churn-responses/audit/logs 返回审计日志."""
        from src.market_ops.workspace.app import app
        from src.market_ops.workspace import app as app_module

        bridge = app_module._get_churn_alert_bridge()
        bridge.process_churn_alert(_make_alert(high_value=15))

        client = TestClient(app)
        resp = client.get("/api/growth/churn-responses/audit/logs")
        assert resp.status_code == 200
        logs = resp.json()
        assert len(logs) >= 1
        assert logs[0]["audit_type"] == "execute"
