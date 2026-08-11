"""Visual Analyzer - 视觉分析器

理解视频画面内容：角色、场景、视觉元素
第一版：基于关键词匹配 + 启发式规则
"""
from __future__ import annotations

from typing import Any

from .models import VisualFeatures


class VisualAnalyzer:
    """视觉分析器"""

    # 角色关键词
    CHARACTER_KEYWORDS: dict[str, list[str]] = {
        "witch": ["witch", "sorceress", "mage", "spellcaster", "enchantress"],
        "dragon": ["dragon", "wyvern", "drake", "serpent"],
        "warrior": ["warrior", "knight", "fighter", "hero", "champion"],
        "monster": ["monster", "creature", "beast", "demon", "goblin"],
        "pet": ["pet", "companion", "familiar", "animal", "creature"],
    }

    # 场景关键词
    SCENE_KEYWORDS: dict[str, list[str]] = {
        "castle": ["castle", "fortress", "palace", "tower", "kingdom"],
        "forest": ["forest", "woods", "jungle", "grove"],
        "battlefield": ["battlefield", "warzone", "arena", "combat"],
        "magic": ["magic", "magical", "mystical", "enchanted", "arcane"],
        "dungeon": ["dungeon", "cave", "ruins", "labyrinth"],
    }

    # 视觉元素关键词
    ELEMENT_KEYWORDS: dict[str, list[str]] = {
        "explosion": ["explosion", "blast", "detonation", "burst"],
        "particle": ["particle", "sparkle", "spark", "stardust", "glimmer"],
        "glow": ["glow", "glowing", "radiant", "luminous", "shimmer"],
        "upgrade": ["upgrade", "evolution", "level up", "power up"],
        "transformation": ["transformation", "transform", "morph", "change"],
        "fire": ["fire", "flame", "inferno", "blaze"],
        "lightning": ["lightning", "thunder", "electric", "spark"],
    }

    def __init__(self):
        self._char_kw = {k: list(v) for k, v in self.CHARACTER_KEYWORDS.items()}
        self._scene_kw = {k: list(v) for k, v in self.SCENE_KEYWORDS.items()}
        self._elem_kw = {k: list(v) for k, v in self.ELEMENT_KEYWORDS.items()}

    def analyze(
        self,
        prompt_text: str,
        frame_paths: list[str] | None = None,
    ) -> VisualFeatures:
        """分析视觉内容

        Args:
            prompt_text: 生成视频的 prompt（用于文本分析）
            frame_paths: 帧图片路径（预留，未来用 VLM）

        Returns:
            VisualFeatures
        """
        text = prompt_text.lower()
        features = VisualFeatures()

        # 检测角色
        for char_name, kws in self._char_kw.items():
            if any(kw in text for kw in kws):
                features.characters.append(char_name)
                features.objects.append(char_name)

        # 检测场景
        for scene_name, kws in self._scene_kw.items():
            if any(kw in text for kw in kws):
                features.scenes.append(scene_name)

        # 检测视觉元素
        for elem_name, kws in self._elem_kw.items():
            if any(kw in text for kw in kws):
                features.elements.append(elem_name)

        # 去重
        features.characters = list(dict.fromkeys(features.characters))
        features.objects = list(dict.fromkeys(features.objects))
        features.scenes = list(dict.fromkeys(features.scenes))
        features.elements = list(dict.fromkeys(features.elements))

        return features

    def detect_characters(self, text: str) -> list[str]:
        """检测角色"""
        text = text.lower()
        found: list[str] = []
        for char_name, kws in self._char_kw.items():
            if any(kw in text for kw in kws):
                found.append(char_name)
        return found

    def detect_elements(self, text: str) -> list[str]:
        """检测视觉元素"""
        text = text.lower()
        found: list[str] = []
        for elem_name, kws in self._elem_kw.items():
            if any(kw in text for kw in kws):
                found.append(elem_name)
        return found

    def score_visual_richness(self, features: VisualFeatures) -> float:
        """评分视觉丰富度（0-100）"""
        score = 30.0
        score += len(features.characters) * 10
        score += len(features.scenes) * 5
        score += len(features.elements) * 8
        # 有角色 + 有特效 = 高丰富度
        if features.characters and features.elements:
            score += 20
        return min(100.0, score)
