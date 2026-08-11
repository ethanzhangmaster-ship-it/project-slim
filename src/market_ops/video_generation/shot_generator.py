"""Shot Generator - 镜头拆解器

把每个 Scene 拆成镜头，每个镜头包含完整的生成参数。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .camera_language import CameraLanguageEngine
from .motion_engine import MotionEngine


@dataclass
class Shot:
    """镜头定义"""
    shot_id: str                # Shot001
    scene_number: int           # 所属场景
    scene_type: str             # hook/gameplay/reward/cta/ending
    duration: float             # 镜头时长
    camera: str                 # 运镜类型
    camera_motion: str          # 运镜描述
    character: str              # 角色
    character_motion: str       # 角色动作
    creature: str               # 生物
    creature_motion: str        # 生物动作
    environment: str            # 环境
    lighting: str               # 光照
    fx: str                     # 特效
    transition: str             # 转场
    sound: str                  # 音效
    prompt: str                 # 完整提示词
    negative_prompt: str        # 负面提示词
    extra_params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "shot_id": self.shot_id,
            "scene_number": self.scene_number,
            "scene_type": self.scene_type,
            "duration": self.duration,
            "camera": self.camera,
            "camera_motion": self.camera_motion,
            "character": self.character,
            "character_motion": self.character_motion,
            "creature": self.creature,
            "creature_motion": self.creature_motion,
            "environment": self.environment,
            "lighting": self.lighting,
            "fx": self.fx,
            "transition": self.transition,
            "sound": self.sound,
            "prompt": self.prompt,
            "negative_prompt": self.negative_prompt,
            "extra_params": self.extra_params,
        }


@dataclass
class ShotList:
    """镜头列表"""
    shot_list_id: str
    variant_id: str
    total_duration: float
    shots: list[Shot] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "shot_list_id": self.shot_list_id,
            "variant_id": self.variant_id,
            "total_duration": self.total_duration,
            "shots": [s.to_dict() for s in self.shots],
            "metadata": self.metadata,
        }


class ShotGenerator:
    """镜头拆解器
    
    将 Storyboard 的每个 Scene 拆解为可执行的镜头。
    """

    # 场景拆分规则
    SCENE_SPLIT_RULES: dict[str, dict[str, Any]] = {
        "hook": {
            "shot_count": 1,
            "intensity": "high",
            "motion_density": "dense",
        },
        "gameplay": {
            "shot_count": 2,
            "intensity": "medium",
            "motion_density": "normal",
        },
        "reward": {
            "shot_count": 2,
            "intensity": "high",
            "motion_density": "dense",
        },
        "cta": {
            "shot_count": 1,
            "intensity": "low",
            "motion_density": "minimal",
        },
        "ending": {
            "shot_count": 1,
            "intensity": "low",
            "motion_density": "minimal",
        },
    }

    # 默认负面提示词
    DEFAULT_NEGATIVE = "bad quality, blurry, low resolution, distorted, disfigured, extra limbs, missing limbs, watermark, text, logo, nsfw, violence, blood, gore"

    def __init__(self):
        self.camera_engine = CameraLanguageEngine()
        self.motion_engine = MotionEngine()

    # ------------------------------------------------------------------
    # 核心生成方法
    # ------------------------------------------------------------------
    def generate(
        self,
        storyboard: dict[str, Any],
        variant: dict[str, Any],
        video_prompt: str = "",
    ) -> ShotList:
        """从 Storyboard 生成镜头列表

        Args:
            storyboard: VideoStoryboard.to_dict()
            variant: Decision Variant
            video_prompt: 主视频提示词

        Returns:
            ShotList
        """
        variant_id = storyboard.get("variant_id", variant.get("variant_id", "unknown"))
        scenes = storyboard.get("scenes", [])
        dna = variant.get("dna", {})

        # 提取基础元素
        character = dna.get("character", {}).get("type", "witch")
        creatures = dna.get("creatures", [{}])
        creature_type = creatures[0].get("type", "dragon") if creatures else "dragon"
        environment = dna.get("environment", {}).get("type", "magic_forest")
        lighting = dna.get("lighting", {}).get("color_temperature", "warm")

        shots = []
        shot_counter = 1

        for scene in scenes:
            scene_number = scene.get("scene_number", 1)
            scene_type = scene.get("scene_type", "hook")
            scene_duration = scene.get("duration", 2.0)

            # 拆分镜头
            rule = self.SCENE_SPLIT_RULES.get(scene_type, {"shot_count": 1})
            shot_count = rule.get("shot_count", 1)

            # 每个镜头时长
            shot_duration = round(scene_duration / shot_count, 1)

            for i in range(shot_count):
                shot = self._build_shot(
                    shot_id=f"Shot{shot_counter:03d}",
                    scene_number=scene_number,
                    scene_type=scene_type,
                    duration=shot_duration,
                    character=character,
                    creature_type=creature_type,
                    environment=environment,
                    lighting=lighting,
                    scene_data=scene,
                    video_prompt=video_prompt,
                )
                shots.append(shot)
                shot_counter += 1

        total_duration = sum(s.duration for s in shots)

        return ShotList(
            shot_list_id=f"sl_{variant_id}",
            variant_id=variant_id,
            total_duration=round(total_duration, 1),
            shots=shots,
            metadata={
                "scene_count": len(scenes),
                "shot_count": len(shots),
                "video_prompt": video_prompt,
            },
        )

    def _build_shot(
        self,
        shot_id: str,
        scene_number: int,
        scene_type: str,
        duration: float,
        character: str,
        creature_type: str,
        environment: str,
        lighting: str,
        scene_data: dict[str, Any],
        video_prompt: str,
    ) -> Shot:
        """构建单个镜头"""
        # 运镜
        camera_shot = self.camera_engine.recommend_for_scene(scene_type)
        camera_name = camera_shot[0].name if camera_shot else "push_in"
        camera_motion = self.camera_engine.to_motion_prompt(camera_name)

        # 动作
        motions = self.motion_engine.suggest_for_scene(scene_type, creature_type)
        char_motion = motions[0].motion_prompt if motions else "character standing"
        creature_motion = motions[1].motion_prompt if len(motions) > 1 else ""

        # 特效
        fx_motions = [m for m in motions if m.category == "fx"]
        fx = ", ".join([m.motion_prompt for m in fx_motions]) if fx_motions else ""

        # 转场
        transition = scene_data.get("transition", "cut")

        # 音效
        sound = scene_data.get("sound", "")

        # 构建完整提示词
        prompt = self._build_shot_prompt(
            video_prompt=video_prompt,
            scene_type=scene_type,
            character=character,
            char_motion=char_motion,
            creature=creature_type,
            creature_motion=creature_motion,
            environment=environment,
            lighting=lighting,
            camera_motion=camera_motion,
            fx=fx,
        )

        return Shot(
            shot_id=shot_id,
            scene_number=scene_number,
            scene_type=scene_type,
            duration=duration,
            camera=camera_name,
            camera_motion=camera_motion,
            character=character,
            character_motion=char_motion,
            creature=creature_type,
            creature_motion=creature_motion,
            environment=environment,
            lighting=lighting,
            fx=fx,
            transition=transition,
            sound=sound,
            prompt=prompt,
            negative_prompt=self.DEFAULT_NEGATIVE,
            extra_params={
                "intensity": self.SCENE_SPLIT_RULES.get(scene_type, {}).get("intensity", "medium"),
            },
        )

    def _build_shot_prompt(
        self,
        video_prompt: str,
        scene_type: str,
        character: str,
        char_motion: str,
        creature: str,
        creature_motion: str,
        environment: str,
        lighting: str,
        camera_motion: str,
        fx: str,
    ) -> str:
        """构建镜头提示词"""
        parts = []

        # 基础视频提示词
        if video_prompt:
            parts.append(video_prompt)

        # 场景描述
        parts.append(f"{scene_type} scene")
        parts.append(f"cute {character} {char_motion}")
        if creature and creature_motion:
            parts.append(f"{creature} {creature_motion}")
        parts.append(f"{environment}")
        parts.append(f"{lighting} cinematic lighting")
        parts.append(f"{camera_motion}")

        # 特效
        if fx:
            parts.append(f"{fx}")

        # 质量修饰
        parts.append("ultra detailed, high quality, Pixar style, 4K")

        return ", ".join(parts)

    # ------------------------------------------------------------------
    # 批量生成
    # ------------------------------------------------------------------
    def generate_batch(
        self,
        storyboards: list[dict[str, Any]],
        variants: dict[str, dict[str, Any]],
    ) -> list[ShotList]:
        """批量生成"""
        results = []
        for sb in storyboards:
            variant_id = sb.get("variant_id", "")
            variant = variants.get(variant_id, {})
            try:
                sl = self.generate(sb, variant)
                results.append(sl)
            except Exception:
                continue
        return results

    # ------------------------------------------------------------------
    # 导出
    # ------------------------------------------------------------------
    def export(self, shot_list: ShotList, output_path: str) -> None:
        """导出为 JSON"""
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(shot_list.to_dict(), f, ensure_ascii=False, indent=2)