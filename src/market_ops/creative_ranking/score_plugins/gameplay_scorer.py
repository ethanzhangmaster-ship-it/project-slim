from .base_scorer import BaseScorer, ScoreResult


class GameplayScorer(BaseScorer):
    """Gameplay Consistency - 玩法一致性评分（新增维度）

    逻辑：
    - 是否符合Merge玩法（合并、收集、养成）
    - 是否还能体现Collection Hook
    - 是否符合Merge节奏（慢节奏、治愈系）
    - 角色和生物是否与Merge Witches世界观一致
    - 是否有合并元素暗示（蛋、物品、生物进化）

    评分因素：
    - Collection元素存在: +25
    - 合并玩法暗示: +20
    - 治愈系节奏: +15
    - 魔法世界观一致: +20
    - 角色与玩法关联: +20
    """

    name = "Gameplay Consistency"
    weight_key = "gameplay_consistency"

    # Collection / 收集类关键词
    _COLLECTION_KEYWORDS: list[str] = [
        "collect", "collection", "gather", "hoard", "assemble", "compendium",
        "图鉴", "收集", "合集", "蛋", "egg", "nest", "book", "catalog",
        "complete", "set", "series", "family", "tier", "evolution",
    ]

    # 合并玩法关键词
    _MERGE_KEYWORDS: list[str] = [
        "merge", "combine", "fuse", "blend", "synthesize", "evolve",
        "合成", "合并", "融合", "进化", "升级", "match", "pair",
        "three in a row", "match-3", "match 3", "连线", "消除",
    ]

    # 治愈系 / 慢节奏关键词
    _COZY_KEYWORDS: list[str] = [
        "cozy", "calm", "peaceful", "gentle", "soft", "warm", "relax",
        "治愈", "温馨", "宁静", "柔和", "慢节奏", "休闲", "舒适",
        "soothing", "tranquil", "serene", "healing", "comfort",
    ]

    # Merge Witches 世界观关键词
    _WORLD_KEYWORDS: list[str] = [
        "witch", "magic", "spell", "potion", "enchant", "mystic", "arcane",
        "女巫", "魔法", "咒语", "药水", "符文", "神秘", "奇幻",
        "forest", "crystal", "glow", "sparkle", "star", "moon",
        "森林", "水晶", "发光", "星星", "月亮", "魔法生物",
    ]

    # 角色与玩法关联关键词（暗示养成/互动）
    _CHARACTER_GAMEPLAY_KEYWORDS: list[str] = [
        "level up", "grow", "train", "nurture", "care", "feed", "pet",
        "升级", "成长", "培养", "照料", "喂食", "抚摸", "陪伴",
        "evolution", "stage", "form", "baby", "adult", "mature",
        "幼体", "成年", "形态", "阶段",
    ]

    # 高风险：与Merge玩法冲突的元素（快节奏、竞技、暴力）
    _CONFLICT_KEYWORDS: list[str] = [
        "fps", "shoot", "gun", "battle royale", "pvp", "competitive",
        "射击", "枪战", "大逃杀", "竞技", "对战", "速通", "rush",
        "fast-paced", "intense action", "explosive", "war",
        "快节奏", "激烈", "爆炸", "战争", "血腥",
    ]

    def score(
        self,
        variant_dna: dict,
        base_dna: dict,
        fb_meta: dict | None = None,
    ) -> ScoreResult:
        """对单个 Variant 进行玩法一致性评分"""
        score = 0.0
        breakdown: dict[str, float] = {}
        recommendations: list[str] = []
        risks: list[str] = []

        # 提取所有文本用于关键词匹配
        text = self._extract_all_text(variant_dna)
        hook_type = self._safe_get(variant_dna, ["hook", "type"], "").lower()
        char_type = self._safe_get(variant_dna, ["character", "type"], "").lower()
        env_type = self._safe_get(variant_dna, ["environment", "type"], "").lower()
        creatures = variant_dna.get("creatures") or []

        # 1. Collection 元素存在 (+25)
        collection_score = 25.0 if self._has_any_keyword(text, self._COLLECTION_KEYWORDS) else 0.0
        # Hook 类型为 collection 时直接满分
        if hook_type == "collection":
            collection_score = 25.0
        score += collection_score
        breakdown["collection_elements"] = collection_score
        if collection_score > 0:
            recommendations.append("素材包含Collection元素，与Merge Witches核心玩法一致")
        else:
            risks.append("未检测到明显的Collection/收集元素，可能影响玩法传达")

        # 2. 合并玩法暗示 (+20)
        merge_score = 20.0 if self._has_any_keyword(text, self._MERGE_KEYWORDS) else 0.0
        # 如果画面中有蛋(Egg)或多只同类型生物，也视为合并暗示
        if not merge_score:
            creature_types = [str(c.get("type", "")).lower() for c in creatures if isinstance(c, dict)]
            if "egg" in creature_types or len(set(creature_types)) < len(creature_types):
                merge_score = 20.0
        score += merge_score
        breakdown["merge_hint"] = merge_score
        if merge_score > 0:
            recommendations.append("素材包含合并/进化玩法暗示，契合Merge核心机制")
        else:
            risks.append("未检测到Merge/合并玩法暗示，建议增加蛋、进化等元素")

        # 3. 治愈系节奏 (+15)
        cozy_score = 15.0 if self._has_any_keyword(text, self._COZY_KEYWORDS) else 0.0
        # 环境为 Magic Forest / Garden / Lake 等也倾向治愈
        if not cozy_score and env_type in ("magic_forest", "magic_garden", "mystic_lake", "enchanted_castle"):
            cozy_score = 15.0
        score += cozy_score
        breakdown["cozy_pacing"] = cozy_score
        if cozy_score > 0:
            recommendations.append("治愈系/慢节奏氛围符合Merge Witches的休闲定位")
        else:
            risks.append("画面节奏偏快或偏冷峻，可能与Merge治愈系定位不符")

        # 4. 魔法世界观一致 (+20)
        world_score = 20.0 if self._has_any_keyword(text, self._WORLD_KEYWORDS) else 0.0
        # 角色类型为 witch/wizard/fairy 等直接满分
        if not world_score and char_type in ("witch", "wizard", "fairy", "queen", "elf"):
            world_score = 20.0
        score += world_score
        breakdown["magic_world_consistency"] = world_score
        if world_score > 0:
            recommendations.append("魔法世界观一致，角色/生物/环境均契合Merge Witches设定")
        else:
            risks.append("世界观元素不足，角色或环境可能偏离魔法女巫主题")

        # 5. 角色与玩法关联 (+20)
        char_gameplay_score = 20.0 if self._has_any_keyword(text, self._CHARACTER_GAMEPLAY_KEYWORDS) else 0.0
        # 角色姿态为 casting/holding_orb 等也视为与玩法关联
        gesture = self._safe_get(variant_dna, ["character", "gesture"], "").lower()
        pose = self._safe_get(variant_dna, ["character", "pose"], "").lower()
        if not char_gameplay_score and gesture in ("casting", "holding_orb", "pointing"):
            char_gameplay_score = 20.0
        if not char_gameplay_score and pose in ("floating", "kneeling"):
            char_gameplay_score = 15.0
        score += char_gameplay_score
        breakdown["character_gameplay_link"] = char_gameplay_score
        if char_gameplay_score > 0:
            recommendations.append("角色姿态/动作暗示养成或魔法互动，增强玩法关联")
        else:
            risks.append("角色与玩法关联较弱，建议增加施法、抱蛋等互动姿态")

        # 冲突检测：如果包含与Merge玩法冲突的元素，整体扣分
        if self._has_any_keyword(text, self._CONFLICT_KEYWORDS):
            score -= 20.0
            breakdown["gameplay_conflict"] = -20.0
            risks.append("检测到与Merge休闲玩法冲突的元素（竞技/暴力/快节奏）")
        else:
            breakdown["gameplay_conflict"] = 0.0

        final_score = max(0.0, min(100.0, score))
        breakdown["raw_score"] = round(score, 2)

        return ScoreResult(
            score=round(final_score, 2),
            breakdown=breakdown,
            recommendations=recommendations,
            risks=risks,
            raw_features={
                "hook_type": hook_type,
                "char_type": char_type,
                "env_type": env_type,
                "creature_types": [str(c.get("type", "")) for c in creatures if isinstance(c, dict)],
            },
        )

    # ------------------------------------------------------------------
    # 内部工具方法
    # ------------------------------------------------------------------

    def _extract_all_text(self, dna: dict) -> str:
        """从 DNA 字典中提取所有字符串文本，合并为小写"""
        texts: list[str] = []

        # 优先提取主体描述字段
        for key in ("subject", "description", "standout_features"):
            val = dna.get(key)
            if isinstance(val, str):
                texts.append(val)
            elif isinstance(val, list):
                texts.extend(str(v) for v in val if v)

        # 递归遍历所有值
        self._collect_strings(dna, texts)
        return " ".join(texts).lower()

    def _collect_strings(self, obj: object, out: list[str]) -> None:
        """递归收集对象中的所有字符串值"""
        if isinstance(obj, str):
            out.append(obj)
        elif isinstance(obj, dict):
            for v in obj.values():
                self._collect_strings(v, out)
        elif isinstance(obj, list):
            for item in obj:
                self._collect_strings(item, out)

    def _has_any_keyword(self, text: str, keywords: list[str]) -> bool:
        """检查文本中是否包含任一关键词"""
        if not text:
            return False
        return any(kw.lower() in text for kw in keywords)
