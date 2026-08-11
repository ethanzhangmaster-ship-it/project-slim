"""Crop Engine — 视频裁剪引擎

处理视频比例转换和裁剪。

支持：
- 16:9 → 9:16（竖屏转换）
- 1:1 → 9:16
- 智能裁剪（保留主体）
- 黑边填充

核心算法：
1. 检测主体位置
2. 计算最佳裁剪区域
3. 应用裁剪和缩放
"""
import subprocess
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple

import cv2
import numpy as np


class CropEngine:
    """视频裁剪引擎"""

    RATIO_CONFIG = {
        "9X16": {"width": 1080, "height": 1920, "ratio": 9/16},
        "1X1": {"width": 1080, "height": 1080, "ratio": 1.0},
        "16X9": {"width": 1920, "height": 1080, "ratio": 16/9},
    }

    def __init__(self):
        pass

    def calculate_crop_region(self, frame: np.ndarray,
                              target_ratio: float) -> Tuple[int, int, int, int]:
        """计算最佳裁剪区域"""
        h, w = frame.shape[:2]
        current_ratio = w / h

        if current_ratio > target_ratio:
            new_width = int(h * target_ratio)
            offset_x = self._find_subject_position(frame, axis=1)
            offset_x = max(0, min(w - new_width, offset_x - new_width // 2))
            return (offset_x, 0, new_width, h)
        else:
            new_height = int(w / target_ratio)
            offset_y = self._find_subject_position(frame, axis=0)
            offset_y = max(0, min(h - new_height, offset_y - new_height // 2))
            return (0, offset_y, w, new_height)

    def _find_subject_position(self, frame: np.ndarray, axis: int = 0) -> int:
        """找到主体位置"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)

        if axis == 0:
            projection = np.sum(edges, axis=1)
        else:
            projection = np.sum(edges, axis=0)

        weighted_sum = np.sum(projection * np.arange(len(projection)))
        total_weight = np.sum(projection)

        if total_weight > 0:
            return int(weighted_sum / total_weight)

        return len(projection) // 2

    def apply_crop(self, input_path: Path, output_path: Path,
                   target_ratio: str = "9X16") -> bool:
        """应用裁剪"""
        config = self.RATIO_CONFIG.get(target_ratio, self.RATIO_CONFIG["9X16"])
        target_w, target_h = config["width"], config["height"]

        probe_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "stream=width,height",
            "-of", "json",
            str(input_path),
        ]

        try:
            result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
            data = json.loads(result.stdout)

            streams = data.get("streams", [])
            video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
            input_w = video_stream.get("width", 1920)
            input_h = video_stream.get("height", 1080)
        except Exception:
            input_w, input_h = 1920, 1080

        input_ratio = input_w / input_h
        target_ratio_val = target_w / target_h

        if input_ratio > target_ratio_val:
            scale_w = target_w
            scale_h = int(target_w / input_ratio)
            pad_top = (target_h - scale_h) // 2
            pad_bottom = target_h - scale_h - pad_top

            filter_str = f"scale={scale_w}:{scale_h},pad={target_w}:{target_h}:0:{pad_top}"
        else:
            scale_h = target_h
            scale_w = int(target_h * input_ratio)
            pad_left = (target_w - scale_w) // 2
            pad_right = target_w - scale_w - pad_left

            filter_str = f"scale={scale_w}:{scale_h},pad={target_w}:{target_h}:{pad_left}:0"

        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-vf", filter_str,
            "-c:v", "libx264", "-crf", "18", "-preset", "fast",
            "-c:a", "copy",
            str(output_path),
        ]

        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=120)
            return result.returncode == 0
        except Exception:
            return False

    def apply_smart_crop(self, input_path: Path, output_path: Path,
                         target_ratio: str = "9X16") -> bool:
        """应用智能裁剪（检测主体）"""
        config = self.RATIO_CONFIG.get(target_ratio, self.RATIO_CONFIG["9X16"])
        target_w, target_h = config["width"], config["height"]

        cap = cv2.VideoCapture(str(input_path))
        if not cap.isOpened():
            return self.apply_crop(input_path, output_path, target_ratio)

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        sample_frame = None
        for i in range(0, total_frames, max(1, total_frames // 10)):
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ret, frame = cap.read()
            if ret:
                sample_frame = frame
                break

        cap.release()

        if sample_frame is None:
            return self.apply_crop(input_path, output_path, target_ratio)

        offset_x, offset_y, crop_w, crop_h = self.calculate_crop_region(
            sample_frame, config["ratio"]
        )

        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-filter:v", f"crop={crop_w}:{crop_h}:{offset_x}:{offset_y},scale={target_w}:{target_h}",
            "-c:v", "libx264", "-crf", "18", "-preset", "fast",
            "-c:a", "copy",
            str(output_path),
        ]

        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=120)
            return result.returncode == 0
        except Exception:
            return False

    def batch_crop(self, input_dir: Path, output_dir: Path,
                   target_ratio: str = "9X16",
                   smart: bool = True) -> Dict[str, bool]:
        """批量裁剪"""
        results = {}
        output_dir.mkdir(parents=True, exist_ok=True)

        for video_file in input_dir.glob("*.mp4"):
            output_path = output_dir / video_file.name

            if smart:
                success = self.apply_smart_crop(video_file, output_path, target_ratio)
            else:
                success = self.apply_crop(video_file, output_path, target_ratio)

            results[video_file.name] = success

        return results