"""测试 Google Play ASO 引擎 + 自然量增长引擎."""

from __future__ import annotations

import pytest

from src.market_ops.workspace.organic_growth_engine import (
    ContentStrategy,
    CrossPromotionOpportunity,
    GooglePlayASOEngine,
    KeywordSuggestion,
    ListingOptimization,
    OrganicGrowthReport,
    get_google_play_aso_engine,
    reset_google_play_aso_engine,
)


class TestGooglePlayASOEngine:
    """Google Play ASO 引擎测试."""

    def _make_engine(self):
        return GooglePlayASOEngine()

    def test_analyze_basic(self):
        """基础分析 — 无评论无竞品."""
        engine = self._make_engine()
        report = engine.analyze(
            game_id="test_game",
            package_name="com.test.game",
            genre="merge",
        )
        assert report.game_id == "test_game"
        assert report.genre == "merge"
        assert report.platform == "google_play"
        assert len(report.keyword_suggestions) > 0
        assert report.listing_optimization is not None
        assert len(report.action_plan) > 0

    def test_analyze_all_genres(self):
        """所有品类都有关键词建议."""
        engine = self._make_engine()
        for genre in ["merge", "puzzle", "trivia", "simulation", "casual"]:
            report = engine.analyze(game_id="test", genre=genre)
            assert len(report.keyword_suggestions) > 0
            assert any(k.priority == "HIGH" for k in report.keyword_suggestions)

    def test_analyze_unknown_genre_defaults_casual(self):
        """未知品类回退到 casual."""
        engine = self._make_engine()
        report = engine.analyze(game_id="test", genre="nonexistent")
        assert report.genre == "nonexistent"
        assert len(report.keyword_suggestions) > 0

    def test_review_mining(self):
        """评论驱动的关键词挖掘."""
        engine = self._make_engine()
        reviews = [
            {"text": "Love this merge game! Best merge puzzle ever.", "rating": 5},
            {"text": "Fun merge puzzle but too many ads. Want offline mode.", "rating": 3},
            {"text": "Amazing merge game! The merge magic is great.", "rating": 5},
            {"text": "Good merge puzzle game. Love merging items.", "rating": 4},
            {"text": "Best merge game! Merge adventure is fun.", "rating": 5},
        ]
        report = engine.analyze(
            game_id="test",
            genre="merge",
            reviews=reviews,
        )
        assert report.review_insights["total_reviews_analyzed"] == 5
        assert len(report.review_insights["top_positive_words"]) > 0
        # 评论驱动的关键词应该出现在建议中
        review_kw = [
            k for k in report.keyword_suggestions
            if k.source in ("review_mining", "review_validated")
        ]
        assert len(review_kw) > 0

    def test_competitor_analysis(self):
        """竞品分析生成关键词."""
        engine = self._make_engine()
        report = engine.analyze(
            game_id="test",
            genre="merge",
            competitor_packages=["com.competitor1", "com.competitor2"],
        )
        comp_kw = [k for k in report.keyword_suggestions if k.source == "competitor"]
        assert len(comp_kw) > 0

    def test_cross_promotion(self):
        """交叉推广策略."""
        engine = self._make_engine()
        portfolio = [
            {"game_id": "game_a", "package_name": "com.a", "genre": "merge"},
            {"game_id": "game_b", "package_name": "com.b", "genre": "puzzle"},
            {"game_id": "game_c", "package_name": "com.c", "genre": "simulation"},
        ]
        report = engine.analyze(
            game_id="test_game",
            genre="merge",
            portfolio_games=portfolio,
        )
        # 同品类的应该排前面
        same_genre = [cp for cp in report.cross_promotions if "同品类" in cp.shared_audience]
        assert len(same_genre) == 1  # game_a
        # 不包括自己
        assert not any(cp.target_game_id == "test_game" for cp in report.cross_promotions)

    def test_content_strategies(self):
        """内容营销策略生成."""
        engine = self._make_engine()
        report = engine.analyze(game_id="test", genre="merge")
        assert len(report.content_strategies) >= 4
        platforms = {cs.platform for cs in report.content_strategies}
        assert "youtube" in platforms
        assert "tiktok" in platforms

    def test_seo_suggestions(self):
        """SEO 建议生成."""
        engine = self._make_engine()
        report = engine.analyze(
            game_id="test",
            genre="merge",
            package_name="com.test.game",
        )
        assert len(report.seo_suggestions) >= 5
        assert any("landing page" in s.lower() or "着陆页" in s for s in report.seo_suggestions)

    def test_action_plan_priority_order(self):
        """行动计划按优先级排序."""
        engine = self._make_engine()
        report = engine.analyze(
            game_id="test",
            genre="merge",
            package_name="com.test",
        )
        assert len(report.action_plan) >= 5
        priorities = [a["priority"] for a in report.action_plan]
        # HIGH 应该在 MEDIUM 之前
        high_idx = [i for i, p in enumerate(priorities) if p == "HIGH"]
        medium_idx = [i for i, p in enumerate(priorities) if p == "MEDIUM"]
        if high_idx and medium_idx:
            assert max(high_idx) < min(medium_idx)

    def test_listing_optimization(self):
        """Store Listing 优化建议."""
        engine = self._make_engine()
        report = engine.analyze(game_id="merge witches", genre="merge")
        lo = report.listing_optimization
        assert lo is not None
        assert len(lo.title_suggestions) > 0
        assert len(lo.short_description_suggestions) > 0
        assert len(lo.screenshot_order_suggestions) > 0
        assert len(lo.localization_suggestions) > 0
        assert lo.icon_optimization != ""

    def test_to_markdown(self):
        """Markdown 报告生成."""
        engine = self._make_engine()
        report = engine.analyze(
            game_id="test",
            genre="merge",
            package_name="com.test",
        )
        md = report.to_markdown()
        assert "Google Play 自然量增长报告" in md
        assert "优先级行动计划" in md
        assert "ASO 关键词建议" in md
        assert "Store Listing 优化建议" in md

    def test_to_dict(self):
        """to_dict 序列化."""
        engine = self._make_engine()
        report = engine.analyze(game_id="test", genre="merge")
        d = report.to_dict()
        assert d["game_id"] == "test"
        assert d["genre"] == "merge"
        assert d["platform"] == "google_play"
        assert "keyword_suggestions" in d
        assert "action_plan" in d
        assert d["total_keywords"] > 0
        assert d["total_actions"] > 0

    def test_singleton(self):
        """单例正常工作."""
        reset_google_play_aso_engine()
        e1 = get_google_play_aso_engine()
        e2 = get_google_play_aso_engine()
        assert e1 is e2
        reset_google_play_aso_engine()


class TestKeywordSuggestionDataclass:
    """KeywordSuggestion 数据模型测试."""

    def test_to_dict(self):
        ks = KeywordSuggestion(
            keyword="merge game",
            source="genre_kb",
            search_volume=50000,
            difficulty=0.4,
            priority="HIGH",
            reason="core keyword",
            action="put in title",
        )
        d = ks.to_dict()
        assert d["keyword"] == "merge game"
        assert d["priority"] == "HIGH"
        assert d["difficulty"] == 0.4
