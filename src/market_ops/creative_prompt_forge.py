from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from market_ops.models import CreativeAssetRow


# ---------------------------------------------------------------------------
# 项目对应的美术风格、关键视觉元素映射表
# ---------------------------------------------------------------------------
GAME_VISUAL_CONTEXT: dict[str, dict[str, Any]] = {
    "P04 Witch": {
        "genre": "merge-2 puzzle / witch-themed casual",
        "palette": "dark purple, neon green, magical gold, deep blue",
        "key_elements": [
            "witch cauldron", "magic potion bottles", "crystal ball",
            "dark forest background", "spell book", "ghost/skeleton side characters",
            "merge board with items", "level-up sparkle effects",
        ],
        "ui_style": "fantasy gothic UI frames, ornate borders, glowing buttons",
        "mood": "mysterious, magical, slightly spooky but cute",
        "cta_text": "Brew the Magic!",
    },
    "P02 Mermaid": {
        "genre": "merge-2 puzzle / mermaid-themed casual",
        "palette": "ocean blue, coral pink, pearl white, seafoam green",
        "key_elements": [
            "mermaid character", "underwater palace", "seashells",
            "pearl merge items", "coral reef background", "bubbles",
            "treasure chest", "starfish", "ocean waves",
        ],
        "ui_style": "underwater crystal UI, shell-shaped buttons, flowing ribbons",
        "mood": "dreamy, elegant, underwater fantasy",
        "cta_text": "Dive into Magic!",
    },
    "P07 Vampire": {
        "genre": "merge-2 puzzle / vampire-themed casual",
        "palette": "blood red, midnight black, moonlight silver, royal purple",
        "key_elements": [
            "vampire character", "gothic mansion", "blood vials",
            "candle-lit merge board", "coffin items", "bat wings",
            "full moon", "rose petals", "ancient tome",
        ],
        "ui_style": "gothic dark UI, blood-red accents, ornate Victorian frames",
        "mood": "dark romantic, mysterious, aristocratic gothic",
        "cta_text": "Awaken the Night!",
    },
}

# Default fallback for unknown projects
FALLBACK_VISUAL = {
    "genre": "casual merge puzzle",
    "palette": "vibrant, high contrast, warm tones",
    "key_elements": ["merge board", "colorful items", "level progress bar"],
    "ui_style": "clean modern casual UI",
    "mood": "fun, satisfying, rewarding",
    "cta_text": "Play Now!",
}


