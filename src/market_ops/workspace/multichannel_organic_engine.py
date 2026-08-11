"""多渠道自然量增长引擎.

不仅靠 Google Play 搜索, 同时铺开 10+ 免费流量渠道, 多管齐下找自然安装.

覆盖渠道:
  1. 第三方 Android 应用市场 (Amazon / Samsung / Huawei / Aptoide / APKPure / Uptodown)
  2. 社交媒体 (Facebook Groups / Reddit / X / Pinterest)
  3. 游戏社区 (Itch.io / GameJolt / IndieDB)
  4. 内容营销 (SEO 着陆页 / Quora / Medium / HubPages)
  5. 视频 SEO (YouTube Shorts / TikTok / Reels 脚本)
  6. 信仰社区 (基督教会论坛 / Bible study groups)
  7. 交叉推广 (Portfolio 内其他圣经类游戏互带)
  8. 免费抽奖 / 礼物卡活动 (提高评分和分享率)

每个渠道提供: 提交 URL, 可直接复制的文案, 执行优先级 (HIGH/MEDIUM/LOW).
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)


# ── 数据模型 ──────────────────────────────────────────────────

@dataclass
class ChannelAction:
    """一个渠道的执行动作."""
    channel: str
    category: str  # "app_market" | "social" | "community" | "content" | "video_seo" | "cross_promo"
    priority: str  # "HIGH" | "MEDIUM" | "LOW"
    platform_url: str
    submit_guide: str
    copy_ready_title: str
    copy_ready_body: str
    hashtags: List[str] = field(default_factory=list)
    target_country: str = "ALL"
    estimated_organic_installs: int = 0
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "channel": self.channel,
            "category": self.category,
            "priority": self.priority,
            "platform_url": self.platform_url,
            "submit_guide": self.submit_guide,
            "copy_ready_title": self.copy_ready_title,
            "copy_ready_body": self.copy_ready_body,
            "hashtags": self.hashtags,
            "target_country": self.target_country,
            "estimated_organic_installs": self.estimated_organic_installs,
            "notes": self.notes,
        }


@dataclass
class MultiChannelGrowthReport:
    """多渠道自然量增长报告."""
    game_id: str
    package_name: str
    game_display_name: str
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    total_channels: int = 0
    total_estimated_installs: int = 0
    channels: List[ChannelAction] = field(default_factory=list)
    cross_promo_plan: List[Dict[str, Any]] = field(default_factory=list)
    seo_keywords: List[str] = field(default_factory=list)
    short_term_actions: List[str] = field(default_factory=list)
    medium_term_actions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "package_name": self.package_name,
            "game_display_name": self.game_display_name,
            "generated_at": self.generated_at,
            "total_channels": self.total_channels,
            "total_estimated_installs": self.total_estimated_installs,
            "channels": [c.to_dict() for c in self.channels],
            "cross_promo_plan": self.cross_promo_plan,
            "seo_keywords": self.seo_keywords,
            "short_term_actions": self.short_term_actions,
            "medium_term_actions": self.medium_term_actions,
        }


# ── 多渠道引擎 ────────────────────────────────────────────────

class MultiChannelOrganicEngine:
    """多渠道自然量增长引擎.

    为单一游戏生成 10+ 免费渠道的提交文案和执行指南.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    # ── 公开入口 ──

    def generate_growth_plan(
        self,
        game_id: str,
        package_name: str,
        game_display_name: str = "",
        genre: str = "casual",
        portfolio_games: Optional[List[Dict[str, Any]]] = None,
    ) -> MultiChannelGrowthReport:
        """生成完整的多渠道自然量增长方案."""
        display = game_display_name or self._extract_display_name(game_id, package_name)

        report = MultiChannelGrowthReport(
            game_id=game_id,
            package_name=package_name,
            game_display_name=display,
        )

        report.channels.extend(self._build_app_markets(display, package_name, genre))
        report.channels.extend(self._build_social_posts(display, package_name, genre))
        report.channels.extend(self._build_game_communities(display, package_name, genre))
        report.channels.extend(self._build_content_marketing(display, package_name, genre))
        report.channels.extend(self._build_video_seo_scripts(display, package_name, genre))
        report.channels.extend(self._build_faith_communities(display, package_name, genre))

        report.total_channels = len(report.channels)
        report.total_estimated_installs = sum(c.estimated_organic_installs for c in report.channels)

        # 交叉推广计划
        if portfolio_games:
            report.cross_promo_plan = self._build_cross_promo(display, package_name, portfolio_games, genre)

        # SEO 关键词 (非 Store, 是网页搜索)
        report.seo_keywords = self._seo_keywords_for_genre(genre, display)

        # 优先级行动列表
        high_priority = [c for c in report.channels if c.priority == "HIGH"]
        medium_priority = [c for c in report.channels if c.priority == "MEDIUM"]

        report.short_term_actions = [
            f"[立即] {c.channel}: {c.copy_ready_title[:60]} — {c.platform_url}"
            for c in high_priority
        ]
        report.medium_term_actions = [
            f"[本周] {c.channel}: {c.copy_ready_title[:60]} — {c.platform_url}"
            for c in medium_priority
        ]

        return report

    # ── 1. 第三方 Android 应用市场 ──

    def _build_app_markets(
        self, display: str, package: str, genre: str
    ) -> List[ChannelAction]:
        """第三方应用市场提交清单."""
        title = self._market_title(display, genre)
        body_short = self._market_body_short(display, genre)
        body_long = self._market_body_long(display, genre)

        return [
            ChannelAction(
                channel="Amazon Appstore",
                category="app_market",
                priority="HIGH",
                platform_url="https://developer.amazon.com/apps-and-games",
                submit_guide="注册亚马逊开发者账号 (免费) → 创建新应用 → 上传相同 APK → 填入标题/描述/截图 → 提交审核 (1-3天)",
                copy_ready_title=title,
                copy_ready_body=body_long,
                estimated_organic_installs=80,
                notes="Fire 平板用户量大, 圣经应用竞争远小于 Google Play",
            ),
            ChannelAction(
                channel="Samsung Galaxy Store",
                category="app_market",
                priority="HIGH",
                platform_url="https://seller.samsungapps.com",
                submit_guide="注册三星卖家 (免费) → 注册商用 Seller → 提交 APK + 元数据 → 审核 2-5 天",
                copy_ready_title=title,
                copy_ready_body=body_long,
                estimated_organic_installs=50,
                notes="三星手机预装商店, 美国/韩国用户量大",
            ),
            ChannelAction(
                channel="Huawei AppGallery",
                category="app_market",
                priority="MEDIUM",
                platform_url="https://developer.huawei.com/consumer/en/service/josp/agc/index.html",
                submit_guide="注册华为开发者 → 实名认证 → 提交 APK → 审核 3-7 天",
                copy_ready_title=title,
                copy_ready_body=body_long,
                estimated_organic_installs=40,
                notes="华为海外用户, 尤其是拉美/欧洲无法用 GMS 的设备",
            ),
            ChannelAction(
                channel="Aptoide",
                category="app_market",
                priority="MEDIUM",
                platform_url="https://upload.aptoide.com",
                submit_guide="注册开发者账号 (免费) → 创建商店 → 上传 APK → 自动索引",
                copy_ready_title=title,
                copy_ready_body=body_short,
                estimated_organic_installs=30,
                notes="第二大第三方安卓市场, 免费用户搜索流量",
            ),
            ChannelAction(
                channel="APKPure",
                category="app_market",
                priority="MEDIUM",
                platform_url="https://apkpure.com/submit",
                submit_guide="提交 APK + 描述 → 人工审核收录 → 搜索可找到",
                copy_ready_title=title,
                copy_ready_body=body_short,
                estimated_organic_installs=25,
                notes="全球用户量大, 但需要 APK 不包含广告违规",
            ),
            ChannelAction(
                channel="Uptodown",
                category="app_market",
                priority="LOW",
                platform_url="https://en.uptodown.com/developers",
                submit_guide="开发者合作形式提交 → 审核后自动更新",
                copy_ready_title=title,
                copy_ready_body=body_short,
                estimated_organic_installs=15,
                notes="西班牙语和拉美用户极多, 本地化 bible 版本有优势",
            ),
        ]

    # ── 2. 社交媒体帖子 ──

    def _build_social_posts(
        self, display: str, package: str, genre: str
    ) -> List[ChannelAction]:
        """社交媒体发布清单 (免费, 不用投广告)."""
        play_url = f"https://play.google.com/store/apps/details?id={package}"

        # 信仰社交内容
        fb_body = (
            f"📖 Looking for a fun way to study the Bible? Try {display} — "
            f"1000+ trivia questions from Genesis to Revelation! 🙏✨\n\n"
            f"✅ Play offline without wifi\n"
            f"✅ Easy / Medium / Hard / Expert levels\n"
            f"✅ Daily Bible verse & devotional\n"
            f"✅ 100% FREE — no subscription needed\n\n"
            f"👉 Download now: {play_url}\n\n"
            f"Tag a friend who loves Bible quizzes! #BibleStudy #Faith"
        )
        reddit_body = (
            f"**{display}** — I made a free Bible trivia game with 1000+ questions "
            f"covering Old & New Testament. No wifi needed, no hidden costs.\n\n"
            f"Features:\n"
            f"- 4 difficulty levels (Easy → Expert)\n"
            f"- Daily Bible verse challenges\n"
            f"- Memorize scripture while having fun\n\n"
            f"Google Play: {play_url}\n\n"
            f"Let me know what you think! Constructive feedback welcome."
        )
        pin_title = f"Free Bible Quiz Game - Test Your Scripture Knowledge"
        pin_body = (
            f"Grow your faith with {display}! A fun & free bible trivia app "
            f"perfect for church groups, bible studies, and personal devotions.\n"
            f"→ Old & New Testament questions\n"
            f"→ Play with friends & family\n"
            f"→ Offline mode: study anywhere\n"
            f"{play_url}\n#Bible #Faith #Christian #Trivia"
        )
        x_body = (
            f"📖 {display} is now FREE on Google Play!\n"
            f"Test your Bible knowledge with 1000+ trivia questions. "
            f"Play offline, daily verses, 4 difficulty levels.\n"
            f"👉 {play_url}\n#BibleQuiz #ChristianApp #BibleTrivia"
        )

        return [
            ChannelAction(
                channel="Facebook Groups",
                category="social",
                priority="HIGH",
                platform_url="https://www.facebook.com/groups/?sort=groups_joined",
                submit_guide="加入 10+ 个圣经/基督教群 (bible study / christian fellowship) → 每个群 1-2 天发一次, 不要纯广告, 加一句灵修心得 → 附 Play 链接",
                copy_ready_title=f"Fun way to study the Bible — {display}!",
                copy_ready_body=fb_body,
                hashtags=["#BibleStudy", "#Christian", "#Faith", "#BibleTrivia", "#ChurchApp"],
                target_country="US,BR,ES",
                estimated_organic_installs=60,
                notes="找 5-10 个活跃的 Bible Study / Christian Appreciation 群, 每周各发 1 次",
            ),
            ChannelAction(
                channel="Reddit",
                category="social",
                priority="HIGH",
                platform_url="https://www.reddit.com/r/TrueChristian/ https://www.reddit.com/r/Christianity/ https://www.reddit.com/r/Bible/",
                submit_guide="在 r/TrueChristian + r/Christianity + r/Bible 发帖 → 以用户分享口气, 不要太广告 → 先发帖问反馈, 评论里附链接",
                copy_ready_title=f"[FREE APP] {display} — 1000+ Bible trivia questions, no wifi needed",
                copy_ready_body=reddit_body,
                hashtags=["#Christian", "#Bible", "#Trivia", "#FreeApp"],
                target_country="US,CA,GB,AU",
                estimated_organic_installs=40,
                notes="Reddit 严禁 spam, 必须有真实反馈价值 (问用户需求, 比如: 你们最想加哪些经文?)",
            ),
            ChannelAction(
                channel="X (Twitter)",
                category="social",
                priority="MEDIUM",
                platform_url="https://x.com",
                submit_guide="注册/登录账号 → 每日发 1-2 条 (含 1 句经文 + 小问答 + Play 链接) → @Pastors/Christian 博主互动",
                copy_ready_title=f"{display} - Free Bible Trivia",
                copy_ready_body=x_body,
                hashtags=["#BibleQuiz", "#BibleTrivia", "#ChristianApp", "#Faith", "#DailyVerse"],
                estimated_organic_installs=25,
                notes="每天找 3 个基督教相关 hashtag (#BibleVerse #DailyDevotion) 发推文",
            ),
            ChannelAction(
                channel="Pinterest",
                category="social",
                priority="MEDIUM",
                platform_url="https://www.pinterest.com",
                submit_guide="创建 Board 'Bible Study Apps' → 发布 Pin (截图 + Play 链接 + 经文短评) → 搜索量长期积累, 不衰减",
                copy_ready_title=pin_title,
                copy_ready_body=pin_body,
                hashtags=["#Bible", "#Christian", "#Faith", "#SundaySchool", "#BibleQuiz"],
                estimated_organic_installs=20,
                notes="Pinterest 对搜索流量很好, 1 个 Pin 可以持续 1 年以上带来自然量",
            ),
        ]

    # ── 3. 游戏社区 ──

    def _build_game_communities(
        self, display: str, package: str, genre: str
    ) -> List[ChannelAction]:
        play_url = f"https://play.google.com/store/apps/details?id={package}"
        title = f"{display} — Free Bible Trivia Game (1000+ Questions)"
        body = (
            f"Hi indie devs! 👋 I just released {display}, a free bible trivia game.\n\n"
            f"📦 Features:\n"
            f"- 1000+ questions covering Genesis to Revelation\n"
            f"- 4 difficulty levels\n"
            f"- Daily verse & devotional challenges\n"
            f"- Offline mode (no wifi required)\n"
            f"- No subscription, no pay-to-win\n\n"
            f"Play Store: {play_url}\n\n"
            f"Would love your feedback! Especially on:\n"
            f"- Are the questions balanced?\n"
            f"- What books/chapters should I add more questions for?"
        )

        return [
            ChannelAction(
                channel="Itch.io",
                category="community",
                priority="HIGH",
                platform_url="https://itch.io/game/upload",
                submit_guide="上传 WebGL demo (如果有) 或 'Mobile game' 形式 → 免费发布, 可嵌入 Play 链接 → 加标签 'bible', 'trivia', 'christian', 'educational'",
                copy_ready_title=title,
                copy_ready_body=body,
                hashtags=["#bible", "#trivia", "#educational", "#christian", "#mobile"],
                estimated_organic_installs=20,
                notes="Itch.io 有免费游戏流量, 加上 bible/educational 标签搜索量不错",
            ),
            ChannelAction(
                channel="GameJolt",
                category="community",
                priority="MEDIUM",
                platform_url="https://gamejolt.com/games/upload",
                submit_guide="免费上传 Mobile 游戏, 填截图 + 描述, 附 Play 链接 → 参加社区活动",
                copy_ready_title=title,
                copy_ready_body=body,
                hashtags=["#trivia", "#educational", "#indie", "#christian"],
                estimated_organic_installs=10,
                notes="GameJolt 社区活跃, 适合找种子用户测试反馈",
            ),
            ChannelAction(
                channel="IndieDB",
                category="community",
                priority="LOW",
                platform_url="https://www.indiedb.com/games/add",
                submit_guide="提交游戏条目 (需审核) → 发布截图 + 开发日志 → 积累 SEO 反链",
                copy_ready_title=title,
                copy_ready_body=body,
                estimated_organic_installs=5,
                notes="主要用于 SEO 反链和增加 Google Play 权威度",
            ),
        ]

    # ── 4. 内容营销 ──

    def _build_content_marketing(
        self, display: str, package: str, genre: str
    ) -> List[ChannelAction]:
        play_url = f"https://play.google.com/store/apps/details?id={package}"
        seo_keywords = self._seo_keywords_for_genre(genre, display)
        kw_line = ", ".join(seo_keywords[:8])

        medium_article = (
            f"# How I Built a Free Bible Trivia Game to Help Christians Grow Their Faith\n\n"
            f"As a believer and game developer, I noticed there was a lack of **high-quality, "
            f"offline-capable** {kw_line} apps on Google Play. So I built {display}.\n\n"
            f"## Why another Bible app?\n\n"
            f"Most Bible quiz apps:\n"
            f"- Only cover Genesis and Psalms\n"
            f"- Require internet connection\n"
            f"- Are packed with intrusive ads\n\n"
            f"Here's what {display} does differently:\n\n"
            f"✅ **1000+ questions** — Old AND New Testament\n"
            f"✅ **4 difficulty levels** — Easy / Medium / Hard / Expert\n"
            f"✅ **Daily challenges** — Learn one new Bible verse each day\n"
            f"✅ **100% offline** — Study on the subway, on a plane, anywhere\n\n"
            f"## Download\n\n"
            f"{play_url}\n\n"
            f"Free forever. No subscription. No pay-to-win.\n\n"
            f"---\n"
            f"If you try it, let me know what you think! I read every review and "
            f"add questions based on your requests.\n"
        )

        # Quora 回答模板 (搜索 Questions 然后答)
        quora_answers = [
            {
                "q": "What is the best free Bible trivia app for Android?",
                "a": f"I've been using {display} for 3 months now. Great coverage of Old Testament and New "
                   f"Testament, works completely offline (which I need for my commute), and the daily verse "
                   f"challenge is perfect for morning devotions. {play_url}",
            },
            {
                "q": "Are there any good Bible quiz apps that work offline?",
                "a": f"Yes, {display} is a solid one — 1000+ trivia questions from Genesis to Revelation, "
                   f"no wifi needed at all. I play on flights and during church retreats. "
                   f"Link: {play_url}",
            },
        ]

        actions = [
            ChannelAction(
                channel="Medium Article",
                category="content",
                priority="HIGH",
                platform_url="https://medium.com/new-story",
                submit_guide="注册 Medium 账号 → 发布本文 → 加入 Christian / Bible Study / Mobile App Development 相关话题 → 评论 3-5 个同类文章引流",
                copy_ready_title=f"How I Built a Free Bible Trivia Game (1000+ Questions, 100% Offline)",
                copy_ready_body=medium_article,
                hashtags=["#Bible", "#Christian", "#MobileApp", "#Faith"],
                estimated_organic_installs=30,
                notes="Medium 文章 SEO 权重高, 关键词 'free bible quiz app' 可排前几页",
            ),
            ChannelAction(
                channel="Quora Answers",
                category="content",
                priority="HIGH",
                platform_url="https://www.quora.com/search?q=best+bible+trivia+app",
                submit_guide="搜索 'bible trivia app' / 'free bible quiz' / 'offline bible game' 问题 → 每条都回答 (真诚, 不硬广) → 文末附 Play 链接",
                copy_ready_title=quora_answers[0]["q"],
                copy_ready_body=quora_answers[0]["a"],
                estimated_organic_installs=25,
                notes=f"建议至少回答 10 个相关问题。额外问题模板: {json.dumps(quora_answers, ensure_ascii=False)}",
            ),
            ChannelAction(
                channel="HubPages",
                category="content",
                priority="MEDIUM",
                platform_url="https://hubpages.com/my/hubs/new",
                submit_guide="发布 Hub: 'Top 10 Free Bible Apps for Android in 2026' → 把你的 app 排第一, 其余 9 个写竞品 (YouVersion, Bible Gateway 等) → 关键词优化",
                copy_ready_title=f"Top 10 Free Bible Apps for Android (2026 Edition)",
                copy_ready_body=(f"#1 {display}: Best Bible Trivia — 1000+ questions, fully offline, free forever. "
                                 f"... [然后 #2-#10 详细评测其他 9 个 App]\n\n"
                                 f"All apps reviewed (including {display}): {play_url}"),
                estimated_organic_installs=20,
                notes="HubPages 文章在 'best bible app' 搜索中排名高, 长尾流量稳定",
            ),
        ]
        return actions

    # ── 5. 视频 SEO 脚本 (Shorts / TikTok / Reels) ──

    def _build_video_seo_scripts(
        self, display: str, package: str, genre: str
    ) -> List[ChannelAction]:
        play_url = f"https://play.google.com/store/apps/details?id={package}"
        seo_hashtags = ["#biblequiz", "#bibletrivia", "#christian", "#faith",
                        "#bibleverse", "#triviagame", "#shorts", "#fyp"]

        scripts = [
            {
                "title": "10-Second Bible Challenge (Hard Mode)",
                "hook": "Can you name the book of the Bible in 5 seconds? 🧠⏱️",
                "flow": "0-3s: 展示经文截图 + 问题 'In which book is the verse found?'; "
                        "3-7s: 倒计时动画 (5-4-3-2-1); "
                        "7-10s: 揭晓答案 + 显示 {display} 游戏画面 + 文字 'Download for 1000+ challenges'",
                "cta": f"Download {display}: {play_url}",
            },
            {
                "title": "Guess the Bible Character",
                "hook": "Who Am I? 🤔 (Level: Expert)",
                "flow": "0-4s: 显示 3 条线索 (1. I was thrown into a den of lions; 2. I interpreted dreams; 3. My name starts with D); "
                        "4-8s: 观众猜; "
                        "8-10s: 答案 Daniel + 游戏画面 + CTA",
                "cta": f"Play 1000+ Bible quizzes: {play_url}",
            },
            {
                "title": "5 Bible Trivia Questions You Might Get Wrong",
                "hook": "90% of people get #3 wrong! 😱",
                "flow": "逐条问 5 个问题, 每个 2s, 最后公布答案。结尾植入游戏画面和下载链接",
                "cta": f"How many did you get right? Test yourself: {play_url}",
            },
        ]

        return [
            ChannelAction(
                channel="YouTube Shorts",
                category="video_seo",
                priority="HIGH",
                platform_url="https://studio.youtube.com/",
                submit_guide="按下方 3 个脚本拍 15-60 秒短视频 (用手机, 画面是游戏录屏 + 大字幕 + 倒计时) → 上传 Shorts → 标题/描述/标签 按 SEO 关键词填 → 每周发 3 条",
                copy_ready_title=scripts[0]["title"],
                copy_ready_body=json.dumps(scripts, ensure_ascii=False, indent=2),
                hashtags=seo_hashtags,
                estimated_organic_installs=80,
                notes="YouTube Shorts 搜索流量极大! 核心关键词 'bible quiz', 'bible trivia' 竞争比想像的小 — 先发每周 3 条, 第 4 周通常见效",
            ),
            ChannelAction(
                channel="TikTok",
                category="video_seo",
                priority="MEDIUM",
                platform_url="https://www.tiktok.com/upload",
                submit_guide="相同 3 个脚本, 改成 TikTok 版本 (加快节奏, 更强钩子, 热门音乐 bgm) → 前 3 秒必须抓住注意力",
                copy_ready_title=scripts[1]["title"],
                copy_ready_body=json.dumps(scripts, ensure_ascii=False, indent=2),
                hashtags=["#bible", "#trivia", "#christian", "#biblequiz", "#faithgame", "#fyp"],
                estimated_organic_installs=40,
                notes="适合 13-25 岁年轻基督徒群体, 拉美/东南亚用户量极大",
            ),
            ChannelAction(
                channel="Instagram Reels",
                category="video_seo",
                priority="MEDIUM",
                platform_url="https://www.instagram.com/",
                submit_guide="复用 Shorts 素材 → 加上 Instagram 专属 Stickers (Quiz/Challenge Poll) → 互动率更高",
                copy_ready_title=scripts[2]["title"],
                copy_ready_body=json.dumps(scripts, ensure_ascii=False, indent=2),
                hashtags=["#BibleQuiz", "#BibleTrivia", "#Faith", "#ChristianApp"],
                estimated_organic_installs=30,
                notes="Reels 目前算法红利期, 多发 (每天 1 条) 可获得推荐",
            ),
        ]

    # ── 6. 信仰社区 (高价值精准流量) ──

    def _build_faith_communities(
        self, display: str, package: str, genre: str
    ) -> List[ChannelAction]:
        play_url = f"https://play.google.com/store/apps/details?id={package}"
        body_church = (
            f"Dear Pastor / Leader, 👋\n\n"
            f"I'm the developer of {display}, a free Bible trivia game designed for "
            f"church groups and youth ministries. It has 1000+ questions covering "
            f"the entire Bible, works fully offline, and can be used in:\n\n"
            f"• Sunday School classes\n"
            f"• Youth group game nights\n"
            f"• Bible study warm-up activities\n"
            f"• Church retreats (no wifi needed!)\n\n"
            f"I want to offer you the Premium version for FREE if you use it in your ministry. "
            f"Just reply with your church name and approximate size, and I'll send you a code.\n\n"
            f"Google Play: {play_url}\n\n"
            f"In Christ,\n"
            f"[Your Name]\n"
            f"{display}"
        )

        return [
            ChannelAction(
                channel="Church Email Outreach",
                category="community",
                priority="HIGH",
                platform_url="https://churchfinder.com/ https://www.churchangel.com/",
                submit_guide="找美国/巴西/西语地区 100 家中小型教会 (50-500 人规模) → 发个性化邮件 (不要 BCC 群发, 每封定制一句提到他们教会名) → 赠送 Premium 兑换码",
                copy_ready_title=f"Free Bible Trivia App for Your Church (Youth Ministry Ready)",
                copy_ready_body=body_church,
                estimated_organic_installs=100,
                notes="教会用了之后: 1) 内部带来 installs; 2) 牧师/老师写 5 星评价提升 Play 权重; 3) 整个教会群体口碑传播",
            ),
            ChannelAction(
                channel="Christian Forums",
                category="community",
                priority="MEDIUM",
                platform_url="https://www.christianforums.com/ https://www.gotquestions.org/forums/",
                submit_guide="注册账号 → 参与讨论 1 周 (建立信任) → 在签名档加 App 链接 → 偶尔发布 'What Bible Quiz Apps Do You Use?' 类型话题分享",
                copy_ready_title=f"Best Bible Trivia App for Group Study?",
                copy_ready_body=(f"Hi brothers/sisters! For our small group bible study, "
                                 f"we recently started using {display} as a warm-up. It's been great! "
                                 f"Fully offline, all books covered, and the daily verses are perfect. "
                                 f"Free on Play Store: {play_url}\n\n"
                                 f"What apps do you use for your study groups?"),
                estimated_organic_installs=40,
                notes="Christian Forums 用户转化率极高 (都是真正的目标人群), 且发帖后持续有搜索流量",
            ),
        ]

    # ── 7. 交叉推广 ──

    def _build_cross_promo(
        self,
        display: str,
        package: str,
        portfolio: List[Dict[str, Any]],
        genre: str,
    ) -> List[Dict[str, Any]]:
        """Portfolio 内其他圣经/问答类游戏交叉推广方案."""
        bible_family = []
        for g in portfolio:
            gid = str(g.get("game_id") or "").lower()
            pkg = str(g.get("package_name") or "").lower()
            if any(k in gid or k in pkg for k in ("bible", "biblia", "bibbia", "quiz", "trivia", "bíblica")):
                bible_family.append(g)

        if not bible_family:
            return [{
                "note": "Portfolio 中暂无其他 bible/quiz 类游戏, 交叉推广无法立即生效。建议等其他 Bible 游戏上线后再用。",
            }]

        play_url = f"https://play.google.com/store/apps/details?id={package}"
        plan: List[Dict[str, Any]] = []
        for g in bible_family[:5]:
            partner_gid = g.get("game_id")
            partner_pkg = g.get("package_name")
            partner_play_url = f"https://play.google.com/store/apps/details?id={partner_pkg}"
            plan.append({
                "partner_game": partner_gid,
                "partner_package": partner_pkg,
                "cross_promo_copy_v1": (
                    f"If you love {partner_gid}, you'll also enjoy {display}!\n"
                    f"More bible trivia, all-new questions, fully offline.\n"
                    f"→ {play_url}"
                ),
                "cross_promo_copy_v2": (
                    f"If you love {display}, check out {partner_gid}!\n"
                    f"→ {partner_play_url}"
                ),
                "placement": "App 内启动页弹窗 + 主菜单 'More Games' 按钮 + 通关后推荐",
                "expected_lift_per_partner": "+5-15% installs",
            })
        return plan

    # ── 辅助方法 ──

    @staticmethod
    def _extract_display_name(game_id: str, package_name: str) -> str:
        """从 game_id / package_name 提取可读名称."""
        raw = package_name or game_id or "Game"
        if "." not in raw or "/" in raw:
            return raw.replace("_", " ").replace("?", " ").strip().title()
        parts = raw.split(".")
        meaningful = [p for p in parts if p.lower() not in ("com", "io", "org", "app", "games", "inc", "co")]
        last = meaningful[-1] if meaningful else parts[-1]
        # 按关键词拆
        keywords = ("bible", "quiz", "trivia", "word", "merge", "puzzle", "crossword", "spelling")
        found = [k for k in keywords if k in last.lower()]
        if found:
            return " ".join(w.title() for w in found)
        import re
        return re.sub(r'([a-z])([A-Z])', r'\1 \2', last).title()

    @staticmethod
    def _market_title(display: str, genre: str) -> str:
        """应用市场专用标题 (30-50 字符)."""
        tail = "Free Bible Trivia Game"
        if genre == "bible":
            tail = "Free Bible Trivia Quiz"
        candidate = f"{display}: {tail}"
        if len(candidate) <= 50:
            return candidate
        return f"{display} - {tail}"[:50]

    @staticmethod
    def _market_body_short(display: str, genre: str) -> str:
        """短描述 (第三方市场用)."""
        return (
            f"Play {display} - free Bible trivia game! 1000+ questions covering Old and New Testament. "
            f"Easy, Medium, Hard and Expert difficulty levels. Offline mode: no wifi required at all. "
            f"Daily Bible verse challenges. 100% free, no subscription needed."
        )

    @staticmethod
    def _market_body_long(display: str, genre: str) -> str:
        """长描述 (第三方市场用)."""
        return (
            f"# {display} - Free Bible Trivia Game\n\n"
            f"Grow your faith and test your Bible knowledge with {display}!\n\n"
            f"## Why Choose {display}?\n\n"
            f"📖 **COMPLETE BIBLE COVERAGE** — Over 1000 questions from Genesis to Revelation. "
            f"Old Testament, New Testament, Psalms, Proverbs, Gospels, Acts, Epistles, and Revelation.\n\n"
            f"🎯 **4 DIFFICULTY LEVELS** — Whether you're new to the Bible or a lifelong student, "
            f"there's a perfect level for you. Easy for beginners, Expert for pastors and scholars.\n\n"
            f"📴 **100% OFFLINE** — No wifi? No problem. Play on the bus, on a plane, during mission trips, "
            f"at church retreats, or anywhere else without an internet connection.\n\n"
            f"📅 **DAILY BIBLE VERSE** — Start each day with a new memory verse and a quick devotional quiz.\n\n"
            f"💯 **100% FREE FOREVER** — No pay-to-win, no subscriptions, no locked content.\n\n"
            f"## Perfect For:\n"
            f"• Personal Bible study & devotions\n"
            f"• Sunday School classes & youth ministry\n"
            f"• Church group game nights\n"
            f"• Family Bible time\n"
            f"• Homeschool curriculum\n\n"
            f"Download {display} now and deepen your faith, one question at a time!"
        )

    @staticmethod
    def _seo_keywords_for_genre(genre: str, display: str) -> List[str]:
        """SEO 关键词 (网页搜索)."""
        base = [
            "free bible quiz app",
            "bible trivia game",
            "best bible trivia app",
            "offline bible quiz",
            "bible quiz for android",
            "bible questions and answers",
            "bible study game",
            "christian trivia app",
            "bible knowledge test",
            "scripture quiz game",
            "daily bible app",
            "bible memory game",
        ]
        return base


# ── 单例 ──────────────────────────────────────────────────────

_engine_instance: Optional["MultiChannelOrganicEngine"] = None
_engine_lock = threading.Lock()


def get_multichannel_organic_engine() -> MultiChannelOrganicEngine:
    """获取多渠道自然量引擎单例."""
    global _engine_instance
    if _engine_instance is None:
        with _engine_lock:
            if _engine_instance is None:
                _engine_instance = MultiChannelOrganicEngine()
    return _engine_instance


__all__ = [
    "ChannelAction",
    "MultiChannelGrowthReport",
    "MultiChannelOrganicEngine",
    "get_multichannel_organic_engine",
]
