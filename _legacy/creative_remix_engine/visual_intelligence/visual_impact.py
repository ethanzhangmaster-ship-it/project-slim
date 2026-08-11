"""Visual Impact Analyzer — 对比度、亮度、饱和度、清晰度等"""
import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict
from PIL import Image


class VisualImpactAnalyzer:
    """视觉冲击力分析器"""

    def analyze(self, frame_paths: List[Path]) -> Dict:
        """
        分析多帧的视觉冲击力指标。
        返回: {impact_score, contrast, brightness, saturation, sharpness, color_diversity, subject_size, foreground_ratio}
        """
        valid = [p for p in frame_paths if p.exists()]
        if not valid:
            return self._empty_result()

        scores = []
        for fp in valid:
            img = cv2.imread(str(fp))
            if img is None:
                continue
            scores.append(self._analyze_frame(img))

        if not scores:
            return self._empty_result()

        # 取平均（可用最高分代表峰值冲击力）
        avg = {k: np.mean([s[k] for s in scores]) for k in scores[0]}
        peak = {k: max([s[k] for s in scores]) for k in scores[0]}

        # impact_score = 加权组合（峰值占 60%，平均占 40%）
        impact = (
            peak.get("contrast", 0) * 0.15 +
            peak.get("saturation", 0) * 0.15 +
            peak.get("sharpness", 0) * 0.20 +
            peak.get("color_diversity", 0) * 0.15 +
            peak.get("subject_size", 0) * 0.15 +
            avg.get("brightness", 0) * 0.05 +
            avg.get("foreground_ratio", 0) * 0.15
        )

        return {
            "impact_score": round(min(100, impact), 1),
            "contrast": round(avg["contrast"], 1),
            "brightness": round(avg["brightness"], 1),
            "saturation": round(avg["saturation"], 1),
            "sharpness": round(avg["sharpness"], 1),
            "color_diversity": round(avg["color_diversity"], 1),
            "subject_size": round(avg["subject_size"], 1),
            "foreground_ratio": round(avg["foreground_ratio"], 1),
        }

    def _analyze_frame(self, img: np.ndarray) -> Dict:
        """单帧分析"""
        h, w = img.shape[:2]
        if h < 10 or w < 10:
            return {"contrast": 30, "brightness": 50, "saturation": 30,
                    "sharpness": 20, "color_diversity": 25, "subject_size": 20, "foreground_ratio": 20}
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        # 对比度 (标准差归一化)
        contrast = min(100, gray.std() / 80 * 100)

        # 亮度
        brightness = min(100, gray.mean() / 255 * 100)

        # 饱和度
        saturation = min(100, hsv[:, :, 1].mean() / 255 * 100)

        # 清晰度 (拉普拉斯方差)
        lap = cv2.Laplacian(gray, cv2.CV_64F)
        sharpness = min(100, lap.var() / 500 * 100)

        # 色彩多样性 (HSV 直方图熵)
        hist_h = cv2.calcHist([hsv], [0], None, [32], [0, 180])
        hist_h = hist_h.flatten() / (hist_h.sum() + 1e-8)
        entropy = -np.sum(hist_h * np.log2(hist_h + 1e-8))
        color_diversity = min(100, entropy / 5 * 100)

        # 主体尺寸估计 (用最大轮廓面积占比)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            max_area = max(cv2.contourArea(c) for c in contours)
            subject_size = min(100, max_area / (h * w) * 100 * 3)  # *3 因为主体通常占 1/3
        else:
            subject_size = 20

        # 前景比例 (高对比度区域占比)
        edges = cv2.Canny(gray, 50, 150)
        foreground_ratio = min(100, np.count_nonzero(edges) / (h * w) * 100 * 5)

        return {
            "contrast": contrast,
            "brightness": brightness,
            "saturation": saturation,
            "sharpness": sharpness,
            "color_diversity": color_diversity,
            "subject_size": subject_size,
            "foreground_ratio": foreground_ratio,
        }

    def _empty_result(self) -> Dict:
        return {
            "impact_score": 40.0,
            "contrast": 40, "brightness": 50, "saturation": 40,
            "sharpness": 30, "color_diversity": 35,
            "subject_size": 25, "foreground_ratio": 30,
        }
