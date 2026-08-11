"""Phase 3.0: Composition Planner — layout and spatial arrangement.

Outputs composition tokens: subject position, foreground, background,
negative space, text area, UI area.
"""

from __future__ import annotations

from ..models.prompt_component import PromptComponent


COMPOSITION_TOKENS: dict[str, dict[str, str]] = {
    "center": {
        "subject": "centered main subject",
        "foreground": "reward item in foreground",
        "background": "magical environment background",
        "negative_space": "balanced negative space around subject",
        "text_area": "text-safe zone at top third",
        "ui_area": "UI elements at bottom",
        "layout": "center composition, strong focal point",
    },
    "left_focus": {
        "subject": "main subject on left third",
        "foreground": "reward item on right, balanced",
        "background": "depth background extending right",
        "negative_space": "right side negative space for text",
        "text_area": "text-safe zone on right",
        "ui_area": "bottom right UI elements",
        "layout": "left-weighted composition, text-ready right side",
    },
    "right_focus": {
        "subject": "main subject on right third",
        "foreground": "reward item on left, balanced",
        "background": "depth background extending left",
        "negative_space": "left side negative space for text",
        "text_area": "text-safe zone on left",
        "ui_area": "bottom left UI elements",
        "layout": "right-weighted composition, text-ready left side",
    },
    "diagonal": {
        "subject": "subject on diagonal line",
        "foreground": "reward item on lower diagonal",
        "background": "depth along diagonal",
        "negative_space": "corners for text placement",
        "text_area": "top-left or bottom-right text zone",
        "ui_area": "opposite corner UI",
        "layout": "dynamic diagonal composition",
    },
    "triangle": {
        "subject": "subject at apex of triangle",
        "foreground": "two reward items at base corners",
        "background": "depth behind triangle",
        "negative_space": "outside triangle for text",
        "text_area": "top or bottom outside triangle",
        "ui_area": "bottom center UI",
        "layout": "stable triangular composition",
    },
    "rule_of_thirds": {
        "subject": "subject at thirds intersection",
        "foreground": "reward item at opposite intersection",
        "background": "depth across frame",
        "negative_space": "remaining third for text",
        "text_area": "empty third zone",
        "ui_area": "bottom third UI",
        "layout": "rule of thirds composition",
    },
    "symmetrical": {
        "subject": "perfectly centered subject",
        "foreground": "symmetrical reward items",
        "background": "mirrored background elements",
        "negative_space": "minimal negative space",
        "text_area": "top center text",
        "ui_area": "bottom center UI",
        "layout": "perfectly symmetrical composition",
    },
}


class CompositionPlanner:
    """Plans spatial layout for a prompt based on composition type."""

    def plan(self, composition: str, strategy: str = "balanced") -> PromptComponent:
        tokens = COMPOSITION_TOKENS.get(composition, COMPOSITION_TOKENS["center"])
        return PromptComponent(
            dimension="composition",
            value=composition,
            label=composition.replace("_", " ").title(),
            weight=1.0,
        )

    def get_tokens(self, composition: str) -> dict[str, str]:
        return COMPOSITION_TOKENS.get(composition, COMPOSITION_TOKENS["center"])