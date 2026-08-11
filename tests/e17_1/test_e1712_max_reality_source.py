"""P1.2 — MaxRealitySource 测试。

覆盖：
1. SIM 回退：确定性样本，real_api_called 恒 False。
2. 生产模式 + 真实 ACCT 报表文件：真读 data/ACCT_TEST_report.json 并 real_api_called=True，
   collector 层 flag 透出；报表无对应 application 时返回 {}。
3. E2E：MaxRealitySource 进 GrowthRealityHub → 公司快照含真实 revenue，
   hub.last_real_api_called == True。

复用验证：生产模式直接读 operation 既有的 data/<ACCT>_report.json 真报表
（与每日 09:30 自动化拉取的同一份真实数据），不新建重复加载层。
"""
from __future__ import annotations

import os

from src.growth_reality.agent import GrowthRealityHub
from src.growth_reality.collector import RealityCollector
from src.growth_reality.production_sources.max_source import MaxRealitySource

# 不可变 fixture 目录：与 data/ 共享缓存解耦。
# 背景：e15_1_2 的晨报测试会经 intelligence_agent cache_rows=True 按「当天往前
# 的窗口」重写 data/ACCT_TEST_report.json，日期推进后会把 5 天样本截短，
# date-dependent 地弄挂本文件的断言 —— 测试 fixture 必须只读。
FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


# --------------------------------------------------------------------------- #
# 1. SIM 回退
# --------------------------------------------------------------------------- #
def test_sim_returns_bundle_and_never_calls_real_api():
    src = MaxRealitySource(mode="sim")
    out = src.collect("merge_monster", "2026-07-29")
    assert set(out.keys()) == {"revenue"}
    rev = out["revenue"]
    assert rev["daily_revenue"] > 0
    assert rev["impressions"] > 0
    assert rev["requests"] > 0
    assert rev["ecpm"] > 0
    assert rev["network_distribution"]
    assert src.real_api_called is False

    # 确定性：两次相同
    again = MaxRealitySource(mode="sim").collect("merge_monster", "2026-07-29")
    assert again == out


# --------------------------------------------------------------------------- #
# 2. 生产模式 + 真实报表文件
# --------------------------------------------------------------------------- #
def test_production_reads_real_report_and_flags():
    src = MaxRealitySource(accounts=["ACCT_TEST"], mode="production", data_dir=FIXTURES)
    out = src.collect("GameA", "2026-07-29")
    # 真读 data/ACCT_TEST_report.json（5 天 × 10.0 = 50，日均 10.0）
    assert src.real_api_called is True
    rev = out["revenue"]
    assert rev["daily_revenue"] == 10.0
    # GameA: impressions=400×5=2000, attempts=11000×5=55000, rev=50 → eCPM=25.0
    assert rev["impressions"] == 2000
    assert rev["requests"] == 55000
    assert rev["ecpm"] == 25.0
    # 全部 REWARD 格式 → rewarded_video_revenue 日均 = 50/5 = 10.0
    assert rev["rewarded_video_revenue"] == 10.0
    assert rev["network_distribution"] == {"MINTEGRAL_BIDDING": 1.0}

    # collector 层汇聚 flag
    collector = RealityCollector(sources=[src])
    collector.collect_game("GameA", "2026-07-29")
    assert collector.real_api_called is True


def test_production_enriches_product_dau_from_user_metrics(monkeypatch):
    import operation.factory_brain.fleet_bridge as fb

    def fake_metrics(self, account):  # noqa: ANN001
        return {"app_dau": {"GameA": 2000}}

    monkeypatch.setattr(fb.RealFleetBridge, "load_user_metrics", fake_metrics)
    src = MaxRealitySource(accounts=["ACCT_TEST"], mode="production", data_dir=FIXTURES)
    out = src.collect("GameA", "2026-07-29")
    # 真实 DAU → product 域 + arpdau = 10.0/2000 = 0.005
    assert "product" in out
    assert out["product"]["dau"] == 2000
    assert out["revenue"]["arpdau"] == 0.005


def test_production_missing_report_returns_empty_and_no_flag():
    # 账号报表文件不存在 → 未读到任何真实数据 → real_api_called 恒 False
    src = MaxRealitySource(accounts=["ACCT_NOPE"], mode="production", data_dir=FIXTURES)
    assert src.collect("game_x", "2026-07-29") == {}
    assert src.real_api_called is False


def test_production_unknown_application_returns_empty_but_file_was_read():
    # 报表已读取（real_api_called=True），但该 application 无行 → 该 game 返回 {}
    src = MaxRealitySource(accounts=["ACCT_TEST"], mode="production", data_dir=FIXTURES)
    assert src.collect("ghost_game", "2026-07-29") == {}
    # 真实报表文件确实被读取过
    assert src.real_api_called is True


# --------------------------------------------------------------------------- #
# 3. E2E：进 GrowthRealityHub
# --------------------------------------------------------------------------- #
def test_e2e_hub_consumes_real_max():
    src = MaxRealitySource(accounts=["ACCT_TEST"], mode="production", data_dir=FIXTURES)
    hub = GrowthRealityHub(sources=[src])
    company = hub.refresh(["GameA", "GameB"], "2026-07-29", persist=False)

    assert hub.last_real_api_called is True
    snap_a = company.per_game["GameA"]
    assert snap_a.revenue is not None
    assert snap_a.revenue.daily_revenue == 10.0
    # 归一化层透传 MAX 原生变现指标（验证整链路未丢字段）
    assert snap_a.revenue.impressions == 2000
    assert snap_a.revenue.requests == 55000
    assert snap_a.revenue.ecpm == 25.0
    assert snap_a.revenue.rewarded_video_revenue == 10.0
    assert snap_a.revenue.network_distribution == {"MINTEGRAL_BIDDING": 1.0}
    # 仅覆盖 revenue 单域 → confidence = 1/5
    assert snap_a.confidence == 1 / 5

    snap_b = company.per_game["GameB"]
    assert snap_b.revenue is not None
    assert snap_b.revenue.daily_revenue == 1.0
