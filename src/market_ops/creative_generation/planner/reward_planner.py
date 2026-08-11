"""Phase 3.0: Reward Planner — reward placement, object, and presentation.

Decides what reward to show and where to place it in the composition.
"""

from __future__ import annotations

from ..models.prompt_component import PromptComponent


REWARD_TOKENS: dict[str, dict[str, str]] = {
    "baby_dragon": {
        "object": "cute baby dragon",
        "placement": "held in character's arms or beside them",
        "presentation": "glowing with magical aura, sparkling scales",
        "description": "Baby Dragon — cute creature reward",
    },
    "blue_dragon": {
        "object": "blue dragon",
        "placement": "flying beside character",
        "presentation": "cyan glow, ice crystals floating around",
        "description": "Blue Dragon — ice creature reward",
    },
    "fire_dragon": {
        "object": "fire dragon",
        "placement": "perched on character's shoulder",
        "presentation": "flame aura, ember particles, warm glow",
        "description": "Fire Dragon — flame creature reward",
    },
    "ice_dragon": {
        "object": "ice dragon",
        "placement": "circling above character",
        "presentation": "frost aura, snowflake particles, cool blue glow",
        "description": "Ice Dragon — frost creature reward",
    },
    "golden_dragon": {
        "object": "golden dragon",
        "placement": "floating majestically beside character",
        "presentation": "golden glow, treasure sparkles, royal aura",
        "description": "Golden Dragon — legendary reward",
    },
    "crystal_dragon": {
        "object": "crystal dragon",
        "placement": "emerging from crystal formation",
        "presentation": "prismatic glow, rainbow refractions, crystal shards",
        "description": "Crystal Dragon — prismatic creature reward",
    },
    "treasure": {
        "object": "treasure chest overflowing with gold",
        "placement": "foreground, at character's feet",
        "presentation": "golden glow, coin sparkles, gem reflections",
        "description": "Treasure Chest — wealth reward",
    },
    "gold_coins": {
        "object": "pile of gold coins and gems",
        "placement": "spilling across foreground",
        "presentation": "golden shimmer, coin reflections, wealth",
        "description": "Gold Coins — currency reward",
    },
    "gem_stones": {
        "object": "glowing gem stones",
        "placement": "floating in a circle around character",
        "presentation": "multi-colored glow, crystal refractions",
        "description": "Gem Stones — precious gems reward",
    },
    "magic_chest": {
        "object": "magical treasure chest",
        "placement": "center foreground, opening dramatically",
        "presentation": "magical light bursting from inside, particle effects",
        "description": "Magic Chest — mysterious treasure",
    },
    "castle": {
        "object": "magical castle",
        "placement": "background, revealed through mist",
        "presentation": "glowing towers, magical aura, grand scale",
        "description": "Castle — grand structure reward",
    },
    "floating_castle": {
        "object": "floating castle in the sky",
        "placement": "upper background, among clouds",
        "presentation": "clouds parting to reveal, golden light",
        "description": "Floating Castle — sky kingdom reward",
    },
    "crystal_castle": {
        "object": "crystal castle",
        "placement": "background, prismatic structure",
        "presentation": "rainbow refractions, crystal spires, magical glow",
        "description": "Crystal Castle — prismatic kingdom reward",
    },
    "evolution": {
        "object": "evolution transformation",
        "placement": "center stage, dramatic reveal",
        "presentation": "transformation glow, power aura, dramatic reveal",
        "description": "Evolution — character transformation reward",
    },
    "transformation": {
        "object": "magical transformation effect",
        "placement": "enveloping character",
        "presentation": "swirling energy, form change, dramatic reveal",
        "description": "Transformation — magical form change",
    },
    "level_up": {
        "object": "level up celebration",
        "placement": "surrounding character",
        "presentation": "level up glow, stat increase effects, celebration",
        "description": "Level Up — progression reward",
    },
    "unlock": {
        "object": "new character or item unlocked",
        "placement": "emerging from magical portal",
        "presentation": "portal glow, unlocking animation, reveal",
        "description": "Unlock — new content revealed",
    },
    "baby_phoenix": {
        "object": "baby phoenix",
        "placement": "perched on character's arm",
        "presentation": "flame plumage, rebirth glow, golden embers",
        "description": "Baby Phoenix — rebirth creature",
    },
    "baby_griffin": {
        "object": "baby griffin",
        "placement": "standing proudly beside character",
        "presentation": "golden feathers, lion cub body, majestic aura",
        "description": "Baby Griffin — mythical creature",
    },
}


class RewardPlanner:
    """Plans reward object and placement for a prompt."""

    def plan(self, reward: str, strategy: str = "balanced") -> PromptComponent:
        tokens = REWARD_TOKENS.get(reward, REWARD_TOKENS["baby_dragon"])
        return PromptComponent(
            dimension="reward",
            value=reward,
            label=tokens.get("description", reward),
            weight=0.9,
        )

    def get_tokens(self, reward: str) -> dict[str, str]:
        return REWARD_TOKENS.get(reward, REWARD_TOKENS["baby_dragon"])