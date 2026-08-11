"""Game Designer Agent 单元测试.

覆盖:
  1. GameDesignerAgent: 关卡/数值/系统/难度/设计文档 生成
  2. 品类模板: Merge/Match3/Simulation
  3. 持久化: JSONL 读写
  4. CEO Memory 回流
  5. API 端点
  6. AgentRegistry 组织架构注册

设计原则:
  - 全部使用 tmp_path, 绝不污染 data/
  - 不依赖外部模块（v9_company 不可导入时降级）
  - 先通过 ProductManagerAgent 生成 GDD 作为输入
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

from src.market_ops.workspace.game_designer_agent import (
    GameDesignerAgent,
    LevelDesign,
    LevelDefinition,
    EconomyBalance,
    CurrencyConfig,
    ItemPricing,
    SystemSpecification,
    DifficultyCurve,
    DifficultyStage,
    DesignDocument,
    GenreDesignConfig,
)
from src.market_ops.workspace.product_agent import (
    ProductManagerAgent,
    MarketOpportunity,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    """临时数据目录."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


@pytest.fixture
def tmp_designer(tmp_data_dir: Path) -> GameDesignerAgent:
    """使用临时目录的 Game Designer Agent."""
    return GameDesignerAgent(data_dir=str(tmp_data_dir))


@pytest.fixture
def tmp_product(tmp_data_dir: Path) -> ProductManagerAgent:
    """使用临时目录的 Product Agent（用于生成 GDD）."""
    return ProductManagerAgent(data_dir=str(tmp_data_dir))


@pytest.fixture
def sample_gdd_id(tmp_product: ProductManagerAgent) -> str:
    """生成一个 Merge 品类的 GDD 并返回 gdd_id."""
    opp = MarketOpportunity(genre="Merge", budget_usd=500000.0, timeline_months=6)
    prd = tmp_product.generate_prd(opp)
    gdd = tmp_product.generate_gdd(prd.prd_id)
    return gdd.gdd_id


@pytest.fixture
def sample_gdd_id_match3(tmp_product: ProductManagerAgent) -> str:
    """生成一个 Match3 品类的 GDD 并返回 gdd_id."""
    opp = MarketOpportunity(genre="Match3", budget_usd=300000.0, timeline_months=6)
    prd = tmp_product.generate_prd(opp)
    gdd = tmp_product.generate_gdd(prd.prd_id)
    return gdd.gdd_id


@pytest.fixture
def sample_gdd_id_simulation(tmp_product: ProductManagerAgent) -> str:
    """生成一个 Simulation 品类的 GDD 并返回 gdd_id."""
    opp = MarketOpportunity(genre="Simulation", budget_usd=400000.0, timeline_months=8)
    prd = tmp_product.generate_prd(opp)
    gdd = tmp_product.generate_gdd(prd.prd_id)
    return gdd.gdd_id


# ═══════════════════════════════════════════════════════════════
# 1. GameDesignerAgent 核心测试
# ═══════════════════════════════════════════════════════════════


