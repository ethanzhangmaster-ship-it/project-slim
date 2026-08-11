"""Scorer — Visual Intelligence Ranking Engine 总入口"""
import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from .frame_sampler import FrameSampler
from .motion_analyzer import MotionAnalyzer
from .visual_impact import VisualImpactAnalyzer
from .gameplay_detector import GameplayDetector
from .hook_predictor import HookPredictor
from .reward_predictor import RewardPredictor
from .shot_ranker import ShotRanker
from .ranking_database import RankingDatabase


class VisualIntelligenceScorer:
    """视觉智能评分引擎总入口"""

    def __init__(self,
                 cache_dir: Path,
                 db_path: Path,
                 video_source_dir: Path):
        self.cache_dir = cache_dir
        self.video_source_dir = video_source_dir
        self.db = RankingDatabase(db_path)

        self.sampler = FrameSampler(cache_dir / "frames")
        self.motion = MotionAnalyzer()
        self.impact = VisualImpactAnalyzer()
        self.gameplay = GameplayDetector()
        self.hook = HookPredictor()
        self.reward = RewardPredictor()
        self.ranker = ShotRanker()

    def analyze_video(self, video_path: Path, force: bool = False) -> Dict:
        """
        对单个视频进行全量视觉分析。
        如果数据库中已有结果且 force=False，则直接返回缓存。
        """
        name = video_path.stem
        if not force and self.db.exists(name):
            cached = self.db.get(name)
            if cached and all(k in cached for k in ["motion_score", "impact_score", "gameplay_score", "hook_score", "reward_score"]):
                return cached

        # 1. 帧采样
        frames = self.sampler.sample(video_path)
        if not frames or not any(f.exists() for f in frames):
            return self._fallback_scores(name)

        # 2. 各项分析
        motion_result = self.motion.analyze(frames)
        impact_result = self.impact.analyze(frames)
        gameplay_result = self.gameplay.analyze(frames, name)
        hook_result = self.hook.analyze(frames, name)
        reward_result = self.reward.analyze(frames, name)

        result = {
            "video_name": name,
            "video_path": str(video_path),
            "motion_score": motion_result["motion_score"],
            "motion_level": motion_result["motion_level"],
            "impact_score": impact_result["impact_score"],
            "gameplay_score": gameplay_result["gameplay_score"],
            "gameplay_type": gameplay_result["gameplay_type"],
            "hook_score": hook_result["hook_score"],
            "reward_score": reward_result["reward_score"],
            "reward_types": reward_result["reward_types"],
            "analyzed_at": datetime.now().isoformat(),
        }

        # 3. 存入数据库
        self.db.upsert(name, result)
        return result

    def analyze_all(self, video_paths: Optional[List[Path]] = None,
                    force: bool = False) -> List[Dict]:
        """
        批量分析全部视频。
        支持增量更新。
        """
        if video_paths is None:
            video_paths = sorted(self.video_source_dir.glob("*.mp4"))

        import sys
        if not force:
            unprocessed = self.db.get_unprocessed(video_paths)
            print(f"[Scorer] Total: {len(video_paths)} | Already analyzed: {len(video_paths) - len(unprocessed)} | New: {len(unprocessed)}", flush=True)
            to_process = unprocessed
        else:
            print(f"[Scorer] Force re-analyzing all {len(video_paths)} videos", flush=True)
            to_process = video_paths

        results = []
        errors = []
        for i, vp in enumerate(to_process):
            if i % 20 == 0:
                print(f"  [{i}/{len(to_process)}] Analyzing {vp.name[:40]}...", flush=True)
            try:
                result = self.analyze_video(vp, force=False)
                results.append(result)
            except Exception as e:
                print(f"  ERROR on {vp.name}: {e}", flush=True)
                errors.append((vp.name, str(e)))
                results.append(self._fallback_scores(vp.stem))
            if i % 50 == 49:
                self.db.save()
                print(f"  [{i+1}/{len(to_process)}] Checkpoint saved", flush=True)

        # 保存数据库
        self.db.save()
        print(f"[Scorer] Analysis complete. Total in DB: {len(self.db.get_all())} | Errors: {len(errors)}", flush=True)
        if errors:
            print(f"  Error videos: {[e[0] for e in errors[:5]]}", flush=True)
        return results

    def build_rankings(self) -> Dict:
        """基于数据库构建全部排行榜"""
        all_data = self.db.get_all()
        self.ranker.rankings.clear()

        for item in all_data:
            vp = Path(item.get("video_path", ""))
            if not vp.exists():
                continue
            self.ranker.add_shot(vp, item)

        return self.ranker.get_ranking_dict()

    def _fallback_scores(self, name: str) -> Dict:
        """无法分析时的回退评分"""
        return {
            "video_name": name,
            "motion_score": 30.0, "impact_score": 35.0,
            "gameplay_score": 30.0, "gameplay_type": "unknown",
            "hook_score": 25.0, "reward_score": 20.0,
            "reward_types": ["unknown"],
            "analyzed_at": datetime.now().isoformat(),
        }
