"""E9.6: DNA Feature Encoder — Creative DNA → Numeric Feature Vector.

Maps creative DNA fields (fantasy, hook, reward, mechanism, etc.)
to 10 normalized numeric features (0-1) that predict archetype affinity.

Feature mapping rules:
  - collection_strength: fantasy drives (collect_*, collection) + reward type
  - progression_strength: progression loops + mechanism type
  - power_expression: fantasy (become_powerful, power_*) + payment_triggers
  - exploration_strength: fantasy (discovery_*, explore_*) + hook type
  - emotion_intensity: hook type (emotional > curiosity > fear > challenge)
  - reward_value: reward type + payment_trigger signals
  - novelty_score: visual style uniqueness + fantasy combination novelty
  - urgency_signal: payment_triggers (time_gate, limited_offer)
  - payment_affinity: payment_triggers + reward type
  - retention_hook_strength: retention hooks + progression loops
"""

from __future__ import annotations

from typing import Any

from market_ops.creative_matching.schemas import DNAFeatureVector


# ═══════════════════════════════════════════════════════════
# Keyword → Feature mapping tables
# ═══════════════════════════════════════════════════════════

# Fantasy drives → collection strength
_COLLECTION_KEYWORDS = {
    "collect_dragons", "collect", "collection", "collect_items",
    "collect_pets", "collect_characters", "complete_set", "gotta_collect_all",
    "rare_collection", "hidden_treasure", "item_collection",
}

# Fantasy drives → power expression
_POWER_KEYWORDS = {
    "become_powerful", "power", "powerful", "strong", "strength",
    "dominate", "conquer", "master", "legendary", "ultimate",
    "unstoppable", "evolve_power", "power_up", "super_power",
}

# Fantasy drives → exploration
_EXPLORE_KEYWORDS = {
    "discovery_world", "discovery", "explore", "exploration",
    "new_world", "unknown", "mystery", "adventure", "journey",
    "unlock_secrets", "hidden", "discover", "find",
}

# Hook type → emotion intensity
_HOOK_EMOTION_MAP = {
    "emotional": 0.9,
    "curiosity": 0.7,
    "fear": 0.6,
    "challenge": 0.5,
    "surprise": 0.8,
    "transformation": 0.7,
    "rescue": 0.8,
    "problem_solution": 0.4,
    "comparison": 0.3,
    "": 0.1,
}

# Reward type → reward value
_REWARD_VALUE_MAP = {
    "discovery": 0.7,
    "evolution": 0.8,
    "collection": 0.9,
    "progression": 0.7,
    "power": 0.9,
    "rare_item": 0.95,
    "baby_dragon": 0.85,
    "": 0.3,
}

# Payment trigger → payment affinity
_PAYMENT_TRIGGER_AFFINITY = {
    "time_gate": 0.7,
    "limited_offer": 0.8,
    "exclusive_item": 0.9,
    "blocked_progress": 0.6,
    "missing_item": 0.5,
    "energy": 0.4,
}

# Visual style → novelty boost
_VISUAL_NOVELTY = {
    "3d": 0.7,
    "2d_flat": 0.3,
    "2d_rich": 0.5,
    "hybrid": 0.8,
    "realistic": 0.6,
    "": 0.4,
}

# Mechanism → progression strength
_MECHANISM_PROGRESSION = {
    "merge": 0.8,
    "merge2": 0.8,
    "puzzle": 0.5,
    "match3": 0.6,
    "simulation": 0.7,
    "rpg": 0.9,
    "": 0.4,
}


# ═══════════════════════════════════════════════════════════
# DNA Feature Encoder
# ═══════════════════════════════════════════════════════════

