"""Asset Consistency - 素材一致性控制

确保所有镜头在视觉风格上保持统一：
- Character（角色）
- UI（界面）
- Chest（宝箱）
- Dragon（龙）
- Background（背景）
- Logo
- Reward（奖励）
- Lighting（灯光）
- FX（特效）
- Theme（主题）
- Color（色彩）
- Typography（字体）

支持：
- Reference Image
- LoRA
- Embedding
- Image Reference
- Video Reference
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConsistencyProfile:
    """一致性配置"""
    variant_id: str
    character: dict[str, Any] = field(default_factory=dict)      # {type, lora, ref_image, embedding}
    ui: dict[str, Any] = field(default_factory=dict)             # {style, color, font}
    chest: dict[str, Any] = field(default_factory=dict)
    dragon: dict[str, Any] = field(default_factory=dict)
    background: dict[str, Any] = field(default_factory=dict)
    logo: dict[str, Any] = field(default_factory=dict)
    reward: dict[str, Any] = field(default_factory=dict)
    lighting: dict[str, str] = field(default_factory=dict)       # 灯光
    fx: dict[str, str] = field(default_factory=dict)             # 特效
    theme: str = ""                                              # fantasy / sci-fi / cute / dark
    color_palette: list[str] = field(default_factory=list)
    typography: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "character": self.character,
            "ui": self.ui,
            "chest": self.chest,
            "dragon": self.dragon,
            "background": self.background,
            "logo": self.logo,
            "reward": self.reward,
            "lighting": self.lighting,
            "fx": self.fx,
            "theme": self.theme,
            "color_palette": self.color_palette,
            "typography": self.typography,
        }


class AssetConsistency:
    """素材一致性控制"""

    # 主题 → 配色
    THEME_PALETTE: dict[str, list[str]] = {
        "fantasy":  ["#9B59B6", "#F1C40F", "#2C3E50", "#ECF0F1", "#E74C3C"],
        "sci-fi":   ["#3498DB", "#1ABC9C", "#34495E", "#ECF0F1", "#E67E22"],
        "cute":     ["#FF6B9D", "#FFC3A0", "#A8E6CF", "#FFFFFF", "#FFD3B5"],
        "dark":     ["#2C3E50", "#8E44AD", "#C0392B", "#ECF0F1", "#F39C12"],
        "magic":    ["#9B59B6", "#3498DB", "#F1C40F", "#E74C3C", "#FFFFFF"],
    }

    # 主题 → 字体
    THEME_TYPOGRAPHY: dict[str, dict[str, str]] = {
        "fantasy":  {"primary": "Cinzel",     "secondary": "Lora",      "weight": "bold"},
        "sci-fi":   {"primary": "Orbitron",   "secondary": "Rajdhani",  "weight": "medium"},
        "cute":     {"primary": "Fredoka",    "secondary": "Quicksand", "weight": "regular"},
        "dark":     {"primary": "Cinzel",     "secondary": "Inter",     "weight": "bold"},
        "magic":    {"primary": "Cinzel",     "secondary": "Quicksand", "weight": "bold"},
    }

    # 主题 → 灯光风格
    THEME_LIGHTING: dict[str, str] = {
        "fantasy":  "warm rim light + magical backlight",
        "sci-fi":   "neon glow + cool fill",
        "cute":     "soft diffuse + warm key",
        "dark":     "low-key + dramatic side light",
        "magic":    "volumetric + golden hour",
    }

    # 主题 → 特效风格
    THEME_FX: dict[str, str] = {
        "fantasy":  "magical particles + golden sparkles",
        "sci-fi":   "holographic glitch + neon trails",
        "cute":     "soft hearts + bubbles + pastel glow",
        "dark":     "smoke + lightning + red eyes",
        "magic":    "spell circles + glowing runes",
    }

    def __init__(self):
        self._theme_palette = {k: list(v) for k, v in self.THEME_PALETTE.items()}
        self._theme_typo = {k: dict(v) for k, v in self.THEME_TYPOGRAPHY.items()}
        self._theme_light = dict(self.THEME_LIGHTING)
        self._theme_fx = dict(self.THEME_FX)

    # ------------------------------------------------------------------
    # 核心方法
    # ------------------------------------------------------------------
    def build_profile(
        self,
        variant: dict[str, Any],
        strategy: Any,
    ) -> ConsistencyProfile:
        """构建一致性配置

        Args:
            variant: Decision Variant
            strategy: CreativeStrategy
        """
        dna = variant.get("dna", {})
        theme = self._infer_theme(dna, strategy)
        character_type = dna.get("character", {}).get("type", "witch")

        # 角色配置
        character_cfg = self._build_character_config(character_type, theme, dna)

        # UI 配置（基于主题）
        ui_cfg = {
            "style": theme,
            "primary_color": self._theme_palette[theme][0],
            "secondary_color": self._theme_palette[theme][1],
            "font": self._theme_typo[theme]["primary"],
        }

        # 宝箱 / 龙
        chest_cfg = self._build_object_config("chest", theme)
        dragon_cfg = self._build_object_config("dragon", theme)

        # 背景
        background_cfg = {
            "type": dna.get("environment", {}).get("type", "magic_forest"),
            "lighting": self._theme_light[theme],
            "depth": "mid-ground + background blur",
        }

        # Logo
        logo_cfg = {
            "position": "bottom_right",
            "opacity": 0.9,
            "animation": "fade_in",
            "duration": 1.5,
        }

        # Reward
        reward_cfg = {
            "style": self._theme_fx[theme],
            "particle_count": 50,
            "color": self._theme_palette[theme][1],
        }

        return ConsistencyProfile(
            variant_id=variant.get("variant_id", "unknown"),
            character=character_cfg,
            ui=ui_cfg,
            chest=chest_cfg,
            dragon=dragon_cfg,
            background=background_cfg,
            logo=logo_cfg,
            reward=reward_cfg,
            lighting={
                "primary": self._theme_light[theme],
                "intensity": "medium",
                "color_temp": "warm" if theme in ("fantasy", "magic", "cute") else "cool",
            },
            fx={
                "primary": self._theme_fx[theme],
                "intensity": "high" if strategy.priority >= 4 else "medium",
            },
            theme=theme,
            color_palette=list(self._theme_palette[theme]),
            typography=dict(self._theme_typo[theme]),
        )

    def apply_to_shot(self, profile: ConsistencyProfile, shot: Any) -> dict[str, Any]:
        """把一致性配置应用到单个镜头

        Returns:
            注入到 shot.prompt 后缀的一致性 prompt
        """
        consistency_suffix = (
            f"Style: {profile.theme} theme. "
            f"Color palette: {', '.join(profile.color_palette)}. "
            f"Lighting: {profile.lighting.get('primary', '')}. "
            f"FX: {profile.fx.get('primary', '')}. "
            f"Character consistency: {profile.character.get('ref_image', 'default')}. "
            f"UI: {profile.ui.get('style', '')} style, {profile.ui.get('font', '')} font. "
        )
        # 返回附加 prompt
        return {
            "consistency_prompt_suffix": consistency_suffix,
            "negative_prompt_addition": (
                "inconsistent character, style change, "
                "different color palette, mismatched lighting"
            ),
            "lora": profile.character.get("lora", ""),
            "embedding": profile.character.get("embedding", ""),
            "ref_image": profile.character.get("ref_image", ""),
            "ref_video": profile.character.get("ref_video", ""),
        }

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------
    def _infer_theme(self, dna: dict[str, Any], strategy: Any) -> str:
        """推断主题"""
        # 从 DNA 推断
        env = dna.get("environment", {}).get("type", "")
        if "forest" in env or "magic" in env or "castle" in env:
            return "fantasy"
        if "space" in env or "cyber" in env or "city" in env:
            return "sci-fi"
        if "candy" in env or "cute" in env:
            return "cute"
        if "dungeon" in env or "cave" in env:
            return "dark"
        if "magic" in env or "rune" in env:
            return "magic"
        # 从 changed_dim 推断
        dim = strategy.metadata.get("changed_dimension", "") if hasattr(strategy, "metadata") else ""
        if dim == "lighting":
            return "magic"
        return "fantasy"

    def _build_character_config(
        self,
        character_type: str,
        theme: str,
        dna: dict[str, Any],
    ) -> dict[str, Any]:
        """构造角色一致性配置"""
        char_dna = dna.get("character", {})
        return {
            "type": character_type,
            "outfit": char_dna.get("outfit", "default"),
            "color": char_dna.get("color", "primary"),
            "ref_image": char_dna.get("ref_image", f"character://{character_type}_ref"),
            "lora": char_dna.get("lora", f"lora://{character_type}_{theme}"),
            "embedding": char_dna.get("embedding", f"emb://{character_type}"),
            "ref_video": char_dna.get("ref_video", ""),
            "consistency_strength": 0.85,
        }

    def _build_object_config(self, obj_type: str, theme: str) -> dict[str, Any]:
        """构造物件配置"""
        return {
            "type": obj_type,
            "theme": theme,
            "ref_image": f"{obj_type}://{theme}_ref",
            "lora": f"lora://{obj_type}_{theme}",
            "color": self._theme_palette[theme][0],
        }
