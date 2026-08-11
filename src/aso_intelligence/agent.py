"""
E16.6.1 — ASO Intelligence Agent: the orchestrator.

    Store data + Reviews + Competitors
        -> Keyword / Conversion / Listing / Competitor Analyzers
        -> ASOInsight list
        -> ASOActionMapper -> GrowthAction (action = ASOAction)
        -> DecisionValidator (E16.1 confidence gate, ASO risk/impact tables)
        -> Growth Executor sink / human queue / record-only
        -> Revenue/ASO feedback -> ASOMemory (experience + patterns)

The ASO Agent is the THIRD Brain (after Revenue E16.1 and Economy E16.2). It
never executes ASO changes itself — every recommendation flows through the
shared ``DecisionValidator`` so ASO moves are gated and audited exactly like
revenue/economy actions.
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
from src.revenue_intelligence.models import GrowthAction, GrowthActionSink

from .action_mapper import ASOActionMapper
from .analyzer import (
    CompetitorAnalyzer,
    ConversionAnalyzer,
    KeywordAnalyzer,
    ListingAnalyzer,
)
from .memory import ASOMemory
from .models import (
    ASOAction,
    ASOInsight,
    ASOReport,
    ASOSnapshot,
    CompetitorSnapshot,
)
from .reality.connector import ASORealityConnector
from .reality.models import ASODataQuality, ASORealitySnapshot

try:  # EP0.11.4 central audit (optional; no-op when not injected)
    from audit.integration import FlowAuditor
except ImportError:  # pragma: no cover - audit package not on path
    FlowAuditor = None  # type: ignore


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ASO risk / impact extensions for the shared DecisionPolicy. ASO moves are
# low-blast-radius (store metadata / creative tests) — none touch game logic.
ASO_RISK: Dict[str, RiskLevel] = {
    ASOAction.ADD_KEYWORD.value: RiskLevel.LOW,
    ASOAction.REMOVE_KEYWORD.value: RiskLevel.LOW,
    ASOAction.UPDATE_TITLE.value: RiskLevel.MEDIUM,
    ASOAction.UPDATE_DESCRIPTION.value: RiskLevel.LOW,
    ASOAction.UPDATE_SCREENSHOT.value: RiskLevel.MEDIUM,
    ASOAction.UPDATE_ICON.value: RiskLevel.MEDIUM,
    ASOAction.CREATE_EXPERIMENT.value: RiskLevel.LOW,
}
ASO_IMPACT: Dict[str, ImpactLevel] = {
    ASOAction.ADD_KEYWORD.value: ImpactLevel.MEDIUM,
    ASOAction.REMOVE_KEYWORD.value: ImpactLevel.LOW,
    ASOAction.UPDATE_TITLE.value: ImpactLevel.HIGH,
    ASOAction.UPDATE_DESCRIPTION.value: ImpactLevel.MEDIUM,
    ASOAction.UPDATE_SCREENSHOT.value: ImpactLevel.HIGH,
    ASOAction.UPDATE_ICON.value: ImpactLevel.HIGH,
    ASOAction.CREATE_EXPERIMENT.value: ImpactLevel.MEDIUM,
}


@dataclass
class ASODecisionReport:
    """One full analyze -> decide run, with the gate results."""

    report: ASOReport
    decisions: List[GrowthDecision] = field(default_factory=list)
    generated_at: datetime = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report": self.report.to_dict(),
            "decisions": [d.to_dict() for d in self.decisions],
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
        return "\n".join(lines)


@dataclass
class ASOAgentRunResult:
    """One full autonomous run: Reality -> ASOSnapshot -> Insight -> Action."""

    game_id: str
    reality: ASORealitySnapshot
    quality: ASODataQuality
    aso_snapshot: ASOSnapshot
    report: ASOReport
    reviews: List[str] = field(default_factory=list)
    competitors: List[CompetitorSnapshot] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "reality": self.reality.to_dict(),
            "quality": self.quality.to_dict(),
            "aso_snapshot": self.aso_snapshot.to_dict(),
            "report": self.report.to_dict(),
            "reviews": list(self.reviews),
            "competitors": [c.to_dict() for c in self.competitors],
        }


class ASOIntelligenceAgent:
    """Orchestrates analyzers, action mapper, gate and memory."""

    def __init__(
        self,
        memory: Optional[ASOMemory] = None,
        action_sink: Optional[GrowthActionSink] = None,
        approval_queue: Optional[JsonlApprovalQueue] = None,
        audit_path: Optional[str] = None,
        policy: Optional[DecisionPolicy] = None,
        auditor: Optional["FlowAuditor"] = None,
    ):
        # EP0.11.4: central audit trail (ASO flow:
        # insight -> plan -> approval -> experiment -> result). No-op if None.
        self.auditor = auditor
        self.keyword_analyzer = KeywordAnalyzer()
        self.conversion_analyzer = ConversionAnalyzer()
        self.listing_analyzer = ListingAnalyzer()
        self.competitor_analyzer = CompetitorAnalyzer()
        self.action_mapper = ASOActionMapper()
        self.memory = memory
        self.policy = policy or DecisionPolicy(
            extra_risk=ASO_RISK, extra_impact=ASO_IMPACT
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
        current: ASOSnapshot,
        previous: Optional[ASOSnapshot] = None,
        reviews: Optional[List[str]] = None,
        intent_keywords: Optional[List[str]] = None,
        competitors_current: Optional[List[CompetitorSnapshot]] = None,
        competitors_previous: Optional[List[CompetitorSnapshot]] = None,
    ) -> ASOReport:
        """Pure analysis: reality -> insights -> recommended GrowthActions."""
        insights: List[ASOInsight] = []

        intent = intent_keywords if intent_keywords is not None else list(
            current.keywords
        )
        insights.extend(
            self.keyword_analyzer.analyze(current, intent, reviews)
        )
        insights.extend(self.conversion_analyzer.analyze(current, previous))
        insights.extend(self.listing_analyzer.analyze(current))
        insights.extend(
            self.competitor_analyzer.analyze(
                current.game_id,
                competitors_current or [],
                competitors_previous,
            )
        )

        insights = self._dedupe(insights)
        insights.sort(key=lambda i: i.impact_score, reverse=True)

        actions = self.action_mapper.map_all(insights)
        summary = self._summarize(current, insights)
        return ASOReport(
            game_id=current.game_id,
            current_date=current.date,
            previous_date=previous.date if previous else current.date,
            platform=current.platform,
            insights=insights,
            actions=actions,
            summary=summary,
        )

    # ------------------------------------------------------------------ #
    def analyze_and_decide(
        self,
        current: ASOSnapshot,
        previous: Optional[ASOSnapshot] = None,
        reviews: Optional[List[str]] = None,
        intent_keywords: Optional[List[str]] = None,
        competitors_current: Optional[List[CompetitorSnapshot]] = None,
        competitors_previous: Optional[List[CompetitorSnapshot]] = None,
    ) -> ASODecisionReport:
        """Full loop: analyze -> gate every action through the validator."""
        report = self.analyze(
            current,
            previous=previous,
            reviews=reviews,
            intent_keywords=intent_keywords,
            competitors_current=competitors_current,
            competitors_previous=competitors_previous,
        )
        # EP0.11.4 audit: insight records (ASO flow step 1)
        if self.auditor is not None:
            for ins in report.insights:
                self.auditor.aso_insight(
                    game_id=report.game_id,
                    insight_type=getattr(ins.insight_type, "value",
                                         str(ins.insight_type)),
                    description=ins.description,
                    impact_score=float(ins.impact_score),
                )
        decisions: List[GrowthDecision] = []
        for action in report.actions:
            stats = self._stats(action)
            decision = self.validator.validate(action, experience_stats=stats)
            decisions.append(decision)
            # EP0.11.4 audit: plan + approval + result (ASO flow steps 2-5)
            if self.auditor is not None:
                self.auditor.aso_gated_action(
                    game_id=report.game_id,
                    action=getattr(action.action, "value", str(action.action)),
                    approval_route=getattr(decision.approval, "value",
                                           str(decision.approval)),
                    executed=bool(decision.executed),
                    queued=bool(decision.queued),
                    reason=getattr(action, "reason", "") or "",
                    confidence=float(getattr(action, "confidence", 1.0) or 1.0),
                )
        return ASODecisionReport(report=report, decisions=decisions)

    # ------------------------------------------------------------------ #
    def run(
        self,
        game_id: str,
        connector: ASORealityConnector,
        *,
        previous: Optional[ASOSnapshot] = None,
        intent_keywords: Optional[List[str]] = None,
        competitors_previous: Optional[List[CompetitorSnapshot]] = None,
        persist: bool = True,
    ) -> ASOAgentRunResult:
        """Autonomous loop: Reality -> ASOSnapshot -> Insight -> Action.

        Pulls real store data through the connector, normalizes it into the
        analysis-ready ``ASOSnapshot``, runs every analyzer and returns the
        full result (reality + quality + report). The connector owns caching &
        history; this method never executes ASO changes (those still flow
        through the shared ``DecisionValidator`` inside ``analyze``).

        This is the upgrade from E16.6.1's ``analyze(snapshot)``: the agent now
        *fetches its own data* instead of being handed a snapshot.
        """
        result = connector.collect(game_id, persist=persist)
        report = self.analyze(
            result.aso_snapshot,
            previous=previous,
            reviews=[r.text for r in result.reviews],
            intent_keywords=intent_keywords,
            competitors_current=result.competitors or None,
            competitors_previous=competitors_previous,
        )
        return ASOAgentRunResult(
            game_id=game_id,
            reality=result.reality,
            quality=result.quality,
            aso_snapshot=result.aso_snapshot,
            report=report,
            reviews=[r.text for r in result.reviews],
            competitors=result.competitors or [],
        )

    # ------------------------------------------------------------------ #
    def record_outcome(
        self,
        game_id: str,
        action: ASOAction,
        reason: str,
        before_revenue: float,
        after_revenue: float,
        before_cvr: Optional[float] = None,
        after_cvr: Optional[float] = None,
    ) -> Optional[Any]:
        """Close the loop: outcome -> experience store + pattern memory."""
        if self.memory is None:
            return None
        return self.memory.record_outcome(
            game_id,
            action,
            reason,
            before_revenue,
            after_revenue,
            before_cvr=before_cvr,
            after_cvr=after_cvr,
        )

    # ------------------------------------------------------------------ #
    def _stats(self, action: GrowthAction) -> Dict[str, Any]:
        if self.memory is None:
            return {}
        return self.memory.experience_store.stats(
            action.game_id, action.action
        )

    # ------------------------------------------------------------------ #
    @staticmethod
    def _dedupe(insights: List[ASOInsight]) -> List[ASOInsight]:
        """Keep the highest-impact insight per (type, target)."""
        best: Dict[Any, ASOInsight] = {}
        for ins in insights:
            key = (
                ins.insight_type,
                ins.evidence.get("keyword")
                or ins.evidence.get("asset_id")
                or ins.evidence.get("competitor_id")
                or "_",
            )
            cur = best.get(key)
            if cur is None or ins.impact_score > cur.impact_score:
                best[key] = ins
        return list(best.values())

    @staticmethod
    def _summarize(snapshot: ASOSnapshot, insights: List[ASOInsight]) -> str:
        if not insights:
            cvr = snapshot.cvr()
            return (
                f"ASO healthy: CVR {cvr:.1%}, rating {snapshot.rating:.1f}, "
                f"{len(snapshot.keywords)} keywords indexed, no issues detected."
            )
        top = insights[0]
        return (
            f"{len(insights)} ASO issue(s) detected; top: "
            f"[{top.insight_type.value}] {top.description}"
        )


__all__ = [
    "ASOIntelligenceAgent",
    "ASODecisionReport",
    "ASOAgentRunResult",
    "ASO_RISK",
    "ASO_IMPACT",
]
