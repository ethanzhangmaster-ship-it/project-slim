"""Creative Entity V2 Adapters — Convert old objects to unified CreativeEntity.

Design: Never delete old objects. Build adapters that map old → new.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from .creative_entity_v2 import (
    CreativeEntity, CreativeAsset, PerformanceData, CreativeDNA,
    HookDNA, GameplayDNA, RewardDNA, VisualDNA, PsychologyDNA,
    CreativeLineage, GenerationHistory, GenerationRecord,
    CreativeMapping, SourceType, AttributionSource,
)


# ── PerformanceDataAdapter ──

class PerformanceDataAdapter:
    """Convert CreativePerformance (old) → PerformanceData (new)."""

    @staticmethod
    def from_creative_performance(perf: Any) -> PerformanceData:
        """From market_ops.creative_growth_loop.01_collectors.facebook_ads_collector.CreativePerformance"""
        return PerformanceData(
            spend=perf.spend if perf.spend else None,
            impressions=perf.impression if perf.impression else None,
            clicks=perf.click if perf.click else None,
            installs=perf.install if perf.install else None,
            ctr=perf.ctr if perf.ctr else None,
            cpi=perf.cpi if perf.cpi else None,
            roas_d1=perf.roas_d1 if perf.roas_d1 else None,
            roas_d7=perf.roas_d7 if perf.roas_d7 else None,
            attribution_source=AttributionSource.FACEBOOK,
        )

    @staticmethod
    def from_dict(data: dict[str, Any]) -> PerformanceData:
        """From raw dict (e.g., creative_mapping_v2 row)."""
        return PerformanceData(
            spend=float(data.get("spend", 0)) if data.get("spend") else None,
            impressions=int(float(data.get("impressions", 0))) if data.get("impressions") else None,
            clicks=int(float(data.get("clicks", 0))) if data.get("clicks") else None,
            installs=int(float(data.get("installs", 0))) if data.get("installs") else None,
            purchases=int(float(data.get("purchases", 0))) if data.get("purchases") else None,
            revenue=float(data.get("revenue", 0)) if data.get("revenue") else None,
            ctr=float(data.get("ctr", 0)) if data.get("ctr") else None,
            cpi=float(data.get("cpa", 0)) if data.get("cpa") else None,
            roas_d1=float(data.get("roas", 0)) if data.get("roas") else None,
            roas_d7=float(data.get("roas_d7", 0)) if data.get("roas_d7") else None,
            attribution_source=AttributionSource.FACEBOOK,
        )


# ── WinnerAdapter ──

class WinnerAdapter:
    """Convert Winner (old) → CreativeEntity (new)."""

    @staticmethod
    def from_winner(winner: Any) -> CreativeEntity:
        """From market_ops.creative_growth_loop.02_performance.winner_engine.Winner"""
        return CreativeEntity(
            creative_id=winner.creative_id,
            project_id=winner.project,
            source_type=SourceType.FACEBOOK_ORIGINAL,
            asset=CreativeAsset(image_path=winner.image_path),
            performance=PerformanceData(
                ctr=winner.ctr if winner.ctr else None,
                roas_d1=winner.roas_d1 if winner.roas_d1 else None,
                roas_d7=winner.roas_d7 if winner.roas_d7 else None,
                attribution_source=AttributionSource.FACEBOOK,
            ),
            lineage=CreativeLineage(),
        )


# ── DNAAdapter ──

class DNAAdapter:
    """Convert old DNA formats → CreativeDNA (new)."""

    @staticmethod
    def from_creative_dna_item(item: Any) -> CreativeDNA:
        """From market_ops.creative_dna.CreativeDnaItem"""
        return CreativeDNA(
            hook=HookDNA(
                type=item.hook_type or "",
                emotion=item.emotion or "",
            ),
            visual=VisualDNA(
                style="",
                color="",
                composition="",
            ),
            raw_summary=f"{item.creative_name} (hook={item.hook_type}, spend=${item.spend})",
            raw_subject=item.creative_name or "",
        )

    @staticmethod
    def from_creative_dna_v2(dna_v2: Any) -> CreativeDNA:
        """From market_ops.creative_growth_loop.03_gene.creative_dna_v2.CreativeDNAV2"""
        return CreativeDNA(
            hook=HookDNA(
                type=dna_v2.hook_type or "",
            ),
            gameplay=GameplayDNA(
                genre="merge",
                mechanic=dna_v2.mechanism_type or "",
            ),
            reward=RewardDNA(
                type=dna_v2.reward_type or "",
            ),
            visual=VisualDNA(
                composition=dna_v2.layout_template or "",
            ),
            psychology=PsychologyDNA(
                motivation=", ".join(dna_v2.psychology_drive) if dna_v2.psychology_drive else "",
                trigger=dna_v2.attention_goal or "",
            ),
        )

    @staticmethod
    def from_contrastive_dna(dna_dict: dict[str, Any]) -> CreativeDNA:
        """From our contrastive_dna.json analysis result."""
        color = dna_dict.get("color", {})
        comp = dna_dict.get("composition", {})

        return CreativeDNA(
            hook=HookDNA(
                type=dna_dict.get("hook_type", ""),
            ),
            gameplay=GameplayDNA(
                genre="merge",
            ),
            visual=VisualDNA(
                style="",
                color=color.get("dominant_hue", ""),
                palette="",
                composition=comp.get("vertical_weight", ""),
                lighting=f"brightness={color.get('brightness', '?')}",
            ),
            raw_summary=dna_dict.get("creative_name", ""),
            raw_subject=dna_dict.get("creative_name", ""),
        )

    @staticmethod
    def from_dna_cache(dna_cache: dict[str, Any]) -> CreativeDNA:
        """From winners_dna.json / real_winners_dna_vision.json format."""
        vdna = dna_cache.get("visual_dna", dna_cache)

        return CreativeDNA(
            hook=HookDNA(
                type=vdna.get("hook_type", ""),
            ),
            gameplay=GameplayDNA(
                genre="merge",
                progression="",
            ),
            reward=RewardDNA(
                type="",
                progression="",
            ),
            visual=VisualDNA(
                style=vdna.get("mood", ""),
                color=vdna.get("palette", ""),
                composition=vdna.get("composition", ""),
                lighting=vdna.get("lighting", ""),
            ),
            psychology=PsychologyDNA(
                motivation="",
            ),
            raw_summary=vdna.get("overall_summary", ""),
            raw_subject=vdna.get("subject", ""),
            raw_ui_elements=vdna.get("ui_elements", []),
            raw_gameplay_elements=vdna.get("gameplay_elements", []),
        )


# ── CreativeEntityBuilder ──

class CreativeEntityBuilder:
    """Build a complete CreativeEntity from multiple data sources.

    This is the main entry point for Phase 1.2 verification.
    """

    @staticmethod
    def from_creative_mapping_row(row: dict[str, Any]) -> CreativeEntity:
        """Build from a creative_mapping_v2.csv row (has FB performance data)."""
        creative_id = row.get("creative_id", "").strip()

        entity = CreativeEntity(
            creative_id=creative_id,
            project_id="merge_witches",
            source_type=SourceType.FACEBOOK_ORIGINAL,
            asset=CreativeAsset(
                image_path="",
                video_path=row.get("eagle_filepath", ""),
            ),
            performance=PerformanceDataAdapter.from_dict(row),
            lineage=CreativeLineage(),
        )

        return entity

    @staticmethod
    def from_winner_dna_file(json_path: str) -> list[CreativeEntity]:
        """Build CreativeEntities from a DNA cache JSON file."""
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        entities = []
        winners = data.get("winners", data.get("creatives", []))

        for w in winners:
            cid = w.get("creative_id", "")
            entity = CreativeEntity(
                creative_id=cid,
                project_id="merge_witches",
                source_type=SourceType.FACEBOOK_ORIGINAL,
                asset=CreativeAsset(image_path=w.get("local_image_path", "")),
                performance=PerformanceData(
                    spend=w.get("spend"),
                    revenue=w.get("revenue"),
                    roas_d1=w.get("roas"),
                    installs=w.get("installs"),
                    purchases=w.get("purchases"),
                    attribution_source=AttributionSource.FACEBOOK,
                ),
                dna=DNAAdapter.from_dna_cache(w),
                lineage=CreativeLineage(),
            )
            entities.append(entity)

        return entities

    @staticmethod
    def enrich_with_contrastive_dna(
        entities: list[CreativeEntity],
        contrastive_json_path: str,
    ) -> list[CreativeEntity]:
        """Enrich entities with contrastive DNA analysis data."""
        with open(contrastive_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        creatives_map = {c["creative_id"]: c for c in data.get("creatives", [])}

        for entity in entities:
            if entity.creative_id in creatives_map:
                cdata = creatives_map[entity.creative_id]
                entity.dna = DNAAdapter.from_contrastive_dna(cdata)

        return entities


# ── CreativeMappingBuilder ──

class CreativeMappingBuilder:
    """Build FB ↔ Adjust creative ID mappings."""

    @staticmethod
    def from_creative_mapping_csv(csv_path: str) -> list[CreativeMapping]:
        """Build mappings from creative_mapping_v2.csv."""
        import csv

        mappings = []
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ad_name = (row.get("ad_name") or "").strip()
                platform = "unknown"
                if "IOS" in ad_name:
                    platform = "ios"
                elif "And" in ad_name:
                    platform = "android"

                mappings.append(CreativeMapping(
                    facebook_creative_id=row.get("creative_id", "").strip(),
                    adjust_creative_id="",  # TODO: link from Adjust data
                    package_name="",
                    platform=platform,
                    campaign_id=row.get("campaign_id", "").strip(),
                ))

        return mappings

    @staticmethod
    def build_index(mappings: list[CreativeMapping]) -> dict[str, CreativeMapping]:
        """Build lookup index by facebook_creative_id."""
        return {m.facebook_creative_id: m for m in mappings if m.facebook_creative_id}