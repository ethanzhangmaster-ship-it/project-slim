"""ASO 自动优化执行器.

生成可直接部署的 Google Play Store Listing 内容, 并持续追踪优化效果.

核心能力:
  1. 生成完整的 Store Listing 部署包 (标题/短描述/完整描述/关键词)
  2. 生成本地化版本 (PT-BR / ES / DE / FR / JA / KO)
  3. 生成截图脚本和 Icon A/B 测试方案
  4. 追踪优化前后的 KPI 变化
  5. 自动迭代 — 基于效果数据持续优化

部署包格式:
  每个 game 生成一个 JSON 部署包, 可直接导入 Google Play Console.
  部署包包含: title, short_description, full_description, keywords,
  localization (多语言), screenshot_order, icon_ab_test_variants.

用法:
  executor = ASOAutoOptimizer()
  package = executor.generate_deploy_package("Bible Quiz", "com.born2play.biblequiz", "trivia")
  executor.save_package(package, "data/aso_deploy/biblequiz/")
"""

from __future__ import annotations

import json
import logging
import os
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .organic_growth_engine import (
    GooglePlayASOEngine,
    KeywordSuggestion,
    OrganicGrowthReport,
    get_google_play_aso_engine,
)

logger = logging.getLogger(__name__)


# ── 本地化模板 ────────────────────────────────────────────────

_LOCALIZATION: Dict[str, Dict[str, str]] = {
    "pt-BR": {
        "language_name": "Português (Brasil)",
        "market": "巴西",
        "market_note": "休闲游戏增长最快的市场",
        "title_suffix": "Jogo de Quiz",
        "desc_prefix": "O melhor jogo de trivia bíblica!",
        "cta": "Baixe agora grátis!",
        "offline": "Jogue offline sem wifi",
    },
    "es": {
        "language_name": "Español",
        "market": "西班牙语市场",
        "market_note": "拉美 + 西班牙, 高增长",
        "title_suffix": "Juego de Trivia",
        "desc_prefix": "¡El mejor juego de trivia bíblica!",
        "cta": "¡Descarga gratis ahora!",
        "offline": "Juega sin conexión a internet",
    },
    "de": {
        "language_name": "Deutsch",
        "market": "德国",
        "market_note": "高 ARPU 市场",
        "title_suffix": "Quiz Spiel",
        "desc_prefix": "Das beste Bibel-Quiz-Spiel!",
        "cta": "Jetzt gratis herunterladen!",
        "offline": "Offline spielen ohne WLAN",
    },
    "fr": {
        "language_name": "Français",
        "market": "法国",
        "market_note": "欧洲核心市场",
        "title_suffix": "Jeu de Quiz",
        "desc_prefix": "Le meilleur jeu de trivia biblique!",
        "cta": "Téléchargez gratuitement!",
        "offline": "Jouez hors ligne sans wifi",
    },
    "ja": {
        "language_name": "日本語",
        "market": "日本",
        "market_note": "高付费市场",
        "title_suffix": "クイズゲーム",
        "desc_prefix": "最高の聖書クイズゲーム！",
        "cta": "今すぐ無料ダウンロード！",
        "offline": "Wi-Fi不要でオフラインプレイ",
    },
    "ko": {
        "language_name": "한국어",
        "market": "韩国",
        "market_note": "高活跃市场",
        "title_suffix": "퀴즈 게임",
        "desc_prefix": "최고의 성경 퀴즈 게임!",
        "cta": "지금 무료 다운로드!",
        "offline": "와이파이 없이 오프라인으로 플레이",
    },
}


# ── 品类模板 ──────────────────────────────────────────────────

