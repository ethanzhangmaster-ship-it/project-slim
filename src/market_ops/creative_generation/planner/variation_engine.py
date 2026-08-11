"""Phase 3.0: Variation Engine — the core variation generator.

Input: Winner DNA (e.g., {"character": "witch", "camera": "45_degree"})
Output: Multiple variations per dimension (e.g., "Cute Witch", "Dark Witch", "Golden Witch")

The Variation Engine is the heart of the Creative Prompt Planner. It takes
a single DNA and expands each dimension into multiple creative variants,
enabling massive prompt diversity from a single source.

Supports 4 strategies:
  - Conservative: small changes (1-2 adjective variations)
  - Balanced: moderate changes (3-5 variations per dimension)
  - Aggressive: many changes (different directions)
  - Experimental: radical changes (cross-category)
"""

from __future__ import annotations

import random
from typing import Any

from ..models.variation import Variation


# ═══════════════════════════════════════════════════════════
# Variation Libraries — per-dimension thesaurus
# ═══════════════════════════════════════════════════════════

CHARACTER_VARIANTS: dict[str, list[tuple[str, str, float]]] = {
    "witch": [
        ("young_witch", "Young Witch", 0.2),
        ("cute_witch", "Cute Witch", 0.3),
        ("magic_witch", "Magic Witch", 0.3),
        ("happy_witch", "Happy Witch", 0.4),
        ("dark_witch", "Dark Witch", 0.6),
        ("golden_witch", "Golden Witch", 0.5),
        ("victory_witch", "Victory Witch", 0.5),
        ("mysterious_witch", "Mysterious Witch", 0.6),
        ("powerful_sorceress", "Powerful Sorceress", 0.7),
        ("enchanted_witch", "Enchanted Witch", 0.4),
        ("celestial_witch", "Celestial Witch", 0.7),
        ("shadow_witch", "Shadow Witch", 0.8),
    ],
    "dragon": [
        ("baby_dragon", "Baby Dragon", 0.2),
        ("cute_dragon", "Cute Dragon", 0.3),
        ("blue_dragon", "Blue Dragon", 0.4),
        ("fire_dragon", "Fire Dragon", 0.5),
        ("ice_dragon", "Ice Dragon", 0.6),
        ("golden_dragon", "Golden Dragon", 0.5),
        ("crystal_dragon", "Crystal Dragon", 0.6),
        ("storm_dragon", "Storm Dragon", 0.7),
        ("shadow_dragon", "Shadow Dragon", 0.8),
        ("celestial_dragon", "Celestial Dragon", 0.7),
    ],
    "fairy": [
        ("cute_fairy", "Cute Fairy", 0.2),
        ("sparkle_fairy", "Sparkle Fairy", 0.3),
        ("forest_fairy", "Forest Fairy", 0.4),
        ("moon_fairy", "Moon Fairy", 0.5),
        ("star_fairy", "Star Fairy", 0.5),
        ("dark_fairy", "Dark Fairy", 0.6),
        ("crystal_fairy", "Crystal Fairy", 0.5),
    ],
    "wizard": [
        ("young_wizard", "Young Wizard", 0.2),
        ("powerful_wizard", "Powerful Wizard", 0.4),
        ("ancient_wizard", "Ancient Wizard", 0.6),
        ("dark_wizard", "Dark Wizard", 0.7),
        ("elemental_wizard", "Elemental Wizard", 0.5),
    ],
    "princess": [
        ("cute_princess", "Cute Princess", 0.2),
        ("warrior_princess", "Warrior Princess", 0.5),
        ("magic_princess", "Magic Princess", 0.4),
        ("ice_princess", "Ice Princess", 0.6),
        ("dark_princess", "Dark Princess", 0.7),
    ],
}

