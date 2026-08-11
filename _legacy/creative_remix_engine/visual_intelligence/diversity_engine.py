"""Diversity Engine — 避免连续镜头在颜色/角度/主体/运动上重复"""
import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple


class DiversityEngine:
    """多样性引擎"""

    def compute_diversity_penalty(self, frame_paths_list: List[List[Path]]) -> float:
        """
        计算一组视频之间的多样性惩罚分。
        frame_paths_list: 每个视频对应的帧路径列表
        返回: 0-100 的惩罚分（越高越相似，应该避免）
        """
        if len(frame_paths_list) < 2:
            return 0.0

        features = []
        for fps in frame_paths_list:
            feat = self._extract_features(fps)
            features.append(feat)

        penalties = []
        for i in range(len(features)):
            for j in range(i + 1, len(features)):
                sim = self._similarity(features[i], features[j])
                penalties.append(sim)

        return round(np.mean(penalties) if penalties else 0, 1)

    def _extract_features(self, frame_paths: List[Path]) -> Dict:
        """提取视频的颜色/运动/主体特征摘要"""
        valid = [p for p in frame_paths if p.exists()]
        if not valid:
            return {"color_hist": None, "edge_hist": None, "brightness": 50}

        color_hists = []
        edge_hists = []
        brightnesses = []

        for fp in valid:
            img = cv2.imread(str(fp))
            if img is None:
                continue
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # 颜色直方图 (H通道，16 bin)
            hist = cv2.calcHist([hsv], [0], None, [16], [0, 180])
            hist = hist.flatten() / (hist.sum() + 1e-8)
            color_hists.append(hist)

            # 边缘方向直方图
            edges = cv2.Canny(gray, 50, 150)
            gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
            gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
            mag = np.sqrt(gx ** 2 + gy ** 2)
            ori = np.arctan2(gy, gx) * 180 / np.pi
            ori = (ori + 180) % 180
            edge_hist = np.zeros(8)
            for b in range(8):
                mask = (ori >= b * 22.5) & (ori < (b + 1) * 22.5) & (edges > 0)
                edge_hist[b] = np.count_nonzero(mask)
            edge_hist = edge_hist / (edge_hist.sum() + 1e-8)
            edge_hists.append(edge_hist)

            brightnesses.append(gray.mean())

        return {
            "color_hist": np.mean(color_hists, axis=0) if color_hists else None,
            "edge_hist": np.mean(edge_hists, axis=0) if edge_hists else None,
            "brightness": np.mean(brightnesses) if brightnesses else 50,
        }

    def _similarity(self, a: Dict, b: Dict) -> float:
        """计算两个视频特征的相似度 (0-100)"""
        scores = []

        if a["color_hist"] is not None and b["color_hist"] is not None:
            # 巴氏距离
            bc = np.sum(np.sqrt(a["color_hist"] * b["color_hist"]))
            scores.append(bc * 100)

        if a["edge_hist"] is not None and b["edge_hist"] is not None:
            bc = np.sum(np.sqrt(a["edge_hist"] * b["edge_hist"]))
            scores.append(bc * 100)

        # 亮度相似
        bright_sim = max(0, 100 - abs(a["brightness"] - b["brightness"]))
        scores.append(bright_sim)

        return np.mean(scores) if scores else 50.0

    def check_sequence_diversity(self, selected_videos: List[Path],
                                 threshold: float = 75.0) -> List[str]:
        """
        检查已选视频序列的多样性问题。
        返回问题列表。
        """
        issues = []
        if len(selected_videos) < 2:
            return issues

        # 检查是否重复使用同一源视频
        stems = [v.stem for v in selected_videos]
        if len(stems) != len(set(stems)):
            issues.append("DUPLICATE_SOURCE")

        return issues
