"""FFmpeg Pipeline — FFmpeg 执行管道

负责执行 FFmpeg 命令并处理输出。

核心功能：
1. 执行 FFmpeg 命令
2. 处理进度和错误
3. 验证输出视频
4. 批量处理
"""
import subprocess
import shutil
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class PipelineResult:
    """管道执行结果"""
    success: bool
    output_path: Optional[Path] = None
    duration: Optional[float] = None
    error: Optional[str] = None
    log: Optional[str] = None


class FFmpegPipeline:
    """FFmpeg 执行管道"""

    def __init__(self, ffmpeg_path: str = "ffmpeg"):
        self.ffmpeg_path = ffmpeg_path
        self._check_ffmpeg()

    def _check_ffmpeg(self):
        """检查 FFmpeg 是否可用"""
        try:
            result = subprocess.run(
                [self.ffmpeg_path, "-version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                print("[FFmpegPipeline] Warning: FFmpeg not found")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print("[FFmpegPipeline] Error: FFmpeg not found in PATH")

    def execute(self, cmd: List[str], timeout: int = 120) -> PipelineResult:
        """执行单个 FFmpeg 命令"""
        print(f"[FFmpegPipeline] Executing: {' '.join(cmd)}")
        output_path = Path(cmd[-1]) if cmd else None
        print(f"[FFmpegPipeline] Output path: {output_path}")
        print(f"[FFmpegPipeline] Output parent exists: {output_path.parent.exists() if output_path else False}")

        try:
            if output_path and output_path.parent:
                output_path.parent.mkdir(parents=True, exist_ok=True)

            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout,
            )

            print(f"[FFmpegPipeline] Return code: {result.returncode}")
            if result.returncode != 0:
                print(f"[FFmpegPipeline] FFmpeg error output (first 1000 chars):")
                print(result.stdout[:1000])

            if result.returncode == 0:
                duration = self._get_video_duration(output_path) if output_path else None

                return PipelineResult(
                    success=True,
                    output_path=output_path,
                    duration=duration,
                    log=result.stdout,
                )
            else:
                return PipelineResult(
                    success=False,
                    error=result.stdout[-500:] if len(result.stdout) > 500 else result.stdout,
                    log=result.stdout,
                )

        except subprocess.TimeoutExpired:
            return PipelineResult(
                success=False,
                error="Command timed out",
            )
        except Exception as e:
            print(f"[FFmpegPipeline] Exception: {type(e).__name__}: {e}")
            return PipelineResult(
                success=False,
                error=f"Exception: {type(e).__name__}: {e}",
            )
        except Exception as e:
            return PipelineResult(
                success=False,
                error=str(e),
            )

    def execute_batch(self, commands, output_dir: Path) -> List[PipelineResult]:
        """批量执行命令"""
        results = []

        for cmd in commands:
            if cmd.cmd:
                result = self.execute(cmd.cmd)
                results.append(result)
            else:
                results.append(PipelineResult(
                    success=False,
                    error="Empty command",
                ))

        return results

    def compose_creative(self, timeline_builder, timeline,
                         output_path: Path) -> PipelineResult:
        """合成单个创意视频"""
        cmd = timeline_builder.build_concat_command(timeline, output_path)

        if not cmd.cmd:
            return PipelineResult(
                success=False,
                error="No command generated",
            )

        return self.execute(cmd.cmd)

    def compose_batch(self, timeline_builder, timelines,
                      output_dir: Path) -> Dict[str, PipelineResult]:
        """批量合成创意视频"""
        results = {}

        output_dir.mkdir(parents=True, exist_ok=True)

        for timeline in timelines:
            output_path = output_dir / f"{timeline.creative_id}.mp4"
            result = self.compose_creative(timeline_builder, timeline, output_path)
            results[timeline.creative_id] = result

            if result.success:
                print(f"[FFmpegPipeline] Created: {output_path}")
            else:
                print(f"[FFmpegPipeline] Failed: {timeline.creative_id} - {result.error}")

        return results

    def _get_video_duration(self, video_path: Path) -> Optional[float]:
        """获取视频时长"""
        if not video_path.exists():
            return None

        try:
            cmd = [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "json",
                str(video_path),
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                return float(data.get("format", {}).get("duration", 0))
        except Exception:
            pass

        return None

    def validate_video(self, video_path: Path) -> bool:
        """验证视频是否有效"""
        if not video_path.exists():
            return False

        duration = self._get_video_duration(video_path)
        if duration is None or duration < 0.5:
            return False

        return True

    def validate_batch(self, output_dir: Path) -> Dict[str, bool]:
        """批量验证视频"""
        results = {}

        for video_file in output_dir.glob("*.mp4"):
            results[video_file.stem] = self.validate_video(video_file)

        return results