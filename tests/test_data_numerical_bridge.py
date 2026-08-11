"""DataNumericalBridge 测试 — Data Analyst → Numerical Designer 跨 Agent 协同.

测试覆盖:
  1. 数据转换: BehaviorData → GameMetrics
  2. 单事件处理: behavior_analyzed / retention_predicted / players_segmented / anomalies_detected
  3. 完整分析闭环: run_analysis_closed_loop
  4. MessageBus 订阅: register / _handle_message
  5. 持久化与查询: list_collaborations / get_collaboration / get_stats
  6. CEO Memory 回流
  7. API 端点
  8. 边界场景: 无 numerical_agent / 无 message_bus
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.market_ops.workspace.data_numerical_bridge import DataNumericalBridge
from src.market_ops.workspace.numerical_designer_agent import (
    GameMetrics,
    NumericalDesignerAgent,
    NumericalModel,
    RetentionCurveModel,
    PayConversionFunnel,
    TuningRecommendation,
    ABTestDesign,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def numerical_agent(tmp_path: Path) -> NumericalDesignerAgent:
    """创建 Numerical Designer Agent (临时目录, 无外部依赖)."""
    return NumericalDesignerAgent(
        data_dir=str(tmp_path),
        profitability_engine=None,
    )


@pytest.fixture
def bridge(tmp_path: Path, numerical_agent: NumericalDesignerAgent) -> DataNumericalBridge:
    """创建 DataNumericalBridge (注入 numerical_agent, 无 message_bus)."""
    return DataNumericalBridge(
        data_dir=str(tmp_path),
        numerical_agent=numerical_agent,
    )


@pytest.fixture
def behavior_payload() -> dict:
    """行为分析事件 payload."""
    return {
        "game_id": "merge_game_001",
        "genre": "Merge",
        "dau": 12000,
        "mau": 96000,
        "revenue_total": 6000.0,
        "payer_count": 720,
        "retention_d1": 0.45,
        "retention_d7": 0.20,
        "retention_d30": 0.12,
    }


@pytest.fixture
def retention_payload() -> dict:
    """留存预测事件 payload."""
    return {
        "game_id": "merge_game_001",
        "genre": "Merge",
        "dau": 12000,
        "mau": 96000,
        "revenue_total": 6000.0,
        "payer_count": 720,
        "historical_d1": 0.45,
        "historical_d7": 0.20,
        "historical_d30": 0.12,
        "predicted_d60": 0.08,
        "predicted_d90": 0.06,
    }


@pytest.fixture
def segmentation_payload() -> dict:
    """玩家分群事件 payload."""
    return {
        "game_id": "merge_game_001",
        "genre": "Merge",
        "dau": 12000,
        "mau": 96000,
        "revenue_total": 6000.0,
        "payer_count": 720,
        "total_users": 96000,
        "segmentation_method": "rfm",
        "key_insight": "高价值玩家占比偏低",
    }


@pytest.fixture
def anomaly_payload() -> dict:
    """异常检测事件 payload (含 1 个 critical)."""
    return {
        "game_id": "merge_game_001",
        "genre": "Merge",
        "dau": 12000,
        "mau": 96000,
        "revenue_total": 6000.0,
        "payer_count": 720,
        "retention_d1": 0.45,
        "retention_d7": 0.20,
        "retention_d30": 0.12,
        "anomalies": [
            {
                "alert_id": "an_001",
                "metric_name": "retention_d7",
                "current_value": 0.12,
                "expected_value": 0.20,
                "deviation_pct": -0.40,
                "severity": "critical",
            },
            {
                "alert_id": "an_002",
                "metric_name": "arpu",
                "current_value": 0.35,
                "expected_value": 0.50,
                "deviation_pct": -0.30,
                "severity": "warning",
            },
        ],
    }


# ═══════════════════════════════════════════════════════════════
# 1. 数据转换测试
# ═══════════════════════════════════════════════════════════════


class TestDataConversion:
    """BehaviorData → GameMetrics 数据转换."""

    def test_behavior_to_metrics_computes_arpu(self, bridge: DataNumericalBridge):
        """ARPU = revenue_total / dau."""
        metrics = bridge._behavior_to_game_metrics({
            "dau": 10000,
            "revenue_total": 5000.0,
            "payer_count": 500,
        })
        assert metrics["arpu"] == 0.5

    def test_behavior_to_metrics_computes_arppu(self, bridge: DataNumericalBridge):
        """ARPPU = revenue_total / payer_count."""
        metrics = bridge._behavior_to_game_metrics({
            "dau": 10000,
            "revenue_total": 5000.0,
            "payer_count": 500,
        })
        assert metrics["arppu"] == 10.0

    def test_behavior_to_metrics_computes_payer_rate(self, bridge: DataNumericalBridge):
        """payer_rate = payer_count / dau."""
        metrics = bridge._behavior_to_game_metrics({
            "dau": 10000,
            "payer_count": 600,
        })
        assert metrics["payer_rate"] == 0.06

    def test_behavior_to_metrics_mau_to_total_users(self, bridge: DataNumericalBridge):
        """total_users = mau."""
        metrics = bridge._behavior_to_game_metrics({
            "dau": 10000,
            "mau": 80000,
        })
        assert metrics["total_users"] == 80000

    def test_behavior_to_metrics_estimates_spend(self, bridge: DataNumericalBridge):
        """spend = revenue_total * 0.6."""
        metrics = bridge._behavior_to_game_metrics({
            "dau": 10000,
            "revenue_total": 5000.0,
        })
        assert metrics["spend"] == 3000.0

    def test_behavior_to_metrics_passes_retention(self, bridge: DataNumericalBridge):
        """留存率正确传递."""
        metrics = bridge._behavior_to_game_metrics({
            "retention_d1": 0.42,
            "retention_d7": 0.18,
            "retention_d30": 0.10,
        })
        assert metrics["retention_d1"] == 0.42
        assert metrics["retention_d7"] == 0.18
        assert metrics["retention_d30"] == 0.10

    def test_behavior_to_metrics_handles_historical_retention(
        self, bridge: DataNumericalBridge
    ):
        """historical_d1/d7/d30 作为 fallback."""
        metrics = bridge._behavior_to_game_metrics({
            "historical_d1": 0.40,
            "historical_d7": 0.16,
            "historical_d30": 0.08,
        })
        assert metrics["retention_d1"] == 0.40
        assert metrics["retention_d7"] == 0.16


# ═══════════════════════════════════════════════════════════════
# 2. 单事件处理测试
# ═══════════════════════════════════════════════════════════════


class TestBehaviorAnalysisHandler:
    """behavior_analyzed → model_numerical."""

    def test_returns_collaboration_record(
        self, bridge: DataNumericalBridge, behavior_payload: dict
    ):
        """返回完整协同记录."""
        result = bridge.process_behavior_analysis(behavior_payload)

        assert result["collaboration_id"].startswith("colab-")
        assert result["trigger_event"] == "behavior_analyzed"
        assert result["trigger_source"] == "data_analyst"
        assert result["target_method"] == "model_numerical"
        assert result["target_agent"] == "numerical"
        assert result["game_id"] == "merge_game_001"
        assert result["status"] == "success"
        assert "numerical_model" in result["numerical_output"]
        assert "model_id" in result["numerical_output"]["numerical_model"]

    def test_persists_to_jsonl(
        self, bridge: DataNumericalBridge, behavior_payload: dict, tmp_path: Path
    ):
        """协同记录写入 JSONL."""
        bridge.process_behavior_analysis(behavior_payload)

        jsonl_path = tmp_path / "collaboration" / "data_numerical.jsonl"
        assert jsonl_path.exists()
        lines = [l for l in jsonl_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["trigger_event"] == "behavior_analyzed"

    def test_writes_ceo_memory(
        self, bridge: DataNumericalBridge, behavior_payload: dict, tmp_path: Path
    ):
        """协同结果回流 CEO Memory.

        注: NumericalDesignerAgent 自身也会写 CEO memory (domain="numerical"),
        bridge 额外写一条 cross_agent_collaboration 记录 (domain="data_numerical_bridge").
        """
        bridge.process_behavior_analysis(behavior_payload)

        ceo_path = tmp_path / "ceo" / "execution_memory.jsonl"
        assert ceo_path.exists()
        lines = [l for l in ceo_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        # 2 条: numerical agent 自身 1 条 + bridge 1 条
        assert len(lines) == 2
        records = [json.loads(l) for l in lines]
        domains = {r["domain"] for r in records}
        assert "numerical" in domains
        assert "data_numerical_bridge" in domains

        bridge_records = [r for r in records if r["domain"] == "data_numerical_bridge"]
        assert len(bridge_records) == 1
        assert bridge_records[0]["strategy_type"] == "cross_agent_collaboration"
        assert bridge_records[0]["success"] is True


class TestRetentionPredictionHandler:
    """retention_predicted → model_retention."""

    def test_returns_retention_curve(
        self, bridge: DataNumericalBridge, retention_payload: dict
    ):
        """返回留存曲线模型."""
        result = bridge.process_retention_prediction(retention_payload)

        assert result["trigger_event"] == "retention_predicted"
        assert result["target_method"] == "model_retention"
        assert result["status"] == "success"
        assert "retention_curve" in result["numerical_output"]
        assert "curve_id" in result["numerical_output"]["retention_curve"]


class TestPlayerSegmentationHandler:
    """players_segmented → analyze_pay_conversion."""

    def test_returns_pay_conversion(
        self, bridge: DataNumericalBridge, segmentation_payload: dict
    ):
        """返回付费转化漏斗."""
        result = bridge.process_player_segmentation(segmentation_payload)

        assert result["trigger_event"] == "players_segmented"
        assert result["target_method"] == "analyze_pay_conversion"
        assert result["status"] == "success"
        assert "pay_conversion" in result["numerical_output"]
        assert "funnel_id" in result["numerical_output"]["pay_conversion"]


class TestAnomalyAlertsHandler:
    """anomalies_detected → recommend_tuning (+design_ab_test if critical)."""

    def test_returns_tuning_recommendations(
        self, bridge: DataNumericalBridge, anomaly_payload: dict
    ):
        """返回调优建议."""
        result = bridge.process_anomaly_alerts(anomaly_payload)

        assert result["trigger_event"] == "anomalies_detected"
        assert result["status"] == "success"
        assert "tuning_recommendations" in result["numerical_output"]

    def test_triggers_ab_test_for_critical(
        self, bridge: DataNumericalBridge, anomaly_payload: dict
    ):
        """critical 异常触发 A/B 测试设计."""
        result = bridge.process_anomaly_alerts(anomaly_payload)

        assert "+design_ab_test" in result["target_method"]
        assert "ab_test" in result["numerical_output"]
        assert "test_id" in result["numerical_output"]["ab_test"]

    def test_no_ab_test_without_critical(
        self, bridge: DataNumericalBridge
    ):
        """无 critical 异常不触发 A/B 测试."""
        payload = {
            "game_id": "g1",
            "dau": 10000,
            "mau": 80000,
            "revenue_total": 5000.0,
            "payer_count": 600,
            "anomalies": [
                {"metric_name": "arpu", "severity": "warning"},
            ],
        }
        result = bridge.process_anomaly_alerts(payload)

        assert "+design_ab_test" not in result["target_method"]
        assert "ab_test" not in result["numerical_output"]


# ═══════════════════════════════════════════════════════════════
# 3. 完整分析闭环测试
# ═══════════════════════════════════════════════════════════════


class TestAnalysisClosedLoop:
    """run_analysis_closed_loop 端到端测试."""

    def test_returns_loop_summary(
        self, bridge: DataNumericalBridge, behavior_payload: dict
    ):
        """返回闭环汇总."""
        result = bridge.run_analysis_closed_loop(
            "merge_game_001", behavior_payload
        )

        assert result["loop_id"].startswith("loop-merge_game_001-")
        assert result["game_id"] == "merge_game_001"
        assert result["collaboration_count"] == 4
        assert len(result["steps"]) == 4

    def test_four_steps_in_order(
        self, bridge: DataNumericalBridge, behavior_payload: dict
    ):
        """4 步协同按顺序执行."""
        result = bridge.run_analysis_closed_loop(
            "g1", behavior_payload
        )

        steps = result["steps"]
        assert steps[0]["trigger_event"] == "behavior_analyzed"
        assert steps[0]["target_method"] == "model_numerical"
        assert steps[1]["trigger_event"] == "retention_predicted"
        assert steps[1]["target_method"] == "model_retention"
        assert steps[2]["trigger_event"] == "players_segmented"
        assert steps[2]["target_method"] == "analyze_pay_conversion"
        assert steps[3]["trigger_event"] == "anomalies_detected"
        assert "recommend_tuning" in steps[3]["target_method"]

    def test_all_steps_succeed(
        self, bridge: DataNumericalBridge, behavior_payload: dict
    ):
        """所有步骤状态为 success."""
        result = bridge.run_analysis_closed_loop(
            "g1", behavior_payload
        )

        for step in result["steps"]:
            assert step["status"] == "success"

    def test_persists_audit_log(
        self, bridge: DataNumericalBridge, behavior_payload: dict, tmp_path: Path
    ):
        """闭环审计日志写入."""
        bridge.run_analysis_closed_loop("g1", behavior_payload)

        audit_path = tmp_path / "collaboration" / "data_numerical_audit.jsonl"
        assert audit_path.exists()
        lines = [l for l in audit_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["audit_type"] == "closed_loop"
        assert record["collaboration_count"] == 4

    def test_writes_four_ceo_memory_records(
        self, bridge: DataNumericalBridge, behavior_payload: dict, tmp_path: Path
    ):
        """4 步闭环各写 1 条 bridge CEO Memory 记录 (共 4 条 bridge 记录).

        注: numerical agent 自身也写 4 条 (domain="numerical"), 总计 8 条.
        """
        bridge.run_analysis_closed_loop("g1", behavior_payload)

        ceo_path = tmp_path / "ceo" / "execution_memory.jsonl"
        lines = [l for l in ceo_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        # 8 条: 4 步 × (numerical agent 1 条 + bridge 1 条)
        assert len(lines) == 8
        records = [json.loads(l) for l in lines]
        bridge_records = [r for r in records if r["domain"] == "data_numerical_bridge"]
        assert len(bridge_records) == 4


# ═══════════════════════════════════════════════════════════════
# 4. MessageBus 订阅测试
# ═══════════════════════════════════════════════════════════════


class TestMessageBusSubscription:
    """MessageBus 注册与消息处理."""

    def test_register_returns_false_without_bus(self, tmp_path: Path):
        """无 message_bus 时 register 返回 False."""
        bridge = DataNumericalBridge(data_dir=str(tmp_path))
        assert bridge.register() is False

    def test_register_with_mock_bus(self, tmp_path: Path):
        """注入 mock bus 时 register 成功."""
        mock_bus = MagicMock()
        bridge = DataNumericalBridge(
            data_dir=str(tmp_path),
            message_bus=mock_bus,
            numerical_agent=NumericalDesignerAgent(data_dir=str(tmp_path), profitability_engine=None),
        )
        assert bridge.register() is True
        mock_bus.register_handler_fn.assert_called_once()

    def test_handle_message_filters_non_data_analyst(
        self, bridge: DataNumericalBridge
    ):
        """非 data_analyst 前缀的消息被忽略."""
        mock_msg = MagicMock()
        mock_msg.subject = "liveops:churn_alert"
        result = bridge._handle_message(mock_msg)
        assert result is None

    def test_handle_message_routes_behavior_analyzed(
        self, bridge: DataNumericalBridge, behavior_payload: dict
    ):
        """behavior_analyzed 消息路由到 process_behavior_analysis."""
        mock_msg = MagicMock()
        mock_msg.subject = "data_analyst:behavior_analyzed"
        mock_msg.body = behavior_payload

        bridge._handle_message(mock_msg)

        records = bridge.list_collaborations()
        assert len(records) == 1
        assert records[0]["trigger_event"] == "behavior_analyzed"


# ═══════════════════════════════════════════════════════════════
# 5. 查询 API 测试
# ═══════════════════════════════════════════════════════════════


class TestQueryAPI:
    """协同记录查询."""

    def test_list_collaborations_empty(self, bridge: DataNumericalBridge):
        """无记录时返回空列表."""
        assert bridge.list_collaborations() == []

    def test_list_collaborations_filter_by_game(
        self, bridge: DataNumericalBridge, behavior_payload: dict
    ):
        """按 game_id 过滤."""
        bridge.process_behavior_analysis({**behavior_payload, "game_id": "g1"})
        bridge.process_behavior_analysis({**behavior_payload, "game_id": "g2"})

        g1_records = bridge.list_collaborations(game_id="g1")
        assert len(g1_records) == 1
        assert g1_records[0]["game_id"] == "g1"

    def test_get_collaboration_by_id(
        self, bridge: DataNumericalBridge, behavior_payload: dict
    ):
        """按 ID 查询协同记录."""
        result = bridge.process_behavior_analysis(behavior_payload)
        colab_id = result["collaboration_id"]

        found = bridge.get_collaboration(colab_id)
        assert found is not None
        assert found["collaboration_id"] == colab_id

    def test_get_collaboration_not_found(self, bridge: DataNumericalBridge):
        """查询不存在的 ID 返回 None."""
        assert bridge.get_collaboration("nonexistent") is None

    def test_get_stats(
        self, bridge: DataNumericalBridge, behavior_payload: dict
    ):
        """统计概览."""
        bridge.process_behavior_analysis(behavior_payload)
        bridge.process_retention_prediction({
            **behavior_payload,
            "historical_d1": 0.45,
        })

        stats = bridge.get_stats()
        assert stats["total_collaborations"] == 2
        assert "behavior_analyzed" in stats["by_trigger_event"]
        assert "retention_predicted" in stats["by_trigger_event"]
        assert stats["by_status"]["success"] == 2


# ═══════════════════════════════════════════════════════════════
# 6. 边界场景测试
# ═══════════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界场景."""

    def test_no_numerical_agent_returns_skipped(self, tmp_path: Path):
        """无 numerical_agent 时状态为 skipped_no_agent."""
        bridge = DataNumericalBridge(data_dir=str(tmp_path))
        result = bridge.process_behavior_analysis({"game_id": "g1", "dau": 100})

        assert result["status"] == "skipped_no_agent"
        assert result["numerical_output"] == {}

    def test_no_numerical_agent_closed_loop(
        self, tmp_path: Path
    ):
        """无 numerical_agent 时闭环仍执行 (4 步全部 skipped)."""
        bridge = DataNumericalBridge(data_dir=str(tmp_path))
        result = bridge.run_analysis_closed_loop("g1", {"dau": 100})

        assert result["collaboration_count"] == 4
        for step in result["steps"]:
            assert step["status"] == "skipped_no_agent"

    def test_list_audit_logs_empty(self, bridge: DataNumericalBridge):
        """无审计日志时返回空列表."""
        assert bridge.list_audit_logs() == []


