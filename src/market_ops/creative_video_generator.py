"""Creative Video Generator — Winner DNA → Storyboard → Video Plan.

Phase B of Creative Factory Loop v1.1:
  CreativePerformance (winners)
        │
        ▼
  build_dna_from_winner()
        │
        ▼
  Story Planner (5 archetypes: rescue/revenge/evolution/challenge/impossible_level)
        │
        ▼
  StoryPlan (beats: hook → problem → gameplay → reward → cta)
        │
        ▼
  Video Generation Plan (JSON) → Remix Engine / ffmpeg composer
        │
        ▼
  GeneratedVideo

Story archetypes mapped to DNA:
  - witch character + trapped hook → rescue
  - dragon + evolution reward → evolution
  - merge puzzle + challenge → challenge
  - high ROAS (>2.0) → revenge (aggressive)
  - exploration → impossible_level

Usage:
    generator = CreativeVideoGenerator()
    plans = generator.generate_from_winners(winners, per_winner=3)
    # → storyboards ready for Remix Engine consumption
"""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import date
from pathlib import Path
from typing import Any, Optional

from .creative_performance_builder import CreativePerformance
from .creative_image_generator import MERGE_WITCHES_DEFAULT_DNA


# ── Story Archetypes (from creative_remix_engine/director/story_planner.py) ──

@dataclass
class StoryBeat:
    """A single beat in the storyboard timeline."""
    beat_id: str = ""
    role: str = ""          # hook / problem / gameplay / reward / cta
    duration: float = 0.0   # seconds
    subtitle: str = ""
    subtitle_style: str = "normal"  # normal / big / urgent / whisper
    visual_direction: str = ""
    transition_in: str = "hard_cut"  # hard_cut / zoom_in / impact_hit / flash_white / fade
    emotion_target: str = ""
    sound_hint: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StoryPlan:
    """A complete video storyboard."""
    plan_id: str = ""
    story_type: str = ""       # rescue / revenge / evolution / challenge / impossible_level
    title: str = ""
    emotion_arc: list[str] = field(default_factory=list)
    beats: list[StoryBeat] = field(default_factory=list)
    total_duration: float = 15.0
    target_ratio: str = "9:16"
    dna_match_score: float = 0.0
    source_winner_id: str = ""
    source_platform: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["beats"] = [b.to_dict() for b in self.beats]
        return d


@dataclass
class GeneratedVideo:
    """A single generated video result."""
    filename: str = ""
    local_path: str = ""
    plan_id: str = ""
    story_type: str = ""
    title: str = ""
    duration: float = 0.0
    winner_id: str = ""
    platform: str = ""
    generated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VideoGenerationResult:
    """Result from a batch video generation run."""
    date: str = ""
    total_plans: int = 0
    total_generated: int = 0
    videos: list[GeneratedVideo] = field(default_factory=list)
    story_plans: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    elapsed_sec: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["videos"] = [v.to_dict() for v in self.videos]
        return d

    @property
    def success_rate(self) -> float:
        if self.total_plans == 0:
            return 0.0
        return round(self.total_generated / self.total_plans, 4)


# ── Story Templates (5 archetypes from the Remix Engine) ──

