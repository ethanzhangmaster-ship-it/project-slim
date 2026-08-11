from .base_scorer import BaseScorer, ScoreResult


class FatigueScorer(BaseScorer):
    """Creative Fatigue - 广告疲劳风险评估

    逻辑：
    - 与Winning相似度 >95% = 极易疲劳（低分）
    - 与Winning相似度 70-95% = 中等风险
    - 与Winning相似度 <70% = 安全（高分）
    - 同一Winning的变体数量过多 = 疲劳累积
    - 颜色变体过多 = 视觉疲劳
    - 生物变体过多 = 认知疲劳

    注意：这个维度是"风险"，分数越高表示越不容易疲劳
    """

    name = "Creative Fatigue"
    weight_key = "creative_fatigue"

    # 用于相似度对比的 DNA 字段路径
    _COMPARE_PATHS = [
        (["hook"], "hook"),
        (["hook", "type"], "hook_type"),
        (["identity"], "identity"),
        (["character", "type"], "character_type"),
        (["character", "clothes"], "character_clothes"),
        (["character", "pose"], "character_pose"),
        (["style"], "style"),
        (["scene"], "scene"),
        (["environment", "type"], "environment_type"),
        (["environment", "time"], "environment_time"),
        (["composition"], "composition"),
        (["composition", "layout"], "composition_layout"),
        (["camera"], "camera"),
        (["camera", "shot_type"], "camera_shot"),
        (["camera", "movement"], "camera_movement"),
        (["lighting"], "lighting"),
        (["lighting", "color_temperature"], "lighting_temperature"),
        (["colors", "mood_palette"], "color_mood"),
        (["creatures", "0", "type"], "creature_type"),
        (["creatures", "0", "color"], "creature_color"),
        (["creatures", "0", "action"], "creature_action"),
        (["mechanic"], "mechanic"),
        (["reward"], "reward"),
        (["cta"], "cta"),
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

        fb_meta = fb_meta or {}

        # ---- 1. 计算与 Winning Creative 的字段级相似度 ----
        matched = 0
        total = 0
        diff_fields: list[str] = []
        for path, key in self._COMPARE_PATHS:
            v = self._safe_get(variant_dna, path)
            b = self._safe_get(base_dna, path)
            if v is None and b is None:
                continue
            total += 1
            if v is not None and b is not None:
                if str(v).strip().lower() == str(b).strip().lower():
                    matched += 1
                else:
                    diff_fields.append(key)
            else:
                diff_fields.append(key)

        similarity = matched / total if total > 0 else 1.0
        raw_features["similarity_ratio"] = round(similarity, 3)
        raw_features["matched_fields"] = matched
        raw_features["total_fields"] = total
        raw_features["diff_fields"] = diff_fields

        # ---- 2. 根据相似度区间映射基础分 ----
        if similarity > 0.95:
            # 极易疲劳：几乎一模一样
            score = 35.0
            breakdown["similarity_band"] = {
                "band": "极易疲劳",
                "similarity": round(similarity, 3),
                "base_score": 35.0,
                "reason": "与Winning Creative相似度>95%，用户极易产生广告疲劳",
            }
            risks.append("该变体与Winning Creative过于相似，投放后很快会进入疲劳期，CTR衰减风险高")
            recommendations.append("建议增加至少一个P1维度的变化（如生物类型、环境）以延长素材生命周期")
        elif similarity >= 0.70:
            # 中等风险
            # 在70%-95%之间线性插值：95%→50分，70%→70分
            score = 50.0 + (0.95 - similarity) * (20.0 / 0.25)
            breakdown["similarity_band"] = {
                "band": "中等风险",
                "similarity": round(similarity, 3),
                "base_score": round(score, 2),
                "reason": "与Winning Creative相似度70%-95%，存在一定疲劳风险",
            }
            risks.append("相似度处于中等风险区间，建议监控投放3-5天后的CTR衰减情况")
            recommendations.append("可考虑微调颜色或光效，在保持学习阶段稳定的同时延缓疲劳")
        else:
            # 安全区
            # 在<70%时：70%→75分，越低分越高，最低50%→90分
            score = 75.0 + (0.70 - similarity) * (15.0 / 0.20)
            score = min(90.0, score)
            breakdown["similarity_band"] = {
                "band": "安全",
                "similarity": round(similarity, 3),
                "base_score": round(score, 2),
                "reason": "与Winning Creative相似度<70%，差异性足够，疲劳风险低",
            }
            recommendations.append("该变体差异性充足，疲劳风险低，适合作为新一轮投放主力")

        # ---- 3. 同一 Winning 变体数量过多 → 疲劳累积 ----
        variant_count = fb_meta.get("same_winning_variants") or fb_meta.get("variant_count") or 0
        raw_features["same_winning_variants"] = variant_count
        if variant_count > 10:
            penalty = min(20.0, (variant_count - 10) * 2.0)
            score -= penalty
            breakdown["variant_count_fatigue"] = {
                "penalty": -penalty,
                "variant_count": variant_count,
                "reason": f"同一Winning已有{variant_count}个变体，疲劳累积严重",
            }
            risks.append(f"同一Winning Creative已有{variant_count}个变体，用户覆盖面接近饱和")
            recommendations.append("建议暂停该Winning的新变体生成，转向其他Winning或全新创意方向")
        elif variant_count > 5:
            penalty = (variant_count - 5) * 1.5
            score -= penalty
            breakdown["variant_count_fatigue"] = {
                "penalty": -penalty,
                "variant_count": variant_count,
                "reason": f"同一Winning已有{variant_count}个变体，疲劳开始累积",
            }
            risks.append(f"同一Winning已有{variant_count}个变体，继续增加需更谨慎把控差异度")
            recommendations.append("建议优先测试与Winning差异度>30%的变体，避免同质化")
        else:
            breakdown["variant_count_fatigue"] = {
                "penalty": 0.0,
                "variant_count": variant_count,
                "reason": f"同一Winning仅{variant_count}个变体，疲劳累积可控",
            }

        # ---- 4. 颜色变体过多 → 视觉疲劳 ----
        color_variant_count = fb_meta.get("color_variant_count") or 0
        raw_features["color_variant_count"] = color_variant_count
        if color_variant_count > 5:
            penalty = min(15.0, (color_variant_count - 5) * 3.0)
            score -= penalty
            breakdown["color_fatigue"] = {
                "penalty": -penalty,
                "color_variant_count": color_variant_count,
                "reason": f"颜色变体已达{color_variant_count}个，易产生视觉疲劳",
            }
            risks.append(f"颜色变体过多（{color_variant_count}个），用户视觉上已难以区分差异")
            recommendations.append("颜色变体建议控制在5个以内，后续可转向生物或环境维度")
        elif color_variant_count > 3:
            penalty = (color_variant_count - 3) * 1.5
            score -= penalty
            breakdown["color_fatigue"] = {
                "penalty": -penalty,
                "color_variant_count": color_variant_count,
                "reason": f"颜色变体{color_variant_count}个，接近视觉疲劳阈值",
            }
            recommendations.append("颜色变体接近饱和，下一个变体建议切换为P1维度")
        else:
            breakdown["color_fatigue"] = {
                "penalty": 0.0,
                "color_variant_count": color_variant_count,
                "reason": f"颜色变体{color_variant_count}个，视觉疲劳风险低",
            }

        # ---- 5. 生物变体过多 → 认知疲劳 ----
        creature_variant_count = fb_meta.get("creature_variant_count") or 0
        raw_features["creature_variant_count"] = creature_variant_count
        if creature_variant_count > 3:
            penalty = min(15.0, (creature_variant_count - 3) * 4.0)
            score -= penalty
            breakdown["creature_fatigue"] = {
                "penalty": -penalty,
                "creature_variant_count": creature_variant_count,
                "reason": f"生物变体已达{creature_variant_count}个，易产生认知疲劳",
            }
            risks.append(f"生物变体过多（{creature_variant_count}个），用户对'合成新生物'的新鲜感递减")
            recommendations.append("生物变体建议控制在3个以内，可考虑环境或角色维度创造新的惊喜感")
        elif creature_variant_count > 2:
            penalty = (creature_variant_count - 2) * 2.0
            score -= penalty
            breakdown["creature_fatigue"] = {
                "penalty": -penalty,
                "creature_variant_count": creature_variant_count,
                "reason": f"生物变体{creature_variant_count}个，接近认知疲劳阈值",
            }
            recommendations.append("生物变体接近饱和，下一个变体建议切换维度")
        else:
            breakdown["creature_fatigue"] = {
                "penalty": 0.0,
                "creature_variant_count": creature_variant_count,
                "reason": f"生物变体{creature_variant_count}个，认知疲劳风险低",
            }

        # ---- 6. 综合风险总结 ----
        if score < 40:
            risks.append("综合疲劳风险高：该变体可能在一周内出现明显CTR衰减")
            recommendations.append("强烈建议增加变化维度或暂缓投放，优先测试差异更大的变体")
        elif score < 60:
            risks.append("综合疲劳风险中等：预计素材生命周期为2-3周")
            recommendations.append("可正常投放，但需密切监控CTR和频次指标，准备替补素材")
        else:
            recommendations.append("综合疲劳风险低，素材生命周期预期较长，可放心加大预算")

        score = max(0.0, min(100.0, score))

        return ScoreResult(
            score=round(score, 2),
            breakdown=breakdown,
            recommendations=recommendations,
            risks=risks,
            raw_features=raw_features,
        )
