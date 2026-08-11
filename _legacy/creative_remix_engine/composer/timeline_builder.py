"""Timeline Builder — 时间线构建器

将创意时间线转换为 FFmpeg 可执行的指令序列。

输入：CreativeTimeline（创意时间线）
输出：FFmpeg 命令序列

核心功能：
1. 构建输入文件列表
2. 构建滤镜链
3. 生成 concat 指令
4. 处理转场效果
"""
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

import numpy as np


@dataclass
class FFmpegInput:
    """FFmpeg 输入文件"""
    filepath: Path
    start_time: float
    end_time: float
    duration: float


@dataclass
class FFmpegFilter:
    """FFmpeg 滤镜"""
    name: str
    params: Dict[str, str]
    input_label: Optional[str] = None
    output_label: Optional[str] = None


@dataclass
class FFmpegCommand:
    """FFmpeg 命令"""
    cmd: List[str]
    description: str


class TimelineBuilder:
    """时间线构建器"""

    def __init__(self, video_source_dir: Path):
        self.video_source_dir = video_source_dir

    def build_ffmpeg_inputs(self, timeline_segments) -> List[FFmpegInput]:
        """构建 FFmpeg 输入列表"""
        inputs = []

        for segment in timeline_segments:
            video_file = self.video_source_dir / f"{segment.source_video}.mp4"

            print(f"[TimelineBuilder] Looking for: {video_file} (exists={video_file.exists()})")

            if video_file.exists():
                inputs.append(FFmpegInput(
                    filepath=video_file,
                    start_time=segment.shot_start_time,
                    end_time=segment.shot_end_time,
                    duration=segment.shot_duration,
                ))

        if not inputs:
            print(f"[TimelineBuilder] No valid inputs found. Source dir: {self.video_source_dir}")
            print(f"[TimelineBuilder] Available files: {list(self.video_source_dir.glob('*.mp4'))}")

        return inputs

    def build_filter_complex(self, timeline_segments) -> str:
        """构建滤镜链（P0-4 修复：xfade offset 递推）。

        关键：xfade 的 offset = 当前累计输出时长 - 转场时长 T，
        每次融合后累计时长 = 累计时长 + 本段时长 - T。
        这样无论多少段交叉淡入都有效（旧实现用绝对时间轴位置 - T，
        在第 3 段起就会超出第一段时长而失败）。
        """
        filters = []
        prev_label = None
        prev_audio = None
        input_idx = 0
        target_width, target_height = 1080, 1920

        # 仅保留文件存在的段，并预计算各段时长
        segs = []
        for seg in timeline_segments:
            vf = self.video_source_dir / f"{seg.source_video}.mp4"
            if vf.exists():
                segs.append(seg)
        if not segs:
            return ""
        durs = [float(s.shot_end_time) - float(s.shot_start_time) for s in segs]
        T = min(0.3, (min(durs) / 2.0) if durs else 0.3)

        acc_dur = durs[0]  # 累计输出时长（第一段）

        for i, segment in enumerate(segs):
            label = f"v{i}"

            atrim_start = segment.shot_start_time
            atrim_end = segment.shot_end_time

            filters.append(f"[{input_idx}:v]trim=start={atrim_start}:end={atrim_end},setpts=PTS-STARTPTS[{label}_trim]")
            filters.append(f"[{input_idx}:a]atrim=start={atrim_start}:end={atrim_end},asetpts=PTS-STARTPTS[{label}_audio]")

            filters.append(f"[{label}_trim]scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black[{label}_padded]")

            if prev_label:
                offset = max(0.0, acc_dur - T)
                filters.append(f"[{prev_label}][{label}_padded]xfade=transition=fade:duration={T}:offset={offset:.3f}[{label}]")
                filters.append(f"[{prev_audio}][{label}_audio]acrossfade=d={T:.3f}[{label}_a]")
                prev_audio = f"{label}_a"
                prev_label = label
            else:
                prev_audio = f"{label}_audio"
                prev_label = f"{label}_padded"

            if i >= 1:
                acc_dur = acc_dur + durs[i] - T
            input_idx += 1

        if prev_label:
            filters.append(f"[{prev_label}]format=yuv420p[vout]")
            filters.append(f"[{prev_audio}]aformat=sample_fmts=fltp[aout]")

        return ";".join(filters)

    def build_concat_command(self, timeline, output_path: Path) -> FFmpegCommand:
        """构建 concat 命令"""
        inputs = self.build_ffmpeg_inputs(timeline.segments)

        if not inputs:
            return FFmpegCommand(cmd=[], description="No valid inputs")

        cmd = ["ffmpeg", "-y"]

        for inp in inputs:
            cmd.extend(["-i", str(inp.filepath)])

        filter_complex = self.build_filter_complex(timeline.segments)
        cmd.extend(["-filter_complex", filter_complex])

        cmd.extend(["-map", "[vout]", "-map", "[aout]"])
        cmd.extend(["-c:v", "libx264", "-crf", "18", "-preset", "fast"])
        cmd.extend(["-c:a", "aac", "-b:a", "128k"])
        cmd.extend(["-r", "30"])
        cmd.extend([str(output_path)])

        return FFmpegCommand(
            cmd=cmd,
            description=f"Build creative {timeline.creative_id}"
        )

    def build_single_segment_command(self, segment, output_path: Path,
                                     target_width: int = 1080,
                                     target_height: int = 1920) -> FFmpegCommand:
        """构建单个片段的提取命令"""
        video_file = self.video_source_dir / f"{segment.source_video}.mp4"

        if not video_file.exists():
            return FFmpegCommand(cmd=[], description="Source file not found")

        cmd = [
            "ffmpeg", "-y",
            "-ss", str(segment.shot_start_time),
            "-to", str(segment.shot_end_time),
            "-i", str(video_file),
            "-vf", f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black",
            "-c:v", "libx264", "-crf", "18", "-preset", "fast",
            "-c:a", "aac", "-b:a", "128k",
            "-r", "30",
            str(output_path),
        ]

        return FFmpegCommand(
            cmd=cmd,
            description=f"Extract segment {segment.shot_id}"
        )

    def build_segment_commands(self, timeline, output_dir: Path) -> List[FFmpegCommand]:
        """构建所有片段的提取命令"""
        commands = []

        for segment in timeline.segments:
            output_path = output_dir / f"{segment.shot_id}.mp4"
            cmd = self.build_single_segment_command(segment, output_path)
            if cmd.cmd:
                commands.append(cmd)

        return commands