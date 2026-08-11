"""Creative Remix Composer — 自动剪辑合成引擎

功能：
- Timeline Builder: 构建剪辑时间线
- FFmpeg Editor: 使用 ffmpeg 进行视频编辑
- Transition Engine: 转场效果
- Subtitle Engine: 字幕叠加
- Music Sync: BGM 匹配与同步
- Export: 最终输出

输入：RemixPlan
输出：creative_001.mp4, creative_002.mp4, ...
"""
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

import numpy as np

from .remix_planner import RemixPlan, RemixSegment


@dataclass
class TimelineClip:
    """时间线片段"""
    source_video: Path
    start_time: float
    end_time: float
    duration: float
    role: str
    transition_in: str = "cut"      # cut, fade, dissolve
    transition_out: str = "cut"


@dataclass
class Timeline:
    """剪辑时间线"""
    clips: List[TimelineClip]
    total_duration: float
    target_resolution: tuple = (1080, 1920)  # 9:16
    target_fps: int = 30
    bgm_path: Optional[Path] = None
    subtitle_text: Optional[str] = None


class TimelineBuilder:
    """时间线构建器"""

    def __init__(self, video_source_dir: Path):
        self.video_source_dir = video_source_dir

    def build(self, plan: RemixPlan) -> Timeline:
        """从 RemixPlan 构建时间线"""
        clips = []

        for i, seg in enumerate(plan.segments):
            source_video = self._find_source_video(seg.source_video)

            # 确定转场效果
            transition_in = "fade" if i > 0 else "cut"
            transition_out = "fade" if i < len(plan.segments) - 1 else "cut"

            clip = TimelineClip(
                source_video=source_video,
                start_time=seg.start_time,
                end_time=seg.end_time,
                duration=seg.duration,
                role=seg.role,
                transition_in=transition_in,
                transition_out=transition_out,
            )
            clips.append(clip)

        total_duration = sum(c.duration for c in clips)

        # 生成字幕文本
        subtitle = self._generate_subtitle(plan)

        return Timeline(
            clips=clips,
            total_duration=total_duration,
            subtitle_text=subtitle,
        )

    def _find_source_video(self, source_video_name: str) -> Path:
        """查找源视频文件"""
        # 尝试多种扩展名
        for ext in [".mp4", ".mov", ".avi", ".mkv"]:
            path = self.video_source_dir / f"{source_video_name}{ext}"
            if path.exists():
                return path

        # 返回一个占位路径
        return self.video_source_dir / f"{source_video_name}.mp4"

    def _generate_subtitle(self, plan: RemixPlan) -> str:
        """生成字幕文本"""
        role_texts = {
            "hook": "Amazing!",
            "gameplay": "Play Now!",
            "reward": "Get Reward!",
            "story": "Discover More!",
            "ending": "Download Now!",
        }

        texts = [role_texts.get(seg.role, "") for seg in plan.segments]
        return " | ".join(filter(None, texts))


