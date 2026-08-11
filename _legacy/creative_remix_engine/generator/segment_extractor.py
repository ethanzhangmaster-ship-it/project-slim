"""Segment Extractor — 片段提取"""
from pathlib import Path
import subprocess

from ..models import RemixSegment


class SegmentExtractor:
    """从原始视频提取片段"""

    def extract(self, seg: RemixSegment, out_path: Path, with_audio: bool = True) -> bool:
        """提取单个片段"""
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(seg.start),
            "-i", str(seg.filepath),
            "-t", str(seg.duration),
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        ]
        if with_audio:
            cmd.extend(["-c:a", "aac", "-b:a", "192k"])
        else:
            cmd.append("-an")
        cmd.append(str(out_path))

        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0
