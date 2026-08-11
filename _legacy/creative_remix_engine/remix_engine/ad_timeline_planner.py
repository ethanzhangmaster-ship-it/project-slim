"""Creative Remix Planner V2 — 广告时间线规划器

对比 V3.9：
❌ 简单角色匹配
✅ 广告结构约束 + 真实 Shot 选择

例如生成：
Creative #001
0-3s:   hook shot    → shot_123
3-7s:   gameplay shot → shot_456
7-12s:  reward shot   → shot_789
12-15s: CTA           → shot_999

核心功能：
1. 根据结构模板生成时间线
2. 从 Shot Database 选择最佳 shot
3. 确保多样性和质量
4. 生成可执行的混剪方案
"""
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

import numpy as np


@dataclass
class TimelineSegment:
    """时间线片段"""
    role: str
    start_time: float
    end_time: float
    duration: float
    shot_id: str
    source_video: str
    shot_start_time: float
    shot_end_time: float
    shot_duration: float
    visual_hook: bool
    hook_strength: float
    visual_quality: int
    performance_score: int


@dataclass
class CreativeTimeline:
    """创意时间线"""
    creative_id: str
    template_name: str
    structure_pattern: str
    total_duration: float
    segments: List[TimelineSegment]
    target_ratio: str = "9X16"
    estimated_quality: float = 0.0


