"""Camera Language - 运镜语言引擎

支持的运镜：
- Pan（横摇）
- Tilt（俯仰）
- Push（推进）
- Pull（拉远）
- Zoom（变焦）
- Orbit（环绕）
- Tracking（跟拍）
- Handheld（手持）
- Static（固定）
- TopDown（俯视）
- Follow（跟随）

提供运镜推荐和组合。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CameraMove:
    """运镜动作"""
    name: str
    camera: str
    speed: str              # slow / medium / fast
    motion_vector: str      # in / out / left / right / up / down / orbit
    intensity: float        # 0-1
    description: str
    best_for: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "camera": self.camera,
            "speed": self.speed,
            "motion_vector": self.motion_vector,
            "intensity": self.intensity,
            "description": self.description,
            "best_for": self.best_for,
        }


class CameraLanguageEngine:
    """运镜语言引擎"""

    # 运镜库
    CAMERA_LIBRARY: dict[str, CameraMove] = {
        "pan": CameraMove(
            name="pan", camera="pan", speed="medium", motion_vector="horizontal",
            intensity=0.5, description="横摇镜头",
            best_for=["gameplay", "environment", "reveal"],
        ),
        "tilt": CameraMove(
            name="tilt", camera="tilt", speed="medium", motion_vector="vertical",
            intensity=0.5, description="俯仰镜头",
            best_for=["reveal", "tower", "vertical_action"],
        ),
        "push": CameraMove(
            name="push", camera="push", speed="slow", motion_vector="in",
            intensity=0.7, description="推进镜头，增加紧张感和期待",
            best_for=["hook", "reward", "reveal"],
        ),
        "pull": CameraMove(
            name="pull", camera="pull", speed="slow", motion_vector="out",
            intensity=0.6, description="拉远镜头，展示全貌",
            best_for=["ending", "wide_shot", "reveal_scale"],
        ),
        "zoom": CameraMove(
            name="zoom", camera="zoom", speed="fast", motion_vector="in",
            intensity=0.8, description="变焦推进，强化情绪",
            best_for=["reward", "climax", "impact"],
        ),
        "orbit": CameraMove(
            name="orbit", camera="orbit", speed="medium", motion_vector="orbit",
            intensity=0.7, description="环绕镜头，展示主体立体感",
            best_for=["boss", "reward", "epic_moment"],
        ),
        "tracking": CameraMove(
            name="tracking", camera="tracking", speed="medium", motion_vector="follow",
            intensity=0.6, description="跟拍镜头，主体移动相机跟随",
            best_for=["gameplay", "chase", "movement"],
        ),
        "handheld": CameraMove(
            name="handheld", camera="handheld", speed="fast", motion_vector="shake",
            intensity=0.8, description="手持镜头，紧张感和真实感",
            best_for=["conflict", "fail", "action"],
        ),
        "static": CameraMove(
            name="static", camera="static", speed="none", motion_vector="none",
            intensity=0.0, description="固定镜头，UI/CTA 清晰展示",
            best_for=["cta", "ui_showcase", "logo"],
        ),
        "topdown": CameraMove(
            name="topdown", camera="topdown", speed="medium", motion_vector="down",
            intensity=0.6, description="俯视镜头，展示策略和布局",
            best_for=["merge", "puzzle", "strategy"],
        ),
        "follow": CameraMove(
            name="follow", camera="follow", speed="medium", motion_vector="follow",
            intensity=0.5, description="跟随镜头，主角移动相机跟随",
            best_for=["gameplay", "chase", "story"],
        ),
    }

    # 段落类型 → 推荐运镜（按顺序）
    SEGMENT_CAMERA_RECOMMENDATIONS: dict[str, list[str]] = {
        "opening":   ["push", "zoom", "tilt"],
        "gameplay":  ["tracking", "follow", "topdown"],
        "conflict":  ["handheld", "pan", "tilt"],
        "reward":    ["orbit", "push", "zoom"],
        "cta":       ["static", "push"],
        "ending":    ["pull", "pan", "tilt"],
    }

    # 玩法 → 运镜
    GAMEPLAY_CAMERA: dict[str, list[str]] = {
        "merge":         ["topdown", "tracking"],
        "collection":    ["tracking", "push"],
        "transformation":["zoom", "orbit"],
        "fail":          ["handheld", "tilt"],
        "emotion":       ["push", "pull"],
        "battle":        ["orbit", "handheld"],
    }

    def __init__(self):
        self._library = dict(self.CAMERA_LIBRARY)
        self._seg_recs = {k: list(v) for k, v in self.SEGMENT_CAMERA_RECOMMENDATIONS.items()}
        self._gameplay_cam = {k: list(v) for k, v in self.GAMEPLAY_CAMERA.items()}

    # ------------------------------------------------------------------
    # 核心方法
    # ------------------------------------------------------------------
    def recommend(
        self,
        segment_type: str,
        gameplay: str = "collection",
        emotion: str = "好奇/期待",
        editing_style: str = "",
    ) -> list[CameraMove]:
        """为段落推荐运镜组合

        Args:
            segment_type: 段落类型
            gameplay: 玩法类型
            emotion: 情绪
            editing_style: 编辑节奏
        """
        candidates: list[str] = list(self._seg_recs.get(segment_type, ["static"]))
        # 玩法特定运镜前置
        gp_cams = self._gameplay_cam.get(gameplay, [])
        for cam in reversed(gp_cams):
            if cam in self._library and cam not in candidates:
                candidates.insert(0, cam)

        # 情绪影响
        if "紧张" in emotion or "挑战" in emotion:
            if "handheld" in self._library and "handheld" not in candidates:
                candidates.append("handheld")
        elif "震撼" in emotion or "惊喜" in emotion:
            if "zoom" in self._library and "zoom" not in candidates:
                candidates.append("zoom")

        # 节奏影响
        if "快节奏" in editing_style:
            # 加快速度
            for name in candidates:
                move = self._library.get(name)
                if move and move.speed == "slow":
                    move.speed = "medium"

        return [self._library[c] for c in candidates if c in self._library]

    def get(self, name: str) -> CameraMove | None:
        """获取指定运镜"""
        return self._library.get(name)

    def list_all(self) -> list[str]:
        """列出所有支持的运镜"""
        return list(self._library.keys())

    def describe_combo(self, combo: list[CameraMove]) -> str:
        """描述运镜组合"""
        if not combo:
            return "无运镜"
        return " → ".join(
            f"{c.name}({c.speed}, {c.motion_vector})" for c in combo
        )
