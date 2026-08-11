"""Video Parser - 视频解析器

读取视频基础信息：duration, fps, resolution, codec, frame count
"""
from __future__ import annotations

import os
from typing import Any

from .models import VideoInfo


class VideoParser:
    """视频解析器"""

    MIN_DURATION: float = 3.0
    MIN_WIDTH: int = 480
    MIN_HEIGHT: int = 480
    MIN_FPS: float = 6.0

    def parse(self, video_path: str) -> VideoInfo:
        """解析视频文件

        Returns:
            VideoInfo
        """
        info = VideoInfo()

        if not os.path.exists(video_path):
            info.issues.append(f"文件不存在: {video_path}")
            return info

        info.file_size = os.path.getsize(video_path)
        if info.file_size < 1024:
            info.issues.append(f"文件过小: {info.file_size} bytes")
            return info

        # 尝试 cv2
        try:
            import cv2
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                info.issues.append("无法打开视频文件")
                return info

            info.width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            info.height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            info.fps = cap.get(cv2.CAP_PROP_FPS)
            info.frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            if info.fps > 0:
                info.duration = info.frame_count / info.fps

            info.resolution = f"{info.width}x{info.height}"
            info.codec = self._detect_codec(cap)

            # 验证
            if info.duration < self.MIN_DURATION:
                info.issues.append(f"时长过短: {info.duration:.1f}s < {self.MIN_DURATION}s")
            if info.width < self.MIN_WIDTH or info.height < self.MIN_HEIGHT:
                info.issues.append(f"分辨率过低: {info.resolution}")
            if info.fps < self.MIN_FPS:
                info.issues.append(f"帧率过低: {info.fps:.1f} < {self.MIN_FPS}")
            if info.frame_count < 10:
                info.issues.append(f"帧数过少: {info.frame_count}")

            info.valid = len(info.issues) == 0
            cap.release()

        except ImportError:
            info.issues.append("cv2 未安装")
        except Exception as e:
            info.issues.append(f"解析异常: {e}")

        return info

    def _detect_codec(self, cap: Any) -> str:
        """检测编码格式"""
        try:
            fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
            return "".join(chr((fourcc >> (8 * i)) & 0xFF) for i in range(4))
        except Exception:
            return "unknown"
