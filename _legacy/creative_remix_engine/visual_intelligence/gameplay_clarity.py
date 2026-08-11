"""Gameplay Clarity — 单独建模玩法清晰度

评分维度：
- Drag Action（拖动动作）
- Merge Action（合成动作）
- Upgrade（升级）
- Before/After（前后对比）
- Reward Result（奖励结果）

输出 gameplay_score 0-100
"""
import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict


class GameplayClarityAnalyzer:
    """玩法清晰度分析器"""

    def analyze(self, frame_paths: List[Path], video_name: str = "") -> Dict:
        """分析视频的玩法清晰度"""
        valid = [p for p in frame_paths if p.exists()]
        if not valid:
            return self._empty_result()

        # 1. 拖动动作检测（帧间位移方向一致性）
        drag_score = self._detect_drag(valid)

        # 2. 合成动作检测（物体数量变化 + 中心合并）
        merge_score = self._detect_merge(valid)

        # 3. 升级检测（物体尺寸增长 + 闪光）
        upgrade_score = self._detect_upgrade(valid)

        # 4. 前后对比（亮度/颜色/尺寸变化幅度）
        before_after_score = self._detect_before_after(valid)

        # 5. 奖励结果（末尾帧的高亮/大物体）
        reward_result_score = self._detect_reward_result(valid)

        # 文件名信号
        name_bonus = self._name_bonus(video_name)

        # 综合：merge 权重最高（P04 核心玩法），drag 其次
        gameplay_score = (
            merge_score * 0.30 +
            drag_score * 0.25 +
            upgrade_score * 0.20 +
            before_after_score * 0.15 +
            reward_result_score * 0.10 +
            name_bonus * 0.10
        )

        return {
            "gameplay_score": round(min(100, gameplay_score), 1),
            "merge_score": round(merge_score, 1),
            "drag_score": round(drag_score, 1),
            "upgrade_score": round(upgrade_score, 1),
            "before_after_score": round(before_after_score, 1),
            "reward_result_score": round(reward_result_score, 1),
            "name_bonus": name_bonus,
        }

    def _detect_drag(self, frames: List[Path]) -> float:
        """检测拖动动作：物体沿某方向持续移动"""
        if len(frames) < 3:
            return 30

        motions = []
        for i in range(len(frames) - 1):
            f1 = cv2.imread(str(frames[i]), cv2.IMREAD_GRAYSCALE)
            f2 = cv2.imread(str(frames[i + 1]), cv2.IMREAD_GRAYSCALE)
            if f1 is None or f2 is None:
                continue
            h, w = min(f1.shape[0], f2.shape[0]), min(f1.shape[1], f2.shape[1])
            f1r = cv2.resize(f1, (w, h))
            f2r = cv2.resize(f2, (w, h))

            corners = cv2.goodFeaturesToTrack(f1r, 50, 0.01, 10)
            if corners is not None:
                next_pts, status, _ = cv2.calcOpticalFlowPyrLK(f1r, f2r, corners, None)
                if next_pts is not None and status is not None:
                    good = next_pts[status.flatten() == 1] - corners[status.flatten() == 1]
                    if len(good) > 3:
                        # 方向一致性
                        angles = np.arctan2(good[:, 1], good[:, 0])
                        angle_std = np.std(angles)
                        motion_mag = np.mean(np.linalg.norm(good, axis=1))
                        # 方向一致 + 有运动量 = 拖动
                        dragness = min(100, motion_mag * 5 + (30 - angle_std) * 2)
                        motions.append(dragness)

        return np.mean(motions) if motions else 30

    def _detect_merge(self, frames: List[Path]) -> float:
        """检测合成动作：两个物体靠近 + 合并成一个"""
        if len(frames) < 3:
            return 30

        # 简化：检测物体数量变化（多 → 少）
        object_counts = []
        for fp in frames:
            img = cv2.imread(str(fp))
            if img is None or img.size < 100:
                continue
            h, w = img.shape[:2]
            if h < 10 or w < 10:
                continue
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            # 过滤小噪声
            valid_contours = [c for c in contours if cv2.contourArea(c) > 100]
            object_counts.append(len(valid_contours))

        if len(object_counts) < 2:
            return 30

        # 合并模式：前期物体多，后期变少但单个变大
        early = np.mean(object_counts[:len(object_counts)//2])
        late = np.mean(object_counts[len(object_counts)//2:])
        if early > late and early > 3:
            return min(100, (early - late) * 15 + 40)
        return 30

    def _detect_upgrade(self, frames: List[Path]) -> float:
        """检测升级：物体尺寸增长 + 亮度提升"""
        if len(frames) < 2:
            return 30

        sizes = []
        brightnesses = []
        for fp in frames:
            img = cv2.imread(str(fp))
            if img is None:
                continue
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                max_area = max(cv2.contourArea(c) for c in contours)
                sizes.append(max_area)
            brightnesses.append(gray.mean())

        if len(sizes) < 2:
            return 30

        size_growth = (sizes[-1] - sizes[0]) / max(sizes[0], 1)
        bright_growth = (brightnesses[-1] - brightnesses[0]) / max(brightnesses[0], 1)

        return min(100, max(0, size_growth * 50 + bright_growth * 30 + 30))

    def _detect_before_after(self, frames: List[Path]) -> float:
        """检测前后对比：首尾帧差异大"""
        if len(frames) < 2:
            return 30

        first = cv2.imread(str(frames[0]), cv2.IMREAD_GRAYSCALE)
        last = cv2.imread(str(frames[-1]), cv2.IMREAD_GRAYSCALE)
        if first is None or last is None:
            return 30

        h, w = min(first.shape[0], last.shape[0]), min(first.shape[1], last.shape[1])
        first_r = cv2.resize(first, (w, h))
        last_r = cv2.resize(last, (w, h))

        diff = cv2.absdiff(first_r, last_r).mean()
        return min(100, diff / 2 + 20)

    def _detect_reward_result(self, frames: List[Path]) -> float:
        """检测奖励结果：末尾帧有高亮/大物体"""
        if not frames:
            return 30

        last = cv2.imread(str(frames[-1]))
        if last is None:
            return 30

        gray = cv2.cvtColor(last, cv2.COLOR_BGR2GRAY)
        h, w = last.shape[:2]

        # 亮度峰值
        _, bright = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        bright_ratio = cv2.countNonZero(bright) / (h * w)

        # 大物体
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        big_obj = 0
        if contours:
            max_area = max(cv2.contourArea(c) for c in contours)
            big_obj = min(100, max_area / (h * w) * 100 * 5)

        return min(100, bright_ratio * 200 + big_obj * 0.5 + 20)

    def _name_bonus(self, name: str) -> float:
        s = name.lower()
        if any(k in s for k in ["wanfa", "玩法", "gameplay", "merge", "play", "hecheng", "drag"]):
            return 35
        if any(k in s for k in ["upgrade", "level", "evol", "合成"]):
            return 25
        return 10

    def _empty_result(self) -> Dict:
        return {
            "gameplay_score": 30.0,
            "merge_score": 30, "drag_score": 30,
            "upgrade_score": 30, "before_after_score": 30,
            "reward_result_score": 30, "name_bonus": 10,
        }
