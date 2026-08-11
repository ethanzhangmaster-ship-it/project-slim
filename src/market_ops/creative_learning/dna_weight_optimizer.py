"""E9.7: DNA Weight Optimizer — Learns optimal DNA feature weights from errors.

Analyzes prediction errors grouped by DNA features (hook type, reward type,
mechanism) and adjusts archetype affinity weights to minimize future errors.

Algorithm (V1 Rule-Based):
  1. Group errors by DNA feature (hook, reward, mechanism)
  2. Compute mean error per archetype per feature group
  3. If error > threshold: increase weight (feature was undervalued)
  4. If error < -threshold: decrease weight (feature was overvalued)
  5. Apply learning rate to smooth updates
  6. Normalize weights per archetype (sum to 1.0)
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from market_ops.creative_learning.schemas import (
    PredictionRecord, CreativeActualPerformance, PredictionError,
    DNAWeightUpdate, DNAWeightConfig,
)


# ═══════════════════════════════════════════════════════════
# Default weights (from E9.6 archetype_predictor.py)
# ═══════════════════════════════════════════════════════════

_DEFAULT_WEIGHTS = {
    "power": {
        "power_expression": 0.50,
        "payment_affinity": 0.30,
        "reward_value": 0.20,
    },
    "collector": {
        "collection_strength": 0.50,
        "reward_value": 0.30,
        "emotion_intensity": 0.20,
    },
    "explorer": {
        "exploration_strength": 0.50,
        "novelty_score": 0.30,
        "emotion_intensity": 0.20,
    },
    "progression": {
        "progression_strength": 0.50,
        "retention_hook_strength": 0.30,
        "emotion_intensity": 0.20,
    },
}

# DNA feature → archetype mapping (which features affect which archetypes)
_FEATURE_ARCHETYPE_MAP = {
    "power_expression": ["power"],
    "payment_affinity": ["power"],
    "reward_value": ["power", "collector"],
    "collection_strength": ["collector"],
    "emotion_intensity": ["collector", "explorer", "progression"],
    "exploration_strength": ["explorer"],
    "novelty_score": ["explorer"],
    "progression_strength": ["progression"],
    "retention_hook_strength": ["progression"],
}

# DNA feature → source field mapping (for error grouping)
_FEATURE_SOURCE_MAP = {
    "hook_type": ["emotion_intensity"],
    "reward_type": ["reward_value"],
    "mechanism_type": ["progression_strength"],
    "fantasy_drives": ["power_expression", "collection_strength", "exploration_strength"],
    "payment_triggers": ["payment_affinity"],
    "retention_hooks": ["retention_hook_strength"],
}


# ═══════════════════════════════════════════════════════════
# DNA Weight Optimizer
# ═══════════════════════════════════════════════════════════

class DNAWeightOptimizer:
    """Learns optimal DNA feature weights from prediction errors.

    Usage:
        optimizer = DNAWeightOptimizer()
        optimizer.load_weights()  # or start from defaults
        config = optimizer.optimize(errors, predictions, actuals)
        optimizer.save_weights("dna_weight_config.json")
    """

    def __init__(self) -> None:
        self._weights: dict[str, dict[str, float]] = {
            arch: dict(features)
            for arch, features in _DEFAULT_WEIGHTS.items()
        }
        self._updates: list[DNAWeightUpdate] = []
        self._learning_rate: float = 0.25
        self._error_threshold: float = 0.01  # min error to trigger update

    # ── Loading ────────────────────────────────────────────

    def load_weights(self, config: dict[str, dict[str, float]] | None = None) -> None:
        """Load weight configuration (or use defaults)."""
        if config:
            self._weights = {
                arch: dict(features) if features else {}
                for arch, features in config.items()
            }
        else:
            self._weights = {
                arch: dict(features)
                for arch, features in _DEFAULT_WEIGHTS.items()
            }

    def load_defaults(self) -> None:
        self._weights = {
            arch: dict(features)
            for arch, features in _DEFAULT_WEIGHTS.items()
        }

    # ── Optimization ───────────────────────────────────────

    def optimize(
        self,
        errors: dict[str, PredictionError],
        predictions: dict[str, PredictionRecord],
        actuals: dict[str, CreativeActualPerformance],
    ) -> DNAWeightConfig:
        """Optimize DNA feature weights based on prediction errors.

        Args:
            errors: per-creative prediction errors
            predictions: original prediction records
            actuals: actual performance data

        Returns:
            DNAWeightConfig with updated weights
        """
        self._updates = []

        # Step 1: Group errors by DNA feature values
        feature_errors = self._group_errors_by_feature(errors, predictions, actuals)

        # Step 2: For each (feature, archetype) pair, compute error and adjust
        for source_field, feature_list in _FEATURE_SOURCE_MAP.items():
            for feature in feature_list:
                target_arches = _FEATURE_ARCHETYPE_MAP.get(feature, [])
                for arch in target_arches:
                    key = (source_field, arch)
                    if key not in feature_errors:
                        continue

                    # Get errors grouped by feature value
                    value_errors = feature_errors[key]

                    for feature_value, error_data in value_errors.items():
                        if not error_data:
                            continue

                        # Skip empty/unknown feature values (noise)
                        if feature_value in ("", "unknown", "none"):
                            continue

                        mean_error = sum(error_data) / len(error_data)

                        # Only adjust if error is significant
                        if abs(mean_error) < self._error_threshold:
                            continue

                        # Underprediction (actual > predicted) → increase weight
                        # Overprediction (actual < predicted) → decrease weight
                        delta = mean_error * self._learning_rate
                        delta = max(-0.3, min(0.3, delta))  # clamp

                        old_weight = self._weights.get(arch, {}).get(feature, 0.0)
                        new_weight = max(0.01, min(0.9, old_weight + delta))

                        if abs(new_weight - old_weight) > 0.001:
                            self._weights.setdefault(arch, {})[feature] = new_weight

                            direction = "increased" if delta > 0 else "decreased"
                            reason = (
                                f"{feature_value} {source_field}: "
                                f"{direction} {feature} weight by {abs(delta):.3f} "
                                f"(mean_error={mean_error:.3f})"
                            )

                            self._updates.append(DNAWeightUpdate(
                                feature=feature,
                                archetype=arch,
                                old_weight=round(old_weight, 3),
                                new_weight=round(new_weight, 3),
                                delta=round(delta, 3),
                                reason=reason,
                            ))

        # Step 3: Normalize weights per archetype
        self._normalize_weights()

        # Step 4: Build config
        return DNAWeightConfig(
            version="1.1",
            updated_at=datetime.now(timezone.utc).isoformat(),
            weights=self._weights,
            updates=self._updates,
        )

    def _group_errors_by_feature(
        self,
        errors: dict[str, PredictionError],
        predictions: dict[str, PredictionRecord],
        actuals: dict[str, CreativeActualPerformance],
    ) -> dict[tuple[str, str], dict[str, list[float]]]:
        """Group archetype prediction errors by DNA feature values.

        Returns:
            {(source_field, archetype): {feature_value: [error_values]}}
        """
        grouped: dict[tuple[str, str], dict[str, list[float]]] = defaultdict(
            lambda: defaultdict(list),
        )

        for cid, error in errors.items():
            pred = predictions.get(cid)
            actual = actuals.get(cid)
            if pred is None or actual is None:
                continue

            dna = pred.dna_features
            source = dna.get("source_dna", {}) if isinstance(dna, dict) else {}

            # For each source field, extract the feature value
            for source_field, feature_list in _FEATURE_SOURCE_MAP.items():
                feature_value = None

                if source_field == "hook_type":
                    feature_value = source.get("hook", "") or "unknown"
                elif source_field == "reward_type":
                    feature_value = source.get("reward", "") or "unknown"
                elif source_field == "mechanism_type":
                    feature_value = source.get("mechanism", "") or "unknown"
                elif source_field == "payment_triggers":
                    triggers = source.get("payment_triggers", [])
                    feature_value = triggers[0] if triggers else "none"
                elif source_field == "retention_hooks":
                    hooks = source.get("retention_hooks", [])
                    feature_value = hooks[0] if hooks else "none"
                elif source_field == "fantasy_drives":
                    drives = source.get("fantasy", [])
                    if isinstance(drives, list):
                        feature_value = drives[0] if drives else "none"
                    else:
                        feature_value = "none"

                if feature_value is None:
                    continue

                # For each affected feature, collect archetype errors
                for feature in feature_list:
                    target_arches = _FEATURE_ARCHETYPE_MAP.get(feature, [])
                    for arch in target_arches:
                        if arch in error.archetype_errors:
                            arch_err = error.archetype_errors[arch].absolute_error
                            key = (source_field, arch)
                            grouped[key][feature_value].append(arch_err)

        return dict(grouped)

    def _normalize_weights(self) -> None:
        """Normalize weights per archetype to sum to 1.0."""
        for arch, features in self._weights.items():
            total = sum(features.values())
            if total > 0:
                for feature in features:
                    features[feature] = round(features[feature] / total, 3)

    # ── Saving ─────────────────────────────────────────────

    def save_weights(self, path: str) -> str:
        """Save weight configuration to JSON."""
        import json
        from pathlib import Path

        config = DNAWeightConfig(
            version="1.1",
            updated_at=datetime.now(timezone.utc).isoformat(),
            weights=self._weights,
            updates=self._updates,
        )

        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(config.to_dict(), f, ensure_ascii=False, indent=2)

        return str(p)

    # ── Queries ────────────────────────────────────────────

    def get_weights(self) -> dict[str, dict[str, float]]:
        return self._weights

    def get_weight(self, archetype: str, feature: str) -> float:
        return self._weights.get(archetype, {}).get(feature, 0.0)

    def get_weight_deltas(self) -> dict[str, dict[str, float]]:
        """Get weight changes from defaults."""
        deltas = {}
        for arch, features in self._weights.items():
            defaults = _DEFAULT_WEIGHTS.get(arch, {})
            deltas[arch] = {}
            for feat, w in features.items():
                default_w = defaults.get(feat, 0.0)
                deltas[arch][feat] = round(w - default_w, 3)
        return deltas

    @property
    def updates(self) -> list[DNAWeightUpdate]:
        return self._updates

    @property
    def total_updates(self) -> int:
        return len(self._updates)