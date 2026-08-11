"""Opportunity Genome Builder — convert Opportunity into V5 Creative Genome.

Bridges Opportunity Intelligence Layer → V5 Evolution System.
"""

from __future__ import annotations

from typing import Any

from market_ops.creative_opportunity.schemas import Opportunity, ExperimentVariant
from market_ops.creative_brain.v5_evolution.schemas import Genome, Gene, GeneType
from market_ops.creative_brain.v5_evolution.genome_manager import GenomeManager


class OpportunityGenomeBuilder:
    """Build V5 Genomes from Opportunities (for Creative Factory input)."""

    def __init__(self, genome_manager: GenomeManager | None = None) -> None:
        self._genome_manager = genome_manager or GenomeManager()

    def build_from_opportunity(self, opportunity: Opportunity) -> Genome:
        """Convert an Opportunity into a V5 Genome.

        Uses opportunity tags + metadata to construct genes.
        Genome is registered in GenomeManager for evolution tracking.
        """
        tags = [t.lower() for t in opportunity.tags]
        name = opportunity.name or "unnamed_opportunity"

        genes = self._construct_genes(opportunity, tags)

        genome = Genome(
            name=name,
            generation=0,
            genes={g.gene_type.value: g for g in genes},
            metadata={
                "opportunity_id": opportunity.opportunity_id,
                "source": "opportunity_intelligence",
                "category": opportunity.category.value,
                "score": opportunity.score,
                "confidence": opportunity.confidence,
                "reference_games": opportunity.reference_games,
                "tags": opportunity.tags,
            },
        )

        # Register
        self._genome_manager._genomes[genome.genome_id] = genome
        if 0 not in self._genome_manager._by_generation:
            self._genome_manager._by_generation[0] = set()
        self._genome_manager._by_generation[0].add(genome.genome_id)

        return genome

    def build_from_variant(self, variant: ExperimentVariant, opportunity: Opportunity) -> Genome:
        """Build a Genome from an experiment variant's genome_hint."""
        genes = self._genes_from_hint(variant.genome_hint)

        genome = Genome(
            name=f"{opportunity.name} — {variant.name}",
            generation=0,
            genes={g.gene_type.value: g for g in genes},
            metadata={
                "opportunity_id": opportunity.opportunity_id,
                "variant_id": variant.variant_id,
                "source": "experiment_variant",
            },
        )

        self._genome_manager._genomes[genome.genome_id] = genome
        if 0 not in self._genome_manager._by_generation:
            self._genome_manager._by_generation[0] = set()
        self._genome_manager._by_generation[0].add(genome.genome_id)

        return genome

    # ── Gene Construction ───────────────────────────────────

    def _construct_genes(self, opportunity: Opportunity, tags: list[str]) -> list[Gene]:
        """Build Gene list from opportunity data."""
        genes: list[Gene] = []

        # HOOK gene
        hook_type = self._detect_hook(tags, opportunity.description)
        genes.append(Gene(
            gene_type=GeneType.HOOK,
            value=hook_type,
            mutation_pool=[hook_type, "rescue", "reward", "twist", "escape"],
            mutation_probability=0.15,
            confidence=0.6,
            source="opportunity_inference",
        ))

        # GAMEPLAY gene
        mechanic = self._detect_mechanic(tags)
        genes.append(Gene(
            gene_type=GeneType.GAMEPLAY,
            value=mechanic,
            mutation_pool=[mechanic, "merge", "sort", "puzzle", "simulation", "build"],
            mutation_probability=0.12,
            confidence=0.7,
            source="opportunity_inference",
        ))

        # VISUAL gene
        visual_style = self._detect_visual(tags)
        genes.append(Gene(
            gene_type=GeneType.VISUAL,
            value=visual_style,
            mutation_pool=[visual_style, "3d_cartoon", "2d_bright", "realistic", "minimal"],
            mutation_probability=0.10,
            confidence=0.5,
            source="opportunity_inference",
        ))

        # EMOTION gene
        emotion = self._detect_emotion(tags, opportunity.description)
        genes.append(Gene(
            gene_type=GeneType.EMOTION,
            value=emotion,
            mutation_pool=[emotion, "curiosity", "satisfaction", "anxiety", "excitement"],
            mutation_probability=0.10,
            confidence=0.5,
            source="opportunity_inference",
        ))

        # PACING gene
        pacing = "fast" if "fast" in tags or "quick" in tags else "mid"
        genes.append(Gene(
            gene_type=GeneType.PACING,
            value=pacing,
            mutation_pool=[pacing, "fast", "slow", "build_up", "explosive"],
            mutation_probability=0.08,
            confidence=0.6,
            source="opportunity_inference",
        ))

        # STORY gene
        story = "gameplay" if "gameplay" in tags else "progression"
        genes.append(Gene(
            gene_type=GeneType.STORY,
            value=story,
            mutation_pool=[story, "ugc", "tutorial", "comparison", "challenge"],
            mutation_probability=0.08,
            confidence=0.4,
            source="opportunity_inference",
        ))

        return genes

    def _genes_from_hint(self, hint: dict[str, Any]) -> list[Gene]:
        """Build genes from experiment variant genome_hint."""
        genes: list[Gene] = []

        gene_type_map = {
            "hook_gene": GeneType.HOOK,
            "gameplay_gene": GeneType.GAMEPLAY,
            "visual_gene": GeneType.VISUAL,
            "reward_gene": GeneType.REWARD,
            "pacing_gene": GeneType.PACING,
            "cta_gene": GeneType.PLATFORM,  # closest match
            "character_gene": GeneType.CHARACTER,
        }

        for hint_key, gene_type in gene_type_map.items():
            if hint_key in hint:
                data = hint[hint_key]
                if isinstance(data, dict):
                    # Use primary value or serialize
                    value = data.get("type") or data.get("mechanic") or data.get("style") or str(data)
                else:
                    value = str(data)
                genes.append(Gene(
                    gene_type=gene_type,
                    value=value,
                    mutation_pool=[value],
                    mutation_probability=0.1,
                    confidence=0.7,
                    source="experiment_variant_hint",
                ))

        return genes

    # ── Detection Helpers ───────────────────────────────────

    @staticmethod
    def _detect_mechanic(tags: list[str]) -> str:
        for m in ["merge", "sort", "puzzle", "simulation", "battle", "build"]:
            if m in tags:
                return m
        return "merge"

    @staticmethod
    def _detect_hook(tags: list[str], description: str) -> str:
        text = " ".join(tags) + " " + description.lower()
        if any(w in text for w in ["rescue", "save", "help", "danger"]):
            return "rescue"
        if any(w in text for w in ["reward", "win", "bonus", "jackpot"]):
            return "reward"
        if any(w in text for w in ["twist", "unexpected", "fail", "wrong"]):
            return "twist"
        return "reward"

    @staticmethod
    def _detect_visual(tags: list[str]) -> str:
        if "3d" in tags:
            return "3d_cartoon"
        if "cozy" in tags or "home" in tags:
            return "cozy_bright"
        return "2d_bright"

    @staticmethod
    def _detect_emotion(tags: list[str], description: str) -> str:
        text = " ".join(tags) + " " + description.lower()
        if any(w in text for w in ["cozy", "heal", "relax", "home"]):
            return "satisfaction"
        if any(w in text for w in ["danger", "crisis", "urgent"]):
            return "anxiety"
        if any(w in text for w in ["exciting", "fast", "explosive"]):
            return "excitement"
        return "curiosity"
