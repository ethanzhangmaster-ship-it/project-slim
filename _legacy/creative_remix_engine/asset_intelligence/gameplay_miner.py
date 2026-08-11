"""Gameplay Miner — 从全部素材中挖掘展示玩法的视频

识别标准：
- gameplay_clarity > 45
- merge_score / drag_score / upgrade_score 高
- 网格结构明显
- 前后对比清晰
- 有动作连续性

目标：从 599 素材中挖掘 100+ 潜在 Gameplay
"""
import json
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class GameplayCandidate:
    video_name: str
    video_path: str
    gameplay_score: float
    merge_score: float
    drag_score: float
    upgrade_score: float
    before_after_score: float
    motion_score: float
    reason: str
    rank: int = 0


class GameplayMiner:
    """Gameplay 素材挖掘器"""

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

    def mine(self, target_count: int = 100) -> List[GameplayCandidate]:
        """
        从全部素材中挖掘 Gameplay 候选。
        评分标准：
        - gameplay_clarity (40%)
        - merge_score (20%)
        - drag_score (15%)
        - before_after_score (15%)
        - motion_score (10%)
        """
        candidates = []
        for name, rank in self.ranking_data.items():
            clarity = rank.get("gameplay_clarity", 0)
            clarity_break = rank.get("gameplay_clarity_breakdown", {})
            merge = clarity_break.get("merge_score", 30)
            drag = clarity_break.get("drag_score", 30)
            upgrade = clarity_break.get("upgrade_score", 30)
            before_after = clarity_break.get("before_after_score", 30)
            motion = rank.get("motion_score", 0)
            gameplay_score = rank.get("gameplay_score", 0)

            # 综合 Gameplay 潜力
            potential = (
                clarity * 0.40 +
                merge * 0.20 +
                drag * 0.15 +
                before_after * 0.15 +
                motion * 0.10
            )

            # 生成理由
            reasons = []
            if clarity > 50:
                reasons.append("clear_gameplay")
            if merge > 50:
                reasons.append("merge_visible")
            if drag > 50:
                reasons.append("drag_visible")
            if before_after > 50:
                reasons.append("before_after_clear")
            if motion > 50:
                reasons.append("continuous_motion")
            if upgrade > 50:
                reasons.append("upgrade_visible")

            # 宽松门槛：potential > 30
            if potential > 30:
                candidates.append(GameplayCandidate(
                    video_name=name,
                    video_path=rank.get("video_path", ""),
                    gameplay_score=clarity,
                    merge_score=merge,
                    drag_score=drag,
                    upgrade_score=upgrade,
                    before_after_score=before_after,
                    motion_score=motion,
                    reason=", ".join(reasons) if reasons else "moderate",
                ))

        candidates.sort(key=lambda x: -(x.gameplay_score * 0.4 + x.merge_score * 0.2 + x.drag_score * 0.15 + x.before_after_score * 0.15 + x.motion_score * 0.1))

        for i, c in enumerate(candidates):
            c.rank = i + 1

        return candidates

    def export_library(self, candidates: List[GameplayCandidate], output_path: Path) -> dict:
        """导出 Gameplay Library JSON"""
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
    def _to_dict(c: GameplayCandidate) -> dict:
        return {
            "rank": c.rank,
            "video_name": c.video_name,
            "video_path": c.video_path,
            "gameplay_score": c.gameplay_score,
            "merge_score": c.merge_score,
            "drag_score": c.drag_score,
            "upgrade_score": c.upgrade_score,
            "before_after_score": c.before_after_score,
            "motion_score": c.motion_score,
            "reason": c.reason,
        }