STORY_TEMPLATES: dict[str, dict] = {
    "rescue": {
        "title": "Rescue the Witch",
        "emotion_arc": ["curiosity", "tension", "excitement", "satisfaction"],
        "beats": [
            {"role": "hook", "duration": 2.5, "subtitle": "The Witch is TRAPPED!",
             "style": "big", "visual": "witch trapped in dark cage, close-up",
             "transition": "zoom_in", "emotion": "shock", "sound": "heartbeat"},
            {"role": "problem", "duration": 2.5, "subtitle": "Only YOU can save her",
             "style": "urgent", "visual": "player finger tapping screen",
             "transition": "hard_cut", "emotion": "urgency", "sound": "clock_tick"},
            {"role": "gameplay", "duration": 6.0, "subtitle": "MERGE → EVOLVE → RESCUE",
             "style": "normal", "visual": "fast merge chain, dragon appearing",
             "transition": "impact_hit", "emotion": "excitement", "sound": "combo_sfx"},
            {"role": "reward", "duration": 2.5, "subtitle": "SHE'S FREE!",
             "style": "big", "visual": "witch transforming, bright light",
             "transition": "flash_white", "emotion": "triumph", "sound": "magic_burst"},
            {"role": "cta", "duration": 1.5, "subtitle": "Download & Save Her Now",
             "style": "urgent", "visual": "app store icon + character pose",
             "transition": "fade", "emotion": "desire", "sound": "click"},
        ],
    },
    "revenge": {
        "title": "Witch's Revenge",
        "emotion_arc": ["anger", "determination", "power", "victory"],
        "beats": [
            {"role": "hook", "duration": 2.5, "subtitle": "They took EVERYTHING",
             "style": "big", "visual": "castle burning, witch silhouette",
             "transition": "zoom_in", "emotion": "rage", "sound": "thunder"},
            {"role": "problem", "duration": 2.0, "subtitle": "But she has a SECRET",
             "style": "whisper", "visual": "ancient spell book glowing",
             "transition": "flash_white", "emotion": "mystery", "sound": "whisper"},
            {"role": "gameplay", "duration": 6.5, "subtitle": "Merge to UNLEASH HELL",
             "style": "normal", "visual": "explosive merges, dragon attacks",
             "transition": "impact_hit", "emotion": "power", "sound": "explosion"},
            {"role": "reward", "duration": 2.5, "subtitle": "VICTORY IS YOURS",
             "style": "big", "visual": "dragon breathing fire on enemies",
             "transition": "zoom_in", "emotion": "triumph", "sound": "victory_horn"},
            {"role": "cta", "duration": 1.5, "subtitle": "Join the Revenge",
             "style": "urgent", "visual": "download button pulsating",
             "transition": "fade", "emotion": "desire", "sound": "click"},
        ],
    },
    "evolution": {
        "title": "From Egg to Dragon God",
        "emotion_arc": ["curiosity", "anticipation", "amazement", "satisfaction"],
        "beats": [
            {"role": "hook", "duration": 2.5, "subtitle": "Level 1 vs Level 99",
             "style": "big", "visual": "tiny egg vs massive dragon side by side",
             "transition": "hard_cut", "emotion": "curiosity", "sound": "pop"},
            {"role": "problem", "duration": 2.0, "subtitle": "Can you reach the MAX?",
             "style": "normal", "visual": "level bar filling slowly",
             "transition": "zoom_in", "emotion": "challenge", "sound": "level_up"},
            {"role": "gameplay", "duration": 7.0, "subtitle": "SWIPE → MERGE → EVOLVE",
             "style": "normal", "visual": "continuous merge chain, rapid evolution",
             "transition": "impact_hit", "emotion": "excitement", "sound": "combo_sfx"},
            {"role": "reward", "duration": 2.0, "subtitle": "ULTIMATE FORM UNLOCKED",
             "style": "big", "visual": "legendary dragon with aura, screen shake",
             "transition": "flash_white", "emotion": "amazement", "sound": "epic_fanfare"},
            {"role": "cta", "duration": 1.5, "subtitle": "Evolve Yours Now",
             "style": "urgent", "visual": "character collection showcase",
             "transition": "fade", "emotion": "desire", "sound": "click"},
        ],
    },
    "challenge": {
        "title": "Impossible Merge Challenge",
        "emotion_arc": ["confidence", "frustration", "determination", "triumph"],
        "beats": [
            {"role": "hook", "duration": 2.5, "subtitle": "99% CAN'T Pass Level 47",
             "style": "big", "visual": "failed attempt counter at 99",
             "transition": "zoom_in", "emotion": "challenge", "sound": "buzzer"},
            {"role": "problem", "duration": 2.5, "subtitle": "The board is FULL!",
             "style": "urgent", "visual": "grid packed with items, timer at 3s",
             "transition": "hard_cut", "emotion": "tension", "sound": "heartbeat"},
            {"role": "gameplay", "duration": 6.0, "subtitle": "ONE perfect move...",
             "style": "normal", "visual": "slow motion merge, chain reaction",
             "transition": "impact_hit", "emotion": "hope", "sound": "swoosh"},
            {"role": "reward", "duration": 2.5, "subtitle": "GENIUS!",
             "style": "big", "visual": "victory screen, confetti",
             "transition": "flash_white", "emotion": "triumph", "sound": "cheer"},
            {"role": "cta", "duration": 1.5, "subtitle": "Can YOU beat it?",
             "style": "urgent", "visual": "finger tapping download",
             "transition": "fade", "emotion": "desire", "sound": "click"},
        ],
    },
    "impossible_level": {
        "title": "The Final Boss Battle",
        "emotion_arc": ["fear", "desperation", "hope", "glory"],
        "beats": [
            {"role": "hook", "duration": 2.5, "subtitle": "This Boss is UNBEATABLE",
             "style": "big", "visual": "giant boss shadow, HP bar massive",
             "transition": "zoom_in", "emotion": "fear", "sound": "roar"},
            {"role": "problem", "duration": 2.0, "subtitle": "Your team is WEAK",
             "style": "whisper", "visual": "low-level characters trembling",
             "transition": "hard_cut", "emotion": "despair", "sound": "sigh"},
            {"role": "gameplay", "duration": 7.0, "subtitle": "MERGE = POWER UP",
             "style": "normal", "visual": "rapid merges, characters leveling up",
             "transition": "impact_hit", "emotion": "hope", "sound": "power_up"},
            {"role": "reward", "duration": 2.0, "subtitle": "IMPOSSIBLE IS NOTHING",
             "style": "big", "visual": "boss defeated, legendary drop",
             "transition": "flash_white", "emotion": "glory", "sound": "epic_fanfare"},
            {"role": "cta", "duration": 1.5, "subtitle": "Face the Boss Now",
             "style": "urgent", "visual": "boss icon + download CTA",
             "transition": "fade", "emotion": "desire", "sound": "click"},
        ],
    },
}

