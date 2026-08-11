from .base_scorer import BaseScorer, ScoreResult


class PolicyScorer(BaseScorer):
    """Facebook Policy Risk - Facebook政策合规风险评估

    注意：分数越高表示越合规（风险越低）

    逻辑：
    - 是否有误导性内容（夸大效果）
    - 是否有违规内容（暴力、敏感）
    - 是否有版权问题（角色、音乐）
    - Logo和UI是否正确
    - 是否有虚假承诺（"免费获得"等）
    - 是否包含敏感文字

    对于Merge Witches游戏：
    - 可爱魔法系 = 低风险
    - 无暴力元素 = 安全
    - 无真实货币诱导 = 安全
    - 检查prompt中是否有高风险词汇
    """

    name = "Facebook Policy Risk"
    weight_key = "facebook_policy_risk"

    # 误导性内容关键词
    _MISLEADING_KEYWORDS: list[str] = [
        "guaranteed", "100% win", "always win", "never lose", "sure profit",
        "包赢", "必中", "稳赚", "绝对不亏", "百分百",
        "instant rich", "get rich quick", "millionaire", "unlimited money",
        "一夜暴富", "无限金币", "秒变富豪", "躺赚",
    ]

    # 违规内容：暴力
    _VIOLENCE_KEYWORDS: list[str] = [
        "kill", "murder", "blood", "gore", "death", "dead", "corpse",
        "杀", "血", "尸体", "死亡", "谋杀", "暴力", "残忍",
        "torture", "brutal", "massacre", "genocide", "terror",
        "酷刑", "屠杀", "恐怖", "炸弹", "枪击",
    ]

    # 违规内容：敏感/成人
    _SENSITIVE_KEYWORDS: list[str] = [
        "nude", "naked", "sex", "porn", "adult", "gambling", "casino",
        "裸", "性", "色情", "成人", "赌博", "博彩", "赌场",
        "drug", "cocaine", "heroin", "weed", "marijuana",
        "毒品", "可卡因", "海洛因", "大麻",
        "racist", "hate speech", "discrimination",
        "种族歧视", "仇恨言论", "歧视",
    ]

    # 版权问题
    _COPYRIGHT_KEYWORDS: list[str] = [
        "disney", "marvel", "pokemon", "nintendo", "star wars", "harry potter",
        "米奇", "漫威", "宝可梦", "任天堂", "星球大战", "哈利波特",
        "mickey", "batman", "superman", "spider-man", "iron man",
        "蝙蝠侠", "超人", "蜘蛛侠", "钢铁侠",
        # 注意：允许使用 Merge Witches 自有世界观词汇
    ]

    # 虚假承诺 / 诱导性词汇
    _FALSE_PROMISE_KEYWORDS: list[str] = [
        "free", "no cost", "zero cost", "completely free",
        "免费", "零成本", "完全免费", "不花钱",
        "everyone wins", "all players get", "guaranteed reward",
        "人人有奖", "必得", "免费送",
        "click here to claim", "limited time only", "act now",
        "点击领取", "限时", "马上行动", "手慢无",
    ]

    # 真实货币诱导
    _MONEY_BAIT_KEYWORDS: list[str] = [
        "real money", "cash out", "withdraw", "earn money", "make money",
        "真钱", "提现", "赚钱", "现金", "人民币", "美元",
        "paypal", "bank transfer", "gift card",
        "支付宝", "微信转账", "银行卡", "礼品卡",
    ]

    # 可爱/安全风格加分词
    _SAFE_STYLE_KEYWORDS: list[str] = [
        "cute", "kawaii", "chibi", "cartoon", "stylized", "fantasy",
        "可爱", "卡通", "Q版", "萌", "风格化", "幻想",
        "magic", "enchant", "fairy tale", "storybook",
        "魔法", "童话", "绘本",
    ]

    def score(
        self,
        variant_dna: dict,
        base_dna: dict,
        fb_meta: dict | None = None,
    ) -> ScoreResult:
        """对单个 Variant 进行 Facebook 政策合规评分"""
        score = 100.0
        breakdown: dict[str, float] = {}
        recommendations: list[str] = []
        risks: list[str] = []

        # 提取所有文本
        text = self._extract_all_text(variant_dna)
        fb_headline = ""
        fb_cta = ""
        if fb_meta:
            fb_headline = str(fb_meta.get("headline", "")).lower()
            fb_cta = str(fb_meta.get("cta", "")).lower()
        full_text = f"{text} {fb_headline} {fb_cta}".lower()

        # 1. 误导性内容检查
        misleading_count = self._count_keywords(full_text, self._MISLEADING_KEYWORDS)
        if misleading_count > 0:
            penalty = min(30.0, misleading_count * 15.0)
            score -= penalty
            breakdown["misleading_content"] = -penalty
            risks.append(f"检测到误导性内容（夸大效果/收益），风险等级高")
        else:
            breakdown["misleading_content"] = 0.0
            recommendations.append("无误导性夸大表述，符合Facebook真实宣传要求")

        # 2. 暴力内容检查
        violence_count = self._count_keywords(full_text, self._VIOLENCE_KEYWORDS)
        if violence_count > 0:
            penalty = min(40.0, violence_count * 20.0)
            score -= penalty
            breakdown["violence_content"] = -penalty
            risks.append(f"检测到暴力/血腥相关描述，严重违规风险")
        else:
            breakdown["violence_content"] = 0.0
            recommendations.append("无暴力或血腥元素，内容安全")

        # 3. 敏感/成人内容检查
        sensitive_count = self._count_keywords(full_text, self._SENSITIVE_KEYWORDS)
        if sensitive_count > 0:
            penalty = min(50.0, sensitive_count * 25.0)
            score -= penalty
            breakdown["sensitive_content"] = -penalty
            risks.append(f"检测到敏感/成人/违禁内容，极高违规风险")
        else:
            breakdown["sensitive_content"] = 0.0
            recommendations.append("无敏感或成人内容，合规")

        # 4. 版权问题检查
        copyright_count = self._count_keywords(full_text, self._COPYRIGHT_KEYWORDS)
        if copyright_count > 0:
            penalty = min(35.0, copyright_count * 17.5)
            score -= penalty
            breakdown["copyright_risk"] = -penalty
            risks.append(f"可能涉及第三方IP/版权元素，需注意素材来源")
        else:
            breakdown["copyright_risk"] = 0.0
            recommendations.append("未发现明显第三方版权元素")

        # 5. 虚假承诺检查
        false_promise_count = self._count_keywords(full_text, self._FALSE_PROMISE_KEYWORDS)
        if false_promise_count > 0:
            penalty = min(25.0, false_promise_count * 12.5)
            score -= penalty
            breakdown["false_promise"] = -penalty
            risks.append(f"检测到虚假承诺/过度诱导性用语，存在政策风险")
        else:
            breakdown["false_promise"] = 0.0
            recommendations.append("无虚假承诺或过度诱导性文案")

        # 6. 真实货币诱导检查
        money_bait_count = self._count_keywords(full_text, self._MONEY_BAIT_KEYWORDS)
        if money_bait_count > 0:
            penalty = min(30.0, money_bait_count * 15.0)
            score -= penalty
            breakdown["money_bait"] = -penalty
            risks.append(f"检测到真实货币/提现相关诱导，严重违规")
        else:
            breakdown["money_bait"] = 0.0
            recommendations.append("无真实货币诱导内容，安全")

        # 7. Merge Witches 安全风格加分
        safe_style_count = self._count_keywords(full_text, self._SAFE_STYLE_KEYWORDS)
        if safe_style_count > 0:
            bonus = min(10.0, safe_style_count * 2.5)
            score += bonus
            breakdown["safe_style_bonus"] = bonus
            recommendations.append("可爱魔法系风格，属于Facebook低风险内容")
        else:
            breakdown["safe_style_bonus"] = 0.0

        # 8. 针对Merge Witches的特定检查：无暴力元素 = 安全
        char_type = self._safe_get(variant_dna, ["character", "type"], "").lower()
        env_type = self._safe_get(variant_dna, ["environment", "type"], "").lower()
        creatures = variant_dna.get("creatures") or []
        creature_types = [str(c.get("type", "")).lower() for c in creatures if isinstance(c, dict)]

        # 如果包含蜘蛛/蛇/狼等偏暗黑生物，稍微提醒但不直接扣分（因为是游戏世界观内）
        dark_creatures = {"spider", "snake", "wolf", "bat", "raven", "troll"}
        has_dark_creature = bool(dark_creatures & set(creature_types))
        if has_dark_creature:
            breakdown["dark_creature_note"] = 0.0
            recommendations.append("包含偏暗黑风格生物，但仍在Merge Witches魔法世界观内，通常合规")
        else:
            breakdown["dark_creature_note"] = 0.0

        final_score = max(0.0, min(100.0, score))
        breakdown["raw_score"] = round(score, 2)

        # 如果整体非常安全，给出明确推荐
        if final_score >= 90 and not risks:
            recommendations.append("整体政策风险极低，适合Facebook全量投放")
        elif final_score < 70:
            risks.append("政策合规分数偏低，建议人工复核后再投放")

        return ScoreResult(
            score=round(final_score, 2),
            breakdown=breakdown,
            recommendations=recommendations,
            risks=risks,
            raw_features={
                "char_type": char_type,
                "env_type": env_type,
                "creature_types": creature_types,
                "fb_headline": fb_headline,
                "fb_cta": fb_cta,
            },
        )

    # ------------------------------------------------------------------
    # 内部工具方法
    # ------------------------------------------------------------------

    def _extract_all_text(self, dna: dict) -> str:
        """从 DNA 字典中提取所有字符串文本"""
        texts: list[str] = []

        for key in ("subject", "description", "standout_features"):
            val = dna.get(key)
            if isinstance(val, str):
                texts.append(val)
            elif isinstance(val, list):
                texts.extend(str(v) for v in val if v)

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

    def _count_keywords(self, text: str, keywords: list[str]) -> int:
        """统计文本中包含的关键词数量"""
        if not text:
            return 0
        count = 0
        for kw in keywords:
            if kw.lower() in text:
                count += 1
        return count
