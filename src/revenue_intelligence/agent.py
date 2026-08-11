"""
E16.1 / E16.1.1 — Revenue Intelligence Agent (the "Business Brain")

E16.1 (analyst): reads revenue facts -> delta -> attribution -> insights ->
patterns -> recommended GrowthActions (no execution by default).

E16.1.1 (decision loop): wraps the analyst in an operational closed loop --
every recommended action is (1) simulated via the ``RevenueSimulator`` (E12/E13
provider seam), (2) gated by a three-tier Confidence Gate into
AUTO / HUMAN_QUEUE / RECORD_ONLY, (3) routed to the E13.3 Growth Action Sink
(executor) or a human approval queue, and (4) its real outcome is recorded back
into Revenue Experience Memory so future decisions learn from what actually
made money.

    Adjust/Meta/MAX/Play -> Revenue Intelligence Agent
        -> Insight -> Simulation -> Decision -> Execution -> Result -> Memory
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from .adapters import RealityFactRevenueSource  # noqa: F401 (public bridge)
from .analyzer import RevenueDeltaEngine
from .attribution import RevenueAttributionEngine
from .action_mapper import ActionMapper
from .decision.policy import ApprovalRoute, DecisionPolicy
from .decision.validator import (
    DecisionValidator,
    GrowthDecision,
    JsonlApprovalQueue,
)
from .experience import (
    JsonlRevenueExperienceStore,
    RevenueExperience,
    RevenuePoint,
    compute_reward,
)
from .executor import NullGrowthActionSink
from .forecasting import RevenueForecast, RevenueForecaster
from .insight_engine import InsightEngine
from .models import (
    GrowthAction,
    GrowthActionSink,
    InsightType,
    PatternMatch,
    PatternMemory,
    RevenueAction,
    RevenueDataSource,
    RevenueDelta,
    RevenueInsight,
    RevenueReport,
    RevenueSnapshot,
)
from .pattern_memory import JsonlPatternMemory
from .portfolio import (
    GamePortfolioEntry,
    PortfolioIntelligence,
    PortfolioReport,
)
from .profit import (
    DEFAULT_PLATFORM_FEE_RATE,
    ProfitEngine,
    ProfitReport,
    ProfitSnapshot,
)
from .simulator import RevenueSimulator, SimulationResult


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class DecisionReport:
    """Unified output of the closed-loop decision pass."""
    game_id: str
    current_date: str
    previous_date: str
    generated_at: datetime = field(default_factory=_now)
    report: Optional[RevenueReport] = None
    decisions: List[GrowthDecision] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "current_date": self.current_date,
            "previous_date": self.previous_date,
            "generated_at": self.generated_at.isoformat(),
            "report": self.report.to_dict() if self.report else None,
            "decisions": [d.to_dict() for d in self.decisions],
            "summary": self.summary,
        }

    def to_markdown(self) -> str:
        lines = [
            f"# Revenue Decision Loop — {self.game_id}",
            f"Period: {self.previous_date} → {self.current_date}",
            "",
        ]
        if self.summary:
            lines += [self.summary, ""]
        tag = {
            ApprovalRoute.AUTO: "AUTO",
            ApprovalRoute.HUMAN_QUEUE: "HUMAN",
            ApprovalRoute.RECORD_ONLY: "LOG",
        }
        for d in self.decisions:
            state = (
                "executed"
                if d.executed
                else ("queued" if d.queued else "logged")
            )
            lines.append(
                f"- [{tag.get(d.approval, d.approval.value)}] "
                f"{d.action.action.value} "
                f"(conf {d.action.confidence:.0%}, risk {d.score.risk.value}, "
                f"{state})"
            )
            if d.simulation:
                sim = d.simulation
                lines.append(
                    f"    sim: spend {sim['expected_spend_pct']:+.0f}% / "
                    f"rev {sim['expected_revenue_pct']:+.0f}% / "
                    f"ROAS {sim['expected_roas']:.2f} / "
                    f"conf {sim['confidence']:.0%}"
                )
        return "\n".join(lines)


class RevenueIntelligenceAgent:
    """Turns two revenue snapshots into a decision-ready report."""

    def __init__(
        self,
        pattern_memory: Optional[PatternMemory] = None,
        action_sink: Optional[GrowthActionSink] = None,
        *,
        simulator: Optional[RevenueSimulator] = None,
        validator: Optional[DecisionValidator] = None,
        experience_store: Optional[JsonlRevenueExperienceStore] = None,
        approval_queue: Optional[JsonlApprovalQueue] = None,
        audit_path: Optional[str] = None,
    ):
        self.delta_engine = RevenueDeltaEngine()
        self.attribution_engine = RevenueAttributionEngine()
        self.insight_engine = InsightEngine()
        self.action_mapper = ActionMapper()
        self.pattern_memory = pattern_memory
        self.action_sink = action_sink or NullGrowthActionSink()
        self.simulator = simulator
        self.experience_store = experience_store
        self.validator = validator or DecisionValidator(
            action_sink=self.action_sink,
            approval_queue=approval_queue,
            experience_store=experience_store,
            audit_path=audit_path,
        )

    # ------------------------------------------------------------------ #
    # E16.1 analyst path (unchanged behaviour: recommends, does not execute)
    # ------------------------------------------------------------------ #
    def analyze(
        self,
        current: RevenueSnapshot,
        previous: RevenueSnapshot,
        *,
        auto_execute: bool = False,
    ) -> RevenueReport:
        delta = self.delta_engine.compare(current, previous)
        attribution = self.attribution_engine.analyze(current, previous, delta)
        insights = self.insight_engine.generate(
            current, previous, delta, attribution
        )

        patterns: List[PatternMatch] = []
        if self.pattern_memory is not None:
            signal = self._build_signal(current, delta, insights)
            patterns = self.pattern_memory.search_similar(
                current.game_id, signal, limit=3
            )

        actions = self.action_mapper.map(
            current, previous, delta, insights, patterns
        )

        if auto_execute and actions:
            for a in actions:
                self.action_sink.submit(a)

        summary = self._summarize(delta, attribution, insights, actions)
        return RevenueReport(
            game_id=current.game_id,
            current_date=current.date,
            previous_date=previous.date,
            delta=delta,
            attribution=attribution,
            insights=insights,
            patterns=patterns,
            actions=actions,
            summary=summary,
        )

    # ------------------------------------------------------------------ #
    def analyze_from_source(
        self,
        source: RevenueDataSource,
        game_id: str,
        current_period: str,
        previous_period: str,
        *,
        auto_execute: bool = False,
    ) -> RevenueReport:
        current = source.load_snapshot(game_id, current_period)
        previous = source.load_snapshot(game_id, previous_period)
        return self.analyze(current, previous, auto_execute=auto_execute)

    # ------------------------------------------------------------------ #
    # E16.1.1 closed-loop path: Insight -> Simulation -> Decision -> Exec
    # ------------------------------------------------------------------ #
    def analyze_and_decide(
        self, current: RevenueSnapshot, previous: RevenueSnapshot
    ) -> DecisionReport:
        report = self.analyze(current, previous, auto_execute=False)
        decisions: List[GrowthDecision] = []
        for action in report.actions:
            sim = self._simulate(action, current)
            exp_stats = self._experience_stats(current.game_id, action)
            decision = self.validator.validate(
                action, simulation=sim, experience_stats=exp_stats
            )
            decisions.append(decision)
        summary = self._summarize_decisions(report, decisions)
        return DecisionReport(
            game_id=current.game_id,
            current_date=current.date,
            previous_date=previous.date,
            report=report,
            decisions=decisions,
            summary=summary,
        )

    def analyze_and_decide_from_source(
        self,
        source: RevenueDataSource,
        game_id: str,
        current_period: str,
        previous_period: str,
    ) -> DecisionReport:
        current = source.load_snapshot(game_id, current_period)
        previous = source.load_snapshot(game_id, previous_period)
        return self.analyze_and_decide(current, previous)

    # ------------------------------------------------------------------ #
    # E16.1.2 / E16.1.3 / E16.1.4 — the CFO upgrades (thin delegation)
    # ------------------------------------------------------------------ #
    def forecast(self, history: List[RevenueSnapshot]) -> RevenueForecast:
        """E16.1.2: project 7d/30d revenue + LTV from snapshot history."""
        return RevenueForecaster().forecast(history)

    def profit_report(
        self,
        current: RevenueSnapshot,
        previous: Optional[RevenueSnapshot] = None,
        *,
        platform_fee_rate: float = DEFAULT_PLATFORM_FEE_RATE,
        other_cost: float = 0.0,
    ) -> ProfitReport:
        """E16.1.3: revenue → true profit view with named insights."""
        cur = ProfitSnapshot.from_revenue_snapshot(
            current, platform_fee_rate=platform_fee_rate, other_cost=other_cost
        )
        prev = (
            ProfitSnapshot.from_revenue_snapshot(
                previous,
                platform_fee_rate=platform_fee_rate,
                other_cost=other_cost,
            )
            if previous
            else None
        )
        return ProfitEngine().analyze(cur, prev)

    def portfolio_report(
        self, entries: List[GamePortfolioEntry]
    ) -> PortfolioReport:
        """E16.1.4: fund-manager verdicts across the whole game fleet."""
        return PortfolioIntelligence().evaluate(entries)

    # ------------------------------------------------------------------ #
    # Closed-loop learning: record the real result of a decision.
    # ------------------------------------------------------------------ #
    def record_outcome(
        self,
        action: Union[GrowthAction, RevenueAction],
        before: Union[RevenuePoint, RevenueSnapshot],
        after: Union[RevenuePoint, RevenueSnapshot],
        *,
        reason: str = "",
        game_id: Optional[str] = None,
    ) -> RevenueExperience:
        """Persist the outcome of a decision and feed it back into memory."""
        act = action.action if isinstance(action, GrowthAction) else action
        gid = game_id or (
            action.game_id if isinstance(action, GrowthAction) else ""
        )
        if isinstance(before, RevenueSnapshot):
            before = RevenuePoint.from_snapshot(before)
        if isinstance(after, RevenueSnapshot):
            after = RevenuePoint.from_snapshot(after)

        exp = RevenueExperience(
            game_id=gid,
            action=act,
            reason=reason,
            before=before,
            after=after,
        )
        reward, success = compute_reward(exp)
        exp.reward, exp.success = reward, success

        if self.experience_store is not None:
            self.experience_store.add(exp)
        # closed-loop: surface the outcome into E13.4 Growth Memory (optional)
        if self.pattern_memory is not None and isinstance(
            self.pattern_memory, JsonlPatternMemory
        ):
            self._feed_pattern_memory(gid, act, exp)
        return exp

    # ------------------------------------------------------------------ #
    def _simulate(
        self, action: GrowthAction, current: RevenueSnapshot
    ) -> Optional[SimulationResult]:
        if self.simulator is None:
            return None
        exp_stats = self._experience_stats(current.game_id, action)
        return self.simulator.simulate(
            action, current, experience_stats=exp_stats
        )

    def _experience_stats(
        self, game_id: str, action: Union[GrowthAction, RevenueAction]
    ) -> Optional[Dict[str, Any]]:
        if self.experience_store is None:
            return None
        act = action.action if isinstance(action, GrowthAction) else action
        return self.experience_store.stats(game_id, act)

    def _feed_pattern_memory(
        self, game_id: str, action: RevenueAction, exp: RevenueExperience
    ) -> None:
        outcome = "win" if exp.success else "loss"
        self.pattern_memory.add(  # type: ignore[union-attr]
            PatternMatch(
                pattern_id=f"exp_{int(exp.created_at.timestamp())}",
                description=(
                    f"Past {action.value} on {game_id}: {outcome} "
                    f"(reward {exp.reward:+.2f})"
                ),
                confidence=min(0.99, 0.5 + abs(exp.reward)),
                similar_case=f"experience:{game_id}:{action.value}",
                recommended_action=action if exp.success else None,
                recommended_strategy=exp.reason,
            ),
            game_id=game_id,
        )

    @staticmethod
    def _summarize_decisions(
        report: RevenueReport, decisions: List[GrowthDecision]
    ) -> str:
        n_auto = sum(
            1
            for d in decisions
            if d.approval == ApprovalRoute.AUTO and d.executed
        )
        n_queue = sum(
            1
            for d in decisions
            if d.approval == ApprovalRoute.HUMAN_QUEUE and d.queued
        )
        n_log = sum(
            1 for d in decisions if d.approval == ApprovalRoute.RECORD_ONLY
        )
        return (
            f"{len(report.actions)} action(s) gated: "
            f"{n_auto} auto-executed, {n_queue} queued for human, "
            f"{n_log} logged only."
        )

    # ------------------------------------------------------------------ #
    @staticmethod
    def _build_signal(
        current: RevenueSnapshot,
        delta: RevenueDelta,
        insights: List[RevenueInsight],
    ) -> Dict[str, Any]:
        return {
            "game_id": current.game_id,
            "revenue_total_pct": delta.revenue_total_pct,
            "spend_pct": delta.spend_pct,
            "roas": current.roas,
            "insight_types": [i.insight_type.value for i in insights],
            "dominant_insight": (
                insights[0].insight_type.value if insights else None
            ),
        }

    @staticmethod
    def _summarize(
        delta: RevenueDelta,
        attribution: Any,
        insights: List[RevenueInsight],
        actions: List[Any],
    ) -> str:
        pct = delta.revenue_total_pct
        if pct is None:
            direction = "no comparable revenue change"
        elif pct >= 0:
            direction = f"revenue up {pct:+.1f}%"
        else:
            direction = f"revenue down {pct:+.1f}%"
        dom = attribution.dominant() if attribution else None
        dom_txt = (
            f"; dominant driver: {dom.name} ({dom.contribution_pct:+.1f}%)"
            if dom
            else ""
        )
        n_actions = len(actions)
        return (
            f"{direction}{dom_txt}. "
            f"{len(insights)} insight(s), {n_actions} recommended action(s)."
        )


__all__ = [
    "RevenueIntelligenceAgent",
    "RevenueAction",
    "InsightType",
    "DecisionReport",
    "DecisionPolicy",
    "DecisionValidator",
    "RevenueSimulator",
    "JsonlRevenueExperienceStore",
]
