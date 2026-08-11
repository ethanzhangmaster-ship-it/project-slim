"""E5/E7: Human Feedback Loop + Autonomous Idea Evolution.

E5: Human selects/rejects opportunities → feedback trains scoring model.
E7: Full autonomous idea evolution:
     Human Idea → AI Mutation → Idea variants → Ranking → Prototype → Test → Learn
"""

from __future__ import annotations

from typing import Any

from market_ops.creative_opportunity.schemas import (
    HumanIdea, Opportunity, OpportunityStatus, ExperimentPlan,
)
from market_ops.creative_opportunity.human_idea import HumanIdeaInbox
from market_ops.creative_opportunity.hypothesis_engine import HypothesisEngine
from market_ops.creative_opportunity.opportunity_ranker import OpportunityRanker
from market_ops.creative_brain_ui.creative_analysis_engine import CreativeAnalysisEngine
from market_ops.creative_brain_ui.creative_scoring import CreativeScoringEngine, CreativeScore
from market_ops.creative_brain_ui.multi_agent_debate import MultiAgentDebateEngine, DebateResult
from market_ops.creative_brain_ui.genome_marketplace import GenomeMarketplace, VerifiedGenome
from market_ops.creative_evolution.experiment_engine import (
    AutonomousExperimentEngine, ExperimentResult, ExperimentDecision,
)
from market_ops.creative_brain.v5_evolution.schemas import Genome


class HumanFeedbackLoop:
    """Records and learns from human selections.

    Tracks:
      - Which ideas humans approved/rejected
      - What gene patterns correlate with human approval
      - Updates scoring model weights based on feedback
    """

    def __init__(self) -> None:
        self._feedback_history: list[dict[str, Any]] = []
        self._approval_rates: dict[str, dict[str, float]] = {}  # gene_type → {value → rate}

    def record_selection(
        self, idea: HumanIdea, approved: bool, genome: Genome | None = None,
    ) -> None:
        """Record a human decision."""
        entry = {
            "idea_id": idea.idea_id,
            "title": idea.title,
            "approved": approved,
            "tags": idea.tags,
            "timestamp": idea.created_time,
        }
        if genome:
            entry["genes"] = {k: v.value for k, v in genome.genes.items()}
            self._update_approval_rates(genome, approved)

        self._feedback_history.append(entry)

    def _update_approval_rates(self, genome: Genome, approved: bool) -> None:
        for key, gene in genome.genes.items():
            if key not in self._approval_rates:
                self._approval_rates[key] = {}
            rates = self._approval_rates[key]
            if gene.value not in rates:
                rates[gene.value] = (0, 0)
            approved_count, total = rates[gene.value]
            rates[gene.value] = (approved_count + (1 if approved else 0), total + 1)

    def get_approval_rates(self) -> dict[str, list[dict[str, Any]]]:
        """Get human approval rates per gene value."""
        result = {}
        for gene_type, values in self._approval_rates.items():
            result[gene_type] = []
            for value, (approved, total) in values.items():
                result[gene_type].append({
                    "gene_value": value,
                    "approval_rate": round(approved / total, 2),
                    "total_selections": total,
                })
        return result

    def get_top_approved_genes(self, n: int = 5) -> list[dict[str, Any]]:
        """Get genes most approved by humans."""
        all_genes = []
        for gene_type, values in self._approval_rates.items():
            for value, (approved, total) in values.items():
                if total >= 2:
                    all_genes.append({
                        "gene_type": gene_type,
                        "value": value,
                        "approval_rate": round(approved / total, 2),
                        "total": total,
                    })
        return sorted(all_genes, key=lambda x: x["approval_rate"], reverse=True)[:n]


