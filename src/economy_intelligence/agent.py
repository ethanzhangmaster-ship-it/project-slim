"""
E16.2 — Economy Intelligence Agent: the orchestrator.

The "AI Game Economy Designer": turns raw economy facts into gated,
executor-ready decisions.

    Player Behavior -> Economy Analysis -> Monetization Insight
        -> Offer/Price/Economy GrowthAction -> Economy Simulation gate
        -> Decision Validator (E16.1 confidence gate)
        -> Growth Executor sink / human queue / record-only
        -> Revenue Feedback -> Economy Memory (experience + patterns)

E16.2 never executes anything itself: every recommendation flows through the
same ``DecisionValidator`` as the Revenue Brain (E16.1), forming the dual-core
``Revenue Brain + Economy Brain`` system.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.revenue_intelligence.decision.policy import (
    DecisionPolicy,
    ImpactLevel,
    RiskLevel,
)
from src.revenue_intelligence.decision.validator import (
    DecisionValidator,
    GrowthDecision,
    JsonlApprovalQueue,
)
from src.revenue_intelligence.experience import RevenueExperience
from src.revenue_intelligence.models import GrowthAction, GrowthActionSink

from .funnel_analyzer import FunnelAnalyzer
from .memory import EconomyMemory
from .models import (
    EconomyAction,
    EconomyInsight,
    EconomyInsightType,
    EconomyReport,
    PlayerEconomySnapshot,
    ProductOffer,
    PurchaseFunnel,
)
from .offer_optimizer import OfferOptimizer
from .payer_analysis import PayerAnalyzer
from .price_strategy import PriceStrategyAgent
from .simulator import (
    EconomySimulationProvider,
    EconomySimulationResult,
    EconomySimulator,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# Economy risk / impact extensions for the shared DecisionPolicy.
ECONOMY_RISK: Dict[str, RiskLevel] = {
    EconomyAction.CREATE_OFFER.value: RiskLevel.LOW,
    EconomyAction.MODIFY_PRICE.value: RiskLevel.HIGH,
    EconomyAction.MODIFY_REWARD.value: RiskLevel.MEDIUM,
    EconomyAction.MODIFY_RESOURCE_RATE.value: RiskLevel.HIGH,
    EconomyAction.MODIFY_SHOP_ORDER.value: RiskLevel.LOW,
    EconomyAction.REMOVE_BAD_OFFER.value: RiskLevel.LOW,
}
ECONOMY_IMPACT: Dict[str, ImpactLevel] = {
    EconomyAction.CREATE_OFFER.value: ImpactLevel.HIGH,
    EconomyAction.MODIFY_PRICE.value: ImpactLevel.HIGH,
    EconomyAction.MODIFY_REWARD.value: ImpactLevel.MEDIUM,
    EconomyAction.MODIFY_RESOURCE_RATE.value: ImpactLevel.HIGH,
    EconomyAction.MODIFY_SHOP_ORDER.value: ImpactLevel.LOW,
    EconomyAction.REMOVE_BAD_OFFER.value: ImpactLevel.LOW,
}

# insight type -> (action, magnitude_pct) recommendation mapping.
_INSIGHT_ACTION: Dict[EconomyInsightType, tuple] = {
    EconomyInsightType.PAYWALL_DETECTED: (EconomyAction.CREATE_OFFER, 10.0),
    EconomyInsightType.PRICE_TOO_HIGH: (EconomyAction.MODIFY_PRICE, -20.0),
    EconomyInsightType.PRICE_TOO_LOW: (EconomyAction.MODIFY_PRICE, 20.0),
    EconomyInsightType.OFFER_WINNER: (EconomyAction.MODIFY_SHOP_ORDER, 10.0),
    EconomyInsightType.OFFER_FAILURE: (EconomyAction.REMOVE_BAD_OFFER, 10.0),
    EconomyInsightType.RESOURCE_SHORTAGE: (EconomyAction.CREATE_OFFER, 10.0),
    EconomyInsightType.RESOURCE_SURPLUS: (
        EconomyAction.MODIFY_RESOURCE_RATE,
        -15.0,
    ),
    EconomyInsightType.PAYER_SEGMENT_CHANGE: (
        EconomyAction.CREATE_OFFER,
        10.0,
    ),
}


@dataclass
class EconomyDecisionReport:
    """One full analyze -> decide run, with the gate results."""

    report: EconomyReport
    decisions: List[GrowthDecision] = field(default_factory=list)
    rejected_by_simulation: List[Dict[str, Any]] = field(default_factory=list)
    generated_at: datetime = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report": self.report.to_dict(),
            "decisions": [d.to_dict() for d in self.decisions],
            "rejected_by_simulation": self.rejected_by_simulation,
            "generated_at": self.generated_at.isoformat(),
        }

    def to_markdown(self) -> str:
        lines = [self.report.to_markdown()]
        if self.decisions:
            lines.append("## Gated Decisions")
            for d in self.decisions:
                status = (
                    "executed"
                    if d.executed
                    else ("queued" if d.queued else "recorded")
                )
                lines.append(
                    f"- {getattr(d.action.action, 'value', d.action.action)} "
                    f"[{d.approval.value}] -> {status}"
                )
            lines.append("")
        if self.rejected_by_simulation:
            lines.append("## Rejected by Simulation")
            for r in self.rejected_by_simulation:
                lines.append(f"- {r.get('action')}: {r.get('reason')}")
            lines.append("")
        return "\n".join(lines)


class EconomyIntelligenceAgent:
    """Orchestrates analyzers, simulator, gate and memory."""

    def __init__(
        self,
        simulator: Optional[EconomySimulationProvider] = None,
        memory: Optional[EconomyMemory] = None,
        action_sink: Optional[GrowthActionSink] = None,
        approval_queue: Optional[JsonlApprovalQueue] = None,
        audit_path: Optional[str] = None,
        policy: Optional[DecisionPolicy] = None,
    ):
        self.payer_analyzer = PayerAnalyzer()
        self.funnel_analyzer = FunnelAnalyzer()
        self.offer_optimizer = OfferOptimizer()
        self.price_strategy = PriceStrategyAgent()
        self.simulator: EconomySimulationProvider = simulator or EconomySimulator()
        self.memory = memory
        self.policy = policy or DecisionPolicy(
            extra_risk=ECONOMY_RISK, extra_impact=ECONOMY_IMPACT
        )
        self.validator = DecisionValidator(
            policy=self.policy,
            action_sink=action_sink,
            approval_queue=approval_queue,
            audit_path=audit_path,
        )

    # ------------------------------------------------------------------ #
    def analyze(
        self,
        snapshot: PlayerEconomySnapshot,
        funnel: Optional[PurchaseFunnel] = None,
        offers: Optional[List[ProductOffer]] = None,
    ) -> EconomyReport:
        """Pure analysis: facts -> insights -> recommended GrowthActions."""
        insights: List[EconomyInsight] = []
        insights.extend(self.payer_analyzer.analyze(snapshot))
        insights.extend(self.funnel_analyzer.analyze_resources(snapshot))
        if funnel is not None:
            insights.extend(self.funnel_analyzer.analyze_funnel(funnel))
        if offers:
            insights.extend(self.offer_optimizer.analyze(snapshot.game_id, offers))
            insights.extend(self.price_strategy.diagnose(snapshot.game_id, offers))

        # dedupe insight types keeping the highest-confidence instance
        best: Dict[EconomyInsightType, EconomyInsight] = {}
        for ins in insights:
            cur = best.get(ins.insight_type)
            if cur is None or ins.confidence > cur.confidence:
                best[ins.insight_type] = ins
        insights = sorted(
            best.values(), key=lambda i: i.impact_score, reverse=True
        )

        actions = [self._to_action(ins) for ins in insights]
        actions = [a for a in actions if a is not None]

        summary = self._summarize(snapshot, insights)
        return EconomyReport(
            game_id=snapshot.game_id,
            date=snapshot.date,
            snapshot=snapshot,
            funnel=funnel,
            offers=offers or [],
            insights=insights,
            actions=actions,
            summary=summary,
        )

    # ------------------------------------------------------------------ #
    def analyze_and_decide(
        self,
        snapshot: PlayerEconomySnapshot,
        funnel: Optional[PurchaseFunnel] = None,
        offers: Optional[List[ProductOffer]] = None,
    ) -> EconomyDecisionReport:
        """Full loop: analyze, simulate every action, gate the survivors."""
        report = self.analyze(snapshot, funnel, offers)
        decisions: List[GrowthDecision] = []
        rejected: List[Dict[str, Any]] = []

        for action in report.actions:
            magnitude = float(action.evidence.get("magnitude_pct", 10.0))
            stats = self._stats(action)
            sim = self.simulator.simulate(
                action.action,
                snapshot,
                magnitude_pct=magnitude,
                experience_stats=stats,
            )
            if not sim.recommended:
                rejected.append(
                    {
                        "action": getattr(action.action, "value", action.action),
                        "title": action.title,
                        "reason": sim.reason,
                        "simulation": sim.to_dict(),
                    }
                )
                continue
            decisions.append(
                self.validator.validate(
                    action, simulation=sim, experience_stats=stats
                )
            )
        return EconomyDecisionReport(
            report=report,
            decisions=decisions,
            rejected_by_simulation=rejected,
        )

    # ------------------------------------------------------------------ #
    def decide_action(
        self,
        action: GrowthAction,
        snapshot: PlayerEconomySnapshot,
        magnitude_pct: float = 10.0,
    ) -> Optional[GrowthDecision]:
        """Gate a single externally-built economy action (None = sim-rejected)."""
        stats = self._stats(action)
        sim = self.simulator.simulate(
            action.action,
            snapshot,
            magnitude_pct=magnitude_pct,
            experience_stats=stats,
        )
        if not sim.recommended:
            return None
        return self.validator.validate(
            action, simulation=sim, experience_stats=stats
        )

    # ------------------------------------------------------------------ #
    def record_outcome(
        self,
        game_id: str,
        action: EconomyAction,
        reason: str,
        before_revenue: float,
        after_revenue: float,
    ) -> Optional[RevenueExperience]:
        """Close the loop: outcome -> experience store + pattern memory."""
        if self.memory is None:
            return None
        return self.memory.record_outcome(
            game_id, action, reason, before_revenue, after_revenue
        )

    # ------------------------------------------------------------------ #
    def _stats(self, action: GrowthAction) -> Dict[str, Any]:
        if self.memory is None:
            return {}
        return self.memory.experience_store.stats(
            action.game_id, action.action
        )

    @staticmethod
    def _to_action(ins: EconomyInsight) -> Optional[GrowthAction]:
        mapping = _INSIGHT_ACTION.get(ins.insight_type)
        if mapping is None:
            return None
        action_enum, magnitude = mapping
        evidence = dict(ins.evidence)
        evidence["insight_type"] = ins.insight_type.value
        evidence["magnitude_pct"] = magnitude
        return GrowthAction(
            game_id=ins.game_id,
            action=action_enum,
            title=ins.description[:120],
            rationale=ins.description,
            evidence=evidence,
            confidence=ins.confidence,
            impact_score=ins.impact_score,
            source="economy_intelligence",
        )

    @staticmethod
    def _summarize(
        s: PlayerEconomySnapshot, insights: List[EconomyInsight]
    ) -> str:
        if not insights:
            return (
                f"Economy healthy: conv {s.payer_conversion:.2%}, "
                f"ARPPU ${s.arppu:.2f}, no structural issues detected."
            )
        top = insights[0]
        return (
            f"{len(insights)} economy issue(s) detected; top: "
            f"[{top.insight_type.value}] {top.description}"
        )


__all__ = [
    "EconomyIntelligenceAgent",
    "EconomyDecisionReport",
    "ECONOMY_RISK",
    "ECONOMY_IMPACT",
]
