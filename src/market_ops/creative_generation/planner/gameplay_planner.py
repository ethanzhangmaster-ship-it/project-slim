"""Phase 3.0: Gameplay Planner — shows what the player does.

For Merge games: drag, merge, upgrade, reward, explosion.
Produces dynamic gameplay moment descriptions, not static images.
"""

from __future__ import annotations

from ..models.prompt_component import PromptComponent


GAMEPLAY_TOKENS: dict[str, dict[str, str]] = {
    "merge": {
        "action": "drag and merge",
        "moment": "two items floating together, merging with magical energy",
        "before": "two separate glowing items",
        "after": "one combined superior item emerging",
        "effect": "magical fusion particles, energy swirl",
        "description": "Merge: combining items into something better",
    },
    "drag_merge": {
        "action": "player dragging item",
        "moment": "item being dragged across the board, merge target glowing",
        "before": "two identical items separated",
        "after": "upgraded item appearing with sparkle",
        "effect": "drag trail, target glow, anticipation",
        "description": "Drag Merge: player actively combining items",
    },
    "auto_merge": {
        "action": "automatic merge",
        "moment": "items automatically floating together, combining",
        "before": "items arranged on board",
        "after": "automatic combination with satisfying effect",
        "effect": "auto merge glow, chain reaction",
        "description": "Auto Merge: automatic combination",
    },
    "chain_merge": {
        "action": "chain reaction merge",
        "moment": "cascading chain of merges across the board",
        "before": "multiple merge-ready pairs",
        "after": "chain of upgraded items appearing",
        "effect": "domino effect, chain particles, combo text",
        "description": "Chain Merge: cascading combinations",
    },
    "combo_merge": {
        "action": "combo merge",
        "moment": "multiple merges happening simultaneously",
        "before": "board full of mergeable items",
        "after": "multiple upgraded items, combo score",
        "effect": "combo explosion, score popup, celebration",
        "description": "Combo Merge: multiple simultaneous merges",
    },
    "explosion_merge": {
        "action": "explosive merge",
        "moment": "dramatic explosion of merging energy",
        "before": "items charged with energy",
        "after": "epic upgraded item revealed",
        "effect": "explosion particles, screen shake, epic reveal",
        "description": "Explosion Merge: dramatic epic combination",
    },
    "evolution": {
        "action": "character evolution",
        "moment": "character transforming, evolving into stronger form",
        "before": "base form character",
        "after": "evolved powerful form",
        "effect": "evolution glow, transformation particles, power aura",
        "description": "Evolution: character transforming",
    },
    "staged_evolution": {
        "action": "staged evolution",
        "moment": "character going through evolution stages",
        "before": "level 1 form",
        "after": "level 3 ultimate form",
        "effect": "stage transitions, power upgrades, aura growth",
        "description": "Staged Evolution: multiple transformation stages",
    },
    "collection": {
        "action": "collecting items",
        "moment": "character discovering and collecting rare items",
        "before": "empty collection slots",
        "after": "filled collection with rewards",
        "effect": "collection glow, discovery sparkle, reward popup",
        "description": "Collection: discovering rare items",
    },
    "puzzle": {
        "action": "solving puzzle",
        "moment": "character solving a magical puzzle or mechanism",
        "before": "unsolved puzzle state",
        "after": "puzzle solved, treasure revealed",
        "effect": "solution glow, unlocking animation, reward reveal",
        "description": "Puzzle: solving magical challenges",
    },
    "match_three": {
        "action": "match three gems",
        "moment": "three matching gems aligning, clearing",
        "before": "gems on board",
        "after": "matched gems cleared, new gems fall",
        "effect": "match glow, clear animation, cascade",
        "description": "Match Three: classic gem matching",
    },
}


class GameplayPlanner:
    """Plans gameplay moment description for a prompt."""

    def plan(self, gameplay: str, strategy: str = "balanced") -> PromptComponent:
        tokens = GAMEPLAY_TOKENS.get(gameplay, GAMEPLAY_TOKENS["merge"])
        return PromptComponent(
            dimension="gameplay",
            value=gameplay,
            label=tokens.get("description", gameplay),
            weight=0.9,
        )

    def get_tokens(self, gameplay: str) -> dict[str, str]:
        return GAMEPLAY_TOKENS.get(gameplay, GAMEPLAY_TOKENS["merge"])