CAMERA_VARIANTS: dict[str, list[tuple[str, str, float]]] = {
    "45_degree": [
        ("35_degree", "35° Angle", 0.2),
        ("55_degree", "55° Angle", 0.3),
        ("top_down", "Top Down", 0.6),
        ("low_angle", "Low Angle", 0.5),
        ("eye_level", "Eye Level", 0.4),
        ("dutch_angle", "Dutch Tilt", 0.7),
    ],
    "top_down": [
        ("45_degree", "45° Overhead", 0.4),
        ("isometric", "Isometric", 0.3),
        ("bird_eye", "Bird's Eye", 0.5),
        ("low_angle", "Low Angle", 0.7),
    ],
    "close_up": [
        ("extreme_close_up", "Extreme Close-Up", 0.3),
        ("medium_shot", "Medium Shot", 0.4),
        ("full_body", "Full Body", 0.5),
        ("cowboy_shot", "Cowboy Shot", 0.6),
    ],
    "medium_shot": [
        ("close_up", "Close-Up", 0.3),
        ("full_body", "Full Body", 0.4),
        ("wide_shot", "Wide Shot", 0.5),
    ],
}

COMPOSITION_VARIANTS: dict[str, list[tuple[str, str, float]]] = {
    "center": [
        ("left_focus", "Left Focus", 0.4),
        ("right_focus", "Right Focus", 0.4),
        ("diagonal", "Diagonal", 0.5),
        ("triangle", "Triangle", 0.5),
        ("rule_of_thirds", "Rule of Thirds", 0.3),
        ("golden_ratio", "Golden Ratio", 0.6),
        ("symmetrical", "Symmetrical", 0.3),
        ("framing", "Natural Frame", 0.5),
    ],
    "left_focus": [
        ("right_focus", "Right Focus", 0.5),
        ("center", "Center", 0.4),
        ("diagonal", "Diagonal", 0.5),
    ],
    "triangle": [
        ("inverted_triangle", "Inverted Triangle", 0.4),
        ("diamond", "Diamond", 0.5),
        ("circle", "Circle", 0.6),
    ],
}

LIGHTING_VARIANTS: dict[str, list[tuple[str, str, float]]] = {
    "warm": [
        ("golden_hour", "Golden Hour", 0.3),
        ("soft_diffuse", "Soft Diffuse", 0.3),
        ("sunset", "Sunset", 0.4),
        ("fantasy_glow", "Fantasy Glow", 0.4),
        ("cinematic", "Cinematic", 0.5),
        ("dramatic", "Dramatic", 0.6),
        ("volumetric", "Volumetric Light", 0.5),
    ],
    "cool": [
        ("moonlight", "Moonlight", 0.3),
        ("mystical", "Mystical Blue", 0.4),
        ("neon", "Neon", 0.6),
        ("aurora", "Aurora", 0.7),
    ],
    "magical_glow": [
        ("sparkle", "Sparkle Light", 0.3),
        ("ethereal", "Ethereal", 0.4),
        ("rune_glow", "Rune Glow", 0.5),
        ("portal_light", "Portal Light", 0.6),
    ],
    "dramatic": [
        ("chiaroscuro", "Chiaroscuro", 0.5),
        ("rim_light", "Rim Light", 0.4),
        ("silhouette", "Silhouette", 0.6),
        ("god_rays", "God Rays", 0.5),
    ],
}

COLOR_PALETTE_VARIANTS: dict[str, list[tuple[str, str, float]]] = {
    "purple_gold": [
        ("purple_silver", "Purple Silver", 0.3),
        ("violet_gold", "Violet Gold", 0.2),
        ("amethyst", "Amethyst", 0.4),
        ("deep_purple", "Deep Purple", 0.3),
        ("lavender_gold", "Lavender Gold", 0.4),
    ],
    "purple": [
        ("purple_gold", "Purple Gold", 0.3),
        ("purple_blue", "Purple Blue", 0.4),
        ("purple_pink", "Purple Pink", 0.5),
        ("dark_purple", "Dark Purple", 0.4),
    ],
    "warm_golden": [
        ("warm_orange", "Warm Orange", 0.3),
        ("golden_amber", "Golden Amber", 0.2),
        ("autumn_gold", "Autumn Gold", 0.4),
        ("rose_gold", "Rose Gold", 0.5),
    ],
    "blue_cool": [
        ("cyan", "Cyan", 0.3),
        ("ice_blue", "Ice Blue", 0.3),
        ("deep_blue", "Deep Blue", 0.5),
        ("teal", "Teal", 0.4),
    ],
    "green": [
        ("emerald", "Emerald", 0.3),
        ("forest_green", "Forest Green", 0.3),
        ("mint", "Mint", 0.5),
        ("jade", "Jade", 0.4),
    ],
}

