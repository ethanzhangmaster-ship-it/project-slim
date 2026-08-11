"""Upgrade Detector — 升级游戏玩法检测器

检测逻辑：
1. 物体发光/特效
2. 数字变化（等级提升）
3. 颜色变化（升级后变色）
4. 新物体出现

输出：
{
  "gameplay": true,
  "action": "upgrade",
  "clarity": 0.88
}
"""
from typing import List, Dict, Tuple
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class UpgradeDetection:
    gameplay: bool
    action: str
    confidence: float
    clarity: float


@dataclass
class UpgradeEvent:
    event_type: str
    start_time: float
    end_time: float
    confidence: float
    details: Dict


class UpgradeDetector:
    """升级游戏检测器"""

    def __init__(self, min_upgrade_confidence: float = 0.5):
        self.min_upgrade_confidence = min_upgrade_confidence

    def detect(self, frames: List[np.ndarray]) -> UpgradeDetection:
        """检测升级玩法"""
        if len(frames) < 5:
            return UpgradeDetection(
                gameplay=False,
                action="upgrade",
                confidence=0.0,
                clarity=0.0
            )

        upgrade_score = 0.0

        glow_effect = self._detect_glow_effect(frames)
        upgrade_score += glow_effect * 0.3

        number_change = self._detect_number_change(frames)
        upgrade_score += number_change * 0.35

        color_change = self._detect_color_change(frames)
        upgrade_score += color_change * 0.2

        new_object = self._detect_new_object_appearance(frames)
        upgrade_score += new_object * 0.15

        gameplay = upgrade_score >= self.min_upgrade_confidence
        clarity = self._calculate_clarity(frames)

        return UpgradeDetection(
            gameplay=gameplay,
            action="upgrade",
            confidence=round(upgrade_score, 2),
            clarity=round(clarity, 2)
        )

    def detect_events(self, frames: List[np.ndarray]) -> List[UpgradeEvent]:
        """检测升级事件序列"""
        events = []

        if len(frames) < 8:
            return events

        fps = 30
        window_size = 6

        for i in range(len(frames) - window_size):
            window = frames[i:i+window_size]

            glow = self._detect_glow_effect(window)
            number = self._detect_number_change(window)
            color = self._detect_color_change(window)
            new_obj = self._detect_new_object_appearance(window)

            confidence = (glow + number + color + new_obj) / 4

            if confidence > 0.4:
                events.append(UpgradeEvent(
                    event_type="upgrade",
                    start_time=i * fps,
                    end_time=(i + window_size) * fps,
                    confidence=round(confidence, 2),
                    details={
                        "glow_effect": glow,
                        "number_change": number,
                        "color_change": color,
                        "new_object": new_obj,
                    }
                ))

        return events

    def _detect_glow_effect(self, frames: List[np.ndarray]) -> float:
        """检测发光特效（升级时的闪光）"""
        if len(frames) < 3:
            return 0.0

        glow_count = 0
        for frame in frames:
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

            bright_mask = cv2.inRange(hsv, (0, 50, 200), (180, 255, 255))
            bright_area = np.sum(bright_mask)

            if bright_area > frame.size * 0.05:
                glow_count += 1

        return min(1.0, glow_count / len(frames))

    def _detect_number_change(self, frames: List[np.ndarray]) -> float:
        """检测数字变化（等级提升）"""
        if len(frames) < 3:
            return 0.0

        digit_regions = []
        for frame in frames:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
            contours, _ = cv2.findContours(
                thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )

            for contour in contours:
                area = cv2.contourArea(contour)
                if 50 < area < 500:
                    x, y, w, h = cv2.boundingRect(contour)
                    aspect_ratio = w / h
                    if 0.3 < aspect_ratio < 1.5:
                        digit_regions.append((x, y, w, h))

        if len(digit_regions) < 2:
            return 0.0

        changes = 0
        for i in range(1, len(digit_regions)):
            prev = digit_regions[i-1]
            curr = digit_regions[i]
            if abs(prev[0] - curr[0]) > 5 or abs(prev[1] - curr[1]) > 5:
                changes += 1

        return min(1.0, changes / max(1, len(digit_regions) - 1))

    def _detect_color_change(self, frames: List[np.ndarray]) -> float:
        """检测颜色变化（升级后物体变色）"""
        if len(frames) < 3:
            return 0.0

        first_frame = frames[0]
        last_frame = frames[-1]

        first_hsv = cv2.cvtColor(first_frame, cv2.COLOR_BGR2HSV)
        last_hsv = cv2.cvtColor(last_frame, cv2.COLOR_BGR2HSV)

        hue_diff = np.mean(np.abs(first_hsv[:, :, 0] - last_hsv[:, :, 0]))
        sat_diff = np.mean(np.abs(first_hsv[:, :, 1] - last_hsv[:, :, 1]))

        total_diff = (hue_diff + sat_diff) / 2

        if total_diff > 30:
            return min(1.0, total_diff / 100)
        return 0.0

    def _detect_new_object_appearance(self, frames: List[np.ndarray]) -> float:
        """检测新物体出现"""
        if len(frames) < 3:
            return 0.0

        first_count = self._count_objects(frames[0])
        last_count = self._count_objects(frames[-1])

        if last_count > first_count:
            return min(1.0, (last_count - first_count) / max(1, first_count))
        return 0.0

    def _count_objects(self, frame: np.ndarray) -> int:
        """计数物体"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        _, thresh = cv2.threshold(blurred, 100, 255, cv2.THRESH_BINARY)

        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        count = 0
        for contour in contours:
            area = cv2.contourArea(contour)
            if 200 < area < 10000:
                count += 1

        return count

    def _calculate_clarity(self, frames: List[np.ndarray]) -> float:
        """计算画面清晰度"""
        if not frames:
            return 0.5

        sharpness_scores = []
        for frame in frames:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
            sharpness_scores.append(min(100, sharpness / 20))

        return np.mean(sharpness_scores) / 100