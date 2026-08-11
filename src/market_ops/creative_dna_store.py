"""E8.5: Creative DNA Store — maps creative_id → DNA → Genome from real data.

Bridges the core gap in the Reality Learning Loop:
  Campaign Performance (spend/ROAS/installs)
    → Creative DNA (hook/emotion/pace/ui/structure)
    → Genome (genes with real performance)
    → GenomeAttribution (gene-level contribution analysis)
    → Evolution Engine (Darwinian selection)

Data sources (priority order):
  1. creative_mapping_adjust_merged_v2.csv — creative_id, creative_name, fb_spend, adjust_revenue
  2. _infer_labels() keyword matching — DNA inference from creative_name + eagle_filename
  3. ads_performance.csv — additional spend/ROAS/CTR data

Usage:
    store = CreativeDNAStore()
    store.load()
    genome = store.build_genome_from_creative("creative_id_123")
    store.feed_all_to_attribution(gene_attribution)
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from market_ops.creative_brain.v5_evolution.schemas import (
    Genome, Gene, GeneType, Fitness,
)


# ═══════════════════════════════════════════════════════════
# DNA Inference — keyword-based (same as creative_dna.py)
# ═══════════════════════════════════════════════════════════

_DNA_FIELDS = [
    "hook_type", "emotion", "pace", "ui_type",
    "copy_style", "cta_strength", "video_structure",
    "subtitle_style", "first_3s_density", "conflict_strength",
]

_DNA_RULES: list[tuple[str, str, list[str]]] = [
    ("hook_type", "rescue", ["危机", "rescue", "save", "help", "困", "danger", "crisis"]),
    ("hook_type", "reward", ["爽", "win", "level", "reward", "bonus", "collection"]),
    ("hook_type", "twist", ["反转", "unexpected", "fail", "wrong", "before_after"]),
    ("emotion", "anxiety", ["焦虑", "urgent", "danger", "救"]),
    ("emotion", "satisfaction", ["爽", "win", "clear", "success", "magical"]),
    ("emotion", "healing", ["治愈", "home", "garden", "cozy", "relax"]),
    ("emotion", "curiosity", ["adventure", "explore", "discover", "secret", "mystery"]),
    ("pace", "fast", ["fast", "quick", "快切", "short", "秒"]),
    ("pace", "slow", ["slow", "story", "剧情", "铺垫"]),
    ("ui_type", "merge", ["merge", "合成", "mermaid", "witch", "vampire", "dragon"]),
    ("ui_type", "sort", ["sort", "整理", "排序", "goods"]),
    ("ui_type", "build", ["build", "home", "装修", "建造", "design"]),
    ("ui_type", "puzzle", ["puzzle", "解谜", "escape"]),
    ("copy_style", "strong_title", ["big text", "title", "headline", "大字", "标题"]),
    ("copy_style", "soft_title", ["ugc", "native", "story"]),
    ("cta_strength", "strong", ["install", "download", "play now", "立即", "马上", "start"]),
    ("cta_strength", "soft", ["try", "看看", "story"]),
    ("video_structure", "ugc", ["ugc", "creator", "真人", "口播"]),
    ("video_structure", "gameplay", ["gameplay", "录屏", "screen", "playable"]),
    ("video_structure", "animation", ["animation", "animated", "2d", "3d", "cartoon"]),
    ("subtitle_style", "large_subtitle", ["大字", "big text", "caption"]),
    ("subtitle_style", "suspense", ["悬疑", "why", "secret", "mystery"]),
    ("subtitle_style", "dense", ["dense", "多字幕", "高密度"]),
    ("first_3s_density", "high", ["hook", "3s", "前三秒", "快切"]),
    ("first_3s_density", "low", ["slow", "铺垫"]),
    ("conflict_strength", "strong", ["危机", "救", "fail", "wrong", "fight", "danger"]),
    ("conflict_strength", "soft", ["cozy", "home", "治愈", "relax"]),
]

# DNA field → GeneType mapping
DNA_TO_GENE: dict[str, GeneType] = {
    "hook_type": GeneType.HOOK,
    "emotion": GeneType.EMOTION,
    "pace": GeneType.PACING,
    "ui_type": GeneType.GAMEPLAY,
    "video_structure": GeneType.STORY,
    "subtitle_style": GeneType.VISUAL,
    "first_3s_density": GeneType.PACING,
    "conflict_strength": GeneType.HOOK,
    "cta_strength": GeneType.VISUAL,
    "copy_style": GeneType.STORY,
}


def _infer_dna(text: str) -> dict[str, str]:
    """Infer DNA labels from text using keyword rules."""
    normalized = (text or "").lower()
    labels = {field: "unknown" for field in _DNA_FIELDS}
    for field, value, keywords in _DNA_RULES:
        if labels[field] != "unknown":
            continue
        if any(kw.lower() in normalized for kw in keywords):
            labels[field] = value
    return labels


def _build_genes(dna: dict[str, str]) -> dict[str, Gene]:
    """Build V5 Gene objects from DNA labels."""
    genes: dict[str, Gene] = {}
    for dna_field, gene_type in DNA_TO_GENE.items():
        value = dna.get(dna_field, "unknown")
        if value == "unknown":
            continue
        key = gene_type.value
        if key not in genes:
            genes[key] = Gene(gene_type=gene_type, value=value)
        # Supplementary fields are simply skipped (Gene schema has no metadata field)
    return genes


# ═══════════════════════════════════════════════════════════
# Creative DNA Record
# ═══════════════════════════════════════════════════════════

@dataclass
class CreativeDnaRecord:
    """One creative with DNA + real performance."""
    creative_id: str
    creative_name: str = ""
    # DNA
    dna: dict[str, str] = field(default_factory=dict)
    # Performance
    spend: float = 0.0
    revenue: float = 0.0
    installs: int = 0
    roas: float = 0.0
    # Metadata
    eagle_filename: str = ""
    campaign: str = ""
    match_method: str = ""

    @property
    def is_winner(self) -> bool:
        return self.roas >= 1.0 and self.spend >= 100

    @property
    def has_dna(self) -> bool:
        return any(v != "unknown" for v in self.dna.values())


# ═══════════════════════════════════════════════════════════
# Creative DNA Store
# ═══════════════════════════════════════════════════════════

class CreativeDNAStore:
    """Loads and queries creative DNA from real data sources.

    Usage:
        store = CreativeDNAStore()
        store.load()  # Load from CSV
        genome = store.build_genome(record)
        stats = store.get_gene_stats()
    """

    def __init__(self) -> None:
        self._records: dict[str, CreativeDnaRecord] = {}
        self._by_gene_value: dict[str, list[CreativeDnaRecord]] = {}
        self._loaded = False

    # ── Loading ──────────────────────────────────────────────

    def load(self) -> int:
        """Load all available creative DNA sources.

        Priority:
          1. creative_dna_master.json (E9.1 fused DNA with confidence)
          2. creative_mapping_adjust_merged_v2.csv (raw CSV with name inference)

        Returns: total records loaded.
        """
        # Priority 1: Fused DNA master
        master_path = Path("output/active/creative_dna_master.json")
        if master_path.exists():
            count = self._load_from_master_json(master_path)
            if count > 0:
                self._loaded = True
                self._build_index()
                return count

        # Priority 2: Raw CSV
        count = self._load_from_mapping_csv()
        self._loaded = True
        self._build_index()
        return count

    def _load_from_master_json(self, path: Path) -> int:
        """Load from creative_dna_master.json (E9.1 fused DNA)."""
        import json
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for item in data:
            creative_id = item.get("creative_id", "")
            if not creative_id:
                continue

            # Map fused DNA fields to simplified DNA dict
            mech = item.get("mechanism", {})
            hook = item.get("hook", {})
            reward = item.get("reward", {})
            visual = item.get("visual", {})
            psych = item.get("psychology", {})
            perf = item.get("performance", {})

            dna = {
                "hook_type": hook.get("type", "unknown"),
                "emotion": hook.get("type", "unknown"),
                "pace": "unknown",
                "ui_type": mech.get("type", "unknown"),
                "copy_style": "unknown",
                "cta_strength": "unknown",
                "video_structure": visual.get("style", "unknown"),
                "subtitle_style": "unknown",
                "first_3s_density": "unknown",
                "conflict_strength": "unknown",
                # E9.1 enriched fields
                "_reward_type": reward.get("type", ""),
                "_psychology_drives": psych.get("drives", []),
                "_mechanism_confidence": mech.get("confidence", 0),
                "_hook_confidence": hook.get("confidence", 0),
                "_total_confidence": item.get("total_confidence", 0),
                # E9.3 IAP fields
                "_fantasy_drives": item.get("fantasy", {}).get("drives", []),
                "_progression_loops": item.get("progression", {}).get("loops", []),
                "_payment_triggers": item.get("payment_trigger", {}).get("triggers", []),
                "_retention_hooks": item.get("retention", {}).get("hooks", []),
                "_iap_fitness_score": item.get("iap_fitness", {}).get("score", 0),
                "_player_value_score": item.get("iap_fitness", {}).get("player_value_score", 0),
            }

            record = CreativeDnaRecord(
                creative_id=creative_id,
                creative_name=item.get("creative_name", ""),
                dna=dna,
                spend=perf.get("spend", 0),
                revenue=perf.get("revenue", 0),
                installs=perf.get("installs", 0),
                roas=perf.get("roas", 0),
                eagle_filename=item.get("eagle_filename", ""),
                match_method="fusion_v1",
            )

            self._records[creative_id] = record

        return len(self._records)

    def _load_from_mapping_csv(self) -> int:
        """Load from creative_mapping_adjust_merged_v2.csv."""
        csv_path = Path("output/video_intelligence/p04/creative_mapping_adjust_merged_v2.csv")
        if not csv_path.exists():
            return 0

        count = 0
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                creative_id = row.get("creative_id", "").strip()
                if not creative_id:
                    continue

                creative_name = row.get("creative_name", "").strip()
                eagle_filename = row.get("eagle_filename", "").strip()

                # Infer DNA from creative_name + eagle_filename
                dna_text = f"{creative_name} {eagle_filename}"
                dna = _infer_dna(dna_text)

                # Performance from Adjust (canonical) + FB fallback
                adj_cost = float(row.get("adjust_cost", 0) or 0)
                adj_revenue = float(row.get("adjust_revenue", 0) or 0)
                adj_installs = int(float(row.get("adjust_installs", 0) or 0))
                fb_spend = float(row.get("fb_spend", 0) or 0)
                fb_revenue = float(row.get("fb_revenue", 0) or 0)
                fb_installs = int(float(row.get("fb_installs", 0) or 0))

                spend = adj_cost if adj_cost > 0 else fb_spend
                revenue = adj_revenue if adj_revenue > 0 else fb_revenue
                installs = adj_installs if adj_installs > 0 else fb_installs
                roas = revenue / spend if spend > 0 else 0

                record = CreativeDnaRecord(
                    creative_id=creative_id,
                    creative_name=creative_name,
                    dna=dna,
                    spend=spend,
                    revenue=revenue,
                    installs=installs,
                    roas=roas,
                    eagle_filename=eagle_filename,
                    campaign=row.get("campaign_name", ""),
                    match_method=row.get("match_method", ""),
                )

                self._records[creative_id] = record
                count += 1

        return count

    def _build_index(self) -> None:
        """Build gene value → records index for fast queries."""
        self._by_gene_value = {}
        for record in self._records.values():
            for field, value in record.dna.items():
                if value == "unknown":
                    continue
                gene_type = DNA_TO_GENE.get(field)
                if gene_type is None:
                    continue
                key = f"{gene_type.value}:{value}"
                self._by_gene_value.setdefault(key, []).append(record)

    # ── Querying ─────────────────────────────────────────────

    def get_record(self, creative_id: str) -> CreativeDnaRecord | None:
        return self._records.get(creative_id)

    def get_all_records(self) -> list[CreativeDnaRecord]:
        return list(self._records.values())

    def build_genome(self, record: CreativeDnaRecord) -> Genome:
        """Build a V5 Genome from a CreativeDnaRecord with real performance."""
        genes = _build_genes(record.dna)

        genome = Genome(
            name=record.creative_name or record.creative_id,
            genes=genes,
            generation=0,
            metadata={
                "creative_id": record.creative_id,
                "spend": record.spend,
                "revenue": record.revenue,
                "installs": record.installs,
                "roas": record.roas,
                "is_winner": record.is_winner,
                "source": "creative_dna_store",
            },
        )

        # Attach fitness using real performance data
        fitness = Fitness(
            genome_id=genome.genome_id,
            generation=0,
            components={
                "roas_d7": min(record.roas / 2.0, 1.0),
            },
            composite_score=min(record.roas / 2.0, 1.0),
            explanation=[f"roas={record.roas:.3f}", f"spend={record.spend:.0f}"],
            confidence=min(record.spend / 1000.0, 1.0),
            sample_size=max(1, int(record.spend / 10)),
        )
        genome.fitness = fitness
        genome.fitness_history.append(fitness)

        return genome

    def feed_to_attribution(self, attribution: Any) -> int:
        """Feed all creative records into GenomeAttribution.

        Returns: number of records processed.
        """
        count = 0
        for record in self._records.values():
            if record.spend <= 0:
                continue
            try:
                genome = self.build_genome(record)
                attribution.record_outcome(
                    genome, record.roas, 0.0,
                    record.spend / max(1, record.installs),  # CPI
                    record.is_winner,
                )
                count += 1
            except Exception:
                pass
        return count

    # ── Statistics ───────────────────────────────────────────

    def get_gene_stats(self) -> dict[str, Any]:
        """Get gene-level performance statistics from real data.

        Returns: {gene_type: {value: {count, avg_roas, winner_rate}}}
        """
        stats: dict[str, dict[str, dict[str, Any]]] = {}
        for key, records in self._by_gene_value.items():
            gene_type, value = key.split(":", 1)
            if gene_type not in stats:
                stats[gene_type] = {}

            winners = sum(1 for r in records if r.is_winner)
            total_roas = sum(r.roas for r in records)
            n = len(records)

            stats[gene_type][value] = {
                "count": n,
                "avg_roas": round(total_roas / n, 3) if n > 0 else 0,
                "winner_rate": round(winners / n, 3) if n > 0 else 0,
                "total_spend": round(sum(r.spend for r in records), 2),
            }

        return stats

    def get_winning_genes(self, min_count: int = 3) -> list[dict[str, Any]]:
        """Get genes with highest winner rates."""
        results = []
        for key, records in self._by_gene_value.items():
            if len(records) < min_count:
                continue
            gene_type, value = key.split(":", 1)
            winners = sum(1 for r in records if r.is_winner)
            avg_roas = sum(r.roas for r in records) / len(records)
            results.append({
                "gene_type": gene_type,
                "value": value,
                "count": len(records),
                "winner_rate": round(winners / len(records), 3),
                "avg_roas": round(avg_roas, 3),
            })

        results.sort(key=lambda x: (x["winner_rate"], x["avg_roas"]), reverse=True)
        return results

    def get_genome_combinations(self, min_occurrence: int = 3
                                ) -> list[dict[str, Any]]:
        """E9.2: Discover winning genome combinations (gene pairs).

        Goes beyond single-gene analysis to find multi-gene patterns.
        Returns: list of {genes, count, avg_roas, winner_rate} sorted by winner_rate.
        """
        from collections import defaultdict

        combo_stats: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"count": 0, "total_roas": 0.0, "winners": 0, "total_spend": 0.0}
        )

        for record in self._records.values():
            if not record.has_dna or record.spend <= 0:
                continue
            # Build combo key from DNA fields
            parts = []
            for field in ["hook_type", "ui_type", "emotion", "video_structure"]:
                val = record.dna.get(field, "unknown")
                if val and val != "unknown":
                    parts.append(f"{field}={val}")
            # Add enriched fields
            reward = record.dna.get("_reward_type", "")
            if reward:
                parts.append(f"reward={reward}")
            if len(parts) < 2:
                continue

            key = " + ".join(sorted(parts))
            s = combo_stats[key]
            s["count"] += 1
            s["total_roas"] += record.roas
            s["total_spend"] += record.spend
            if record.is_winner:
                s["winners"] += 1

        results = []
        for key, s in combo_stats.items():
            n = s["count"]
            if n < min_occurrence:
                continue
            results.append({
                "genes": key,
                "count": n,
                "avg_roas": round(s["total_roas"] / n, 3),
                "winner_rate": round(s["winners"] / n, 3),
                "total_spend": round(s["total_spend"], 2),
            })

        results.sort(key=lambda x: (x["winner_rate"], x["avg_roas"]), reverse=True)
        return results

    def get_summary(self) -> dict[str, Any]:
        """Get overall store summary."""
        if not self._records:
            return {"status": "empty", "records": 0}

        records = list(self._records.values())
        total_spend = sum(r.spend for r in records)
        total_revenue = sum(r.revenue for r in records)
        winners = sum(1 for r in records if r.is_winner)
        with_dna = sum(1 for r in records if r.has_dna)

        return {
            "total_records": len(records),
            "with_dna": with_dna,
            "total_spend": round(total_spend, 2),
            "total_revenue": round(total_revenue, 2),
            "aggregate_roas": round(total_revenue / max(0.01, total_spend), 3),
            "winners": winners,
            "winner_rate": round(winners / max(1, len(records)), 3),
            "gene_stats": self.get_gene_stats(),
            "winning_genes": self.get_winning_genes()[:10],
        }