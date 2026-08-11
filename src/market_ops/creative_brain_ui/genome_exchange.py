"""E6.3: Genome Exchange — Creative DNA as Tradable Assets.

Upgrades GenomeMarketplace from database to exchange:
  - Genome Asset: complete financial profile of a creative DNA
  - Historical performance across multiple projects
  - Cross-project genome reuse tracking
  - "Golden Genome" designation for top performers
  - Genome combination portfolio (A + B → C tracking)

This turns "creative DNA" into an actual asset class.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from market_ops.creative_brain.v5_evolution.schemas import Genome
from market_ops.creative_brain_ui.genome_value import GenomeValueEngine, GenomeValuation, GenomeTier


@dataclass
class GenomeAsset:
    """A creative genome as a financial asset."""
    asset_id: str = ""
    genome: Genome | None = None
    # Performance across projects
    projects_used: list[str] = field(default_factory=list)
    total_creatives_deployed: int = 0
    total_spend: float = 0.0
    total_revenue: float = 0.0
    avg_roas: float = 0.0
    avg_ctr: float = 0.0
    best_roas: float = 0.0
    # Valuation
    valuation: GenomeValuation | None = None
    tier: GenomeTier = GenomeTier.BRONZE
    is_golden: bool = False
    # Metadata
    date_created: str = field(default_factory=lambda: datetime.now().isoformat())
    date_last_used: str = ""
    total_derivatives: int = 0    # How many variations produced
    derivative_success_rate: float = 0.0
    royalty_score: float = 0.0     # How much this genome "earns" for the exchange

    def __post_init__(self) -> None:
        if not self.asset_id:
            import uuid
            self.asset_id = f"asset_{str(uuid.uuid4())[:8]}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "genome_name": self.genome.name if self.genome else "unknown",
            "projects": len(self.projects_used),
            "avg_roas": round(self.avg_roas, 3),
            "best_roas": round(self.best_roas, 3),
            "tier": self.tier.value,
            "is_golden": self.is_golden,
            "total_derivatives": self.total_derivatives,
            "derivative_success_rate": round(self.derivative_success_rate, 3),
        }


@dataclass
class GenomePortfolio:
    """A collection of genome assets for a game/project."""
    project_name: str = ""
    assets: list[GenomeAsset] = field(default_factory=list)
    total_value: float = 0.0
    diversification_score: float = 0.0  # 0-1, how diverse is the portfolio
    best_performing: str = ""  # asset_id of top performer

    def to_dict(self) -> dict[str, Any]:
        return {
            "project": self.project_name,
            "assets": len(self.assets),
            "total_value": round(self.total_value, 1),
            "diversification": round(self.diversification_score, 2),
            "best": self.best_performing,
        }


class GenomeExchange:
    """The genome asset exchange — tracks, values, and combines genome assets.

    Key difference from GenomeMarketplace:
      - Marketplace: store + search genomes
      - Exchange: track genome performance as assets + enable portfolio management

    Usage:
        exchange = GenomeExchange()
        exchange.register_genome(genome, d7_roas=1.5, project="P04 Witch Merge")
        exchange.record_derivative(parent_genome, child_genome, was_successful=True)
        portfolio = exchange.build_portfolio("P04 Witch Merge")
    """

    def __init__(self) -> None:
        self._value_engine = GenomeValueEngine()
        self._assets: dict[str, GenomeAsset] = {}
        self._by_project: dict[str, list[str]] = {}  # project → asset_ids
        self._derivative_graph: dict[str, list[str]] = {}  # parent → children
        self._golden_genomes: list[str] = []  # asset_ids of golden genomes

    # ── Registration ────────────────────────────────────────

    def register_genome(
        self,
        genome: Genome,
        d7_roas: float = 0.0,
        ctr: float = 0.0,
        installs: int = 0,
        project: str = "",
        category: str = "",
    ) -> GenomeAsset:
        """Register a genome as an exchange asset.

        If already exists, updates performance history.
        """
        existing = self._find_by_genome(genome)
        if existing:
            return self._update_asset(existing, d7_roas, ctr, installs, project)

        valuation = self._value_engine.evaluate(genome, d7_roas=d7_roas, ctr=ctr,
                                                 installs=installs, market_heat=85)

        asset = GenomeAsset(
            genome=genome,
            valuation=valuation,
            tier=valuation.tier,
            is_golden=valuation.tier == GenomeTier.PLATINUM,
            projects_used=[project] if project else [],
            total_creatives_deployed=1,
            total_spend=d7_roas * 100 if d7_roas > 0 else 50,
            total_revenue=d7_roas * 100 * (d7_roas if d7_roas > 0 else 0.5),
            avg_roas=d7_roas,
            avg_ctr=ctr,
            best_roas=d7_roas,
        )

        self._assets[asset.asset_id] = asset
        if project:
            self._by_project.setdefault(project, []).append(asset.asset_id)
        if asset.is_golden:
            self._golden_genomes.append(asset.asset_id)

        return asset

    def record_derivative(
        self, parent: Genome, child: Genome, was_successful: bool, roas: float = 0,
    ) -> None:
        """Record that a genome was derived from another genome.

        Tracks the "family tree" of genome mutations.
        """
        parent_asset = self._find_by_genome(parent)
        if parent_asset:
            parent_asset.total_derivatives += 1
            if was_successful:
                parent_asset.derivative_success_rate = (
                    parent_asset.derivative_success_rate * (parent_asset.total_derivatives - 1) + 1
                ) / parent_asset.total_derivatives
            else:
                parent_asset.derivative_success_rate = (
                    parent_asset.derivative_success_rate * (parent_asset.total_derivatives - 1)
                ) / parent_asset.total_derivatives

        self._derivative_graph.setdefault(parent.genome_id, []).append(child.genome_id)

        # Update royalty score: successful derivatives increase parent value
        if parent_asset and was_successful:
            parent_asset.royalty_score += 0.1
            # Recalculate: if royalty > 0.5, upgrade tier
            if parent_asset.royalty_score > 0.5 and parent_asset.tier != GenomeTier.PLATINUM:
                parent_asset.tier = GenomeTier.PLATINUM
                parent_asset.is_golden = True
                if parent_asset.asset_id not in self._golden_genomes:
                    self._golden_genomes.append(parent_asset.asset_id)

    # ── Query ───────────────────────────────────────────────

    def get_asset(self, asset_id: str) -> GenomeAsset | None:
        return self._assets.get(asset_id)

    def get_golden_genomes(self) -> list[GenomeAsset]:
        """Get platinum-tier (golden) genome assets."""
        return [self._assets[aid] for aid in self._golden_genomes if aid in self._assets]

    def get_by_project(self, project: str) -> list[GenomeAsset]:
        """Get all genome assets used in a project."""
        aids = self._by_project.get(project, [])
        return [self._assets[aid] for aid in aids if aid in self._assets]

    def get_derivative_tree(self, genome_id: str) -> dict[str, Any]:
        """Get the full derivative family tree."""
        children = self._derivative_graph.get(genome_id, [])
        return {
            "genome_id": genome_id,
            "derivatives": len(children),
            "children": children,
        }

    def build_portfolio(self, project: str) -> GenomePortfolio:
        """Build a portfolio for a project.

        Shows: total value, diversification, top performer.
        """
        assets = self.get_by_project(project)
        if not assets:
            return GenomePortfolio(project_name=project)

        total_value = sum(a.valuation.total_value for a in assets if a.valuation)
        gene_sets = [set(a.genome.genes.keys()) for a in assets if a.genome]
        all_genes = set()
        for gs in gene_sets:
            all_genes.update(gs)
        unique_ratio = len(all_genes) / max(1, sum(len(gs) for gs in gene_sets))
        # Diversification: mix of different gene types
        div_score = max(0, min(1, unique_ratio * 2))

        best = max(assets, key=lambda a: a.avg_roas) if assets else None

        return GenomePortfolio(
            project_name=project,
            assets=assets,
            total_value=total_value,
            diversification_score=div_score,
            best_performing=best.asset_id if best else "",
        )

    def transfer_genome(
        self, genome: Genome, from_project: str, to_project: str,
    ) -> GenomeAsset:
        """Transfer a genome asset between projects (cross-project reuse).

        Records the transfer in performance history.
        """
        asset = self.register_genome(genome, project=to_project)
        if from_project in self._by_project:
            aids = self._by_project[from_project]
            if asset.asset_id in aids:
                aids.remove(asset.asset_id)
        return asset

    def get_exchange_summary(self) -> dict[str, Any]:
        """Exchange-level summary."""
        all_assets = list(self._assets.values())
        golden = self.get_golden_genomes()
        total_revenue = sum(a.total_revenue for a in all_assets)
        total_spend = sum(a.total_spend for a in all_assets)
        total_derivatives = sum(a.total_derivatives for a in all_assets)

        return {
            "total_assets": len(all_assets),
            "golden_genomes": len(golden),
            "total_projects": len(self._by_project),
            "total_derivatives_tracked": total_derivatives,
            "aggregate_roi": round(total_revenue / max(1, total_spend), 2),
            "top_golden": [a.to_dict() for a in golden[:5]],
        }

    # ── Internal ────────────────────────────────────────────

    def _find_by_genome(self, genome: Genome) -> GenomeAsset | None:
        """Find asset by genome (match by genome_id)."""
        for asset in self._assets.values():
            if asset.genome and asset.genome.genome_id == genome.genome_id:
                return asset
        return None

    def _update_asset(
        self, asset: GenomeAsset, roas: float, ctr: float, installs: int, project: str,
    ) -> GenomeAsset:
        """Update an existing asset with new performance data."""
        n = len(asset.projects_used) + 1
        asset.avg_roas = (asset.avg_roas * (n - 1) + roas) / n
        asset.avg_ctr = (asset.avg_ctr * (n - 1) + ctr) / n
        asset.best_roas = max(asset.best_roas, roas)
        asset.total_creatives_deployed += 1
        asset.total_spend += roas * 100
        asset.total_revenue += roas * 100 * roas
        if project and project not in asset.projects_used:
            asset.projects_used.append(project)

        # Re-value
        asset.valuation = self._value_engine.evaluate(
            asset.genome, d7_roas=asset.avg_roas, ctr=asset.avg_ctr,
            installs=installs,
        )
        asset.tier = asset.valuation.tier
        asset.is_golden = asset.tier == GenomeTier.PLATINUM

        return asset
