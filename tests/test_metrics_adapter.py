"""MetricsAdapter 指标适配层测试 (接线 3)。

验证多源数据适配为 creative 级 current_metrics:
  - 广告侧主源: 8 字段契约保持
  - 产品侧 IAP 收入富集 revenue (按 spend 占比分摊)
  - 产品侧 IAA 收入富集 revenue (按归因分摊)
  - 产品侧 installs 校验
  - 产品上下文附加 (_context 字段)
  - 无产品侧数据时向后兼容
  - 输出可直接传入 DiagnosticEngine
"""

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from scripts.metrics_adapter import MetricsAdapter, EnrichmentReport, adapt_metrics


# ──────────────────────────────────────────────
# Mock 数据结构
# ──────────────────────────────────────────────


@dataclass
class MockFunnelStep:
    step_name: str = ""
    event_name: str = ""
    entered: int = 0
    completed: int = 0
    conversion_rate: float = 0.0
    drop_off_rate: float = 0.0
    avg_time_seconds: float = 0.0


@dataclass
class MockFunnelSnapshot:
    steps: list[MockFunnelStep] = field(default_factory=list)
    overall_conversion: float = 0.0
    drop_off_steps: list[str] = field(default_factory=list)
    insights: list[str] = field(default_factory=list)


@dataclass
class MockMonetizationSnapshot:
    total_revenue: float = 0.0
    arpu: float = 0.0
    arppu: float = 0.0
    payer_rate: float = 0.0
    ltv_d7: float = 0.0
    ltv_d30: float = 0.0


@dataclass
class MockLifecycleSnapshot:
    d1_retention: float = 0.0
    d7_retention: float = 0.0
    d30_retention: float = 0.0
    churn_risk_rate: float = 0.0
    dau: int = 0


@dataclass
class MockUserValueSnapshot:
    avg_value_score: float = 0.0
    pareto_ratio: float = 0.0


@dataclass
class MockGameplaySnapshot:
    total_players: int = 0
    avg_session_len: float = 0.0


@dataclass
class MockPlayerProfile:
    user_id: str = ""
    total_ad_revenue: float = 0.0
    total_ad_shows: int = 0
    total_ad_requests: int = 0


# ──────────────────────────────────────────────
# 工厂函数
# ──────────────────────────────────────────────


def _make_ads_metrics(
    creatives: dict[str, dict[str, float]] | None = None,
) -> dict[str, dict[str, float]]:
    """构造广告侧 metrics (模拟 aggregate_by_creative 输出)。"""
    if creatives is None:
        return {
            "c_001": {
                "spend": 200.0, "clicks": 100, "ctr": 0.02,
                "cpi": 2.0, "roas": 0.5, "impressions": 5000,
                "installs": 100, "revenue": 100.0,
            },
            "c_002": {
                "spend": 300.0, "clicks": 150, "ctr": 0.025,
                "cpi": 3.0, "roas": 0.6, "impressions": 6000,
                "installs": 100, "revenue": 180.0,
            },
        }
    return creatives


def _make_snapshots(
    iap_revenue: float = 0.0,
    real_installs: int = 0,
    d1_retention: float = 0.0,
    arpu: float = 0.0,
) -> dict[str, Any]:
    """构造七域快照。"""
    snapshots: dict[str, Any] = {}
    if iap_revenue > 0:
        snapshots["Monetization"] = MockMonetizationSnapshot(
            total_revenue=iap_revenue, arpu=arpu, arppu=arpu * 10,
            payer_rate=0.05, ltv_d7=arpu * 7, ltv_d30=arpu * 30,
        )
    if real_installs > 0:
        snapshots["Funnel"] = MockFunnelSnapshot(
            steps=[MockFunnelStep(step_name="安装", entered=real_installs)]
        )
    if d1_retention > 0:
        snapshots["Lifecycle"] = MockLifecycleSnapshot(
            d1_retention=d1_retention, d7_retention=d1_retention * 0.5,
            d30_retention=d1_retention * 0.2, churn_risk_rate=0.1, dau=5000,
        )
    snapshots["UserValue"] = MockUserValueSnapshot(
        avg_value_score=0.65, pareto_ratio=0.8,
    )
    snapshots["Gameplay"] = MockGameplaySnapshot(
        total_players=8000, avg_session_len=180.0,
    )
    return snapshots


def _make_profiles(
    mapping: dict[str, float] | None = None,
) -> list[MockPlayerProfile]:
    """构造 PlayerProfile 列表。mapping = {user_id: ad_revenue}。"""
    if mapping is None:
        return []
    return [
        MockPlayerProfile(user_id=uid, total_ad_revenue=rev)
        for uid, rev in mapping.items()
    ]


