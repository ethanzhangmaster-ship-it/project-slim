"""
E16.1 — Revenue Intelligence Agent: data models & integration seams.

Pure data definitions only. No I/O, no external imports, no side effects.
This module is the contract that the rest of the agent (and the existing
E11–E15 infrastructure) speaks through:

* ``RevenueSnapshot`` / ``RevenueDelta``  — the facts & the change
* ``RevenueInsight`` / ``InsightType``    — the "what happened" explanation
* ``AttributionFactor`` / ``AttributionBreakdown`` — the "why" decomposition
* ``PatternMatch``                        — historical precedent (E13.4)
* ``GrowthAction`` / ``RevenueAction``    — the "what to do next" (→ E13.3)
* ``RevenueReport``                       — the unified output

Three ``Protocol`` seams define how this agent plugs into the rest of the
system without hard dependencies:

* ``RevenueDataSource`` — where current/previous facts come from
* ``PatternMemory``     — E13.4 Growth Memory (historical cases)
* ``GrowthActionSink``  — E13.3 Growth Decision Executor entry point
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# 1. Facts
# --------------------------------------------------------------------------- #
@dataclass
class RevenueSnapshot:
    """One period of revenue reality for a single game.

    13 canonical business fields + ``version`` (for VERSION_IMPACT) and a free
    ``extra`` bag for source-specific signals that downstream agents may use.
    """

    game_id: str
    date: str  # period label, e.g. "2026-07-27" or "2026-W30"

    # --- revenue ---
    revenue_total: float = 0.0
    iap_revenue: float = 0.0
    ad_revenue: float = 0.0

    # --- acquisition / efficiency ---
    spend: float = 0.0
    roas: float = 0.0  # revenue_total / spend

    # --- players ---
    payer_count: int = 0
    payer_conversion: float = 0.0  # payer_count / dau
    arppu: float = 0.0  # iap_revenue / payer_count

    # --- audience ---
    dau: int = 0

    # --- retention (cohort) ---
    retention_d1: float = 0.0
    retention_d7: float = 0.0
    retention_d30: float = 0.0

    # --- provenance ---
    version: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "date": self.date,
            "revenue_total": round(self.revenue_total, 4),
            "iap_revenue": round(self.iap_revenue, 4),
            "ad_revenue": round(self.ad_revenue, 4),
            "spend": round(self.spend, 4),
            "roas": round(self.roas, 4),
            "payer_count": self.payer_count,
            "payer_conversion": round(self.payer_conversion, 4),
            "arppu": round(self.arppu, 4),
            "dau": self.dau,
            "retention_d1": round(self.retention_d1, 4),
            "retention_d7": round(self.retention_d7, 4),
            "retention_d30": round(self.retention_d30, 4),
            "version": self.version,
            "extra": self.extra,
        }


@dataclass
class RevenueDelta:
    """Period-over-period % change for every metric in ``RevenueSnapshot``.

    A ``None`` means the metric was not comparable (previous value was 0 / missing).
    ``revenue_total_abs`` carries the absolute delta for convenience.
    """

    game_id: str
    current_date: str
    previous_date: str

    revenue_total_pct: Optional[float] = None
    iap_revenue_pct: Optional[float] = None
    ad_revenue_pct: Optional[float] = None
    spend_pct: Optional[float] = None
    roas_pct: Optional[float] = None
    payer_count_pct: Optional[float] = None
    payer_conversion_pct: Optional[float] = None
    arppu_pct: Optional[float] = None
    dau_pct: Optional[float] = None
    retention_d1_pct: Optional[float] = None
    retention_d7_pct: Optional[float] = None
    retention_d30_pct: Optional[float] = None

    revenue_total_abs: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "current_date": self.current_date,
            "previous_date": self.previous_date,
            "revenue_total_pct": self.revenue_total_pct,
            "iap_revenue_pct": self.iap_revenue_pct,
            "ad_revenue_pct": self.ad_revenue_pct,
            "spend_pct": self.spend_pct,
            "roas_pct": self.roas_pct,
            "payer_count_pct": self.payer_count_pct,
            "payer_conversion_pct": self.payer_conversion_pct,
            "arppu_pct": self.arppu_pct,
            "dau_pct": self.dau_pct,
            "retention_d1_pct": self.retention_d1_pct,
            "retention_d7_pct": self.retention_d7_pct,
            "retention_d30_pct": self.retention_d30_pct,
            "revenue_total_abs": round(self.revenue_total_abs, 4),
        }


# --------------------------------------------------------------------------- #
# 2. Insights
# --------------------------------------------------------------------------- #
class InsightType(str, Enum):
    REVENUE_GROWTH = "revenue_growth"
    REVENUE_DECLINE = "revenue_decline"
    UA_EFFICIENCY = "ua_efficiency"
    MONETIZATION_CHANGE = "monetization_change"
    RETENTION_CHANGE = "retention_change"
    VERSION_IMPACT = "version_impact"


@dataclass
class RevenueInsight:
    """A single explained observation about the revenue change."""

    game_id: str
    insight_type: InsightType
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
# 3. Attribution (the "why")
# --------------------------------------------------------------------------- #
@dataclass
class AttributionFactor:
    """One driver's share of the total revenue change."""

    name: str  # "ua" | "product" | "monetization" | "seasonality" | "noise"
    contribution_pct: float  # share of total change, weights sum to 100%
    absolute: float = 0.0  # absolute revenue contribution
    description: str = ""
    confidence: float = 0.0  # 0.0–1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "contribution_pct": round(self.contribution_pct, 2),
            "absolute": round(self.absolute, 4),
            "description": self.description,
            "confidence": round(self.confidence, 4),
        }


