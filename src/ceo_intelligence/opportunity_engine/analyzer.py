"""E17.2 分析器：把 E17.1 快照 + 历史派生为 GameSignals，跑规则，排序。"""
from __future__ import annotations

from typing import List, Optional

from src.growth_reality.models import GrowthRealitySnapshot

from .memory import OpportunityMemory
from .models import GameSignals, GrowthOpportunity
from .ranking import rank
from .rules import evaluate


class OpportunityAnalyzer:
    def __init__(self, memory: Optional[OpportunityMemory] = None):
        self.memory = memory

    # -- 从快照 + 历史派生信号 --
    def build_signals(
        self, snap: GrowthRealitySnapshot, prev: Optional[GrowthRealitySnapshot] = None
    ) -> GameSignals:
        s = GameSignals(game_id=snap.game_id)
        if snap.revenue:
            s.revenue = snap.revenue.daily_revenue
            if prev and prev.revenue and prev.revenue.daily_revenue > 0:
                s.revenue_growth = (
                    snap.revenue.daily_revenue - prev.revenue.daily_revenue
                ) / prev.revenue.daily_revenue
        if snap.acquisition:
            s.spend = snap.acquisition.spend
            s.installs = snap.acquisition.installs
            s.cpi = snap.acquisition.cpi
            s.roas = snap.acquisition.roas
            if prev and prev.acquisition and prev.acquisition.spend > 0:
                s.spend_growth = (
                    snap.acquisition.spend - prev.acquisition.spend
                ) / prev.acquisition.spend
            if prev and prev.acquisition and prev.acquisition.roas > 0:
                s.roas_growth = (
                    snap.acquisition.roas - prev.acquisition.roas
                ) / prev.acquisition.roas
        if snap.creative:
            s.ctr = snap.creative.ctr
            s.fatigue_score = snap.creative.fatigue_score
            s.creative_score = snap.creative.creative_score
            if prev and prev.creative and prev.creative.ctr > 0:
                s.ctr_growth = (
                    snap.creative.ctr - prev.creative.ctr
                ) / prev.creative.ctr
            if prev and prev.creative and prev.creative.creative_score > 0:
                s.creative_score_growth = (
                    snap.creative.creative_score - prev.creative.creative_score
                ) / prev.creative.creative_score
        if snap.aso:
            s.ranking = snap.aso.ranking
            s.rating = snap.aso.rating
            s.store_cvr = snap.aso.store_cvr
            if prev and prev.aso and prev.aso.store_cvr > 0:
                s.store_cvr_growth = (
                    snap.aso.store_cvr - prev.aso.store_cvr
                ) / prev.aso.store_cvr
            if prev and prev.aso and prev.aso.ranking > 0:
                s.ranking_growth = (
                    snap.aso.ranking - prev.aso.ranking
                ) / prev.aso.ranking
        if snap.product:
            s.dau = snap.product.dau
            s.retention = snap.product.retention
            s.conversion = snap.product.conversion
        s.coverage = snap.domain_coverage()
        return s

    # -- 单游戏分析 --
    def analyze_snapshot(
        self,
        snap: GrowthRealitySnapshot,
        prev: Optional[GrowthRealitySnapshot] = None,
        segment: str = "global",
        created_at: str = "",
    ) -> List[GrowthOpportunity]:
        sig = self.build_signals(snap, prev)
        opps = evaluate(sig, snap.game_id, created_at, segment)
        if self.memory:
            for o in opps:
                self.memory.apply_boost(o, segment)
        return rank(opps)
