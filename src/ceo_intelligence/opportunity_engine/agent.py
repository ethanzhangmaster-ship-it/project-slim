"""E17.2 主入口：GrowthOpportunityAgent。

输入：E17.1 的 CompanySnapshot（可携带 GrowthFeatureStore 历史以算环比）
输出：OpportunityReport（total / top_priority / portfolio_ranking / risk_summary）
"""
from __future__ import annotations

from typing import Dict, List, Optional

from src.growth_reality.models import GrowthRealitySnapshot
from src.growth_reality.snapshot import CompanySnapshot

try:  # 历史 prev 可选
    from src.growth_reality.feature_store import GrowthFeatureStore
except Exception:  # pragma: no cover
    GrowthFeatureStore = None  # type: ignore

from .analyzer import OpportunityAnalyzer
from .memory import OpportunityMemory
from .models import GrowthOpportunity, OpportunityReport, PortfolioOpportunity
from .ranking import rank


class GrowthOpportunityAgent:
    def __init__(self, memory: Optional[OpportunityMemory] = None):
        self.analyzer = OpportunityAnalyzer(memory)

    def analyze(
        self,
        company: CompanySnapshot,
        store: Optional["GrowthFeatureStore"] = None,
        segment: str = "global",
        created_at: str = "",
        top_n: int = 10,
    ) -> OpportunityReport:
        all_opps: List[GrowthOpportunity] = []
        for gid, snap in company.per_game.items():
            prev = self._prev_for(gid, snap, store)
            opps = self.analyzer.analyze_snapshot(snap, prev, segment, created_at)
            all_opps.extend(opps)

        ranked = rank(all_opps)
        portfolio = self._portfolio_ranking(ranked)
        risk = self._risk_summary(ranked)

        return OpportunityReport(
            total_opportunities=len(ranked),
            top_priority=ranked[:top_n],
            portfolio_ranking=portfolio,
            risk_summary=risk,
        )

    # -- 历史 prev 获取 --
    def _prev_for(self, gid, snap: GrowthRealitySnapshot, store) -> Optional[GrowthRealitySnapshot]:
        if store is None:
            return None
        hist = store.history(gid, limit=2)
        if len(hist) >= 2:
            return hist[-2]
        return None

    # -- 组合排序：每游戏取最高优先级机会 --
    @staticmethod
    def _portfolio_ranking(ranked: List[GrowthOpportunity]) -> List[PortfolioOpportunity]:
        best: Dict[str, GrowthOpportunity] = {}
        for o in ranked:
            if o.game_id not in best or o.priority > best[o.game_id].priority:
                best[o.game_id] = o
        rows = [
            PortfolioOpportunity(
                game_id=gid,
                top_problem=o.problem,
                priority=round(o.priority, 4),
                type=o.type.value,
            )
            for gid, o in best.items()
        ]
        return sorted(rows, key=lambda x: x.priority, reverse=True)

    # -- 风险摘要 --
    @staticmethod
    def _risk_summary(ranked: List[GrowthOpportunity]) -> Dict[str, object]:
        high = medium = low = 0
        total_impact = 0.0
        for o in ranked:
            total_impact += o.expected_impact
            if o.risk >= 0.6:
                high += 1
            elif o.risk >= 0.35:
                medium += 1
            else:
                low += 1
        return {
            "high": high,
            "medium": medium,
            "low": low,
            "total_expected_impact": round(total_impact, 4),
        }
