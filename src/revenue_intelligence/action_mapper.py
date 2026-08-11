"""
E16.1 — Action Mapper

Translates insights + delta into unified ``GrowthAction`` objects (carrying a
``RevenueAction``) that the E13.3 Growth Decision Executor can route uniformly
with actions from other Brain agents. This module only *recommends* — it never
executes. Execution is the Executor's job via the ``GrowthActionSink`` seam.

Deterministic rule map. Duplicate actions are de-duplicated, keeping the
highest business-impact candidate.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from .models import (
    GrowthAction,
    InsightType,
    PatternMatch,
    RevenueAction,
    RevenueDelta,
    RevenueInsight,
    RevenueSnapshot,
)

# ROAS at/above which scaling UA is considered safe
ROAS_SCALE_THRESHOLD = 1.2


class ActionMapper:
    """Maps analytics output to a de-duplicated list of GrowthActions."""

    def map(
        self,
        current: RevenueSnapshot,
        previous: RevenueSnapshot,
        delta: RevenueDelta,
        insights: List[RevenueInsight],
        patterns: Optional[List[PatternMatch]] = None,
    ) -> List[GrowthAction]:
        types = {i.insight_type for i in insights}
        candidates: List[GrowthAction] = []

        # 1) UA budget direction
        candidates += self._ua_budget(current, delta)

        # 2) decline triage
        if InsightType.REVENUE_DECLINE in types:
            if InsightType.VERSION_IMPACT in types:
                candidates.append(
                    self._mk(
                        current,
                        RevenueAction.ROLLBACK_VERSION,
                        "Roll back recent app version",
                        "Revenue declined after a version change; revert to "
                        "last known-good build and A/B the regression.",
                        {"version": current.version},
                        confidence=0.6,
                        impact_score=70.0,
                    )
                )
            else:
                candidates.append(
                    self._mk(
                        current,
                        RevenueAction.INVESTIGATE_RETENTION,
                        "Investigate revenue decline",
                        "Revenue down without a version change; diagnose "
                        "retention / monetization leak before spending more.",
                        {"revenue_total_pct": delta.revenue_total_pct},
                        confidence=0.7,
                        impact_score=60.0,
                    )
                )

        # 3) retention
        if InsightType.RETENTION_CHANGE in types:
            candidates.append(
                self._mk(
                    current,
                    RevenueAction.INVESTIGATE_RETENTION,
                    "Investigate retention drop",
                    "A retention cohort moved beyond threshold; retention is a "
                    "leading driver of LTV and revenue.",
                    {
                        k: v
                        for k, v in delta.to_dict().items()
                        if k.startswith("retention")
                    },
                    confidence=0.75,
                    impact_score=65.0,
                )
            )

        # 4) monetization
        if InsightType.MONETIZATION_CHANGE in types:
            if delta.arppu_pct is not None and delta.arppu_pct < 0:
                candidates.append(
                    self._mk(
                        current,
                        RevenueAction.MODIFY_PRICE,
                        "Review price / offer",
                        "ARPPPU declined; test price points or a fresh offer "
                        "to recover per-payer value.",
                        {"arppu_pct": delta.arppu_pct},
                        confidence=0.6,
                        impact_score=55.0,
                    )
                )
            else:
                candidates.append(
                    self._mk(
                        current,
                        RevenueAction.SCALE_FEATURE,
                        "Scale winning monetization",
                        "Monetization is improving; scale the winning format / "
                        "offer to more segments.",
                        {"arppu_pct": delta.arppu_pct},
                        confidence=0.6,
                        impact_score=55.0,
                    )
                )

        # 5) growth → scale
        if InsightType.REVENUE_GROWTH in types and InsightType.UA_EFFICIENCY not in types:
            if (delta.dau_pct or 0) > 0:
                candidates.append(
                    self._mk(
                        current,
                        RevenueAction.SCALE_FEATURE,
                        "Scale the growth engine",
                        "Revenue and audience are growing organically; double "
                        "down on the product/store levers driving it.",
                        {"dau_pct": delta.dau_pct},
                        confidence=0.6,
                        impact_score=50.0,
                    )
                )

        # 6) historical patterns → recommended action
        for p in patterns or []:
            if p.recommended_action is not None and p.confidence >= 0.4:
                candidates.append(
                    self._mk(
                        current,
                        p.recommended_action,
                        f"Apply historical pattern: {p.similar_case or p.pattern_id}",
                        p.recommended_strategy
                        or f"Similar past case suggests {p.recommended_action.value}.",
                        {"pattern_id": p.pattern_id, "confidence": p.confidence},
                        confidence=p.confidence,
                        impact_score=round(p.confidence * 80.0, 2),
                    )
                )

        return self._dedup(candidates)

    # ------------------------------------------------------------------ #
    def _ua_budget(
        self, current: RevenueSnapshot, delta: RevenueDelta
    ) -> List[GrowthAction]:
        sp = delta.spend_pct
        rev_pct = delta.revenue_total_pct
        out: List[GrowthAction] = []
        if current.roas >= ROAS_SCALE_THRESHOLD and (sp is None or sp >= 0) and (
            rev_pct is None or rev_pct >= 0
        ):
            out.append(
                self._mk(
                    current,
                    RevenueAction.INCREASE_UA_BUDGET,
                    "Increase UA budget",
                    f"ROAS is healthy at {current.roas:.2f}; scale acquisition "
                    "to capture more efficiently-acquired volume.",
                    {"roas": current.roas, "spend_pct": sp},
                    confidence=0.75,
                    impact_score=80.0,
                )
            )
        elif sp is not None and sp > 0 and delta.roas_pct is not None and delta.roas_pct < 0:
            out.append(
                self._mk(
                    current,
                    RevenueAction.DECREASE_UA_BUDGET,
                    "Decrease / re-target UA budget",
                    "UA spend rose but ROAS fell; pull back or re-target the "
                    "underperforming channels.",
                    {"spend_pct": sp, "roas_pct": delta.roas_pct},
                    confidence=0.7,
                    impact_score=70.0,
                )
            )
        return out

    @staticmethod
    def _mk(
        current: RevenueSnapshot,
        action: RevenueAction,
        title: str,
        rationale: str,
        evidence: dict,
        confidence: float,
        impact_score: float,
    ) -> GrowthAction:
        return GrowthAction(
            game_id=current.game_id,
            action=action,
            title=title,
            rationale=rationale,
            evidence=evidence,
            confidence=round(confidence, 4),
            impact_score=round(impact_score, 2),
            source="revenue_intelligence",
        )

    @staticmethod
    def _dedup(candidates: List[GrowthAction]) -> List[GrowthAction]:
        best: Dict[RevenueAction, GrowthAction] = {}
        for c in candidates:
            prev = best.get(c.action)
            if prev is None or c.impact_score > prev.impact_score:
                best[c.action] = c
        # stable order by impact (desc)
        return sorted(best.values(), key=lambda a: a.impact_score, reverse=True)


__all__ = ["ActionMapper", "ROAS_SCALE_THRESHOLD"]
