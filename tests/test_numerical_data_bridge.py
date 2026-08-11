"""NumericalDataBridge 测试 — Numerical Designer → Data Analyst 反向跨 Agent 协同.

测试覆盖 (与 test_data_numerical_bridge.py 对称):
  1. 单事件处理: tuning_recommended / numerical_modeled / ab_test_designed
  2. 完整反向闭环: run_reverse_closed_loop
  3. MessageBus 订阅: register / _handle_message
  4. 持久化与查询: list_collaborations / get_collaboration / get_stats
  5. CEO Memory 回流
  6. API 端点
  7. 边界场景: 无 data_analyst_agent / 无 message_bus
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.market_ops.workspace.numerical_data_bridge import NumericalDataBridge
from src.market_ops.workspace.data_analyst_agent import DataAnalystAgent


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def data_analyst_agent(tmp_path: Path) -> DataAnalystAgent:
    """创建 Data Analyst Agent (临时目录, 无外部依赖)."""
    return DataAnalystAgent(data_dir=str(tmp_path))


@pytest.fixture
def bridge(tmp_path: Path, data_analyst_agent: DataAnalystAgent) -> NumericalDataBridge:
    """创建 NumericalDataBridge (注入 data_analyst_agent, 无 message_bus)."""
    return NumericalDataBridge(
        data_dir=str(tmp_path),
        data_analyst_agent=data_analyst_agent,
    )


@pytest.fixture
def tuning_payload() -> dict:
    """调优建议事件 payload."""
    return {
        "game_id": "merge_game_001",
        "genre": "Merge",
        "target_metric": "retention_d1",
        "current_value": 0.35,
        "target_value": 0.45,
        "gap": -0.10,
        "parameter": "onboarding_reward",
        "current_param": 100.0,
        "suggested_param": 150.0,
        "adjustment_pct": 50.0,
        "expected_impact": "提升新用户首日留存",
        "priority": "HIGH",
        "risk_level": "LOW",
        "rationale": "D1 留存低于 benchmark, 调整新手奖励",
        "dau": 12000,
        "mau": 96000,
        "revenue_total": 6000.0,
        "payer_count": 720,
        "retention_d1": 0.35,
        "retention_d7": 0.18,
        "retention_d30": 0.10,
    }


@pytest.fixture
def modeling_payload() -> dict:
    """数值建模事件 payload."""
    return {
        "game_id": "merge_game_001",
        "genre": "Merge",
        "ltv": 2.5,
        "cac": 5.0,
        "roi": 1.5,
        "payback_days": 30,
        "dau": 12000,
        "mau": 96000,
        "retention_d1": 0.42,
        "retention_d7": 0.20,
        "retention_d30": 0.12,
        "revenue_total": 6000.0,
        "payer_count": 720,
    }


@pytest.fixture
def ab_test_payload() -> dict:
    """A/B 测试设计事件 payload."""
    return {
        "game_id": "merge_game_001",
        "genre": "Merge",
        "test_id": "test-merge-001-abc12345",
        "hypothesis": "调整新手奖励提升 D1 留存",
        "target_metric": "retention_d1",
        "variants": ["control", "treatment"],
        "dau": 12000,
        "mau": 96000,
        "retention_d1": 0.35,
        "retention_d7": 0.18,
        "retention_d30": 0.10,
        "revenue_total": 6000.0,
        "payer_count": 720,
    }


# ═══════════════════════════════════════════════════════════════
# 1. 单事件处理测试
# ═══════════════════════════════════════════════════════════════


class TestTuningRecommendation:
    def test_process_tuning_success(self, bridge, tuning_payload):
        """调优建议 → 异常检测 (成功)."""
        result = bridge.process_tuning_recommendation(tuning_payload)

        assert result["status"] == "success"
        assert result["trigger_event"] == "tuning_recommended"
        assert result["trigger_source"] == "numerical"
        assert result["target_method"] == "detect_anomalies"
        assert result["target_agent"] == "data_analyst"
        assert result["direction"] == "numerical_to_data_analyst"
        assert result["game_id"] == "merge_game_001"
        assert "anomaly_alerts" in result["analyst_output"]
        assert "collaboration_id" in result
        assert result["collaboration_id"].startswith("rev-colab-")

    def test_tuning_input_summary(self, bridge, tuning_payload):
        """验证 input_summary 包含调优关键信息."""
        result = bridge.process_tuning_recommendation(tuning_payload)
        summary = result["input_summary"]
        assert summary["tuning_target_metric"] == "retention_d1"
        assert summary["tuning_parameter"] == "onboarding_reward"
        assert summary["tuning_adjustment_pct"] == 50.0
        assert summary["tuning_priority"] == "HIGH"

    def test_tuning_persisted_to_jsonl(self, bridge, tuning_payload, tmp_path):
        """验证协同记录写入 JSONL."""
        bridge.process_tuning_recommendation(tuning_payload)
        jsonl_path = tmp_path / "collaboration" / "numerical_data.jsonl"
        assert jsonl_path.exists()
        lines = jsonl_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["trigger_event"] == "tuning_recommended"

    def test_tuning_ceo_memory_written(self, bridge, tuning_payload, tmp_path):
        """验证 CEO Memory 回流 (Bridge 写入的记录在最后)."""
        bridge.process_tuning_recommendation(tuning_payload)
        ceo_path = tmp_path / "ceo" / "execution_memory.jsonl"
        assert ceo_path.exists()
        lines = ceo_path.read_text(encoding="utf-8").strip().split("\n")
        # DataAnalystAgent 内部可能也写入 execution_memory, Bridge 的记录在最后
        assert len(lines) >= 1
        memory = json.loads(lines[-1])
        assert memory["domain"] == "numerical_data_bridge"
        assert memory["strategy_type"] == "reverse_cross_agent_collaboration"
        assert "Numerical" in memory["detail"]
        assert "Data Analyst" in memory["detail"]


class TestNumericalModeling:
    def test_process_modeling_success(self, bridge, modeling_payload):
        """数值建模 → 留存预测 (成功)."""
        result = bridge.process_numerical_modeling(modeling_payload)

        assert result["status"] == "success"
        assert result["trigger_event"] == "numerical_modeled"
        assert result["target_method"] == "predict_retention"
        assert "retention_prediction" in result["analyst_output"]

    def test_modeling_input_summary(self, bridge, modeling_payload):
        """验证 input_summary 包含模型关键指标."""
        result = bridge.process_numerical_modeling(modeling_payload)
        summary = result["input_summary"]
        assert summary["model_ltv"] == 2.5
        assert summary["model_cac"] == 5.0
        assert summary["model_roi"] == 1.5


class TestAbTestDesign:
    def test_process_ab_test_success(self, bridge, ab_test_payload):
        """A/B 测试设计 → 行为基线分析 (成功)."""
        result = bridge.process_ab_test_design(ab_test_payload)

        assert result["status"] == "success"
        assert result["trigger_event"] == "ab_test_designed"
        assert result["target_method"] == "analyze_behavior"
        assert "behavior_baseline" in result["analyst_output"]

    def test_ab_test_input_summary(self, bridge, ab_test_payload):
        """验证 input_summary 包含 A/B 测试信息."""
        result = bridge.process_ab_test_design(ab_test_payload)
        summary = result["input_summary"]
        assert summary["test_id"] == "test-merge-001-abc12345"
        assert summary["hypothesis"] == "调整新手奖励提升 D1 留存"
        assert summary["target_metric"] == "retention_d1"


# ═══════════════════════════════════════════════════════════════
# 2. 反向闭环测试
# ═══════════════════════════════════════════════════════════════


class TestReverseClosedLoop:
    def test_closed_loop_3_steps(self, bridge, tuning_payload):
        """反向闭环执行 3 步."""
        result = bridge.run_reverse_closed_loop("merge_game_001", tuning_payload)

        assert result["game_id"] == "merge_game_001"
        assert result["direction"] == "numerical_to_data_analyst"
        assert result["collaboration_count"] == 3
        assert len(result["steps"]) == 3

        # 验证步骤顺序
        assert result["steps"][0]["method"] == "detect_anomalies"
        assert result["steps"][1]["method"] == "predict_retention"
        assert result["steps"][2]["method"] == "analyze_behavior"

    def test_closed_loop_loop_id_format(self, bridge, tuning_payload):
        """loop_id 格式正确."""
        result = bridge.run_reverse_closed_loop("game_123", tuning_payload)
        assert result["loop_id"].startswith("reverse-loop-game_123-")

    def test_closed_loop_audit_persisted(self, bridge, tuning_payload, tmp_path):
        """闭环审计记录写入 JSONL."""
        bridge.run_reverse_closed_loop("merge_game_001", tuning_payload)
        audit_path = tmp_path / "collaboration" / "numerical_data_audit.jsonl"
        assert audit_path.exists()
        lines = audit_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        audit = json.loads(lines[0])
        assert audit["audit_type"] == "reverse_closed_loop"
        assert audit["collaboration_count"] == 3
        assert len(audit["steps_summary"]) == 3

    def test_closed_loop_all_success(self, bridge, tuning_payload):
        """闭环中所有步骤都成功."""
        result = bridge.run_reverse_closed_loop("merge_game_001", tuning_payload)
        for step in result["steps"]:
            assert step["record"]["status"] == "success"


# ═══════════════════════════════════════════════════════════════
# 3. MessageBus 订阅测试
# ═══════════════════════════════════════════════════════════════


class TestMessageBusSubscription:
    def test_register_without_bus_returns_false(self, bridge):
        """无 message_bus 时注册失败."""
        assert bridge.register() is False

    def test_register_with_bus(self, tmp_path, data_analyst_agent):
        """有 message_bus 时注册成功."""
        mock_bus = MagicMock()
        mock_bus.register_handler_fn = MagicMock()
        b = NumericalDataBridge(
            data_dir=str(tmp_path),
            message_bus=mock_bus,
            data_analyst_agent=data_analyst_agent,
        )
        assert b.register() is True
        mock_bus.register_handler_fn.assert_called_once()

    def test_handle_message_filters_non_numerical(self, bridge):
        """非 numerical: 前缀的消息被忽略."""
        mock_msg = MagicMock()
        mock_msg.subject = "data_analyst:behavior_analyzed"
        mock_msg.body = {}
        # 应返回 None 且不抛异常
        assert bridge._handle_message(mock_msg) is None

    def test_handle_message_routes_tuning(self, bridge, tuning_payload):
        """numerical:tuning_recommended 被路由到 process_tuning_recommendation."""
        mock_msg = MagicMock()
        mock_msg.subject = "numerical:tuning_recommended"
        mock_msg.body = tuning_payload
        bridge._handle_message(mock_msg)
        # 验证协同记录已写入
        records = bridge.list_collaborations()
        assert len(records) == 1
        assert records[0]["trigger_event"] == "tuning_recommended"

    def test_handle_message_routes_modeling(self, bridge, modeling_payload):
        """numerical:numerical_modeled 被路由到 process_numerical_modeling."""
        mock_msg = MagicMock()
        mock_msg.subject = "numerical:numerical_modeled"
        mock_msg.body = modeling_payload
        bridge._handle_message(mock_msg)
        records = bridge.list_collaborations()
        assert len(records) == 1
        assert records[0]["trigger_event"] == "numerical_modeled"

    def test_handle_message_unknown_event(self, bridge):
        """未知 numerical 事件被忽略."""
        mock_msg = MagicMock()
        mock_msg.subject = "numerical:unknown_event"
        mock_msg.body = {"game_id": "test"}
        bridge._handle_message(mock_msg)
        # 不应写入任何记录
        assert len(bridge.list_collaborations()) == 0


# ═══════════════════════════════════════════════════════════════
# 4. 持久化与查询测试
# ═══════════════════════════════════════════════════════════════


class TestPersistenceAndQuery:
    def test_list_collaborations_empty(self, bridge):
        """空状态查询返回空列表."""
        assert bridge.list_collaborations() == []

    def test_list_collaborations_with_records(self, bridge, tuning_payload, modeling_payload):
        """多条记录查询."""
        bridge.process_tuning_recommendation(tuning_payload)
        bridge.process_numerical_modeling(modeling_payload)
        records = bridge.list_collaborations()
        assert len(records) == 2

    def test_list_collaborations_filter_by_game(self, bridge, tuning_payload):
        """按 game_id 过滤."""
        payload2 = {**tuning_payload, "game_id": "game_002"}
        bridge.process_tuning_recommendation(tuning_payload)
        bridge.process_tuning_recommendation(payload2)
        records = bridge.list_collaborations(game_id="merge_game_001")
        assert len(records) == 1
        assert records[0]["game_id"] == "merge_game_001"

    def test_get_collaboration_by_id(self, bridge, tuning_payload):
        """按 ID 查询单条记录."""
        result = bridge.process_tuning_recommendation(tuning_payload)
        colab_id = result["collaboration_id"]
        found = bridge.get_collaboration(colab_id)
        assert found is not None
        assert found["collaboration_id"] == colab_id

    def test_get_collaboration_not_found(self, bridge):
        """查询不存在的 ID 返回 None."""
        assert bridge.get_collaboration("nonexistent-id") is None

    def test_get_stats(self, bridge, tuning_payload, modeling_payload):
        """统计信息."""
        bridge.process_tuning_recommendation(tuning_payload)
        bridge.process_numerical_modeling(modeling_payload)
        stats = bridge.get_stats()
        assert stats["direction"] == "numerical_to_data_analyst"
        assert stats["total_collaborations"] == 2
        assert "tuning_recommended" in stats["event_type_counts"]
        assert "numerical_modeled" in stats["event_type_counts"]
        assert "detect_anomalies" in stats["method_counts"]
        assert "predict_retention" in stats["method_counts"]
        assert stats["status_counts"].get("success", 0) == 2


# ═══════════════════════════════════════════════════════════════
# 5. 边界场景测试
# ═══════════════════════════════════════════════════════════════


class TestEdgeCases:
    def test_no_data_analyst_agent(self, tmp_path):
        """无 data_analyst_agent 时状态为 skipped_no_agent."""
        b = NumericalDataBridge(data_dir=str(tmp_path))
        result = b.process_tuning_recommendation({"game_id": "test"})
        assert result["status"] == "skipped_no_agent"
        assert result["analyst_output"] == {}

    def test_no_message_bus_register(self, tmp_path, data_analyst_agent):
        """无 message_bus 时 register 返回 False."""
        b = NumericalDataBridge(
            data_dir=str(tmp_path),
            data_analyst_agent=data_analyst_agent,
        )
        assert b.register() is False

    def test_agent_id_with_identity(self, tmp_path, data_analyst_agent):
        """有 agent_identity 时返回 identity.agent_id."""
        mock_identity = MagicMock()
        mock_identity.agent_id = "data_analyst_001"
        b = NumericalDataBridge(
            data_dir=str(tmp_path),
            agent_identity=mock_identity,
            data_analyst_agent=data_analyst_agent,
        )
        assert b._agent_id() == "data_analyst_001"

    def test_agent_id_without_identity(self, tmp_path):
        """无 agent_identity 时返回默认 ID."""
        b = NumericalDataBridge(data_dir=str(tmp_path))
        assert b._agent_id() == "numerical_data_bridge"

    def test_closed_loop_without_agent(self, tmp_path):
        """无 agent 时闭环仍执行 (状态为 skipped)."""
        b = NumericalDataBridge(data_dir=str(tmp_path))
        result = b.run_reverse_closed_loop("test_game", {"game_id": "test_game"})
        assert result["collaboration_count"] == 3
        for step in result["steps"]:
            assert step["record"]["status"] == "skipped_no_agent"


# ═══════════════════════════════════════════════════════════════
# 6. API 端点测试
# ═══════════════════════════════════════════════════════════════


class TestReverseCollaborationAPI:
    @pytest.fixture
    def client(self):
        from src.market_ops.workspace.app import app
        return TestClient(app)

    def test_reverse_loop_endpoint(self, client, tuning_payload):
        """测试反向闭环 API 端点."""
        resp = client.post(
            "/api/collaboration/reverse-loop",
            json={"game_id": "merge_game_001", "tuning_payload": tuning_payload},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["game_id"] == "merge_game_001"
        assert data["direction"] == "numerical_to_data_analyst"
        assert data["collaboration_count"] == 3

    def test_numerical_data_list_endpoint(self, client):
        """测试反向协同列表端点."""
        resp = client.get("/api/collaboration/numerical-data")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_numerical_data_stats_endpoint(self, client):
        """测试反向协同统计端点."""
        resp = client.get("/api/collaboration/numerical-data/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "direction" in data
        assert "total_collaborations" in data
        assert data["direction"] == "numerical_to_data_analyst"

    def test_numerical_data_detail_not_found(self, client):
        """测试不存在的协同记录返回 404."""
        resp = client.get("/api/collaboration/numerical-data/nonexistent-id")
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════
# 7. 数据转换测试
# ═══════════════════════════════════════════════════════════════


class TestDataConversion:
    def test_tuning_to_behavior_data(self, bridge, tuning_payload):
        """调优建议 → BehaviorData 转换."""
        behavior_data = bridge._tuning_to_behavior_data(tuning_payload)
        assert behavior_data.game_id == "merge_game_001"
        assert behavior_data.genre == "Merge"
        # target_metric=retention_d1, current_value=0.35 → retention_d1=0.35
        assert behavior_data.retention_d1 == 0.35

    def test_modeling_to_behavior_data(self, bridge, modeling_payload):
        """数值模型 → BehaviorData 转换."""
        behavior_data = bridge._modeling_to_behavior_data(modeling_payload)
        assert behavior_data.game_id == "merge_game_001"
        assert behavior_data.retention_d1 == 0.42

    def test_ab_test_to_behavior_data(self, bridge, ab_test_payload):
        """A/B 测试 → BehaviorData 转换."""
        behavior_data = bridge._ab_test_to_behavior_data(ab_test_payload)
        assert behavior_data.game_id == "merge_game_001"
        assert behavior_data.retention_d1 == 0.35

    def test_build_modeling_payload_from_tuning(self, bridge, tuning_payload):
        """从调优建议构建数值模型 payload."""
        payload = bridge._build_modeling_payload_from_tuning(tuning_payload, "game_002")
        assert payload["game_id"] == "game_002"
        assert payload["ltv"] == 0.45  # target_value
        assert payload["retention_d1"] == 0.35  # current_value

    def test_build_ab_test_payload_from_tuning(self, bridge, tuning_payload):
        """从调优建议构建 A/B 测试 payload."""
        payload = bridge._build_ab_test_payload_from_tuning(tuning_payload, "game_002")
        assert payload["game_id"] == "game_002"
        assert payload["test_id"].startswith("test-game_002-")
        assert "onboarding_reward" in payload["hypothesis"]
        assert "retention_d1" in payload["hypothesis"]
