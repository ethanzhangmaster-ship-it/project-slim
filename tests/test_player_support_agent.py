"""Player Support Agent 单元测试.

覆盖:
  1. 工单处理
  2. FAQ 管理
  3. 舆情监控
  4. VIP 服务
  5. 满意度分析
  6. 持久化
  7. API 端点
  8. 组织架构注册
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

from src.market_ops.workspace.player_support_agent import (
    PlayerSupportAgent,
    PlayerSupportConfig,
    PlayerFeedback,
    TicketRecord,
    SentimentReport,
    VIPServiceRecord,
    SatisfactionReport,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def tmp_agent(tmp_path: Path) -> PlayerSupportAgent:
    """使用临时目录的 Player Support Agent."""
    return PlayerSupportAgent(data_dir=str(tmp_path / "data"))


@pytest.fixture
def sample_feedback() -> PlayerFeedback:
    """标准反馈数据."""
    return PlayerFeedback(game_id="merge_game_001")


# ═══════════════════════════════════════════════════════════════
# 1. 工单处理
# ═══════════════════════════════════════════════════════════════


class TestTicketManagement:
    """工单处理."""

    def test_process_ticket_returns_complete(
        self, tmp_agent: PlayerSupportAgent
    ):
        """工单处理包含完整字段."""
        ticket = tmp_agent.process_ticket(
            "g1", "player_001", "payment",
            "充值未到账", "购买 $4.99 宝石未到账", "high"
        )

        assert isinstance(ticket, TicketRecord)
        assert ticket.ticket_id.startswith("tk_")
        assert ticket.game_id == "g1"
        assert ticket.player_id == "player_001"
        assert ticket.category == "payment"
        assert ticket.priority == "high"
        assert ticket.status in ("open", "in_progress", "resolved", "escalated", "closed")
        assert ticket.assigned_to in ("auto", "human", "vip_team")
        assert ticket.auto_reply != ""
        assert ticket.resolution_time_hours > 0

    def test_ticket_auto_route_payment_high_to_human(
        self, tmp_agent: PlayerSupportAgent
    ):
        """支付高优先级 → 人工."""
        ticket = tmp_agent.process_ticket(
            "g1", "p1", "payment", "充值问题", "desc", "high"
        )
        assert ticket.assigned_to == "human"

    def test_ticket_auto_route_gameplay_to_auto(
        self, tmp_agent: PlayerSupportAgent
    ):
        """玩法反馈 → 自动."""
        ticket = tmp_agent.process_ticket(
            "g1", "p1", "gameplay", "建议", "desc", "medium"
        )
        assert ticket.assigned_to == "auto"
        assert ticket.status == "resolved"

    def test_ticket_critical_priority_to_human(
        self, tmp_agent: PlayerSupportAgent
    ):
        """critical 优先级 → 人工."""
        ticket = tmp_agent.process_ticket(
            "g1", "p1", "bug", "严重 Bug", "desc", "critical"
        )
        assert ticket.assigned_to == "human"

    def test_ticket_persists(
        self, tmp_agent: PlayerSupportAgent
    ):
        """工单持久化."""
        tmp_agent.process_ticket("g1", "p1", "bug", "title", "desc", "medium")
        tickets = tmp_agent.list_tickets()
        assert len(tickets) == 1

    def test_ticket_writes_ceo_memory(
        self, tmp_agent: PlayerSupportAgent
    ):
        """工单写入 CEO Memory."""
        tmp_agent.process_ticket("g1", "p1", "bug", "title", "desc", "medium")

        ceo_memory_path = Path(tmp_agent.data_dir) / "ceo" / "execution_memory.jsonl"
        assert ceo_memory_path.exists()

        records = [json.loads(l) for l in ceo_memory_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(records) == 1
        assert records[0]["domain"] == "player_support"
        assert records[0]["action_type"] == "ticket_management"


# ═══════════════════════════════════════════════════════════════
# 2. FAQ 管理
# ═══════════════════════════════════════════════════════════════


class TestFAQManagement:
    """FAQ 知识库."""

    def test_faq_create(self, tmp_agent: PlayerSupportAgent):
        """创建 FAQ."""
        result = tmp_agent.manage_faq(
            "g1", action="create",
            question="如何充值?", answer="在设置中点击充值按钮",
            category="payment"
        )
        assert result["action"] == "create"
        assert result["success"] is True
        assert "faq" in result

    def test_faq_list(self, tmp_agent: PlayerSupportAgent):
        """列出 FAQ."""
        tmp_agent.manage_faq("g1", action="create", question="Q1", answer="A1")
        result = tmp_agent.manage_faq("g1", action="list")
        assert result["total"] == 1
        assert len(result["faqs"]) == 1

    def test_faq_search(self, tmp_agent: PlayerSupportAgent):
        """搜索 FAQ."""
        tmp_agent.manage_faq("g1", action="create",
                             question="如何充值宝石?", answer="在商店中购买", category="payment")
        tmp_agent.manage_faq("g1", action="create",
                             question="账号丢失怎么办?", answer="联系客服", category="account")
        result = tmp_agent.manage_faq("g1", action="search", question="充值")
        assert len(result["results"]) == 1

    def test_faq_create_requires_question_answer(
        self, tmp_agent: PlayerSupportAgent
    ):
        """创建 FAQ 需要问题和答案."""
        result = tmp_agent.manage_faq("g1", action="create", question="", answer="")
        assert result["success"] is False


# ═══════════════════════════════════════════════════════════════
# 3. 舆情监控
# ═══════════════════════════════════════════════════════════════


class TestSentimentMonitoring:
    """舆情监控."""

    def test_monitor_sentiment_returns_complete(
        self, tmp_agent: PlayerSupportAgent, sample_feedback: PlayerFeedback
    ):
        """舆情报告包含完整字段."""
        report = tmp_agent.monitor_sentiment("g1", sample_feedback)

        assert isinstance(report, SentimentReport)
        assert report.report_id.startswith("sent_")
        assert report.game_id == "g1"
        assert 0 <= report.avg_rating <= 5
        assert 0 <= report.sentiment_score <= 100
        assert report.positive_count + report.negative_count + report.neutral_count == report.total_reviews
        assert len(report.top_complaints) > 0
        assert report.trend in ("improving", "stable", "declining")

    def test_sentiment_crisis_alert(
        self, tmp_agent: PlayerSupportAgent
    ):
        """低情绪分触发危机告警."""
        feedback = PlayerFeedback(
            game_id="g1",
            avg_rating=2.5,
            total_reviews=1000,
            positive_reviews=200,
            negative_reviews=600,
            neutral_reviews=200,
        )
        report = tmp_agent.monitor_sentiment("g1", feedback)
        assert len(report.crisis_alerts) > 0
        assert any(a["severity"] == "critical" for a in report.crisis_alerts)

    def test_sentiment_trend_improving(
        self, tmp_agent: PlayerSupportAgent
    ):
        """高评分 → improving."""
        feedback = PlayerFeedback(game_id="g1", avg_rating=4.8)
        report = tmp_agent.monitor_sentiment("g1", feedback)
        assert report.trend == "improving"

    def test_sentiment_persists(
        self, tmp_agent: PlayerSupportAgent, sample_feedback: PlayerFeedback
    ):
        """舆情报告持久化."""
        tmp_agent.monitor_sentiment("g1", sample_feedback)
        reports = tmp_agent.list_sentiment_reports()
        assert len(reports) == 1


# ═══════════════════════════════════════════════════════════════
# 4. VIP 服务
# ═══════════════════════════════════════════════════════════════


class TestVIPService:
    """VIP 服务."""

    def test_serve_vip_returns_complete(
        self, tmp_agent: PlayerSupportAgent
    ):
        """VIP 服务记录完整."""
        record = tmp_agent.serve_vip("g1", "vip_001", "diamond", "专属礼包请求")

        assert isinstance(record, VIPServiceRecord)
        assert record.service_id.startswith("vip_")
        assert record.vip_level == "diamond"
        assert record.service_type == "dedicated_channel"
        assert record.response_time_minutes == 5.0
        assert record.handled_by == "dedicated_manager"
        assert record.satisfaction == 0.95

    def test_vip_diamond_fast_response(
        self, tmp_agent: PlayerSupportAgent
    ):
        """Diamond VIP 5 分钟响应."""
        record = tmp_agent.serve_vip("g1", "p1", "diamond", "req")
        assert record.response_time_minutes == 5.0

    def test_vip_gold_slower_response(
        self, tmp_agent: PlayerSupportAgent
    ):
        """Gold VIP 30 分钟响应."""
        record = tmp_agent.serve_vip("g1", "p1", "gold", "req")
        assert record.response_time_minutes == 30.0

    def test_vip_persists(
        self, tmp_agent: PlayerSupportAgent
    ):
        """VIP 记录持久化."""
        tmp_agent.serve_vip("g1", "p1", "gold", "req")
        records = tmp_agent.list_vip_records()
        assert len(records) == 1


# ═══════════════════════════════════════════════════════════════
# 5. 满意度分析
# ═══════════════════════════════════════════════════════════════


class TestSatisfactionAnalysis:
    """满意度分析."""

    def test_analyze_satisfaction_returns_complete(
        self, tmp_agent: PlayerSupportAgent, sample_feedback: PlayerFeedback
    ):
        """满意度报告完整."""
        report = tmp_agent.analyze_satisfaction("g1", sample_feedback)

        assert isinstance(report, SatisfactionReport)
        assert report.report_id.startswith("sat_")
        assert report.csat_score == sample_feedback.csat_score
        assert -100 <= report.nps_score <= 100
        assert report.promoter_count + report.passive_count + report.detractor_count == report.total_responses
        assert "csat_by_category" in report.to_dict()
        assert len(report.improvement_areas) > 0

    def test_nps_calculation(
        self, tmp_agent: PlayerSupportAgent
    ):
        """NPS 计算正确."""
        feedback = PlayerFeedback(
            game_id="g1",
            nps_responses=100,
            promoters=50,
            passives=30,
            detractors=20,
        )
        report = tmp_agent.analyze_satisfaction("g1", feedback)
        # NPS = 50% - 20% = 30
        assert abs(report.nps_score - 30.0) < 1.0

    def test_satisfaction_improvement_areas(
        self, tmp_agent: PlayerSupportAgent
    ):
        """低 NPS → 改进建议."""
        feedback = PlayerFeedback(
            game_id="g1",
            nps_responses=100,
            promoters=10,
            passives=20,
            detractors=70,
        )
        report = tmp_agent.analyze_satisfaction("g1", feedback)
        assert len(report.improvement_areas) > 0
        assert any("NPS" in area for area in report.improvement_areas)


# ═══════════════════════════════════════════════════════════════
# 6. 统计概览
# ═══════════════════════════════════════════════════════════════


class TestStats:
    """统计方法."""

    def test_get_stats_returns_complete(
        self, tmp_agent: PlayerSupportAgent, sample_feedback: PlayerFeedback
    ):
        """统计概览完整."""
        tmp_agent.process_ticket("g1", "p1", "bug", "t", "d", "medium")
        tmp_agent.monitor_sentiment("g1", sample_feedback)
        tmp_agent.serve_vip("g1", "p1", "gold", "req")

        stats = tmp_agent.get_stats()
        assert stats["total_tickets"] == 1
        assert stats["total_sentiment_reports"] == 1
        assert stats["total_vip_records"] == 1
        assert "ticket_status_distribution" in stats
        assert "ticket_category_distribution" in stats


# ═══════════════════════════════════════════════════════════════
# 7. API 端点
# ═══════════════════════════════════════════════════════════════


class TestPlayerSupportAPI:
    """Player Support API 端点."""

    @pytest.fixture
    def client(self, monkeypatch, tmp_path: Path):
        """临时 client."""
        import src.market_ops.workspace.app as app_module
        monkeypatch.setattr(app_module, "_PROJECT_ROOT", tmp_path)
        if hasattr(app_module._get_player_support_agent, "_instance"):
            del app_module._get_player_support_agent._instance
        from src.market_ops.workspace.app import app
        return TestClient(app)

    def test_ticket_endpoint(self, client):
        """工单端点."""
        resp = client.post("/api/player-support/ticket", json={
            "game_id": "g1", "player_id": "p1", "category": "payment",
            "subject": "充值问题", "description": "未到账", "priority": "high"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["category"] == "payment"

    def test_faq_endpoint(self, client):
        """FAQ 端点."""
        resp = client.post("/api/player-support/faq", json={
            "game_id": "g1", "action": "create",
            "question": "Q1", "answer": "A1", "category": "payment"
        })
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_sentiment_endpoint(self, client):
        """舆情端点."""
        resp = client.post("/api/player-support/sentiment", json={"game_id": "g1"})
        assert resp.status_code == 200
        assert "sentiment_score" in resp.json()

    def test_vip_endpoint(self, client):
        """VIP 端点."""
        resp = client.post("/api/player-support/vip", json={
            "game_id": "g1", "player_id": "p1", "vip_level": "diamond", "request": "req"
        })
        assert resp.status_code == 200
        assert resp.json()["vip_level"] == "diamond"

    def test_satisfaction_endpoint(self, client):
        """满意度端点."""
        resp = client.post("/api/player-support/satisfaction", json={"game_id": "g1"})
        assert resp.status_code == 200
        assert "nps_score" in resp.json()

    def test_stats_endpoint(self, client):
        """统计端点."""
        client.post("/api/player-support/ticket", json={
            "game_id": "g1", "player_id": "p1", "subject": "t", "description": "d"
        })
        resp = client.get("/api/player-support/stats")
        assert resp.status_code == 200
        assert "total_tickets" in resp.json()


# ═══════════════════════════════════════════════════════════════
# 8. 组织架构注册
# ═══════════════════════════════════════════════════════════════


class TestPlayerSupportRegistry:
    """组织架构注册."""

    def test_player_support_registered_in_organization(self):
        """Player Support 注册在默认组织中."""
        from src.market_ops.creative_vision_runtime.growth_runtime.agent.communication import (
            create_default_organization,
            AgentRole,
        )
        registry = create_default_organization()
        all_records = registry.get_all()
        roles = [r.identity.role for r in all_records]
        assert AgentRole.PLAYER_SUPPORT in roles

    def test_player_support_identity_has_capabilities(self):
        """Player Support 身份包含能力."""
        from src.market_ops.creative_vision_runtime.growth_runtime.agent.communication import (
            create_player_support_agent_identity,
        )
        identity = create_player_support_agent_identity()
        assert "ticket_management" in identity.capabilities
        assert "faq_knowledge_base" in identity.capabilities
        assert "sentiment_monitoring" in identity.capabilities
