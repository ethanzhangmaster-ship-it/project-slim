"""Scene Detector — 场景检测"""
import subprocess
from pathlib import Path
from typing import List


class SceneDetector:
    """检测视频中的场景切换"""

    def detect(self, video_path: Path, threshold: float = 0.3) -> List[float]:
        """返回场景切换时间点列表"""
        result = subprocess.run([
            "ffmpeg", "-i", str(video_path),
            "-filter:v", f"select='gt(scene,{threshold})',showinfo",
            "-f", "null", "-"
        ], capture_output=True, text=True)

        scenes = []
        for line in result.stderr.split("\n"):
            if "pts_time:" in line:
                try:
                    time_str = line.split("pts_time:")[1].split(" ")[0]
                    scenes.append(float(time_str))
                except:
                    pass
        return scenes
