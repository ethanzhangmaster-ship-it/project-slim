"""
E16.1.4 — Portfolio Intelligence (多游戏组合智能).

The one-person, 10-50 game studio cannot think game-by-game; it must think
like a fund manager. This module ranks the whole fleet and issues one
verdict per game:

* SCALE      — profitable and trending up → pour more in
* MAINTAIN   — fine as-is → keep steady
* REDUCE     — economics weakening → cut budget
* SUNSET     — persistent loser at low volume → stop maintaining
* REPLICATE  — the top winner whose pattern should be cloned to siblings

Deterministic scoring; the same fleet always ranks the same way.
Pure logic, no I/O.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

__all__ = [
    "PortfolioVerdict",
    "GamePortfolioEntry",
    "PortfolioDecision",
    "PortfolioReport",
    "PortfolioIntelligence",
]


class PortfolioVerdict(str, Enum):
    SCALE = "scale"
    MAINTAIN = "maintain"
    REDUCE = "reduce"
    SUNSET = "sunset"
    REPLICATE = "replicate"  # top winner: clone its pattern to siblings


# --------------------------------------------------------------------------- #
# Input / output models
# --------------------------------------------------------------------------- #
@dataclass
class GamePortfolioEntry:
    """One game's summarized economics for portfolio ranking."""

    game_id: str
    revenue: float = 0.0  # period revenue
    profit: float = 0.0  # period profit (after UA + fees)
    roas: float = 0.0
    dau: int = 0
    trend: str = "flat"  # "up" | "down" | "flat" (e.g. from RevenueForecaster)
    genre: Optional[str] = None  # for replicate-to-siblings hints
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "revenue": round(self.revenue, 4),
            "profit": round(self.profit, 4),
            "roas": round(self.roas, 4),
            "dau": self.dau,
            "trend": self.trend,
            "genre": self.genre,
            "extra": self.extra,
        }


@dataclass
class PortfolioDecision:
    game_id: str
    verdict: PortfolioVerdict
    score: float  # composite 0-100 ranking score
    rationale: str
    confidence: float = 0.8
    replicate_targets: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "verdict": self.verdict.value,
            "score": round(self.score, 2),
            "rationale": self.rationale,
            "confidence": round(self.confidence, 4),
            "replicate_targets": list(self.replicate_targets),
        }


@dataclass
class PortfolioReport:
    decisions: List[PortfolioDecision] = field(default_factory=list)
    total_revenue: float = 0.0
    total_profit: float = 0.0
    fleet_size: int = 0

    def by_verdict(self, verdict: PortfolioVerdict) -> List[PortfolioDecision]:
        return [d for d in self.decisions if d.verdict == verdict]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fleet_size": self.fleet_size,
            "total_revenue": round(self.total_revenue, 4),
            "total_profit": round(self.total_profit, 4),
            "decisions": [d.to_dict() for d in self.decisions],
        }

    def to_markdown(self) -> str:
        lines = [
            "## Portfolio Report",
            f"- Fleet: {self.fleet_size} games | "
            f"Revenue ${self.total_revenue:,.0f} | "
            f"Profit ${self.total_profit:,.0f}",
            "",
            "| Game | Verdict | Score | Why |",
            "|---|---|---|---|",
        ]
        for d in self.decisions:
            lines.append(
                f"| {d.game_id} | {d.verdict.value.upper()} | "
                f"{d.score:.0f} | {d.rationale} |"
            )
        return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #
