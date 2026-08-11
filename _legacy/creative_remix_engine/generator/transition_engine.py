"""Transition Engine — 转场效果"""
from pathlib import Path
import subprocess


class TransitionEngine:
    """视频转场处理"""

    FADE = "fade"
    DISSOLVE = "dissolve"

    @staticmethod
    def apply_fade(clip_path: Path, duration: float, fade_in: float = 0.3, fade_out: float = 0.3) -> Path:
        """给片段添加 fade 转场"""
        out_path = clip_path.parent / f"{clip_path.stem}_fade{clip_path.suffix}"
        vf = f"fade=t=in:st=0:d={fade_in},fade=t=out:st={duration-fade_out}:d={fade_out}"

        cmd = [
            "ffmpeg", "-y", "-i", str(clip_path),
            "-vf", vf,
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "copy",
            str(out_path)
        ]
        subprocess.run(cmd, capture_output=True, text=True)
        return out_path
