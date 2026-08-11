"""
E16.2 — Economy Intelligence Agent: data models.

The "AI Game Economy Designer + Monetization Strategist" answers:

* Why don't players pay?          -> PayerAnalyzer / FunnelAnalyzer
* Which products should we sell?  -> OfferOptimizer
* At what price?                  -> PriceStrategyAgent
* When / to whom?                 -> EconomyInsight evidence
* How to grow IAP LTV?            -> EconomySimulator + GrowthAction loop

Pure data definitions only — no I/O, no side effects. E16.2 depends one-way on
E16.1 (``revenue_intelligence``): it emits standard ``GrowthAction`` objects
(carrying ``EconomyAction`` enum members) into the same Decision Validator /
Growth Executor pipeline, forming the second Brain of the dual-core
``Revenue Brain + Economy Brain`` system.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from src.revenue_intelligence.models import (
    GrowthAction,
    register_action_enum,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# 1. Enums
# --------------------------------------------------------------------------- #
class EconomyInsightType(str, Enum):
    PAYWALL_DETECTED = "paywall_detected"
    PRICE_TOO_HIGH = "price_too_high"
    PRICE_TOO_LOW = "price_too_low"
    OFFER_WINNER = "offer_winner"
    OFFER_FAILURE = "offer_failure"
    RESOURCE_SHORTAGE = "resource_shortage"
    RESOURCE_SURPLUS = "resource_surplus"
    PAYER_SEGMENT_CHANGE = "payer_segment_change"


class EconomyAction(str, Enum):
    CREATE_OFFER = "economy_create_offer"
    MODIFY_PRICE = "economy_modify_price"
    MODIFY_REWARD = "economy_modify_reward"
    MODIFY_RESOURCE_RATE = "economy_modify_resource_rate"
    MODIFY_SHOP_ORDER = "economy_modify_shop_order"
    REMOVE_BAD_OFFER = "economy_remove_bad_offer"


# Register with E16.1 so GrowthAction.from_dict / JsonlPatternMemory can
# round-trip economy actions through the shared JSONL stores.
register_action_enum(EconomyAction)


# --------------------------------------------------------------------------- #
# 2. Player economy state
# --------------------------------------------------------------------------- #
@dataclass
class PlayerEconomySnapshot:
    """One period of in-game economy reality for a single game."""

    game_id: str
    date: str  # period label, e.g. "2026-07-28"

    # --- audience & payers ---
    dau: int = 0
    payer_count: int = 0
    payer_conversion: float = 0.0  # payer_count / dau
    first_time_payer_share: float = 0.0  # share of payers who paid first time
    repeat_payer_share: float = 0.0  # share of payers with 2+ purchases

    # --- monetization depth ---
    arppu: float = 0.0
    purchase_frequency: float = 0.0  # purchases / payer / period
    avg_purchase_value: float = 0.0
    iap_revenue: float = 0.0

    # --- in-game economy health ---
    currency_balance_avg: float = 0.0  # avg soft-currency balance per player
    currency_earn_rate: float = 0.0  # earned per active player per period
    currency_spend_rate: float = 0.0  # spent per active player per period
    resource_shortage_rate: float = 0.0  # share of sessions hitting "not enough"
    level_progression: Dict[str, float] = field(default_factory=dict)
    # e.g. {"L5": 0.82, "L10": 0.61, "L25": 0.31} — share of installs reaching level

    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "date": self.date,
            "dau": self.dau,
            "payer_count": self.payer_count,
            "payer_conversion": round(self.payer_conversion, 4),
            "first_time_payer_share": round(self.first_time_payer_share, 4),
            "repeat_payer_share": round(self.repeat_payer_share, 4),
            "arppu": round(self.arppu, 4),
            "purchase_frequency": round(self.purchase_frequency, 4),
            "avg_purchase_value": round(self.avg_purchase_value, 4),
            "iap_revenue": round(self.iap_revenue, 4),
            "currency_balance_avg": round(self.currency_balance_avg, 4),
            "currency_earn_rate": round(self.currency_earn_rate, 4),
            "currency_spend_rate": round(self.currency_spend_rate, 4),
            "resource_shortage_rate": round(self.resource_shortage_rate, 4),
            "level_progression": self.level_progression,
            "extra": self.extra,
        }


# --------------------------------------------------------------------------- #
# 3. Products / Offers
# --------------------------------------------------------------------------- #
@dataclass
class ProductOffer:
    """One IAP product / offer being sold in the shop."""

    offer_id: str
    name: str
    price: float  # USD
    currency_amount: float = 0.0  # how much in-game value the pack grants
    bonus_value: float = 0.0  # extra % value vs baseline pack (e.g. 0.25)
    impressions: int = 0  # times shown
    purchase_count: int = 0
    conversion_rate: float = 0.0  # purchase_count / impressions
    revenue: float = 0.0
    segment: str = "all"  # target payer segment

    def to_dict(self) -> Dict[str, Any]:
        return {
            "offer_id": self.offer_id,
            "name": self.name,
            "price": round(self.price, 2),
            "currency_amount": round(self.currency_amount, 2),
            "bonus_value": round(self.bonus_value, 4),
            "impressions": self.impressions,
            "purchase_count": self.purchase_count,
            "conversion_rate": round(self.conversion_rate, 4),
            "revenue": round(self.revenue, 4),
            "segment": self.segment,
        }

    @property
    def value_per_dollar(self) -> float:
        if self.price <= 0:
            return 0.0
        return self.currency_amount * (1.0 + self.bonus_value) / self.price


# --------------------------------------------------------------------------- #
# 4. Purchase funnel
# --------------------------------------------------------------------------- #
@dataclass
class FunnelStage:
    """One step of the player -> payer journey."""

    name: str  # e.g. "install", "L5", "L10", "first_shortage", "offer_shown", "purchase"
    players: int = 0
    conversion_from_previous: Optional[float] = None  # None for the first stage
    drop_rate: Optional[float] = None  # 1 - conversion

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "players": self.players,
            "conversion_from_previous": self.conversion_from_previous,
            "drop_rate": self.drop_rate,
        }


@dataclass
class PurchaseFunnel:
    """The full Install -> ... -> Purchase funnel for one game/period."""

    game_id: str
    date: str
    stages: List[FunnelStage] = field(default_factory=list)

    def worst_stage(self) -> Optional[FunnelStage]:
        candidates = [s for s in self.stages if s.drop_rate is not None]
        if not candidates:
            return None
        return max(candidates, key=lambda s: s.drop_rate or 0.0)

    def to_dict(self) -> Dict[str, Any]:
        worst = self.worst_stage()
        return {
            "game_id": self.game_id,
            "date": self.date,
            "stages": [s.to_dict() for s in self.stages],
            "worst_stage": worst.name if worst else None,
        }


# --------------------------------------------------------------------------- #
# 5. Insights
# --------------------------------------------------------------------------- #
@dataclass
class EconomyInsight:
    """A single explained observation about the game economy."""

    game_id: str
    insight_type: EconomyInsightType
    description: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0  # 0.0–1.0
    impact_score: float = 0.0  # 0.0–100.0 (business materiality)
    generated_at: datetime = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "insight_type": self.insight_type.value,
            "description": self.description,
            "evidence": self.evidence,
            "confidence": round(self.confidence, 4),
            "impact_score": round(self.impact_score, 2),
            "generated_at": self.generated_at.isoformat(),
        }


# --------------------------------------------------------------------------- #
# 6. Price simulation output
# --------------------------------------------------------------------------- #
@dataclass
class RevenueImpactPrediction:
    """Predicted business impact of a price change (from PriceStrategyAgent)."""

    offer_id: str
    old_price: float
    new_price: float
    price_change_pct: float
    predicted_purchase_rate_change_pct: float
    predicted_revenue_change_pct: float
    confidence: float = 0.0
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "offer_id": self.offer_id,
            "old_price": round(self.old_price, 2),
            "new_price": round(self.new_price, 2),
            "price_change_pct": round(self.price_change_pct, 2),
            "predicted_purchase_rate_change_pct": round(
                self.predicted_purchase_rate_change_pct, 2
            ),
            "predicted_revenue_change_pct": round(
                self.predicted_revenue_change_pct, 2
            ),
            "confidence": round(self.confidence, 4),
            "note": self.note,
        }


# --------------------------------------------------------------------------- #
# 7. Report
# --------------------------------------------------------------------------- #
@dataclass
class EconomyReport:
    """Unified output of one Economy Intelligence run."""

    game_id: str
    date: str
    generated_at: datetime = field(default_factory=_now)
    snapshot: Optional[PlayerEconomySnapshot] = None
    funnel: Optional[PurchaseFunnel] = None
    offers: List[ProductOffer] = field(default_factory=list)
    insights: List[EconomyInsight] = field(default_factory=list)
    price_predictions: List[RevenueImpactPrediction] = field(default_factory=list)
    actions: List[GrowthAction] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "date": self.date,
            "generated_at": self.generated_at.isoformat(),
            "snapshot": self.snapshot.to_dict() if self.snapshot else None,
            "funnel": self.funnel.to_dict() if self.funnel else None,
            "offers": [o.to_dict() for o in self.offers],
            "insights": [i.to_dict() for i in self.insights],
            "price_predictions": [p.to_dict() for p in self.price_predictions],
            "actions": [a.to_dict() for a in self.actions],
            "summary": self.summary,
        }

    def to_markdown(self) -> str:
        lines = [
            f"# Economy Intelligence — {self.game_id}",
            f"Period: {self.date}",
            "",
        ]
        if self.summary:
            lines += [self.summary, ""]
        if self.snapshot:
            s = self.snapshot
            lines += [
                "## Economy State",
                f"- DAU {s.dau} | payers {s.payer_count} "
                f"(conv {s.payer_conversion:.2%})",
                f"- ARPPU ${s.arppu:.2f} | avg purchase ${s.avg_purchase_value:.2f}",
                f"- shortage rate {s.resource_shortage_rate:.0%} | "
                f"currency balance {s.currency_balance_avg:.0f}",
                "",
            ]
        if self.insights:
            lines.append("## Insights")
            for i in self.insights:
                lines.append(
                    f"- [{i.insight_type.value}] {i.description} "
                    f"(conf {i.confidence:.0%})"
                )
            lines.append("")
        if self.price_predictions:
            lines.append("## Price Simulations")
            for p in self.price_predictions:
                lines.append(
                    f"- {p.offer_id}: ${p.old_price:.2f} -> ${p.new_price:.2f} "
                    f"=> revenue {p.predicted_revenue_change_pct:+.1f}%"
                )
            lines.append("")
        if self.actions:
            lines.append("## Recommended Actions")
            for a in self.actions:
                lines.append(
                    f"- {getattr(a.action, 'value', a.action)}: {a.title}"
                )
            lines.append("")
        return "\n".join(lines)


# --------------------------------------------------------------------------- #
# 8. Integration seams
# --------------------------------------------------------------------------- #
@runtime_checkable
class EconomyDataSource(Protocol):
    """Supplies the current economy facts for a game."""

    def load_economy_snapshot(
        self, game_id: str, period: str
    ) -> PlayerEconomySnapshot:
        ...


__all__ = [
    "EconomyInsightType",
    "EconomyAction",
    "PlayerEconomySnapshot",
    "ProductOffer",
    "FunnelStage",
    "PurchaseFunnel",
    "EconomyInsight",
    "RevenueImpactPrediction",
    "EconomyReport",
    "EconomyDataSource",
]
