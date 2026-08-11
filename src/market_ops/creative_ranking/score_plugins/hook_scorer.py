from .base_scorer import BaseScorer, ScoreResult
from ..config import RankingConfig


class HookScorer(BaseScorer):
    """Facebook Hook Score - 前3秒吸引力评分

    逻辑：
    - 主体是否突出（占画面40-70%）
    - 颜色是否鲜艳饱和
    - 对比度是否足够
    - 是否有动态元素（粒子、发光）
    - 角色是否看向镜头（眼神交流）
    - 是否有视觉钩子（好奇、收集、危机）

    Facebook最佳实践：
    - Hook必须在3秒内抓住注意力
    - 主体必须清晰可见
    - 颜色要鲜艳（移动端小屏幕）
    """

    name = "Facebook Hook Score"
    weight_key = "facebook_hook"

    def score(
        self,
        variant_dna: dict,
        base_dna: dict | None = None,
        fb_meta: dict | None = None,
    ) -> ScoreResult:
        config = RankingConfig()
        constraints = config.fb_constraints

        breakdown = {}
        recommendations = []
        risks = []
        total_score = 0.0

        # 1. 主体覆盖率 (0-25分)
        subject_coverage = self._safe_get(
            variant_dna, ["composition", "subject_coverage"], default=None
        )
        if subject_coverage is None and fb_meta:
            subject_coverage = fb_meta.get("subject_coverage")
        if subject_coverage is None:
            # 尝试从视觉层级估算
            subject_coverage = 0.55  # 默认中等

        min_cov = constraints.get("min_subject_coverage", 0.40)
        max_cov = constraints.get("max_subject_coverage", 0.70)

        if min_cov <= subject_coverage <= max_cov:
            coverage_score = 25.0
            recommendations.append(f"主体占画面{subject_coverage:.0%}，处于最佳范围")
        elif subject_coverage < min_cov:
            coverage_score = max(0.0, subject_coverage / min_cov * 25.0)
            risks.append(f"主体占比过低（{subject_coverage:.0%}），在Feed中难以识别")
        else:
            coverage_score = max(0.0, (1.0 - subject_coverage) / (1.0 - max_cov) * 25.0)
            risks.append(f"主体占比过高（{subject_coverage:.0%}），画面可能过于拥挤")

        breakdown["subject_coverage"] = {
            "score": round(coverage_score, 1),
            "value": subject_coverage,
            "ideal_range": f"{min_cov:.0%}-{max_cov:.0%}",
        }
        total_score += coverage_score

        # 2. 颜色鲜艳度 (0-20分)
        saturation = self._safe_get(variant_dna, ["colors", "saturation"], default=None)
        if saturation is None and fb_meta:
            saturation = fb_meta.get("saturation")
        if saturation is None:
            # 从 mood_palette 推断
            mood_palette = self._safe_get(variant_dna, ["colors", "mood_palette"], default=[])
            vivid_keywords = ["vivid", "bright", "bold", "neon", "fluorescent", "鲜艳", "明亮"]
            if mood_palette and any(kw in str(m).lower() for m in mood_palette for kw in vivid_keywords):
                saturation = 0.75
            else:
                saturation = 0.50

        if saturation >= 0.70:
            color_score = 20.0
            recommendations.append("颜色鲜艳饱和，适合移动端小屏幕展示")
        elif saturation >= 0.45:
            color_score = 15.0 + (saturation - 0.45) / 0.25 * 5.0
        else:
            color_score = max(0.0, saturation / 0.45 * 15.0)
            risks.append("颜色饱和度偏低，在Facebook Feed中可能不够醒目")

        breakdown["color_saturation"] = {
            "score": round(color_score, 1),
            "value": saturation,
        }
        total_score += color_score

        # 3. 对比度 (0-15分)
        contrast = self._safe_get(variant_dna, ["lighting", "contrast"], default=None)
        if contrast is None and fb_meta:
            contrast = fb_meta.get("contrast")
        if contrast is None:
            contrast = self._safe_get(variant_dna, ["video_analysis", "contrast"], default=3.0)

        min_contrast = constraints.get("min_contrast_ratio", 3.0)
        if contrast >= min_contrast:
            contrast_score = 15.0
            if contrast >= min_contrast * 1.5:
                recommendations.append("画面对比度充足，主体突出")
        else:
            contrast_score = max(0.0, contrast / min_contrast * 15.0)
            risks.append("对比度不足，主体可能融入背景")

        breakdown["contrast"] = {
            "score": round(contrast_score, 1),
            "value": contrast,
            "min_required": min_contrast,
        }
        total_score += contrast_score

        # 4. 动态元素 (0-15分)
        motion_elements = []
        particle_effects = self._safe_get(
            variant_dna, ["motion", "particle_effects"], default=[]
        )
        if particle_effects:
            motion_elements.extend(particle_effects)
        camera_movement = self._safe_get(
            variant_dna, ["motion", "camera_movement"], default=""
        )
        if camera_movement and str(camera_movement).lower() not in ["static", "none", "固定"]:
            motion_elements.append(camera_movement)
        creature_actions = self._safe_get(
            variant_dna, ["motion", "creature_actions"], default=[]
        )
        if creature_actions:
            motion_elements.extend(creature_actions)

        # 魔法元素
        magic_elements = self._safe_get(
            variant_dna, ["environment", "magic_elements"], default=[]
        )
        if magic_elements:
            motion_elements.extend(magic_elements)

        motion_count = len(motion_elements)
        if motion_count >= 3:
            motion_score = 15.0
            recommendations.append("丰富的动态元素（粒子、发光、镜头运动），能有效抓住注意力")
        elif motion_count >= 1:
            motion_score = 8.0 + (motion_count - 1) * 3.5
            recommendations.append("包含动态元素，有助于提升前3秒停留率")
        else:
            motion_score = 0.0
            risks.append("缺乏动态元素，静态画面在Feed中较难脱颖而出")

        breakdown["motion_elements"] = {
            "score": round(motion_score, 1),
            "count": motion_count,
            "elements": motion_elements[:5],
        }
        total_score += motion_score

        # 5. 眼神交流 / 角色朝向 (0-15分)
        character_eyes = self._safe_get(variant_dna, ["character", "eyes"], default="")
        character_pose = self._safe_get(variant_dna, ["character", "pose"], default="")
        gaze_keywords = ["front", "camera", "viewer", "镜头", "正视", "看镜头", "forward"]
        pose_str = str(character_pose).lower()
        eyes_str = str(character_eyes).lower()

        if any(kw in eyes_str for kw in gaze_keywords) or any(kw in pose_str for kw in gaze_keywords):
            gaze_score = 15.0
            recommendations.append("角色正视镜头，建立了有效的眼神交流，增强代入感")
        elif character_pose or character_eyes:
            gaze_score = 7.0
            risks.append("角色未直接看向镜头，可能降低用户情感连接")
        else:
            gaze_score = 5.0
            risks.append("缺少角色眼神/朝向信息，建议增加镜头互动")

        breakdown["eye_contact"] = {
            "score": round(gaze_score, 1),
            "character_eyes": character_eyes,
            "character_pose": character_pose,
        }
        total_score += gaze_score

        # 6. 视觉钩子类型 (0-10分)
        hook_type = self._safe_get(variant_dna, ["hook", "type"], default="")
        strong_hook_types = ["collection", "transformation", "challenge", "crisis", "curiosity"]
        medium_hook_types = ["secret", "progression", "achievement", "reward"]
        hook_str = str(hook_type).lower()

        if any(h in hook_str for h in strong_hook_types):
            hook_score = 10.0
            recommendations.append(f"Hook类型 '{hook_type}' 属于强吸引力类型，适合前3秒展示")
        elif any(h in hook_str for h in medium_hook_types):
            hook_score = 7.0
            recommendations.append(f"Hook类型 '{hook_type}' 具有中等吸引力")
        elif hook_type:
            hook_score = 4.0
            risks.append(f"Hook类型 '{hook_type}' 吸引力偏弱，建议优化前3秒呈现")
        else:
            hook_score = 0.0
            risks.append("未定义Hook类型，前3秒缺乏明确的注意力抓手")

        breakdown["hook_type"] = {
            "score": round(hook_score, 1),
            "value": hook_type,
        }
        total_score += hook_score

        final_score = max(0.0, min(100.0, total_score))

        # 根据总分给出整体建议
        if final_score >= 80:
            recommendations.insert(0, "Hook综合表现优秀，前3秒注意力抓取能力强")
        elif final_score >= 60:
            recommendations.insert(0, "Hook表现良好，仍有优化空间")
        else:
            risks.insert(0, "Hook得分偏低，前3秒可能无法有效阻止用户划走")

        return ScoreResult(
            score=round(final_score, 1),
            breakdown=breakdown,
            recommendations=recommendations,
            risks=risks,
            raw_features={
                "subject_coverage": subject_coverage,
                "saturation": saturation,
                "contrast": contrast,
                "motion_count": motion_count,
                "hook_type": hook_type,
            },
        )
