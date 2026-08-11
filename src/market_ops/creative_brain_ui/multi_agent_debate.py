"""E4: Multi-Agent Creative Debate Engine.

Simulates an internal discussion between 5 AI agents:
  - Market Agent:     market trends, competition, timing
  - Gameplay Agent:   core loop quality, retention potential
  - UA Agent:         ad expressiveness, CPI prediction
  - Producer Agent:   development cost, timeline, feasibility
  - Investor Agent:   ROI risk, budget allocation, portfolio fit

All agents debate and produce a consensus decision with rationale.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class AgentRole(Enum):
    MARKET = "market"
    GAMEPLAY = "gameplay"
    UA = "ua"
    PRODUCER = "producer"
    INVESTOR = "investor"


class Vote(Enum):
    BUILD = "build"
    PROTOTYPE = "prototype"
    WATCH = "watch"
    SKIP = "skip"


@dataclass
class AgentOpinion:
    """One agent's analysis."""
    agent_role: AgentRole = AgentRole.MARKET
    vote: Vote = Vote.WATCH
    confidence: float = 0.5
    reasoning: str = ""
    key_concerns: list[str] = field(default_factory=list)
    key_strengths: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_role": self.agent_role.value,
            "vote": self.vote.value,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "key_concerns": self.key_concerns,
            "key_strengths": self.key_strengths,
        }


@dataclass
class DebateResult:
    """Consensus result from multi-agent debate."""
    opportunity_name: str = ""
    opinions: list[AgentOpinion] = field(default_factory=list)
    vote_counts: dict[str, int] = field(default_factory=dict)
    final_vote: Vote = Vote.WATCH
    consensus_strength: float = 0.0  # 0-1, how aligned agents are
    majority_reasoning: str = ""
    dissenting_view: str = ""
    action_items: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "opportunity_name": self.opportunity_name,
            "opinions": [o.to_dict() for o in self.opinions],
            "vote_counts": self.vote_counts,
            "final_vote": self.final_vote.value,
            "consensus_strength": round(self.consensus_strength, 2),
            "majority_reasoning": self.majority_reasoning,
            "dissenting_view": self.dissenting_view,
            "action_items": self.action_items,
        }


