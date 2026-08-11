"""Frame Sampler — 从视频提取6帧（0%,20%,40%,60%,80%,100%）"""
import subprocess
from pathlib import Path
from typing import List, Optional


class FrameSampler:
    """视频帧采样器，支持缓存"""

    SAMPLE_POINTS = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_video_duration(self, video_path: Path) -> float:
        """获取视频时长"""
        try:
            r = subprocess.run([
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=duration",
                "-of", "json", str(video_path)
            ], capture_output=True, text=True, timeout=10)
            import json
            s = json.loads(r.stdout).get("streams", [{}])[0]
            return float(s.get("duration", 0) or 0)
        except Exception:
            return 0

    def get_frame_dir(self, video_path: Path) -> Path:
        """获取该视频的帧缓存目录"""
        vid = video_path.stem[:50]
        return self.cache_dir / vid

    def is_cached(self, video_path: Path) -> bool:
        """检查是否已缓存"""
        fd = self.get_frame_dir(video_path)
        expected = [fd / f"{i:03d}.jpg" for i in range(len(self.SAMPLE_POINTS))]
        return all(f.exists() for f in expected)

    def sample(self, video_path: Path, force: bool = False) -> List[Path]:
        """
        提取6帧，返回帧文件路径列表。
        如果已缓存且 force=False 则直接返回。
        """
        frame_dir = self.get_frame_dir(video_path)
        if not force and self.is_cached(video_path):
            return [frame_dir / f"{i:03d}.jpg" for i in range(len(self.SAMPLE_POINTS))]

        frame_dir.mkdir(parents=True, exist_ok=True)
        duration = self._get_video_duration(video_path)
        if duration <= 0:
            return []

        frame_paths = []
        for i, ratio in enumerate(self.SAMPLE_POINTS):
            ts = duration * ratio
            if ratio >= 1.0:
                ts = max(0, duration - 0.1)
            out = frame_dir / f"{i:03d}.jpg"
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(ts),
                "-i", str(video_path),
                "-vframes", "1",
                "-q:v", "2",
                "-loglevel", "error",
                str(out)
            ]
            try:
                subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            except Exception:
                pass
            frame_paths.append(out)

        return frame_paths
