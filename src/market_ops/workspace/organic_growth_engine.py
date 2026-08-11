"""Google Play ASO 引擎 + 自然量增长引擎.

不花钱的 Google Play ASO 关键词研究和自然量获取策略.

核心能力:
  1. 品类关键词知识库 — 基于游戏品类预置高转化关键词
  2. 评论驱动的关键词挖掘 — 从用户评论中提取真实搜索词
  3. 竞品 listing 分析 — 抓取竞品标题/描述提取关键词
  4. Store Listing 优化建议 — 标题/描述/截图/本地化
  5. 交叉推广策略 — 利用 portfolio 中多个游戏互推
  6. 内容营销策略 — YouTube/TikTok/社区运营建议
  7. SEO 策略 — 基于 ASO 关键词的 Web SEO 建议

设计原则:
  - 完全免费: 不依赖外部 ASO 工具 (Sensor Tower / data.ai)
  - 数据驱动: 基于评论、品类知识、竞品分析
  - 可执行: 每条建议都有具体操作步骤
  - 可持续: 定期运行持续产出优化建议

用法:
  engine = GooglePlayASOEngine()
  report = engine.analyze(game_id="merge witches", package_name="com.born2play.mergewitches", genre="merge")
  print(report.to_markdown())
"""

from __future__ import annotations

import logging
import re
import threading
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ── 品类关键词知识库 ──────────────────────────────────────────

_GENRE_KEYWORDS: Dict[str, Dict[str, List[str]]] = {
    "merge": {
        "core": [
            "merge game", "merge puzzle", "merge magic", "merge dragons",
            "merge town", "merge city", "merge farm", "merge island",
            "merge mansion", "merge monsters", "merge witches", "merge kingdom",
        ],
        "long_tail": [
            "free merge game", "merge game offline", "merge puzzle free",
            "best merge game 2024", "merge game no wifi", "merge game for kids",
            "merge and match game", "merge building game", "merge adventure",
            "merge quest game", "merge craft game", "merge evolution",
        ],
        "related": [
            "puzzle game", "matching game", "casual game", "idle game",
            "simulation game", "building game", "crafting game",
        ],
    },
    "puzzle": {
        "core": [
            "puzzle game", "word puzzle", "crossword puzzle", "brain puzzle",
            "logic puzzle", "trivia game", "quiz game", "word game",
            "brain teaser", "mind game",
        ],
        "long_tail": [
            "free puzzle game", "puzzle game offline", "word puzzle free",
            "best puzzle game 2024", "puzzle game no wifi", "puzzle game for adults",
            "brain training game", "word connect game", "trivia quiz free",
            "daily crossword puzzle", "bible quiz game", "bible trivia game",
        ],
        "related": [
            "educational game", "word search", "anagram game", "spelling game",
            "knowledge game", "learning game", "fun trivia",
        ],
    },
    "bible": {
        "core": [
            "bible quiz", "bible trivia", "biblical quiz", "scripture quiz",
            "bible game", "faith quiz", "bible questions", "bible study",
            "bible knowledge", "bible verse", "christian trivia",
        ],
        "long_tail": [
            "free bible quiz", "bible quiz offline", "bible trivia free",
            "bible quiz game for free", "bible game no wifi", "bible quiz daily",
            "bible trivia game offline", "christian quiz", "bible word game",
            "bible guess game", "bible quiz and answers", "bible trivia with answers",
            "old testament trivia", "new testament trivia", "who wrote genesis",
            "12 disciples quiz", "who killed goliath", "psalms 23 verse",
            "genesis to revelation", "bible quiz for kids", "bible trivia for adults",
            "bible multiple choice", "bible verse memory", "bible prophecy quiz",
            "psalms quiz", "proverbs trivia", "gospel questions",
        ],
        "related": [
            "scripture game", "bible learning", "bible memory", "bible puzzle",
            "bible study app", "christian game", "faith based game",
            "bible facts", "old testament quiz", "new testament quiz",
            "jesus miracles quiz", "bible character quiz", "moses exodus trivia",
            "david and goliath", "bible story game", "christian education app",
        ],
    },
    "trivia": {
        "core": [
            "trivia game", "quiz game", "trivia crack", "trivia questions",
            "bible quiz", "bible trivia", "movie quiz", "food quiz",
            "geography quiz", "history quiz", "science quiz",
        ],
        "long_tail": [
            "free trivia game", "trivia game offline", "bible quiz free",
            "best trivia game 2024", "trivia game no wifi", "trivia game for adults",
            "daily trivia game", "multiplayer trivia", "trivia puzzle",
            "bible trivia free", "movie trivia game", "food trivia game",
        ],
        "related": [
            "puzzle game", "word game", "brain game", "knowledge test",
            "educational game", "learning quiz", "fun quiz",
        ],
    },
    "simulation": {
        "core": [
            "simulation game", "hospital game", "doctor game", "salon game",
            "makeover game", "cooking game", "chef game", "fashion game",
            "hospital simulation", "asmr game",
        ],
        "long_tail": [
            "free simulation game", "hospital game offline", "doctor game free",
            "best simulation game 2024", "hospital tycoon game", "salon makeover game",
            "cooking simulator game", "fashion design game", "asmr doctor game",
            "casual simulation", "time management game",
        ],
        "related": [
            "casual game", "management game", "tycoon game", "role playing",
            "farming game", "building game",
        ],
    },
    "casual": {
        "core": [
            "casual game", "fun game", "addictive game", "relaxing game",
            "time killer game", "hyper casual", "mini game",
        ],
        "long_tail": [
            "free casual game", "casual game offline", "best casual game 2024",
            "casual game no wifi", "relaxing puzzle game", "fun mini games",
            "casual games for free", "easy casual game", "casual time killer",
        ],
        "related": [
            "puzzle game", "arcade game", "strategy game", "card game",
        ],
    },
}


