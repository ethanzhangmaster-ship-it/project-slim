"""Reward Detector — 奖励事件检测器

检测逻辑：
1. 画面突然变亮（奖励闪光）
2. 金币/宝石出现
3. 文字"获得"/"奖励"/"+数字"
4. 物体变大或变多

输出：
{
  "gameplay": true,
  "action": "reward",
  "clarity": 0.95
}
"""
from typing import List, Dict, Tuple
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class RewardDetection:
    gameplay: bool
    action: str
    confidence: float
    clarity: float


@dataclass
class RewardEvent:
    event_type: str
    start_time: float
    end_time: float
    confidence: float
    details: Dict


class RewardDetector:
    """奖励事件检测器"""

    def __init__(self, min_reward_confidence: float = 0.5):
        self.min_reward_confidence = min_reward_confidence

    def detect(self, frames: List[np.ndarray]) -> RewardDetection:
        """检测奖励事件"""
        if len(frames) < 5:
            return RewardDetection(
                gameplay=False,
                action="reward",
                confidence=0.0,
                clarity=0.0
            )

        reward_score = 0.0

        brightness_spike = self._detect_brightness_spike(frames)
        reward_score += brightness_spike * 0.3

        gold_coins = self._detect_gold_coins(frames)
        reward_score += gold_coins * 0.25

        text_reward = self._detect_reward_text(frames)
        reward_score += text_reward * 0.3

        object_appearance = self._detect_object_appearance(frames)
        reward_score += object_appearance * 0.15

        gameplay = reward_score >= self.min_reward_confidence
        clarity = self._calculate_clarity(frames)

        return RewardDetection(
            gameplay=gameplay,
            action="reward",
            confidence=round(reward_score, 2),
            clarity=round(clarity, 2)
        )

    def detect_events(self, frames: List[np.ndarray]) -> List[RewardEvent]:
        """检测奖励事件序列"""
        events = []

        if len(frames) < 8:
            return events

        fps = 30
        window_size = 5

        for i in range(len(frames) - window_size):
            window = frames[i:i+window_size]

            brightness = self._detect_brightness_spike(window)
            gold = self._detect_gold_coins(window)
            text = self._detect_reward_text(window)
            obj_app = self._detect_object_appearance(window)

            confidence = (brightness + gold + text + obj_app) / 4

            if confidence > 0.4:
                events.append(RewardEvent(
                    event_type="reward",
                    start_time=i * fps,
                    end_time=(i + window_size) * fps,
                    confidence=round(confidence, 2),
                    details={
                        "brightness_spike": brightness,
                        "gold_coins": gold,
                        "reward_text": text,
                        "object_appearance": obj_app,
                    }
                ))

        return events

    def _detect_brightness_spike(self, frames: List[np.ndarray]) -> float:
        """检测亮度突然增加（奖励闪光）"""
        if len(frames) < 3:
            return 0.0

        brightness_values = []
        for frame in frames:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            brightness_values.append(np.mean(gray))

        if len(brightness_values) < 3:
            return 0.0

        max_brightness = max(brightness_values)
        avg_brightness = np.mean(brightness_values)

        if max_brightness > avg_brightness * 1.5:
            return min(1.0, (max_brightness - avg_brightness) / avg_brightness)
        return 0.0

    def _detect_gold_coins(self, frames: List[np.ndarray]) -> float:
        """检测金币/宝石（黄色/金色物体）"""
        if len(frames) < 3:
            return 0.0

        gold_count = 0
        for frame in frames:
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

            yellow_mask = cv2.inRange(hsv, (20, 100, 100), (40, 255, 255))
            gold_mask = cv2.inRange(hsv, (40, 100, 100), (60, 255, 255))

            combined_mask = cv2.bitwise_or(yellow_mask, gold_mask)
            gold_area = np.sum(combined_mask)

            if gold_area > frame.size * 0.03:
                gold_count += 1

        return min(1.0, gold_count / len(frames))

    def _detect_reward_text(self, frames: List[np.ndarray]) -> float:
        """检测奖励文字（白色/黄色文字区域）"""
        if len(frames) < 3:
            return 0.0

        text_count = 0
        for frame in frames:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)

            contours, _ = cv2.findContours(
                thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )

            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                aspect_ratio = w / h
                area = cv2.contourArea(contour)

                if 0.2 < aspect_ratio < 3.0 and 50 < area < 2000:
                    if y < frame.shape[0] * 0.3 or y > frame.shape[0] * 0.7:
                        text_count += 1
                        break

        return min(1.0, text_count / len(frames))

    def _detect_object_appearance(self, frames: List[np.ndarray]) -> float:
        """检测新物体出现（奖励获得）"""
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