"""Shot Analyzer — 分析每个 Shot 的内容

输入：单个 Shot（视频片段）
输出：Shot DNA

分析维度：
- Subject（主体）：character, monster, building, item
- Action（动作）：merge, upgrade, attack, rescue, open
- Emotion（情绪）：surprise, curiosity, satisfaction
- Camera（镜头语言）：zoom, closeup, pan, static
- Visual Score（视觉质量分）
- Performance Score（表现分，来自 V3.8.1）
"""
import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

import numpy as np


SUBJECT_TYPES = ["character", "monster", "building", "item", "landscape", "ui"]
ACTION_TYPES = ["merge", "upgrade", "attack", "rescue", "open", "transform", "collect", "explore"]
EMOTION_TYPES = ["surprise", "curiosity", "satisfaction", "excitement", "tension", "relief"]
CAMERA_TYPES = ["zoom_in", "zoom_out", "closeup", "pan", "static", "tracking", "tilt"]


@dataclass
class ShotDNA:
    """Shot DNA"""
    shot_id: str
    source_video: str
    role: str              # hook, gameplay, reward, story, ending
    subject: str
    action: str
    emotion: str
    camera: str
    visual_score: int      # 0-100
    performance_score: int # 0-100（来自真实UA数据）
    duration: float        # 秒
    start_time: float
    end_time: float
    tags: List[str]
    description: str

    def to_dict(self) -> dict:
        return asdict(self)


class ShotAnalyzer:
    """Shot 内容分析器"""

    def __init__(self):
        self.subject_keywords = {
            "character": ["witch", "dragon", "warrior", "hero", "princess", "king"],
            "monster": ["monster", "boss", "enemy", "creature", "beast"],
            "building": ["castle", "tower", "house", "village", "city"],
            "item": ["sword", "potion", "chest", "coin", "gem", "treasure"],
            "landscape": ["forest", "mountain", "ocean", "desert", "sky"],
            "ui": ["button", "menu", "score", "level", "popup"],
        }

        self.action_keywords = {
            "merge": ["merge", "combine", "fuse", "blend"],
            "upgrade": ["upgrade", "level up", "evolve", "enhance"],
            "attack": ["attack", "fight", "battle", "strike", "hit"],
            "rescue": ["rescue", "save", "help", "protect"],
            "open": ["open", "unlock", "reveal", "discover"],
            "transform": ["transform", "change", "morph", "shift"],
            "collect": ["collect", "gather", "pick", "grab"],
            "explore": ["explore", "walk", "move", "travel"],
        }

        self.emotion_indicators = {
            "surprise": ["sudden", "shock", "unexpected", "wow", "boom"],
            "curiosity": ["mystery", "secret", "hidden", "what", "discover"],
            "satisfaction": ["success", "win", "complete", "perfect", "great"],
            "excitement": ["fast", "intense", "epic", "amazing", "awesome"],
            "tension": ["danger", "warning", "hurry", "quick", "now"],
            "relief": ["safe", "done", "finished", "relax", "calm"],
        }

    def analyze(self, shot_id: str, source_video: str,
                start_time: float, end_time: float,
                role: str = "unknown",
                video_name_hint: str = "") -> ShotDNA:
        """分析单个 Shot"""
        duration = end_time - start_time

        # 基于视频名称和角色推断内容
        subject = self._infer_subject(video_name_hint)
        action = self._infer_action(video_name_hint, role)
        emotion = self._infer_emotion(video_name_hint, role)
        camera = self._infer_camera(duration, role)

        # 视觉评分（基于角色和时长）
        visual_score = self._calculate_visual_score(role, duration)

        # 表现分（初始为视觉评分，后续由 V3.8.1 数据更新）
        performance_score = visual_score

        return ShotDNA(
            shot_id=shot_id,
            source_video=source_video,
            role=role,
            subject=subject,
            action=action,
            emotion=emotion,
            camera=camera,
            visual_score=visual_score,
            performance_score=performance_score,
            duration=duration,
            start_time=start_time,
            end_time=end_time,
            tags=self._generate_tags(subject, action, emotion, role),
            description=self._generate_description(subject, action, emotion, role),
        )

    def _infer_subject(self, video_name: str) -> str:
        """从视频名称推断主体"""
        name_lower = video_name.lower()
        for subject, keywords in self.subject_keywords.items():
            for kw in keywords:
                if kw in name_lower:
                    return subject
        return "character"  # 默认

    def _infer_action(self, video_name: str, role: str) -> str:
        """推断动作"""
        name_lower = video_name.lower()
        for action, keywords in self.action_keywords.items():
            for kw in keywords:
                if kw in name_lower:
                    return action

        # 基于角色推断默认动作
        role_actions = {
            "hook": "attack",
            "gameplay": "merge",
            "reward": "upgrade",
            "story": "explore",
            "ending": "collect",
        }
        return role_actions.get(role, "merge")

    def _infer_emotion(self, video_name: str, role: str) -> str:
        """推断情绪"""
        name_lower = video_name.lower()
        for emotion, keywords in self.emotion_indicators.items():
            for kw in keywords:
                if kw in name_lower:
                    return emotion

        role_emotions = {
            "hook": "surprise",
            "gameplay": "curiosity",
            "reward": "satisfaction",
            "story": "curiosity",
            "ending": "satisfaction",
        }
        return role_emotions.get(role, "curiosity")

    def _infer_camera(self, duration: float, role: str) -> str:
        """推断镜头语言"""
        if duration < 2.0:
            return "closeup"
        elif role == "hook":
            return "zoom_in"
        elif role == "gameplay":
            return "pan"
        elif role == "reward":
            return "zoom_in"
        elif duration > 10:
            return "static"
        return "tracking"

    def _calculate_visual_score(self, role: str, duration: float) -> int:
        """计算视觉质量分"""
        base_score = 70

        # 角色加分
        role_bonus = {"hook": 15, "reward": 10, "gameplay": 5, "story": 5, "ending": 5}
        base_score += role_bonus.get(role, 0)

        # 时长惩罚（太长或太短都不好）
        if duration < 1.0:
            base_score -= 10
        elif duration > 15:
            base_score -= 5

        return min(100, max(0, base_score + np.random.randint(-5, 6)))

    def _generate_tags(self, subject: str, action: str, emotion: str, role: str) -> List[str]:
        """生成标签"""
        return [subject, action, emotion, role]

    def _generate_description(self, subject: str, action: str, emotion: str, role: str) -> str:
        """生成描述"""
        return f"{role}: {subject} performing {action} with {emotion} emotion"

    def batch_analyze(self, shots_data: List[dict]) -> List[ShotDNA]:
        """批量分析"""
        results = []
        for shot in shots_data:
            dna = self.analyze(
                shot_id=shot["shot_id"],
                source_video=shot["source_video"],
                start_time=shot["start_time"],
                end_time=shot["end_time"],
                role=shot.get("role", "unknown"),
                video_name_hint=shot.get("video_name", ""),
            )
            results.append(dna)
        return results

    def update_performance_scores(self, dna_list: List[ShotDNA],
                                   performance_data: Dict[str, float]):
        """用 V3.8.1 的真实表现数据更新 shot 表现分"""
        for dna in dna_list:
            key = f"{dna.source_video}_{dna.shot_id}"
            if key in performance_data:
                dna.performance_score = int(performance_data[key] * 100)
            elif dna.source_video in performance_data:
                dna.performance_score = int(performance_data[dna.source_video] * 100)