"""Phase D.1 — Creative Genome Builder.

Bridges CreativePerformance + CreativeDNA → V5 Genome.

Core flow:
    1292 creatives (CSV)
        +
    DNA inference (from creative_name)
        +
    Performance metrics (ROAS, CTR, CPI)
        ↓
    Genome (Gen 0)
        ↓
    Population (seed)

Usage:
    builder = CreativeGenomeBuilder()
    population = builder.build_seed_population()
    builder.save()  # Persist genome database
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from market_ops.creative_performance_builder import (
    CreativePerformance,
    CreativePerformanceBuilder,
)
from market_ops.creative_brain.v5_evolution.schemas import (
    Genome,
    Gene,
    GeneType,
    Fitness,
    FitnessComponent,
    Population,
)
from market_ops.creative_brain.v5_evolution.genome_manager import GenomeManager
from market_ops.creative_brain.v5_evolution.population_manager import PopulationManager
from market_ops.creative_brain.v5_evolution.fitness_calculator import FitnessCalculator


# ═══════════════════════════════════════════════════════════
# Seed Fitness Weights — simplified for available metrics
# ═══════════════════════════════════════════════════════════

SEED_FITNESS_WEIGHTS: dict[str, float] = {
    FitnessComponent.CTR.value: 0.20,
    FitnessComponent.CVR.value: 0.10,
    FitnessComponent.ROAS_D7.value: 0.45,
    FitnessComponent.CPI.value: -0.15,
    FitnessComponent.DIVERSITY_BONUS.value: 0.05,
    FitnessComponent.NOVELTY_BONUS.value: 0.05,
}


# ═══════════════════════════════════════════════════════════
# Mutation Pools — domain values extracted from _infer_labels
#   + expanded with V5 domain vocabulary
# ═══════════════════════════════════════════════════════════

DEFAULT_MUTATION_POOLS: dict[str, list[str]] = {
    "hook": [
        "crisis", "reward", "twist",
        "rescue", "escape", "protect", "revenge",
        "save", "help", "danger",
    ],
    "emotion": [
        "anxiety", "satisfaction", "healing",
        "cute", "fear", "curiosity", "excitement", "relax",
    ],
    "pacing": [
        "fast", "slow", "build_up", "explosive", "mid",
    ],
    "gameplay": [
        "merge", "build", "battle",
        "puzzle", "sort", "simulation",
    ],
    "story": [
        "ugc", "gameplay", "image",
        "story", "comparison", "tutorial",
    ],
    "visual": [
        "large_subtitle", "suspense_subtitle", "dense_subtitle", "minimal",
        "3d_cartoon", "close_up", "bright", "dark", "realistic",
    ],
    "platform": [
        "ios", "android", "facebook", "tiktok", "google",
    ],
    "audience": [
        "us", "tw", "jp", "global", "eu", "sea", "hk", "gb", "de",
    ],
    "character": [
        "dragon", "cat", "monster", "witch", "phoenix",
        "baby_dragon", "mermaid", "vampire", "fairy",
    ],
    "reward": [
        "growth", "evolution", "collection",
        "baby_dragon", "phoenix", "upgrade", "unlock",
    ],
}


# ═══════════════════════════════════════════════════════════
# DNA → Gene Mapping
# ═══════════════════════════════════════════════════════════

DNA_FIELD_TO_GENE_TYPE: dict[str, GeneType] = {
    "hook_type": GeneType.HOOK,
    "emotion": GeneType.EMOTION,
    "pace": GeneType.PACING,
    "ui_type": GeneType.GAMEPLAY,
    "video_structure": GeneType.STORY,
    "subtitle_style": GeneType.VISUAL,
    # Supplementary fields stored as gene metadata
    "first_3s_density": GeneType.PACING,
    "conflict_strength": GeneType.HOOK,
    "cta_strength": GeneType.VISUAL,
    "copy_style": GeneType.STORY,
}

# Supplementary DNA fields that enrich primary genes (stored in gene.metadata)
SUPPLEMENTARY_FIELDS: dict[str, str] = {
    "first_3s_density": "pacing",
    "conflict_strength": "hook",
    "cta_strength": "visual",
    "copy_style": "story",
}


# ═══════════════════════════════════════════════════════════
# Creative Genome Builder
# ═══════════════════════════════════════════════════════════

class CreativeGenomeBuilder:
    """Builds V5 Genomes from CreativePerformance + inferred DNA."""

    def __init__(
        self,
        performance_builder: CreativePerformanceBuilder | None = None,
        genome_manager: GenomeManager | None = None,
        fitness_calculator: FitnessCalculator | None = None,
    ) -> None:
        self._perf_builder = performance_builder or CreativePerformanceBuilder()
        self._genome_manager = genome_manager or GenomeManager()
        self._fitness_calc = fitness_calculator or FitnessCalculator(
            weights=SEED_FITNESS_WEIGHTS
        )

    # ── Public API ──────────────────────────────────────────

    def build_genome(
        self,
        performance: CreativePerformance,
        dna_labels: dict[str, str] | None = None,
    ) -> Genome:
        """Build a single Genome from CreativePerformance + DNA labels.

        If dna_labels not provided, infers from creative_name.
        """
        labels = dna_labels or self._infer_dna(performance.creative_name)
        genes, supplementary_meta = self._build_genes(labels, performance)
        fitness = self._build_fitness(performance)

        metadata = {
            "creative_id": performance.creative_id,
            "platform": performance.platform,
            "country": performance.country,
            "campaign": performance.campaign,
            "is_winner": performance.is_winner,
            "decision": performance.decision,
            "confidence": performance.confidence,
            "source": "creative_performance_seed",
        }
        metadata.update(supplementary_meta)

        genome = Genome(
            name=performance.creative_name or performance.creative_id,
            generation=0,
            genes={g.gene_type.value: g for g in genes},
            fitness=fitness,
            metadata=metadata,
        )

        # Sync genome_id into fitness
        fitness.genome_id = genome.genome_id

        # Register with GenomeManager
        self._genome_manager.update_fitness(genome.genome_id, fitness)
        self._genome_manager._genomes[genome.genome_id] = genome
        if 0 not in self._genome_manager._by_generation:
            self._genome_manager._by_generation[0] = set()
        self._genome_manager._by_generation[0].add(genome.genome_id)

        return genome

    def build_seed_population(
        self,
        population_manager: PopulationManager | None = None,
    ) -> Population:
        """Build Generation 0 population from all creatives in CSV.

        Returns:
            Population containing all seed genomes.
        """
        performances = self._perf_builder.load()
        genomes: list[Genome] = []

        for perf in performances:
            try:
                genome = self.build_genome(perf)
                genomes.append(genome)
            except Exception:
                continue

        pop_mgr = population_manager or PopulationManager()
        population = pop_mgr.create_population(
            generation=0,
            genomes=genomes,
            metadata={
                "source": "creative_performance_seed",
                "total_creatives_processed": len(performances),
                "genomes_created": len(genomes),
                "build_timestamp": time.time(),
            },
        )

        # Score all genomes in population
        self._score_population(population)

        return population

    def save(self, output_dir: Path | None = None) -> dict[str, Path]:
        """Persist genome database + population to disk.

        Returns:
            Paths to saved files.
        """
        if output_dir is None:
            output_dir = Path("output/creative_factory/genome_db")
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = str(int(time.time()))

        # Save all genomes
        genomes_path = output_dir / f"genomes_seed_{suffix}.json"
        genomes_data = [g.to_dict() for g in self._genome_manager._genomes.values()]
        genomes_path.write_text(
            json.dumps(genomes_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # Save genome manager stats
        stats_path = output_dir / f"genome_stats_{suffix}.json"
        stats_path.write_text(
            json.dumps(self._genome_manager.get_stats(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return {
            "genomes": genomes_path,
            "stats": stats_path,
        }

    def get_summary(self) -> dict[str, Any]:
        """Get summary of built genomes."""
        stats = self._genome_manager.get_stats()
        genomes = list(self._genome_manager._genomes.values())
        winners = [g for g in genomes if g.metadata.get("is_winner")]
        with_fitness = [g for g in genomes if g.fitness is not None]

        return {
            "total_genomes": len(genomes),
            "winners": len(winners),
            "with_fitness": len(with_fitness),
            "avg_fitness": round(
                sum(g.fitness.composite_score for g in with_fitness) / max(1, len(with_fitness)), 4
            ) if with_fitness else 0.0,
            "best_fitness": round(
                max(g.fitness.composite_score for g in with_fitness), 4
            ) if with_fitness else 0.0,
            "by_decision": self._count_by_decision(genomes),
            "by_platform": self._count_by_platform(genomes),
            "stats": stats,
        }

    # ── Internal: DNA Inference ─────────────────────────────

    @staticmethod
    def _infer_dna(creative_name: str) -> dict[str, str]:
        """Infer DNA labels from creative name text (self-contained, no cv2 dep)."""
        text = (creative_name or "").lower()
        labels: dict[str, str] = {
            "hook_type": "unknown",
            "emotion": "unknown",
            "pace": "unknown",
            "ui_type": "unknown",
            "copy_style": "unknown",
            "cta_strength": "unknown",
            "video_structure": "unknown",
            "subtitle_style": "unknown",
            "first_3s_density": "unknown",
            "conflict_strength": "unknown",
        }

        rules: list[tuple[str, str, list[str]]] = [
            ("hook_type", "crisis", ["危机", "rescue", "save", "help", "困", "danger", "crisis"]),
            ("hook_type", "reward", ["爽", "win", "level", "reward", "bonus"]),
            ("hook_type", "twist", ["反转", "unexpected", "fail", "wrong"]),
            ("emotion", "anxiety", ["焦虑", "urgent", "快", "danger", "救"]),
            ("emotion", "satisfaction", ["爽", "win", "clear", "success"]),
            ("emotion", "healing", ["治愈", "home", "garden", "cozy", "relax"]),
            ("pace", "fast", ["fast", "quick", "快切", "short", "秒"]),
            ("pace", "slow", ["slow", "story", "剧情", "铺垫"]),
            ("ui_type", "merge", ["merge", "合成", "mermaid", "witch", "vampire"]),
            ("ui_type", "build", ["build", "home", "装修", "建造"]),
            ("ui_type", "battle", ["battle", "fight", "attack", "boss"]),
            ("copy_style", "strong_title", ["big text", "title", "headline", "大字", "标题"]),
            ("copy_style", "soft_title", ["ugc", "native", "story"]),
            ("cta_strength", "strong_cta", ["install", "download", "play now", "立即", "马上"]),
            ("cta_strength", "soft_cta", ["try", "看看", "story"]),
            ("video_structure", "ugc", ["ugc", "creator", "真人", "口播"]),
            ("video_structure", "gameplay", ["gameplay", "录屏", "screen", "playable"]),
            ("video_structure", "image", ["image", "图片", "素材"]),
            ("subtitle_style", "large_subtitle", ["大字", "big text", "caption"]),
            ("subtitle_style", "suspense_subtitle", ["悬疑", "why", "secret", "mystery"]),
            ("subtitle_style", "dense_subtitle", ["dense", "多字幕", "高密度"]),
            ("first_3s_density", "high_density", ["hook", "3s", "前三秒", "快切"]),
            ("first_3s_density", "low_density", ["slow", "铺垫"]),
            ("conflict_strength", "strong_conflict", ["危机", "救", "fail", "wrong", "fight", "danger"]),
            ("conflict_strength", "soft_conflict", ["cozy", "home", "治愈", "relax"]),
        ]

        for field, value, keywords in rules:
            if labels[field] != "unknown":
                continue
            if any(keyword.lower() in text for keyword in keywords):
                labels[field] = value

        return labels

    # ── Internal: Gene Building ─────────────────────────────

    @classmethod
    def _build_genes(
        cls,
        labels: dict[str, str],
        performance: CreativePerformance,
    ) -> tuple[list[Gene], dict[str, Any]]:
        """Convert DNA labels + performance into Gene objects + supplementary metadata."""
        genes: list[Gene] = []
        supplementary_meta: dict[str, Any] = {}

        # Handle supplementary fields (stored in genome metadata, not gene)
        for field, _primary_key in SUPPLEMENTARY_FIELDS.items():
            value = labels.get(field, "unknown")
            if value and value != "unknown":
                supplementary_meta[field] = value

        # Build primary genes from DNA fields
        for field, gene_type in DNA_FIELD_TO_GENE_TYPE.items():
            if field in SUPPLEMENTARY_FIELDS:
                continue  # Skip supplementary, already handled

            value = labels.get(field, "unknown") or "unknown"
            pool = cls._get_mutation_pool(gene_type, value)

            gene = Gene(
                gene_type=gene_type,
                value=value,
                mutation_pool=pool,
                mutation_probability=0.1,
                mutation_cost=cls._estimate_mutation_cost(gene_type, value),
                mutation_risk=cls._estimate_mutation_risk(gene_type, value),
                confidence=0.5 if value != "unknown" else 0.2,
                source="inferred_from_creative_name",
            )
            genes.append(gene)

        # Add PLATFORM gene from performance.platform
        platform_value = performance.platform or "unknown"
        genes.append(Gene(
            gene_type=GeneType.PLATFORM,
            value=platform_value,
            mutation_pool=DEFAULT_MUTATION_POOLS["platform"],
            mutation_probability=0.05,
            mutation_cost=0.05,
            mutation_risk=0.05,
            confidence=0.8,
            source="performance_platform",
        ))

        # Add AUDIENCE gene from performance.country
        audience_value = performance.country or "global"
        genes.append(Gene(
            gene_type=GeneType.AUDIENCE,
            value=audience_value.lower(),
            mutation_pool=DEFAULT_MUTATION_POOLS["audience"],
            mutation_probability=0.05,
            mutation_cost=0.05,
            mutation_risk=0.05,
            confidence=0.8,
            source="performance_country",
        ))

        # Add CHARACTER gene (inferred from creative_name / campaign)
        character_value = cls._infer_character(performance.creative_name)
        if character_value != "unknown":
            genes.append(Gene(
                gene_type=GeneType.CHARACTER,
                value=character_value,
                mutation_pool=DEFAULT_MUTATION_POOLS["character"],
                mutation_probability=0.15,
                mutation_cost=0.1,
                mutation_risk=0.1,
                confidence=0.4,
                source="inferred_from_creative_name",
            ))

        # Add REWARD gene (inferred from creative_name)
        reward_value = cls._infer_reward(performance.creative_name)
        if reward_value != "unknown":
            genes.append(Gene(
                gene_type=GeneType.REWARD,
                value=reward_value,
                mutation_pool=DEFAULT_MUTATION_POOLS["reward"],
                mutation_probability=0.15,
                mutation_cost=0.1,
                mutation_risk=0.1,
                confidence=0.4,
                source="inferred_from_creative_name",
            ))

        return genes, supplementary_meta

    @classmethod
    def _get_mutation_pool(cls, gene_type: GeneType, current_value: str) -> list[str]:
        """Get mutation pool for a gene type, ensuring current value is included."""
        pool = list(DEFAULT_MUTATION_POOLS.get(gene_type.value, []))
        if current_value not in pool:
            pool.append(current_value)
        if not pool:
            pool = ["unknown"]
        return pool

    @staticmethod
    def _estimate_mutation_cost(gene_type: GeneType, value: str) -> float:
        """Estimate how costly (risky) it is to mutate this gene."""
        # High-impact genes are more costly to mutate
        if gene_type in (GeneType.GAMEPLAY, GeneType.HOOK):
            return 0.2
        if gene_type in (GeneType.VISUAL, GeneType.CHARACTER):
            return 0.1
        return 0.05

    @staticmethod
    def _estimate_mutation_risk(gene_type: GeneType, value: str) -> float:
        """Estimate risk of performance degradation from mutation."""
        if gene_type == GeneType.GAMEPLAY:
            return 0.25  # Changing mechanic is risky
        if gene_type == GeneType.HOOK:
            return 0.15
        if gene_type in (GeneType.VISUAL, GeneType.CHARACTER):
            return 0.08
        return 0.05

    @staticmethod
    def _infer_character(text: str) -> str:
        """Infer character type from creative name."""
        text_lower = (text or "").lower()
        char_keywords: dict[str, list[str]] = {
            "dragon": ["dragon", "龙"],
            "witch": ["witch", "女巫"],
            "mermaid": ["mermaid", "美人鱼"],
            "vampire": ["vampire", "吸血鬼"],
            "cat": ["cat", "猫", "kitty"],
            "monster": ["monster", "怪物", "怪兽"],
            "baby_dragon": ["baby", "宝宝", "幼龙"],
            "phoenix": ["phoenix", "凤凰"],
        }
        for char, keywords in char_keywords.items():
            if any(kw in text_lower for kw in keywords):
                return char
        return "unknown"

    @staticmethod
    def _infer_reward(text: str) -> str:
        """Infer reward mechanism from creative name."""
        text_lower = (text or "").lower()
        reward_keywords: dict[str, list[str]] = {
            "evolution": ["evolution", "进化", "evolve"],
            "growth": ["growth", "grow", "成长", "升级"],
            "collection": ["collection", "collect", "收集"],
            "unlock": ["unlock", "解锁", "open"],
            "merge": ["merge", "合成", "融合"],
        }
        for reward, keywords in reward_keywords.items():
            if any(kw in text_lower for kw in keywords):
                return reward
        return "unknown"

    # ── Internal: Fitness Building ──────────────────────────

    def _build_fitness(self, performance: CreativePerformance) -> Fitness:
        """Build Fitness from CreativePerformance metrics."""
        components: dict[str, float] = {}

        if performance.ctr > 0:
            components[FitnessComponent.CTR.value] = performance.ctr
        if performance.roas > 0:
            components[FitnessComponent.ROAS_D7.value] = performance.roas
        if performance.cpi > 0:
            components[FitnessComponent.CPI.value] = performance.cpi

        # Estimate CVR from installs / (impressions estimate)
        # impressions ≈ installs / (CTR * typical CVR of 0.15)
        estimated_cvr = 0.0
        if performance.ctr > 0 and performance.installs > 0 and performance.spend > 0:
            estimated_impressions = performance.installs / max(0.001, performance.ctr * 0.15)
            estimated_clicks = estimated_impressions * performance.ctr
            if estimated_clicks > 0:
                estimated_cvr = performance.installs / estimated_clicks
                components[FitnessComponent.CVR.value] = round(estimated_cvr, 4)

        # Use installs as sample_size proxy
        sample_size = performance.installs

        # Use spend + revenue for confidence
        confidence = self._calculate_confidence(performance)

        composite = self._fitness_calc._compute_composite(components)
        category_scores = self._fitness_calc._compute_category_scores(components)

        return Fitness(
            genome_id="",  # Will be set after genome creation
            generation=0,
            components=components,
            component_weights=dict(self._fitness_calc.get_weights()),
            composite_score=composite,
            category_scores=category_scores,
            confidence=confidence,
            sample_size=sample_size,
            is_online=True,
        )

    @staticmethod
    def _calculate_confidence(performance: CreativePerformance) -> float:
        """Calculate data confidence from spend and installs."""
        if not performance.is_valid_sample:
            return 0.2
        if performance.spend >= 500 and performance.installs >= 100:
            return 0.9
        if performance.spend >= 200 and performance.installs >= 50:
            return 0.7
        if performance.spend >= 100 or performance.installs >= 30:
            return 0.5
        return 0.3

    # ── Internal: Population Scoring ────────────────────────

    def _score_population(self, population: Population) -> None:
        """Score all genomes in a population and update ranks."""
        scored = [g for g in population.genomes if g.fitness is not None]
        if not scored:
            return

        scored.sort(key=lambda g: g.fitness.composite_score, reverse=True)
        for rank, genome in enumerate(scored, 1):
            if genome.fitness:
                genome.fitness.rank_in_generation = rank
                genome.fitness.genome_id = genome.genome_id

        population.best_fitness = scored[0].fitness.composite_score
        population.avg_fitness = sum(g.fitness.composite_score for g in scored) / len(scored)
        population.median_fitness = scored[len(scored) // 2].fitness.composite_score

    # ── Internal: Summary Helpers ───────────────────────────

    @staticmethod
    def _count_by_decision(genomes: list[Genome]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for g in genomes:
            decision = g.metadata.get("decision", "unknown")
            counts[decision] = counts.get(decision, 0) + 1
        return counts

    @staticmethod
    def _count_by_platform(genomes: list[Genome]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for g in genomes:
            platform = g.metadata.get("platform", "unknown")
            counts[platform] = counts.get(platform, 0) + 1
        return counts


# ═══════════════════════════════════════════════════════════
# CLI / Standalone Entry Point
# ═══════════════════════════════════════════════════════════

def build_seed_population_cli() -> dict[str, Any]:
    """CLI entry point for building seed population.

    Returns:
        Summary of the built population.
    """
    builder = CreativeGenomeBuilder()
    population = builder.build_seed_population()
    summary = builder.get_summary()
    saved = builder.save()

    return {
        "population": population.to_dict(),
        "summary": summary,
        "saved_paths": {k: str(v) for k, v in saved.items()},
    }


if __name__ == "__main__":
    result = build_seed_population_cli()
    print(json.dumps(result, ensure_ascii=False, indent=2))
