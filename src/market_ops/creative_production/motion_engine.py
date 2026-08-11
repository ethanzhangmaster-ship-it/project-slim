"""Motion Engine - 动作引擎

生成各种动作描述：
- Character Motion（角色动作）
- Camera Motion（镜头运动）
- Object Motion（物体动作）
- FX Motion（特效动作）

例如：
- Dragon Fly
- Coin Explosion
- Magic Glow
- Camera Zoom
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MotionSpec:
    """动作规格"""
    name: str
    category: str            # character / camera / object / fx
    duration_range: tuple[float, float] = (1.0, 3.0)
    intensity: float = 0.5   # 0-1
    description: str = ""
    prompt_phrase: str = ""  # 用在 prompt 中的短语
    best_for: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "duration_range": list(self.duration_range),
            "intensity": self.intensity,
            "description": self.description,
            "prompt_phrase": self.prompt_phrase,
            "best_for": self.best_for,
        }


class MotionEngine:
    """动作引擎"""

    # 角色动作库
    CHARACTER_MOTIONS: dict[str, MotionSpec] = {
        "dragon_fly": MotionSpec(
            name="dragon_fly", category="character",
            duration_range=(2.0, 5.0), intensity=0.7,
            description="飞龙飞过镜头",
            prompt_phrase="a dragon flies across the scene, wings spread, fire breath optional",
            best_for=["opening", "gameplay", "reward"],
        ),
        "character_walk": MotionSpec(
            name="character_walk", category="character",
            duration_range=(2.0, 4.0), intensity=0.4,
            description="角色行走",
            prompt_phrase="character walks confidently through the environment",
            best_for=["gameplay", "story"],
        ),
        "character_jump": MotionSpec(
            name="character_jump", category="character",
            duration_range=(0.5, 1.5), intensity=0.6,
            description="角色跳跃",
            prompt_phrase="character jumps with excitement, arms up",
            best_for=["reward", "opening"],
        ),
        "character_celebrate": MotionSpec(
            name="character_celebrate", category="character",
            duration_range=(1.5, 3.0), intensity=0.8,
            description="角色庆祝",
            prompt_phrase="character celebrates with arms raised, big smile, victory pose",
            best_for=["reward", "ending"],
        ),
        "character_react_surprise": MotionSpec(
            name="character_react_surprise", category="character",
            duration_range=(0.5, 1.5), intensity=0.7,
            description="角色惊讶反应",
            prompt_phrase="character reacts with surprise, eyes wide, slight lean back",
            best_for=["opening"],
        ),
        "character_collect": MotionSpec(
            name="character_collect", category="character",
            duration_range=(0.5, 1.5), intensity=0.4,
            description="角色收集物品",
            prompt_phrase="character reaches out and collects glowing item",
            best_for=["gameplay", "collection"],
        ),
        "character_merge": MotionSpec(
            name="character_merge", category="character",
            duration_range=(1.0, 2.5), intensity=0.6,
            description="角色合并",
            prompt_phrase="character merges two items with a swipe gesture",
            best_for=["merge"],
        ),
        "character_transform": MotionSpec(
            name="character_transform", category="character",
            duration_range=(2.0, 4.0), intensity=0.9,
            description="角色变身",
            prompt_phrase="character transforms with magical energy, new form revealed",
            best_for=["transformation", "reward"],
        ),
    }

    # 物体动作
    OBJECT_MOTIONS: dict[str, MotionSpec] = {
        "coin_explosion": MotionSpec(
            name="coin_explosion", category="object",
            duration_range=(1.0, 2.0), intensity=0.9,
            description="金币爆炸",
            prompt_phrase="coins burst out from chest, scatter in arc",
            best_for=["reward", "ending"],
        ),
        "chest_open": MotionSpec(
            name="chest_open", category="object",
            duration_range=(1.0, 2.0), intensity=0.7,
            description="宝箱开启",
            prompt_phrase="treasure chest opens with light beam, glow intensifies",
            best_for=["reward", "opening"],
        ),
        "magic_glow": MotionSpec(
            name="magic_glow", category="object",
            duration_range=(1.0, 3.0), intensity=0.5,
            description="魔法发光",
            prompt_phrase="magical glow pulses around object, particles drift",
            best_for=["opening", "gameplay", "reward"],
        ),
        "item_rotate": MotionSpec(
            name="item_rotate", category="object",
            duration_range=(2.0, 4.0), intensity=0.4,
            description="物品旋转",
            prompt_phrase="rare item rotates slowly, glowing edges",
            best_for=["opening", "reward"],
        ),
        "sparkle_trail": MotionSpec(
            name="sparkle_trail", category="object",
            duration_range=(1.5, 3.0), intensity=0.5,
            description="闪光拖尾",
            prompt_phrase="sparkle trail follows character movement",
            best_for=["gameplay", "opening"],
        ),
        "ui_pop": MotionSpec(
            name="ui_pop", category="object",
            duration_range=(0.3, 0.8), intensity=0.4,
            description="UI 弹出",
            prompt_phrase="UI element pops in with bounce, score +100 floats up",
            best_for=["gameplay", "reward"],
        ),
        "level_up_burst": MotionSpec(
            name="level_up_burst", category="object",
            duration_range=(1.5, 3.0), intensity=0.9,
            description="升级爆发",
            prompt_phrase="level up text appears with radial burst, glowing ring expands",
            best_for=["reward"],
        ),
    }

    # 镜头运动
    CAMERA_MOTIONS: dict[str, MotionSpec] = {
        "camera_zoom": MotionSpec(
            name="camera_zoom", category="camera",
            duration_range=(1.0, 2.0), intensity=0.6,
            description="镜头推进/拉远",
            prompt_phrase="camera zooms in slowly toward subject",
            best_for=["reward", "opening"],
        ),
        "camera_pan": MotionSpec(
            name="camera_pan", category="camera",
            duration_range=(2.0, 4.0), intensity=0.4,
            description="镜头横摇",
            prompt_phrase="camera pans horizontally revealing scene",
            best_for=["gameplay", "reveal"],
        ),
        "camera_orbit": MotionSpec(
            name="camera_orbit", category="camera",
            duration_range=(2.0, 4.0), intensity=0.7,
            description="镜头环绕",
            prompt_phrase="camera orbits around subject, 360 degrees",
            best_for=["reward", "boss"],
        ),
        "camera_shake": MotionSpec(
            name="camera_shake", category="camera",
            duration_range=(0.5, 1.5), intensity=0.9,
            description="镜头震动",
            prompt_phrase="camera shakes with impact, slight motion blur",
            best_for=["conflict", "fail"],
        ),
    }

    # 特效动作
    FX_MOTIONS: dict[str, MotionSpec] = {
        "fire_explosion": MotionSpec(
            name="fire_explosion", category="fx",
            duration_range=(0.5, 1.5), intensity=0.9,
            description="火焰爆发",
            prompt_phrase="fire explosion with smoke and sparks",
            best_for=["reward", "conflict"],
        ),
        "ice_shatter": MotionSpec(
            name="ice_shatter", category="fx",
            duration_range=(0.5, 1.5), intensity=0.8,
            description="冰晶破碎",
            prompt_phrase="ice crystals shatter into fragments",
            best_for=["conflict", "fail"],
        ),
        "lightning_strike": MotionSpec(
            name="lightning_strike", category="fx",
            duration_range=(0.3, 1.0), intensity=0.9,
            description="闪电击打",
            prompt_phrase="lightning strikes from sky, flash illuminates scene",
            best_for=["conflict", "reward"],
        ),
        "confetti_rain": MotionSpec(
            name="confetti_rain", category="fx",
            duration_range=(2.0, 4.0), intensity=0.7,
            description="彩纸雨",
            prompt_phrase="colorful confetti rains down, golden sparkles",
            best_for=["reward", "ending"],
        ),
        "magic_circle": MotionSpec(
            name="magic_circle", category="fx",
            duration_range=(1.5, 3.0), intensity=0.6,
            description="魔法阵",
            prompt_phrase="glowing magic circle appears on ground, runes activate",
            best_for=["opening", "transformation", "reward"],
        ),
        "particle_burst": MotionSpec(
            name="particle_burst", category="fx",
            duration_range=(0.5, 2.0), intensity=0.7,
            description="粒子爆发",
            prompt_phrase="particle burst in radial pattern, golden sparkles",
            best_for=["reward", "opening"],
        ),
    }

    def __init__(self):
        self._char = dict(self.CHARACTER_MOTIONS)
        self._obj = dict(self.OBJECT_MOTIONS)
        self._cam = dict(self.CAMERA_MOTIONS)
        self._fx = dict(self.FX_MOTIONS)

    # ------------------------------------------------------------------
    # 核心方法
    # ------------------------------------------------------------------
    def get_motion(self, name: str) -> MotionSpec | None:
        """获取指定动作"""
        for lib in (self._char, self._obj, self._cam, self._fx):
            if name in lib:
                return lib[name]
        return None

    def list_by_category(self, category: str) -> list[MotionSpec]:
        """按类别列出动作"""
        lib_map = {
            "character": self._char,
            "object": self._obj,
            "camera": self._cam,
            "fx": self._fx,
        }
        return list(lib_map.get(category, {}).values())

    def recommend_for_segment(self, segment_type: str) -> dict[str, list[MotionSpec]]:
        """为段落推荐动作组合"""
        recs: dict[str, list[MotionSpec]] = {
            "character": [],
            "object": [],
            "camera": [],
            "fx": [],
        }

        if segment_type == "opening":
            recs["character"] = [self._char["character_react_surprise"]]
            recs["object"] = [self._obj["item_rotate"], self._obj["magic_glow"]]
            recs["fx"] = [self._fx["magic_circle"]]
        elif segment_type == "gameplay":
            recs["character"] = [self._char["character_walk"], self._char["character_collect"]]
            recs["object"] = [self._obj["ui_pop"], self._obj["sparkle_trail"]]
        elif segment_type == "conflict":
            recs["character"] = [self._char["character_walk"]]
            recs["fx"] = [self._fx["lightning_strike"], self._fx["ice_shatter"]]
            recs["camera"] = [self._cam["camera_shake"]]
        elif segment_type == "reward":
            recs["character"] = [self._char["character_celebrate"]]
            recs["object"] = [self._obj["coin_explosion"], self._obj["chest_open"], self._obj["level_up_burst"]]
            recs["fx"] = [self._fx["confetti_rain"], self._fx["particle_burst"]]
            recs["camera"] = [self._cam["camera_orbit"]]
        elif segment_type == "cta":
            recs["character"] = [self._char["character_celebrate"]]
        elif segment_type == "ending":
            recs["character"] = [self._char["character_celebrate"]]
            recs["object"] = [self._obj["magic_glow"]]
            recs["fx"] = [self._fx["confetti_rain"]]

        return recs

    def build_motion_prompt(
        self,
        segment_type: str,
    ) -> str:
        """为段落构造动作 Prompt"""
        recs = self.recommend_for_segment(segment_type)
        parts: list[str] = []
        for category, motions in recs.items():
            for m in motions:
                if m.prompt_phrase:
                    parts.append(m.prompt_phrase)
        return ", ".join(parts)

    def list_all(self) -> list[str]:
        """列出所有动作"""
        all_motions = []
        for lib in (self._char, self._obj, self._cam, self._fx):
            all_motions.extend(lib.keys())
        return all_motions