# ── 停用词 (评论分析时过滤) ───────────────────────────────────

_STOP_WORDS_EN: Set[str] = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "can", "shall", "to", "of", "in",
    "for", "on", "with", "at", "by", "from", "as", "into", "through",
    "during", "before", "after", "above", "below", "up", "down", "out",
    "off", "over", "under", "again", "further", "then", "once", "here",
    "there", "when", "where", "why", "how", "all", "each", "every", "both",
    "few", "more", "most", "other", "some", "such", "no", "nor", "not",
    "only", "own", "same", "so", "than", "too", "very", "just", "but",
    "if", "or", "because", "until", "while", "about", "against", "between",
    "this", "that", "these", "those", "i", "me", "my", "we", "us", "our",
    "you", "your", "he", "him", "his", "she", "her", "it", "its", "they",
    "them", "their", "what", "which", "who", "whom", "and",
    "playing", "played", "get", "got", "one", "really", "much", "like",
    "good", "great", "love", "fun", "nice", "best", "amazing", "awesome",
}

_STOP_WORDS_EXTRA: Set[str] = {
    "it's", "i'm", "don't", "can't", "won't", "isn't", "aren't", "wasn't",
    "weren't", "haven't", "hasn't", "hadn't", "doesn't", "didn't", "couldn't",
    "shouldn't", "wouldn't", "mustn't", "let's", "that's", "there's", "here's",
    "what's", "who's", "how's", "app", "update", "version", "phone", "mobile",
}


# ── 数据模型 ──────────────────────────────────────────────────

@dataclass
class KeywordSuggestion:
    """关键词建议."""

    keyword: str
    source: str = ""           # "genre_kb" / "review_mining" / "competitor" / "long_tail"
    search_volume: int = 0     # 估算搜索量
    difficulty: float = 0.3    # 0-1, 估算难度
    priority: str = "MEDIUM"   # HIGH / MEDIUM / LOW
    reason: str = ""           # 为什么推荐这个词
    action: str = ""           # 具体操作建议

    def to_dict(self) -> Dict[str, Any]:
        return {
            "keyword": self.keyword,
            "source": self.source,
            "search_volume": self.search_volume,
            "difficulty": round(self.difficulty, 2),
            "priority": self.priority,
            "reason": self.reason,
            "action": self.action,
        }


@dataclass
class ListingOptimization:
    """Store Listing 优化建议."""

    title_suggestions: List[str] = field(default_factory=list)
    short_description_suggestions: List[str] = field(default_factory=list)
    full_description_keywords: List[str] = field(default_factory=list)
    screenshot_order_suggestions: List[str] = field(default_factory=list)
    localization_suggestions: List[str] = field(default_factory=list)
    icon_optimization: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title_suggestions": self.title_suggestions,
            "short_description_suggestions": self.short_description_suggestions,
            "full_description_keywords": self.full_description_keywords,
            "screenshot_order_suggestions": self.screenshot_order_suggestions,
            "localization_suggestions": self.localization_suggestions,
            "icon_optimization": self.icon_optimization,
        }


@dataclass
class CrossPromotionOpportunity:
    """交叉推广机会."""

    target_game_id: str
    target_package_name: str = ""
    shared_audience: str = ""    # 为什么用户群重叠
    promotion_channel: str = ""  # "in_app" / "push" / "store_listing"
    expected_lift: str = ""      # 预期效果

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_game_id": self.target_game_id,
            "target_package_name": self.target_package_name,
            "shared_audience": self.shared_audience,
            "promotion_channel": self.promotion_channel,
            "expected_lift": self.expected_lift,
        }


@dataclass
class ContentStrategy:
    """内容营销策略建议."""

    platform: str = ""           # "youtube" / "tiktok" / "reddit" / "instagram"
    content_type: str = ""       # "gameplay" / "tutorial" / "review" / "meme"
    topic: str = ""              # 具体主题
    keywords: List[str] = field(default_factory=list)
    frequency: str = ""          # 发布频率
    expected_reach: str = ""     # 预期触达

    def to_dict(self) -> Dict[str, Any]:
        return {
            "platform": self.platform,
            "content_type": self.content_type,
            "topic": self.topic,
            "keywords": self.keywords,
            "frequency": self.frequency,
            "expected_reach": self.expected_reach,
        }


