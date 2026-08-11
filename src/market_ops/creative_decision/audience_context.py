"""Module 2: Audience Context Engine

评分不能脱离 Facebook Audience 上下文。
根据不同市场、人群、版位重新排序创意。

例如：
- 美国：Cute Dragon Score 94
- 德国：Cute Dragon Score 76
- 英国：Magic Castle Score 91
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AudienceScore:
    variant_id: str
    context: str                      # e.g. "US_25-45_F"
    base_score: float = 0.0
    adjusted_score: float = 0.0
    factors: dict = field(default_factory=dict)


class AudienceContextEngine:
    """受众上下文引擎
    
    支持的上下文维度：
    - Country: US, UK, DE, JP, KR, BR, etc.
    - Age: 18-24, 25-34, 35-44, 45+
    - Gender: M, F
    - Placement: FB_Feed, IG_Feed, IG_Reels, FB_Reels, Audience_Network
    - OS: iOS, Android
    - Campaign Objective: Install, AEO, VO, ROAS, AAA
    
    调整规则（基于 Merge Witches 游戏数据）：
    - US: 喜欢可爱生物 (+10 Dragon, +5 Cat)
    - DE: 喜欢魔法氛围 (+10 Castle, +5 Forest)
    - JP: 喜欢 Q版角色 (+15 Chibi, +5 Kawaii)
    - iOS: CTR 通常高 15% → 对 Hook 要求更高
    - IG_Reels: 需要更强的前3秒 → Hook 权重+20%
    """

    # 市场偏好映射
    COUNTRY_PREFS = {
        "US": {"creature": {"dragon": +10, "cat": +5, "unicorn": +8}, "theme": {"cute": +10}},
        "UK": {"creature": {"fairy": +10, "owl": +5}, "theme": {"magical": +10}},
        "DE": {"creature": {"phoenix": +8, "dragon": +5}, "theme": {"epic": +10}},
        "JP": {"creature": {"cat": +15, "fox": +10}, "theme": {"kawaii": +15, "chibi": +15}},
        "KR": {"creature": {"dragon": +10, "fox": +8}, "theme": {"cute": +10}},
        "BR": {"creature": {"cat": +10, "owl": +5}, "theme": {"colorful": +10}},
    }

    # 版位调整系数
    PLACEMENT_ADJUSTMENTS = {
        "FB_Feed": {"hook_multiplier": 1.0, "readability_multiplier": 1.0, "theme_bonus": 0},
        "IG_Feed": {"hook_multiplier": 1.05, "readability_multiplier": 1.05, "theme_bonus": 0},
        "IG_Reels": {"hook_multiplier": 1.20, "readability_multiplier": 1.10, "theme_bonus": +5},
        "FB_Reels": {"hook_multiplier": 1.15, "readability_multiplier": 1.05, "theme_bonus": +3},
        "Audience_Network": {"hook_multiplier": 0.95, "readability_multiplier": 0.95, "theme_bonus": -3},
    }

    # OS 调整
    OS_ADJUSTMENTS = {
        "iOS": {"hook_threshold_boost": +5, "quality_premium": +3},
        "Android": {"hook_threshold_boost": 0, "quality_premium": 0},
    }

    # 年龄段偏好
    AGE_PREFS = {
        "18-24": {"creature": {"cat": +5, "fox": +5}, "theme": {"trendy": +5, "kawaii": +5}},
        "25-34": {"creature": {"dragon": +5, "unicorn": +5}, "theme": {"cute": +5, "magical": +3}},
        "35-44": {"creature": {"owl": +5, "phoenix": +5}, "theme": {"epic": +5, "magical": +5}},
        "45+": {"creature": {"dragon": +3}, "theme": {"calm": +5, "nostalgic": +5}},
    }

    # 性别偏好
    GENDER_PREFS = {
        "F": {"creature": {"cat": +5, "unicorn": +5, "fairy": +5}, "theme": {"cute": +5, "kawaii": +5, "colorful": +3}},
        "M": {"creature": {"dragon": +5, "phoenix": +5, "fox": +3}, "theme": {"epic": +5, "competitive": +3}},
    }

    # Campaign Objective 对维度权重的调整
    OBJECTIVE_DIM_WEIGHTS = {
        "Install": {"hook": 0.35, "gameplay": 0.25, "brand": 0.20, "novelty": 0.20},
        "AEO": {"hook": 0.25, "gameplay": 0.30, "brand": 0.30, "novelty": 0.15},
        "VO": {"hook": 0.20, "gameplay": 0.35, "brand": 0.30, "novelty": 0.15},
        "ROAS": {"hook": 0.20, "gameplay": 0.30, "brand": 0.35, "novelty": 0.15},
        "AAA": {"hook": 0.30, "gameplay": 0.30, "brand": 0.25, "novelty": 0.15},
    }

    def score_for_context(self, variant: dict, context: dict) -> AudienceScore:
        """计算 variant 在特定受众上下文下的分数
        
        Args:
            variant: ranking.json 中的单个 variant
            context: {"country": "US", "age": "25-34", "gender": "F", "placement": "IG_Reels", "os": "iOS"}
        """
        variant_id = variant.get("variant_id", "unknown")
        base_score = variant.get("overall_score", 50.0)
        dimensions = variant.get("dimensions", {})
        modified_dna = variant.get("modified_dna", {})

        # 提取 DNA 特征
        dna_features = self._extract_dna_features(modified_dna)

        # 初始化调整
        adjustment = 0.0
        factors = {}

        # 1. 国家/市场调整
        country = context.get("country", "")
        if country in self.COUNTRY_PREFS:
            country_bonus = self._compute_preference_bonus(dna_features, self.COUNTRY_PREFS[country])
            adjustment += country_bonus
            factors["country"] = {"market": country, "bonus": round(country_bonus, 1)}

        # 2. 年龄段调整
        age = context.get("age", "")
        if age in self.AGE_PREFS:
            age_bonus = self._compute_preference_bonus(dna_features, self.AGE_PREFS[age])
            adjustment += age_bonus
            factors["age"] = {"group": age, "bonus": round(age_bonus, 1)}

        # 3. 性别调整
        gender = context.get("gender", "")
        if gender in self.GENDER_PREFS:
            gender_bonus = self._compute_preference_bonus(dna_features, self.GENDER_PREFS[gender])
            adjustment += gender_bonus
            factors["gender"] = {"group": gender, "bonus": round(gender_bonus, 1)}

        # 4. 版位调整
        placement = context.get("placement", "")
        placement_adj = self.PLACEMENT_ADJUSTMENTS.get(placement, {})
        if placement_adj:
            # 版位对 Hook 要求更高/更低
            hook_score = dimensions.get("facebook_hook", {}).get("score", 50.0)
            hook_multiplier = placement_adj.get("hook_multiplier", 1.0)
            readability_score = dimensions.get("visual_readability", {}).get("score", 50.0)
            readability_multiplier = placement_adj.get("readability_multiplier", 1.0)

            # 计算版位带来的分数偏移
            placement_bonus = (
                (hook_score * (hook_multiplier - 1.0) * 0.5)
                + (readability_score * (readability_multiplier - 1.0) * 0.3)
                + placement_adj.get("theme_bonus", 0)
            )
            adjustment += placement_bonus
            factors["placement"] = {
                "placement": placement,
                "hook_multiplier": hook_multiplier,
                "readability_multiplier": readability_multiplier,
                "bonus": round(placement_bonus, 1),
            }

        # 5. OS 调整
        os = context.get("os", "")
        os_adj = self.OS_ADJUSTMENTS.get(os, {})
        if os_adj:
            # iOS 用户对质量更敏感，Brand 和 Readability 分数高的素材获益
            brand_score = dimensions.get("brand_consistency", {}).get("score", 50.0)
            readability_score = dimensions.get("visual_readability", {}).get("score", 50.0)
            quality_premium = os_adj.get("quality_premium", 0)
            os_bonus = ((brand_score - 50) * 0.05 + (readability_score - 50) * 0.03) + quality_premium
            adjustment += os_bonus
            factors["os"] = {"os": os, "bonus": round(os_bonus, 1)}

        # 6. Campaign Objective 调整
        objective = context.get("objective", "")
        obj_weights = self.OBJECTIVE_DIM_WEIGHTS.get(objective, {})
        if obj_weights:
            # 重新按 objective 加权计算一个偏移分
            hook = dimensions.get("facebook_hook", {}).get("score", 50.0)
            gameplay = dimensions.get("gameplay_consistency", {}).get("score", 50.0)
            brand = dimensions.get("brand_consistency", {}).get("score", 50.0)
            novelty = dimensions.get("novelty", {}).get("score", 50.0)

            # 默认权重
            default_weights = {"hook": 0.25, "gameplay": 0.25, "brand": 0.25, "novelty": 0.25}
            obj_score = (
                hook * obj_weights.get("hook", 0.25)
                + gameplay * obj_weights.get("gameplay", 0.25)
                + brand * obj_weights.get("brand", 0.25)
                + novelty * obj_weights.get("novelty", 0.25)
            )
            default_score = (
                hook * default_weights["hook"]
                + gameplay * default_weights["gameplay"]
                + brand * default_weights["brand"]
                + novelty * default_weights["novelty"]
            )
            objective_bonus = (obj_score - default_score) * 0.5
            adjustment += objective_bonus
            factors["objective"] = {
                "objective": objective,
                "bonus": round(objective_bonus, 1),
            }

        # 计算调整后分数
        adjusted_score = max(0.0, min(100.0, base_score + adjustment))

        # 生成上下文标识
        context_parts = [str(v) for k, v in context.items() if v]
        context_str = "_".join(context_parts) if context_parts else "default"

        factors["base_score"] = base_score
        factors["total_adjustment"] = round(adjustment, 1)
        factors["dna_features"] = dna_features

        return AudienceScore(
            variant_id=variant_id,
            context=context_str,
            base_score=round(base_score, 1),
            adjusted_score=round(adjusted_score, 1),
            factors=factors,
        )

    def rerank_for_context(self, rankings: list[dict], context: dict) -> list[AudienceScore]:
        """按受众上下文重新排序"""
        scored = [self.score_for_context(r, context) for r in rankings]
        scored.sort(key=lambda x: x.adjusted_score, reverse=True)
        return scored

    def _extract_dna_features(self, modified_dna: dict) -> dict:
        """从 modified_dna 中提取用于偏好匹配的特征"""
        features = {
            "creatures": [],
            "themes": [],
            "environment": "",
            "hook_type": "",
            "character_type": "",
            "style": "",
        }

        if not modified_dna:
            return features

        # 生物类型
        creatures = modified_dna.get("creatures", [])
        if creatures and isinstance(creatures, list):
            for c in creatures:
                if isinstance(c, dict):
                    creature_type = c.get("type", "")
                    if creature_type:
                        features["creatures"].append(str(creature_type).lower())
        elif isinstance(creatures, dict):
            creature_type = creatures.get("type", "")
            if creature_type:
                features["creatures"].append(str(creature_type).lower())

        # 环境
        env = modified_dna.get("environment", {})
        if isinstance(env, dict):
            features["environment"] = str(env.get("type", "")).lower()
        else:
            features["environment"] = str(env).lower()

        # Hook 类型
        hook = modified_dna.get("hook", {})
        if isinstance(hook, dict):
            features["hook_type"] = str(hook.get("type", "")).lower()
        else:
            features["hook_type"] = str(hook).lower()

        # 角色类型
        character = modified_dna.get("character", {})
        if isinstance(character, dict):
            features["character_type"] = str(character.get("type", "")).lower()
        else:
            features["character_type"] = str(character).lower()

        # 风格/色调主题
        colors = modified_dna.get("colors", {})
        if isinstance(colors, dict):
            mood_palette = colors.get("mood_palette", [])
            if isinstance(mood_palette, list):
                features["themes"] = [str(m).lower() for m in mood_palette]
            else:
                features["themes"] = [str(mood_palette).lower()]
        style = modified_dna.get("style", "")
        if style:
            features["style"] = str(style).lower()

        # 从 lighting 和 composition 补充主题关键词
        lighting = modified_dna.get("lighting", {})
        if isinstance(lighting, dict):
            temp = lighting.get("color_temperature", "")
            if temp:
                features["themes"].append(str(temp).lower())
            effects = lighting.get("special_effects", [])
            if isinstance(effects, list):
                features["themes"].extend([str(e).lower() for e in effects])

        return features

    def _compute_preference_bonus(self, dna_features: dict, prefs: dict) -> float:
        """根据 DNA 特征和偏好映射计算加分"""
        bonus = 0.0

        # 生物偏好匹配
        creature_prefs = prefs.get("creature", {})
        for creature in dna_features.get("creatures", []):
            for pref_creature, value in creature_prefs.items():
                if pref_creature.lower() in creature or creature in pref_creature.lower():
                    bonus += value

        # 主题偏好匹配
        theme_prefs = prefs.get("theme", {})
        for theme in dna_features.get("themes", []):
            for pref_theme, value in theme_prefs.items():
                if pref_theme.lower() in theme or theme in pref_theme.lower():
                    bonus += value

        # 环境偏好匹配（简单关键词）
        env = dna_features.get("environment", "")
        for pref_creature, value in creature_prefs.items():
            if pref_creature.lower() in env:
                bonus += value * 0.5
        for pref_theme, value in theme_prefs.items():
            if pref_theme.lower() in env:
                bonus += value * 0.5

        return bonus