# ──────────────────────────────────────────────
# 基础适配测试
# ──────────────────────────────────────────────


class TestBasicAdaptation:
    """基础适配: 无产品侧数据时, 广告侧原样输出。"""

    def test_no_enrichment_sources(self):
        """无七域快照 + 无 PlayerProfile → 广告侧原样输出。"""
        ads = _make_ads_metrics()
        adapter = MetricsAdapter()
        metrics, report = adapter.adapt(ads_metrics=ads)

        assert len(metrics) == 2
        assert metrics["c_001"]["spend"] == 200.0
        assert metrics["c_001"]["revenue"] == 100.0
        assert metrics["c_001"]["roas"] == 0.5
        assert report.total_creatives == 2
        assert report.revenue_enriched == 0
        assert report.context_added == 0

    def test_empty_ads_metrics(self):
        """空广告侧 metrics → 空输出。"""
        adapter = MetricsAdapter()
        metrics, report = adapter.adapt(ads_metrics={})

        assert metrics == {}
        assert report.total_creatives == 0

    def test_8_field_contract_preserved(self):
        """适配后仍保持 8 字段契约。"""
        ads = _make_ads_metrics()
        adapter = MetricsAdapter()
        metrics, _ = adapter.adapt(ads_metrics=ads)

        required_fields = {
            "spend", "clicks", "ctr", "cpi",
            "roas", "impressions", "installs", "revenue",
        }
        for cid, m in metrics.items():
            assert required_fields.issubset(m.keys()), (
                f"{cid} 缺少字段: {required_fields - set(m.keys())}"
            )

    def test_original_ads_metrics_not_mutated(self):
        """适配不应修改原始 ads_metrics。"""
        ads = _make_ads_metrics()
        original_revenue = ads["c_001"]["revenue"]

        adapter = MetricsAdapter()
        snapshots = _make_snapshots(iap_revenue=500.0, arpu=1.0)
        metrics, _ = adapter.adapt(
            ads_metrics=ads, seven_domain_snapshots=snapshots,
        )

        # 原始 ads_metrics 不变
        assert ads["c_001"]["revenue"] == original_revenue
        # 适配后的 metrics 已富集
        assert metrics["c_001"]["revenue"] != original_revenue


# ──────────────────────────────────────────────
# IAP 收入富集测试
# ──────────────────────────────────────────────


class TestIAPRevenueEnrichment:
    """用产品侧 IAP 收入富集 revenue。"""

    def test_iap_revenue_replace_ads_revenue(self):
        """IAP 收入按 spend 占比分摊, 替换广告侧反推 revenue。"""
        ads = _make_ads_metrics()
        # c_001 spend=200, c_002 spend=300, total=500
        # IAP=1000 → c_001 分到 400, c_002 分到 600
        snapshots = _make_snapshots(iap_revenue=1000.0, arpu=1.0)

        adapter = MetricsAdapter()
        metrics, report = adapter.adapt(
            ads_metrics=ads, seven_domain_snapshots=snapshots,
        )

        # c_001: IAP 分摊 = 1000 * (200/500) = 400
        assert metrics["c_001"]["revenue"] == pytest.approx(400.0, abs=0.1)
        # roas = 400 / 200 = 2.0
        assert metrics["c_001"]["roas"] == pytest.approx(2.0, abs=0.01)

        # c_002: IAP 分摊 = 1000 * (300/500) = 600
        assert metrics["c_002"]["revenue"] == pytest.approx(600.0, abs=0.1)
        assert metrics["c_002"]["roas"] == pytest.approx(2.0, abs=0.01)

        assert report.revenue_enriched == 2

    def test_iap_revenue_discrepancy_recorded(self):
        """广告侧 vs 产品侧 revenue 偏差 > 30% 时记录。"""
        ads = _make_ads_metrics()
        # 广告侧: c_001 revenue=100, IAP 分摊=400 → 偏差 300% >> 30%
        snapshots = _make_snapshots(iap_revenue=1000.0, arpu=1.0)

        adapter = MetricsAdapter()
        _, report = adapter.adapt(
            ads_metrics=ads, seven_domain_snapshots=snapshots,
        )

        assert len(report.revenue_discrepancies) >= 1
        disc = report.revenue_discrepancies[0]
        assert disc["creative_id"] in ("c_001", "c_002")
        assert disc["discrepancy"] > 0.30

    def test_iap_zero_skipped(self):
        """IAP=0 时不富集 revenue。"""
        ads = _make_ads_metrics()
        snapshots = _make_snapshots(iap_revenue=0.0)

        adapter = MetricsAdapter()
        metrics, report = adapter.adapt(
            ads_metrics=ads, seven_domain_snapshots=snapshots,
        )

        assert metrics["c_001"]["revenue"] == 100.0  # 原值不变
        assert report.revenue_enriched == 0


