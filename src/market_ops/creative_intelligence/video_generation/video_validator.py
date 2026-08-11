"""Video Validator - 视频技术验证器

检测生成视频是否可用：
- resolution / fps / duration / codec
- frame corruption
- file integrity
"""
from __future__ import annotations

import os
from typing import Any

from .models import VideoValidation


class VideoValidator:
    """视频技术验证器"""

    # 最小要求
    MIN_DURATION: float = 3.0   # 秒
    MIN_WIDTH: int = 480
    MIN_HEIGHT: int = 480
    MIN_FPS: float = 6.0

    def __init__(self):
        pass

    def validate(self, video_path: str) -> VideoValidation:
        """验证视频文件

        Returns:
            VideoValidation
        """
        result = VideoValidation()

        if not os.path.exists(video_path):
            result.issues.append(f"文件不存在: {video_path}")
            return result

        result.file_size = os.path.getsize(video_path)
        if result.file_size < 1024:
            result.issues.append(f"文件过小: {result.file_size} bytes")
            return result

        # 尝试用 cv2 分析
        try:
            import cv2
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                result.issues.append("无法打开视频文件")
                return result

            result.width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            result.height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            result.fps = cap.get(cv2.CAP_PROP_FPS)
            result.frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            if result.fps > 0:
                result.duration = result.frame_count / result.fps

            result.resolution = f"{result.width}x{result.height}"
            result.codec = self._detect_codec(cap)

            # 检查帧损坏
            corrupted = self._check_frame_corruption(cap, max_check=30)
            if corrupted > 0:
                result.issues.append(f"检测到 {corrupted} 帧损坏")

            cap.release()

        except ImportError:
            result.issues.append("cv2 未安装，仅做基础文件检查")
        except Exception as e:
            result.issues.append(f"验证异常: {e}")

        # 判定是否通过
        result.valid = self._judge(result)
        return result

    def _detect_codec(self, cap: Any) -> str:
        """检测视频编码"""
        try:
            fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
            return "".join(chr((fourcc >> (8 * i)) & 0xFF) for i in range(4))
        except Exception:
            return "unknown"

    def _check_frame_corruption(self, cap: Any, max_check: int = 30) -> int:
        """检查帧是否损坏"""
        corrupted = 0
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        check_frames = min(total, max_check)

        for i in range(check_frames):
            ret, frame = cap.read()
            if not ret:
                corrupted += 1
                continue
            if frame is None or frame.size == 0:
                corrupted += 1
                continue
            # 检查是否全黑或全白
            if frame.mean() < 1.0 or frame.mean() > 254.0:
                corrupted += 1

        # 重置位置
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        return corrupted

    def _judge(self, result: VideoValidation) -> bool:
        """综合判定视频是否可用"""
        if result.issues:
            return False
        if result.duration < self.MIN_DURATION:
            return False
        if result.width < self.MIN_WIDTH or result.height < self.MIN_HEIGHT:
            return False
        if result.fps < self.MIN_FPS:
            return False
        if result.frame_count < 10:
            return False
        return True
