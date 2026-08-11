"""Color Normalizer — 色彩标准化"""
from pathlib import Path
import subprocess


class ColorNormalizer:
    """统一视频色彩风格"""

    def normalize(self, input_path: Path, output_path: Path,
                  brightness: float = 0.0, contrast: float = 1.0, saturation: float = 1.0):
        """标准化视频色彩"""
        cmd = [
            "ffmpeg", "-y", "-i", str(input_path),
            "-vf", f"eq=brightness={brightness}:contrast={contrast}:saturation={saturation}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "copy",
            str(output_path)
        ]
        subprocess.run(cmd, capture_output=True, text=True)
        return output_path.exists()
