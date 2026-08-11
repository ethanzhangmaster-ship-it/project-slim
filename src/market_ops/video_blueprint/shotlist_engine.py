"""Shotlist Engine - 镜头拆解引擎

把 Storyboard 拆成镜头，视频制作人员直接照着做。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .camera_engine import CameraSpec, CameraEngine


@dataclass
class Shot:
    """单个镜头"""
    shot_id: str
    shot_index: int
    scene_id: str
    scene_name: str
    duration: float
    start_time: float
    end_time: float
    camera: CameraSpec
    motion: str
    focus: str
    fx: list[str] = field(default_factory=list)
    voice: str = ""
    subtitle: str = ""
    transition: str = ""
    character: str = ""
    environment: str = ""
    music_marker: str = ""
    asset_reference: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "shot_id": self.shot_id,
            "shot_index": self.shot_index,
            "scene_id": self.scene_id,
            "scene_name": self.scene_name,
            "duration": self.duration,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "camera": self.camera.to_dict(),
            "motion": self.motion,
            "focus": self.focus,
            "fx": self.fx,
            "voice": self.voice,
            "subtitle": self.subtitle,
            "transition": self.transition,
            "character": self.character,
            "environment": self.environment,
            "music_marker": self.music_marker,
            "asset_reference": self.asset_reference,
            "notes": self.notes,
        }


@dataclass
class Shotlist:
    """镜头列表"""
    shotlist_id: str
    variant_id: str
    total_shots: int
    total_duration: float
    shots: list[Shot] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "shotlist_id": self.shotlist_id,
            "variant_id": self.variant_id,
            "total_shots": self.total_shots,
            "total_duration": self.total_duration,
            "shots": [s.to_dict() for s in self.shots],
        }


class ShotlistEngine:
    """镜头拆解引擎"""

    # 场景 → 镜头数
    SCENE_SHOT_COUNT: dict[str, int] = {
        "Hook": 3, "Opening": 3,
        "Search": 2, "Think": 2,
        "Collect": 3, "Merge": 3, "Match": 3,
        "Boss": 3, "Attack": 3, "Special": 2,
        "Fail": 2, "Retry": 2,
        "Victory": 3, "Reward": 3, "LevelUp": 2,
        "CTA": 2,
    }

    # 场景 → 镜头模板
    SCENE_TEMPLATES: dict[str, list[dict[str, str]]] = {
        "default": [
            {"camera": "Close Up", "motion": "Fast Push", "focus": "Subject"},
            {"camera": "Medium", "motion": "Tracking", "focus": "Action"},
            {"camera": "Wide", "motion": "Slow Pull", "focus": "Environment"},
        ],
    }

    def generate(self, dna: VideoDNA, storyboard: Storyboard) -> Shotlist:
        """根据 Video DNA 和 Storyboard 拆解镜头"""
        shots = []
        shot_idx = 1
        current_time = 0.0
        camera_engine = CameraEngine()

        # 获取 DNA 中的角色和环境信息
        dna_data = dna.metadata.get("dna_data", {}) if dna.metadata else {}
        character_type = dna_data.get("character", {}).get("type", "")
        environment_type = dna_data.get("environment", {}).get("type", "")

        for scene in storyboard.scenes:
            n_shots = self.SCENE_SHOT_COUNT.get(scene.name, 2)
            base_dur = scene.duration / n_shots
            templates = self.SCENE_TEMPLATES.get("default", [])

            # 根据场景获取 CameraSpec
            move_key = self._map_scene_to_move(scene.name, dna.hook)
            spec_tpl = camera_engine.MOVE_SPECS.get(move_key, camera_engine.MOVE_SPECS["medium"])
            scene_camera_spec = CameraSpec(
                move=move_key,
                lens=spec_tpl["lens"],
                move_speed=spec_tpl["move_speed"],
                shake=spec_tpl["shake"],
                focus=spec_tpl["focus"],
                depth=spec_tpl["depth"],
                zoom=spec_tpl["zoom"],
                frame_rate=spec_tpl.get("frame_rate", 60),
                fov=spec_tpl.get("fov", "medium"),
            )

            for s in range(n_shots):
                shot_dur = round(base_dur, 2)
                start = round(current_time, 2)
                end = round(current_time + shot_dur, 2)
                current_time = end

                template = templates[s % len(templates)]
                motion = self._adjust_motion(template["motion"], scene.motion)

                # 根据镜头位置微调 CameraSpec
                shot_camera_spec = self._adjust_camera_spec(scene_camera_spec, s, n_shots)

                # 根据场景分配音乐标记
                music_marker = self._get_music_marker(scene.name)

                shot = Shot(
                    shot_id=f"S{shot_idx:02d}",
                    shot_index=shot_idx,
                    scene_id=scene.scene_id,
                    scene_name=scene.name,
                    duration=shot_dur,
                    start_time=start,
                    end_time=end,
                    camera=shot_camera_spec,
                    motion=motion,
                    focus=template["focus"],
                    fx=scene.fx if scene.fx else [],
                    voice="None",
                    subtitle=scene.subtitle if s == n_shots // 2 else "",
                    transition=scene.transition if s == n_shots - 1 else "Cut",
                    character=character_type,
                    environment=environment_type,
                    music_marker=music_marker,
                    asset_reference=f"asset_{scene.scene_id}_{s+1}",
                    notes=f"{scene.name} - Shot {s+1}/{n_shots}",
                )
                shots.append(shot)
                shot_idx += 1

        # 校正最后一个镜头
        if shots:
            shots[-1].duration = round(storyboard.total_duration - shots[-1].start_time, 2)
            shots[-1].end_time = storyboard.total_duration

        return Shotlist(
            shotlist_id=f"shotlist_{storyboard.variant_id}",
            variant_id=storyboard.variant_id,
            total_shots=len(shots),
            total_duration=storyboard.total_duration,
            shots=shots,
        )

    def _map_scene_to_move(self, scene_name: str, hook: str) -> str:
        """根据场景名称映射运镜"""
        mapping = {
            "Hook": CameraEngine.HOOK_CAMERA.get(hook, "zoom"),
            "Opening": "wide",
            "Search": "tracking",
            "Think": "close",
            "Collect": "tracking",
            "Merge": "macro",
            "Match": "top",
            "Boss": "orbit",
            "Attack": "handheld",
            "Special": "zoom",
            "Fail": "handheld",
            "Retry": "push",
            "Victory": "orbit",
            "Reward": "push",
            "LevelUp": "zoom",
            "CTA": "static",
        }
        return mapping.get(scene_name, "medium")

    def _adjust_camera_spec(self, base_spec: CameraSpec, shot_idx: int, total_shots: int) -> CameraSpec:
        """根据镜头位置微调 CameraSpec"""
        if total_shots == 1:
            return base_spec
        elif shot_idx == 0:
            return CameraSpec(
                move=base_spec.move,
                lens=base_spec.lens,
                move_speed="slow" if base_spec.move_speed == "normal" else base_spec.move_speed,
                shake=base_spec.shake,
                focus=base_spec.focus,
                depth=base_spec.depth,
                zoom="1.0x",
                frame_rate=base_spec.frame_rate,
                fov=base_spec.fov,
            )
        elif shot_idx == total_shots - 1:
            return CameraSpec(
                move=base_spec.move,
                lens=base_spec.lens,
                move_speed="fast" if base_spec.move_speed == "normal" else base_spec.move_speed,
                shake=base_spec.shake,
                focus=base_spec.focus,
                depth=base_spec.depth,
                zoom="1.3x",
                frame_rate=base_spec.frame_rate,
                fov=base_spec.fov,
            )
        return base_spec

    def _adjust_motion(self, base: str, scene_motion: str) -> str:
        if scene_motion and scene_motion != "None":
            return scene_motion
        return base

    def _get_music_marker(self, scene_name: str) -> str:
        """根据场景名称分配音乐标记"""
        mapping = {
            "Hook": "intro",
            "Opening": "build",
            "Search": "build",
            "Think": "build",
            "Collect": "drop",
            "Merge": "drop",
            "Match": "drop",
            "Boss": "reward_rise",
            "Attack": "drop",
            "Special": "drop",
            "Fail": "build",
            "Retry": "build",
            "Victory": "reward_rise",
            "Reward": "reward_rise",
            "LevelUp": "reward_rise",
            "CTA": "cta_rise",
        }
        return mapping.get(scene_name, "build")
