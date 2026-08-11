"""Scene Understanding — 场景理解"""
from typing import Dict, List
from pathlib import Path


class SceneUnderstanding:
    """理解视频场景类型和内容"""

    SCENE_TYPES = ["hook", "gameplay", "transformation", "reward", "cta", "problem"]

    def classify_scene(self, video_path: Path, start: float, end: float) -> str:
        """基于文件名和时间段分类场景"""
        name = video_path.stem.lower()

        if any(k in name for k in ["hook", "intro", "opening", "start"]):
            return "hook"
        if any(k in name for k in ["gameplay", "play", "merge", "action"]):
            return "gameplay"
        if any(k in name for k in ["transform", "evolve", "upgrade"]):
            return "transformation"
        if any(k in name for k in ["reward", "bonus", "win", "success"]):
            return "reward"
        if any(k in name for k in ["cta", "download", "install", "get"]):
            return "cta"

        # 基于时间段推断
        if start < 3:
            return "hook"
        elif end - start > 8:
            return "gameplay"
        elif start > 10:
            return "reward"
        return "problem"

    def extract_objects(self, video_path: Path) -> List[str]:
        """从文件名提取视觉对象"""
        name = video_path.stem.lower()
        objects = []

        keywords = {
            "witch": ["witch", "mage", "sorcerer"],
            "dragon": ["dragon", "dino", "monster"],
            "castle": ["castle", "fortress", "tower"],
            "pet": ["pet", "animal", "creature"],
            "character": ["character", "hero", "avatar"],
        }

        for obj, terms in keywords.items():
            if any(t in name for t in terms):
                objects.append(obj)

        return objects
