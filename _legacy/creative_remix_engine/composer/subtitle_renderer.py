"""Subtitle Renderer — 字幕渲染器

支持：
1. SRT/ASS 字幕生成
2. 内嵌字幕到视频
3. 自定义字体和样式
4. 动态字幕位置
5. 多语言支持

核心功能：
- 根据 Hook/Gameplay/Reward 内容生成字幕
- 控制字幕出现时机和时长
- 支持不同风格（醒目/简洁/动感）
"""
import subprocess
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class SubtitleLine:
    """字幕行"""
    start_time: float
    end_time: float
    text: str
    style: str = "default"
    position: str = "bottom"


@dataclass
class SubtitleConfig:
    """字幕配置"""
    font_name: str = "Arial"
    font_size: int = 36
    font_color: str = "white"
    bg_color: str = "black"
    opacity: float = 0.8
    stroke_color: str = "black"
    stroke_width: int = 2
    shadow: bool = True
    alignment: str = "center"


class SubtitleRenderer:
    """字幕渲染器"""

    STYLE_PRESETS = {
        "hook": {
            "font_size": 44,
            "font_color": "#FFD700",
            "stroke_color": "#000000",
            "stroke_width": 3,
            "shadow": True,
        },
        "gameplay": {
            "font_size": 32,
            "font_color": "#00FF00",
            "stroke_color": "#000000",
            "stroke_width": 2,
            "shadow": True,
        },
        "reward": {
            "font_size": 40,
            "font_color": "#FF69B4",
            "stroke_color": "#000000",
            "stroke_width": 3,
            "shadow": True,
        },
        "cta": {
            "font_size": 48,
            "font_color": "#FF0000",
            "stroke_color": "#FFFFFF",
            "stroke_width": 4,
            "shadow": True,
        },
    }

    def __init__(self, font_path: Optional[Path] = None):
        self.font_path = font_path
        self._check_font()

    def _check_font(self):
        """检查字体文件"""
        if self.font_path and not self.font_path.exists():
            print(f"[SubtitleRenderer] Warning: Font not found at {self.font_path}")
            self.font_path = None

    def generate_srt(self, lines: List[SubtitleLine], output_path: Path):
        """生成 SRT 字幕文件"""
        content = ""
        for i, line in enumerate(lines, 1):
            start = self._format_time(line.start_time)
            end = self._format_time(line.end_time)
            content += f"{i}\n{start} --> {end}\n{line.text}\n\n"

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

    def _format_time(self, seconds: float) -> str:
        """格式化时间为 SRT 格式"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        msecs = int((seconds - int(seconds)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{msecs:03d}"

    def generate_ass(self, lines: List[SubtitleLine], output_path: Path,
                      config: Optional[SubtitleConfig] = None):
        """生成 ASS 字幕文件（更丰富的样式）"""
        config = config or SubtitleConfig()

        header = f"""[Script Info]
