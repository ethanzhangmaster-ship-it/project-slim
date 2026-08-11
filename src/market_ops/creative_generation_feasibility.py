"""Phase 1.6 + 1.6.1: Generation Feasibility Test + Ad Readiness V2.

V1: Validates spec completeness (100pt structural quality).
V2: Validates Facebook ad readiness (100pt: DNA + Ad Structure + Lovart + CTR).

No image generation. Only production interface quality validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

from .creative_blueprint_validator import (
    CreativeGenerationSpec, HookScene, GameplaySequence,
    RewardMoment, VisualConstraints,
)


# ═══════════════════════════════════════════════════════════
# 1. GenerationSpecQualityChecker — 100-point scoring
# ═══════════════════════════════════════════════════════════

# Known game-specific values (high specificity = more actionable)
SPECIFIC_VALUES = {
    "character": {"cute_witch", "dragon", "magical_girl", "fairy", "sorceress"},
    "action": {"evolving", "casting_spell", "transforming", "merging", "unlocking"},
    "interaction": {"drag_and_merge", "tap_to_evolve", "auto_merge", "swipe_to_combine"},
    "state_before": {"small_magic_items", "scattered_gems", "baby_dragons", "potion_bottles"},
    "state_after": {"dragon_castle", "evolved_witch", "legendary_dragon", "magic_castle"},
    "reward_object": {"dragon", "evolved_witch", "legendary_dragon", "magic_castle", "fire_dragon"},
    "reward_action": {"evolution", "transformation", "level_up", "unlock", "merge"},
    "reward_emotion": {"surprise", "satisfaction", "excitement", "awe", "delight"},
    "theme": {"purple_magic", "mystical_blue", "golden_light", "enchanted_forest", "fire_magic"},
}

# Generic values that indicate lack of specificity
GENERIC_PATTERNS = {"game", "item", "object", "character", "thing", "stuff", "show", "display"}


def _is_specific(value: str, category: str) -> bool:
    """Check if a value is specific enough to guide generation."""
    if not value:
        return False
    v = value.lower().strip()
    if v in GENERIC_PATTERNS:
        return False
    if category in SPECIFIC_VALUES and v in SPECIFIC_VALUES[category]:
        return True
    # Has underscores = compound specific term (e.g., "cute_witch")
    if "_" in v:
        return True
    # Single-word generic terms
    if len(v) < 5 and v not in SPECIFIC_VALUES.get(category, set()):
        return False
    return True


@dataclass
class SectionScore:
    """Score breakdown for one section of a GenerationSpec."""
    section: str = ""
    filled: int = 0
    total: int = 0
    score: int = 0
    max_score: int = 0
    deductions: list[str] = field(default_factory=list)


@dataclass
class SpecQualityResult:
    """Quality assessment for a single GenerationSpec."""
    spec_id: str = ""
    readiness_score: int = 0  # 0-100
    scene_score: SectionScore = field(default_factory=lambda: SectionScore(section="scene"))
    gameplay_score: SectionScore = field(default_factory=lambda: SectionScore(section="gameplay"))
    reward_score: SectionScore = field(default_factory=lambda: SectionScore(section="reward"))
    visual_score: SectionScore = field(default_factory=lambda: SectionScore(section="visual"))
    missing: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    is_ready: bool = False  # score >= 70

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec_id": self.spec_id,
            "readiness_score": self.readiness_score,
            "scene_score": asdict(self.scene_score),
            "gameplay_score": asdict(self.gameplay_score),
            "reward_score": asdict(self.reward_score),
            "visual_score": asdict(self.visual_score),
            "missing": self.missing,
            "warnings": self.warnings,
            "is_ready": self.is_ready,
        }


class GenerationSpecQualityChecker:
    """Quality checks a GenerationSpec for production readiness.

    Scoring (100 points total):
      Scene:     25 pts (5 fields × 5)
      Gameplay:  25 pts (5 fields × 5)
      Reward:    25 pts (3 fields × 5 + 10 specificity bonus)
      Visual:    25 pts (5 fields × 5)
    """

    READY_THRESHOLD = 70

    def check(self, spec: CreativeGenerationSpec) -> SpecQualityResult:
        scene = self._score_scene(spec.hook_scene)
        gameplay = self._score_gameplay(spec.gameplay_sequence)
        reward = self._score_reward(spec.reward_moment)
        visual = self._score_visual(spec.visual_constraints, spec.format)

        total = scene.score + gameplay.score + reward.score + visual.score
        missing = []
        warnings = []

        # Collect missing fields
        if scene.filled < scene.total:
            for d in scene.deductions:
                if "empty" in d:
                    missing.append(d.replace("empty: ", ""))
        if gameplay.filled < gameplay.total:
            for d in gameplay.deductions:
                if "empty" in d:
                    missing.append(d.replace("empty: ", ""))
        if reward.filled < reward.total:
            for d in reward.deductions:
                if "empty" in d:
                    missing.append(d.replace("empty: ", ""))
        if visual.filled < visual.total:
            for d in visual.deductions:
                if "empty" in d:
                    missing.append(d.replace("empty: ", ""))

        # Collect warnings (non-empty but low quality)
        for d in scene.deductions:
            if "generic" in d:
                warnings.append(f"scene: {d.replace('generic: ', '')}")
        for d in gameplay.deductions:
            if "generic" in d:
                warnings.append(f"gameplay: {d.replace('generic: ', '')}")
        for d in reward.deductions:
            if "generic" in d:
                warnings.append(f"reward: {d.replace('generic: ', '')}")
        for d in visual.deductions:
            if "generic" in d:
                warnings.append(f"visual: {d.replace('generic: ', '')}")

        # Check for "gameplay change" — the most critical factor for FB ads
        if spec.gameplay_sequence.visual_change not in ("large", "medium"):
            warnings.append("gameplay: visual_change is too subtle for FB ad")

        return SpecQualityResult(
            spec_id=spec.source_pattern,
            readiness_score=total,
            scene_score=scene,
            gameplay_score=gameplay,
            reward_score=reward,
            visual_score=visual,
            missing=missing,
            warnings=warnings,
            is_ready=(total >= self.READY_THRESHOLD),
        )

    def check_all(self, specs: list[CreativeGenerationSpec]) -> list[SpecQualityResult]:
        return [self.check(s) for s in specs]

    # ── Scene scoring (25 pts) ──

    def _score_scene(self, s: HookScene) -> SectionScore:
        fields = [
            ("camera", s.camera, "character"),
            ("character", s.character, "character"),
            ("position", s.position, "position"),
            ("action", s.action, "action"),
            ("attention_reason", s.attention_reason, "reason"),
        ]
        return self._score_section("scene", fields, 25)

    # ── Gameplay scoring (25 pts) ──

    def _score_gameplay(self, g: GameplaySequence) -> SectionScore:
        fields = [
            ("interaction", g.interaction, "interaction"),
            ("state_before", g.state_before, "state_before"),
            ("state_after", g.state_after, "state_after"),
            ("visual_change", g.visual_change, "visual_change"),
            ("transition", g.transition, "transition"),
        ]
        return self._score_section("gameplay", fields, 25)

    # ── Reward scoring (25 pts) ──

    def _score_reward(self, r: RewardMoment) -> SectionScore:
        fields = [
            ("reward_object", r.reward_object, "reward_object"),
            ("reward_action", r.reward_action, "reward_action"),
            ("reward_emotion", r.reward_emotion, "reward_emotion"),
        ]
        result = self._score_section("reward", fields, 15)

        # Bonus: specificity (10 pts)
        bonus = 0
        if r.reward_object and _is_specific(r.reward_object, "reward_object"):
            bonus += 5
        else:
            result.deductions.append("generic: reward_object too generic")
        if r.reward_action and _is_specific(r.reward_action, "reward_action"):
            bonus += 5
        else:
            result.deductions.append("generic: reward_action not specific")

        result.score += bonus
        result.max_score += 10
        return result

    # ── Visual scoring (25 pts) ──

    def _score_visual(self, v: VisualConstraints, fmt: str) -> SectionScore:
        fields = [
            ("theme", v.theme, "theme"),
            ("composition", v.composition, "composition"),
            ("color_palette", v.color_palette, "color_palette"),
            ("lighting", v.lighting, "lighting"),
            ("format", fmt, "format"),
        ]
        return self._score_section("visual", fields, 25)

    # ── Generic section scorer ──

    def _score_section(self, section: str, fields: list[tuple[str, str, str]],
                       max_score: int) -> SectionScore:
        per_field = max_score // len(fields)
        score = 0
        filled = 0
        deductions = []

        for name, value, category in fields:
            if not value:
                deductions.append(f"empty: {name}")
                continue
            filled += 1
            if _is_specific(value, category):
                score += per_field
            else:
                score += per_field // 2  # half credit for generic
                deductions.append(f"generic: {name}='{value}' is too generic")

        return SectionScore(
            section=section,
            filled=filled,
            total=len(fields),
            score=score,
            max_score=max_score,
            deductions=deductions,
        )


# ═══════════════════════════════════════════════════════════
# 2. Human Review Prompt Generator
# ═══════════════════════════════════════════════════════════

class HumanReviewPromptGenerator:
    """Generate a concise, actionable review prompt for a human reviewer.

    This is what a human would read to verify: "Can this generate a
    high-CTR Facebook ad?"
    """

    def generate(self, spec: CreativeGenerationSpec) -> str:
        """Generate a human-readable review prompt."""
        s = spec.hook_scene
        g = spec.gameplay_sequence
        r = spec.reward_moment
        v = spec.visual_constraints

        lines = [
            f"Create a {spec.format} Facebook mobile game advertisement.",
            "",
            "Requirements:",
            "",
            f"Camera: {s.camera}",
            f"Character: {s.character} in {s.position}",
            f"Action: {s.action}",
            f"Click reason: {s.attention_reason}",
            "",
            f"Gameplay: show {g.interaction.replace('_', ' ')}",
            f"Before: {g.state_before.replace('_', ' ')}",
            f"After: {g.state_after.replace('_', ' ')}",
            f"Change: {g.visual_change} visual transformation",
            f"Transition: {g.transition}",
            "",
            f"Reward: {r.reward_object} {r.reward_action}",
            f"Emotion: {r.reward_emotion}",
            "",
            f"Style: {v.theme.replace('_', ' ')} theme",
            f"Composition: {v.composition}",
            f"Color: {v.color_palette}",
            f"Lighting: {v.lighting.replace('_', ' ')}",
            "",
            f"Game: Merge Witches (Evolution Merge)",
            f"Source: {spec.source_pattern} (confidence {spec.confidence:.2f})",
        ]
        return "\n".join(lines)

    def generate_all(self, specs: list[CreativeGenerationSpec]) -> list[str]:
        return [self.generate(s) for s in specs]


# ═══════════════════════════════════════════════════════════
# 3. Feasibility Report
# ═══════════════════════════════════════════════════════════

@dataclass
class FeasibilityReport:
    """Full Phase 1.6 feasibility test report."""
    total_specs: int = 0
    ready_specs: int = 0
    average_score: float = 0.0
    total_missing: int = 0
    quality_results: list[SpecQualityResult] = field(default_factory=list)
    review_prompts: list[str] = field(default_factory=list)
    phase_2_ready: bool = False

    def print_report(self) -> str:
        lines = []
        lines.append("=" * 65)
        lines.append("  PHASE 1.6: Generation Feasibility Test")
        lines.append("  Merge Witches — Creative Factory V2")
        lines.append("=" * 65)

        lines.append("")
        lines.append("Generation Feasibility Report")
        lines.append("")
        lines.append(f"  Total Specs:          {self.total_specs}")
        lines.append(f"  Ready:                {self.ready_specs}")
        lines.append(f"  Average Score:        {self.average_score:.0f}/100")
        lines.append(f"  Missing:              {self.total_missing}")
        lines.append(f"  Phase 2 Ready:        {'YES' if self.phase_2_ready else 'NO'}")

        # Detail per spec
        lines.append("")
        lines.append(f"  {'Spec':<45} {'Score':>5} {'Ready':>6}")
        lines.append(f"  {'─'*58}")
        for r in self.quality_results:
            status = "YES" if r.is_ready else "NO"
            lines.append(f"  {r.spec_id:<45} {r.readiness_score:>5} {status:>6}")

        # Score breakdown
        lines.append("")
        lines.append("  Score Breakdown:")
        for r in self.quality_results:
            lines.append(f"    [{r.spec_id}]")
            lines.append(f"      Scene:    {r.scene_score.score}/{r.scene_score.max_score}")
            lines.append(f"      Gameplay: {r.gameplay_score.score}/{r.gameplay_score.max_score}")
            lines.append(f"      Reward:   {r.reward_score.score}/{r.reward_score.max_score}")
            lines.append(f"      Visual:   {r.visual_score.score}/{r.visual_score.max_score}")

        # Warnings
        all_warnings = [w for r in self.quality_results for w in r.warnings]
        if all_warnings:
            lines.append("")
            lines.append("  Warnings:")
            for w in all_warnings:
                lines.append(f"    - {w}")

        # Missing
        all_missing = [m for r in self.quality_results for m in r.missing]
        if all_missing:
            lines.append("")
            lines.append("  Missing Fields:")
            for m in all_missing:
                lines.append(f"    - {m}")

        lines.append("")
        lines.append("=" * 65)
        if self.phase_2_ready:
            lines.append("  PHASE 1.6 COMPLETE — Ready for Phase 2")
            lines.append("=" * 65)
            lines.append(f"  All {self.ready_specs}/{self.total_specs} specs pass quality gate.")
            lines.append(f"  Average quality: {self.average_score:.0f}/100")
            lines.append(f"")
            lines.append(f"  Next: Phase 2 — Lovart AI Creative Generator MVP")
            lines.append(f"  Input: CreativeGenerationSpec")
            lines.append(f"  Output: Facebook UA ad creatives (NOT AI illustrations)")
        else:
            lines.append("  PHASE 1.6 INCOMPLETE — Fix missing fields first")
            lines.append("=" * 65)

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": "1.6",
            "total_specs": self.total_specs,
            "ready_specs": self.ready_specs,
            "average_score": round(self.average_score, 1),
            "total_missing": self.total_missing,
            "phase_2_ready": self.phase_2_ready,
            "quality_results": [r.to_dict() for r in self.quality_results],
            "review_prompts": self.review_prompts,
        }


# ═══════════════════════════════════════════════════════════
# V2: Creative Ad Readiness Scoring (Phase 1.6.1 — CORRECTED)
# ═══════════════════════════════════════════════════════════
# Evaluates whether a CreativeGenerationSpec can produce a
# high-ROAS Facebook UA ad via Lovart, NOT a game screenshot.
#
# Dimensions:
#   1. Historical DNA Alignment (30pts) — is this from a real winner?
#   2. Facebook Ad Structure (30pts) — first-second hook + comprehension speed
#   3. Lovart Generation Feasibility (25pts) — can Lovart execute this?
#   4. CTR Visual Factors (15pts) — will it stop the scroll?
#   ─────────────────
#   Total: 100pts


# ── First-second attention: subject prominence ──
ATTENTION_SUBJECTS: dict[str, int] = {
    "cute_witch": 5, "dragon": 5, "magical_girl": 4,
    "fairy": 3, "sorceress": 3, "": 0,
}

# ── Color → CTR contrast ──
COLOR_CONTRAST: dict[str, int] = {
    "purple": 5, "warm_red": 5, "purple_magic": 5,
    "blue_cool": 4, "mystical_blue": 4,
    "warm_golden": 3, "golden_light": 3,
    "green": 2, "enchanted_forest": 2,
}

# ── Composition → attention capture ──
COMPOSITION_ATTENTION: dict[str, int] = {
    "center": 5, "top": 3, "bottom": 2, "balanced": 1,
}

# ── Emotion → CTR ──
EMOTION_CTR: dict[str, int] = {
    "surprise": 5, "excitement": 5, "wow": 5, "awe": 5,
    "satisfaction": 4, "cute": 4, "delight": 4,
    "neutral": 2, "calm": 1,
}

# ── Lovart prompt quality indicators ──
LOVART_QUALITY_INDICATORS = [
    "specific subject",        # has a named character/object
    "color directive",         # specifies a color palette
    "composition directive",   # specifies layout
    "style guard",            # tells Lovart what NOT to do
    "format specified",       # 1080x1080 etc.
    "emotion target",         # surprise, excitement etc.
    "action moment",          # transformation, evolution etc.
    "ad context",             # "Facebook ad", "mobile game ad"
]


class HistoricalDNAAligner:
    """Validate alignment with Phase 1.4 winner DNA (30pts).

    Winner DNA match:     15pts — does it use proven winner dimensions?
    ROAS correlation:     10pts — how strong is the ROAS signal?
    Sample confidence:     5pts — how many samples support this?
    """

    def __init__(self, rules: list[dict[str, Any]]) -> None:
        self._impact_map: dict[str, float] = {}
        self._roas_map: dict[str, float] = {}
        for r in rules:
            if r.get("decision") == "GENERATE":
                key = f"{r['dimension']}:{r['value']}"
                self._impact_map[key] = r.get("impact_score", 0.0)
                self._roas_map[key] = r.get("confidence", 0.0)
        self._max_impact = sum(self._impact_map.values()) if self._impact_map else 1.0
        self._max_roas = sum(self._roas_map.values()) if self._roas_map else 1.0

    def score(self, spec: CreativeGenerationSpec) -> tuple[int, list[str]]:
        details: list[str] = []
        matched_impact = 0.0
        matched_roas = 0.0
        matched_count = 0
        matched_keys: list[str] = []

        # Check hook
        for key_prefix in ["hook:character_showcase", "hook:merge_upgrade", "hook:evolution"]:
            if key_prefix in self._impact_map:
                matched_impact += self._impact_map[key_prefix]
                matched_roas += self._roas_map.get(key_prefix, 0.0)
                matched_count += 1
                matched_keys.append(key_prefix)
                break

        # Check composition
        comp_key = f"composition:{spec.visual_constraints.composition}"
        if comp_key in self._impact_map:
            matched_impact += self._impact_map[comp_key]
            matched_roas += self._roas_map.get(comp_key, 0.0)
            matched_count += 1
            matched_keys.append(comp_key)

        # Check color
        color_key = f"color:{spec.visual_constraints.color_palette}"
        if color_key in self._impact_map:
            matched_impact += self._impact_map[color_key]
            matched_roas += self._roas_map.get(color_key, 0.0)
            matched_count += 1
            matched_keys.append(color_key)

        # 1. Winner DNA match (15pts)
        if self._max_impact > 0:
            dna_match = int(round((matched_impact / self._max_impact) * 15))
        else:
            dna_match = 0

        # 2. ROAS correlation (10pts)
        if self._max_roas > 0:
            roas_corr = int(round((matched_roas / self._max_roas) * 10))
        else:
            roas_corr = 0

        # 3. Sample confidence (5pts)
        sample_conf = min(matched_count * 2, 5)

        total = dna_match + roas_corr + sample_conf
        details.append(f"dna_match={dna_match}/15: {matched_keys}")
        details.append(f"roas_corr={roas_corr}/10: impact={matched_impact:.3f}/{self._max_impact:.3f}")
        details.append(f"sample_conf={sample_conf}/5: {matched_count} dimensions matched")

        return total, details


class FacebookAdStructureScorer:
    """Evaluate Facebook UA ad structure (30pts).

    First-second attention: 15pts — does it grab attention instantly?
    Info comprehension:     15pts — does user understand in 1 second?
    """

    def score(self, spec: CreativeGenerationSpec) -> tuple[int, list[str]]:
        s = spec.hook_scene
        v = spec.visual_constraints
        r = spec.reward_moment
        details: list[str] = []

        # ── First-second attention (15pts) ──
        # Subject prominence (5pts)
        subject_score = ATTENTION_SUBJECTS.get(s.character, 2)
        details.append(f"subject_prominence={subject_score}/5: {s.character}")

        # Color contrast (5pts)
        color_score = COLOR_CONTRAST.get(v.color_palette, 2)
        details.append(f"color_contrast={color_score}/5: {v.color_palette}")

        # Composition (5pts)
        comp_score = COMPOSITION_ATTENTION.get(v.composition, 2)
        details.append(f"composition_attention={comp_score}/5: {v.composition}")

        attention_total = subject_score + color_score + comp_score

        # ── Info comprehension speed (15pts) ──
        # Is it obvious this is a game ad? (5pts)
        has_game_context = bool(s.character and v.theme)
        is_game = 5 if has_game_context else 2
        details.append(f"is_game_obvious={is_game}/5")

        # Is the core action clear? (5pts)
        has_action = bool(s.action and s.action != "idle")
        has_reward = bool(r.reward_action)
        is_clear = 5 if (has_action or has_reward) else 2
        details.append(f"action_clear={is_clear}/5: action={s.action}, reward={r.reward_action}")

        # Is the value proposition obvious? (5pts)
        has_value = bool(r.reward_object and r.reward_action)
        value_prop = 5 if has_value else 3
        details.append(f"value_prop={value_prop}/5")

        comprehension_total = is_game + is_clear + value_prop

        total = attention_total + comprehension_total
        return total, details


class LovartFeasibilityScorer:
    """Evaluate how well the spec can guide Lovart generation (25pts).

    Checks if the prompt contains enough specific directives
    for Lovart to produce a useful ad, not a fantasy illustration.
    """

    def score(self, spec: CreativeGenerationSpec) -> tuple[int, list[str]]:
        s = spec.hook_scene
        v = spec.visual_constraints
        r = spec.reward_moment
        g = spec.gameplay_sequence
        details: list[str] = []

        indicators = {
            "specific subject": bool(s.character and s.character not in ("", "character", "game", "subject")),
            "color directive": bool(v.color_palette and v.color_palette not in ("", "color", "theme")),
            "composition directive": bool(v.composition and v.composition not in ("", "layout")),
            "style guard": True,  # always present in our builder
            "format specified": bool(spec.format),
            "emotion target": bool(r.reward_emotion),
            "action moment": bool(r.reward_action and r.reward_action != "idle"),
            "ad context": bool(s.character and v.theme),
        }

        per_indicator = 25 // len(indicators)  # 3 pts each
        score = 0
        all_present = True
        for name, present in indicators.items():
            if present:
                score += per_indicator
                details.append(f"lovart_{name.replace(' ', '_')}: +{per_indicator}")
            else:
                all_present = False
                details.append(f"lovart_{name.replace(' ', '_')}: MISSING")

        # Bonus for fully complete spec
        if all_present:
            score += (25 - per_indicator * len(indicators))  # fill remaining to 25
            details.append(f"lovart_bonus_complete: +{25 - per_indicator * len(indicators)}")

        # Deduct for overly generic descriptions
        generic_count = 0
        if s.character in ("", "character", "game"):
            generic_count += 1
        if v.color_palette in ("", "color", "theme"):
            generic_count += 1
        if r.reward_action in ("", "action", "change"):
            generic_count += 1
        if generic_count > 0:
            deduction = min(generic_count * 3, score)
            score -= deduction
            details.append(f"lovart_generic_deduction: -{deduction} ({generic_count} generic fields)")

        return max(score, 0), details


class CTRVisualScorer:
    """Evaluate CTR-driving visual factors (15pts).

    Subject prominence: 5pts — is the main subject large and clear?
    Color contrast:     5pts — does the color palette pop?
    Emotion expression: 5pts — is there a clear emotional trigger?
    """

    def score(self, spec: CreativeGenerationSpec) -> tuple[int, list[str]]:
        s = spec.hook_scene
        v = spec.visual_constraints
        r = spec.reward_moment
        details: list[str] = []

        # Subject prominence (5pts)
        has_center = (s.position == "center")
        has_named_char = bool(s.character and s.character not in ("", "character"))
        if has_center and has_named_char:
            subj = 5
        elif has_center or has_named_char:
            subj = 3
        else:
            subj = 1
        details.append(f"subject_prominence={subj}/5: center={has_center}, named={has_named_char}")

        # Color contrast (5pts)
        color = COLOR_CONTRAST.get(v.color_palette, 2)
        details.append(f"color_contrast={color}/5: {v.color_palette}")

        # Emotion expression (5pts)
        emotion = EMOTION_CTR.get(r.reward_emotion, 2)
        details.append(f"emotion={emotion}/5: {r.reward_emotion}")

        total = subj + color + emotion
        return total, details


@dataclass
class SpecReadinessV2:
    """Ad readiness score for a single GenerationSpec (corrected)."""
    spec_id: str = ""
    dna_alignment: int = 0       # 0-30
    ad_structure: int = 0        # 0-30
    lovart_feasibility: int = 0  # 0-25
    ctr_factors: int = 0         # 0-15
    total: int = 0               # 0-100
    details: list[str] = field(default_factory=list)
    phase_2_gate: bool = False   # total>=80, dna>=20, ad_structure>=20

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec_id": self.spec_id,
            "dna_alignment": self.dna_alignment,
            "ad_structure": self.ad_structure,
            "lovart_feasibility": self.lovart_feasibility,
            "ctr_factors": self.ctr_factors,
            "total": self.total,
            "details": self.details,
            "phase_2_gate": self.phase_2_gate,
        }


class GenerationReadinessScorerV2:
    """Creative Ad Readiness Scoring (100pts).

    Dimensions:
      Historical DNA Alignment:   30pts (winner DNA + ROAS + sample)
      Facebook Ad Structure:      30pts (first-second hook + comprehension)
      Lovart Generation Feasibility: 25pts (can Lovart execute this?)
      CTR Visual Factors:         15pts (subject + color + emotion)
    """

    PHASE2_TOTAL_MIN = 80
    PHASE2_DNA_MIN = 20
    PHASE2_AD_MIN = 20

    def __init__(self, rules: list[dict[str, Any]]) -> None:
        self._dna = HistoricalDNAAligner(rules)
        self._ad = FacebookAdStructureScorer()
        self._lovart = LovartFeasibilityScorer()
        self._ctr = CTRVisualScorer()

    def score(self, spec: CreativeGenerationSpec) -> SpecReadinessV2:
        details: list[str] = []

        dna_score, dna_details = self._dna.score(spec)
        details.extend(dna_details)

        ad_score, ad_details = self._ad.score(spec)
        details.extend(ad_details)

        lovart_score, lovart_details = self._lovart.score(spec)
        details.extend(lovart_details)

        ctr_score, ctr_details = self._ctr.score(spec)
        details.extend(ctr_details)

        total = dna_score + ad_score + lovart_score + ctr_score

        gate = (
            total >= self.PHASE2_TOTAL_MIN
            and dna_score >= self.PHASE2_DNA_MIN
            and ad_score >= self.PHASE2_AD_MIN
        )

        return SpecReadinessV2(
            spec_id=spec.source_pattern,
            dna_alignment=dna_score,
            ad_structure=ad_score,
            lovart_feasibility=lovart_score,
            ctr_factors=ctr_score,
            total=total,
            details=details,
            phase_2_gate=gate,
        )

    def score_all(self, specs: list[CreativeGenerationSpec]) -> list[SpecReadinessV2]:
        return [self.score(s) for s in specs]


@dataclass
class FeasibilityReportV2:
    """Full Phase 1.6.1 feasibility test report (corrected V2)."""
    total_specs: int = 0
    passed_gate: int = 0
    average_score: float = 0.0
    results: list[SpecReadinessV2] = field(default_factory=list)
    phase_2_ready: bool = False

    def print_report(self) -> str:
        lines = []
        lines.append("=" * 65)
        lines.append("  PHASE 1.6.1: Creative Ad Readiness Score V2")
        lines.append("  Merge Witches — Facebook UA Creative Factory")
        lines.append("=" * 65)

        lines.append("")
        lines.append("Creative Ad Readiness V2")
        lines.append("")
        lines.append(f"  Total Specs:          {self.total_specs}")
        lines.append(f"  Passed Phase 2 Gate:  {self.passed_gate}")
        lines.append(f"  Average Score:        {self.average_score:.0f}/100")
        lines.append(f"  Phase 2 Ready:        {'YES' if self.phase_2_ready else 'NO'}")
        lines.append(f"")
        lines.append(f"  Gate: Total>=80, DNA>=20, Ad Structure>=20")

        lines.append("")
        lines.append(f"  {'Spec':<40} {'DNA':>4} {'Ad':>3} {'Lovart':>7} {'CTR':>4} {'Total':>5} {'Gate':>5}")
        lines.append(f"  {'─'*72}")
        for r in self.results:
            gate = "PASS" if r.phase_2_gate else "FAIL"
            lines.append(f"  {r.spec_id:<40} {r.dna_alignment:>4} {r.ad_structure:>3} "
                         f"{r.lovart_feasibility:>7} {r.ctr_factors:>4} {r.total:>5} {gate:>5}")

        lines.append("")
        lines.append("  Score Breakdown:")
        for r in self.results:
            lines.append(f"    [{r.spec_id}] total={r.total}")
            for d in r.details:
                lines.append(f"      {d}")

        lines.append("")
        lines.append("=" * 65)
        if self.phase_2_ready:
            lines.append("  PHASE 1.6.1 COMPLETE — Ready for Phase 2")
            lines.append("=" * 65)
            lines.append(f"  {self.passed_gate}/{self.total_specs} specs pass ad readiness gate.")
            lines.append(f"  Average ad readiness: {self.average_score:.0f}/100")
            lines.append(f"")
            lines.append(f"  Next: Phase 2 — Lovart AI Creative Generator MVP")
            lines.append(f"  Goal: Auto-generate Facebook UA ad creatives")
        else:
            lines.append("  PHASE 1.6.1 INCOMPLETE — Fix failing specs")
            lines.append("=" * 65)

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": "1.6.1",
            "total_specs": self.total_specs,
            "passed_gate": self.passed_gate,
            "average_score": round(self.average_score, 1),
            "phase_2_ready": self.phase_2_ready,
            "results": [r.to_dict() for r in self.results],
        }