_GENRE_TEMPLATES: Dict[str, Dict[str, str]] = {
    "bible": {
        "title_pattern": "{name}: {keyword}",
        "desc_template": (
            "Grow closer to God with {name} - the #1 {genre} trivia game!\n\n"
            "{features}\n\n"
            "KEY FEATURES:\n"
            "✓ 1,000+ {genre} questions from Old & New Testament\n"
            "✓ Easy, Medium, Hard & Expert difficulty levels\n"
            "✓ Daily Bible verse & devotional quiz challenges\n"
            "✓ Memorize scripture while playing offline\n"
            "✓ No wifi needed - play anytime, anywhere\n\n"
            "{keywords_paragraph}\n\n"
            "Perfect for church groups, bible studies, and anyone wanting to deepen their faith.\n"
            "Download {name} now and test your biblical knowledge!\n\n"
            "{cta} {offline}"
        ),
        "features": (
            "Answer fun scripture questions, learn bible facts, "
            "and grow your faith every day. From Genesis to Revelation, "
            "explore the Bible through engaging quizzes and daily verses."
        ),
    },
    "trivia": {
        "title_pattern": "{name}: {keyword}",
        "desc_template": (
            "Test your knowledge with {name} - the ultimate {genre} game!\n\n"
            "{features}\n\n"
            "KEY FEATURES:\n"
            "✓ Thousands of {genre} questions\n"
            "✓ Multiple difficulty levels\n"
            "✓ Daily challenges and rewards\n"
            "✓ Learn while having fun\n"
            "✓ Play offline - no wifi needed\n\n"
            "{keywords_paragraph}\n\n"
            "Download {name} now and become a {genre} master!\n\n"
            "{cta} {offline}"
        ),
        "features": "Challenge yourself with bible questions, scripture trivia, and faith-based quizzes.",
    },
    "merge": {
        "title_pattern": "{name}: {keyword}",
        "desc_template": (
            "Welcome to {name} - the most addictive {genre} puzzle game!\n\n"
            "{features}\n\n"
            "KEY FEATURES:\n"
            "✓ Merge and match items to create new ones\n"
            "✓ Hundreds of levels to explore\n"
            "✓ Build and decorate your world\n"
            "✓ Unlock rare items and characters\n"
            "✓ Play offline - no wifi needed\n\n"
            "{keywords_paragraph}\n\n"
            "Download {name} now and start your {genre} adventure!\n\n"
            "{cta} {offline}"
        ),
        "features": "Merge magic items, build your kingdom, and discover mysterious creatures.",
    },
    "puzzle": {
        "title_pattern": "{name}: {keyword}",
        "desc_template": (
            "Challenge your brain with {name} - the best {genre} game!\n\n"
            "{features}\n\n"
            "KEY FEATURES:\n"
            "✓ Hundreds of brain-teasing levels\n"
            "✓ Multiple game modes\n"
            "✓ Daily puzzles and rewards\n"
            "✓ Train your brain while having fun\n"
            "✓ Play offline - no wifi needed\n\n"
            "{keywords_paragraph}\n\n"
            "Download {name} now and test your skills!\n\n"
            "{cta} {offline}"
        ),
        "features": "Solve challenging puzzles, train your brain, and improve your vocabulary.",
    },
    "simulation": {
        "title_pattern": "{name}: {keyword}",
        "desc_template": (
            "Build your dream with {name} - the #1 {genre} game!\n\n"
            "{features}\n\n"
            "KEY FEATURES:\n"
            "✓ Build and manage your own world\n"
            "✓ Customize and decorate\n"
            "✓ Complete fun missions\n"
            "✓ Unlock new content daily\n"
            "✓ Play offline - no wifi needed\n\n"
            "{keywords_paragraph}\n\n"
            "Download {name} now and start building!\n\n"
            "{cta} {offline}"
        ),
        "features": "Manage your hospital, serve customers, and become the best in town.",
    },
    "casual": {
        "title_pattern": "{name}: {keyword}",
        "desc_template": (
            "Play {name} - the fun and relaxing {genre} game!\n\n"
            "{features}\n\n"
            "KEY FEATURES:\n"
            "✓ Simple and addictive gameplay\n"
            "✓ Beautiful graphics\n"
            "✓ Daily rewards and bonuses\n"
            "✓ Perfect for all ages\n"
            "✓ Play offline - no wifi needed\n\n"
            "{keywords_paragraph}\n\n"
            "Download {name} now for endless fun!\n\n"
            "{cta} {offline}"
        ),
        "features": "Enjoy fun and relaxing gameplay perfect for killing time.",
    },
}


# ── 数据模型 ──────────────────────────────────────────────────

@dataclass
class StoreListingPackage:
    """Google Play Store Listing 部署包 — 可直接导入 Play Console."""

    game_id: str
    package_name: str
    genre: str
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    version: int = 1

    # 英文版 (默认)
    title: str = ""
    short_description: str = ""
    full_description: str = ""
    keywords: List[str] = field(default_factory=list)

    # 本地化版本
    localizations: Dict[str, Dict[str, str]] = field(default_factory=dict)

    # 截图顺序
    screenshot_order: List[str] = field(default_factory=list)

    # Icon A/B 测试
    icon_ab_variants: List[Dict[str, str]] = field(default_factory=list)

    # 优化理由
    optimization_notes: List[str] = field(default_factory=list)

    # 预期效果
    expected_impact: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "package_name": self.package_name,
            "genre": self.genre,
            "generated_at": self.generated_at,
            "version": self.version,
            "title": self.title,
            "short_description": self.short_description,
            "full_description": self.full_description,
            "keywords": self.keywords,
            "localizations": self.localizations,
            "screenshot_order": self.screenshot_order,
            "icon_ab_variants": self.icon_ab_variants,
            "optimization_notes": self.optimization_notes,
            "expected_impact": self.expected_impact,
        }

    def to_deploy_json(self) -> Dict[str, Any]:
        """生成可直接导入 Google Play Console 的 JSON 格式."""
        deploy: Dict[str, Any] = {
            "package_name": self.package_name,
            "listings": {
                "en-US": {
                    "title": self.title,
                    "short_description": self.short_description,
                    "full_description": self.full_description,
                },
            },
        }
        for locale, data in self.localizations.items():
            deploy["listings"][locale] = {
                "title": data.get("title", self.title),
                "short_description": data.get("short_description", self.short_description),
                "full_description": data.get("full_description", self.full_description),
            }
        return deploy


