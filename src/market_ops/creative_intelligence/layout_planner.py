"""Creative Layout Planner V1

在生成图片之前，先生成 UA Creative Layout Blueprint。

核心职责：
  - 规划广告中每个元素的精确位置
  - 确保 AI 理解：哪个位置放玩法、哪个位置放奖励、哪个位置展示升级
  - 将抽象的策略转化为具体的视觉布局指令

输出四层区域：
  1. Hook Area      — Top，强 CTA + 玩法诱因
  2. Gameplay Area  — Center，merge grid + items + combination
  3. Reward Area    — Right，upgraded creature / rare item
  4. Character Area — 保留 Winner DNA 角色，但必须参与动作
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class LayoutRegion:
    position: str
    element: str
    description: str = ""
    size_hint: str = ""  # e.g. "40% width", "upper third"


@dataclass(slots=True)
class LayoutBlueprint:
    layout_type: str
    regions: list[LayoutRegion] = field(default_factory=list)
    text_area: dict[str, str] = field(default_factory=dict)
    character_area: dict[str, str] = field(default_factory=dict)
    must_show_elements: list[str] = field(default_factory=list)
    avoid_elements: list[str] = field(default_factory=list)
    layout_description: str = ""  # ASCII art + text description


# ---------------------------------------------------------------------------
# Layout Planner
# ---------------------------------------------------------------------------
class CreativeLayoutPlanner:
    """Plans the spatial structure of a UA performance creative before generation."""

    # Predefined layout templates
    LAYOUT_TEMPLATES = {
        "before_after_merge": {
            "name": "Before → Merge → After (Triptych)",
            "description": (
                "Horizontal triptych layout: LEFT shows low-level items, CENTER shows "
                "active merge action with explosion/glow, RIGHT shows legendary upgraded reward. "
                "Top banner carries strong hook text. Character anchors the composition from "
                "bottom or background."
            ),
            "regions": [
                LayoutRegion(
                    "top",
                    "hook_text_banner",
                    "Bold advertising headline in gothic fantasy typography. Must be instantly readable.",
                    "full width, upper 15%",
                ),
                LayoutRegion(
                    "left",
                    "low_level_items",
                    "Two identical low-tier merge items ready to combine. Clear and recognizable.",
                    "30% width, left side",
                ),
                LayoutRegion(
                    "center",
                    "merge_action",
                    "Active merge explosion/magical glow where two items meet. Sparkle, particles, energy.",
                    "40% width, center focal point",
                ),
                LayoutRegion(
                    "right",
                    "legendary_reward",
                    "High-tier upgraded creature or rare item — the satisfying payoff. Gold glow, premium feel.",
                    "30% width, right side",
                ),
                LayoutRegion(
                    "bottom",
                    "character_anchor",
                    "Witch character positioned to guide eye toward merge action. Hands extended, engaged.",
                    "full width, lower 20%",
                ),
            ],
            "must_show": [
                "visible merge grid or merge board",
                "two low-level items on the left",
                "active merge explosion/glow in center",
                "legendary upgraded reward on the right",
                "upgrade arrow or glow connecting left→center→right",
                "bold hook text at top",
                "witch character engaged with merge action (not static portrait)",
            ],
            "avoid": [
                "poster or splash screen composition",
                "character filling entire frame",
                "no visible gameplay mechanics",
                "missing before→after sequence",
                "static character standing pose",
                "abstract magical effects without literal items",
                "reward hidden or too small",
                "no text overlay",
            ],
        },
        "vertical_progression": {
            "name": "Vertical Progression Stack",
            "description": (
                "Vertical stack: TOP shows starting item, MIDDLE shows merge action, "
                "BOTTOM shows final reward. Character frames the sides. Strong top-to-bottom "
                "eye flow mimics mobile screen scroll."
            ),
            "regions": [
                LayoutRegion(
                    "top",
                    "starting_items",
                    "Low-level items at top with 'BEFORE' energy. Smaller, dimmer.",
                    "full width, upper 25%",
                ),
                LayoutRegion(
                    "center",
                    "merge_explosion",
                    "Dramatic merge explosion at vertical center. Maximum visual energy. Sparkles.",
                    "full width, center 35%",
                ),
                LayoutRegion(
                    "bottom",
                    "final_reward",
                    "Legendary reward at bottom with 'AFTER' glow. Larger, brighter, gold accents.",
                    "full width, lower 25%",
                ),
                LayoutRegion(
                    "left_edge",
                    "character_left",
                    "Witch on left side guiding eye downward. Hand pointing toward progression.",
                    "15% width, left edge",
                ),
                LayoutRegion(
                    "right_edge",
                    "character_right",
                    "Witch on right side (or magical familiar) framing the progression.",
                    "15% width, right edge",
                ),
            ],
            "must_show": [
                "vertical before→after stack",
                "merge explosion at center",
                "legendary reward glowing at bottom",
                "upgrade arrow or energy flow from top to bottom",
                "character framing the progression (not blocking it)",
                "bold text overlay showing progression label",
            ],
            "avoid": [
                "horizontal poster composition",
                "character blocking the progression",
                "no clear top-to-bottom flow",
                "missing merge action",
                "reward same size as starting item",
            ],
        },
        "character_driven_merge": {
            "name": "Character-Driven Merge Moment",
            "description": (
                "Character is the hero: witch actively performing a merge spell. "
                "Merge board is visible in the scene (not hidden). Character's expression "
                "and pose convey excitement/satisfaction. Reward emerges from the merge."
            ),
            "regions": [
                LayoutRegion(
                    "center",
                    "witch_hero",
                    "Witch is the dominant focal point, actively casting merge spell. Dynamic pose.",
                    "50% width, center-left",
                ),
                LayoutRegion(
                    "right",
                    "merge_board_visible",
                    "Merge board visible with two items combining. NOT hidden behind character.",
                    "40% width, right side",
                ),
                LayoutRegion(
                    "top",
                    "hook_text",
                    "Strong advertising text overlay. 'MERGE & WATCH THE MAGIC' style.",
                    "full width, upper 15%",
                ),
                LayoutRegion(
                    "bottom_right",
                    "reward_emerging",
                    "Legendary creature/item emerging from merge. Gold glow, sparkles.",
                    "30% width, lower right",
                ),
            ],
            "must_show": [
                "witch in dynamic active pose (not static portrait)",
                "merge board clearly visible in scene",
                "two items actively merging",
                "reward emerging with glow effect",
                "bold advertising text overlay",
            ],
            "avoid": [
                "character filling frame with no gameplay",
                "merge board hidden or obscured",
                "static standing pose",
                "no visible merge action",
                "poster/splash composition",
            ],
        },
        "split_screen_compare": {
            "name": "Split-Screen Comparison",
            "description": (
                "LEFT half: low-level / failed state. RIGHT half: legendary / success state. "
                "Center divider shows merge action. Strong contrast between before and after."
            ),
            "regions": [
                LayoutRegion(
                    "left_half",
                    "before_state",
                    "DIMMER, smaller items. 'Level 1' energy. Common creature.",
                    "45% width, left",
                ),
                LayoutRegion(
                    "center_divider",
                    "merge_action",
                    "Merge explosion acting as divider between before/after. Energy burst.",
                    "10% width, center",
                ),
                LayoutRegion(
                    "right_half",
                    "after_state",
                    "BRIGHTER, larger legendary reward. 'MAX LEVEL' energy. Gold glow.",
                    "45% width, right",
                ),
                LayoutRegion(
                    "top",
                    "hook_text",
                    "Comparison headline: 'Level 1 → Level 10' or 'Common → Legendary'.",
                    "full width, top",
                ),
            ],
            "must_show": [
                "clear left/right split",
                "dramatic contrast between before and after",
                "merge explosion at center divider",
                "upgrade arrow or glow connecting halves",
                "legendary reward significantly larger/brighter than starting item",
                "comparison text overlay",
            ],
            "avoid": [
                "no contrast between sides",
                "before and after look the same",
                "missing center merge action",
                "poster composition without split",
                "character portrait without gameplay",
            ],
        },
    }

    def __init__(self, project: str = "P04 Witch") -> None:
        self._project = project

    # ----- public API -----

    def plan(
        self,
        visual_dna: dict[str, Any],
        product_type: str = "merge_iap",
        creative_mode: str = "gameplay_transformation",
        layout_mode: str = "before_after_merge",
    ) -> LayoutBlueprint:
        """Generate a Layout Blueprint from Winner DNA and product context."""

        # Select layout template
        template = self.LAYOUT_TEMPLATES.get(layout_mode)
        if not template:
            layout_mode = "before_after_merge"
            template = self.LAYOUT_TEMPLATES["before_after_merge"]

        # Extract DNA components for customization
        subject = visual_dna.get("subject", "a witch character")
        overlay_text = visual_dna.get("overlay_text", "Merge & Watch the Magic")
        hook_type = visual_dna.get("hook_type", "collection")
        character_pose = visual_dna.get("character_pose", "witch casting spell")

        # Customize regions based on DNA
        regions = []
        for reg in template["regions"]:
            desc = reg.description
            # Inject DNA-specific details
            if "character" in reg.element.lower() or "witch" in desc.lower():
                desc = desc.replace("Witch", subject.split()[0].capitalize())
                desc += f" Pose reference: {character_pose}."
            if "hook_text" in reg.element.lower():
                desc += f" Text content: '{overlay_text}'."
            regions.append(
                LayoutRegion(
                    position=reg.position,
                    element=reg.element,
                    description=desc,
                    size_hint=reg.size_hint,
                )
            )

        # Customize must_show / avoid based on creative_mode
        must_show = list(template["must_show"])
        avoid = list(template["avoid"])

        if creative_mode == "gameplay_transformation":
            must_show.extend([
                "instantly understandable merge mechanic within 3 seconds",
                "upgrade arrow or glow effect connecting transformation",
            ])
            avoid.extend([
                "abstract magical effects without literal merge items",
                "merge board too small or hidden",
            ])
        elif creative_mode == "character_focus":
            must_show.extend([
                "character expression conveys excitement or satisfaction",
                "character actively engaged with merge action (not just present)",
            ])
            avoid.extend([
                "character filling entire frame with no gameplay context",
                "static portrait pose",
            ])

        # Build ASCII layout visualization
        ascii_layout = self._build_ascii_layout(layout_mode, regions, overlay_text)

        return LayoutBlueprint(
            layout_type=layout_mode,
            regions=regions,
            text_area={
                "position": "top",
                "copy": overlay_text,
                "style": "bold gothic fantasy typography, high contrast against background",
                "requirements": "instantly readable at thumbnail size, no more than 6 words",
            },
            character_area={
                "position": "bottom or framing",
                "role": "guide eye toward merge action",
                "pose_requirement": f"{character_pose}, actively engaged, not static",
                "expression": "excited, satisfied, or focused on merge result",
            },
            must_show_elements=must_show,
            avoid_elements=avoid,
            layout_description=ascii_layout,
        )

    def save_blueprint(
        self,
        blueprint: LayoutBlueprint,
        output_dir: Path | str,
    ) -> dict[str, Path]:
        """Save layout blueprint artifacts to output directory."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        # layout_blueprint.json
        bp_path = out / "layout_blueprint.json"
        bp_data = {
            "layout_type": blueprint.layout_type,
            "regions": [asdict(r) for r in blueprint.regions],
            "text_area": blueprint.text_area,
            "character_area": blueprint.character_area,
            "must_show_elements": blueprint.must_show_elements,
            "avoid_elements": blueprint.avoid_elements,
            "layout_description": blueprint.layout_description,
        }
        bp_path.write_text(json.dumps(bp_data, indent=2, ensure_ascii=False), encoding="utf-8")

        # layout_report.md
        report_path = out / "layout_report.md"
        report = self._build_report(blueprint)
        report_path.write_text(report, encoding="utf-8")

        return {
            "layout_blueprint": bp_path,
            "layout_report": report_path,
        }

    # ----- internal -----

    def _build_ascii_layout(self, layout_mode: str, regions: list[LayoutRegion], overlay_text: str) -> str:
        if layout_mode == "before_after_merge":
            return (
                "+----------------------------------------------------------+\n"
                "|  [HOOK TEXT]  \"{text}\"                                    |\n"
                "+----------------------------------------------------------+\n"
                "|                                                            |\n"
                "|  [LEFT]          [CENTER]            [RIGHT]              |\n"
                "|  Low Level       Merge Action        Legendary           |\n"
                "|  Item A          ✨🔥✨              Reward              |\n"
                "|  Item B          ↑                  (Dragon)            |\n"
                "|                  Evolution                                |\n"
                "|                                                            |\n"
                "|  [BOTTOM: Witch Character guiding eye to merge action]    |\n"
                "+----------------------------------------------------------+"
            ).format(text=overlay_text[:30])
        elif layout_mode == "vertical_progression":
            return (
                "+----------------------------------------------------------+\n"
                "|  [TOP] Starting Items (BEFORE)                            |\n"
                "|       🥚 🥚                                               |\n"
                "|         ↓                                                 |\n"
                "|  [CENTER] MERGE EXPLOSION 🔥✨                            |\n"
                "|         ↓                                                 |\n"
                "|  [BOTTOM] Legendary Reward (AFTER)                        |\n"
                "|       🐉✨                                                |\n"
                "|  [SIDES: Character framing progression]                   |\n"
                "+----------------------------------------------------------+"
            )
        elif layout_mode == "character_driven_merge":
            return (
                "+----------------------------------------------------------+\n"
                "|  [TOP] \"{text}\"                                          |\n"
                "+----------------------------------------------------------+\n"
                "|                                                            |\n"
                "|  [CENTER-LEFT]        [RIGHT]                             |\n"
                "|  Witch (hero)         Merge Board                         |\n"
                "|  casting spell        with items merging                  |\n"
                "|                       ↓                                   |\n"
                "|              [BOTTOM-RIGHT] Reward emerges               |\n"
                "+----------------------------------------------------------+"
            ).format(text=overlay_text[:30])
        elif layout_mode == "split_screen_compare":
            return (
                "+----------------------------------------------------------+\n"
                "|  [TOP] \"{text}\"                                          |\n"
                "+----------------------------------------------------------+\n"
                "|  [LEFT HALF]    | [CENTER] |    [RIGHT HALF]             |\n"
                "|  BEFORE         | MERGE    |    AFTER                    |\n"
                "|  dim, small     | 🔥✨     |    bright, large            |\n"
                "|  common item    | divider  |    legendary                |\n"
                "+----------------------------------------------------------+"
            ).format(text=overlay_text[:30])
        return "Layout visualization not available for this mode."

    def _build_report(self, blueprint: LayoutBlueprint) -> str:
        lines = [
            "# Creative Layout Planner V1 Report",
            "",
            f"**Layout Type**: {blueprint.layout_type}",
            "",
            "## Layout Visualization",
            "```",
            blueprint.layout_description,
            "```",
            "",
            "## Regions",
        ]
        for reg in blueprint.regions:
            lines.append(f"### {reg.position.upper()}: {reg.element}")
            lines.append(f"- Description: {reg.description}")
            lines.append(f"- Size: {reg.size_hint}")
            lines.append("")

        lines.extend([
            "## Text Area",
            f"- Position: {blueprint.text_area.get('position', 'top')}",
            f"- Copy: {blueprint.text_area.get('copy', 'N/A')}",
            f"- Style: {blueprint.text_area.get('style', 'N/A')}",
            "",
            "## Character Area",
            f"- Position: {blueprint.character_area.get('position', 'N/A')}",
            f"- Role: {blueprint.character_area.get('role', 'N/A')}",
            f"- Pose: {blueprint.character_area.get('pose_requirement', 'N/A')}",
            "",
            "## Must-Show Elements",
        ])
        for item in blueprint.must_show_elements:
            lines.append(f"- {item}")

        lines.extend([
            "",
            "## Avoid Elements",
        ])
        for item in blueprint.avoid_elements:
            lines.append(f"- {item}")

        return "\n".join(lines)
