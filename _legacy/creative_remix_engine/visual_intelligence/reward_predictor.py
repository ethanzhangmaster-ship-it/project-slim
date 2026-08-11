"""Reward Predictor — 识别 Reward 类内容（Dragon/Castle/Treasure/Magic/Epic/Unlock/Evolution）"""
import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict


class RewardPredictor:
    """Reward 内容识别器"""

    REWARD_KEYWORDS = {
        "dragon": ["dragon", "龙", "egg", "evolution", "evolve", "legendary"],
        "castle": ["castle", "城堡", "kingdom", "fortress", "base", "home"],
        "treasure": ["treasure", "宝箱", "gold", "gem", "chest", "loot", "reward"],
        "magic": ["magic", "魔法", "spell", "witch", "wizard", "fairy", "enchant"],
        "epic": ["epic", "ultimate", "final", "god", "divine", "supreme"],
        "unlock": ["unlock", "解锁", "new", "discover", "reveal", "open"],
        "upgrade": ["upgrade", "升", "level up", "max", "power up", "enhance"],
    }

    def analyze(self, frame_paths: List[Path], video_name: str = "") -> Dict:
        """
        识别视频是否包含 Reward 类内容。
        基于文件名 + 帧特征（闪光检测、粒子效果、大物体出现）。
        """
        valid = [p for p in frame_paths if p.exists()]
        if not valid:
            return self._empty_result()

        # 文件名分析
        name_score, detected_types = self._analyze_name(video_name)

        # 帧特征分析
        flash_scores = []
        particle_scores = []
        big_object_scores = []
        brightness_peaks = []

        for fp in valid:
            img = cv2.imread(str(fp))
            if img is None:
                continue

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            h, w = img.shape[:2]

            # 闪光检测 (局部极亮区域)
            _, bright = cv2.threshold(gray, 220, 255, cv2.THRESH_BINARY)
            flash_ratio = np.count_nonzero(bright) / (h * w)
            flash_scores.append(min(100, flash_ratio * 100 * 10))

            # 粒子/特效检测 (高饱和度小区域)
            sat = hsv[:, :, 1]
            _, high_sat = cv2.threshold(sat, 200, 255, cv2.THRESH_BINARY)
            particle_scores.append(min(100, np.count_nonzero(high_sat) / (h * w) * 100 * 5))

            # 大物体出现 (Reward 通常有大物体居中)
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                max_area = max(cv2.contourArea(c) for c in contours)
                big_object_scores.append(min(100, max_area / (h * w) * 100 * 5))
            else:
                big_object_scores.append(10)

            # 亮度峰值
            brightness_peaks.append(min(100, gray.mean() / 255 * 100))

        avg_flash = np.mean(flash_scores) if flash_scores else 0
        avg_particle = np.mean(particle_scores) if particle_scores else 0
        avg_big = np.mean(big_object_scores) if big_object_scores else 0
        avg_bright = np.mean(brightness_peaks) if brightness_peaks else 0

        # Reward score = 文件名(25%) + 闪光(20%) + 粒子(20%) + 大物体(20%) + 亮度(15%)
        reward_score = (
            name_score * 0.25 +
            avg_flash * 0.20 +
            avg_particle * 0.20 +
            avg_big * 0.20 +
            avg_bright * 0.15
        )

        # 检测到的 reward 类型
        if not detected_types:
            if avg_flash > 40 or avg_particle > 40:
                detected_types = ["magic"]
            elif avg_big > 50:
                detected_types = ["dragon"]
            else:
                detected_types = ["reward"]

        return {
            "reward_score": round(min(100, reward_score), 1),
            "reward_types": detected_types,
            "flash_score": round(avg_flash, 1),
            "particle_score": round(avg_particle, 1),
            "big_object_score": round(avg_big, 1),
            "brightness_peak": round(avg_bright, 1),
            "name_score": name_score,
        }

    def _analyze_name(self, name: str) -> tuple:
        s = name.lower()
        scores = {}
        detected = []
        for rtype, kws in self.REWARD_KEYWORDS.items():
            for kw in kws:
                if kw in s:
                    scores[rtype] = scores.get(rtype, 0) + 25
                    if rtype not in detected:
                        detected.append(rtype)

        if not scores:
            return 20, []
        return min(100, max(scores.values())), detected

    def _empty_result(self) -> Dict:
        return {
            "reward_score": 20.0,
            "reward_types": ["unknown"],
            "flash_score": 0, "particle_score": 0,
            "big_object_score": 0, "brightness_peak": 0,
            "name_score": 20,
        }