REWARD_VARIANTS: dict[str, list[tuple[str, str, float]]] = {
    "baby_dragon": [
        ("blue_dragon", "Blue Dragon", 0.3),
        ("fire_dragon", "Fire Dragon", 0.4),
        ("ice_dragon", "Ice Dragon", 0.5),
        ("golden_dragon", "Golden Dragon", 0.4),
        ("crystal_dragon", "Crystal Dragon", 0.5),
        ("baby_phoenix", "Baby Phoenix", 0.6),
        ("baby_griffin", "Baby Griffin", 0.7),
    ],
    "treasure": [
        ("gold_coins", "Gold Coins", 0.3),
        ("gem_stones", "Gem Stones", 0.3),
        ("magic_chest", "Magic Chest", 0.4),
        ("crystal_crown", "Crystal Crown", 0.5),
        ("ancient_artifact", "Ancient Artifact", 0.6),
    ],
    "castle": [
        ("floating_castle", "Floating Castle", 0.4),
        ("crystal_castle", "Crystal Castle", 0.5),
        ("dark_castle", "Dark Castle", 0.6),
        ("sky_castle", "Sky Castle", 0.5),
    ],
    "evolution": [
        ("transformation", "Transformation", 0.3),
        ("level_up", "Level Up", 0.3),
        ("unlock", "Unlock", 0.4),
        ("merge", "Merge", 0.3),
    ],
}

GAMEPLAY_VARIANTS: dict[str, list[tuple[str, str, float]]] = {
    "merge": [
        ("drag_merge", "Drag and Merge", 0.2),
        ("auto_merge", "Auto Merge", 0.3),
        ("chain_merge", "Chain Merge", 0.4),
        ("combo_merge", "Combo Merge", 0.4),
        ("explosion_merge", "Explosion Merge", 0.6),
    ],
    "evolution": [
        ("instant_evolution", "Instant Evolution", 0.3),
        ("staged_evolution", "Staged Evolution", 0.4),
        ("ultimate_evolution", "Ultimate Evolution", 0.5),
    ],
    "collection": [
        ("item_collection", "Item Collection", 0.2),
        ("set_collection", "Set Collection", 0.3),
        ("rare_collection", "Rare Collection", 0.4),
        ("complete_collection", "Complete Collection", 0.5),
    ],
    "puzzle": [
        ("match_three", "Match Three", 0.2),
        ("tile_match", "Tile Match", 0.3),
        ("solve_puzzle", "Solve Puzzle", 0.3),
        ("unlock_secret", "Unlock Secret", 0.5),
    ],
}

EMOTION_VARIANTS: dict[str, list[tuple[str, str, float]]] = {
    "surprise": [
        ("excitement", "Excitement", 0.3),
        ("awe", "Awe", 0.4),
        ("shock", "Shock", 0.5),
        ("wonder", "Wonder", 0.3),
        ("amazement", "Amazement", 0.3),
    ],
    "happiness": [
        ("joy", "Joy", 0.3),
        ("delight", "Delight", 0.3),
        ("triumph", "Triumph", 0.5),
        ("satisfaction", "Satisfaction", 0.3),
    ],
    "curiosity": [
        ("intrigue", "Intrigue", 0.3),
        ("mystery", "Mystery", 0.4),
        ("discovery", "Discovery", 0.3),
        ("anticipation", "Anticipation", 0.4),
    ],
    "determination": [
        ("focus", "Focus", 0.3),
        ("power", "Power", 0.4),
        ("confidence", "Confidence", 0.3),
        ("victory", "Victory", 0.5),
    ],
}

STYLE_VARIANTS: dict[str, list[tuple[str, str, float]]] = {
    "cartoon": [
        ("chibi", "Chibi", 0.3),
        ("anime", "Anime", 0.5),
        ("pixar", "Pixar Style", 0.4),
        ("disney", "Disney Style", 0.5),
        ("dreamworks", "DreamWorks", 0.5),
        ("semi_realistic", "Semi-Realistic", 0.6),
    ],
    "pixar": [
        ("disney", "Disney Style", 0.3),
        ("dreamworks", "DreamWorks", 0.3),
        ("chibi", "Chibi", 0.5),
        ("semi_realistic", "Semi-Realistic", 0.6),
    ],
    "anime": [
        ("chibi", "Chibi", 0.4),
        ("semi_realistic", "Semi-Realistic", 0.5),
        ("cartoon", "Cartoon", 0.4),
    ],
}

