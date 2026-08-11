"""Map ad metric changes → character feature deltas.

Rule table:
  Metric change    → attributed feature
  CTR ↑            → curiosity_trigger
  CVR ↑            → reward_clarity
  ROAS ↑           → cta_affinity + emotional_trust
  IPM ↑            → visual_identity
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Attribution mapping
# ---------------------------------------------------------------------------

ATTRIBUTION_RULES: dict[str, list[str]] = {
    "ctr_signal": ["curiosity_trigger"],
    "cvr_signal": ["reward_clarity"],
    "roas_signal": ["cta_affinity", "emotional_trust"],
    "ipm_signal": ["visual_identity"],
}

DEFAULT_LEARNING_RATE = 0.05

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_feature_deltas(
    *,
    signals: dict[str, float],
    learning_rate: float = DEFAULT_LEARNING_RATE,
) -> dict[str, Any]:
    """Convert CAF extractor signals to character feature deltas.

    Returns {
        "feature_deltas": {feature_name: delta, ...},
        "attribution": {signal: [features], ...},
    }
    """
    deltas: dict[str, float] = {}
    attribution: dict[str, list[str]] = {}

    for signal_key, signal_val in signals.items():
        features = ATTRIBUTION_RULES.get(signal_key, [])
        if not features:
            continue
        attribution[signal_key] = list(features)
        for feat in features:
            delta = signal_val * learning_rate
            deltas[feat] = round(deltas.get(feat, 0.0) + delta, 4)

    return {
        "feature_deltas": deltas,
        "attribution": attribution,
    }
