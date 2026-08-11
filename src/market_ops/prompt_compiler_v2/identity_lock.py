"""Identity Lock — V2 multi-project identity enforcement.

Each project has one locked identity. No per-creative character description.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

IDENTITIES: dict[str, dict[str, Any]] = {
    "witch_v1": {
        "identity_id": "witch_v1",
        "project": "P04 Witch",
        "name": "Witch",
        "style": "cute whimsical witch, warm amber/gold palette, cozy magical atmosphere",
        "constraint": "CHARACTER STYLE: cute whimsical P04 Witch, warm amber/gold palette, soft purple accents. Keep the same witch character across all creatives. Only vary Hook, Reward, Mechanic, Camera, Composition, CTA. Square 1080x1080 pixels, 1:1 ratio. No portrait, no landscape.",
    },
    "mermaid_v1": {
        "identity_id": "mermaid_v1",
        "project": "P02 Mermaid",
        "name": "Mermaid",
        "style": "colorful mermaid characters, vibrant ocean palette, cheerful underwater setting",
        "constraint": "CHARACTER STYLE: colorful P02 Mermaid, vibrant turquoise/ocean palette, cheerful characters. Keep the same mermaid character design across all creatives. Only vary Hook, Reward, Mechanic, Camera, Composition, CTA. Square 1080x1080 pixels, 1:1 ratio. No portrait, no landscape.",
    },
    "vampire_v1": {
        "identity_id": "vampire_v1",
        "project": "P07 Vampire",
        "name": "Vampire",
        "style": "dramatic vampire characters, dark purple/blue palette, Victorian aesthetic, 4-panel comic format",
        "constraint": "CHARACTER STYLE: dramatic P07 Vampire, dark purple/blue palette, Victorian aesthetic, 4-panel comic format. Keep the same vampire identity across all creatives. Only vary Hook, Reward, Mechanic, Camera, Composition, CTA. Square 1080x1080 pixels, 1:1 ratio. No portrait, no landscape.",
    },
}

DEFAULT_IDENTITY = "witch_v1"

# Square size constraint appended to every prompt
SIZE_CONSTRAINT = "Square 1080x1080 pixels, 1:1 aspect ratio. DO NOT generate portrait or landscape."

# V1 legal: only these fields may vary across creatives.
ALLOWED_VARIABLE_FIELDS = {
    "hook", "reward", "mechanic", "camera", "composition", "cta",
}


def validate_identity(spec_identity: str) -> None:
    """Raise if a CreativeSpec identity is not registered."""
    clean = (spec_identity or "").strip().lower()
    if clean not in IDENTITIES:
        raise ValueError(
            f"Identity '{spec_identity}' is not registered. "
            f"Available: {list(IDENTITIES.keys())}"
        )


def identity_ref_constraint(identity_id: str = "witch_v1") -> str:
    """Return the per-project identity constraint string for prompt injection."""
    ident = IDENTITIES.get(identity_id, IDENTITIES[DEFAULT_IDENTITY])
    return ident.get("constraint", "")


def build_identity_metadata(identity_id: str = "witch_v1") -> dict[str, Any]:
    """Return identity metadata for creative metadata JSON."""
    ident = IDENTITIES.get(identity_id, IDENTITIES[DEFAULT_IDENTITY])
    return {"identity": ident["identity_id"], "project": ident["project"]}


def identity_id_for_project(project: str) -> str:
    """Map project name to identity_id."""
    key = (project or "").strip().lower()
    if any(kw in key for kw in ["witch", "p04"]):
        return "witch_v1"
    if any(kw in key for kw in ["mermaid", "p02"]):
        return "mermaid_v1"
    if any(kw in key for kw in ["vampire", "p07"]):
        return "vampire_v1"
    return "witch_v1"