class AdTimelinePlanner:
    """广告时间线规划器"""

    RATIO_CONFIG = {
        "9X16": {"width": 1080, "height": 1920},
        "1X1": {"width": 1080, "height": 1080},
        "16X9": {"width": 1920, "height": 1080},
    }

    ROLE_DURATION_RANGES = {
        "hook": (1.5, 4.0),
        "gameplay": (3.0, 10.0),
        "reward": (2.0, 6.0),
        "cta": (1.0, 3.0),
        "story": (2.0, 8.0),
        "ending": (1.0, 4.0),
    }

    def __init__(self, shot_database):
        self.shot_database = shot_database

    def plan_timeline(self, structure_template,
                      target_duration: float = 15.0,
                      target_ratio: str = "9X16") -> CreativeTimeline:
        """规划创意时间线"""
        pattern = structure_template.pattern
        roles = pattern.split("-")

        creative_id = f"creative_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        segment_durations = self._calculate_segment_durations(roles, target_duration)
        segments = self._build_segments(roles, segment_durations, structure_template)

        estimated_quality = self._calculate_estimated_quality(segments)

        return CreativeTimeline(
            creative_id=creative_id,
            template_name=structure_template.name,
            structure_pattern=pattern,
            total_duration=target_duration,
            segments=segments,
            target_ratio=target_ratio,
            estimated_quality=round(estimated_quality, 2),
        )

    def plan_batch_timelines(self, structure_template,
                             count: int = 20,
                             target_duration: float = 15.0,
                             target_ratio: str = "9X16") -> List[CreativeTimeline]:
        """批量规划创意时间线"""
        timelines = []

        for i in range(count):
            timeline = self.plan_timeline(structure_template, target_duration, target_ratio)
            timeline.creative_id = f"creative_{i+1:03d}"
            timelines.append(timeline)

        return timelines

    def _calculate_segment_durations(self, roles: List[str],
                                     total_duration: float) -> List[float]:
        """计算每个片段的时长"""
        weights = {
            "hook": 0.25,
            "gameplay": 0.40,
            "reward": 0.20,
            "cta": 0.10,
            "story": 0.20,
            "ending": 0.10,
        }

        role_weights = [weights.get(r, 0.2) for r in roles]
        total_weight = sum(role_weights)

        durations = []
        cumulative = 0.0

        for i, role in enumerate(roles):
            if i == len(roles) - 1:
                duration = max(total_duration - cumulative, 0.5)
            else:
                duration = (role_weights[i] / total_weight) * total_duration

            min_d, max_d = self.ROLE_DURATION_RANGES.get(role, (0.5, 10.0))
            duration = max(min_d, min(max_d, duration))

            durations.append(round(duration, 2))
            cumulative += duration

        return durations

    def _build_segments(self, roles: List[str], durations: List[float],
                        structure_template) -> List[TimelineSegment]:
        """构建时间线片段"""
        segments = []
        current_time = 0.0

        used_shots = set()

        for i, (role, duration) in enumerate(zip(roles, durations)):
            shot = self._select_shot(role, structure_template, used_shots)

            if shot:
                used_shots.add(shot.shot_id)

                segment = TimelineSegment(
                    role=role,
                    start_time=round(current_time, 2),
                    end_time=round(current_time + duration, 2),
                    duration=duration,
                    shot_id=shot.shot_id,
                    source_video=getattr(shot, 'source_video', ''),
                    shot_start_time=getattr(shot, 'start_time', 0.0),
                    shot_end_time=getattr(shot, 'end_time', duration),
                    shot_duration=getattr(shot, 'duration', duration),
                    visual_hook=getattr(shot, 'visual_hook', False),
                    hook_strength=getattr(shot, 'hook_strength', 0.0),
                    visual_quality=getattr(shot, 'visual_quality', 0),
                    performance_score=getattr(shot, 'performance_score', 0),
                )
            else:
                segment = TimelineSegment(
                    role=role,
                    start_time=round(current_time, 2),
                    end_time=round(current_time + duration, 2),
                    duration=duration,
                    shot_id="missing",
                    source_video="",
                    shot_start_time=0.0,
                    shot_end_time=duration,
                    shot_duration=duration,
                    visual_hook=False,
                    hook_strength=0.0,
                    visual_quality=0,
                    performance_score=0,
                )

            segments.append(segment)
            current_time += duration

        return segments

    def _select_shot(self, role: str, structure_template,
                     used_shots: set) -> Optional:
        """选择最佳 shot"""
        all_shots = list(self.shot_database.shots.values())
        candidates = [c for c in all_shots if c.shot_id not in used_shots]

        if not candidates:
            return None

        if role == "hook":
            candidates.sort(key=lambda s: (-getattr(s, 'hook_strength', 0),
                                          -getattr(s, 'visual_quality', 0)))
        elif role == "gameplay":
            candidates.sort(key=lambda s: (-getattr(s, 'performance_score', 0),
                                          -getattr(s, 'visual_quality', 0)))
        elif role == "reward":
            candidates.sort(key=lambda s: (-getattr(s, 'visual_quality', 0),
                                          -getattr(s, 'performance_score', 0)))
        elif role == "cta":
            candidates.sort(key=lambda s: (-getattr(s, 'visual_quality', 0),
                                          -getattr(s, 'hook_strength', 0)))
        elif role == "problem":
            candidates.sort(key=lambda s: (-getattr(s, 'visual_quality', 0),
                                           -getattr(s, 'hook_strength', 0)))
        elif role == "story":
            candidates.sort(key=lambda s: (-getattr(s, 'visual_quality', 0),
                                           -getattr(s, 'performance_score', 0)))
        elif role == "ending":
            candidates.sort(key=lambda s: (-getattr(s, 'visual_quality', 0),
                                           -getattr(s, 'hook_strength', 0)))
        else:
            candidates.sort(key=lambda s: -getattr(s, 'performance_score', 0))

        return candidates[0]

    def _calculate_estimated_quality(self, segments: List[TimelineSegment]) -> float:
        """计算预估质量"""
        if not segments:
            return 0.0

        total_score = 0.0
        total_weight = 0.0

        for segment in segments:
            weight = {
                "hook": 0.30,
                "gameplay": 0.25,
                "reward": 0.20,
                "cta": 0.10,
                "story": 0.10,
                "ending": 0.05,
            }.get(segment.role, 0.1)

            quality = segment.visual_quality / 100
            performance = segment.performance_score / 100

            if segment.role == "hook":
                hook_bonus = segment.hook_strength / 100
                score = (quality * 0.4 + performance * 0.3 + hook_bonus * 0.3)
            else:
                score = (quality * 0.6 + performance * 0.4)

            total_score += score * weight
            total_weight += weight

        return total_score / total_weight if total_weight > 0 else 0.0

    def save_timeline(self, timeline: CreativeTimeline, output_path: Path):
        """保存时间线"""
        data = {
            "creative_id": timeline.creative_id,
            "template_name": timeline.template_name,
            "structure_pattern": timeline.structure_pattern,
            "total_duration": timeline.total_duration,
            "target_ratio": timeline.target_ratio,
            "estimated_quality": timeline.estimated_quality,
            "segments": [{
                "role": s.role,
                "start_time": s.start_time,
                "end_time": s.end_time,
                "duration": s.duration,
                "shot_id": s.shot_id,
                "source_video": s.source_video,
                "shot_start_time": s.shot_start_time,
                "shot_end_time": s.shot_end_time,
                "shot_duration": s.shot_duration,
                "visual_hook": s.visual_hook,
                "hook_strength": s.hook_strength,
                "visual_quality": s.visual_quality,
                "performance_score": s.performance_score,
            } for s in timeline.segments],
            "timestamp": datetime.now().isoformat(),
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def save_batch_timelines(self, timelines: List[CreativeTimeline],
                            output_dir: Path):
        """批量保存时间线"""
        output_dir.mkdir(parents=True, exist_ok=True)

        for timeline in timelines:
            output_path = output_dir / f"{timeline.creative_id}.json"
            self.save_timeline(timeline, output_path)

        manifest = {
            "version": "V3.9.1",
            "total_creatives": len(timelines),
            "timelines": [t.creative_id for t in timelines],
            "timestamp": datetime.now().isoformat(),
        }

        with open(output_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        print(f"[AdTimelinePlanner] Saved {len(timelines)} timelines to {output_dir}")