# DNA → Story type mapping
DNA_TO_STORY: dict[str, list[str]] = {
    "rescue": ["witch", "trapped", "save", "rescue"],
    "revenge": ["revenge", "destroy", "burn", "fight"],
    "evolution": ["dragon", "egg", "evolve", "hatch", "level up"],
    "challenge": ["merge", "puzzle", "challenge", "impossible", "fail"],
    "impossible_level": ["boss", "battle", "final", "unbeatable"],
}


class CreativeVideoGenerator:
    """Generate Merge Witches ad video storyboards from Winner DNA.

    Pipeline:
      1. Build DNA from CreativePerformance winners
      2. Select best story archetype based on DNA
      3. Generate StoryPlan with beats
      4. Output video generation plan (JSON) for Remix Engine consumption
    """

    def __init__(
        self,
        output_dir: Path | None = None,
        target_duration: float = 15.0,
        target_ratio: str = "9:16",
    ) -> None:
        self.output_dir = Path(output_dir) if output_dir else Path("output/creative_factory/videos")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.target_duration = target_duration
        self.target_ratio = target_ratio

    # ── Public API ──

    def generate_from_winners(
        self,
        winners: list[CreativePerformance],
        per_winner: int = 3,
        max_total: int = 20,
    ) -> VideoGenerationResult:
        """Generate video storyboards from a list of winner CreativePerformances.

        Args:
            winners: List of winner CreativePerformance objects.
            per_winner: Number of story variants per winner.
            max_total: Maximum total video plans to generate.

        Returns:
            VideoGenerationResult with all story plans.
        """
        import time
        today = date.today().isoformat()
        result = VideoGenerationResult(date=today)
        t0 = time.time()

        sorted_winners = sorted(winners, key=lambda w: w.roas, reverse=True)

        for winner in sorted_winners:
            if result.total_plans >= max_total:
                break

            dna = self._build_dna_from_winner(winner)
            story_type = self._select_story_type(dna, winner)

            remaining = max_total - result.total_plans
            count = min(per_winner, remaining)

            for i in range(count):
                try:
                    plan = self._generate_story_plan(
                        dna=dna,
                        story_type=story_type,
                        winner=winner,
                        variant_index=i,
                    )
                    result.story_plans.append(plan.to_dict())
                    result.total_plans += 1

                except Exception as e:
                    result.errors.append(f"[{winner.creative_id}] story plan failed: {e}")

        result.total_generated = result.total_plans
        result.elapsed_sec = round(time.time() - t0, 1)

        # Save manifest
        self._save_manifest(result)

        return result

    def generate_from_dna(
        self,
        dna: dict[str, Any],
        count: int = 3,
        label: str = "custom",
    ) -> VideoGenerationResult:
        """Generate video storyboards from a raw DNA dict."""
        import time
        today = date.today().isoformat()
        result = VideoGenerationResult(date=today)
        t0 = time.time()

        story_type = self._select_story_type(dna)

        for i in range(count):
            try:
                dummy_winner = CreativePerformance(
                    creative_id=f"dna_{label}",
                    creative_name=label,
                    platform="custom",
                    roas=1.0,
                )
                plan = self._generate_story_plan(
                    dna=dna,
                    story_type=story_type,
                    winner=dummy_winner,
                    variant_index=i,
                )
                result.story_plans.append(plan.to_dict())
                result.total_plans += 1
            except Exception as e:
                result.errors.append(f"[{label}] story plan failed: {e}")

        result.total_generated = result.total_plans
        result.elapsed_sec = round(time.time() - t0, 1)
        self._save_manifest(result)
        return result

    def generate_plans_only(
        self,
        winners: list[CreativePerformance],
        per_winner: int = 3,
    ) -> list[dict[str, Any]]:
        """Generate story plans without video composition (for testing)."""
        result = self.generate_from_winners(winners, per_winner=per_winner)
        return result.story_plans

    # ── Internal: DNA Building ──

    def _build_dna_from_winner(self, winner: CreativePerformance) -> dict[str, str]:
        """Build DNA from winner, merging defaults with performance signals."""
        dna = dict(MERGE_WITCHES_DEFAULT_DNA)

        if winner.platform == "ios":
            dna["style"] = "cartoon polished"
        elif winner.platform == "android":
            dna["style"] = "cartoon vibrant"

        if winner.roas >= 2.0:
            dna["emotion"] = "excitement and triumph"
            dna["hook"] = "merge win moment"
        if winner.spend >= 5000:
            dna["style"] = dna.get("style", "cartoon") + " proven winner"

        return dna

    # ── Internal: Story Selection ──

    def _select_story_type(
        self,
        dna: dict[str, Any],
        winner: CreativePerformance | None = None,
    ) -> str:
        """Select the best story archetype based on DNA content.

        Scoring:
          - Match DNA values against keyword lists
          - High ROAS winners get more aggressive archetypes
        """
        scores: dict[str, int] = {k: 0 for k in STORY_TEMPLATES}

        # Score based on DNA keywords
        dna_text = " ".join(str(v).lower() for v in dna.values())
        for story_type, keywords in DNA_TO_STORY.items():
            for kw in keywords:
                if kw in dna_text:
                    scores[story_type] += 1

        # Boost based on ROAS
        if winner and winner.roas >= 2.0:
            scores["revenge"] += 2
            scores["impossible_level"] += 1
        if winner and winner.roas >= 1.5:
            scores["evolution"] += 1
        if winner and winner.platform == "ios":
            scores["rescue"] += 1  # iOS audience responds to emotional hooks

        # Default to challenge if no clear winner
        best = max(scores, key=scores.get)
        if scores[best] == 0:
            return "challenge"
        return best

    # ── Internal: Story Plan Generation ──

    def _generate_story_plan(
        self,
        dna: dict[str, Any],
        story_type: str,
        winner: CreativePerformance,
        variant_index: int = 0,
    ) -> StoryPlan:
        """Generate a single StoryPlan from DNA and story type."""
        template = STORY_TEMPLATES.get(story_type, STORY_TEMPLATES["challenge"])

        # Build beats
        beats: list[StoryBeat] = []
        for i, beat_data in enumerate(template["beats"]):
            subtitle = self._personalize_subtitle(beat_data["subtitle"], dna, winner, variant_index)
            beats.append(StoryBeat(
                beat_id=f"{story_type}_{i+1}",
                role=beat_data["role"],
                duration=beat_data["duration"],
                subtitle=subtitle,
                subtitle_style=beat_data["style"],
                visual_direction=beat_data["visual"],
                transition_in=beat_data["transition"],
                emotion_target=beat_data["emotion"],
                sound_hint=beat_data.get("sound", ""),
            ))

        total_duration = sum(b.duration for b in beats)

        # Generate deterministic plan ID
        plan_hash = hashlib.md5(
            f"{winner.creative_id}_{story_type}_{variant_index}".encode()
        ).hexdigest()[:12]

        return StoryPlan(
            plan_id=f"vid_{plan_hash}",
            story_type=story_type,
            title=template["title"],
            emotion_arc=template["emotion_arc"],
            beats=beats,
            total_duration=total_duration,
            target_ratio=self.target_ratio,
            dna_match_score=self._calc_dna_match(dna, story_type),
            source_winner_id=winner.creative_id,
            source_platform=winner.platform,
        )

    @staticmethod
    def _personalize_subtitle(
        template_text: str,
        dna: dict[str, Any],
        winner: CreativePerformance,
        variant_index: int,
    ) -> str:
        """Add small variations to subtitles for diversity."""
        # Simple variant: alternate emoji or punctuation
        if variant_index % 2 == 1:
            return template_text.replace("!", "!!").replace("?", "?!")
        return template_text

    @staticmethod
    def _calc_dna_match(dna: dict[str, Any], story_type: str) -> float:
        """Calculate how well the DNA matches the story type."""
        if story_type not in DNA_TO_STORY:
            return 0.5
        keywords = DNA_TO_STORY[story_type]
        dna_text = " ".join(str(v).lower() for v in dna.values())
        matches = sum(1 for kw in keywords if kw in dna_text)
        return round(min(matches / len(keywords) * 2, 1.0), 2)

    # ── Internal: Persistence ──

    def _save_manifest(self, result: VideoGenerationResult) -> Path:
        """Save video generation manifest to JSON."""
        today = date.today().isoformat().replace("-", "")
        path = self.output_dir / f"video_manifest_{today}.json"
        path.write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path


# ── Convenience function ──

def create_default_video_generator(
    output_dir: str | Path = "output/creative_factory/videos",
) -> CreativeVideoGenerator:
    """Create a CreativeVideoGenerator with sensible defaults."""
    return CreativeVideoGenerator(
        output_dir=Path(output_dir),
        target_duration=15.0,
        target_ratio="9:16",
    )