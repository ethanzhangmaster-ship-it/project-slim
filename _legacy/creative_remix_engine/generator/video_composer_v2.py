"""Phase 3: AI Video Composer V2 — 动态时间线 + 转场 + 字幕合成

核心能力：
- 动态时间线：基于 Story Beats 的非固定时长
- 转场：hard_cut / zoom_in / impact_hit / flash_white / fade
- 运动效果：zoompan / brightness / fade
- AI 字幕：基于 emotion 的样式（normal / big / urgent / whisper）
- 输出：15s 9:16 MP4
"""
import json
import subprocess
import shutil
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple

from ..config import FFMPEG_PRESET, FFMPEG_CRF, FADE_DURATION


# Windows 常见中文字体候选
FONT_CANDIDATES = [
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
]

SUBTITLE_STYLES = {
    "normal": {"fontsize": 42, "fontcolor": "white", "borderw": 4, "y": "h*0.82"},
    "big":    {"fontsize": 54, "fontcolor": "white", "borderw": 5, "y": "h*0.78"},
    "urgent": {"fontsize": 50, "fontcolor": "yellow", "borderw": 5, "y": "h*0.80"},
    "whisper":{"fontsize": 36, "fontcolor": "0xDDDDDD", "borderw": 3, "y": "h*0.85"},
}


def _find_font() -> Optional[Path]:
    """找到系统中的中文字体文件路径"""
    for f in FONT_CANDIDATES:
        p = Path(f)
        if p.exists():
            return p
    return None


def _get_video_info(path: Path) -> dict:
    try:
        r = subprocess.run([
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,duration",
            "-of", "json", str(path)
        ], capture_output=True, text=True, timeout=10)
        s = json.loads(r.stdout)["streams"][0]
        return {"width": int(s.get("width", 0)), "height": int(s.get("height", 0)),
                "duration": float(s.get("duration", 0) or 0)}
    except Exception:
        return {"width": 0, "height": 0, "duration": 0}


