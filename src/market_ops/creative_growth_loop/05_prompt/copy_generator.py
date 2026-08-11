"""Ad Copy Generator - V15素材增长闭环
基于创意基因生成多语言广告文案：Headline / Primary Text / Description / CTA

分层决策链：
1. Game Category → 确定核心信息点
2. Country/Language → 选择语言模板
3. Audience Segment → 调整文案风格
4. Creative Hook Type → 匹配文案句式
5. Emotion → 调整文案语气
6. Reward Type → 植入利益点
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Dict, Optional

# 注意：不直接 import CreativeGene，使用 duck typing（gene.hook / gene.reward / gene.emotion）
# 原因：gene_extractor 位于 03_gene 目录，Python 不支持数字前缀模块名的 import 语句


@dataclass
class AdCopy:
    """单条广告文案集合"""
    headline: str
    primary_text: str
    description: str
    cta: str
    language: str
    hook_type: str
    emotion: str
    reward: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "headline": self.headline,
            "primary_text": self.primary_text,
            "description": self.description,
            "cta": self.cta,
            "language": self.language,
            "hook_type": self.hook_type,
            "emotion": self.emotion,
            "reward": self.reward,
        }


@dataclass
class CopyVariant:
    """文案变体集合，用于A/B测试"""
    variant_id: str
    copies: AdCopy

    def to_dict(self) -> Dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            **self.copies.to_dict(),
        }


class CopyGenerator:
    """广告文案生成器

    输入：CreativeGene + 上下文信息（游戏、国家、受众）
    输出：多条不同风格的文案变体
    """

    # 多语言模板 - CTA
    CTA_TEMPLATES = {
        "en": {
            "INSTALL_MOBILE_APP": "Install Now",
            "PLAY_NOW": "Play Now",
            "DOWNLOAD": "Download",
            "GET_STARTED": "Get Started",
            "TRY_IT": "Try It Free",
            "OPEN": "Open App",
            "BOOK_NOW": "Book Now",
            "LEARN_MORE": "Learn More",
            "SIGN_UP": "Sign Up",
        },
        "zh": {
            "INSTALL_MOBILE_APP": "立即下载",
            "PLAY_NOW": "立即游玩",
            "DOWNLOAD": "点击下载",
            "GET_STARTED": "开始体验",
            "TRY_IT": "免费试玩",
            "OPEN": "打开游戏",
            "BOOK_NOW": "立即预约",
            "LEARN_MORE": "了解详情",
            "SIGN_UP": "立即注册",
        },
        "ja": {
            "INSTALL_MOBILE_APP": "今すぐダウンロード",
            "PLAY_NOW": "今すぐプレイ",
            "DOWNLOAD": "ダウンロード",
            "GET_STARTED": "始めてみよう",
            "TRY_IT": "無料で試す",
            "OPEN": "アプリを開く",
            "BOOK_NOW": "予約する",
            "LEARN_MORE": "詳細を見る",
            "SIGN_UP": "登録する",
        },
        "ko": {
            "INSTALL_MOBILE_APP": "지금 다운로드",
            "PLAY_NOW": "지금 플레이",
            "DOWNLOAD": "다운로드",
            "GET_STARTED": "시작하기",
            "TRY_IT": "무료 체험",
            "OPEN": "앱 열기",
            "BOOK_NOW": "예약하기",
            "LEARN_MORE": "자세히 보기",
            "SIGN_UP": "가입하기",
        },
        "es": {
            "INSTALL_MOBILE_APP": "Instalar Ahora",
            "PLAY_NOW": "Juega Ahora",
            "DOWNLOAD": "Descargar",
            "GET_STARTED": "Empezar",
            "TRY_IT": "Prueba Gratis",
            "OPEN": "Abrir App",
            "BOOK_NOW": "Reservar",
            "LEARN_MORE": "Más Información",
            "SIGN_UP": "Registrarse",
        },
    }

    # Hook类型 → Headline模板
    HOOK_HEADLINE_TEMPLATES = {
        "secret": {
            "en": [
                "The secret that nobody tells you",
                "Did you know this trick?",
                "This hidden trick changed everything",
                "Nobody wants you to know this",
            ],
            "zh": [
                "这个秘密没人告诉你",
                "你知道这个技巧吗？",
                "这个隐藏技巧改变了一切",
                "大佬都不愿说的秘诀",
            ],
            "ja": [
                "誰も教えてくれない秘密",
                "このテクニック知ってる？",
                "この裏技で全てが変わった",
                "誰も教えたがらないこと",
            ],
        },
        "challenge": {
            "en": [
                "Can you beat this level?",
                "Only 1% can pass this",
                "I bet you can't",
                "Challenge accepted?",
            ],
            "zh": [
                "你能闯过这关吗？",
                "只有1%的人能通关",
                "我打赌你过不了",
                "敢接受挑战吗？",
            ],
            "ja": [
                "このレベルクリアできる？",
                "1%の人しかクリアできない",
                "絶対クリアできないと思う",
                "チャレンジ受け入れる？",
            ],
        },
        "warning": {
            "en": [
                "Stop playing before you see this",
                "Don't play this game if...",
                "Warning: this is addicting",
                "Don't download if you hate fun",
            ],
            "zh": [
                "玩之前一定要看这个",
                "如果...别玩这个游戏",
                "警告：太上头了",
                "怕上瘾别下载",
            ],
            "ja": [
                "これを見るまでプレイするな",
                "こんな人はこのゲームをするな",
                "警告：中毒性があります",
                "楽しいのが嫌いならダウンロードするな",
            ],
        },
        "wrong_choice": {
            "en": [
                "Most people pick the wrong one",
                "Which would you choose?",
                "Did you make the right choice?",
                "Everyone picks this wrong",
            ],
            "zh": [
                "大多数人选错了",
                "你选哪一个？",
                "你选对了吗？",
                "人人都选错",
            ],
            "ja": [
                "ほとんどの人が間違える",
                "あなたはどっちを選ぶ？",
                "正しい選択できましたか？",
                "みんなこれを間違える",
            ],
        },
        "before_after": {
            "en": [
                "Before vs After - Amazing",
                "Look what happened after",
                "This is what changed",
                "You won't believe the difference",
            ],
            "zh": [
                "前后对比太神奇了",
                "看看之后发生了什么",
                "这就是改变后的样子",
                "你不会相信这个差别",
            ],
            "ja": [
                "ビフォーアフター - 驚き",
                "その後何が起こったか見て",
                "これが変わったところ",
                "違いに驚くはず",
            ],
        },
        "reward": {
            "en": [
                "Claim your free reward now",
                "Get {reward} for free",
                "Free {reward} inside",
                "Unlock your legendary {reward}",
            ],
            "zh": [
                "立即领取免费奖励",
                "免费获取{reward}",
                "内含免费{reward}",
                "解锁你的传奇{reward}",
            ],
            "ja": [
                "今すぐ無料報酬を受け取れ",
                "{reward}が無料で手に入る",
                "中に無料の{reward}",
                "伝説の{reward}をアンロック",
            ],
        },
        "curiosity": {
            "en": [
                "What's hidden in this game?",
                "Guess what happens next",
                "You'll never guess",
                "Something unexpected happens",
            ],
            "zh": [
                "游戏里藏着什么？",
                "猜猜接下来发生什么",
                "你绝对猜不到",
                "发生了意想不到的事",
            ],
            "ja": [
                "このゲームに何が隠れてる？",
                "次に何が起こるか当てて",
                "絶対当てられない",
                "予想外のことが起こる",
            ],
        },
        "urgency": {
            "en": [
                "Limited time offer inside",
                "Only available for 48 hours",
                "Don't miss out",
                "Offer ends soon",
            ],
            "zh": [
                "限时活动进行中",
                "仅48小时有效",
                "不要错过",
                "活动即将结束",
            ],
            "ja": [
                "期間限定オファー",
                "48時間限定",
                "見逃すな",
                "まもなく終了",
            ],
        },
        "social": {
            "en": [
                "10M players are playing now",
                "Everyone is talking about this",
                "Join millions of players",
                "Your friends are playing this",
            ],
            "zh": [
                "千万玩家正在玩",
                "人人都在讨论这个",
                "加入数百万玩家行列",
                "你的朋友都在玩",
            ],
            "ja": [
                "1000万人が今プレイ中",
                "みんなこれを話題にしてる",
                "何百万人ものプレイヤーに参加",
                "友達もみんなプレイしてる",
            ],
        },
        "achievement": {
            "en": [
                "Become a legend now",
                "Unlock all achievements",
                "Beat the hardest level",
                "Reach the top rank",
            ],
            "zh": [
                "现在成为传奇",
                "解锁所有成就",
                "通关最难关卡",
                "冲上第一名",
            ],
            "ja": [
                "今すぐレジェンドになろう",
                "全実績解除",
                "最難関をクリア",
                "トップランクに到達",
            ],
        },
    }

    # 情绪 → Primary Text 风格
    EMOTION_PRIMARY_TEXT = {
        "surprise": {
            "en": "You won't believe what you're missing. This game has a hidden surprise waiting for you!",
            "zh": "你绝对想不到这里藏着什么。这个游戏有一个惊喜在等你发现！",
            "ja": "あなたが何を逃しているか信じられないでしょう。このゲームには隠されたサプライズが待っています！",
        },
        "excited": {
            "en": "Get ready for the most addictive game you've played all year! Non-stop fun and excitement awaits.",
            "zh": "准备好迎接全年最上头的游戏！停不下来的乐趣和刺激等着你。",
            "ja": "今年一番中毒性のあるゲームの準備をしよう！ノンストップの楽しさと興奮が待っています。",
        },
        "happy": {
            "en": "Fun for all ages! Relax and enjoy this beautiful game anytime, anywhere.",
            "zh": "全年龄段都能玩！随时随地放松享受这款精美的游戏。",
            "ja": "全年代楽しめる！いつでもどこでもリラックスしてこの美しいゲームを楽しめる。",
        },
        "panic": {
            "en": "Things are getting intense! Can you keep up with the action? Prove you have what it takes.",
            "zh": "局势越来越紧张！你能跟上节奏吗？证明你的实力。",
            "ja": "状況はどんどん激しくなる！アクションについていける？実力を証明しよう。",
        },
        "wow": {
            "en": "This is absolutely amazing! The graphics, the gameplay, everything just works perfectly. Download now and see for yourself.",
            "zh": "这太不可思议了！画质、玩法，一切都完美运行。现在下载亲自体验。",
            "ja": "これは本当にすごい！グラフィックもゲームプレイも、全てが完璧。今すぐダウンロードして自分で確かめよう。",
        },
        "curious": {
            "en": "There's more to this game than meets the eye. Discover hidden secrets and unlock amazing rewards.",
            "zh": "这款游戏比看上去更有内涵。发现隐藏秘密，解锁惊人奖励。",
            "ja": "このゲームには見た目以上のものがある。隠された秘密を発見して、驚くべき報酬をアンロックしよう。",
        },
        "mysterious": {
            "en": "Dark secrets lurk in every corner. Can you solve the mystery and uncover the truth?",
            "zh": "每个角落都隐藏着黑暗秘密。你能解开谜团，发现真相吗？",
            "ja": "闇の秘密があらゆる隅に潜んでいる。謎を解き明かして真実を暴けるか？",
        },
    }

    # Game Category 通用模板
    GAME_CATEGORY_DESCRIPTION = {
        "puzzle": {
            "en": "Exercise your brain with challenging puzzles. Easy to learn, hard to master. Can you solve them all?",
            "zh": "用烧脑谜题锻炼脑力。易学难精，你能全通关吗？",
            "ja": "難しいパズルで脳を鍛えよう。簡単に学べて、マスターは難しい。全部解けるかな？",
        },
        "rpg": {
            "en": "Embark on an epic adventure! Collect powerful items, defeat tough enemies, and become the hero of the realm.",
            "zh": "踏上史诗冒险！收集强力装备，击败强大敌人，成为这片大陆的英雄。",
            "ja": "壮大な冒険に出発！強力なアイテムを集め、手強い敵を倒し、王国の英雄になろう。",
        },
        "casual": {
            "en": "Perfect for killing time! Play in short sessions anytime, anywhere. No pressure, just fun.",
            "zh": "杀时间神器！随时随地短局游玩，没有压力，只有乐趣。",
            "ja": "暇つぶしに最適！いつでもどこでも短時間プレイ。プレッシャーなしで、ただ楽しい。",
        },
        "strategy": {
            "en": "Think carefully and outsmart your opponents. Plan your moves wisely and claim victory. Are you smart enough?",
            "zh": "深思熟虑，智胜对手。精心规划每一步，夺取胜利。你够聪明吗？",
            "ja": "よく考えて対戦相手を出し抜こう。賢く手を計画して勝利を掴め。あなたは十分頭がいい？",
        },
        "hyper_casual": {
            "en": "One tap gameplay, instant fun. No complicated controls, just relax and enjoy. Perfect for a quick break.",
            "zh": "一键操作，即刻开玩。没有复杂操控，放松享受就好。小憩一下的完美选择。",
            "ja": "ワンタッププレイ、即楽しめる。複雑な操作なし、ただリラックスして楽しめる。ちょっとした休憩に最適。",
        },
        "match3": {
            "en": "Match-3 fun with thousands of levels. New puzzles every week, never get bored. Swap and match your way to victory!",
            "zh": "三消乐趣，数千关卡。每周更新新谜题，永远不会无聊。交换匹配，通往胜利！",
            "ja": "マッチ3の楽しさ、数千レベル。毎週新しいパズル、飽きることなし。スワップしてマッチして勝利へ！",
        },
        "simulation": {
            "en": "Build your dream world from scratch. Manage resources, expand your territory, and create something amazing.",
            "zh": "从零开始建造你的梦想世界。管理资源，扩张领土，创造奇迹。",
            "ja": "ゼロから夢の世界を建てよう。資源を管理し、領土を拡大し、素晴らしいものを作ろう。",
        },
        "action": {
            "en": "Non-stop action! Fast-paced gameplay that keeps you on the edge of your seat. Can you handle the heat?",
            "zh": "停不下来的动作体验！快节奏玩法让你肾上腺素飙升。你能应对吗？",
            "ja": "ノンストップアクション！ペースの速いゲームプレイで席の端に座りっぱなし。この熱さに耐えられる？",
        },
    }

    # 受众人群 → 风格调整
    AUDIENCE_ADJUSTMENT = {
        "casual": {
            "en": "Great for players of all skill levels",
            "zh": "适合所有水平的玩家",
            "ja": "全レベルのプレイヤーに最適",
        },
        "hardcore": {
            "en": "For true gamers who love a challenge",
            "zh": "专为喜欢挑战的真玩家",
            "ja": "チャレンジが好きな真のゲーマーのため",
        },
        "f2p": {
            "en": "Free to play, download now!",
            "zh": "免费游玩，现在下载！",
            "ja": "無料プレイ、今すぐダウンロード！",
        },
        "midcore": {
            "en": "The perfect balance of fun and challenge",
            "zh": "乐趣与挑战的完美平衡",
            "ja": "楽しさとチャレンジの完璧なバランス",
        },
    }

    # Reward 翻译/描述
    REWARD_NAMES = {
        "gold_dragon": {
            "en": "Golden Dragon",
            "zh": "金龙",
            "ja": "ゴールデンドラゴン",
        },
        "castle": {
            "en": "Castle",
            "zh": "城堡",
            "ja": "城",
        },
        "treasure": {
            "en": "Treasure",
            "zh": "宝藏",
            "ja": "宝物",
        },
        "diamond": {
            "en": "Diamond",
            "zh": "钻石",
            "ja": "ダイヤモンド",
        },
        "phoenix": {
            "en": "Phoenix",
            "zh": "凤凰",
            "ja": "フェニックス",
        },
        "unicorn": {
            "en": "Unicorn",
            "zh": "独角兽",
            "ja": "ユニコーン",
        },
        "golden_tree": {
            "en": "Golden Tree",
            "zh": "黄金树",
            "ja": "ゴールデンツリー",
        },
        "magic_item": {
            "en": "Magic Item",
            "zh": "魔法物品",
            "ja": "魔法のアイテム",
        },
        "legendary": {
            "en": "Legendary Item",
            "zh": "传奇装备",
            "ja": "レジェンダリーアイテム",
        },
        "rare": {
            "en": "Rare Item",
            "zh": "稀有物品",
            "ja": "レアアイテム",
        },
        "unknown": {
            "en": "Amazing Reward",
            "zh": "惊人奖励",
            "ja": "驚きの報酬",
        },
    }

    def __init__(self, output_dir: str = "output/creative_growth_loop/copy"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def get_language_for_country(self, country: str) -> str:
        """根据国家推断主要语言"""
        country_lang_map = {
            # Chinese speaking
            "CN": "zh", "HK": "zh", "TW": "zh", "SG": "zh",
            # Japanese
            "JP": "ja",
            # Korean
            "KR": "ko",
            # Spanish
            "ES": "es", "MX": "es", "AR": "es", "CO": "es", "CL": "es", "PE": "es",
            # Default to English
        }
        return country_lang_map.get(country.upper(), "en")

    def _get_reward_name(self, reward: str, language: str) -> str:
        """获取Reward在目标语言中的名称"""
        if reward in self.REWARD_NAMES:
            return self.REWARD_NAMES[reward].get(language, self.REWARD_NAMES[reward]["en"])
        return self.REWARD_NAMES["unknown"].get(language, self.REWARD_NAMES["unknown"]["en"])

    def _random_template(self, hook_type: str, language: str, reward: str) -> str:
        """随机选择一个Headline模板，并替换Reward占位符"""
        reward_name = self._get_reward_name(reward, language)

        # Get templates for this hook type and language
        if hook_type in self.HOOK_HEADLINE_TEMPLATES:
            templates = self.HOOK_HEADLINE_TEMPLATES[hook_type].get(language)
            if not templates:
                templates = self.HOOK_HEADLINE_TEMPLATES[hook_type].get("en", ["Play Now"])
        else:
            # Default templates
            templates = self.HOOK_HEADLINE_TEMPLATES["curiosity"][language] if language in self.HOOK_HEADLINE_TEMPLATES["curiosity"] else self.HOOK_HEADLINE_TEMPLATES["curiosity"]["en"]

        template = random.choice(templates)
        return template.replace("{reward}", reward_name)

    def generate_ad_copy(
        self,
        gene: Any,
        game_category: str = "casual",
        country: str = "US",
        audience: str = "casual",
        cta_type: str = "INSTALL_MOBILE_APP",
    ) -> AdCopy:
        """根据基因和上下文生成单条广告文案

        Args:
            gene: 创意基因（具有 hook, reward, emotion 属性的对象）
            game_category: 游戏类型 (puzzle, rpg, casual, strategy, hyper_casual, match3, simulation, action)
            country: 投放国家（用于语言选择）
            audience: 受众类型 (casual, hardcore, f2p, midcore)
            cta_type: CTA类型

        Returns:
            AdCopy 生成的文案
        """
        language = self.get_language_for_country(country)

        # 1. Headline from Hook + Emotion + Reward
        headline = self._random_template(gene.hook, language, gene.reward)

        # 2. Primary Text from Emotion + Audience
        if gene.emotion in self.EMOTION_PRIMARY_TEXT:
            primary_base = self.EMOTION_PRIMARY_TEXT[gene.emotion].get(
                language, self.EMOTION_PRIMARY_TEXT[gene.emotion].get("en", "")
            )
        else:
            primary_base = self.EMOTION_PRIMARY_TEXT["curious"].get(
                language, self.EMOTION_PRIMARY_TEXT["curious"]["en"]
            )

        # Add audience adjustment
        if audience in self.AUDIENCE_ADJUSTMENT:
            audience_note = self.AUDIENCE_ADJUSTMENT[audience].get(
                language, self.AUDIENCE_ADJUSTMENT[audience]["en"]
            )
            primary_text = f"{primary_base} {audience_note}"
        else:
            primary_text = primary_base

        # 3. Description from Game Category
        if game_category in self.GAME_CATEGORY_DESCRIPTION:
            description = self.GAME_CATEGORY_DESCRIPTION[game_category].get(
                language, self.GAME_CATEGORY_DESCRIPTION[game_category].get("en", "")
            )
        else:
            description = self.GAME_CATEGORY_DESCRIPTION["casual"].get(
                language, self.GAME_CATEGORY_DESCRIPTION["casual"]["en"]
            )

        # 4. CTA
        if cta_type in self.CTA_TEMPLATES.get(language, {}):
            cta = self.CTA_TEMPLATES[language][cta_type]
        elif cta_type in self.CTA_TEMPLATES["en"]:
            cta = self.CTA_TEMPLATES["en"][cta_type]
        else:
            cta = self.CTA_TEMPLATES["en"]["INSTALL_MOBILE_APP"]

        return AdCopy(
            headline=headline,
            primary_text=primary_text,
            description=description,
            cta=cta,
            language=language,
            hook_type=gene.hook,
            emotion=gene.emotion,
            reward=gene.reward,
        )

    def generate_variants(
        self,
        gene: Any,
        game_category: str = "casual",
        country: str = "US",
        audience: str = "casual",
        count: int = 5,
    ) -> List[CopyVariant]:
        """生成多个文案变体，用于A/B测试

        Args:
            gene: 创意基因
            game_category: 游戏类型
            country: 投放国家
            audience: 受众类型
            count: 生成多少个变体

        Returns:
            文案变体列表
        """
        variants: List[CopyVariant] = []

        # 不同变体用不同的CTA类型随机化
        cta_options = [
            "INSTALL_MOBILE_APP",
            "PLAY_NOW",
            "DOWNLOAD",
            "GET_STARTED",
            "TRY_IT",
        ]

        for i in range(count):
            cta_type = cta_options[i % len(cta_options)]
            ad_copy = self.generate_ad_copy(
                gene=gene,
                game_category=game_category,
                country=country,
                audience=audience,
                cta_type=cta_type,
            )
            variant = CopyVariant(
                variant_id=f"copy_{i:03d}",
                copies=ad_copy,
            )
            variants.append(variant)

        return variants

    def generate_multi_language(
        self,
        gene: Any,
        game_category: str,
        countries: List[str],
        audience: str = "casual",
    ) -> Dict[str, AdCopy]:
        """为多个国家生成对应语言的文案

        Args:
            gene: 创意基因
            game_category: 游戏类型
            countries: 国家列表
            audience: 受众

        Returns:
            {country: AdCopy} 字典
        """
        result: Dict[str, AdCopy] = {}
        for country in countries:
            copy = self.generate_ad_copy(gene, game_category, country, audience)
            result[country] = copy
        return result

    def save_variants(self, variants: List[CopyVariant], run_id: str = None) -> Path:
        """保存生成的文案变体到文件"""
        from datetime import datetime
        if run_id is None:
            run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        filename = f"copy_variants_{run_id}.json"
        output_path = self.output_dir / filename

        data = [v.to_dict() for v in variants]
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return output_path

    def extract_headlines(self, variants: List[CopyVariant]) -> List[str]:
        """提取所有Headline，供Facebook发布使用"""
        return [v.copies.headline for v in variants]

    def extract_primary_texts(self, variants: List[CopyVariant]) -> List[str]:
        """提取所有Primary Text，供Facebook发布使用"""
        return [v.copies.primary_text for v in variants]

    def extract_descriptions(self, variants: List[CopyVariant]) -> List[str]:
        """提取所有Description，供Facebook发布使用"""
        return [v.copies.description for v in variants]

    def extract_ctas(self, variants: List[CopyVariant]) -> List[str]:
        """提取所有CTA类型，供Facebook发布使用"""
        return [v.copies.cta for v in variants]
