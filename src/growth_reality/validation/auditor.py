"""P1.7.5 — 真实校验审计编排器（Reality Auditor）。

打通 P1.7.1–P1.7.4 全链路：
    CompanySnapshot
        │
        ├─→ RevenueReconciler  (对账)
        ├─→ DataFreshnessMonitor (新鲜度)
        │
        └─→ ConfidenceScorer   (综合可信分)
                │
                └─→ RealityGate (决策门控)

产出：AuditReport（每日审计日报，Markdown 输出到 outputs/）
"""
from __future__ import annotations

from typing import Dict, List, Optional

from ..models import GrowthRealitySnapshot
from ..snapshot import CompanySnapshot
from .confidence import ConfidenceScorer
from .freshness import DataFreshnessMonitor
from .gate import RealityGate, apply_level
from .models import (
    AuditReport,
    GameAuditEntry,
    GameFreshness,
    RealityScore,
    RevenueReconciliation,
)
from .reconciliation import RevenueReconciler


class RealityAuditor:
    """P1.7 审计编排器：综合对账、新鲜度、可信分，生成每日审计报告。"""

    def __init__(self, data_dir: str = "data"):
        self.reconciler = RevenueReconciler()
        self.freshness = DataFreshnessMonitor(data_dir)
        self.scorer = ConfidenceScorer()
        self.gate = RealityGate()

    def audit(
        self,
        company: CompanySnapshot,
        adjust_by_game: Optional[Dict[str, Optional[float]]] = None,
        max_by_game: Optional[Dict[str, Optional[float]]] = None,
        reported_by_game: Optional[Dict[str, Optional[float]]] = None,
        active_sources_by_game: Optional[Dict[str, set]] = None,
    ) -> AuditReport:
        """执行全舰队审计。

        Args:
            company: E17.1 公司快照
            adjust_by_game: {game_id: IAP日收入}，无数据键不存在或为 None
            max_by_game: {game_id: 广告日收入}
            active_sources_by_game: {game_id: set of source_ids with real data}

        Returns:
            AuditReport with per-game entries and fleet summary
        """
        adj_map = adjust_by_game or {}
        max_map = max_by_game or {}
        src_map = active_sources_by_game or {}

        # Step 1: 收入对账
        recons = self.reconciler.reconcile_fleet(company, adj_map, max_map, reported_by_game)

        # Step 2: 新鲜度（逐游戏）
        fresh_map: Dict[str, GameFreshness] = {}
        sf = self.freshness.check_all()
        for gid, snap in company.per_game.items():
            active = src_map.get(gid) or set(snap.sources)
            fresh_map[gid] = self.freshness.game_freshness(gid, sf, active)

        # Step 3: 综合可信分
        entries: List[GameAuditEntry] = []
        stats = {"GREEN": 0, "YELLOW": 0, "RED": 0, "INSUFFICIENT": 0}
        total_f = 0
        total_f_green = 0
        ready = 0

        for gid, snap in company.per_game.items():
            recon = recons.get(gid)
            fresh = fresh_map.get(gid)
            cov = snap.real_confidence if snap else 0.0
            fscore = fresh.freshness_score if fresh else 1.0
            cscore = RevenueReconciler.consistency_score(recon) if recon else 1.0

            score = self.scorer.score_game(gid, cov, fscore, cscore)
            apply_level(score)

            entries.append(GameAuditEntry(
                game_id=gid, recon=recon, freshness=fresh, score=score,
            ))

            # 统计
            if recon:
                stats[recon.status] = stats.get(recon.status, 0) + 1
            if fresh:
                total_f += 1
                if fresh.overall in ("GREEN", "YELLOW"):
                    total_f_green += 1
            if score.composite >= 0.5:
                ready += 1

        return AuditReport(
            as_of=company.as_of,
            entries=entries,
            total_games=len(entries),
            green=stats["GREEN"],
            yellow=stats["YELLOW"],
            red=stats["RED"],
            insufficient=stats["INSUFFICIENT"],
            decision_ready=ready,
            revenue_integrity=(stats["GREEN"] / len(entries)) if entries else 0.0,
            data_freshness=(total_f_green / total_f) if total_f else 0.0,
        )
