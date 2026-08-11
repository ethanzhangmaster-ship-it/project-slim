"""Export Manager — 导出管理器

负责：
1. 管理输出目录结构
2. 导出创意视频
3. 生成导出报告
4. 验证输出质量
5. 批量导出管理

输出格式：
- MP4 (H264, 1080x1920, 30fps, 15-30秒)
- JSON 报告
- 字幕文件
"""
import json
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

from .timeline_builder import TimelineBuilder
from .ffmpeg_pipeline import FFmpegPipeline
from .crop_engine import CropEngine
from .subtitle_renderer import SubtitleRenderer
from .audio_mixer import AudioMixer


@dataclass
class ExportResult:
    """导出结果"""
    creative_id: str
    output_path: Path
    success: bool
    duration: Optional[float] = None
    width: int = 0
    height: int = 0
    fps: int = 0
    file_size: int = 0
    error: Optional[str] = None
    timestamp: str = ""


@dataclass
class ExportConfig:
    """导出配置"""
    output_dir: Path = Path("output/v391")
    target_width: int = 1080
    target_height: int = 1920
    target_fps: int = 30
    target_duration_min: float = 15.0
    target_duration_max: float = 30.0
    video_codec: str = "libx264"
    audio_codec: str = "aac"
    crf: int = 18
    preset: str = "fast"
    add_subtitles: bool = True
    add_bgm: bool = True
    normalize_audio: bool = True
    smart_crop: bool = True