class TestGameDesignerCore:
    """游戏策划 Agent 核心方法."""

    def test_design_levels_returns_complete_design(
        self, tmp_designer: GameDesignerAgent, sample_gdd_id: str
    ):
        """关卡设计包含完整字段."""
        design = tmp_designer.design_levels(sample_gdd_id)

        assert isinstance(design, LevelDesign)
        assert design.design_id.startswith("lvl_design_")
        assert design.gdd_id == sample_gdd_id
        assert design.genre == "Merge"
        assert design.total_levels == 200
        assert design.total_chapters > 0
        assert len(design.levels) == 200
        assert len(design.chapter_structure) == design.total_chapters

    def test_design_levels_first_level_is_easy(
        self, tmp_designer: GameDesignerAgent, sample_gdd_id: str
    ):
        """第一关应该是 EASY 难度."""
        design = tmp_designer.design_levels(sample_gdd_id)
        assert design.levels[0].difficulty == "EASY"
        assert design.levels[0].level_number == 1
        assert design.levels[0].chapter == 1

    def test_design_levels_last_level_is_expert(
        self, tmp_designer: GameDesignerAgent, sample_gdd_id: str
    ):
        """最后一关应该是 EXPERT 难度."""
        design = tmp_designer.design_levels(sample_gdd_id)
        assert design.levels[-1].difficulty == "EXPERT"

    def test_design_levels_reward_increases(
        self, tmp_designer: GameDesignerAgent, sample_gdd_id: str
    ):
        """关卡奖励随关卡递增."""
        design = tmp_designer.design_levels(sample_gdd_id)
        assert design.levels[-1].reward_amount > design.levels[0].reward_amount

    def test_design_levels_persists(
        self, tmp_designer: GameDesignerAgent, sample_gdd_id: str
    ):
        """关卡设计持久化."""
        tmp_designer.design_levels(sample_gdd_id)
        designs = tmp_designer.list_level_designs()
        assert len(designs) == 1
        assert designs[0]["gdd_id"] == sample_gdd_id

    def test_design_levels_gdd_not_found_raises(
        self, tmp_designer: GameDesignerAgent
    ):
        """GDD 不存在时抛出 ValueError."""
        with pytest.raises(ValueError, match="GDD not found"):
            tmp_designer.design_levels("gdd_nonexistent")

    def test_balance_economy_returns_complete_balance(
        self, tmp_designer: GameDesignerAgent, sample_gdd_id: str
    ):
        """经济平衡包含完整字段."""
        balance = tmp_designer.balance_economy(sample_gdd_id)

        assert isinstance(balance, EconomyBalance)
        assert balance.balance_id.startswith("eco_")
        assert balance.gdd_id == sample_gdd_id
        assert len(balance.currencies) == 3  # hard/soft/energy
        assert len(balance.item_pricing) > 0
        assert balance.sink_to_faucet_ratio > 1.0  # 消耗大于产出
        assert len(balance.pay_points) > 0

    def test_balance_economy_has_hard_soft_energy(
        self, tmp_designer: GameDesignerAgent, sample_gdd_id: str
    ):
        """经济平衡包含 hard/soft/energy 三种货币."""
        balance = tmp_designer.balance_economy(sample_gdd_id)
        types = {c.currency_type for c in balance.currencies}
        assert types == {"hard", "soft", "energy"}

    def test_balance_economy_persists(
        self, tmp_designer: GameDesignerAgent, sample_gdd_id: str
    ):
        """经济平衡持久化."""
        tmp_designer.balance_economy(sample_gdd_id)
        balances = tmp_designer.list_economy_balances()
        assert len(balances) == 1

    def test_specify_systems_returns_list(
        self, tmp_designer: GameDesignerAgent, sample_gdd_id: str
    ):
        """系统规格返回列表."""
        systems = tmp_designer.specify_systems(sample_gdd_id)

        assert isinstance(systems, list)
        assert len(systems) > 0
        assert all(isinstance(s, SystemSpecification) for s in systems)
        # 至少有一个 core 类型系统
        types = {s.system_type for s in systems}
        assert "core" in types

    def test_specify_systems_has_parameters(
        self, tmp_designer: GameDesignerAgent, sample_gdd_id: str
    ):
        """系统规格包含参数."""
        systems = tmp_designer.specify_systems(sample_gdd_id)
        for s in systems:
            assert isinstance(s.parameters, dict)
            assert len(s.parameters) > 0
            assert len(s.interactions) > 0
            assert s.complexity in ("low", "medium", "high")

    def test_specify_systems_persists(
        self, tmp_designer: GameDesignerAgent, sample_gdd_id: str
    ):
        """系统规格持久化."""
        tmp_designer.specify_systems(sample_gdd_id)
        specs = tmp_designer.list_system_specs()
        assert len(specs) == 1

    def test_generate_difficulty_curve_returns_stages(
        self, tmp_designer: GameDesignerAgent, sample_gdd_id: str
    ):
        """难度曲线包含阶段."""
        curve = tmp_designer.generate_difficulty_curve(sample_gdd_id)

        assert isinstance(curve, DifficultyCurve)
        assert curve.curve_id.startswith("curve_")
        assert len(curve.stages) == 5  # Onboarding/Early/Mid/Late/Endgame
        assert curve.slope_parameter > 0
        assert len(curve.plateau_levels) > 0
        assert len(curve.spike_levels) > 0

    def test_difficulty_curve_stages_ordered(
        self, tmp_designer: GameDesignerAgent, sample_gdd_id: str
    ):
        """难度阶段按分数递增."""
        curve = tmp_designer.generate_difficulty_curve(sample_gdd_id)
        scores = [s.difficulty_score for s in curve.stages]
        for i in range(len(scores) - 1):
            assert scores[i] < scores[i + 1]

    def test_difficulty_curve_persists(
        self, tmp_designer: GameDesignerAgent, sample_gdd_id: str
    ):
        """难度曲线持久化."""
        tmp_designer.generate_difficulty_curve(sample_gdd_id)
        curves = tmp_designer.list_difficulty_curves()
        assert len(curves) == 1

    def test_create_design_document_aggregates_all(
        self, tmp_designer: GameDesignerAgent, sample_gdd_id: str
    ):
        """设计文档聚合所有设计产物."""
        doc = tmp_designer.create_design_document(sample_gdd_id)

        assert isinstance(doc, DesignDocument)
        assert doc.document_id.startswith("doc_")
        assert doc.gdd_id == sample_gdd_id
        assert doc.level_design["total_levels"] > 0
        assert len(doc.economy_balance["currencies"]) > 0
        assert len(doc.system_specs) > 0
        assert len(doc.difficulty_curve["stages"]) > 0
        assert doc.ready_for_dev is True
        assert doc.design_summary != ""

    def test_create_design_document_persists(
        self, tmp_designer: GameDesignerAgent, sample_gdd_id: str
    ):
        """设计文档持久化."""
        tmp_designer.create_design_document(sample_gdd_id)
        docs = tmp_designer.list_design_documents()
        assert len(docs) == 1
        assert docs[0]["ready_for_dev"] is True

    def test_get_design_document_by_id(
        self, tmp_designer: GameDesignerAgent, sample_gdd_id: str
    ):
        """按 ID 查询设计文档."""
        created = tmp_designer.create_design_document(sample_gdd_id)
        found = tmp_designer.get_design_document(created.document_id)
        assert found is not None
        assert found["document_id"] == created.document_id

    def test_get_design_document_not_found(
        self, tmp_designer: GameDesignerAgent
    ):
        """查询不存在的设计文档返回 None."""
        assert tmp_designer.get_design_document("doc_nonexistent") is None


