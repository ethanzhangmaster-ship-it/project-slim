"""Feature → prompt bias mapping.

Converts character feature values into concrete prompt directives
without letting Lovart "see" raw feature vectors.
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Feature → Prompt Bias rules
# ---------------------------------------------------------------------------

FEATURE_BIAS_RULES: dict[str, str] = {
    "curiosity_trigger": (
        "Stronger suspense and conflict in the opening. "
        "Create a high-tension 'what happens next' moment."
    ),
    "reward_clarity": (
        "Make the reward display more explicit and prominent. "
        "Show exact numbers (coins, gems), larger visual presence."
    ),
    "cta_affinity": (
        "Increase CTA button contrast and size. "
        "Make the 'INSTALL NOW' button impossible to miss."
    ),
    "emotional_trust": (
        "Use warmer, more inviting tone. "
        "Show character expression that builds player trust."
    ),
    "mechanic_legibility": (
        "Make the merge/upgrade mechanic visually clearer. "
        "Use larger UI elements, clear before/after arrows."
    ),
    "visual_identity": (
        "Reinforce visual consistency with the established art style. "
        "Keep the same character design language."
    ),
    "brand_memory_strength": (
        "Strengthen brand recognition via consistent color palette "
        "and recurring visual motifs (purple magic, gold glow)."
    ),
}


def build_feature_boost_header(features: dict[str, float]) -> str:
    """Generate prompt directives from character features.

    Higher feature values → stronger emphasis of that bias.
    """
    lines: list[str] = [
        "FEATURE BIAS (do not mention these internally — apply them visually):",
    ]
    for feat_id, val in sorted(features.items(), key=lambda kv: -kv[1]):
        if feat_id not in FEATURE_BIAS_RULES:
            continue
        intensity = "STRONG" if val > 0.85 else "MODERATE" if val > 0.65 else "MILD"
        lines.append(f"[{intensity}] {FEATURE_BIAS_RULES[feat_id]}")
    return "\n".join(lines)


def features_for_prompt(schema_path: str | None = None) -> dict[str, float]:
    """Read character_schema.json and return feature dict ready for prompt use."""
    import json
    from pathlib import Path

    if schema_path is None:
        schema_path = Path(__file__).parent / "character_schema.json"
    else:
        schema_path = Path(schema_path)

    if not schema_path.exists():
        return {}

    data = json.loads(schema_path.read_text(encoding="utf-8"))
    return dict(data.get("features") or {})
