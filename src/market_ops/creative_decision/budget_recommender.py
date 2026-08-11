"""Module 5: Budget Recommendation
Module 6: Placement Recommendation
Module 7: Campaign Recommendation

根据 Overall Score、Performance、Risk 推荐预算、版位和 Campaign 类型。
"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class BudgetRecommendation:
    variant_id: str
    tier: str                           # S/A/B/C
    daily_budget_usd: float = 0.0
    test_budget_usd: float = 0.0
    reasoning: str = ""


@dataclass
class PlacementRecommendation:
    variant_id: str
    primary: str = ""                   # 首选版位
    secondary: list[str] = field(default_factory=list)         # 次选版位
    avoid: list[str] = field(default_factory=list)             # 避免版位
    reasoning: str = ""


@dataclass
class CampaignRecommendation:
    variant_id: str
    campaign_type: str = ""             # ASC/AEO/VO/AAA/ROAS
    objective: str = ""                 # INSTALL/AEO/VO/ROAS
    reasoning: str = ""


class BudgetPlacementCampaignRecommender:
    """预算 + 版位 + Campaign 推荐器
    
    预算分层：
    - S (Score >= 85): $300-500/day，优先测试
    - A (Score 75-84): $150-300/day
    - B (Score 65-74): $50-150/day
    - C (Score 60-64): $30-50/day，谨慎测试
    - Discard (<60): $0
    
    版位推荐：
    - 9:16 竖版 + 主体大 → IG_Reels (首选), FB_Reels, IG_Stories
    - 1:1 方版 → FB_Feed, IG_Feed
    - 4:5 竖版 → FB_Feed, IG_Feed
    - 主体小/文字多 → Audience Network (避免)
    - 节奏快/Hook强 → Reels 系列
    - 节奏慢/展示型 → Feed 系列
    
    Campaign 推荐：
    - Collection Hook + 高 Gameplay → AEO (App Event Optimization)
    - Collection Hook + 高 Brand → VO (Value Optimization)
    - 全新 Creative + 未知表现 → ASC (Advantage+ Shopping Campaign)
    - 已验证 Creative → AAA (Automated App Ads)
    - ROAS 导向 → ROAS Campaign
    """

    def recommend_budget(self, variant: dict) -> BudgetRecommendation:
        score = variant.get("overall_score", 0.0)
        vid = variant.get("variant_id", "")

        if score >= 85:
            return BudgetRecommendation(
                variant_id=vid,
                tier="S",
                daily_budget_usd=400.0,
                test_budget_usd=2000.0,
                reasoning=f"Score {score:.1f} >= 85，属于 S 级，优先测试，每日预算 $400，测试预算 $2000",
            )
        elif score >= 75:
            return BudgetRecommendation(
                variant_id=vid,
                tier="A",
                daily_budget_usd=225.0,
                test_budget_usd=1125.0,
                reasoning=f"Score {score:.1f} 在 75-84 之间，属于 A 级，每日预算 $225，测试预算 $1125",
            )
        elif score >= 65:
            return BudgetRecommendation(
                variant_id=vid,
                tier="B",
                daily_budget_usd=100.0,
                test_budget_usd=500.0,
                reasoning=f"Score {score:.1f} 在 65-74 之间，属于 B 级，每日预算 $100，测试预算 $500",
            )
        elif score >= 60:
            return BudgetRecommendation(
                variant_id=vid,
                tier="C",
                daily_budget_usd=40.0,
                test_budget_usd=200.0,
                reasoning=f"Score {score:.1f} 在 60-64 之间，属于 C 级，谨慎测试，每日预算 $40，测试预算 $200",
            )
        else:
            return BudgetRecommendation(
                variant_id=vid,
                tier="Discard",
                daily_budget_usd=0.0,
                test_budget_usd=0.0,
                reasoning=f"Score {score:.1f} < 60，建议 Discard，不分配预算",
            )

    def recommend_placement(self, variant: dict) -> PlacementRecommendation:
        vid = variant.get("variant_id", "")

        aspect_ratio = variant.get("aspect_ratio", "")
        subject_size = variant.get("subject_size", "")  # large / small
        text_heavy = variant.get("text_heavy", False)
        pace = variant.get("pace", "")  # fast / slow
        hook_strength = variant.get("hook_strength", "")

        primary = ""
        secondary = []
        avoid = []
        reasons = []

        # 根据比例判断
        if aspect_ratio == "9:16":
            if subject_size == "large":
                primary = "IG_Reels"
                secondary = ["FB_Reels", "IG_Stories"]
                reasons.append("9:16 竖版 + 主体大，适合 Reels 系列")
            else:
                primary = "FB_Reels"
                secondary = ["IG_Stories"]
                reasons.append("9:16 竖版但主体不大，适合 Reels 与 Stories")
        elif aspect_ratio == "1:1":
            primary = "FB_Feed"
            secondary = ["IG_Feed"]
            reasons.append("1:1 方版，适合 Feed 系列")
        elif aspect_ratio == "4:5":
            primary = "FB_Feed"
            secondary = ["IG_Feed"]
            reasons.append("4:5 竖版，适合 Feed 系列")
        else:
            primary = "FB_Feed"
            secondary = ["IG_Feed", "IG_Reels"]
            reasons.append("未识别比例，默认 Feed 系列")

        # 节奏与 Hook
        if pace == "fast" or hook_strength in ("strong", "high"):
            if primary not in ("IG_Reels", "FB_Reels"):
                secondary = ["IG_Reels"] + secondary
            reasons.append("节奏快/Hook强，推荐 Reels 系列")
        elif pace == "slow":
            reasons.append("节奏慢/展示型，Feed 系列更合适")

        # 主体小/文字多
        if subject_size == "small" or text_heavy:
            avoid.append("Audience Network")
            reasons.append("主体小或文字多，避免 Audience Network")

        # 去重
        seen = set()
        deduped_secondary = []
        for p in secondary:
            if p != primary and p not in seen:
                deduped_secondary.append(p)
                seen.add(p)

        return PlacementRecommendation(
            variant_id=vid,
            primary=primary,
            secondary=deduped_secondary,
            avoid=avoid,
            reasoning="；".join(reasons),
        )

    def recommend_campaign(self, variant: dict) -> CampaignRecommendation:
        vid = variant.get("variant_id", "")
        hook_type = variant.get("hook_type", "")
        gameplay_score = variant.get("gameplay_score", 0.0)
        brand_score = variant.get("brand_score", 0.0)
        verified = variant.get("verified", False)
        roas_focused = variant.get("roas_focused", False)

        reasons = []

        if roas_focused:
            return CampaignRecommendation(
                variant_id=vid,
                campaign_type="ROAS",
                objective="ROAS",
                reasoning="ROAS 导向，直接跑 ROAS Campaign",
            )

        if hook_type == "collection":
            if gameplay_score >= brand_score:
                campaign_type = "AEO"
                objective = "AEO"
                reasons.append("Collection Hook + 高 Gameplay，选 AEO (App Event Optimization)")
            else:
                campaign_type = "VO"
                objective = "VO"
                reasons.append("Collection Hook + 高 Brand，选 VO (Value Optimization)")
        else:
            if verified:
                campaign_type = "AAA"
                objective = "INSTALL"
                reasons.append("已验证 Creative，选 AAA (Automated App Ads)")
            else:
                campaign_type = "ASC"
                objective = "INSTALL"
                reasons.append("全新 Creative + 未知表现，选 ASC (Advantage+ Shopping Campaign)")

        return CampaignRecommendation(
            variant_id=vid,
            campaign_type=campaign_type,
            objective=objective,
            reasoning="；".join(reasons),
        )

    def recommend_all(self, variant: dict) -> dict:
        """一次返回所有推荐"""
        return {
            "budget": self.recommend_budget(variant),
            "placement": self.recommend_placement(variant),
            "campaign": self.recommend_campaign(variant),
        }
