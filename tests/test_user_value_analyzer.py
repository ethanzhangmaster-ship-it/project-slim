"""用户价值分析器单元测试。

验证 UserValueAnalyzer 在 Mock 模式下的核心逻辑：
  - 价值分层与评分
  - 价值构成（多维度贡献）
  - 价值演进
  - 价值集中度与结构评价
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
    UserValueAnalyzer,
    UserValueSnapshot,
    UserSegment,
    ValueContribution,
)


# ── UserValueAnalyzer ──────────────────────────────────────


class TestUserValueAnalyzer:
    """用户价值分析器测试。"""

    def test_analyze_mock_mode(self):
        """Mock 模式下生成用户价值快照。"""
        analyzer = UserValueAnalyzer()
        snapshot = analyzer.analyze(project_id=102, lookback_days=30)

        assert isinstance(snapshot, UserValueSnapshot)
        assert snapshot.project_id == 102
        assert snapshot.total_users > 0
        assert snapshot.avg_value_score > 0
        assert len(snapshot.segments) > 0
        assert snapshot.value_structure != ""
        assert len(snapshot.insights) > 0

    def test_segments_populated(self):
        """四个价值分层均已填充。"""
        analyzer = UserValueAnalyzer()
        snapshot = analyzer.analyze(102)

        segment_names = {s.segment_name for s in snapshot.segments}
        assert "high_value" in segment_names
        assert "mid_value" in segment_names
        assert "low_value" in segment_names
        assert "churn_risk" in segment_names

    def test_segment_counts_consistency(self):
        """分层用户数与汇总字段一致。"""
        analyzer = UserValueAnalyzer()
        snapshot = analyzer.analyze(102)

        assert snapshot.high_value_users == next(
            s.user_count for s in snapshot.segments
            if s.segment_name == "high_value"
        )
        assert snapshot.mid_value_users == next(
            s.user_count for s in snapshot.segments
            if s.segment_name == "mid_value"
        )
        assert snapshot.low_value_users == next(
            s.user_count for s in snapshot.segments
            if s.segment_name == "low_value"
        )
        assert snapshot.churn_risk_users == next(
            s.user_count for s in snapshot.segments
            if s.segment_name == "churn_risk"
        )

    def test_total_users_equal_segment_sum(self):
        """总用户数等于各分层用户数之和。"""
        analyzer = UserValueAnalyzer()
        snapshot = analyzer.analyze(102)

        segment_sum = (
            snapshot.high_value_users
            + snapshot.mid_value_users
            + snapshot.low_value_users
            + snapshot.churn_risk_users
        )
        assert snapshot.total_users == segment_sum

    def test_segment_shares_sum_to_one(self):
        """各分层用户占比之和约等于 1。"""
        analyzer = UserValueAnalyzer()
        snapshot = analyzer.analyze(102)

        total_share = sum(s.user_share for s in snapshot.segments)
        assert total_share == pytest.approx(1.0, abs=0.01)

    def test_segment_score_ordering(self):
        """分层平均价值评分符合 high > mid > low > churn_risk。"""
        analyzer = UserValueAnalyzer()
        snapshot = analyzer.analyze(102)

        score_map = {s.segment_name: s.avg_value_score for s in snapshot.segments}
        assert score_map["high_value"] > score_map["mid_value"]
        assert score_map["mid_value"] > score_map["low_value"]
        assert score_map["low_value"] > score_map["churn_risk"]

    def test_avg_value_score_computed(self):
        """全体平均价值评分已计算（加权平均）。"""
        analyzer = UserValueAnalyzer()
        snapshot = analyzer.analyze(102)

        # 手动计算加权平均
        expected = (
            sum(s.avg_value_score * s.user_count for s in snapshot.segments)
            / snapshot.total_users
        )
        assert snapshot.avg_value_score == pytest.approx(expected, abs=0.1)

    def test_value_composition_populated(self):
        """价值构成四维度均已填充。"""
        analyzer = UserValueAnalyzer()
        snapshot = analyzer.analyze(102)

        assert len(snapshot.value_composition) == 4
        dims = {c.dimension for c in snapshot.value_composition}
        assert dims == {"revenue", "engagement", "social", "content"}

    def test_value_composition_shares_sum_to_one(self):
        """价值构成各维度占比之和约等于 1。"""
        analyzer = UserValueAnalyzer()
        snapshot = analyzer.analyze(102)

        total_share = sum(c.share for c in snapshot.value_composition)
        assert total_share == pytest.approx(1.0, abs=0.01)

    def test_value_evolution_populated(self):
        """价值演进指标已填充。"""
        analyzer = UserValueAnalyzer()
        snapshot = analyzer.analyze(102)

        assert snapshot.rising_stars > 0
        assert snapshot.declining_users > 0
        assert snapshot.new_high_value > 0
        assert snapshot.churned_high_value > 0

    def test_pareto_ratio_in_range(self):
        """帕累托比在合理区间 (0, 1]。"""
        analyzer = UserValueAnalyzer()
        snapshot = analyzer.analyze(102)

        assert 0.0 < snapshot.pareto_ratio <= 1.0
        # mock 数据预期约 0.51
        assert snapshot.pareto_ratio == pytest.approx(0.51, abs=0.05)

    def test_concentration_index_in_range(self):
        """集中度指数在 [0, 1] 区间。"""
        analyzer = UserValueAnalyzer()
        snapshot = analyzer.analyze(102)

        assert 0.0 <= snapshot.concentration_index <= 1.0

    def test_value_structure_healthy(self):
        """mock 数据下价值结构为 healthy。"""
        analyzer = UserValueAnalyzer()
        snapshot = analyzer.analyze(102)

        # mock: pareto ≈ 0.51，在 (0.50, 0.85) 区间 → healthy
        assert snapshot.value_structure == "healthy"

    def test_value_structure_valid_value(self):
        """价值结构评价取值合法。"""
        analyzer = UserValueAnalyzer()
        snapshot = analyzer.analyze(102)

        assert snapshot.value_structure in (
            "healthy",
            "top_heavy",
            "bottom_heavy",
            "fragmented",
        )

    def test_insights_content(self):
        """洞察包含价值结构或构成相关建议。"""
        analyzer = UserValueAnalyzer()
        snapshot = analyzer.analyze(102)

        assert len(snapshot.insights) > 0
        # 应包含价值结构或构成关键词
        assert any(
            "价值结构" in i
            or "价值主要由" in i
            or "价值上升" in i
            or "价值下降" in i
            for i in snapshot.insights
        )

    def test_insights_include_evolution(self):
        """洞察包含价值演进建议。"""
        analyzer = UserValueAnalyzer()
        snapshot = analyzer.analyze(102)

        insights_text = " ".join(snapshot.insights)
        assert "价值上升" in insights_text
        assert "价值下降" in insights_text
        assert "新晋高价值" in insights_text
        assert "高价值用户流失" in insights_text

    def test_to_dict_complete(self):
        """to_dict 完整。"""
        analyzer = UserValueAnalyzer()
        snapshot = analyzer.analyze(102)

        d = snapshot.to_dict()
        assert "project_id" in d
        assert "total_users" in d
        assert "avg_value_score" in d
        assert "segments" in d
        assert "high_value_users" in d
        assert "mid_value_users" in d
        assert "low_value_users" in d
        assert "churn_risk_users" in d
        assert "value_composition" in d
        assert "rising_stars" in d
        assert "declining_users" in d
        assert "new_high_value" in d
        assert "churned_high_value" in d
        assert "pareto_ratio" in d
        assert "concentration_index" in d
        assert "value_structure" in d
        assert "insights" in d
        assert len(d["segments"]) == len(snapshot.segments)
        assert len(d["value_composition"]) == len(snapshot.value_composition)

    def test_with_td_reality(self):
        """有 ThinkingDataReality 时的分析（无 client → mock）。"""
        td = ThinkingDataReality()
        analyzer = UserValueAnalyzer(td)
        snapshot = analyzer.analyze(102)

        assert snapshot.total_users > 0
        assert len(snapshot.segments) > 0
        assert snapshot.avg_value_score > 0

    def test_total_analyzed_counter(self):
        """分析计数器递增。"""
        analyzer = UserValueAnalyzer()
        assert analyzer.total_analyzed == 0
        analyzer.analyze(102)
        assert analyzer.total_analyzed == 1
        analyzer.analyze(102)
        assert analyzer.total_analyzed == 2

    def test_lookback_days_affects_period(self):
        """不同回溯天数生成不同周期。"""
        analyzer = UserValueAnalyzer()
        snap_7 = analyzer.analyze(102, lookback_days=7)
        snap_30 = analyzer.analyze(102, lookback_days=30)

        assert snap_7.period_start != snap_30.period_start
        assert snap_7.period_end == snap_30.period_end


# ── 价值评分计算逻辑测试 ───────────────────────────────────


class TestValueScoreComputation:
    """价值评分与分层逻辑测试。"""

    def test_value_score_weighted_sum(self):
        """综合价值评分等于四维度加权求和。"""
        analyzer = UserValueAnalyzer()

        score = analyzer._compute_value_score(
            revenue_score=100.0,
            engagement_score=100.0,
            social_score=100.0,
            content_score=100.0,
        )
        # 全满分 → 100
        assert score == pytest.approx(100.0, abs=0.1)

    def test_value_score_weighted_zero(self):
        """全零分 → 0。"""
        analyzer = UserValueAnalyzer()
        score = analyzer._compute_value_score(0, 0, 0, 0)
        assert score == pytest.approx(0.0, abs=0.1)

    def test_value_score_weighted_revenue_dominant(self):
        """付费权重最高（0.40）。"""
        analyzer = UserValueAnalyzer()
        # 仅付费满分
        score = analyzer._compute_value_score(100, 0, 0, 0)
        assert score == pytest.approx(40.0, abs=0.1)

    def test_segment_name_thresholds(self):
        """分层阈值边界判定。"""
        analyzer = UserValueAnalyzer()

        assert analyzer._segment_name(70.0) == "high_value"
        assert analyzer._segment_name(69.9) == "mid_value"
        assert analyzer._segment_name(40.0) == "mid_value"
        assert analyzer._segment_name(39.9) == "low_value"
        assert analyzer._segment_name(15.0) == "low_value"
        assert analyzer._segment_name(14.9) == "churn_risk"
        assert analyzer._segment_name(0.0) == "churn_risk"

    def test_weights_sum_to_one(self):
        """四维度权重之和等于 1。"""
        analyzer = UserValueAnalyzer()
        total = (
            analyzer.WEIGHT_REVENUE
            + analyzer.WEIGHT_ENGAGEMENT
            + analyzer.WEIGHT_SOCIAL
            + analyzer.WEIGHT_CONTENT
        )
        assert total == pytest.approx(1.0, abs=0.001)


# ── 数据模型测试 ───────────────────────────────────────────


class TestDataModels:
    """数据模型 to_dict 测试。"""

    def test_user_segment_to_dict(self):
        """UserSegment.to_dict 完整。"""
        seg = UserSegment(
            segment_name="high_value",
            user_count=1800,
            user_share=0.18,
            avg_value_score=95.0,
            avg_revenue=200.0,
            avg_active_days=27.0,
            avg_sessions=220.0,
        )
        d = seg.to_dict()
        assert d["segment_name"] == "high_value"
        assert d["user_count"] == 1800
        assert d["user_share"] == 0.18
        assert d["avg_value_score"] == 95.0
        assert d["avg_revenue"] == 200.0
        assert d["avg_active_days"] == 27.0
        assert d["avg_sessions"] == 220.0

    def test_value_contribution_to_dict(self):
        """ValueContribution.to_dict 完整。"""
        vc = ValueContribution(
            dimension="revenue",
            total_contribution=520000.0,
            share=0.5485,
            top_users=1200,
        )
        d = vc.to_dict()
        assert d["dimension"] == "revenue"
        assert d["total_contribution"] == 520000.0
        assert d["share"] == 0.5485
        assert d["top_users"] == 1200

    def test_snapshot_to_dict_roundtrip(self):
        """快照 to_dict 可序列化。"""
        analyzer = UserValueAnalyzer()
        snapshot = analyzer.analyze(102)
        d = snapshot.to_dict()

        # 验证嵌套结构可序列化
        import json
        json_str = json.dumps(d, ensure_ascii=False)
        assert len(json_str) > 0
        restored = json.loads(json_str)
        assert restored["project_id"] == 102
        assert len(restored["segments"]) == 4


# ── 与其他分析域协同测试 ───────────────────────────────────


class TestUserValueCrossDomain:
    """用户价值分析器与其他分析域协同测试。"""

    def test_with_monetization_complementary(self):
        """与商业化分析器互补运行。"""
        from market_ops.creative_vision_runtime.reality.analyzers import (
            MonetizationAnalyzer,
        )

        td = ThinkingDataReality()

        user_value = UserValueAnalyzer(td).analyze(102)
        monetization = MonetizationAnalyzer(td).analyze(102)

        # 商业化关注付费指标
        assert monetization.payer_rate > 0
        assert monetization.arpu > 0
        # 用户价值关注综合价值结构
        assert user_value.total_users > 0
        assert user_value.high_value_users > 0
        assert user_value.pareto_ratio > 0

    def test_share_td_reality(self):
        """与其他分析器共享同一 ThinkingDataReality。"""
        from market_ops.creative_vision_runtime.reality.analyzers import (
            EconomyAnalyzer,
            GameplayAnalyzer,
        )

        td = ThinkingDataReality()

        uv_analyzer = UserValueAnalyzer(td)
        e_analyzer = EconomyAnalyzer(td)
        g_analyzer = GameplayAnalyzer(td)

        uv_snap = uv_analyzer.analyze(102)
        e_snap = e_analyzer.analyze(102)
        g_snap = g_analyzer.analyze(102)

        assert uv_snap.total_users > 0
        assert len(e_snap.resources) > 0
        assert g_snap.total_players > 0

    def test_all_seven_domains_together(self):
        """七大分析域同时运行（含此前 6 个）。"""
        from market_ops.creative_vision_runtime.reality.analyzers import (
            LifecycleAnalyzer,
            FunnelAnalyzer,
            RetentionAnalyzer,
            MonetizationAnalyzer,
            EconomyAnalyzer,
            GameplayAnalyzer,
        )

        td = ThinkingDataReality()

        lifecycle = LifecycleAnalyzer(td).analyze(102)
        funnel = FunnelAnalyzer(td).analyze(102)
        retention = RetentionAnalyzer(td).analyze(102)
        monetization = MonetizationAnalyzer(td).analyze(102)
        economy = EconomyAnalyzer(td).analyze(102)
        gameplay = GameplayAnalyzer(td).analyze(102)
        user_value = UserValueAnalyzer(td).analyze(102)

        # 所有快照都有数据
        assert lifecycle.d7_retention > 0
        assert funnel.overall_conversion > 0
        assert retention.d7_retention > 0
        assert monetization.total_revenue > 0
        assert economy.avg_inflation_rate != 0
        assert gameplay.total_players > 0
        assert user_value.total_users > 0
        assert user_value.high_value_users > 0


# ── P3: SQL 聚合路径测试 ───────────────────────────────────


class TestSegmentsFromSQL:
    """验证 _build_segments_from_sql 正确解析 SQL 聚合结果。"""

    @staticmethod
    def _make_analyzer() -> UserValueAnalyzer:
        return UserValueAnalyzer()

    @staticmethod
    def _make_snapshot() -> UserValueSnapshot:
        return UserValueSnapshot(project_id=102)

    def test_dict_rows_all_four_segments(self):
        """4 个分段全部返回 dict 格式。"""
        az = self._make_analyzer()
        snap = self._make_snapshot()

        rows = [
            {"segment": "high_value", "user_count": 1800, "avg_score": 95.0,
             "avg_revenue": 200.0, "avg_active_days": 27.0, "avg_sessions": 220.0},
            {"segment": "mid_value", "user_count": 2200, "avg_score": 45.0,
             "avg_revenue": 30.0, "avg_active_days": 16.0, "avg_sessions": 110.0},
            {"segment": "low_value", "user_count": 4000, "avg_score": 18.0,
             "avg_revenue": 2.0, "avg_active_days": 8.0, "avg_sessions": 40.0},
            {"segment": "churn_risk", "user_count": 2000, "avg_score": 5.0,
             "avg_revenue": 0.0, "avg_active_days": 2.0, "avg_sessions": 6.0},
        ]

        az._build_segments_from_sql(rows, snap)

        assert snap.total_users == 10000
        assert snap.high_value_users == 1800
        assert snap.mid_value_users == 2200
        assert snap.low_value_users == 4000
        assert snap.churn_risk_users == 2000
        assert len(snap.segments) == 4
        assert snap.segments[0].segment_name == "high_value"
        assert snap.segments[0].avg_value_score == 95.0
        assert snap.segments[3].segment_name == "churn_risk"

    def test_list_rows_all_four_segments(self):
        """4 个分段全部返回 list 格式。"""
        az = self._make_analyzer()
        snap = self._make_snapshot()

        rows = [
            ["high_value", 1800, 95.0, 200.0, 27.0, 220.0],
            ["mid_value", 2200, 45.0, 30.0, 16.0, 110.0],
            ["low_value", 4000, 18.0, 2.0, 8.0, 40.0],
            ["churn_risk", 2000, 5.0, 0.0, 2.0, 6.0],
        ]

        az._build_segments_from_sql(rows, snap)

        assert snap.total_users == 10000
        assert snap.high_value_users == 1800
        assert snap.mid_value_users == 2200
        assert snap.low_value_users == 4000
        assert snap.churn_risk_users == 2000

    def test_partial_segments_missing_mid(self):
        """缺少 mid_value 分段时补空。"""
        az = self._make_analyzer()
        snap = self._make_snapshot()

        rows = [
            {"segment": "high_value", "user_count": 500, "avg_score": 85.0,
             "avg_revenue": 150.0, "avg_active_days": 25.0, "avg_sessions": 200.0},
            # mid_value 缺失
            {"segment": "low_value", "user_count": 3000, "avg_score": 20.0,
             "avg_revenue": 5.0, "avg_active_days": 10.0, "avg_sessions": 50.0},
            {"segment": "churn_risk", "user_count": 1500, "avg_score": 8.0,
             "avg_revenue": 0.0, "avg_active_days": 3.0, "avg_sessions": 8.0},
        ]

        az._build_segments_from_sql(rows, snap)

        assert snap.total_users == 5000
        assert snap.high_value_users == 500
        assert snap.mid_value_users == 0  # 补空
        assert snap.low_value_users == 3000
        assert snap.churn_risk_users == 1500
        assert len(snap.segments) == 4
        # mid_value 应为空 UserSegment
        mid_seg = snap.segments[1]
        assert mid_seg.segment_name == "mid_value"
        assert mid_seg.user_count == 0
        assert mid_seg.user_share == 0.0

    def test_empty_rows(self):
        """空结果返回全零快照。"""
        az = self._make_analyzer()
        snap = self._make_snapshot()

        az._build_segments_from_sql([], snap)

        assert snap.total_users == 0
        assert snap.high_value_users == 0
        assert snap.mid_value_users == 0
        assert snap.low_value_users == 0
        assert snap.churn_risk_users == 0
        assert len(snap.segments) == 4
        # 所有分段 user_count = 0
        for seg in snap.segments:
            assert seg.user_count == 0
            assert seg.user_share == 0.0

    def test_all_users_single_segment(self):
        """所有用户在同一分段（边界情况）。"""
        az = self._make_analyzer()
        snap = self._make_snapshot()

        rows = [
            {"segment": "mid_value", "user_count": 8000, "avg_score": 55.0,
             "avg_revenue": 40.0, "avg_active_days": 18.0, "avg_sessions": 120.0},
        ]

        az._build_segments_from_sql(rows, snap)

        assert snap.total_users == 8000
        assert snap.high_value_users == 0
        assert snap.mid_value_users == 8000
        assert snap.low_value_users == 0
        assert snap.churn_risk_users == 0

    def test_avg_value_score_weighted_correct(self):
        """avg_value_score 按加权平均正确计算。"""
        az = self._make_analyzer()
        snap = self._make_snapshot()

        rows = [
            {"segment": "high_value", "user_count": 1000, "avg_score": 80.0,
             "avg_revenue": 180.0, "avg_active_days": 26.0, "avg_sessions": 200.0},
            {"segment": "mid_value", "user_count": 3000, "avg_score": 50.0,
             "avg_revenue": 35.0, "avg_active_days": 15.0, "avg_sessions": 100.0},
            {"segment": "low_value", "user_count": 4000, "avg_score": 20.0,
             "avg_revenue": 3.0, "avg_active_days": 7.0, "avg_sessions": 35.0},
            {"segment": "churn_risk", "user_count": 2000, "avg_score": 6.0,
             "avg_revenue": 0.0, "avg_active_days": 2.0, "avg_sessions": 5.0},
        ]

        az._build_segments_from_sql(rows, snap)

        # 加权平均 = (80*1000 + 50*3000 + 20*4000 + 6*2000) / 10000
        expected = (80 * 1000 + 50 * 3000 + 20 * 4000 + 6 * 2000) / 10000
        assert snap.avg_value_score == round(expected, 2)
        assert snap.total_users == 10000

    def test_user_share_sums_to_one(self):
        """各分段 user_share 之和为 1.0。"""
        az = self._make_analyzer()
        snap = self._make_snapshot()

        rows = [
            {"segment": "high_value", "user_count": 1200, "avg_score": 90.0,
             "avg_revenue": 220.0, "avg_active_days": 28.0, "avg_sessions": 240.0},
            {"segment": "mid_value", "user_count": 2500, "avg_score": 48.0,
             "avg_revenue": 32.0, "avg_active_days": 17.0, "avg_sessions": 115.0},
            {"segment": "low_value", "user_count": 3800, "avg_score": 19.0,
             "avg_revenue": 2.5, "avg_active_days": 8.0, "avg_sessions": 42.0},
            {"segment": "churn_risk", "user_count": 2500, "avg_score": 4.0,
             "avg_revenue": 0.0, "avg_active_days": 1.0, "avg_sessions": 4.0},
        ]

        az._build_segments_from_sql(rows, snap)

        total_share = sum(seg.user_share for seg in snap.segments)
        assert abs(total_share - 1.0) < 0.001


# ── P3: SQL 加权公式与 Python 一致性验证 ────────────────────


class TestWeightedFormulaConsistency:
    """验证 SQL 层加权公式与 Python _compute_value_score 一致。"""

    def test_formula_matches_python_computation(self):
        """SQL 子查询公式 == Python _compute_value_score。"""
        az = UserValueAnalyzer()

        test_cases = [
            (100, 80, 50, 30),   # 高价值用户
            (60, 70, 40, 20),    # 中价值用户
            (20, 30, 15, 10),    # 低价值用户
            (5, 10, 5, 3),       # 流失风险
            (0, 0, 0, 0),        # 全零
            (100, 100, 100, 100), # 全满
        ]

        for r, e, s, c in test_cases:
            # Python 计算
            py_score = az._compute_value_score(r, e, s, c)

            # SQL 公式（与 SQL 子查询一致）
            sql_score = round(
                az.WEIGHT_REVENUE * r
                + az.WEIGHT_ENGAGEMENT * e
                + az.WEIGHT_SOCIAL * s
                + az.WEIGHT_CONTENT * c,
                2,
            )

            assert py_score == sql_score, (
                f"({r},{e},{s},{c}): Python={py_score} != SQL={sql_score}"
            )

    def test_segment_boundaries_match_sql(self):
        """分层阈值与 SQL CASE WHEN 一致。"""
        az = UserValueAnalyzer()

        boundary_cases = [
            (70.0, "high_value"),   # 刚好高价值阈值
            (69.99, "mid_value"),   # 刚好低于高价值
            (40.0, "mid_value"),    # 刚好中价值阈值
            (39.99, "low_value"),   # 刚好低于中价值
            (15.0, "low_value"),    # 刚好低价值阈值
            (14.99, "churn_risk"),  # 刚好低于低价值
            (0.0, "churn_risk"),    # 零分
        ]

        for score, expected in boundary_cases:
            actual = az._segment_name(score)
            assert actual == expected, (
                f"score={score}: expected {expected}, got {actual}"
            )


# ── P3: Mock Client SQL 聚合路径集成测试 ───────────────────


class TestUserValueSQLIntegration:
    """验证 _fetch_user_segments 在 SQL 聚合路径下端到端正确。"""

    def test_sql_aggregation_via_mock_client(self):
        """通过 Mock client 模拟 SQL 返回聚合结果，验证完整路径。"""
        from unittest.mock import MagicMock

        client = MagicMock()
        client.sql_query.return_value = {
            "data": [
                {"segment": "high_value", "user_count": 1200, "avg_score": 92.0,
                 "avg_revenue": 210.0, "avg_active_days": 28.0, "avg_sessions": 230.0},
                {"segment": "mid_value", "user_count": 2300, "avg_score": 46.0,
                 "avg_revenue": 28.0, "avg_active_days": 15.0, "avg_sessions": 105.0},
                {"segment": "low_value", "user_count": 4200, "avg_score": 17.0,
                 "avg_revenue": 1.5, "avg_active_days": 7.0, "avg_sessions": 38.0},
                {"segment": "churn_risk", "user_count": 2300, "avg_score": 4.5,
                 "avg_revenue": 0.0, "avg_active_days": 1.5, "avg_sessions": 5.0},
            ]
        }

        td = ThinkingDataReality(client)
        az = UserValueAnalyzer(td)
        snap = az.analyze(102, 30)

        assert snap.total_users == 10000
        assert snap.high_value_users == 1200
        assert snap.mid_value_users == 2300
        assert snap.low_value_users == 4200
        assert snap.churn_risk_users == 2300
        assert len(snap.segments) == 4
        assert snap.segments[0].avg_value_score == 92.0

    def test_sql_aggregation_preserves_concentration(self):
        """SQL 聚合路径下价值集中度计算正确。"""
        from unittest.mock import MagicMock

        client = MagicMock()

        # 第一段 SQL：segments 聚合
        # 第二段 SQL：value_composition
        # 第三段 SQL：value_evolution
        client.sql_query.side_effect = [
            {
                "data": [
                    {"segment": "high_value", "user_count": 2000, "avg_score": 88.0,
                     "avg_revenue": 250.0, "avg_active_days": 29.0, "avg_sessions": 250.0},
                    {"segment": "mid_value", "user_count": 2000, "avg_score": 48.0,
                     "avg_revenue": 35.0, "avg_active_days": 16.0, "avg_sessions": 110.0},
                    {"segment": "low_value", "user_count": 4000, "avg_score": 20.0,
                     "avg_revenue": 3.0, "avg_active_days": 8.0, "avg_sessions": 42.0},
                    {"segment": "churn_risk", "user_count": 2000, "avg_score": 6.0,
                     "avg_revenue": 0.0, "avg_active_days": 2.0, "avg_sessions": 6.0},
                ]
            },
            {
                "data": [
                    {"dim": "revenue", "total": 520000.0, "top": 1200},
                    {"dim": "engagement", "total": 285000.0, "top": 3800},
                    {"dim": "social", "total": 75000.0, "top": 800},
                    {"dim": "content", "total": 68000.0, "top": 600},
                ]
            },
            {
                "data": [
                    {"rising": 450, "declining": 280, "new_high": 85, "churned_high": 42},
                ]
            },
        ]

        td = ThinkingDataReality(client)
        az = UserValueAnalyzer(td)
        snap = az.analyze(102, 30)

        # 集中度指标应正常计算
        assert snap.pareto_ratio > 0
        assert snap.concentration_index > 0
        assert snap.value_structure in ("healthy", "top_heavy", "bottom_heavy", "fragmented")
        # 洞察应生成
        assert len(snap.insights) > 0

    def test_sql_failure_falls_back_to_mock(self):
        """SQL 失败时降级到 Mock 数据。"""
        from unittest.mock import MagicMock

        client = MagicMock()
        client.sql_query.side_effect = Exception("SQL timeout")

        td = ThinkingDataReality(client)
        az = UserValueAnalyzer(td)
        snap = az.analyze(102, 30)

        # Mock 降级：应有数据
        assert snap.total_users == 10000
        assert snap.high_value_users == 1800
        assert len(snap.segments) == 4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
