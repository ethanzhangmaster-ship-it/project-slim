"""Camera Language Engine - 运镜语言引擎

自动生成运镜建议，支持不同 Hook 类型。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class CameraShot:
    """运镜定义"""
    name: str                 # 运镜名称
    description: str          # 中文描述
    motion: str               # 英文动作描述
    duration_range: str       # 适用时长范围
    best_for: list[str]       # 最适合的场景类型
    intensity: str            # intensity / medium / slow


class CameraLanguageEngine:
    """运镜语言引擎
    
    支持的运镜类型:
    - Pan（横摇）
    - Tilt（纵摇）
    - Zoom（缩放）
    - Push In（推进）
    - Pull Out（拉远）
    - Orbit（环绕）
    - Tracking（跟踪）
    - Static（静态）
    - Handheld（手持）
    - Drone（无人机视角）
    - Top-Down（俯视）
    - Hero Shot（英雄镜头）
    - Explosion Zoom（爆炸缩放）
    """

    # 运镜定义库
    CAMERA_LIBRARY: dict[str, CameraShot] = {
        "pan": CameraShot(
            name="pan",
            description="横摇：镜头左右移动",
            motion="camera panning horizontally",
            duration_range="2-10s",
            best_for=["gameplay", "environment reveal"],
            intensity="medium",
        ),
        "tilt": CameraShot(
            name="tilt",
            description="纵摇：镜头上下移动",
            motion="camera tilting up/down",
            duration_range="2-5s",
            best_for=["reveal", "reward reveal"],
            intensity="medium",
        ),
        "zoom": CameraShot(
            name="zoom",
            description="缩放：镜头拉近或拉远",
            motion="camera zooming in/out",
            duration_range="1-3s",
            best_for=["focus", "reveal"],
            intensity="fast",
        ),
        "push_in": CameraShot(
            name="push_in",
            description="推进：镜头向前推进",
            motion="camera pushing in towards subject",
            duration_range="2-5s",
            best_for=["hook", "focus", "emotion"],
            intensity="medium",
        ),
        "pull_out": CameraShot(
            name="pull_out",
            description="拉远：镜头向后拉远",
            motion="camera pulling out from subject",
            duration_range="2-5s",
            best_for=["ending", "environment reveal"],
            intensity="slow",
        ),
        "orbit": CameraShot(
            name="orbit",
            description="环绕：镜头围绕主体旋转",
            motion="camera orbiting around subject",
            duration_range="3-8s",
            best_for=["boss reveal", "character showcase"],
            intensity="medium",
        ),
        "tracking": CameraShot(
            name="tracking",
            description="跟踪：镜头跟随主体移动",
            motion="camera tracking subject movement",
            duration_range="3-10s",
            best_for=["gameplay", "action sequence"],
            intensity="medium",
        ),
        "static": CameraShot(
            name="static",
            description="静态：镜头固定不动",
            motion="static camera shot",
            duration_range="1-10s",
            best_for=["ui", "cta", "ending"],
            intensity="slow",
        ),
        "handheld": CameraShot(
            name="handheld",
            description="手持：轻微晃动的手持感",
            motion="handheld camera movement",
            duration_range="2-5s",
            best_for=["action", "intense moment"],
            intensity="fast",
        ),
        "drone": CameraShot(
            name="drone",
            description="无人机：高空俯视视角",
            motion="drone aerial shot",
            duration_range="3-10s",
            best_for=["environment reveal", "landscape"],
            intensity="slow",
        ),
        "top_down": CameraShot(
            name="top_down",
            description="俯视：从上往下看",
            motion="top-down camera view",
            duration_range="3-10s",
            best_for=["merge gameplay", "puzzle"],
            intensity="static",
        ),
        "hero_shot": CameraShot(
            name="hero_shot",
            description="英雄镜头：角色展示镜头",
            motion="hero shot, character showcase",
            duration_range="3-5s",
            best_for=["reward", "victory", "character reveal"],
            intensity="medium",
        ),
        "explosion_zoom": CameraShot(
            name="explosion_zoom",
            description="爆炸缩放：快速冲击缩放",
            motion="explosion zoom, fast impact",
            duration_range="1-2s",
            best_for=["reward explosion", "hook impact"],
            intensity="fast",
        ),
        "close_up_push": CameraShot(
            name="close_up_push",
            description="特写推进：推进到特写",
            motion="close-up push in to face",
            duration_range="2-3s",
            best_for=["hook", "emotion", "surprise"],
            intensity="medium",
        ),
    }

    # Hook 类型推荐运镜
    HOOK_CAMERA_RECOMMENDATIONS: dict[str, list[str]] = {
        "collection": ["close_up_push", "tracking", "push_in"],
        "reward": ["explosion_zoom", "hero_shot", "zoom"],
        "merge": ["top_down", "tracking", "zoom"],
        "boss": ["orbit", "push_in", "handheld"],
        "transformation": ["orbit", "zoom", "hero_shot"],
        "emotion": ["close_up_push", "push_in", "static"],
        "fail": ["handheld", "tilt", "pull_out"],
    }

    def __init__(self):
        self._library = dict(self.CAMERA_LIBRARY)
        self._hook_rec = dict(self.HOOK_CAMERA_RECOMMENDATIONS)

    # ------------------------------------------------------------------
    # 核心方法
    # ------------------------------------------------------------------
    def get_camera(self, name: str) -> CameraShot | None:
        """获取运镜定义"""
        return self._library.get(name.lower())

    def recommend_for_hook(self, hook_type: str, limit: int = 3) -> list[CameraShot]:
        """为 Hook 类型推荐运镜"""
        names = self._hook_rec.get(hook_type.lower(), ["push_in", "tracking", "zoom"])
        results = []
        for n in names[:limit]:
            shot = self.get_camera(n)
            if shot:
                results.append(shot)
        return results

    def recommend_for_scene(self, scene_type: str) -> list[CameraShot]:
        """为场景类型推荐运镜"""
        matching = []
        for shot in self._library.values():
            if scene_type in shot.best_for:
                matching.append(shot)
        return matching[:3]

    def generate_camera_sequence(
        self,
        hook_type: str,
        scene_types: list[str],
    ) -> list[dict[str, Any]]:
        """生成完整运镜序列"""
        sequence = []

        # Hook 场景用 Hook 推荐
        hook_shots = self.recommend_for_hook(hook_type)
        if hook_shots:
            sequence.append({
                "scene": "hook",
                "camera": hook_shots[0].name,
                "motion": hook_shots[0].motion,
                "description": hook_shots[0].description,
            })

        # 其他场景用场景推荐
        for scene_type in scene_types:
            if scene_type == "hook":
                continue
            shots = self.recommend_for_scene(scene_type)
            if shots:
                sequence.append({
                    "scene": scene_type,
                    "camera": shots[0].name,
                    "motion": shots[0].motion,
                    "description": shots[0].description,
                })

        return sequence

    def get_all_cameras(self) -> list[CameraShot]:
        """获取所有运镜"""
        return list(self._library.values())

    def to_motion_prompt(self, camera_name: str) -> str:
        """转换为动作提示词"""
        shot = self.get_camera(camera_name)
        return shot.motion if shot else ""