class PortfolioIntelligence:
    """Fund-manager view over the whole game fleet.

    Scoring (0-100): profit contribution (0-40) + ROAS quality (0-30) +
    trend (0-20) + volume (0-10). Verdicts derive from score bands plus
    hard rules (losers, sunset candidates, top replicable winner).
    """

    def __init__(
        self,
        scale_roas: float = 1.3,
        reduce_roas: float = 1.0,
        sunset_dau: int = 200,
        sunset_profit: float = 0.0,
        replicate_min_score: float = 70.0,
        organic_scale_share: float = 0.2,
        organic_sunset_revenue: float = 5.0,
    ):
        self.scale_roas = scale_roas
        self.reduce_roas = reduce_roas
        self.sunset_dau = sunset_dau
        self.sunset_profit = sunset_profit
        self.replicate_min_score = replicate_min_score
        # Organic mode (no UA spend, roas <= 0 with revenue > 0):
        # ROAS rules do not apply; judge by fleet revenue share + trend.
        self.organic_scale_share = organic_scale_share
        self.organic_sunset_revenue = organic_sunset_revenue

    @staticmethod
    def _is_organic(e: GamePortfolioEntry) -> bool:
        """No UA spend: ROAS is undefined (0) yet the game earns revenue."""
        return e.roas <= 0.0 and e.revenue > 0.0

    # ------------------------------------------------------------------ #
    def evaluate(self, entries: List[GamePortfolioEntry]) -> PortfolioReport:
        if not entries:
            return PortfolioReport()

        total_revenue = sum(e.revenue for e in entries)
        total_profit = sum(e.profit for e in entries)
        max_profit = max((e.profit for e in entries), default=0.0)
        max_dau = max((e.dau for e in entries), default=0)
        max_revenue = max((e.revenue for e in entries), default=0.0)

        scored = [
            (e, self._score(e, max_profit, max_dau, max_revenue))
            for e in entries
        ]
        scored.sort(key=lambda t: t[1], reverse=True)

        decisions: List[PortfolioDecision] = []
        for e, score in scored:
            if self._is_organic(e):
                decisions.append(self._organic_verdict(e, score, total_revenue))
            else:
                decisions.append(self._verdict(e, score))

        # Top winner becomes REPLICATE if strong enough
        if scored:
            top_entry, top_score = scored[0]
            top_is_organic_winner = (
                self._is_organic(top_entry)
                and total_revenue > 1e-9
                and (top_entry.revenue / total_revenue)
                >= max(self.organic_scale_share, 0.5)
                and top_entry.trend != "down"
            )
            if top_is_organic_winner or (
                top_score >= self.replicate_min_score
                and top_entry.profit > 0
                and top_entry.trend == "up"
                and top_entry.roas >= self.scale_roas
            ):
                targets = [
                    e.game_id
                    for e, _ in scored[1:]
                    if top_entry.genre and e.genre == top_entry.genre
                ]
                decisions[0] = PortfolioDecision(
                    game_id=top_entry.game_id,
                    verdict=PortfolioVerdict.REPLICATE,
                    score=top_score,
                    rationale=(
                        f"Fleet winner (score {top_score:.0f}, profit "
                        f"${top_entry.profit:,.0f}) — replicate its pattern"
                        + (f" to {len(targets)} sibling(s)" if targets else "")
                        + "."
                    ),
                    confidence=0.85,
                    replicate_targets=targets,
                )

        return PortfolioReport(
            decisions=decisions,
            total_revenue=total_revenue,
            total_profit=total_profit,
            fleet_size=len(entries),
        )

    # ------------------------------------------------------------------ #
    def _score(
        self,
        e: GamePortfolioEntry,
        max_profit: float,
        max_dau: int,
        max_revenue: float = 0.0,
    ) -> float:
        # profit contribution 0-40 (relative to fleet best; losers get 0)
        if max_profit > 1e-9 and e.profit > 0:
            profit_pts = 40.0 * (e.profit / max_profit)
        else:
            profit_pts = 0.0

        # ROAS quality 0-30 (1.0 → 15, scale_roas+ → 30, 0 → 0).
        # Organic games have no UA spend so ROAS is undefined; substitute
        # relative revenue strength so they are not unfairly capped at 70.
        if self._is_organic(e):
            roas_pts = (
                30.0 * (e.revenue / max_revenue) if max_revenue > 1e-9 else 0.0
            )
        elif e.roas <= 0:
            roas_pts = 0.0
        else:
            roas_pts = min(30.0, 15.0 * (e.roas / max(self.reduce_roas, 1e-9)))

        # trend 0-20
        trend_pts = {"up": 20.0, "flat": 10.0, "down": 0.0}.get(e.trend, 10.0)

        # volume 0-10
        volume_pts = 10.0 * (e.dau / max_dau) if max_dau > 0 else 0.0

        return min(100.0, profit_pts + roas_pts + trend_pts + volume_pts)

    def _organic_verdict(
        self, e: GamePortfolioEntry, score: float, total_revenue: float
    ) -> PortfolioDecision:
        """Verdict for organic (no UA spend) titles.

        ROAS rules do not apply. Judge by fleet revenue share + trend:
        * near-zero revenue → SUNSET (stop maintaining)
        * meaningful share + not declining → SCALE (worth real investment:
          UA test, feature push, ASO)
        * declining or marginal → MAINTAIN (zero cost to keep alive)
        """
        share = (e.revenue / total_revenue) if total_revenue > 1e-9 else 0.0

        if e.revenue < self.organic_sunset_revenue:
            return PortfolioDecision(
                game_id=e.game_id,
                verdict=PortfolioVerdict.SUNSET,
                score=score,
                rationale=(
                    f"Organic title earning ${e.revenue:,.2f} — below "
                    f"maintenance-worthy threshold, stop maintaining."
                ),
                confidence=0.8,
            )

        if share >= self.organic_scale_share and e.trend != "down":
            return PortfolioDecision(
                game_id=e.game_id,
                verdict=PortfolioVerdict.SCALE,
                score=score,
                rationale=(
                    f"Organic earner with {share:.0%} of fleet revenue "
                    f"(${e.revenue:,.2f}) and {e.trend} trend — worth real "
                    f"investment (UA test / ASO / feature push)."
                ),
                confidence=0.8,
            )

        return PortfolioDecision(
            game_id=e.game_id,
            verdict=PortfolioVerdict.MAINTAIN,
            score=score,
            rationale=(
                f"Organic title at {share:.0%} fleet share, trend {e.trend} "
                f"— zero-cost to keep, no active investment."
            ),
            confidence=0.75,
        )

    def _verdict(
        self, e: GamePortfolioEntry, score: float
    ) -> PortfolioDecision:
        # Hard rule: persistent loser at low volume → SUNSET
        if e.profit <= self.sunset_profit and e.dau < self.sunset_dau:
            return PortfolioDecision(
                game_id=e.game_id,
                verdict=PortfolioVerdict.SUNSET,
                score=score,
                rationale=(
                    f"Unprofitable (${e.profit:,.0f}) at low volume "
                    f"({e.dau} DAU) — stop maintaining."
                ),
                confidence=0.85,
            )

        # Hard rule: economics weakening → REDUCE
        if e.roas < self.reduce_roas or (e.profit < 0 and e.trend == "down"):
            return PortfolioDecision(
                game_id=e.game_id,
                verdict=PortfolioVerdict.REDUCE,
                score=score,
                rationale=(
                    f"ROAS {e.roas:.2f} below breakeven or losing with a "
                    f"down trend — cut budget."
                ),
                confidence=0.8,
            )

        # Strong economics + upward trend → SCALE
        if e.roas >= self.scale_roas and e.trend == "up" and e.profit > 0:
            return PortfolioDecision(
                game_id=e.game_id,
                verdict=PortfolioVerdict.SCALE,
                score=score,
                rationale=(
                    f"ROAS {e.roas:.2f} with rising revenue and "
                    f"${e.profit:,.0f} profit — increase investment."
                ),
                confidence=0.85,
            )

        return PortfolioDecision(
            game_id=e.game_id,
            verdict=PortfolioVerdict.MAINTAIN,
            score=score,
            rationale="Stable economics — keep current investment level.",
            confidence=0.75,
        )