@dataclass
class OrganicGrowthReport:
    """自然量增长报告 — 完整的 ASO + 自然量策略."""

    game_id: str
    package_name: str = ""
    genre: str = ""
    platform: str = "google_play"
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # ASO 关键词
    keyword_suggestions: List[KeywordSuggestion] = field(default_factory=list)

    # Store Listing 优化
    listing_optimization: Optional[ListingOptimization] = None

    # 评论洞察
    review_insights: Dict[str, Any] = field(default_factory=dict)

    # 交叉推广
    cross_promotions: List[CrossPromotionOpportunity] = field(default_factory=list)

    # 内容营销
    content_strategies: List[ContentStrategy] = field(default_factory=list)

    # SEO 建议
    seo_suggestions: List[str] = field(default_factory=list)

    # 优先级行动计划
    action_plan: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "package_name": self.package_name,
            "genre": self.genre,
            "platform": self.platform,
            "generated_at": self.generated_at,
            "keyword_suggestions": [k.to_dict() for k in self.keyword_suggestions],
            "listing_optimization": self.listing_optimization.to_dict() if self.listing_optimization else {},
            "review_insights": self.review_insights,
            "cross_promotions": [c.to_dict() for c in self.cross_promotions],
            "content_strategies": [c.to_dict() for c in self.content_strategies],
            "seo_suggestions": self.seo_suggestions,
            "action_plan": self.action_plan,
            "total_keywords": len(self.keyword_suggestions),
            "total_actions": len(self.action_plan),
        }

    def to_markdown(self) -> str:
        """生成可读的 Markdown 报告."""
        lines: List[str] = []
        lines.append(f"# Google Play 自然量增长报告")
        lines.append(f"")
        lines.append(f"**游戏:** {self.game_id}")
        lines.append(f"**包名:** {self.package_name or '(未配置)'}")
        lines.append(f"**品类:** {self.genre}")
        lines.append(f"**平台:** {self.platform}")
        lines.append(f"**生成时间:** {self.generated_at}")
        lines.append(f"")

        # 行动计划 (最重要的放最前面)
        if self.action_plan:
            lines.append(f"## 🎯 优先级行动计划")
            lines.append(f"")
            for i, action in enumerate(self.action_plan, 1):
                priority = action.get("priority", "MEDIUM")
                emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(priority, "⚪")
                lines.append(f"{i}. {emoji} **[{priority}]** {action.get('action', '')}")
                if action.get("expected_impact"):
                    lines.append(f"   - 预期效果: {action['expected_impact']}")
                if action.get("timeline"):
                    lines.append(f"   - 时间线: {action['timeline']}")
                lines.append(f"")

        # 关键词建议
        if self.keyword_suggestions:
            lines.append(f"## 📊 ASO 关键词建议 ({len(self.keyword_suggestions)} 个)")
            lines.append(f"")
            # 按优先级排序
            priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
            sorted_kw = sorted(self.keyword_suggestions, key=lambda k: priority_order.get(k.priority, 3))
            for kw in sorted_kw[:20]:
                lines.append(
                    f"- **{kw.keyword}** [{kw.priority}] "
                    f"(来源: {kw.source}, 量: {kw.search_volume}, "
                    f"难度: {kw.difficulty:.0%})"
                )
                if kw.reason:
                    lines.append(f"  - 理由: {kw.reason}")
                if kw.action:
                    lines.append(f"  - 操作: {kw.action}")
            lines.append(f"")

        # Store Listing 优化
        if self.listing_optimization:
            lo = self.listing_optimization
            lines.append(f"## 🏪 Store Listing 优化建议")
            lines.append(f"")
            if lo.title_suggestions:
                lines.append(f"### 标题建议")
                for t in lo.title_suggestions:
                    lines.append(f"- {t}")
                lines.append(f"")
            if lo.short_description_suggestions:
                lines.append(f"### 短描述建议")
                for d in lo.short_description_suggestions:
                    lines.append(f"- {d}")
                lines.append(f"")
            if lo.localization_suggestions:
                lines.append(f"### 本地化建议")
                for loc in lo.localization_suggestions:
                    lines.append(f"- {loc}")
                lines.append(f"")

        # 评论洞察
        if self.review_insights:
            lines.append(f"## 💬 用户评论洞察")
            lines.append(f"")
            if self.review_insights.get("top_positive_words"):
                lines.append(f"### 用户正面高频词")
                words = self.review_insights["top_positive_words"]
                lines.append(f"  {', '.join(w for w, _ in words[:15])}")
                lines.append(f"")
            if self.review_insights.get("top_negative_words"):
                lines.append(f"### 用户负面高频词 (优化方向)")
                words = self.review_insights["top_negative_words"]
                lines.append(f"  {', '.join(w for w, _ in words[:10])}")
                lines.append(f"")
            if self.review_insights.get("feature_requests"):
                lines.append(f"### 用户功能请求")
                for req, count in self.review_insights["feature_requests"][:5]:
                    lines.append(f"- {req} (提及 {count} 次)")
                lines.append(f"")

        # 交叉推广
        if self.cross_promotions:
            lines.append(f"## 🔄 交叉推广机会 ({len(self.cross_promotions)} 个)")
            lines.append(f"")
            for cp in self.cross_promotions[:5]:
                lines.append(f"- **{cp.target_game_id}** ({cp.target_package_name})")
                lines.append(f"  - 重叠用户: {cp.shared_audience}")
                lines.append(f"  - 渠道: {cp.promotion_channel}")
                lines.append(f"  - 预期: {cp.expected_lift}")
            lines.append(f"")

        # 内容营销
        if self.content_strategies:
            lines.append(f"## 📱 内容营销策略 ({len(self.content_strategies)} 条)")
            lines.append(f"")
            for cs in self.content_strategies:
                lines.append(f"- **{cs.platform}** — {cs.content_type}: {cs.topic}")
                if cs.keywords:
                    lines.append(f"  - 关键词: {', '.join(cs.keywords[:5])}")
                lines.append(f"  - 频率: {cs.frequency}")
                lines.append(f"  - 预期: {cs.expected_reach}")
            lines.append(f"")

        # SEO 建议
        if self.seo_suggestions:
            lines.append(f"## 🔍 SEO 建议")
            lines.append(f"")
            for s in self.seo_suggestions:
                lines.append(f"- {s}")
            lines.append(f"")

        return "\n".join(lines)


