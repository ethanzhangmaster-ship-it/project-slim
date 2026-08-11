"""Storyboard Engine - 跨平台分镜引擎

把 CreativeScript 转换成完整的分镜（Scene）。
支持：
- Facebook (1:1, 4:5, 9:16)
- TikTok (9:16)
- Google (16:9, 1:1)

每个 Scene 包含：场景名、时长、情绪、动作、视觉参考、过渡
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StoryboardScene:
    """分镜场景"""
    scene_id: str
    scene_index: int
    name: str                     # Hook / Gameplay / Reward / CTA
    segment_type: str             # opening / gameplay / conflict / reward / cta / ending
    start_time: float
    end_time: float
    duration: float
    emotion: str                  # 场景情绪
    visual: str                   # 画面描述
    action: str                   # 动作描述
    transition_in: str            # 入场过渡
    transition_out: str           # 出场过渡
    aspect_ratio: str             # 1:1 / 9:16 / 4:5 / 16:9
    platform: str                 # facebook / tiktok / google
    camera_suggestion: str        # 镜头建议
    color_palette: list[str] = field(default_factory=list)
    reference_tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "scene_index": self.scene_index,
            "name": self.name,
            "segment_type": self.segment_type,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "emotion": self.emotion,
            "visual": self.visual,
            "action": self.action,
            "transition_in": self.transition_in,
            "transition_out": self.transition_out,
            "aspect_ratio": self.aspect_ratio,
            "platform": self.platform,
            "camera_suggestion": self.camera_suggestion,
            "color_palette": self.color_palette,
            "reference_tags": self.reference_tags,
        }


@dataclass
class Storyboard:
    """分镜"""
    storyboard_id: str
    variant_id: str
    platform: str
    aspect_ratio: str
    total_duration: float
    scenes: list[StoryboardScene] = field(default_factory=list)
    script_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "storyboard_id": self.storyboard_id,
            "variant_id": self.variant_id,
            "platform": self.platform,
            "aspect_ratio": self.aspect_ratio,
            "total_duration": self.total_duration,
            "scenes": [s.to_dict() for s in self.scenes],
            "script_id": self.script_id,
            "metadata": self.metadata,
        }


class StoryboardEngine:
    """跨平台分镜引擎"""

    # 平台 → 画幅比例
    PLATFORM_ASPECT: dict[str, str] = {
        "facebook_feed": "1:1",
        "facebook_reels": "9:16",
        "facebook_stories": "9:16",
        "tiktok": "9:16",
        "google_display": "16:9",
        "google_short": "9:16",
    }

    # 平台别名归一
    PLATFORM_ALIAS: dict[str, str] = {
        "facebook": "facebook_feed",
        "fb": "facebook_feed",
        "reels": "facebook_reels",
        "stories": "facebook_stories",
        "ig": "facebook_reels",
        "instagram": "facebook_reels",
        "google": "google_display",
        "youtube": "google_display",
    }

    # 段落类型 → 场景名
    SEGMENT_TO_SCENE_NAME: dict[str, str] = {
        "opening": "Hook",
        "gameplay": "Gameplay",
        "conflict": "Conflict",
        "reward": "Reward",
        "cta": "CTA",
        "ending": "Ending",
    }

    # 段落类型 → 场景情绪
    SEGMENT_TO_EMOTION: dict[str, str] = {
        "opening": "好奇/期待",
        "gameplay": "兴奋/沉浸",
        "conflict": "紧张/挑战",
        "reward": "满足/惊喜",
        "cta": "果断/行动",
        "ending": "温暖/品牌",
    }

    # 段落类型 → 过渡
    TRANSITION_PAIRS: dict[str, tuple[str, str]] = {
        "opening":   ("Fade In",       "Match Cut"),
        "gameplay":  ("Match Cut",     "Whip Pan"),
        "conflict":  ("Whip Pan",      "Quick Cut"),
        "reward":    ("Quick Cut",     "Flash"),
        "cta":       ("Flash",         "Dissolve"),
        "ending":    ("Dissolve",      "Fade Out"),
    }

    # 段落类型 → 镜头建议
    SEGMENT_TO_CAMERA: dict[str, str] = {
        "opening":   "Push In / Close-up",
        "gameplay":  "Tracking / Following",
        "conflict":  "Handheld / Tilt",
        "reward":    "Orbit / Push + Zoom",
        "cta":       "Static / Locked",
        "ending":    "Pull Out / Wide",
    }

    # 段落类型 → 色板
    SEGMENT_COLOR_PALETTE: dict[str, list[str]] = {
        "opening":   ["#FFD700", "#FF6B6B", "#1A1A2E"],
        "gameplay":  ["#4ECDC4", "#45B7D1", "#F7DC6F"],
        "conflict":  ["#E74C3C", "#2C3E50", "#ECF0F1"],
        "reward":    ["#F1C40F", "#E67E22", "#FFFFFF"],
        "cta":       ["#27AE60", "#FFFFFF", "#000000"],
        "ending":    ["#3498DB", "#9B59B6", "#FFFFFF"],
    }

    # 段落类型 → 参考标签
    SEGMENT_REF_TAGS: dict[str, list[str]] = {
        "opening":   ["intro", "hook", "curiosity"],
        "gameplay":  ["core-loop", "ui", "interaction"],
        "conflict":  ["challenge", "tension", "choice"],
        "reward":    ["celebration", "fx", "victory"],
        "cta":       ["download", "button", "brand"],
        "ending":    ["logo", "brand-recall", "warm"],
    }

    def __init__(self):
        self._aspect = dict(self.PLATFORM_ASPECT)
        self._alias = dict(self.PLATFORM_ALIAS)
        self._scene_name = dict(self.SEGMENT_TO_SCENE_NAME)
        self._emotion = dict(self.SEGMENT_TO_EMOTION)
        self._trans = dict(self.TRANSITION_PAIRS)
        self._camera = dict(self.SEGMENT_TO_CAMERA)
        self._palette = dict(self.SEGMENT_COLOR_PALETTE)
        self._refs = dict(self.SEGMENT_REF_TAGS)

    # ------------------------------------------------------------------
    # 核心方法
    # ------------------------------------------------------------------
    def build(
        self,
        script: Any,                  # CreativeScript
        strategy: Any,                # CreativeStrategy
        platform: str | None = None,
    ) -> Storyboard:
        """根据 CreativeScript 生成分镜

        Args:
            script: 广告脚本
            strategy: 创意策略
            platform: 平台别名（facebook/tiktok/google 等）
        """
        platform_norm = self._normalize_platform(platform or strategy.platform)
        aspect_ratio = self._aspect.get(platform_norm, "1:1")

        scenes: list[StoryboardScene] = []
        for idx, seg in enumerate(script.segments):
            seg_type = seg.segment_type
            scene = StoryboardScene(
                scene_id=f"scene_{script.variant_id}_{idx+1:02d}",
                scene_index=idx + 1,
                name=self._scene_name.get(seg_type, seg_type),
                segment_type=seg_type,
                start_time=seg.start_time,
                end_time=seg.end_time,
                duration=seg.duration,
                emotion=self._emotion.get(seg_type, "中性"),
                visual=seg.visual,
                action=seg.action,
                transition_in=self._trans.get(seg_type, ("Cut", "Cut"))[0],
                transition_out=self._trans.get(seg_type, ("Cut", "Cut"))[1],
                aspect_ratio=aspect_ratio,
                platform=platform_norm,
                camera_suggestion=self._camera.get(seg_type, "Static"),
                color_palette=list(self._palette.get(seg_type, [])),
                reference_tags=list(self._refs.get(seg_type, [])),
            )
            scenes.append(scene)

        return Storyboard(
            storyboard_id=f"storyboard_{script.variant_id}",
            variant_id=script.variant_id,
            platform=platform_norm,
            aspect_ratio=aspect_ratio,
            total_duration=script.total_duration,
            scenes=scenes,
            script_id=script.script_id,
            metadata={
                "hook": strategy.hook,
                "objective": strategy.objective,
                "emotion": strategy.emotion,
                "scene_count": len(scenes),
            },
        )

    def build_multi_platform(
        self,
        script: Any,
        strategy: Any,
        platforms: list[str] | None = None,
    ) -> list[Storyboard]:
        """一次输出多平台分镜

        Args:
            script: 广告脚本
            strategy: 创意策略
            platforms: 平台列表，默认 facebook/tiktok/google
        """
        if platforms is None:
            platforms = ["facebook", "tiktok", "google"]
        return [self.build(script, strategy, p) for p in platforms]

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------
    def _normalize_platform(self, platform: str) -> str:
        """平台名归一"""
        p = (platform or "").lower().strip()
        if p in self._aspect:
            return p
        if p in self._alias:
            return self._alias[p]
        # 平台包含关键字
        for k, v in self._alias.items():
            if k in p:
                return v
        return "facebook_feed"

    # ------------------------------------------------------------------
    # 格式化
    # ------------------------------------------------------------------
    def format_as_text(self, storyboard: Storyboard) -> str:
        """分镜文本格式"""
        lines = [
            f"# {storyboard.storyboard_id}",
            f"平台: {storyboard.platform} | 画幅: {storyboard.aspect_ratio}",
            f"总时长: {storyboard.total_duration}秒 | 场景数: {len(storyboard.scenes)}",
            "",
        ]
        for scene in storyboard.scenes:
            lines.extend([
                f"## Scene {scene.scene_index:02d} - {scene.name} [{scene.start_time}-{scene.end_time}秒]",
                f"情绪: {scene.emotion}",
                f"画面: {scene.visual}",
                f"动作: {scene.action}",
                f"镜头: {scene.camera_suggestion}",
                f"过渡: {scene.transition_in} → {scene.transition_out}",
                f"色板: {', '.join(scene.color_palette)}",
                f"标签: {', '.join(scene.reference_tags)}",
                "",
            ])
        return "\n".join(lines)
