"""Hook Miner — 从全部素材中挖掘适合做 Hook 的视频

不是只看文件名，而是基于 Visual Intelligence 评分：
- hook_score_v2 > 50
- visual_impact > 50
- subject_size > 50
- novelty > 30
- 前3秒有强视觉冲击

目标：从 599 素材中挖掘 100+ 潜在 Hook
"""
import json
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class HookCandidate:
    video_name: str
    video_path: str
    hook_score: float
    impact_score: float
    subject_size: float
    novelty: float
    emotion: float
    reason: str
    rank: int = 0


class HookMiner:
    """Hook 素材挖掘器"""

    def __init__(self, ranking_db_path: Optional[Path] = None):
        if ranking_db_path is None:
            ranking_db_path = Path("d:/project_slim/project_slim/creative_remix_engine/storage/outputs/v36_1_ranking_db.json")
        self.ranking_data = {}
        self._load(ranking_db_path)

    def _load(self, path: Path):
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data.get("shots", []):
                    self.ranking_data[item.get("video_name", "")] = item
            except Exception:
                pass

    def mine(self, target_count: int = 100) -> List[HookCandidate]:
        """
        从全部素材中挖掘 Hook 候选。
        评分标准：
        - hook_score_v2 (40%)
        - impact_score (25%)
        - subject_size (20%)
        - novelty (10%)
        - emotion (5%)
        """
        candidates = []
        for name, rank in self.ranking_data.items():
            hook_v2 = rank.get("hook_score_v2", 0)
            hook_break = rank.get("hook_breakdown", {})
            impact = hook_break.get("visual_impact", rank.get("impact_score", 0))
            subject = hook_break.get("subject_size", 30)
            novelty = hook_break.get("novelty", 20)
            emotion = hook_break.get("emotion", 30)
            motion = rank.get("motion_score", 0)

            # 综合 Hook 潜力分
            potential = (
                hook_v2 * 0.40 +
                impact * 0.25 +
                subject * 0.20 +
                novelty * 0.10 +
                emotion * 0.05
            )

            # 生成理由
            reasons = []
            if hook_v2 > 50:
                reasons.append("strong_hook")
            if impact > 50:
                reasons.append("high_impact")
            if subject > 50:
                reasons.append("large_subject")
            if novelty > 40:
                reasons.append("high_novelty")
            if motion > 50:
                reasons.append("fast_motion")
            if emotion > 50:
                reasons.append("strong_emotion")

            # 只要潜力 > 35 就入选（宽松，确保数量）
            if potential > 35:
                candidates.append(HookCandidate(
                    video_name=name,
                    video_path=rank.get("video_path", ""),
                    hook_score=hook_v2,
                    impact_score=impact,
                    subject_size=subject,
                    novelty=novelty,
                    emotion=emotion,
                    reason=", ".join(reasons) if reasons else "moderate",
                ))

        # 排序
        candidates.sort(key=lambda x: -(x.hook_score * 0.4 + x.impact_score * 0.25 + x.subject_size * 0.2 + x.novelty * 0.1 + x.emotion * 0.05))

        for i, c in enumerate(candidates):
            c.rank = i + 1

        return candidates

    def export_library(self, candidates: List[HookCandidate], output_path: Path) -> dict:
        """导出 Hook Library JSON"""
        library = {
            "total": len(candidates),
            "target": 100,
            "top_20": [self._to_dict(c) for c in candidates[:20]],
            "all": [self._to_dict(c) for c in candidates],
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(library, f, ensure_ascii=False, indent=2, default=str)
        return library

    @staticmethod
    def _to_dict(c: HookCandidate) -> dict:
        return {
            "rank": c.rank,
            "video_name": c.video_name,
            "video_path": c.video_path,
            "hook_score": c.hook_score,
            "impact_score": c.impact_score,
            "subject_size": c.subject_size,
            "novelty": c.novelty,
            "emotion": c.emotion,
            "reason": c.reason,
        }