@dataclass
class AttributionBreakdown:
    """Full decomposition of a revenue change into named drivers."""

    game_id: str
    revenue_change_abs: float
    revenue_change_pct: Optional[float]
    total_revenue_current: float
    total_revenue_previous: float
    factors: List[AttributionFactor] = field(default_factory=list)

    def dominant(self) -> Optional[AttributionFactor]:
        if not self.factors:
            return None
        return max(self.factors, key=lambda f: abs(f.contribution_pct))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "revenue_change_abs": round(self.revenue_change_abs, 4),
            "revenue_change_pct": self.revenue_change_pct,
            "total_revenue_current": round(self.total_revenue_current, 4),
            "total_revenue_previous": round(self.total_revenue_previous, 4),
            "factors": [f.to_dict() for f in self.factors],
            "dominant_factor": self.dominant().name if self.dominant() else None,
        }


# --------------------------------------------------------------------------- #
# 4. Pattern memory (E13.4)
# --------------------------------------------------------------------------- #
@dataclass
class PatternMatch:
    """A historical precedent returned by the Growth Memory."""

    pattern_id: str
    description: str
    confidence: float  # 0.0–1.0
    similar_case: str = ""  # historical case id / label
    recommended_action: Optional["RevenueAction"] = None
    recommended_strategy: str = ""
    source: str = "growth_memory"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "description": self.description,
            "confidence": round(self.confidence, 4),
            "similar_case": self.similar_case,
            "recommended_action": getattr(
                self.recommended_action, "value", self.recommended_action
            )
            if self.recommended_action
            else None,
            "recommended_strategy": self.recommended_strategy,
            "source": self.source,
        }


# --------------------------------------------------------------------------- #
# 5. Actions (the "what to do") — feed E13.3 Growth Decision Executor
# --------------------------------------------------------------------------- #
class RevenueAction(str, Enum):
    INCREASE_UA_BUDGET = "increase_ua_budget"
    DECREASE_UA_BUDGET = "decrease_ua_budget"
    CREATE_OFFER = "create_offer"
    MODIFY_PRICE = "modify_price"
    INVESTIGATE_RETENTION = "investigate_retention"
    ROLLBACK_VERSION = "rollback_version"
    SCALE_FEATURE = "scale_feature"


# Registry of action enums that a GrowthAction may carry. Other "Brain"
# packages (e.g. E16.2 economy_intelligence) register their own str-Enum here
# at import time so ``GrowthAction.from_dict`` can round-trip them without a
# reverse dependency.
_ACTION_ENUMS: List[type] = [RevenueAction]


def register_action_enum(enum_cls: type) -> None:
    """Register an additional str-Enum whose members may appear as
    ``GrowthAction.action`` (called by sibling Brain packages)."""
    if enum_cls not in _ACTION_ENUMS:
        _ACTION_ENUMS.append(enum_cls)


def resolve_action(value: Any) -> Any:
    """Resolve a raw action value against all registered action enums.

    Falls back to the raw string so that persisted actions from newer /
    unknown Brain packages never crash deserialization.
    """
    if isinstance(value, Enum):
        return value
    for enum_cls in _ACTION_ENUMS:
        try:
            return enum_cls(value)
        except (ValueError, TypeError):
            continue
    return value  # tolerant fallback: keep the raw string


