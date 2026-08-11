"""Creative Expansion Quality Scorer - 素材变体质量评分器

对每个素材变体在 6 个维度上评分，确保变体既与 Winning Creative 足够相似
（利于 Facebook 学习阶段），又有足够的钩子强度和品牌一致性。

6 个评分维度：
1. Creative Similarity (0-100)  - 与获胜素材的相似度
2. Facebook Readability (0-100) - Facebook 信息流移动端可读性
3. Hook Strength (0-100)        - 滚动停留能力
4. Visual Quality (0-100)       - AI 生成画面质量可行性
5. Brand Consistency (0-100)    - 品牌一致性（Merge Witches 风格）
6. AI Generation Confidence (0-100) - AI 模型生成好结果的信心度
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

# ── 变更优先级定义 ──────────────────────────────────────────────────────────
# P0: 最安全的变更（颜色、光效、粒子），对学习阶段影响最小
# P1: 中等风险变更（姿势、镜头角度），可能影响学习阶段
# P2: 高风险变更（角色类型、画风），学习阶段会重新开始

PRIORITY_P0 = "P0"
PRIORITY_P1 = "P1"
PRIORITY_P2 = "P2"

# 各变更类型 → 优先级映射
MUTATION_PRIORITY: dict[str, str] = {
    "color_swap": PRIORITY_P0,
    "lighting_swap": PRIORITY_P0,
    "particle_swap": PRIORITY_P0,
    "glow_swap": PRIORITY_P0,
    "pose_swap": PRIORITY_P1,
    "camera_swap": PRIORITY_P1,
    "composition_swap": PRIORITY_P1,
    "subject_swap": PRIORITY_P2,
    "emotion_swap": PRIORITY_P2,
    "background_swap": PRIORITY_P2,
    "costume_swap": PRIORITY_P2,
    "style_swap": PRIORITY_P2,
    "character_swap": PRIORITY_P2,
}

# ── DNA 字段分组 ────────────────────────────────────────────────────────────
# 对相似性影响大的核心字段
CORE_DNA_FIELDS: list[str] = [
    "hook", "identity", "scene", "style", "composition",
]

# 对相似性影响中等的字段
MODERATE_DNA_FIELDS: list[str] = [
    "camera", "lighting", "emotion", "mechanic", "reward",
]

# 对相似性影响较小的辅助字段
AUXILIARY_DNA_FIELDS: list[str] = [
    "cta", "template", "negative",
]

# ── 可读性相关字段 ──────────────────────────────────────────────────────────
# 高对比度 / 简洁背景 / 主体居中的关键词映射
HIGH_CONTRAST_KEYWORDS = {"dramatic", "neon", "spotlight", "golden hour", "cinematic", "sunset", "高对比"}
SIMPLE_BG_KEYWORDS = {"solid", "gradient", "simple", "plain", "blur", "bokeh", "简洁", "纯色"}
CENTERED_KEYWORDS = {"center", "centered", "portrait", "居中", "正面"}
COMPLEXITY_KEYWORDS = {"crowd", "many", "complex", "busy", "detailed", "intricate", "complex", "混乱", "复杂"}

# ── 钩子强度相关字段 ────────────────────────────────────────────────────────
# Collection Hook: 有生物/角色出现的组合钩子
COLLECTION_HOOK_KEYWORDS = {"collection", "creature", "character", "merge", "summon", "组合", "合成", "召唤"}
CAMERA_EYE_KEYWORDS = {"looking at camera", "facing camera", "eye contact", "stare", "直视", "注视"}
BRIGHT_KEYWORDS = {"bright", "vibrant", "saturated", "neon", "glow", "shiny", "亮", "鲜艳", "发光"}
PARTICLE_KEYWORDS = {"particle", "sparkle", "glow", "magic dust", "firefly", "粒子", "光点", "火花"}
EMOTIONAL_HOOK_KEYWORDS = {"cute", "adorable", "wonder", "amazing", "surprise", "mystery", "可愛", "惊奇", "神秘"}


@dataclass(slots=True)
class QualityScore:
    """单个变体的 6 维质量评分结果。"""
    variant_id: str
    creative_similarity: float       # 0-100, 与获胜素材的相似度
    facebook_readability: float      # 0-100, Facebook 移动端可读性
    hook_strength: float             # 0-100, 滚动停留能力
    visual_quality: float            # 0-100, AI 生成画面质量可行性
    brand_consistency: float         # 0-100, 品牌一致性
    ai_generation_confidence: float  # 0-100, AI 生成信心度
    overall_score: float             # 加权平均总分
    score_breakdown: dict            # 每个维度的评分解释

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class QualityScorer:
    """对创意变体进行 Facebook 广告适宜性评分。

    评分核心原则：
    - 只变更 1 个字段是最佳实践（控制变量法）
    - 变更的优先级决定了对 Facebook 学习阶段的影响
    - P0 变更（颜色/光效/粒子）几乎不影响学习阶段
    - P2 变更（角色/画风）会触发重新学习
    """

    # 加权系数：hook_strength 权重最高，因为 Facebook 广告最看重停止滚动
    WEIGHTS: dict[str, float] = {
        "creative_similarity": 0.20,
        "facebook_readability": 0.20,
        "hook_strength": 0.25,
        "visual_quality": 0.10,
        "brand_consistency": 0.15,
        "ai_generation_confidence": 0.10,
    }

    def score(self, variant: dict, base_dna: dict) -> QualityScore:
        """对单个变体评分。

        Args:
            variant: 变体字典，需包含 variant_id 以及 DNA 字段。
                     可选字段：mutation_type（变更类型），changed_fields（变更字段列表）
            base_dna: 获胜素材的 DNA 字典，包含 hook/identity/scene/style 等 DNA 字段。

        Returns:
            QualityScore 评分结果。
        """
        variant_id = str(variant.get("variant_id", variant.get("creative_id", "unknown")))
        variant_dna = variant if "hook" in variant or "character" in variant else {k: v for k, v in variant.items() if k not in ("variant_id", "creative_id", "mutation_type", "changed_fields")}

        sim_score, sim_breakdown = self._score_similarity(variant_dna, base_dna)
        read_score, read_breakdown = self._score_readability(variant_dna)
        hook_score, hook_breakdown = self._score_hook(variant_dna)
        visual_score, visual_breakdown = self._score_visual_quality(variant_dna)
        brand_score, brand_breakdown = self._score_brand(variant_dna, base_dna)
        ai_score, ai_breakdown = self._score_ai_confidence(variant_dna, variant)

        overall = (
            sim_score * self.WEIGHTS["creative_similarity"]
            + read_score * self.WEIGHTS["facebook_readability"]
            + hook_score * self.WEIGHTS["hook_strength"]
            + visual_score * self.WEIGHTS["visual_quality"]
            + brand_score * self.WEIGHTS["brand_consistency"]
            + ai_score * self.WEIGHTS["ai_generation_confidence"]
        )
        overall = round(max(0.0, min(100.0, overall)), 2)

        return QualityScore(
            variant_id=variant_id,
            creative_similarity=round(sim_score, 2),
            facebook_readability=round(read_score, 2),
            hook_strength=round(hook_score, 2),
            visual_quality=round(visual_score, 2),
            brand_consistency=round(brand_score, 2),
            ai_generation_confidence=round(ai_score, 2),
            overall_score=overall,
            score_breakdown={
                "creative_similarity": sim_breakdown,
                "facebook_readability": read_breakdown,
                "hook_strength": hook_breakdown,
                "visual_quality": visual_breakdown,
                "brand_consistency": brand_breakdown,
                "ai_generation_confidence": ai_breakdown,
            },
        )

    def score_batch(self, variants: list[dict], base_dna: dict) -> list[QualityScore]:
        """批量评分，按 overall_score 降序排列。"""
        scores = [self.score(v, base_dna) for v in variants]
        scores.sort(key=lambda s: s.overall_score, reverse=True)
        return scores

    # ── 内部评分方法 ──────────────────────────────────────────────────────

    def _score_similarity(self, variant_dna: dict, base_dna: dict) -> tuple[float, dict]:
        """评分创意相似度。

        核心逻辑：
        - 对比变体和 base 的每个 DNA 字段
        - 只允许 1 个字段不同（控制变量法）
        - P0 变更：相似度 85-95（对学习阶段几乎无影响）
        - P1 变更：相似度 75-85（轻微影响）
        - P2 变更：相似度 60-75（触发重新学习）
        - 多字段不同：惩罚
        """
        # 找出所有不同的字段
        all_fields = CORE_DNA_FIELDS + MODERATE_DNA_FIELDS + AUXILIARY_DNA_FIELDS
        diff_fields: list[str] = []
        for field in all_fields:
            v_val = str(variant_dna.get(field, "") or "").strip().lower()
            b_val = str(base_dna.get(field, "") or "").strip().lower()
            if v_val and b_val and v_val != b_val:
                diff_fields.append(field)

        if not diff_fields:
            # 完全一致，相似度最高
            return 98.0, {"reason": "无变更，与 base 完全一致", "diff_fields": [], "priority": None}

        # 根据变更字段的优先级确定基础相似度范围
        # 先判断变更字段的优先级：取最高风险的那个
        priorities: list[str] = []
        for field in diff_fields:
            priority = self._field_priority(field, variant_dna)
            priorities.append(priority)

        # 取最严格（最低）的优先级作为主要判断依据
        if PRIORITY_P2 in priorities:
            base_score_range = (60, 75)
            dominant_priority = PRIORITY_P2
        elif PRIORITY_P1 in priorities:
            base_score_range = (75, 85)
            dominant_priority = PRIORITY_P1
        else:
            base_score_range = (85, 95)
            dominant_priority = PRIORITY_P0

        # 在范围内根据差异字段数量微调
        # 只变 1 个字段 → 取范围上限
        # 每多一个字段 → 递减
        num_diff = len(diff_fields)
        if num_diff == 1:
            score = base_score_range[1]
        else:
            # 每多一个字段扣 5 分
            penalty = (num_diff - 1) * 5
            score = base_score_range[0] + (base_score_range[1] - base_score_range[0]) * 0.3
            score = max(base_score_range[0], score - penalty)

        # 核心字段变更额外扣分（因为这些对学习阶段影响更大）
        core_diffs = [f for f in diff_fields if f in CORE_DNA_FIELDS]
        if core_diffs:
            score -= len(core_diffs) * 3

        score = max(0.0, min(100.0, score))

        return score, {
            "reason": f"变更了 {num_diff} 个字段，主导优先级 {dominant_priority}",
            "diff_fields": diff_fields,
            "priority": dominant_priority,
            "core_field_changes": core_diffs,
            "penalty_applied": num_diff > 1,
        }

    def _field_priority(self, field: str, variant_dna: dict) -> str:
        """根据字段名和变体中的 mutation_type 判断变更优先级。"""
        # 如果变体携带了 mutation_type，直接使用预定义映射
        mutation_type = str(variant_dna.get("mutation_type") or "").strip()
        if mutation_type and mutation_type in MUTATION_PRIORITY:
            return MUTATION_PRIORITY[mutation_type]

        # 否则根据字段名推断
        field_lower = field.lower()
        # P0 字段：颜色、光效、粒子类
        if field_lower in ("lighting", "color", "palette", "glow", "particle"):
            return PRIORITY_P0
        # P1 字段：姿势、镜头角度类
        if field_lower in ("camera", "composition", "pose", "camera_angle"):
            return PRIORITY_P1
        # P2 字段：角色类型、画风、场景类
        if field_lower in ("identity", "style", "scene", "subject", "character", "background", "hook", "mechanic"):
            return PRIORITY_P2
        # 默认 P1
        return PRIORITY_P1

    def _score_readability(self, variant_dna: dict) -> tuple[float, dict]:
        """评分 Facebook 移动端可读性。

        逻辑：
        - 居中构图 = 高分
        - 主体占 40-70% 画面 = 高分
        - 高对比度 = 高分
        - 简洁背景 = 高分
        - 元素过多 = 低分
        """
        score = 70.0  # 基础分
        reasons: list[str] = []

        # 构图分析
        composition = str(variant_dna.get("composition") or "").lower()
        if any(kw in composition for kw in CENTERED_KEYWORDS):
            score += 10
            reasons.append("居中构图，移动端友好")
        elif "wide" in composition or "全景" in composition:
            score -= 5
            reasons.append("广角构图，主体可能偏小")

        # 背景分析
        scene = str(variant_dna.get("scene") or "").lower()
        if any(kw in scene for kw in SIMPLE_BG_KEYWORDS):
            score += 8
            reasons.append("简洁背景，信息清晰")
        elif any(kw in scene for kw in COMPLEXITY_KEYWORDS):
            score -= 8
            reasons.append("复杂背景，可能分散注意力")

        # 光照/对比度分析
        lighting = str(variant_dna.get("lighting") or "").lower()
        if any(kw in lighting for kw in HIGH_CONTRAST_KEYWORDS):
            score += 8
            reasons.append("高对比光照，移动端清晰")
        elif "soft" in lighting or "ambient" in lighting:
            score -= 3
            reasons.append("柔光，对比度可能不足")

        # 镜头类型分析：特写 > 全景
        camera = str(variant_dna.get("camera") or "").lower()
        if any(kw in camera for kw in ("close up", "portrait", "特写", "近景")):
            score += 10
            reasons.append("特写/近景，主体突出")
        elif any(kw in camera for kw in ("wide", "panoramic", "广角", "全景")):
            score -= 8
            reasons.append("广角/全景，主体可能不突出")

        # 主体占比推断（基于 identity + composition）
        identity = str(variant_dna.get("identity") or "").lower()
        if identity and any(kw in camera for kw in ("close up", "portrait", "特写")):
            score += 5
            reasons.append("特写+角色，主体占画面大")

        # 元素数量检查：多角色/多生物降低可读性
        creature_count = self._estimate_creature_count(variant_dna)
        if creature_count >= 4:
            score -= 8
            reasons.append(f"元素过多（约{creature_count}个生物），降低可读性")
        elif creature_count >= 2:
            score -= 3
            reasons.append(f"多个生物（约{creature_count}个），略影响可读性")

        # CTA 文字分析
        cta = str(variant_dna.get("cta") or "").lower()
        if any(kw in cta for kw in ("big text", "large", "bold", "大字", "醒目")):
            score += 5
            reasons.append("大字 CTA，移动端易读")

        score = max(0.0, min(100.0, score))
        return score, {"reasons": reasons, "creature_count": creature_count}

    def _score_hook(self, variant_dna: dict) -> tuple[float, dict]:
        """评分钩子强度（停止滚动的能力）。

        逻辑：
        - Collection Hook（有生物/角色出现）= 高分
        - 角色直视镜头 = 高分
        - 鲜艳/饱和色彩 = 高分
        - 粒子/光效 = 中等加分
        - 情感触发（可爱、惊奇）= 高分
        """
        score = 60.0  # 基础分
        reasons: list[str] = []

        # Hook 类型分析
        hook = str(variant_dna.get("hook") or "").lower()
        if any(kw in hook for kw in COLLECTION_HOOK_KEYWORDS):
            score += 15
            reasons.append("Collection Hook，强烈组合吸引力")
        elif any(kw in hook for kw in ("crisis", "danger", "rescue", "危机", "救援")):
            score += 12
            reasons.append("危机 Hook，情感冲击强")
        elif any(kw in hook for kw in ("reward", "bonus", "爽", "奖励")):
            score += 10
            reasons.append("奖励 Hook，正向激励")
        elif any(kw in hook for kw in ("twist", "unexpected", "反转")):
            score += 10
            reasons.append("反转 Hook，好奇心驱动")

        # 角色直视镜头
        composition = str(variant_dna.get("composition") or "").lower()
        identity = str(variant_dna.get("identity") or "").lower()
        camera = str(variant_dna.get("camera") or "").lower()
        looking_text = f"{composition} {identity} {camera}"
        if any(kw in looking_text for kw in CAMERA_EYE_KEYWORDS):
            score += 12
            reasons.append("角色直视镜头，强烈的社交注视效果")

        # 色彩鲜艳度
        lighting = str(variant_dna.get("lighting") or "").lower()
        style = str(variant_dna.get("style") or "").lower()
        color_text = f"{lighting} {style}"
        if any(kw in color_text for kw in BRIGHT_KEYWORDS):
            score += 8
            reasons.append("鲜艳/发光色彩，视觉冲击强")

        # 粒子效果
        scene_text = f"{hook} {composition} {lighting}"
        if any(kw in scene_text for kw in PARTICLE_KEYWORDS):
            score += 6
            reasons.append("粒子/光效，增加视觉吸引力")

        # 情感触发
        emotion = str(variant_dna.get("emotion") or "").lower()
        if any(kw in emotion for kw in EMOTIONAL_HOOK_KEYWORDS):
            score += 10
            reasons.append("情感触发（可爱/惊奇），强停留力")
        elif any(kw in emotion for kw in ("epic", "fierce", "intense", "史诗", "激烈")):
            score += 8
            reasons.append("史诗/激烈情感，有冲击力")

        # 惊奇/神秘感
        if any(kw in scene_text for kw in ("mystery", "secret", "hidden", "神秘", "隐藏")):
            score += 7
            reasons.append("神秘/好奇心驱动，增加停留")

        # 无任何钩子特征
        if not reasons:
            score -= 5
            reasons.append("无明显钩子特征")

        score = max(0.0, min(100.0, score))
        return score, {"reasons": reasons, "hook_type": hook}

    def _score_visual_quality(self, variant_dna: dict) -> tuple[float, dict]:
        """评分 AI 生成画面质量可行性。

        逻辑：
        - 简单变更（颜色互换）= 非常高信心 (90+)
        - 生物替换 = 高 (80-90)
        - 场景变更 = 中等 (70-80)
        - 角色变更 = 较低 (60-70)
        - 复杂构图 = 较低
        """
        score = 75.0  # 基础分
        reasons: list[str] = []

        mutation_type = str(variant_dna.get("mutation_type") or "").strip()
        changed_fields = variant_dna.get("changed_fields") or []

        # 根据变更类型确定基础分数
        if mutation_type:
            if mutation_type in ("color_swap", "lighting_swap", "glow_swap", "particle_swap"):
                score = 92.0
                reasons.append(f"简单变更({mutation_type})，AI 生成质量高")
            elif mutation_type in ("subject_swap",):
                score = 82.0
                reasons.append("生物替换，AI 擅长此类变更")
            elif mutation_type in ("background_swap", "scene_swap"):
                score = 75.0
                reasons.append("场景变更，AI 需保持角色一致性")
            elif mutation_type in ("pose_swap", "camera_swap"):
                score = 78.0
                reasons.append("姿势/镜头变更，AI 需理解空间关系")
            elif mutation_type in ("costume_swap",):
                score = 72.0
                reasons.append("服装变更，AI 需处理细节一致性")
            elif mutation_type in ("character_swap", "style_swap", "emotion_swap"):
                score = 65.0
                reasons.append("角色/画风/情绪变更，AI 生成不确定性较高")
        else:
            # 无 mutation_type，从 changed_fields 推断
            if changed_fields:
                field = str(changed_fields[0]).lower() if changed_fields else ""
                if field in ("lighting", "color", "palette"):
                    score = 90.0
                    reasons.append(f"变更字段({field})简单，AI 擅长")
                elif field in ("scene", "background"):
                    score = 75.0
                    reasons.append(f"变更字段({field})中等难度")
                elif field in ("identity", "style"):
                    score = 65.0
                    reasons.append(f"变更字段({field})复杂，AI 不确定性高")

        # 风格对 AI 生成的影响
        style = str(variant_dna.get("style") or "").lower()
        if "3d render" in style or "3d" in style:
            score += 5
            reasons.append("3D 渲染风格，AI 生成质量稳定")
        elif "realistic" in style or "photo" in style:
            score -= 5
            reasons.append("写实风格，AI 可能生成伪影")
        elif "anime" in style or "cartoon" in style:
            score += 3
            reasons.append("卡通/动漫风格，AI 生成效果好")

        # 多元素检查
        creature_count = self._estimate_creature_count(variant_dna)
        if creature_count >= 3:
            score -= 8
            reasons.append(f"多生物({creature_count}个)，增加 AI 生成不一致风险")
        elif creature_count >= 2:
            score -= 3
            reasons.append(f"双生物({creature_count}个)，轻微增加不一致风险")

        # 手部/手指可见性检查
        identity = str(variant_dna.get("identity") or "").lower()
        composition = str(variant_dna.get("composition") or "").lower()
        pose_text = f"{identity} {composition}"
        if any(kw in pose_text for kw in ("hand", "finger", "holding", "手", "握")):
            score -= 8
            reasons.append("涉及手部/手指，AI 生成常见问题区域")

        score = max(0.0, min(100.0, score))
        return score, {"reasons": reasons, "mutation_type": mutation_type}

    def _score_brand(self, variant_dna: dict, base_dna: dict) -> tuple[float, dict]:
        """评分品牌一致性。

        逻辑：
        - 同角色类型 = 高分
        - 同风格（3D render）= 高分
        - 同色调 = 中高分
        - 同钩子类型 = 高分
        - 不同角色类型 = 低分
        """
        score = 80.0  # 基础分
        reasons: list[str] = []

        # 角色类型一致性
        v_identity = str(variant_dna.get("identity") or "").lower()
        b_identity = str(base_dna.get("identity") or "").lower()
        if v_identity and b_identity:
            if v_identity == b_identity:
                score += 10
                reasons.append(f"角色类型一致({v_identity})")
            elif self._same_character_family(v_identity, b_identity):
                score += 5
                reasons.append(f"角色类型相近({v_identity} ≈ {b_identity})")
            else:
                score -= 15
                reasons.append(f"角色类型不同({v_identity} vs {b_identity})，品牌断裂")

        # 风格一致性
        v_style = str(variant_dna.get("style") or "").lower()
        b_style = str(base_dna.get("style") or "").lower()
        if v_style and b_style:
            if v_style == b_style:
                score += 10
                reasons.append(f"画风一致({v_style})")
            elif "3d" in v_style and "3d" in b_style:
                score += 7
                reasons.append("同为 3D 渲染风格")
            elif "3d" not in v_style and "3d" in b_style:
                score -= 10
                reasons.append("画风从 3D 变为非 3D，品牌风格不一致")

        # 色调一致性
        v_lighting = str(variant_dna.get("lighting") or "").lower()
        b_lighting = str(base_dna.get("lighting") or "").lower()
        if v_lighting and b_lighting:
            if v_lighting == b_lighting:
                score += 5
                reasons.append("光照一致")
            elif self._same_color_mood(v_lighting, b_lighting):
                score += 3
                reasons.append("色调相近")
            else:
                score -= 3
                reasons.append("色调变化，品牌感略偏")

        # 钩子类型一致性
        v_hook = str(variant_dna.get("hook") or "").lower()
        b_hook = str(base_dna.get("hook") or "").lower()
        if v_hook and b_hook:
            if v_hook == b_hook:
                score += 8
                reasons.append(f"钩子类型一致({v_hook})")
            else:
                score -= 5
                reasons.append(f"钩子类型变化({v_hook} vs {b_hook})")

        # Merge Witches 特征检查
        identity_text = f"{v_identity} {v_style}"
        if any(kw in identity_text for kw in ("witch", "merge", "witches")):
            score += 5
            reasons.append("保留 Merge Witches 核心角色特征")

        score = max(0.0, min(100.0, score))
        return score, {"reasons": reasons}

    def _score_ai_confidence(self, variant_dna: dict, variant: dict) -> tuple[float, dict]:
        """评分 AI 生成信心度。

        逻辑：
        - P0 变更（颜色、光效、粒子）= 非常高信心 (90+)
        - P1 变更（姿势、镜头）= 高信心 (80-90)
        - P2 变更（角色类型、画风）= 中等信心 (60-75)
        - 多生物 = 略低
        - 手部/手指可见 = 低（AI 难点）
        """
        score = 75.0  # 基础分
        reasons: list[str] = []

        mutation_type = str(variant_dna.get("mutation_type") or variant.get("mutation_type") or "").strip()

        # 根据变更优先级确定基础分数
        if mutation_type:
            priority = MUTATION_PRIORITY.get(mutation_type, PRIORITY_P1)
            if priority == PRIORITY_P0:
                score = 92.0
                reasons.append(f"P0 变更({mutation_type})，AI 生成信心高")
            elif priority == PRIORITY_P1:
                score = 83.0
                reasons.append(f"P1 变更({mutation_type})，AI 生成信心中等")
            elif priority == PRIORITY_P2:
                score = 67.0
                reasons.append(f"P2 变更({mutation_type})，AI 生成信心偏低")
        else:
            # 从变更字段推断
            changed_fields = variant_dna.get("changed_fields") or variant.get("changed_fields") or []
            if changed_fields:
                # 取所有变更字段的最高优先级
                field_priorities = [self._field_priority(f, variant_dna) for f in changed_fields]
                if PRIORITY_P2 in field_priorities:
                    score = 67.0
                    reasons.append(f"含 P2 字段变更{changed_fields}，信心偏低")
                elif PRIORITY_P1 in field_priorities:
                    score = 83.0
                    reasons.append(f"含 P1 字段变更{changed_fields}，信心中等")
                else:
                    score = 92.0
                    reasons.append(f"仅 P0 字段变更{changed_fields}，信心高")

        # 多生物影响
        creature_count = self._estimate_creature_count(variant_dna)
        if creature_count >= 3:
            score -= 7
            reasons.append(f"多生物({creature_count}个)，AI 一致性风险增加")
        elif creature_count >= 2:
            score -= 3
            reasons.append(f"双生物({creature_count}个)，轻微一致性风险")

        # 手部/手指检查
        identity = str(variant_dna.get("identity") or "").lower()
        composition = str(variant_dna.get("composition") or "").lower()
        pose_text = f"{identity} {composition}"
        if any(kw in pose_text for kw in ("hand", "finger", "holding", "手", "握")):
            score -= 10
            reasons.append("涉及手部/手指，AI 常见失败区域")

        # 场景复杂度
        scene = str(variant_dna.get("scene") or "").lower()
        if any(kw in scene for kw in ("forest", "jungle", "city", "crowd", "森林", "城市")):
            score -= 5
            reasons.append("复杂场景，AI 细节生成不稳定")

        # 提示词质量指示
        style = str(variant_dna.get("style") or "").lower()
        if "3d render" in style:
            score += 3
            reasons.append("3D render 提示词明确，AI 理解准确")
        elif "abstract" in style or "抽象" in style:
            score -= 5
            reasons.append("抽象风格提示词模糊，AI 结果不可控")

        score = max(0.0, min(100.0, score))
        return score, {"reasons": reasons, "mutation_type": mutation_type}

    # ── 辅助方法 ──────────────────────────────────────────────────────────

    @staticmethod
    def _estimate_creature_count(variant_dna: dict) -> int:
        """估算变体中生物/角色数量。

        基于 hook/composition/identity 等字段中的关键词推断。
        """
        count = 1  # 默认有 1 个主体
        hook = str(variant_dna.get("hook") or "").lower()
        composition = str(variant_dna.get("composition") or "").lower()
        identity = str(variant_dna.get("identity") or "").lower()
        scene = str(variant_dna.get("scene") or "").lower()
        text = f"{hook} {composition} {identity} {scene}"

        # 明确的数量词
        for word, num in [("three", 3), ("four", 4), ("five", 5), ("six", 6),
                          ("many", 4), ("multiple", 3), ("group", 4), ("crowd", 5),
                          ("三", 3), ("四", 4), ("五", 5), ("多", 3), ("群", 4)]:
            if word in text:
                count = max(count, num)

        # Collection / 合成 特征暗示多生物
        if any(kw in text for kw in ("collection", "merge", "组合", "合成", "collection hook")):
            count = max(count, 3)

        # "two" / "双" / "pair"
        if any(kw in text for kw in ("two", "pair", "double", "双", "两")):
            count = max(count, 2)

        return count

    @staticmethod
    def _same_character_family(identity_a: str, identity_b: str) -> bool:
        """判断两个角色类型是否属于同一系列。

        例如：witch 和 wizard 都是魔法系，cat 和 fox 都是动物系。
        """
        magic_family = {"witch", "wizard", "mage", "sorcerer", "enchantress", "fairy", "warlock"}
        animal_family = {"cat", "owl", "fox", "rabbit", "bear", "wolf", "deer", "panda", "dragon"}
        human_family = {"princess", "knight", "warrior", "hero", "pirate", "ninja"}

        a_lower = identity_a.lower()
        b_lower = identity_b.lower()

        for family in (magic_family, animal_family, human_family):
            a_in = any(member in a_lower for member in family)
            b_in = any(member in b_lower for member in family)
            if a_in and b_in:
                return True
        return False

    @staticmethod
    def _same_color_mood(lighting_a: str, lighting_b: str) -> bool:
        """判断两种光照是否属于同一色调氛围。"""
        warm_keywords = {"sunset", "golden", "warm", "candlelight", "amber", "日落", "暖"}
        cool_keywords = {"blue", "moonlight", "neon", "cyan", "cool", "蓝", "冷"}
        neutral_keywords = {"natural", "soft", "ambient", "studio", "自然", "柔"}

        a_lower = lighting_a.lower()
        b_lower = lighting_b.lower()

        for mood_keywords in (warm_keywords, cool_keywords, neutral_keywords):
            a_in = any(kw in a_lower for kw in mood_keywords)
            b_in = any(kw in b_lower for kw in mood_keywords)
            if a_in and b_in:
                return True
        return False