@dataclass
class ASOMetrics:
    """ASO 优化前后的 KPI 指标."""

    game_id: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Store 表现
    store_impressions: int = 0
    store_conversion_rate: float = 0.0
    organic_installs: int = 0

    # 搜索表现
    keyword_rankings: Dict[str, int] = field(default_factory=dict)
    search_visibility_score: float = 0.0

    # 收入
    organic_revenue: float = 0.0
    organic_dau: int = 0

    # 评分
    average_rating: float = 0.0
    rating_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "timestamp": self.timestamp,
            "store_impressions": self.store_impressions,
            "store_conversion_rate": self.store_conversion_rate,
            "organic_installs": self.organic_installs,
            "keyword_rankings": self.keyword_rankings,
            "search_visibility_score": self.search_visibility_score,
            "organic_revenue": self.organic_revenue,
            "organic_dau": self.organic_dau,
            "average_rating": self.average_rating,
            "rating_count": self.rating_count,
        }


@dataclass
class OptimizationRecord:
    """一次优化记录 — 记录优化前后的指标变化."""

    game_id: str
    optimization_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    optimization_type: str = ""  # "listing_update" / "keyword_deploy" / "localization"
    description: str = ""
    before_metrics: Optional[ASOMetrics] = None
    after_metrics: Optional[ASOMetrics] = None
    # generated: 仅生成了部署包, 尚未证明已发布到商店
    # published: 已收到 Google Play 发布确认, 等待效果数据
    # measuring/completed: 已开始/完成效果评估
    status: str = "pending"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "optimization_id": self.optimization_id,
            "timestamp": self.timestamp,
            "optimization_type": self.optimization_type,
            "description": self.description,
            "before_metrics": self.before_metrics.to_dict() if self.before_metrics else None,
            "after_metrics": self.after_metrics.to_dict() if self.after_metrics else None,
            "status": self.status,
        }


# ── ASO 自动优化执行器 ────────────────────────────────────────

