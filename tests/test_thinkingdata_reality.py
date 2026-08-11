"""ThinkingDataReality 单元测试。

验证产品行为真相层的核心逻辑：
  1. Mock 模式下 fetch_campaign_users 生成确定性数据
  2. fetch_recent_retention 按渠道生成留存数据
  3. fetch_user_cluster 按分群名生成用户数据
  4. fetch_multi_revenue 过滤非付费用户
  5. RealityDataHub 集成 ThinkingData 后合并逻辑正确
  6. ProductBehaviorRecord 模型完整性
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# 确保 src 在路径中
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from market_ops.creative_vision_runtime.reality.models import (
    ProductBehaviorRecord,
    RealitySource,
    RealitySnapshot,
    CampaignReality,
)
from market_ops.creative_vision_runtime.reality.thinkingdata_reality import (
    ThinkingDataReality,
)


# ── ProductBehaviorRecord 模型测试 ──────────────────────────


class TestProductBehaviorRecord:
    """ProductBehaviorRecord 数据模型测试。"""

    def test_default_values(self):
        """默认值构造。"""
        record = ProductBehaviorRecord()
        assert record.source == RealitySource.THINKING_DATA
        assert record.is_payer is False
        assert record.payer_segment == "non_payer"
        assert record.record_id  # 自动生成 UUID
        assert record.recorded_at  # 自动生成时间戳

    def test_payer_auto_segment(self):
        """付费用户自动设置 payer_segment。"""
        record = ProductBehaviorRecord(
            user_id="u001",
            is_payer=True,
            total_revenue=29.99,
        )
        assert record.payer_segment == "first_payer"

    def test_whale_segment(self):
        """大R玩家自动设置 whale 分层。"""
        record = ProductBehaviorRecord(
            user_id="u002",
            is_payer=True,
            total_revenue=600.0,
            pay_count=5,
        )
        assert record.payer_segment == "whale"

    def test_non_payer_overrides_segment(self):
        """非付费用户强制设置 non_payer。"""
        record = ProductBehaviorRecord(
            user_id="u003",
            is_payer=False,
            payer_segment="whale",  # 错误的初始值
        )
        assert record.payer_segment == "non_payer"

    def test_to_dict_contains_all_fields(self):
        """to_dict 包含所有字段。"""
        record = ProductBehaviorRecord(
            project_id=102,
            user_id="u004",
            is_payer=True,
            total_revenue=49.99,
            d7_retention=0.35,
        )
        d = record.to_dict()
        assert d["project_id"] == 102
        assert d["user_id"] == "u004"
        assert d["is_payer"] is True
        assert d["total_revenue"] == 49.99
        assert d["d7_retention"] == 0.35
        assert d["source"] == "thinking_data"
        assert "record_id" in d
        assert "recorded_at" in d

    def test_repr(self):
        """__repr__ 格式正确。"""
        record = ProductBehaviorRecord(
            user_id="u005",
            lifecycle_stage="retention",
            d7_retention=0.25,
            is_payer=True,
        )
        r = repr(record)
        assert "u005" in r
        assert "retention" in r
        assert "payer=True" in r


# ── ThinkingDataReality Mock 模式测试 ──────────────────────


class TestThinkingDataRealityMock:
    """Mock 模式（无 client）下的 ThinkingDataReality 测试。"""

    def test_not_connected_without_client(self):
        """无 client 时 is_connected 返回 False。"""
        reality = ThinkingDataReality()
        assert reality.is_connected() is False

    def test_fetch_campaign_users_mock(self):
        """Mock 模式下生成确定性用户行为数据。"""
        reality = ThinkingDataReality()
        records = reality.fetch_campaign_users(102, ["camp_001"])

        assert len(records) == 10  # mock 生成 10 个用户
        assert all(isinstance(r, ProductBehaviorRecord) for r in records)
        assert all(r.project_id == 102 for r in records)
        assert all(r.campaign_id == "camp_001" for r in records)
        assert reality.total_fetched == 10
        assert reality.last_fetched_at is not None

    def test_mock_deterministic(self):
        """相同 campaign_id 生成相同的 mock 数据。"""
        reality1 = ThinkingDataReality()
        reality2 = ThinkingDataReality()
        records1 = reality1.fetch_campaign_users(102, ["camp_001"])
        records2 = reality2.fetch_campaign_users(102, ["camp_001"])

        for r1, r2 in zip(records1, records2):
            assert r1.user_id == r2.user_id
            assert r1.is_payer == r2.is_payer
            assert r1.total_revenue == r2.total_revenue

    def test_mock_has_payers_and_non_payers(self):
        """Mock 数据包含付费和非付费用户。"""
        reality = ThinkingDataReality()
        records = reality.fetch_campaign_users(102, ["camp_test"])
        payers = [r for r in records if r.is_payer]
        non_payers = [r for r in records if not r.is_payer]
        assert len(payers) > 0
        assert len(non_payers) > 0

    def test_mock_payer_segment_diversity(self):
        """Mock 数据包含多种付费分层。"""
        reality = ThinkingDataReality()
        records = reality.fetch_campaign_users(102, ["camp_diverse"])
        segments = {r.payer_segment for r in records}
        assert "non_payer" in segments
        # 至少有一种付费分层
        assert len(segments) >= 2

    def test_fetch_recent_retention_mock(self):
        """Mock 模式下生成渠道留存数据。"""
        reality = ThinkingDataReality()
        records = reality.fetch_recent_retention(102, lookback_days=7)

        assert len(records) == 5  # 5 个渠道
        channels = {r.channel for r in records}
        assert "meta" in channels
        assert "google" in channels
        assert all(r.lifecycle_stage == "retention" for r in records)
        assert all(r.d1_retention > 0 for r in records)
        assert all(r.d7_retention < r.d1_retention for r in records)

    def test_fetch_user_cluster_mock(self):
        """Mock 模式下生成分群用户数据。"""
        reality = ThinkingDataReality()
        records = reality.fetch_user_cluster(102, "付费用户")

        assert len(records) > 0
        assert all(r.is_payer for r in records)
        assert all(r.payer_segment in ("first_payer", "repeat_payer", "whale") for r in records)

    def test_fetch_user_cluster_churn(self):
        """流失风险分群。"""
        reality = ThinkingDataReality()
        records = reality.fetch_user_cluster(102, "流失风险用户")

        assert len(records) > 0
        assert all(r.lifecycle_stage == "churn" for r in records)

    def test_fetch_multi_revenue_only_payers(self):
        """fetch_multi_revenue 仅返回付费用户。"""
        reality = ThinkingDataReality()
        records = reality.fetch_multi_revenue(102, ["camp_001"])

        assert len(records) > 0
        assert all(r.is_payer for r in records)
        assert all(r.total_revenue > 0 for r in records)

    def test_fetch_empty_campaign_ids(self):
        """空 campaign_ids 返回空列表。"""
        reality = ThinkingDataReality()
        records = reality.fetch_campaign_users(102, [])
        assert records == []


# ── ThinkingDataReality 真实 client 模式测试 ───────────────


class TestThinkingDataRealityWithClient:
    """有 client 时的 ThinkingDataReality 测试（mock client）。"""

    def test_connected_with_client(self):
        """有 client 时 is_connected 返回 True。"""
        client = MagicMock()
        reality = ThinkingDataReality(client)
        assert reality.is_connected() is True

    def test_sql_query_calls_client(self):
        """fetch_campaign_users 调用 client.sql_query。"""
        client = MagicMock()
        client.sql_query.return_value = {
            "data": [
                {
                    "user_id": "td_user_1",
                    "install_date": "2026-07-01",
                    "last_active_date": "2026-08-01",
                    "active_days": 31,
                    "session_count": 50,
                    "level": 25,
                    "total_revenue": 99.99,
                    "pay_count": 3,
                    "first_pay_date": "2026-07-05",
                    "country": "US",
                    "channel": "meta",
                    "campaign_id": "camp_td_1",
                    "platform": "ios",
                }
            ]
        }

        reality = ThinkingDataReality(client)
        records = reality.fetch_campaign_users(102, ["camp_td_1"])

        assert len(records) == 1
        r = records[0]
        assert r.user_id == "td_user_1"
        assert r.is_payer is True
        assert r.total_revenue == 99.99
        assert r.pay_count == 3
        assert r.payer_segment == "repeat_payer"
        assert r.channel == "meta"
        assert r.campaign_id == "camp_td_1"
        assert r.country == "US"
        assert r.platform == "ios"

    def test_sql_query_fallback_to_mock_on_error(self):
        """SQL 查询失败时降级到 mock。"""
        client = MagicMock()
        client.sql_query.side_effect = Exception("API timeout")

        reality = ThinkingDataReality(client)
        records = reality.fetch_campaign_users(102, ["camp_err"])

        assert len(records) == 10  # mock 数据
        assert all(r.campaign_id == "camp_err" for r in records)

    def test_retention_analyze_calls_client(self):
        """fetch_recent_retention 调用 client.retention_analyze。"""
        client = MagicMock()
        client.retention_analyze.return_value = {
            "data": {
                "rows": [
                    {
                        "groups": ["meta"],
                        "values": [0.45, 0.25, 0.10],
                    },
                    {
                        "groups": ["google"],
                        "values": [0.40, 0.22, 0.08],
                    },
                ]
            }
        }

        reality = ThinkingDataReality(client)
        records = reality.fetch_recent_retention(102, lookback_days=7)

        assert len(records) == 2
        assert records[0].channel == "meta"
        assert records[0].d1_retention == 0.45
        assert records[0].d7_retention == 0.25
        assert records[0].d30_retention == 0.10
        assert records[1].channel == "google"
        assert records[1].d1_retention == 0.40

    def test_cluster_detail_calls_client(self):
        """fetch_user_cluster 调用 client.get_user_cluster_detail。"""
        client = MagicMock()
        client.get_user_cluster_detail.return_value = {
            "user_ids": ["u001", "u002", "u003"],
        }

        reality = ThinkingDataReality(client)
        records = reality.fetch_user_cluster(102, "付费用户")

        assert len(records) == 3
        assert all(r.user_id in ("u001", "u002", "u003") for r in records)


# ── RealityDataHub 集成测试 ────────────────────────────────


class TestRealityDataHubIntegration:
    """RealityDataHub 集成 ThinkingData 后的合并测试。"""

    def test_hub_with_thinkingdata_only(self):
        """仅 ThinkingData 数据源的 Hub poll。"""
        from market_ops.creative_vision_runtime.reality import RealityDataHub

        td_reality = ThinkingDataReality()
        hub = RealityDataHub(thinkingdata=td_reality)

        snapshot = hub.poll(["camp_integration_1", "camp_integration_2"])

        assert isinstance(snapshot, RealitySnapshot)
        assert len(snapshot.campaigns) == 2
        # ThinkingData mock 数据应影响留存和付费率
        for campaign in snapshot.campaigns:
            assert campaign.retention_d7 > 0  # 数数提供真实留存

    def test_hub_is_ready_with_thinkingdata(self):
        """Hub is_ready 包含 ThinkingData 检查。"""
        from market_ops.creative_vision_runtime.reality import RealityDataHub

        td_reality = ThinkingDataReality()  # 无 client → not connected
        hub = RealityDataHub(thinkingdata=td_reality)
        assert hub.is_ready() is False  # ThinkingData 未连接

        td_reality_connected = ThinkingDataReality(MagicMock())
        hub2 = RealityDataHub(thinkingdata=td_reality_connected)
        assert hub2.is_ready() is True

    def test_hub_with_all_three_sources(self):
        """Meta Ads + Adjust + ThinkingData 三源合并。"""
        from market_ops.creative_vision_runtime.reality import (
            RealityDataHub,
            MetaAdsReality,
            AdjustReality,
        )

        hub = RealityDataHub(
            meta_ads=MetaAdsReality(),
            adjust=AdjustReality(),
            thinkingdata=ThinkingDataReality(),
        )

        snapshot = hub.poll(["camp_all_1", "camp_all_2"])

        assert len(snapshot.campaigns) == 2
        # 每个campaign应有来自三源的数据
        for c in snapshot.campaigns:
            assert c.spend > 0  # 来自 Meta Ads mock
            assert c.revenue_d30 > 0  # 来自 Adjust 或 ThinkingData
            assert c.retention_d7 > 0  # 被 ThinkingData 增强

    def test_hub_thinkingdata_enhances_retention(self):
        """ThinkingData 数据增强留存指标。"""
        from market_ops.creative_vision_runtime.reality import (
            RealityDataHub,
            AdjustReality,
        )

        # 仅 Adjust → mock 留存 = 0.3
        hub_adjust_only = RealityDataHub(adjust=AdjustReality())
        snapshot1 = hub_adjust_only.poll(["camp_enhance"])
        retention_adjust_only = snapshot1.campaigns[0].retention_d7

        # Adjust + ThinkingData → 数数真实留存覆盖
        hub_both = RealityDataHub(
            adjust=AdjustReality(),
            thinkingdata=ThinkingDataReality(),
        )
        snapshot2 = hub_both.poll(["camp_enhance"])
        retention_with_td = snapshot2.campaigns[0].retention_d7

        # ThinkingData 的留存数据应覆盖或增强 Adjust 的 mock 值
        assert retention_with_td >= retention_adjust_only


# ── 生命周期推断测试 ────────────────────────────────────────


class TestLifecycleInference:
    """生命周期阶段推断逻辑测试。"""

    def test_infer_engagement(self):
        """最近活跃 → engagement。"""
        from datetime import date as d
        today = d.today().isoformat()
        stage = ThinkingDataReality._infer_lifecycle_stage(today, False)
        assert stage == "engagement"

    def test_infer_churn(self):
        """30 天前活跃 → churn。"""
        from datetime import timedelta, date as d
        old_date = (d.today() - timedelta(days=45)).isoformat()
        stage = ThinkingDataReality._infer_lifecycle_stage(old_date, False)
        assert stage == "churn"

    def test_infer_empty_date(self):
        """空日期 → install。"""
        stage = ThinkingDataReality._infer_lifecycle_stage("", False)
        assert stage == "install"

    def test_payer_segment_non_payer(self):
        """无付费 → non_payer。"""
        seg = ThinkingDataReality._infer_payer_segment(0.0, 0)
        assert seg == "non_payer"

    def test_payer_segment_first_payer(self):
        """一次付费 → first_payer。"""
        seg = ThinkingDataReality._infer_payer_segment(9.99, 1)
        assert seg == "first_payer"

    def test_payer_segment_whale(self):
        """大额付费 → whale。"""
        seg = ThinkingDataReality._infer_payer_segment(600.0, 5)
        assert seg == "whale"

    def test_payer_segment_repeat(self):
        """多次小额付费 → repeat_payer。"""
        seg = ThinkingDataReality._infer_payer_segment(50.0, 3)
        assert seg == "repeat_payer"


# ── 留存数据缓存测试 (P2-A) ────────────────────────────────


class TestRetentionCache:
    """验证 fetch_recent_retention 的 TTL 缓存逻辑。"""

    def test_cache_hit_returns_cached_data(self):
        """首次调用拉取数据，第二次命中缓存。"""
        reality = ThinkingDataReality()
        reality.clear_retention_cache()

        r1 = reality.fetch_recent_retention(102, lookback_days=7)
        assert len(r1) == 5

        # 第二次调用：应命中缓存，返回相同数据
        r2 = reality.fetch_recent_retention(102, lookback_days=7)
        assert len(r2) == 5
        for a, b in zip(r1, r2):
            assert a.channel == b.channel
            assert a.d1_retention == b.d1_retention
            assert a.d7_retention == b.d7_retention
            assert a.d30_retention == b.d30_retention

    def test_cache_bypass_with_use_cache_false(self):
        """use_cache=False 跳过缓存，强制重新拉取。"""
        reality = ThinkingDataReality()
        reality.clear_retention_cache()

        r1 = reality.fetch_recent_retention(102, lookback_days=7)
        # use_cache=False 应绕过缓存
        r2 = reality.fetch_recent_retention(102, lookback_days=7, use_cache=False)
        assert len(r2) == 5
        for a, b in zip(r1, r2):
            assert a.channel == b.channel

    def test_clear_cache_evicts_all(self):
        """clear_retention_cache 清空缓存后重新拉取。"""
        reality = ThinkingDataReality()

        r1 = reality.fetch_recent_retention(102, lookback_days=7)
        reality.clear_retention_cache()
        r2 = reality.fetch_recent_retention(102, lookback_days=7)

        # 清空后重新拉取，数据仍一致（Mock 模式确定性）
        for a, b in zip(r1, r2):
            assert a.channel == b.channel
            assert a.d1_retention == b.d1_retention

    def test_different_keys_independent(self):
        """不同 project_id / lookback_days 使用独立缓存键。"""
        reality = ThinkingDataReality()
        reality.clear_retention_cache()

        r_102_7 = reality.fetch_recent_retention(102, lookback_days=7)
        r_102_30 = reality.fetch_recent_retention(102, lookback_days=30)
        r_103_7 = reality.fetch_recent_retention(103, lookback_days=7)

        # 不同参数应产生各自的缓存条目
        assert len(r_102_7) == 5
        assert len(r_102_30) == 5
        assert len(r_103_7) == 5

        # 缓存中应有 3 个独立条目
        assert len(reality._retention_cache) == 3

    def test_cache_with_mock_client(self):
        """Mock client 场景下缓存同样生效。"""
        client = MagicMock()
        client.retention_analyze.return_value = {
            "data": {
                "rows": [
                    {"groups": ["meta"], "values": [0.45, 0.25, 0.10]},
                ]
            }
        }

        reality = ThinkingDataReality(client)
        reality.clear_retention_cache()

        r1 = reality.fetch_recent_retention(102, lookback_days=7)
        assert client.retention_analyze.call_count == 1

        r2 = reality.fetch_recent_retention(102, lookback_days=7)
        # 缓存命中，不应再次调用 API
        assert client.retention_analyze.call_count == 1
        assert len(r2) == 1
        assert r2[0].channel == "meta"

    def test_cache_preserves_data_integrity(self):
        """缓存数据与首次拉取数据完全一致。"""
        reality = ThinkingDataReality()
        reality.clear_retention_cache()

        r1 = reality.fetch_recent_retention(102, lookback_days=7)
        r2 = reality.fetch_recent_retention(102, lookback_days=7)

        for i in range(len(r1)):
            assert r1[i].to_dict() == r2[i].to_dict()


# ── Lifecycle + Retention 共享缓存集成测试 ──────────────────


class TestLifecycleRetentionSharedCache:
    """验证 LifecycleAnalyzer 和 RetentionAnalyzer 共享缓存数据。"""

    def test_shared_cache_consistent_results(self):
        """两个分析器使用同一缓存，结果一致。"""
        from market_ops.creative_vision_runtime.reality.analyzers import (
            LifecycleAnalyzer,
            RetentionAnalyzer,
        )

        td = ThinkingDataReality()
        td.clear_retention_cache()

        lc = LifecycleAnalyzer(td)
        rt = RetentionAnalyzer(td)

        lc_snap = lc.analyze(102, 30)
        rt_snap = rt.analyze(102, 30)

        # 两者 D7 留存应一致（共享缓存）
        assert lc_snap.d7_retention > 0
        assert rt_snap.d7_retention > 0
        assert abs(lc_snap.d7_retention - rt_snap.d7_retention) < 0.01

    def test_cache_hit_after_lifecycle_analyze(self):
        """LifecycleAnalyzer 调用后缓存被填充，RetentionAnalyzer 命中缓存。"""
        from market_ops.creative_vision_runtime.reality.analyzers import (
            LifecycleAnalyzer,
            RetentionAnalyzer,
        )

        td = ThinkingDataReality()
        td.clear_retention_cache()

        lc = LifecycleAnalyzer(td)
        lc.analyze(102, 30)

        # 缓存应已填充
        assert (102, 30) in td._retention_cache

        rt = RetentionAnalyzer(td)
        rt.analyze(102, 30)

        # 缓存仍存在
        assert (102, 30) in td._retention_cache


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
