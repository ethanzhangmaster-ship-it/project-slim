"""Shot Role Classifier — Shot 角色分类器

将 shot 分类为：
- hook: 开场吸引
- gameplay: 玩法展示
- reward: 奖励展示
- story: 剧情/叙事
- ending: 结尾/CTA

输入：Shot 内容特征
输出：Role 概率分布
"""
import json
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np


ROLES = ["hook", "gameplay", "reward", "story", "ending"]


class ShotRoleClassifier:
    """Shot 角色分类器"""

    def __init__(self):
        self.role_weights = {
            "hook": {
                "duration_range": (0.5, 4.0),
                "emotions": ["surprise", "excitement", "tension"],
                "cameras": ["zoom_in", "closeup"],
                "visual_importance": 0.9,
            },
            "gameplay": {
                "duration_range": (3.0, 12.0),
                "emotions": ["curiosity", "satisfaction"],
                "cameras": ["pan", "tracking", "static"],
                "visual_importance": 0.7,
            },
            "reward": {
                "duration_range": (2.0, 8.0),
                "emotions": ["satisfaction", "excitement", "relief"],
                "cameras": ["zoom_in", "closeup"],
                "visual_importance": 0.85,
            },
            "story": {
                "duration_range": (3.0, 15.0),
                "emotions": ["curiosity", "tension"],
                "cameras": ["pan", "tracking", "tilt"],
                "visual_importance": 0.6,
            },
            "ending": {
                "duration_range": (1.0, 5.0),
                "emotions": ["satisfaction", "excitement"],
                "cameras": ["static", "zoom_out"],
                "visual_importance": 0.75,
            },
        }

    def classify(self, duration: float, emotion: str, camera: str,
                 visual_score: int, position_in_video: float = 0.5) -> Dict[str, float]:
        """分类 shot 角色

        Args:
            duration: shot 时长
            emotion: 情绪
            camera: 镜头类型
            visual_score: 视觉分
            position_in_video: 在视频中的位置 (0-1)
        """
        scores = {}

        for role, config in self.role_weights.items():
            score = 0.0

            # 时长匹配
            min_d, max_d = config["duration_range"]
            if min_d <= duration <= max_d:
                score += 0.3
            else:
                # 越界惩罚
                dist = min(abs(duration - min_d), abs(duration - max_d))
                score += max(0, 0.3 - dist * 0.05)

            # 情绪匹配
            if emotion in config["emotions"]:
                score += 0.25

            # 镜头匹配
            if camera in config["cameras"]:
                score += 0.2

            # 视觉分加权
            score += (visual_score / 100) * config["visual_importance"] * 0.15

            # 位置偏好
            if role == "hook" and position_in_video < 0.2:
                score += 0.1
            elif role == "ending" and position_in_video > 0.8:
                score += 0.1
            elif role == "gameplay" and 0.2 <= position_in_video <= 0.7:
                score += 0.05

            scores[role] = score

        # Softmax 归一化
        exp_scores = {k: np.exp(v) for k, v in scores.items()}
        total = sum(exp_scores.values())
        return {k: round(v / total, 3) for k, v in exp_scores.items()}

    def predict_role(self, duration: float, emotion: str, camera: str,
                     visual_score: int, position_in_video: float = 0.5) -> str:
        """预测最可能的角色"""
        probs = self.classify(duration, emotion, camera, visual_score, position_in_video)
        return max(probs, key=probs.get)

    def classify_shot(self, shot) -> Dict[str, float]:
        """对 ShotDNA 对象分类"""
        # 计算位置（假设标准 30s 视频）
        position = shot.start_time / 30.0 if hasattr(shot, 'start_time') else 0.5
        return self.classify(
            duration=shot.duration if hasattr(shot, 'duration') else 5.0,
            emotion=shot.emotion if hasattr(shot, 'emotion') else "curiosity",
            camera=shot.camera if hasattr(shot, 'camera') else "static",
            visual_score=shot.visual_score if hasattr(shot, 'visual_score') else 70,
            position_in_video=position,
        )

    def batch_classify(self, shots: List) -> List[Dict[str, float]]:
        """批量分类"""
        return [self.classify_shot(s) for s in shots]

    def reclassify_with_context(self, shots: List, video_duration: float) -> List[str]:
        """结合上下文重新分类（考虑相邻 shot 的连贯性）"""
        roles = []
        for i, shot in enumerate(shots):
            position = shot.start_time / video_duration if video_duration > 0 else 0.5
            role = self.predict_role(
                duration=shot.duration,
                emotion=shot.emotion,
                camera=shot.camera,
                visual_score=shot.visual_score,
                position_in_video=position,
            )
            roles.append(role)

        # 后处理：确保顺序合理性
        # 通常顺序：hook -> gameplay -> reward -> ending
        if len(roles) >= 3:
            if roles[0] not in ["hook", "story"]:
                roles[0] = "hook"
            if roles[-1] not in ["ending", "reward"]:
                roles[-1] = "ending"

        return roles