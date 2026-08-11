"""Gameplay Quality Gate V2

4 维度评分模型：
  1. Board Detection (30pts): grid, cells, slots
  2. UI Density (25pts): level, coins, energy, buttons, HUD
  3. Merge Action (25pts): two objects, arrow, fusion, upgrade
  4. Screenshot Authenticity (20pts): mobile game screenshot feeling

验收规则: total_score >= 80 → PASS, < 80 → REGENERATE
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


BOARD_EVAL_QUESTIONS = [
    "Is there a visible hexagonal or grid-based merge board? (yes/no)",
    "Are there clearly defined game cells or slots on the board? (yes/no)",
    "Do the cells contain game objects/items? (yes/no)",
    "Does the board fill a significant portion of the image (50%+)? (yes/no)",
]

UI_EVAL_QUESTIONS = [
    "Is there a visible level indicator or badge? (yes/no)",
    "Is there a coin or currency counter display? (yes/no)",
    "Is there an energy bar or resource meter? (yes/no)",
    "Are there interactive buttons visible (e.g. MERGE, UPGRADE)? (yes/no)",
    "Does the image have mobile game HUD elements? (yes/no)",
]

MERGE_EVAL_QUESTIONS = [
    "Are there two identical or similar objects positioned to merge? (yes/no)",
    "Is there a visible merge arrow or connection indicator? (yes/no)",
    "Is there a fusion/upgrade glow or explosion effect? (yes/no)",
    "Can you see a before→after progression (e.g. eggs → dragon)? (yes/no)",
    "Is the merge action the focal point of the image? (yes/no)",
]

AUTH_EVAL_QUESTIONS = [
    "Does this look like an actual mobile game screenshot rather than concept art? (yes/no)",
    "Does it look like an App Store screenshot or gameplay capture? (yes/no)",
    "Is the UI functional-looking rather than purely decorative? (yes/no)",
    "Does it look like a real game someone would play, not a marketing image? (yes/no)",
]


@dataclass(slots=True)
class GameplayQualityResult:
    """4-dimension quality evaluation result."""
    total_score: float = 0.0
    board_score: float = 0.0
    ui_score: float = 0.0
    merge_score: float = 0.0
    auth_score: float = 0.0
    passed: bool = False
    details: dict[str, Any] = field(default_factory=dict)


class GameplayQualityGate:
    """V2: Multi-dimension gameplay quality evaluation.

    Uses Lovart scorer to evaluate each dimension with targeted questions.
    Falls back to heuristic scoring if Lovart is unavailable.
    """

    def __init__(self, pass_threshold: float = 80.0) -> None:
        self.pass_threshold = pass_threshold

    def evaluate(self, image_path: str) -> GameplayQualityResult:
        """Evaluate gameplay image quality across 4 dimensions.

        Returns:
            GameplayQualityResult with scores and pass/fail status.
        """
        # Try Lovart-based evaluation
        try:
            return self._evaluate_lovart(image_path)
        except Exception:
            return self._evaluate_heuristic(image_path)

    def _evaluate_lovart(self, image_path: str) -> GameplayQualityResult:
        """Use Lovart scorer to evaluate each dimension."""
        from market_ops.creative_image_scorer import CreativeImageScorer

        scorer = CreativeImageScorer(threshold=0)

        # Evaluate each dimension
        board_score = self._score_dimension(scorer, image_path, BOARD_EVAL_QUESTIONS, max_score=30)
        ui_score = self._score_dimension(scorer, image_path, UI_EVAL_QUESTIONS, max_score=25)
        merge_score = self._score_dimension(scorer, image_path, MERGE_EVAL_QUESTIONS, max_score=25)
        auth_score = self._score_dimension(scorer, image_path, AUTH_EVAL_QUESTIONS, max_score=20)

        total = board_score + ui_score + merge_score + auth_score

        return GameplayQualityResult(
            total_score=round(total, 1),
            board_score=round(board_score, 1),
            ui_score=round(ui_score, 1),
            merge_score=round(merge_score, 1),
            auth_score=round(auth_score, 1),
            passed=total >= self.pass_threshold,
            details={
                "board_questions": BOARD_EVAL_QUESTIONS,
                "ui_questions": UI_EVAL_QUESTIONS,
                "merge_questions": MERGE_EVAL_QUESTIONS,
                "auth_questions": AUTH_EVAL_QUESTIONS,
            },
        )

    def _score_dimension(self, scorer: Any, image_path: str, questions: list[str], max_score: float) -> float:
        """Score a single dimension by asking targeted questions.

        Uses the Lovart scorer to evaluate the image against specific yes/no questions.
        Each "yes" answer contributes proportionally to the max_score.
        """
        yes_count = 0
        for question in questions:
            try:
                # Create a prompt that asks the scorer to evaluate this specific aspect
                eval_prompt = (
                    f"Look at this image and answer: {question} "
                    f"Answer ONLY 'yes' or 'no'."
                )
                image_dict = {
                    "file_path": image_path,
                    "prompt_used": eval_prompt,
                    "model": "quality_gate",
                    "image_id": "gate_eval",
                    "hook_type": "gameplay",
                }
                result = scorer.score_batch([image_dict], project="P04 Witch")
                if result.scores:
                    score = result.scores[0].overall
                    # If score >= 7.0, consider it a "yes" (raised from 5.0 to reduce false positives)
                    if score >= 7.0:
                        yes_count += 1
            except Exception:
                pass

        # Calculate proportional score
        if questions:
            return (yes_count / len(questions)) * max_score
        return 0.0

    def _evaluate_heuristic(self, image_path: str) -> GameplayQualityResult:
        """Fallback heuristic evaluation using image properties."""
        from PIL import Image, ImageStat

        img = Image.open(image_path).convert("RGB")
        stat = ImageStat.Stat(img)

        # Heuristic: images with more varied colors and higher contrast
        # tend to look more like game screenshots
        stddev = sum(stat.stddev) / 3
        mean = sum(stat.mean) / 3

        # Higher stddev suggests more UI elements and contrast
        contrast_factor = min(stddev / 80.0, 1.0)

        # Estimate scores based on image properties
        board_score = 15.0 + contrast_factor * 10.0
        ui_score = 12.0 + contrast_factor * 8.0
        merge_score = 10.0 + contrast_factor * 10.0
        auth_score = 10.0 + contrast_factor * 5.0

        total = board_score + ui_score + merge_score + auth_score

        return GameplayQualityResult(
            total_score=round(total, 1),
            board_score=round(board_score, 1),
            ui_score=round(ui_score, 1),
            merge_score=round(merge_score, 1),
            auth_score=round(auth_score, 1),
            passed=total >= self.pass_threshold,
            details={"method": "heuristic", "stddev": round(stddev, 1)},
        )

    def save_report(self, result: GameplayQualityResult, output_path: str) -> None:
        """Save quality evaluation report to JSON."""
        report = {
            "total_score": result.total_score,
            "board_score": result.board_score,
            "ui_score": result.ui_score,
            "merge_score": result.merge_score,
            "auth_score": result.auth_score,
            "passed": result.passed,
            "threshold": self.pass_threshold,
            "details": result.details,
        }
        Path(output_path).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")