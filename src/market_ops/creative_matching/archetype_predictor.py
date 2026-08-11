"""E9.6: Archetype Predictor — Rule + Bayesian Archetype Distribution Prediction.

Predicts Player Archetype distribution from Creative DNA features.

Formula:
  1. Raw DNA affinity: feature vector → per-archetype affinity score
  2. Bayesian blending: P(arch | DNA) = α × DNA_affinity + (1-α) × prior
  3. Normalize: ensure all probabilities sum to 1.0

Archetype → DNA Feature mapping:
  Power:      power_expression, payment_affinity, reward_value
  Collector:  collection_strength, reward_value, emotion_intensity
  Explorer:   exploration_strength, novelty_score, emotion_intensity
  Progression: progression_strength, retention_hook_strength, mechanism (merge)
  Casual:     inverse of max active (baseline)
"""

from __future__ import annotations

from typing import Any

from market_ops.creative_matching.schemas import (
    DNAFeatureVector, ArchetypeAffinity, CreativePrediction,
)
from market_ops.creative_matching.creative_archetype_profile import CreativeArchetypeProfileDB


# ═══════════════════════════════════════════════════════════
# DNA → Archetype Affinity Mapping
# ═══════════════════════════════════════════════════════════

# Weight configs for each archetype's raw affinity calculation
_AFFINITY_WEIGHTS = {
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
        "emotion_intensity": 0.20,  # mechanism affinity via emotion
    },
}

# Explanation factors for each archetype
_ARCHETYPE_FACTORS = {
    "power": ["power_expression", "payment_affinity", "reward_value"],
    "collector": ["collection_strength", "reward_value", "emotion_intensity"],
    "explorer": ["exploration_strength", "novelty_score", "emotion_intensity"],
    "progression": ["progression_strength", "retention_hook_strength", "gameplay_loop"],
}

# Bayesian smoothing: weight on DNA signal vs historical prior
_BAYES_ALPHA = 0.8  # 80% DNA signal, 20% historical prior

# Minimum probability floor (avoid zero probabilities)
_MIN_PROBABILITY = 0.01


# ═══════════════════════════════════════════════════════════
# Archetype Predictor
# ═══════════════════════════════════════════════════════════

