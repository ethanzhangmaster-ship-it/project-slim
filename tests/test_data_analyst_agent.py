"""Data Analyst Agent 单元测试.

覆盖:
  1. 玩家行为分析
  2. 漏斗归因
  3. 留存预测
  4. 玩家分群
  5. BI 报表
  6. 异常检测
  7. 持久化
  8. API 端点
  9. 组织架构注册

设计原则:
  - 全部使用 tmp_path, 绝不污染 data/
  - 不依赖外部模块
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_PROJECT_ROOT / "src"))
sys.path.insert(0, str(_PROJECT_ROOT / "scripts"))

from src.market_ops.workspace.data_analyst_agent import (
    DataAnalystAgent,
    DataAnalystConfig,
    BehaviorData,
    BehaviorReport,
    FunnelAnalysis,
    RetentionPrediction,
    PlayerSegmentation,
    BIReport,
    AnomalyAlert,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def tmp_agent(tmp_path: Path) -> DataAnalystAgent:
    """使用临时目录的 Data Analyst Agent."""
    return DataAnalystAgent(data_dir=str(tmp_path / "data"))


@pytest.fixture
def merge_data() -> BehaviorData:
    """标准行为数据."""
    return BehaviorData(game_id="merge_game_001", genre="Merge")


# ═══════════════════════════════════════════════════════════════
# 1. 玩家行为分析
# ═══════════════════════════════════════════════════════════════


class TestBehaviorAnalysis:
    """玩家行为分析核心方法."""

    def test_analyze_behavior_returns_complete_report(
        self, tmp_agent: DataAnalystAgent, merge_data: BehaviorData
    ):
        """行为分析包含完整字段."""
        report = tmp_agent.analyze_behavior("merge_game_001", merge_data)

        assert isinstance(report, BehaviorReport)
        assert report.report_id.startswith("beh_")
        assert report.game_id == "merge_game_001"
        assert report.dau == merge_data.dau
        assert report.mau == merge_data.mau
        assert 0 <= report.stickiness <= 1
        assert 0 <= report.engagement_score <= 100
        assert len(report.top_actions) > 0
        assert len(report.insights) > 0

    def test_analyze_behavior_persists_to_jsonl(
        self, tmp_agent: DataAnalystAgent, merge_data: BehaviorData
    ):
        """行为分析持久化."""
        tmp_agent.analyze_behavior("merge_game_001", merge_data)

        reports = tmp_agent.list_behavior_reports()
        assert len(reports) == 1
        assert reports[0]["game_id"] == "merge_game_001"

    def test_analyze_behavior_writes_ceo_memory(
        self, tmp_agent: DataAnalystAgent, merge_data: BehaviorData
    ):
        """行为分析写入 CEO Memory."""
        tmp_agent.analyze_behavior("merge_game_001", merge_data)

        ceo_memory_path = Path(tmp_agent.data_dir) / "ceo" / "execution_memory.jsonl"
        assert ceo_memory_path.exists()

        records = [json.loads(l) for l in ceo_memory_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(records) == 1
        assert records[0]["domain"] == "data_analyst"
        assert records[0]["action_type"] == "player_behavior_analysis"
        assert records[0]["success"] is True

    def test_stickiness_calculation(
        self, tmp_agent: DataAnalystAgent
    ):
        """粘性比计算正确."""
        data = BehaviorData(game_id="g1", dau=10000, mau=50000)
        report = tmp_agent.analyze_behavior("g1", data)
        assert abs(report.stickiness - 0.2) < 0.01


# ═══════════════════════════════════════════════════════════════
# 2. 漏斗归因
# ═══════════════════════════════════════════════════════════════


class TestFunnelAnalysis:
    """漏斗归因分析."""

    def test_analyze_funnel_returns_complete(
        self, tmp_agent: DataAnalystAgent, merge_data: BehaviorData
    ):
        """漏斗分析包含完整字段."""
        funnel = tmp_agent.analyze_funnel("merge_game_001", merge_data)

        assert isinstance(funnel, FunnelAnalysis)
        assert funnel.funnel_id.startswith("funnel_")
        assert len(funnel.steps) == 5  # install→activate→tutorial→d7→pay
        assert 0 <= funnel.overall_conversion <= 1
        assert funnel.bottleneck_step != ""
        assert funnel.bottleneck_reason != ""
        assert len(funnel.recommendations) > 0

    def test_funnel_bottleneck_identification(
        self, tmp_agent: DataAnalystAgent
    ):
        """漏斗瓶颈识别 — 最大流失步骤."""
        data = BehaviorData(
            game_id="g1",
            funnel_data={"install": 1000, "activate": 900, "complete_tutorial": 200, "first_pay": 100},
        )
        funnel = tmp_agent.analyze_funnel("g1", data)
        # complete_tutorial 流失率最高 (900→200, 78%)
        assert funnel.bottleneck_step == "complete_tutorial"

    def test_funnel_persists(
        self, tmp_agent: DataAnalystAgent, merge_data: BehaviorData
    ):
        """漏斗持久化."""
        tmp_agent.analyze_funnel("merge_game_001", merge_data)
        funnels = tmp_agent.list_funnels()
        assert len(funnels) == 1


# ═══════════════════════════════════════════════════════════════
# 3. 留存预测
# ═══════════════════════════════════════════════════════════════


class TestRetentionPrediction:
    """留存预测."""

    def test_predict_retention_returns_complete(
        self, tmp_agent: DataAnalystAgent, merge_data: BehaviorData
    ):
        """留存预测包含完整字段."""
        pred = tmp_agent.predict_retention("merge_game_001", merge_data)

        assert isinstance(pred, RetentionPrediction)
        assert pred.prediction_id.startswith("pred_")
        assert pred.historical_d1 == merge_data.retention_d1
        assert pred.historical_d30 == merge_data.retention_d30
        assert pred.predicted_d60 > 0
        assert pred.predicted_d90 > 0
        assert pred.predicted_d180 > 0
        # D180 < D90 < D60 (衰减)
        assert pred.predicted_d180 < pred.predicted_d90 < pred.predicted_d60
        assert pred.decay_model == "power_law"
        assert 0 <= pred.confidence <= 1
        assert pred.trend in ("improving", "stable", "declining")

    def test_retention_trend_improving(
        self, tmp_agent: DataAnalystAgent
    ):
        """高 D7/D1 比例 → improving."""
        data = BehaviorData(game_id="g1", retention_d1=0.50, retention_d7=0.25)
        pred = tmp_agent.predict_retention("g1", data)
        assert pred.trend == "improving"
        assert pred.confidence == 0.85

    def test_retention_trend_declining(
        self, tmp_agent: DataAnalystAgent
    ):
        """低 D7/D1 比例 → declining."""
        data = BehaviorData(game_id="g1", retention_d1=0.50, retention_d7=0.10)
        pred = tmp_agent.predict_retention("g1", data)
        assert pred.trend == "declining"
        assert pred.confidence == 0.65


# ═══════════════════════════════════════════════════════════════
# 4. 玩家分群
# ═══════════════════════════════════════════════════════════════


class TestPlayerSegmentation:
    """玩家分群."""

    def test_segment_players_returns_complete(
        self, tmp_agent: DataAnalystAgent, merge_data: BehaviorData
    ):
        """分群包含完整字段."""
        seg = tmp_agent.segment_players("merge_game_001", merge_data)

        assert isinstance(seg, PlayerSegmentation)
        assert seg.segmentation_id.startswith("seg_")
        assert seg.total_users == merge_data.mau
        assert len(seg.segments) > 0
        assert seg.segmentation_method == "rfm"
        assert seg.key_insight != ""

    def test_segment_shares_sum_approximately(
        self, tmp_agent: DataAnalystAgent, merge_data: BehaviorData
    ):
        """分群占比总和约等于 1."""
        seg = tmp_agent.segment_players("g1", merge_data)
        total_share = sum(s["user_share"] for s in seg.segments)
        assert abs(total_share - 1.0) < 0.1  # 允许 10% 误差（因 min_segment_size 过滤）

    def test_segment_has_recommended_action(
        self, tmp_agent: DataAnalystAgent, merge_data: BehaviorData
    ):
        """每个分群都有推荐动作."""
        seg = tmp_agent.segment_players("g1", merge_data)
        for s in seg.segments:
            assert s["recommended_action"] != ""


# ═══════════════════════════════════════════════════════════════
# 5. BI 报表
# ═══════════════════════════════════════════════════════════════


class TestBIReport:
    """BI 报表."""

    def test_generate_bi_report_returns_complete(
        self, tmp_agent: DataAnalystAgent, merge_data: BehaviorData
    ):
        """BI 报表包含完整字段."""
        report = tmp_agent.generate_bi_report("merge_game_001", merge_data)

        assert isinstance(report, BIReport)
        assert report.report_id.startswith("bi_")
        assert report.game_id == "merge_game_001"
        assert "dau" in report.kpi_summary
        assert "d1_retention" in report.growth_metrics
        assert "arpu" in report.revenue_metrics
        assert "stickiness" in report.engagement_metrics
        assert report.health_status in ("HEALTHY", "ATTENTION", "CRITICAL")
        assert 0 <= report.health_score <= 100
        assert len(report.highlights) > 0
        assert len(report.risks) > 0

    def test_bi_report_health_healthy(
        self, tmp_agent: DataAnalystAgent
    ):
        """高指标 → HEALTHY."""
        data = BehaviorData(
            game_id="g1",
            dau=20000, mau=80000,
            retention_d1=0.50, retention_d30=0.15,
            payer_count=1200,  # 6% 付费率
        )
        report = tmp_agent.generate_bi_report("g1", data)
        assert report.health_status == "HEALTHY"
        assert report.health_score >= 75

    def test_bi_report_health_critical(
        self, tmp_agent: DataAnalystAgent
    ):
        """低指标 → CRITICAL."""
        data = BehaviorData(
            game_id="g1",
            dau=5000, mau=80000,
            retention_d1=0.20, retention_d30=0.03,
            payer_count=100,  # 2% 付费率
        )
        report = tmp_agent.generate_bi_report("g1", data)
        assert report.health_status == "CRITICAL"

    def test_bi_report_persists(
        self, tmp_agent: DataAnalystAgent, merge_data: BehaviorData
    ):
        """BI 报表持久化."""
        tmp_agent.generate_bi_report("g1", merge_data)
        reports = tmp_agent.list_bi_reports()
        assert len(reports) == 1


# ═══════════════════════════════════════════════════════════════
# 6. 异常检测
# ═══════════════════════════════════════════════════════════════


class TestAnomalyDetection:
    """异常检测."""

    def test_detect_anomalies_returns_list(
        self, tmp_agent: DataAnalystAgent, merge_data: BehaviorData
    ):
        """异常检测返回列表."""
        alerts = tmp_agent.detect_anomalies("g1", merge_data)
        assert isinstance(alerts, list)

    def test_anomaly_triggered_on_low_metrics(
        self, tmp_agent: DataAnalystAgent
    ):
        """低指标触发告警."""
        data = BehaviorData(
            game_id="g1",
            retention_d1=0.20,  # 低于基准 0.45 超过 30%
            retention_d30=0.05,  # 低于基准 0.12 超过 30%
            dau=5000, mau=80000,  # 粘性低
            avg_session_duration=200.0,  # 低于基准 480 超过 30%
        )
        alerts = tmp_agent.detect_anomalies("g1", data)
        assert len(alerts) > 0
        # 至少有一个 critical
        assert any(a.severity == "critical" for a in alerts)

    def test_no_anomaly_on_healthy_metrics(
        self, tmp_agent: DataAnalystAgent
    ):
        """健康指标不触发告警."""
        data = BehaviorData(
            game_id="g1",
            retention_d1=0.50,  # 超过基准
            retention_d30=0.15,
            dau=20000, mau=80000,
            avg_session_duration=500.0,
        )
        alerts = tmp_agent.detect_anomalies("g1", data)
        assert len(alerts) == 0


# ═══════════════════════════════════════════════════════════════
# 7. 统计概览
# ═══════════════════════════════════════════════════════════════


class TestStats:
    """统计方法."""

    def test_get_stats_returns_complete(
        self, tmp_agent: DataAnalystAgent, merge_data: BehaviorData
    ):
        """统计概览完整."""
        tmp_agent.analyze_behavior("g1", merge_data)
        tmp_agent.generate_bi_report("g1", merge_data)
        tmp_agent.detect_anomalies("g1", merge_data)

        stats = tmp_agent.get_stats()
        assert stats["total_behavior_reports"] == 1
        assert stats["total_bi_reports"] == 1
        assert "health_distribution" in stats
        assert "severity_distribution" in stats


# ═══════════════════════════════════════════════════════════════
# 8. 品类模板
# ═══════════════════════════════════════════════════════════════


class TestGenreTemplates:
    """品类模板."""

    @pytest.mark.parametrize("genre", ["Merge", "Match3", "Simulation"])
    def test_genre_template_works(
        self, tmp_agent: DataAnalystAgent, genre: str
    ):
        """每个品类模板都能正常工作."""
        data = BehaviorData(game_id="g1", genre=genre)
        report = tmp_agent.analyze_behavior("g1", data)
        assert report.engagement_score >= 0


# ═══════════════════════════════════════════════════════════════
# 9. API 端点
# ═══════════════════════════════════════════════════════════════


class TestDataAnalystAPI:
    """Data Analyst API 端点."""

    @pytest.fixture
    def client(self, monkeypatch, tmp_path: Path):
        """临时 client."""
        # 使用临时目录覆盖 _PROJECT_ROOT (monkeypatch 自动恢复, 避免污染其他测试)
        import src.market_ops.workspace.app as app_module
        monkeypatch.setattr(app_module, "_PROJECT_ROOT", tmp_path)
        # 重置单例
        if hasattr(app_module._get_data_analyst_agent, "_instance"):
            del app_module._get_data_analyst_agent._instance
        from src.market_ops.workspace.app import app
        return TestClient(app)

    def test_behavior_endpoint(self, client):
        """行为分析端点."""
        resp = client.post("/api/data-analyst/behavior", json={"game_id": "g1"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["game_id"] == "g1"
        assert "engagement_score" in data

    def test_funnel_endpoint(self, client):
        """漏斗分析端点."""
        resp = client.post("/api/data-analyst/funnel", json={"game_id": "g1"})
        assert resp.status_code == 200
        data = resp.json()
        assert "bottleneck_step" in data

    def test_bi_report_endpoint(self, client):
        """BI 报表端点."""
        resp = client.post("/api/data-analyst/bi-report", json={"game_id": "g1"})
        assert resp.status_code == 200
        data = resp.json()
        assert "health_status" in data

    def test_anomalies_endpoint(self, client):
        """异常检测端点."""
        resp = client.post("/api/data-analyst/anomalies", json={"game_id": "g1"})
        assert resp.status_code == 200
        data = resp.json()
        assert "alert_count" in data
        assert "alerts" in data

    def test_stats_endpoint(self, client):
        """统计端点."""
        client.post("/api/data-analyst/behavior", json={"game_id": "g1"})
        resp = client.get("/api/data-analyst/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_behavior_reports" in data


# ═══════════════════════════════════════════════════════════════
# 10. 组织架构注册
# ═══════════════════════════════════════════════════════════════


class TestDataAnalystRegistry:
    """组织架构注册."""

    def test_data_analyst_registered_in_organization(self):
        """Data Analyst 注册在默认组织中."""
        from src.market_ops.creative_vision_runtime.growth_runtime.agent.communication import (
            create_default_organization,
            AgentRole,
        )
        registry = create_default_organization()
        all_records = registry.get_all()
        roles = [r.identity.role for r in all_records]
        assert AgentRole.DATA_ANALYST in roles

    def test_data_analyst_identity_has_capabilities(self):
        """Data Analyst 身份包含能力."""
        from src.market_ops.creative_vision_runtime.growth_runtime.agent.communication import (
            create_data_analyst_agent_identity,
        )
        identity = create_data_analyst_agent_identity()
        assert "player_behavior_analysis" in identity.capabilities
        assert "funnel_attribution" in identity.capabilities
        assert "bi_reporting" in identity.capabilities
