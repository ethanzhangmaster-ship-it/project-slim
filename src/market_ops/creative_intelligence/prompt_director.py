"""Creative Prompt Director V2

将 Winner Visual DNA + Layout Blueprint 转换成 Performance Creative Strategy Prompt。

核心职责：
  - 不是让 AI 生成「游戏海报」
  - 而是让 AI 生成「可驱动点击和付费的 Facebook UA 广告素材」

新增 V2：
  - 接收 Layout Blueprint 作为输入
  - 将布局约束转化为具体的 prompt 指令
  - 让 AI 理解每个元素在画面中的精确位置

输出四层结构：
  1. Hook Layer        — 前3秒视觉冲击
  2. Gameplay Layer    — 必须展示 merge 玩法
  3. Progression Layer — growth / upgrade / unlock
  4. IAP Intent Layer  — 用户想要 legenday / rare / premium
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class CreativeStrategy:
    creative_type: str
    hook_strategy: str
    gameplay_moment: str
    must_have_elements: list[str] = field(default_factory=list)
    avoid_elements: list[str] = field(default_factory=list)
    generation_prompt: str = ""
    negative_prompt: str = ""
    winner_type: str = ""
    winner_dna_summary: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Prompt Director
# ---------------------------------------------------------------------------
class CreativePromptDirector:
    """Directs AI image generation toward performance UA creative output."""

    # UA 创意类型定义
    CREATIVE_TYPES = {
        "gameplay_transformation": (
            "Show a real merge gameplay moment with visible before→after transformation, "
            "merge board, upgrade explosion, and reward reveal."
        ),
        "character_focus": (
            "Character-driven ad where the witch is the hero, but MUST include "
            "merge gameplay elements (board, items, upgrade arrows) as supporting context. "
            "NOT a standalone character portrait."
        ),
        "poster": (
            "Game poster / splash screen style. Best for store assets, NOT for UA performance. "
            "High production value but may lack gameplay clarity."
        ),
    }

    # Style Constraint — 无论什么 creative_type 都强制附加
    _STYLE_CONSTRAINT = (
        "Style: AAA casual mobile game ADVERTISEMENT, 3D cartoon rendering, "
        "premium mobile game ad quality. "
        "This is NOT a game poster. NOT a splash screen. NOT character artwork. "
        "NOT a cinematic wallpaper. "
        "It IS a Facebook user acquisition performance creative designed to drive clicks and installs."
    )

    # Gameplay Constraint — gameplay_transformation 模式强制附加
    _GAMEPLAY_CONSTRAINT = (
        "GAMEPLAY REQUIREMENT: Show an actual merge gameplay moment. "
        "A visible merge board or merge grid must be present. "
        "Two items MUST be shown transforming into a higher-level reward. "
        "Clear BEFORE and AFTER progression must be visible. "
        "Upgrade arrows or glow effects connecting the transformation are REQUIRED. "
        "The merge mechanic must be instantly understandable within 3 seconds."
    )

    # Advertising Constraint — 所有模式都强制附加
    _ADVERTISING_CONSTRAINT = (
        "ADVERTISING REQUIREMENT: Designed specifically for Facebook user acquisition. "
        "Instantly understandable within 3 seconds of viewing. "
        "Strong focal point with high visual contrast. "
        "Clear call-to-action energy even without explicit CTA button. "
        "Optimized for thumb-stopping in a crowded feed. "
        "1:1 square aspect ratio, 1080x1080 pixels."
    )

    # Progression Layer — 所有模式都附加
    _PROGRESSION_CONSTRAINT = (
        "PROGRESSION LAYER: The creative MUST communicate growth, upgrade, unlock, or collection. "
        "Show a satisfying transformation that makes the viewer want to achieve it themselves. "
        "Examples: Level 1 item → Level 10 item, common creature → legendary creature, "
        "small cottage → grand castle, seed → blooming magical plant."
    )

    # IAP Intent Layer — 所有模式都附加
    _IAP_INTENT_CONSTRAINT = (
        "IAP INTENT LAYER: Visually communicate the desire for premium rewards. "
        "Show legendary creatures, rare glowing items, powerful upgrades, or exclusive content. "
        "The reward must look desirable enough that viewers want to merge/play to obtain it. "
        "Gold accents, sparkle effects, and glow highlights reinforce premium value."
    )

    # Hook strategies by hook_type
    _HOOK_STRATEGIES = {
        "collection": (
            "HOOK: 'Merge & Watch the Magic' — show a dramatic merge transformation "
            "where two items combine with a magical explosion into a rare reward. "
            "The viewer's curiosity is triggered by the mystery of what will emerge."
        ),
        "crisis": (
            "HOOK: 'Can You Fix This?' — show a messy merge board with a timer, "
            "chaotic items, and a worried witch. Creates urgency and challenge appeal."
        ),
        "reward": (
            "HOOK: 'Best Merge Ever!' — show a satisfying combo merge with sparkle effects, "
            "level-up glow, and a legendary creature emerging. Pure dopamine hit."
        ),
        "twist": (
            "HOOK: 'Don't Make This Mistake!' — split-screen showing a failed merge vs perfect merge. "
            "Creates curiosity and learning desire."
        ),
        "comparison": (
            "HOOK: 'Level 1 → Level 10 in ONE Merge!' — dramatic before/after showing "
            "low-level items transforming into epic versions. Progression satisfaction."
        ),
        "curiosity": (
            "HOOK: 'What Happens When You Merge These?' — mysterious hidden item partially revealed. "
            "Question overlay triggers click curiosity."
        ),
    }

    # Default negative prompt — what to AVOID
    _NEGATIVE_PROMPT = (
        "game poster, splash screen, character portrait, static fantasy illustration, "
        "cinematic wallpaper, beautiful landscape without gameplay, no UI elements, "
        "no progression indicators, standalone character art, concept art, "
        "2D flat illustration, anime style, realistic photography, blurry, low quality, "
        "pixelated, text errors, watermark, NSFW, violence, gore, distorted faces, "
        "tiny text, cluttered layout, dark underexposed, oversaturated"
    )

    def __init__(self, project: str = "P04 Witch") -> None:
        self._project = project

    # ----- public API -----

    def direct(
        self,
        visual_dna: dict[str, Any],
        winner_type: str = "balanced",
        creative_mode: str = "gameplay_transformation",
        layout_blueprint: Any | None = None,
    ) -> CreativeStrategy:
        """Convert Winner Visual DNA + Layout Blueprint into a UA Performance Creative Strategy."""

        # Validate creative_mode
        if creative_mode not in self.CREATIVE_TYPES:
            creative_mode = "gameplay_transformation"

        # Extract DNA components
        subject = visual_dna.get("subject", "a witch character")
        composition = visual_dna.get("composition", "centered hero shot")
        palette = visual_dna.get("palette", "deep purple and gold")
        lighting = visual_dna.get("lighting", "magical glowing effects")
        overlay_text = visual_dna.get("overlay_text", "Merge & Watch the Magic")
        character_pose = visual_dna.get("character_pose", "witch casting spell")
        mood = visual_dna.get("mood", "mysterious and magical")
        hook_type = visual_dna.get("hook_type", "collection")
        standout = visual_dna.get("standout_features", [])
        overall = visual_dna.get("overall_summary", "")

        # Build Hook Strategy
        hook_strategy = self._build_hook_strategy(hook_type, overlay_text, standout)

        # Build Gameplay Moment description
        gameplay_moment = self._build_gameplay_moment(
            creative_mode, subject, composition, standout
        )

        # Build Must-Have Elements (merge with layout if available)
        must_have = self._build_must_have(creative_mode, overlay_text)
        avoid = self._build_avoid(creative_mode)

        if layout_blueprint is not None:
            must_have.extend(layout_blueprint.must_show_elements)
            avoid.extend(layout_blueprint.avoid_elements)
            # Deduplicate
            must_have = list(dict.fromkeys(must_have))
            avoid = list(dict.fromkeys(avoid))

        # Assemble Generation Prompt
        generation_prompt = self._assemble_prompt(
            creative_mode=creative_mode,
            subject=subject,
            composition=composition,
            palette=palette,
            lighting=lighting,
            character_pose=character_pose,
            mood=mood,
            overlay_text=overlay_text,
            standout=standout,
            overall=overall,
            hook_strategy=hook_strategy,
            gameplay_moment=gameplay_moment,
            layout_blueprint=layout_blueprint,
        )

        # Assemble Negative Prompt
        negative_prompt = self._assemble_negative(creative_mode, layout_blueprint)

        return CreativeStrategy(
            creative_type=creative_mode,
            hook_strategy=hook_strategy,
            gameplay_moment=gameplay_moment,
            must_have_elements=must_have,
            avoid_elements=avoid,
            generation_prompt=generation_prompt,
            negative_prompt=negative_prompt,
            winner_type=winner_type,
            winner_dna_summary={
                "subject": subject,
                "palette": palette,
                "overlay_text": overlay_text,
                "mood": mood,
                "hook_type": hook_type,
            },
        )

    def save_strategy(
        self,
        strategy: CreativeStrategy,
        output_dir: Path | str,
    ) -> dict[str, Path]:
        """Save strategy artifacts to output directory."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        # creative_strategy.json
        strategy_path = out / "creative_strategy.json"
        strategy_path.write_text(
            json.dumps(
                {
                    "creative_type": strategy.creative_type,
                    "winner_type": strategy.winner_type,
                    "hook_strategy": strategy.hook_strategy,
                    "gameplay_moment": strategy.gameplay_moment,
                    "must_have_elements": strategy.must_have_elements,
                    "avoid_elements": strategy.avoid_elements,
                    "winner_dna_summary": strategy.winner_dna_summary,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        # generation_prompt.txt
        gen_path = out / "generation_prompt.txt"
        gen_path.write_text(strategy.generation_prompt, encoding="utf-8")

        # negative_prompt.txt
        neg_path = out / "negative_prompt.txt"
        neg_path.write_text(strategy.negative_prompt, encoding="utf-8")

        # director_report.md
        report_path = out / "director_report.md"
        report = self._build_report(strategy)
        report_path.write_text(report, encoding="utf-8")

        return {
            "strategy_json": strategy_path,
            "generation_prompt": gen_path,
            "negative_prompt": neg_path,
            "director_report": report_path,
        }

    # ----- internal builders -----

    def _build_hook_strategy(
        self,
        hook_type: str,
        overlay_text: str,
        standout: list[str],
    ) -> str:
        base = self._HOOK_STRATEGIES.get(hook_type, self._HOOK_STRATEGIES["collection"])
        if overlay_text:
            base += f" Overlay text anchor: '{overlay_text}'."
        if standout:
            standout_str = "; ".join(str(s) for s in standout[:2])
            base += f" Standout hook elements: {standout_str}."
        return base

    def _build_gameplay_moment(
        self,
        creative_mode: str,
        subject: str,
        composition: str,
        standout: list[str],
    ) -> str:
        if creative_mode == "gameplay_transformation":
            return (
                f"The central moment is a merge transformation: two identical items on a merge board "
                f"combine with a magical glow/explosion into a higher-tier reward. "
                f"The witch character is positioned to guide the viewer's eye toward this transformation. "
                f"Composition reference: {composition[:80]}..."
            )
        elif creative_mode == "character_focus":
            return (
                f"The witch character is the hero ({subject}), but the merge board is visible "
                f"in the foreground or background showing an active merge moment. "
                f"The character's pose and expression convey satisfaction from the merge result."
            )
        else:  # poster
            return (
                f"High-impact splash-style composition: {composition[:80]}... "
                f"Premium production value but gameplay elements may be stylized rather than literal."
            )

    def _build_must_have(self, creative_mode: str, overlay_text: str) -> list[str]:
        common = [
            "witch character as focal point",
            "bold overlay text in gothic fantasy typography",
            "rich purple + gold color palette with magical glow",
            "3D cartoon art style, premium mobile game ad quality",
            "1:1 square aspect ratio, 1080x1080",
        ]

        if creative_mode == "gameplay_transformation":
            common.extend([
                "visible merge board or merge grid",
                "two items shown merging into a higher-level reward",
                "before→after progression with upgrade arrows or glow effects",
                "magical transformation explosion or sparkle effect",
                "instantly understandable merge mechanic within 3 seconds",
            ])
        elif creative_mode == "character_focus":
            common.extend([
                "merge board visible as supporting context (not hidden)",
                "at least one merge item or upgrade indicator present",
                "character expression conveys satisfaction or excitement",
            ])

        if overlay_text:
            common.append(f"overlay text similar to: '{overlay_text}'")

        return common

    def _build_avoid(self, creative_mode: str) -> list[str]:
        common = [
            "game poster or splash screen",
            "standalone character portrait without gameplay",
            "static fantasy illustration",
            "cinematic wallpaper without UI/gameplay",
            "beautiful landscape with no progression indicators",
            "2D flat illustration instead of 3D cartoon",
            "realistic photography",
            "no visible merge mechanic",
            "no before→after transformation",
            "generic text without gothic fantasy styling",
        ]

        if creative_mode == "gameplay_transformation":
            common.extend([
                "merge board hidden or too small to read",
                "transformation without clear before/after",
                "missing upgrade arrows or progression indicators",
                "abstract magical effects instead of literal merge gameplay",
            ])

        return common

    def _assemble_prompt(
        self,
        creative_mode: str,
        subject: str,
        composition: str,
        palette: str,
        lighting: str,
        character_pose: str,
        mood: str,
        overlay_text: str,
        standout: list[str],
        overall: str,
        hook_strategy: str,
        gameplay_moment: str,
        layout_blueprint: Any | None = None,
    ) -> str:
        # Creative type description
        type_desc = self.CREATIVE_TYPES.get(creative_mode, "")

        # Standout features text
        standout_text = "\n".join(f"- {s}" for s in standout[:5]) if standout else ""

        # Assemble the full prompt
        parts = [
            f"Create a Facebook mobile game UA performance creative for {self._project}. "
            f"1:1 square aspect ratio, 1080x1080 pixels. {type_desc}",
            "",
            "--- WINNER DNA INHERITANCE ---",
            f"Subject: {subject}",
            f"Composition: {composition}",
            f"Color palette: {palette}",
            f"Lighting: {lighting}",
            f"Character pose: {character_pose}",
            f"Mood: {mood}",
            f"Overlay text reference: \"{overlay_text}\"",
            f"Standout features to preserve:\n{standout_text}" if standout_text else "",
            f"Why this wins: {overall}" if overall else "",
            "",
            "--- CREATIVE STRATEGY ---",
            hook_strategy,
            "",
            f"Gameplay Moment: {gameplay_moment}",
            "",
        ]

        # Inject Layout Blueprint constraints if available
        if layout_blueprint is not None:
            parts.extend([
                "--- EXACT LAYOUT BLUEPRINT (Follow This Precisely) ---",
                f"Layout Type: {layout_blueprint.layout_type}",
                "",
                "SPATIAL REGIONS — Place each element in its designated area:",
            ])
            for reg in layout_blueprint.regions:
                parts.append(f"[{reg.position.upper()}] {reg.element}: {reg.description} (Size: {reg.size_hint})")
            parts.append("")

            if layout_blueprint.text_area:
                ta = layout_blueprint.text_area
                parts.append(
                    f"TEXT AREA — Position: {ta.get('position', 'top')}, "
                    f"Copy: '{ta.get('copy', '')}', Style: {ta.get('style', '')}"
                )
            if layout_blueprint.character_area:
                ca = layout_blueprint.character_area
                parts.append(
                    f"CHARACTER AREA — Position: {ca.get('position', '')}, "
                    f"Role: {ca.get('role', '')}, Pose: {ca.get('pose_requirement', '')}"
                )
            parts.append("")

        parts.extend([
            self._STYLE_CONSTRAINT,
            "",
        ])

        if creative_mode == "gameplay_transformation":
            parts.append(self._GAMEPLAY_CONSTRAINT)
            parts.append("")

        parts.extend([
            self._PROGRESSION_CONSTRAINT,
            "",
            self._IAP_INTENT_CONSTRAINT,
            "",
            self._ADVERTISING_CONSTRAINT,
        ])

        # Filter empty strings and join
        return "\n".join(p for p in parts if p is not None)

    def _assemble_negative(self, creative_mode: str, layout_blueprint: Any | None = None) -> str:
        base = self._NEGATIVE_PROMPT

        if creative_mode == "gameplay_transformation":
            base += (
                ", hidden merge board, too small merge grid, abstract merge effect without "
                "literal items, missing before→after, no upgrade arrows, transformation "
                "without clear progression, character-only with no gameplay"
            )
        elif creative_mode == "character_focus":
            base += (
                ", character filling entire frame with no gameplay context, merge board "
                "completely absent, pure character artwork without game elements"
            )

        # Inject layout-specific avoid elements
        if layout_blueprint is not None and layout_blueprint.avoid_elements:
            extra = ", ".join(layout_blueprint.avoid_elements[:8])
            base += f", {extra}"

        return base

    def _build_report(self, strategy: CreativeStrategy) -> str:
        lines = [
            "# Creative Prompt Director V1 Report",
            "",
            f"**Project**: {self._project}",
            f"**Winner Type**: {strategy.winner_type}",
            f"**Creative Mode**: {strategy.creative_type}",
            "",
            "## Creative Strategy",
            "",
            f"### Hook Strategy\n{strategy.hook_strategy}",
            "",
            f"### Gameplay Moment\n{strategy.gameplay_moment}",
            "",
            "### Must-Have Elements",
        ]
        for item in strategy.must_have_elements:
            lines.append(f"- {item}")

        lines.extend([
            "",
            "### Avoid Elements",
        ])
        for item in strategy.avoid_elements:
            lines.append(f"- {item}")

        lines.extend([
            "",
            "## Generation Prompt",
            "```",
            strategy.generation_prompt,
            "```",
            "",
            "## Negative Prompt",
            "```",
            strategy.negative_prompt,
            "```",
        ])

        return "\n".join(lines)
