"""Hook Predictor V2 — 升级版 Hook 评分

公式：
  Hook Score = Visual Impact×30% + Motion×25% + Subject Size×20% + Novelty×15% + Emotion×10%

新增：
- Subject Detection: 最大物体面积/占比
- Novelty: 前后帧变化程度
- Emotion: 颜色情绪（红=urgent, 蓝=cool, 金=reward）
"""
import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict


class HookPredictorV2:
    """V2 Hook 预测器"""

    def analyze(self, frame_paths: List[Path], video_name: str = "") -> Dict:
        valid = [p for p in frame_paths if p.exists()]
        if not valid:
            return self._empty_result()

        # 优先分析前3帧（代表前段内容）
        early = valid[:3] if len(valid) >= 3 else valid

        visual_impacts = []
        motions = []
        subject_sizes = []
        novelties = []
        emotions = []

        prev_gray = None
        for i, fp in enumerate(early):
            img = cv2.imread(str(fp))
            if img is None or img.size < 100:
                continue
            h, w = img.shape[:2]
            if h < 10 or w < 10:
                continue
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

            # 1. Visual Impact = 对比度 + 饱和度 + 边缘密度
            contrast = min(100, gray.std() / 80 * 100)
            saturation = min(100, hsv[:, :, 1].mean() / 255 * 100)
            edges = cv2.Canny(gray, 50, 150)
            edge_density = min(100, np.count_nonzero(edges) / (h * w) * 100 * 3)
            visual_impacts.append((contrast + saturation + edge_density) / 3)

            # 2. Motion = 帧间差分
            if prev_gray is not None:
                ph, pw = min(gray.shape[0], prev_gray.shape[0]), min(gray.shape[1], prev_gray.shape[1])
                gray_r = cv2.resize(gray, (pw, ph))
                prev_r = cv2.resize(prev_gray, (pw, ph))
                diff = cv2.absdiff(gray_r, prev_r).mean()
                motions.append(min(100, diff * 2))
            prev_gray = gray

            # 3. Subject Size = 最大轮廓面积占比
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                max_area = max(cv2.contourArea(c) for c in contours)
                subject_sizes.append(min(100, max_area / (h * w) * 100 * 5))
            else:
                subject_sizes.append(15)

            # 4. Novelty = 与第一帧的差异（动态变化感）
            if i > 0:
                first = cv2.imread(str(early[0]), cv2.IMREAD_GRAYSCALE)
                if first is not None:
                    fh, fw = min(gray.shape[0], first.shape[0]), min(gray.shape[1], first.shape[1])
                    gray_r = cv2.resize(gray, (fw, fh))
                    first_r = cv2.resize(first, (fw, fh))
                    novel = cv2.absdiff(gray_r, first_r).mean()
                    novelties.append(min(100, novel * 1.5))

            # 5. Emotion = 颜色情绪分析
            emotion = self._analyze_emotion(hsv)
            emotions.append(emotion)

        avg_impact = np.mean(visual_impacts) if visual_impacts else 30
        avg_motion = np.mean(motions) if motions else 25
        avg_subject = np.mean(subject_sizes) if subject_sizes else 20
        avg_novelty = np.mean(novelties) if novelties else 20
        avg_emotion = np.mean(emotions) if emotions else 30

        # 文件名加分
        name_bonus = self._name_bonus(video_name)

        hook_score = (
            avg_impact * 0.30 +
            avg_motion * 0.25 +
            avg_subject * 0.20 +
            avg_novelty * 0.15 +
            avg_emotion * 0.10 +
            name_bonus * 0.10
        )

        return {
            "hook_score": round(min(100, hook_score), 1),
            "visual_impact": round(avg_impact, 1),
            "motion": round(avg_motion, 1),
            "subject_size": round(avg_subject, 1),
            "novelty": round(avg_novelty, 1),
            "emotion": round(avg_emotion, 1),
            "name_bonus": name_bonus,
        }

    def _analyze_emotion(self, hsv: np.ndarray) -> float:
        """颜色情绪分析"""
        h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]

        # 高饱和度区域的情绪
        mask = s > 100
        if np.count_nonzero(mask) < 100:
            return 30

        hues = h[mask]
        # 红色(0-15) = urgent/anger, 橙色(15-30) = warm, 黄色(30-45) = happy
        # 蓝色(90-130) = cool/calm, 紫色(130-160) = magic/mystery
        red_ratio = np.count_nonzero((hues >= 0) & (hues < 20)) / len(hues)
        orange_ratio = np.count_nonzero((hues >= 20) & (hues < 40)) / len(hues)
        purple_ratio = np.count_nonzero((hues >= 130) & (hues < 170)) / len(hues)

        # 红色/橙色 = 高情绪冲击力，紫色 = 魔法感
        emotion = red_ratio * 80 + orange_ratio * 50 + purple_ratio * 40 + 20
        return min(100, emotion)

    def _name_bonus(self, name: str) -> float:
        s = name.lower()
        for kw in ["kaitou", "开场", "hook", "start", "intro", "trap", "surprise", "omg"]:
            if kw in s:
                return 40
        for kw in ["level", "vs", "boss", "dragon", "witch"]:
            if kw in s:
                return 25
        return 10

    def _empty_result(self) -> Dict:
        return {
            "hook_score": 30.0,
            "visual_impact": 30, "motion": 25,
            "subject_size": 20, "novelty": 20,
            "emotion": 30, "name_bonus": 10,
        }
