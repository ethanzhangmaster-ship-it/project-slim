"""Campaign Strategy - Campaign/AdSet 创建策略决策

策略决策层：
1. 根据 预算/目标/复杂度 → 选择 ABO / CBO / ASC
2. 根据 Game/Country → 构建 Targeting（国家/年龄/兴趣/Lookalike/Broad）
3. 根据 Optimization Goal → 选择 Placement / Optimization Event / Attribution
4. 根据 Budget → 设置 Bid Strategy / Cost Cap / Bid Cap

输出：CampaignConfig + AdSetConfig，可直接传给 FacebookPublisher
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class CampaignBuyingType(str, Enum):
    AUCTION = "AUCTION"
    RESERVED = "RESERVED"


class CampaignObjective(str, Enum):
    APP_INSTALLS = "APP_INSTALLS"
    CONVERSIONS = "CONVERSIONS"
    LINK_CLICKS = "LINK_CLICKS"
    BRAND_AWARENESS = "BRAND_AWARENESS"
    REACH = "REACH"
    VIDEO_VIEWS = "VIDEO_VIEWS"
    ENGAGEMENT = "ENGAGEMENT"


class CampaignStrategy(str, Enum):
    """投放策略类型"""
    ABO = "ABO"  # Ad Set Budget Optimization
    CBO = "CBO"  # Campaign Budget Optimization
    ASC = "ASC"  # Advantage+ Shopping Campaign


class OptimizationGoal(str, Enum):
    APP_INSTALLS = "APP_INSTALLS"
    IMPRESSIONS = "IMPRESSIONS"
    LINK_CLICKS = "LINK_CLICKS"
    VALUE = "VALUE"
    REACH = "REACH"
    CONVERSIONS = "CONVERSIONS"


class BillingEvent(str, Enum):
    IMPRESSIONS = "IMPRESSIONS"
    LINK_CLICKS = "LINK_CLICKS"
    APP_INSTALLS = "APP_INSTALLS"


class BidStrategy(str, Enum):
    LOWEST_COST_WITHOUT_CAP = "LOWEST_COST_WITHOUT_CAP"
    LOWEST_COST_WITH_BID_CAP = "LOWEST_COST_WITH_BID_CAP"
    COST_CAP = "COST_CAP"


class AdSetStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"


# ---------------------------------------------------------------------------
# Config Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class CampaignConfig:
    """Campaign 创建配置"""
    name: str
    objective: CampaignObjective = CampaignObjective.APP_INSTALLS
    buying_type: CampaignBuyingType = CampaignBuyingType.AUCTION
    status: str = "PAUSED"
    special_ad_categories: List[str] = field(default_factory=list)
    strategy: CampaignStrategy = CampaignStrategy.ABO

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "objective": self.objective.value,
            "buying_type": self.buying_type.value,
            "status": self.status,
            "special_ad_categories": self.special_ad_categories,
            "strategy": self.strategy.value,
        }


@dataclass
class TargetingConfig:
    """广告定向配置"""
    # Geo
    countries: List[str] = field(default_factory=list)
    # Demo
    age_min: int = 18
    age_max: int = 65
    genders: List[int] = field(default_factory=lambda: [1, 2])  # 1=男, 2=女
    languages: List[str] = field(default_factory=list)
    # Interests
    interests: List[Dict] = field(default_factory=list)  # [{"id": "xxx", "name": "yyy"}]
    # Behaviors
    behaviors: List[Dict] = field(default_factory=list)
    # Custom Audiences
    custom_audiences: List[Dict] = field(default_factory=list)
    # Lookalike
    lookalike_audiences: List[Dict] = field(default_factory=list)
    # Exclusions
    excluded_custom_audiences: List[Dict] = field(default_factory=list)
    # Broad targeting
    is_broad: bool = False

    def to_facebook_spec(self) -> Dict:
        """转换为 Facebook API 所需的 targeting 格式"""
        spec: Dict = {
            "geo_locations": {
                "countries": [c.upper() for c in self.countries],
            },
            "age_min": self.age_min,
            "age_max": self.age_max,
        }

        if self.genders:
            spec["genders"] = self.genders

        if self.languages:
            spec["locales"] = self.languages

        if self.interests:
            spec["interests"] = [{"id": i["id"], "name": i["name"]} for i in self.interests]

        if self.behaviors:
            spec["behaviors"] = self.behaviors

        if self.custom_audiences:
            audience_ids = [{"id": a["id"]} for a in self.custom_audiences]
            spec["custom_audiences"] = audience_ids

        if self.lookalike_audiences:
            spec["flexible_spec"] = [
                {"lookalike_spec": {"id": la["id"]}} for la in self.lookalike_audiences
            ]

        if self.excluded_custom_audiences:
            spec["excluded_custom_audiences"] = [
                {"id": a["id"]} for a in self.excluded_custom_audiences
            ]

        return spec


@dataclass
class AdSetConfig:
    """Ad Set 创建配置"""
    name: str
    campaign_id: str = ""
    # Budget
    daily_budget: int = 0  # 单位：分（Facebook 最小单位）
    lifetime_budget: int = 0
    # Optimization
    optimization_goal: OptimizationGoal = OptimizationGoal.APP_INSTALLS
    billing_event: BillingEvent = BillingEvent.IMPRESSIONS
    bid_strategy: BidStrategy = BidStrategy.LOWEST_COST_WITHOUT_CAP
    bid_amount: Optional[int] = None  # 单位：分
    # Targeting
    targeting: TargetingConfig = field(default_factory=TargetingConfig)
    # Placements
    placements: List[str] = field(default_factory=lambda: [
        "facebook_feed",
        "instagram_feed",
        "instagram_stories",
        "facebook_video_feeds",
        "facebook_reels",
        "instagram_reels",
    ])
    # Attribution
    attribution_spec: Optional[List[Dict]] = None  # [{"event_type": "CLICK_THROUGH", "window_days": 7}]
    # Optimization
    optimization_sub_event: Optional[str] = None  # 如 "APP_INSTALL" 或 "PURCHASE"
    # Status
    status: str = "PAUSED"
    # Learning
    is_dynamic_creative: bool = False

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "campaign_id": self.campaign_id,
            "daily_budget": self.daily_budget,
            "lifetime_budget": self.lifetime_budget,
            "optimization_goal": self.optimization_goal.value,
            "billing_event": self.billing_event.value,
            "bid_strategy": self.bid_strategy.value,
            "bid_amount": self.bid_amount,
            "targeting": self.targeting.to_facebook_spec(),
            "placements": self.placements,
            "attribution_spec": self.attribution_spec,
            "optimization_sub_event": self.optimization_sub_event,
            "status": self.status,
            "is_dynamic_creative": self.is_dynamic_creative,
        }


# ---------------------------------------------------------------------------
# Strategy Builder
# ---------------------------------------------------------------------------

class CampaignStrategyBuilder:
    """Campaign/AdSet 策略构建器

    根据输入参数自动决策：
    - ABO / CBO / ASC 选择
    - Targeting 构建
    - Budget 策略
    """

    # 国家 → 语言的默认映射
    COUNTRY_LANGUAGE_MAP = {
        "CN": ["zh_CN"],
        "HK": ["zh_HK"],
        "TW": ["zh_TW"],
        "JP": ["ja_JP"],
        "KR": ["ko_KR"],
        "US": ["en_US"],
        "GB": ["en_GB"],
        "CA": ["en_US", "fr_CA"],
        "AU": ["en_AU"],
        "DE": ["de_DE"],
        "FR": ["fr_FR"],
        "ES": ["es_ES"],
        "MX": ["es_LA"],
        "AR": ["es_LA"],
        "BR": ["pt_BR"],
        "IT": ["it_IT"],
        "RU": ["ru_RU"],
        "IN": ["en_IN", "hi_IN"],
        "ID": ["id_ID"],
        "TH": ["th_TH"],
        "VN": ["vi_VN"],
        "PH": ["en_PH", "tl_PH"],
        "SA": ["ar_SA"],
        "AE": ["ar_AR", "en_US"],
        "TR": ["tr_TR"],
    }

    # 游戏类型 → 兴趣推荐
    GAME_INTEREST_KEYWORDS = {
        "puzzle": ["Puzzle video game", "Brain teaser", "Logic puzzle"],
        "rpg": ["Role-playing video game", "Fantasy", "Dungeon game"],
        "casual": ["Casual game", "Mobile game", "Arcade game"],
        "strategy": ["Strategy video game", "Tower defense", "Real-time strategy"],
        "hyper_casual": ["Hyper-casual game", "Clicker game", "Idle game"],
        "match3": ["Match-3 game", "Tile-matching video game", "Candy Crush"],
        "simulation": ["Simulation video game", "Virtual world", "Life simulation game"],
        "action": ["Action game", "Fighting game", "Shooter game"],
    }

    def __init__(self):
        pass

    # ------------------------------------------------------------------
    # Campaign 策略选择
    # ------------------------------------------------------------------

    def select_campaign_strategy(
        self,
        budget: float,
        adset_count: int,
        use_advantage_plus: bool = False,
    ) -> CampaignStrategy:
        """根据预算和广告组数量选择投放策略

        决策逻辑：
        - budget >= $500/day AND adset_count >= 3 → CBO
        - use_advantage_plus == True → ASC
        - 默认 → ABO
        """
        if use_advantage_plus:
            return CampaignStrategy.ASC
        if budget >= 500 and adset_count >= 3:
            return CampaignStrategy.CBO
        return CampaignStrategy.ABO

    # ------------------------------------------------------------------
    # Targeting 构建
    # ------------------------------------------------------------------

    def build_targeting(
        self,
        countries: List[str],
        game_category: str = "casual",
        age_min: int = 18,
        age_max: int = 65,
        is_broad: bool = False,
        custom_audience_ids: Optional[List[str]] = None,
        lookalike_audience_ids: Optional[List[str]] = None,
        exclude_audience_ids: Optional[List[str]] = None,
    ) -> TargetingConfig:
        """构建 TargetingConfig

        Args:
            countries: 国家代码列表
            game_category: 游戏类型
            age_min: 最小年龄
            age_max: 最大年龄
            is_broad: 是否广撒网（不设兴趣限制）
            custom_audience_ids: 自定义受众ID列表
            lookalike_audience_ids: Lookalike受众ID列表
            exclude_audience_ids: 排除受众ID列表

        Returns:
            TargetingConfig
        """
        # 语言推断
        languages: List[str] = []
        for country in countries:
            langs = self.COUNTRY_LANGUAGE_MAP.get(country.upper(), ["en_US"])
            for lang in langs:
                if lang not in languages:
                    languages.append(lang)

        # 兴趣（非Broad时）
        interests: List[Dict] = []
        if not is_broad and game_category in self.GAME_INTEREST_KEYWORDS:
            for kw in self.GAME_INTEREST_KEYWORDS[game_category]:
                interests.append({"id": "", "name": kw})

        # 自定义受众
        custom_audiences: List[Dict] = []
        if custom_audience_ids:
            custom_audiences = [{"id": aid} for aid in custom_audience_ids]

        lookalike_audiences: List[Dict] = []
        if lookalike_audience_ids:
            lookalike_audiences = [{"id": aid} for aid in lookalike_audience_ids]

        excluded: List[Dict] = []
        if exclude_audience_ids:
            excluded = [{"id": aid} for aid in exclude_audience_ids]

        return TargetingConfig(
            countries=countries,
            age_min=age_min,
            age_max=age_max,
            languages=languages,
            interests=interests,
            custom_audiences=custom_audiences,
            lookalike_audiences=lookalike_audiences,
            excluded_custom_audiences=excluded,
            is_broad=is_broad,
        )

    # ------------------------------------------------------------------
    # Budget 策略
    # ------------------------------------------------------------------

    def select_bid_strategy(
        self,
        daily_budget: float,
        target_cpi: Optional[float] = None,
        target_roas: Optional[float] = None,
    ) -> tuple[BidStrategy, Optional[int], Optional[int]]:
        """选择出价策略

        决策逻辑：
        - 有 target_cpi → COST_CAP (设置 cost_cap = target_cpi)
        - 有 bid 上限 → LOWEST_COST_WITH_BID_CAP
        - 默认 → LOWEST_COST_WITHOUT_CAP

        Returns:
            (BidStrategy, bid_amount, cost_cap)
        """
        if target_cpi is not None and target_cpi > 0:
            # COST_CAP: 以目标CPI为上限
            return BidStrategy.COST_CAP, None, int(target_cpi * 100)
        return BidStrategy.LOWEST_COST_WITHOUT_CAP, None, None

    # ------------------------------------------------------------------
    # Placement 选择
    # ------------------------------------------------------------------

    def select_placements(
        self,
        game_category: str,
        use_automatic_placements: bool = True,
    ) -> List[str]:
        """选择广告版位

        Facebook 建议启用自动版位，但可以手动控制。
        """
        if use_automatic_placements:
            return []  # 空列表表示自动版位

        # 手动版位（游戏行业常用）
        placements = [
            "facebook_feed",
            "facebook_video_feeds",
            "facebook_reels",
            "instagram_feed",
            "instagram_stories",
            "instagram_reels",
        ]

        # 超休闲游戏加 Audience Network
        if game_category in ("hyper_casual", "casual"):
            placements.extend([
                "audience_network_rewarded_video",
                "audience_network_native",
            ])

        return placements

    # ------------------------------------------------------------------
    # 完整 Campaign + AdSet 构建
    # ------------------------------------------------------------------

    def build_campaign(
        self,
        name: str,
        objective: CampaignObjective = CampaignObjective.APP_INSTALLS,
        strategy: CampaignStrategy = CampaignStrategy.ABO,
        status: str = "PAUSED",
    ) -> CampaignConfig:
        """构建 CampaignConfig"""
        return CampaignConfig(
            name=name,
            objective=objective,
            strategy=strategy,
            status=status,
        )

    def build_adset(
        self,
        name: str,
        campaign_id: str,
        daily_budget: float,
        countries: List[str],
        game_category: str = "casual",
        optimization_goal: OptimizationGoal = OptimizationGoal.APP_INSTALLS,
        is_broad: bool = False,
        target_cpi: Optional[float] = None,
        custom_audience_ids: Optional[List[str]] = None,
        lookalike_audience_ids: Optional[List[str]] = None,
        bid_strategy: Optional[BidStrategy] = None,
        status: str = "PAUSED",
    ) -> AdSetConfig:
        """构建 AdSetConfig（一站式）

        Args:
            name: AdSet 名称
            campaign_id: 关联的 Campaign ID
            daily_budget: 日预算（美元）
            countries: 目标国家
            game_category: 游戏类型
            optimization_goal: 优化目标
            is_broad: 是否广撒网
            target_cpi: 目标CPI（美元）
            custom_audience_ids: 自定义受众ID
            lookalike_audience_ids: Lookalike受众ID
            bid_strategy: 出价策略（不传则自动选择）
            status: 状态

        Returns:
            AdSetConfig
        """
        targeting = self.build_targeting(
            countries=countries,
            game_category=game_category,
            is_broad=is_broad,
            custom_audience_ids=custom_audience_ids,
            lookalike_audience_ids=lookalike_audience_ids,
        )

        placements = self.select_placements(game_category, use_automatic_placements=True)

        if bid_strategy is None:
            bid_strategy, bid_amount, _ = self.select_bid_strategy(
                daily_budget=daily_budget,
                target_cpi=target_cpi,
            )
        else:
            bid_amount = None

        # 默认 attribution: 7天点击 + 1天浏览
        attribution_spec = [
            {"event_type": "CLICK_THROUGH", "window_days": 7},
            {"event_type": "VIEW_THROUGH", "window_days": 1},
        ]

        return AdSetConfig(
            name=name,
            campaign_id=campaign_id,
            daily_budget=int(daily_budget * 100),  # 美元 → 分
            optimization_goal=optimization_goal,
            billing_event=BillingEvent.IMPRESSIONS,
            bid_strategy=bid_strategy,
            bid_amount=bid_amount,
            targeting=targeting,
            placements=placements,
            attribution_spec=attribution_spec,
            status=status,
        )

    def build_full_campaign(
        self,
        project_name: str,
        daily_budget: float,
        countries: List[str],
        game_category: str = "casual",
        adset_count: int = 1,
        is_broad: bool = False,
        target_cpi: Optional[float] = None,
        use_advantage_plus: bool = False,
        custom_audience_ids: Optional[List[str]] = None,
        lookalike_audience_ids: Optional[List[str]] = None,
    ) -> Dict:
        """构建完整的 Campaign + AdSet 配置

        返回一个可直接传给 FacebookPublisher 的完整配置字典。

        Returns:
            {
                "campaign": CampaignConfig,
                "adsets": [AdSetConfig, ...],
            }
        """
        strategy = self.select_campaign_strategy(
            budget=daily_budget,
            adset_count=adset_count,
            use_advantage_plus=use_advantage_plus,
        )

        campaign = self.build_campaign(
            name=f"{project_name}_Auto_{strategy.value}",
            strategy=strategy,
        )

        # 每个国家一个 AdSet（如果 ABO）
        # CBO 下也按国家拆分 AdSet
        adsets: List[AdSetConfig] = []
        if strategy == CampaignStrategy.ABO:
            for country in countries:
                country_budget = daily_budget / max(len(countries), 1)
                adset = self.build_adset(
                    name=f"{project_name}_{country}_{game_category}",
                    campaign_id="",  # 创建后回填
                    daily_budget=country_budget,
                    countries=[country],
                    game_category=game_category,
                    is_broad=is_broad,
                    target_cpi=target_cpi,
                    custom_audience_ids=custom_audience_ids,
                    lookalike_audience_ids=lookalike_audience_ids,
                )
                adsets.append(adset)
        else:
            # CBO / ASC: 一个 AdSet 包含所有国家
            adset = self.build_adset(
                name=f"{project_name}_AllCountries_{game_category}",
                campaign_id="",
                daily_budget=daily_budget,
                countries=countries,
                game_category=game_category,
                is_broad=is_broad,
                target_cpi=target_cpi,
                custom_audience_ids=custom_audience_ids,
                lookalike_audience_ids=lookalike_audience_ids,
            )
            adsets.append(adset)

        return {
            "campaign": campaign,
            "adsets": adsets,
        }