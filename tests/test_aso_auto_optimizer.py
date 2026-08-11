"""测试 ASO 自动优化执行器."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from src.market_ops.workspace.aso_auto_optimizer import (
    ASOAutoOptimizer,
    ASOMetrics,
    OptimizationRecord,
    StoreListingPackage,
    get_aso_auto_optimizer,
    reset_aso_auto_optimizer,
)


class TestStoreListingPackage:
    """StoreListingPackage 数据模型测试."""

    def test_to_dict(self):
        pkg = StoreListingPackage(
            game_id="test_game",
            package_name="com.test",
            genre="trivia",
            title="Test Game: Trivia",
            short_description="Best trivia game!",
            full_description="Long description...",
            keywords=["trivia", "quiz"],
        )
        d = pkg.to_dict()
        assert d["game_id"] == "test_game"
        assert d["title"] == "Test Game: Trivia"
        assert len(d["keywords"]) == 2

    def test_to_deploy_json(self):
        pkg = StoreListingPackage(
            game_id="test",
            package_name="com.test",
            genre="trivia",
            title="Test",
            short_description="Short",
            full_description="Full",
            localizations={
                "pt-BR": {
                    "title": "Test PT",
                    "short_description": "Short PT",
                    "full_description": "Full PT",
                },
            },
        )
        deploy = pkg.to_deploy_json()
        assert deploy["package_name"] == "com.test"
        assert "en-US" in deploy["listings"]
        assert "pt-BR" in deploy["listings"]
        assert deploy["listings"]["pt-BR"]["title"] == "Test PT"


class TestASOAutoOptimizer:
    """ASO 自动优化执行器测试."""

    @pytest.fixture
    def optimizer(self, tmp_path):
        """每个测试用独立临时目录."""
        return ASOAutoOptimizer(data_dir=str(tmp_path / "aso_deploy"))

    def test_generate_deploy_package_basic(self, optimizer):
        """基础部署包生成."""
        pkg = optimizer.generate_deploy_package(
            game_id="Bible Quiz",
            package_name="com.born2play.biblequiz",
            genre="trivia",
        )
        assert pkg.game_id == "Bible Quiz"
        assert pkg.package_name == "com.born2play.biblequiz"
        assert pkg.genre == "trivia"
        assert len(pkg.title) <= 30
        assert len(pkg.short_description) <= 80
        assert len(pkg.full_description) <= 4000
        assert len(pkg.keywords) > 0

    def test_generate_with_reviews(self, optimizer):
        """带评论的部署包."""
        reviews = [
            {"text": "Great bible trivia game! Love the quiz questions.", "rating": 5},
            {"text": "Best bible quiz! Fun trivia for the family.", "rating": 5},
            {"text": "Good bible trivia but needs more quiz questions.", "rating": 4},
        ]
        pkg = optimizer.generate_deploy_package(
            game_id="Bible Quiz",
            package_name="com.born2play.biblequiz",
            genre="trivia",
            reviews=reviews,
        )
        # 评论验证的关键词应该在列表中
        validated = [k for k in pkg.keywords if "bible" in k.lower() or "trivia" in k.lower()]
        assert len(validated) > 0

    def test_generate_all_genres(self, optimizer):
        """所有品类都能生成部署包."""
        for genre in ["merge", "puzzle", "trivia", "simulation", "casual"]:
            pkg = optimizer.generate_deploy_package(
                game_id=f"test_{genre}",
                package_name=f"com.test.{genre}",
                genre=genre,
            )
            assert pkg.title != ""
            assert pkg.short_description != ""
            assert pkg.full_description != ""

    def test_title_within_limit(self, optimizer):
        """标题不超过 30 字符."""
        pkg = optimizer.generate_deploy_package(
            game_id="Bible Quiz",
            package_name="com.born2play.biblequiz",
            genre="trivia",
        )
        assert len(pkg.title) <= 30

    def test_short_description_within_limit(self, optimizer):
        """短描述不超过 80 字符."""
        pkg = optimizer.generate_deploy_package(
            game_id="Bible Quiz",
            package_name="com.born2play.biblequiz",
            genre="trivia",
        )
        assert len(pkg.short_description) <= 80

    def test_localizations_generated(self, optimizer):
        """本地化版本生成."""
        pkg = optimizer.generate_deploy_package(
            game_id="Bible Quiz",
            package_name="com.born2play.biblequiz",
            genre="trivia",
            localize=True,
        )
        assert len(pkg.localizations) == 6
        assert "pt-BR" in pkg.localizations
        assert "es" in pkg.localizations
        assert "de" in pkg.localizations
        assert "fr" in pkg.localizations
        assert "ja" in pkg.localizations
        assert "ko" in pkg.localizations

    def test_no_localization(self, optimizer):
        """关闭本地化."""
        pkg = optimizer.generate_deploy_package(
            game_id="test",
            package_name="com.test",
            genre="trivia",
            localize=False,
        )
        assert len(pkg.localizations) == 0

    def test_save_package(self, optimizer, tmp_path):
        """保存部署包到文件."""
        pkg = optimizer.generate_deploy_package(
            game_id="Bible Quiz",
            package_name="com.born2play.biblequiz",
            genre="trivia",
        )
        path = optimizer.save_package(pkg)
        assert Path(path).exists()

        # 检查 JSON 文件
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert data["game_id"] == "Bible Quiz"

        # 检查 deploy JSON
        deploy_path = Path(path).parent / "play_console_deploy.json"
        assert deploy_path.exists()

        # 检查 README
        md_path = Path(path).parent / "README.md"
        assert md_path.exists()

    def test_save_package_with_special_chars(self, optimizer):
        """游戏名含特殊字符时正确保存."""
        pkg = optimizer.generate_deploy_package(
            game_id="Drama Hospital: ASMR Care",
            package_name="com.test.drama",
            genre="simulation",
        )
        path = optimizer.save_package(pkg)
        assert Path(path).exists()

    def test_record_optimization(self, optimizer):
        """记录优化."""
        record = optimizer.record_optimization(
            game_id="Bible Quiz",
            optimization_type="listing_update",
            description="Test optimization",
        )
        assert record.game_id == "Bible Quiz"
        assert record.status == "generated"

        history = optimizer.get_optimization_history("Bible Quiz")
        assert len(history) == 1
        assert history[0]["description"] == "Test optimization"

    def test_update_metrics(self, optimizer):
        """更新指标."""
        optimizer.record_optimization(
            game_id="Bible Quiz",
            optimization_type="listing_update",
            description="Test",
        )
        assert optimizer.mark_published("Bible Quiz") is True
        metrics = ASOMetrics(
            game_id="Bible Quiz",
            organic_installs=1000,
            organic_revenue=500.0,
            store_conversion_rate=0.15,
        )
        optimizer.update_metrics("Bible Quiz", metrics)

        history = optimizer.get_optimization_history("Bible Quiz")
        assert history[0]["after_metrics"] is not None
        assert history[0]["after_metrics"]["organic_installs"] == 1000
        assert history[0]["status"] == "measuring"

    def test_history_survives_process_restart(self, tmp_path):
        """云端定时任务每次都是新进程，历史必须从磁盘恢复."""
        first = ASOAutoOptimizer(data_dir=str(tmp_path))
        first.record_optimization(
            game_id="com.born2play.biblequiz",
            optimization_type="listing_update",
            description="自动循环优化 v1",
        )

        restarted = ASOAutoOptimizer(data_dir=str(tmp_path))
        history = restarted.get_optimization_history("com.born2play.biblequiz")
        assert len(history) == 1
        assert history[0]["status"] == "generated"

        pkg = restarted.generate_deploy_package(
            game_id="com.born2play.biblequiz",
            package_name="com.born2play.biblequiz",
            genre="bible",
        )
        assert pkg.version == 2

    def test_legacy_deployed_without_metrics_is_migrated(self, tmp_path):
        """旧数据没有真实发布凭证，不能继续冒充 deployed."""
        history_path = tmp_path / "optimization_history.json"
        history_path.write_text(json.dumps({
            "com.born2play.biblequiz": [{
                "game_id": "com.born2play.biblequiz",
                "optimization_id": "legacy",
                "timestamp": "2026-08-11T00:00:00+00:00",
                "optimization_type": "listing_update",
                "description": "自动循环优化 v1",
                "before_metrics": None,
                "after_metrics": None,
                "status": "deployed",
            }],
        }), encoding="utf-8")

        optimizer = ASOAutoOptimizer(data_dir=str(tmp_path))
        history = optimizer.get_optimization_history("com.born2play.biblequiz")
        assert history[0]["status"] == "generated"

    def test_auto_optimize_batch(self, optimizer):
        """批量自动优化."""
        games = [
            {"game_id": "Bible Quiz", "package_name": "com.born2play.biblequiz", "genre": "trivia"},
            {"game_id": "merge witches", "package_name": "com.born2play.mergewitches", "genre": "merge"},
            {"game_id": "Word Tile Master", "package_name": "", "genre": "puzzle"},
        ]
        packages = optimizer.auto_optimize(games)
        assert len(packages) == 3

        status = optimizer.get_status_summary()
        assert status["total_games_optimized"] == 3
        assert status["total_optimizations"] == 3

    def test_auto_optimize_with_reviews(self, optimizer):
        """批量优化带评论."""
        games = [
            {"game_id": "Bible Quiz", "package_name": "com.born2play.biblequiz", "genre": "trivia"},
        ]
        reviews_map = {
            "Bible Quiz": [
                {"text": "Great bible trivia quiz game!", "rating": 5},
                {"text": "Love this bible quiz trivia!", "rating": 5},
            ],
        }
        packages = optimizer.auto_optimize(games, reviews_map=reviews_map)
        assert len(packages) == 1

    def test_auto_optimize_skips_empty_game_id(self, optimizer):
        """空 game_id 被跳过."""
        games = [
            {"game_id": "", "package_name": "com.test", "genre": "trivia"},
            {"game_id": "Bible Quiz", "package_name": "com.born2play.biblequiz", "genre": "trivia"},
        ]
        packages = optimizer.auto_optimize(games)
        assert len(packages) == 1

    def test_icon_ab_variants(self, optimizer):
        """Icon A/B 测试变体."""
        pkg = optimizer.generate_deploy_package(
            game_id="test",
            package_name="com.test",
            genre="trivia",
        )
        assert len(pkg.icon_ab_variants) == 3
        variants = [v["variant"] for v in pkg.icon_ab_variants]
        assert "A (当前)" in variants

    def test_expected_impact(self, optimizer):
        """预期效果."""
        pkg = optimizer.generate_deploy_package(
            game_id="test",
            package_name="com.test",
            genre="trivia",
        )
        assert "search_visibility" in pkg.expected_impact
        assert "organic_installs_30d" in pkg.expected_impact
        assert "organic_revenue_30d" in pkg.expected_impact

    def test_optimization_notes(self, optimizer):
        """优化理由."""
        pkg = optimizer.generate_deploy_package(
            game_id="test",
            package_name="com.test",
            genre="trivia",
        )
        assert len(pkg.optimization_notes) > 0

    def test_screenshot_order(self, optimizer):
        """截图顺序."""
        pkg = optimizer.generate_deploy_package(
            game_id="test",
            package_name="com.test",
            genre="trivia",
        )
        assert len(pkg.screenshot_order) == 8

    def test_singleton(self):
        """单例正常工作."""
        reset_aso_auto_optimizer()
        o1 = get_aso_auto_optimizer()
        o2 = get_aso_auto_optimizer()
        assert o1 is o2
        reset_aso_auto_optimizer()


class TestASOMetrics:
    """ASOMetrics 数据模型测试."""

    def test_to_dict(self):
        m = ASOMetrics(
            game_id="test",
            store_impressions=10000,
            store_conversion_rate=0.15,
            organic_installs=1500,
            organic_revenue=750.0,
        )
        d = m.to_dict()
        assert d["game_id"] == "test"
        assert d["store_impressions"] == 10000
        assert d["organic_revenue"] == 750.0