class ExportManager:
    """导出管理器"""

    def __init__(self, video_source_dir: Path,
                 config: Optional[ExportConfig] = None):
        self.video_source_dir = video_source_dir
        self.config = config or ExportConfig()
        self.timeline_builder = TimelineBuilder(video_source_dir)
        self.ffmpeg_pipeline = FFmpegPipeline()
        self.crop_engine = CropEngine()
        self.subtitle_renderer = SubtitleRenderer()
        self.audio_mixer = AudioMixer()

    def export_creative(self, timeline,
                        output_path: Optional[Path] = None) -> ExportResult:
        """导出单个创意视频"""
        creative_id = timeline.creative_id

        if not output_path:
            output_path = self.config.output_dir / f"{creative_id}.mp4"

        output_path.parent.mkdir(parents=True, exist_ok=True)

        temp_dir = output_path.parent / f"temp_{creative_id}"
        temp_dir.mkdir(exist_ok=True)

        try:
            step1_output = temp_dir / "step1_raw.mp4"
            step2_output = temp_dir / "step2_cropped.mp4"
            step3_output = temp_dir / "step3_subtitled.mp4"

            result = self.ffmpeg_pipeline.compose_creative(
                self.timeline_builder, timeline, step1_output
            )

            if not result.success:
                return ExportResult(
                    creative_id=creative_id,
                    output_path=output_path,
                    success=False,
                    error=result.error,
                    timestamp=datetime.now().isoformat(),
                )

            print(f"[ExportManager] Step1 exists: {step1_output.exists()}, size: {step1_output.stat().st_size if step1_output.exists() else 0}")

            if self.config.smart_crop:
                crop_ok = self.crop_engine.apply_smart_crop(
                    step1_output, step2_output, "9X16"
                )
                print(f"[ExportManager] Smart crop result: {crop_ok}, step2 exists: {step2_output.exists()}")
                if not crop_ok or not step2_output.exists():
                    shutil.copy(step1_output, step2_output)
            else:
                shutil.copy(step1_output, step2_output)

            print(f"[ExportManager] Step2 exists: {step2_output.exists()}, size: {step2_output.stat().st_size if step2_output.exists() else 0}")

            if self.config.add_subtitles:
                subtitle_path = temp_dir / f"{creative_id}.ass"
                self.subtitle_renderer.generate_timeline_subtitles(
                    timeline, subtitle_path
                )
                burn_ok = self.subtitle_renderer.burn_subtitles(
                    step2_output, subtitle_path, step3_output
                )
                print(f"[ExportManager] Burn subtitles result: {burn_ok}, step3 exists: {step3_output.exists()}")
                if not burn_ok or not step3_output.exists():
                    shutil.copy(step2_output, step3_output)
            else:
                shutil.copy(step2_output, step3_output)

            if self.config.add_bgm:
                self.audio_mixer.add_bgm_by_timeline(
                    step3_output, timeline, output_path
                )
            else:
                shutil.copy(step3_output, output_path)

            if self.config.normalize_audio:
                temp_normalized = temp_dir / "step4_normalized.mp4"
                self.audio_mixer.normalize_audio(output_path, temp_normalized)
                shutil.copy(temp_normalized, output_path)

            video_info = self._get_video_info(output_path)

            shutil.rmtree(temp_dir, ignore_errors=True)

            return ExportResult(
                creative_id=creative_id,
                output_path=output_path,
                success=True,
                duration=video_info.get("duration"),
                width=video_info.get("width", 0),
                height=video_info.get("height", 0),
                fps=video_info.get("fps", 0),
                file_size=output_path.stat().st_size if output_path.exists() else 0,
                timestamp=datetime.now().isoformat(),
            )

        except Exception as e:
            shutil.rmtree(temp_dir, ignore_errors=True)
            return ExportResult(
                creative_id=creative_id,
                output_path=output_path,
                success=False,
                error=str(e),
                timestamp=datetime.now().isoformat(),
            )

    def export_batch(self, timelines) -> List[ExportResult]:
        """批量导出创意视频"""
        results = []
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

        for i, timeline in enumerate(timelines):
            print(f"[ExportManager] Exporting {i+1}/{len(timelines)}: {timeline.creative_id}")
            result = self.export_creative(timeline)
            results.append(result)

            if result.success:
                print(f"  ✓ {result.output_path} ({result.duration:.1f}s)")
            else:
                print(f"  ✗ Failed: {result.error}")

        return results

    def export_ab_test_set(self, baseline_timelines, variant_timelines,
                           output_dir: Optional[Path] = None) -> Dict[str, List[ExportResult]]:
        """导出 A/B 测试数据集"""
        output_dir = output_dir or self.config.output_dir

        baseline_dir = output_dir / "baseline"
        variant_dir = output_dir / "variant"

        baseline_dir.mkdir(parents=True, exist_ok=True)
        variant_dir.mkdir(parents=True, exist_ok=True)

        print("[ExportManager] Exporting baseline set...")
        baseline_results = []
        for i, timeline in enumerate(baseline_timelines):
            timeline.creative_id = f"baseline_{i+1:02d}"
            result = self.export_creative(timeline, baseline_dir / f"{timeline.creative_id}.mp4")
            baseline_results.append(result)

        print("[ExportManager] Exporting variant set...")
        variant_results = []
        for i, timeline in enumerate(variant_timelines):
            timeline.creative_id = f"variant_{i+1:02d}"
            result = self.export_creative(timeline, variant_dir / f"{timeline.creative_id}.mp4")
            variant_results.append(result)

        return {
            "baseline": baseline_results,
            "variant": variant_results,
        }

    def generate_report(self, results: List[ExportResult],
                        output_path: Optional[Path] = None) -> Path:
        """生成导出报告"""
        if not output_path:
            output_path = self.config.output_dir / "export_report.json"

        total = len(results)
        success_count = sum(1 for r in results if r.success)
        total_duration = sum(r.duration for r in results if r.success and r.duration)
        total_size = sum(r.file_size for r in results if r.success)

        report = {
            "version": "V3.9.1",
            "timestamp": datetime.now().isoformat(),
            "config": asdict(self.config),
            "summary": {
                "total_creatives": total,
                "success_count": success_count,
                "failure_count": total - success_count,
                "success_rate": round(success_count / total * 100, 2) if total > 0 else 0,
                "avg_duration": round(total_duration / success_count, 2) if success_count > 0 else 0,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "avg_size_mb": round(total_size / (1024 * 1024 * success_count), 2) if success_count > 0 else 0,
            },
            "creatives": [{
                "creative_id": r.creative_id,
                "output_path": str(r.output_path),
                "success": r.success,
                "duration": r.duration,
                "width": r.width,
                "height": r.height,
                "fps": r.fps,
                "file_size_mb": round(r.file_size / (1024 * 1024), 2),
                "error": r.error,
                "timestamp": r.timestamp,
            } for r in results],
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        return output_path

    def validate_output(self) -> Dict[str, bool]:
        """验证输出视频"""
        results = {}

        for video_file in self.config.output_dir.glob("*.mp4"):
            results[video_file.name] = self.ffmpeg_pipeline.validate_video(video_file)

        return results

    def _get_video_info(self, video_path: Path) -> Dict:
        """获取视频信息"""
        import subprocess

        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "stream=width,height,r_frame_rate",
            "-show_entries", "format=duration,size",
            "-of", "json",
            str(video_path),
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            data = json.loads(result.stdout)

            streams = data.get("streams", [])
            video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})

            r_frame_rate = video_stream.get("r_frame_rate", "30/1")
            num, denom = map(int, r_frame_rate.split("/"))

            return {
                "width": video_stream.get("width", 0),
                "height": video_stream.get("height", 0),
                "fps": int(num / denom),
                "duration": float(data.get("format", {}).get("duration", 0)),
                "size": int(data.get("format", {}).get("size", 0)),
            }
        except Exception:
            return {"width": 0, "height": 0, "fps": 0, "duration": 0, "size": 0}

    def get_output_stats(self) -> Dict:
        """获取输出统计"""
        results = []
        for video_file in self.config.output_dir.glob("*.mp4"):
            info = self._get_video_info(video_file)
            results.append(info)

        if not results:
            return {"total": 0}

        return {
            "total": len(results),
            "avg_width": round(sum(r["width"] for r in results) / len(results)),
            "avg_height": round(sum(r["height"] for r in results) / len(results)),
            "avg_fps": round(sum(r["fps"] for r in results) / len(results)),
            "avg_duration": round(sum(r["duration"] for r in results) / len(results), 2),
            "avg_size_mb": round(sum(r["size"] for r in results) / (1024 * 1024 * len(results)), 2),
        }

    def cleanup_temp_files(self):
        """清理临时文件"""
        for item in self.config.output_dir.iterdir():
            if item.is_dir() and item.name.startswith("temp_"):
                shutil.rmtree(item, ignore_errors=True)

    def prepare_output_structure(self):
        """准备输出目录结构"""
        dirs = [
            self.config.output_dir,
            self.config.output_dir / "baseline",
            self.config.output_dir / "variant",
            self.config.output_dir / "subtitles",
            self.config.output_dir / "audio",
        ]

        for dir_path in dirs:
            dir_path.mkdir(parents=True, exist_ok=True)

        print(f"[ExportManager] Output structure prepared at {self.config.output_dir}")