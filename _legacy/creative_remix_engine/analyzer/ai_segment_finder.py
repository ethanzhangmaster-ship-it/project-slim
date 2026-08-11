"""AI Segment Finder V2 — 基于多维度评分的片段查找"""
from typing import Dict, List, Optional, Tuple
from pathlib import Path

from ..models import SegmentScore, VideoAnalysis
from ..analyzer.video_intelligence_engine import VideoIntelligenceEngine
from ..analyzer.emotion_analyzer import EmotionAnalyzer
from ..utils import get_video_info


class AISegmentFinder:
    """V2: 真实AI评分寻找最佳片段"""

    def __init__(self):
        self.vi_engine = VideoIntelligenceEngine()
        self.emotion_analyzer = EmotionAnalyzer()

    def find_best_segments(self, video_id: str, video_path: Path,
                           target_roles: List[str] = None) -> Dict[str, SegmentScore]:
        """
        为视频找到各角色的最佳片段
        返回: {role: SegmentScore}
        """
        analysis = self.vi_engine.analyze(video_id, video_path)
        if not analysis or not analysis.scenes:
            return {}

        target_roles = target_roles or ["hook", "gameplay", "reward"]
        results = {}

        for role in target_roles:
            best = self._find_best_for_role(analysis, role, video_path)
            if best:
                results[role] = best

        return results

    def _find_best_for_role(self, analysis: VideoAnalysis, role: str,
                            video_path: Path) -> Optional[SegmentScore]:
        """为特定角色找最佳片段"""
        matching_scenes = [s for s in analysis.scenes if s.scene_type == role]
        if not matching_scenes:
            return None

        best_scene = None
        best_score = 0

        for scene in matching_scenes:
            # V2 评分公式
            emotions = self.emotion_analyzer.analyze(video_path, role)
            dominant_emo = self.emotion_analyzer.dominant_emotion(emotions)
            emotion_val = emotions.get(dominant_emo, 0.5)

            score = (
                scene.hook_score * 0.30 +          # Visual Impact 30%
                scene.motion_score * 100 * 0.25 +   # Motion 25%
                emotion_val * 100 * 0.20 +          # Emotion 20%
                scene.gameplay_score * 0.15 +       # Gameplay Clarity 15%
                50 * 0.10                           # Historical baseline 10%
            )

            if score > best_score:
                best_score = score
                best_scene = scene

        if not best_scene:
            return None

        return SegmentScore(
            start=best_scene.start,
            duration=min(best_scene.end - best_scene.start, 5.0),
            visual_impact=best_scene.hook_score if role == "hook" else best_scene.gameplay_score,
            motion_score=best_scene.motion_score * 100,
            emotion_score=emotions.get(self.emotion_analyzer.dominant_emotion(
                self.emotion_analyzer.analyze(video_path, role)), 50),
            hook_impact=best_scene.hook_score if role == "hook" else 0,
            gameplay_match=best_scene.gameplay_score if role == "gameplay" else 0,
            overall=best_score,
        )

    def get_top_segments(self, video_index: Dict, role: str,
                         top_n: int = 50) -> List[Tuple[str, SegmentScore]]:
        """从所有视频中获取某角色的TOP N片段"""
        all_scores = []

        for v_num, asset in video_index.items():
            segs = self.find_best_segments(v_num, asset.filepath, [role])
            if role in segs:
                all_scores.append((v_num, segs[role]))

        all_scores.sort(key=lambda x: -x[1].overall)
        return all_scores[:top_n]