# ═══════════════════════════════════════════════════════════════
# 7. API 端点测试
# ═══════════════════════════════════════════════════════════════


class TestCollaborationAPI:
    """协同 API 端点测试."""

    def test_analysis_loop_endpoint(self):
        """POST /api/collaboration/analysis-loop 端点."""
        from fastapi.testclient import TestClient
        from src.market_ops.workspace.app import app

        client = TestClient(app)
        resp = client.post("/api/collaboration/analysis-loop", json={
            "game_id": "test_api_game",
            "dau": 8000,
            "mau": 64000,
            "revenue_total": 4000.0,
            "payer_count": 400,
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["game_id"] == "test_api_game"
        assert data["collaboration_count"] == 4
        assert len(data["steps"]) == 4

    def test_list_collaborations_endpoint(self):
        """GET /api/collaboration/data-numerical 端点."""
        from fastapi.testclient import TestClient
        from src.market_ops.workspace.app import app

        client = TestClient(app)
        # 先触发一次闭环
        client.post("/api/collaboration/analysis-loop", json={
            "game_id": "test_list_game",
        })

        resp = client.get("/api/collaboration/data-numerical", params={
            "game_id": "test_list_game",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 4

    def test_stats_endpoint(self):
        """GET /api/collaboration/data-numerical/stats 端点."""
        from fastapi.testclient import TestClient
        from src.market_ops.workspace.app import app

        client = TestClient(app)
        resp = client.get("/api/collaboration/data-numerical/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_collaborations" in data
        assert "by_trigger_event" in data
        assert "by_status" in data

    def test_collaboration_detail_not_found(self):
        """GET /api/collaboration/data-numerical/{id} 404."""
        from fastapi.testclient import TestClient
        from src.market_ops.workspace.app import app

        client = TestClient(app)
        resp = client.get("/api/collaboration/data-numerical/nonexistent-id")
        assert resp.status_code == 404