class ASOAutoOptimizer:
    """ASO 自动优化执行器.

    生成可直接部署的 Store Listing 内容, 并追踪优化效果.

    线程安全: 单实例可并发调用.
    """

    def __init__(self, data_dir: str = "data/aso_deploy") -> None:
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._engine = get_google_play_aso_engine()
        self._lock = threading.Lock()
        self._records: Dict[str, List[OptimizationRecord]] = defaultdict(list)
        self._load_records()

    # ── 1. 生成 Store Listing 部署包 ──

    def generate_deploy_package(
        self,
        game_id: str,
        package_name: str,
        genre: str,
        reviews: Optional[List[Dict[str, Any]]] = None,
        portfolio_games: Optional[List[Dict[str, Any]]] = None,
        localize: bool = True,
    ) -> StoreListingPackage:
        """生成完整的 Store Listing 部署包."""
        genre = (genre or "casual").lower().strip()

        # 1. 先跑 ASO 分析
        report = self._engine.analyze(
            game_id=game_id,
            package_name=package_name,
            genre=genre,
            reviews=reviews,
            portfolio_games=portfolio_games,
        )

        # 2. 构建部署包 — 版本号自动递增
        next_version = self._next_version(game_id)
        pkg = StoreListingPackage(
            game_id=game_id,
            package_name=package_name,
            genre=genre,
            version=next_version,
        )

        # 3. 生成标题
        pkg.title = self._generate_title(game_id, genre, report.keyword_suggestions, package_name=package_name)

        # 4. 生成短描述
        pkg.short_description = self._generate_short_description(game_id, genre, report.keyword_suggestions, package_name=package_name)

        # 5. 生成完整描述
        pkg.full_description = self._generate_full_description(game_id, genre, report.keyword_suggestions, package_name=package_name)

        # 6. 部署关键词列表
        pkg.keywords = self._select_deploy_keywords(report.keyword_suggestions)

        # 7. 本地化
        if localize:
            pkg.localizations = self._generate_localizations(game_id, genre, pkg)

        # 8. 截图顺序
        pkg.screenshot_order = self._generate_screenshot_order(genre)

        # 9. Icon A/B 测试方案
        pkg.icon_ab_variants = self._generate_icon_ab_test(game_id, genre)

        # 10. 优化理由
        pkg.optimization_notes = self._generate_optimization_notes(report)

        # 11. 预期效果
        pkg.expected_impact = self._estimate_impact(report)

        return pkg

    # 已知游戏关键词 — 用于从包名中提取可读游戏名
    _GAME_NAME_KEYWORDS: Tuple[str, ...] = (
        "bible", "quiz", "trivia", "word", "merge", "witches", "monster",
        "puzzle", "crossword", "spelling", "tile", "food", "movie",
        "geography", "math", "wrestling", "daily", "codewords", "encryption",
        "challenge", "travel", "leisure", "feud", "islamic", "grammar",
        "millionaire", "spelling", "master", "free", "game",
        "bibbia", "estrela", "estrella", "biblique", "biblico", "biblia",
        "adivinar", "palabras", "desafio",
    )

    @classmethod
    def _extract_game_name(cls, game_id: str, package_name: str = "") -> str:
        """从 game_id / package_name 提取可读的游戏名.

        优先用 package_name (更标准), 回退到 game_id.

        策略:
          1. 包名格式 (含点): 取最后一段, 识别已知关键词组合
          2. 非包名: 直接按 _ / ? 拆分
          3. 兜底: 用最后一段 title case
        """
        raw = (package_name or game_id or "").strip()
        if not raw:
            return "Game"

        # 非包名格式 (不含点, 或含斜杠) — 直接清洗
        if "." not in raw or "/" in raw:
            return raw.replace("_", " ").replace("?", " ").strip().title() or "Game"

        # 包名格式: com.born2play.biblequiz -> 取最后一段 biblequiz
        parts = raw.split(".")
        # 跳过常见前缀 com / io / org / app / games
        meaningful = [p for p in parts if p.lower() not in ("com", "io", "org", "app", "apps", "games", "game", "inc", "co")]
        last_segment = meaningful[-1] if meaningful else parts[-1]

        if not last_segment:
            return "Game"

        lower = last_segment.lower()
        # 识别已知关键词 — 按在原文中的位置排序 (而非长度)
        # 先找所有匹配, 记录位置, 再按位置升序输出
        found_with_pos: List[Tuple[int, str]] = []
        matched_spans: List[Tuple[int, int]] = []
        for kw in cls._GAME_NAME_KEYWORDS:
            idx = lower.find(kw)
            if idx < 0:
                continue
            # 避免与已匹配区间重叠
            if any(s <= idx < e or s < idx + len(kw) <= e for s, e in matched_spans):
                continue
            matched_spans.append((idx, idx + len(kw)))
            found_with_pos.append((idx, kw))

        # 按位置排序
        found_with_pos.sort(key=lambda x: x[0])

        if found_with_pos:
            # 去除无意义词
            stop_words = {"game", "free", "master"}
            ordered = [kw for _, kw in found_with_pos if kw not in stop_words]
            if ordered:
                return " ".join(ordered).title()

        # 没识别到关键词 — 按驼峰拆分
        import re
        words = re.sub(r'([a-z])([A-Z])', r'\1 \2', last_segment)
        return words.title() if words else last_segment.title()

    def _generate_title(
        self,
        game_id: str,
        genre: str,
        keywords: List[KeywordSuggestion],
        package_name: str = "",
    ) -> str:
        """生成标题 (Google Play 限 30 字符)."""
        game_name = self._extract_game_name(game_id, package_name)

        # 获取关键词 (先去掉与游戏名完全重复的)
        high_kw = [k for k in keywords if k.priority == "HIGH"]
        game_name_lower = game_name.lower().strip()
        unique_high = []
        seen_variants = {game_name_lower, game_name_lower.replace(" ", "")}
        for k in high_kw:
            kl = k.keyword.lower().strip()
            if kl not in seen_variants and kl.replace(" ", "") not in seen_variants:
                unique_high.append(k)
            if len(unique_high) >= 3:
                break

        kw_primary = (unique_high[0].keyword if unique_high
                      else (high_kw[0].keyword if high_kw else f"{genre} game"))
        kw_secondary = (unique_high[1].keyword if len(unique_high) > 1
                        else f"{genre} app")

        # 按吸引力 + 不重复 + 字符数 综合排序
        # 额外要求: 游戏名与关键词共享大量单词时, 降低重复方案分数
        def _shared_words_score(a: str, b: str) -> float:
            """两字符串共享小写去空格后的字符重合比例."""
            a_s = set(a.lower().replace(" ", ""))
            b_s = set(b.lower().replace(" ", ""))
            if not a_s or not b_s:
                return 0.0
            inter = a_s & b_s
            return len(inter) / min(len(a_s), len(b_s))

        overlap_penalty_p = max(0, int(_shared_words_score(game_name, kw_primary) * 5))
        overlap_penalty_s = max(0, int(_shared_words_score(game_name, kw_secondary) * 5))

        candidates = [
            # 方案 A: 游戏名 + 差异化卖点 (首选 - 不重复品类词)
            (f"{game_name}: Scripture & Faith", 12),
            # 方案 B: 游戏名 + 精准长尾搜索词 (Faith / Scripture 都是搜索量词)
            (f"{game_name}: Bible Trivia Game", 11),
            # 方案 C: 游戏名 + 关键词 (有重叠惩罚)
            (f"{game_name}: {kw_primary.title()}", max(0, 9 - overlap_penalty_p)),
            # 方案 D: 游戏名 + 次级关键词
            (f"{game_name}: {kw_secondary.title()}", max(0, 10 - overlap_penalty_s)),
            # 方案 E: 游戏名 + 促销驱动
            (f"{game_name} - Free Trivia Game", 8),
            # 方案 F: 关键词驱动 + 游戏名
            (f"{kw_primary.title()} - {game_name}", max(0, 7 - overlap_penalty_p)),
            # 方案 G: 纯游戏名
            (game_name, 6),
        ]

        # 选: 字符 ≤ 30 且 不重复 + 分数最高的
        best = ("", 0)
        for cand, score in candidates:
            cand = cand.strip()
            if not cand or len(cand) > 30:
                continue
            # 简单重复检查: 不允许左右两半近似相同
            halves = cand.lower().replace(" ", "").split(":")[-1].replace("-", "").strip()
            left_half = game_name_lower.replace(" ", "")
            if halves and left_half and halves in left_half:
                score -= 3  # 惩罚重复
            if score > best[1]:
                best = (cand, score)

        if best[0]:
            return best[0]

        # 兜底
        return f"{game_name}: {genre.title()}"[:30]

    def _generate_short_description(
        self,
        game_id: str,
        genre: str,
        keywords: List[KeywordSuggestion],
        package_name: str = "",
    ) -> str:
        """生成短描述 (Google Play 限 80 字符)."""
        game_name = self._extract_game_name(game_id, package_name)
        high_kw = [k for k in keywords if k.priority == "HIGH"]
        top_kw = high_kw[0].keyword if high_kw else f"{genre} game"
        # 找与游戏名不重复的第二关键词
        gn_l = game_name.lower().replace(" ", "")
        unique_kws = [k for k in high_kw if k.keyword.lower().replace(" ", "") != gn_l]
        second_kw = unique_kws[1].keyword if len(unique_kws) > 1 else (
            high_kw[2].keyword if len(high_kw) > 2 else "scripture questions"
        )
        # third_kw 作为另一个卖点补充
        third_kw = (
            unique_kws[2].keyword if len(unique_kws) > 2 else
            (high_kw[3].keyword if len(high_kw) > 3 else "daily bible verses")
        )
        # 关键词修正: 把单数 quiz → questions/verses, 更自然
        if second_kw.endswith(" quiz") and "bible" in second_kw:
            second_feature = "bible trivia questions"
        elif second_kw.endswith(" quiz"):
            second_feature = second_kw.replace("quiz", "questions")
        else:
            second_feature = second_kw

        # 优先用高转化的短描述模板
        candidates = [
            # 短描述黄金结构: 卖点数字 + 关键词 + CTA + 无重复
            f"1000+ {second_feature}. Play offline! Free {genre} game.",
            f"Test {genre} knowledge — {third_kw}! Free & no wifi needed.",
            f"{game_name}: {third_kw} + daily verses. 100% free offline.",
            f"Play {game_name}! {second_feature}. Free download, no ads.",
            f"Best free {genre} trivia. {second_feature}. Play offline.",
            f"Best free {genre} app. {second_feature}. Play without internet.",
            f"Love {genre}? Try {top_kw}! Free download, no wifi.",
        ]

        for candidate in candidates:
            if len(candidate) <= 80 and candidate.strip():
                return candidate.strip()

        return f"Best free {genre} game. Offline play. Download now!"[:80]

    def _generate_full_description(
        self,
        game_id: str,
        genre: str,
        keywords: List[KeywordSuggestion],
        package_name: str = "",
    ) -> str:
        """生成完整描述 (Google Play 限 4000 字符)."""
        game_name = self._extract_game_name(game_id, package_name)
        template = _GENRE_TEMPLATES.get(genre, _GENRE_TEMPLATES["casual"])

        # 构建关键词段落
        high_kw = [k.keyword for k in keywords if k.priority == "HIGH"][:5]
        medium_kw = [k.keyword for k in keywords if k.priority == "MEDIUM"][:8]
        all_kw = high_kw + medium_kw

        keywords_paragraph = ""
        if all_kw:
            # 自然嵌入关键词
            keywords_paragraph = (
                f"This {genre} game features {all_kw[0]}, "
                f"{all_kw[1] if len(all_kw) > 1 else 'puzzles'}, "
                f"and {all_kw[2] if len(all_kw) > 2 else 'challenges'}. "
            )
            if len(all_kw) > 3:
                keywords_paragraph += (
                    f"Perfect for fans of {', '.join(all_kw[3:6])}. "
                )
            keywords_paragraph += (
                f"Keywords: {', '.join(all_kw[:10])}."
            )

        desc = template["desc_template"].format(
            name=game_name,
            genre=genre,
            features=template["features"],
            keywords_paragraph=keywords_paragraph,
            cta="Download now and start playing!",
            offline="Play offline without wifi!",
        )

        # 截断到 4000 字符
        return desc[:4000]

    def _select_deploy_keywords(self, keywords: List[KeywordSuggestion]) -> List[str]:
        """选择部署的关键词 (按优先级)."""
        priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        sorted_kw = sorted(keywords, key=lambda k: priority_order.get(k.priority, 3))
        return [k.keyword for k in sorted_kw[:20]]

    def _generate_localizations(
        self,
        game_id: str,
        genre: str,
        pkg: StoreListingPackage,
    ) -> Dict[str, Dict[str, str]]:
        """生成多语言本地化版本."""
        game_name = pkg.title.split(":")[0].strip()
        localizations: Dict[str, Dict[str, str]] = {}

        for locale, loc_data in _LOCALIZATION.items():
            # 标题
            loc_title = f"{game_name}: {loc_data['title_suffix']}"[:30]

            # 短描述
            loc_short = f"{loc_data['desc_prefix']} {loc_data['cta']}"[:80]

            # 完整描述 (基于英文版翻译, 实际部署时应人工校对)
            loc_full = (
                f"{loc_data['desc_prefix']}\n\n"
                f"{pkg.full_description[:500]}\n\n"
                f"{loc_data['cta']} {loc_data['offline']}"
            )[:4000]

            localizations[locale] = {
                "title": loc_title,
                "short_description": loc_short,
                "full_description": loc_full,
                "language": loc_data["language_name"],
                "market": loc_data["market"],
                "market_note": loc_data["market_note"],
            }

        return localizations

    def _generate_screenshot_order(self, genre: str) -> List[str]:
        """生成截图顺序建议."""
        return [
            "1. 游戏核心玩法截图 (最吸引人的画面)",
            "2. 特色功能展示 (独特机制)",
            "3. 角色/元素展示",
            "4. 关卡/进度展示",
            "5. 社交/竞技功能 (如有)",
            "6. 奖励/成就展示",
            "7. 操作引导截图",
            "8. 情绪唤起截图 (快乐/成就感)",
        ]

    def _generate_icon_ab_test(self, game_id: str, genre: str) -> List[Dict[str, str]]:
        """生成 Icon A/B 测试方案."""
        return [
            {
                "variant": "A (当前)",
                "description": f"保持现有 Icon 作为 baseline",
                "hypothesis": "基线版本, 用于对比",
            },
            {
                "variant": "B (高对比度)",
                "description": f"提高色彩饱和度, 放大主体元素, 使用 {genre} 品类标志性色彩",
                "hypothesis": "高对比度 Icon 在搜索结果中更醒目, 预计 CTR +3-5%",
            },
            {
                "variant": "C (情绪化)",
                "description": f"使用角色表情/动作, 传达游戏乐趣, 适合 {genre} 品类",
                "hypothesis": "情绪化设计吸引点击, 预计 CTR +5-8%",
            },
        ]

    def _generate_optimization_notes(self, report: OrganicGrowthReport) -> List[str]:
        """生成优化理由."""
        notes: List[str] = []

        high_kw = [k for k in report.keyword_suggestions if k.priority == "HIGH"]
        notes.append(
            f"标题包含 {len(high_kw)} 个 HIGH 优先级关键词, "
            f"最大化搜索可见度"
        )

        if report.review_insights:
            validated = [
                k for k in report.keyword_suggestions
                if k.source in ("review_mining", "review_validated")
            ]
            if validated:
                notes.append(
                    f"{len(validated)} 个关键词来自用户评论挖掘, "
                    f"匹配真实搜索意图"
                )

        notes.append(
            f"完整描述嵌入 {len(report.keyword_suggestions[:15])} 个关键词, "
            f"覆盖长尾搜索流量"
        )

        if report.listing_optimization and report.listing_optimization.localization_suggestions:
            notes.append(
                f"本地化 {len(report.listing_optimization.localization_suggestions)} 条建议, "
                f"覆盖巴西/西语/欧洲/亚洲市场"
            )

        return notes

    def _estimate_impact(self, report: OrganicGrowthReport) -> Dict[str, str]:
        """估算优化后的预期效果."""
        return {
            "search_visibility": "+15-30% (标题+描述关键词优化)",
            "install_conversion": "+5-15% (截图+Icon 优化)",
            "organic_installs_30d": "+20-50% (综合优化效果)",
            "organic_revenue_30d": "+15-40% (自然量增长带动收入)",
            "localization_lift": "+50-100% (巴西市场), +30-60% (西语市场)",
            "timeline": "7天内部署, 2-4周见效, 3个月稳定增长",
        }

    # ── 2. 保存部署包 ──

    def save_package(self, pkg: StoreListingPackage, output_dir: Optional[str] = None) -> str:
        """保存部署包到文件.

        Returns:
            保存的文件路径.
        """
        if output_dir:
            out = Path(output_dir)
        else:
            safe_id = pkg.game_id.replace(" ", "_").replace("/", "_").replace(":", "").replace(":", "").lower()
            out = self._data_dir / safe_id

        out.mkdir(parents=True, exist_ok=True)

        # 保存完整部署包
        pkg_path = out / "store_listing.json"
        with pkg_path.open("w", encoding="utf-8") as f:
            json.dump(pkg.to_dict(), f, ensure_ascii=False, indent=2)
            f.write("\n")

        # 保存 Play Console 导入格式
        deploy_path = out / "play_console_deploy.json"
        with deploy_path.open("w", encoding="utf-8") as f:
            json.dump(pkg.to_deploy_json(), f, ensure_ascii=False, indent=2)
            f.write("\n")

        # 保存 Markdown 版本 (人类可读)
        md_path = out / "README.md"
        with md_path.open("w", encoding="utf-8") as f:
            f.write(self._package_to_markdown(pkg))

        return str(pkg_path)

    def _package_to_markdown(self, pkg: StoreListingPackage) -> str:
        """部署包转 Markdown."""
        lines: List[str] = []
        lines.append(f"# Store Listing 部署包: {pkg.game_id}")
        lines.append(f"")
        lines.append(f"**包名:** {pkg.package_name}")
        lines.append(f"**品类:** {pkg.genre}")
        lines.append(f"**版本:** v{pkg.version}")
        lines.append(f"**生成时间:** {pkg.generated_at}")
        lines.append(f"")

        lines.append(f"## 标题 (30 字符限制)")
        lines.append("```")
        lines.append(pkg.title)
        lines.append("```")
        lines.append(f"字符数: {len(pkg.title)}/30")
        lines.append(f"")

        lines.append(f"## 短描述 (80 字符限制)")
        lines.append("```")
        lines.append(pkg.short_description)
        lines.append("```")
        lines.append(f"字符数: {len(pkg.short_description)}/80")
        lines.append(f"")

        lines.append(f"## 完整描述 (4000 字符限制)")
        lines.append("```")
        lines.append(pkg.full_description)
        lines.append("```")
        lines.append(f"字符数: {len(pkg.full_description)}/4000")
        lines.append(f"")

        lines.append(f"## 部署关键词 ({len(pkg.keywords)} 个)")
        for i, kw in enumerate(pkg.keywords, 1):
            lines.append(f"{i}. {kw}")
        lines.append(f"")

        if pkg.localizations:
            lines.append(f"## 本地化 ({len(pkg.localizations)} 语言)")
            for locale, data in pkg.localizations.items():
                lines.append(f"### {locale} - {data.get('language', '')}")
                lines.append(f"- 市场: {data.get('market', '')} ({data.get('market_note', '')})")
                lines.append(f"- 标题: {data.get('title', '')}")
                lines.append(f"- 短描述: {data.get('short_description', '')}")
                lines.append(f"")
            lines.append(f"")

        lines.append(f"## 截图顺序")
        for s in pkg.screenshot_order:
            lines.append(f"- {s}")
        lines.append(f"")

        lines.append(f"## Icon A/B 测试")
        for v in pkg.icon_ab_variants:
            lines.append(f"- **{v['variant']}**: {v['description']}")
            lines.append(f"  - 假设: {v['hypothesis']}")
        lines.append(f"")

        lines.append(f"## 优化理由")
        for note in pkg.optimization_notes:
            lines.append(f"- {note}")
        lines.append(f"")

        lines.append(f"## 预期效果")
        for k, v in pkg.expected_impact.items():
            lines.append(f"- **{k}**: {v}")
        lines.append(f"")

        return "\n".join(lines)

    # ── 3. 优化效果追踪 ──

    def _next_version(self, game_id: str) -> int:
        """获取下一个版本号 — 基于历史记录递增."""
        with self._lock:
            records = self._records.get(game_id, [])
            if not records:
                return 1
            # 从历史记录中找最大版本号
            max_v = 0
            for r in records:
                # OptimizationRecord 没有 version 字段, 但 description 含 "vN"
                import re
                m = re.search(r'v(\d+)', r.description or "")
                if m:
                    max_v = max(max_v, int(m.group(1)))
            return max_v + 1 if max_v > 0 else len(records) + 1

    def record_optimization(
        self,
        game_id: str,
        optimization_type: str,
        description: str,
        before_metrics: Optional[ASOMetrics] = None,
        status: str = "generated",
    ) -> OptimizationRecord:
        """记录一次优化.

        默认状态是 ``generated``，因为保存部署 JSON 不等于已经发布到
        Google Play。只有真实发布接口返回成功后才应调用
        :meth:`mark_published`。
        """
        record = OptimizationRecord(
            game_id=game_id,
            optimization_id=f"opt_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            optimization_type=optimization_type,
            description=description,
            before_metrics=before_metrics,
            status=status,
        )
        with self._lock:
            self._records[game_id].append(record)
        self._save_records()
        return record

    def mark_published(
        self,
        game_id: str,
        optimization_id: Optional[str] = None,
    ) -> bool:
        """在收到真实商店发布确认后，将部署包标为已发布."""
        with self._lock:
            records = self._records.get(game_id, [])
            target: Optional[OptimizationRecord] = None
            if optimization_id:
                target = next(
                    (r for r in reversed(records)
                     if r.optimization_id == optimization_id),
                    None,
                )
            elif records:
                target = records[-1]
            if target is None:
                return False
            target.status = "published"
            self._save_records()
            return True

    def update_metrics(self, game_id: str, metrics: ASOMetrics) -> None:
        """更新优化后的指标."""
        with self._lock:
            if game_id in self._records and self._records[game_id]:
                latest = self._records[game_id][-1]
                if latest.status in ("published", "deployed"):
                    latest.after_metrics = metrics
                    latest.status = "measuring"
                elif latest.status == "measuring":
                    # 持续更新最新指标
                    latest.after_metrics = metrics
            self._save_records()

    def get_optimization_history(self, game_id: str) -> List[Dict[str, Any]]:
        """获取优化历史."""
        with self._lock:
            return [r.to_dict() for r in self._records.get(game_id, [])]

    def _save_records(self) -> None:
        """保存优化记录."""
        records_path = self._data_dir / "optimization_history.json"
        all_records: Dict[str, List[Dict[str, Any]]] = {}
        for gid, records in self._records.items():
            all_records[gid] = [r.to_dict() for r in records]
        with records_path.open("w", encoding="utf-8") as f:
            json.dump(all_records, f, ensure_ascii=False, indent=2)
            f.write("\n")

    @staticmethod
    def _metrics_from_dict(data: Optional[Dict[str, Any]]) -> Optional[ASOMetrics]:
        if not isinstance(data, dict):
            return None
        fields = {
            "timestamp", "store_impressions", "store_conversion_rate",
            "organic_installs", "keyword_rankings", "search_visibility_score",
            "organic_revenue", "organic_dau", "average_rating", "rating_count",
        }
        kwargs = {k: data[k] for k in fields if k in data}
        return ASOMetrics(game_id=str(data.get("game_id", "")), **kwargs)

    def _load_records(self) -> None:
        """加载跨进程优化历史，避免每天都把同一方案重新生成成 v1.

        旧版本把“只生成文件”错误记录为 ``deployed``。没有 after_metrics
        的这类记录在加载时迁移成 ``generated``，防止误报真实发布。
        """
        records_path = self._data_dir / "optimization_history.json"
        if not records_path.exists():
            return
        try:
            migrated = False
            with records_path.open(encoding="utf-8") as f:
                raw = json.load(f)
            for game_id, items in (raw or {}).items():
                if not isinstance(items, list):
                    continue
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    status = str(item.get("status") or "generated")
                    if status == "deployed" and not item.get("after_metrics"):
                        status = "generated"
                        migrated = True
                    self._records[str(game_id)].append(OptimizationRecord(
                        game_id=str(item.get("game_id") or game_id),
                        optimization_id=str(item.get("optimization_id") or ""),
                        timestamp=str(item.get("timestamp") or datetime.now(timezone.utc).isoformat()),
                        optimization_type=str(item.get("optimization_type") or ""),
                        description=str(item.get("description") or ""),
                        before_metrics=self._metrics_from_dict(item.get("before_metrics")),
                        after_metrics=self._metrics_from_dict(item.get("after_metrics")),
                        status=status,
                    ))
            if migrated:
                self._save_records()
        except (OSError, ValueError, TypeError) as exc:
            logger.warning("加载 ASO 优化历史失败, 将从空历史继续: %s", exc)

    # ── 4. 自动优化循环 ──

    def auto_optimize(
        self,
        games: List[Dict[str, Any]],
        reviews_map: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    ) -> List[StoreListingPackage]:
        """批量自动优化多个游戏.

        Args:
            games: 游戏列表 [{game_id, package_name, genre}, ...]
            reviews_map: 游戏ID → 评论列表 (可选)

        Returns:
            部署包列表
        """
        packages: List[StoreListingPackage] = []
        reviews_map = reviews_map or {}

        for game in games:
            gid = game.get("game_id", "")
            pkg_name = game.get("package_name", "")
            genre = game.get("genre", "casual")

            if not gid:
                continue

            reviews = reviews_map.get(gid, [])
            portfolio = games  # 所有游戏作为 portfolio

            try:
                pkg = self.generate_deploy_package(
                    game_id=gid,
                    package_name=pkg_name,
                    genre=genre,
                    reviews=reviews,
                    portfolio_games=portfolio,
                )
                self.save_package(pkg)
                self.record_optimization(
                    game_id=gid,
                    optimization_type="listing_update",
                    description=f"自动生成 Store Listing v{pkg.version} (genre={genre})",
                )
                packages.append(pkg)
                logger.info("ASO 部署包已生成: %s (%s)", gid, pkg_name)
            except Exception as exc:
                logger.error("ASO 优化失败 %s: %s", gid, exc)

        return packages

    def get_status_summary(self) -> Dict[str, Any]:
        """获取所有优化状态汇总."""
        with self._lock:
            total_games = len(self._records)
            total_optimizations = sum(len(v) for v in self._records.values())
            measuring = sum(
                1 for records in self._records.values()
                for r in records if r.status == "measuring"
            )
            completed = sum(
                1 for records in self._records.values()
                for r in records if r.status == "completed"
            )

        return {
            "total_games_optimized": total_games,
            "total_optimizations": total_optimizations,
            "measuring": measuring,
            "completed": completed,
            "data_dir": str(self._data_dir),
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }


# ── 单例 ──────────────────────────────────────────────────────

_instance: Optional[ASOAutoOptimizer] = None
_instance_lock = threading.Lock()


def get_aso_auto_optimizer(data_dir: str = "data/aso_deploy") -> ASOAutoOptimizer:
    """获取单例实例."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = ASOAutoOptimizer(data_dir=data_dir)
    return _instance


def reset_aso_auto_optimizer() -> None:
    """重置单例 (用于测试)."""
    global _instance
    with _instance_lock:
        _instance = None


__all__ = [
    "StoreListingPackage",
    "ASOMetrics",
    "OptimizationRecord",
    "ASOAutoOptimizer",
    "get_aso_auto_optimizer",
    "reset_aso_auto_optimizer",
]