# ──────────────────────────────────────────────
# IAA 收入富集测试
# ──────────────────────────────────────────────


class TestIAARevenueEnrichment:
    """用 PlayerProfile IAA 收入富集 revenue (按归因分摊)。"""

    def test_iaa_revenue_attribution(self):
        """IAA 收入按 user_id → creative_id 归因分摊。"""
        ads = _make_ads_metrics()
        profiles = _make_profiles({
            "u_001": 50.0,  # 归因到 c_001
            "u_002": 30.0,  # 归因到 c_001
            "u_003": 70.0,  # 归因到 c_002
        })
        attribution = {
            "u_001": "c_001", "u_002": "c_001", "u_003": "c_002",
        }

        adapter = MetricsAdapter()
        metrics, report = adapter.adapt(
            ads_metrics=ads,
            player_profiles=profiles,
            creative_attribution=attribution,
        )

        # c_001 IAA = 50 + 30 = 80, 无 IAP → revenue=80
        assert metrics["c_001"]["revenue"] == pytest.approx(80.0, abs=0.1)
        # roas = 80 / 200 = 0.4
        assert metrics["c_001"]["roas"] == pytest.approx(0.4, abs=0.01)

        # c_002 IAA = 70
        assert metrics["c_002"]["revenue"] == pytest.approx(70.0, abs=0.1)

        assert report.revenue_enriched == 2

    def test_iaa_no_attribution_skipped(self):
        """有 profiles 但无 attribution → IAA 不分摊。"""
        ads = _make_ads_metrics()
        profiles = _make_profiles({"u_001": 50.0})

        adapter = MetricsAdapter()
        metrics, report = adapter.adapt(
            ads_metrics=ads,
            player_profiles=profiles,
            creative_attribution=None,
        )

        assert metrics["c_001"]["revenue"] == 100.0  # 原值不变
        assert report.revenue_enriched == 0

    def test_iaa_unknown_user_skipped(self):
        """归因到未知 creative 的 user → 跳过。"""
        ads = _make_ads_metrics()
        profiles = _make_profiles({"u_001": 50.0, "u_002": 100.0})
        attribution = {"u_001": "c_001", "u_002": "c_UNKNOWN"}

        adapter = MetricsAdapter()
        metrics, _ = adapter.adapt(
            ads_metrics=ads,
            player_profiles=profiles,
            creative_attribution=attribution,
        )

        # 只有 u_001 的 50 归因到 c_001
        assert metrics["c_001"]["revenue"] == pytest.approx(50.0, abs=0.1)
        # c_002 无 IAA → 原值不变
        assert metrics["c_002"]["revenue"] == 180.0

    def test_iap_plus_iaa_combined(self):
        """IAP + IAA 合并为真实收入。"""
        ads = _make_ads_metrics()
        # IAP=500, 按 spend 分摊: c_001=200, c_002=300
        snapshots = _make_snapshots(iap_revenue=500.0, arpu=1.0)
        # IAA: c_001=80, c_002=70
        profiles = _make_profiles({"u_001": 80.0, "u_002": 70.0})
        attribution = {"u_001": "c_001", "u_002": "c_002"}

        adapter = MetricsAdapter()
        metrics, report = adapter.adapt(
            ads_metrics=ads,
            seven_domain_snapshots=snapshots,
            player_profiles=profiles,
            creative_attribution=attribution,
        )

        # c_001: IAP=500*(200/500)=200 + IAA=80 = 280
        assert metrics["c_001"]["revenue"] == pytest.approx(280.0, abs=0.1)
        # c_002: IAP=500*(300/500)=300 + IAA=70 = 370
        assert metrics["c_002"]["revenue"] == pytest.approx(370.0, abs=0.1)

        assert report.revenue_enriched == 2


# ──────────────────────────────────────────────
# Installs 校验测试
# ──────────────────────────────────────────────


