"""Editor Timeline - 剪辑时间线

把所有镜头组合，生成时间线。

输出：
- timeline.json（统一格式）
- Premiere XML（FCP7 格式）
- DaVinci Resolve XML
- CapCut Draft（JSON）
- After Effects JSON

时间线结构：
- Clip
- Transition
- Music
- Subtitle
- Sound
- Effect
- Duration
"""
from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TimelineClip:
    """时间线片段"""
    clip_id: str
    shot_id: str
    name: str
    start_time: float
    end_time: float
    duration: float
    source: str                  # ai / eagle / unity / winner / manual
    source_path: str
    model: str                   # 视频模型
    transition_in: str = ""
    transition_out: str = ""
    effect: list[str] = field(default_factory=list)
    speed: float = 1.0
    volume: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "clip_id": self.clip_id,
            "shot_id": self.shot_id,
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "source": self.source,
            "source_path": self.source_path,
            "model": self.model,
            "transition_in": self.transition_in,
            "transition_out": self.transition_out,
            "effect": self.effect,
            "speed": self.speed,
            "volume": self.volume,
            "metadata": self.metadata,
        }


@dataclass
class TimelineTrack:
    """时间线轨道"""
    track_id: str
    track_type: str               # video / audio / subtitle / effect
    clips: list[TimelineClip] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "track_id": self.track_id,
            "track_type": self.track_type,
            "clips": [c.to_dict() for c in self.clips],
        }


@dataclass
class EditorTimelineData:
    """剪辑时间线数据"""
    timeline_id: str
    variant_id: str
    total_duration: float
    fps: int
    resolution: str
    aspect_ratio: str
    video_tracks: list[TimelineTrack] = field(default_factory=list)
    audio_tracks: list[TimelineTrack] = field(default_factory=list)
    subtitle_tracks: list[TimelineTrack] = field(default_factory=list)
    music_bed: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timeline_id": self.timeline_id,
            "variant_id": self.variant_id,
            "total_duration": self.total_duration,
            "fps": self.fps,
            "resolution": self.resolution,
            "aspect_ratio": self.aspect_ratio,
            "video_tracks": [t.to_dict() for t in self.video_tracks],
            "audio_tracks": [t.to_dict() for t in self.audio_tracks],
            "subtitle_tracks": [t.to_dict() for t in self.subtitle_tracks],
            "music_bed": self.music_bed,
            "metadata": self.metadata,
        }


