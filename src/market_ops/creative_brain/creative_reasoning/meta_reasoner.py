"""V4.2 Meta Reasoner — cross-game knowledge transfer reasoning.

The highest-level reasoning layer. Answers:
  - Why is a certain game mechanic working?
  - What characteristics can transfer to other game types?
  - How to abstract winning patterns from one game to another?

This is KNOWLEDGE TRANSFER, not keyword matching.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import KnowledgeTransferModel


# Game type profiles — what creative DNA works for each game type
GAME_TYPE_PROFILES: dict[str, dict[str, Any]] = {
    "merge": {
        "name": "Merge Games",
        "core_mechanics": ["merge", "combine", "upgrade"],
        "key_hooks": ["collection", "transformation", "satisfying"],
        "key_rewards": ["dragon", "evolution", "treasure"],
        "key_characters": ["dragon", "witch", "knight"],
        "psychology": ["completion", "progression", "surprise"],
        "animation_style": "smooth_merge",
        "particle_effects": "sparkle",
    },
    "puzzle": {
        "name": "Puzzle Games",
        "core_mechanics": ["match", "sort", "solve"],
        "key_hooks": ["challenge", "fail", "surprise"],
        "key_rewards": ["gold", "treasure", "collection"],
        "key_characters": ["warrior", "ninja", "mage"],
        "psychology": ["achievement", "problem_solving", "curiosity"],
        "animation_style": "satisfying_pop",
        "particle_effects": "confetti",
    },
    "simulation": {
        "name": "Simulation Games",
        "core_mechanics": ["build", "manage", "grow"],
        "key_hooks": ["transformation", "collection", "satisfying"],
        "key_rewards": ["evolution", "collection", "gold"],
        "key_characters": ["princess", "robot", "fairy"],
        "psychology": ["ownership", "creativity", "nurturing"],
        "animation_style": "smooth_grow",
        "particle_effects": "gentle_glow",
    },
    "rpg": {
        "name": "RPG Games",
        "core_mechanics": ["fight", "level_up", "quest"],
        "key_hooks": ["challenge", "transformation", "collection"],
        "key_rewards": ["dragon", "evolution", "treasure"],
        "key_characters": ["warrior", "dragon", "mage"],
        "psychology": ["power", "progression", "mastery"],
        "animation_style": "epic_impact",
        "particle_effects": "explosion",
    },
    "idle": {
        "name": "Idle Games",
        "core_mechanics": ["auto_play", "accumulate", "prestige"],
        "key_hooks": ["collection", "satisfying", "challenge"],
        "key_rewards": ["gold", "evolution", "collection"],
        "key_characters": ["robot", "warrior", "dragon"],
        "psychology": ["progress", "optimization", "passive_reward"],
        "animation_style": "continuous_flow",
        "particle_effects": "cascade",
    },
    "category_sort": {
        "name": "Category Sort Games",
        "core_mechanics": ["sort", "organize", "categorize"],
        "key_hooks": ["satisfying", "collection", "challenge"],
        "key_rewards": ["collection", "gold", "treasure"],
        "key_characters": ["princess", "fairy", "witch"],
        "psychology": ["order", "completion", "satisfaction"],
        "animation_style": "smooth_sort",
        "particle_effects": "subtle_sparkle",
    },
    "goods_sort": {
        "name": "Goods Sort Games",
        "core_mechanics": ["sort", "organize", "match"],
        "key_hooks": ["satisfying", "collection", "challenge"],
        "key_rewards": ["gold", "collection", "treasure"],
        "key_characters": ["princess", "fairy", "robot"],
        "psychology": ["order", "completion", "satisfaction"],
        "animation_style": "smooth_sort",
        "particle_effects": "subtle_sparkle",
    },
}


@dataclass
class MetaAnalysis:
    """Result of meta-level reasoning about a creative or game."""
    game_type: str = ""
    core_psychology: list[str] = field(default_factory=list)
    transferable_elements: list[dict[str, Any]] = field(default_factory=list)
    transfer_plans: list[KnowledgeTransferModel] = field(default_factory=list)
    insights: list[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "game_type": self.game_type,
            "core_psychology": self.core_psychology,
            "transferable_elements": self.transferable_elements,
            "transfer_plans": [t.to_dict() for t in self.transfer_plans],
            "insights": self.insights,
            "summary": self.summary,
        }


class MetaReasoner:
    """Highest-level reasoning: cross-game knowledge transfer.

    Not "keyword matching" — this is about understanding WHY something works
    in one game type and HOW to transfer that insight to another game type.

    Example:
      "Sand puzzle" works because of satisfying hook + particles + feedback.
      → Transfer "satisfying" + "particles" to Merge, Category Sort, etc.
    """

    def __init__(self) -> None:
        self._profiles = GAME_TYPE_PROFILES

    def analyze_why(self, game_type: str,
                    success_factors: list[str] | None = None) -> MetaAnalysis:
        """Analyze WHY a game type or creative pattern works.

        Decomposes success into psychology, mechanics, animation, and feedback.
        """
        profile = self._profiles.get(game_type, {})
        if not profile:
            return MetaAnalysis(
                game_type=game_type,
                summary=f"No profile data for game type: {game_type}",
            )

        psychology = profile.get("psychology", [])
        mechanics = profile.get("core_mechanics", [])
        hooks = profile.get("key_hooks", [])
        rewards = profile.get("key_rewards", [])

        # Decompose what makes this work
        transferable = []
        for p in psychology:
            transferable.append({
                "element": "psychology",
                "value": p,
                "description": f"Psychological driver: {p}",
                "transferability": "high",
            })
        for m in mechanics:
            transferable.append({
                "element": "mechanic",
                "value": m,
                "description": f"Core mechanic: {m}",
                "transferability": "medium",
            })
        for h in hooks:
            transferable.append({
                "element": "hook",
                "value": h,
                "description": f"Engagement hook: {h}",
                "transferability": "high",
            })

        insights = [
            f"{profile.get('name', game_type)} works because of: "
            f"{', '.join(psychology[:3])}.",
            f"Key mechanics: {', '.join(mechanics[:3])}.",
            f"Effective hooks: {', '.join(hooks[:3])}.",
            f"Effective rewards: {', '.join(rewards[:3])}.",
        ]

        return MetaAnalysis(
            game_type=game_type,
            core_psychology=psychology,
            transferable_elements=transferable,
            insights=insights,
            summary=f"{profile.get('name', game_type)} success driven by "
                    f"{', '.join(psychology[:2])} psychology + "
                    f"{', '.join(mechanics[:2])} mechanics.",
        )

    def transfer_to(self, source_game: str,
                    target_game: str) -> KnowledgeTransferModel:
        """Generate a knowledge transfer plan from source to target game.

        Not "copy paste" — intelligently maps what can transfer and what needs adaptation.
        """
        source = self._profiles.get(source_game, {})
        target = self._profiles.get(target_game, {})

        if not source or not target:
            return KnowledgeTransferModel(
                transfer_id=f"{source_game}_to_{target_game}",
                source_game=source_game,
                target_game=target_game,
                transfer_score=0.0,
                expected_impact="Insufficient profile data for transfer analysis.",
            )

        transferable = []
        adaptation = []

        # Psychology: high transferability
        shared_psych = set(source.get("psychology", [])) & set(target.get("psychology", []))
        if shared_psych:
            transferable.append(f"Psychology: {', '.join(shared_psych)}")
        unique_psych = set(source.get("psychology", [])) - set(target.get("psychology", []))
        if unique_psych:
            adaptation.append(f"Psychology: adapt {', '.join(unique_psych)}")

        # Hooks: medium transferability
        shared_hooks = set(source.get("key_hooks", [])) & set(target.get("key_hooks", []))
        if shared_hooks:
            transferable.append(f"Hooks: {', '.join(shared_hooks)}")
        unique_hooks = set(source.get("key_hooks", [])) - set(target.get("key_hooks", []))
        if unique_hooks:
            adaptation.append(f"Hooks: adapt {', '.join(unique_hooks)}")

        # Rewards: medium transferability
        shared_rewards = set(source.get("key_rewards", [])) & set(target.get("key_rewards", []))
        if shared_rewards:
            transferable.append(f"Rewards: {', '.join(shared_rewards)}")

        # Characters: low transferability (game-specific)
        adaptation.append(
            f"Characters: replace {source.get('key_characters', [])[:3]} "
            f"with {target.get('key_characters', [])[:3]}"
        )

        # Animation: low transferability
        adaptation.append(
            f"Animation: adapt {source.get('animation_style', '')} "
            f"→ {target.get('animation_style', '')}"
        )

        # Particles: low transferability
        adaptation.append(
            f"Particles: adapt {source.get('particle_effects', '')} "
            f"→ {target.get('particle_effects', '')}"
        )

        # Compute transfer score
        total_dims = len(transferable) + len(adaptation)
        transfer_score = len(transferable) / max(total_dims, 1)

        # Expected impact
        if transfer_score >= 0.6:
            impact = "HIGH — many elements transfer directly. Expect strong performance."
        elif transfer_score >= 0.3:
            impact = "MEDIUM — some elements transfer, significant adaptation needed."
        else:
            impact = "LOW — fundamental differences between game types. High risk."

        return KnowledgeTransferModel(
            transfer_id=f"{source_game}_to_{target_game}",
            source_game=source_game,
            target_game=target_game,
            transferable_dimensions=transferable,
            adaptation_required=adaptation,
            transfer_score=transfer_score,
            expected_impact=impact,
            evidence=[
                f"Source: {source.get('name', source_game)}",
                f"Target: {target.get('name', target_game)}",
            ],
        )

    def transfer_to_all(self, source_game: str) -> list[KnowledgeTransferModel]:
        """Generate transfer plans to all other game types."""
        plans = []
        for target in self._profiles:
            if target != source_game:
                plans.append(self.transfer_to(source_game, target))
        plans.sort(key=lambda p: p.transfer_score, reverse=True)
        return plans

    def get_game_profile(self, game_type: str) -> dict[str, Any] | None:
        """Get a game type's creative profile."""
        return self._profiles.get(game_type)

    def register_game_type(self, game_type: str,
                           profile: dict[str, Any]) -> None:
        """Register a new game type profile."""
        self._profiles[game_type] = profile