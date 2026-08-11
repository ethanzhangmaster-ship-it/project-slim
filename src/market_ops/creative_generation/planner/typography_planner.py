"""Phase 3.0: Typography Planner — Facebook ad copy and text placement.

Decides ad copy text, font, position, color, and size for Facebook creatives.
"""

from __future__ import annotations

from ..models.prompt_component import PromptComponent


HOOK_COPY: dict[str, list[str]] = {
    "collection": [
        "Collect Them All!",
        "Can You Find The Rarest?",
        "Gotta Collect Every One!",
        "Which One Will You Get?",
        "My Collection Is Almost Complete!",
    ],
    "merge": [
        "Merge Now!",
        "Can You Solve It?",
        "Merge To Evolve!",
        "What Happens When You Merge?",
        "Only 1% Unlock This!",
    ],
    "evolution": [
        "Watch Them Evolve!",
        "You Won't Believe The Final Form!",
        "Evolve To Win!",
        "From Cute To EPIC!",
        "Evolution Surprise!",
    ],
    "reward": [
        "Free Reward Inside!",
        "Claim Your Prize Now!",
        "You Deserve This!",
        "Epic Reward Waiting!",
        "Open Your Gift!",
    ],
    "puzzle": [
        "Can You Solve This?",
        "Only Geniuses Pass Level 10!",
        "Your Brain Will Love This!",
        "Solve In 10 Seconds?",
        "99% Fail This Level!",
    ],
    "fail": [
        "Can You Do Better?",
        "I Failed... Help Me!",
        "Don't Make My Mistake!",
        "Even I Couldn't Beat This!",
        "Save Me!",
    ],
    "emotion": [
        "This Made Me Cry!",
        "The Most Satisfying Game Ever!",
        "You'll Feel Amazing!",
        "Pure Joy In One Game!",
        "This Feeling Is Addictive!",
    ],
    "challenge": [
        "Beat This Level!",
        "Are You Ready?",
        "Challenge Accepted?",
        "Prove You're The Best!",
        "Only The Brave Win!",
    ],
}


TYPOGRAPHY_TOKENS: dict[str, dict[str, str]] = {
    "default": {
        "font": "bold sans-serif, game UI style",
        "position": "top third or bottom third, text-safe area",
        "color": "white with dark shadow, or gold gradient",
        "size": "large, readable at thumbnail size",
        "style": "mobile game ad text, not too much text, clean",
        "description": "Standard game ad typography",
    },
}


class TypographyPlanner:
    """Plans ad copy and typography for a prompt."""

    def plan(self, hook: str = "merge", strategy: str = "balanced") -> PromptComponent:
        copy_options = HOOK_COPY.get(hook, HOOK_COPY["merge"])
        selected = copy_options[0]  # Default to first; variation engine handles diversity

        return PromptComponent(
            dimension="typography",
            value=hook,
            label=selected,
            weight=0.5,
        )

    def get_copy_options(self, hook: str) -> list[str]:
        return HOOK_COPY.get(hook, HOOK_COPY["merge"])

    def get_typography_tokens(self) -> dict[str, str]:
        return TYPOGRAPHY_TOKENS["default"]