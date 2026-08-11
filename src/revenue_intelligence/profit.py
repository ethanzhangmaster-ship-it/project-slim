"""
E16.1.3 — Profit Intelligence (利润智能).

Revenue tells you the top line; this module tells you the truth:

    Profit = Revenue - UA Cost - Platform Fee - Other Ad/Network Cost

It upgrades the Revenue Brain from "revenue analyst" to "CFO":

* ``ProfitSnapshot``  — one period of profit reality (derived from a
  ``RevenueSnapshot`` + cost assumptions, or built directly)
* ``ProfitDelta``     — period-over-period change
* ``ProfitInsight``   — named business judgements:
    - unprofitable_growth  (revenue up, profit down — buying fake growth)
    - margin_compression   (profit up but margin shrinking)
    - healthy_scaling      (revenue & profit & margin all up)
    - loss_making          (profit < 0)
* ``ProfitEngine``    — analyze(current, previous) → ProfitReport

Deterministic, pure, no I/O.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .models import RevenueSnapshot

__all__ = [
    "ProfitSnapshot",
    "ProfitDelta",
    "ProfitInsight",
    "ProfitReport",
    "ProfitEngine",
    "DEFAULT_PLATFORM_FEE_RATE",
]

DEFAULT_PLATFORM_FEE_RATE = 0.30  # Google Play / App Store standard cut on IAP


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #
@dataclass
class ProfitSnapshot:
    """One period of profit reality for a single game."""

    game_id: str
    date: str

    revenue: float = 0.0
    ua_cost: float = 0.0
    platform_fee: float = 0.0
    other_cost: float = 0.0  # ad-serving / network / tooling costs

    @property
    def total_cost(self) -> float:
        return self.ua_cost + self.platform_fee + self.other_cost

    @property
    def profit(self) -> float:
        return self.revenue - self.total_cost

    @property
    def margin(self) -> float:
        """Profit margin as a fraction of revenue (0 when revenue is 0)."""
        if self.revenue <= 1e-9:
            return 0.0
        return self.profit / self.revenue

    @property
    def roi(self) -> Optional[float]:
        """Profit / total cost. None when there is no cost basis."""
        if self.total_cost <= 1e-9:
            return None
        return self.profit / self.total_cost

    @classmethod
    def from_revenue_snapshot(
        cls,
        snap: RevenueSnapshot,
        platform_fee_rate: float = DEFAULT_PLATFORM_FEE_RATE,
        other_cost: float = 0.0,
    ) -> "ProfitSnapshot":
        """Derive profit reality from a RevenueSnapshot.

        Platform fee applies to IAP revenue only (ad revenue is already net
        of the mediation cut in MAX reporting).
        """
        return cls(
            game_id=snap.game_id,
            date=snap.date,
            revenue=snap.revenue_total,
            ua_cost=snap.spend,
            platform_fee=snap.iap_revenue * platform_fee_rate,
            other_cost=other_cost,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "date": self.date,
            "revenue": round(self.revenue, 4),
            "ua_cost": round(self.ua_cost, 4),
            "platform_fee": round(self.platform_fee, 4),
            "other_cost": round(self.other_cost, 4),
            "total_cost": round(self.total_cost, 4),
            "profit": round(self.profit, 4),
            "margin": round(self.margin, 4),
            "roi": round(self.roi, 4) if self.roi is not None else None,
        }


@dataclass
class ProfitDelta:
    game_id: str
    current_date: str
    previous_date: str

    revenue_pct: Optional[float] = None
    cost_pct: Optional[float] = None
    profit_pct: Optional[float] = None
    profit_abs: float = 0.0
    margin_change: float = 0.0  # absolute margin points (e.g. -0.05)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "current_date": self.current_date,
            "previous_date": self.previous_date,
            "revenue_pct": self.revenue_pct,
            "cost_pct": self.cost_pct,
            "profit_pct": self.profit_pct,
            "profit_abs": round(self.profit_abs, 4),
            "margin_change": round(self.margin_change, 4),
        }


@dataclass
class ProfitInsight:
    game_id: str
    kind: str  # unprofitable_growth | margin_compression | healthy_scaling | loss_making
    summary: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.8
    severity: str = "info"  # info | warning | critical

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "kind": self.kind,
            "summary": self.summary,
            "evidence": self.evidence,
            "confidence": round(self.confidence, 4),
            "severity": self.severity,
        }


@dataclass
class ProfitReport:
    game_id: str
    current: ProfitSnapshot
    previous: Optional[ProfitSnapshot] = None
    delta: Optional[ProfitDelta] = None
    insights: List[ProfitInsight] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "current": self.current.to_dict(),
            "previous": self.previous.to_dict() if self.previous else None,
            "delta": self.delta.to_dict() if self.delta else None,
            "insights": [i.to_dict() for i in self.insights],
        }

    def to_markdown(self) -> str:
        c = self.current
        lines = [
            f"## Profit Report — {self.game_id} ({c.date})",
            f"- Revenue: ${c.revenue:,.0f}",
            f"- Costs: ${c.total_cost:,.0f} "
            f"(UA ${c.ua_cost:,.0f} / fee ${c.platform_fee:,.0f} / other ${c.other_cost:,.0f})",
            f"- **Profit: ${c.profit:,.0f}** (margin {c.margin * 100:.1f}%)",
        ]
        if self.delta and self.delta.profit_pct is not None:
            lines.append(f"- Profit change: {self.delta.profit_pct:+.1f}%")
        for i in self.insights:
            lines.append(f"- [{i.severity}] {i.kind}: {i.summary}")
        return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #
class ProfitEngine:
    """Deterministic profit analysis: snapshot → delta → named insights."""

    def __init__(self, margin_compression_points: float = 0.03):
        # margin drop (absolute points) that triggers margin_compression
        self.margin_compression_points = margin_compression_points

    def analyze(
        self,
        current: ProfitSnapshot,
        previous: Optional[ProfitSnapshot] = None,
    ) -> ProfitReport:
        delta = self._delta(current, previous) if previous else None
        insights = self._insights(current, previous, delta)
        return ProfitReport(
            game_id=current.game_id,
            current=current,
            previous=previous,
            delta=delta,
            insights=insights,
        )

    # ------------------------------------------------------------------ #
    @staticmethod
    def _pct(cur: float, prev: float) -> Optional[float]:
        if abs(prev) <= 1e-9:
            return None
        return (cur - prev) / abs(prev) * 100.0

    def _delta(
        self, current: ProfitSnapshot, previous: ProfitSnapshot
    ) -> ProfitDelta:
        return ProfitDelta(
            game_id=current.game_id,
            current_date=current.date,
            previous_date=previous.date,
            revenue_pct=self._pct(current.revenue, previous.revenue),
            cost_pct=self._pct(current.total_cost, previous.total_cost),
            profit_pct=self._pct(current.profit, previous.profit),
            profit_abs=current.profit - previous.profit,
            margin_change=current.margin - previous.margin,
        )

    def _insights(
        self,
        current: ProfitSnapshot,
        previous: Optional[ProfitSnapshot],
        delta: Optional[ProfitDelta],
    ) -> List[ProfitInsight]:
        out: List[ProfitInsight] = []

        # loss making — always checked, no history needed
        if current.profit < 0:
            out.append(
                ProfitInsight(
                    game_id=current.game_id,
                    kind="loss_making",
                    summary=(
                        f"Losing ${abs(current.profit):,.0f} this period "
                        f"(margin {current.margin * 100:.1f}%)."
                    ),
                    evidence={"profit": round(current.profit, 2)},
                    confidence=0.95,
                    severity="critical",
                )
            )

        if not previous or not delta:
            return out

        rev_up = (delta.revenue_pct or 0.0) > 0.0
        profit_down = current.profit < previous.profit
        profit_up = current.profit > previous.profit

        # 收入涨、利润跌 → 买来的假增长
        if rev_up and profit_down:
            out.append(
                ProfitInsight(
                    game_id=current.game_id,
                    kind="unprofitable_growth",
                    summary=(
                        f"Revenue {delta.revenue_pct:+.1f}% but profit fell "
                        f"${abs(delta.profit_abs):,.0f} — growth is being "
                        f"bought at a loss."
                    ),
                    evidence={
                        "revenue_pct": delta.revenue_pct,
                        "profit_abs": round(delta.profit_abs, 2),
                        "cost_pct": delta.cost_pct,
                    },
                    confidence=0.9,
                    severity="warning",
                )
            )

        # 利润涨但毛利率压缩 → 规模在吃效率
        if (
            profit_up
            and delta.margin_change < -self.margin_compression_points
        ):
            out.append(
                ProfitInsight(
                    game_id=current.game_id,
                    kind="margin_compression",
                    summary=(
                        f"Profit up but margin compressed "
                        f"{delta.margin_change * 100:+.1f} pts — scale is "
                        f"eating efficiency."
                    ),
                    evidence={"margin_change": round(delta.margin_change, 4)},
                    confidence=0.8,
                    severity="warning",
                )
            )

        # 健康扩张：收入、利润都涨且毛利率没有明显压缩
        if (
            rev_up
            and profit_up
            and delta.margin_change >= -self.margin_compression_points
        ):
            out.append(
                ProfitInsight(
                    game_id=current.game_id,
                    kind="healthy_scaling",
                    summary=(
                        f"Revenue {delta.revenue_pct:+.1f}% and profit "
                        f"{(delta.profit_pct or 0):+.1f}% with stable margin — "
                        f"healthy, scalable growth."
                    ),
                    evidence={
                        "revenue_pct": delta.revenue_pct,
                        "profit_pct": delta.profit_pct,
                        "margin_change": round(delta.margin_change, 4),
                    },
                    confidence=0.85,
                    severity="info",
                )
            )

        return out
