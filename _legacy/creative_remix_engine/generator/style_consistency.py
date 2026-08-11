"""Style Consistency — 风格一致性处理"""
from pathlib import Path
from typing import List
import subprocess


class StyleConsistency:
    """确保拼接视频风格一致"""

    def standardize(self, clip_paths: List[Path], output_dir: Path) -> List[Path]:
        """标准化所有片段的分辨率、FPS、色彩"""
        standardized = []

        for i, clip in enumerate(clip_paths):
            out = output_dir / f"std_{i:02d}_{clip.name}"
            if out.exists():
                standardized.append(out)
                continue

            cmd = [
                "ffmpeg", "-y", "-i", str(clip),
                "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
                "-r", "30",
                "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                "-c:a", "aac", "-b:a", "192k",
                str(out)
            ]
            subprocess.run(cmd, capture_output=True, text=True)
            if out.exists():
                standardized.append(out)
            else:
                standardized.append(clip)

        return standardized
