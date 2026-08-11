"""Video Quality Checker — 视频质量检查"""
import subprocess
from pathlib import Path

from ..models import QAResult, RemixRecipe


class VideoQualityChecker:
    """自动检查视频技术质量"""

    def check(self, recipe: RemixRecipe, video_path: Path) -> QAResult:
        """检查生成的视频"""
        result = QAResult(creative_id=recipe.recipe_id)

        if not video_path.exists():
            result.passed = False
            result.issues.append("视频文件不存在")
            return result

        # 检查黑屏
        if self._is_black_screen(video_path):
            result.passed = False
            result.issues.append("检测到黑屏")

        # 检查音频
        if not self._has_audio(video_path):
            result.warnings.append("无音频轨道")

        # 检查时长
        actual_dur = self._get_duration(video_path)
        if actual_dur < 1:
            result.passed = False
            result.issues.append(f"视频时长异常: {actual_dur:.1f}s")
        elif abs(actual_dur - recipe.total_duration) > 3:
            result.warnings.append(f"时长偏差: 预期{recipe.total_duration:.1f}s, 实际{actual_dur:.1f}s")

        # 检查比例
        ratio_ok = self._check_ratio(video_path, recipe.target_ratio)
        if not ratio_ok:
            result.issues.append(f"比例不符合: 预期{recipe.target_ratio}")

        return result

    def _is_black_screen(self, path: Path) -> bool:
        """检测是否黑屏"""
        try:
            result = subprocess.run([
                "ffmpeg", "-i", str(path),
                "-vf", "blackdetect=d=0.5:pix_th=0.1",
                "-an", "-f", "null", "-"
            ], capture_output=True, text=True)
            return "blackdetect" in result.stderr and "black_start" in result.stderr
        except:
            return False

    def _has_audio(self, path: Path) -> bool:
        """检查是否有音频"""
        try:
            result = subprocess.run([
                "ffprobe", "-v", "error",
                "-select_streams", "a",
                "-show_entries", "stream=codec_type",
                "-of", "csv=p=0",
                str(path)
            ], capture_output=True, text=True)
            return "audio" in result.stdout
        except:
            return False

    def _get_duration(self, path: Path) -> float:
        """获取视频时长"""
        try:
            result = subprocess.run([
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(path)
            ], capture_output=True, text=True)
            return float(result.stdout.strip())
        except:
            return 0

    def _check_ratio(self, path: Path, target_ratio: str) -> bool:
        """检查画面比例"""
        try:
            result = subprocess.run([
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "csv=s=x:p=0",
                str(path)
            ], capture_output=True, text=True)
            w, h = result.stdout.strip().split("x")
            r = int(w) / int(h)
            if target_ratio == "9X16":
                return r < 0.7
            elif target_ratio == "1X1":
                return 0.7 <= r <= 1.3
            elif target_ratio == "16X9":
                return r > 1.3
            return True
        except:
            return False
