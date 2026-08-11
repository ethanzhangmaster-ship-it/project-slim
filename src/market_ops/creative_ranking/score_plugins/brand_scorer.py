from .base_scorer import BaseScorer, ScoreResult


class BrandScorer(BaseScorer):
    """Brand Consistency - 品牌一致性评分

    逻辑：
    - 角色是否还是女巫/可爱系（Merge Witches风格）
    - 色彩是否保持魔法系（紫/蓝/金）
    - 是否还能看出是Merge Witches
    - Logo位置是否保持
    - 世界观是否一致（魔法森林、可爱生物）

    评分因素：
    - 角色一致性: +20
    - 画风一致性: +20
    - 色调一致性: +15
    - Hook一致性: +15
    - Merge Witches特征: +15
    - Logo位置: +15
    """

    name = "Brand Consistency"
    weight_key = "brand_consistency"

    # 魔法系角色关键词
    _MAGIC_CHARACTER_KEYWORDS = {
        "witch", "wizard", "mage", "sorcerer", "sorceress", "enchantress",
        "fairy", "fairy_queen", "warlock", "magical", "cute", "girl", "boy",
    }
    # 魔法系色调关键词
    _MAGIC_COLOR_KEYWORDS = {
        "purple", "blue", "gold", "lavender", "mysterious_blue", "enchanted",
        "glowing_gold", "dark_purple", "blue_gold", "warm_gold", "cool",
        "mysterious", "moonlit", "magic",
    }
    # Merge Witches 核心特征词
    _MW_CORE_KEYWORDS = {
        "witch", "merge", "witches", "magic", "magical", "enchanted",
        "mystical", "spell", "potion", "cute", "adorable", "kawaii",
    }
    # 3D/可爱画风关键词
    _STYLE_CONSISTENT_KEYWORDS = {
        "3d render", "3d", "cute", "cartoon", "anime", "chibi", "stylized",
    }
    # Merge Witches 世界观关键词
    _MW_WORLD_KEYWORDS = {
        "magic_forest", "crystal_cave", "moon_lake", "magic_garden",
        "star_tower", "sky_island", "mushroom_village", "vineyard",
        "forest", "magic", "enchanted", "mystical", "fairy",
    }

    def score(
        self,
        variant_dna: dict,
        base_dna: dict,
        fb_meta: dict | None = None,
    ) -> ScoreResult:
        score = 0.0
        breakdown: dict = {}
        recommendations: list[str] = []
        risks: list[str] = []
        raw_features: dict = {}

        # ---- 1. 角色一致性 (+20) ----
        v_identity = str(self._safe_get(variant_dna, ["identity"]) or "").lower()
        b_identity = str(self._safe_get(base_dna, ["identity"]) or "").lower()
        v_char_type = str(self._safe_get(variant_dna, ["character", "type"]) or "").lower()
        b_char_type = str(self._safe_get(base_dna, ["character", "type"]) or "").lower()

        raw_features["variant_identity"] = v_identity
        raw_features["base_identity"] = b_identity
        raw_features["variant_character_type"] = v_char_type
        raw_features["base_character_type"] = b_char_type

        char_score = 0.0
        if v_identity and b_identity and v_identity == b_identity:
            char_score = 20.0
            breakdown["character_consistency"] = {"score": 20.0, "reason": f"角色完全一致({v_identity})"}
        elif v_char_type and b_char_type and v_char_type == b_char_type:
            char_score = 18.0
            breakdown["character_consistency"] = {"score": 18.0, "reason": f"角色类型一致({v_char_type})"}
        elif self._has_keyword(v_identity, self._MAGIC_CHARACTER_KEYWORDS) or \
             self._has_keyword(v_char_type, self._MAGIC_CHARACTER_KEYWORDS):
            char_score = 12.0
            breakdown["character_consistency"] = {"score": 12.0, "reason": f"角色变化但保留魔法/可爱系特征({v_identity or v_char_type})"}
            risks.append("角色已变更，虽仍属魔法系，但品牌辨识度可能下降")
            recommendations.append("如变更角色，建议在服装或道具上保留女巫标志性元素以维持品牌认知")
        else:
            char_score = 3.0
            breakdown["character_consistency"] = {"score": 3.0, "reason": f"角色偏离魔法系({v_identity or v_char_type})"}
            risks.append("角色严重偏离Merge Witches的魔法/可爱系定位，品牌断裂风险极高")
            recommendations.append("强烈建议将角色改回女巫、法师或可爱系角色，避免用户认知混淆")
        score += char_score

        # ---- 2. 画风一致性 (+20) ----
        v_style = str(self._safe_get(variant_dna, ["style"]) or "").lower()
        b_style = str(self._safe_get(base_dna, ["style"]) or "").lower()
        raw_features["variant_style"] = v_style
        raw_features["base_style"] = b_style

        style_score = 0.0
        if v_style and b_style and v_style == b_style:
            style_score = 20.0
            breakdown["style_consistency"] = {"score": 20.0, "reason": f"画风完全一致({v_style})"}
        elif self._has_keyword(v_style, self._STYLE_CONSISTENT_KEYWORDS) and \
             self._has_keyword(b_style, self._STYLE_CONSISTENT_KEYWORDS):
            style_score = 16.0
            breakdown["style_consistency"] = {"score": 16.0, "reason": f"画风不同但同属3D/可爱系({v_style} vs {b_style})"}
            recommendations.append("画风微调可接受，但需确保渲染质感与Base保持一致")
        elif self._has_keyword(v_style, self._STYLE_CONSISTENT_KEYWORDS):
            style_score = 10.0
            breakdown["style_consistency"] = {"score": 10.0, "reason": f"画风变化但仍是3D/可爱系({v_style})"}
            risks.append("画风已变化，虽然仍是3D/可爱系，但老用户可能感到违和")
            recommendations.append("建议在小范围受众中测试画风变化对留存的影响")
        else:
            style_score = 3.0
            breakdown["style_consistency"] = {"score": 3.0, "reason": f"画风严重偏离({v_style})"}
            risks.append("画风严重偏离Base，可能导致用户下载后发现实际游戏不符，引发差评或高卸载率")
            recommendations.append("画风必须拉回3D cute render方向，保持与游戏本体一致")
        score += style_score

        # ---- 3. 色调一致性 (+15) ----
        v_lighting = str(self._safe_get(variant_dna, ["lighting"]) or "").lower()
        b_lighting = str(self._safe_get(base_dna, ["lighting"]) or "").lower()
        v_color_mood = str(self._safe_get(variant_dna, ["colors", "mood_palette"]) or "").lower()
        b_color_mood = str(self._safe_get(base_dna, ["colors", "mood_palette"]) or "").lower()
        v_lighting_temp = str(self._safe_get(variant_dna, ["lighting", "color_temperature"]) or "").lower()
        b_lighting_temp = str(self._safe_get(base_dna, ["lighting", "color_temperature"]) or "").lower()

        raw_features["variant_lighting"] = v_lighting
        raw_features["base_lighting"] = b_lighting
        raw_features["variant_color_mood"] = v_color_mood
        raw_features["base_color_mood"] = b_color_mood

        color_score = 0.0
        lighting_match = v_lighting and b_lighting and v_lighting == b_lighting
        mood_match = v_color_mood and b_color_mood and v_color_mood == b_color_mood
        temp_match = v_lighting_temp and b_lighting_temp and v_lighting_temp == b_lighting_temp

        if lighting_match or mood_match or temp_match:
            color_score = 15.0
            breakdown["color_consistency"] = {"score": 15.0, "reason": "色调/光照/色温至少一项完全一致"}
        elif (self._has_keyword(v_lighting, self._MAGIC_COLOR_KEYWORDS) or
              self._has_keyword(v_color_mood, self._MAGIC_COLOR_KEYWORDS) or
              self._has_keyword(v_lighting_temp, self._MAGIC_COLOR_KEYWORDS)):
            color_score = 10.0
            breakdown["color_consistency"] = {"score": 10.0, "reason": f"色调变化但保留魔法色系({v_lighting or v_color_mood or v_lighting_temp})"}
            recommendations.append("色调微调可接受，但建议保持紫/蓝/金为主基调以强化品牌记忆")
        else:
            color_score = 4.0
            breakdown["color_consistency"] = {"score": 4.0, "reason": f"色调严重偏离魔法系({v_lighting or v_color_mood or v_lighting_temp})"}
            risks.append("色调偏离魔法系（紫/蓝/金），品牌色彩记忆点丧失")
            recommendations.append("请将主色调调回紫色、神秘蓝或金色系，保持Merge Witches的魔法氛围")
        score += color_score

        # ---- 4. Hook一致性 (+15) ----
        v_hook = str(self._safe_get(variant_dna, ["hook"]) or "").lower()
        b_hook = str(self._safe_get(base_dna, ["hook"]) or "").lower()
        v_hook_type = str(self._safe_get(variant_dna, ["hook", "type"]) or "").lower()
        b_hook_type = str(self._safe_get(base_dna, ["hook", "type"]) or "").lower()

        raw_features["variant_hook"] = v_hook
        raw_features["base_hook"] = b_hook
        raw_features["variant_hook_type"] = v_hook_type
        raw_features["base_hook_type"] = b_hook_type

        hook_score = 0.0
        if (v_hook and b_hook and v_hook == b_hook) or (v_hook_type and b_hook_type and v_hook_type == b_hook_type):
            hook_score = 15.0
            breakdown["hook_consistency"] = {"score": 15.0, "reason": f"Hook完全一致({v_hook_type or v_hook})"}
        elif (v_hook_type and b_hook_type and
              self._same_hook_family(v_hook_type, b_hook_type)):
            hook_score = 10.0
            breakdown["hook_consistency"] = {"score": 10.0, "reason": f"Hook类型不同但同属一个家族({v_hook_type} vs {b_hook_type})"}
            recommendations.append("Hook类型微调可接受，但需确保仍能有效驱动滚动停留")
        else:
            hook_score = 5.0
            breakdown["hook_consistency"] = {"score": 5.0, "reason": f"Hook类型变化({v_hook_type or v_hook} vs {b_hook_type or b_hook})"}
            risks.append("Hook类型变化可能导致已验证的停留逻辑失效")
            recommendations.append("如变更Hook，请务必在小预算下验证3秒停留率和完播率")
        score += hook_score

        # ---- 5. Merge Witches特征 (+15) ----
        mw_text = " ".join([
            v_identity, v_char_type, v_style, v_hook, v_hook_type,
            str(self._safe_get(variant_dna, ["scene"]) or "").lower(),
            str(self._safe_get(variant_dna, ["environment", "type"]) or "").lower(),
        ])
        raw_features["mw_feature_text"] = mw_text.strip()

        mw_score = 0.0
        mw_matches = [kw for kw in self._MW_CORE_KEYWORDS if kw in mw_text]
        world_matches = [kw for kw in self._MW_WORLD_KEYWORDS if kw in mw_text]
        if len(mw_matches) >= 3:
            mw_score = 15.0
            breakdown["mw_identity"] = {"score": 15.0, "reason": f"强Merge Witches特征（命中{len(mw_matches)}个核心词）"}
        elif len(mw_matches) >= 2 or (len(mw_matches) >= 1 and len(world_matches) >= 2):
            mw_score = 10.0
            breakdown["mw_identity"] = {"score": 10.0, "reason": f"保留Merge Witches核心特征（命中{len(mw_matches)}个核心词,{len(world_matches)}个世界观词）"}
            recommendations.append("建议在世界观或角色上增加1-2个Merge Witches标志性元素，强化品牌辨识度")
        elif len(mw_matches) >= 1:
            mw_score = 6.0
            breakdown["mw_identity"] = {"score": 6.0, "reason": f"Merge Witches特征较弱（仅命中{len(mw_matches)}个核心词）"}
            risks.append("Merge Witches品牌特征不足，用户可能无法一眼认出是Merge Witches广告")
            recommendations.append("建议在画面中加入女巫、合成、魔法森林等标志性视觉锚点")
        else:
            mw_score = 1.0
            breakdown["mw_identity"] = {"score": 1.0, "reason": "几乎无Merge Witches特征"}
            risks.append("该变体几乎看不出是Merge Witches广告，品牌资产严重流失")
            recommendations.append("必须加入女巫角色、魔法合成玩法或魔法森林场景等核心品牌符号")
        score += mw_score

        # ---- 6. Logo位置 (+15) ----
        v_logo = str(self._safe_get(variant_dna, ["logo", "position"]) or "").lower()
        b_logo = str(self._safe_get(base_dna, ["logo", "position"]) or "").lower()
        raw_features["variant_logo_position"] = v_logo
        raw_features["base_logo_position"] = b_logo

        logo_score = 0.0
        if v_logo and b_logo:
            if v_logo == b_logo:
                logo_score = 15.0
                breakdown["logo_consistency"] = {"score": 15.0, "reason": f"Logo位置保持一致({v_logo})"}
            else:
                logo_score = 7.0
                breakdown["logo_consistency"] = {"score": 7.0, "reason": f"Logo位置变化({v_logo} vs {b_logo})"}
                risks.append("Logo位置变化可能降低品牌记忆度")
                recommendations.append("建议保持Logo位置统一，强化品牌曝光的一致性")
        elif v_logo or b_logo:
            logo_score = 8.0
            breakdown["logo_consistency"] = {"score": 8.0, "reason": "Logo位置信息不完整"}
            recommendations.append("建议明确Logo位置，确保品牌露出规范")
        else:
            # 双方都没有logo位置信息，默认给中等分（假设保持）
            logo_score = 10.0
            breakdown["logo_consistency"] = {"score": 10.0, "reason": "无Logo位置数据，默认假设保持"}
            recommendations.append("建议在DNA中记录Logo位置，以便更精确评估品牌一致性")
        score += logo_score

        # ---- 7. 世界观一致性（附加检查，不额外加分，用于风险判断） ----
        v_env = str(self._safe_get(variant_dna, ["environment", "type"]) or "").lower()
        b_env = str(self._safe_get(base_dna, ["environment", "type"]) or "").lower()
        v_scene = str(self._safe_get(variant_dna, ["scene"]) or "").lower()
        b_scene = str(self._safe_get(base_dna, ["scene"]) or "").lower()

        world_deviated = False
        if v_env and b_env and v_env != b_env:
            if not self._has_keyword(v_env, self._MW_WORLD_KEYWORDS):
                world_deviated = True
        if v_scene and b_scene and v_scene != b_scene:
            if not self._has_keyword(v_scene, self._MW_WORLD_KEYWORDS):
                world_deviated = True

        if world_deviated:
            risks.append("场景/环境偏离魔法森林世界观，用户可能产生'这不是Merge Witches'的困惑")
            recommendations.append("环境变更时建议保留魔法森林、水晶洞穴、月亮湖等标志性场景元素")

        score = max(0.0, min(100.0, score))

        # ---- 8. 综合建议 ----
        if score >= 85:
            recommendations.append("品牌一致性优秀，该变体能清晰传递Merge Witches品牌形象，可放心加大预算")
        elif score >= 70:
            recommendations.append("品牌一致性良好， minor偏差在可接受范围内，建议正常投放并监控品牌词搜索量")
        elif score >= 50:
            risks.append("品牌一致性中等，存在一定品牌稀释风险")
            recommendations.append("建议在投放文案或落地页中强化Merge Witches品牌名，补偿素材端的品牌辨识度")
        else:
            risks.append("品牌一致性差，用户可能无法将该广告与Merge Witches建立关联")
            recommendations.append("不建议直接投放该变体，请先回退品牌核心要素（女巫角色+魔法色调+合成玩法）")

        return ScoreResult(
            score=round(score, 2),
            breakdown=breakdown,
            recommendations=recommendations,
            risks=risks,
            raw_features=raw_features,
        )

    @staticmethod
    def _has_keyword(text: str, keywords: set[str]) -> bool:
        """检查文本中是否包含任一关键词"""
        if not text:
            return False
        return any(kw in text for kw in keywords)

    @staticmethod
    def _same_hook_family(hook_a: str, hook_b: str) -> bool:
        """判断两个Hook类型是否属于同一家族"""
        collection_family = {"collection", "merge", "summon", "evolution", "transformation"}
        emotion_family = {"crisis", "danger", "rescue", "reward", "bonus", "surprise"}
        curiosity_family = {"curiosity", "secret", "hidden", "mystery", "twist"}
        challenge_family = {"challenge", "wrong_choice", "before_after", "comparison"}

        a_lower = hook_a.lower()
        b_lower = hook_b.lower()

        for family in (collection_family, emotion_family, curiosity_family, challenge_family):
            a_in = any(member in a_lower for member in family)
            b_in = any(member in b_lower for member in family)
            if a_in and b_in:
                return True
        return False
