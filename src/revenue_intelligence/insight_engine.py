"""
E16.1 — Insight Engine

Turns the delta + attribution into human/business explanations. Six
deterministic insight types (no ML, no randomness):

    REVENUE_GROWTH    revenue_total up beyond threshold
    REVENUE_DECLINE   revenue_total down beyond threshold
    UA_EFFICIENCY     UA spend active, revenue/ROAS response measured
    MONETIZATION_CHANGE  ARPPPU or ad/IAP revenue mix shifted
    RETENTION_CHANGE  any cohort retention moved beyond threshold
    VERSION_IMPACT    app version changed between periods

Pure, deterministic, no I/O.
"""
from __future__ import annotations

from .models import (
    AttributionBreakdown,
    InsightType,
    RevenueDelta,
    RevenueInsight,
    RevenueSnapshot,
)

GROWTH_THRESHOLD = 5.0  # % revenue move to flag growth/decline
RETENTION_THRESHOLD = 3.0  # % retention move to flag
UA_ACTIVE_THRESHOLD = 5.0  # % spend move to consider UA "active"
MONETIZATION_THRESHOLD = 5.0  # % ARPPPU / mix shift to flag


class InsightEngine:
    """Generates a list of ``RevenueInsight`` from facts + delta + attribution."""

    def generate(
        self,
        current: RevenueSnapshot,
        previous: RevenueSnapshot,
        delta: RevenueDelta,
        attribution: AttributionBreakdown,
    ) -> list[RevenueInsight]:
        out: list[RevenueInsight] = []
        out += self._revenue_direction(current, delta)
        out += self._ua_efficiency(current, previous, delta)
        out += self._monetization(current, previous, delta)
        out += self._retention(current, delta)
        out += self._version(current, previous)
        return out

    # ------------------------------------------------------------------ #
    def _revenue_direction(
        self, current: RevenueSnapshot, delta: RevenueDelta
    ) -> list[RevenueInsight]:
        pct = delta.revenue_total_pct
        if pct is None:
            return []
        if pct >= GROWTH_THRESHOLD:
            return [
                RevenueInsight(
                    game_id=current.game_id,
                    insight_type=InsightType.REVENUE_GROWTH,
                    description=(
                        f"Revenue grew {pct:+.1f}% "
                        f"({delta.revenue_total_abs:+.0f}) vs previous period."
                    ),
                    evidence={
                        "revenue_total_pct": pct,
                        "revenue_total_abs": delta.revenue_total_abs,
                    },
                    confidence=round(min(0.95, 0.6 + abs(pct) / 200), 4),
                    impact_score=round(min(100.0, abs(pct) * 2), 2),
                )
            ]
        if pct <= -GROWTH_THRESHOLD:
            return [
                RevenueInsight(
                    game_id=current.game_id,
                    insight_type=InsightType.REVENUE_DECLINE,
                    description=(
                        f"Revenue declined {pct:+.1f}% "
                        f"({delta.revenue_total_abs:+.0f}) vs previous period."
                    ),
                    evidence={
                        "revenue_total_pct": pct,
                        "revenue_total_abs": delta.revenue_total_abs,
                    },
                    confidence=round(min(0.95, 0.6 + abs(pct) / 200), 4),
                    impact_score=round(min(100.0, abs(pct) * 2), 2),
                )
            ]
        return []

    def _ua_efficiency(
        self,
        current: RevenueSnapshot,
        previous: RevenueSnapshot,
        delta: RevenueDelta,
    ) -> list[RevenueInsight]:
        sp = delta.spend_pct
        if sp is None or abs(sp) < UA_ACTIVE_THRESHOLD:
            return []
        rev_pct = delta.revenue_total_pct or 0.0
        roas_pct = delta.roas_pct
        efficient = (rev_pct > sp) or (roas_pct is not None and roas_pct > 0)
        if efficient:
            desc = (
                f"UA scaling is efficient: spend {sp:+.1f}% drove revenue "
                f"{rev_pct:+.1f}% (ROAS {current.roas:.2f})."
            )
        else:
            desc = (
                f"UA efficiency declining: spend {sp:+.1f}% but revenue "
                f"{rev_pct:+.1f}% (ROAS {current.roas:.2f})."
            )
        return [
            RevenueInsight(
                game_id=current.game_id,
                insight_type=InsightType.UA_EFFICIENCY,
                description=desc,
                evidence={
                    "spend_pct": sp,
                    "revenue_total_pct": rev_pct,
                    "roas": current.roas,
                    "roas_pct": roas_pct,
                },
                confidence=0.7,
                impact_score=round(min(100.0, abs(sp) * 1.5), 2),
            )
        ]

    def _monetization(
        self,
        current: RevenueSnapshot,
        previous: RevenueSnapshot,
        delta: RevenueDelta,
    ) -> list[RevenueInsight]:
        signals = []
        if delta.arppu_pct is not None and abs(delta.arppu_pct) >= MONETIZATION_THRESHOLD:
            signals.append(("ARPPPU", delta.arppu_pct))
        prev_mix = (
            previous.ad_revenue / previous.revenue_total
            if previous.revenue_total
            else 0.0
        )
        cur_mix = (
            current.ad_revenue / current.revenue_total
            if current.revenue_total
            else 0.0
        )
        mix_shift = (cur_mix - prev_mix) * 100.0
        if abs(mix_shift) >= MONETIZATION_THRESHOLD:
            signals.append(("ad/IAP mix", round(mix_shift, 2)))
        if not signals:
            return []
        detail = ", ".join(f"{k} {v:+.1f}%" for k, v in signals)
        return [
            RevenueInsight(
                game_id=current.game_id,
                insight_type=InsightType.MONETIZATION_CHANGE,
                description=f"Monetization shifted: {detail}.",
                evidence={"arppu_pct": delta.arppu_pct, "mix_shift_pp": mix_shift},
                confidence=0.65,
                impact_score=round(min(100.0, max(abs(v) for _, v in signals) * 2), 2),
            )
        ]

    def _retention(
        self, current: RevenueSnapshot, delta: RevenueDelta
    ) -> list[RevenueInsight]:
        moves = []
        for label, pct in (
            ("D1", delta.retention_d1_pct),
            ("D7", delta.retention_d7_pct),
            ("D30", delta.retention_d30_pct),
        ):
            if pct is not None and abs(pct) >= RETENTION_THRESHOLD:
                moves.append((label, pct))
        if not moves:
            return []
        worst = max(moves, key=lambda m: abs(m[1]))
        return [
            RevenueInsight(
                game_id=current.game_id,
                insight_type=InsightType.RETENTION_CHANGE,
                description=(
                    f"Retention moved: "
                    + ", ".join(f"{l} {p:+.1f}%" for l, p in moves)
                    + f". Largest shift at {worst[0]} ({worst[1]:+.1f}%)."
                ),
                evidence={f"retention_{l.lower()}_pct": p for l, p in moves},
                confidence=0.75,
                impact_score=round(min(100.0, abs(worst[1]) * 2), 2),
            )
        ]

    def _version(
        self, current: RevenueSnapshot, previous: RevenueSnapshot
    ) -> list[RevenueInsight]:
        cv, pv = current.version, previous.version
        if cv is not None and cv != pv:
            return [
                RevenueInsight(
                    game_id=current.game_id,
                    insight_type=InsightType.VERSION_IMPACT,
                    description=(
                        f"App version changed ({pv or 'none'} → {cv}); "
                        f"revenue delta may be partly version-driven."
                    ),
                    evidence={"previous_version": pv, "current_version": cv},
                    confidence=0.6,
                    impact_score=50.0,
                )
            ]
        return []


__all__ = ["InsightEngine", "GROWTH_THRESHOLD", "RETENTION_THRESHOLD"]
