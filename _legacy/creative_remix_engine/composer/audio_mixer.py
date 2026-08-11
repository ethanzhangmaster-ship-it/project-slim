"""Audio Mixer — 音频混合器

支持：
1. 背景音乐混合
2. 音效添加
3. 音频淡入淡出
4. 音量平衡
5. 多轨道混合

核心功能：
- 为创意视频添加合适的 BGM
- 根据片段类型调整音频
- 确保音频和视频同步
"""
import subprocess
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class AudioTrack:
    """音轨"""
    filepath: Path
    start_time: float = 0.0
    duration: Optional[float] = None
    volume: float = 1.0
    fade_in: float = 0.0
    fade_out: float = 0.0
    loop: bool = False


@dataclass
class AudioConfig:
    """音频配置"""
    bgm_volume: float = 0.3
    sfx_volume: float = 0.7
    voice_volume: float = 1.0
    crossfade_duration: float = 0.5
    normalize_audio: bool = True


class AudioMixer:
    """音频混合器"""

    BGM_PRESETS = {
        "hook": {
            "genre": "epic",
            "tempo": "fast",
            "volume": 0.4,
        },
        "gameplay": {
            "genre": "electronic",
            "tempo": "medium",
            "volume": 0.3,
        },
        "reward": {
            "genre": "uplifting",
            "tempo": "fast",
            "volume": 0.5,
        },
        "cta": {
            "genre": "urgent",
            "tempo": "fast",
            "volume": 0.4,
        },
    }

    def __init__(self, bgm_dir: Optional[Path] = None, sfx_dir: Optional[Path] = None):
        self.bgm_dir = bgm_dir
        self.sfx_dir = sfx_dir

    def _get_video_duration(self, video_path: Path) -> Optional[float]:
        """获取视频时长"""
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            str(video_path),
        ]

        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=30)
            data = json.loads(result.stdout)
            return float(data.get("format", {}).get("duration", 0))
        except Exception:
            return None

    def add_bgm(self, video_path: Path, bgm_path: Path, output_path: Path,
                config: Optional[AudioConfig] = None) -> bool:
        """为视频添加背景音乐"""
        config = config or AudioConfig()

        video_duration = self._get_video_duration(video_path)
        if not video_duration:
            return False

        bgm_duration = self._get_video_duration(bgm_path) or 180

        if bgm_duration < video_duration:
            loop_count = int(video_duration / bgm_duration) + 1
            loop_filter = f"apad=pad_dur={video_duration}"
        else:
            loop_count = 1
            loop_filter = f"atrim=end={video_duration}"

        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(bgm_path),
            "-filter_complex", (
                f"[1:a]{loop_filter},volume={config.bgm_volume}[bgm];"
                f"[0:a]volume={1.0}[video_audio];"
                f"[video_audio][bgm]amix=inputs=2:duration=first[aout]"
            ),
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "128k",
            str(output_path),
        ]

        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=120)
            return result.returncode == 0
        except Exception as e:
            print(f"[AudioMixer] Error adding BGM: {e}")
            return False

    def add_fade(self, video_path: Path, output_path: Path,
                 fade_in_duration: float = 0.5,
                 fade_out_duration: float = 0.5) -> bool:
        """添加音频淡入淡出"""
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-af", f"afade=t=in:st=0:d={fade_in_duration},afade=t=out:st=end-{fade_out_duration}:d={fade_out_duration}",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "128k",
            str(output_path),
        ]

        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=120)
            return result.returncode == 0
        except Exception as e:
            print(f"[AudioMixer] Error adding fade: {e}")
            return False

    def adjust_volume(self, video_path: Path, output_path: Path,
                     volume: float = 1.0) -> bool:
        """调整音量"""
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-af", f"volume={volume}",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "128k",
            str(output_path),
        ]

        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=120)
            return result.returncode == 0
        except Exception as e:
            print(f"[AudioMixer] Error adjusting volume: {e}")
            return False

    def normalize_audio(self, video_path: Path, output_path: Path,
                        target_level: float = -16.0) -> bool:
        """音频归一化"""
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-af", f"loudnorm=I={target_level}:LRA=11:TP=-1.5",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "128k",
            str(output_path),
        ]

        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=120)
            return result.returncode == 0
        except Exception as e:
            print(f"[AudioMixer] Error normalizing audio: {e}")
            return False

    def mix_multiple_tracks(self, video_path: Path, tracks: List[AudioTrack],
                            output_path: Path) -> bool:
        """混合多个音轨"""
        if not tracks:
            return False

        video_duration = self._get_video_duration(video_path) or 30

        inputs = ["-i", str(video_path)]
        filter_complex_parts = []
        audio_maps = ["[0:a]"]

        for i, track in enumerate(tracks):
            inputs.extend(["-i", str(track.filepath)])
            track_idx = i + 1

            volume_filter = f"volume={track.volume}" if track.volume != 1.0 else ""
            fade_filters = []

            if track.fade_in > 0:
                fade_filters.append(f"afade=t=in:d={track.fade_in}")
            if track.fade_out > 0:
                fade_filters.append(f"afade=t=out:d={track.fade_out}:st={track.duration - track.fade_out if track.duration else video_duration - track.fade_out}")

            filter_parts = []
            if track.start_time > 0:
                filter_parts.append(f"adelay={track.start_time * 1000}")
            if volume_filter:
                filter_parts.append(volume_filter)
            if fade_filters:
                filter_parts.extend(fade_filters)

            if filter_parts:
                filter_complex_parts.append(f"[{track_idx}:a]{','.join(filter_parts)}[track{i}]")
                audio_maps.append(f"[track{i}]")
            else:
                audio_maps.append(f"[{track_idx}:a]")

        if filter_complex_parts:
            filter_complex = ";".join(filter_complex_parts)
            filter_complex += f";{'[0:a]' if filter_complex else '[0:a]'}"
        else:
            filter_complex = ""

        mix_inputs = len(audio_maps)
        if mix_inputs > 1:
            mix_filter = f"amix=inputs={mix_inputs}:duration=first[aout]"
            if filter_complex:
                filter_complex += ";" + ":".join(audio_maps) + f";{mix_filter}"
            else:
                filter_complex = ":".join(audio_maps) + f";{mix_filter}"

        cmd = ["ffmpeg", "-y"] + inputs

        if filter_complex:
            cmd.extend(["-filter_complex", filter_complex])
            cmd.extend(["-map", "0:v", "-map", "[aout]"])
        else:
            cmd.extend(["-map", "0:v", "-map", "0:a"])

        cmd.extend(["-c:v", "copy", "-c:a", "aac", "-b:a", "128k"])
        cmd.append(str(output_path))

        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=120)
            return result.returncode == 0
        except Exception as e:
            print(f"[AudioMixer] Error mixing tracks: {e}")
            return False

    def select_bgm_for_role(self, role: str) -> Optional[Path]:
        """根据角色选择合适的 BGM"""
        if not self.bgm_dir or not self.bgm_dir.exists():
            return None

        preset = self.BGM_PRESETS.get(role, self.BGM_PRESETS["gameplay"])
        genre = preset["genre"]

        for bgm_file in self.bgm_dir.glob("*.mp3"):
            if genre.lower() in bgm_file.name.lower():
                return bgm_file

        for bgm_file in self.bgm_dir.glob("*.mp3"):
            return bgm_file

        return None

    def add_bgm_by_timeline(self, video_path: Path, timeline, output_path: Path,
                             config: Optional[AudioConfig] = None) -> bool:
        """根据时间线添加 BGM"""
        config = config or AudioConfig()

        bgm_path = self.select_bgm_for_role(timeline.segments[0].role if timeline.segments else "gameplay")
        if not bgm_path:
            return False

        return self.add_bgm(video_path, bgm_path, output_path, config)

    def batch_add_audio(self, video_paths: List[Path], output_dir: Path,
                        config: Optional[AudioConfig] = None) -> Dict[str, bool]:
        """批量添加音频处理"""
        results = {}

        for video_path in video_paths:
            output_path = output_dir / video_path.name

            success = True
            temp_path = output_dir / f"temp_{video_path.name}"

            if config and config.normalize_audio:
                success = success and self.normalize_audio(video_path, temp_path)

            if success:
                success = success and self.add_fade(temp_path, output_path)

            results[video_path.name] = success

        return results