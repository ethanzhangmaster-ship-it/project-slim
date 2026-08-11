"""E11 Phase 4.1 — Visual Analyzer（IAP 版）。

分析素材的视觉元素如何影响购买欲望：
  - composition: 主体是谁？角色/玩法/奖励哪个是焦点？
  - color:      色彩是否传达高级感？
  - emotion:    情绪是 curiosity/achievement/desire？
  - quality:    专业度 + 移动广告适配度

不是分析"是否漂亮"，而是分析"是否提升购买欲望"。
"""

from __future__ import annotations

from .models import (
    VisualFeatures,
    Composition,
    ColorProfile,
    EmotionProfile,
    QualityProfile,
    VisualSubject,
    ColorStyle,
)


class VisualAnalyzer:
    """视觉分析器。

    从 CreativeEntity 中读取视觉信息，生成 VisualFeatures。
    """

    # 主体检测关键词
    SUBJECT_KEYWORDS: dict[VisualSubject, list[str]] = {
        VisualSubject.CHARACTER: ["character", "dragon", "princess", "witch", "hero", "monster", "creature", "knight"],
        VisualSubject.ITEM: ["item", "weapon", "potion", "gem", "stone", "treasure", "chest", "tool"],
        VisualSubject.GAMEPLAY: ["gameplay", "merge", "match", "puzzle", "board", "grid", "level"],
        VisualSubject.REWARD: ["reward", "prize", "rare", "legendary", "epic", "special", "unlock", "bonus"],
        VisualSubject.SCENE: ["castle", "map", "island", "world", "area", "zone", "garden", "forest"],
        VisualSubject.UI: ["ui", "button", "menu", "shop", "store", "offer", "bundle"],
    }

    # 色彩 → 高级感映射
    COLOR_PREMIUM_MAP: dict[str, float] = {
        "vibrant": 60, "premium": 90, "dark": 70,
        "high_contrast": 50, "pastel": 40, "unknown": 30,
    }

    def analyze(self, entity) -> VisualFeatures:
        analysis = getattr(entity, "analysis", None)
        identity = getattr(entity, "identity", None)

        video_dna = getattr(analysis, "video_dna", {}) or {} if analysis else {}
        image_dna = getattr(analysis, "image_dna", {}) or {} if analysis else {}
        dna_data = video_dna if video_dna else image_dna
        style = getattr(analysis, "style", "") if analysis else ""
        name = getattr(identity, "name", "").lower() if identity else ""

        # Composition
        composition = self._analyze_composition(entity, dna_data, name)

        # Color
        color = self._analyze_color(style, dna_data)

        # Emotion
        emotion = self._analyze_emotion(entity, dna_data, name)

        # Quality
        quality = self._analyze_quality(dna_data)

        return VisualFeatures(
            composition=composition,
            color=color,
            emotion=emotion,
            quality=quality,
        )

    def analyze_batch(self, entities: list) -> list[VisualFeatures]:
        return [self.analyze(e) for e in entities]

    # ── Composition ──────────────────────────────────────

    def _analyze_composition(self, entity, dna_data: dict, name: str) -> Composition:
        # 主体检测
        subject = self._detect_subject(dna_data, name)

        # 中心焦点
        center_focus = dna_data.get("center_focus", dna_data.get("subject", ""))
        if not center_focus:
            center_focus = subject.value if subject != VisualSubject.UNKNOWN else "mixed"

        # 角色焦点
        character_focus = float(dna_data.get("character_focus", dna_data.get("character_scale", 0)) * 100
            if dna_data.get("character_scale") else 0)
        if character_focus == 0 and subject == VisualSubject.CHARACTER:
            character_focus = 70
        if character_focus == 0 and subject == VisualSubject.REWARD:
            character_focus = 40

        # 玩法焦点
        gameplay_focus = float(dna_data.get("gameplay_focus", 0))
        if gameplay_focus == 0 and subject == VisualSubject.GAMEPLAY:
            gameplay_focus = 80
        if gameplay_focus == 0 and "merge" in name:
            gameplay_focus = 60

        return Composition(
            center_focus=str(center_focus),
            character_focus=min(character_focus, 100),
            gameplay_focus=min(gameplay_focus, 100),
            subject=subject,
        )

    def _detect_subject(self, dna_data: dict, name: str) -> VisualSubject:
        raw = dna_data.get("subject", "")
        if raw:
            try:
                return VisualSubject(str(raw).lower())
            except ValueError:
                pass

        for vs, keywords in self.SUBJECT_KEYWORDS.items():
            for kw in keywords:
                if kw in name:
                    return vs
        return VisualSubject.MIXED

    # ── Color ────────────────────────────────────────────

    def _analyze_color(self, style: str, dna_data: dict) -> ColorProfile:
        saturation = float(dna_data.get("saturation", dna_data.get("contrast", 50)))
        contrast = float(dna_data.get("contrast", dna_data.get("contrast_score", 50)))
        if isinstance(contrast, float) and contrast <= 1:
            contrast *= 100

        # 高级感：从 style 推断
        premium = float(dna_data.get("premium_feeling", 0))
        if premium == 0:
            premium = self.COLOR_PREMIUM_MAP.get(style.lower(), 30)

        # 色彩风格
        try:
            color_style = ColorStyle(style.lower())
        except ValueError:
            color_style = ColorStyle.UNKNOWN

        return ColorProfile(
            saturation=min(saturation, 100),
            contrast=min(contrast, 100),
            premium_feeling=min(premium, 100),
            style=color_style,
        )

    # ── Emotion ──────────────────────────────────────────

    def _analyze_emotion(self, entity, dna_data: dict, name: str) -> EmotionProfile:
        analysis = getattr(entity, "analysis", None)
        hook_type = getattr(analysis, "hook_type", "").lower() if analysis else ""

        curiosity = float(dna_data.get("curiosity", 0))
        achievement = float(dna_data.get("achievement", 0))
        desire = float(dna_data.get("desire", 0))

        # 从 Hook 类型推断情绪
        if not curiosity and not achievement and not desire:
            if hook_type in ("rare_item", "reward_reveal"):
                desire = 85
                curiosity = 70
                achievement = 30
            elif hook_type == "collection":
                desire = 80
                achievement = 70
                curiosity = 40
            elif hook_type == "progression":
                achievement = 85
                desire = 50
                curiosity = 30
            elif hook_type == "impossible_result":
                curiosity = 90
                desire = 30
                achievement = 20
            elif hook_type == "curiosity":
                curiosity = 90
                desire = 20
                achievement = 10
            else:
                curiosity = 40
                achievement = 30
                desire = 30

        # 从名称增强
        if "rare" in name or "legendary" in name:
            desire = max(desire, 80)
        if "collect" in name:
            desire = max(desire, 70)
            achievement = max(achievement, 60)

        return EmotionProfile(
            curiosity=min(curiosity, 100),
            achievement=min(achievement, 100),
            desire=min(desire, 100),
        )

    # ── Quality ──────────────────────────────────────────

    def _analyze_quality(self, dna_data: dict) -> QualityProfile:
        professional = float(dna_data.get("professional_level", 60))
        mobile_fit = float(dna_data.get("mobile_ad_fit", 70))

        # 从复杂度反推
        complexity = float(dna_data.get("complexity", 0.5))
        if isinstance(complexity, float) and complexity <= 1:
            # 复杂度适中最好
            if 0.3 <= complexity <= 0.6:
                mobile_fit = 80
            elif complexity > 0.8:
                mobile_fit = 40

        return QualityProfile(
            professional_level=min(professional, 100),
            mobile_ad_fit=min(mobile_fit, 100),
        )