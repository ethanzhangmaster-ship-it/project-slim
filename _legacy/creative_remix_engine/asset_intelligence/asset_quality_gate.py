"""Asset Quality Gate — S/A/B/C 质量分级

过滤标准：
- S: 3+维度 > 60，可用于任何场景
- A: 2+维度 > 60 或 ad_value > 50，优质素材
- B: 1+维度 > 60 或 ad_value > 35，可用但有限制
- C: 全部 < 60，淘汰或仅作备用
"""
import json
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class QualityReport:
    total: int
    s_grade: int
    a_grade: int
    b_grade: int
    c_grade: int
    approved: int
    rejected: int
    s_videos: List[str]
    a_videos: List[str]
    b_videos: List[str]


class AssetQualityGate:
    """素材质量关卡"""

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

    def grade(self, name: str) -> str:
        """单视频分级"""
        rank = self.ranking_data.get(name, {})
        scores = [
            rank.get("hook_score_v2", 0),
            rank.get("impact_score", 0),
            rank.get("motion_score", 0),
            rank.get("gameplay_clarity", 0),
            rank.get("reward_score", 0),
            rank.get("ad_value_score", 0),
        ]
        high_dims = sum(1 for s in scores if s > 60)
        ad_value = rank.get("ad_value_score", 0)

        if high_dims >= 3:
            return "S"
        if high_dims >= 2 or ad_value > 50:
            return "A"
        if high_dims >= 1 or ad_value > 35:
            return "B"
        return "C"

    def evaluate_all(self) -> QualityReport:
        """评估全部素材"""
        s_videos, a_videos, b_videos, c_videos = [], [], [], []

        for name in self.ranking_data:
            g = self.grade(name)
            if g == "S":
                s_videos.append(name)
            elif g == "A":
                a_videos.append(name)
            elif g == "B":
                b_videos.append(name)
            else:
                c_videos.append(name)

        total = len(self.ranking_data)
        approved = len(s_videos) + len(a_videos) + len(b_videos)
        rejected = len(c_videos)

        return QualityReport(
            total=total,
            s_grade=len(s_videos),
            a_grade=len(a_videos),
            b_grade=len(b_videos),
            c_grade=len(c_videos),
            approved=approved,
            rejected=rejected,
            s_videos=s_videos,
            a_videos=a_videos,
            b_videos=b_videos,
        )

    def export(self, report: QualityReport, output_path: Path):
        """导出质量报告"""
        data = {
            "total": report.total,
            "approved": report.approved,
            "rejected": report.rejected,
            "grades": {
                "S": {"count": report.s_grade, "videos": report.s_videos},
                "A": {"count": report.a_grade, "videos": report.a_videos},
                "B": {"count": report.b_grade, "videos": report.b_videos},
                "C": {"count": report.c_grade, "videos": []},
            },
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        return data
