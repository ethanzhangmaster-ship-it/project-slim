"""
E16.6.3 — ASO Creative Generator Bridge (Lovart / Image Agent interface).

E16.6.3 deliberately does **not** re-invent a creative generator. It formats an
ASO-driven generation *request* from an ``OptimizationAction`` and hands it to a
real image agent (Lovart, Midjourney, an in-house E11 generator, …) through the
``GeneratorSink`` Protocol. The returned candidates are then re-scored by the
vision analyzer and pushed into an experiment.

Flow:
    ASO Optimizer → OptimizationAction
        → ASOCreativeGeneratorBridge.build_request  (formats the brief)
        → GeneratorSink.generate                    (real image agent, dry-run in tests)
        → GeneratedCandidate(s)
        → vision analyzer re-scores → experiment

``DryRunGenerator`` is a test double that returns a structured placeholder
candidate (no network, no pixels) so the whole loop is exercisable offline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from src.aso_intelligence.creative.models import (
    ASOCreativeDNA,
    ASOCreativePattern,
    AssetType,
    OptimizationAction,
)


# --------------------------------------------------------------------------- #
# Request / candidate
# --------------------------------------------------------------------------- #
@dataclass
class GeneratorRequest:
    """A formatted creative-generation brief for an image agent."""

    game_id: str
    asset_type: AssetType
    target: str
    category: str
    prompt: str
    desired_traits: Dict[str, str] = field(default_factory=dict)
    reference_urls: List[str] = field(default_factory=list)
    source_action: str = ""  # the OptimizationAction.reason/suggestion origin
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "asset_type": self.asset_type.value,
            "target": self.target,
            "category": self.category,
            "prompt": self.prompt,
            "desired_traits": dict(self.desired_traits),
            "reference_urls": list(self.reference_urls),
            "source_action": self.source_action,
            "extra": self.extra,
        }


@dataclass
class GeneratedCandidate:
    """One candidate asset returned by the generator (or a dry-run placeholder)."""

    asset_type: AssetType
    url: str
    prompt_used: str
    source: str = "lovart"  # "lovart" | "dryrun"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_type": self.asset_type.value,
            "url": self.url,
            "prompt_used": self.prompt_used,
            "source": self.source,
            "metadata": self.metadata,
        }


# --------------------------------------------------------------------------- #
# Sink protocol (real image agent plugs here)
# --------------------------------------------------------------------------- #
@runtime_checkable
class GeneratorSink(Protocol):
    """An external image-generation agent (Lovart, E11 generator, …)."""

    def generate(self, request: GeneratorRequest) -> List[GeneratedCandidate]:
        ...


# --------------------------------------------------------------------------- #
# Bridge
# --------------------------------------------------------------------------- #
class ASOCreativeGeneratorBridge:
    """Formats ASO optimization actions into generator requests."""

    def __init__(self, sink: GeneratorSink):
        self._sink = sink

    # ------------------------------------------------------------------ #
    def build_prompt(
        self,
        opt: OptimizationAction,
        category: str,
        *,
        current_dna: Optional[ASOCreativeDNA] = None,
        pattern: Optional[ASOCreativePattern] = None,
        reference_urls: Optional[List[str]] = None,
    ) -> str:
        """Build the human/agent-readable generation brief text."""
        traits = self._desired_traits(opt, current_dna, pattern)
        trait_str = (
            ", ".join(f"{k}={v}" for k, v in traits.items())
            if traits
            else "none (free generation)"
        )
        refs = ", ".join(reference_urls or []) or "none"
        lines = [
            "ASO Creative Generation Brief",
            f"Game: {opt.game_id}",
            f"Asset: {opt.asset_type.value} ({opt.target})",
            f"Category: {category}",
            f"Problem: {opt.reason}",
            f"Direction: {opt.suggestion}",
            f"Desired creative DNA: {trait_str}",
            f"Reference style: {refs}",
        ]
        return "\n".join(lines)

    def _desired_traits(
        self,
        opt: OptimizationAction,
        current_dna: Optional[ASOCreativeDNA],
        pattern: Optional[ASOCreativePattern],
    ) -> Dict[str, str]:
        traits: Dict[str, str] = {}
        # 1) desired traits from the mined competitor pattern ("dim:value")
        if pattern is not None and pattern.pattern:
            if ":" in pattern.pattern:
                dim, val = pattern.pattern.split(":", 1)
                traits[dim.strip()] = val.strip()
        # 2) carry over the current DNA (so we keep brand identity)
        if current_dna is not None:
            for f in (
                "dominant_color",
                "character_style",
                "composition",
                "message_type",
                "emotional_trigger",
                "gameplay_focus",
            ):
                v = getattr(current_dna, f, "unknown")
                if v and v != "unknown" and f not in traits:
                    traits[f] = v
        return traits

    def build_request(
        self,
        opt: OptimizationAction,
        category: str,
        *,
        current_dna: Optional[ASOCreativeDNA] = None,
        pattern: Optional[ASOCreativePattern] = None,
        reference_urls: Optional[List[str]] = None,
    ) -> GeneratorRequest:
        prompt = self.build_prompt(
            opt,
            category,
            current_dna=current_dna,
            pattern=pattern,
            reference_urls=reference_urls,
        )
        return GeneratorRequest(
            game_id=opt.game_id,
            asset_type=opt.asset_type,
            target=opt.target,
            category=category,
            prompt=prompt,
            desired_traits=self._desired_traits(opt, current_dna, pattern),
            reference_urls=list(reference_urls or []),
            source_action=opt.reason,
        )

    def generate(
        self,
        opt: OptimizationAction,
        category: str,
        *,
        current_dna: Optional[ASOCreativeDNA] = None,
        pattern: Optional[ASOCreativePattern] = None,
        reference_urls: Optional[List[str]] = None,
    ) -> List[GeneratedCandidate]:
        req = self.build_request(
            opt,
            category,
            current_dna=current_dna,
            pattern=pattern,
            reference_urls=reference_urls,
        )
        return self._sink.generate(req)


# --------------------------------------------------------------------------- #
# Dry-run sink (test double)
# --------------------------------------------------------------------------- #
class DryRunGenerator:
    """Test double: returns one placeholder candidate, no network / no pixels."""

    def generate(self, request: GeneratorRequest) -> List[GeneratedCandidate]:
        return [
            GeneratedCandidate(
                asset_type=request.asset_type,
                url="",  # no real asset in dry-run
                prompt_used=request.prompt,
                source="dryrun",
                metadata={"desired_traits": request.desired_traits},
            )
        ]


__all__ = [
    "GeneratorRequest",
    "GeneratedCandidate",
    "GeneratorSink",
    "ASOCreativeGeneratorBridge",
    "DryRunGenerator",
]
