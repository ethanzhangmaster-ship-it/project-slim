"""E17.10 Portfolio Dashboard — aggregator.

Deterministically folds E17.1-E17.9 artifacts into a single
``PortfolioDashboard`` document. No LLM, no IO, no randomness
(does NOT depend on decision audit_id values).

Inputs (all in-process objects, reused not rebuilt):
- E17.1  ``CompanySnapshot``           — fleet reality
- E17.3  ``DecisionReport``            — decisions with risk per game
- E17.8  ``PortfolioSimulationReport`` — gates + portfolio distribution
- E17.9  ``List[GamePriority]``        — CEO priority ranking
- E17.9  ``List[DailyActionItem]``     — AUTO / APPROVAL / BLOCK actions
- E17.7  ``GrowthMemoryGraph``         — learned patterns (optional)
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.ceo_intelligence.daily_operator.models import (
    ActionKind,
    classify_company,
)
from src.ceo_intelligence.growth_memory_graph.patterns import extract_patterns
from .models import (
    GameStatus,
    GameTile,
    LearnedPattern,
    PortfolioDashboard,
    PortfolioKPI,
    QueueEntry,
    RiskFlag,
    RiskLevel,
    classify_game,
)

# Deterministic ordering for the decision queue: what needs eyes first.
_KIND_ORDER: Dict[str, int] = {
    ActionKind.APPROVAL.value: 0,
    ActionKind.BLOCK.value: 1,
    ActionKind.AUTO.value: 2,
}

MAX_LEARNED_PATTERNS = 5


class PortfolioAggregator:
    """Builds a PortfolioDashboard from upstream E17 artifacts."""

    def aggregate(
        self,
        company: Any,
        *,
        date: str,
        dec_report: Any = None,
        sim_report: Any = None,
        priorities: Optional[List[Any]] = None,
        actions: Optional[List[Any]] = None,
        memory_graph: Any = None,
    ) -> PortfolioDashboard:
        priorities = list(priorities or [])
        actions = list(actions or [])

        top_priority = self._top_priority_by_game(priorities)
        risk_by_game = self._risk_by_game(dec_report)
        gate_by_game = self._gate_by_game(sim_report)

        tiles = self._build_tiles(
            company, top_priority, risk_by_game, gate_by_game
        )
        kpi = self._build_kpi(company, tiles, actions, priorities, sim_report)
        queue = self._build_queue(actions)
        flags = self._build_risk_flags(company, tiles, sim_report)
        patterns, memory_summary = self._build_memory_view(memory_graph)

        return PortfolioDashboard(
            date=date,
            company_status=classify_company(company).value,
            kpi=kpi,
            tiles=tiles,
            decision_queue=queue,
            risk_flags=flags,
            learned_patterns=patterns,
            memory_summary=memory_summary,
        )

    # ------------------------------------------------------------------ #
    # upstream indexing (deterministic; never keyed by audit_id)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _top_priority_by_game(priorities: List[Any]) -> Dict[str, Any]:
        """Best (lowest rank) GamePriority per game."""
        top: Dict[str, Any] = {}
        for p in sorted(priorities, key=lambda x: (x.rank, x.game_id)):
            top.setdefault(p.game_id, p)
        return top

    @staticmethod
    def _risk_by_game(dec_report: Any) -> Dict[str, float]:
        """Max decision risk per game from E17.3 DecisionReport."""
        risk: Dict[str, float] = {}
        if dec_report is None:
            return risk
        for d in getattr(dec_report, "decisions", []) or []:
            prev = risk.get(d.game_id, 0.0)
            if d.risk > prev:
                risk[d.game_id] = d.risk
        return risk

    @staticmethod
    def _gate_by_game(sim_report: Any) -> Dict[str, str]:
        """Worst gate per game from E17.8 (block > review > pass)."""
        severity = {"block": 2, "review": 1, "pass": 0}
        gate: Dict[str, str] = {}
        if sim_report is None:
            return gate
        for sim in getattr(sim_report, "simulations", []) or []:
            status = sim.flag.status.value
            prev = gate.get(sim.game_id)
            if prev is None or severity.get(status, 0) > severity.get(prev, 0):
                gate[sim.game_id] = status
        return gate

    # ------------------------------------------------------------------ #
    # tiles
    # ------------------------------------------------------------------ #
    def _build_tiles(
        self,
        company: Any,
        top_priority: Dict[str, Any],
        risk_by_game: Dict[str, float],
        gate_by_game: Dict[str, str],
    ) -> List[GameTile]:
        at_risk = set(company.at_risk)
        tiles: List[GameTile] = []
        for game_id in sorted(company.per_game):
            snap = company.per_game[game_id]
            revenue = snap.revenue.daily_revenue if snap.revenue else None
            dau = snap.product.dau if snap.product else None
            roas = snap.acquisition.roas if snap.acquisition else None
            prio = top_priority.get(game_id)
            gate = gate_by_game.get(game_id, prio.gate if prio else "")
            tiles.append(
                GameTile(
                    game_id=game_id,
                    status=classify_game(
                        confidence=snap.confidence,
                        daily_revenue=revenue,
                        gate=gate,
                        at_risk=game_id in at_risk,
                    ),
                    rank=prio.rank if prio else 0,
                    priority_score=(
                        prio.priority_score_value if prio else 0.0
                    ),
                    opportunity_type=prio.opportunity_type if prio else "",
                    top_action=prio.action if prio else "",
                    decision_type=prio.decision_type if prio else "",
                    gate=gate,
                    daily_revenue=revenue,
                    dau=dau,
                    roas=roas,
                    confidence=snap.confidence,
                    risk=risk_by_game.get(game_id, 0.0),
                    expected_impact=prio.impact if prio else 0.0,
                )
            )
        # priority first (rank>0 ascending), then no-priority games by id
        tiles.sort(key=lambda t: (t.rank == 0, t.rank, t.game_id))
        return tiles

    # ------------------------------------------------------------------ #
    # KPI
    # ------------------------------------------------------------------ #
    def _build_kpi(
        self,
        company: Any,
        tiles: List[GameTile],
        actions: List[Any],
        priorities: List[Any],
        sim_report: Any,
    ) -> PortfolioKPI:
        auto = [a for a in actions if a.kind == ActionKind.AUTO]
        approval = [a for a in actions if a.kind == ActionKind.APPROVAL]
        blocked = [a for a in actions if a.kind == ActionKind.BLOCK]

        impact_by_game = {p.game_id: p.impact for p in priorities}
        expected_impact = round(
            sum(impact_by_game.get(a.game_id, 0.0) for a in auto), 6
        )

        sim_p50: Optional[float] = None
        if sim_report is not None:
            base = getattr(sim_report, "portfolio", {}).get("baseline")
            if base is not None:
                sim_p50 = base.p50

        return PortfolioKPI(
            total_games=company.game_count,
            total_daily_revenue=company.total_revenue,
            total_dau=company.total_dau,
            total_spend=company.total_spend,
            total_installs=company.total_installs,
            avg_confidence=company.avg_confidence,
            healthy_games=sum(
                1 for t in tiles if t.status == GameStatus.HEALTHY
            ),
            attention_games=sum(
                1 for t in tiles if t.status == GameStatus.ATTENTION
            ),
            critical_games=sum(
                1 for t in tiles if t.status == GameStatus.CRITICAL
            ),
            auto_actions=len(auto),
            approval_actions=len(approval),
            blocked_actions=len(blocked),
            expected_revenue_impact=expected_impact,
            portfolio_sim_p50=sim_p50,
        )

    # ------------------------------------------------------------------ #
    # decision queue
    # ------------------------------------------------------------------ #
    @staticmethod
    def _build_queue(actions: List[Any]) -> List[QueueEntry]:
        entries = [
            QueueEntry(
                kind=a.kind.value,
                game_id=a.game_id,
                action=a.action,
                detail=a.detail,
                opportunity_type=a.opportunity_type,
            )
            for a in actions
        ]
        entries.sort(key=lambda e: (_KIND_ORDER.get(e.kind, 9), e.game_id))
        return entries

    # ------------------------------------------------------------------ #
    # risk flags
    # ------------------------------------------------------------------ #
    @staticmethod
    def _build_risk_flags(
        company: Any, tiles: List[GameTile], sim_report: Any
    ) -> List[RiskFlag]:
        flags: List[RiskFlag] = []
        tile_by_game = {t.game_id: t for t in tiles}

        # 1) reality-layer at_risk games
        for game_id in sorted(company.at_risk):
            snap = company.per_game.get(game_id)
            if snap is not None and snap.revenue and snap.revenue.daily_revenue <= 0:
                flags.append(
                    RiskFlag(
                        level=RiskLevel.HIGH,
                        game_id=game_id,
                        domain="revenue",
                        reason="日收入 <= 0（现实层判定 at_risk）",
                    )
                )
            else:
                flags.append(
                    RiskFlag(
                        level=RiskLevel.MEDIUM,
                        game_id=game_id,
                        domain="data",
                        reason="数据置信度过低（<40%），现实层判定 at_risk",
                    )
                )

        # 2) simulation gate blocks / reviews
        if sim_report is not None:
            for sim in getattr(sim_report, "simulations", []) or []:
                status = sim.flag.status.value
                if status == "block":
                    flags.append(
                        RiskFlag(
                            level=RiskLevel.HIGH,
                            game_id=sim.game_id,
                            domain="simulation",
                            reason=f"闸门阻断：{sim.flag.reason or sim.action}",
                        )
                    )
                elif status == "review":
                    flags.append(
                        RiskFlag(
                            level=RiskLevel.MEDIUM,
                            game_id=sim.game_id,
                            domain="simulation",
                            reason=f"闸门要求复核：{sim.flag.reason or sim.action}",
                        )
                    )

        # 3) low-confidence tiles not already flagged
        flagged = {(f.game_id, f.domain) for f in flags}
        for tile in tiles:
            if tile.confidence < 0.6 and (tile.game_id, "data") not in flagged:
                if tile.game_id not in company.at_risk:
                    flags.append(
                        RiskFlag(
                            level=RiskLevel.LOW,
                            game_id=tile.game_id,
                            domain="data",
                            reason=f"数据置信度偏低（{tile.confidence:.0%}）",
                        )
                    )

        order = {RiskLevel.HIGH: 0, RiskLevel.MEDIUM: 1, RiskLevel.LOW: 2}
        flags.sort(key=lambda f: (order[f.level], f.game_id, f.domain))
        return flags

    # ------------------------------------------------------------------ #
    # memory (E17.7 patterns)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _build_memory_view(memory_graph: Any) -> tuple:
        if memory_graph is None:
            return [], ""
        raw = extract_patterns(memory_graph)
        patterns = [
            LearnedPattern(
                strategy_type=p.strategy_type,
                domain=p.domain,
                action_type=p.action_type,
                samples=p.samples,
                success_rate=p.success_rate,
                avg_revenue_delta=p.avg_revenue_delta,
                confidence_boost=p.confidence_boost,
            )
            for p in raw[:MAX_LEARNED_PATTERNS]
        ]
        if not patterns:
            return [], "记忆图谱暂无可用模式（样本不足）。"
        best = patterns[0]
        summary = (
            f"已沉淀 {len(raw)} 个模式；最佳：{best.strategy_type}"
            f"（{best.domain}/{best.action_type}）"
            f"成功率 {best.success_rate:.0%}，"
            f"平均收入增量 {best.avg_revenue_delta:+.1%}，"
            f"置信加成 +{best.confidence_boost:.0%}"
        )
        return patterns, summary


__all__ = ["PortfolioAggregator", "MAX_LEARNED_PATTERNS"]
