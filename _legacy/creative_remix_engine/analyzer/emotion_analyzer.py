"""Emotion Analyzer — 情感分析"""
from typing import Dict
from pathlib import Path


class EmotionAnalyzer:
    """分析视频情感曲线"""

    EMOTIONS = ["surprise", "excitement", "tension", "satisfaction", "curiosity", "urgency"]

    def analyze(self, video_path: Path, segment_role: str = "") -> Dict[str, float]:
        """基于内容类型分析情感"""
        content = video_path.stem.lower()

        # 默认情感分布
        emotions = {
            "surprise": 0.3,
            "excitement": 0.3,
            "tension": 0.2,
            "satisfaction": 0.1,
            "curiosity": 0.1,
            "urgency": 0.0,
        }

        # 根据segment角色调整
        role_emotions = {
            "hook": {"surprise": 0.9, "curiosity": 0.8, "urgency": 0.3},
            "gameplay": {"excitement": 0.9, "tension": 0.7, "surprise": 0.4},
            "problem": {"tension": 0.9, "curiosity": 0.6, "urgency": 0.5},
            "transformation": {"excitement": 0.95, "surprise": 0.8, "satisfaction": 0.3},
            "reward": {"satisfaction": 0.95, "excitement": 0.6, "surprise": 0.2},
            "cta": {"urgency": 0.9, "excitement": 0.5, "curiosity": 0.4},
        }

        if segment_role in role_emotions:
            for emo, val in role_emotions[segment_role].items():
                emotions[emo] = val

        # 根据文件名关键词调整
        if any(k in content for k in ["attack", "battle", "fight"]):
            emotions["excitement"] = max(emotions["excitement"], 0.9)
            emotions["tension"] = max(emotions["tension"], 0.8)

        if any(k in content for k in ["rescue", "save", "help"]):
            emotions["tension"] = max(emotions["tension"], 0.8)
            emotions["curiosity"] = max(emotions["curiosity"], 0.7)

        if any(k in content for k in ["reward", "win", "bonus", "treasure"]):
            emotions["satisfaction"] = max(emotions["satisfaction"], 0.95)
            emotions["excitement"] = max(emotions["excitement"], 0.7)

        return emotions

    def dominant_emotion(self, emotions: Dict[str, float]) -> str:
        """获取主导情感"""
        return max(emotions, key=emotions.get)
