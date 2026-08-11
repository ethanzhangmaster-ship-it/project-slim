"""E6: Creative Genome Marketplace — verified genome library.

A searchable, performance-indexed library of creative genomes.

Features:
  - CRUD for verified genomes with performance data
  - Search by gene type, ROAS, CTR, category
  - Genome combination (A + B → new concept)
  - Template library for proven patterns
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from market_ops.creative_brain.v5_evolution.schemas import Genome, Gene, GeneType


@dataclass
class VerifiedGenome:
    """A genome with verified performance data."""
    genome_id: str = ""
    name: str = ""
    category: str = ""
    genes: dict[str, str] = field(default_factory=dict)
    d7_roas: float = 0.0
    total_spend: float = 0.0
    total_creatives: int = 0
    success_level: str = "unknown"  # "high", "medium", "low"
    tags: list[str] = field(default_factory=list)
    created_from: str = ""  # source opportunity/idea

    def to_dict(self) -> dict[str, Any]:
        return {
            "genome_id": self.genome_id,
            "name": self.name,
            "category": self.category,
            "genes": self.genes,
            "d7_roas": round(self.d7_roas, 3),
            "total_spend": round(self.total_spend, 2),
            "total_creatives": self.total_creatives,
            "success_level": self.success_level,
            "tags": self.tags,
            "created_from": self.created_from,
        }

    @property
    def is_winner(self) -> bool:
        return self.d7_roas >= 1.0 and self.total_spend >= 100


@dataclass
class GenomeCombo:
    """A combination of two genomes → new concept."""
    genome_a: str = ""
    genome_b: str = ""
    combo_name: str = ""
    description: str = ""
    shared_genes: list[str] = field(default_factory=list)
    new_gene_suggestions: list[str] = field(default_factory=list)
    predicted_score: float = 0.0


class GenomeMarketplace:
    """Searchable library of verified creative genomes.

    Usage:
        marketplace = GenomeMarketplace()
        marketplace.publish(genome, performance_data)
        results = marketplace.search(category="merge", min_roas=1.0)
        combos = marketplace.suggest_combinations()
    """

    def __init__(self, storage_dir: Path | None = None) -> None:
        self._genomes: list[VerifiedGenome] = []
        self._storage_dir = storage_dir

    # ── CRUD ──────────────────────────────────────────────

    def publish(
        self,
        genome: Genome,
        d7_roas: float,
        total_spend: float = 0,
        total_creatives: int = 0,
        category: str = "",
        tags: list[str] | None = None,
    ) -> VerifiedGenome:
        """Publish a genome to the marketplace."""
        success = "high" if d7_roas >= 1.0 else ("medium" if d7_roas >= 0.5 else "low")

        vg = VerifiedGenome(
            genome_id=genome.genome_id,
            name=genome.name,
            category=category or genome.metadata.get("category", "unknown"),
            genes={k: v.value for k, v in genome.genes.items()},
            d7_roas=d7_roas,
            total_spend=total_spend,
            total_creatives=total_creatives,
            success_level=success,
            tags=tags or genome.metadata.get("tags", []),
            created_from=genome.metadata.get("opportunity_id", ""),
        )
        self._genomes.append(vg)
        return vg

    def get_all(self) -> list[VerifiedGenome]:
        return list(self._genomes)

    def get_winner_genomes(self) -> list[VerifiedGenome]:
        return [g for g in self._genomes if g.is_winner]

    def get_by_category(self, category: str) -> list[VerifiedGenome]:
        return [g for g in self._genomes if g.category == category]
    # ── Search ────────────────────────────────────────────

    def search(
        self,
        category: str | None = None,
        min_roas: float | None = None,
        success_level: str | None = None,
        tag: str | None = None,
        limit: int = 20,
    ) -> list[VerifiedGenome]:
        """Search marketplace with filters."""
        results = self._genomes

        if category:
            results = [g for g in results if g.category == category]
        if min_roas is not None:
            results = [g for g in results if g.d7_roas >= min_roas]
        if success_level:
            results = [g for g in results if g.success_level == success_level]
        if tag:
            results = [g for g in results if tag in g.tags]

        results.sort(key=lambda g: g.d7_roas, reverse=True)
        return results[:limit]

    def search_by_gene(self, gene_type: str, gene_value: str) -> list[VerifiedGenome]:
        """Find genomes with a specific gene value."""
        return [
            g for g in self._genomes
            if g.genes.get(gene_type) == gene_value
        ]

    # ── Combinations ──────────────────────────────────────

    def suggest_combinations(self) -> list[GenomeCombo]:
        """Suggest combinations of winner genomes → new concepts.

        Finds pairs of winner genomes in different categories.
        """
        winners = self.get_winner_genomes()
        if len(winners) < 2:
            return []

        combos: list[GenomeCombo] = []

        for i in range(len(winners)):
            for j in range(i + 1, len(winners)):
                a, b = winners[i], winners[j]
                if a.category == b.category:
                    continue  # same category, skip

                shared = list(set(a.genes.keys()) & set(b.genes.keys()))
                new_suggestions = list(set(a.genes.keys()) ^ set(b.genes.keys()))

                combo = GenomeCombo(
                    genome_a=a.name,
                    genome_b=b.name,
                    combo_name=f"{a.name} + {b.name}",
                    description=f"Combines {a.name} ({a.category}) with {b.name} ({b.category})",
                    shared_genes=shared,
                    new_gene_suggestions=new_suggestions,
                    predicted_score=round(min(95, (a.d7_roas + b.d7_roas) / 2 * 40 + 30), 0),
                )
                combos.append(combo)

        return sorted(combos, key=lambda c: c.predicted_score, reverse=True)

    def get_templates(self) -> list[VerifiedGenome]:
        """Return genomes suitable as templates (high success)."""
        return [g for g in self._genomes if g.success_level == "high" and g.total_creatives >= 5]

    # ── Persistence ───────────────────────────────────────

    def save(self, path: Path | None = None) -> Path:
        """Persist marketplace to disk."""
        if path is None and self._storage_dir:
            path = self._storage_dir / "genome_marketplace.json"
        if path is None:
            path = Path("output/genome_marketplace.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        data = [g.to_dict() for g in self._genomes]
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def load(self, path: Path) -> None:
        """Load marketplace from disk."""
        data = json.loads(path.read_text(encoding="utf-8"))
        for d in data:
            self._genomes.append(VerifiedGenome(
                genome_id=d["genome_id"],
                name=d["name"],
                category=d["category"],
                genes=d["genes"],
                d7_roas=d["d7_roas"],
                total_spend=d["total_spend"],
                total_creatives=d["total_creatives"],
                success_level=d["success_level"],
                tags=d["tags"],
                created_from=d.get("created_from", ""),
            ))