class MultiAgentDebateEngine:
    """Orchestrates a debate between 5 specialized AI agents.

    Usage:
        engine = MultiAgentDebateEngine()
        debate = engine.debate(analysis, score)
        print(f"Consensus: {debate.final_vote.value}")
    """

    def __init__(self) -> None:
        pass

    def debate(self, analysis: dict[str, Any], score: Any) -> DebateResult:
        """Run full debate and produce consensus.

        Args:
            analysis: From CreativeAnalysisEngine
            score: CreativeScore from CreativeScoringEngine

        Returns:
            DebateResult with all agent opinions + consensus.
        """
        genes = analysis.get("genes", {})
        name = analysis.get("idea_type", "") or analysis.get("category", "opportunity")

        opinions = [
            self._market_agent_opinion(genes, analysis),
            self._gameplay_agent_opinion(genes, analysis),
            self._ua_agent_opinion(genes, analysis),
            self._producer_agent_opinion(genes, analysis),
            self._investor_agent_opinion(genes, score, analysis),
        ]

        vote_counts = self._count_votes(opinions)
        final_vote, consensus = self._determine_consensus(vote_counts)
        majority, dissenting = self._extract_rationale(opinions, final_vote)
        action_items = self._generate_action_items(final_vote, genes)

        return DebateResult(
            opportunity_name=name,
            opinions=opinions,
            vote_counts=vote_counts,
            final_vote=final_vote,
            consensus_strength=consensus,
            majority_reasoning=majority,
            dissenting_view=dissenting,
            action_items=action_items,
        )

    # ── Agent Opinions ────────────────────────────────────

    def _market_agent_opinion(
        self, genes: dict[str, str], analysis: dict[str, Any]
    ) -> AgentOpinion:
        """Market Agent: trend analysis perspective."""
        core = genes.get("core_loop", "unknown")

        if core in ["merge", "sort"]:
            vote = Vote.BUILD
            reasoning = "Trend is strong. Merge/Sort category has +180% ad volume increase."
            strengths = ["High market momentum", "Proven category"]
            concerns = []
        elif core in ["puzzle", "simulation"]:
            vote = Vote.PROTOTYPE
            reasoning = "Growing but competitive. Worth testing with differentiation."
            strengths = ["Growing category"]
            concerns = ["Competition is high"]
        else:
            vote = Vote.WATCH
            reasoning = "Unclear market positioning. Need more data."
            strengths = []
            concerns = ["Unknown market fit"]

        return AgentOpinion(
            agent_role=AgentRole.MARKET,
            vote=vote,
            confidence=0.75 if core in ["merge", "sort"] else 0.5,
            reasoning=reasoning,
            key_concerns=concerns,
            key_strengths=strengths,
        )

    def _gameplay_agent_opinion(
        self, genes: dict[str, str], analysis: dict[str, Any]
    ) -> AgentOpinion:
        """Gameplay Agent: core loop quality."""
        has_reward = "reward" in genes or "retention" in genes
        has_hook = "hook" in genes

        if has_hook and has_reward:
            vote = Vote.BUILD
            reasoning = "Solid core loop with hook + reward. Retention potential is high."
            strengths = ["Complete game loop", "Hook + reward present"]
            concerns = []
        elif has_hook or has_reward:
            vote = Vote.PROTOTYPE
            reasoning = "Good start but missing dimensions. Add reward or hook to complete."
            strengths = ["Partial loop defined"]
            concerns = ["Missing dimension"]
        else:
            vote = Vote.WATCH
            reasoning = "Core loop undefined. Too early to judge."
            strengths = []
            concerns = ["No hook or reward defined"]

        return AgentOpinion(
            agent_role=AgentRole.GAMEPLAY,
            vote=vote,
            confidence=0.7 if has_hook and has_reward else 0.4,
            reasoning=reasoning,
            key_concerns=concerns,
            key_strengths=strengths,
        )

    def _ua_agent_opinion(
        self, genes: dict[str, str], analysis: dict[str, Any]
    ) -> AgentOpinion:
        """UA Agent: ad expressiveness."""
        hook = genes.get("hook", "")
        visual = genes.get("visual", "")

        if hook == "rescue" and visual in ["3d_cartoon", "bright"]:
            vote = Vote.BUILD
            reasoning = "Easy to express in ads. Rescue+hook + bright visual = high CTR."
            strengths = ["Strong ad hook", "Visual clarity"]
            concerns = []
        elif hook:
            vote = Vote.PROTOTYPE
            reasoning = "Hook defined. Can test creative variations quickly."
            strengths = ["Has ad hook"]
            concerns = ["Visual style unclear"]
        else:
            vote = Vote.WATCH
            reasoning = "No clear ad hook. CPI may be high at launch."
            strengths = []
            concerns = ["Hard to express in 3-second ads"]

        return AgentOpinion(
            agent_role=AgentRole.UA,
            vote=vote,
            confidence=0.8 if hook == "rescue" else 0.5,
            reasoning=reasoning,
            key_concerns=concerns,
            key_strengths=strengths,
        )

    def _producer_agent_opinion(
        self, genes: dict[str, str], analysis: dict[str, Any]
    ) -> AgentOpinion:
        """Producer Agent: development feasibility."""
        core = genes.get("core_loop", "")
        monet = genes.get("monetization", "")

        if core in ["merge", "sort"]:
            vote = Vote.BUILD
            reasoning = "Proven mechanic. Estimated 7-14 day prototype."
            strengths = ["Low development cost", "Proven template exists"]
            concerns = []
        elif monet == "IAP":
            vote = Vote.WATCH
            reasoning = "IAP adds development complexity. Longer timeline."
            strengths = ["Revenue potential"]
            concerns = ["Development time increase"]
        else:
            vote = Vote.PROTOTYPE
            reasoning = "Feasible with standard framework. Moderate effort."
            strengths = ["Standard pipeline"]
            concerns = []

        return AgentOpinion(
            agent_role=AgentRole.PRODUCER,
            vote=vote,
            confidence=0.65,
            reasoning=reasoning,
            key_concerns=concerns,
            key_strengths=strengths,
        )

    def _investor_agent_opinion(
        self, genes: dict[str, str], score: Any, analysis: dict[str, Any]
    ) -> AgentOpinion:
        """Investor Agent: ROI risk assessment."""
        total = getattr(score, 'total', 50)

        if total >= 80:
            vote = Vote.BUILD
            reasoning = f"Score {total}/100. ROI profile is attractive. Budget: $3K MVP test."
            strengths = ["High score", "Attractive risk/reward"]
            concerns = ["Opportunity cost of not building"]
        elif total >= 60:
            vote = Vote.PROTOTYPE
            reasoning = f"Score {total}/100. Decent ROI potential but risk moderate."
            strengths = ["Manageable risk"]
            concerns = ["Medium confidence"]
        else:
            vote = Vote.SKIP
            reasoning = f"Score {total}/100. ROI risk too high. Wait for better signals."
            strengths = []
            concerns = ["High ROI risk", "Low confidence"]

        return AgentOpinion(
            agent_role=AgentRole.INVESTOR,
            vote=vote,
            confidence=min(0.85, total / 100 + 0.1),
            reasoning=reasoning,
            key_concerns=concerns,
            key_strengths=strengths,
        )

    # ── Consensus Logic ─────────────────────────────────

    @staticmethod
    def _count_votes(opinions: list[AgentOpinion]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for o in opinions:
            v = o.vote.value
            counts[v] = counts.get(v, 0) + 1
        return counts

    @staticmethod
    def _determine_consensus(vote_counts: dict[str, int]) -> tuple[Vote, float]:
        total = sum(vote_counts.values())
        if total == 0:
            return Vote.WATCH, 0.0

        best_vote = max(vote_counts, key=vote_counts.get)
        consensus = vote_counts[best_vote] / total

        return Vote(best_vote), round(consensus, 2)

    @staticmethod
    def _extract_rationale(
        opinions: list[AgentOpinion], final_vote: Vote,
    ) -> tuple[str, str]:
        supporting = [o for o in opinions if o.vote == final_vote]
        dissenting = [o for o in opinions if o.vote != final_vote]

        majority = "; ".join(
            f"[{o.agent_role.value}] {o.reasoning}" for o in supporting[:2]
        )
        dissent = "; ".join(
            f"[{o.agent_role.value}] {o.reasoning}" for o in dissenting[:1]
        ) if dissenting else ""

        return majority, dissent

    @staticmethod
    def _generate_action_items(vote: Vote, genes: dict[str, str]) -> list[str]:
        items = []
        if vote in (Vote.BUILD, Vote.PROTOTYPE):
            items.append("Generate 3 creative variants via HypothesisEngine")
            items.append("Build Creative Genome → push to CreativeFactory")
        if "reward" not in genes:
            items.append("Define reward/retention loop")
        if "visual" not in genes:
            items.append("Define visual style guide")
        return items
