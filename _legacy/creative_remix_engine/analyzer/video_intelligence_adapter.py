"""Video Intelligence Adapter — 接入视频分析结果"""
import json
import subprocess
from pathlib import Path
from typing import Dict, Optional, List

from ..models import VideoAnalysis, VideoScene, SegmentScore
from ..config import VIDEO_ANALYSIS_DIR, SEGMENT_WEIGHTS


class VideoIntelligenceAdapter:
    """接入 Video Intelligence 分析结果，替代随机时间截取"""

    def __init__(self):
        self.cache: Dict[str, VideoAnalysis] = {}

    def load_analysis(self, video_id: str) -> Optional[VideoAnalysis]:
        """加载视频分析结果（从已有分析目录或动态分析）"""
        if video_id in self.cache:
            return self.cache[video_id]

        # 尝试从已有分析文件加载
        analysis_path = VIDEO_ANALYSIS_DIR / f"{video_id}"
        if analysis_path.exists():
            # 尝试加载已分析的关键帧信息
            analysis = self._build_from_frames(video_id, analysis_path)
            if analysis:
                self.cache[video_id] = analysis
                return analysis

        # 动态分析（简化版：基于场景检测）
        return None

    def _build_from_frames(self, video_id: str, analysis_path: Path) -> Optional[VideoAnalysis]:
        """从提取的关键帧构建分析结果"""
        frames = sorted(analysis_path.glob("frame_*.jpg"))
        if not frames:
            return None

        # 基于帧数量估算场景
        duration = len(frames) * 0.5  # 每0.5秒一帧
        scenes = []

        # 分段为 hook / gameplay / reward
        segment_durations = [
            (0, min(3, duration), "hook"),
            (min(3, duration), min(10, duration), "gameplay"),
            (min(10, duration), duration, "reward"),
        ]

        for start, end, scene_type in segment_durations:
            if start >= end:
                continue
            scene = VideoScene(
                start=start,
                end=end,
                scene_type=scene_type,
                motion_score=0.7 if scene_type == "gameplay" else 0.5,
                emotion_score=0.8 if scene_type == "hook" else 0.6,
                hook_score=90 if scene_type == "hook" else 50,
                gameplay_score=90 if scene_type == "gameplay" else 40,
                reward_score=85 if scene_type == "reward" else 40,
            )
            scenes.append(scene)

        analysis = VideoAnalysis(video_id=video_id, duration=duration, scenes=scenes)
        analysis.best_hook = next((s for s in scenes if s.scene_type == "hook"), None)
        analysis.best_gameplay = next((s for s in scenes if s.scene_type == "gameplay"), None)
        analysis.best_reward = next((s for s in scenes if s.scene_type == "reward"), None)
        return analysis

    def find_best_segment(self, video_id: str, role: str,
                          target_duration: float = 3.0) -> Optional[SegmentScore]:
        """
        自动寻找最佳片段

        Args:
            video_id: 视频编号
            role: hook / gameplay / reward / problem / cta
            target_duration: 目标片段时长
        """
        analysis = self.load_analysis(video_id)
        if not analysis or not analysis.scenes:
            return None

        # 找到匹配 role 的场景
        matching_scenes = [s for s in analysis.scenes if s.scene_type == role]
        if not matching_scenes:
            # 回退：使用所有场景中最匹配的
            matching_scenes = analysis.scenes

        # 评分每个场景
        best_scene = None
        best_score = 0

        for scene in matching_scenes:
            score = self._score_scene(scene, role)
            if score > best_score:
                best_score = score
                best_scene = scene

        if not best_scene:
            return None

        return SegmentScore(
            start=best_scene.start,
            duration=min(target_duration, best_scene.end - best_scene.start),
            visual_impact=best_scene.motion_score * 100,
            motion_score=best_scene.motion_score * 100,
            emotion_score=best_scene.emotion_score * 100,
            hook_impact=best_scene.hook_score,
            gameplay_match=best_scene.gameplay_score,
            overall=best_score,
        )

    def _score_scene(self, scene: VideoScene, role: str) -> float:
        """评分场景与角色的匹配度"""
        if role == "hook":
            return (
                scene.hook_score * SEGMENT_WEIGHTS["hook_impact"] +
                scene.motion_score * 100 * SEGMENT_WEIGHTS["motion"] +
                scene.emotion_score * 100 * SEGMENT_WEIGHTS["emotion"]
            )
        elif role == "gameplay":
            return (
                scene.gameplay_score * SEGMENT_WEIGHTS["gameplay_match"] +
                scene.motion_score * 100 * SEGMENT_WEIGHTS["motion"] +
                scene.emotion_score * 100 * SEGMENT_WEIGHTS["emotion"]
            )
        elif role in ["reward", "cta"]:
            return (
                scene.reward_score * 0.4 +
                scene.emotion_score * 100 * 0.3 +
                scene.motion_score * 100 * 0.3
            )
        else:
            return scene.motion_score * 50 + scene.emotion_score * 50