# Master variant library
VARIANT_LIBRARY: dict[str, dict[str, list[tuple[str, str, float]]]] = {
    "character": CHARACTER_VARIANTS,
    "camera": CAMERA_VARIANTS,
    "composition": COMPOSITION_VARIANTS,
    "lighting": LIGHTING_VARIANTS,
    "palette": COLOR_PALETTE_VARIANTS,
    "reward": REWARD_VARIANTS,
    "gameplay": GAMEPLAY_VARIANTS,
    "emotion": EMOTION_VARIANTS,
    "style": STYLE_VARIANTS,
}


# ═══════════════════════════════════════════════════════════
# Strategy Parameters
# ═══════════════════════════════════════════════════════════

STRATEGY_PARAMS = {
    "conservative": {"max_distance": 0.3, "min_variants": 1, "max_variants": 2},
    "balanced": {"max_distance": 0.5, "min_variants": 3, "max_variants": 5},
    "aggressive": {"max_distance": 0.7, "min_variants": 5, "max_variants": 8},
    "experimental": {"max_distance": 1.0, "min_variants": 6, "max_variants": 12},
}


# ═══════════════════════════════════════════════════════════
# Variation Engine
# ═══════════════════════════════════════════════════════════

class VariationEngine:
    """Generates creative variations for each dimension of a Winner DNA.

    Usage:
        engine = VariationEngine()
        dna = {"character": "witch", "camera": "45_degree", "lighting": "warm"}

        # Get all variations for one dimension
        variants = engine.vary_dimension("character", "witch", strategy="balanced")

        # Get all variations for an entire DNA
        all_variants = engine.vary_all(dna, strategy="aggressive")
    """

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed) if seed is not None else random.Random()

    def vary_dimension(
        self, dimension: str, value: str, strategy: str = "balanced",
    ) -> list[Variation]:
        """Generate variations for a single dimension value.

        Args:
            dimension: "character", "camera", "lighting", etc.
            value: the current value (e.g., "witch", "45_degree")
            strategy: conservative | balanced | aggressive | experimental

        Returns:
            List of Variation objects, sorted by distance (closest first).
        """
        library = VARIANT_LIBRARY.get(dimension, {})
        variants = library.get(value, [])

        if not variants:
            # Fallback: try to find partial matches
            for key in library:
                if key in value or value in key:
                    variants = library[key]
                    break

        if not variants:
            return [Variation(dimension=dimension, original=value,
                              variant=value, label=value.replace("_", " ").title(),
                              distance=0.0)]

        params = STRATEGY_PARAMS.get(strategy, STRATEGY_PARAMS["balanced"])
        max_dist = params["max_distance"]
        max_count = params["max_variants"]

        # Filter by max distance
        filtered = [(v, l, d) for v, l, d in variants if d <= max_dist]

        # Shuffle and pick
        self._rng.shuffle(filtered)
        selected = filtered[:max_count]

        # Sort by distance (closest first)
        selected.sort(key=lambda x: x[2])

        return [
            Variation(dimension=dimension, original=value, variant=v, label=l, distance=d)
            for v, l, d in selected
        ]

    def vary_all(
        self, dna: dict[str, Any], strategy: str = "balanced",
    ) -> dict[str, list[Variation]]:
        """Generate variations for all dimensions in a DNA.

        Args:
            dna: Winner DNA dict with dimensions as keys.
            strategy: variation strategy.

        Returns:
            Dict mapping dimension → list of Variations.
        """
        results: dict[str, list[Variation]] = {}
        for dim, value in dna.items():
            if dim in VARIANT_LIBRARY:
                results[dim] = self.vary_dimension(dim, str(value), strategy)
        return results

    def get_variant_count(self, dna: dict[str, Any], strategy: str = "balanced") -> int:
        """Estimate total number of unique prompt combinations."""
        all_variants = self.vary_all(dna, strategy)
        total = 1
        for variants in all_variants.values():
            if variants:
                total *= len(variants)
        return total