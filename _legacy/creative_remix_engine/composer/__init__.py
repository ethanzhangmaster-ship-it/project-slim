"""Composer Module — Real FFmpeg Video Composition

V3.9.1 核心模块：
- TimelineBuilder: 时间线构建器，生成 FFmpeg 命令
- FFmpegPipeline: FFmpeg 执行管道
- CropEngine: 视频裁剪引擎（智能裁剪）
- SubtitleRenderer: 字幕渲染器（支持 SRT/ASS）
- AudioMixer: 音频混合器（BGM/音效）
- ExportManager: 导出管理器（批量导出/A/B测试）

输出格式：
- MP4 (H264, 1080x1920, 30fps, 15-30秒)
"""
from .timeline_builder import TimelineBuilder, FFmpegInput, FFmpegFilter, FFmpegCommand
from .ffmpeg_pipeline import FFmpegPipeline, PipelineResult
from .crop_engine import CropEngine
from .subtitle_renderer import SubtitleRenderer, SubtitleLine, SubtitleConfig
from .audio_mixer import AudioMixer, AudioTrack, AudioConfig
from .export_manager import ExportManager, ExportResult, ExportConfig

__all__ = [
    "TimelineBuilder",
    "FFmpegInput",
    "FFmpegFilter",
    "FFmpegCommand",
    "FFmpegPipeline",
    "PipelineResult",
    "CropEngine",
    "SubtitleRenderer",
    "SubtitleLine",
    "SubtitleConfig",
    "AudioMixer",
    "AudioTrack",
    "AudioConfig",
    "ExportManager",
    "ExportResult",
    "ExportConfig",
]