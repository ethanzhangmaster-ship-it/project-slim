"""E7.1+E7.2: Failure Intelligence — learn why predictions were wrong.

Two key capabilities:

1. FailureAnalyzer: Attributing prediction errors to specific agents
   - Which agent was most wrong? (Market, Gameplay, UA, Producer, Investor)
   - What dimension was misjudged? (CPI, CTR, retention, competition)
   - How much should each agent's weight change?

2. GenomeAttribution: Connecting genome performance back to gene values
   - Which gene values correlate with success/failure?
   - What gene combinations produce winners vs losers?
   - Updated gene-level statistics from reality data

This is the "anti-pattern" learner — it learns more from failures than successes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from market_ops.creative_reality.reality_tracker import GenomePerformanceDelta, CampaignReality
from market_ops.creative_brain.v5_evolution.schemas import Genome
from market_ops.creative_brain_ui.debate_engine.decision_history import DecisionHistory


@dataclass
class AgentErrorReport:
    """How much each agent contributed to a wrong prediction."""
    agent_name: str = ""
    dimension: str = ""         # what they judged
    predicted_vote: str = ""    # what they voted
    error_magnitude: float = 0.0  # how wrong (0=perfect, 1=completely wrong)
    error_direction: str = ""   # "overconfident" or "underconfident"
    adjusted_weight: float = 0.5  # new weight after adjustment
    lesson: str = ""


@dataclass
class GenePerformanceAttribution:
    """How a specific gene value performed in reality."""
    gene_type: str = ""
    gene_value: str = ""
    appearances: int = 0
    winner_count: int = 0
    avg_roas: float = 0.0
    avg_ctr: float = 0.0
    avg_cpi: float = 0.0
    success_rate: float = 0.0
    # when this gene appears + another gene, what happens?
    synergy_with: dict[str, float] = field(default_factory=dict)  # gene_value → avg_roas


class FailureAnalyzer:
    """Analyze WHY predictions were wrong and attribute errors to agents.

    Learning principle: each failure contains more information than 10 successes.
    """

    def __init__(self, decision_history: DecisionHistory | None = None) -> None:
        self._decision_history = decision_history or DecisionHistory()
        self._error_reports: list[AgentErrorReport] = []
        self._agent_error_rate: dict[str, dict[str, float]] = {}  # agent → {overconfident, underconfident, total}

    def analyze_failure(
        self, delta: GenomePerformanceDelta, agent_votes: dict[str, dict[str, Any]],
    ) -> list[AgentErrorReport]:
        """Analyze a failed prediction — which agents were wrong and why?

        Args:
            delta: Reality vs prediction delta
            agent_votes: {agent_name: {vote, confidence, dimension}}

        Returns: AgentErrorReport for each agent involved
        """
        reports = []

        for agent_name, vote_info in agent_votes.items():
            vote = vote_info.get("vote", "watch")
            confidence = vote_info.get("confidence", 0.5)
            dimension = vote_info.get("dimension", "unknown")

            # Calculate error
            predicted_build = vote in ("build", "prototype")
            was_winner = delta.was_winner

            if predicted_build != was_winner:
                # Agent was wrong
                error_magnitude = confidence  # High confidence + wrong = bigger error
                direction = "overconfident" if predicted_build else "underconfident"

                # Adjust weight: penalize more for high-confidence errors
                penalty = confidence * 0.15  # Max penalty 0.15 per error
                new_weight = max(0.2, vote_info.get("current_weight", 0.5) - penalty)

                # Generate lesson
                if direction == "overconfident":
                    lesson = f"[{agent_name}] Overconfident on {dimension}: voted {vote} but actual ROAS {delta.actual_roas:.2f}"
                else:
                    lesson = f"[{agent_name}] Underconfident on {dimension}: voted {vote} but actual ROAS {delta.actual_roas:.2f}"

                report = AgentErrorReport(
                    agent_name=agent_name, dimension=dimension,
                    predicted_vote=vote,
                    error_magnitude=round(error_magnitude, 3),
                    error_direction=direction,
                    adjusted_weight=round(new_weight, 3),
                    lesson=lesson,
                )
                reports.append(report)
                self._error_reports.append(report)

                # Update agent error tracking
                self._agent_error_rate.setdefault(agent_name, {})
                self._agent_error_rate[agent_name].setdefault(direction, 0)
                self._agent_error_rate[agent_name][direction] += 1
                self._agent_error_rate[agent_name]["total"] = \
                    self._agent_error_rate[agent_name].get("total", 0) + 1

        return reports

    def get_agent_error_profile(self, agent_name: str) -> dict[str, Any]:
        """Get how this agent tends to be wrong."""
        rates = self._agent_error_rate.get(agent_name, {})
        total = rates.get("total", 1)
        return {
            "agent": agent_name,
            "total_errors": total,
            "overconfident_rate": round(rates.get("overconfident", 0) / max(1, total), 2),
            "underconfident_rate": round(rates.get("underconfident", 0) / max(1, total), 2),
        }

    def get_system_error_summary(self) -> dict[str, Any]:
        """Get system-wide error patterns."""
        if not self._error_reports:
            return {"status": "no_errors_recorded"}

        overconfident = sum(1 for r in self._error_reports if r.error_direction == "overconfident")
        underconfident = sum(1 for r in self._error_reports if r.error_direction == "underconfident")
        total = len(self._error_reports)

        # Which dimension is most frequently misjudged?
        dimension_errors: dict[str, int] = {}
        for r in self._error_reports:
            dimension_errors[r.dimension] = dimension_errors.get(r.dimension, 0) + 1
        worst_dimension = max(dimension_errors, key=dimension_errors.get) if dimension_errors else "unknown"

        return {
            "total_errors_analyzed": total,
            "overconfident_pct": round(overconfident / max(1, total), 2),
            "underconfident_pct": round(underconfident / max(1, total), 2),
            "most_misjudged_dimension": worst_dimension,
            "agent_profiles": {name: self.get_agent_error_profile(name)
                               for name in self._agent_error_rate},
        }


class GenomeAttribution:
    """Connects genome gene values to real-world performance outcomes.

    Answer: "Which genes actually work in reality?"
    """

    def __init__(self) -> None:
        self._gene_stats: dict[str, dict[str, GenePerformanceAttribution]] = {}
        self._synergy_stats: dict[str, dict[str, dict[str, float]]] = {}  # gene_type → val → other_val → avg_roas

    def record_outcome(self, genome: Genome, roas: float, ctr: float, cpi: float,
                       was_winner: bool) -> None:
        """Record how a genome performed in reality."""
        for key, gene in genome.genes.items():
            value = str(getattr(gene, 'value', getattr(gene, 'gene_type', 'unknown')))

            stats = self._gene_stats.setdefault(key, {}).setdefault(
                value, GenePerformanceAttribution(gene_type=key, gene_value=value),
            )
            stats.appearances += 1
            if was_winner:
                stats.winner_count += 1
            stats.avg_roas = (stats.avg_roas * (stats.appearances - 1) + roas) / stats.appearances
            stats.avg_ctr = (stats.avg_ctr * (stats.appearances - 1) + ctr) / stats.appearances
            stats.avg_cpi = (stats.avg_cpi * (stats.appearances - 1) + cpi) / stats.appearances
            stats.success_rate = stats.winner_count / stats.appearances

            # Track synergy: how does this gene perform with others?
            for other_key, other_gene in genome.genes.items():
                if other_key == key:
                    continue
                other_value = str(getattr(other_gene, 'value',
                                          getattr(other_gene, 'gene_type', 'unknown')))
                synergy = self._synergy_stats.setdefault(key, {}).setdefault(value, {})
                if other_value not in synergy:
                    synergy[other_value] = {"total_roas": 0, "count": 0}
                synergy[other_value]["total_roas"] += roas
                synergy[other_value]["count"] += 1
                stats.synergy_with[other_value] = round(
                    synergy[other_value]["total_roas"] / synergy[other_value]["count"], 3,
                )

    def get_winning_genes(self, min_appearances: int = 3) -> list[dict[str, Any]]:
        """Get genes that reliably produce winners."""
        results = []
        for gene_type, values in self._gene_stats.items():
            for value, stats in values.items():
                if stats.appearances >= min_appearances and stats.success_rate >= 0.5:
                    results.append({
                        "gene_type": gene_type,
                        "value": value,
                        "success_rate": round(stats.success_rate, 2),
                        "avg_roas": round(stats.avg_roas, 3),
                        "appearances": stats.appearances,
                    })
        return sorted(results, key=lambda r: r["success_rate"], reverse=True)

    def get_losing_genes(self, min_appearances: int = 3) -> list[dict[str, Any]]:
        """Get genes that reliably produce failures."""
        results = []
        for gene_type, values in self._gene_stats.items():
            for value, stats in values.items():
                if stats.appearances >= min_appearances and stats.success_rate <= 0.2:
                    results.append({
                        "gene_type": gene_type,
                        "value": value,
                        "failure_rate": round(1 - stats.success_rate, 2),
                        "avg_roas": round(stats.avg_roas, 3),
                        "appearances": stats.appearances,
                    })
        return sorted(results, key=lambda r: r["failure_rate"], reverse=True)

    def get_best_synergies(self, min_roas: float = 1.0) -> list[dict[str, Any]]:
        """Get gene combinations that consistently produce high ROAS."""
        synergies = []
        for gene_type, values in self._synergy_stats.items():
            for value, partners in values.items():
                for partner_val, stats in partners.items():
                    avg_roas = stats["total_roas"] / max(1, stats["count"])
                    if avg_roas >= min_roas and stats["count"] >= 2:
                        synergies.append({
                            "gene_a": f"{gene_type}:{value}",
                            "gene_b": partner_val,
                            "avg_roas": round(avg_roas, 3),
                            "samples": stats["count"],
                        })
        return sorted(synergies, key=lambda s: s["avg_roas"], reverse=True)
