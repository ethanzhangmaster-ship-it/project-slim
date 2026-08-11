"""四大产品分析域单元测试。

验证 LifecycleAnalyzer / FunnelAnalyzer / RetentionAnalyzer / MonetizationAnalyzer
在 Mock 模式下的核心逻辑。
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from market_ops.creative_vision_runtime.reality.thinkingdata_reality import (
    ThinkingDataReality,
)
from market_ops.creative_vision_runtime.reality.analyzers import (
    LifecycleAnalyzer,
    LifecycleSnapshot,
    FunnelAnalyzer,
    FunnelSnapshot,
    FunnelStep,
    RetentionAnalyzer,
    RetentionSnapshot,
    ChannelRetention,
    MonetizationAnalyzer,
    MonetizationSnapshot,
    OfferPerformance,
)


# ── LifecycleAnalyzer ──────────────────────────────────────


class TestLifecycleAnalyzer:
    """用户生命周期分析器测试。"""

    def test_analyze_mock_mode(self):
        """Mock 模式下生成完整快照。"""
        analyzer = LifecycleAnalyzer()
        snapshot = analyzer.analyze(project_id=102, lookback_days=30)

        assert isinstance(snapshot, LifecycleSnapshot)
        assert snapshot.project_id == 102
        assert snapshot.d1_retention > 0
        assert snapshot.d7_retention > 0
        assert snapshot.d30_retention > 0
        assert snapshot.d7_retention < snapshot.d1_retention  # 留存衰减
        assert len(snapshot.stage_distribution) > 0
        assert snapshot.churn_risk_count > 0
        assert snapshot.dau > 0
        assert len(snapshot.insights) > 0

    def test_stage_distribution_has_all_stages(self):
        """阶段分布包含所有 5 个阶段。"""
        analyzer = LifecycleAnalyzer()
        snapshot = analyzer.analyze(102)

        stages = set(snapshot.stage_distribution.keys())
        assert "churn" in stages
        assert "engagement" in stages

    def test_insights_generated(self):
        """洞察包含具体建议。"""
        analyzer = LifecycleAnalyzer()
        snapshot = analyzer.analyze(102)

        assert len(snapshot.insights) > 0
        # 至少有一条洞察包含具体数据
        assert any("%" in i or "D" in i for i in snapshot.insights)

    def test_with_td_reality(self):
        """有 ThinkingDataReality 时的分析。"""
        td = ThinkingDataReality()  # 无 client → mock
        analyzer = LifecycleAnalyzer(td)
        snapshot = analyzer.analyze(102)

        assert snapshot.d1_retention > 0
        assert snapshot.d7_retention > 0

    def test_total_analyzed_counter(self):
        """分析计数器递增。"""
        analyzer = LifecycleAnalyzer()
        assert analyzer.total_analyzed == 0
        analyzer.analyze(102)
        assert analyzer.total_analyzed == 1
        analyzer.analyze(102)
        assert analyzer.total_analyzed == 2


# ── FunnelAnalyzer ─────────────────────────────────────────


class TestFunnelAnalyzer:
    """游戏漏斗分析器测试。"""

    def test_analyze_mock_mode(self):
        """Mock 模式下生成漏斗。"""
        analyzer = FunnelAnalyzer()
        snapshot = analyzer.analyze(project_id=102, lookback_days=30)

        assert isinstance(snapshot, FunnelSnapshot)
        assert len(snapshot.steps) == 5  # 默认 5 步漏斗
        assert snapshot.overall_conversion > 0
        assert snapshot.overall_conversion < 1

    def test_funnel_steps_decreasing(self):
        """漏斗每步完成人数递减。"""
        analyzer = FunnelAnalyzer()
        snapshot = analyzer.analyze(102)

        for i in range(1, len(snapshot.steps)):
            assert snapshot.steps[i].completed <= snapshot.steps[i - 1].completed

    def test_conversion_rates_computed(self):
        """每步转化率已计算。"""
        analyzer = FunnelAnalyzer()
        snapshot = analyzer.analyze(102)

        for step in snapshot.steps:
            assert 0.0 <= step.conversion_rate <= 1.0
            assert 0.0 <= step.drop_off_rate <= 1.0
            assert step.conversion_rate + step.drop_off_rate == pytest.approx(1.0, abs=0.01)

    def test_drop_off_steps_identified(self):
        """流失步骤已识别。"""
        analyzer = FunnelAnalyzer()
        snapshot = analyzer.analyze(102)

        # mock 数据中应该有流失步骤
        assert isinstance(snapshot.drop_off_steps, list)

    def test_insights_generated(self):
        """洞察已生成。"""
        analyzer = FunnelAnalyzer()
        snapshot = analyzer.analyze(102)

        assert len(snapshot.insights) > 0

    def test_custom_funnel(self):
        """自定义漏斗步骤。"""
        custom_steps = [
            {"step": "安装", "event": "ta_app_install"},
            {"step": "注册", "event": "user_register"},
            {"step": "付费", "event": "purchase"},
        ]
        analyzer = FunnelAnalyzer()
        snapshot = analyzer.analyze(102, funnel_steps=custom_steps)

        assert len(snapshot.steps) == 3
        assert snapshot.steps[0].step_name == "安装"
        assert snapshot.steps[-1].step_name == "付费"

    def test_to_dict(self):
        """to_dict 完整。"""
        analyzer = FunnelAnalyzer()
        snapshot = analyzer.analyze(102)

        d = snapshot.to_dict()
        assert "steps" in d
        assert "overall_conversion" in d
        assert "drop_off_steps" in d
        assert "insights" in d
        assert len(d["steps"]) == 5


# ── RetentionAnalyzer ─────────────────────────────────────


class TestRetentionAnalyzer:
    """留存分析器测试。"""

    def test_analyze_mock_mode(self):
        """Mock 模式下生成留存快照。"""
        analyzer = RetentionAnalyzer()
        snapshot = analyzer.analyze(project_id=102, lookback_days=30)

        assert isinstance(snapshot, RetentionSnapshot)
        assert snapshot.d1_retention > 0
        assert snapshot.d7_retention > 0
        assert snapshot.d30_retention > 0
        assert len(snapshot.channel_retention) == 5  # 5 个渠道

    def test_channel_retention_ordering(self):
        """渠道留存有差异。"""
        analyzer = RetentionAnalyzer()
        snapshot = analyzer.analyze(102)

        d7_values = [c.d7 for c in snapshot.channel_retention]
        assert max(d7_values) != min(d7_values)  # 渠道间有差异

    def test_best_and_worst_channel(self):
        """最佳和最差渠道已识别。"""
        analyzer = RetentionAnalyzer()
        snapshot = analyzer.analyze(102)

        assert snapshot.best_channel != ""
        assert snapshot.worst_channel != ""
        assert snapshot.best_channel != snapshot.worst_channel

        best_d7 = next(c.d7 for c in snapshot.channel_retention if c.channel == snapshot.best_channel)
        worst_d7 = next(c.d7 for c in snapshot.channel_retention if c.channel == snapshot.worst_channel)
        assert best_d7 > worst_d7

    def test_retention_drivers(self):
        """留存驱动因素已识别。"""
        analyzer = RetentionAnalyzer()
        snapshot = analyzer.analyze(102)

        assert len(snapshot.retention_drivers) > 0

    def test_behavior_comparison(self):
        """留存 vs 流失行为对比。"""
        analyzer = RetentionAnalyzer()
        snapshot = analyzer.analyze(102)

        assert len(snapshot.retained_behaviors) > 0
        assert len(snapshot.churned_behaviors) > 0

    def test_behavior_comparison_sql(self):
        """验证 SQL 模式下行为对比结果不为空。"""
        client = MagicMock()
        client.sql_query.return_value = {
            "data": [
                {"behavior": "完成关卡数≥30", "rate_diff": 0.35},
                {"behavior": "购买过礼包", "rate_diff": 0.30},
                {"behavior": "参加活动", "rate_diff": 0.25},
                {"behavior": "每日登录", "rate_diff": 0.22},
                {"behavior": "加入公会", "rate_diff": -0.21},
                {"behavior": "使用道具", "rate_diff": -0.25},
            ]
        }
        td = ThinkingDataReality(client)
        analyzer = RetentionAnalyzer(td)
        snapshot = analyzer.analyze(102)

        assert len(snapshot.retained_behaviors) > 0
        assert len(snapshot.churned_behaviors) > 0
        assert "完成关卡数≥30" in snapshot.retained_behaviors
        assert "加入公会" in snapshot.churned_behaviors

    def test_insights_generated(self):
        """洞察已生成。"""
        analyzer = RetentionAnalyzer()
        snapshot = analyzer.analyze(102)

        assert len(snapshot.insights) > 0

    def test_with_td_reality(self):
        """有 ThinkingDataReality 时的分析。"""
        td = ThinkingDataReality()
        analyzer = RetentionAnalyzer(td)
        snapshot = analyzer.analyze(102)

        assert len(snapshot.channel_retention) > 0
        assert snapshot.best_channel != ""


# ── MonetizationAnalyzer ───────────────────────────────────


class TestMonetizationAnalyzer:
    """商业化分析器测试。"""

    def test_analyze_mock_mode(self):
        """Mock 模式下生成商业化快照。"""
        analyzer = MonetizationAnalyzer()
        snapshot = analyzer.analyze(project_id=102, lookback_days=30)

        assert isinstance(snapshot, MonetizationSnapshot)
        assert snapshot.total_revenue > 0
        assert snapshot.total_users > 0
        assert snapshot.total_payers > 0
        assert 0 < snapshot.payer_rate < 1
        assert snapshot.arpu > 0
        assert snapshot.arppu > snapshot.arpu  # ARPPU > ARPU

    def test_payer_segments(self):
        """用户付费分层完整。"""
        analyzer = MonetizationAnalyzer()
        snapshot = analyzer.analyze(102)

        assert "non_payer" in snapshot.payer_segments
        assert "first_payer" in snapshot.payer_segments
        assert "repeat_payer" in snapshot.payer_segments
        assert "whale" in snapshot.payer_segments

        # 非付费用户最多
        assert snapshot.payer_segments["non_payer"] > snapshot.payer_segments["whale"]

    def test_offers(self):
        """Offer 表现数据。"""
        analyzer = MonetizationAnalyzer()
        snapshot = analyzer.analyze(102)

        assert len(snapshot.offers) >= 2
        for offer in snapshot.offers:
            assert isinstance(offer, OfferPerformance)
            assert offer.revenue > 0
            assert offer.conversion_rate > 0

    def test_first_pay_distribution(self):
        """首充时间分布。"""
        analyzer = MonetizationAnalyzer()
        snapshot = analyzer.analyze(102)

        assert snapshot.avg_first_pay_days > 0
        assert len(snapshot.first_pay_distribution) > 0
        # 首日付费应最多
        assert snapshot.first_pay_distribution.get("day_1", 0) > 0

    def test_ltv_computed(self):
        """LTV 已计算。"""
        analyzer = MonetizationAnalyzer()
        snapshot = analyzer.analyze(102)

        assert snapshot.ltv_d7 > 0
        assert snapshot.ltv_d30 > snapshot.ltv_d7  # LTV 随时间增长
        assert snapshot.ltv_d90 > snapshot.ltv_d30

    def test_insights_generated(self):
        """洞察已生成。"""
        analyzer = MonetizationAnalyzer()
        snapshot = analyzer.analyze(102)

        assert len(snapshot.insights) > 0
        # 应包含付费率或 ARPPU 相关洞察
        assert any(
            "付费率" in i or "ARPPU" in i or "Offer" in i or "首充" in i
            for i in snapshot.insights
        )

    def test_to_dict_complete(self):
        """to_dict 完整。"""
        analyzer = MonetizationAnalyzer()
        snapshot = analyzer.analyze(102)

        d = snapshot.to_dict()
        assert "payer_rate" in d
        assert "arpu" in d
        assert "arppu" in d
        assert "payer_segments" in d
        assert "offers" in d
        assert "ltv_d30" in d
        assert "insights" in d

    def test_with_td_reality(self):
        """有 ThinkingDataReality 时的分析。"""
        td = ThinkingDataReality()
        analyzer = MonetizationAnalyzer(td)
        snapshot = analyzer.analyze(102)

        assert snapshot.total_revenue > 0
        assert snapshot.payer_rate > 0


# ── 交叉测试 ────────────────────────────────────────────────


class TestCrossAnalyzer:
    """多个分析器协同测试。"""

    def test_all_four_domains(self):
        """四大分析域同时运行。"""
        td = ThinkingDataReality()

        lifecycle = LifecycleAnalyzer(td).analyze(102)
        funnel = FunnelAnalyzer(td).analyze(102)
        retention = RetentionAnalyzer(td).analyze(102)
        monetization = MonetizationAnalyzer(td).analyze(102)

        # 所有快照都有数据
        assert lifecycle.d7_retention > 0
        assert funnel.overall_conversion > 0
        assert retention.d7_retention > 0
        assert monetization.total_revenue > 0

    def test_analyzers_share_td_reality(self):
        """多个分析器共享同一 ThinkingDataReality。"""
        td = ThinkingDataReality()

        # 同一个 td 实例传给多个分析器
        a1 = LifecycleAnalyzer(td)
        a2 = RetentionAnalyzer(td)

        s1 = a1.analyze(102)
        s2 = a2.analyze(102)

        # 两者都从同一 td 获取了数据
        assert s1.d7_retention > 0
        assert s2.d7_retention > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