@dataclass
class GrowthAction:
    """A unified, executor-ready action emitted by a Brain agent.

    ``action`` is a str-Enum — typically ``RevenueAction`` (E16.1) or
    ``EconomyAction`` (E16.2) — so the E13.3 Growth Decision Executor can
    route actions from all Brain agents uniformly.
    """

    game_id: str
    action: Any  # str-Enum member (RevenueAction / EconomyAction / ...)
    title: str
    rationale: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0  # 0.0–1.0
    impact_score: float = 0.0  # 0.0–100.0
    source: str = "revenue_intelligence"
    created_at: datetime = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "action": getattr(self.action, "value", self.action),
            "title": self.title,
            "rationale": self.rationale,
            "evidence": self.evidence,
            "confidence": round(self.confidence, 4),
            "impact_score": round(self.impact_score, 2),
            "source": self.source,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GrowthAction":
        created_at = d.get("created_at")
        if created_at:
            try:
                created_at = datetime.fromisoformat(created_at)
            except Exception:
                created_at = _now()
        else:
            created_at = _now()
        return cls(
            game_id=d["game_id"],
            action=resolve_action(d["action"]),
            title=d.get("title", ""),
            rationale=d.get("rationale", ""),
            evidence=d.get("evidence", {}),
            confidence=float(d.get("confidence", 0.0)),
            impact_score=float(d.get("impact_score", 0.0)),
            source=d.get("source", "revenue_intelligence"),
            created_at=created_at,
        )


# --------------------------------------------------------------------------- #
# 6. Report
# --------------------------------------------------------------------------- #
@dataclass
class RevenueReport:
    game_id: str
    current_date: str
    previous_date: str
    generated_at: datetime = field(default_factory=_now)
    delta: Optional[RevenueDelta] = None
    attribution: Optional[AttributionBreakdown] = None
    insights: List[RevenueInsight] = field(default_factory=list)
    patterns: List[PatternMatch] = field(default_factory=list)
    actions: List[GrowthAction] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "current_date": self.current_date,
            "previous_date": self.previous_date,
            "generated_at": self.generated_at.isoformat(),
            "delta": self.delta.to_dict() if self.delta else None,
            "attribution": self.attribution.to_dict() if self.attribution else None,
            "insights": [i.to_dict() for i in self.insights],
            "patterns": [p.to_dict() for p in self.patterns],
            "actions": [a.to_dict() for a in self.actions],
            "summary": self.summary,
        }

    def to_markdown(self) -> str:
        lines = [
            f"# Revenue Intelligence — {self.game_id}",
            f"Period: {self.previous_date} → {self.current_date}",
            "",
        ]
        if self.summary:
            lines += [self.summary, ""]
        if self.delta:
            pct = self.delta.revenue_total_pct
            arrow = "▲" if (pct or 0) >= 0 else "▼"
            lines.append(
                f"## Revenue Δ: {arrow} {pct:+.1f}% "
                f"({self.delta.revenue_total_abs:+.0f})"
                if pct is not None
                else "## Revenue Δ: n/a"
            )
            lines.append("")
        if self.attribution:
            lines.append("## Attribution")
            for f in self.attribution.factors:
                lines.append(f"- {f.name}: {f.contribution_pct:+.1f}%")
            lines.append("")
        if self.insights:
            lines.append("## Insights")
            for i in self.insights:
                lines.append(
                    f"- [{i.insight_type.value}] {i.description} "
                    f"(conf {i.confidence:.0%})"
                )
            lines.append("")
        if self.patterns:
            lines.append("## Historical Patterns")
            for p in self.patterns:
                lines.append(
                    f"- {p.description} (similar: {p.similar_case or '—'}, "
                    f"conf {p.confidence:.0%})"
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
# 7. Integration seams (Protocols) — no hard dependencies
# --------------------------------------------------------------------------- #
@runtime_checkable
class RevenueDataSource(Protocol):
    """Supplies current/previous revenue facts for a game."""

    def load_snapshot(self, game_id: str, period: str) -> RevenueSnapshot:
        ...


@runtime_checkable
class PatternMemory(Protocol):
    """E13.4 Growth Memory: historical cases for a given signal."""

    def search_similar(
        self, game_id: str, signal: Dict[str, Any], limit: int = 3
    ) -> List[PatternMatch]:
        ...


@runtime_checkable
class GrowthActionSink(Protocol):
    """E13.3 Growth Decision Executor entry point."""

    def submit(self, action: GrowthAction) -> bool:
        ...


__all__ = [
    "RevenueSnapshot",
    "RevenueDelta",
    "InsightType",
    "RevenueInsight",
    "AttributionFactor",
    "AttributionBreakdown",
    "PatternMatch",
    "RevenueAction",
    "register_action_enum",
    "resolve_action",
    "GrowthAction",
    "RevenueReport",
    "RevenueDataSource",
    "PatternMemory",
    "GrowthActionSink",
]
