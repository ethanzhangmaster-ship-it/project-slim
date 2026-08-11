"""LiveOps Agent 单元测试.

覆盖 Spec §4.1-§4.9 验收标准:
  §4.1 LiveOpsAgent.analyze_churn_risk 返回完整 ChurnAnalysis
  §4.2 LiveOpsAgent.design_winback_campaign 返回 WinbackCampaign
  §4.3 回流活动方案基于流失分群自动选择类型
  §4.4 AgentRegistry 能注册和发现 liveops 角色
  §4.5 workspace /api/agents 返回 LiveOps Agent
  §4.6 GET /api/liveops/churn-analysis/{game_id} 返回 200
  §4.7 POST /api/liveops/winback-campaign 返回 200 + 活动方案
  §4.9 单元测试覆盖（≥15 个用例）
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


# ═══════════════════════════════════════════════════════════════
# Helpers — 构造 mock 依赖
# ═══════════════════════════════════════════════════════════════


@dataclass
class _MockSegment:
    user_id: str
    segment: str
    value_score: float   # 0..100
    churn_risk: float    # 0..1
    ad_tolerance: str = "medium"
    confidence: float = 0.5


class _MockSegmenter:
    """可控分群器 — 按 user_id 前缀决定 segment."""

    def __init__(self, mapping: dict[str, str] | None = None) -> None:
        self.mapping = mapping or {}

    def classify(self, profile):
        uid = profile.user_id
        seg_name = self.mapping.get(uid, "moderate_ad_player")
        # at_risk_churn 给高 value_score 以测试 high_value_at_risk
        value_score = 80 if seg_name == "at_risk_churn" else 40
        risk = 0.7 if seg_name == "at_risk_churn" else 0.1
        return _MockSegment(
            user_id=uid, segment=seg_name,
            value_score=value_score, churn_risk=risk,
        )


class _MockDetector:
    """可控生命周期检测器 — 按 user_id 前缀决定 stage."""

    def __init__(self, mapping: dict[str, str] | None = None) -> None:
        self.mapping = mapping or {}

    def stage(self, profile, days_since_last_active=None):
        return self.mapping.get(profile.user_id, "ENGAGED")


class _MockCollector:
    """可控事件收集器 — 返回预设的 profile 列表."""

    def __init__(self, profiles: list) -> None:
        self.profiles = profiles

    def collect(self, app_id="", start="", end=""):
        return list(self.profiles)


def _make_profile(user_id: str, **kwargs):
    """构造一个 PlayerProfile (从 operation.player_monetization.models 导入)."""
    from operation.player_monetization.models import PlayerProfile
    defaults = {
        "user_id": user_id,
        "country": "US",
        "level": 10,
        "session_count": 5,
        "days_active": 5,
        "active": True,
        "fail_rate": 0.1,
        "total_ad_revenue": 0.5,
        "reward_accept_rate": 0.6,
    }
    defaults.update(kwargs)
    return PlayerProfile(**defaults)


# ═══════════════════════════════════════════════════════════════
# §4.1-§4.3, §4.9: LiveOpsAgent 核心方法测试
# ═══════════════════════════════════════════════════════════════


class TestLiveOpsAgentCore:
    """LiveOpsAgent 核心方法测试."""

    def _make_agent(self, tmp_path: Path, profiles=None, seg_map=None, stage_map=None):
        from src.market_ops.workspace.liveops_agent import LiveOpsAgent
        return LiveOpsAgent(
            data_dir=str(tmp_path / "data"),
            collector=_MockCollector(profiles or []),
            detector=_MockDetector(stage_map or {}),
            segmenter=_MockSegmenter(seg_map or {}),
        )

    def test_analyze_churn_risk_returns_complete_analysis(self, tmp_path):
        """§4.1 analyze_churn_risk 返回完整 ChurnAnalysis."""
        # 3 个用户: 1 at_risk, 1 churning, 1 engaged
        profiles = [
            _make_profile("u1"),
            _make_profile("u2"),
            _make_profile("u3"),
        ]
        seg_map = {"u1": "at_risk_churn", "u2": "moderate_ad_player", "u3": "power_user"}
        stage_map = {"u1": "CHURNING", "u2": "ENGAGED", "u3": "ENGAGED"}
        agent = self._make_agent(tmp_path, profiles, seg_map, stage_map)

        analysis = agent.analyze_churn_risk("game_x")

        assert analysis.game_id == "game_x"
        assert analysis.total_players == 3
        assert analysis.at_risk_count == 1
        assert analysis.churning_count == 1
        assert analysis.lapsed_count == 0
        assert analysis.segments["at_risk_churn"] == 1
        assert analysis.segments["moderate_ad_player"] == 1
        assert analysis.lifecycle_stages["CHURNING"] == 1
        assert analysis.high_value_at_risk == 1  # at_risk_churn 的 value_score=80 >= 0.5
        assert 0.0 <= analysis.avg_churn_risk <= 1.0

    def test_analyze_churn_risk_with_empty_profiles(self, tmp_path):
        """§4.1 无用户时返回空分析 (不报错)."""
        agent = self._make_agent(tmp_path, profiles=[])
        analysis = agent.analyze_churn_risk("empty_game")
        assert analysis.total_players == 0
        assert analysis.at_risk_count == 0
        assert analysis.avg_churn_risk == 0.0
        assert analysis.segments == {}

    def test_analyze_churn_risk_persists_to_jsonl(self, tmp_path):
        """§4.1 分析结果持久化到 JSONL."""
        agent = self._make_agent(tmp_path, profiles=[_make_profile("u1")])
        agent.analyze_churn_risk("persist_game")
        analysis_path = tmp_path / "data" / "liveops" / "churn_analysis" / "persist_game.jsonl"
        assert analysis_path.exists()
        import json
        lines = analysis_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["game_id"] == "persist_game"

    def test_design_winback_campaign_returns_campaign(self, tmp_path):
        """§4.2 design_winback_campaign 返回 WinbackCampaign."""
        from src.market_ops.workspace.liveops_agent import ChurnAnalysis
        agent = self._make_agent(tmp_path)
        analysis = ChurnAnalysis(
            game_id="game_y", analysis_date="2026-08-07",
            total_players=100, at_risk_count=20, lapsed_count=0, churning_count=0,
            avg_churn_risk=0.3, segments={"at_risk_churn": 20},
            lifecycle_stages={"CHURNING": 20}, high_value_at_risk=5,
        )
        campaign = agent.design_winback_campaign("game_y", analysis)

        assert campaign.game_id == "game_y"
        assert campaign.campaign_id.startswith("wb-game_y-")
        assert campaign.campaign_type == "login_bonus"  # at_risk_churn → login_bonus
        assert campaign.target_segment == "at_risk_churn"
        assert campaign.target_count == 20
        assert campaign.rewards_pool > 0
        assert len(campaign.actions) > 0
        assert campaign.created_at != ""

    def test_design_winback_campaign_selects_login_bonus_for_at_risk(self, tmp_path):
        """§4.3 at_risk_churn 分群 → login_bonus 活动类型."""
        from src.market_ops.workspace.liveops_agent import ChurnAnalysis
        agent = self._make_agent(tmp_path)
        analysis = ChurnAnalysis(
            game_id="g", analysis_date="",
            total_players=50, at_risk_count=10, lapsed_count=0, churning_count=0,
            avg_churn_risk=0.2, segments={}, lifecycle_stages={}, high_value_at_risk=0,
        )
        campaign = agent.design_winback_campaign("g", analysis)
        assert campaign.campaign_type == "login_bonus"
        assert campaign.target_segment == "at_risk_churn"

    def test_design_winback_campaign_selects_special_offer_for_churning(self, tmp_path):
        """§4.3 churning 分群 → special_offer 活动类型."""
        from src.market_ops.workspace.liveops_agent import ChurnAnalysis
        agent = self._make_agent(tmp_path)
        analysis = ChurnAnalysis(
            game_id="g", analysis_date="",
            total_players=50, at_risk_count=10, lapsed_count=0, churning_count=15,
            avg_churn_risk=0.3, segments={}, lifecycle_stages={}, high_value_at_risk=0,
        )
        campaign = agent.design_winback_campaign("g", analysis)
        assert campaign.campaign_type == "special_offer"
        assert campaign.target_segment == "churning"
        assert campaign.target_count == 15

    def test_design_winback_campaign_selects_push_for_lapsed(self, tmp_path):
        """§4.3 lapsed 分群 → push_re-engagement 活动类型."""
        from src.market_ops.workspace.liveops_agent import ChurnAnalysis
        agent = self._make_agent(tmp_path)
        analysis = ChurnAnalysis(
            game_id="g", analysis_date="",
            total_players=50, at_risk_count=10, lapsed_count=5, churning_count=15,
            avg_churn_risk=0.3, segments={}, lifecycle_stages={}, high_value_at_risk=0,
        )
        campaign = agent.design_winback_campaign("g", analysis)
        assert campaign.campaign_type == "push_re-engagement"
        assert campaign.target_segment == "lapsed"
        assert campaign.target_count == 5

    def test_design_winback_campaign_with_no_churn_users(self, tmp_path):
        """§4.3 无流失用户时生成预防性方案 (at_risk_churn)."""
        from src.market_ops.workspace.liveops_agent import ChurnAnalysis
        agent = self._make_agent(tmp_path)
        analysis = ChurnAnalysis(
            game_id="g", analysis_date="",
            total_players=100, at_risk_count=0, lapsed_count=0, churning_count=0,
            avg_churn_risk=0.0, segments={}, lifecycle_stages={}, high_value_at_risk=0,
        )
        campaign = agent.design_winback_campaign("g", analysis)
        assert campaign.target_segment == "at_risk_churn"
        assert campaign.target_count == 10  # total_players // 10
        assert campaign.campaign_type == "login_bonus"

    def test_design_winback_campaign_persists_campaign(self, tmp_path):
        """§4.2 活动方案持久化到 JSONL."""
        from src.market_ops.workspace.liveops_agent import ChurnAnalysis
        agent = self._make_agent(tmp_path)
        analysis = ChurnAnalysis(
            game_id="g", analysis_date="",
            total_players=10, at_risk_count=3, lapsed_count=0, churning_count=0,
            avg_churn_risk=0.2, segments={}, lifecycle_stages={}, high_value_at_risk=0,
        )
        campaign = agent.design_winback_campaign("g", analysis)
        campaigns_path = tmp_path / "data" / "liveops" / "campaigns.jsonl"
        assert campaigns_path.exists()
        loaded = agent.get_campaign(campaign.campaign_id)
        assert loaded is not None
        assert loaded.campaign_type == campaign.campaign_type

    def test_evaluate_campaign_returns_evaluation(self, tmp_path):
        """§4.2 evaluate_campaign 返回评估结果."""
        from src.market_ops.workspace.liveops_agent import ChurnAnalysis
        agent = self._make_agent(tmp_path)
        analysis = ChurnAnalysis(
            game_id="g", analysis_date="",
            total_players=100, at_risk_count=20, lapsed_count=0, churning_count=0,
            avg_churn_risk=0.2, segments={}, lifecycle_stages={}, high_value_at_risk=0,
        )
        campaign = agent.design_winback_campaign("g", analysis)
        evaluation = agent.evaluate_campaign(campaign.campaign_id)

        assert evaluation.campaign_id == campaign.campaign_id
        assert 0.0 <= evaluation.participation_rate <= 1.0
        assert evaluation.retention_uplift > 0
        assert evaluation.player_satisfaction >= 0.5

    def test_evaluate_campaign_unknown_returns_zeros(self, tmp_path):
        """§4.2 未知 campaign_id 返回零值评估."""
        agent = self._make_agent(tmp_path)
        evaluation = agent.evaluate_campaign("nonexistent-id")
        assert evaluation.participation_rate == 0.0
        assert evaluation.retention_uplift == 0.0
        assert evaluation.revenue_uplift == 0.0

    def test_list_campaigns_filters_by_game(self, tmp_path):
        """§4.2 list_campaigns 按 game_id 过滤."""
        from src.market_ops.workspace.liveops_agent import ChurnAnalysis
        agent = self._make_agent(tmp_path)
        # 为两个游戏各生成一个活动
        for gid in ["game_a", "game_b"]:
            analysis = ChurnAnalysis(
                game_id=gid, analysis_date="",
                total_players=10, at_risk_count=2, lapsed_count=0, churning_count=0,
                avg_churn_risk=0.1, segments={}, lifecycle_stages={}, high_value_at_risk=0,
            )
            agent.design_winback_campaign(gid, analysis)

        all_campaigns = agent.list_campaigns()
        assert len(all_campaigns) == 2
        game_a = agent.list_campaigns(game_id="game_a")
        assert len(game_a) == 1
        assert game_a[0].game_id == "game_a"

    def test_config_high_value_threshold(self, tmp_path):
        """§4.9 配置驱动的 high_value_threshold."""
        from src.market_ops.workspace.liveops_agent import (
            LiveOpsAgent, WinbackCampaignConfig,
        )
        # 降低阈值到 0.3，则 value_score=40 的用户也算高价值
        config = WinbackCampaignConfig(high_value_threshold=0.3)
        profiles = [_make_profile("u1")]
        agent = LiveOpsAgent(
            data_dir=str(tmp_path / "data"),
            collector=_MockCollector(profiles),
            detector=_MockDetector({"u1": "CHURNING"}),
            segmenter=_MockSegmenter({"u1": "at_risk_churn"}),  # value_score=80
            config=config,
        )
        analysis = agent.analyze_churn_risk("g")
        # value_score=80 → 0.8 >= 0.3, 应计入 high_value_at_risk
        assert analysis.high_value_at_risk == 1


# ═══════════════════════════════════════════════════════════════
# §4.4: AgentRegistry 注册测试
# ═══════════════════════════════════════════════════════════════


class TestLiveOpsAgentRegistry:
    """§4.4 AgentRegistry 能注册和发现 liveops 角色."""

    def test_create_default_organization_includes_liveops(self):
        """create_default_organization 注册 LiveOps Agent."""
        from src.market_ops.creative_vision_runtime.growth_runtime.agent.communication.agent_message import (
            AgentRole,
        )
        from src.market_ops.creative_vision_runtime.growth_runtime.agent.communication.agent_registry import (
            create_default_organization,
        )
        registry = create_default_organization()
        liveops_agents = registry.find_by_role(AgentRole.LIVEOPS)
        assert len(liveops_agents) == 1
        assert liveops_agents[0].identity.name == "LiveOps Agent"

    def test_find_by_role_liveops(self):
        """find_by_role(LIVEOPS) 返回 LiveOps Agent."""
        from src.market_ops.creative_vision_runtime.growth_runtime.agent.communication.agent_message import (
            AgentRole, create_liveops_agent_identity,
        )
        from src.market_ops.creative_vision_runtime.growth_runtime.agent.communication.agent_registry import (
            create_agent_registry,
        )
        registry = create_agent_registry()
        registry.register(create_liveops_agent_identity())
        found = registry.find_by_role(AgentRole.LIVEOPS)
        assert len(found) == 1
        assert "churn_analysis" in found[0].identity.capabilities

    def test_create_liveops_agent_identity(self):
        """create_liveops_agent_identity 返回正确身份."""
        from src.market_ops.creative_vision_runtime.growth_runtime.agent.communication.agent_message import (
            AgentRole, create_liveops_agent_identity,
        )
        identity = create_liveops_agent_identity()
        assert identity.role == AgentRole.LIVEOPS
        assert identity.name == "LiveOps Agent"
        assert "winback_campaign_design" in identity.capabilities
        assert len(identity.capabilities) == 5


# ═══════════════════════════════════════════════════════════════
# §4.5-§4.7: Workspace API 测试
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def workspace_env(tmp_path: Path, monkeypatch):
    """设置 Workspace 测试环境 (参考 test_ceo_daily_run.py)."""
    monkeypatch.setenv("WORKSPACE_DATA_PROVIDER", "mock")

    data_dir = tmp_path / "data"
    liveops_dir = data_dir / "liveops"
    liveops_dir.mkdir(parents=True, exist_ok=True)

    # Monkeypatch app.py 路径 — 让 LiveOpsAgent 用 tmp_path/data
    from src.market_ops.workspace import app as app_module
    monkeypatch.setattr(app_module, "_PROJECT_ROOT", tmp_path)

    # Monkeypatch real_provider 路径常量 (避免读取真实数据)
    from src.market_ops.workspace import real_provider as rp
    monkeypatch.setattr(rp, "_real_provider", None)

    # Monkeypatch agent_registry_store 路径 (避免读取真实快照)
    from src.market_ops.workspace import agent_registry_store as store
    monkeypatch.setattr(store, "AGENTS_SNAPSHOT_PATH", tmp_path / "data" / "workspace" / "agents.jsonl")

    return {"data_dir": data_dir, "tmp_path": tmp_path}


@pytest.fixture
def client(workspace_env):
    """FastAPI TestClient (mock 模式)."""
    from src.market_ops.workspace.app import app
    from src.market_ops.workspace import aggregator as agg_module
    agg_module._aggregator = None
    return TestClient(app)


class TestLiveOpsAPI:
    """§4.5-§4.7 LiveOps API 端点测试."""

    def test_get_agents_returns_liveops(self, client):
        """§4.5 /api/agents 返回 LiveOps Agent (mock 模式)."""
        resp = client.get("/api/agents")
        assert resp.status_code == 200
        agents = resp.json()
        liveops = [a for a in agents if a.get("department") == "LiveOps"]
        assert len(liveops) == 1
        assert liveops[0]["name"] == "LiveOps Agent"
        assert "Churn Analysis" in liveops[0]["capabilities"]

    def test_get_churn_analysis_returns_200(self, client):
        """§4.6 GET /api/liveops/churn-analysis/{game_id} 返回 200."""
        resp = client.get("/api/liveops/churn-analysis/test_game")
        assert resp.status_code == 200
        data = resp.json()
        assert data["game_id"] == "test_game"
        assert "total_players" in data
        assert "at_risk_count" in data
        assert "segments" in data
        assert "lifecycle_stages" in data

    def test_design_winback_campaign_returns_200(self, client):
        """§4.7 POST /api/liveops/winback-campaign 返回 200 + 活动方案."""
        # 先设计一个带 analysis 的活动 (不依赖 player_monetization 数据)
        body = {
            "game_id": "test_game",
            "analysis": {
                "game_id": "test_game",
                "analysis_date": "2026-08-07",
                "total_players": 100,
                "at_risk_count": 15,
                "lapsed_count": 5,
                "churning_count": 10,
                "avg_churn_risk": 0.25,
                "segments": {"at_risk_churn": 15},
                "lifecycle_stages": {"LAPSED": 5, "CHURNING": 10},
                "high_value_at_risk": 3,
            },
        }
        resp = client.post("/api/liveops/winback-campaign", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["game_id"] == "test_game"
        assert data["campaign_type"] == "push_re-engagement"  # lapsed 优先级最高
        assert data["target_segment"] == "lapsed"
        assert data["target_count"] == 5
        assert len(data["actions"]) > 0
        assert data["campaign_id"].startswith("wb-test_game-")

    def test_design_winback_campaign_without_analysis(self, client):
        """§4.7 不传 analysis 时自动调用 analyze_churn_risk."""
        resp = client.post("/api/liveops/winback-campaign", json={"game_id": "auto_game"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["game_id"] == "auto_game"
        # 无玩家数据时生成预防性方案
        assert data["campaign_type"] == "login_bonus"

    def test_list_campaigns_returns_200(self, client):
        """§4.7 GET /api/liveops/campaigns 返回活动列表."""
        # 先创建一个活动
        client.post("/api/liveops/winback-campaign", json={
            "game_id": "list_game",
            "analysis": {
                "game_id": "list_game", "analysis_date": "",
                "total_players": 10, "at_risk_count": 2,
                "lapsed_count": 0, "churning_count": 0,
                "avg_churn_risk": 0.1, "segments": {}, "lifecycle_stages": {},
                "high_value_at_risk": 0,
            },
        })
        resp = client.get("/api/liveops/campaigns")
        assert resp.status_code == 200
        campaigns = resp.json()
        assert len(campaigns) >= 1
        assert any(c["game_id"] == "list_game" for c in campaigns)

    def test_list_campaigns_filter_by_game(self, client):
        """§4.7 GET /api/liveops/campaigns?game_id=xxx 按游戏过滤."""
        for gid in ["filter_a", "filter_b"]:
            client.post("/api/liveops/winback-campaign", json={
                "game_id": gid,
                "analysis": {
                    "game_id": gid, "analysis_date": "",
                    "total_players": 10, "at_risk_count": 2,
                    "lapsed_count": 0, "churning_count": 0,
                    "avg_churn_risk": 0.1, "segments": {}, "lifecycle_stages": {},
                    "high_value_at_risk": 0,
                },
            })
        resp = client.get("/api/liveops/campaigns?game_id=filter_a")
        assert resp.status_code == 200
        campaigns = resp.json()
        assert len(campaigns) == 1
        assert campaigns[0]["game_id"] == "filter_a"

    def test_get_campaign_returns_200(self, client):
        """§4.7 GET /api/liveops/campaigns/{id} 返回活动详情."""
        create = client.post("/api/liveops/winback-campaign", json={
            "game_id": "detail_game",
            "analysis": {
                "game_id": "detail_game", "analysis_date": "",
                "total_players": 10, "at_risk_count": 2,
                "lapsed_count": 0, "churning_count": 0,
                "avg_churn_risk": 0.1, "segments": {}, "lifecycle_stages": {},
                "high_value_at_risk": 0,
            },
        })
        campaign_id = create.json()["campaign_id"]
        resp = client.get(f"/api/liveops/campaigns/{campaign_id}")
        assert resp.status_code == 200
        assert resp.json()["campaign_id"] == campaign_id

    def test_get_campaign_unknown_returns_404(self, client):
        """§4.7 未知 campaign_id 返回 404."""
        resp = client.get("/api/liveops/campaigns/nonexistent")
        assert resp.status_code == 404

    def test_evaluate_campaign_returns_200(self, client):
        """§4.7 POST /api/liveops/campaigns/{id}/evaluate 返回评估."""
        create = client.post("/api/liveops/winback-campaign", json={
            "game_id": "eval_game",
            "analysis": {
                "game_id": "eval_game", "analysis_date": "",
                "total_players": 100, "at_risk_count": 20,
                "lapsed_count": 0, "churning_count": 0,
                "avg_churn_risk": 0.2, "segments": {}, "lifecycle_stages": {},
                "high_value_at_risk": 0,
            },
        })
        campaign_id = create.json()["campaign_id"]
        resp = client.post(f"/api/liveops/campaigns/{campaign_id}/evaluate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["campaign_id"] == campaign_id
        assert "participation_rate" in data
        assert "campaign" in data

    def test_evaluate_campaign_unknown_returns_404(self, client):
        """§4.7 评估未知 campaign_id 返回 404."""
        resp = client.post("/api/liveops/campaigns/nonexistent/evaluate")
        assert resp.status_code == 404

    def test_organization_includes_liveops_department(self, client):
        """§4.5 组织架构树包含 LiveOps 部门."""
        resp = client.get("/api/organization")
        assert resp.status_code == 200
        org = resp.json()
        dept_names = [c["name"] for c in org.get("children", [])]
        assert "LiveOps Department" in dept_names
