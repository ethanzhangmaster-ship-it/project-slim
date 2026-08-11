"""Scorer V2 — Visual Intelligence Ranking Engine 总入口 (V3.6.1)

升级点：
- Role Classifier V2（多标签）
- Hook Predictor V2（Subject + Novelty + Emotion）
- Gameplay Clarity 单独建模
- Beat-specific Ranking 权重
- Ad Value Score + 买量指标预测
"""
import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from .frame_sampler import FrameSampler
from .motion_analyzer import MotionAnalyzer
from .visual_impact import VisualImpactAnalyzer
from .gameplay_detector import GameplayDetector
from .hook_predictor_v2 import HookPredictorV2
from .reward_predictor import RewardPredictor
from .role_classifier_v2 import RoleClassifierV2
from .gameplay_clarity import GameplayClarityAnalyzer
from .shot_ranker import ShotRanker
from .ranking_database import RankingDatabase
from .feedback_memory import FeedbackMemory


class VisualIntelligenceScorerV2:
    """V2 视觉智能评分引擎"""

    def __init__(self,
                 cache_dir: Path,
                 db_path: Path,
                 video_source_dir: Path,
                 feedback_path: Optional[Path] = None):
        self.cache_dir = cache_dir
        self.video_source_dir = video_source_dir
        self.db = RankingDatabase(db_path)

        self.sampler = FrameSampler(cache_dir / "frames")
        self.motion = MotionAnalyzer()
        self.impact = VisualImpactAnalyzer()
        self.gameplay = GameplayDetector()
        self.hook_v2 = HookPredictorV2()
        self.reward = RewardPredictor()
        self.role_classifier = RoleClassifierV2()
        self.gameplay_clarity = GameplayClarityAnalyzer()
        self.ranker = ShotRanker()

        # Feedback memory
        if feedback_path is None:
            feedback_path = db_path.parent / "feedback_memory.json"
        self.feedback = FeedbackMemory(feedback_path)

    def analyze_video(self, video_path: Path, force: bool = False) -> Dict:
        """对单个视频进行全量视觉分析（V3.6.1 升级版）"""
        name = video_path.stem
        if not force and self.db.exists(name):
            cached = self.db.get(name)
            if cached and all(k in cached for k in ["motion_score", "impact_score", "hook_score_v2", "gameplay_clarity"]):
                return cached

        frames = self.sampler.sample(video_path)
        if not frames or not any(f.exists() for f in frames):
            return self._fallback_scores(name)

        # 并行分析各项（带错误回退）
        try:
            motion_result = self.motion.analyze(frames)
        except Exception:
            motion_result = {"motion_score": 30, "motion_level": "MEDIUM", "optical_flow": 0, "camera_motion": 0, "object_motion": 0}
        try:
            impact_result = self.impact.analyze(frames)
        except Exception:
            impact_result = {"impact_score": 35, "contrast": 40, "brightness": 50, "saturation": 40, "sharpness": 30, "color_diversity": 35, "subject_size": 25, "foreground_ratio": 30}
        try:
            gameplay_result = self.gameplay.analyze(frames, name)
        except Exception:
            gameplay_result = {"gameplay_score": 30, "gameplay_type": "unknown", "gameplay_types": [], "grid_score": 0, "ui_score": 0, "motion_continuous": 0}
        try:
            hook_v2_result = self.hook_v2.analyze(frames, name)
        except Exception:
            hook_v2_result = {"hook_score": 30, "visual_impact": 30, "motion": 25, "subject_size": 20, "novelty": 20, "emotion": 30, "name_bonus": 10}
        try:
            reward_result = self.reward.analyze(frames, name)
        except Exception:
            reward_result = {"reward_score": 20, "reward_types": ["unknown"], "flash_score": 0, "particle_score": 0, "big_object_score": 0, "brightness_peak": 0, "name_score": 20}
        try:
            role_scores = self.role_classifier.classify(name, frames)
        except Exception:
            role_scores = {}
        try:
            gameplay_clarity_result = self.gameplay_clarity.analyze(frames, name)
        except Exception:
            gameplay_clarity_result = {"gameplay_score": 30, "merge_score": 30, "drag_score": 30, "upgrade_score": 30, "before_after_score": 30, "reward_result_score": 30, "name_bonus": 10}

        # Ad Value Score 计算
        ad_value = self._calc_ad_value(
            hook_v2_result["hook_score"],
            motion_result["motion_score"],
            gameplay_clarity_result["gameplay_score"],
            reward_result["reward_score"],
            impact_result["impact_score"],
        )

        # 买量指标预测
        ctr, cvr, purchase_intent = self._predict_ad_metrics(ad_value)

        result = {
            "video_name": name,
            "video_path": str(video_path),
            "motion_score": motion_result["motion_score"],
            "motion_level": motion_result["motion_level"],
            "impact_score": impact_result["impact_score"],
            "gameplay_score": gameplay_result["gameplay_score"],
            "gameplay_type": gameplay_result["gameplay_type"],
            "hook_score_v2": hook_v2_result["hook_score"],
            "hook_breakdown": {k: v for k, v in hook_v2_result.items() if k != "hook_score"},
            "reward_score": reward_result["reward_score"],
            "reward_types": reward_result["reward_types"],
            "gameplay_clarity": gameplay_clarity_result["gameplay_score"],
            "gameplay_clarity_breakdown": {k: v for k, v in gameplay_clarity_result.items() if k != "gameplay_score"},
            "role_scores": role_scores,
            "top_roles": self.role_classifier.get_top_roles(role_scores),
            "ad_value_score": ad_value,
            "predicted_ctr": ctr,
            "predicted_cvr": cvr,
            "purchase_intent": purchase_intent,
            "analyzed_at": datetime.now().isoformat(),
        }

        self.db.upsert(name, result)
        return result

    def _calc_ad_value(self, hook: float, motion: float,
                       gameplay: float, reward: float, impact: float) -> float:
        """Ad Value Score = Hook×35% + Retention(proxy=motion)×25% + Gameplay×20% + Reward×15% + CTA(proxy=impact)×5%"""
        return round(
            hook * 0.35 +
            motion * 0.25 +
            gameplay * 0.20 +
            reward * 0.15 +
            impact * 0.05,
            1
        )

    def _predict_ad_metrics(self, ad_value: float) -> tuple:
        """基于 Ad Value 预测买量指标"""
        # 简化线性映射
        ctr = round(min(5.0, max(0.5, ad_value / 20)), 2)
        cvr = round(min(15.0, max(1.0, ad_value / 8)), 2)
        purchase_intent = round(min(80, max(10, ad_value * 0.8)), 1)
        return ctr, cvr, purchase_intent

    def analyze_all(self, video_paths: Optional[List[Path]] = None,
                    force: bool = False) -> List[Dict]:
        if video_paths is None:
            video_paths = sorted(self.video_source_dir.glob("*.mp4"))

        import sys
        if not force:
            unprocessed = self.db.get_unprocessed(video_paths)
            print(f"[ScorerV2] Total: {len(video_paths)} | Cached: {len(video_paths) - len(unprocessed)} | New: {len(unprocessed)}", flush=True)
            to_process = unprocessed
        else:
            print(f"[ScorerV2] Force re-analyzing all {len(video_paths)} videos", flush=True)
            to_process = video_paths

        results = []
        errors = []
        for i, vp in enumerate(to_process):
            if i % 20 == 0:
                print(f"  [{i}/{len(to_process)}] {vp.name[:40]}...", flush=True)
            try:
                result = self.analyze_video(vp, force=False)
                results.append(result)
            except Exception as e:
                print(f"  ERROR: {vp.name}: {e}", flush=True)
                errors.append((vp.name, str(e)))
                results.append(self._fallback_scores(vp.stem))
            if i % 50 == 49:
                self.db.save()

        self.db.save()
        print(f"[ScorerV2] Done. DB={len(self.db.get_all())} | Errors={len(errors)}", flush=True)
        return results

    def build_rankings(self) -> Dict:
        all_data = self.db.get_all()
        self.ranker.rankings.clear()
        for item in all_data:
            vp = Path(item.get("video_path", ""))
            if not vp.exists():
                continue
            self.ranker.add_shot(vp, item)
        return self.ranker.get_ranking_dict()

    def _fallback_scores(self, name: str) -> Dict:
        return {
            "video_name": name,
            "motion_score": 30.0, "impact_score": 35.0,
            "gameplay_score": 30.0, "gameplay_type": "unknown",
            "hook_score_v2": 30.0, "reward_score": 20.0,
            "gameplay_clarity": 30.0,
            "role_scores": {}, "top_roles": [],
            "ad_value_score": 28.0,
            "predicted_ctr": 1.5, "predicted_cvr": 3.5, "purchase_intent": 22.0,
            "analyzed_at": datetime.now().isoformat(),
        }
