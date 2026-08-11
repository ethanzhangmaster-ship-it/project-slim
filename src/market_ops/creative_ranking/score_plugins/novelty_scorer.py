from .base_scorer import BaseScorer, ScoreResult


class NoveltyScorer(BaseScorer):
    """Novelty Score - 创新程度评分

    逻辑：
    - 只是换颜色 = 低创新（+5）
    - 换生物 = 中等创新（+15）
    - 换环境 = 高创新（+20）
    - 换角色 = 极高创新但风险大（+10）
    - 换风格 = 不建议（-20）

    同时需要平衡：
    - 太相似 = 无新意（分数低）
    - 太不同 = 偏离Winning DNA（分数低）
    - 理想：有新鲜感但核心DNA保留
    """

    name = "Novelty Score"
    weight_key = "novelty"

    # 各创新维度的检测路径
    _COLOR_PATHS = [
        (["colors", "mood_palette"], "color_mood"),
        (["creatures", "0", "color"], "creature_color"),
        (["lighting", "color_temperature"], "lighting_temperature"),
        (["lighting", "special_effects", "0"], "lighting_effect"),
    ]
    _CREATURE_PATHS = [
        (["creatures", "0", "type"], "creature_type"),
    ]
    _ENVIRONMENT_PATHS = [
        (["environment", "type"], "environment_type"),
        (["environment", "time"], "environment_time"),
        (["scene"], "scene"),
    ]
    _CHARACTER_PATHS = [
        (["character", "type"], "character_type"),
        (["character", "clothes"], "character_clothes"),
        (["character", "pose"], "character_pose"),
        (["character", "gesture"], "character_gesture"),
        (["identity"], "identity"),
    ]
    _STYLE_PATHS = [
        (["style"], "style"),
    ]
    _HOOK_PATHS = [
        (["hook", "type"], "hook_type"),
        (["hook"], "hook"),
    ]

    def score(
        self,
        variant_dna: dict,
        base_dna: dict,
        fb_meta: dict | None = None,
    ) -> ScoreResult:
        score = 50.0
        breakdown: dict = {}
        recommendations: list[str] = []
        risks: list[str] = []
        raw_features: dict = {}
        changed_categories: list[str] = []
        total_diff_count = 0

        # ---- 1. 颜色变化检测 ----
        color_changed = False
        for path, key in self._COLOR_PATHS:
            v = self._safe_get(variant_dna, path, "")
            b = self._safe_get(base_dna, path, "")
            if v and b and str(v).strip().lower() != str(b).strip().lower():
                color_changed = True
                total_diff_count += 1
                raw_features[f"{key}_variant"] = v
                raw_features[f"{key}_base"] = b
        if color_changed:
            changed_categories.append("color")
            score += 5.0
            breakdown["color_change"] = {"bonus": 5.0, "reason": "颜色变化，低创新但安全"}

        # ---- 2. 生物变化检测 ----
        creature_changed = False
        for path, key in self._CREATURE_PATHS:
            v = self._safe_get(variant_dna, path, "")
            b = self._safe_get(base_dna, path, "")
            if v and b and str(v).strip().lower() != str(b).strip().lower():
                creature_changed = True
                total_diff_count += 1
                raw_features[f"{key}_variant"] = v
                raw_features[f"{key}_base"] = b
        if creature_changed:
            changed_categories.append("creature")
            score += 15.0
            breakdown["creature_change"] = {"bonus": 15.0, "reason": "生物类型变化，中等创新"}

        # ---- 3. 环境变化检测 ----
        env_changed = False
        for path, key in self._ENVIRONMENT_PATHS:
            v = self._safe_get(variant_dna, path, "")
            b = self._safe_get(base_dna, path, "")
            if v and b and str(v).strip().lower() != str(b).strip().lower():
                env_changed = True
                total_diff_count += 1
                raw_features[f"{key}_variant"] = v
                raw_features[f"{key}_base"] = b
        if env_changed:
            changed_categories.append("environment")
            score += 20.0
            breakdown["environment_change"] = {"bonus": 20.0, "reason": "环境变化，高创新"}

        # ---- 4. 角色变化检测 ----
        character_changed = False
        for path, key in self._CHARACTER_PATHS:
            v = self._safe_get(variant_dna, path, "")
            b = self._safe_get(base_dna, path, "")
            if v and b and str(v).strip().lower() != str(b).strip().lower():
                character_changed = True
                total_diff_count += 1
                raw_features[f"{key}_variant"] = v
                raw_features[f"{key}_base"] = b
        if character_changed:
            changed_categories.append("character")
            score += 10.0
            breakdown["character_change"] = {"bonus": 10.0, "reason": "角色变化，极高创新但风险大"}

        # ---- 5. 风格变化检测 ----
        style_changed = False
        for path, key in self._STYLE_PATHS:
            v = self._safe_get(variant_dna, path, "")
            b = self._safe_get(base_dna, path, "")
            if v and b and str(v).strip().lower() != str(b).strip().lower():
                style_changed = True
                total_diff_count += 1
                raw_features[f"{key}_variant"] = v
                raw_features[f"{key}_base"] = b
        if style_changed:
            changed_categories.append("style")
            score -= 20.0
            breakdown["style_change"] = {"penalty": -20.0, "reason": "风格变化，不建议，偏离品牌DNA"}
            risks.append("风格变更会导致品牌认知断裂，建议保持原有画风")

        # ---- 6. Hook 变化检测 ----
        hook_changed = False
        for path, key in self._HOOK_PATHS:
            v = self._safe_get(variant_dna, path, "")
            b = self._safe_get(base_dna, path, "")
            if v and b and str(v).strip().lower() != str(b).strip().lower():
                hook_changed = True
                total_diff_count += 1
                raw_features[f"{key}_variant"] = v
                raw_features[f"{key}_base"] = b
        if hook_changed:
            changed_categories.append("hook")
            score -= 15.0
            breakdown["hook_change"] = {"penalty": -15.0, "reason": "Hook类型变化，高风险，可能破坏已验证的停留逻辑"}
            risks.append("Hook是已验证的滚动停留关键，变更可能导致CVR下降")

        # ---- 7. 无变化 = 无新意 ----
        if not changed_categories:
            score = 20.0
            breakdown["no_change"] = {"penalty": -30.0, "reason": "无任何变化，与Winning Creative完全一致，无新意"}
            risks.append("该变体与Winning Creative完全一致，用户容易产生审美疲劳，创新价值极低")
            recommendations.append("建议至少修改一个P0维度（如颜色、光效、粒子效果）以增加新鲜感")

        # ---- 8. 变化过多 = 偏离 DNA ----
        category_count = len(changed_categories)
        if category_count > 2:
            penalty = (category_count - 2) * 10.0
            score -= penalty
            breakdown["too_many_changes"] = {
                "penalty": -penalty,
                "reason": f"变化类别过多（{category_count}类），偏离Winning DNA核心",
                "changed_categories": changed_categories,
                "total_diff_fields": total_diff_count,
            }
            risks.append(f"变化点过多（{category_count}类/{total_diff_count}处），Facebook学习阶段可能重启")
            recommendations.append("建议每次只变更1-2个维度，确保A/B测试归因可追溯")

        # ---- 9. 理想创新区间建议 ----
        if changed_categories and category_count <= 2 and not style_changed:
            if "environment" in changed_categories:
                recommendations.append("环境变体创新度高且核心DNA保留，适合中等预算测试")
            elif "creature" in changed_categories:
                recommendations.append("生物变体有新鲜感，用户认知负担可控，推荐测试")
            elif "character" in changed_categories:
                recommendations.append("角色变体创新度高但风险较大，建议小预算先行验证")
            elif "color" in changed_categories:
                recommendations.append("颜色变体安全可控，ROI可预期，适合作为P0首选批量测试")
            if category_count == 2 and not hook_changed:
                recommendations.append("双维度变化在可控范围内，有新鲜感且保留了核心转化逻辑")

        if hook_changed and not style_changed and category_count <= 2:
            recommendations.append("如必须变更Hook，建议搭配强CTA并进行小规模A/B测试验证停留率")

        score = max(0.0, min(100.0, score))

        return ScoreResult(
            score=round(score, 2),
            breakdown=breakdown,
            recommendations=recommendations,
            risks=risks,
            raw_features=raw_features,
        )
