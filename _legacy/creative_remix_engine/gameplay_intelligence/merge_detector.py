"""Merge Detector — 合并游戏玩法检测器

检测逻辑：
1. 两个物体靠近
2. 移动轨迹汇聚
3. 合成结果（物体数量减少或变大）

输出：
{
  "gameplay": true,
  "action": "merge",
  "clarity": 0.92
}
"""
from typing import List, Dict, Tuple
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class MergeDetection:
    gameplay: bool
    action: str
    confidence: float
    clarity: float


@dataclass
class MergeEvent:
    event_type: str
    start_time: float
    end_time: float
    confidence: float
    details: Dict


class MergeDetector:
    """合并游戏检测器"""

    def __init__(self, min_merge_confidence: float = 0.6):
        self.min_merge_confidence = min_merge_confidence

    def detect(self, frames: List[np.ndarray]) -> MergeDetection:
        """检测合并玩法"""
        if len(frames) < 5:
            return MergeDetection(
                gameplay=False,
                action="merge",
                confidence=0.0,
                clarity=0.0
            )

        merge_score = 0.0

        object_convergence = self._detect_object_convergence(frames)
        merge_score += object_convergence * 0.4

        size_increase = self._detect_size_increase(frames)
        merge_score += size_increase * 0.3

        count_decrease = self._detect_object_count_decrease(frames)
        merge_score += count_decrease * 0.3

        gameplay = merge_score >= self.min_merge_confidence
        clarity = self._calculate_clarity(frames)

        return MergeDetection(
            gameplay=gameplay,
            action="merge",
            confidence=round(merge_score, 2),
            clarity=round(clarity, 2)
        )

    def detect_events(self, frames: List[np.ndarray]) -> List[MergeEvent]:
        """检测合并事件序列"""
        events = []

        if len(frames) < 10:
            return events

        fps = 30
        window_size = 5

        for i in range(len(frames) - window_size):
            window = frames[i:i+window_size]

            object_convergence = self._detect_object_convergence(window)
            size_increase = self._detect_size_increase(window)
            count_decrease = self._detect_object_count_decrease(window)

            confidence = (object_convergence + size_increase + count_decrease) / 3

            if confidence > 0.5:
                events.append(MergeEvent(
                    event_type="merge",
                    start_time=i * fps,
                    end_time=(i + window_size) * fps,
                    confidence=round(confidence, 2),
                    details={
                        "object_convergence": object_convergence,
                        "size_increase": size_increase,
                        "count_decrease": count_decrease,
                    }
                ))

        return events

    def _detect_object_convergence(self, frames: List[np.ndarray]) -> float:
        """检测物体汇聚（两个物体移动到一起）"""
        if len(frames) < 3:
            return 0.0

        score = 0.0
        for i in range(1, len(frames)):
            prev_frame = frames[i-1]
            curr_frame = frames[i]

            prev_centers = self._find_object_centers(prev_frame)
            curr_centers = self._find_object_centers(curr_frame)

            if len(prev_centers) >= 2 and len(curr_centers) >= 1:
                distances = []
                for pc in prev_centers:
                    for cc in curr_centers:
                        dist = np.linalg.norm(np.array(pc) - np.array(cc))
                        distances.append(dist)

                if distances:
                    min_dist = min(distances)
                    if min_dist < 50:
                        score += 0.3

        return min(1.0, score / (len(frames) - 1))

    def _find_object_centers(self, frame: np.ndarray) -> List[Tuple[int, int]]:
        """找到画面中的物体中心"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        _, thresh = cv2.threshold(blurred, 100, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        centers = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if 200 < area < 5000:
                M = cv2.moments(contour)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    centers.append((cx, cy))

        return centers[:5]

    def _detect_size_increase(self, frames: List[np.ndarray]) -> float:
        """检测物体尺寸增加（合并后变大）"""
        if len(frames) < 3:
            return 0.0

        first_frame = frames[0]
        last_frame = frames[-1]

        first_objects = self._get_object_sizes(first_frame)
        last_objects = self._get_object_sizes(last_frame)

        if not first_objects or not last_objects:
            return 0.0

        avg_first_size = np.mean(first_objects)
        avg_last_size = np.mean(last_objects)

        if avg_last_size > avg_first_size * 1.2:
            return min(1.0, (avg_last_size - avg_first_size) / avg_first_size)
        return 0.0

    def _get_object_sizes(self, frame: np.ndarray) -> List[float]:
        """获取物体尺寸列表"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        _, thresh = cv2.threshold(blurred, 100, 255, cv2.THRESH_BINARY)

        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        sizes = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if 200 < area < 10000:
                sizes.append(area)

        return sizes

    def _detect_object_count_decrease(self, frames: List[np.ndarray]) -> float:
        """检测物体数量减少（合并后数量变少）"""
        if len(frames) < 3:
            return 0.0

        first_count = self._count_objects(frames[0])
        last_count = self._count_objects(frames[-1])

        if first_count >= 2 and last_count < first_count:
            return min(1.0, (first_count - last_count) / first_count)
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