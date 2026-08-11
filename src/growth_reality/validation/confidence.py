"""P1.7.3 — 真实置信分（Reality Confidence Score）。

综合真实数据的三维可信度：
    RealityScore = Coverage × Freshness × Consistency

- Coverage   : 来自 P1.6 real_confidence（真实源覆盖域数/5）
- Freshness  : 来自 freshness.py 的游戏级 freshness_score（0-1）
- Consistency: 来自 reconciliation.py 的 consistency_score（0-1）
"""
from __future__ import annotations

from typing import Dict, Optional

from ..models import GrowthRealitySnapshot
from .models import RealityScore


class ConfidenceScorer:
    """三维可信分计算器。

    对每个游戏，综合 coverage / freshness / consistency 得出 composite RealityScore。
    """

    @staticmethod
    def score_game(
        game_id: str,
        coverage: float,
        freshness: float,
        consistency: float,
    ) -> RealityScore:
        return RealityScore.compute(game_id, coverage, freshness, consistency)

    @staticmethod
    def score_from_components(
        game_id: str,
        snap: Optional[GrowthRealitySnapshot] = None,
        freshness_score: float = 1.0,
        consistency_score: float = 1.0,
    ) -> RealityScore:
        """便捷方法：从快照取 coverage，其余显式传入。"""
        cov = snap.real_confidence if snap else 0.0
        return RealityScore.compute(game_id, cov, freshness_score, consistency_score)

    @staticmethod
    def score_fleet(
        coverage_by_game: Dict[str, float],
        freshness_by_game: Dict[str, float],
        consistency_by_game: Dict[str, float],
    ) -> Dict[str, RealityScore]:
        game_ids = set(coverage_by_game) | set(freshness_by_game) | set(consistency_by_game)
        return {
            gid: RealityScore.compute(
                gid,
                coverage_by_game.get(gid, 0.0),
                freshness_by_game.get(gid, 1.0),
                consistency_by_game.get(gid, 1.0),
            )
            for gid in game_ids
        }
