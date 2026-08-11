"""V4.0: Human Review — unified review system for Image and Video.

Human review dimensions:
  - Hook: how attention-grabbing
  - Gameplay: how well gameplay is shown
  - Reward: how desirable the reward is
  - CTR: predicted click-through rate
  - Brand: game identity clarity
  - Overall: overall quality score
  - Launchable: ready to launch?
  - Notes: free-text feedback
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


REVIEW_DIMENSIONS = [
    "hook",
    "gameplay",
    "reward",
    "ctr",
    "brand",
    "overall",
]

MAX_SCORE = 10


@dataclass
class ReviewResult:
    """Complete human review result."""
    creative_id: str = ""
    creative_type: str = ""
    scores: dict[str, int] = field(default_factory=dict)
    average: float = 0.0
    launchable: bool = False
    notes: str = ""
    reviewed_at: str = ""
    reviewer: str = ""


class HumanReview:
    """Human review system for creative assets.

    Usage:
        review = HumanReview()
        result = review.score(
            creative_id="creative_000001",
            hook=8, gameplay=7, reward=9, ctr=8, brand=7, overall=8,
            launchable=True,
            notes="Good hook, reward is strong. Ready to launch.",
        )
        review.save(result, repo)
    """

    def __init__(self) -> None:
        pass

    def score(
        self,
        creative_id: str,
        creative_type: str = "image",
        hook: int = 0,
        gameplay: int = 0,
        reward: int = 0,
        ctr: int = 0,
        brand: int = 0,
        overall: int = 0,
        launchable: bool = False,
        notes: str = "",
        reviewer: str = "",
    ) -> ReviewResult:
        """Create a review result from scores."""
        scores = {
            "hook": hook,
            "gameplay": gameplay,
            "reward": reward,
            "ctr": ctr,
            "brand": brand,
            "overall": overall,
        }
        valid_scores = {k: v for k, v in scores.items() if v > 0}
        avg = sum(valid_scores.values()) / max(len(valid_scores), 1)

        return ReviewResult(
            creative_id=creative_id,
            creative_type=creative_type,
            scores=scores,
            average=round(avg, 1),
            launchable=launchable,
            notes=notes,
            reviewed_at=datetime.now().isoformat(),
            reviewer=reviewer,
        )

    def save(self, result: ReviewResult, repo) -> bool:
        """Save review result to the creative repository."""
        return repo.save_review(result.creative_id, {
            **result.scores,
            "launchable": result.launchable,
            "notes": result.notes,
            "reviewer": result.reviewer,
        })

    def to_dict(self, result: ReviewResult) -> dict[str, Any]:
        return {
            "creative_id": result.creative_id,
            "creative_type": result.creative_type,
            "scores": result.scores,
            "average": result.average,
            "launchable": result.launchable,
            "notes": result.notes,
            "reviewed_at": result.reviewed_at,
            "reviewer": result.reviewer,
        }