Title: Generated Subtitle
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{config.font_name},{config.font_size},&H{self._hex_to_bgr(config.font_color)},&H00FFFFFF,&H{self._hex_to_bgr(config.stroke_color)},&H{self._hex_to_bgr(config.bg_color)},-1,0,0,0,100,100,0,0,1,{config.stroke_width},{1 if config.shadow else 0},{self._get_alignment(config.alignment)},10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

        events = ""
        for line in lines:
            start = self._format_ass_time(line.start_time)
            end = self._format_ass_time(line.end_time)
            style_preset = self.STYLE_PRESETS.get(line.style, {})
            font_size = style_preset.get("font_size", config.font_size)
            events += f"Dialogue: 0,{start},{end},Default,,0,0,0,,{{\\fs{font_size}}}{line.text}\n"

        content = header + events

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

    def _format_ass_time(self, seconds: float) -> str:
        """格式化时间为 ASS 格式"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        centisecs = int((seconds - int(seconds)) * 100)
        return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"

    def _hex_to_bgr(self, hex_color: str) -> str:
        """将十六进制颜色转换为 BGR 格式"""
        hex_color = hex_color.lstrip("#")
        if len(hex_color) == 6:
            b = hex_color[4:6]
            g = hex_color[2:4]
            r = hex_color[0:2]
            return f"00{r}{g}{b}"
        return "00FFFFFF"

    def _get_alignment(self, alignment: str) -> int:
        """获取 ASS 对齐码"""
        align_map = {
            "center": 2,
            "left": 1,
            "right": 3,
            "top": 8,
            "top-center": 5,
            "top-left": 7,
            "top-right": 9,
            "bottom": 2,
            "bottom-left": 1,
            "bottom-right": 3,
        }
        return align_map.get(alignment, 2)

    def burn_subtitles(self, video_path: Path, subtitle_path: Path,
                       output_path: Path,
                       config: Optional[SubtitleConfig] = None) -> bool:
        """将字幕内嵌到视频"""
        config = config or SubtitleConfig()

        font_path = f":fontfile={str(self.font_path)}" if self.font_path else ""

        style_args = [
            f"FontName={config.font_name}",
            f"FontSize={config.font_size}",
            f"PrimaryColour=&H{self._hex_to_bgr(config.font_color)}",
            f"OutlineColour=&H{self._hex_to_bgr(config.stroke_color)}",
            f"BackColour=&H{self._hex_to_bgr(config.bg_color)}",
            f"Outline={config.stroke_width}",
            f"Shadow={1 if config.shadow else 0}",
            f"Alignment={self._get_alignment(config.alignment)}",
            f"MarginV=10",
        ]

        style_str = ":".join(style_args) + font_path

        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vf", f"subtitles={str(subtitle_path)}:force_style='{style_str}'",
            "-c:v", "libx264", "-crf", "18", "-preset", "fast",
            "-c:a", "copy",
            str(output_path),
        ]

        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=120)
            return result.returncode == 0
        except Exception as e:
            print(f"[SubtitleRenderer] Error burning subtitles: {e}")
            return False

    def add_text_overlay(self, video_path: Path, text: str, start_time: float,
                         end_time: float, output_path: Path,
                         style: str = "hook") -> bool:
        """添加简单文字覆盖层"""
        preset = self.STYLE_PRESETS.get(style, self.STYLE_PRESETS["hook"])
        font_size = preset["font_size"]
        font_color = preset["font_color"].lstrip("#")

        duration = end_time - start_time

        drawtext_filter = (
            f"drawtext=text='{text}':fontsize={font_size}:"
            f"fontcolor={font_color}:fontfile={str(self.font_path) if self.font_path else 'Arial'}:"
            f"x=(w-text_w)/2:y=h*0.85:enable='between(t,{start_time},{end_time})'"
            f":borderw=2:bordercolor=black"
        )

        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vf", drawtext_filter,
            "-c:v", "libx264", "-crf", "18", "-preset", "fast",
            "-c:a", "copy",
            str(output_path),
        ]

        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=120)
            return result.returncode == 0
        except Exception as e:
            print(f"[SubtitleRenderer] Error adding text overlay: {e}")
            return False

    def generate_timeline_subtitles(self, timeline, output_path: Path):
        """根据时间线生成字幕"""
        lines = []

        for segment in timeline.segments:
            role = segment.role
            start = segment.start_time
            end = segment.end_time

            if role == "hook":
                lines.append(SubtitleLine(
                    start_time=start,
                    end_time=min(start + 2.0, end),
                    text="AMAZING!",
                    style="hook",
                    position="top",
                ))
            elif role == "gameplay":
                actions = getattr(segment, 'actions', [])
                if actions:
                    text = " ".join(actions).upper()[:20]
                else:
                    text = "PLAY NOW"
                lines.append(SubtitleLine(
                    start_time=start + 0.5,
                    end_time=end - 0.5,
                    text=text,
                    style="gameplay",
                    position="bottom",
                ))
            elif role == "reward":
                lines.append(SubtitleLine(
                    start_time=start,
                    end_time=end,
                    text="EPIC REWARD!",
                    style="reward",
                    position="center",
                ))
            elif role == "cta":
                lines.append(SubtitleLine(
                    start_time=start,
                    end_time=end,
                    text="DOWNLOAD NOW!",
                    style="cta",
                    position="bottom",
                ))

        self.generate_ass(lines, output_path)
        return lines

    def batch_add_subtitles(self, video_paths: List[Path], subtitle_paths: List[Path],
                            output_dir: Path) -> Dict[str, bool]:
        """批量添加字幕"""
        results = {}

        for video_path, subtitle_path in zip(video_paths, subtitle_paths):
            output_path = output_dir / video_path.name
            success = self.burn_subtitles(video_path, subtitle_path, output_path)
            results[video_path.name] = success

        return results