# ---------------------------------------------------------------------------
# Prompt templates for different hook types
# ---------------------------------------------------------------------------
HOOK_PROMPT_TEMPLATES: dict[str, str] = {
    "crisis": (
        "Show a {game} gameplay screenshot in a critical state: a messy merge board with timer running out, "
        "items scattered chaotically, the witch looks worried. Add a bold text overlay: 'Can YOU fix this in 10 seconds?' "
        "Use {palette} colors. CTA button at bottom: '{cta}'. Mobile portrait 9:16."
    ),
    "reward": (
        "Show a {game} gameplay close-up of a satisfying merge combo: multiple items merging into a rare high-level item, "
        "sparkle and level-up effects. Bold overlay text: 'Best Merge Ever!' Use {palette}. "
        "CTA: '{cta}'. Mobile portrait 9:16."
    ),
    "twist": (
        "Split-screen {game} image: LEFT side shows a 'fail' (wrong merge, ugly result), "
        "RIGHT side shows the perfect merge result. Overlay text: 'Don't make this mistake!' "
        "Use {palette} and {mood} feeling. CTA: '{cta}'. Mobile portrait 9:16."
    ),
    "comparison": (
        "Before/after {game} screenshot: top half shows low-level items, bottom half shows the same items merged "
        "into epic versions. Arrow pointing down. Overlay: 'Level 1 → Level 10 in ONE merge!' "
        "Use {palette}. CTA: '{cta}'. Mobile portrait 9:16."
    ),
    "curiosity": (
        "A mysterious {game} screenshot with a hidden item partially revealed behind fog/shadows. "
        "Question overlay: 'What happens when you merge these?' A glowing merge board hint in background. "
        "Use {palette} and {mood} atmosphere. CTA: '{cta}'. Mobile portrait 9:16."
    ),
    "collection": (
        "A {game} collection screen showing many locked character/item slots with 1-2 unlocked. "
        "Overlay: 'Collect ALL 50 characters!' Progress bar at bottom. Use {palette}. "
        "CTA: '{cta}'. Mobile portrait 9:16."
    ),
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class ImagePrompt:
    """A single AI image generation prompt with metadata."""

    prompt_id: str
    project: str
    hook_type: str
    emotion: str
    target_platform: str  # "Facebook", "Instagram", etc.
    prompt_text: str
    negative_prompt: str = ""
    reference_elements: list[str] = field(default_factory=list)
    expected_ctr_range: str = ""
    expected_cvr_range: str = ""
    # When set, the image generator passes this as a Lovart attachment so the
    # new image is generated as a variation of this real winner (img2img),
    # not a free-form text-to-image guess.
    reference_image_url: str = ""
    # Human-readable label of what this prompt varies vs. the source winner,
    # e.g. "companion_creature: baby owl". Used for logging and review.
    variation_axis: str = ""


@dataclass(slots=True)
class PromptBatch:
    """A batch of generated prompts ready for image generation."""

    project: str
    generated_at: str
    total_prompts: int
    prompts: list[ImagePrompt]


# ---------------------------------------------------------------------------
# Prompt Forge
# ---------------------------------------------------------------------------
class CreativePromptForge:
    """Generates AI image prompts from winning creative patterns.

    Reads CreativeDNA output (or CSV creative data) and produces structured
    prompts optimized for game ad image generation.
    """

    def __init__(self, game: str = "P04 Witch") -> None:
        self._game = game
        self._visual = GAME_VISUAL_CONTEXT.get(game, FALLBACK_VISUAL)

    def set_game(self, game: str) -> None:
        self._game = game
        self._visual = GAME_VISUAL_CONTEXT.get(game, FALLBACK_VISUAL)

    # ----- public API -----

    def forge_from_dna(self, dna_payload: dict[str, Any], max_prompts: int = 10) -> PromptBatch:
        """Generate prompts from CreativeDNA JSON output."""
        items = dna_payload.get("top_scalable") or dna_payload.get("items") or []
        return self._forge(items, max_prompts)

    def forge_from_csv(self, creative_rows: list[CreativeAssetRow], max_prompts: int = 10) -> PromptBatch:
        """Generate prompts directly from creative rows (without DNA analysis)."""
        items = []
        for row in creative_rows:
            items.append({
                "creative_id": row.asset_id or row.creative_name,
                "project": row.game,
                "hook_type": row.hook_type or "unknown",
                "emotion": _infer_emotion(row.hook_type, row.creative_name),
                "predicted_scalability": 0.7,
                "roi": float(row.roas or 0),
                "spend": float(row.spend or 0),
                "ctr": float(row.ctr or 0),
                "cvr": float(row.cvr or 0),
                "channel": row.channel,
                "creative_name": row.creative_name or "",
            })
        return self._forge(items, max_prompts)

    def forge_from_manual(
        self,
        hook_types: list[str],
        emotions: list[str] | None = None,
        max_prompts: int = 5,
    ) -> PromptBatch:
        """Generate prompts from manually specified hook types and emotions."""
        from datetime import datetime

        emotions = emotions or [_infer_emotion(h, "") for h in hook_types]
        prompts: list[ImagePrompt] = []
        for i, (hook, emotion) in enumerate(zip(hook_types, emotions)):
            prompt_text = self._build_prompt(hook, emotion)
            prompts.append(ImagePrompt(
                prompt_id=f"manual_{i+1:03d}",
                project=self._game,
                hook_type=hook,
                emotion=emotion,
                target_platform="Facebook",
                prompt_text=prompt_text,
                negative_prompt=self._build_negative(),
                reference_elements=self._visual["key_elements"][:5],
                expected_ctr_range="2.0%-5.0%",
                expected_cvr_range="15%-30%",
            ))

        return PromptBatch(
            project=self._game,
            generated_at=datetime.now().isoformat(),
            total_prompts=len(prompts),
            prompts=prompts,
        )

    # ----- winner-fission path (real visual DNA, not template fill-in) -----

    def forge_from_winner_dna(
        self,
        winner_items: list[dict[str, Any]],
        max_prompts: int = 6,
    ) -> PromptBatch:
        """Generate variation prompts from REAL winner visual DNA.

        This is the path that replaces template fill-in: each prompt is anchored
        to a real winner's visual description (its visual_dna) and varies only
        ONE secondary axis while keeping the proven winner core intact. Each
        prompt also carries the winner's CDN url so the image generator can do
        true img2img variation instead of text-only generation.

        Args:
            winner_items: items from winner_visual_dna.json, each shaped as
                {"creative_id": ..., "cdn_url": ..., "visual_dna": {...}}.
            max_prompts: cap on total prompts across all winners.

        Variation axes (each prompt picks one):
            - companion_creature: swap the side creature (dragon/owl/fox/spirit)
            - character_action: change what the witch is doing
            - collection_copy: rewrite the "N+ to collect" copy
            - scene_setting: change the background scene
            - palette_shift: nudge the proven palette warmer/cooler
        """
        from datetime import datetime

        if not winner_items:
            return PromptBatch(
                project=self._game,
                generated_at=datetime.now().isoformat(),
                total_prompts=0,
                prompts=[],
            )

        prompts: list[ImagePrompt] = []
        idx = 0
        # Rotate through axes so a single winner produces diverse variations,
        # and rotate through winners so no winner dominates.
        # Variation axes for TRUE fission (different enough to test, similar enough to win).
        # Each axis creates a recognizably different ad while inheriting the winner's DNA.
        # We use the reference image as style guide, NOT as a clone template.
        axes = [
            ("hook_angle", [
                "curiosity hook: show a half-hidden mystery egg, text 'What's Inside?'",
                "urgency hook: add a countdown timer, text 'Merge Before Time Runs Out!'",
                "challenge hook: show a failed merge with messy board, text 'Can You Fix This?'",
                "reward hook: show a rare legendary creature emerging, text 'You Got Lucky!'",
                "progression hook: show before→after merge transformation, text 'Watch It Grow!'",
            ]),
            ("composition", [
                "split-screen: left side messy before, right side perfect after merge",
                "close-up hero: single magnificent creature filling 70% of frame, game UI minimal",
                "gameplay focus: merge board dominant, witch small in corner pointing at it",
                "cinematic wide: full scene with witch, creatures, castle, magical effects in landscape",
                "vertical scroll: three-tier top-to-bottom showing merge stages with arrows",
            ]),
            ("scene_moment", [
                "the moment of merge: items glowing mid-combination, sparks flying",
                "the reveal: curtain/portal opening to show a new legendary creature",
                "the collection: witch surrounded by shelves of collected creatures, proud pose",
                "the quest start: witch reading a map, pointing toward adventure, fresh journey",
                "the celebration: confetti, level-up glow, 'New Record!' banner",
            ]),
            ("creature_focus", [
                "baby dragon center stage, witch nurturing it",
                "a single massive legendary creature dwarfing the witch",
                "three different creatures showing evolution stages (baby→adult→legendary)",
                "a swarm of tiny cute creatures surrounding a confused witch",
                "no creatures — focus on mysterious glowing eggs waiting to hatch",
            ]),
            ("mood_lighting", [
                "bright daylit magical forest, warm sunbeams, cheerful and inviting",
                "mysterious midnight with glowing mushrooms and fireflies, curiosity-driven",
                "stormy dramatic sky with lightning illuminating the scene, urgent and epic",
                "cozy candlelit interior, witch's study, warm amber tones, intimate feel",
                "neon magical glow, bioluminescent everything, futuristic fantasy vibe",
            ]),
        ]

        for slot in range(max_prompts):
            winner = winner_items[slot % len(winner_items)]
            dna = winner.get("visual_dna") or {}
            if not dna or "error" in dna:
                continue
            axis_name, menu = axes[slot % len(axes)]
            variation_value = menu[(slot // len(axes)) % len(menu)]

            prompt_text = self._build_winner_variation_prompt(dna, axis_name, variation_value)
            reference_url = str(winner.get("cdn_url") or "").strip()

            prompts.append(ImagePrompt(
                prompt_id=f"winner_{idx:03d}",
                project=self._game,
                hook_type=str(dna.get("hook_type") or "collection"),
                emotion=str(dna.get("mood") or "satisfaction"),
                target_platform="Facebook",
                prompt_text=prompt_text,
                negative_prompt=self._build_negative(),
                reference_elements=list(dna.get("standout_features") or [])[:5],
                reference_image_url=reference_url,
                variation_axis=f"{axis_name}: {variation_value}",
            ))
            idx += 1

        return PromptBatch(
            project=self._game,
            generated_at=datetime.now().isoformat(),
            total_prompts=len(prompts),
            prompts=prompts,
        )

    def _build_winner_variation_prompt(
        self,
        dna: dict[str, Any],
        axis_name: str,
        variation_value: str,
    ) -> str:
        """Build a TRUE fission prompt: reference the winner's style, create a different ad.

        Unlike the old "KEEP EXACTLY + CHANGE ONLY" approach (which produced near-clones),
        this tells the model to use the winner image as a visual style reference while
        generating a NEW composition/direction — recognizably same brand, meaningfully
        different creative that could win on its own.
        """
        # Winner DNA used as style anchor, not rigid template
        subject = str(dna.get("subject") or "a witch character in a magical setting")
        palette = str(dna.get("palette") or self._visual["palette"])
        mood = str(dna.get("mood") or "magical, inviting")
        standout = dna.get("standout_features") or []
        overlay = str(dna.get("overlay_text") or "")

        # Style anchor: what to INHERIT from the winner
        style_brief = (
            f"Reference style from the winning image:\n"
            f"- Art style and rendering quality: {'; '.join(str(s) for s in standout[:2]) if standout else 'high-quality fantasy game art'}\n"
            f"- Color palette: {palette}\n"
            f"- Visual mood: {mood}\n"
            f"- Brand: {self._game} merge puzzle game ad\n"
        )
        if overlay:
            style_brief += f"- The winner used overlay text like: \"{overlay}\"\n"

        # Creative direction: what's NEW/DIFERENT in this variation
        return (
            f"Create a NEW Facebook ad for {self._game}, inspired by the reference winner image "
            f"but with a fresh creative direction. Mobile portrait 9:16, professional game ad quality.\n\n"
            f"{style_brief}\n"
            f"CREATIVE DIRECTION for this variation:\n"
            f"{variation_value}\n\n"
            f"IMPORTANT: This should look like a DIFFERENT ad in the same campaign — "
            f"not a copy of the reference. Change the composition, the moment, the focal point. "
            f"Same brand feel, different creative execution.\n"
            f"Do NOT add watermarks, realistic photos, or unrelated UI elements."
        )

    # ----- internal -----

    def _forge(self, items: list[dict[str, Any]], max_prompts: int) -> PromptBatch:
        """Core forge logic: select winners → classify hooks → generate prompts."""
        from datetime import datetime

        # 1. Select winning patterns: sort by scalability × ROI
        scored = []
        for item in items:
            roi = float(item.get("roi") or 0)
            scalability = float(item.get("predicted_scalability") or 0)
            spend = float(item.get("spend") or 0)
            score = roi * 0.5 + scalability * 0.3 + min(spend / 1000, 1.0) * 0.2
            scored.append((score, item))
        scored.sort(key=lambda x: x[0], reverse=True)

        winners = [item for _, item in scored[:max_prompts]]

        # 2. Group by hook_type + emotion, diversify
        hook_emotion_seen: set[tuple[str, str]] = set()
        prompts: list[ImagePrompt] = []
        prompt_idx = 0

        for item in winners:
            hook = str(item.get("hook_type") or "reward").strip().lower()
            emotion = str(item.get("emotion") or _infer_emotion(hook, "")).strip()

            # Normalize to known hook types
            hook = _normalize_hook(hook)

            # Diversify: skip if we already have this combination
            key = (hook, emotion)
            if key in hook_emotion_seen and len(prompts) >= 3:
                continue
            hook_emotion_seen.add(key)

            prompt_text = self._build_prompt(hook, emotion)
            channel = str(item.get("channel") or "Facebook")

            prompts.append(ImagePrompt(
                prompt_id=f"forge_{prompt_idx:03d}",
                project=str(item.get("project") or self._game),
                hook_type=hook,
                emotion=emotion,
                target_platform=channel,
                prompt_text=prompt_text,
                negative_prompt=self._build_negative(),
                reference_elements=self._visual["key_elements"][:5],
                expected_ctr_range=_estimate_ctr(item),
                expected_cvr_range=_estimate_cvr(item),
            ))
            prompt_idx += 1

        return PromptBatch(
            project=self._game,
            generated_at=datetime.now().isoformat(),
            total_prompts=len(prompts),
            prompts=prompts,
        )

    def _build_prompt(self, hook_type: str, emotion: str) -> str:
        """Build a DALL-E / Stable Diffusion prompt from hook + visual context."""
        v = self._visual

        # Try template match
        template = HOOK_PROMPT_TEMPLATES.get(hook_type)
        if template:
            return template.format(
                game=self._game,
                palette=v["palette"],
                mood=v.get("mood", "engaging"),
                cta=v.get("cta_text", "Play Now!"),
            )

        # Fallback: build from parts
        elements = ", ".join(v["key_elements"][:4])
        return (
            f"A high-quality mobile game ad screenshot for {self._game}. "
            f"Style: {v['genre']}, {v['mood']} atmosphere. "
            f"Color palette: {v['palette']}. "
            f"Key visual elements: {elements}. "
            f"Hook: {hook_type} ({emotion}). "
            f"Bold overlay text relevant to {hook_type}. "
            f"CTA button: '{v.get('cta_text', 'Play Now!')}'. "
            f"UI style: {v['ui_style']}. "
            f"Mobile portrait 9:16 aspect ratio. Professional game ad quality."
        )

    def _build_negative(self) -> str:
        return (
            "blurry, low quality, pixelated, text errors, watermark, "
            "realistic photo, NSFW, violence, gore, distorted faces, "
            "tiny text, cluttered layout, dark underexposed, oversaturated"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _normalize_hook(hook: str) -> str:
    hook = hook.lower()
    mapping = {
        "crisis": "crisis", "危机": "crisis", "rescue": "crisis", "save": "crisis",
        "reward": "reward", "爽点": "reward", "win": "reward", "success": "reward",
        "twist": "twist", "反转": "twist", "unexpected": "twist", "fail": "twist",
        "comparison": "comparison", "对比": "comparison", "before_after": "comparison",
        "curiosity": "curiosity", "好奇": "curiosity", "mystery": "curiosity",
        "collection": "collection", "收集": "collection",
    }
    return mapping.get(hook, "reward")


def _infer_emotion(hook_type: str, creative_name: str) -> str:
    text = f"{hook_type} {creative_name}".lower()
    if any(w in text for w in ("救", "danger", "fail", "wrong", "lose")):
        return "anxiety"
    if any(w in text for w in ("爽", "win", "success", "clear", "level")):
        return "satisfaction"
    if any(w in text for w in ("cozy", "home", "治愈", "relax", "garden")):
        return "healing"
    if any(w in text for w in ("mystery", "secret", "hidden", "unlock")):
        return "curiosity"
    return "satisfaction"


def _estimate_ctr(item: dict[str, Any]) -> str:
    ctr = float(item.get("ctr") or 0)
    if ctr > 0.04:
        return "4.0%-6.0%"
    if ctr > 0.02:
        return "2.0%-4.0%"
    return "1.0%-3.0%"


def _estimate_cvr(item: dict[str, Any]) -> str:
    cvr = float(item.get("cvr") or 0)
    if cvr > 0.25:
        return "25%-40%"
    if cvr > 0.15:
        return "15%-25%"
    return "10%-20%"


# ---------------------------------------------------------------------------
# CLI helper
# ---------------------------------------------------------------------------
def save_prompt_batch(batch: PromptBatch, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"prompt_batch_{batch.generated_at[:10].replace('-', '')}.json"
    data = {
        "project": batch.project,
        "generated_at": batch.generated_at,
        "total_prompts": batch.total_prompts,
        "prompts": [asdict(p) for p in batch.prompts],
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