class DNAFeatureEncoder:
    """Encodes Creative DNA into numeric feature vector.

    Usage:
        encoder = DNAFeatureEncoder()
        features = encoder.encode(creative_dna_entry)
        all_features = encoder.encode_all(creative_dna_list)
    """

    def __init__(self) -> None:
        self._features: dict[str, DNAFeatureVector] = {}

    def encode(self, creative_dna: dict[str, Any]) -> DNAFeatureVector:
        """Encode a single creative DNA entry into feature vector.

        Args:
            creative_dna: dict from creative_dna_master.json

        Returns:
            DNAFeatureVector with 10 normalized features
        """
        creative_id = creative_dna.get("creative_id", "")
        creative_name = creative_dna.get("creative_name", "")

        # Extract DNA sub-fields
        fantasy = creative_dna.get("fantasy", {})
        hook = creative_dna.get("hook", {})
        reward = creative_dna.get("reward", {})
        mechanism = creative_dna.get("mechanism", {})
        visual = creative_dna.get("visual", {})
        progression = creative_dna.get("progression", {})
        payment_trigger = creative_dna.get("payment_trigger", {})
        retention = creative_dna.get("retention", {})

        # Parse values
        fantasy_drives = self._get_list(fantasy, "drives")
        fantasy_loops = self._get_list(fantasy, "loops")
        all_fantasy = fantasy_drives + fantasy_loops

        hook_type = self._get_str(hook, "type")
        reward_type = self._get_str(reward, "type")
        mechanism_type = self._get_str(mechanism, "type")
        visual_style = self._get_str(visual, "style")
        progression_loops = self._get_list(progression, "loops")
        payment_triggers = self._get_list(payment_trigger, "triggers")
        retention_hooks = self._get_list(retention, "hooks")

        # ── Compute features ──

        # Collection strength: fantasy drives matching collection keywords
        collection_strength = self._keyword_match_score(
            all_fantasy, _COLLECTION_KEYWORDS,
        )
        # Boost if reward type is collection-related
        if reward_type in ("collection", "rare_item", "baby_dragon"):
            collection_strength = min(1.0, collection_strength + 0.2)

        # Progression strength: mechanism + progression loops
        progression_strength = _MECHANISM_PROGRESSION.get(mechanism_type, 0.4)
        if progression_loops:
            progression_strength = min(1.0, progression_strength + 0.15)

        # Power expression: fantasy keywords + payment triggers
        power_expression = self._keyword_match_score(
            all_fantasy, _POWER_KEYWORDS,
        )
        if payment_triggers:
            power_expression = min(1.0, power_expression + 0.15)

        # Exploration strength: fantasy keywords + hook type
        exploration_strength = self._keyword_match_score(
            all_fantasy, _EXPLORE_KEYWORDS,
        )
        if hook_type in ("curiosity", "mystery", "surprise"):
            exploration_strength = min(1.0, exploration_strength + 0.15)

        # Emotion intensity: hook type mapping
        emotion_intensity = _HOOK_EMOTION_MAP.get(hook_type, 0.3)

        # Reward value: reward type mapping
        reward_value = _REWARD_VALUE_MAP.get(reward_type, 0.3)

        # Novelty: visual style + fantasy combination diversity
        novelty_score = _VISUAL_NOVELTY.get(visual_style, 0.4)
        if len(all_fantasy) >= 3:
            novelty_score = min(1.0, novelty_score + 0.1)

        # Urgency: payment triggers
        urgency_signal = 0.0
        for t in payment_triggers:
            if t in ("time_gate", "limited_offer"):
                urgency_signal = max(urgency_signal, 0.7)
            elif t in ("energy", "blocked_progress"):
                urgency_signal = max(urgency_signal, 0.4)

        # Payment affinity: payment triggers + reward
        payment_affinity = 0.0
        for t in payment_triggers:
            payment_affinity = max(
                payment_affinity,
                _PAYMENT_TRIGGER_AFFINITY.get(t, 0.3),
            )
        if reward_type in ("power", "rare_item", "evolution"):
            payment_affinity = min(1.0, payment_affinity + 0.15)

        # Retention hook strength: retention hooks + progression
        retention_hook_strength = 0.0
        if retention_hooks:
            retention_hook_strength = min(1.0, len(retention_hooks) * 0.3)
        if progression_loops:
            retention_hook_strength = min(1.0, retention_hook_strength + 0.2)

        # Build genome name from signature
        genome_name = self._build_genome_name(
            fantasy_drives, hook_type, mechanism_type, reward_type,
        )

        return DNAFeatureVector(
            creative_id=creative_id,
            creative_genome_name=genome_name,
            collection_strength=round(collection_strength, 3),
            progression_strength=round(progression_strength, 3),
            power_expression=round(power_expression, 3),
            exploration_strength=round(exploration_strength, 3),
            emotion_intensity=round(emotion_intensity, 3),
            reward_value=round(reward_value, 3),
            novelty_score=round(novelty_score, 3),
            urgency_signal=round(urgency_signal, 3),
            payment_affinity=round(payment_affinity, 3),
            retention_hook_strength=round(retention_hook_strength, 3),
            fantasy_drives=all_fantasy,
            mechanism_type=mechanism_type,
            hook_type=hook_type,
            reward_type=reward_type,
            visual_style=visual_style,
            payment_triggers=payment_triggers,
            retention_hooks=retention_hooks,
        )

    def encode_all(
        self,
        creative_dna_list: list[dict[str, Any]],
    ) -> dict[str, DNAFeatureVector]:
        """Encode all creative DNA entries.

        Returns:
            {creative_id: DNAFeatureVector}
        """
        self._features = {}
        for entry in creative_dna_list:
            fv = self.encode(entry)
            self._features[fv.creative_id] = fv
        return self._features

    # ── Helpers ────────────────────────────────────────────

    @staticmethod
    def _get_list(d: dict, key: str) -> list[str]:
        val = d.get(key, [])
        if isinstance(val, list):
            return val
        return []

    @staticmethod
    def _get_str(d: dict, key: str) -> str:
        val = d.get(key, "")
        if isinstance(val, str):
            return val
        return ""

    @staticmethod
    def _keyword_match_score(
        source: list[str], keywords: set[str],
    ) -> float:
        """Score how many source terms match the keyword set."""
        if not source:
            return 0.0
        matches = sum(1 for s in source if s.lower() in keywords)
        # Normalize: 1 match = 0.5, 2+ matches = 0.8, 3+ = 1.0
        if matches >= 3:
            return 1.0
        elif matches >= 2:
            return 0.8
        elif matches >= 1:
            return 0.5
        return 0.0

    @staticmethod
    def _build_genome_name(
        fantasy: list[str], hook: str, mechanism: str, reward: str,
    ) -> str:
        """Build human-readable genome name."""
        parts = []
        if fantasy:
            parts.append("-".join(fantasy[:2]))
        if hook:
            parts.append(hook)
        if mechanism:
            parts.append(mechanism)
        if reward:
            parts.append(reward)
        return "_".join(parts) if parts else "unknown"

    @property
    def features(self) -> dict[str, DNAFeatureVector]:
        return self._features