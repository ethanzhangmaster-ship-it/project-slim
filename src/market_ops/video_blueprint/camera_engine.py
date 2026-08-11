"""Camera Engine - 相机规范引擎

统一运镜语言 + 镜头参数规范。

支持运镜:
Wide / Medium / Close / Top / Low / Orbit / Tracking / Push / Pull / Zoom / Macro / POV / Handheld / Drone

输出参数:
Lens / Move Speed / Shake / Focus / Depth / Zoom
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CameraMove:
    """运镜动作"""
    name: str
    description: str
    best_for: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description, "best_for": self.best_for}


@dataclass
class CameraSpec:
    """镜头参数规范"""
    move: str
    lens: str = "24mm"
    move_speed: str = "normal"
    shake: str = "none"
    focus: str = "auto"
    depth: str = "medium"
    zoom: str = "none"
    frame_rate: int = 60
    fov: str = "medium"

    def to_dict(self) -> dict[str, Any]:
        return {
            "move": self.move,
            "lens": self.lens,
            "move_speed": self.move_speed,
            "shake": self.shake,
            "focus": self.focus,
            "depth": self.depth,
            "zoom": self.zoom,
            "frame_rate": self.frame_rate,
            "fov": self.fov,
        }


@dataclass
class CameraProfile:
    """相机配置总表"""
    variant_id: str
    recommended_move: str = ""
    specs: list[CameraSpec] = field(default_factory=list)
    all_moves: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "recommended_move": self.recommended_move,
            "specs": [s.to_dict() for s in self.specs],
            "all_moves": self.all_moves,
        }


class CameraEngine:
    """相机规范引擎"""

    MOVES: dict[str, CameraMove] = {
        "wide": CameraMove("Wide", "广角镜头，展示全貌", "Reveal, Environment, Opening"),
        "medium": CameraMove("Medium", "中景镜头，平衡主体与环境", "Dialogue, Interaction"),
        "close": CameraMove("Close", "特写镜头，强调细节", "Emotion, Reward, Item"),
        "top": CameraMove("Top", "俯视角度", "Strategy, Board, Map"),
        "low": CameraMove("Low", "低角度仰拍，增强气势", "Boss, Hero, Epic"),
        "orbit": CameraMove("Orbit", "环绕主体360度", "Reward, Boss, Epic"),
        "tracking": CameraMove("Tracking", "镜头跟随主体移动", "Collection, Gameplay"),
        "push": CameraMove("Push In", "推进，增加紧张感", "Hook, Reward"),
        "pull": CameraMove("Pull Out", "拉远，展示全貌", "Ending, Reveal"),
        "zoom": CameraMove("Zoom", "快速变焦", "Hook, Transformation"),
        "macro": CameraMove("Macro", "微距镜头，细节特写", "Detail, Item, Merge"),
        "pov": CameraMove("POV", "第一人称视角", "Immersive, Gameplay"),
        "handheld": CameraMove("Handheld", "手持镜头，紧张感", "Action, Conflict"),
        "drone": CameraMove("Drone", "无人机航拍", "Environment, Wide"),
    }

    HOOK_CAMERA: dict[str, str] = {
        "Collection": "tracking",
        "Transformation": "zoom",
        "Boss": "orbit",
        "Story": "medium",
        "Discovery": "push",
        "Surprise": "zoom",
    }

    # Move -> 镜头参数映射
    MOVE_SPECS: dict[str, dict[str, Any]] = {
        "wide": {"lens": "16mm", "move_speed": "slow", "shake": "none", "focus": "infinity", "depth": "deep", "zoom": "1.0x", "frame_rate": 60, "fov": "wide"},
        "medium": {"lens": "35mm", "move_speed": "normal", "shake": "none", "focus": "auto", "depth": "medium", "zoom": "1.0x", "frame_rate": 60, "fov": "medium"},
        "close": {"lens": "85mm", "move_speed": "slow", "shake": "none", "focus": "manual", "depth": "shallow", "zoom": "1.0x", "frame_rate": 60, "fov": "narrow"},
        "top": {"lens": "24mm", "move_speed": "normal", "shake": "none", "focus": "auto", "depth": "deep", "zoom": "1.0x", "frame_rate": 60, "fov": "wide"},
        "low": {"lens": "24mm", "move_speed": "slow", "shake": "none", "focus": "auto", "depth": "medium", "zoom": "1.0x", "frame_rate": 60, "fov": "medium"},
        "orbit": {"lens": "35mm", "move_speed": "smooth", "shake": "none", "focus": "tracking", "depth": "medium", "zoom": "1.0x", "frame_rate": 60, "fov": "medium"},
        "tracking": {"lens": "24mm", "move_speed": "medium", "shake": "none", "focus": "tracking", "depth": "medium", "zoom": "1.0x", "frame_rate": 60, "fov": "medium"},
        "push": {"lens": "35mm", "move_speed": "fast", "shake": "none", "focus": "auto", "depth": "shallow", "zoom": "1.3x", "frame_rate": 60, "fov": "medium"},
        "pull": {"lens": "24mm", "move_speed": "slow", "shake": "none", "focus": "auto", "depth": "deep", "zoom": "0.7x", "frame_rate": 60, "fov": "wide"},
        "zoom": {"lens": "24-70mm", "move_speed": "fast", "shake": "none", "focus": "auto", "depth": "medium", "zoom": "2.0x", "frame_rate": 60, "fov": "medium"},
        "macro": {"lens": "100mm", "move_speed": "slow", "shake": "none", "focus": "manual", "depth": "shallow", "zoom": "1.0x", "frame_rate": 60, "fov": "narrow"},
        "pov": {"lens": "16mm", "move_speed": "medium", "shake": "light", "focus": "auto", "depth": "deep", "zoom": "1.0x", "frame_rate": 60, "fov": "wide"},
        "handheld": {"lens": "35mm", "move_speed": "medium", "shake": "heavy", "focus": "auto", "depth": "medium", "zoom": "1.0x", "frame_rate": 60, "fov": "medium"},
        "drone": {"lens": "24mm", "move_speed": "smooth", "shake": "none", "focus": "infinity", "depth": "deep", "zoom": "1.0x", "frame_rate": 60, "fov": "wide"},
        "static": {"lens": "35mm", "move_speed": "none", "shake": "none", "focus": "auto", "depth": "medium", "zoom": "1.0x", "frame_rate": 60, "fov": "medium"},
    }

    def get(self, name: str) -> CameraMove | None:
        return self.MOVES.get(name)

    def list_all(self) -> list[str]:
        return [m.name for m in self.MOVES.values()]

    def recommend_for_hook(self, hook: str) -> CameraMove | None:
        cam = self.HOOK_CAMERA.get(hook)
        return self.MOVES.get(cam) if cam else None

    def generate(self, dna: VideoDNA, storyboard: Storyboard) -> CameraProfile:
        """根据 Video DNA 和 Storyboard 生成完整 Camera Spec"""
        rec = self.recommend_for_hook(dna.hook)
        rec_name = rec.name if rec else "Zoom"

        specs = []
        for scene in storyboard.scenes:
            move_key = self._map_scene_to_move(scene.name, dna.hook)
            spec_tpl = self.MOVE_SPECS.get(move_key, self.MOVE_SPECS["medium"])
            specs.append(CameraSpec(
                move=move_key,
                lens=spec_tpl["lens"],
                move_speed=spec_tpl["move_speed"],
                shake=spec_tpl["shake"],
                focus=spec_tpl["focus"],
                depth=spec_tpl["depth"],
                zoom=spec_tpl["zoom"],
                frame_rate=spec_tpl.get("frame_rate", 60),
                fov=spec_tpl.get("fov", "medium"),
            ))

        return CameraProfile(
            variant_id=dna.variant_id,
            recommended_move=rec_name,
            specs=specs,
            all_moves=self.list_all(),
        )

    def _map_scene_to_move(self, scene_name: str, hook: str) -> str:
        """根据场景名称映射运镜"""
        mapping = {
            "Hook": self.HOOK_CAMERA.get(hook, "zoom"),
            "Opening": "wide",
            "Search": "tracking",
            "Think": "close",
            "Collect": "tracking",
            "Merge": "macro",
            "Match": "top",
            "Boss": "orbit",
            "Attack": "handheld",
            "Special": "zoom",
            "Fail": "shake",
            "Retry": "push",
            "Victory": "orbit",
            "Reward": "push",
            "LevelUp": "zoom",
            "CTA": "static",
        }
        return mapping.get(scene_name, "medium")
