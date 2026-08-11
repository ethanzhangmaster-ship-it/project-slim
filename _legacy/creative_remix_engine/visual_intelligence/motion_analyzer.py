"""Motion Analyzer — 光流、相机运动、物体运动分析"""
import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict


class MotionAnalyzer:
    """运动分析器"""

    def analyze(self, frame_paths: List[Path]) -> Dict:
        """
        基于连续帧分析运动。
        返回: {motion_score, motion_level, optical_flow, camera_motion, object_motion}
        """
        valid = [p for p in frame_paths if p.exists()]
        if len(valid) < 2:
            return self._empty_result()

        flows = []
        camera_motions = []
        object_motions = []

        for i in range(len(valid) - 1):
            f1 = cv2.imread(str(valid[i]), cv2.IMREAD_GRAYSCALE)
            f2 = cv2.imread(str(valid[i + 1]), cv2.IMREAD_GRAYSCALE)
            if f1 is None or f2 is None:
                continue

            # 统一尺寸
            h, w = min(f1.shape[0], f2.shape[0]), min(f1.shape[1], f2.shape[1])
            f1 = cv2.resize(f1, (w, h))
            f2 = cv2.resize(f2, (w, h))

            # 帧差法估计运动量 (快速)
            diff = cv2.absdiff(f1, f2)
            object_motions.append(np.mean(diff))

            # 光流 (稀疏特征点追踪)
            corners = cv2.goodFeaturesToTrack(f1, maxCorners=80, qualityLevel=0.01, minDistance=10)
            if corners is not None:
                next_pts, status, err = cv2.calcOpticalFlowPyrLK(f1, f2, corners, None,
                                                                  winSize=(15, 15), maxLevel=2)
                if next_pts is not None and status is not None:
                    good_old = corners[status.flatten() == 1]
                    good_new = next_pts[status.flatten() == 1]
                    if len(good_old) > 5:
                        motion_vec = good_new - good_old
                        mags = np.linalg.norm(motion_vec, axis=1)
                        flows.append(np.mean(mags))
                        # 相机运动 = 平均位移
                        camera_motions.append(np.linalg.norm(np.mean(motion_vec, axis=0)))

        avg_flow = np.mean(flows) if flows else 0
        avg_obj = np.mean(object_motions) if object_motions else 0
        avg_cam = np.mean(camera_motions) if camera_motions else 0

        # 归一化到 0-100
        motion_score = min(100, (avg_flow * 2 + avg_obj * 0.5 + avg_cam * 1.5))

        if motion_score < 20:
            level = "LOW"
        elif motion_score < 50:
            level = "MEDIUM"
        else:
            level = "HIGH"

        return {
            "motion_score": round(motion_score, 1),
            "motion_level": level,
            "optical_flow": round(avg_flow, 2),
            "camera_motion": round(avg_cam, 2),
            "object_motion": round(avg_obj, 2),
        }

    def _empty_result(self) -> Dict:
        return {
            "motion_score": 30.0,
            "motion_level": "MEDIUM",
            "optical_flow": 0,
            "camera_motion": 0,
            "object_motion": 0,
        }
