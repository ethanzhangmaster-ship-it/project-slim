"""Numerical Designer Agent 单元测试.

覆盖:
  1. NumericalDesignerAgent: 数值建模/留存/付费/调优/A-B测试/通胀/报告
  2. 品类基准: Merge/Match3/Simulation
  3. 持久化: JSONL 读写
  4. CEO Memory 回流
  5. API 端点
  6. AgentRegistry 组织架构注册

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

from src.market_ops.workspace.numerical_designer_agent import (
    NumericalDesignerAgent,
    NumericalModel,
    RetentionCurveModel,
    PayConversionFunnel,
    PayerSegment,
    TuningRecommendation,
    ABTestDesign,
    ABTestVariant,
    InflationReport,
    NumericalReport,
    GameMetrics,
    NumericalModelConfig,
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
def tmp_numerical(tmp_data_dir: Path) -> NumericalDesignerAgent:
    """使用临时目录的 Numerical Designer Agent.

    注入 None 作为 profitability_engine/economy_manager, 强制使用内置降级模型,
    避免 v9_company mock 数据干扰数值验证.
    """
    return NumericalDesignerAgent(
        data_dir=str(tmp_data_dir),
        profitability_engine=None,
        economy_manager=None,
    )


@pytest.fixture
def merge_metrics() -> GameMetrics:
    """Merge 品类运营指标."""
    return GameMetrics(
        game_id="merge_game_001",
        genre="Merge",
        dau=12000,
        total_users=150000,
        revenue_total=6000.0,
        spend=3600.0,
        arpu=0.14,
        arppu=7.5,
        retention_d1=0.40,
        retention_d7=0.17,
        retention_d30=0.09,
        payer_rate=0.055,
        first_pay_rate=0.045,
        avg_first_pay_days=3.8,
        avg_first_pay_amount=4.99,
    )


@pytest.fixture
def match3_metrics() -> GameMetrics:
    """Match3 品类运营指标."""
    return GameMetrics(
        game_id="match3_game_001",
        genre="Match3",
        dau=20000,
        total_users=300000,
        revenue_total=8000.0,
        spend=5000.0,
        arpu=0.10,
        arppu=5.5,
        retention_d1=0.38,
        retention_d7=0.15,
        retention_d30=0.08,
        payer_rate=0.05,
        first_pay_rate=0.04,
        avg_first_pay_days=4.2,
        avg_first_pay_amount=3.99,
    )


@pytest.fixture
def simulation_metrics() -> GameMetrics:
    """Simulation 品类运营指标."""
    return GameMetrics(
        game_id="sim_game_001",
        genre="Simulation",
        dau=8000,
        total_users=80000,
        revenue_total=4000.0,
        spend=2400.0,
        arpu=0.18,
        arppu=11.0,
        retention_d1=0.36,
        retention_d7=0.20,
        retention_d30=0.14,
        payer_rate=0.04,
        first_pay_rate=0.035,
        avg_first_pay_days=5.0,
        avg_first_pay_amount=6.99,
    )


# ═══════════════════════════════════════════════════════════════
# 1. 数值建模测试
# ═══════════════════════════════════════════════════════════════


class TestNumericalModeling:
    """数值建模核心方法."""

    def test_model_numerical_returns_complete_model(
        self, tmp_numerical: NumericalDesignerAgent, merge_metrics: GameMetrics
    ):
        """数值建模包含完整字段."""
        model = tmp_numerical.model_numerical("merge_game_001", merge_metrics)

        assert isinstance(model, NumericalModel)
        assert model.model_id.startswith("model_")
        assert model.game_id == "merge_game_001"
        assert model.arpu == merge_metrics.arpu
        assert model.arppu == merge_metrics.arppu
        assert model.cac > 0
        assert model.ltv_d7 > 0
        assert model.ltv_d30 > 0
        assert model.ltv_d90 > model.ltv_d30  # 90 日 > 30 日
        assert model.ltv_cac_ratio > 0
        assert model.payback_days > 0
        assert 0 <= model.health_score <= 100
        assert model.diagnosis != ""

    def test_model_numerical_persists(
        self, tmp_numerical: NumericalDesignerAgent, merge_metrics: GameMetrics
    ):
        """数值建模持久化."""
        tmp_numerical.model_numerical("merge_game_001", merge_metrics)
        models = tmp_numerical.list_numerical_models()
        assert len(models) == 1
        assert models[0]["game_id"] == "merge_game_001"

    def test_model_numerical_ltv_cac_calculated(
        self, tmp_numerical: NumericalDesignerAgent, merge_metrics: GameMetrics
    ):
        """LTV/CAC 比计算正确."""
        model = tmp_numerical.model_numerical("merge_game_001", merge_metrics)
        # CAC > 0 (可能来自 ProfitabilityEngine 或降级估算 spend/dau)
        assert model.cac > 0
        # LTV/CAC 比与 LTV_D30/CAC 一致
        expected_ratio = model.ltv_d30 / model.cac
        assert abs(model.ltv_cac_ratio - expected_ratio) < 0.1

    def test_model_numerical_health_score_range(
        self, tmp_numerical: NumericalDesignerAgent,
        merge_metrics: GameMetrics, match3_metrics: GameMetrics
    ):
        """健康分在 0-100 范围内."""
        for m in [merge_metrics, match3_metrics]:
            model = tmp_numerical.model_numerical(m.game_id, m)
            assert 0 <= model.health_score <= 100

    def test_model_retention_returns_curve(
        self, tmp_numerical: NumericalDesignerAgent, merge_metrics: GameMetrics
    ):
        """留存曲线建模."""
        curve = tmp_numerical.model_retention("merge_game_001", merge_metrics)

        assert isinstance(curve, RetentionCurveModel)
        assert curve.curve_id.startswith("ret_curve_")
        assert curve.retention_d1 == merge_metrics.retention_d1
        assert curve.retention_d7 == merge_metrics.retention_d7
        assert curve.retention_d30 == merge_metrics.retention_d30
        assert curve.decay_rate > 0
        assert curve.curve_type == "power_law"
        assert curve.predicted_d180 > 0
        assert curve.predicted_d180 < curve.retention_d30  # 180 日 < 30 日
        assert curve.benchmark_d1 > 0
        assert curve.gap_to_benchmark != ""

    def test_model_retention_decay_decreasing(
        self, tmp_numerical: NumericalDesignerAgent, merge_metrics: GameMetrics
    ):
        """留存曲线衰减递减."""
        curve = tmp_numerical.model_retention("merge_game_001", merge_metrics)
        # D1 > D7 > D30 > D90
        assert curve.retention_d1 > curve.retention_d7
        assert curve.retention_d7 > curve.retention_d30
        assert curve.retention_d30 > curve.retention_d90

    def test_model_retention_persists(
        self, tmp_numerical: NumericalDesignerAgent, merge_metrics: GameMetrics
    ):
        """留存曲线持久化."""
        tmp_numerical.model_retention("merge_game_001", merge_metrics)
        curves = tmp_numerical.list_retention_curves()
        assert len(curves) == 1

    def test_analyze_pay_conversion_returns_funnel(
        self, tmp_numerical: NumericalDesignerAgent, merge_metrics: GameMetrics
    ):
        """付费转化漏斗分析."""
        funnel = tmp_numerical.analyze_pay_conversion("merge_game_001", merge_metrics)

        assert isinstance(funnel, PayConversionFunnel)
        assert funnel.funnel_id.startswith("funnel_")
        assert funnel.total_users == merge_metrics.total_users
        assert funnel.activated_users > 0
        assert funnel.first_pay_users > 0
        assert funnel.repeat_pay_users > 0
        assert funnel.whale_users > 0
        assert 0 <= funnel.activation_rate <= 1
        assert 0 <= funnel.first_pay_rate <= 1
        assert len(funnel.payer_segments) == 3  # minnow/dolphin/whale
        assert funnel.bottleneck != ""

    def test_pay_conversion_segments_sum(
        self, tmp_numerical: NumericalDesignerAgent, merge_metrics: GameMetrics
    ):
        """付费分群收入占比合计约 100%."""
        funnel = tmp_numerical.analyze_pay_conversion("merge_game_001", merge_metrics)
        total_share = sum(s.revenue_share for s in funnel.payer_segments)
        assert abs(total_share - 1.0) < 0.01

    def test_pay_conversion_persists(
        self, tmp_numerical: NumericalDesignerAgent, merge_metrics: GameMetrics
    ):
        """付费漏斗持久化."""
        tmp_numerical.analyze_pay_conversion("merge_game_001", merge_metrics)
        funnels = tmp_numerical.list_pay_funnels()
        assert len(funnels) == 1


# ═══════════════════════════════════════════════════════════════
# 2. 调优建议和 A/B 测试测试
# ═══════════════════════════════════════════════════════════════


class TestTuningAndABTest:
    """数值调优和 A/B 测试."""

    def test_recommend_tuning_returns_recommendations(
        self, tmp_numerical: NumericalDesignerAgent, merge_metrics: GameMetrics
    ):
        """调优建议生成."""
        recs = tmp_numerical.recommend_tuning("merge_game_001", merge_metrics)

        assert isinstance(recs, list)
        assert len(recs) > 0
        assert all(isinstance(r, TuningRecommendation) for r in recs)
        for r in recs:
            assert r.recommendation_id.startswith("rec_")
            assert r.priority in ("HIGH", "MEDIUM", "LOW")
            assert r.risk_level in ("LOW", "MEDIUM", "HIGH")
            assert r.rationale != ""

    def test_recommend_tuning_low_retention_triggers_rec(
        self, tmp_numerical: NumericalDesignerAgent
    ):
        """低留存触发调优建议."""
        metrics = GameMetrics(
            game_id="test_game",
            genre="Merge",
            retention_d1=0.30,  # 低于基准 0.45
            retention_d7=0.10,
            retention_d30=0.05,
            arpu=0.20,  # 高于基准
            arppu=10.0,
            first_pay_rate=0.08,  # 高于基准
            dau=10000, spend=3000.0,
        )
        recs = tmp_numerical.recommend_tuning("test_game", metrics)
        # 应该有留存调优建议
        retention_recs = [r for r in recs if r.target_metric == "retention_d1"]
        assert len(retention_recs) == 1
        assert retention_recs[0].priority == "HIGH"

    def test_recommend_tuning_persists(
        self, tmp_numerical: NumericalDesignerAgent, merge_metrics: GameMetrics
    ):
        """调优建议持久化."""
        tmp_numerical.recommend_tuning("merge_game_001", merge_metrics)
        recs = tmp_numerical.list_tuning_recommendations()
        assert len(recs) == 1

    def test_design_ab_test_returns_complete_test(
        self, tmp_numerical: NumericalDesignerAgent, merge_metrics: GameMetrics
    ):
        """A/B 测试方案设计."""
        test = tmp_numerical.design_ab_test(
            "merge_game_001", "提高首充率至 8%", merge_metrics, "first_pay_rate"
        )

        assert isinstance(test, ABTestDesign)
        assert test.test_id.startswith("abtest_")
        assert test.game_id == "merge_game_001"
        assert test.hypothesis == "提高首充率至 8%"
        assert test.target_metric == "first_pay_rate"
        assert len(test.variants) == 3  # control + treatment_a + treatment_b
        assert test.sample_size_per_variant >= 1000
        assert test.duration_days >= 7
        assert test.significance_level == 0.05
        assert test.power == 0.80
        assert test.success_criteria != ""

    def test_ab_test_variants_have_changes(
        self, tmp_numerical: NumericalDesignerAgent, merge_metrics: GameMetrics
    ):
        """A/B 测试变体有参数变更."""
        test = tmp_numerical.design_ab_test(
            "merge_game_001", "测试假设", merge_metrics
        )
        # 对照组无变更
        control = [v for v in test.variants if v.variant_name == "control"][0]
        assert len(control.parameter_changes) == 0
        # 处理组有变更
        treatments = [v for v in test.variants if v.variant_name.startswith("treatment")]
        assert len(treatments) == 2
        for t in treatments:
            assert len(t.parameter_changes) > 0

    def test_ab_test_persists(
        self, tmp_numerical: NumericalDesignerAgent, merge_metrics: GameMetrics
    ):
        """A/B 测试持久化."""
        tmp_numerical.design_ab_test("merge_game_001", "假设", merge_metrics)
        tests = tmp_numerical.list_ab_tests()
        assert len(tests) == 1


# ═══════════════════════════════════════════════════════════════
# 3. 通胀监控和完整报告测试
# ═══════════════════════════════════════════════════════════════


class TestInflationAndReport:
    """通胀监控和完整数值报告."""

    def test_monitor_inflation_returns_report(
        self, tmp_numerical: NumericalDesignerAgent
    ):
        """通胀监控报告."""
        report = tmp_numerical.monitor_inflation("merge_game_001")

        assert isinstance(report, InflationReport)
        assert report.report_id.startswith("inflation_")
        assert report.game_id == "merge_game_001"
        assert len(report.currencies) > 0
        assert report.overall_inflation_rate >= 0
        assert report.inflation_status in ("HEALTHY", "WARNING", "CRITICAL")
        assert report.sink_to_faucet_ratio > 0
        assert len(report.recommended_actions) > 0

    def test_monitor_inflation_with_custom_data(
        self, tmp_numerical: NumericalDesignerAgent
    ):
        """通胀监控自定义数据."""
        eco_data = {
            "currencies": [
                {"name": "Gems", "inflation_rate": 0.01, "sink_to_faucet": 1.10, "avg_wallet": 100},
                {"name": "Coins", "inflation_rate": 0.05, "sink_to_faucet": 0.95, "avg_wallet": 5000},
            ]
        }
        report = tmp_numerical.monitor_inflation("test_game", eco_data)
        assert report.overall_inflation_rate == pytest.approx(0.03, abs=1e-9)  # (0.01+0.05)/2
        assert report.inflation_status == "WARNING"  # 0.03 > 0.02 target, < 0.04
        assert len(report.currency_imbalance) > 0  # Coins 失衡

    def test_monitor_inflation_critical(
        self, tmp_numerical: NumericalDesignerAgent
    ):
        """高通胀触发 CRITICAL."""
        eco_data = {
            "currencies": [
                {"name": "Gems", "inflation_rate": 0.10, "sink_to_faucet": 0.90, "avg_wallet": 200},
            ]
        }
        report = tmp_numerical.monitor_inflation("test_game", eco_data)
        assert report.inflation_status == "CRITICAL"

    def test_monitor_inflation_persists(
        self, tmp_numerical: NumericalDesignerAgent
    ):
        """通胀报告持久化."""
        tmp_numerical.monitor_inflation("merge_game_001")
        reports = tmp_numerical.list_inflation_reports()
        assert len(reports) == 1

    def test_create_numerical_report_aggregates_all(
        self, tmp_numerical: NumericalDesignerAgent, merge_metrics: GameMetrics
    ):
        """完整数值报告聚合所有产物."""
        report = tmp_numerical.create_numerical_report("merge_game_001", merge_metrics)

        assert isinstance(report, NumericalReport)
        assert report.report_id.startswith("num_report_")
        assert report.game_id == "merge_game_001"
        assert "model_id" in report.numerical_model
        assert "curve_id" in report.retention_curve
        assert "funnel_id" in report.pay_conversion
        assert len(report.tuning_recommendations) >= 0
        assert "report_id" in report.inflation_report
        assert report.overall_health in ("HEALTHY", "ATTENTION", "CRITICAL")
        assert 0 <= report.health_score <= 100
        assert report.summary != ""

    def test_numerical_report_persists(
        self, tmp_numerical: NumericalDesignerAgent, merge_metrics: GameMetrics
    ):
        """数值报告持久化."""
        tmp_numerical.create_numerical_report("merge_game_001", merge_metrics)
        reports = tmp_numerical.list_numerical_reports()
        assert len(reports) == 1

    def test_get_numerical_report_by_id(
        self, tmp_numerical: NumericalDesignerAgent, merge_metrics: GameMetrics
    ):
        """按 ID 查询数值报告."""
        created = tmp_numerical.create_numerical_report("merge_game_001", merge_metrics)
        found = tmp_numerical.get_numerical_report(created.report_id)
        assert found is not None
        assert found["report_id"] == created.report_id

    def test_get_numerical_report_not_found(
        self, tmp_numerical: NumericalDesignerAgent
    ):
        """查询不存在的报告返回 None."""
        assert tmp_numerical.get_numerical_report("nonexistent") is None


# ═══════════════════════════════════════════════════════════════
# 4. 品类基准测试
# ═══════════════════════════════════════════════════════════════


class TestGenreBenchmarks:
    """品类基准覆盖."""

    def test_merge_benchmark_applied(
        self, tmp_numerical: NumericalDesignerAgent, merge_metrics: GameMetrics
    ):
        """Merge 基准应用."""
        curve = tmp_numerical.model_retention("merge_game_001", merge_metrics)
        assert curve.benchmark_d1 == 0.45
        assert curve.benchmark_d30 == 0.12

    def test_match3_benchmark_applied(
        self, tmp_numerical: NumericalDesignerAgent, match3_metrics: GameMetrics
    ):
        """Match3 基准应用."""
        curve = tmp_numerical.model_retention("match3_game_001", match3_metrics)
        assert curve.benchmark_d1 == 0.40
        assert curve.benchmark_d30 == 0.10

    def test_simulation_benchmark_applied(
        self, tmp_numerical: NumericalDesignerAgent, simulation_metrics: GameMetrics
    ):
        """Simulation 基准应用."""
        curve = tmp_numerical.model_retention("sim_game_001", simulation_metrics)
        assert curve.benchmark_d1 == 0.38
        assert curve.benchmark_d30 == 0.15

    def test_unknown_genre_falls_back(
        self, tmp_numerical: NumericalDesignerAgent
    ):
        """未知品类降级到默认基准."""
        metrics = GameMetrics(game_id="test", genre="Unknown")
        curve = tmp_numerical.model_retention("test", metrics)
        # 应该使用 Merge 默认基准
        assert curve.benchmark_d1 == 0.45


# ═══════════════════════════════════════════════════════════════
# 5. 持久化和统计测试
# ═══════════════════════════════════════════════════════════════


class TestPersistenceAndStats:
    """持久化和统计."""

    def test_stats_empty(self, tmp_numerical: NumericalDesignerAgent):
        """空数据统计."""
        stats = tmp_numerical.get_stats()
        assert stats["total_numerical_models"] == 0
        assert stats["total_retention_curves"] == 0
        assert stats["total_pay_funnels"] == 0
        assert stats["total_tuning_recommendations"] == 0
        assert stats["total_ab_tests"] == 0
        assert stats["total_inflation_reports"] == 0
        assert stats["total_numerical_reports"] == 0

    def test_stats_after_full_report(
        self, tmp_numerical: NumericalDesignerAgent, merge_metrics: GameMetrics
    ):
        """完整报告后统计."""
        tmp_numerical.create_numerical_report("merge_game_001", merge_metrics)
        stats = tmp_numerical.get_stats()
        assert stats["total_numerical_models"] == 1
        assert stats["total_retention_curves"] == 1
        assert stats["total_pay_funnels"] == 1
        assert stats["total_tuning_recommendations"] == 1
        assert stats["total_inflation_reports"] == 1
        assert stats["total_numerical_reports"] == 1
        assert "health_distribution" in stats

    def test_ceo_memory_written(
        self, tmp_numerical: NumericalDesignerAgent,
        merge_metrics: GameMetrics, tmp_data_dir: Path
    ):
        """数值产物回流 CEO Memory."""
        tmp_numerical.model_numerical("merge_game_001", merge_metrics)
        ceo_memory_path = tmp_data_dir / "ceo" / "execution_memory.jsonl"
        assert ceo_memory_path.exists()
        records = [
            json.loads(line)
            for line in ceo_memory_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(records) > 0
        numerical_records = [r for r in records if r.get("domain") == "numerical"]
        assert len(numerical_records) > 0
        assert numerical_records[0]["action_type"] == "ltv_cac_modeling"

    def test_multiple_reports_coexist(
        self, tmp_numerical: NumericalDesignerAgent,
        merge_metrics: GameMetrics, match3_metrics: GameMetrics
    ):
        """多个数值报告共存."""
        tmp_numerical.create_numerical_report("merge_game_001", merge_metrics)
        tmp_numerical.create_numerical_report("match3_game_001", match3_metrics)
        reports = tmp_numerical.list_numerical_reports()
        assert len(reports) == 2


# ═══════════════════════════════════════════════════════════════
# 6. API 端点测试
# ═══════════════════════════════════════════════════════════════


class TestNumericalAPI:
    """Numerical Designer API 端点."""

    @pytest.fixture
    def api_client(self, tmp_path: Path, monkeypatch):
        """FastAPI TestClient + 临时数据目录."""
        data_dir = tmp_path / "data"
        for sub in ["growth_loop", "ceo/audit", "ceo/game_reality", "liveops",
                     "product", "design", "numerical", "workspace"]:
            (data_dir / sub).mkdir(parents=True, exist_ok=True)
        (data_dir / "growth_loop" / "cycle_history.jsonl").write_text("", encoding="utf-8")

        from src.market_ops.workspace import app as app_module
        monkeypatch.setattr(app_module, "_PROJECT_ROOT", tmp_path)

        for attr in ["_instance"]:
            for fn_name in ["_get_numerical_agent", "_get_designer_agent",
                            "_get_product_agent", "_get_ceo_decision_center"]:
                fn = getattr(app_module, fn_name, None)
                if fn is not None and hasattr(fn, attr):
                    delattr(fn, attr)

        return TestClient(app_module.app)

    def _metrics_payload(self, game_id: str = "api_test_game") -> dict:
        return {
            "game_id": game_id,
            "genre": "Merge",
            "dau": 10000,
            "total_users": 100000,
            "revenue_total": 5000.0,
            "spend": 3000.0,
            "arpu": 0.14,
            "arppu": 8.0,
            "retention_d1": 0.40,
            "retention_d7": 0.17,
            "retention_d30": 0.09,
            "payer_rate": 0.055,
            "first_pay_rate": 0.045,
            "avg_first_pay_days": 3.8,
            "avg_first_pay_amount": 4.99,
        }

    def test_model_numerical_api(self, api_client: TestClient):
        """数值建模 API."""
        resp = api_client.post("/api/numerical/model", json=self._metrics_payload())
        assert resp.status_code == 200
        data = resp.json()
        assert data["game_id"] == "api_test_game"
        assert data["ltv_cac_ratio"] > 0
        assert 0 <= data["health_score"] <= 100

    def test_model_retention_api(self, api_client: TestClient):
        """留存曲线 API."""
        resp = api_client.post("/api/numerical/retention", json=self._metrics_payload())
        assert resp.status_code == 200
        data = resp.json()
        assert data["retention_d1"] == 0.40
        assert data["decay_rate"] > 0

    def test_pay_conversion_api(self, api_client: TestClient):
        """付费转化 API."""
        resp = api_client.post("/api/numerical/pay-conversion", json=self._metrics_payload())
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["payer_segments"]) == 3

    def test_tuning_api(self, api_client: TestClient):
        """调优建议 API."""
        resp = api_client.post("/api/numerical/tuning", json=self._metrics_payload())
        assert resp.status_code == 200
        data = resp.json()
        assert data["recommendation_count"] >= 0
        assert "high_priority_count" in data

    def test_ab_test_api(self, api_client: TestClient):
        """A/B 测试 API."""
        payload = {**self._metrics_payload(), "hypothesis": "提高首充率", "target_metric": "first_pay_rate"}
        resp = api_client.post("/api/numerical/ab-test", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["variants"]) == 3
        assert data["sample_size_per_variant"] >= 1000

    def test_inflation_api(self, api_client: TestClient):
        """通胀监控 API."""
        resp = api_client.post("/api/numerical/inflation?game_id=test_game")
        assert resp.status_code == 200
        data = resp.json()
        assert data["inflation_status"] in ("HEALTHY", "WARNING", "CRITICAL")

    def test_numerical_report_api(self, api_client: TestClient):
        """完整数值报告 API."""
        resp = api_client.post("/api/numerical/report", json=self._metrics_payload())
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_health"] in ("HEALTHY", "ATTENTION", "CRITICAL")
        assert "numerical_model" in data
        assert "retention_curve" in data

    def test_list_numerical_reports_api(self, api_client: TestClient):
        """数值报告列表 API."""
        api_client.post("/api/numerical/report", json=self._metrics_payload())
        resp = api_client.get("/api/numerical/reports")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_get_numerical_report_api(self, api_client: TestClient):
        """数值报告详情 API."""
        create_resp = api_client.post("/api/numerical/report", json=self._metrics_payload())
        report_id = create_resp.json()["report_id"]
        resp = api_client.get(f"/api/numerical/reports/{report_id}")
        assert resp.status_code == 200
        assert resp.json()["report_id"] == report_id

    def test_get_numerical_report_not_found_api(self, api_client: TestClient):
        """查询不存在的报告返回 404."""
        resp = api_client.get("/api/numerical/reports/nonexistent")
        assert resp.status_code == 404

    def test_numerical_stats_api(self, api_client: TestClient):
        """数值统计 API."""
        api_client.post("/api/numerical/report", json=self._metrics_payload())
        resp = api_client.get("/api/numerical/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_numerical_reports"] == 1


# ═══════════════════════════════════════════════════════════════
# 7. AgentRegistry 组织架构注册测试
# ═══════════════════════════════════════════════════════════════


class TestNumericalRegistry:
    """Numerical Designer Agent 在 AgentRegistry 组织架构中的注册."""

    def test_numerical_registered_in_default_organization(self):
        """默认组织包含 Numerical Designer Agent."""
        from src.market_ops.creative_vision_runtime.growth_runtime.agent.communication.agent_registry import (
            create_default_organization,
        )
        registry = create_default_organization()
        all_records = registry.get_all()
        numerical_records = [r for r in all_records if r.identity.role.value == "numerical"]
        assert len(numerical_records) == 1

    def test_numerical_has_modeling_capabilities(self):
        """Numerical Agent 包含数值建模能力."""
        from src.market_ops.creative_vision_runtime.growth_runtime.agent.communication.agent_message import (
            create_numerical_designer_agent_identity,
        )
        identity = create_numerical_designer_agent_identity()
        assert "ltv_cac_modeling" in identity.capabilities
        assert "retention_curve_modeling" in identity.capabilities
        assert "ab_test_design" in identity.capabilities
        assert "inflation_monitoring" in identity.capabilities

    def test_find_numerical_by_capability(self):
        """能通过 LTV 建模能力查找到 Numerical Agent."""
        from src.market_ops.creative_vision_runtime.growth_runtime.agent.communication.agent_registry import (
            create_default_organization,
        )
        registry = create_default_organization()
        found = registry.find_by_capability("ltv_cac_modeling")
        assert len(found) == 1
        assert found[0].identity.role.value == "numerical"

    def test_default_organization_has_ten_agents(self):
        """默认组织包含 10 个 Agent."""
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

    def test_numerical_visible_in_workspace_snapshot(self, tmp_path: Path):
        """Numerical Agent 在 Workspace 快照中可见."""
        from src.market_ops.workspace import agent_registry_store
        snapshot_path = tmp_path / "agents.jsonl"
        records = agent_registry_store.create_default_agents_snapshot(snapshot_path)
        assert len(records) == 10
        numerical_records = [
            r for r in records
            if (r.get("identity", {}) or {}).get("role") == "numerical"
        ]
        assert len(numerical_records) == 1
        capabilities = numerical_records[0]["identity"]["capabilities"]
        assert "ltv_cac_modeling" in capabilities

    def test_numerical_department_is_design(self):
        """Numerical Agent 映射到 Design 部门."""
        from src.market_ops.workspace.real_provider import _ROLE_TO_DEPARTMENT
        assert _ROLE_TO_DEPARTMENT.get("numerical") == "Design"
