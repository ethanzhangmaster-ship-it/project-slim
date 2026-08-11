"""Market Intelligence Agent 单元测试.

测试覆盖:
  1. 数据模型 (MarketAnalysisResult, MarketReport) 序列化/反序列化
  2. Agent 初始化
  3. 各方法调用（返回正确数据结构）
  4. 单例模式
  5. API 端点测试 (TestClient)
  6. 统计信息
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# 确保项目根目录在 path 中
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.market_ops.workspace.market_intelligence_agent import (
    MarketAnalysisResult,
    MarketIntelligenceAgent,
    MarketIntelligenceConfig,
    MarketReport,
    get_market_intelligence_agent,
    reset_market_intelligence_agent,
)


# ── Fixtures ─────────────────────────────────────────────


@pytest.fixture
def agent(tmp_path: Path) -> MarketIntelligenceAgent:
    """创建使用临时数据目录的 agent 实例."""
    return MarketIntelligenceAgent(data_dir=str(tmp_path / "data"))


@pytest.fixture(autouse=True)
def _reset_singleton():
    """每个测试前后重置单例，避免状态污染."""
    reset_market_intelligence_agent()
    yield
    reset_market_intelligence_agent()


# ═══════════════════════════════════════════════════════════════
# 1. 数据模型序列化/反序列化
# ═══════════════════════════════════════════════════════════════


class TestDataModels:
    """数据模型序列化/反序列化测试."""

    def test_market_analysis_result_to_dict(self) -> None:
        """MarketAnalysisResult.to_dict() 返回完整字典."""
        result = MarketAnalysisResult(
            analysis_id="mkt_test001",
            trends=[{"signal_id": "t1", "category": "sort"}],
            competitors=[{"game_id": "c1", "name": "Game A"}],
            creative_signals=[{"signal_id": "s1", "dimension": "hook"}],
            heatmap={"cells": [], "hot_categories": ["sort"]},
            opportunities=[{"opportunity_id": "o1", "score": 80.0}],
            summary="测试摘要",
            top_opportunity="Sort + 3d Sort Physics",
            exploding_trend_count=3,
            rising_trend_count=5,
            top_threat="Goods Sort",
            created_at="2026-08-10T00:00:00+00:00",
        )
        d = result.to_dict()

        assert d["analysis_id"] == "mkt_test001"
        assert len(d["trends"]) == 1
        assert len(d["competitors"]) == 1
        assert len(d["creative_signals"]) == 1
        assert d["heatmap"]["hot_categories"] == ["sort"]
        assert len(d["opportunities"]) == 1
        assert d["summary"] == "测试摘要"
        assert d["top_opportunity"] == "Sort + 3d Sort Physics"
        assert d["exploding_trend_count"] == 3
        assert d["rising_trend_count"] == 5
        assert d["top_threat"] == "Goods Sort"
        assert d["created_at"] == "2026-08-10T00:00:00+00:00"

    def test_market_analysis_result_json_roundtrip(self) -> None:
        """MarketAnalysisResult 可 JSON 序列化/反序列化."""
        result = MarketAnalysisResult(
            analysis_id="mkt_roundtrip",
            trends=[{"category": "merge"}],
            competitors=[{"name": "Merge Mansion"}],
            creative_signals=[{"dimension": "visual"}],
            heatmap={"cells": [], "hot_categories": []},
            opportunities=[{"score": 75.5}],
            summary="roundtrip 测试",
            top_opportunity="test",
            exploding_trend_count=1,
            rising_trend_count=2,
            top_threat="test_threat",
            created_at="2026-01-01T00:00:00+00:00",
        )
        serialized = json.dumps(result.to_dict(), ensure_ascii=False)
        deserialized = json.loads(serialized)

        assert deserialized["analysis_id"] == "mkt_roundtrip"
        assert deserialized["summary"] == "roundtrip 测试"

    def test_market_report_to_dict(self) -> None:
        """MarketReport.to_dict() 返回完整字典."""
        report = MarketReport(
            report_id="mkt_report_001",
            period="2026-W32",
            executive_summary="执行摘要",
            market_overview={"total_trends": 8},
            trend_highlights=[{"category": "sort"}],
            competitive_landscape={"tier_1_count": 3},
            creative_insights=[{"dimension": "hook"}],
            opportunity_pipeline=[{"score": 90.0}],
            recommendations=["建议 1", "建议 2"],
            risk_alerts=["风险 1"],
            created_at="2026-08-10T00:00:00+00:00",
        )
        d = report.to_dict()

        assert d["report_id"] == "mkt_report_001"
        assert d["period"] == "2026-W32"
        assert d["executive_summary"] == "执行摘要"
        assert d["market_overview"]["total_trends"] == 8
        assert len(d["trend_highlights"]) == 1
        assert d["competitive_landscape"]["tier_1_count"] == 3
        assert len(d["creative_insights"]) == 1
        assert len(d["opportunity_pipeline"]) == 1
        assert len(d["recommendations"]) == 2
        assert len(d["risk_alerts"]) == 1

    def test_market_report_json_roundtrip(self) -> None:
        """MarketReport 可 JSON 序列化/反序列化."""
        report = MarketReport(
            report_id="mkt_report_rt",
            period="2026-W01",
            executive_summary="RT",
            market_overview={},
            trend_highlights=[],
            competitive_landscape={},
            creative_insights=[],
            opportunity_pipeline=[],
            recommendations=["rec"],
            risk_alerts=["alert"],
            created_at="2026-01-01T00:00:00+00:00",
        )
        serialized = json.dumps(report.to_dict(), ensure_ascii=False)
        deserialized = json.loads(serialized)

        assert deserialized["report_id"] == "mkt_report_rt"
        assert deserialized["recommendations"] == ["rec"]


# ═══════════════════════════════════════════════════════════════
# 2. Agent 初始化
# ═══════════════════════════════════════════════════════════════


class TestAgentInit:
    """Agent 初始化测试."""

    def test_init_with_defaults(self, tmp_path: Path) -> None:
        """默认配置初始化."""
        agent = MarketIntelligenceAgent(data_dir=str(tmp_path / "data"))
        assert agent.data_dir == str(tmp_path / "data")
        assert isinstance(agent.config, MarketIntelligenceConfig)
        assert agent.config.top_trends_limit == 10
        # 管道模块已初始化
        assert agent._trend_detector is not None
        assert agent._competitor_tracker is not None
        assert agent._signal_miner is not None
        assert agent._heatmap_engine is not None
        assert agent._opportunity_generator is not None

    def test_init_with_custom_config(self, tmp_path: Path) -> None:
        """自定义配置初始化."""
        config = MarketIntelligenceConfig(
            top_trends_limit=5,
            top_competitors_limit=3,
            top_signals_limit=10,
            top_opportunities_limit=5,
        )
        agent = MarketIntelligenceAgent(
            data_dir=str(tmp_path / "data"), config=config
        )
        assert agent.config.top_trends_limit == 5
        assert agent.config.top_competitors_limit == 3
        assert agent.config.top_signals_limit == 10
        assert agent.config.top_opportunities_limit == 5


# ═══════════════════════════════════════════════════════════════
# 3. 各方法调用（返回正确数据结构）
# ═══════════════════════════════════════════════════════════════


class TestAgentMethods:
    """Agent 各核心方法测试."""

    def test_analyze_market(self, agent: MarketIntelligenceAgent) -> None:
        """analyze_market 返回 MarketAnalysisResult 并包含完整数据."""
        result = agent.analyze_market()

        assert isinstance(result, MarketAnalysisResult)
        assert result.analysis_id.startswith("mkt_")
        assert len(result.trends) > 0
        assert len(result.competitors) > 0
        assert len(result.creative_signals) > 0
        assert "cells" in result.heatmap
        assert len(result.opportunities) > 0
        assert result.summary != ""
        assert result.exploding_trend_count >= 0
        assert result.rising_trend_count >= 0
        assert result.created_at != ""

    def test_detect_trends(self, agent: MarketIntelligenceAgent) -> None:
        """detect_trends 返回趋势列表."""
        trends = agent.detect_trends()

        assert isinstance(trends, list)
        assert len(trends) > 0
        trend = trends[0]
        assert "signal_id" in trend
        assert "category" in trend
        assert "direction" in trend
        assert "growth_pct" in trend
        assert "velocity_score" in trend
        assert "confidence" in trend

    def test_detect_trends_respects_limit(self, tmp_path: Path) -> None:
        """detect_trends 遵守 top_trends_limit 配置."""
        config = MarketIntelligenceConfig(top_trends_limit=3)
        agent = MarketIntelligenceAgent(
            data_dir=str(tmp_path / "data"), config=config
        )
        trends = agent.detect_trends()
        assert len(trends) <= 3

    def test_track_competitors(self, agent: MarketIntelligenceAgent) -> None:
        """track_competitors 返回竞品列表."""
        competitors = agent.track_competitors()

        assert isinstance(competitors, list)
        assert len(competitors) > 0
        comp = competitors[0]
        assert "game_id" in comp
        assert "name" in comp
        assert "category" in comp
        assert "tier" in comp
        assert "threat_level" in comp
        assert "growth_30d" in comp

    def test_mine_creative_signals(self, agent: MarketIntelligenceAgent) -> None:
        """mine_creative_signals 返回创意信号列表."""
        signals = agent.mine_creative_signals()

        assert isinstance(signals, list)
        assert len(signals) > 0
        signal = signals[0]
        assert "signal_id" in signal
        assert "dimension" in signal
        assert "value" in signal
        assert "prevalence" in signal
        assert "growth_30d" in signal
        assert "ctr_prediction" in signal

    def test_get_category_heatmap(self, agent: MarketIntelligenceAgent) -> None:
        """get_category_heatmap 返回热度图字典."""
        heatmap = agent.get_category_heatmap()

        assert isinstance(heatmap, dict)
        assert "cells" in heatmap
        assert "hot_categories" in heatmap
        assert "cold_categories" in heatmap
        assert "top_opportunities" in heatmap
        assert len(heatmap["cells"]) > 0
        cell = heatmap["cells"][0]
        assert "category" in cell
        assert "market_heat" in cell
        assert "competition_density" in cell
        assert "opportunity_gap" in cell

    def test_generate_opportunities(self, agent: MarketIntelligenceAgent) -> None:
        """generate_opportunities 返回机会列表."""
        opportunities = agent.generate_opportunities()

        assert isinstance(opportunities, list)
        assert len(opportunities) > 0
        opp = opportunities[0]
        assert "opportunity_id" in opp
        assert "name" in opp
        assert "category" in opp
        assert "score" in opp
        assert "components" in opp
        assert "recommended_genome" in opp

    def test_get_market_report(self, agent: MarketIntelligenceAgent) -> None:
        """get_market_report 返回 MarketReport."""
        report = agent.get_market_report()

        assert isinstance(report, MarketReport)
        assert report.report_id.startswith("mkt_report_")
        assert report.period != ""
        assert report.executive_summary != ""
        assert "total_trends" in report.market_overview
        assert len(report.trend_highlights) > 0
        assert "tier_1_count" in report.competitive_landscape
        assert len(report.creative_insights) > 0
        assert len(report.opportunity_pipeline) > 0
        assert len(report.recommendations) > 0
        assert len(report.risk_alerts) > 0

    def test_persistence(self, agent: MarketIntelligenceAgent) -> None:
        """分析结果和报告持久化到 JSONL."""
        agent.analyze_market()
        agent.get_market_report()

        analyses = agent.list_analyses()
        reports = agent.list_reports()

        assert len(analyses) >= 1
        assert len(reports) >= 1
        assert analyses[0]["analysis_id"].startswith("mkt_")
        assert reports[0]["report_id"].startswith("mkt_report_")


# ═══════════════════════════════════════════════════════════════
# 4. 单例模式
# ═══════════════════════════════════════════════════════════════


class TestSingleton:
    """单例模式测试."""

    def test_get_agent_returns_singleton(self, tmp_path: Path) -> None:
        """get_market_intelligence_agent 返回同一实例."""
        agent1 = get_market_intelligence_agent(data_dir=str(tmp_path / "data"))
        agent2 = get_market_intelligence_agent()
        assert agent1 is agent2

    def test_reset_singleton(self, tmp_path: Path) -> None:
        """reset 后获取新实例."""
        agent1 = get_market_intelligence_agent(data_dir=str(tmp_path / "data1"))
        reset_market_intelligence_agent()
        agent2 = get_market_intelligence_agent(data_dir=str(tmp_path / "data2"))
        assert agent1 is not agent2

    def test_singleton_thread_safety(self, tmp_path: Path) -> None:
        """多线程下单例安全."""
        import threading

        results: list[MarketIntelligenceAgent] = []
        barrier = threading.Barrier(5)

        def get_agent():
            barrier.wait()
            a = get_market_intelligence_agent(data_dir=str(tmp_path / "data"))
            results.append(a)

        threads = [threading.Thread(target=get_agent) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 所有线程应获取同一实例
        assert len(results) == 5
        assert all(r is results[0] for r in results)


# ═══════════════════════════════════════════════════════════════
# 5. 统计信息
# ═══════════════════════════════════════════════════════════════


class TestStats:
    """统计信息测试."""

    def test_stats_empty(self, agent: MarketIntelligenceAgent) -> None:
        """无历史数据时统计信息正确."""
        stats = agent.get_stats()

        assert stats["total_analyses"] == 0
        assert stats["total_reports"] == 0
        assert "pipeline_stats" in stats
        assert stats["pipeline_stats"]["trend_count"] > 0
        assert stats["pipeline_stats"]["competitor_count"] > 0
        assert stats["pipeline_stats"]["creative_signal_count"] > 0
        assert stats["pipeline_stats"]["opportunity_count"] > 0

    def test_stats_after_analysis(self, agent: MarketIntelligenceAgent) -> None:
        """分析后统计信息正确."""
        agent.analyze_market()
        agent.get_market_report()

        stats = agent.get_stats()

        assert stats["total_analyses"] >= 1
        assert stats["total_reports"] >= 1
        assert "trend_direction_distribution" in stats
        assert "competitor_tier_distribution" in stats
        assert "signal_dimension_distribution" in stats
        assert "hot_categories" in stats
        assert stats["top_opportunity_score"] > 0
        assert len(stats["recent_analyses"]) >= 1
        assert len(stats["recent_reports"]) >= 1

    def test_stats_distributions(self, agent: MarketIntelligenceAgent) -> None:
        """统计信息中的分布字典有效."""
        stats = agent.get_stats()

        # 趋势方向分布
        dir_dist = stats["trend_direction_distribution"]
        assert sum(dir_dist.values()) == stats["pipeline_stats"]["trend_count"]
        # 至少有一个 rising 或 exploding
        assert "rising" in dir_dist or "exploding" in dir_dist

        # 竞品等级分布
        tier_dist = stats["competitor_tier_distribution"]
        assert sum(tier_dist.values()) == stats["pipeline_stats"]["competitor_count"]

        # 信号维度分布
        dim_dist = stats["signal_dimension_distribution"]
        assert sum(dim_dist.values()) == stats["pipeline_stats"]["creative_signal_count"]
        assert "hook" in dim_dist
        assert "visual" in dim_dist


# ═══════════════════════════════════════════════════════════════
# 6. API 端点测试
# ═══════════════════════════════════════════════════════════════


class TestAPIEndpoints:
    """API 端点测试 (使用 TestClient)."""

    @pytest.fixture
    def client(self, tmp_path: Path):
        """创建测试客户端, 使用临时 agent 单例."""
        from fastapi.testclient import TestClient

        reset_market_intelligence_agent()
        tmp_agent = MarketIntelligenceAgent(data_dir=str(tmp_path / "data"))

        with patch(
            "src.market_ops.workspace.app._get_market_intelligence_agent",
            return_value=tmp_agent,
        ):
            from src.market_ops.workspace.app import app
            client = TestClient(app)
            yield client

        reset_market_intelligence_agent()

    def test_analyze_endpoint(self, client) -> None:
        """GET /api/market-intelligence/analyze 返回 200."""
        response = client.get("/api/market-intelligence/analyze")
        assert response.status_code == 200
        data = response.json()
        assert "analysis_id" in data
        assert "trends" in data
        assert "competitors" in data
        assert "creative_signals" in data
        assert "heatmap" in data
        assert "opportunities" in data
        assert "summary" in data

    def test_trends_endpoint(self, client) -> None:
        """GET /api/market-intelligence/trends 返回 200."""
        response = client.get("/api/market-intelligence/trends")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "trends" in data
        assert data["total"] > 0
        assert len(data["trends"]) > 0

    def test_competitors_endpoint(self, client) -> None:
        """GET /api/market-intelligence/competitors 返回 200."""
        response = client.get("/api/market-intelligence/competitors")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "competitors" in data
        assert data["total"] > 0

    def test_creative_signals_endpoint(self, client) -> None:
        """GET /api/market-intelligence/creative-signals 返回 200."""
        response = client.get("/api/market-intelligence/creative-signals")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "creative_signals" in data
        assert data["total"] > 0

    def test_heatmap_endpoint(self, client) -> None:
        """GET /api/market-intelligence/heatmap 返回 200."""
        response = client.get("/api/market-intelligence/heatmap")
        assert response.status_code == 200
        data = response.json()
        assert "cells" in data
        assert "hot_categories" in data
        assert "cold_categories" in data
        assert "top_opportunities" in data
        assert len(data["cells"]) > 0

    def test_opportunities_endpoint(self, client) -> None:
        """GET /api/market-intelligence/opportunities 返回 200."""
        response = client.get("/api/market-intelligence/opportunities")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "opportunities" in data
        assert data["total"] > 0

    def test_report_endpoint(self, client) -> None:
        """GET /api/market-intelligence/report 返回 200."""
        response = client.get("/api/market-intelligence/report")
        assert response.status_code == 200
        data = response.json()
        assert "report_id" in data
        assert "executive_summary" in data
        assert "market_overview" in data
        assert "trend_highlights" in data
        assert "competitive_landscape" in data
        assert "creative_insights" in data
        assert "opportunity_pipeline" in data
        assert "recommendations" in data
        assert "risk_alerts" in data

    def test_stats_endpoint(self, client) -> None:
        """GET /api/market-intelligence/stats 返回 200."""
        response = client.get("/api/market-intelligence/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_analyses" in data
        assert "total_reports" in data
        assert "pipeline_stats" in data
        assert "trend_direction_distribution" in data
        assert "competitor_tier_distribution" in data

    def test_all_endpoints_return_valid_json(self, client) -> None:
        """所有端点返回有效 JSON."""
        endpoints = [
            "/api/market-intelligence/analyze",
            "/api/market-intelligence/trends",
            "/api/market-intelligence/competitors",
            "/api/market-intelligence/creative-signals",
            "/api/market-intelligence/heatmap",
            "/api/market-intelligence/opportunities",
            "/api/market-intelligence/report",
            "/api/market-intelligence/stats",
        ]
        for ep in endpoints:
            response = client.get(ep)
            assert response.status_code == 200, f"{ep} returned {response.status_code}"
            # 确保可序列化
            json.loads(response.text)
