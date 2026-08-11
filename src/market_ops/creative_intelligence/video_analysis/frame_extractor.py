"""Frame Extractor - 关键帧提取器

自动抽取关键帧：0s, 1s, 2s, 3s, 5s, 8s, 12s, 15s
"""
from __future__ import annotations

import os
from typing import Any

from .models import FrameInfo


class FrameExtractor:
    """关键帧提取器"""

    # 默认提取时间点（秒）
    DEFAULT_TIMES: list[float] = [0.0, 1.0, 2.0, 3.0, 5.0, 8.0, 12.0, 15.0]

    def __init__(self, output_dir: str = ""):
        if not output_dir:
            output_dir = os.path.join(os.getcwd(), "analysis_frames")
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def extract(
        self,
        video_path: str,
        video_id: str = "",
        times: list[float] | None = None,
    ) -> list[FrameInfo]:
        """提取关键帧

        Args:
            video_path: 视频路径
            video_id: 视频ID（用于命名）
            times: 提取时间点列表

        Returns:
            FrameInfo 列表
        """
        if times is None:
            times = list(self.DEFAULT_TIMES)

        frames: list[FrameInfo] = []

        try:
            import cv2
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return frames

            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = total_frames / fps if fps > 0 else 0

            vid = video_id or os.path.splitext(os.path.basename(video_path))[0]

            for i, t in enumerate(times):
                if t > duration and duration > 0:
                    continue

                frame_idx = int(t * fps)
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, frame = cap.read()

                if ret and frame is not None:
                    filename = f"{vid}_frame_{i:03d}_{int(t)}s.jpg"
                    filepath = os.path.join(self.output_dir, filename)
                    cv2.imwrite(filepath, frame)
                    frames.append(FrameInfo(time=t, path=filepath, index=i))

            cap.release()

        except ImportError:
            pass
        except Exception:
            pass

        return frames

    def extract_uniform(
        self,
        video_path: str,
        video_id: str = "",
        count: int = 8,
    ) -> list[FrameInfo]:
        """均匀提取 count 帧"""
        try:
            import cv2
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return []

            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            duration = total_frames / fps if fps > 0 else 0

            if count <= 0:
                count = 8

            step = max(1, total_frames // count)
            frames: list[FrameInfo] = []
            vid = video_id or os.path.splitext(os.path.basename(video_path))[0]

            for i in range(count):
                idx = min(i * step, total_frames - 1)
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                ret, frame = cap.read()
                t = idx / fps if fps > 0 else 0

                if ret and frame is not None:
                    filename = f"{vid}_uniform_{i:03d}_{int(t)}s.jpg"
                    filepath = os.path.join(self.output_dir, filename)
                    cv2.imwrite(filepath, frame)
                    frames.append(FrameInfo(time=t, path=filepath, index=i))

            cap.release()
            return frames

        except Exception:
            return []
