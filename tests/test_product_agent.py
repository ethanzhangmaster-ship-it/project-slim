"""Product Manager Agent + CEO Decision Center 单元测试.

覆盖:
  1. ProductManagerAgent: PRD/GDD/Feature/Roadmap 生成
  2. 品类模板: Merge/Match3/Simulation
  3. Go/No-Go 评估逻辑
  4. 持久化: JSONL 读写
  5. CEO Memory 回流
  6. API 端点: Product + CEO Decision Center

设计原则:
  - 全部使用 tmp_path, 绝不污染 data/
  - 不依赖外部模块（v9_company 不可导入时降级）
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

from src.market_ops.workspace.product_agent import (
    ProductManagerAgent,
    MarketOpportunity,
    ProductRequirementDoc,
    GameDesignDocument,
    FeatureItem,
    ProductRoadmap,
    ProductTemplateConfig,
)
from src.market_ops.workspace.ceo_decision_center import CEODecisionCenter


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def tmp_agent(tmp_path: Path) -> ProductManagerAgent:
    """使用临时目录的 Product Agent."""
    return ProductManagerAgent(data_dir=str(tmp_path / "data"))


@pytest.fixture
def tmp_ceo_center(tmp_path: Path) -> CEODecisionCenter:
    """使用临时目录的 CEO Decision Center."""
    return CEODecisionCenter(data_dir=str(tmp_path / "data"))


@pytest.fixture
def sample_opportunity() -> MarketOpportunity:
    """标准市场机会输入."""
    return MarketOpportunity(
        genre="Merge",
        target_audience="女性30-45",
        target_market="US",
        budget_usd=500000.0,
        timeline_months=6,
    )


# ═══════════════════════════════════════════════════════════════
# 1. ProductManagerAgent 核心测试
# ═══════════════════════════════════════════════════════════════


class TestProductAgentCore:
    """产品经理 Agent 核心方法."""

    def test_generate_prd_returns_complete_prd(
        self, tmp_agent: ProductManagerAgent, sample_opportunity: MarketOpportunity
    ):
        """生成 PRD 包含所有必需字段."""
        prd = tmp_agent.generate_prd(sample_opportunity)

        assert isinstance(prd, ProductRequirementDoc)
        assert prd.prd_id.startswith("prd_")
        assert prd.title != ""
        assert prd.genre == "Merge"
        assert prd.vision != ""
        assert prd.core_gameplay != ""
        assert prd.meta_loop != ""
        assert prd.monetization_model == "Hybrid"
        assert len(prd.kpi_targets) > 0
        assert len(prd.key_features) > 0
        assert prd.go_no_go in ("GO", "REVIEW", "NO_GO")
        assert prd.created_at != ""

    def test_generate_prd_persists_to_jsonl(
        self, tmp_agent: ProductManagerAgent, sample_opportunity: MarketOpportunity
    ):
        """PRD 持久化到 JSONL 文件."""
        prd = tmp_agent.generate_prd(sample_opportunity)

        prds = tmp_agent.list_prds()
        assert len(prds) == 1
        assert prds[0]["prd_id"] == prd.prd_id

    def test_generate_prd_writes_ceo_memory(
        self, tmp_agent: ProductManagerAgent, sample_opportunity: MarketOpportunity
    ):
        """PRD 生成后写入 CEO Memory."""
        tmp_agent.generate_prd(sample_opportunity)

        ceo_memory_path = Path(tmp_agent.data_dir) / "ceo" / "execution_memory.jsonl"
        assert ceo_memory_path.exists()

        records = [json.loads(l) for l in ceo_memory_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(records) == 1
        assert records[0]["domain"] == "product"
        assert records[0]["action_type"] == "prd_generation"
        assert records[0]["success"] is True

    def test_generate_gdd_from_prd(
        self, tmp_agent: ProductManagerAgent, sample_opportunity: MarketOpportunity
    ):
        """从 PRD 生成 GDD."""
        prd = tmp_agent.generate_prd(sample_opportunity)
        gdd = tmp_agent.generate_gdd(prd.prd_id)

        assert isinstance(gdd, GameDesignDocument)
        assert gdd.gdd_id.startswith("gdd_")
        assert gdd.prd_id == prd.prd_id
        assert gdd.game_name == prd.title
        assert gdd.genre == "Merge"
        assert len(gdd.core_loop) > 0
        assert len(gdd.meta_loop) > 0
        assert len(gdd.mechanics) > 0
        assert gdd.economy_system != {}
        assert gdd.art_style != ""

    def test_generate_gdd_persists(
        self, tmp_agent: ProductManagerAgent, sample_opportunity: MarketOpportunity
    ):
        """GDD 持久化."""
        prd = tmp_agent.generate_prd(sample_opportunity)
        tmp_agent.generate_gdd(prd.prd_id)

        gdds = tmp_agent.list_gdds()
        assert len(gdds) == 1

    def test_generate_gdd_prd_not_found_raises(
        self, tmp_agent: ProductManagerAgent
    ):
        """PRD 不存在时 GDD 生成抛出 ValueError."""
        with pytest.raises(ValueError, match="PRD not found"):
            tmp_agent.generate_gdd("prd_nonexistent")

    def test_prioritize_features(
        self, tmp_agent: ProductManagerAgent, sample_opportunity: MarketOpportunity
    ):
        """Feature 优先级排序."""
        prd = tmp_agent.generate_prd(sample_opportunity)
        features = tmp_agent.prioritize_features(prd.prd_id)

        assert len(features) > 0
        assert all(isinstance(f, FeatureItem) for f in features)
        # 验证按 priority_score 降序
        for i in range(len(features) - 1):
            assert features[i].priority_score >= features[i + 1].priority_score
        # 第一个应该是核心玩法（最高优先级）
        assert features[0].priority_score == 95.0

    def test_create_roadmap(
        self, tmp_agent: ProductManagerAgent, sample_opportunity: MarketOpportunity
    ):
        """路线图生成."""
        prd = tmp_agent.generate_prd(sample_opportunity)
        roadmap = tmp_agent.create_roadmap(prd.prd_id)

        assert isinstance(roadmap, ProductRoadmap)
        assert roadmap.roadmap_id.startswith("rm_")
        assert roadmap.prd_id == prd.prd_id
        assert len(roadmap.milestones) == 4
        assert roadmap.total_sprints > 0
        # 验证里程碑顺序
        assert roadmap.milestones[0].title == "Prototype / Vertical Slice"
        assert roadmap.milestones[-1].title == "Global Launch"

    def test_get_stats(
        self, tmp_agent: ProductManagerAgent, sample_opportunity: MarketOpportunity
    ):
        """统计概览."""
        tmp_agent.generate_prd(sample_opportunity)
        tmp_agent.generate_gdd(tmp_agent.list_prds()[0]["prd_id"])

        stats = tmp_agent.get_stats()
        assert stats["total_prds"] == 1
        assert stats["total_gdds"] == 1
        assert "Merge" in stats["genre_distribution"]
        assert "GO" in stats["go_no_go_distribution"] or "REVIEW" in stats["go_no_go_distribution"]


# ═══════════════════════════════════════════════════════════════
# 2. 品类模板测试
# ═══════════════════════════════════════════════════════════════


class TestGenreTemplates:
    """品类模板覆盖."""

    @pytest.mark.parametrize("genre", ["Merge", "Match3", "Simulation"])
    def test_genre_template_generates_prd(
        self, tmp_agent: ProductManagerAgent, genre: str
    ):
        """每个品类模板都能生成 PRD."""
        opp = MarketOpportunity(genre=genre, budget_usd=300000.0, timeline_months=6)
        prd = tmp_agent.generate_prd(opp)
        assert prd.genre == genre
        assert len(prd.key_features) > 0
        assert len(prd.kpi_targets) > 0

    def test_unknown_genre_falls_back_to_merge(
        self, tmp_agent: ProductManagerAgent
    ):
        """未知品类降级到 Merge 模板."""
        opp = MarketOpportunity(genre="Unknown", budget_usd=300000.0, timeline_months=6)
        prd = tmp_agent.generate_prd(opp)
        assert prd.genre == "Unknown"
        # 降级到 Merge 模板的内容
        assert "合并" in prd.core_gameplay

    def test_match3_template_has_lives_economy(
        self, tmp_agent: ProductManagerAgent
    ):
        """Match3 模板使用 lives 经济系统."""
        opp = MarketOpportunity(genre="Match3", budget_usd=300000.0, timeline_months=6)
        prd = tmp_agent.generate_prd(opp)
        gdd = tmp_agent.generate_gdd(prd.prd_id)
        assert "lives" in gdd.economy_system

    def test_simulation_template_uses_iap(
        self, tmp_agent: ProductManagerAgent
    ):
        """Simulation 模板使用 IAP 变现."""
        opp = MarketOpportunity(genre="Simulation", budget_usd=300000.0, timeline_months=6)
        prd = tmp_agent.generate_prd(opp)
        assert prd.monetization_model == "IAP"


# ═══════════════════════════════════════════════════════════════
# 3. Go/No-Go 评估测试
# ═══════════════════════════════════════════════════════════════


class TestGoNoGoAssessment:
    """Go/No-Go 决策逻辑."""

    def test_high_budget_returns_go(
        self, tmp_agent: ProductManagerAgent
    ):
        """高预算 + 充足周期 → GO."""
        opp = MarketOpportunity(
            genre="Merge",
            budget_usd=500000.0,
            timeline_months=8,
        )
        prd = tmp_agent.generate_prd(opp)
        assert prd.go_no_go == "GO"

    def test_low_budget_returns_no_go(
        self, tmp_agent: ProductManagerAgent
    ):
        """低预算 + 短周期 → NO_GO."""
        opp = MarketOpportunity(
            genre="Merge",
            budget_usd=50000.0,   # 远低于默认 300000
            timeline_months=2,     # 远低于默认 6
        )
        prd = tmp_agent.generate_prd(opp)
        assert prd.go_no_go == "NO_GO"

    def test_medium_budget_returns_review(
        self, tmp_agent: ProductManagerAgent
    ):
        """中等预算 → REVIEW."""
        opp = MarketOpportunity(
            genre="Merge",
            budget_usd=200000.0,  # 低于默认但有风险因子扣分
            timeline_months=6,
        )
        prd = tmp_agent.generate_prd(opp)
        assert prd.go_no_go in ("GO", "REVIEW", "NO_GO")

    def test_risk_assessment_includes_budget_risk(
        self, tmp_agent: ProductManagerAgent
    ):
        """低预算时风险评估包含预算风险."""
        opp = MarketOpportunity(
            genre="Merge",
            budget_usd=50000.0,
            timeline_months=6,
        )
        prd = tmp_agent.generate_prd(opp)
        assert "预算偏低" in prd.risk_assessment

    def test_risk_assessment_includes_timeline_risk(
        self, tmp_agent: ProductManagerAgent
    ):
        """短周期时风险评估包含周期风险."""
        opp = MarketOpportunity(
            genre="Merge",
            budget_usd=300000.0,
            timeline_months=2,
        )
        prd = tmp_agent.generate_prd(opp)
        assert "周期偏短" in prd.risk_assessment


# ═══════════════════════════════════════════════════════════════
# 4. 持久化测试
# ═══════════════════════════════════════════════════════════════


class TestPersistence:
    """JSONL 持久化."""

    def test_prd_round_trip(
        self, tmp_agent: ProductManagerAgent, sample_opportunity: MarketOpportunity
    ):
        """PRD 保存后能正确读取."""
        prd = tmp_agent.generate_prd(sample_opportunity)

        loaded = tmp_agent.get_prd(prd.prd_id)
        assert loaded is not None
        assert loaded["prd_id"] == prd.prd_id
        assert loaded["title"] == prd.title
        assert loaded["genre"] == prd.genre

    def test_gdd_round_trip(
        self, tmp_agent: ProductManagerAgent, sample_opportunity: MarketOpportunity
    ):
        """GDD 保存后能正确读取."""
        prd = tmp_agent.generate_prd(sample_opportunity)
        gdd = tmp_agent.generate_gdd(prd.prd_id)

        loaded = tmp_agent.get_gdd(gdd.gdd_id)
        assert loaded is not None
        assert loaded["gdd_id"] == gdd.gdd_id
        assert loaded["game_name"] == gdd.game_name

    def test_list_prds_empty(
        self, tmp_agent: ProductManagerAgent
    ):
        """空数据时 list 返回空列表."""
        assert tmp_agent.list_prds() == []

    def test_get_prd_not_found(
        self, tmp_agent: ProductManagerAgent
    ):
        """PRD 不存在时返回 None."""
        assert tmp_agent.get_prd("prd_nonexistent") is None

    def test_multiple_prds_listed(
        self, tmp_agent: ProductManagerAgent
    ):
        """多个 PRD 都能列出."""
        for i in range(3):
            opp = MarketOpportunity(genre="Merge", budget_usd=300000.0, timeline_months=6)
            tmp_agent.generate_prd(opp)
        prds = tmp_agent.list_prds()
        assert len(prds) == 3


# ═══════════════════════════════════════════════════════════════
# 5. CEO Decision Center 测试
# ═══════════════════════════════════════════════════════════════


class TestCEODecisionCenter:
    """CEO Decision Center 核心方法."""

    def test_get_dashboard_empty_data(self, tmp_ceo_center: CEODecisionCenter):
        """空数据时仪表盘返回默认结构."""
        dashboard = tmp_ceo_center.get_dashboard()

        assert "company_status" in dashboard
        assert dashboard["company_status"] == "HEALTHY"
        assert "summary" in dashboard
        assert "departments" in dashboard
        assert "pending_actions" in dashboard
        assert "alerts" in dashboard
        assert "recent_decisions" in dashboard
        assert "kpi_cards" in dashboard
        assert dashboard["summary"]["total_games"] == 0

    def test_get_dashboard_with_growth_loop_data(
        self, tmp_ceo_center: CEODecisionCenter
    ):
        """有 GrowthLoop 数据时仪表盘正确聚合."""
        # 写入测试数据
        gl_dir = Path(tmp_ceo_center.data_dir) / "growth_loop"
        gl_dir.mkdir(parents=True, exist_ok=True)
        gl_path = gl_dir / "cycle_history.jsonl"
        gl_path.write_text(json.dumps({
            "cycle_number": 1,
            "actions_executed": 5,
            "execution_results": [{"success": True}, {"success": True}, {"success": False}],
            "completed_at": "2026-08-07T10:00:00+00:00",
        }) + "\n", encoding="utf-8")

        dashboard = tmp_ceo_center.get_dashboard()
        assert dashboard["summary"]["growth_loop_cycles"] == 1
        assert dashboard["summary"]["success_rate"] < 1.0  # 有失败

    def test_get_company_report(self, tmp_ceo_center: CEODecisionCenter):
        """公司日报包含所有必需字段."""
        report = tmp_ceo_center.get_company_report()

        assert "report_date" in report
        assert "company_status" in report
        assert "executive_summary" in report
        assert "department_reports" in report
        assert "portfolio" in report
        assert "resource_allocation" in report
        assert "next_actions" in report
        assert "kpi_summary" in report

    def test_get_portfolio_overview_empty(self, tmp_ceo_center: CEODecisionCenter):
        """空数据时投资组合返回空."""
        portfolio = tmp_ceo_center.get_portfolio_overview()
        assert portfolio["total_games"] == 0
        assert portfolio["games"] == []

    def test_get_portfolio_with_game_data(
        self, tmp_ceo_center: CEODecisionCenter
    ):
        """有游戏数据时投资组合正确聚合."""
        # 写入测试游戏数据
        gr_dir = Path(tmp_ceo_center.data_dir) / "ceo" / "game_reality"
        gr_dir.mkdir(parents=True, exist_ok=True)
        (gr_dir / "game_a.jsonl").write_text(json.dumps({
            "game_id": "game_a",
            "game_name": "Game A",
            "revenue_daily": 5000.0,
            "dau": 50000,
            "roas": 1.5,
        }) + "\n", encoding="utf-8")

        portfolio = tmp_ceo_center.get_portfolio_overview()
        assert portfolio["total_games"] == 1
        assert portfolio["games"][0]["game_id"] == "game_a"
        assert portfolio["games"][0]["health"] == "healthy"

    def test_get_pending_decisions_empty(self, tmp_ceo_center: CEODecisionCenter):
        """空数据时待审批返回空."""
        assert tmp_ceo_center.get_pending_decisions() == []

    def test_get_pending_decisions_with_data(
        self, tmp_ceo_center: CEODecisionCenter
    ):
        """有待审批数据时正确过滤."""
        aq_dir = Path(tmp_ceo_center.data_dir) / "ceo"
        aq_dir.mkdir(parents=True, exist_ok=True)
        aq_path = aq_dir / "approval_queue.jsonl"
        aq_path.write_text(
            json.dumps({"audit_id": "a1", "status": "pending", "game_id": "g1", "risk": 0.3}) + "\n" +
            json.dumps({"audit_id": "a2", "status": "pending", "game_id": "g2", "risk": 0.8}) + "\n" +
            json.dumps({"kind": "resolution", "audit_id": "a1"}) + "\n"
        , encoding="utf-8")

        pending = tmp_ceo_center.get_pending_decisions()
        assert len(pending) == 1  # a1 已 resolved，只剩 a2
        assert pending[0]["audit_id"] == "a2"

    def test_get_cross_department_view(self, tmp_ceo_center: CEODecisionCenter):
        """跨部门视图包含所有域."""
        view = tmp_ceo_center.get_cross_department_view()
        assert "growth_loop" in view
        assert "liveops" in view
        assert "product" in view
        assert "approval" in view
        assert "execution" in view
        assert "agent_topology" in view

    def test_alerts_on_low_success_rate(
        self, tmp_ceo_center: CEODecisionCenter
    ):
        """成功率低时生成告警."""
        gl_dir = Path(tmp_ceo_center.data_dir) / "growth_loop"
        gl_dir.mkdir(parents=True, exist_ok=True)
        (gl_dir / "cycle_history.jsonl").write_text(json.dumps({
            "cycle_number": 1,
            "actions_executed": 5,
            "execution_results": [{"success": False}, {"success": False}, {"success": False}],
            "completed_at": "2026-08-07T10:00:00+00:00",
        }) + "\n", encoding="utf-8")

        dashboard = tmp_ceo_center.get_dashboard()
        gl_alerts = [a for a in dashboard["alerts"] if a["category"] == "growth_loop"]
        assert len(gl_alerts) > 0
        assert gl_alerts[0]["severity"] == "critical"

    def test_company_status_critical_with_high_risk_pending(
        self, tmp_ceo_center: CEODecisionCenter
    ):
        """高风险待审批时公司状态为 CRITICAL."""
        aq_dir = Path(tmp_ceo_center.data_dir) / "ceo"
        aq_dir.mkdir(parents=True, exist_ok=True)
        (aq_dir / "approval_queue.jsonl").write_text(json.dumps({
            "audit_id": "a1", "status": "pending", "game_id": "g1", "risk": 0.9,
        }) + "\n", encoding="utf-8")

        dashboard = tmp_ceo_center.get_dashboard()
        assert dashboard["company_status"] == "CRITICAL"


# ═══════════════════════════════════════════════════════════════
# 6. API 端点测试
# ═══════════════════════════════════════════════════════════════


class TestProductAPI:
    """Product Agent HTTP API 端点测试."""

    @pytest.fixture
    def api_client(self, tmp_path: Path, monkeypatch):
        """FastAPI TestClient + 临时数据目录."""
        data_dir = tmp_path / "data"
        for sub in ["growth_loop", "ceo/audit", "ceo/game_reality", "liveops", "product", "workspace"]:
            (data_dir / sub).mkdir(parents=True, exist_ok=True)
        (data_dir / "growth_loop" / "cycle_history.jsonl").write_text("", encoding="utf-8")

        from src.market_ops.workspace import app as app_module
        monkeypatch.setattr(app_module, "_PROJECT_ROOT", tmp_path)

        # 重置单例
        for attr in ["_instance"]:
            if hasattr(app_module._get_product_agent, attr):
                delattr(app_module._get_product_agent, attr)
            if hasattr(app_module._get_ceo_decision_center, attr):
                delattr(app_module._get_ceo_decision_center, attr)

        from src.market_ops.workspace import aggregator as agg_module
        agg_module._aggregator = None

        from src.market_ops.workspace.app import app
        return TestClient(app)

    def test_generate_prd_api(self, api_client: TestClient):
        """POST /api/product/prd 生成 PRD."""
        resp = api_client.post("/api/product/prd", json={
            "genre": "Merge",
            "target_audience": "女性30-45",
            "target_market": "US",
            "budget_usd": 500000.0,
            "timeline_months": 6,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["prd_id"].startswith("prd_")
        assert data["genre"] == "Merge"
        assert data["go_no_go"] in ("GO", "REVIEW", "NO_GO")
        assert len(data["kpi_targets"]) > 0

    def test_generate_gdd_api(self, api_client: TestClient):
        """POST /api/product/gdd/{prd_id} 生成 GDD."""
        # 先生成 PRD
        prd_resp = api_client.post("/api/product/prd", json={
            "genre": "Merge", "budget_usd": 500000.0, "timeline_months": 6,
        })
        prd_id = prd_resp.json()["prd_id"]

        # 生成 GDD
        resp = api_client.post(f"/api/product/gdd/{prd_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["gdd_id"].startswith("gdd_")
        assert data["prd_id"] == prd_id
        assert len(data["core_loop"]) > 0

    def test_generate_gdd_prd_not_found_api(self, api_client: TestClient):
        """POST /api/product/gdd/{prd_id} PRD 不存在返回 404."""
        resp = api_client.post("/api/product/gdd/prd_nonexistent")
        assert resp.status_code == 404

    def test_prioritize_features_api(self, api_client: TestClient):
        """POST /api/product/features/{prd_id}."""
        prd_resp = api_client.post("/api/product/prd", json={
            "genre": "Match3", "budget_usd": 300000.0, "timeline_months": 6,
        })
        prd_id = prd_resp.json()["prd_id"]

        resp = api_client.post(f"/api/product/features/{prd_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["feature_count"] > 0
        assert len(data["features"]) > 0

    def test_create_roadmap_api(self, api_client: TestClient):
        """POST /api/product/roadmap/{prd_id}."""
        prd_resp = api_client.post("/api/product/prd", json={
            "genre": "Simulation", "budget_usd": 400000.0, "timeline_months": 8,
        })
        prd_id = prd_resp.json()["prd_id"]

        resp = api_client.post(f"/api/product/roadmap/{prd_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["roadmap_id"].startswith("rm_")
        assert len(data["milestones"]) == 4

    def test_list_prds_api(self, api_client: TestClient):
        """GET /api/product/prds."""
        api_client.post("/api/product/prd", json={
            "genre": "Merge", "budget_usd": 300000.0, "timeline_months": 6,
        })
        resp = api_client.get("/api/product/prds")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_get_prd_api(self, api_client: TestClient):
        """GET /api/product/prds/{prd_id}."""
        prd_resp = api_client.post("/api/product/prd", json={
            "genre": "Merge", "budget_usd": 300000.0, "timeline_months": 6,
        })
        prd_id = prd_resp.json()["prd_id"]

        resp = api_client.get(f"/api/product/prds/{prd_id}")
        assert resp.status_code == 200
        assert resp.json()["prd_id"] == prd_id

    def test_get_prd_not_found_api(self, api_client: TestClient):
        """GET /api/product/prds/{prd_id} 不存在返回 404."""
        resp = api_client.get("/api/product/prds/prd_nonexistent")
        assert resp.status_code == 404

    def test_get_product_stats_api(self, api_client: TestClient):
        """GET /api/product/stats."""
        api_client.post("/api/product/prd", json={
            "genre": "Merge", "budget_usd": 300000.0, "timeline_months": 6,
        })
        resp = api_client.get("/api/product/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_prds"] >= 1

    def test_full_product_pipeline_api(self, api_client: TestClient):
        """完整产品管线: PRD → GDD → Features → Roadmap."""
        # 1. 生成 PRD
        prd_resp = api_client.post("/api/product/prd", json={
            "genre": "Merge",
            "target_audience": "女性30-45",
            "target_market": "US",
            "budget_usd": 500000.0,
            "timeline_months": 6,
        })
        assert prd_resp.status_code == 200
        prd_id = prd_resp.json()["prd_id"]

        # 2. 生成 GDD
        gdd_resp = api_client.post(f"/api/product/gdd/{prd_id}")
        assert gdd_resp.status_code == 200

        # 3. Feature 排序
        feat_resp = api_client.post(f"/api/product/features/{prd_id}")
        assert feat_resp.status_code == 200

        # 4. 生成 Roadmap
        rm_resp = api_client.post(f"/api/product/roadmap/{prd_id}")
        assert rm_resp.status_code == 200

        # 验证所有产物
        stats = api_client.get("/api/product/stats").json()
        assert stats["total_prds"] >= 1
        assert stats["total_gdds"] >= 1
        assert stats["total_roadmaps"] >= 1


class TestCEODecisionCenterAPI:
    """CEO Decision Center HTTP API 端点测试."""

    @pytest.fixture
    def api_client(self, tmp_path: Path, monkeypatch):
        """FastAPI TestClient + 临时数据目录."""
        data_dir = tmp_path / "data"
        for sub in ["growth_loop", "ceo/audit", "ceo/game_reality", "liveops", "product", "workspace"]:
            (data_dir / sub).mkdir(parents=True, exist_ok=True)
        (data_dir / "growth_loop" / "cycle_history.jsonl").write_text("", encoding="utf-8")

        from src.market_ops.workspace import app as app_module
        monkeypatch.setattr(app_module, "_PROJECT_ROOT", tmp_path)

        for attr in ["_instance"]:
            if hasattr(app_module._get_ceo_decision_center, attr):
                delattr(app_module._get_ceo_decision_center, attr)
            if hasattr(app_module._get_product_agent, attr):
                delattr(app_module._get_product_agent, attr)

        from src.market_ops.workspace import aggregator as agg_module
        agg_module._aggregator = None

        from src.market_ops.workspace.app import app
        return TestClient(app)

    def test_get_ceo_dashboard_api(self, api_client: TestClient):
        """GET /api/ceo/dashboard."""
        resp = api_client.get("/api/ceo/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert data["company_status"] in ("HEALTHY", "ATTENTION", "CRITICAL")
        assert "summary" in data
        assert "departments" in data

    def test_get_ceo_company_report_api(self, api_client: TestClient):
        """GET /api/ceo/company-report."""
        resp = api_client.get("/api/ceo/company-report")
        assert resp.status_code == 200
        data = resp.json()
        assert "executive_summary" in data
        assert "department_reports" in data
        assert "portfolio" in data

    def test_get_ceo_portfolio_api(self, api_client: TestClient):
        """GET /api/ceo/portfolio."""
        resp = api_client.get("/api/ceo/portfolio")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_games" in data
        assert "games" in data

    def test_get_ceo_pending_decisions_api(self, api_client: TestClient):
        """GET /api/ceo/decisions/pending."""
        resp = api_client.get("/api/ceo/decisions/pending")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_ceo_decision_history_api(self, api_client: TestClient):
        """GET /api/ceo/decisions/history."""
        resp = api_client.get("/api/ceo/decisions/history")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_ceo_execution_timeline_api(self, api_client: TestClient):
        """GET /api/ceo/execution-timeline."""
        resp = api_client.get("/api/ceo/execution-timeline")
        assert resp.status_code == 200
        data = resp.json()
        assert "timeline" in data
        assert "domain_distribution" in data

    def test_get_ceo_cross_department_api(self, api_client: TestClient):
        """GET /api/ceo/cross-department."""
        resp = api_client.get("/api/ceo/cross-department")
        assert resp.status_code == 200
        data = resp.json()
        assert "growth_loop" in data
        assert "liveops" in data
        assert "product" in data

    def test_ceo_dashboard_with_product_data(self, api_client: TestClient):
        """生成 PRD 后 CEO Dashboard 显示产品统计."""
        # 生成 PRD
        api_client.post("/api/product/prd", json={
            "genre": "Merge", "budget_usd": 500000.0, "timeline_months": 6,
        })

        # 检查 Dashboard
        resp = api_client.get("/api/ceo/dashboard")
        data = resp.json()
        assert data["summary"]["product_prds"] >= 1


# ═══════════════════════════════════════════════════════════════
# 7. AgentRegistry 组织架构注册测试
# ═══════════════════════════════════════════════════════════════


class TestProductAgentRegistry:
    """Product Agent 在 AgentRegistry 组织架构中的注册."""

    def test_product_agent_registered_in_default_organization(self):
        """默认组织包含 Product Agent."""
        from src.market_ops.creative_vision_runtime.growth_runtime.agent.communication.agent_registry import (
            create_default_organization,
            AgentRegistry,
        )
        registry = create_default_organization()
        assert isinstance(registry, AgentRegistry)

        all_records = registry.get_all()
        product_records = [r for r in all_records if r.identity.role.value == "product"]
        assert len(product_records) == 1

    def test_product_agent_has_prd_generation_capability(self):
        """Product Agent 注册时包含 PRD/GDD/Roadmap 能力."""
        from src.market_ops.creative_vision_runtime.growth_runtime.agent.communication.agent_registry import (
            create_default_organization,
        )
        registry = create_default_organization()
        product_agents = registry.find_by_role(
            __import__(
                "src.market_ops.creative_vision_runtime.growth_runtime.agent.communication.agent_message",
                fromlist=["AgentRole"],
            ).AgentRole.PRODUCT
        )
        assert len(product_agents) == 1
        capabilities = product_agents[0].identity.capabilities
        # 新增的产品立项能力
        assert "prd_generation" in capabilities
        assert "gdd_generation" in capabilities
        assert "feature_prioritization" in capabilities
        assert "roadmap_planning" in capabilities
        assert "go_no_go_assessment" in capabilities

    def test_product_agent_name_is_product_manager(self):
        """Product Agent 名称反映产品经理角色."""
        from src.market_ops.creative_vision_runtime.growth_runtime.agent.communication.agent_message import (
            create_product_agent_identity,
        )
        identity = create_product_agent_identity()
        assert "Product" in identity.name

    def test_find_product_by_capability(self):
        """能通过 PRD 能力查找到 Product Agent."""
        from src.market_ops.creative_vision_runtime.growth_runtime.agent.communication.agent_registry import (
            create_default_organization,
        )
        registry = create_default_organization()
        found = registry.find_by_capability("prd_generation")
        assert len(found) == 1
        assert found[0].identity.role.value == "product"

    def test_default_organization_has_ten_agents(self):
        """默认组织包含 10 个 Agent (Supervisor/UA/Creative/Monetization/Product/LiveOps/Designer/Numerical/DataAnalyst/PlayerSupport)."""
        from src.market_ops.creative_vision_runtime.growth_runtime.agent.communication.agent_registry import (
            create_default_organization,
        )
        registry = create_default_organization()
        all_records = registry.get_all()
        assert len(all_records) == 10
        roles = {r.identity.role.value for r in all_records}
        assert roles == {"supervisor", "ua", "creative", "monetization", "product", "liveops", "designer", "numerical", "data_analyst", "player_support"}

    def test_product_agent_visible_in_workspace(self, tmp_path: Path, monkeypatch):
        """Product Agent 在 Workspace /api/agents 中可见且包含新能力."""
        from src.market_ops.workspace import agent_registry_store
        # 用临时路径生成快照
        snapshot_path = tmp_path / "agents.jsonl"
        records = agent_registry_store.create_default_agents_snapshot(snapshot_path)
        assert len(records) == 10
        product_records = [r for r in records if (r.get("identity", {}) or {}).get("role") == "product"]
        assert len(product_records) == 1
        capabilities = product_records[0]["identity"]["capabilities"]
        assert "prd_generation" in capabilities
