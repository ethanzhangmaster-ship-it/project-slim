"""Hook Predictor — 预测镜头是否适合作为前3秒 Hook"""
import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict


class HookPredictor:
    """Hook 效果预测器"""

    def analyze(self, frame_paths: List[Path], video_name: str = "") -> Dict:
        """
        预测该视频作为前3秒 Hook 的效果。
        分析: 人物尺寸、运动量、亮度变化、颜色冲击、文字密度、视觉焦点
        """
        valid = [p for p in frame_paths if p.exists()]
        if not valid:
            return self._empty_result()

        # 优先分析前两帧（代表前段内容）
        early_frames = valid[:3] if len(valid) >= 3 else valid

        subject_sizes = []
        brightness_changes = []
        color_shocks = []
        text_densities = []
        focus_scores = []

        prev_brightness = None
        for fp in early_frames:
            img = cv2.imread(str(fp))
            if img is None:
                continue

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            h, w = img.shape[:2]

            # 人物/主体尺寸 (用最大轮廓估计)
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                max_area = max(cv2.contourArea(c) for c in contours)
                subject_sizes.append(min(100, max_area / (h * w) * 100 * 4))
            else:
                subject_sizes.append(15)

            # 亮度变化 (Hook 通常有强烈的明暗变化)
            brightness = gray.mean()
            if prev_brightness is not None:
                brightness_changes.append(min(100, abs(brightness - prev_brightness) / 2))
            prev_brightness = brightness

            # 颜色冲击 (高饱和度 + 高对比度)
            saturation = hsv[:, :, 1].mean() / 255 * 100
            contrast = gray.std() / 80 * 100
            color_shocks.append(min(100, (saturation + contrast) / 2))

            # 文字密度 (用边缘密度估算)
            edges = cv2.Canny(gray, 50, 150)
            text_densities.append(min(100, np.count_nonzero(edges) / (h * w) * 100 * 3))

            # 视觉焦点 (中心区域对比度)
            cx, cy = w // 2, h // 2
            center = gray[cy - h // 4:cy + h // 4, cx - w // 4:cx + w // 4]
            if center.size > 0:
                focus_scores.append(min(100, center.std() / 60 * 100))
            else:
                focus_scores.append(30)

        # 文件名加分
        name_bonus = self._name_bonus(video_name)

        avg_subj = np.mean(subject_sizes) if subject_sizes else 30
        avg_bright = np.mean(brightness_changes) if brightness_changes else 20
        avg_color = np.mean(color_shocks) if color_shocks else 30
        avg_text = np.mean(text_densities) if text_densities else 20
        avg_focus = np.mean(focus_scores) if focus_scores else 30

        hook_score = (
            avg_subj * 0.20 +
            avg_bright * 0.20 +
            avg_color * 0.20 +
            avg_text * 0.15 +
            avg_focus * 0.15 +
            name_bonus * 0.10
        )

        return {
            "hook_score": round(min(100, hook_score), 1),
            "subject_size": round(avg_subj, 1),
            "brightness_change": round(avg_bright, 1),
            "color_shock": round(avg_color, 1),
            "text_density": round(avg_text, 1),
            "visual_focus": round(avg_focus, 1),
            "name_bonus": name_bonus,
        }

    def _name_bonus(self, name: str) -> float:
        """文件名 Hook 信号"""
        s = name.lower()
        hook_kw = ["kaitou", "开场", "hook", "start", "intro", "level", "vs",
                   "boss", "attack", "dragon", "witch", "trap", "rescue"]
        for kw in hook_kw:
            if kw in s:
                return 40
        return 10

    def _empty_result(self) -> Dict:
        return {
            "hook_score": 30.0,
            "subject_size": 20, "brightness_change": 15,
            "color_shock": 20, "text_density": 15, "visual_focus": 20,
            "name_bonus": 10,
        }