class TestInstallsEnrichment:
    """用产品侧真实 installs 校验广告侧反推 installs。"""

    def test_installs_discrepancy_logged(self):
        """广告侧 vs 产品侧 installs 偏差大时记录 (不替换)。"""
        ads = _make_ads_metrics()
        # 广告侧总 installs = 100 + 100 = 200
        # 产品侧真实 = 500 → 偏差 150% > 30%
        snapshots = _make_snapshots(iap_revenue=0, real_installs=500)

        adapter = MetricsAdapter()
        metrics, report = adapter.adapt(
            ads_metrics=ads, seven_domain_snapshots=snapshots,
        )

        # installs 不替换
        assert metrics["c_001"]["installs"] == 100  # 原值不变
        assert report.installs_enriched == 1  # 有校验记录

    def test_no_funnel_skipped(self):
        """无 Funnel 快照 → 跳过 installs 校验。"""
        ads = _make_ads_metrics()
        snapshots = {"Monetization": MockMonetizationSnapshot(total_revenue=100)}

        adapter = MetricsAdapter()
        _, report = adapter.adapt(
            ads_metrics=ads, seven_domain_snapshots=snapshots,
        )

        assert report.installs_enriched == 0


# ──────────────────────────────────────────────
# 产品上下文测试
# ──────────────────────────────────────────────


class TestProductContext:
    """产品上下文附加到 _context 字段。"""

    def test_context_attached(self):
        """七域快照中的产品指标附加到 _context。"""
        ads = _make_ads_metrics()
        snapshots = _make_snapshots(
            iap_revenue=1000.0, real_installs=200,
            d1_retention=0.35, arpu=1.5,
        )

        adapter = MetricsAdapter()
        metrics, report = adapter.adapt(
            ads_metrics=ads, seven_domain_snapshots=snapshots,
        )

        for cid in ("c_001", "c_002"):
            assert "_context" in metrics[cid]
            ctx = metrics[cid]["_context"]
            assert ctx["d1_retention"] == 0.35
            assert ctx["d7_retention"] == pytest.approx(0.175, abs=0.01)
            assert ctx["arpu"] == 1.5
            assert ctx["avg_value_score"] == 0.65
            assert ctx["total_players"] == 8000

        assert report.context_added == 2

    def test_no_snapshots_no_context(self):
        """无七域快照 → 不附加 _context。"""
        ads = _make_ads_metrics()
        adapter = MetricsAdapter()
        metrics, _ = adapter.adapt(ads_metrics=ads)

        assert "_context" not in metrics["c_001"]


# ──────────────────────────────────────────────
# 端到端: 适配后可直接传入 DiagnosticEngine
# ──────────────────────────────────────────────


class TestEndToEndWithDiagnostic:
    """适配后 metrics 可直接传入 DiagnosticEngine。"""

    def test_adapted_metrics_work_with_diagnostic_engine(self):
        """适配后 metrics 不破坏 DiagnosticEngine 诊断。"""
        from scripts.diagnostic_engine import DiagnosticEngine

        ads = _make_ads_metrics()
        snapshots = _make_snapshots(
            iap_revenue=500.0, arpu=1.0, d1_retention=0.3,
        )

        adapter = MetricsAdapter()
        metrics, _ = adapter.adapt(
            ads_metrics=ads, seven_domain_snapshots=snapshots,
        )

        # 构造一个 roas_decline 信号
        signal = type("Signal", (), {
            "signal_type": "roas_decline",
            "creative_id": "c_001",
            "signal_id": "fs_e2e_001",
        })()

        engine = DiagnosticEngine()
        previous_metrics = {
            "c_001": {
                "spend": 200.0, "ctr": 0.03, "cpi": 2.0,
                "roas": 1.5, "impressions": 5000, "installs": 100,
            }
        }

        # 应该能正常诊断, 不报错
        result = engine.diagnose(
            signal=signal,
            current_metrics=metrics["c_001"],
            previous_metrics=previous_metrics["c_001"],
        )

        assert result.creative_id == "c_001"
        assert result.signal_type == "roas_decline"
        # 诊断不应降级为 undiagnosed (spend 和 ctr 都非零)
        assert result.root_cause.value != "undiagnosed" or result.confidence > 0

    def test_convenience_function(self):
        """adapt_metrics 便捷函数返回纯 metrics (无 report)。"""
        ads = _make_ads_metrics()
        snapshots = _make_snapshots(iap_revenue=500.0, arpu=1.0)

        metrics = adapt_metrics(
            ads_metrics=ads, seven_domain_snapshots=snapshots,
        )

        assert len(metrics) == 2
        assert metrics["c_001"]["revenue"] > 0
        # 便捷函数不返回 report
        assert "_context" in metrics["c_001"]