class EditorTimeline:
    """剪辑时间线生成器"""

    # 默认分辨率
    ASPECT_TO_RESOLUTION: dict[str, str] = {
        "9:16": "1080x1920",
        "1:1":  "1080x1080",
        "4:5":  "1080x1350",
        "16:9": "1920x1080",
    }

    def __init__(self, fps: int = 30):
        self.fps = fps
        self._aspect_res = dict(self.ASPECT_TO_RESOLUTION)

    # ------------------------------------------------------------------
    # 核心方法
    # ------------------------------------------------------------------
    def build(
        self,
        shot_list: Any,            # ShotList
        plan: Any,                 # ProductionPlan
        strategy: Any,             # CreativeStrategy
        aspect_ratio: str = "9:16",
    ) -> EditorTimelineData:
        """构造时间线

        Args:
            shot_list: 镜头列表
            plan: 生产计划
            strategy: 创意策略
            aspect_ratio: 画幅
        """
        resolution = self._aspect_res.get(aspect_ratio, "1080x1920")

        # 视频轨
        video_track = TimelineTrack(track_id="V1", track_type="video")
        audio_track = TimelineTrack(track_id="A1", track_type="audio")
        subtitle_track = TimelineTrack(track_id="S1", track_type="subtitle")

        # 索引 assignments by shot_id
        assign_map = {a.shot_id: a for a in plan.assignments}

        for shot in shot_list.shots:
            assign = assign_map.get(shot.shot_id)
            source = assign.source if assign else "ai"
            source_path = assign.source_path if assign else ""
            model = assign.model if assign else ""

            # Video clip
            video_clip = TimelineClip(
                clip_id=f"clip_{shot.shot_id}",
                shot_id=shot.shot_id,
                name=shot.name,
                start_time=shot.start_time,
                end_time=shot.end_time,
                duration=shot.duration,
                source=source,
                source_path=source_path,
                model=model,
                transition_in=shot.transition_in,
                transition_out=shot.transition_out,
                effect=list(shot.fx) if hasattr(shot, "fx") else [],
                speed=1.0,
                volume=1.0,
            )
            video_track.clips.append(video_clip)

            # Audio clip（来自 shot.sound_effects）
            if hasattr(shot, "sound_effects") and shot.sound_effects:
                audio_clip = TimelineClip(
                    clip_id=f"audio_{shot.shot_id}",
                    shot_id=shot.shot_id,
                    name=f"SFX-{shot.name}",
                    start_time=shot.start_time,
                    end_time=shot.end_time,
                    duration=shot.duration,
                    source="sfx",
                    source_path=",".join(shot.sound_effects),
                    model="",
                    volume=0.7,
                )
                audio_track.clips.append(audio_clip)

            # Subtitle clip
            if hasattr(shot, "subtitle") and shot.subtitle:
                sub_clip = TimelineClip(
                    clip_id=f"sub_{shot.shot_id}",
                    shot_id=shot.shot_id,
                    name=f"Sub-{shot.name}",
                    start_time=shot.start_time,
                    end_time=shot.end_time,
                    duration=shot.duration,
                    source="subtitle",
                    source_path=shot.subtitle,
                    model="",
                )
                subtitle_track.clips.append(sub_clip)

        return EditorTimelineData(
            timeline_id=f"timeline_{shot_list.variant_id}",
            variant_id=shot_list.variant_id,
            total_duration=shot_list.total_duration,
            fps=self.fps,
            resolution=resolution,
            aspect_ratio=aspect_ratio,
            video_tracks=[video_track],
            audio_tracks=[audio_track] if audio_track.clips else [],
            subtitle_tracks=[subtitle_track] if subtitle_track.clips else [],
            music_bed=self._select_music_bed(strategy),
            metadata={
                "shot_count": shot_list.total_shots,
                "platform": strategy.platform,
            },
        )

    # ------------------------------------------------------------------
    # 导出格式
    # ------------------------------------------------------------------
    def export_premiere_xml(
        self,
        timeline: EditorTimelineData,
        output_path: str,
    ) -> str:
        """导出 Premiere Pro 兼容的 XML（FCP7 风格）"""
        # 根元素
        xmeml = ET.Element("xmeml", version="4")
        sequence = ET.SubElement(xmeml, "sequence")
        ET.SubElement(sequence, "name").text = timeline.timeline_id
        ET.SubElement(sequence, "duration").text = str(int(timeline.total_duration * timeline.fps))
        rate = ET.SubElement(sequence, "rate")
        ET.SubElement(rate, "timebase").text = str(timeline.fps)
        media = ET.SubElement(sequence, "media")
        video = ET.SubElement(media, "video")

        for track in timeline.video_tracks:
            for clip in track.clips:
                clipitem = ET.SubElement(video, "clipitem", id=clip.clip_id)
                ET.SubElement(clipitem, "name").text = clip.name
                ET.SubElement(clipitem, "duration").text = str(int(clip.duration * timeline.fps))
                ET.SubElement(clipitem, "start").text = str(int(clip.start_time * timeline.fps))
                ET.SubElement(clipitem, "end").text = str(int(clip.end_time * timeline.fps))
                ET.SubElement(clipitem, "enabled").text = "TRUE"
                # source path
                file_el = ET.SubElement(clipitem, "file", id=f"file_{clip.clip_id}")
                ET.SubElement(file_el, "name").text = clip.source_path or clip.name
                ET.SubElement(file_el, "pathurl").text = clip.source_path or ""

        tree = ET.ElementTree(xmeml)
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        tree.write(output_path, encoding="utf-8", xml_declaration=True)
        return output_path

    def export_davinci_xml(
        self,
        timeline: EditorTimelineData,
        output_path: str,
    ) -> str:
        """导出 DaVinci Resolve 兼容的 XML（FCP7 风格，DaVinci 同样支持）"""
        # DaVinci 也使用 FCP7 风格 XML
        return self.export_premiere_xml(timeline, output_path)

    def export_capcut_draft(
        self,
        timeline: EditorTimelineData,
        output_path: str,
    ) -> str:
        """导出 CapCut 草稿格式（JSON）"""
        draft = {
            "id": timeline.timeline_id,
            "version": "3.0.0",
            "fps": timeline.fps,
            "duration": int(timeline.total_duration * 1_000_000),  # 微秒
            "width": int(timeline.resolution.split("x")[0]),
            "height": int(timeline.resolution.split("x")[1]),
            "platform": {
                "app_id": "3704",
                "app_source": "lv",
                "app_version": "5.9.0",
            },
            "materials": {
                "videos": [],
                "audios": [],
                "texts": [],
            },
            "tracks": [],
        }

        # 视频轨
        for track in timeline.video_tracks:
            track_data = {
                "id": track.track_id,
                "type": "video",
                "attribute": 0,
                "flag": 0,
                "segments": [],
            }
            for clip in track.tracks if hasattr(track, "tracks") else []:
                pass
            for clip in track.clips:
                seg = {
                    "id": clip.clip_id,
                    "material_id": clip.clip_id,
                    "target_timerange": {
                        "start": int(clip.start_time * 1_000_000),
                        "duration": int(clip.duration * 1_000_000),
                    },
                    "source_timerange": {
                        "start": 0,
                        "duration": int(clip.duration * 1_000_000),
                    },
                    "speed": clip.speed,
                    "volume": clip.volume,
                }
                track_data["segments"].append(seg)
            draft["tracks"].append(track_data)

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(draft, f, ensure_ascii=False, indent=2)
        return output_path

    def export_after_effects_json(
        self,
        timeline: EditorTimelineData,
        output_path: str,
    ) -> str:
        """导出 After Effects JSON"""
        out = {
            "name": timeline.timeline_id,
            "comp": {
                "width": int(timeline.resolution.split("x")[0]),
                "height": int(timeline.resolution.split("x")[1]),
                "frameRate": timeline.fps,
                "duration": timeline.total_duration,
            },
            "layers": [],
        }

        for track in timeline.video_tracks:
            for clip in track.clips:
                layer = {
                    "name": clip.name,
                    "type": "footage",
                    "source": clip.source_path,
                    "inPoint": clip.start_time,
                    "outPoint": clip.end_time,
                    "effects": clip.effect,
                    "transitionIn": clip.transition_in,
                    "transitionOut": clip.transition_out,
                }
                out["layers"].append(layer)

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        return output_path

    def export_all(
        self,
        timeline: EditorTimelineData,
        output_dir: str,
    ) -> dict[str, str]:
        """一次性导出所有格式"""
        os.makedirs(output_dir, exist_ok=True)
        results = {}
        base = f"{timeline.variant_id}"

        # timeline.json
        json_path = os.path.join(output_dir, "timeline.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(timeline.to_dict(), f, ensure_ascii=False, indent=2)
        results["timeline_json"] = json_path

        # Premiere XML
        prem_path = os.path.join(output_dir, f"{base}_premiere.xml")
        self.export_premiere_xml(timeline, prem_path)
        results["premiere_xml"] = prem_path

        # DaVinci XML
        dav_path = os.path.join(output_dir, f"{base}_davinci.xml")
        self.export_davinci_xml(timeline, dav_path)
        results["davinci_xml"] = dav_path

        # CapCut Draft
        cap_path = os.path.join(output_dir, f"{base}_capcut.json")
        self.export_capcut_draft(timeline, cap_path)
        results["capcut_json"] = cap_path

        # After Effects JSON
        ae_path = os.path.join(output_dir, f"{base}_after_effects.json")
        self.export_after_effects_json(timeline, ae_path)
        results["after_effects_json"] = ae_path

        return results

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------
    def _select_music_bed(self, strategy: Any) -> str:
        """根据情绪选 BGM"""
        emotion = getattr(strategy, "emotion", "")
        if "满足" in emotion or "惊喜" in emotion:
            return "music://celebration_uplifting.mp3"
        if "好奇" in emotion or "期待" in emotion:
            return "music://curiosity_playful.mp3"
        if "紧张" in emotion or "挑战" in emotion:
            return "music://tension_rising.mp3"
        if "震撼" in emotion:
            return "music://epic_dramatic.mp3"
        if "温暖" in emotion:
            return "music://warm_ending.mp3"
        return "music://default_uplifting.mp3"
