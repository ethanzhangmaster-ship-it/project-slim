"""Drag Detector — 拖拽游戏玩法检测器

检测逻辑：
1. 单个物体移动
2. 移动轨迹线性
3. 目标位置有明显目标点

输出：
{
  "gameplay": true,
  "action": "drag",
  "clarity": 0.85
}
"""
from typing import List, Dict, Tuple
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class DragDetection:
    gameplay: bool
    action: str
    confidence: float
    clarity: float


@dataclass
class DragEvent:
    event_type: str
    start_time: float
    end_time: float
    confidence: float
    details: Dict


class DragDetector:
    """拖拽游戏检测器"""

    def __init__(self, min_drag_confidence: float = 0.5):
        self.min_drag_confidence = min_drag_confidence

    def detect(self, frames: List[np.ndarray]) -> DragDetection:
        """检测拖拽玩法"""
        if len(frames) < 5:
            return DragDetection(
                gameplay=False,
                action="drag",
                confidence=0.0,
                clarity=0.0
            )

        drag_score = 0.0

        single_object_motion = self._detect_single_object_motion(frames)
        drag_score += single_object_motion * 0.35

        linear_trajectory = self._detect_linear_trajectory(frames)
        drag_score += linear_trajectory * 0.35

        target_point = self._detect_target_point(frames)
        drag_score += target_point * 0.3

        gameplay = drag_score >= self.min_drag_confidence
        clarity = self._calculate_clarity(frames)

        return DragDetection(
            gameplay=gameplay,
            action="drag",
            confidence=round(drag_score, 2),
            clarity=round(clarity, 2)
        )

    def detect_events(self, frames: List[np.ndarray]) -> List[DragEvent]:
        """检测拖拽事件序列"""
        events = []

        if len(frames) < 8:
            return events

        fps = 30
        window_size = 6

        for i in range(len(frames) - window_size):
            window = frames[i:i+window_size]

            single_motion = self._detect_single_object_motion(window)
            linear_traj = self._detect_linear_trajectory(window)
            target = self._detect_target_point(window)

            confidence = (single_motion + linear_traj + target) / 3

            if confidence > 0.4:
                events.append(DragEvent(
                    event_type="drag",
                    start_time=i * fps,
                    end_time=(i + window_size) * fps,
                    confidence=round(confidence, 2),
                    details={
                        "single_object_motion": single_motion,
                        "linear_trajectory": linear_traj,
                        "target_point": target,
                    }
                ))

        return events

    def _detect_single_object_motion(self, frames: List[np.ndarray]) -> float:
        """检测单个物体的移动"""
        if len(frames) < 3:
            return 0.0

        score = 0.0
        for i in range(1, len(frames)):
            prev_frame = frames[i-1]
            curr_frame = frames[i]

            prev_objects = self._find_object_centers(prev_frame)
            curr_objects = self._find_object_centers(curr_frame)

            if len(prev_objects) == 1 and len(curr_objects) == 1:
                dist = np.linalg.norm(np.array(prev_objects[0]) - np.array(curr_objects[0]))
                if dist > 20:
                    score += 0.3

        return min(1.0, score / (len(frames) - 1))

    def _find_object_centers(self, frame: np.ndarray) -> List[Tuple[int, int]]:
        """找到画面中的物体中心"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (7, 7), 0)

        _, thresh = cv2.threshold(blurred, 120, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        centers = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if 500 < area < 8000:
                M = cv2.moments(contour)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    centers.append((cx, cy))

        return centers

    def _detect_linear_trajectory(self, frames: List[np.ndarray]) -> float:
        """检测线性移动轨迹"""
        if len(frames) < 4:
            return 0.0

        centers_over_time = []
        for frame in frames:
            centers = self._find_object_centers(frame)
            if centers:
                centers_over_time.append(centers[0])

        if len(centers_over_time) < 3:
            return 0.0

        points = np.array(centers_over_time)
        if len(points) < 3:
            return 0.0

        x = points[:, 0]
        y = points[:, 1]

        A = np.vstack([x, np.ones(len(x))]).T
        m, c = np.linalg.lstsq(A, y, rcond=None)[0]

        y_pred = m * x + c
        residuals = np.sqrt(np.mean((y - y_pred) ** 2))

        if residuals < 30:
            return min(1.0, 1 - residuals / 100)
        return 0.0

    def _detect_target_point(self, frames: List[np.ndarray]) -> float:
        """检测目标点（拖拽目标位置）"""
        if len(frames) < 3:
            return 0.0

        last_frame = frames[-1]
        gray = cv2.cvtColor(last_frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        _, thresh = cv2.threshold(blurred, 150, 255, cv2.THRESH_BINARY)

        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        center_area = []
        h, w = last_frame.shape[:2]
        center_region = last_frame[h//4:3*h//4, w//4:3*w//4]
        center_gray = cv2.cvtColor(center_region, cv2.COLOR_BGR2GRAY)

        high_intensity = np.sum(center_gray > 200)
        if high_intensity > center_gray.size * 0.05:
            return 0.7

        for contour in contours:
            area = cv2.contourArea(contour)
            if area > 1000:
                M = cv2.moments(contour)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    if w//4 < cx < 3*w//4 and h//4 < cy < 3*h//4:
                        center_area.append(area)

        if center_area:
            return 0.5
        return 0.0

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