class IdeaEvolutionOrchestrator:
    """Full autonomous idea evolution cycle.

    E7: Human Idea → AI Mutation → Ideas → Rank → Prototype → Test → Learn

    Usage:
        orch = IdeaEvolutionOrchestrator()
        # Submit an idea
        result = orch.submit_and_rank("Sort + Simulation + Collection")
        # Run full evolution cycle
        cycle = orch.run_evolution_cycle()
    """

    def __init__(self) -> None:
        self._inbox = HumanIdeaInbox()
        self._analysis_engine = CreativeAnalysisEngine()
        self._scoring_engine = CreativeScoringEngine()
        self._debate_engine = MultiAgentDebateEngine()
        self._hypothesis_engine = HypothesisEngine()
        self._ranker = OpportunityRanker()
        self._feedback_loop = HumanFeedbackLoop()
        self._marketplace = GenomeMarketplace()

    # ── Submission ─────────────────────────────────────────

    def submit_and_rank(self, text: str, creator: str = "") -> dict[str, Any]:
        """Submit a human idea and get full analysis + score + debate.

        Returns complete analysis pipeline result.
        """
        # E1: Submit + analyze
        idea = self._inbox.submit_text(
            title=text[:50],
            description=text,
            creator=creator,
            tags=self._extract_tags(text),
        )

        # Multi-modal analysis
        analysis = self._analysis_engine.analyze_text(text)
        genome = self._analysis_engine.any_to_genome(idea)

        # E2/E3: Score
        score = self._scoring_engine.score_from_analysis(analysis)

        # E4: Debate
        debate = self._debate_engine.debate(analysis, score)

        # E5: Record feedback (auto-approve for now, human can override)
        self._feedback_loop.record_selection(idea, approved=True, genome=genome)

        # E7: Generate experiment plan
        opportunity = self._make_opportunity(idea, score)
        plan = self._hypothesis_engine.generate(opportunity)

        return {
            "idea": {"id": idea.idea_id, "title": idea.title},
            "analysis": analysis,
            "score": score.to_dict(),
            "debate": debate.to_dict(),
            "genome_id": genome.genome_id,
            "experiment_plan": plan.to_dict(),
        }

    def submit_url_and_rank(self, url: str, notes: str = "") -> dict[str, Any]:
        """Submit a URL and get full analysis."""
        idea = self._inbox.submit_url(url, notes=notes)
        analysis = self._analysis_engine.analyze_url(url)
        score = self._scoring_engine.score_from_analysis(analysis)
        debate = self._debate_engine.debate(analysis, score)

        return {
            "idea": {"id": idea.idea_id, "url": url},
            "analysis": analysis,
            "score": score.to_dict(),
            "debate": debate.to_dict(),
        }

    # ── Evolution Cycle ────────────────────────────────────

    def run_evolution_cycle(self) -> dict[str, Any]:
        """Run one full idea evolution cycle.

        Process:
            1. Scan pending human ideas
            2. Score each
            3. Rank top opportunities
            4. Generate experiment plans
            5. Return actionable list
        """
        pending = self._inbox.get_pending()
        results = []

        for idea in pending[:10]:  # Process top 10
            result = self.submit_and_rank(idea.description, creator=idea.creator)
            results.append(result)
            if result["debate"]["final_vote"] in ("build", "prototype"):
                self._inbox.approve(idea.idea_id)

        # Rank by score
        results.sort(key=lambda r: r["score"]["total"], reverse=True)

        # Publish top 3 to marketplace
        for r in results[:3]:
            genome = Genome(name=r["idea"]["title"])
            self._marketplace.publish(
                genome=genome,
                d7_roas=r["score"]["total"] / 100,  # proxy
                category=r["analysis"].get("category", ""),
            )

        return {
            "cycle_results": len(results),
            "approved_count": sum(1 for r in results if r["debate"]["final_vote"] in ("build", "prototype")),
            "top_suggestions": results[:3],
            "approval_rates": self._feedback_loop.get_approval_rates(),
            "marketplace_size": len(self._marketplace.get_all()),
        }

    # ── Helpers ────────────────────────────────────────────

    @staticmethod
    def _extract_tags(text: str) -> list[str]:
        text_lower = text.lower()
        tags = []
        for t in ["merge", "sort", "puzzle", "simulation", "dragon", "pet",
                   "3d", "collection", "factory", "home", "rescue"]:
            if t in text_lower:
                tags.append(t)
        return tags

    @staticmethod
    def _make_opportunity(idea: HumanIdea, score: CreativeScore) -> Opportunity:
        return Opportunity(
            name=idea.title,
            description=idea.description,
            score=score.total,
            confidence=score.confidence,
            metadata={"idea_id": idea.idea_id},
        )
