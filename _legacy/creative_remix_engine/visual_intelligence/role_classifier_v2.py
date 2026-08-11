"""Role Classifier V2 — 多标签素材分类

每个视频支持多角色标签，而不是单一分类。
例如：一个龙出现视频可以同时是 hook + reward + character
"""
import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict, Set


class RoleClassifierV2:
    """V2 角色分类器 — 多标签"""

    ROLE_KEYWORDS = {
        "hook": ["kaitou", "开场", "hook", "start", "intro", "begin", "trap", "cage", "save", "rescue"],
        "gameplay": ["wanfa", "玩法", "gameplay", "merge", "play", "hecheng", "drag", "swipe", "combo", "level"],
        "reward": ["juese", "角色", "reward", "character", "evol", "zhanshi", "dragon", "unlock", "legendary", "ultimate"],
        "problem": ["wenti", "问题", "problem", "challenge", "fail", "difficult", "boss", "enemy", "attack"],
        "cta": ["cta", "download", "结尾", "end", "get", "now", "free", "join"],
        "character": ["juese", "角色", "character", "witch", "dragon", "hero", "npc", "avatar"],
        "scene": ["changjing", "场景", "scene", "castle", "castle", "kingdom", "world", "map"],
    }

    def classify(self, video_name: str, frame_paths: List[Path]) -> Dict[str, float]:
        """
        返回每个角色的置信度分数 {role: score}
        基于文件名 + 帧特征的多标签分类
        """
        name_scores = self._score_by_name(video_name)
        visual_scores = self._score_by_visual(frame_paths)

        # 合并：文件名(60%) + 视觉(40%)
        final = {}
        for role in self.ROLE_KEYWORDS:
            ns = name_scores.get(role, 0)
            vs = visual_scores.get(role, 0)
            final[role] = round(ns * 0.6 + vs * 0.4, 1)

        return final

    def get_top_roles(self, scores: Dict[str, float], threshold: float = 30.0) -> List[str]:
        """获取超过阈值的角色标签"""
        return [r for r, s in sorted(scores.items(), key=lambda x: -x[1]) if s >= threshold]

    def _score_by_name(self, name: str) -> Dict[str, float]:
        s = name.lower()
        scores = {}
        for role, kws in self.ROLE_KEYWORDS.items():
            score = 20
            for kw in kws:
                if kw in s:
                    score += 30
            scores[role] = min(100, score)
        return scores

    def _score_by_visual(self, frame_paths: List[Path]) -> Dict[str, float]:
        """基于帧特征的视觉角色推断"""
        valid = [p for p in frame_paths if p.exists()]
        if not valid:
            return {r: 20 for r in self.ROLE_KEYWORDS}

        # 汇总帧特征
        total_area_ratio = []
        edge_density = []
        text_density = []
        color_variance = []

        for fp in valid:
            img = cv2.imread(str(fp))
            if img is None or img.size < 100:
                continue
            h, w = img.shape[:2]
            if h < 10 or w < 10:
                continue
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            h, w = img.shape[:2]

            # 最大物体面积比
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                max_area = max(cv2.contourArea(c) for c in contours)
                total_area_ratio.append(max_area / (h * w))

            # 边缘密度
            edges = cv2.Canny(gray, 50, 150)
            edge_density.append(np.count_nonzero(edges) / (h * w))

            # 文字密度（高边缘小区域）
            text_density.append(np.count_nonzero(edges) / (h * w) * 0.5)

            # 色彩方差
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            color_variance.append(hsv[:, :, 1].std())

        avg_area = np.mean(total_area_ratio) if total_area_ratio else 0.1
        avg_edge = np.mean(edge_density) if edge_density else 0.05
        avg_text = np.mean(text_density) if text_density else 0.02
        avg_color = np.mean(color_variance) if color_variance else 30

        # 角色 → 视觉特征映射
        return {
            "hook": min(100, (avg_edge * 500 + avg_area * 300 + avg_color * 0.5)),
            "gameplay": min(100, (avg_edge * 300 + avg_text * 200 + 30)),
            "reward": min(100, (avg_area * 400 + avg_color * 0.8 + 20)),
            "problem": min(100, (avg_edge * 200 + avg_area * 100 + 20)),
            "cta": min(100, (avg_text * 400 + 30)),
            "character": min(100, (avg_area * 500 + avg_color * 0.6 + 20)),
            "scene": min(100, (avg_edge * 150 + avg_area * 200 + 30)),
        }
