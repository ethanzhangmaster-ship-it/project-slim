from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
import random


class ReplicationStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class CreativeDNA:
    dna_id: str
    source_creative_id: str
    elements: Dict[str, Any] = field(default_factory=dict)
    performance_score: float = 0.0
    key_traits: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dna_id": self.dna_id,
            "source_creative_id": self.source_creative_id,
            "elements": self.elements,
            "performance_score": self.performance_score,
            "key_traits": self.key_traits,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class Variant:
    variant_id: str
    source_dna_id: str
    modifications: Dict[str, Any] = field(default_factory=dict)
    expected_performance: float = 0.0
    test_priority: int = 5
    status: str = "pending"
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "source_dna_id": self.source_dna_id,
            "modifications": self.modifications,
            "expected_performance": self.expected_performance,
            "test_priority": self.test_priority,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ReplicationResult:
    result_id: str
    source_creative_id: str
    variants_generated: int = 0
    status: ReplicationStatus = ReplicationStatus.PENDING
    variants: List[Variant] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result_id": self.result_id,
            "source_creative_id": self.source_creative_id,
            "variants_generated": self.variants_generated,
            "status": self.status.value,
            "variants": [v.to_dict() for v in self.variants],
            "created_at": self.created_at.isoformat(),
        }


class WinnerReplicator:
    def __init__(self):
        self._dna_store: Dict[str, CreativeDNA] = {}
        self._variants: Dict[str, Variant] = {}
        self._replications: Dict[str, ReplicationResult] = []

    def replicate_winner(self, creative_id: str, num_variants: int = 3) -> ReplicationResult:
        result_id = f"rep_{creative_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        result = ReplicationResult(
            result_id=result_id,
            source_creative_id=creative_id,
            status=ReplicationStatus.IN_PROGRESS,
        )

        dna = self.extract_dna(creative_id)
        if not dna:
            result.status = ReplicationStatus.FAILED
            self._replications.append(result)
            return result

        variants = self.generate_variants(dna, num_variants)
        result.variants = variants
        result.variants_generated = len(variants)
        result.status = ReplicationStatus.COMPLETED

        self._replications.append(result)
        return result

    def extract_dna(self, creative_id: str) -> Optional[CreativeDNA]:
        dna_id = f"dna_{creative_id}"
        if dna_id in self._dna_store:
            return self._dna_store[dna_id]

        elements = {
            "headline_style": "emotional",
            "color_scheme": "blue_white",
            "cta_type": "action_oriented",
            "image_style": "lifestyle",
            "tone": "casual",
            "length": "short",
            "urgency_level": "high",
            "social_proof": True,
            "benefit_focus": True,
        }

        key_traits = [
            "strong_headline",
            "clear_cta",
            "emotional_appeal",
            "benefit_highlighted",
        ]

        dna = CreativeDNA(
            dna_id=dna_id,
            source_creative_id=creative_id,
            elements=elements,
            performance_score=random.uniform(70, 95),
            key_traits=key_traits,
        )
        self._dna_store[dna_id] = dna
        return dna

    def generate_variants(self, dna: CreativeDNA, num_variants: int = 3) -> List[Variant]:
        variants = []
        modification_patterns = [
            {"headline_style": "question", "color_scheme": "red_white"},
            {"headline_style": "statistical", "cta_type": "urgency"},
            {"tone": "professional", "urgency_level": "medium"},
            {"image_style": "product_focused", "social_proof": False},
            {"length": "medium", "benefit_focus": False},
            {"headline_style": "how_to", "color_scheme": "green_white"},
        ]

        for i in range(min(num_variants, len(modification_patterns))):
            pattern = modification_patterns[i]
            variant_id = f"var_{dna.dna_id}_{i+1}"

            expected_perf = dna.performance_score * random.uniform(0.85, 1.15)
            variant = Variant(
                variant_id=variant_id,
                source_dna_id=dna.dna_id,
                modifications=pattern,
                expected_performance=expected_perf,
                test_priority=1 if expected_perf > dna.performance_score else 3,
            )
            variants.append(variant)
            self._variants[variant_id] = variant

        return variants

    def get_dna(self, creative_id: str) -> Optional[CreativeDNA]:
        dna_id = f"dna_{creative_id}"
        return self._dna_store.get(dna_id)

    def get_variant(self, variant_id: str) -> Optional[Variant]:
        return self._variants.get(variant_id)

    def get_all_dna(self) -> List[CreativeDNA]:
        return list(self._dna_store.values())

    def get_all_variants(self) -> List[Variant]:
        return list(self._variants.values())

    def get_replication_history(self, limit: int = 50) -> List[ReplicationResult]:
        return self._replications[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_dna_extracted": len(self._dna_store),
            "total_variants_generated": len(self._variants),
            "total_replications": len(self._replications),
            "successful_replications": sum(1 for r in self._replications if r.status == ReplicationStatus.COMPLETED),
            "average_variants_per_replication": sum(r.variants_generated for r in self._replications) / len(self._replications) if self._replications else 0,
        }