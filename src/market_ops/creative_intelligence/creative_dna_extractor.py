"""E11 Phase 4.1 — Creative DNA Extractor。

把分析结果转成下一代生产规则。

输入：
  CreativeAnalysis + PerformanceData (ROAS)

输出：
  CreativeDNA V2（hook / scene / emotion / monetization）

连接 Phase 4.2 的 Creative DNA Evolution。
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

from .models import (
    CreativeAnalysis,
    VisualFeatures,
    HookFeatures,
    GameplayFeatures,
    MonetizationFeatures,
)


@dataclass
class CreativeDNA:
    """Creative DNA V2 — 制作规则。

    从分析结果提取的，可指导下一轮素材生产的 DNA。

    字段：
      - hook:          Hook 类型
      - scene:         场景描述
      - emotion:       情绪方向
      - monetization:  变现策略
      - visual_rules:  视觉制作规则
      - avoid_rules:   避免规则
    """

    hook: str = ""
    scene: str = ""
    emotion: str = ""
    monetization: str = ""
    visual_rules: list[str] = field(default_factory=list)
    avoid_rules: list[str] = field(default_factory=list)
    roas_correlation: float = 0.0          # 与 ROAS 的关联度

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CreativeDNA:
        return cls(
            hook=data.get("hook", ""),
            scene=data.get("scene", ""),
            emotion=data.get("emotion", ""),
            monetization=data.get("monetization", ""),
            visual_rules=data.get("visual_rules", []),
            avoid_rules=data.get("avoid_rules", []),
            roas_correlation=float(data.get("roas_correlation", 0)),
        )


# Hook → Creative DNA 映射
HOOK_TO_DNA: dict[str, dict[str, str]] = {
    "rare_item": {
        "hook": "rare_collection_reward",
        "scene": "fantasy treasure opening",
        "emotion": "desire",
        "monetization": "exclusive_character_unlock",
    },
    "collection": {
        "hook": "collection_completion",
        "scene": "collection progress showcase",
        "emotion": "achievement",
        "monetization": "collection_bundle_purchase",
    },
    "reward_reveal": {
        "hook": "rare_reward_reveal",
        "scene": "mystery box opening",
        "emotion": "curiosity",
        "monetization": "premium_currency_purchase",
    },
    "progression": {
        "hook": "progression_milestone",
        "scene": "level up celebration",
        "emotion": "achievement",
        "monetization": "progression_boost_purchase",
    },
    "before_after": {
        "hook": "transformation_reveal",
        "scene": "before/after comparison",
        "emotion": "achievement",
        "monetization": "upgrade_acceleration",
    },
    "impossible_result": {
        "hook": "impossible_merge_result",
        "scene": "shocking outcome",
        "emotion": "curiosity",
        "monetization": "low_iap_value",
    },
    "curiosity": {
        "hook": "clickbait_curiosity",
        "scene": "attention grab",
        "emotion": "curiosity",
        "monetization": "low_iap_value",
    },
}

# Visual → 制作规则
VISUAL_RULE_MAP: dict[str, list[str]] = {
    "character_focus": ["use large character as focal point", "character should occupy >30% of frame"],
    "gameplay_focus": ["show clear gameplay in first 3 seconds", "demonstrate merge/combine action"],
    "reward_focus": ["highlight reward at center", "use glow/sparkle effect on reward"],
}

# 避免规则
AVOID_RULES = {
    "clickbait": ["avoid curiosity-only hooks", "avoid misleading thumbnails"],
    "low_character": ["avoid small character size", "avoid empty backgrounds"],
    "low_reward": ["avoid hiding rewards", "avoid unclear reward preview"],
    "low_monetization": ["avoid no IAP value display", "avoid pure gameplay without reward"],
}


class CreativeDNAExtractor:
    """Creative DNA 提取器。

    从 CreativeAnalysis 中提取 CreativeDNA，
    结合 PerformanceData 计算 ROAS 关联度。
    """

    def extract(
        self,
        analysis: CreativeAnalysis,
        roas_d30: float | None = None,
    ) -> CreativeDNA:
        """从单次分析提取 DNA。

        Args:
            analysis: CreativeAnalysis 结果
            roas_d30: 可选的 D30 ROAS 值

        Returns:
            CreativeDNA: 生产规则
        """
        hook = str(analysis.hook_features.hook_type.value)

        # 从 Hook 映射获取 DNA
        dna_map = HOOK_TO_DNA.get(hook, HOOK_TO_DNA["curiosity"])
        dna_hook = dna_map["hook"]
        dna_scene = dna_map["scene"]
        dna_emotion = dna_map["emotion"]
        dna_monetization = dna_map["monetization"]

        # 视觉制作规则
        visual_rules = self._extract_visual_rules(analysis.visual_features)

        # 避免规则
        avoid_rules = self._extract_avoid_rules(
            analysis.visual_features, analysis.hook_features, analysis.monetization_features,
        )

        # ROAS 关联度
        roas_correlation = self._compute_roas_correlation(analysis, roas_d30)

        return CreativeDNA(
            hook=dna_hook,
            scene=dna_scene,
            emotion=dna_emotion,
            monetization=dna_monetization,
            visual_rules=visual_rules,
            avoid_rules=avoid_rules,
            roas_correlation=roas_correlation,
        )

    def extract_batch(
        self,
        analyses: list[CreativeAnalysis],
        roas_map: dict[str, float] | None = None,
    ) -> list[CreativeDNA]:
        """批量提取 DNA。"""
        roas_map = roas_map or {}
        return [
            self.extract(a, roas_d30=roas_map.get(a.creative_id))
            for a in analyses
        ]

    # ── 视觉规则 ─────────────────────────────────────────

    def _extract_visual_rules(self, visual: VisualFeatures) -> list[str]:
        rules: list[str] = []

        comp = visual.composition
        if comp.character_focus >= 60:
            rules.extend(VISUAL_RULE_MAP.get("character_focus", []))
        if comp.gameplay_focus >= 60:
            rules.extend(VISUAL_RULE_MAP.get("gameplay_focus", []))
        if comp.center_focus == "reward":
            rules.extend(VISUAL_RULE_MAP.get("reward_focus", []))

        color = visual.color
        if color.premium_feeling >= 70:
            rules.append("use premium color palette (gold/purple)")
        if color.saturation >= 70:
            rules.append("maintain high saturation for visual pop")

        return rules

    # ── 避免规则 ─────────────────────────────────────────

    def _extract_avoid_rules(
        self, visual: VisualFeatures, hook: HookFeatures, monetization: MonetizationFeatures,
    ) -> list[str]:
        avoid: list[str] = []

        if hook.is_clickbait:
            avoid.extend(AVOID_RULES["clickbait"])
        if visual.composition.character_focus < 30:
            avoid.extend(AVOID_RULES["low_character"])
        if hook.reward_expectation < 40:
            avoid.extend(AVOID_RULES["low_reward"])
        if not monetization.is_high_monetization:
            avoid.extend(AVOID_RULES["low_monetization"])

        return avoid

    # ── ROAS 关联 ────────────────────────────────────────

    def _compute_roas_correlation(
        self, analysis: CreativeAnalysis, roas_d30: float | None,
    ) -> float:
        """计算 DNA 与 ROAS 的关联度。

        ROAS ≥ 2.0 → 关联度 1.0
        ROAS < 0.5 → 关联度 0.0
        """
        if roas_d30 is None:
            return 0.0
        return min(max(roas_d30 / 2.0, 0.0), 1.0)