class FFmpegEditor:
    """FFmpeg 视频编辑器"""

    def __init__(self, ffmpeg_path: str = "ffmpeg"):
        self.ffmpeg = ffmpeg_path

    def extract_segment(self, input_path: Path, output_path: Path,
                        start: float, duration: float,
                        resolution: tuple = (1080, 1920)) -> bool:
        """提取视频片段并裁剪为 9:16"""
        width, height = resolution

        cmd = [
            self.ffmpeg, "-y",
            "-i", str(input_path),
            "-ss", str(start),
            "-t", str(duration),
            "-vf", f"crop={width}:{height},scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-r", "30",
            str(output_path),
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def concat_segments(self, segment_paths: List[Path],
                        output_path: Path,
                        add_fade: bool = True) -> bool:
        """拼接多个片段"""
        if not segment_paths:
            return False

        # 创建 concat list 文件
        list_file = output_path.parent / "concat_list.txt"
        with open(list_file, "w", encoding="utf-8") as f:
            for seg_path in segment_paths:
                f.write(f"file '{seg_path.absolute()}'\n")

        cmd = [
            self.ffmpeg, "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(list_file),
            "-c", "copy",
            str(output_path),
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            list_file.unlink(missing_ok=True)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            list_file.unlink(missing_ok=True)
            return False

    def add_subtitle(self, video_path: Path, output_path: Path,
                     subtitle_text: str,
                     position: str = "bottom") -> bool:
        """添加字幕"""
        y_pos = "h-text_h-50" if position == "bottom" else "50"

        cmd = [
            self.ffmpeg, "-y",
            "-i", str(video_path),
            "-vf", f"drawtext=text='{subtitle_text}':fontsize=48:fontcolor=white:box=1:boxcolor=black@0.5:x=(w-text_w)/2:y={y_pos}",
            "-c:a", "copy",
            str(output_path),
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def add_bgm(self, video_path: Path, output_path: Path,
                bgm_path: Path,
                bgm_volume: float = 0.3) -> bool:
        """添加背景音乐"""
        cmd = [
            self.ffmpeg, "-y",
            "-i", str(video_path),
            "-i", str(bgm_path),
            "-filter_complex", f"[1:a]volume={bgm_volume}[bgm];[0:a][bgm]amix=inputs=2:duration=first",
            "-c:v", "copy",
            str(output_path),
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def speed_adjust(self, video_path: Path, output_path: Path,
                     speed_factor: float = 1.0) -> bool:
        """调整播放速度"""
        if speed_factor == 1.0:
            return True

        cmd = [
            self.ffmpeg, "-y",
            "-i", str(video_path),
            "-filter_complex", f"[0:v]setpts={1/speed_factor}*PTS[v];[0:a]atempo={speed_factor}[a]",
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "fast",
            str(output_path),
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False


class TransitionEngine:
    """转场效果引擎"""

    TRANSITIONS = {
        "cut": {"duration": 0.0, "filter": ""},
        "fade": {"duration": 0.5, "filter": "fade=t=out:st={start}:d=0.5,fade=t=in:st={next_start}:d=0.5"},
        "dissolve": {"duration": 0.8, "filter": "xfade=transition=fade:duration=0.8:offset={start}"},
        "wipe": {"duration": 0.6, "filter": "xfade=transition=wipeleft:duration=0.6:offset={start}"},
    }

    def apply(self, video_paths: List[Path], output_path: Path,
              transitions: List[str]) -> bool:
        """应用转场效果"""
        if len(video_paths) < 2:
            return False

        # 简化实现：使用 xfade 滤镜（ffmpeg 4.4+）
        # 实际实现可能需要更复杂的处理
        inputs = []
        for path in video_paths:
            inputs.extend(["-i", str(path)])

        # 构建 filter_complex
        filter_parts = []
        for i in range(len(video_paths) - 1):
            trans = transitions[i] if i < len(transitions) else "fade"
            trans_config = self.TRANSITIONS.get(trans, self.TRANSITIONS["fade"])
            # 简化：直接拼接

        # 使用 concat 作为基线
        cmd = ["ffmpeg", "-y"] + inputs + [
            "-filter_complex", f"concat=n={len(video_paths)}:v=1:a=1",
            "-c:v", "libx264", "-preset", "fast",
            str(output_path),
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False


class CreativeRemixComposer:
    """Creative Remix 合成器（主控类）"""

    def __init__(self,
                 video_source_dir: Path,
                 output_dir: Path,
                 bgm_dir: Optional[Path] = None):
        self.video_source_dir = video_source_dir
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.bgm_dir = bgm_dir

        self.timeline_builder = TimelineBuilder(video_source_dir)
        self.ffmpeg = FFmpegEditor()
        self.transition = TransitionEngine()

    def compose(self, plan: RemixPlan,
                creative_id: Optional[str] = None) -> Optional[Path]:
        """合成单个创意视频"""
        creative_id = creative_id or plan.creative_id
        print(f"  [Composer] Composing {creative_id}...")

        # Step 1: 构建时间线
        timeline = self.timeline_builder.build(plan)

        # Step 2: 提取并裁剪每个片段
        temp_segments = []
        temp_dir = self.output_dir / "temp"
        temp_dir.mkdir(exist_ok=True)

        for i, clip in enumerate(timeline.clips):
            if not clip.source_video.exists():
                print(f"    Warning: Source video not found: {clip.source_video}")
                continue

            temp_path = temp_dir / f"{creative_id}_seg_{i:03d}.mp4"
            success = self.ffmpeg.extract_segment(
                clip.source_video,
                temp_path,
                clip.start_time,
                clip.duration,
            )
            if success:
                temp_segments.append(temp_path)

        if not temp_segments:
            print(f"    Error: No segments extracted for {creative_id}")
            return None

        # Step 3: 拼接片段
        concat_path = temp_dir / f"{creative_id}_concat.mp4"
        success = self.ffmpeg.concat_segments(temp_segments, concat_path)
        if not success:
            print(f"    Error: Failed to concat segments")
            return None

        # Step 4: 添加字幕
        final_path = self.output_dir / f"{creative_id}.mp4"
        if timeline.subtitle_text:
            subtitle_path = temp_dir / f"{creative_id}_sub.mp4"
            success = self.ffmpeg.add_subtitle(concat_path, subtitle_path, timeline.subtitle_text)
            if success:
                concat_path = subtitle_path

        # Step 5: 添加 BGM
        if self.bgm_dir and self.bgm_dir.exists():
            bgm_files = list(self.bgm_dir.glob("*.mp3"))
            if bgm_files:
                bgm_path = np.random.choice(bgm_files)
                bgm_output = temp_dir / f"{creative_id}_bgm.mp4"
                success = self.ffmpeg.add_bgm(concat_path, bgm_output, bgm_path)
                if success:
                    concat_path = bgm_output

        # Step 6: 复制到最终位置
        try:
            import shutil
            shutil.copy2(concat_path, final_path)
        except (shutil.Error, OSError):
            final_path = concat_path

        print(f"    Output: {final_path}")
        return final_path

    def compose_batch(self, plans: List[RemixPlan],
                      max_workers: int = 4) -> Dict[str, Path]:
        """批量合成"""
        results = {}

        for plan in plans:
            output = self.compose(plan)
            if output:
                results[plan.creative_id] = output

        return results

    def generate_composition_report(self, results: Dict[str, Path]) -> dict:
        """生成合成报告"""
        return {
            "total_planned": len(results),
            "successful": len([p for p in results.values() if p]),
            "failed": len([p for p in results.values() if not p]),
            "outputs": {k: str(v) for k, v in results.items() if v},
            "timestamp": datetime.now().isoformat(),
        }

    def cleanup_temp(self):
        """清理临时文件"""
        temp_dir = self.output_dir / "temp"
        if temp_dir.exists():
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)