class VideoComposerV2:
    """V2 视频合成引擎"""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._font_src = _find_font()
        self._temp_files: List[Path] = []

    def _build_segment_filter(self, dur: float, transition: str,
                              style: str, text: str,
                              proj_dir: Path, idx: int) -> str:
        """
        构建单个片段的 ffmpeg 视频滤镜。
        所有路径使用相对于 proj_dir 的文件名（避免 Windows 绝对路径中的冒号问题）。
        """
        # 基础 fade
        fade_in = f"fade=t=in:st=0:d={FADE_DURATION}"
        fade_out = f"fade=t=out:st={max(0.1, dur-FADE_DURATION)}:d={FADE_DURATION}"
        effects = [fade_in, fade_out]

        # 转场效果 → 施加在片段开头
        if transition == "zoom_in":
            frames = max(int(dur * 30), 10)
            effects.append(
                f"zoompan=z='min(zoom+0.002,1.25)':d={frames}:s=1080x1920:fps=30"
            )
        elif transition == "impact_hit":
            frames = max(int(dur * 30), 10)
            effects.append(
                f"zoompan=z='if(lte(on,3),1.2,1.0)':d={frames}:s=1080x1920:fps=30"
            )
            effects.append("eq=brightness=0.3:contrast=1.2")
        elif transition == "flash_white":
            effects.append("fade=t=in:st=0:d=0.15:alpha=1")
            effects.append("eq=brightness=0.4:contrast=0.8")
        elif transition == "fade":
            effects.append("fade=t=in:st=0:d=0.4")

        # 字幕样式
        st = SUBTITLE_STYLES.get(style, SUBTITLE_STYLES["normal"])
        textfile = proj_dir / f"_sub_{idx:02d}.txt"
        textfile.write_text(text, encoding="utf-8")
        self._temp_files.append(textfile)

        # 使用相对于 proj_dir 的文件名，避免绝对路径中的冒号
        font_name = "_font.ttf"
        sub_name = f"_sub_{idx:02d}.txt"

        drawtext = (
            f"drawtext=fontfile={font_name}:"
            f"textfile={sub_name}:"
            f"fontsize={st['fontsize']}:fontcolor={st['fontcolor']}:"
            f"borderw={st['borderw']}:bordercolor=black@0.7:"
            f"x=(w-text_w)/2:y={st['y']}"
        )
        effects.append(drawtext)

        return ",".join(effects)

    def _process_segment(self, src: Path, dst: Path,
                         start: float, dur: float,
                         transition: str, style: str, text: str,
                         proj_dir: Path, idx: int) -> bool:
        """处理单个片段：提取 + 效果 + 字幕"""
        vf = self._build_segment_filter(dur, transition, style, text, proj_dir, idx)

        # 复制字体到项目目录，使 drawtext 可以用相对路径找到它
        if self._font_src and self._font_src.exists():
            font_dst = proj_dir / "_font.ttf"
            if not font_dst.exists():
                shutil.copy2(str(self._font_src), str(font_dst))

        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-i", str(src),
            "-t", str(dur),
            "-vf", vf,
            "-c:v", "libx264", "-preset", FFMPEG_PRESET, "-crf", str(FFMPEG_CRF),
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-loglevel", "error",
            str(dst.name)  # 用相对文件名，因为 cwd=proj_dir
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=str(proj_dir))
            if r.returncode == 0 and dst.exists():
                return True
            print(f"      segment filter failed, trying fallback: {r.stderr[-120:]}")
        except subprocess.TimeoutExpired:
            print("      segment timeout")
        except Exception as e:
            print(f"      segment exception: {e}")

        # Fallback: 无特效 + 无字幕
        cmd2 = [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-i", str(src),
            "-t", str(dur),
            "-vf", "fade=t=in:st=0:d=0.25,fade=t=out:st=0.8:d=0.25",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-loglevel", "error",
            str(dst.name)
        ]
        try:
            r = subprocess.run(cmd2, capture_output=True, text=True, timeout=120, cwd=str(proj_dir))
            return r.returncode == 0 and dst.exists()
        except Exception:
            return False

    def _concat_segments(self, segments: List[Path], output_path: Path) -> bool:
        """拼接所有片段"""
        valid = [s for s in segments if s.exists()]
        if not valid:
            return False

        # concat demuxer
        concat_file = output_path.parent / "_concat.txt"
        with open(concat_file, "w", encoding="utf-8") as f:
            for v in valid:
                f.write(f"file '{v.as_posix()}'\n")
        self._temp_files.append(concat_file)

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_file),
            "-c:v", "libx264", "-preset", FFMPEG_PRESET, "-crf", str(FFMPEG_CRF),
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-loglevel", "error",
            str(output_path)
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            ok = r.returncode == 0 and output_path.exists()
            if not ok:
                print(f"      concat error: {r.stderr[-150:]}")
            return ok
        except Exception as e:
            print(f"      concat exception: {e}")
            return False

    def compose(self, plan, shot_map: Dict,
                video_id: str = "v001") -> Tuple[Optional[Path], dict]:
        """
        合成完整视频。
        plan: StoryPlan
        shot_map: {beat_id: [(shot, start, dur), ...]}
        返回: (output_path, report_dict)
        """
        proj_dir = self.output_dir / f"proj_{video_id}"
        proj_dir.mkdir(parents=True, exist_ok=True)

        segment_files = []
        report_segments = []

        for i, beat in enumerate(plan.beats):
            candidates = shot_map.get(beat.beat_id, [])
            if not candidates:
                print(f"    [{video_id}] No shot for beat {beat.beat_id}, skipping")
                continue

            shot, start, dur = candidates[0]
            seg_out = proj_dir / f"seg_{i:02d}_{beat.role}.mp4"

            ok = self._process_segment(
                shot.filepath, seg_out,
                start, dur,
                beat.transition_in, beat.subtitle_style, beat.subtitle,
                proj_dir, i
            )
            if ok:
                segment_files.append(seg_out)
                report_segments.append({
                    "beat_id": beat.beat_id,
                    "role": beat.role,
                    "source": shot.filepath.name,
                    "start": start,
                    "duration": dur,
                    "transition": beat.transition_in,
                    "subtitle": beat.subtitle,
                    "shot_score": round(shot.overall_score, 1),
                })
            else:
                print(f"    [{video_id}] Segment {i} failed")

        if not segment_files:
            return None, {"error": "No segments produced"}

        final_path = self.output_dir / f"{video_id}.mp4"
        ok = self._concat_segments(segment_files, final_path)

        # 清理临时字幕文件
        for tf in self._temp_files:
            if tf.exists():
                tf.unlink(missing_ok=True)
        self._temp_files.clear()

        if not ok or not final_path.exists():
            return None, {"error": "Concat failed"}

        # 质检
        info = _get_video_info(final_path)
        report = {
            "video_id": video_id,
            "story_type": plan.story_type,
            "title": plan.title,
            "dna_match_score": plan.dna_match_score,
            "segments": report_segments,
            "output_path": str(final_path),
            "duration": info["duration"],
            "resolution": f"{info['width']}x{info['height']}",
            "size_mb": round(final_path.stat().st_size / 1024 / 1024, 1),
        }
        return final_path, report
