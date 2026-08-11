"""MetaAdsDataFetcher 单元测试 + /api/loop/trigger fetch_meta_ads 集成测试.

测试覆盖:
  1. MetaAdsDataFetcher 基础功能: is_configured / 构造函数参数优先级
  2. fetch() 未配置场景: 返回 fetch_error
  3. fetch() 异常处理: _do_fetch 抛异常时不传播, 返回 fetch_error
  4. _do_fetch() 数据流编排: mock 底层模块, 验证 GrowthLoopInput 字段
  5. _do_fetch() 空数据: current_rows 为空时返回 fetch_error
  6. _do_fetch() RealityGate 失败: 审计异常不阻塞, 仍返回数据
  7. API /api/loop/trigger fetch_meta_ads=true 未配置 → 400
  8. API /api/loop/trigger fetch_meta_ads=true + fetch_error → 200 含错误信息
  9. API /api/loop/trigger fetch_meta_ads=true + 正常数据 → 200 含 meta_ads_data
  10. API /api/loop/trigger live 模式注入 MetaAdsPlatformAdapter

设计原则:
  - 全部使用 tmp_path, 绝不污染 data/
  - 用 patch.dict(sys.modules) mock 重依赖模块 (run_growth_loop 等)
  - 用 mock 替换 GrowthLoopOrchestrator.run_cycle
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ── 1. MetaAdsDataFetcher 基础功能 ──────────────────────────


class TestMetaAdsDataFetcherConfig:
    """MetaAdsDataFetcher 配置和 is_configured 测试."""

    def test_is_configured_false_when_no_env(self, monkeypatch):
        """未设置环境变量时 is_configured 应返回 False."""
        monkeypatch.delenv("META_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("META_AD_ACCOUNT_ID", raising=False)
        from src.market_ops.workspace.meta_ads_fetcher import MetaAdsDataFetcher

        fetcher = MetaAdsDataFetcher()
        assert fetcher.is_configured() is False

    def test_is_configured_true_when_env_set(self, monkeypatch):
        """环境变量齐全时 is_configured 应返回 True."""
        monkeypatch.setenv("META_ACCESS_TOKEN", "test_token_123")
        monkeypatch.setenv("META_AD_ACCOUNT_ID", "act_123456")
        from src.market_ops.workspace.meta_ads_fetcher import MetaAdsDataFetcher

        fetcher = MetaAdsDataFetcher()
        assert fetcher.is_configured() is True

    def test_is_configured_false_when_only_token(self, monkeypatch):
        """只有 token 没有 ad_account_id 时应返回 False."""
        monkeypatch.setenv("META_ACCESS_TOKEN", "test_token_123")
        monkeypatch.delenv("META_AD_ACCOUNT_ID", raising=False)
        from src.market_ops.workspace.meta_ads_fetcher import MetaAdsDataFetcher

        fetcher = MetaAdsDataFetcher()
        assert fetcher.is_configured() is False

    def test_constructor_params_override_env(self, monkeypatch):
        """显式构造参数应优先于环境变量."""
        monkeypatch.setenv("META_ACCESS_TOKEN", "env_token")
        monkeypatch.setenv("META_AD_ACCOUNT_ID", "env_account")
        monkeypatch.setenv("META_API_VERSION", "v20.0")
        monkeypatch.setenv("DEFAULT_GAME_NAME", "EnvGame")
        from src.market_ops.workspace.meta_ads_fetcher import MetaAdsDataFetcher

        fetcher = MetaAdsDataFetcher(
            access_token="explicit_token",
            ad_account_id="explicit_account",
            api_version="v22.0",
            game_name="ExplicitGame",
        )
        assert fetcher.access_token == "explicit_token"
        assert fetcher.ad_account_id == "explicit_account"
        assert fetcher.api_version == "v22.0"
        assert fetcher.game_name == "ExplicitGame"

    def test_default_api_version_and_game_name(self, monkeypatch):
        """未提供 api_version 和 game_name 时使用默认值."""
        monkeypatch.delenv("META_API_VERSION", raising=False)
        monkeypatch.delenv("DEFAULT_GAME_NAME", raising=False)
        from src.market_ops.workspace.meta_ads_fetcher import MetaAdsDataFetcher

        fetcher = MetaAdsDataFetcher(access_token="t", ad_account_id="a")
        assert fetcher.api_version == "v22.0"
        assert fetcher.game_name == "P04"


# ── 2. fetch() 未配置和异常处理 ──────────────────────────────


class TestMetaAdsDataFetcherFetch:
    """MetaAdsDataFetcher.fetch() 行为测试."""

    def test_fetch_returns_error_when_not_configured(self, monkeypatch):
        """未配置时 fetch 应返回带 fetch_error 的 GrowthLoopInput."""
        monkeypatch.delenv("META_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("META_AD_ACCOUNT_ID", raising=False)
        from src.market_ops.workspace.meta_ads_fetcher import (
            GrowthLoopInput,
            MetaAdsDataFetcher,
        )

        fetcher = MetaAdsDataFetcher()
        result = fetcher.fetch(days=7)

        assert isinstance(result, GrowthLoopInput)
        assert result.fetch_error is not None
        assert "META_ACCESS_TOKEN" in result.fetch_error
        assert result.signals == []
        assert result.current_metrics == {}

    def test_fetch_catches_exception_and_returns_error(self, monkeypatch):
        """_do_fetch 抛异常时 fetch 应捕获并返回 fetch_error."""
        monkeypatch.setenv("META_ACCESS_TOKEN", "tok")
        monkeypatch.setenv("META_AD_ACCOUNT_ID", "acct")
        from src.market_ops.workspace.meta_ads_fetcher import (
            GrowthLoopInput,
            MetaAdsDataFetcher,
        )

        fetcher = MetaAdsDataFetcher()

        with patch.object(
            fetcher, "_do_fetch", side_effect=RuntimeError("API timeout")
        ):
            result = fetcher.fetch(days=7)

        assert isinstance(result, GrowthLoopInput)
        assert result.fetch_error == "API timeout"
        assert result.signals == []


# ── 3. _do_fetch() 数据流编排 ────────────────────────────────


class TestMetaAdsDataFetcherDoFetch:
    """MetaAdsDataFetcher._do_fetch() 数据流测试.

    使用 patch.dict(sys.modules) 注入 mock 模块, 避免加载重依赖.
    """

    @staticmethod
    def _make_mock_modules():
        """创建 mock 模块集合, 配置合理的返回值."""
        mock_rgl = MagicMock()  # run_growth_loop
        mock_rfb = MagicMock()  # run_feedback_bridge
        mock_feedback = MagicMock()  # market_ops.creative_vision_runtime.reality.feedback
        mock_exp_store = MagicMock()  # ...meta_learning.experience_store

        # load_meta_ads_data 返回 (current_rows, previous_rows)
        current_rows = [MagicMock(creative_id="c1"), MagicMock(creative_id="c2")]
        previous_rows = [MagicMock(creative_id="c1")]
        mock_rgl.load_meta_ads_data.return_value = (current_rows, previous_rows)

        # aggregate_by_creative 返回指标字典
        current_metrics = {
            "c1": {"spend": 100.0, "clicks": 50, "impressions": 1000, "installs": 10},
            "c2": {"spend": 50.0, "clicks": 25, "impressions": 500, "installs": 5},
        }
        previous_metrics = {
            "c1": {"spend": 80.0, "clicks": 40, "impressions": 800, "installs": 8},
        }
        mock_rfb.aggregate_by_creative.side_effect = [current_metrics, previous_metrics]

        # build_creative_to_adset_map
        creative_to_adset = {"c1": "adset_1", "c2": "adset_2"}
        mock_rgl.build_creative_to_adset_map.return_value = creative_to_adset

        # estimate_current_budgets
        current_budgets = {"adset_1": 100.0, "adset_2": 50.0}
        mock_rgl.estimate_current_budgets.return_value = current_budgets

        # generate_predictions
        predictions = [MagicMock(), MagicMock(), MagicMock()]
        mock_rfb.generate_predictions.return_value = predictions

        # filter_actionable_signals (在 run_growth_loop 中定义)
        signals = [MagicMock(signal_type="budget_increase"),
                   MagicMock(signal_type="pause_creative")]
        mock_rgl.filter_actionable_signals.return_value = signals

        # run_reality_audit
        reality_scores = {"P04": MagicMock(composite=0.85, decision_level="full")}
        creative_to_game = {"c1": "P04", "c2": "P04"}
        mock_rgl.run_reality_audit.return_value = (reality_scores, creative_to_game)

        # make_game_id_resolver
        resolver = MagicMock(return_value="P04")
        mock_rgl.make_game_id_resolver.return_value = resolver

        return {
            "run_growth_loop": mock_rgl,
            "run_feedback_bridge": mock_rfb,
            "market_ops.creative_vision_runtime.reality.feedback": mock_feedback,
            "market_ops.creative_vision_runtime.reality.meta_learning.experience_store": mock_exp_store,
        }, {
            "current_metrics": current_metrics,
            "previous_metrics": previous_metrics,
            "creative_to_adset": creative_to_adset,
            "current_budgets": current_budgets,
            "signals": signals,
            "predictions": predictions,
            "reality_scores": reality_scores,
            "resolver": resolver,
        }

    def test_do_fetch_returns_correct_growth_loop_input(self, monkeypatch):
        """_do_fetch 应正确编排数据流并返回完整的 GrowthLoopInput."""
        monkeypatch.setenv("META_ACCESS_TOKEN", "tok")
        monkeypatch.setenv("META_AD_ACCOUNT_ID", "acct")
        from src.market_ops.workspace.meta_ads_fetcher import (
            GrowthLoopInput,
            MetaAdsDataFetcher,
        )

        mocks, expected = self._make_mock_modules()

        with patch.dict(sys.modules, mocks):
            fetcher = MetaAdsDataFetcher(access_token="tok", ad_account_id="acct")
            result = fetcher._do_fetch(days=7)

        assert isinstance(result, GrowthLoopInput)
        assert result.fetch_error is None
        assert result.signals == expected["signals"]
        assert result.current_metrics == expected["current_metrics"]
        assert result.previous_metrics == expected["previous_metrics"]
        assert result.creative_to_adset_map == expected["creative_to_adset"]
        assert result.current_budgets == expected["current_budgets"]
        assert result.reality_scores == expected["reality_scores"]
        assert result.game_id_resolver == expected["resolver"]
        assert result.creative_count == 2
        assert result.prediction_count == 3

    def test_do_fetch_calls_load_meta_ads_data_with_correct_args(self, monkeypatch):
        """_do_fetch 应使用正确的凭据和参数调用 load_meta_ads_data."""
        monkeypatch.setenv("META_ACCESS_TOKEN", "tok")
        monkeypatch.setenv("META_AD_ACCOUNT_ID", "acct")
        from src.market_ops.workspace.meta_ads_fetcher import MetaAdsDataFetcher

        mocks, _ = self._make_mock_modules()

        with patch.dict(sys.modules, mocks):
            fetcher = MetaAdsDataFetcher(
                access_token="my_token",
                ad_account_id="my_account",
                api_version="v22.0",
                game_name="MyGame",
            )
            fetcher._do_fetch(days=14)

        mocks["run_growth_loop"].load_meta_ads_data.assert_called_once_with(
            "my_token", "my_account", "v22.0", "MyGame", 14
        )

    def test_do_fetch_returns_error_when_no_current_rows(self, monkeypatch):
        """当前周期数据为空时应返回 fetch_error."""
        monkeypatch.setenv("META_ACCESS_TOKEN", "tok")
        monkeypatch.setenv("META_AD_ACCOUNT_ID", "acct")
        from src.market_ops.workspace.meta_ads_fetcher import (
            GrowthLoopInput,
            MetaAdsDataFetcher,
        )

        mocks, _ = self._make_mock_modules()
        # 修改: current_rows 为空
        mocks["run_growth_loop"].load_meta_ads_data.return_value = ([], [])

        with patch.dict(sys.modules, mocks):
            fetcher = MetaAdsDataFetcher(access_token="tok", ad_account_id="acct")
            result = fetcher._do_fetch(days=7)

        assert isinstance(result, GrowthLoopInput)
        assert result.fetch_error is not None
        assert "无数据" in result.fetch_error

    def test_do_fetch_reality_audit_failure_does_not_block(self, monkeypatch):
        """RealityGate 审计失败时应记录警告但不阻塞数据返回."""
        monkeypatch.setenv("META_ACCESS_TOKEN", "tok")
        monkeypatch.setenv("META_AD_ACCOUNT_ID", "acct")
        from src.market_ops.workspace.meta_ads_fetcher import (
            GrowthLoopInput,
            MetaAdsDataFetcher,
        )

        mocks, expected = self._make_mock_modules()
        # 修改: run_reality_audit 抛异常
        mocks["run_growth_loop"].run_reality_audit.side_effect = RuntimeError(
            "audit failed"
        )

        with patch.dict(sys.modules, mocks):
            fetcher = MetaAdsDataFetcher(access_token="tok", ad_account_id="acct")
            result = fetcher._do_fetch(days=7)

        assert isinstance(result, GrowthLoopInput)
        assert result.fetch_error is None
        # 数据仍然返回
        assert result.signals == expected["signals"]
        assert result.current_metrics == expected["current_metrics"]
        # RealityGate 相关字段为空
        assert result.reality_scores == {}
        assert result.game_id_resolver is None

    def test_do_fetch_aggregate_called_with_correct_rows(self, monkeypatch):
        """aggregate_by_creative 应分别用 current_rows 和 previous_rows 调用."""
        monkeypatch.setenv("META_ACCESS_TOKEN", "tok")
        monkeypatch.setenv("META_AD_ACCOUNT_ID", "acct")
        from src.market_ops.workspace.meta_ads_fetcher import MetaAdsDataFetcher

        mocks, _ = self._make_mock_modules()

        with patch.dict(sys.modules, mocks):
            fetcher = MetaAdsDataFetcher(access_token="tok", ad_account_id="acct")
            fetcher._do_fetch(days=7)

        mock_agg = mocks["run_feedback_bridge"].aggregate_by_creative
        assert mock_agg.call_count == 2


# ── 4. /api/loop/trigger fetch_meta_ads 集成测试 ─────────────


@pytest.fixture
def workspace_env(tmp_path: Path, monkeypatch):
    """设置 Workspace 测试环境: real provider + 临时数据目录."""
    monkeypatch.setenv("WORKSPACE_DATA_PROVIDER", "real")

    data_dir = tmp_path / "data"
    growth_loop_dir = data_dir / "growth_loop"
    ceo_dir = data_dir / "ceo"
    ceo_audit_dir = ceo_dir / "audit"
    game_reality_dir = ceo_dir / "game_reality"

    for d in [growth_loop_dir, ceo_audit_dir, game_reality_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # 创建最小测试数据
    _create_test_approval_queue(ceo_dir / "approval_queue.jsonl")
    _create_test_cycle_history(growth_loop_dir / "cycle_history.jsonl")
    _create_test_game_reality(game_reality_dir)
    _create_test_company_snapshot(ceo_dir / "company_snapshot.jsonl")

    # Monkeypatch real_provider 路径常量
    from src.market_ops.workspace import real_provider as rp

    monkeypatch.setattr(rp, "GROWTH_LOOP_HISTORY", growth_loop_dir / "cycle_history.jsonl")
    monkeypatch.setattr(rp, "CEO_DECISIONS_AUDIT", ceo_audit_dir / "decisions.jsonl")
    monkeypatch.setattr(rp, "CEO_APPROVAL_QUEUE", ceo_dir / "approval_queue.jsonl")
    monkeypatch.setattr(rp, "GAME_REALITY_DIR", game_reality_dir)
    monkeypatch.setattr(rp, "COMPANY_SNAPSHOT", ceo_dir / "company_snapshot.jsonl")
    monkeypatch.setattr(rp, "_real_provider", None)

    # Monkeypatch app.py 路径
    from src.market_ops.workspace import app as app_module

    monkeypatch.setattr(app_module, "_PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        app_module, "_GROWTH_LOOP_HISTORY", growth_loop_dir / "cycle_history.jsonl"
    )
    monkeypatch.setattr(
        app_module, "_EXECUTION_MEMORY", ceo_dir / "execution_memory.jsonl"
    )
    monkeypatch.setattr(
        app_module, "_EXECUTION_EXPERIENCE", ceo_dir / "execution_experience.jsonl"
    )
    monkeypatch.setattr(
        app_module, "_OPERATOR_MEMORY", ceo_dir / "operator_memory.jsonl"
    )

    # 确保 scripts 目录在 path 中
    scripts_dir = str(tmp_path.parent / "project_slim" / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    return {
        "data_dir": data_dir,
        "tmp_path": tmp_path,
    }


@pytest.fixture
def client(workspace_env):
    """FastAPI TestClient — 自动注入 real provider."""
    from src.market_ops.workspace.app import app
    from src.market_ops.workspace import aggregator as agg_module
    agg_module._aggregator = None
    return TestClient(app)


def _create_test_approval_queue(path: Path) -> None:
    records = [
        {
            "audit_id": "dec_test_001",
            "decision_id": "dec_test_001",
            "game_id": "cooking_fever_x",
            "action": "update_budget",
            "reason": "ROAS 下降",
            "confidence": 0.75,
            "status": "pending",
            "queued": True,
            "executed": False,
            "inputs": {},
            "timestamp": "2026-08-07T10:00:00Z",
        },
    ]
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _create_test_cycle_history(path: Path) -> None:
    """创建测试用 cycle_history.jsonl (2 个 cycle, 含动作和执行结果)."""
    records = [
        {
            "cycle_number": 1,
            "loop_id": "test_loop",
            "started_at": "2026-08-07T10:00:00Z",
            "completed_at": "2026-08-07T10:05:00Z",
            "duration_ms": 5000,
            "signal_ids": ["fs_1", "fs_2"],
            "actions_planned": 2,
            "actions_executed": 2,
            "actions_rolled_back": 0,
            "actions": [
                {"action_id": "act_1", "action_type": "update_budget"},
                {"action_id": "act_2", "action_type": "pause_campaign"},
            ],
            "execution_results": [
                {"action_id": "act_1", "success": True, "dry_run": True},
                {"action_id": "act_2", "success": True, "dry_run": True},
            ],
        },
        {
            "cycle_number": 2,
            "loop_id": "test_loop",
            "started_at": "2026-08-07T11:00:00Z",
            "completed_at": "2026-08-07T11:05:00Z",
            "duration_ms": 3000,
            "signal_ids": ["fs_3"],
            "actions_planned": 1,
            "actions_executed": 1,
            "actions_rolled_back": 0,
            "actions": [
                {"action_id": "act_3", "action_type": "update_budget"},
            ],
            "execution_results": [
                {"action_id": "act_3", "success": True, "dry_run": False},
            ],
        },
    ]
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _create_test_game_reality(game_dir: Path) -> None:
    games = {
        "cooking_fever_x": {
            "game_id": "cooking_fever_x",
            "health_score": 0.55,
            "metrics": {"dau": 38000, "revenue_total": 1390.0, "spend": 620.0, "roas": 2.24},
            "signals": [],
        },
    }
    for game_id, snapshot in games.items():
        path = game_dir / f"{game_id}.jsonl"
        with path.open("w", encoding="utf-8") as f:
            f.write(json.dumps(snapshot, ensure_ascii=False) + "\n")


def _create_test_company_snapshot(path: Path) -> None:
    snapshot = {
        "date": "2026-08-07",
        "active_games": 1,
        "total_games": 1,
        "total_dau": 38000,
        "total_revenue": 1390.0,
        "total_spend": 620.0,
    }
    with path.open("w", encoding="utf-8") as f:
        f.write(json.dumps(snapshot, ensure_ascii=False) + "\n")


def _make_mock_growth_loop_result():
    """创建 mock GrowthLoopOrchestrator.run_cycle 返回值."""
    mock_result = MagicMock()
    mock_result.cycle_number = 42
    mock_action = MagicMock()
    mock_action.action_id = "act_001"
    mock_action.action_type = "update_budget"
    mock_action.creative_id = "c1_creative"
    mock_action.risk_level = "low"
    mock_action.approval_level = 0
    mock_result.actions = [mock_action]
    mock_result.execution_results = [{"id": "act_001", "success": True}]
    mock_result.evaluated_count = 5
    mock_result.pending_created = 2
    return mock_result


class TestLoopTriggerFetchMetaAds:
    """/api/loop/trigger fetch_meta_ads=true 集成测试."""

    def test_fetch_meta_ads_not_configured_returns_400(self, client, workspace_env, monkeypatch):
        """fetch_meta_ads=true 但凭据未配置时应返回 400."""
        monkeypatch.delenv("META_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("META_AD_ACCOUNT_ID", raising=False)

        resp = client.post(
            "/api/loop/trigger",
            json={"dry_run": True, "fetch_meta_ads": True, "days": 7},
        )
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert "META_ACCESS_TOKEN" in detail or "META_AD_ACCOUNT_ID" in detail

    @patch("scripts.growth_loop_orchestrator.GrowthLoopOrchestrator")
    def test_fetch_meta_ads_with_fetch_error_returns_200(
        self, mock_orch_class, client, workspace_env, monkeypatch
    ):
        """fetch_meta_ads=true 且 fetcher 返回 fetch_error 时应返回 200 含错误信息."""
        monkeypatch.setenv("META_ACCESS_TOKEN", "tok")
        monkeypatch.setenv("META_AD_ACCOUNT_ID", "acct")

        mock_orch = MagicMock()
        mock_orch.run_cycle.return_value = _make_mock_growth_loop_result()
        mock_orch_class.return_value = mock_orch

        # Mock MetaAdsDataFetcher 返回 fetch_error
        mock_fetcher = MagicMock()
        mock_fetcher.is_configured.return_value = True
        mock_fetcher.fetch.return_value = MagicMock(
            fetch_error="Meta API timeout",
            signals=[],
            current_metrics={},
            previous_metrics={},
            creative_to_adset_map={},
            current_budgets={},
            reality_scores={},
            game_id_resolver=None,
            creative_count=0,
            prediction_count=0,
        )

        with patch(
            "src.market_ops.workspace.meta_ads_fetcher.MetaAdsDataFetcher",
            return_value=mock_fetcher,
        ):
            resp = client.post(
                "/api/loop/trigger",
                json={"dry_run": True, "fetch_meta_ads": True, "days": 7},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["fetch_meta_ads"] is True
        assert data["meta_ads_data"]["fetch_error"] == "Meta API timeout"
        assert data["meta_ads_data"]["creatives_fetched"] == 0

    @patch("scripts.growth_loop_orchestrator.GrowthLoopOrchestrator")
    def test_fetch_meta_ads_success_returns_meta_ads_data(
        self, mock_orch_class, client, workspace_env, monkeypatch
    ):
        """fetch_meta_ads=true 且数据拉取成功时应返回 meta_ads_data 和 action_details."""
        monkeypatch.setenv("META_ACCESS_TOKEN", "tok")
        monkeypatch.setenv("META_AD_ACCOUNT_ID", "acct")

        mock_orch = MagicMock()
        mock_orch.run_cycle.return_value = _make_mock_growth_loop_result()
        mock_orch_class.return_value = mock_orch

        # Mock GrowthLoopInput (成功拉取)
        mock_input = MagicMock()
        mock_input.fetch_error = None
        mock_input.signals = [MagicMock(), MagicMock()]
        mock_input.current_metrics = {"c1": {"spend": 100.0}}
        mock_input.previous_metrics = {"c1": {"spend": 80.0}}
        mock_input.creative_to_adset_map = {"c1": "adset_1"}
        mock_input.current_budgets = {"adset_1": 100.0}
        mock_input.reality_scores = {"P04": MagicMock()}
        mock_input.game_id_resolver = MagicMock()
        mock_input.creative_count = 3
        mock_input.prediction_count = 5

        mock_fetcher = MagicMock()
        mock_fetcher.is_configured.return_value = True
        mock_fetcher.fetch.return_value = mock_input

        with patch(
            "src.market_ops.workspace.meta_ads_fetcher.MetaAdsDataFetcher",
            return_value=mock_fetcher,
        ):
            resp = client.post(
                "/api/loop/trigger",
                json={"dry_run": True, "fetch_meta_ads": True, "days": 7},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["fetch_meta_ads"] is True
        assert data["meta_ads_data"]["creatives_fetched"] == 3
        assert data["meta_ads_data"]["signals_generated"] == 2
        assert data["meta_ads_data"]["predictions_generated"] == 5
        assert "fetch_error" not in data["meta_ads_data"]

        # 验证 action_details
        assert len(data["action_details"]) == 1
        detail = data["action_details"][0]
        assert detail["action_type"] == "update_budget"
        assert detail["creative_id"] == "c1_creative"
        assert detail["approval_level"] == 0
        assert detail["risk_level"] == "low"

        # 验证 orchestrator 被传入了真实数据
        call_kwargs = mock_orch.run_cycle.call_args.kwargs
        assert call_kwargs.get("signals") is not None
        assert call_kwargs.get("current_metrics") == {"c1": {"spend": 100.0}}
        assert call_kwargs.get("previous_metrics") == {"c1": {"spend": 80.0}}
        assert call_kwargs.get("creative_to_adset_map") == {"c1": "adset_1"}
        assert call_kwargs.get("current_budgets") == {"adset_1": 100.0}

    @patch("scripts.growth_loop_orchestrator.GrowthLoopOrchestrator")
    def test_live_mode_injects_meta_ads_adapter(
        self, mock_orch_class, client, workspace_env, monkeypatch
    ):
        """dry_run=false + fetch_meta_ads=true 应注入 MetaAdsPlatformAdapter."""
        monkeypatch.setenv("META_ACCESS_TOKEN", "tok")
        monkeypatch.setenv("META_AD_ACCOUNT_ID", "acct")

        mock_orch = MagicMock()
        mock_orch.run_cycle.return_value = _make_mock_growth_loop_result()
        mock_orch_class.return_value = mock_orch

        mock_input = MagicMock()
        mock_input.fetch_error = None
        mock_input.signals = []
        mock_input.current_metrics = {"c1": {"spend": 100.0}}
        mock_input.previous_metrics = {}
        mock_input.creative_to_adset_map = {"c1": "adset_1"}
        mock_input.current_budgets = {"adset_1": 100.0}
        mock_input.reality_scores = {}
        mock_input.game_id_resolver = None
        mock_input.creative_count = 1
        mock_input.prediction_count = 0

        mock_fetcher = MagicMock()
        mock_fetcher.is_configured.return_value = True
        mock_fetcher.fetch.return_value = mock_input

        mock_adapter = MagicMock()
        mock_client = MagicMock()

        with patch(
            "src.market_ops.workspace.meta_ads_fetcher.MetaAdsDataFetcher",
            return_value=mock_fetcher,
        ), patch(
            "scripts.meta_ads_adapter.MetaAdsPlatformAdapter",
            return_value=mock_adapter,
        ) as mock_adapter_class, patch(
            "market_ops.execution_runtime.adapters.facebook.FacebookClient",
            return_value=mock_client,
        ):
            resp = client.post(
                "/api/loop/trigger",
                json={"dry_run": False, "fetch_meta_ads": True, "days": 7},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["dry_run"] is False

        # 验证 MetaAdsPlatformAdapter 被创建
        mock_adapter_class.assert_called_once_with(mock_client)

        # 验证 orchestrator 构造时传入了 adapter
        orch_kwargs = mock_orch_class.call_args.kwargs
        assert orch_kwargs.get("adapter") is mock_adapter

    @patch("scripts.growth_loop_orchestrator.GrowthLoopOrchestrator")
    def test_live_mode_adapter_failure_does_not_block(
        self, mock_orch_class, client, workspace_env, monkeypatch
    ):
        """live 模式下 MetaAdsPlatformAdapter 创建失败不应阻塞 Loop 执行."""
        monkeypatch.setenv("META_ACCESS_TOKEN", "tok")
        monkeypatch.setenv("META_AD_ACCOUNT_ID", "acct")

        mock_orch = MagicMock()
        mock_orch.run_cycle.return_value = _make_mock_growth_loop_result()
        mock_orch_class.return_value = mock_orch

        mock_input = MagicMock()
        mock_input.fetch_error = None
        mock_input.signals = []
        mock_input.current_metrics = {"c1": {"spend": 100.0}}
        mock_input.previous_metrics = {}
        mock_input.creative_to_adset_map = {}
        mock_input.current_budgets = {}
        mock_input.reality_scores = {}
        mock_input.game_id_resolver = None
        mock_input.creative_count = 1
        mock_input.prediction_count = 0

        mock_fetcher = MagicMock()
        mock_fetcher.is_configured.return_value = True
        mock_fetcher.fetch.return_value = mock_input

        with patch(
            "src.market_ops.workspace.meta_ads_fetcher.MetaAdsDataFetcher",
            return_value=mock_fetcher,
        ), patch(
            "market_ops.execution_runtime.adapters.facebook.FacebookClient",
            side_effect=ImportError("facebook module not available"),
        ):
            resp = client.post(
                "/api/loop/trigger",
                json={"dry_run": False, "fetch_meta_ads": True, "days": 7},
            )

        # 即使 adapter 注入失败, Loop 仍然执行
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        mock_orch.run_cycle.assert_called_once()


# ── 5. /api/loop/history 和 /api/loop/cycle/{n} 端点测试 ────


class TestLoopHistoryEndpoint:
    """/api/loop/history 和 /api/loop/cycle/{n} 端点测试."""

    def test_history_returns_list_of_summaries(self, client, workspace_env):
        """history 端点应返回 cycle 摘要列表."""
        resp = client.get("/api/loop/history?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0
        # 验证摘要字段
        first = data[0]
        assert "cycle_number" in first
        assert "actions_planned" in first
        assert "actions_executed" in first
        assert "success_rate" in first
        assert "action_types" in first
        assert "dry_run" in first
        assert "signal_count" in first

    def test_history_returns_most_recent_first(self, client, workspace_env):
        """history 端点应返回最新的 cycle 在前."""
        resp = client.get("/api/loop/history?limit=10")
        data = resp.json()
        if len(data) >= 2:
            # 最新的在前 (cycle_number 倒序)
            assert data[0]["cycle_number"] >= data[1]["cycle_number"]

    def test_history_includes_action_types_distribution(self, client, workspace_env):
        """history 摘要应包含动作类型分布."""
        resp = client.get("/api/loop/history?limit=5")
        data = resp.json()
        # 至少有一个 cycle 有动作类型
        has_action_types = any(
            len(c.get("action_types", {})) > 0 for c in data
        )
        assert has_action_types, "至少一个 cycle 应有动作类型分布"

    def test_history_includes_dry_run_flag(self, client, workspace_env):
        """history 摘要应包含 dry_run 标志."""
        resp = client.get("/api/loop/history?limit=5")
        data = resp.json()
        for c in data:
            assert isinstance(c["dry_run"], bool)

    def test_cycle_detail_returns_full_record(self, client, workspace_env):
        """cycle/{n} 端点应返回完整的 cycle 记录."""
        # 先获取 history 找到一个有效的 cycle_number
        hist_resp = client.get("/api/loop/history?limit=5")
        cycles = hist_resp.json()
        if not cycles:
            pytest.skip("No cycles available for detail test")
        target_cycle = cycles[0]["cycle_number"]

        resp = client.get(f"/api/loop/cycle/{target_cycle}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cycle_number"] == target_cycle
        # 完整记录应包含 actions 和 execution_results
        assert "actions" in data
        assert "execution_results" in data

    def test_cycle_detail_returns_404_for_nonexistent(self, client, workspace_env):
        """不存在的 cycle_number 应返回 404."""
        resp = client.get("/api/loop/cycle/99999")
        assert resp.status_code == 404


# ── 6. 增强 trigger 响应字段测试 ─────────────────────────────


class TestLoopTriggerEnhancedResponse:
    """/api/loop/trigger 增强响应字段测试 (success_rate, reality_scores 等)."""

    @patch("scripts.growth_loop_orchestrator.GrowthLoopOrchestrator")
    def test_trigger_response_includes_success_rate(
        self, mock_orch_class, client, workspace_env, monkeypatch
    ):
        """trigger 响应应包含 actions_succeeded 和 success_rate."""
        monkeypatch.setenv("META_ACCESS_TOKEN", "tok")
        monkeypatch.setenv("META_AD_ACCOUNT_ID", "acct")

        mock_result = MagicMock()
        mock_result.cycle_number = 10
        mock_result.actions = [MagicMock()]
        mock_result.actions[0].action_id = "act_1"
        mock_result.actions[0].action_type = "update_budget"
        mock_result.actions[0].creative_id = "c1"
        mock_result.actions[0].adset_id = "as1"
        mock_result.actions[0].risk_level = "low"
        mock_result.actions[0].approval_level = 0
        mock_result.actions[0].confidence = 0.8
        mock_result.actions[0].budget_impact = 50.0
        mock_result.actions[0].status = "completed"
        mock_result.actions[0].reason = "test"
        mock_result.execution_results = [{"id": "act_1", "success": True}]
        mock_result.evaluated_count = 0
        mock_result.pending_created = 0
        mock_result.diagnosis = None
        mock_result.strategy = None
        mock_orch_class.return_value = mock_result
        mock_orch_class.return_value.run_cycle.return_value = mock_result

        resp = client.post("/api/loop/trigger", json={"dry_run": True})
        assert resp.status_code == 200
        data = resp.json()
        assert "actions_succeeded" in data
        assert data["actions_succeeded"] == 1
        assert "success_rate" in data
        assert data["success_rate"] == 1.0

    @patch("scripts.growth_loop_orchestrator.GrowthLoopOrchestrator")
    def test_trigger_response_includes_reality_scores(
        self, mock_orch_class, client, workspace_env, monkeypatch
    ):
        """拉取 Meta Ads 数据时响应应包含 reality_scores."""
        monkeypatch.setenv("META_ACCESS_TOKEN", "tok")
        monkeypatch.setenv("META_AD_ACCOUNT_ID", "acct")

        mock_result = MagicMock()
        mock_result.cycle_number = 11
        mock_result.actions = []
        mock_result.execution_results = []
        mock_result.evaluated_count = 0
        mock_result.pending_created = 0
        mock_result.diagnosis = None
        mock_result.strategy = None
        mock_orch_class.return_value = mock_result
        mock_orch_class.return_value.run_cycle.return_value = mock_result

        # Mock GrowthLoopInput with reality_scores
        mock_score = MagicMock()
        mock_score.composite = 0.85
        mock_score.decision_level = "EXECUTE"
        mock_score.coverage = 0.8
        mock_score.freshness = 1.0
        mock_score.consistency = 1.0

        mock_input = MagicMock()
        mock_input.fetch_error = None
        mock_input.signals = []
        mock_input.current_metrics = {}
        mock_input.previous_metrics = {}
        mock_input.creative_to_adset_map = {}
        mock_input.current_budgets = {}
        mock_input.reality_scores = {"P04": mock_score}
        mock_input.game_id_resolver = None
        mock_input.creative_count = 1
        mock_input.prediction_count = 0

        mock_fetcher = MagicMock()
        mock_fetcher.is_configured.return_value = True
        mock_fetcher.fetch.return_value = mock_input

        with patch(
            "src.market_ops.workspace.meta_ads_fetcher.MetaAdsDataFetcher",
            return_value=mock_fetcher,
        ):
            resp = client.post(
                "/api/loop/trigger",
                json={"dry_run": True, "fetch_meta_ads": True, "days": 7},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "reality_scores" in data
        assert len(data["reality_scores"]) == 1
        rs = data["reality_scores"][0]
        assert rs["game_id"] == "P04"
        assert rs["composite"] == 0.85
        assert rs["decision_level"] == "EXECUTE"

    @patch("scripts.growth_loop_orchestrator.GrowthLoopOrchestrator")
    def test_trigger_response_includes_diagnosis_and_strategy(
        self, mock_orch_class, client, workspace_env, monkeypatch
    ):
        """trigger 响应应包含 diagnosis_summary 和 strategy_summary."""
        monkeypatch.setenv("META_ACCESS_TOKEN", "tok")
        monkeypatch.setenv("META_AD_ACCOUNT_ID", "acct")

        mock_result = MagicMock()
        mock_result.cycle_number = 12
        mock_result.actions = []
        mock_result.execution_results = []
        mock_result.evaluated_count = 0
        mock_result.pending_created = 0
        mock_result.diagnosis = {
            "root_cause": "audience_quality_drop",
            "confidence": 0.82,
            "creative_id": "c1",
            "evidence": ["CPI +24.7%", "CTR 稳定"],
        }
        mock_result.strategy = {
            "strategy_type": "suppress",
            "intensity": 0.62,
            "target_creative_id": "c1",
            "time_horizon_days": 7,
        }
        mock_orch_class.return_value = mock_result
        mock_orch_class.return_value.run_cycle.return_value = mock_result

        resp = client.post("/api/loop/trigger", json={"dry_run": True})
        assert resp.status_code == 200
        data = resp.json()
        assert "diagnosis_summary" in data
        assert data["diagnosis_summary"]["root_cause"] == "audience_quality_drop"
        assert data["diagnosis_summary"]["confidence"] == 0.82
        assert "strategy_summary" in data
        assert data["strategy_summary"]["strategy_type"] == "suppress"
        assert data["strategy_summary"]["intensity"] == 0.62

    @patch("scripts.growth_loop_orchestrator.GrowthLoopOrchestrator")
    def test_trigger_response_action_details_include_full_fields(
        self, mock_orch_class, client, workspace_env, monkeypatch
    ):
        """action_details 应包含 confidence, budget_impact, status, reason 等完整字段."""
        monkeypatch.setenv("META_ACCESS_TOKEN", "tok")
        monkeypatch.setenv("META_AD_ACCOUNT_ID", "acct")

        mock_action = MagicMock()
        mock_action.action_id = "act_full_1"
        mock_action.action_type = "pause_campaign"
        mock_action.creative_id = "c_full"
        mock_action.adset_id = "as_full"
        mock_action.risk_level = "medium"
        mock_action.approval_level = 1
        mock_action.confidence = 0.75
        mock_action.budget_impact = 100.0
        mock_action.status = "completed"
        mock_action.reason = "clickbait_mismatch"

        mock_result = MagicMock()
        mock_result.cycle_number = 13
        mock_result.actions = [mock_action]
        mock_result.execution_results = [{"id": "act_full_1", "success": True}]
        mock_result.evaluated_count = 0
        mock_result.pending_created = 0
        mock_result.diagnosis = None
        mock_result.strategy = None
        mock_orch_class.return_value = mock_result
        mock_orch_class.return_value.run_cycle.return_value = mock_result

        resp = client.post("/api/loop/trigger", json={"dry_run": True})
        assert resp.status_code == 200
        data = resp.json()
        detail = data["action_details"][0]
        assert detail["confidence"] == 0.75
        assert detail["budget_impact"] == 100.0
        assert detail["status"] == "completed"
        assert detail["reason"] == "clickbait_mismatch"
        assert detail["adset_id"] == "as_full"
