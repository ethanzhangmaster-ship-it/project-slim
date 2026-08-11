"""Creative Entity V2 — Unified Core Data Model for Merge Witches Creative Factory.

Phase 1.2: Data architecture foundation.
All subsequent modules (Winner Mining, DNA Extraction, Generation, Quality Gate,
Facebook Publisher, Bandit Learning) work through this unified entity.

Design principles:
  - Core entity + sub-objects, not one giant flat class
  - All fields nullable (don't let missing Adjust data block creation)
  - Old objects preserved via adapters (no breaking changes)
  - FB + Adjust data unified in single PerformanceData
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Optional

# ── Enums ──

class SourceType:
    FACEBOOK_ORIGINAL = "facebook_original"
    GENERATED = "generated"
    VARIATION = "variation"


class HookType:
    COLLECTION = "collection"
    TRANSFORMATION = "transformation"
    CHALLENGE = "challenge"
    SECRET = "secret"
    CURIOSITY = "curiosity"
    PROGRESSION = "progression"
    ACHIEVEMENT = "achievement"
    BEFORE_AFTER = "before_after"
    REWARD_REVEAL = "reward_reveal"
    HATCHING_EGG = "hatching_egg"
    CHARACTER_SHOWCASE = "character_showcase"
    BUILD_UPGRADE = "build_upgrade"
    EVOLUTION = "evolution"
    MERGE_UPGRADE = "merge_upgrade"
    STORY_HOOK = "story_hook"
    GENERAL_SHOWCASE = "general_showcase"


class GameplayGenre:
    MERGE = "merge"
    SORT = "sort"
    MATCH3 = "match3"
    SIMULATION = "simulation"
    PUZZLE = "puzzle"


class GenerationMethod:
    LOVART = "lovart"
    FAKE_GAMEPLAY = "fake_gameplay"
    TEMPLATE = "template"
    REMIX = "remix"
    MUTATION = "mutation"
    PIL_COMPOSITE = "pil_composite"


class AttributionSource:
    FACEBOOK = "facebook"
    ADJUST = "adjust"


# ── 1. PerformanceData ──

@dataclass
class PerformanceData:
    """Unified FB + Adjust performance metrics. All fields nullable."""

    spend: Optional[float] = None
    impressions: Optional[int] = None
    clicks: Optional[int] = None
    installs: Optional[int] = None
    purchases: Optional[int] = None
    revenue: Optional[float] = None

    ctr: Optional[float] = None
    cvr: Optional[float] = None
    cpi: Optional[float] = None
    arpu: Optional[float] = None
    roas_d1: Optional[float] = None
    roas_d7: Optional[float] = None
    roas_d30: Optional[float] = None

    attribution_source: str = ""

    # Convenience
    @property
    def has_roas(self) -> bool:
        return self.roas_d1 is not None or self.roas_d7 is not None

    @property
    def has_purchase(self) -> bool:
        return self.purchases is not None and self.purchases > 0

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


# ── 2. CreativeDNA ──

@dataclass
class HookDNA:
    type: str = ""
    emotion: str = ""
    curiosity: str = ""

    def to_dict(self) -> dict[str, str]:
        return {k: v for k, v in asdict(self).items() if v}


@dataclass
class GameplayDNA:
    genre: str = ""
    mechanic: str = ""
    action: str = ""
    progression: str = ""

    def to_dict(self) -> dict[str, str]:
        return {k: v for k, v in asdict(self).items() if v}


@dataclass
class RewardDNA:
    type: str = ""
    progression: str = ""
    visual_change: str = ""

    def to_dict(self) -> dict[str, str]:
        return {k: v for k, v in asdict(self).items() if v}


@dataclass
class VisualDNA:
    style: str = ""
    color: str = ""
    composition: str = ""
    palette: str = ""
    lighting: str = ""

    def to_dict(self) -> dict[str, str]:
        return {k: v for k, v in asdict(self).items() if v}


@dataclass
class PsychologyDNA:
    motivation: str = ""
    trigger: str = ""

    def to_dict(self) -> dict[str, str]:
        return {k: v for k, v in asdict(self).items() if v}


@dataclass
class CreativeDNA:
    """Unified Creative DNA. Describes WHY users click, not WHAT is in the image."""

    hook: HookDNA = field(default_factory=HookDNA)
    gameplay: GameplayDNA = field(default_factory=GameplayDNA)
    reward: RewardDNA = field(default_factory=RewardDNA)
    visual: VisualDNA = field(default_factory=VisualDNA)
    psychology: PsychologyDNA = field(default_factory=PsychologyDNA)

    # Raw analysis data (for backward compatibility)
    raw_summary: str = ""
    raw_subject: str = ""
    raw_ui_elements: list[str] = field(default_factory=list)
    raw_gameplay_elements: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = {
            "hook": self.hook.to_dict(),
            "gameplay": self.gameplay.to_dict(),
            "reward": self.reward.to_dict(),
            "visual": self.visual.to_dict(),
            "psychology": self.psychology.to_dict(),
        }
        if self.raw_summary:
            d["raw_summary"] = self.raw_summary
        if self.raw_subject:
            d["raw_subject"] = self.raw_subject
        if self.raw_ui_elements:
            d["raw_ui_elements"] = self.raw_ui_elements
        if self.raw_gameplay_elements:
            d["raw_gameplay_elements"] = self.raw_gameplay_elements
        return d


# ── 3. CreativeLineage ──

@dataclass
class CreativeLineage:
    """Tracks parent-child creative relationships."""

    parent_creative_id: str = ""
    generation_method: str = ""
    mutation_rules: dict[str, bool] = field(default_factory=dict)

    # Convenience
    @property
    def is_original(self) -> bool:
        return not self.parent_creative_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "parent_creative_id": self.parent_creative_id,
            "generation_method": self.generation_method,
            "mutation_rules": self.mutation_rules,
            "is_original": self.is_original,
        }


# ── 4. GenerationHistory ──

@dataclass
class GenerationRecord:
    """Single generation event."""

    generation_id: str = ""
    model: str = ""
    prompt: str = ""
    input_dna: dict[str, Any] = field(default_factory=dict)
    output_asset: str = ""
    quality_score: dict[str, Any] = field(default_factory=dict)
    publish_status: str = ""
    performance_result: Optional[PerformanceData] = None
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = {k: v for k, v in asdict(self).items() if v}
        if self.performance_result:
            d["performance_result"] = self.performance_result.to_dict()
        return d


@dataclass
class GenerationHistory:
    """Tracks all generations of a creative."""

    records: list[GenerationRecord] = field(default_factory=list)

    @property
    def total_generations(self) -> int:
        return len(self.records)

    @property
    def latest(self) -> Optional[GenerationRecord]:
        return self.records[-1] if self.records else None

    def add(self, record: GenerationRecord) -> None:
        self.records.append(record)

    def to_dict(self) -> list[dict[str, Any]]:
        return [r.to_dict() for r in self.records]


# ── 5. CreativeAsset ──

@dataclass
class CreativeAsset:
    """Creative media asset reference."""

    image_path: str = ""
    video_path: str = ""
    width: int = 0
    height: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v}


# ── 6. CreativeMapping ──

@dataclass
class CreativeMapping:
    """FB creative_id ↔ Adjust creative_id mapping."""

    facebook_creative_id: str = ""
    adjust_creative_id: str = ""
    package_name: str = ""
    platform: str = ""
    country: str = ""
    campaign_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v}


# ── 7. CreativeEntity (Core) ──

@dataclass
class CreativeEntity:
    """Unified Creative Entity V2 — the core data object.

    All subsequent modules work through this entity.
    """

    creative_id: str = ""
    project_id: str = "merge_witches"
    source_type: str = ""

    asset: CreativeAsset = field(default_factory=CreativeAsset)
    performance: PerformanceData = field(default_factory=PerformanceData)
    dna: CreativeDNA = field(default_factory=CreativeDNA)
    lineage: CreativeLineage = field(default_factory=CreativeLineage)
    generation: GenerationHistory = field(default_factory=GenerationHistory)

    metadata: dict[str, Any] = field(default_factory=lambda: {
        "created_time": datetime.now().isoformat(),
        "version": "2.0.0",
    })

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "project_id": self.project_id,
            "source_type": self.source_type,
            "asset": self.asset.to_dict(),
            "performance": self.performance.to_dict(),
            "dna": self.dna.to_dict(),
            "lineage": self.lineage.to_dict(),
            "generation": self.generation.to_dict(),
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    # ── Convenience accessors ──

    @property
    def has_image(self) -> bool:
        return bool(self.asset.image_path)

    @property
    def has_performance(self) -> bool:
        return self.performance.spend is not None

    @property
    def has_dna(self) -> bool:
        return bool(self.dna.hook.type or self.dna.gameplay.genre)

    @property
    def is_winner(self) -> bool:
        if self.performance.roas_d1 is not None:
            return self.performance.roas_d1 > 1.0
        return False

    @property
    def is_original(self) -> bool:
        return self.source_type == SourceType.FACEBOOK_ORIGINAL

    def summary(self) -> str:
        """One-line summary of this creative."""
        parts = [f"ID={self.creative_id}"]
        if self.dna.hook.type:
            parts.append(f"hook={self.dna.hook.type}")
        if self.performance.roas_d1 is not None:
            parts.append(f"ROAS={self.performance.roas_d1:.2f}")
        if self.performance.revenue is not None:
            parts.append(f"rev=${self.performance.revenue:.0f}")
        return " | ".join(parts)