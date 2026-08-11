"""Creative Hypothesis Engine — turn opportunities into testable experiment plans."""

from __future__ import annotations

from typing import Any

from market_ops.creative_opportunity.schemas import (
    Opportunity,
    ExperimentPlan,
    ExperimentVariant,
    OpportunityCategory,
)


class HypothesisEngine:
    """Generate hypotheses and experiment plans from opportunities."""

    def generate(self, opportunity: Opportunity) -> ExperimentPlan:
        """Generate a full experiment plan from an opportunity.

        Returns:
            ExperimentPlan with hypothesis, variants, and success metrics.
        """
        hypothesis = self._build_hypothesis(opportunity)
        variants = self._build_variants(opportunity)
        budget = self._estimate_budget(variants)

        return ExperimentPlan(
            hypothesis=hypothesis,
            opportunity_id=opportunity.opportunity_id,
            variants=variants,
            success_metrics=["CTR", "CVR", "D7_ROAS", "CPI"],
            estimated_budget=budget,
            estimated_duration_days=7,
        )

    def generate_batch(self, opportunities: list[Opportunity]) -> list[ExperimentPlan]:
        """Generate experiment plans for multiple opportunities."""
        return [self.generate(opp) for opp in opportunities]

    # ── Hypothesis Building ─────────────────────────────────

    @staticmethod
    def _build_hypothesis(opportunity: Opportunity) -> str:
        """Build a testable hypothesis from opportunity."""
        category_hypotheses: dict[OpportunityCategory, str] = {
            OpportunityCategory.GAMEPLAY_INNOVATION: (
                f"Users will engage more with {opportunity.name} "
                f"because the hybrid gameplay mechanic combines proven elements "
                f"({', '.join(opportunity.reference_games[:2]) or 'similar games'})."
            ),
            OpportunityCategory.VISUAL_TREND: (
                f"Ads using {opportunity.name} visual style will achieve "
                f"higher CTR due to novelty and aesthetic appeal in the current market."
            ),
            OpportunityCategory.MONETIZATION_TREND: (
                f"Implementing {opportunity.name} will improve LTV/CPI ratio "
                f"without negatively impacting retention."
            ),
            OpportunityCategory.UA_OPPORTUNITY: (
                f"{opportunity.name} represents an underpriced UA channel/trend "
                f"that can deliver CPI below current benchmarks."
            ),
            OpportunityCategory.MARKET_GAP: (
                f"{opportunity.name} addresses an underserved segment with "
                f"low competition and strong player demand signals."
            ),
        }
        return category_hypotheses.get(
            opportunity.category,
            f"{opportunity.name} will outperform current creatives based on market signals.",
        )

    # ── Variant Building ────────────────────────────────────

    @staticmethod
    def _build_variants(opportunity: Opportunity) -> list[ExperimentVariant]:
        """Build A/B/C test variants from opportunity."""
        variants: list[ExperimentVariant] = []
        tags = [t.lower() for t in opportunity.tags]

        # Variant A: Core mechanic emphasis
        variants.append(
            ExperimentVariant(
                name="A: Core Mechanic",
                description=f"Focus on core {opportunity.name} gameplay loop.",
                genome_hint=HypothesisEngine._build_genome_hint(opportunity, "core"),
            )
        )

        # Variant B: Emotional hook
        variants.append(
            ExperimentVariant(
                name="B: Emotional Hook",
                description="Lead with emotional payoff and progression satisfaction.",
                genome_hint=HypothesisEngine._build_genome_hint(opportunity, "emotion"),
            )
        )

        # Variant C: Visual spectacle (if visual-related) or secondary mechanic
        if any(t in tags for t in ["3d", "visual", "animation", "style"]):
            variants.append(
                ExperimentVariant(
                    name="C: Visual Spectacle",
                    description="Emphasize visual quality and stunning effects.",
                    genome_hint=HypothesisEngine._build_genome_hint(opportunity, "visual"),
                )
            )
        else:
            variants.append(
                ExperimentVariant(
                    name="C: Secondary Mechanic",
                    description="Introduce a supporting mechanic to deepen engagement.",
                    genome_hint=HypothesisEngine._build_genome_hint(opportunity, "secondary"),
                )
            )

        return variants

    @staticmethod
    def _build_genome_hint(opportunity: Opportunity, variant_type: str) -> dict[str, Any]:
        """Build a genome hint for a specific variant."""
        tags = [t.lower() for t in opportunity.tags]

        # Extract primary mechanic
        mechanic = "merge"
        for m in ["merge", "sort", "puzzle", "simulation", "battle", "build"]:
            if m in tags:
                mechanic = m
                break

        # Extract theme
        theme = "fantasy"
        for t in ["factory", "home", "pet", "dragon", "cozy", "magic"]:
            if t in tags:
                theme = t
                break

        hints: dict[str, Any] = {
            "gameplay_gene": {
                "mechanic": mechanic,
                "difficulty": "easy",
            },
            "visual_gene": {
                "style": "3d_cartoon" if "3d" in tags else "2d_bright",
                "theme": theme,
            },
            "hook_gene": {
                "type": "rescue" if variant_type == "emotion" else "reward",
                "duration": 3,
            },
            "reward_gene": {
                "type": "evolution" if "evolution" in tags else "growth",
                "reveal_time": 8,
            },
            "pacing_gene": {
                "cuts": "fast" if variant_type == "core" else "build_up",
                "duration": 15,
            },
            "cta_gene": {
                "type": "play_now",
                "position": "end",
            },
        }

        if variant_type == "visual":
            hints["visual_gene"]["camera"] = "close_up"
            hints["visual_gene"]["effects"] = "particle_burst"
        elif variant_type == "secondary":
            hints["gameplay_gene"]["secondary"] = "collection"

        return hints

    @staticmethod
    def _estimate_budget(variants: list[ExperimentVariant]) -> float:
        """Estimate test budget based on number of variants."""
        base_budget = 300.0  # per variant
        return round(len(variants) * base_budget, 2)
