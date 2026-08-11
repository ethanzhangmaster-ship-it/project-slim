"""Key Frame Extractor — ffmpeg-based multi-frame extraction.

Extracts frames at configurable time positions (default: 5%, 25%, 50%, 75%, 95%).
Avoids logo/black-screen/loading frames by spreading extraction across video.
Supports disk cache with corrupt-file detection.
"""
import subprocess
from pathlib import Path
from typing import List, Optional
from PIL import Image


class KeyFrameExtractor:
    """Extract key frames from video using ffmpeg seek."""

    def __init__(self, config):
        kf = config.get("keyframe", default={})
        self.positions = kf.get("positions", [0.05, 0.25, 0.50, 0.75, 0.95])

    def extract(self, filepath: str, vid: str, cache_dir: Path) -> List[Image.Image]:
        """Extract key frames. Returns list of PIL Images."""
        frames = []
        dur = self._get_duration(filepath)
        if dur <= 0:
            return frames

        for pct in self.positions:
            cache_path = cache_dir / f"kf_{vid}_{int(pct * 100):02d}.jpg"

            # Try cache first — skip corrupt files
            if cache_path.exists():
                if cache_path.stat().st_size > 1024:
                    try:
                        frames.append(Image.open(cache_path))
                        continue
                    except Exception:
                        cache_path.unlink(missing_ok=True)
                else:
                    cache_path.unlink(missing_ok=True)

            # Extract via ffmpeg
            ss = dur * pct
            try:
                r = subprocess.run(
                    ["ffmpeg", "-ss", str(ss), "-i", filepath,
                     "-vframes", "1", "-q:v", "2", str(cache_path)],
                    capture_output=True, timeout=30,
                )
                if r.returncode == 0 and cache_path.exists() and cache_path.stat().st_size > 1024:
                    frames.append(Image.open(cache_path))
                    continue

                # Fallback: seek after -i (slower but more compatible)
                r2 = subprocess.run(
                    ["ffmpeg", "-i", filepath, "-ss", str(ss),
                     "-vframes", "1", "-q:v", "2", str(cache_path)],
                    capture_output=True, timeout=30,
                )
                if r2.returncode == 0 and cache_path.exists() and cache_path.stat().st_size > 1024:
                    frames.append(Image.open(cache_path))
            except (subprocess.TimeoutExpired, Exception):
                pass

        return frames

    def _get_duration(self, filepath: str) -> float:
        try:
            r = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries",
                 "format=duration", "-of",
                 "default=noprint_wrappers=1:nokey=1", filepath],
                capture_output=True, text=True, timeout=15,
            )
            if r.returncode == 0 and r.stdout.strip():
                return float(r.stdout.strip())
        except Exception:
            pass
        return 0
