"""Phase 1.5: Creative Blueprint Reality Check.

Validates that CreativeBlueprintV2 / ProductionRules can actually
describe a real Facebook IAP game creative — not just abstract data
patterns. Bridging the gap between "data says this works" and
"here's what to generate."

No image generation. Only production requirement definition validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional

from .creative_causality_validator import (
    CreativeBlueprintV2, GameplayRequirement, VisualRequirement,
    ProductionRules, DNAImpactScore,
)


# ═══════════════════════════════════════════════════════════
# 1. CreativeGenerationSpec — the Phase 2 Input Contract
# ═══════════════════════════════════════════════════════════

@dataclass
class HookScene:
    """What the user sees that makes them click."""
    camera: str = ""            # top_down, isometric, close_up
    character: str = ""         # cute_witch, dragon, magical_girl
    position: str = ""          # center, left, right
    action: str = ""            # idle, casting_spell, evolving
    attention_reason: str = ""  # why user clicks: cute_character_transformation, etc.

    def is_complete(self) -> bool:
        return bool(self.character and self.position and self.attention_reason)

    def missing_fields(self) -> list[str]:
        missing = []
        if not self.character:
            missing.append("character")
        if not self.position:
            missing.append("position")
        if not self.attention_reason:
            missing.append("attention_reason")
        return missing

    def to_dict(self) -> dict[str, str]:
        return {k: v for k, v in asdict(self).items() if v}


@dataclass
class GameplaySequence:
    """What happens in the game during the ad."""
    interaction: str = ""       # drag_and_merge, tap_to_evolve, auto_merge
    state_before: str = ""      # small_magic_items, scattered_gems, baby_dragons
    state_after: str = ""       # dragon_castle, evolved_witch, legendary_item
    visual_change: str = ""     # large, medium, subtle
    transition: str = ""        # visible, instant, animated

    def is_complete(self) -> bool:
        return bool(self.interaction and self.state_before and
                    self.state_after and self.visual_change)

    def missing_fields(self) -> list[str]:
        missing = []
        if not self.interaction:
            missing.append("interaction")
        if not self.state_before:
            missing.append("state_before")
        if not self.state_after:
            missing.append("state_after")
        if not self.visual_change:
            missing.append("visual_change")
        return missing

    def to_dict(self) -> dict[str, str]:
        return {k: v for k, v in asdict(self).items() if v}


@dataclass
class RewardMoment:
    """The payoff the user sees at the end."""
    reward_object: str = ""     # dragon, evolved_witch, legendary_castle
    reward_action: str = ""     # evolution, transformation, level_up
    reward_emotion: str = ""    # surprise, satisfaction, excitement

    def is_complete(self) -> bool:
        return bool(self.reward_object and self.reward_action and self.reward_emotion)

    def missing_fields(self) -> list[str]:
        missing = []
        if not self.reward_object:
            missing.append("reward_object")
        if not self.reward_action:
            missing.append("reward_action")
        if not self.reward_emotion:
            missing.append("reward_emotion")
        return missing

    def to_dict(self) -> dict[str, str]:
        return {k: v for k, v in asdict(self).items() if v}


@dataclass
class VisualConstraints:
    """Visual style constraints for the generated creative."""
    theme: str = ""             # purple_magic, dark_fantasy, bright_casual
    composition: str = ""       # center, top_heavy, balanced
    color_palette: str = ""     # purple, blue_cool, warm_golden
    lighting: str = ""          # magical_glow, natural, dramatic

    def is_complete(self) -> bool:
        return bool(self.theme and self.composition and self.color_palette)

    def missing_fields(self) -> list[str]:
        missing = []
        if not self.theme:
            missing.append("theme")
        if not self.composition:
            missing.append("composition")
        if not self.color_palette:
            missing.append("color_palette")
        return missing

    def to_dict(self) -> dict[str, str]:
        return {k: v for k, v in asdict(self).items() if v}


@dataclass
class CreativeGenerationSpec:
    """The ONLY input Phase 2 AI Creative Generator should accept.

    This is a concrete, actionable specification — not abstract booleans.
    """
    source_pattern: str = ""
    confidence: float = 0.0
    hook_scene: HookScene = field(default_factory=HookScene)
    gameplay_sequence: GameplaySequence = field(default_factory=GameplaySequence)
    reward_moment: RewardMoment = field(default_factory=RewardMoment)
    visual_constraints: VisualConstraints = field(default_factory=VisualConstraints)
    format: str = "1080x1080"

    def is_complete(self) -> bool:
        return (self.hook_scene.is_complete() and
                self.gameplay_sequence.is_complete() and
                self.reward_moment.is_complete() and
                self.visual_constraints.is_complete())

    def missing_fields(self) -> dict[str, list[str]]:
        missing = {}
        if not self.hook_scene.is_complete():
            missing["hook_scene"] = self.hook_scene.missing_fields()
        if not self.gameplay_sequence.is_complete():
            missing["gameplay_sequence"] = self.gameplay_sequence.missing_fields()
        if not self.reward_moment.is_complete():
            missing["reward_moment"] = self.reward_moment.missing_fields()
        if not self.visual_constraints.is_complete():
            missing["visual_constraints"] = self.visual_constraints.missing_fields()
        return missing

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source_pattern,
            "confidence": self.confidence,
            "scene": self.hook_scene.to_dict(),
            "gameplay": self.gameplay_sequence.to_dict(),
            "reward": self.reward_moment.to_dict(),
            "visual": self.visual_constraints.to_dict(),
            "format": self.format,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CreativeGenerationSpec":
        """Reconstruct from a JSON dict (e.g., generation_specs.json)."""
        scene = data.get("scene", {})
        gameplay = data.get("gameplay", {})
        reward = data.get("reward", {})
        visual = data.get("visual", {})

        return cls(
            source_pattern=data.get("source", ""),
            confidence=data.get("confidence", 0.0),
            hook_scene=HookScene(
                camera=scene.get("camera", ""),
                character=scene.get("character", ""),
                position=scene.get("position", ""),
                action=scene.get("action", ""),
                attention_reason=scene.get("attention_reason", ""),
            ),
            gameplay_sequence=GameplaySequence(
                interaction=gameplay.get("interaction", ""),
                state_before=gameplay.get("state_before", ""),
                state_after=gameplay.get("state_after", ""),
                visual_change=gameplay.get("visual_change", ""),
                transition=gameplay.get("transition", ""),
            ),
            reward_moment=RewardMoment(
                reward_object=reward.get("reward_object", ""),
                reward_action=reward.get("reward_action", ""),
                reward_emotion=reward.get("reward_emotion", ""),
            ),
            visual_constraints=VisualConstraints(
                theme=visual.get("theme", ""),
                composition=visual.get("composition", ""),
                color_palette=visual.get("color_palette", ""),
                lighting=visual.get("lighting", ""),
            ),
            format=data.get("format", "1080x1080"),
        )

    def to_generation_prompt(self) -> str:
        """Generate a human-readable prompt for the AI Creative Generator."""
        parts = [
            f"Generate a Merge Witches IAP game ad creative:",
            f"",
            f"Scene:",
            f"  - Camera: {self.hook_scene.camera}",
            f"  - Character: {self.hook_scene.character} at {self.hook_scene.position}",
            f"  - Reason user clicks: {self.hook_scene.attention_reason}",
            f"",
            f"Gameplay:",
            f"  - Action: {self.gameplay_sequence.interaction}",
            f"  - Before: {self.gameplay_sequence.state_before}",
            f"  - After: {self.gameplay_sequence.state_after}",
            f"  - Visual change: {self.gameplay_sequence.visual_change}",
            f"  - Transition: {self.gameplay_sequence.transition}",
            f"",
            f"Reward:",
            f"  - Object: {self.reward_moment.reward_object}",
            f"  - Action: {self.reward_moment.reward_action}",
            f"  - Emotion: {self.reward_moment.reward_emotion}",
            f"",
            f"Visual:",
            f"  - Theme: {self.visual_constraints.theme}",
            f"  - Composition: {self.visual_constraints.composition}",
            f"  - Color: {self.visual_constraints.color_palette}",
            f"  - Lighting: {self.visual_constraints.lighting}",
            f"",
            f"Format: {self.format}",
            f"",
            f"Source: {self.source_pattern} (confidence {self.confidence:.2f})",
        ]
        return "\n".join(parts)


# ═══════════════════════════════════════════════════════════
# 2. CreativeBlueprintValidator
# ═══════════════════════════════════════════════════════════

@dataclass
class BlueprintValidationResult:
    """Validation result for a single blueprint/spec."""
    source_pattern: str = ""
    is_ready: bool = False
    hook_complete: bool = False
    gameplay_complete: bool = False
    reward_complete: bool = False
    visual_complete: bool = False
    missing_fields: dict[str, list[str]] = field(default_factory=dict)
    score: int = 0  # 0-4, one point per complete section


class CreativeBlueprintValidator:
    """Validates that blueprints are complete enough for generation.

    A blueprint is "ready" when all 4 sections are complete:
    - Hook: character + position + attention_reason
    - Gameplay: interaction + state_before + state_after + visual_change
    - Reward: object + action + emotion
    - Visual: theme + composition + color_palette
    """

    def validate(self, spec: CreativeGenerationSpec) -> BlueprintValidationResult:
        hook_ok = spec.hook_scene.is_complete()
        gameplay_ok = spec.gameplay_sequence.is_complete()
        reward_ok = spec.reward_moment.is_complete()
        visual_ok = spec.visual_constraints.is_complete()

        score = sum([hook_ok, gameplay_ok, reward_ok, visual_ok])

        return BlueprintValidationResult(
            source_pattern=spec.source_pattern,
            is_ready=(score == 4),
            hook_complete=hook_ok,
            gameplay_complete=gameplay_ok,
            reward_complete=reward_ok,
            visual_complete=visual_ok,
            missing_fields=spec.missing_fields(),
            score=score,
        )

    def validate_all(self, specs: list[CreativeGenerationSpec]) -> list[BlueprintValidationResult]:
        return [self.validate(s) for s in specs]

    def summary(self, results: list[BlueprintValidationResult]) -> dict[str, Any]:
        ready = [r for r in results if r.is_ready]
        not_ready = [r for r in results if not r.is_ready]

        missing_gameplay = [r for r in results if not r.gameplay_complete]
        missing_reward = [r for r in results if not r.reward_complete]
        missing_hook = [r for r in results if not r.hook_complete]
        missing_visual = [r for r in results if not r.visual_complete]

        return {
            "total": len(results),
            "ready_for_generation": len(ready),
            "not_ready": len(not_ready),
            "missing_gameplay": len(missing_gameplay),
            "missing_reward": len(missing_reward),
            "missing_hook": len(missing_hook),
            "missing_visual": len(missing_visual),
            "ready_patterns": [r.source_pattern for r in ready],
            "incomplete_patterns": [
                {"pattern": r.source_pattern, "score": r.score, "missing": r.missing_fields}
                for r in not_ready
            ],
        }


# ═══════════════════════════════════════════════════════════
# 3. Blueprint Template System
# ═══════════════════════════════════════════════════════════

# Knowledge base: what Merge Witches actually IS
# This is the bridge between abstract rules and concrete generation specs.

MERGE_WITCHES_KNOWLEDGE = {
    "game": "Merge Witches (Evolution Merge)",
    "genre": "merge_puzzle",
    "core_loop": "merge_items → evolve_witches → unlock_dragons → build_castle",
    "characters": ["cute_witch", "dragon", "magical_girl", "fairy"],
    "items": ["magic_gems", "dragon_eggs", "spell_books", "potion_bottles", "magic_plants"],
    "merge_results": ["dragon_castle", "evolved_witch", "legendary_dragon", "magic_castle"],
    "themes": {
        "purple": "purple_magic",
        "blue_cool": "mystical_blue",
        "warm_golden": "golden_light",
        "green": "enchanted_forest",
        "warm_red": "fire_magic",
    },
}


# Hook → Scene templates
HOOK_SCENE_TEMPLATES: dict[str, dict[str, Any]] = {
    "character_showcase": {
        "camera": "close_up",
        "character": "cute_witch",
        "position": "center",
        "action": "evolving",
        "attention_reason": "cute_character_transformation",
    },
    "merge_upgrade": {
        "camera": "top_down",
        "character": "cute_witch",
        "position": "center",
        "action": "casting_spell",
        "attention_reason": "satisfying_merge_chain",
    },
    "general_showcase": {
        "camera": "isometric",
        "character": "cute_witch",
        "position": "center",
        "action": "idle",
        "attention_reason": "beautiful_game_world",
    },
    "evolution": {
        "camera": "close_up",
        "character": "dragon",
        "position": "center",
        "action": "evolving",
        "attention_reason": "dragon_transformation_reveal",
    },
}


# Composition → Gameplay modifiers
COMPOSITION_GAMEPLAY: dict[str, dict[str, str]] = {
    "center": {
        "interaction": "drag_and_merge",
        "state_before": "small_magic_items",
        "state_after": "dragon_castle",
        "visual_change": "large",
        "transition": "visible",
    },
    "top": {
        "interaction": "tap_to_evolve",
        "state_before": "scattered_gems",
        "state_after": "evolved_witch",
        "visual_change": "medium",
        "transition": "animated",
    },
    "balanced": {
        "interaction": "auto_merge",
        "state_before": "baby_dragons",
        "state_after": "legendary_dragon",
        "visual_change": "large",
        "transition": "visible",
    },
    "bottom": {
        "interaction": "drag_and_merge",
        "state_before": "potion_bottles",
        "state_after": "magic_castle",
        "visual_change": "medium",
        "transition": "instant",
    },
}


# Color → Reward modifiers
COLOR_REWARD: dict[str, dict[str, str]] = {
    "purple": {
        "reward_object": "dragon",
        "reward_action": "evolution",
        "reward_emotion": "surprise",
    },
    "blue_cool": {
        "reward_object": "evolved_witch",
        "reward_action": "transformation",
        "reward_emotion": "satisfaction",
    },
    "warm_golden": {
        "reward_object": "legendary_dragon",
        "reward_action": "level_up",
        "reward_emotion": "excitement",
    },
    "green": {
        "reward_object": "magic_castle",
        "reward_action": "unlock",
        "reward_emotion": "satisfaction",
    },
    "warm_red": {
        "reward_object": "fire_dragon",
        "reward_action": "evolution",
        "reward_emotion": "excitement",
    },
}


# ═══════════════════════════════════════════════════════════
# 4. Production Rule → GenerationSpec Builder
# ═══════════════════════════════════════════════════════════

class GenerationSpecBuilder:
    """Build CreativeGenerationSpec from ProductionRules.

    Converts: RULE_001 (color=purple) + RULE_002 (composition=center) + RULE_003 (hook=character_showcase)
    Into:     CreativeGenerationSpec with concrete scene/gameplay/reward/visual.

    Uses knowledge base templates to fill in the gaps between
    "data says this works" and "here's what to generate."
    """

    def __init__(self) -> None:
        self._hook_templates = HOOK_SCENE_TEMPLATES
        self._gameplay_templates = COMPOSITION_GAMEPLAY
        self._reward_templates = COLOR_REWARD
        self._themes = MERGE_WITCHES_KNOWLEDGE["themes"]

    def build(self, rules: ProductionRules) -> list[CreativeGenerationSpec]:
        """Build generation specs from validated production rules."""
        specs = []

        # Extract rules by dimension
        hook_rule = None
        composition_rule = None
        color_rule = None

        for r in rules.rules:
            if r["decision"] != "GENERATE":
                continue
            if r["dimension"] == "hook":
                hook_rule = r
            elif r["dimension"] == "composition":
                composition_rule = r
            elif r["dimension"] == "color":
                color_rule = r

        if not hook_rule:
            return specs

        # Build primary spec: hook + composition + color
        if composition_rule and color_rule:
            specs.append(self._build_spec(
                hook_rule, composition_rule, color_rule,
                pattern_id=f"{hook_rule['value']}_{composition_rule['value']}_{color_rule['value']}",
            ))

        # Build fallback: hook + composition (no color)
        if composition_rule:
            specs.append(self._build_spec(
                hook_rule, composition_rule, None,
                pattern_id=f"{hook_rule['value']}_{composition_rule['value']}",
            ))

        # Build fallback: hook + color (no composition)
        if color_rule:
            specs.append(self._build_spec(
                hook_rule, None, color_rule,
                pattern_id=f"{hook_rule['value']}_{color_rule['value']}",
            ))

        # Build minimal: hook only
        specs.append(self._build_spec(
            hook_rule, None, None,
            pattern_id=hook_rule["value"],
        ))

        return specs

    def _build_spec(self, hook_rule: dict, composition_rule: Optional[dict],
                    color_rule: Optional[dict], pattern_id: str) -> CreativeGenerationSpec:
        # Confidence: average of contributing rules
        confidences = [hook_rule["confidence"]]
        if composition_rule:
            confidences.append(composition_rule["confidence"])
        if color_rule:
            confidences.append(color_rule["confidence"])
        confidence = sum(confidences) / len(confidences)

        # Hook scene
        hook_template = self._hook_templates.get(hook_rule["value"], {})
        hook_scene = HookScene(
            camera=hook_template.get("camera", "close_up"),
            character=hook_template.get("character", "cute_witch"),
            position=hook_template.get("position", "center"),
            action=hook_template.get("action", "idle"),
            attention_reason=hook_template.get("attention_reason", ""),
        )

        # Gameplay sequence
        comp_value = composition_rule["value"] if composition_rule else "center"
        gameplay_template = self._gameplay_templates.get(comp_value, {})
        gameplay_seq = GameplaySequence(
            interaction=gameplay_template.get("interaction", "drag_and_merge"),
            state_before=gameplay_template.get("state_before", "small_magic_items"),
            state_after=gameplay_template.get("state_after", "dragon_castle"),
            visual_change=gameplay_template.get("visual_change", "large"),
            transition=gameplay_template.get("transition", "visible"),
        )

        # Reward moment
        color_value = color_rule["value"] if color_rule else "purple"
        reward_template = self._reward_templates.get(color_value, {})
        reward_moment = RewardMoment(
            reward_object=reward_template.get("reward_object", "dragon"),
            reward_action=reward_template.get("reward_action", "evolution"),
            reward_emotion=reward_template.get("reward_emotion", "surprise"),
        )

        # Visual constraints
        theme = self._themes.get(color_value, "purple_magic")
        visual_constraints = VisualConstraints(
            theme=theme,
            composition=comp_value,
            color_palette=color_value,
            lighting="magical_glow" if color_value == "purple" else "natural",
        )

        return CreativeGenerationSpec(
            source_pattern=pattern_id,
            confidence=round(confidence, 3),
            hook_scene=hook_scene,
            gameplay_sequence=gameplay_seq,
            reward_moment=reward_moment,
            visual_constraints=visual_constraints,
            format="1080x1080",
        )


# ═══════════════════════════════════════════════════════════
# 5. Blueprint Completeness Report
# ═══════════════════════════════════════════════════════════

@dataclass
class BlueprintCompletenessReport:
    """Full Phase 1.5 validation report."""
    total_winner_patterns: int = 0
    specs_generated: int = 0
    ready_for_generation: int = 0
    missing_gameplay: int = 0
    missing_reward: int = 0
    missing_hook: int = 0
    missing_visual: int = 0
    validation_results: list[BlueprintValidationResult] = field(default_factory=list)
    ready_specs: list[CreativeGenerationSpec] = field(default_factory=list)
    generation_prompts: list[str] = field(default_factory=list)

    def print_report(self) -> str:
        lines = []
        lines.append("=" * 65)
        lines.append("  PHASE 1.5: Creative Blueprint Reality Check")
        lines.append("  Merge Witches — Creative Factory V2")
        lines.append("=" * 65)

        lines.append("")
        lines.append("Blueprint Validation")
        lines.append("")
        lines.append(f"  Total winner patterns:    {self.total_winner_patterns}")
        lines.append(f"  Generation specs built:    {self.specs_generated}")
        lines.append(f"  Ready for generation:      {self.ready_for_generation}")
        lines.append(f"  Missing gameplay info:     {self.missing_gameplay}")
        lines.append(f"  Missing reward:            {self.missing_reward}")
        lines.append(f"  Missing hook:              {self.missing_hook}")
        lines.append(f"  Missing visual:            {self.missing_visual}")

        if self.ready_specs:
            lines.append("")
            lines.append(f"  Ready Specs ({len(self.ready_specs)}):")
            for i, spec in enumerate(self.ready_specs):
                lines.append(f"    [{i+1}] {spec.source_pattern} (conf={spec.confidence:.2f})")
                lines.append(f"        Hook:  {spec.hook_scene.character} @ {spec.hook_scene.position} — {spec.hook_scene.attention_reason}")
                lines.append(f"        Game:  {spec.gameplay_sequence.interaction}: {spec.gameplay_sequence.state_before} → {spec.gameplay_sequence.state_after}")
                lines.append(f"        Reward:{spec.reward_moment.reward_object} {spec.reward_moment.reward_action} ({spec.reward_moment.reward_emotion})")
                lines.append(f"        Visual:{spec.visual_constraints.theme} / {spec.visual_constraints.composition} / {spec.visual_constraints.color_palette}")

        if any(not r.is_ready for r in self.validation_results):
            lines.append("")
            lines.append("  Incomplete Specs:")
            for r in self.validation_results:
                if not r.is_ready:
                    lines.append(f"    [{r.score}/4] {r.source_pattern}")
                    for section, fields in r.missing_fields.items():
                        lines.append(f"        {section}: missing {fields}")

        lines.append("")
        lines.append("=" * 65)
        lines.append("  PHASE 1.5 COMPLETE — Production Interface Validated")
        lines.append("=" * 65)
        lines.append(f"  Ready specs:          {self.ready_for_generation}")
        lines.append(f"  Generation prompts:   {len(self.generation_prompts)}")
        lines.append(f"")
        lines.append(f"  Next: Phase 2 — Lovart AI Creative Generator MVP")
        lines.append(f"  Input: CreativeGenerationSpec (NOT raw images)")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": "1.5",
            "total_winner_patterns": self.total_winner_patterns,
            "specs_generated": self.specs_generated,
            "ready_for_generation": self.ready_for_generation,
            "missing_gameplay": self.missing_gameplay,
            "missing_reward": self.missing_reward,
            "missing_hook": self.missing_hook,
            "missing_visual": self.missing_visual,
            "validation_results": [
                {
                    "pattern": r.source_pattern,
                    "is_ready": r.is_ready,
                    "score": r.score,
                    "hook_complete": r.hook_complete,
                    "gameplay_complete": r.gameplay_complete,
                    "reward_complete": r.reward_complete,
                    "visual_complete": r.visual_complete,
                    "missing_fields": r.missing_fields,
                }
                for r in self.validation_results
            ],
            "ready_specs": [s.to_dict() for s in self.ready_specs],
            "generation_prompts": self.generation_prompts,
        }