# ═══════════════════════════════════════════════════════════════
# 2. 品类模板测试
# ═══════════════════════════════════════════════════════════════


class TestGenreTemplates:
    """品类模板覆盖."""

    def test_merge_template_200_levels(
        self, tmp_designer: GameDesignerAgent, sample_gdd_id: str
    ):
        """Merge 模板生成 200 关."""
        design = tmp_designer.design_levels(sample_gdd_id)
        assert design.total_levels == 200
        assert design.total_chapters == 10  # 200 / 20

    def test_match3_template_500_levels(
        self, tmp_designer: GameDesignerAgent, sample_gdd_id_match3: str
    ):
        """Match3 模板生成 500 关."""
        design = tmp_designer.design_levels(sample_gdd_id_match3)
        assert design.total_levels == 500
        assert design.total_chapters == 20  # 500 / 25

    def test_simulation_template_100_levels(
        self, tmp_designer: GameDesignerAgent, sample_gdd_id_simulation: str
    ):
        """Simulation 模板生成 100 关."""
        design = tmp_designer.design_levels(sample_gdd_id_simulation)
        assert design.total_levels == 100
        assert design.total_chapters == 10  # 100 / 10

    def test_match3_uses_lives_not_energy(
        self, tmp_designer: GameDesignerAgent, sample_gdd_id_match3: str
    ):
        """Match3 使用 Lives 而非 Energy."""
        balance = tmp_designer.balance_economy(sample_gdd_id_match3)
        names = {c.currency_name for c in balance.currencies}
        assert "Lives" in names

    def test_simulation_uses_diamonds(
        self, tmp_designer: GameDesignerAgent, sample_gdd_id_simulation: str
    ):
        """Simulation 使用 Diamonds 作为硬通货币."""
        balance = tmp_designer.balance_economy(sample_gdd_id_simulation)
        hard_currencies = [c for c in balance.currencies if c.currency_type == "hard"]
        assert any(c.currency_name == "Diamonds" for c in hard_currencies)

    def test_each_genre_has_unique_systems(
        self, tmp_designer: GameDesignerAgent,
        sample_gdd_id: str, sample_gdd_id_match3: str
    ):
        """不同品类有不同系统."""
        merge_systems = tmp_designer.specify_systems(sample_gdd_id)
        match3_systems = tmp_designer.specify_systems(sample_gdd_id_match3)
        merge_names = {s.name for s in merge_systems}
        match3_names = {s.name for s in match3_systems}
        assert merge_names != match3_names


# ═══════════════════════════════════════════════════════════════
# 3. 持久化和统计测试
# ═══════════════════════════════════════════════════════════════


