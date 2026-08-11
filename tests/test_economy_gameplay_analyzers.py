"""经济系统与玩法分析器单元测试。

验证 EconomyAnalyzer / GameplayAnalyzer 在 Mock 模式下的核心逻辑。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from market_ops.creative_vision_runtime.reality.thinkingdata_reality import (
    ThinkingDataReality,
)
from market_ops.creative_vision_runtime.reality.analyzers import (
    EconomyAnalyzer,
    EconomySnapshot,
    ResourceFlow,
    GameplayAnalyzer,
    GameplaySnapshot,
    LevelPerformance,
    ModeEngagement,
)


# ── EconomyAnalyzer ────────────────────────────────────────


class TestEconomyAnalyzer:
    """经济系统分析器测试。"""

    def test_analyze_mock_mode(self):
        """Mock 模式下生成经济快照。"""
        analyzer = EconomyAnalyzer()
        snapshot = analyzer.analyze(project_id=102, lookback_days=30)

        assert isinstance(snapshot, EconomySnapshot)
        assert snapshot.project_id == 102
        assert len(snapshot.resources) > 0
        assert snapshot.avg_inflation_rate != 0
        assert snapshot.overall_status != ""
        assert len(snapshot.insights) > 0

    def test_default_resources_tracked(self):
        """默认追踪 4 种资源。"""
        analyzer = EconomyAnalyzer()
        snapshot = analyzer.analyze(102)

        resource_names = {r.resource_name for r in snapshot.resources}
        assert "coins" in resource_names
        assert "gems" in resource_names
        assert "energy" in resource_names
        assert "materials" in resource_names

    def test_resource_flow_balance(self):
        """资源流 net_balance = source - sink。"""
        analyzer = EconomyAnalyzer()
        snapshot = analyzer.analyze(102)

        for flow in snapshot.resources:
            assert isinstance(flow, ResourceFlow)
            assert flow.net_balance == pytest.approx(
                flow.total_source - flow.total_sink, abs=0.01
            )

    def test_inflation_rate_sign(self):
        """通胀率符号与状态一致。"""
        analyzer = EconomyAnalyzer()
        snapshot = analyzer.analyze(102)

        for flow in snapshot.resources:
            if flow.status == "inflation":
                assert flow.inflation_rate > analyzer.INFLATION_THRESHOLD
            elif flow.status == "deflation":
                assert flow.inflation_rate < analyzer.DEFLATION_THRESHOLD
            else:
                assert (
                    analyzer.DEFLATION_THRESHOLD
                    <= flow.inflation_rate
                    <= analyzer.INFLATION_THRESHOLD
                )

    def test_imbalance_identification(self):
        """异常资源识别。"""
        analyzer = EconomyAnalyzer()
        snapshot = analyzer.analyze(102)

        # mock 数据中 coins 和 materials 通胀，gems 通缩
        assert "coins" in snapshot.inflation_resources
        assert "materials" in snapshot.inflation_resources
        assert "gems" in snapshot.deflation_resources

        # imbalanced_resources 是 inflation + deflation 的并集
        assert set(snapshot.imbalanced_resources) == (
            set(snapshot.inflation_resources) | set(snapshot.deflation_resources)
        )

    def test_top_sources_and_sinks(self):
        """Top 产出来源和消耗去向已填充。"""
        analyzer = EconomyAnalyzer()
        snapshot = analyzer.analyze(102)

        for flow in snapshot.resources:
            assert len(flow.top_sources) > 0
            assert len(flow.top_sinks) > 0
            # 每条都是 (name, value) 元组
            for name, value in flow.top_sources:
                assert isinstance(name, str)
                assert value > 0

    def test_payer_economy_metrics(self):
        """付费与经济关系指标。"""
        analyzer = EconomyAnalyzer()
        snapshot = analyzer.analyze(102)

        assert snapshot.payer_resource_ratio > 0
        assert snapshot.resource_hoarder_count > 0
        assert snapshot.resource_starved_count > 0

    def test_insights_content(self):
        """洞察包含具体建议。"""
        analyzer = EconomyAnalyzer()
        snapshot = analyzer.analyze(102)

        assert len(snapshot.insights) > 0
        # 应包含通胀/通缩相关或资源名
        assert any(
            "通胀" in i or "通缩" in i or "平衡" in i for i in snapshot.insights
        )

    def test_custom_resources(self):
        """自定义资源列表。"""
        analyzer = EconomyAnalyzer()
        snapshot = analyzer.analyze(102, resources=["gold", "diamond"])

        assert len(snapshot.resources) == 2
        names = {r.resource_name for r in snapshot.resources}
        assert names == {"gold", "diamond"}

    def test_to_dict_complete(self):
        """to_dict 完整。"""
        analyzer = EconomyAnalyzer()
        snapshot = analyzer.analyze(102)

        d = snapshot.to_dict()
        assert "project_id" in d
        assert "resources" in d
        assert "overall_status" in d
        assert "avg_inflation_rate" in d
        assert "imbalanced_resources" in d
        assert "inflation_resources" in d
        assert "deflation_resources" in d
        assert "payer_resource_ratio" in d
        assert "insights" in d
        assert len(d["resources"]) == len(snapshot.resources)

    def test_with_td_reality(self):
        """有 ThinkingDataReality 时的分析。"""
        td = ThinkingDataReality()  # 无 client → mock
        analyzer = EconomyAnalyzer(td)
        snapshot = analyzer.analyze(102)

        assert len(snapshot.resources) > 0
        assert snapshot.avg_inflation_rate != 0

    def test_total_analyzed_counter(self):
        """分析计数器递增。"""
        analyzer = EconomyAnalyzer()
        assert analyzer.total_analyzed == 0
        analyzer.analyze(102)
        assert analyzer.total_analyzed == 1
        analyzer.analyze(102)
        assert analyzer.total_analyzed == 2


# ── GameplayAnalyzer ───────────────────────────────────────


class TestGameplayAnalyzer:
    """玩法分析器测试。"""

    def test_analyze_mock_mode(self):
        """Mock 模式下生成玩法快照。"""
        analyzer = GameplayAnalyzer()
        snapshot = analyzer.analyze(project_id=102, lookback_days=30)

        assert isinstance(snapshot, GameplaySnapshot)
        assert snapshot.project_id == 102
        assert snapshot.total_players > 0
        assert snapshot.avg_session_len > 0
        assert snapshot.avg_sessions_per_user > 0
        assert len(snapshot.levels) > 0
        assert len(snapshot.modes) > 0
        assert len(snapshot.insights) > 0

    def test_level_performance_computed(self):
        """关卡通过率已计算。"""
        analyzer = GameplayAnalyzer()
        snapshot = analyzer.analyze(102)

        for level in snapshot.levels:
            assert isinstance(level, LevelPerformance)
            assert level.attempts >= 0
            assert level.passes >= 0
            assert level.passes <= level.attempts
            assert 0.0 <= level.pass_rate <= 1.0
            assert level.status in ("healthy", "choke_point", "too_easy")

    def test_choke_point_identified(self):
        """卡点关卡已识别。"""
        analyzer = GameplayAnalyzer()
        snapshot = analyzer.analyze(102)

        # mock 数据中 level_6 通过率 < 20%
        assert "level_6" in snapshot.choke_points
        for lvl_id in snapshot.choke_points:
            level = next(
                (l for l in snapshot.levels if l.level_id == lvl_id), None
            )
            assert level is not None
            assert level.pass_rate < analyzer.CHOKE_POINT_RATE

    def test_churn_levels_identified(self):
        """流失关卡已识别。"""
        analyzer = GameplayAnalyzer()
        snapshot = analyzer.analyze(102)

        # mock 数据中 level_6 流失率 0.18 > 0.15
        assert "level_6" in snapshot.churn_levels
        for lvl_id in snapshot.churn_levels:
            level = next(
                (l for l in snapshot.levels if l.level_id == lvl_id), None
            )
            assert level is not None
            assert level.churn_rate > analyzer.CHURN_RATE_THRESHOLD

    def test_mode_engagement(self):
        """玩法模式参与度。"""
        analyzer = GameplayAnalyzer()
        snapshot = analyzer.analyze(102)

        assert len(snapshot.modes) >= 3
        for mode in snapshot.modes:
            assert isinstance(mode, ModeEngagement)
            assert mode.mode_name != ""
            assert mode.participants > 0
            assert mode.sessions > 0
            assert mode.avg_sessions >= 0

    def test_popular_modes_sorted(self):
        """热门玩法按参与人数排序。"""
        analyzer = GameplayAnalyzer()
        snapshot = analyzer.analyze(102)

        assert len(snapshot.popular_modes) > 0
        # popular_modes 是参与人数 Top 3
        assert len(snapshot.popular_modes) <= 3

        # 验证排序
        mode_map = {m.mode_name: m.participants for m in snapshot.modes}
        if len(snapshot.popular_modes) >= 2:
            assert (
                mode_map[snapshot.popular_modes[0]]
                >= mode_map[snapshot.popular_modes[1]]
            )

    def test_difficulty_curve_evaluation(self):
        """难度曲线评价。"""
        analyzer = GameplayAnalyzer()
        snapshot = analyzer.analyze(102)

        # mock 中 10 个关卡只有 1 个卡点 → 1/10 = 10%
        # 在 FLAT(5%) 和 STEEP(30%) 之间 → healthy
        assert snapshot.difficulty_curve == "healthy"

    def test_top_actions_populated(self):
        """行为热度 Top 已填充。"""
        analyzer = GameplayAnalyzer()
        snapshot = analyzer.analyze(102)

        assert len(snapshot.top_actions) > 0
        for action, count in snapshot.top_actions:
            assert isinstance(action, str)
            assert count > 0

    def test_insights_content(self):
        """洞察包含难度曲线或卡点建议。"""
        analyzer = GameplayAnalyzer()
        snapshot = analyzer.analyze(102)

        assert len(snapshot.insights) > 0
        assert any(
            "难度曲线" in i or "卡点" in i or "玩法" in i for i in snapshot.insights
        )

    def test_custom_levels(self):
        """自定义关卡列表。"""
        analyzer = GameplayAnalyzer()
        snapshot = analyzer.analyze(102, levels=["custom_1", "custom_2"])

        # mock 模式下忽略 levels 参数，使用默认 mock 数据
        assert isinstance(snapshot, GameplaySnapshot)
        assert snapshot.project_id == 102

    def test_to_dict_complete(self):
        """to_dict 完整。"""
        analyzer = GameplayAnalyzer()
        snapshot = analyzer.analyze(102)

        d = snapshot.to_dict()
        assert "project_id" in d
        assert "total_players" in d
        assert "levels" in d
        assert "modes" in d
        assert "choke_points" in d
        assert "churn_levels" in d
        assert "popular_modes" in d
        assert "difficulty_curve" in d
        assert "top_actions" in d
        assert "insights" in d
        assert len(d["levels"]) == len(snapshot.levels)

    def test_with_td_reality(self):
        """有 ThinkingDataReality 时的分析。"""
        td = ThinkingDataReality()
        analyzer = GameplayAnalyzer(td)
        snapshot = analyzer.analyze(102)

        assert snapshot.total_players > 0
        assert len(snapshot.levels) > 0

    def test_total_analyzed_counter(self):
        """分析计数器递增。"""
        analyzer = GameplayAnalyzer()
        assert analyzer.total_analyzed == 0
        analyzer.analyze(102)
        assert analyzer.total_analyzed == 1
        analyzer.analyze(102)
        assert analyzer.total_analyzed == 2


# ── 交叉测试 ────────────────────────────────────────────────


class TestEconomyGameplayCross:
    """经济与玩法分析器协同测试。"""

    def test_both_domains_run_together(self):
        """经济与玩法同时运行。"""
        td = ThinkingDataReality()

        economy = EconomyAnalyzer(td).analyze(102)
        gameplay = GameplayAnalyzer(td).analyze(102)

        assert economy.avg_inflation_rate != 0
        assert gameplay.total_players > 0

    def test_share_td_reality(self):
        """两个分析器共享同一 ThinkingDataReality。"""
        td = ThinkingDataReality()

        e_analyzer = EconomyAnalyzer(td)
        g_analyzer = GameplayAnalyzer(td)

        e_snap = e_analyzer.analyze(102)
        g_snap = g_analyzer.analyze(102)

        assert len(e_snap.resources) > 0
        assert len(g_snap.levels) > 0

    def test_all_six_domains_together(self):
        """六大分析域同时运行（含此前 4 个）。"""
        from market_ops.creative_vision_runtime.reality.analyzers import (
            LifecycleAnalyzer,
            FunnelAnalyzer,
            RetentionAnalyzer,
            MonetizationAnalyzer,
        )

        td = ThinkingDataReality()

        lifecycle = LifecycleAnalyzer(td).analyze(102)
        funnel = FunnelAnalyzer(td).analyze(102)
        retention = RetentionAnalyzer(td).analyze(102)
        monetization = MonetizationAnalyzer(td).analyze(102)
        economy = EconomyAnalyzer(td).analyze(102)
        gameplay = GameplayAnalyzer(td).analyze(102)

        # 所有快照都有数据
        assert lifecycle.d7_retention > 0
        assert funnel.overall_conversion > 0
        assert retention.d7_retention > 0
        assert monetization.total_revenue > 0
        assert economy.avg_inflation_rate != 0
        assert gameplay.total_players > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
