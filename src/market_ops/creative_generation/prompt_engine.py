"""Prompt Engine - 从 Decision Variant 生成 Master Prompt

输入: Decision Variant (含 DNA / changed_dimension / decision_score 等)
输出: Master Prompt (含完整提示词 + 参数)

核心功能:
- 从 Decision DNA 提取特征
- 选择对应 Hook 模板
- 填充模板参数
- 生成完整 Master Prompt
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .prompt_templates import PromptTemplateLibrary


@dataclass
class MasterPrompt:
    """主提示词"""
    prompt_id: str
    variant_id: str
    master_prompt: str
    hook_type: str
    style: str
    placement: str
    params: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt_id": self.prompt_id,
            "variant_id": self.variant_id,
            "master_prompt": self.master_prompt,
            "hook_type": self.hook_type,
            "style": self.style,
            "placement": self.placement,
            "params": self.params,
            "metadata": self.metadata,
        }


class PromptEngine:
    """提示词引擎

    将 Decision Engine 的输出转换为可直接用于 AI 生成的 Master Prompt。
    """

    def __init__(self):
        self.templates = PromptTemplateLibrary()

    # ------------------------------------------------------------------
    # 核心生成方法
    # ------------------------------------------------------------------
    def generate(
        self,
        variant: dict[str, Any],
        hook_type: str | None = None,
        style: str = "pixar",
        placement: str = "feed",
    ) -> MasterPrompt:
        """从单个 Decision Variant 生成 Master Prompt

        Args:
            variant: Decision Variant 字典
                包含: variant_id, dna, changed_dimension, new_value, risk_level 等
            hook_type: Hook 类型，默认从 variant 推断
            style: 风格
            placement: 版位

        Returns:
            MasterPrompt
        """
        variant_id = variant.get("variant_id", "unknown")
        dna = variant.get("dna", {})

        # 推断 hook_type
        if hook_type is None:
            hook_type = self._infer_hook_type(variant, dna)

        # 从 DNA 提取参数
        params = self._extract_params(dna, variant)

        # 使用模板生成
        master_text = self.templates.build_master_prompt(
            hook_type=hook_type,
            params=params,
            style=style,
            placement=placement,
        )

        # 如果模板生成失败，回退到基础生成
        if not master_text:
            master_text = self._fallback_generate(dna, variant, style, placement)

        return MasterPrompt(
            prompt_id=f"prompt_{variant_id}",
            variant_id=variant_id,
            master_prompt=master_text,
            hook_type=hook_type,
            style=style,
            placement=placement,
            params=params,
            metadata={
                "changed_dimension": variant.get("changed_dimension", ""),
                "new_value": variant.get("new_value", ""),
                "risk_level": variant.get("risk_level", ""),
                "decision_score": variant.get("decision_score", 0),
                "portfolio_tier": variant.get("portfolio_tier", ""),
            },
        )

    def generate_batch(
        self,
        variants: list[dict[str, Any]],
        hook_type: str | None = None,
        style: str = "pixar",
        placement: str = "feed",
    ) -> list[MasterPrompt]:
        """批量生成"""
        results = []
        for v in variants:
            try:
                mp = self.generate(v, hook_type, style, placement)
                results.append(mp)
            except Exception:
                continue
        return results

    # ------------------------------------------------------------------
    # 参数提取
    # ------------------------------------------------------------------
    def _extract_params(self, dna: dict[str, Any], variant: dict[str, Any]) -> dict[str, Any]:
        """从 DNA 和 Variant 中提取模板参数"""
        params: dict[str, Any] = {}

        # 角色
        character = dna.get("character", {})
        params["character"] = character.get("type", "witch")
        params["character_pose"] = character.get("pose", "standing centered")
        params["character_clothes"] = character.get("clothes", "magical robe")

        # 生物
        creatures = dna.get("creatures", [{}])
        if creatures:
            creature = creatures[0]
            creature_type = creature.get("type", "dragon")
            creature_color = creature.get("color", "blue")
            creature_glow = creature.get("glow", "cyan")
            params["creature_description"] = (
                f"cute baby {creature_type}, {creature_color} scales, {creature_glow} glow"
            )
        else:
            params["creature_description"] = "cute baby dragon, blue scales, cyan glow"

        # 环境
        env = dna.get("environment", {})
        params["environment_type"] = env.get("type", "magic_forest")
        params["time_of_day"] = env.get("time", "night")

        # 光照
        lighting = dna.get("lighting", {})
        params["lighting_type"] = lighting.get("color_temperature", "warm golden")

        # 构图 / 相机
        camera = dna.get("camera", {})
        params["camera_shot"] = camera.get("shot_type", "medium shot")
        params["camera_angle"] = camera.get("angle", "eye level")

        # 主体引用 (用于模板中的 {subject})
        params["subject"] = params["character"]
        params["subject_focus"] = params["character"]

        # Hook 相关
        hook = dna.get("hook", {})
        params["collection_item"] = hook.get("item", "magical crystal")
        params["hook_type"] = hook.get("type", "collection")

        # 颜色
        colors = dna.get("colors", {})
        mood = colors.get("mood_palette", ["balanced"])
        params["color_mood"] = mood[0] if isinstance(mood, list) else mood

        # 从 variant 补充
        changed_dim = variant.get("changed_dimension", "")
        new_val = variant.get("new_value", "")
        if changed_dim and new_val:
            params[f"changed_{changed_dim}"] = new_val

        return params

    # ------------------------------------------------------------------
    # Hook 类型推断
    # ------------------------------------------------------------------
    def _infer_hook_type(self, variant: dict[str, Any], dna: dict[str, Any]) -> str:
        """从 Variant / DNA 推断最合适的 Hook 类型"""
        # 1. 从 DNA 的 hook 字段
        hook = dna.get("hook", {})
        hook_type = hook.get("type", "")
        if hook_type and hook_type in self.templates.list_hook_types():
            return hook_type

        # 2. 从 changed_dimension 推断
        dim = variant.get("changed_dimension", "").lower()
        dim_map = {
            "creature": "collection",
            "character": "emotion",
            "lighting": "collection",
            "background": "collection",
            "camera": "collection",
            "hook_type": "collection",
        }
        if dim in dim_map:
            return dim_map[dim]

        # 3. 默认
        return "collection"

    # ------------------------------------------------------------------
    # 回退生成
    # ------------------------------------------------------------------
    def _fallback_generate(
        self,
        dna: dict[str, Any],
        variant: dict[str, Any],
        style: str,
        placement: str,
    ) -> str:
        """模板匹配失败时的回退生成"""
        params = self._extract_params(dna, variant)

        parts = [
            f"Ultra high quality mobile game advertisement",
            f"Cute chibi {params.get('character', 'witch')} girl",
            f"{params.get('creature_description', 'cute baby dragon')}",
            f"{params.get('environment_type', 'magic forest')}",
            f"{params.get('lighting_type', 'warm cinematic lighting')}",
            f"{params.get('camera_shot', 'close-up')}",
            f"Pixar quality",
            f"Golden particles",
            f"9:16 aspect ratio",
            f"Highly clickable Facebook game advertisement",
        ]

        # 加入风格
        style_mods = self.templates.get_style_modifier(style)
        if style_mods:
            parts.append(", ".join(style_mods[:3]))

        # 加入版位
        placement_mods = self.templates.get_placement_modifier(placement)
        if placement_mods:
            parts.append(", ".join(placement_mods[:2]))

        return ", ".join(parts)

    # ------------------------------------------------------------------
    # Facebook 专属优化
    # ------------------------------------------------------------------
    def generate_for_placement(
        self,
        variant: dict[str, Any],
        placement: str = "feed",
        hook_type: str | None = None,
        style: str = "pixar",
    ) -> MasterPrompt:
        """针对特定版位生成优化 Prompt"""
        mp = self.generate(variant, hook_type, style, placement)

        # 版位特定优化
        placement_extras = {
            "feed": "thumb-stopping, bold colors, clear at small size",
            "reels": "vertical 9:16, fast-paced, sound-on, loop-friendly",
            "stories": "vertical 9:16, quick hook, tap-friendly, 15s max",
            "audience_network": "clean, high contrast, clear focal point",
        }

        extra = placement_extras.get(placement.lower(), "")
        if extra:
            mp.master_prompt += f", {extra}"

        return mp

    def list_required_params(self, hook_type: str) -> list[str]:
        """获取某 Hook 类型所需的参数列表"""
        meta = self.templates.get_template_metadata(hook_type)
        return meta.get("required_params", [])