class TestPersistenceAndStats:
    """持久化和统计."""

    def test_stats_empty(self, tmp_designer: GameDesignerAgent):
        """空数据统计."""
        stats = tmp_designer.get_stats()
        assert stats["total_level_designs"] == 0
        assert stats["total_economy_balances"] == 0
        assert stats["total_system_specs"] == 0
        assert stats["total_difficulty_curves"] == 0
        assert stats["total_design_documents"] == 0
        assert stats["ready_for_dev_count"] == 0

    def test_stats_after_full_design(
        self, tmp_designer: GameDesignerAgent, sample_gdd_id: str
    ):
        """完整设计后统计."""
        tmp_designer.create_design_document(sample_gdd_id)
        stats = tmp_designer.get_stats()
        assert stats["total_level_designs"] == 1
        assert stats["total_economy_balances"] == 1
        assert stats["total_system_specs"] == 1
        assert stats["total_difficulty_curves"] == 1
        assert stats["total_design_documents"] == 1
        assert stats["ready_for_dev_count"] == 1
        assert "Merge" in stats["genre_distribution"]

    def test_ceo_memory_written(
        self, tmp_designer: GameDesignerAgent, sample_gdd_id: str, tmp_data_dir: Path
    ):
        """设计产物回流 CEO Memory."""
        tmp_designer.design_levels(sample_gdd_id)
        ceo_memory_path = tmp_data_dir / "ceo" / "execution_memory.jsonl"
        assert ceo_memory_path.exists()
        records = [
            json.loads(line)
            for line in ceo_memory_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(records) > 0
        design_records = [r for r in records if r.get("domain") == "design"]
        assert len(design_records) > 0
        assert design_records[0]["action_type"] == "level_design"
        assert design_records[0]["success"] is True

    def test_multiple_design_documents(
        self, tmp_designer: GameDesignerAgent,
        sample_gdd_id: str, sample_gdd_id_match3: str
    ):
        """多个设计文档共存."""
        tmp_designer.create_design_document(sample_gdd_id)
        tmp_designer.create_design_document(sample_gdd_id_match3)
        docs = tmp_designer.list_design_documents()
        assert len(docs) == 2


# ═══════════════════════════════════════════════════════════════
# 4. API 端点测试
# ═══════════════════════════════════════════════════════════════


class TestGameDesignerAPI:
    """Game Designer API 端点."""

    @pytest.fixture
    def api_client(
        self, tmp_path: Path, monkeypatch, tmp_product: ProductManagerAgent
    ):
        """FastAPI TestClient + 临时数据目录 + 预生成 GDD."""
        data_dir = tmp_path / "data"
        for sub in ["growth_loop", "ceo/audit", "ceo/game_reality", "liveops",
                     "product", "design", "workspace"]:
            (data_dir / sub).mkdir(parents=True, exist_ok=True)
        (data_dir / "growth_loop" / "cycle_history.jsonl").write_text("", encoding="utf-8")

        from src.market_ops.workspace import app as app_module
        monkeypatch.setattr(app_module, "_PROJECT_ROOT", tmp_path)

        # 重置单例
        for attr in ["_instance"]:
            if hasattr(app_module._get_designer_agent, attr):
                delattr(app_module._get_designer_agent, attr)
            if hasattr(app_module._get_product_agent, attr):
                delattr(app_module._get_product_agent, attr)
            if hasattr(app_module._get_ceo_decision_center, attr):
                delattr(app_module._get_ceo_decision_center, attr)

        return TestClient(app_module.app)

    def _ensure_gdd(self, api_client: TestClient) -> str:
        """通过 API 生成 GDD 并返回 gdd_id."""
        resp = api_client.post("/api/product/prd", json={
            "genre": "Merge", "budget_usd": 500000.0, "timeline_months": 6,
        })
        prd_id = resp.json()["prd_id"]
        resp = api_client.post(f"/api/product/gdd/{prd_id}")
        return resp.json()["gdd_id"]

    def test_design_levels_api(self, api_client: TestClient):
        """关卡设计 API."""
        gdd_id = self._ensure_gdd(api_client)
        resp = api_client.post(f"/api/designer/levels/{gdd_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["gdd_id"] == gdd_id
        assert data["total_levels"] == 200

    def test_balance_economy_api(self, api_client: TestClient):
        """经济平衡 API."""
        gdd_id = self._ensure_gdd(api_client)
        resp = api_client.post(f"/api/designer/economy/{gdd_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["currencies"]) == 3
        assert data["sink_to_faucet_ratio"] > 1.0

    def test_specify_systems_api(self, api_client: TestClient):
        """系统规格 API."""
        gdd_id = self._ensure_gdd(api_client)
        resp = api_client.post(f"/api/designer/systems/{gdd_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["system_count"] > 0
        assert len(data["systems"]) > 0

    def test_generate_difficulty_api(self, api_client: TestClient):
        """难度曲线 API."""
        gdd_id = self._ensure_gdd(api_client)
        resp = api_client.post(f"/api/designer/difficulty/{gdd_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["stages"]) == 5

    def test_create_design_document_api(self, api_client: TestClient):
        """完整设计文档 API."""
        gdd_id = self._ensure_gdd(api_client)
        resp = api_client.post(f"/api/designer/document/{gdd_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ready_for_dev"] is True
        assert data["level_design"]["total_levels"] > 0

    def test_list_design_documents_api(self, api_client: TestClient):
        """设计文档列表 API."""
        gdd_id = self._ensure_gdd(api_client)
        api_client.post(f"/api/designer/document/{gdd_id}")
        resp = api_client.get("/api/designer/documents")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_get_design_document_api(self, api_client: TestClient):
        """设计文档详情 API."""
        gdd_id = self._ensure_gdd(api_client)
        create_resp = api_client.post(f"/api/designer/document/{gdd_id}")
        doc_id = create_resp.json()["document_id"]
        resp = api_client.get(f"/api/designer/documents/{doc_id}")
        assert resp.status_code == 200
        assert resp.json()["document_id"] == doc_id

    def test_get_design_document_not_found_api(self, api_client: TestClient):
        """查询不存在的设计文档返回 404."""
        resp = api_client.get("/api/designer/documents/doc_nonexistent")
        assert resp.status_code == 404

    def test_designer_stats_api(self, api_client: TestClient):
        """设计统计 API."""
        gdd_id = self._ensure_gdd(api_client)
        api_client.post(f"/api/designer/document/{gdd_id}")
        resp = api_client.get("/api/designer/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_design_documents"] == 1
        assert data["ready_for_dev_count"] == 1

    def test_design_levels_gdd_not_found_api(self, api_client: TestClient):
        """GDD 不存在时返回 404."""
        resp = api_client.post("/api/designer/levels/gdd_nonexistent")
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════
# 5. AgentRegistry 组织架构注册测试
# ═══════════════════════════════════════════════════════════════


class TestGameDesignerRegistry:
    """Game Designer Agent 在 AgentRegistry 组织架构中的注册."""

    def test_designer_registered_in_default_organization(self):
        """默认组织包含 Game Designer Agent."""
        from src.market_ops.creative_vision_runtime.growth_runtime.agent.communication.agent_registry import (
            create_default_organization,
        )
        registry = create_default_organization()
        all_records = registry.get_all()
        designer_records = [r for r in all_records if r.identity.role.value == "designer"]
        assert len(designer_records) == 1

    def test_designer_has_level_design_capability(self):
        """Designer Agent 包含关卡设计能力."""
        from src.market_ops.creative_vision_runtime.growth_runtime.agent.communication.agent_message import (
            create_game_designer_agent_identity,
        )
        identity = create_game_designer_agent_identity()
        assert "level_design" in identity.capabilities
        assert "economy_balance" in identity.capabilities
        assert "system_specification" in identity.capabilities
        assert "difficulty_curve" in identity.capabilities

    def test_find_designer_by_capability(self):
        """能通过系统规格能力查找到 Designer Agent（该能力仅 Designer 拥有）."""
        from src.market_ops.creative_vision_runtime.growth_runtime.agent.communication.agent_registry import (
            create_default_organization,
        )
        registry = create_default_organization()
        found = registry.find_by_capability("system_specification")
        assert len(found) == 1
        assert found[0].identity.role.value == "designer"

    def test_default_organization_has_ten_agents(self):
        """默认组织包含 10 个 Agent (含 DataAnalyst + PlayerSupport)."""
        from src.market_ops.creative_vision_runtime.growth_runtime.agent.communication.agent_registry import (
            create_default_organization,
        )
        registry = create_default_organization()
        all_records = registry.get_all()
        assert len(all_records) == 10
        roles = {r.identity.role.value for r in all_records}
        assert roles == {"supervisor", "ua", "creative", "monetization",
                         "product", "liveops", "designer", "numerical",
                         "data_analyst", "player_support"}

    def test_designer_visible_in_workspace_snapshot(self, tmp_path: Path):
        """Designer Agent 在 Workspace 快照中可见."""
        from src.market_ops.workspace import agent_registry_store
        snapshot_path = tmp_path / "agents.jsonl"
        records = agent_registry_store.create_default_agents_snapshot(snapshot_path)
        assert len(records) == 10
        designer_records = [
            r for r in records
            if (r.get("identity", {}) or {}).get("role") == "designer"
        ]
        assert len(designer_records) == 1
        capabilities = designer_records[0]["identity"]["capabilities"]
        assert "level_design" in capabilities

    def test_designer_department_is_design(self):
        """Designer Agent 映射到 Design 部门."""
        from src.market_ops.workspace.real_provider import _ROLE_TO_DEPARTMENT
        assert _ROLE_TO_DEPARTMENT.get("designer") == "Design"