# ── Google Play ASO 引擎 ──────────────────────────────────────

class GooglePlayASOEngine:
    """Google Play ASO 研究引擎 — 不花钱的关键词研究和自然量策略.

    能力:
      1. 基于品类知识库生成关键词建议
      2. 从用户评论中挖掘高频搜索词
      3. 分析竞品 listing 提取关键词
      4. 生成 Store Listing 优化建议
      5. 生成交叉推广策略
      6. 生成内容营销和 SEO 建议

    线程安全: 单实例可并发调用.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    # ── 主入口: 全量分析 ──

    def analyze(
        self,
        game_id: str,
        package_name: str = "",
        genre: str = "",
        country: str = "US",
        reviews: Optional[List[Dict[str, Any]]] = None,
        competitor_packages: Optional[List[str]] = None,
        portfolio_games: Optional[List[Dict[str, Any]]] = None,
    ) -> OrganicGrowthReport:
        """全量分析 — 生成完整的自然量增长报告.

        Args:
            game_id: 游戏 ID
            package_name: Google Play 包名
            genre: 游戏品类 (merge/puzzle/trivia/simulation/casual)
            country: 目标国家
            reviews: 用户评论列表 (可选, 每条含 text + rating)
            competitor_packages: 竞品包名列表 (可选)
            portfolio_games: 同一发行商的其他游戏 (可选, 用于交叉推广)

        Returns:
            OrganicGrowthReport 完整报告
        """
        genre = (genre or "").lower().strip()
        report = OrganicGrowthReport(
            game_id=game_id,
            package_name=package_name,
            genre=genre or "casual",
            platform="google_play",
        )

        # 1. 品类关键词建议 (支持包名/ID 语义自动叠加相关词库)
        report.keyword_suggestions = self._research_keywords_from_genre(
            genre, country, game_id=game_id, package_name=package_name
        )

        # 2. 评论驱动关键词挖掘
        if reviews:
            review_kw, review_insights = self._mine_reviews(reviews, genre)
            # 合并评论关键词
            kw_by_keyword = {k.keyword: k for k in report.keyword_suggestions}
            for kw in review_kw:
                if kw.keyword in kw_by_keyword:
                    # 已存在: 如果是评论验证, 更新来源和理由
                    existing = kw_by_keyword[kw.keyword]
                    if kw.source == "review_validated":
                        existing.source = "review_validated"
                        existing.reason = (
                            f"{existing.reason}; 用户评论验证 "
                            f"({kw.search_volume // 500} 次)"
                        )
                else:
                    report.keyword_suggestions.append(kw)
                    kw_by_keyword[kw.keyword] = kw
            report.review_insights = review_insights

        # 3. 竞品关键词分析
        if competitor_packages:
            comp_kw = self._analyze_competitors(competitor_packages, genre)
            existing_kw = {k.keyword for k in report.keyword_suggestions}
            for kw in comp_kw:
                if kw.keyword not in existing_kw:
                    report.keyword_suggestions.append(kw)
                    existing_kw.add(kw.keyword)

        # 4. Store Listing 优化建议
        report.listing_optimization = self._generate_listing_optimization(
            game_id, genre, report.keyword_suggestions
        )

        # 5. 交叉推广策略
        if portfolio_games:
            report.cross_promotions = self._generate_cross_promotions(
                game_id, genre, portfolio_games
            )

        # 6. 内容营销策略
        report.content_strategies = self._generate_content_strategies(
            game_id, genre, report.keyword_suggestions
        )

        # 7. SEO 建议
        report.seo_suggestions = self._generate_seo_suggestions(
            game_id, genre, package_name, report.keyword_suggestions
        )

        # 8. 优先级行动计划
        report.action_plan = self._build_action_plan(report)

        return report

    # ── 1. 品类关键词研究 ──

    # 语义标签 → 对应词库名的映射 (package_name/game_id 命中时自动叠加)
    _SEMANTIC_TAG_TO_GENRE: Dict[str, Tuple[str, ...]] = {
        "bible": ("bible", "trivia"),
        "scripture": ("bible",),
        "biblia": ("bible",),
        "biblico": ("bible",),
        "biblique": ("bible",),
        "cristiano": ("bible",),
        "christian": ("bible",),
        "faith": ("bible",),
        "quiz": ("trivia",),
        "trivia": ("trivia",),
        "merge": ("merge",),
        "puzzle": ("puzzle",),
        "hospital": ("simulation",),
        "salon": ("simulation",),
        "cooking": ("simulation",),
        "chef": ("simulation",),
    }

    def _detect_semantic_genres(self, game_id: str, package_name: str) -> List[str]:
        """从 game_id / package_name 中检测语义标签, 返回需要叠加的词库名列表 (去重, 原 genre 不含这些)."""
        text = f"{game_id or ''} {package_name or ''}".lower()
        hits: List[str] = []
        seen = set()
        for tag, genres in self._SEMANTIC_TAG_TO_GENRE.items():
            if tag in text:
                for g in genres:
                    if g not in seen:
                        hits.append(g)
                        seen.add(g)
        return hits

    def _research_keywords_from_genre(
        self,
        genre: str,
        country: str,
        game_id: str = "",
        package_name: str = "",
    ) -> List[KeywordSuggestion]:
        """基于品类知识库生成关键词建议 (含包名/ID 的语义叠加)."""
        primary = genre or "casual"
        kb = _GENRE_KEYWORDS.get(primary) or _GENRE_KEYWORDS["casual"]
        suggestions: List[KeywordSuggestion] = []
        seen_kw: set = set()

        # 叠加语义词库 (com.born2play.biblequiz → 命中 bible + trivia → 3 个词库叠加)
        extra_genres = self._detect_semantic_genres(game_id, package_name)
        kbs_to_apply: List[Tuple[str, str]] = [(primary, "primary")]
        for eg in extra_genres:
            if eg != primary:
                kbs_to_apply.append((eg, "semantic"))

        def _priority_for(source: str, tier: str) -> str:
            if source == "primary":
                return {"core": "HIGH", "long_tail": "MEDIUM", "related": "LOW"}[tier]
            # 语义词库: 核心词降一档 (避免跟主品类抢权重), 长尾保持
            return {"core": "MEDIUM", "long_tail": "MEDIUM", "related": "LOW"}[tier]

        for source_name, src_label in kbs_to_apply:
            kb_i = _GENRE_KEYWORDS.get(source_name) or _GENRE_KEYWORDS["casual"]
            for tier, priority_map in (("core", _priority_for(src_label, "core")),
                                        ("long_tail", _priority_for(src_label, "long_tail")),
                                        ("related", _priority_for(src_label, "related"))):
                for kw in kb_i[tier]:
                    if kw in seen_kw:
                        continue
                    seen_kw.add(kw)
                    is_core = tier == "core"
                    label = "语义扩展" if src_label != "primary" else primary
                    suggestions.append(KeywordSuggestion(
                        keyword=kw,
                        source=f"genre_kb:{source_name}" if src_label != "primary" else "genre_kb",
                        search_volume=self._estimate_volume(kw, is_core=is_core),
                        difficulty=0.35 if is_core else 0.22,
                        priority=priority_map,
                        reason=f"{label} 品类词, {tier}",
                        action=("放入标题和短描述前 30 字符" if is_core
                                else "嵌入完整描述, 每个词自然出现 2-3 次"),
                    ))

        return suggestions

    @staticmethod
    def _estimate_volume(keyword: str, is_core: bool) -> int:
        """估算搜索量 (基于关键词长度和类型)."""
        base = 50000 if is_core else 10000
        # 短词搜索量更高
        word_count = len(keyword.split())
        if word_count <= 2:
            return base
        elif word_count <= 4:
            return base // 3
        else:
            return base // 8

    # ── 2. 评论驱动的关键词挖掘 ──

    def _mine_reviews(
        self,
        reviews: List[Dict[str, Any]],
        genre: str,
    ) -> Tuple[List[KeywordSuggestion], Dict[str, Any]]:
        """从用户评论中挖掘关键词和洞察.

        Returns:
            (关键词建议列表, 评论洞察 dict)
        """
        positive_words: Counter = Counter()
        negative_words: Counter = Counter()
        feature_requests: Counter = Counter()
        all_phrases: Counter = Counter()

        for review in reviews:
            text = (review.get("text", "") or "").lower().strip()
            rating = float(review.get("rating", 0) or 0)
            if not text:
                continue

            # 提取词组 (2-3词)
            phrases = self._extract_phrases(text)
            all_phrases.update(phrases)

            # 按评分分类
            if rating >= 4:
                positive_words.update(self._extract_meaningful_words(text))
            elif rating <= 2:
                negative_words.update(self._extract_meaningful_words(text))

            # 检测功能请求
            for pattern in ["wish", "want", "need", "should add", "please add", "hope"]:
                if pattern in text:
                    # 提取包含请求的句子
                    for sentence in text.split("."):
                        if pattern in sentence:
                            req = sentence.strip()[:80]
                            if len(req) > 10:
                                feature_requests[req] += 1
                            break

        # 从高频词组生成关键词建议
        suggestions: List[KeywordSuggestion] = []
        kb = _GENRE_KEYWORDS.get(genre) or _GENRE_KEYWORDS["casual"]
        existing_kw: Set[str] = set(kb["core"] + kb["long_tail"] + kb["related"])

        for phrase, count in all_phrases.most_common(30):
            if count < 2:
                continue
            # 检查是否包含品类相关词
            genre_words = genre.split() + ["game", "puzzle", "level", "play"]
            if any(gw in phrase for gw in genre_words):
                if phrase in existing_kw:
                    # 已在品类知识库中, 标记为评论验证
                    suggestions.append(KeywordSuggestion(
                        keyword=phrase,
                        source="review_validated",
                        search_volume=count * 500,
                        difficulty=0.2,
                        priority="HIGH" if count >= 5 else "MEDIUM",
                        reason=f"用户评论验证 ({count} 次), 确认是高转化关键词",
                        action="优先放入标题/短描述",
                    ))
                else:
                    suggestions.append(KeywordSuggestion(
                        keyword=phrase,
                        source="review_mining",
                        search_volume=count * 500,
                        difficulty=0.2,
                        priority="HIGH" if count >= 5 else "MEDIUM",
                        reason=f"用户评论中高频出现 ({count} 次), 是真实搜索词",
                        action="放入标题/短描述, 匹配用户真实搜索意图",
                    ))
                    existing_kw.add(phrase)

        insights = {
            "total_reviews_analyzed": len(reviews),
            "top_positive_words": positive_words.most_common(20),
            "top_negative_words": negative_words.most_common(15),
            "feature_requests": feature_requests.most_common(10),
            "review_phrases": all_phrases.most_common(30),
        }

        return suggestions, insights

    @staticmethod
    def _extract_phrases(text: str) -> List[str]:
        """从文本中提取 2-3 词短语."""
        phrases: List[str] = []
        words = re.findall(r"[a-z]+", text.lower())
        # 2-gram
        for i in range(len(words) - 1):
            w1, w2 = words[i], words[i + 1]
            if w1 not in _STOP_WORDS_EN and w2 not in _STOP_WORDS_EN:
                if len(w1) > 2 and len(w2) > 2:
                    phrases.append(f"{w1} {w2}")
        # 3-gram
        for i in range(len(words) - 2):
            w1, w2, w3 = words[i], words[i + 1], words[i + 2]
            if (w1 not in _STOP_WORDS_EN and w3 not in _STOP_WORDS_EN
                    and len(w1) > 2 and len(w3) > 2):
                phrases.append(f"{w1} {w2} {w3}")
        return phrases

    @staticmethod
    def _extract_meaningful_words(text: str) -> List[str]:
        """提取有意义的单词 (过滤停用词)."""
        words = re.findall(r"[a-z]+", text.lower())
        return [
            w for w in words
            if len(w) > 3
            and w not in _STOP_WORDS_EN
            and w not in _STOP_WORDS_EXTRA
            and not w.isdigit()
        ]

    # ── 3. 竞品分析 ──

    def _analyze_competitors(
        self,
        competitor_packages: List[str],
        genre: str,
    ) -> List[KeywordSuggestion]:
        """分析竞品 listing 提取关键词 (模拟, 实际需要抓取)."""
        suggestions: List[KeywordSuggestion] = []

        # 基于品类生成竞品常见关键词模式
        kb = _GENRE_KEYWORDS.get(genre) or _GENRE_KEYWORDS["casual"]

        # 竞品常用但我们可能遗漏的词
        competitor_patterns = [
            f"top {genre} game",
            f"{genre} game 2024",
            f"new {genre} game",
            f"best {genre} game",
            f"free {genre} game download",
            f"{genre} game for android",
            f"{genre} game no internet",
            f"{genre} game without wifi",
            f"offline {genre} game",
            f"{genre} game with levels",
        ]

        for kw in competitor_patterns:
            suggestions.append(KeywordSuggestion(
                keyword=kw,
                source="competitor",
                search_volume=self._estimate_volume(kw, is_core=False),
                difficulty=0.35,
                priority="MEDIUM",
                reason="竞品 listing 中常见, 用户搜索意图明确",
                action="放入完整描述, 确保自然出现",
            ))

        return suggestions

    # ── 4. Store Listing 优化建议 ──

    def _generate_listing_optimization(
        self,
        game_id: str,
        genre: str,
        keywords: List[KeywordSuggestion],
    ) -> ListingOptimization:
        """生成 Store Listing 优化建议."""
        opt = ListingOptimization()

        # 获取高优先级关键词
        high_priority_kw = [k.keyword for k in keywords if k.priority == "HIGH"][:5]
        medium_priority_kw = [k.keyword for k in keywords if k.priority == "MEDIUM"][:8]

        # 标题建议 (Google Play 限 30 字符)
        game_name = game_id.replace("_", " ").title()
        if genre == "merge":
            opt.title_suggestions = [
                f"{game_name}: Merge & Match"[:30],
                f"Merge {game_name}"[:30],
                f"{game_name} - Merge Puzzle"[:30],
            ]
        elif genre == "puzzle":
            opt.title_suggestions = [
                f"{game_name}: Puzzle Game"[:30],
                f"{game_name} - Brain Puzzle"[:30],
                f"{game_name} Word Puzzle"[:30],
            ]
        elif genre == "trivia":
            opt.title_suggestions = [
                f"{game_name}: Trivia Game"[:30],
                f"{game_name} - Quiz Game"[:30],
                f"{game_name} Trivia"[:30],
            ]
        elif genre == "simulation":
            opt.title_suggestions = [
                f"{game_name}: Sim Game"[:30],
                f"{game_name} - Tycoon Game"[:30],
                f"{game_name} Simulation"[:30],
            ]
        else:
            opt.title_suggestions = [
                f"{game_name}: Fun Game"[:30],
                f"{game_name} - Casual Game"[:30],
                f"Play {game_name}"[:30],
            ]

        # 短描述建议 (Google Play 限 80 字符)
        if high_priority_kw:
            top_kw = high_priority_kw[0]
            second_kw = high_priority_kw[1] if len(high_priority_kw) > 1 else "free game"
            opt.short_description_suggestions = [
                f"Play {top_kw}! {second_kw} for free. Download now!"[:80],
                f"Best {genre} game! {top_kw}. Free to play offline."[:80],
                f"Love {genre}? Try {top_kw}! Free download, no wifi needed."[:80],
            ]
        else:
            opt.short_description_suggestions = [
                f"Best {genre} game! Free to play. Download now!"[:80],
                f"Fun {genre} game for everyone. Play offline!"[:80],
            ]

        # 完整描述关键词 (Google Play 限 4000 字符)
        opt.full_description_keywords = (
            high_priority_kw + medium_priority_kw
        )[:15]

        # 截图顺序建议
        opt.screenshot_order_suggestions = [
            "1. 游戏核心玩法截图 (最吸引人的画面)",
            "2. 特色功能展示 (独特机制)",
            "3. 角色/元素展示",
            "4. 关卡/进度展示",
            "5. 社交/竞技功能 (如有)",
            "6. 奖励/成就展示",
            "7. 操作引导截图",
            "8. 情绪唤起截图 (快乐/成就感)",
        ]

        # 本地化建议
        opt.localization_suggestions = [
            "优先本地化: 英语 → 葡萄牙语 → 西班牙语 → 德语 → 法语 → 日语 → 韩语",
            "巴西 (PT-BR) 是休闲游戏增长最快的市场, 优先本地化",
            "标题和短描述必须本地化, 完整描述可先机翻后人工校对",
            "截图文字也要本地化, 不要只翻译描述文字",
            "关键词要按地区重新研究, 不要直接翻译英文关键词",
        ]

        # Icon 优化
        opt.icon_optimization = (
            f"Icon 应突出 {genre} 品类特征, 使用高饱和度色彩, "
            f"在 192x192 小尺寸下仍清晰可辨. "
            f"建议 A/B 测试 3 个 Icon 变体, 持续 7 天对比安装转化率."
        )

        return opt

    # ── 5. 交叉推广策略 ──

    def _generate_cross_promotions(
        self,
        game_id: str,
        genre: str,
        portfolio_games: List[Dict[str, Any]],
    ) -> List[CrossPromotionOpportunity]:
        """生成跨游戏交叉推广策略."""
        opportunities: List[CrossPromotionOpportunity] = []

        for game in portfolio_games:
            gid = game.get("game_id", "")
            pkg = game.get("package_name", "")
            g_genre = (game.get("genre", "") or "").lower()

            if gid == game_id:
                continue

            # 同品类 → 高优先级
            if g_genre == genre:
                opportunities.append(CrossPromotionOpportunity(
                    target_game_id=gid,
                    target_package_name=pkg,
                    shared_audience=f"同品类 ({genre}) 用户, 兴趣高度重叠",
                    promotion_channel="in_app",
                    expected_lift="预计 +5-8% 自然量",
                ))
            # 相近品类 → 中优先级
            elif self._genres_compatible(genre, g_genre):
                opportunities.append(CrossPromotionOpportunity(
                    target_game_id=gid,
                    target_package_name=pkg,
                    shared_audience=f"相近品类 ({genre} ↔ {g_genre}), 用户画像部分重叠",
                    promotion_channel="in_app",
                    expected_lift="预计 +2-4% 自然量",
                ))

        return opportunities[:10]

    @staticmethod
    def _genres_compatible(g1: str, g2: str) -> bool:
        """判断两个品类是否用户群兼容."""
        compatible_groups = [
            {"merge", "puzzle", "casual"},
            {"trivia", "puzzle", "educational"},
            {"simulation", "casual"},
        ]
        for group in compatible_groups:
            if g1 in group and g2 in group:
                return True
        return False

    # ── 6. 内容营销策略 ──

    def _generate_content_strategies(
        self,
        game_id: str,
        genre: str,
        keywords: List[KeywordSuggestion],
    ) -> List[ContentStrategy]:
        """生成内容营销策略."""
        strategies: List[ContentStrategy] = []
        top_kw = [k.keyword for k in keywords if k.priority == "HIGH"][:5]

        # YouTube 策略
        strategies.append(ContentStrategy(
            platform="youtube",
            content_type="gameplay",
            topic=f"{genre} game gameplay walkthrough",
            keywords=top_kw[:3],
            frequency="每周 2-3 个视频",
            expected_reach="每个视频 500-5000 观看 (6 个月内)",
        ))
        strategies.append(ContentStrategy(
            platform="youtube",
            content_type="tutorial",
            topic=f"how to play {genre} game - tips and tricks",
            keywords=[f"{genre} tips", f"{genre} guide", f"{genre} strategy"],
            frequency="每周 1 个视频",
            expected_reach="长尾流量持续增长",
        ))

        # TikTok 策略
        strategies.append(ContentStrategy(
            platform="tiktok",
            content_type="short_form",
            topic=f"{genre} game satisfying moments",
            keywords=[f"#{genre}", "#mobilegame", "#freegame"],
            frequency="每天 1-2 个短视频",
            expected_reach="每条 200-2000 观看, 有机会爆款",
        ))

        # Reddit 策略
        strategies.append(ContentStrategy(
            platform="reddit",
            content_type="community",
            topic=f"r/{genre}games 社区互动和游戏分享",
            keywords=[],
            frequency="每周 2-3 帖",
            expected_reach="精准用户, 高转化",
        ))

        # Instagram 策略
        strategies.append(ContentStrategy(
            platform="instagram",
            content_type="visual",
            topic=f"{genre} game art and behind the scenes",
            keywords=[f"#{genre}game", "#mobilegaming", "#gamedev"],
            frequency="每周 3-5 个帖子",
            expected_reach="品牌建设 + 自然搜索",
        ))

        return strategies

    # ── 7. SEO 建议 ──

    def _generate_seo_suggestions(
        self,
        game_id: str,
        genre: str,
        package_name: str,
        keywords: List[KeywordSuggestion],
    ) -> List[str]:
        """生成 SEO 建议."""
        top_kw = [k.keyword for k in keywords if k.priority == "HIGH"][:5]
        suggestions: List[str] = []

        suggestions.append(
            f"创建独立着陆页 (landing page), 优化 SEO 关键词: {', '.join(top_kw[:3])}"
        )
        suggestions.append(
            f"在 landing page 中嵌入 Google Play 安装按钮, 做 deep link"
        )
        suggestions.append(
            f"写 5-10 篇 SEO 博客: '{genre} game tips', 'best {genre} games 2024', "
            f"'how to play {genre}' 等长尾内容"
        )
        suggestions.append(
            f"提交 sitemap 到 Google Search Console, 监控关键词排名"
        )
        suggestions.append(
            f"在 Wikipedia/游戏百科网站创建游戏条目 (如果游戏有足够知名度)"
        )
        if package_name:
            suggestions.append(
                f"使用 Firebase App Indexing 让 Google 搜索能索引 app 内容: {package_name}"
            )
        suggestions.append(
            f"在 GitHub/itch.io 等开发者社区分享开发日志, 建立 indie dev 品牌"
        )

        return suggestions

    # ── 8. 优先级行动计划 ──

    def _build_action_plan(self, report: OrganicGrowthReport) -> List[Dict[str, Any]]:
        """基于报告生成优先级行动计划."""
        actions: List[Dict[str, Any]] = []

        # 最高优先级: 标题和短描述优化
        if report.listing_optimization and report.listing_optimization.title_suggestions:
            actions.append({
                "priority": "HIGH",
                "action": f"优化 Google Play 标题 (当前 → '{report.listing_optimization.title_suggestions[0]}')",
                "expected_impact": "搜索可见度 +15-30%, 安装转化 +5-10%",
                "timeline": "立即执行 (1 天内)",
            })
            actions.append({
                "priority": "HIGH",
                "action": f"优化短描述 → '{report.listing_optimization.short_description_suggestions[0]}'",
                "expected_impact": "搜索转化 +10-20%",
                "timeline": "立即执行 (1 天内)",
            })

        # 高优先级: 完整描述关键词优化
        if report.listing_optimization and report.listing_optimization.full_description_keywords:
            kw_list = ", ".join(report.listing_optimization.full_description_keywords[:5])
            actions.append({
                "priority": "HIGH",
                "action": f"在完整描述中自然嵌入关键词: {kw_list}",
                "expected_impact": "长尾搜索流量 +20-40%",
                "timeline": "1-2 天内",
            })

        # 高优先级: 本地化
        if report.listing_optimization and report.listing_optimization.localization_suggestions:
            actions.append({
                "priority": "HIGH",
                "action": "本地化到 PT-BR (巴西) 和 ES (西班牙语)",
                "expected_impact": "巴西自然量 +50-100%, 西语市场 +30-60%",
                "timeline": "1 周内",
            })

        # 中优先级: 截图优化
        if report.listing_optimization and report.listing_optimization.screenshot_order_suggestions:
            actions.append({
                "priority": "MEDIUM",
                "action": "按建议重排截图顺序, 第一张放最吸引人的画面",
                "expected_impact": "安装转化 +5-15%",
                "timeline": "1 周内",
            })

        # 中优先级: 内容营销启动
        if report.content_strategies:
            actions.append({
                "priority": "MEDIUM",
                "action": "启动 YouTube + TikTok 内容营销, 每周 3 个视频",
                "expected_impact": "3 个月内自然量 +10-20%",
                "timeline": "2 周内启动",
            })

        # 中优先级: 交叉推广
        if report.cross_promotions:
            top_cp = report.cross_promotions[0]
            actions.append({
                "priority": "MEDIUM",
                "action": f"在 {top_cp.target_game_id} 中添加交叉推广 banner",
                "expected_impact": top_cp.expected_lift,
                "timeline": "1 周内",
            })

        # 低优先级: SEO
        if report.seo_suggestions:
            actions.append({
                "priority": "LOW",
                "action": "创建 SEO 着陆页和博客内容",
                "expected_impact": "6 个月内自然搜索 +5-15%",
                "timeline": "1 个月内启动",
            })

        # 低优先级: Icon A/B 测试
        if report.listing_optimization and report.listing_optimization.icon_optimization:
            actions.append({
                "priority": "LOW",
                "action": "A/B 测试 3 个 Icon 变体 (Google Play 内置实验)",
                "expected_impact": "安装转化 +3-8%",
                "timeline": "2-4 周",
            })

        return actions


# ── 单例 ──────────────────────────────────────────────────────

_instance: Optional[GooglePlayASOEngine] = None
_instance_lock = threading.Lock()


def get_google_play_aso_engine() -> GooglePlayASOEngine:
    """获取单例实例."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = GooglePlayASOEngine()
    return _instance


def reset_google_play_aso_engine() -> None:
    """重置单例 (用于测试)."""
    global _instance
    with _instance_lock:
        _instance = None


__all__ = [
    "KeywordSuggestion",
    "ListingOptimization",
    "CrossPromotionOpportunity",
    "ContentStrategy",
    "OrganicGrowthReport",
    "GooglePlayASOEngine",
    "get_google_play_aso_engine",
    "reset_google_play_aso_engine",
]
