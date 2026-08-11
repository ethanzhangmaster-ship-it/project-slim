"""Gameplay Intelligence Engine — 真实游戏玩法理解引擎

这是买量最重要的部分。

检测游戏玩法类型：
- Merge: 合并游戏
- Drag: 拖拽游戏
- Upgrade: 升级游戏
- Match3: 三消游戏
- Idle: 放置游戏
- RPG: 角色扮演游戏

输入：视频片段（Shot）
输出：玩法类型和置信度

算法：
1. 运动轨迹分析
2. 对象识别
3. 合成结果检测
4. 游戏UI分析
"""
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

import cv2
import numpy as np


@dataclass
class GameplayResult:
    """玩法检测结果"""
    gameplay_type: str
    confidence: float
    action: str
    clarity: float
    objects_detected: int
    motion_trajectory: List[Tuple[int, int]]
    timestamp: str


@dataclass
class GameplayEvent:
    """游戏玩法事件"""
    event_type: str
    start_time: float
    end_time: float
    confidence: float
    details: Dict


class GameplayDetector:
    """游戏玩法检测器"""

    GAMEPLAY_TYPES = [
        "merge",
        "drag",
        "upgrade",
        "match3",
        "idle",
        "rpg",
        "puzzle",
        "strategy",
    ]

    def __init__(self):
        self.merge_detector = None
        self.drag_detector = None
        self.upgrade_detector = None
        self.reward_detector = None
        self._load_sub_detectors()

    def _load_sub_detectors(self):
        """延迟加载子检测器"""
        try:
            from .merge_detector import MergeDetector
            self.merge_detector = MergeDetector()
        except ImportError:
            pass

        try:
            from .drag_detector import DragDetector
            self.drag_detector = DragDetector()
        except ImportError:
            pass

        try:
            from .upgrade_detector import UpgradeDetector
            self.upgrade_detector = UpgradeDetector()
        except ImportError:
            pass

        try:
            from .reward_detector import RewardDetector
            self.reward_detector = RewardDetector()
        except ImportError:
            pass

    def detect(self, video_path: Path, start_time: float = 0,
               end_time: float = 30) -> GameplayResult:
        """检测视频中的游戏玩法"""
        frames = self._extract_frames(video_path, start_time, end_time)

        if not frames:
            return self._fallback_result()

        results = {}

        if self.merge_detector:
            merge_result = self.merge_detector.detect(frames)
            results["merge"] = merge_result.confidence

        if self.drag_detector:
            drag_result = self.drag_detector.detect(frames)
            results["drag"] = drag_result.confidence

        if self.upgrade_detector:
            upgrade_result = self.upgrade_detector.detect(frames)
            results["upgrade"] = upgrade_result.confidence

        results["match3"] = self._detect_match3(frames)
        results["idle"] = self._detect_idle(frames)
        results["rpg"] = self._detect_rpg(frames)

        gameplay_type = max(results, key=results.get)
        confidence = results[gameplay_type]

        action = self._infer_action(gameplay_type, confidence)
        clarity = self._calculate_clarity(frames)

        return GameplayResult(
            gameplay_type=gameplay_type,
            confidence=round(confidence, 2),
            action=action,
            clarity=round(clarity, 2),
            objects_detected=self._count_objects(frames),
            motion_trajectory=self._extract_trajectory(frames),
            timestamp=datetime.now().isoformat(),
        )

    def detect_events(self, video_path: Path, start_time: float = 0,
                      end_time: float = 30) -> List[GameplayEvent]:
        """检测视频中的玩法事件序列"""
        frames = self._extract_frames(video_path, start_time, end_time)

        if not frames:
            return []

        events = []

        if self.merge_detector:
            merge_events = self.merge_detector.detect_events(frames)
            events.extend(merge_events)

        if self.upgrade_detector:
            upgrade_events = self.upgrade_detector.detect_events(frames)
            events.extend(upgrade_events)

        if self.reward_detector:
            reward_events = self.reward_detector.detect_events(frames)
            events.extend(reward_events)

        fps = 30
        for event in events:
            event.start_time = start_time + event.start_time / fps
            event.end_time = start_time + event.end_time / fps

        events.sort(key=lambda e: e.start_time)
        return events

    def _extract_frames(self, video_path: Path, start_time: float,
                        end_time: float) -> List[np.ndarray]:
        """提取视频片段的帧"""
        frames = []
        cap = cv2.VideoCapture(str(video_path))

        if not cap.isOpened():
            return frames

        fps = cap.get(cv2.CAP_PROP_FPS)
        start_frame = int(start_time * fps)
        end_frame = int(end_time * fps)

        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

        frame_count = 0
        sample_interval = max(1, int((end_frame - start_frame) / 50))

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            current_frame = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
            if current_frame > end_frame:
                break

            if frame_count % sample_interval == 0:
                frames.append(frame)

            frame_count += 1

        cap.release()
        return frames

    def _detect_match3(self, frames: List[np.ndarray]) -> float:
        """检测三消游戏"""
        if len(frames) < 5:
            return 0.0

        match3_score = 0.0
        color_count = 0

        for frame in frames:
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

            colors = [
                ((0, 50, 50), (10, 255, 255)),   # red
                ((10, 50, 50), (25, 255, 255)),  # orange
                ((25, 50, 50), (35, 255, 255)),  # yellow
                ((35, 50, 50), (80, 255, 255)),  # green
                ((90, 50, 50), (130, 255, 255)), # blue
                ((130, 50, 50), (170, 255, 255)),# purple
            ]

            found_colors = 0
            for lower, upper in colors:
                mask = cv2.inRange(hsv, lower, upper)
                if np.sum(mask) > frame.size * 0.02:
                    found_colors += 1

            if found_colors >= 3:
                color_count += 1

        if color_count > len(frames) * 0.5:
            match3_score += 0.4

        grid_pattern = self._detect_grid_pattern(frames)
        match3_score += grid_pattern * 0.4

        movement = self._detect_vertical_movement(frames)
        match3_score += movement * 0.2

        return min(1.0, match3_score)

    def _detect_grid_pattern(self, frames: List[np.ndarray]) -> float:
        """检测网格图案"""
        if not frames:
            return 0.0

        frame = frames[len(frames) // 2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        edges = cv2.Canny(gray, 50, 150)

        lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=20,
                               minLineLength=50, maxLineGap=5)

        if lines is None:
            return 0.0

        horizontal = 0
        vertical = 0

        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi

            if -10 <= angle <= 10:
                horizontal += 1
            elif 80 <= angle <= 100:
                vertical += 1

        if horizontal >= 4 and vertical >= 4:
            return 0.8
        elif horizontal >= 3 and vertical >= 3:
            return 0.5
        return 0.0

    def _detect_vertical_movement(self, frames: List[np.ndarray]) -> float:
        """检测垂直移动（三消特征）"""
        if len(frames) < 3:
            return 0.0

        score = 0.0
        for i in range(1, len(frames)):
            flow = cv2.calcOpticalFlowFarneback(
                cv2.cvtColor(frames[i-1], cv2.COLOR_BGR2GRAY),
                cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY),
                None, 0.5, 3, 15, 3, 5, 1.2, 0
            )

            vertical_flow = np.mean(np.abs(flow[..., 1]))
            horizontal_flow = np.mean(np.abs(flow[..., 0]))

            if vertical_flow > horizontal_flow * 1.5:
                score += 1

        return min(1.0, score / (len(frames) - 1))

    def _detect_idle(self, frames: List[np.ndarray]) -> float:
        """检测放置游戏"""
        if len(frames) < 10:
            return 0.0

        motion_scores = []
        for i in range(1, len(frames)):
            diff = cv2.absdiff(
                cv2.cvtColor(frames[i-1], cv2.COLOR_BGR2GRAY),
                cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY)
            )
            motion_scores.append(np.mean(diff))

        avg_motion = np.mean(motion_scores)

        if avg_motion < 5:
            ui_score = self._detect_ui_elements(frames)
            return min(1.0, 0.6 + ui_score * 0.4)
        return 0.0

    def _detect_rpg(self, frames: List[np.ndarray]) -> float:
        """检测RPG游戏"""
        if not frames:
            return 0.0

        score = 0.0

        character_count = 0
        for frame in frames:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            contours, _ = cv2.findContours(
                cv2.Canny(gray, 100, 200),
                cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE
            )

            for contour in contours:
                area = cv2.contourArea(contour)
                if 1000 < area < 10000:
                    character_count += 1
                    break

        if character_count > len(frames) * 0.3:
            score += 0.3

        skill_effects = self._detect_skill_effects(frames)
        score += skill_effects * 0.4

        health_bars = self._detect_health_bars(frames)
        score += health_bars * 0.3

        return min(1.0, score)

    def _detect_ui_elements(self, frames: List[np.ndarray]) -> float:
        """检测UI元素"""
        if not frames:
            return 0.0

        frame = frames[0]
        h, w = frame.shape[:2]

        corner_regions = [
            frame[:h//6, :w//6],
            frame[:h//6, -w//6:],
            frame[-h//6:, :w//6],
            frame[-h//6:, -w//6:],
        ]

        ui_count = 0
        for region in corner_regions:
            gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
            if np.mean(gray) > 200:
                ui_count += 1

        return ui_count / 4

    def _detect_skill_effects(self, frames: List[np.ndarray]) -> float:
        """检测技能特效"""
        if len(frames) < 5:
            return 0.0

        effect_count = 0
        for i in range(1, len(frames)):
            diff = cv2.absdiff(frames[i-1], frames[i])
            high_diff = np.sum(diff > 100)
            if high_diff > diff.size * 0.05:
                effect_count += 1

        return min(1.0, effect_count / (len(frames) - 1))

    def _detect_health_bars(self, frames: List[np.ndarray]) -> float:
        """检测血条"""
        if not frames:
            return 0.0

        frame = frames[len(frames) // 2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        horizontal_lines = 0
        for row in range(gray.shape[0]):
            row_std = np.std(gray[row, :])
            if row_std < 5 and np.mean(gray[row, :]) > 200:
                line_length = 0
                for col in range(gray.shape[1]):
                    if gray[row, col] > 220:
                        line_length += 1
                if line_length > gray.shape[1] * 0.1:
                    horizontal_lines += 1

        return min(1.0, horizontal_lines / 10)

    def _infer_action(self, gameplay_type: str, confidence: float) -> str:
        """基于玩法类型推断动作"""
        action_map = {
            "merge": "merge",
            "drag": "drag",
            "upgrade": "upgrade",
            "match3": "match",
            "idle": "collect",
            "rpg": "battle",
            "puzzle": "solve",
            "strategy": "deploy",
        }
        return action_map.get(gameplay_type, "unknown")

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

    def _count_objects(self, frames: List[np.ndarray]) -> int:
        """计数画面中的对象"""
        if not frames:
            return 0

        frame = frames[len(frames) // 2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        contours, _ = cv2.findContours(
            cv2.Canny(gray, 100, 200),
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        valid_objects = 0
        for contour in contours:
            area = cv2.contourArea(contour)
            if 500 < area < 20000:
                valid_objects += 1

        return valid_objects

    def _extract_trajectory(self, frames: List[np.ndarray]) -> List[Tuple[int, int]]:
        """提取运动轨迹"""
        if len(frames) < 2:
            return []

        trajectory = []

        for i in range(1, min(10, len(frames))):
            flow = cv2.calcOpticalFlowFarneback(
                cv2.cvtColor(frames[i-1], cv2.COLOR_BGR2GRAY),
                cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY),
                None, 0.5, 3, 15, 3, 5, 1.2, 0
            )

            avg_x = int(np.mean(flow[..., 0]))
            avg_y = int(np.mean(flow[..., 1]))
            trajectory.append((avg_x, avg_y))

        return trajectory

    def _fallback_result(self) -> GameplayResult:
        """回退结果"""
        return GameplayResult(
            gameplay_type="unknown",
            confidence=0.0,
            action="unknown",
            clarity=0.0,
            objects_detected=0,
            motion_trajectory=[],
            timestamp=datetime.now().isoformat(),
        )

    def batch_detect(self, video_path: Path,
                     shot_boundaries) -> List[GameplayResult]:
        """批量检测"""
        results = []
        for boundary in shot_boundaries:
            result = self.detect(
                video_path,
                boundary.start_time,
                boundary.end_time
            )
            results.append(result)
        return results

    def save_results(self, results: List[GameplayResult], output_path: Path):
        """保存检测结果"""
        data = {
            "gameplay_results": [{
                "gameplay_type": r.gameplay_type,
                "confidence": r.confidence,
                "action": r.action,
                "clarity": r.clarity,
                "objects_detected": r.objects_detected,
                "motion_trajectory": r.motion_trajectory,
                "timestamp": r.timestamp,
            } for r in results],
            "timestamp": datetime.now().isoformat(),
            "total": len(results),
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)