class ArchetypePredictor:
    """Predicts player archetype distribution from Creative DNA features.

    Usage:
        predictor = ArchetypePredictor(profile_db)
        prediction = predictor.predict(dna_features)
        predictor.set_weights(new_weights)  # from E9.7 learning
    """

    def __init__(self, profile_db: CreativeArchetypeProfileDB | None = None) -> None:
        self._profile_db = profile_db or CreativeArchetypeProfileDB()
        self._custom_weights: dict[str, dict[str, float]] | None = None

    def set_weights(self, weights: dict[str, dict[str, float]]) -> None:
        """Set custom DNA feature weights (from E9.7 learning engine)."""
        self._custom_weights = dict(weights)

    def reset_weights(self) -> None:
        """Reset to default weights."""
        self._custom_weights = None

    def _get_weights(self) -> dict[str, dict[str, float]]:
        """Get current weights (custom or default)."""
        if self._custom_weights:
            return self._custom_weights
        return dict(_AFFINITY_WEIGHTS)

    # ── Single Prediction ──────────────────────────────────

    def predict(self, features: DNAFeatureVector) -> CreativePrediction:
        """Predict archetype distribution for one creative DNA.

        Args:
            features: encoded DNA feature vector

        Returns:
            CreativePrediction with per-archetype probabilities
        """
        prediction = CreativePrediction(
            creative_id=features.creative_id,
            creative_genome_name=features.creative_genome_name,
            dna_features=features,
        )

        # Step 1: Compute raw DNA affinity per archetype
        raw_affinities = self._compute_raw_affinities(features)

        # Step 2: Bayesian blending with historical priors
        priors = self._profile_db.get_global_priors() if self._profile_db.has_historical_data() else {}
        archetype_metrics = self._profile_db.get_all_archetype_metrics()

        blended = self._bayesian_blend(raw_affinities, priors)

        # Step 3: Build ArchetypeAffinity objects
        for arch in ["power", "collector", "explorer", "progression", "casual"]:
            prob = blended.get(arch, _MIN_PROBABILITY)
            raw = raw_affinities.get(arch, 0.0)
            prior = priors.get(arch, 0.2)

            # Get historical metrics for this archetype
            metrics = archetype_metrics.get(arch, {})
            expected_ltv = metrics.get("avg_ltv", 0.0)
            expected_payer_rate = metrics.get("avg_payer_rate", 0.0)
            expected_retention = metrics.get("avg_retention", 0.0)

            # Confidence: how much the prediction differs from prior
            confidence = min(abs(prob - prior) * 2.0 + 0.3, 1.0)

            # Contributing factors
            factors = self._build_factors(arch, features, prob, prior)

            prediction.archetypes[arch] = ArchetypeAffinity(
                archetype=arch,
                raw_affinity=round(raw, 3),
                historical_prior=round(prior, 3),
                adjusted_probability=round(prob, 3),
                confidence=round(confidence, 3),
                expected_ltv=expected_ltv,
                expected_payer_rate=expected_payer_rate,
                expected_retention=expected_retention,
                factors=factors,
            )

        prediction.compute_aggregates()
        return prediction

    def predict_all(
        self,
        features_map: dict[str, DNAFeatureVector],
    ) -> dict[str, CreativePrediction]:
        """Predict for all creative DNAs."""
        predictions = {}
        for cid, features in features_map.items():
            predictions[cid] = self.predict(features)
        return predictions

    # ── Raw Affinity ───────────────────────────────────────

    def _compute_raw_affinities(self, f: DNAFeatureVector) -> dict[str, float]:
        """Compute raw DNA-to-archetype affinity scores."""
        raw = {}
        weights = self._get_weights()

        for arch, weight_map in weights.items():
            score = 0.0
            for field, weight in weight_map.items():
                score += weight * getattr(f, field, 0.0)
            raw[arch] = score

        # Casual = inverse of max active (higher casual when all others are low)
        max_active = max(raw.values()) if raw else 0.0
        raw["casual"] = max(0.0, 1.0 - max_active * 3.0)

        return raw

    # ── Bayesian Blending ──────────────────────────────────

    def _bayesian_blend(
        self,
        raw_affinities: dict[str, float],
        priors: dict[str, float],
    ) -> dict[str, float]:
        """Blend raw DNA affinity with historical priors.

        P(arch | DNA) = α × DNA_affinity_norm + (1-α) × prior

        Where DNA_affinity_norm is softmax-normalized raw scores.
        """
        # Softmax normalize raw affinities
        total = sum(raw_affinities.values())
        if total > 0:
            dna_probs = {
                arch: score / total
                for arch, score in raw_affinities.items()
            }
        else:
            dna_probs = {arch: 0.2 for arch in raw_affinities}

        # Blend with priors
        blended = {}
        for arch in ["power", "collector", "explorer", "progression", "casual"]:
            dna_p = dna_probs.get(arch, 0.2)
            prior_p = priors.get(arch, 0.2)
            blended[arch] = _BAYES_ALPHA * dna_p + (1 - _BAYES_ALPHA) * prior_p

        # Ensure minimum probability
        for arch in blended:
            blended[arch] = max(blended[arch], _MIN_PROBABILITY)

        # Renormalize
        total_blended = sum(blended.values())
        if total_blended > 0:
            for arch in blended:
                blended[arch] = blended[arch] / total_blended

        return blended

    # ── Factors ────────────────────────────────────────────

    def _build_factors(
        self, arch: str, f: DNAFeatureVector,
        prob: float, prior: float,
    ) -> list[str]:
        """Build human-readable explanation factors."""
        factors = []

        # Key features driving this archetype
        feature_labels = {
            "power_expression": "high_power_expression",
            "payment_affinity": "high_payment_affinity",
            "reward_value": "high_reward_value",
            "collection_strength": "high_collection_strength",
            "emotion_intensity": "high_emotion_intensity",
            "exploration_strength": "high_exploration_strength",
            "novelty_score": "high_novelty",
            "progression_strength": "high_progression_strength",
            "retention_hook_strength": "strong_retention_hooks",
        }

        weight_map = self._get_weights().get(arch, {})
        for field in weight_map:
            value = getattr(f, field, 0.0)
            if value > 0.5:
                label = feature_labels.get(field, field)
                factors.append(label)

        # Prior influence
        if abs(prob - prior) > 0.1:
            direction = "boosted" if prob > prior else "reduced"
            factors.append(f"{direction}_by_historical_data")

        if not factors:
            factors = ["baseline_prediction"]

        return factors[:5]