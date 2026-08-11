"""Shot Generator - 镜头拆解引擎

把每个 Scene 拆成可执行的 Shot。
每个 Shot 包含：
- Shot ID
- Prompt（给 AI 视频模型的提示词）
- Camera（运镜）
- Motion（动作）
- Duration（时长）
- FX（特效）
- Transition（过渡）
- Sound（声音）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Shot:
    """单个镜头"""
    shot_id: str
    scene_id: str
    shot_index: int
    name: str
    duration: float
    start_time: float
    end_time: float
    prompt: str                  # 视频生成 Prompt
    negative_prompt: str         # 反向提示词
    camera: str                  # 运镜
    camera_motion: str           # 镜头运动描述
    character_motion: str        # 角色动作
    object_motion: str           # 物体动作
    fx: list[str] = field(default_factory=list)  # 特效
    transition_in: str = ""      # 入场过渡
    transition_out: str = ""     # 出场过渡
    sound_effects: list[str] = field(default_factory=list)
    music_cue: str = ""          # BGM 提示
    dialogue: str = ""           # 旁白/对白
    subtitle: str = ""           # 字幕
    lighting: str = ""           # 灯光
    color_grading: str = ""      # 调色
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "shot_id": self.shot_id,
            "scene_id": self.scene_id,
            "shot_index": self.shot_index,
            "name": self.name,
            "duration": self.duration,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "prompt": self.prompt,
            "negative_prompt": self.negative_prompt,
            "camera": self.camera,
            "camera_motion": self.camera_motion,
            "character_motion": self.character_motion,
            "object_motion": self.object_motion,
            "fx": self.fx,
            "transition_in": self.transition_in,
            "transition_out": self.transition_out,
            "sound_effects": self.sound_effects,
            "music_cue": self.music_cue,
            "dialogue": self.dialogue,
            "subtitle": self.subtitle,
            "lighting": self.lighting,
            "color_grading": self.color_grading,
            "metadata": self.metadata,
        }


@dataclass
class ShotList:
    """镜头列表"""
    shot_list_id: str
    variant_id: str
    total_shots: int
    total_duration: float
    shots: list[Shot] = field(default_factory=list)
    storyboard_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "shot_list_id": self.shot_list_id,
            "variant_id": self.variant_id,
            "total_shots": self.total_shots,
            "total_duration": self.total_duration,
            "shots": [s.to_dict() for s in self.shots],
            "storyboard_id": self.storyboard_id,
            "metadata": self.metadata,
        }


class ShotGenerator:
    """镜头拆解引擎"""

    # 默认反向提示词
    DEFAULT_NEGATIVE: str = (
        "low quality, blurry, watermark, text overlay, distorted face, "
        "extra fingers, deformed hands, jpeg artifacts, low resolution"
    )

    # 段落类型 → 镜头数（每段建议拆几镜头）
    SHOTS_PER_SEGMENT: dict[str, int] = {
        "opening": 2,     # 开场通常 2 镜头（人物/场景或动作）
        "gameplay": 3,    # 玩法展示 3 镜头
        "conflict": 2,    # 冲突 2 镜头
        "reward": 3,      # 奖励 3 镜头（高潮）
        "cta": 1,         # CTA 1 镜头
        "ending": 1,      # 结尾 1 镜头
    }

    # 段落类型 → 运镜模板
    SEGMENT_CAMERA_MOTION: dict[str, str] = {
        "opening":   "slow push in, eye-level close-up",
        "gameplay":  "tracking shot, follow action, slight pan",
        "conflict":  "handheld camera, slight shake, quick pan",
        "reward":    "orbit around subject, push in, slight zoom",
        "cta":       "static, locked-off, centered framing",
        "ending":    "slow pull out, wide angle, fade to black",
    }

    # 段落类型 → 角色动作
    SEGMENT_CHARACTER_MOTION: dict[str, str] = {
        "opening":   "character reacts with surprise, eyes wide, slight lean back",
        "gameplay":  "character moves through scene, gestures toward gameplay",
        "conflict":  "character shows tension, slight crouch, focused gaze",
        "reward":    "character celebrates, arms up, big smile",
        "cta":       "character points at camera, inviting gesture",
        "ending":    "character smiles softly, slight wave, looks satisfied",
    }

    # 段落类型 → 物体动作
    SEGMENT_OBJECT_MOTION: dict[str, str] = {
        "opening":   "magical particles drift in, glowing item rotates slowly",
        "gameplay":  "items appear, collect, disappear; UI pulses",
        "conflict":  "obstacle appears, hazard closes in",
        "reward":    "coins burst out, chest opens, fireworks",
        "cta":       "download button glows, sparkle accents",
        "ending":    "logo settles in, particles dissipate",
    }

    # 段落类型 → 特效
    SEGMENT_FX: dict[str, list[str]] = {
        "opening":   ["magic_sparkle", "lens_flare", "soft_glow"],
        "gameplay":  ["motion_blur", "screen_shake", "ui_pop"],
        "conflict":  ["red_flash", "shake", "darken_vignette"],
        "reward":    ["coin_burst", "golden_glow", "confetti", "epic_wings"],
        "cta":       ["button_glow", "shimmer", "rim_light"],
        "ending":    ["light_leak", "soft_bokeh", "fade_dissolve"],
    }

    # 段落类型 → 音效
    SEGMENT_SFX: dict[str, list[str]] = {
        "opening":   ["whoosh_in", "magical_chime", "curiosity_sting"],
        "gameplay":  ["tap_sound", "collect_chime", "loop_music"],
        "conflict":  ["tension_drone", "hit_impact", "warning_beep"],
        "reward":    ["fanfare", "coin_collect_loop", "victory_chord"],
        "cta":       ["button_click", "uplifting_sting"],
        "ending":    ["warm_pad", "soft_piano_chord"],
    }

    # 段落类型 → 灯光
    SEGMENT_LIGHTING: dict[str, str] = {
        "opening":   "warm rim light, soft fill, magical backlight",
        "gameplay":  "natural daylight, balanced exposure",
        "conflict":  "low-key, dramatic shadows, cool blue",
        "reward":    "golden hour, volumetric light, backlight",
        "cta":       "studio lit, even, brand colors",
        "ending":    "soft sunset, gentle bokeh",
    }

    # 段落类型 → 调色
    SEGMENT_COLOR_GRADING: dict[str, str] = {
        "opening":   "vibrant + warm",
        "gameplay":  "natural + saturated",
        "conflict":  "cool + contrast",
        "reward":    "golden + glow + bloom",
        "cta":       "clean + brand palette",
        "ending":    "soft + warm + filmic",
    }

    # 段落类型 → BGM 提示
    SEGMENT_MUSIC_CUE: dict[str, str] = {
        "opening":   "playful intro sting, 100 BPM",
        "gameplay":  "loop-friendly beat, mid-tempo",
        "conflict":  "tension build, rising",
        "reward":    "triumphant drop, celebratory",
        "cta":       "uplifting resolve, strong end",
        "ending":    "soft outro, fade",
    }

    def __init__(self):
        self._shots_per = dict(self.SHOTS_PER_SEGMENT)
        self._camera = dict(self.SEGMENT_CAMERA_MOTION)
        self._char_motion = dict(self.SEGMENT_CHARACTER_MOTION)
        self._obj_motion = dict(self.SEGMENT_OBJECT_MOTION)
        self._fx = {k: list(v) for k, v in self.SEGMENT_FX.items()}
        self._sfx = {k: list(v) for k, v in self.SEGMENT_SFX.items()}
        self._lighting = dict(self.SEGMENT_LIGHTING)
        self._grading = dict(self.SEGMENT_COLOR_GRADING)
        self._music = dict(self.SEGMENT_MUSIC_CUE)
        self._negative = self.DEFAULT_NEGATIVE

    # ------------------------------------------------------------------
    # 核心方法
    # ------------------------------------------------------------------
    def generate(
        self,
        storyboard: Any,  # Storyboard
        strategy: Any,    # CreativeStrategy
        variant: dict[str, Any],
    ) -> ShotList:
        """根据 Storyboard 生成 Shot 列表

        Args:
            storyboard: 分镜
            strategy: 创意策略
            variant: Decision Variant
        """
        dna = variant.get("dna", {})
        character = dna.get("character", {}).get("type", "witch")
        creatures = dna.get("creatures", [{}])
        creature = creatures[0].get("type", "dragon") if creatures else "dragon"
        env = dna.get("environment", {}).get("type", "magic_forest")
        lighting = dna.get("lighting", {}).get("style", "warm")

        shots: list[Shot] = []
        shot_idx = 1
        current_time = 0.0

        for scene in storyboard.scenes:
            seg_type = scene.segment_type
            n_shots = self._shots_per.get(seg_type, 2)
            # 按比例切分
            base_dur = scene.duration / n_shots

            for s in range(n_shots):
                shot_dur = round(base_dur, 2)
                start = round(current_time, 2)
                end = round(current_time + shot_dur, 2)
                current_time = end

                prompt = self._build_prompt(
                    seg_type=seg_type,
                    character=character,
                    creature=creature,
                    env=env,
                    lighting=lighting,
                    scene=scene,
                    shot_in_scene=s + 1,
                    total_in_scene=n_shots,
                    strategy=strategy,
                )

                shot = Shot(
                    shot_id=f"shot_{storyboard.variant_id}_{shot_idx:03d}",
                    scene_id=scene.scene_id,
                    shot_index=shot_idx,
                    name=f"{scene.name}-{s+1}",
                    duration=shot_dur,
                    start_time=start,
                    end_time=end,
                    prompt=prompt,
                    negative_prompt=self._negative,
                    camera=scene.camera_suggestion,
                    camera_motion=self._camera.get(seg_type, "static"),
                    character_motion=self._char_motion.get(seg_type, ""),
                    object_motion=self._obj_motion.get(seg_type, ""),
                    fx=list(self._fx.get(seg_type, [])),
                    transition_in=scene.transition_in if s == 0 else "Cut",
                    transition_out=scene.transition_out if s == n_shots - 1 else "Cut",
                    sound_effects=list(self._sfx.get(seg_type, [])),
                    music_cue=self._music.get(seg_type, ""),
                    dialogue="",
                    subtitle=self._build_subtitle(seg_type, strategy),
                    lighting=self._lighting.get(seg_type, ""),
                    color_grading=self._grading.get(seg_type, ""),
                    metadata={
                        "scene_index": scene.scene_index,
                        "shot_in_scene": s + 1,
                        "total_in_scene": n_shots,
                    },
                )
                shots.append(shot)
                shot_idx += 1

        # 校正总时长
        if shots and abs(current_time - storyboard.total_duration) > 0.1:
            diff = storyboard.total_duration - current_time
            shots[-1].duration = round(shots[-1].duration + diff, 2)
            shots[-1].end_time = storyboard.total_duration

        return ShotList(
            shot_list_id=f"shotlist_{storyboard.variant_id}",
            variant_id=storyboard.variant_id,
            total_shots=len(shots),
            total_duration=storyboard.total_duration,
            shots=shots,
            storyboard_id=storyboard.storyboard_id,
            metadata={
                "platform": storyboard.platform,
                "aspect_ratio": storyboard.aspect_ratio,
                "hook": strategy.hook,
                "character": character,
                "creature": creature,
            },
        )

    # ------------------------------------------------------------------
    # Prompt 构造
    # ------------------------------------------------------------------
    def _build_prompt(
        self,
        seg_type: str,
        character: str,
        creature: str,
        env: str,
        lighting: str,
        scene: Any,
        shot_in_scene: int,
        total_in_scene: int,
        strategy: Any,
    ) -> str:
        """构造 AI 视频生成 Prompt"""
        cam = self._camera.get(seg_type, "static")
        char_m = self._char_motion.get(seg_type, "")
        obj_m = self._obj_motion.get(seg_type, "")

        # 段落类型特定的视觉锚点
        seg_anchor = {
            "opening":   f"opening hook, first impression, {character} reacting to {creature} appearing in {env}",
            "gameplay":  f"gameplay footage of {character} playing in {env}, core loop, UI visible",
            "conflict":  f"challenge moment, {character} faces obstacle in {env}",
            "reward":    f"reward celebration, {character} celebrates, {creature} rejoices, coins burst",
            "cta":       f"call to action, {character} points at camera, download button glows",
            "ending":    f"warm ending, {character} smiles, brand logo fades in",
        }
        anchor = seg_anchor.get(seg_type, f"{character} in {env}")

        prompt = (
            f"{anchor}. "
            f"Camera: {cam}. "
            f"Character motion: {char_m}. "
            f"Object motion: {obj_m}. "
            f"Lighting: {lighting}. "
            f"Style: high quality, cinematic, mobile vertical video, "
            f"vibrant colors, {strategy.emotion} mood, "
            f"Facebook ad aesthetic, 1080p."
        )
        return prompt

    def _build_subtitle(self, seg_type: str, strategy: Any) -> str:
        """构造字幕"""
        sub_map = {
            "opening":   "👀 看！",
            "gameplay":  "快来玩！",
            "conflict":  "你能行吗？",
            "reward":    "🎁 限时奖励！",
            "cta":       strategy.cta_message,
            "ending":    "立即下载，免费玩！",
        }
        return sub_map.get(seg_type, "")

    # ------------------------------------------------------------------
    # 批量
    # ------------------------------------------------------------------
    def generate_batch(
        self,
        storyboards: list[Any],
        strategies: list[Any],
        variants: list[dict[str, Any]],
    ) -> list[ShotList]:
        """批量生成"""
        out = []
        for sb, st, v in zip(storyboards, strategies, variants):
            try:
                out.append(self.generate(sb, st, v))
            except Exception:
                continue
        return out
