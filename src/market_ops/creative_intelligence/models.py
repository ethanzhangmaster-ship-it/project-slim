"""E11 Phase 4.1 — IAP Creative Intelligence Analysis Core Layer（IAP 版）。

定义 4 个创意分析维度 + 7 个 IAP 价值层模型 + 综合结果：

创意分析层（现有）：
  - VisualFeatures:       视觉分析（composition / color / emotion / quality）
  - HookFeatures:         前 3 秒 Hook 分析（hook_type / strength / purchase_intent）
  - GameplayFeatures:     玩法展示分析（progression / economy / retention_signal）
  - MonetizationFeatures: 变现展示分析（purchase_trigger / iap_visibility / value_perception / urgency）
  - CreativeAnalysis:     聚合分析结果

IAP 价值层（新增）：
  - PerformanceMetrics:      广告层指标（CTR/CPI/ROAS/Spend）
  - PlayerAttributionProfile: Creative → Player Cohort 归因
  - ArchetypeProfile:         Creative → Player Archetype 分布
  - PaymentProfile:           Creative → Payment Pattern 付费触发
  - LTVProfile:               DNA → LTV 相关性
  - CreativeValueProfile:     统一创意价值画像（6 层聚合）
  - IAPFitnessResult:         IAP 综合适应度评分（替代 ROAS-based）
  - CreativeEvolutionDirection: 下一代 DNA 进化方向（输出给 Lovart）

核心哲学：
  不是分析"广告是否漂亮"或"点击率多高"，
  而是分析"什么让用户下载后愿意付费"。
  
升级路径：
  ROAS Winner → IAP Fitness Winner
  广告效果分析 → Creative DNA → Player Cohort → Payment → LTV 因果链
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════
# 枚举
# ═══════════════════════════════════════════════════════════

class HookType(str, Enum):
    """Hook 类型。"""
    IMPOSSIBLE_RESULT = "impossible_result"   # "OMG 这怎么可能？"
    BEFORE_AFTER = "before_after"             # 前后对比
    COLLECTION = "collection"                 # 收集/集齐
    REWARD_REVEAL = "reward_reveal"           # 奖励揭示
    PROGRESSION = "progression"               # 进度/成长
    RARE_ITEM = "rare_item"                   # 稀有物品展示
    CURIOSITY = "curiosity"                   # 好奇心（低质量 clickbait）
    UNKNOWN = "unknown"


class VisualSubject(str, Enum):
    """视觉主体类型。"""
    CHARACTER = "character"
    ITEM = "item"
    GAMEPLAY = "gameplay"
    REWARD = "reward"
    SCENE = "scene"
    UI = "ui"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class ColorStyle(str, Enum):
    """色彩风格。"""
    VIBRANT = "vibrant"
    DARK = "dark"
    PASTEL = "pastel"
    PREMIUM = "premium"           # 紫金/高级感
    HIGH_CONTRAST = "high_contrast"
    UNKNOWN = "unknown"


# ═══════════════════════════════════════════════════════════
# 子结构
# ═══════════════════════════════════════════════════════════

@dataclass
class Composition:
    """画面构图。"""
    center_focus: str = "mixed"          # character / gameplay / reward / item
    character_focus: float = 0.0         # 0-100，角色是否焦点
    gameplay_focus: float = 0.0          # 0-100，玩法是否焦点
    subject: VisualSubject = VisualSubject.UNKNOWN

    def to_dict(self) -> dict[str, Any]:
        return {
            "center_focus": self.center_focus,
            "character_focus": self.character_focus,
            "gameplay_focus": self.gameplay_focus,
            "subject": self.subject.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Composition:
        return cls(
            center_focus=data.get("center_focus", "mixed"),
            character_focus=float(data.get("character_focus", 0)),
            gameplay_focus=float(data.get("gameplay_focus", 0)),
            subject=VisualSubject(data.get("subject", "unknown")),
        )


@dataclass
class ColorProfile:
    """色彩分析。"""
    saturation: float = 0.0              # 0-100
    contrast: float = 0.0                # 0-100
    premium_feeling: float = 0.0         # 0-100，高级感
    style: ColorStyle = ColorStyle.UNKNOWN

    def to_dict(self) -> dict[str, Any]:
        return {
            "saturation": self.saturation,
            "contrast": self.contrast,
            "premium_feeling": self.premium_feeling,
            "style": self.style.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ColorProfile:
        return cls(
            saturation=float(data.get("saturation", 0)),
            contrast=float(data.get("contrast", 0)),
            premium_feeling=float(data.get("premium_feeling", 0)),
            style=ColorStyle(data.get("style", "unknown")),
        )


@dataclass
class EmotionProfile:
    """情绪分析。"""
    curiosity: float = 0.0               # 0-100
    achievement: float = 0.0             # 0-100
    desire: float = 0.0                  # 0-100，获取欲

    @property
    def dominant_emotion(self) -> str:
        dims = {
            "curiosity": self.curiosity,
            "achievement": self.achievement,
            "desire": self.desire,
        }
        return max(dims, key=dims.get)

    def to_dict(self) -> dict[str, Any]:
        return {
            "curiosity": self.curiosity,
            "achievement": self.achievement,
            "desire": self.desire,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EmotionProfile:
        return cls(
            curiosity=float(data.get("curiosity", 0)),
            achievement=float(data.get("achievement", 0)),
            desire=float(data.get("desire", 0)),
        )


@dataclass
class QualityProfile:
    """质量分析。"""
    professional_level: float = 0.0       # 0-100
    mobile_ad_fit: float = 0.0            # 0-100，移动广告适配度

    def to_dict(self) -> dict[str, Any]:
        return {
            "professional_level": self.professional_level,
            "mobile_ad_fit": self.mobile_ad_fit,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QualityProfile:
        return cls(
            professional_level=float(data.get("professional_level", 0)),
            mobile_ad_fit=float(data.get("mobile_ad_fit", 0)),
        )


@dataclass
class ProgressionProfile:
    """进度分析。"""
    level_growth: float = 0.0             # 0-100
    collection_growth: float = 0.0        # 0-100
    upgrade: float = 0.0                  # 0-100

    def to_dict(self) -> dict[str, Any]:
        return {
            "level_growth": self.level_growth,
            "collection_growth": self.collection_growth,
            "upgrade": self.upgrade,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProgressionProfile:
        return cls(
            level_growth=float(data.get("level_growth", 0)),
            collection_growth=float(data.get("collection_growth", 0)),
            upgrade=float(data.get("upgrade", 0)),
        )


@dataclass
class EconomyProfile:
    """经济系统分析。"""
    rare_item: float = 0.0                # 0-100
    premium_currency: float = 0.0         # 0-100
    unlock: float = 0.0                   # 0-100

    def to_dict(self) -> dict[str, Any]:
        return {
            "rare_item": self.rare_item,
            "premium_currency": self.premium_currency,
            "unlock": self.unlock,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EconomyProfile:
        return cls(
            rare_item=float(data.get("rare_item", 0)),
            premium_currency=float(data.get("premium_currency", 0)),
            unlock=float(data.get("unlock", 0)),
        )


@dataclass
class RetentionSignal:
    """留存信号。"""
    long_term_goal: float = 0.0           # 0-100
    character_attachment: float = 0.0     # 0-100

    def to_dict(self) -> dict[str, Any]:
        return {
            "long_term_goal": self.long_term_goal,
            "character_attachment": self.character_attachment,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RetentionSignal:
        return cls(
            long_term_goal=float(data.get("long_term_goal", 0)),
            character_attachment=float(data.get("character_attachment", 0)),
        )


@dataclass
class PurchaseTrigger:
    """购买触发分析。"""
    rarity: float = 0.0                   # 0-100
    power: float = 0.0                    # 0-100
    customization: float = 0.0            # 0-100
    collection: float = 0.0               # 0-100
    progression: float = 0.0              # 0-100

    @property
    def dominant_trigger(self) -> str:
        dims = {
            "rarity": self.rarity,
            "power": self.power,
            "customization": self.customization,
            "collection": self.collection,
            "progression": self.progression,
        }
        return max(dims, key=dims.get)

    @property
    def trigger_strength(self) -> float:
        """综合触发强度 (0-100)。"""
        return round(
            self.rarity * 0.30
            + self.collection * 0.25
            + self.progression * 0.20
            + self.power * 0.15
            + self.customization * 0.10,
            1,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "rarity": self.rarity,
            "power": self.power,
            "customization": self.customization,
            "collection": self.collection,
            "progression": self.progression,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PurchaseTrigger:
        return cls(
            rarity=float(data.get("rarity", 0)),
            power=float(data.get("power", 0)),
            customization=float(data.get("customization", 0)),
            collection=float(data.get("collection", 0)),
            progression=float(data.get("progression", 0)),
        )


# ═══════════════════════════════════════════════════════════
# 分析维度
# ═══════════════════════════════════════════════════════════

@dataclass
class VisualFeatures:
    """视觉特征。

    分析素材的视觉元素如何影响购买欲望。
    不是分析"是否漂亮"，而是分析"是否提升购买欲望"。
    """

    composition: Composition = field(default_factory=Composition)
    color: ColorProfile = field(default_factory=ColorProfile)
    emotion: EmotionProfile = field(default_factory=EmotionProfile)
    quality: QualityProfile = field(default_factory=QualityProfile)

    @property
    def visual_score(self) -> float:
        """视觉综合评分 (0-100)。

        权重：emotion.desire(0.35) + composition.character_focus(0.25) +
              color.premium_feeling(0.20) + quality.mobile_ad_fit(0.20)
        """
        return round(
            self.emotion.desire * 0.35
            + self.composition.character_focus * 0.25
            + self.color.premium_feeling * 0.20
            + self.quality.mobile_ad_fit * 0.20,
            1,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "composition": self.composition.to_dict(),
            "color": self.color.to_dict(),
            "emotion": self.emotion.to_dict(),
            "quality": self.quality.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VisualFeatures:
        return cls(
            composition=Composition.from_dict(data.get("composition", {})),
            color=ColorProfile.from_dict(data.get("color", {})),
            emotion=EmotionProfile.from_dict(data.get("emotion", {})),
            quality=QualityProfile.from_dict(data.get("quality", {})),
        )


@dataclass
class HookFeatures:
    """Hook 特征。

    分析前 3 秒 Hook 是否吸引目标付费用户。
    不是单纯点击，而是"用户有没有产生'我想试一下'的冲动"。
    """

    hook_type: HookType = HookType.UNKNOWN
    hook_strength: float = 0.0            # 0-100
    curiosity: float = 0.0                # 0-100
    reward_expectation: float = 0.0       # 0-100
    purchase_intent: float = 0.0          # 0-100，购买意图

    @property
    def is_clickbait(self) -> bool:
        """是否为低质量点击诱饵。"""
        return (
            self.hook_type == HookType.CURIOSITY
            and self.curiosity >= 80
            and self.purchase_intent <= 30
        )

    @property
    def is_iap_quality(self) -> bool:
        """是否为高质量 IAP Hook。"""
        return self.hook_strength >= 60 and self.purchase_intent >= 50

    @property
    def hook_score(self) -> float:
        """Hook 综合评分 (0-100)。

        权重：purchase_intent(0.40) + reward_expectation(0.30) +
              hook_strength(0.20) + curiosity(0.10)
        Clickbait 惩罚：直接降为 15。
        """
        if self.is_clickbait:
            return 15.0
        return round(
            self.purchase_intent * 0.40
            + self.reward_expectation * 0.30
            + self.hook_strength * 0.20
            + self.curiosity * 0.10,
            1,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "hook_type": self.hook_type.value,
            "hook_strength": self.hook_strength,
            "curiosity": self.curiosity,
            "reward_expectation": self.reward_expectation,
            "purchase_intent": self.purchase_intent,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HookFeatures:
        return cls(
            hook_type=HookType(data.get("hook_type", "unknown")),
            hook_strength=float(data.get("hook_strength", 0)),
            curiosity=float(data.get("curiosity", 0)),
            reward_expectation=float(data.get("reward_expectation", 0)),
            purchase_intent=float(data.get("purchase_intent", 0)),
        )


@dataclass
class GameplayFeatures:
    """玩法展示特征。

    IAP 与 IAA 最大区别：
    IAA 要"简单快速爽"，IAP 要"长期价值、成长、收集、付费点"。
    """

    progression: ProgressionProfile = field(default_factory=ProgressionProfile)
    economy: EconomyProfile = field(default_factory=EconomyProfile)
    retention_signal: RetentionSignal = field(default_factory=RetentionSignal)

    @property
    def gameplay_score(self) -> float:
        """玩法综合评分 (0-100)。

        权重：progression.level_growth(0.25) + economy.rare_item(0.25) +
              progression.collection_growth(0.20) + economy.unlock(0.15) +
              retention_signal.long_term_goal(0.15)
        """
        return round(
            self.progression.level_growth * 0.25
            + self.economy.rare_item * 0.25
            + self.progression.collection_growth * 0.20
            + self.economy.unlock * 0.15
            + self.retention_signal.long_term_goal * 0.15,
            1,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "progression": self.progression.to_dict(),
            "economy": self.economy.to_dict(),
            "retention_signal": self.retention_signal.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GameplayFeatures:
        return cls(
            progression=ProgressionProfile.from_dict(data.get("progression", {})),
            economy=EconomyProfile.from_dict(data.get("economy", {})),
            retention_signal=RetentionSignal.from_dict(data.get("retention_signal", {})),
        )


@dataclass
class MonetizationFeatures:
    """变现展示特征（IAP 专用）。

    分析广告有没有展示"购买理由"。
    不是"好不好玩"，而是"为什么用户愿意付钱"。
    """

    purchase_trigger: PurchaseTrigger = field(default_factory=PurchaseTrigger)
    iap_visibility: float = 0.0            # 0-100
    value_perception: float = 0.0          # 0-100
    urgency: float = 0.0                   # 0-100

    @property
    def monetization_score(self) -> float:
        """变现综合评分 (0-100)。

        权重：purchase_trigger(0.45) + iap_visibility(0.25) +
              value_perception(0.20) + urgency(0.10)
        """
        return round(
            self.purchase_trigger.trigger_strength * 0.45
            + self.iap_visibility * 0.25
            + self.value_perception * 0.20
            + self.urgency * 0.10,
            1,
        )

    @property
    def is_high_monetization(self) -> bool:
        return self.monetization_score >= 60

    def to_dict(self) -> dict[str, Any]:
        return {
            "purchase_trigger": self.purchase_trigger.to_dict(),
            "iap_visibility": self.iap_visibility,
            "value_perception": self.value_perception,
            "urgency": self.urgency,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MonetizationFeatures:
        return cls(
            purchase_trigger=PurchaseTrigger.from_dict(data.get("purchase_trigger", {})),
            iap_visibility=float(data.get("iap_visibility", 0)),
            value_perception=float(data.get("value_perception", 0)),
            urgency=float(data.get("urgency", 0)),
        )


# ═══════════════════════════════════════════════════════════
# 聚合结果
# ═══════════════════════════════════════════════════════════

@dataclass
class CreativeAnalysis:
    """创意分析结果。

    聚合所有分析维度，输出综合评分和 AI 洞察。
    """

    creative_id: str = ""

    # ── 分析维度 ────────────────────────────────────────
    visual_features: VisualFeatures = field(default_factory=VisualFeatures)
    hook_features: HookFeatures = field(default_factory=HookFeatures)
    gameplay_features: GameplayFeatures = field(default_factory=GameplayFeatures)
    monetization_features: MonetizationFeatures = field(default_factory=MonetizationFeatures)

    # ── 综合评分 ────────────────────────────────────────
    analysis_score: float = 0.0            # 0-100

    # ── AI 洞察 ─────────────────────────────────────────
    insight: str = ""

    @property
    def is_winner(self) -> bool:
        return self.analysis_score >= 70

    @property
    def is_iap_quality(self) -> bool:
        return (
            self.monetization_features.is_high_monetization
            and not self.hook_features.is_clickbait
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "visual_features": self.visual_features.to_dict(),
            "hook_features": self.hook_features.to_dict(),
            "gameplay_features": self.gameplay_features.to_dict(),
            "monetization_features": self.monetization_features.to_dict(),
            "analysis_score": self.analysis_score,
            "insight": self.insight,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CreativeAnalysis:
        return cls(
            creative_id=data.get("creative_id", ""),
            visual_features=VisualFeatures.from_dict(data.get("visual_features", {})),
            hook_features=HookFeatures.from_dict(data.get("hook_features", {})),
            gameplay_features=GameplayFeatures.from_dict(data.get("gameplay_features", {})),
            monetization_features=MonetizationFeatures.from_dict(data.get("monetization_features", {})),
            analysis_score=float(data.get("analysis_score", 0)),
            insight=data.get("insight", ""),
        )


# ════════════════════════════════════════════════════════════════════
# IAP 价值层模型（Phase 4.1 新增）
# ════════════════════════════════════════════════════════════════════
# 核心理念：Creative DNA → Player Cohort → Payment → LTV 因果链
# 替代旧有的 ROAS-only 分析模式


@dataclass
class PerformanceMetrics:
    """广告层表现指标（来自 sync_pipeline 数据）。

    ROAS 在这里只是验证指标，不是核心判定标准。
    """
    creative_id: str = ""
    platform: str = ""               # ios / android

    # 花费
    fb_spend: float = 0.0
    adjust_cost: float = 0.0
    spend: float = 0.0               # 优先 fb_spend

    # 安装
    adjust_installs: int = 0
    fb_installs: int = 0

    # 曝光点击
    fb_impressions: int = 0
    fb_clicks: int = 0

    # 收入
    adjust_revenue: float = 0.0

    # 衍生指标
    roas: float = 0.0
    cpi: float = 0.0
    ctr: float = 0.0
    cpm: float = 0.0
    cpc: float = 0.0

    # 视频指标
    is_video: bool = False
    video_plays: int = 0
    vtr: float = 0.0                # video through rate

    # 元数据
    status: str = "ACTIVE"
    active_days: int = 0
    ad_name: str = ""
    last_synced: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "platform": self.platform,
            "spend": round(self.spend, 2),
            "adjust_installs": self.adjust_installs,
            "fb_impressions": self.fb_impressions,
            "fb_clicks": self.fb_clicks,
            "adjust_revenue": round(self.adjust_revenue, 2),
            "roas": round(self.roas, 3),
            "cpi": round(self.cpi, 2),
            "ctr": round(self.ctr, 4),
            "cpm": round(self.cpm, 2),
            "cpv": round(self.cpc, 2),
            "is_video": self.is_video,
            "video_plays": self.video_plays,
            "vtr": round(self.vtr, 4),
            "status": self.status,
            "active_days": self.active_days,
        }

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> PerformanceMetrics:
        """从 sync_pipeline 输出的 CSV 行构建."""
        fb_spend = float(row.get("fb_spend") or 0)
        adj_cost = float(row.get("adj_cost") or 0)
        adj_rev = float(row.get("adj_revenue") or 0)
        adj_inst = int(float(row.get("adj_installs") or 0))
        fb_imp = int(float(row.get("fb_impressions") or 0))
        fb_clk = int(float(row.get("fb_clicks") or 0))
        spend = fb_spend if fb_spend > 0 else adj_cost

        return cls(
            creative_id=row.get("ad_id", ""),
            platform=row.get("platform", ""),
            fb_spend=fb_spend,
            adjust_cost=adj_cost,
            spend=round(spend, 2),
            adjust_installs=adj_inst,
            fb_installs=int(float(row.get("fb_installs") or 0)),
            fb_impressions=fb_imp,
            fb_clicks=fb_clk,
            adjust_revenue=adj_rev,
            roas=float(row.get("roas") or 0),
            cpi=float(row.get("cpi") or 0),
            ctr=float(row.get("ctr") or 0),
            cpm=float(row.get("cpm") or 0),
            cpc=float(row.get("cpc") or 0),
            is_video=row.get("is_video", "").lower() == "true",
            video_plays=int(float(row.get("video_plays") or 0)),
            vtr=float(row.get("vtr") or 0),
            status=row.get("status", "ACTIVE"),
            active_days=int(float(row.get("active_days") or 0)),
            ad_name=row.get("ad_name", ""),
            last_synced=row.get("last_synced", ""),
        )


@dataclass
class PlayerAttributionProfile:
    """Creative → Player Cohort 归因结果。

    回答："这个创意吸引来的是什么玩家？"
    """
    creative_id: str = ""

    # 玩家规模
    player_count: int = 0
    payer_count: int = 0
    payer_rate: float = 0.0

    # 留存
    d1_retention: float = 0.0
    d7_retention: float = 0.0
    d30_retention: float = 0.0

    # 行为特征
    avg_merge_count: float = 0.0
    avg_merge_speed: float = 0.0
    avg_areas_unlocked: float = 0.0
    avg_collection_rate: float = 0.0
    avg_progression_velocity: float = 0.0

    # 付费触发
    top_payment_triggers: list[tuple[str, int]] = field(default_factory=list)

    @property
    def is_high_value_cohort(self) -> bool:
        """高价值玩家群体判定."""
        return self.payer_rate >= 0.08 and self.d30_retention >= 0.15

    @property
    def cohort_quality_score(self) -> float:
        """玩家群体质量评分 (0-1)."""
        payer_scaled = min(self.payer_rate / 0.20, 1.0)
        retention_scaled = min(self.d30_retention / 0.30, 1.0)
        return round(payer_scaled * 0.5 + retention_scaled * 0.3
                     + min(self.avg_progression_velocity / 5.0, 1.0) * 0.2, 3)

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "player_count": self.player_count,
            "payer_count": self.payer_count,
            "payer_rate": round(self.payer_rate, 3),
            "d1_retention": round(self.d1_retention, 3),
            "d7_retention": round(self.d7_retention, 3),
            "d30_retention": round(self.d30_retention, 3),
            "avg_merge_count": round(self.avg_merge_count, 1),
            "avg_merge_speed": round(self.avg_merge_speed, 2),
            "avg_areas_unlocked": round(self.avg_areas_unlocked, 1),
            "avg_collection_rate": round(self.avg_collection_rate, 2),
            "avg_progression_velocity": round(self.avg_progression_velocity, 2),
            "top_payment_triggers": [
                {"trigger": t, "count": c} for t, c in self.top_payment_triggers[:5]
            ],
            "cohort_quality_score": self.cohort_quality_score,
            "is_high_value_cohort": self.is_high_value_cohort,
        }


@dataclass
class ArchetypeProfile:
    """Creative → Player Archetype 分布。

    回答："这个创意吸引的是哪种玩家类型？"
    """
    creative_id: str = ""

    # 预测分布（来自 ArchetypePredictor）
    predicted_collector: float = 0.0
    predicted_power: float = 0.0
    predicted_progression: float = 0.0
    predicted_explorer: float = 0.0
    predicted_casual: float = 0.0

    # 实际分布（来自真实玩家数据）
    actual_collector: float = 0.0
    actual_power: float = 0.0
    actual_progression: float = 0.0
    actual_explorer: float = 0.0
    actual_casual: float = 0.0

    # 预测误差
    prediction_error: dict[str, float] = field(default_factory=dict)

    @property
    def dominant_archetype(self) -> str:
        """实际主导玩家类型."""
        dist = {
            "collector": self.actual_collector,
            "power": self.actual_power,
            "progression": self.actual_progression,
            "explorer": self.actual_explorer,
            "casual": self.actual_casual,
        }
        return max(dist, key=dist.get)

    @property
    def high_value_ratio(self) -> float:
        """高价值玩家占比（Collector + Power + Progression）."""
        return round(
            self.actual_collector + self.actual_power + self.actual_progression, 3)

    @property
    def prediction_accuracy(self) -> float:
        """预测准确度 (1 - avg_error)."""
        if not self.prediction_error:
            return 0.0
        avg_err = sum(abs(e) for e in self.prediction_error.values()) / len(self.prediction_error)
        return round(max(0.0, 1.0 - avg_err), 3)

    def compute_prediction_error(self) -> None:
        """计算预测 vs 实际的误差."""
        self.prediction_error = {
            "collector": round(self.actual_collector - self.predicted_collector, 3),
            "power": round(self.actual_power - self.predicted_power, 3),
            "progression": round(self.actual_progression - self.predicted_progression, 3),
            "explorer": round(self.actual_explorer - self.predicted_explorer, 3),
            "casual": round(self.actual_casual - self.predicted_casual, 3),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "predicted": {
                "collector": round(self.predicted_collector, 3),
                "power": round(self.predicted_power, 3),
                "progression": round(self.predicted_progression, 3),
                "explorer": round(self.predicted_explorer, 3),
                "casual": round(self.predicted_casual, 3),
            },
            "actual": {
                "collector": round(self.actual_collector, 3),
                "power": round(self.actual_power, 3),
                "progression": round(self.actual_progression, 3),
                "explorer": round(self.actual_explorer, 3),
                "casual": round(self.actual_casual, 3),
            },
            "dominant_archetype": self.dominant_archetype,
            "high_value_ratio": self.high_value_ratio,
            "prediction_accuracy": self.prediction_accuracy,
            "prediction_error": self.prediction_error,
        }


@dataclass
class PaymentProfile:
    """Creative → Payment Pattern 付费行为分析。

    回答："这个创意吸引的用户为什么付费？什么时候付？"

    Phase 4.1.5 升级：新增 D0/D1/D7 付费率、大R占比、商品偏好。
    """

    creative_id: str = ""

    # 付费规模
    payer_count: int = 0
    payer_rate: float = 0.0
    total_revenue: float = 0.0
    arppu: float = 0.0               # 付费用户人均收入
    arpu: float = 0.0                # 全体用户人均收入

    # 付费行为
    avg_first_purchase_day: float = 0.0
    avg_purchase_frequency: float = 0.0  # 每周购买次数
    avg_order_value: float = 0.0
    avg_purchase_count: float = 0.0      # Phase 4.1.5: 人均购买次数

    # 付费时间窗（Phase 4.1.5 新增）
    d0_payer_rate: float = 0.0           # 安装当天付费率
    d1_payer_rate: float = 0.0           # 首日付费率
    d7_payer_rate: float = 0.0           # 7日付费率

    # 大R分析（Phase 4.1.5 新增）
    whale_ratio: float = 0.0             # 大R占比（ARPPU > $50 的玩家比例）
    whale_threshold: float = 50.0        # 大R判定阈值

    # 付费触发分布
    trigger_distribution: dict[str, float] = field(default_factory=dict)
    # e.g., {"character_pack": 0.35, "energy_refill": 0.25, "collection_complete": 0.20}

    # 商品偏好（Phase 4.1.5 新增）
    preferred_offers: list[str] = field(default_factory=list)
    # e.g., ["collection_bundle", "missing_item", "progression_pack"]

    @property
    def is_healthy_monetization(self) -> bool:
        """付费是否健康（非一次性大R，非纯薅羊毛）."""
        return (
            self.payer_rate >= 0.05
            and self.arppu >= 5.0
            and self.avg_purchase_frequency >= 0.5
        )

    @property
    def dominant_trigger(self) -> str:
        """主导付费触发."""
        if not self.trigger_distribution:
            return "unknown"
        return max(self.trigger_distribution, key=self.trigger_distribution.get)

    @property
    def payment_health_score(self) -> float:
        """付费健康度评分 (0-1)."""
        payer_scaled = min(self.payer_rate / 0.15, 1.0)
        arppu_scaled = min(self.arppu / 20.0, 1.0)
        freq_scaled = min(self.avg_purchase_frequency / 2.0, 1.0)
        return round(payer_scaled * 0.35 + arppu_scaled * 0.40 + freq_scaled * 0.25, 3)

    @property
    def payer_conversion_curve(self) -> dict[str, float]:
        """付费转化曲线：D0 → D1 → D7."""
        return {
            "d0": round(self.d0_payer_rate, 4),
            "d1": round(self.d1_payer_rate, 4),
            "d7": round(self.d7_payer_rate, 4),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "payer_count": self.payer_count,
            "payer_rate": round(self.payer_rate, 3),
            "total_revenue": round(self.total_revenue, 2),
            "arppu": round(self.arppu, 2),
            "arpu": round(self.arpu, 2),
            "avg_first_purchase_day": round(self.avg_first_purchase_day, 1),
            "avg_purchase_frequency": round(self.avg_purchase_frequency, 2),
            "avg_order_value": round(self.avg_order_value, 2),
            "avg_purchase_count": round(self.avg_purchase_count, 2),
            "d0_payer_rate": round(self.d0_payer_rate, 4),
            "d1_payer_rate": round(self.d1_payer_rate, 4),
            "d7_payer_rate": round(self.d7_payer_rate, 4),
            "whale_ratio": round(self.whale_ratio, 4),
            "trigger_distribution": {
                k: round(v, 3) for k, v in self.trigger_distribution.items()
            },
            "preferred_offers": self.preferred_offers[:5],
            "dominant_trigger": self.dominant_trigger,
            "is_healthy_monetization": self.is_healthy_monetization,
            "payment_health_score": self.payment_health_score,
            "payer_conversion_curve": self.payer_conversion_curve,
        }


@dataclass
class LTVProfile:
    """DNA → LTV 相关性分析。

    回答："这个创意 DNA 的长期用户价值是多少？"

    Phase 4.1.5 升级：新增 d7_ltv、DNA 级 LTV 相关性系数。
    """
    creative_id: str = ""

    # LTV 指标
    d7_ltv: float = 0.0              # Phase 4.1.5: 7日 LTV
    d30_ltv: float = 0.0
    d90_ltv: float = 0.0
    projected_ltv: float = 0.0       # 预测终身价值

    # 相关性
    ltv_confidence: float = 0.0       # 样本量置信度
    sample_size: int = 0

    # DNA 级 LTV 相关性（Phase 4.1.5 新增）
    dna_ltv_correlation: float = 0.0  # Creative DNA → LTV 相关系数 (0-1)
    # 0.82 = rescue hook + collection reward + cozy visual → 高 LTV

    # DNA 贡献分解
    dna_contribution: dict[str, float] = field(default_factory=dict)
    # e.g., {"hook:rescue": 0.35, "reward:collection": 0.25, "visual:premium": 0.20}

    @property
    def ltv_tier(self) -> str:
        """LTV 层级."""
        if self.d30_ltv >= 10:
            return "S"
        if self.d30_ltv >= 5:
            return "A"
        if self.d30_ltv >= 2:
            return "B"
        return "C"

    @property
    def ltv_scaled(self) -> float:
        """归一化 LTV (0-1)."""
        return round(min(self.d30_ltv / 20.0, 1.0), 3)

    @property
    def d7_ltv_scaled(self) -> float:
        """归一化 D7 LTV (0-1)."""
        return round(min(self.d7_ltv / 10.0, 1.0), 3)

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "d7_ltv": round(self.d7_ltv, 2),
            "d30_ltv": round(self.d30_ltv, 2),
            "d90_ltv": round(self.d90_ltv, 2),
            "projected_ltv": round(self.projected_ltv, 2),
            "ltv_tier": self.ltv_tier,
            "ltv_scaled": self.ltv_scaled,
            "d7_ltv_scaled": self.d7_ltv_scaled,
            "dna_ltv_correlation": round(self.dna_ltv_correlation, 3),
            "ltv_confidence": round(self.ltv_confidence, 3),
            "sample_size": self.sample_size,
            "dna_contribution": {
                k: round(v, 3) for k, v in self.dna_contribution.items()
            },
        }


# ════════════════════════════════════════════════════════════════════
# 统一聚合模型
# ════════════════════════════════════════════════════════════════════


@dataclass
class CreativeValueProfile:
    """统一创意价值画像 — 6 层聚合。

    整合 Creative Analysis + IAP 价值层，形成完整的创意价值判断。
    替代旧有的简单 ROAS 排序。

    6 层：
      1. Performance (广告表现)
      2. Creative DNA (创意内容分析)
      3. Player Attribution (玩家归因)
      4. Archetype (玩家类型)
      5. Payment (付费行为)
      6. LTV (长期价值)
    """
    creative_id: str = ""

    # Layer 1: 广告表现
    performance: PerformanceMetrics | None = None

    # Layer 2: 创意内容分析
    creative_analysis: CreativeAnalysis | None = None

    # Layer 3: 玩家归因
    player_attribution: PlayerAttributionProfile | None = None

    # Layer 4: 玩家类型
    archetype: ArchetypeProfile | None = None

    # Layer 5: 付费行为
    payment: PaymentProfile | None = None

    # Layer 6: LTV 价值
    ltv: LTVProfile | None = None

    @property
    def iap_fitness(self) -> IAPFitnessResult:
        """计算 IAP 综合适应度."""
        return IAPFitnessResult.compute_from(self)

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "performance": self.performance.to_dict() if self.performance else None,
            "creative_analysis": self.creative_analysis.to_dict() if self.creative_analysis else None,
            "player_attribution": self.player_attribution.to_dict() if self.player_attribution else None,
            "archetype": self.archetype.to_dict() if self.archetype else None,
            "payment": self.payment.to_dict() if self.payment else None,
            "ltv": self.ltv.to_dict() if self.ltv else None,
            "iap_fitness": self.iap_fitness.to_dict(),
        }


@dataclass
class IAPFitnessResult:
    """IAP 综合适应度评分 — 替代 ROAS-based Winner。

    Phase 4.1.5 升级公式：
      IAP Fitness = 0.20 × Creative Performance + 0.20 × Payer Rate
                  + 0.25 × D30 LTV + 0.15 × Retention
                  + 0.10 × Archetype Quality + 0.10 × DNA Future Value

    ROAS 只是验证指标，不是核心。
    IAP 产品买的是未来价值，不是当次 ROAS。
    """
    creative_id: str = ""

    # 组件（Phase 4.1.5 升级）
    creative_performance_scaled: float = 0.0   # 0.20: 广告表现（CTR/CPI归一化）
    payer_rate: float = 0.0                    # 0.20: 付费率
    ltv_scaled: float = 0.0                    # 0.25: D30 LTV 归一化
    d30_retention: float = 0.0                 # 0.15: D30 留存率
    archetype_quality: float = 0.0             # 0.10: 玩家类型质量（Collector+Power+Progression占比）
    dna_future_value: float = 0.0              # 0.10: DNA 未来价值（LTV 相关性系数）

    # 综合
    fitness_score: float = 0.0
    confidence: float = 0.0

    # 验证
    roas: float = 0.0
    roas_validation: str = "unverified"  # verified / pending / unverified

    # 判定
    is_winner: bool = False
    winner_tier: str = "C"            # S / A / B / C
    decision: str = "observe"         # scale / observe / stop / evolve
    recommendation: str = "OBSERVE"   # SCALE / OBSERVE / STOP / EVOLVE

    # 解释
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    insight: str = ""

    @classmethod
    def compute_from(cls, profile: CreativeValueProfile) -> IAPFitnessResult:
        """从 CreativeValueProfile 计算 IAP 适应度（Phase 4.1.5 公式）."""
        result = cls(creative_id=profile.creative_id)

        # 0.20 Creative Performance: 综合 CTR + CPI 归一化
        if profile.performance:
            ctr_scaled = min(profile.performance.ctr / 0.05, 1.0)  # 5% CTR = perfect
            cpi_inv = 1.0 - min(profile.performance.cpi / 20.0, 1.0)  # $20 CPI = 0, $0 CPI = 1
            result.creative_performance_scaled = round(ctr_scaled * 0.4 + cpi_inv * 0.6, 3)
            result.roas = profile.performance.roas
            result.roas_validation = "verified" if profile.performance.spend > 100 else "unverified"

        # 0.20 Payer Rate
        if profile.payment:
            result.payer_rate = profile.payment.payer_rate
            if profile.payment.is_healthy_monetization:
                result.strengths.append("healthy_monetization")
            else:
                result.weaknesses.append("weak_monetization")

        # 0.25 D30 LTV
        if profile.ltv:
            result.ltv_scaled = profile.ltv.ltv_scaled
            result.dna_future_value = profile.ltv.dna_ltv_correlation
            result.confidence = max(result.confidence, profile.ltv.ltv_confidence)

        # 0.15 Retention
        if profile.player_attribution:
            result.d30_retention = profile.player_attribution.d30_retention

        # 0.10 Archetype Quality: Collector + Power + Progression 占比
        if profile.archetype:
            result.archetype_quality = profile.archetype.high_value_ratio

        # 0.10 DNA Future Value: already set from LTV
        # (if no LTV, estimate from archetype quality)
        if result.dna_future_value == 0.0 and profile.archetype:
            result.dna_future_value = min(result.archetype_quality * 0.8, 0.8)

        # Compute fitness (Phase 4.1.5 formula)
        result.fitness_score = round(
            result.creative_performance_scaled * 0.20
            + result.payer_rate * 0.20
            + result.ltv_scaled * 0.25
            + result.d30_retention * 0.15
            + result.archetype_quality * 0.10
            + result.dna_future_value * 0.10,
            4,
        )

        # Winner判定
        result._determine_winner()

        return result

    def _determine_winner(self) -> None:
        """判定 Winner 等级（Phase 4.1.5 升级）."""
        if self.fitness_score >= 0.55:
            self.winner_tier = "S"
            self.is_winner = True
            self.decision = "scale"
            self.recommendation = "SCALE"
        elif self.fitness_score >= 0.40:
            self.winner_tier = "A"
            self.is_winner = True
            self.decision = "scale"
            self.recommendation = "SCALE"
        elif self.fitness_score >= 0.25:
            self.winner_tier = "B"
            self.is_winner = True
            self.decision = "observe"
            self.recommendation = "OBSERVE"
        else:
            self.winner_tier = "C"
            self.is_winner = False
            self.decision = "stop"
            self.recommendation = "STOP"

        # ROAS 验证
        if self.roas < 0.8 and self.is_winner:
            self.decision = "observe"
            self.recommendation = "OBSERVE"
            self.weaknesses.append("low_roas_despite_fitness")
        if self.roas >= 1.5 and not self.is_winner:
            self.decision = "observe"
            self.recommendation = "OBSERVE"
            self.strengths.append("high_roas_despite_low_fitness")

        # IAP 产品特殊逻辑：高付费率但低 ROAS → 仍然是 Winner
        if self.payer_rate >= 0.10 and self.ltv_scaled >= 0.4 and not self.is_winner:
            self.winner_tier = "B"
            self.is_winner = True
            self.decision = "observe"
            self.recommendation = "OBSERVE"
            self.strengths.append("high_payer_ltv_despite_roas")

        # 生成洞察
        if not self.insight:
            parts = []
            if self.winner_tier in ("S", "A"):
                parts.append(f"Tier {self.winner_tier} IAP Winner (fitness={self.fitness_score:.3f})")
            if self.roas > 0:
                parts.append(f"ROAS={self.roas:.2f}")
            if self.payer_rate > 0:
                parts.append(f"payer_rate={self.payer_rate:.1%}")
            if self.d30_retention > 0:
                parts.append(f"D30={self.d30_retention:.1%}")
            if self.archetype_quality > 0:
                parts.append(f"arch_quality={self.archetype_quality:.1%}")
            self.insight = "; ".join(parts) if parts else "insufficient data"

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "components": {
                "creative_performance": round(self.creative_performance_scaled, 3),
                "payer_rate": round(self.payer_rate, 3),
                "ltv_scaled": round(self.ltv_scaled, 3),
                "d30_retention": round(self.d30_retention, 3),
                "archetype_quality": round(self.archetype_quality, 3),
                "dna_future_value": round(self.dna_future_value, 3),
            },
            "fitness_score": self.fitness_score,
            "confidence": round(self.confidence, 3),
            "roas": round(self.roas, 3),
            "roas_validation": self.roas_validation,
            "is_winner": self.is_winner,
            "winner_tier": self.winner_tier,
            "decision": self.decision,
            "recommendation": self.recommendation,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "insight": self.insight,
        }


@dataclass
class CreativeEvolutionDirection:
    """下一代 DNA 进化方向 — 输出给 Phase 4.2 / Lovart。

    不是输出"生成一个好看的图片"，而是输出：
      → 目标玩家类型
      → 获胜 Hook 模式
      → 玩法展示策略
      → IAP 触发点
      → 视觉方向
    """
    source_creative_id: str = ""
    generation: int = 0

    # 目标玩家
    target_archetypes: list[str] = field(default_factory=list)
    # e.g., ["collector", "power"]

    # 获胜 DNA 元素
    winning_hook: str = ""              # e.g., "rare_character_unlock"
    winning_gameplay: str = ""          # e.g., "progression_showcase"
    winning_reward: str = ""            # e.g., "collection_completion"
    winning_visual: str = ""            # e.g., "premium_character_closeup"

    # IAP 触发
    iap_trigger: str = ""               # e.g., "completion_pressure"
    iap_trigger_strength: float = 0.0

    # 变异策略
    mutation_operations: list[str] = field(default_factory=list)
    # e.g., ["hook:rescue→rare_character", "visual:add_premium_effect"]

    # 预期效果
    expected_fitness: float = 0.0
    expected_archetype_shift: dict[str, float] = field(default_factory=dict)

    # 元数据
    based_on_fitness: float = 0.0
    evolution_reason: str = ""

    def to_lovart_prompt_context(self) -> dict[str, Any]:
        """转换为 Lovart 可用的 Prompt 上下文."""
        return {
            "target_player": "+".join(self.target_archetypes) if self.target_archetypes else "casual",
            "winning_hook": self.winning_hook,
            "gameplay": self.winning_gameplay,
            "iap_trigger": self.iap_trigger,
            "visual": self.winning_visual,
            "mutation_operations": self.mutation_operations,
            "expected_fitness": self.expected_fitness,
            "evolution_reason": self.evolution_reason,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_creative_id": self.source_creative_id,
            "generation": self.generation,
            "target_archetypes": self.target_archetypes,
            "winning_hook": self.winning_hook,
            "winning_gameplay": self.winning_gameplay,
            "winning_reward": self.winning_reward,
            "winning_visual": self.winning_visual,
            "iap_trigger": self.iap_trigger,
            "iap_trigger_strength": self.iap_trigger_strength,
            "mutation_operations": self.mutation_operations,
            "expected_fitness": self.expected_fitness,
            "expected_archetype_shift": self.expected_archetype_shift,
            "based_on_fitness": self.based_on_fitness,
            "evolution_reason": self.evolution_reason,
            "lovart_prompt_context": self.to_lovart_prompt_context(),
        }


# ════════════════════════════════════════════════════════════════════
# Phase 4.2 — Creative Causal Intelligence Layer
# ════════════════════════════════════════════════════════════════════
# 核心理念：Creative DNA → Player Behavior → Revenue Outcome 因果链
# 从"这个素材带来高价值玩家"升级到"为什么这个DNA带来高价值"
# 连接 Creative Intelligence → V5 Evolution Engine


# ── Phase 4.2.1: Player Journey 模型 ──────────────────────

@dataclass
class PlayerJourneyProfile:
    """Creative → Player Journey 完整行为轨迹。

    回答："这个创意吸引的用户从安装到付费经历了什么？"
    不是只看付费结果，而是看完整的玩家旅程。
    """

    creative_id: str = ""

    # FTUE (First Time User Experience)
    install_count: int = 0
    ftue_completion_rate: float = 0.0       # 新手引导完成率
    tutorial_skip_rate: float = 0.0         # 跳过教程率

    # 留存
    d1_retention: float = 0.0
    d3_retention: float = 0.0
    d7_retention: float = 0.0
    d30_retention: float = 0.0

    # 进度（Merge 游戏专用）
    d1_progress: float = 0.0                # D1 平均进度（关卡/等级）
    d3_progress: float = 0.0
    d7_progress: float = 0.0
    avg_level_reached: float = 0.0          # 平均到达等级
    avg_areas_unlocked: float = 0.0         # 平均解锁区域数

    # 玩法参与
    avg_merge_count: float = 0.0            # 平均 Merge 次数
    avg_merge_speed: float = 0.0            # 平均 Merge 速度（次/分钟）
    avg_collection_rate: float = 0.0        # 平均收集完成率
    avg_session_count: float = 0.0          # 平均会话数
    avg_session_duration: float = 0.0       # 平均会话时长（分钟）

    # 功能使用
    feature_usage: dict[str, float] = field(default_factory=dict)
    # e.g., {"collection": 0.85, "merge": 0.95, "decoration": 0.20, "guild": 0.10}

    # 付费旅程
    payer_conversion_rate: float = 0.0      # 付费转化率
    first_purchase_hour: float = 0.0        # 首次付费时间（小时）
    avg_purchase_count: float = 0.0
    avg_order_value: float = 0.0
    repeat_purchase_rate: float = 0.0       # 重复购买率

    # 样本量
    sample_size: int = 0

    @property
    def is_high_quality_journey(self) -> bool:
        """高质量玩家旅程判定."""
        return (
            self.ftue_completion_rate >= 0.80
            and self.d7_retention >= 0.30
            and self.payer_conversion_rate >= 0.05
        )

    @property
    def journey_quality_score(self) -> float:
        """玩家旅程质量评分 (0-1)."""
        ftue_scaled = min(self.ftue_completion_rate / 0.90, 1.0)
        d7_scaled = min(self.d7_retention / 0.40, 1.0)
        payer_scaled = min(self.payer_conversion_rate / 0.15, 1.0)
        progress_scaled = min(self.d7_progress / 10.0, 1.0)
        return round(
            ftue_scaled * 0.15 + d7_scaled * 0.35
            + payer_scaled * 0.35 + progress_scaled * 0.15, 3
        )

    @property
    def retention_curve(self) -> dict[str, float]:
        return {
            "d1": round(self.d1_retention, 3),
            "d3": round(self.d3_retention, 3),
            "d7": round(self.d7_retention, 3),
            "d30": round(self.d30_retention, 3),
        }

    @property
    def progression_curve(self) -> dict[str, float]:
        return {
            "d1": round(self.d1_progress, 1),
            "d3": round(self.d3_progress, 1),
            "d7": round(self.d7_progress, 1),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "install_count": self.install_count,
            "ftue_completion_rate": round(self.ftue_completion_rate, 3),
            "tutorial_skip_rate": round(self.tutorial_skip_rate, 3),
            "d1_retention": round(self.d1_retention, 3),
            "d3_retention": round(self.d3_retention, 3),
            "d7_retention": round(self.d7_retention, 3),
            "d30_retention": round(self.d30_retention, 3),
            "d1_progress": round(self.d1_progress, 1),
            "d3_progress": round(self.d3_progress, 1),
            "d7_progress": round(self.d7_progress, 1),
            "avg_level_reached": round(self.avg_level_reached, 1),
            "avg_areas_unlocked": round(self.avg_areas_unlocked, 1),
            "avg_merge_count": round(self.avg_merge_count, 1),
            "avg_merge_speed": round(self.avg_merge_speed, 2),
            "avg_collection_rate": round(self.avg_collection_rate, 2),
            "avg_session_count": round(self.avg_session_count, 1),
            "avg_session_duration": round(self.avg_session_duration, 1),
            "feature_usage": {k: round(v, 2) for k, v in self.feature_usage.items()},
            "payer_conversion_rate": round(self.payer_conversion_rate, 3),
            "first_purchase_hour": round(self.first_purchase_hour, 1),
            "avg_purchase_count": round(self.avg_purchase_count, 2),
            "avg_order_value": round(self.avg_order_value, 2),
            "repeat_purchase_rate": round(self.repeat_purchase_rate, 3),
            "sample_size": self.sample_size,
            "is_high_quality_journey": self.is_high_quality_journey,
            "journey_quality_score": self.journey_quality_score,
            "retention_curve": self.retention_curve,
            "progression_curve": self.progression_curve,
        }


# ── Phase 4.2.2: Causal Discovery 模型 ──────────────────────

@dataclass
class GeneImpact:
    """单个基因对玩家行为的影响度量。

    回答："rescue hook 对 payer_rate 的影响力是多少？"
    """

    gene_name: str = ""               # e.g., "hook:rescue"
    gene_category: str = ""           # e.g., "hook", "visual", "psychology"

    # 影响度量
    payer_rate_lift: float = 0.0      # 付费率提升（相对基准）
    ltv_lift: float = 0.0             # D30 LTV 提升
    retention_lift: float = 0.0       # D7 留存提升
    progression_lift: float = 0.0     # 进度提升

    # 综合影响
    impact_score: float = 0.0         # 综合影响分数 (0-1)
    confidence: float = 0.0           # 置信度
    sample_size: int = 0

    # 玩家类型关联
    highest_archetype: str = ""       # 最受影响玩家类型
    archetype_impact: dict[str, float] = field(default_factory=dict)

    @property
    def is_positive_impact(self) -> bool:
        return self.impact_score >= 0.5

    @property
    def is_high_confidence(self) -> bool:
        return self.confidence >= 0.70

    def to_dict(self) -> dict[str, Any]:
        return {
            "gene_name": self.gene_name,
            "gene_category": self.gene_category,
            "payer_rate_lift": round(self.payer_rate_lift, 4),
            "ltv_lift": round(self.ltv_lift, 4),
            "retention_lift": round(self.retention_lift, 4),
            "progression_lift": round(self.progression_lift, 4),
            "impact_score": round(self.impact_score, 3),
            "confidence": round(self.confidence, 3),
            "sample_size": self.sample_size,
            "highest_archetype": self.highest_archetype,
            "archetype_impact": {k: round(v, 3) for k, v in self.archetype_impact.items()},
            "is_positive_impact": self.is_positive_impact,
            "is_high_confidence": self.is_high_confidence,
        }


@dataclass
class CausalDiscoveryResult:
    """DNA 因果发现完整结果。

    回答："哪些 DNA 元素、影响哪些玩家行为、最终驱动 LTV？"
    """

    creative_id: str = ""

    # 因果链
    # DNA → Behavior → Outcome
    causal_chain: list[dict[str, Any]] = field(default_factory=list)
    # e.g., [
    #   {"dna": "hook:rescue", "behavior": "ftue_completion", "impact": 0.35},
    #   {"dna": "hook:rescue", "behavior": "d7_retention", "impact": 0.28},
    #   {"dna": "reward:collection", "behavior": "payer_rate", "impact": 0.42},
    # ]

    # 基因影响排序
    gene_impacts: list[GeneImpact] = field(default_factory=list)

    # 发现
    winning_patterns: list[str] = field(default_factory=list)
    # e.g., ["rescue_hook + collection_reward + cozy_visual = high_LTV_players"]
    losing_patterns: list[str] = field(default_factory=list)

    # 置信度
    overall_confidence: float = 0.0

    @property
    def top_positive_genes(self) -> list[GeneImpact]:
        return [g for g in self.gene_impacts if g.is_positive_impact][:5]

    @property
    def top_high_confidence_genes(self) -> list[GeneImpact]:
        return [g for g in self.gene_impacts if g.is_high_confidence][:5]

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "causal_chain": self.causal_chain,
            "gene_impacts": [g.to_dict() for g in self.gene_impacts],
            "winning_patterns": self.winning_patterns,
            "losing_patterns": self.losing_patterns,
            "overall_confidence": round(self.overall_confidence, 3),
        }


# ── Phase 4.2.3: Evolution Policy 模型 ──────────────────────

@dataclass
class CreativeHypothesis:
    """创意假设 — 不是"生成一张图片"，而是"生成一个可验证的假设"。

    核心理念：每一次创意生成都是一次实验。
    """

    hypothesis_id: str = ""
    creative_id: str = ""

    # 假设内容
    hypothesis: str = ""              # e.g., "Collector 玩家害怕损失，Rescue Hook 触发 D7 付费"
    target_player: str = ""           # e.g., "collector"
    target_psychology: str = ""       # e.g., "loss_aversion"
    expected_impact: str = ""         # e.g., "提升 D7 payer rate +15%"

    # 验证条件
    required_impressions: int = 5000
    verification_metric: str = "d7_payer_rate"  # 验证指标
    success_threshold: float = 0.0    # 成功阈值

    # 来源
    based_on_winners: list[str] = field(default_factory=list)
    based_on_dna: list[str] = field(default_factory=list)

    # 状态
    status: str = "pending"           # pending / running / verified / rejected

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "creative_id": self.creative_id,
            "hypothesis": self.hypothesis,
            "target_player": self.target_player,
            "target_psychology": self.target_psychology,
            "expected_impact": self.expected_impact,
            "required_impressions": self.required_impressions,
            "verification_metric": self.verification_metric,
            "success_threshold": self.success_threshold,
            "based_on_winners": self.based_on_winners,
            "based_on_dna": self.based_on_dna,
            "status": self.status,
        }


@dataclass
class MutationPolicy:
    """进化策略 — 连接 Causal Discovery → V5 Mutation Engine。

    不是随机变异，而是基于因果发现的定向进化。
    """

    policy_id: str = ""
    generation: int = 0

    # 基因调整策略
    amplify_genes: list[GeneImpact] = field(default_factory=list)
    # 应该放大的基因（高影响力）

    suppress_genes: list[GeneImpact] = field(default_factory=list)
    # 应该抑制的基因（低影响力或负面）

    explore_genes: list[dict[str, Any]] = field(default_factory=list)
    # 应该探索的新基因组合
    # e.g., [{"hook": "social_proof", "reward": "guild_bonus", "risk": 0.3}]

    # 调整幅度
    amplification_rate: float = 0.20   # 放大比例
    suppression_rate: float = 0.15     # 抑制比例
    exploration_rate: float = 0.10     # 探索比例

    # 生成的假设
    hypotheses: list[CreativeHypothesis] = field(default_factory=list)

    # 元数据
    based_on_insights: list[str] = field(default_factory=list)
    confidence: float = 0.0

    def to_v5_mutation_requests(self) -> list[dict[str, Any]]:
        """转换为 V5 Mutation Engine 可用的请求列表."""
        requests = []

        for gene in self.amplify_genes:
            requests.append({
                "gene_name": gene.gene_name,
                "action": "amplify",
                "rate": self.amplification_rate,
                "reason": f"impact_score={gene.impact_score:.3f}, confidence={gene.confidence:.3f}",
            })

        for gene in self.suppress_genes:
            requests.append({
                "gene_name": gene.gene_name,
                "action": "suppress",
                "rate": self.suppression_rate,
                "reason": f"impact_score={gene.impact_score:.3f}, confidence={gene.confidence:.3f}",
            })

        for explore in self.explore_genes:
            requests.append({
                "gene_name": explore.get("hook", "") + "×" + explore.get("reward", ""),
                "action": "explore",
                "risk": explore.get("risk", 0.3),
                "reason": "new combination test",
            })

        return requests

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "generation": self.generation,
            "amplify_genes": [
                {"gene": g.gene_name, "impact": g.impact_score}
                for g in self.amplify_genes[:5]
            ],
            "suppress_genes": [
                {"gene": g.gene_name, "impact": g.impact_score}
                for g in self.suppress_genes[:5]
            ],
            "explore_genes": self.explore_genes[:5],
            "amplification_rate": self.amplification_rate,
            "suppression_rate": self.suppression_rate,
            "exploration_rate": self.exploration_rate,
            "hypotheses": [h.to_dict() for h in self.hypotheses[:5]],
            "based_on_insights": self.based_on_insights[:10],
            "confidence": round(self.confidence, 3),
        }


# ── Phase 4.2: Creative DNA V2 扩展基因 ──────────────────────

@dataclass
class PsychologyGene:
    """心理基因 — 创意触发的心理机制。

    回答："这个创意在玩家心理上触发了什么？"
    不是表面元素，而是深层的心理驱动力。
    """

    # 核心心理机制
    loss_aversion: float = 0.0         # 害怕损失（"再不救就没了"）
    completion_drive: float = 0.0      # 完成驱动（"集齐就能..."）
    anticipation: float = 0.0          # 期待感（"接下来会发生什么？"）
    social_proof: float = 0.0          # 社会证明（"别人都在玩"）
    scarcity: float = 0.0              # 稀缺性（"限时/限量"）
    mastery: float = 0.0               # 掌控感（"我变强了"）
    belonging: float = 0.0             # 归属感（"这是我的一部分"）

    @property
    def dominant_psychology(self) -> str:
        dims = {
            "loss_aversion": self.loss_aversion,
            "completion_drive": self.completion_drive,
            "anticipation": self.anticipation,
            "social_proof": self.social_proof,
            "scarcity": self.scarcity,
            "mastery": self.mastery,
            "belonging": self.belonging,
        }
        return max(dims, key=dims.get)

    @property
    def psychology_score(self) -> float:
        return round(
            self.loss_aversion * 0.25
            + self.completion_drive * 0.20
            + self.anticipation * 0.15
            + self.social_proof * 0.10
            + self.scarcity * 0.10
            + self.mastery * 0.10
            + self.belonging * 0.10, 1
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "loss_aversion": self.loss_aversion,
            "completion_drive": self.completion_drive,
            "anticipation": self.anticipation,
            "social_proof": self.social_proof,
            "scarcity": self.scarcity,
            "mastery": self.mastery,
            "belonging": self.belonging,
            "dominant_psychology": self.dominant_psychology,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PsychologyGene:
        return cls(
            loss_aversion=float(data.get("loss_aversion", 0)),
            completion_drive=float(data.get("completion_drive", 0)),
            anticipation=float(data.get("anticipation", 0)),
            social_proof=float(data.get("social_proof", 0)),
            scarcity=float(data.get("scarcity", 0)),
            mastery=float(data.get("mastery", 0)),
            belonging=float(data.get("belonging", 0)),
        )


@dataclass
class AudienceGene:
    """受众基因 — 创意吸引的目标人群画像。

    回答："这个创意在向谁说话？"
    """

    # 人口统计
    target_gender: str = "all"          # male / female / all
    target_age_range: str = "25-44"     # 18-24 / 25-44 / 45+
    target_platform: str = "all"        # ios / android / all

    # 玩家画像
    collector_score: float = 0.0        # 收藏家倾向
    progression_score: float = 0.0      # 进度党倾向
    power_score: float = 0.0            # 实力党倾向
    explorer_score: float = 0.0         # 探索者倾向
    casual_score: float = 0.0           # 休闲玩家倾向

    # 使用场景
    use_context: str = "anytime"        # anytime / evening / commute / weekend
    session_type: str = "casual"        # casual / deep / competitive

    @property
    def primary_audience(self) -> str:
        dims = {
            "collector": self.collector_score,
            "progression": self.progression_score,
            "power": self.power_score,
            "explorer": self.explorer_score,
            "casual": self.casual_score,
        }
        return max(dims, key=dims.get)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_gender": self.target_gender,
            "target_age_range": self.target_age_range,
            "target_platform": self.target_platform,
            "collector_score": round(self.collector_score, 2),
            "progression_score": round(self.progression_score, 2),
            "power_score": round(self.power_score, 2),
            "explorer_score": round(self.explorer_score, 2),
            "casual_score": round(self.casual_score, 2),
            "use_context": self.use_context,
            "session_type": self.session_type,
            "primary_audience": self.primary_audience,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AudienceGene:
        return cls(
            target_gender=data.get("target_gender", "all"),
            target_age_range=data.get("target_age_range", "25-44"),
            target_platform=data.get("target_platform", "all"),
            collector_score=float(data.get("collector_score", 0)),
            progression_score=float(data.get("progression_score", 0)),
            power_score=float(data.get("power_score", 0)),
            explorer_score=float(data.get("explorer_score", 0)),
            casual_score=float(data.get("casual_score", 0)),
            use_context=data.get("use_context", "anytime"),
            session_type=data.get("session_type", "casual"),
        )


@dataclass
class ContextGene:
    """场景基因 — 创意投放的时机与场景。

    回答："这个创意在什么场景下最有说服力？"
    """

    # 时间场景
    time_of_day: str = "anytime"        # morning / afternoon / evening / night / anytime
    day_of_week: str = "any"           # weekday / weekend / any

    # 情绪场景
    mood: str = "neutral"              # relaxed / bored / stressed / excited / neutral
    attention_level: str = "low"       # low / medium / high

    # 市场场景
    market_lifecycle: str = "growth"   # launch / growth / mature / decline
    competitor_activity: str = "normal"  # low / normal / intense

    # 创意生命周期
    creative_age: str = "fresh"        # fresh / proven / fatigue / retired

    @property
    def is_evening_creative(self) -> bool:
        return self.time_of_day in ("evening", "night")

    @property
    def is_relaxation_context(self) -> bool:
        return self.mood == "relaxed" and self.attention_level == "low"

    def to_dict(self) -> dict[str, Any]:
        return {
            "time_of_day": self.time_of_day,
            "day_of_week": self.day_of_week,
            "mood": self.mood,
            "attention_level": self.attention_level,
            "market_lifecycle": self.market_lifecycle,
            "competitor_activity": self.competitor_activity,
            "creative_age": self.creative_age,
            "is_evening_creative": self.is_evening_creative,
            "is_relaxation_context": self.is_relaxation_context,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContextGene:
        return cls(
            time_of_day=data.get("time_of_day", "anytime"),
            day_of_week=data.get("day_of_week", "any"),
            mood=data.get("mood", "neutral"),
            attention_level=data.get("attention_level", "low"),
            market_lifecycle=data.get("market_lifecycle", "growth"),
            competitor_activity=data.get("competitor_activity", "normal"),
            creative_age=data.get("creative_age", "fresh"),
        )


# ── Phase 4.2: Creative DNA V2 聚合 ─────────────────────────

@dataclass
class CreativeDNAV2:
    """Creative DNA V2 — 7 基因完整基因组。

    升级自 Creative DNA V1（4 基因），新增：
      - Psychology Gene: 心理机制
      - Audience Gene:   目标人群
      - Context Gene:    投放场景
    """

    creative_id: str = ""

    # V1 基因
    visual_gene: dict[str, Any] = field(default_factory=dict)
    hook_gene: dict[str, Any] = field(default_factory=dict)
    gameplay_gene: dict[str, Any] = field(default_factory=dict)
    monetization_gene: dict[str, Any] = field(default_factory=dict)

    # V2 新增基因
    psychology_gene: PsychologyGene = field(default_factory=PsychologyGene)
    audience_gene: AudienceGene = field(default_factory=AudienceGene)
    context_gene: ContextGene = field(default_factory=ContextGene)

    @property
    def gene_count(self) -> int:
        return 7

    @property
    def dominant_psychology(self) -> str:
        return self.psychology_gene.dominant_psychology

    @property
    def primary_audience(self) -> str:
        return self.audience_gene.primary_audience

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "genes": {
                "visual": self.visual_gene,
                "hook": self.hook_gene,
                "gameplay": self.gameplay_gene,
                "monetization": self.monetization_gene,
                "psychology": self.psychology_gene.to_dict(),
                "audience": self.audience_gene.to_dict(),
                "context": self.context_gene.to_dict(),
            },
            "dominant_psychology": self.dominant_psychology,
            "primary_audience": self.primary_audience,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CreativeDNAV2:
        genes = data.get("genes", {})
        return cls(
            creative_id=data.get("creative_id", ""),
            visual_gene=genes.get("visual", {}),
            hook_gene=genes.get("hook", {}),
            gameplay_gene=genes.get("gameplay", {}),
            monetization_gene=genes.get("monetization", {}),
            psychology_gene=PsychologyGene.from_dict(genes.get("psychology", {})),
            audience_gene=AudienceGene.from_dict(genes.get("audience", {})),
            context_gene=ContextGene.from_dict(genes.get("context", {})),
        )