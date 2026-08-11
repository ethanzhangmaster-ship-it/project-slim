"""Phase 3.0A: Image Selector — selects best prompts for image generation.

From a set of scored Prompts, selects the top N for generation.
Strategy:
  - Always includes the highest-scored prompt
  - Ensures diversity (different composition/camera/lighting combos)
  - Respects max count
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..creative_generation.models.prompt import Prompt


@dataclass
class SelectionResult:
    """Result of prompt selection."""
    selected: list[Prompt] = field(default_factory=list)
    total_available: int = 0
    selection_reason: str = ""


class ImageSelector:
    """Selects top prompts for image generation with diversity awareness."""

    def __init__(self, max_count: int = 3, ensure_diversity: bool = True) -> None:
        self._max_count = max_count
        self._ensure_diversity = ensure_diversity

    def select(self, prompts: list[Prompt]) -> SelectionResult:
        """Select the best prompts for image generation.

        Args:
            prompts: Scored prompts sorted by score (descending).

        Returns:
            SelectionResult with selected prompts.
        """
        if not prompts:
            return SelectionResult(total_available=0, selection_reason="No prompts available")

        if len(prompts) <= self._max_count:
            return SelectionResult(
                selected=list(prompts),
                total_available=len(prompts),
                selection_reason=f"All {len(prompts)} prompts selected (<= max {self._max_count})",
            )

        if not self._ensure_diversity:
            selected = prompts[:self._max_count]
            return SelectionResult(
                selected=selected,
                total_available=len(prompts),
                selection_reason=f"Top {self._max_count} by score",
            )

        # Diversity-aware selection
        selected = self._select_diverse(prompts)
        return SelectionResult(
            selected=selected,
            total_available=len(prompts),
            selection_reason=f"{len(selected)} diverse prompts selected from {len(prompts)}",
        )

    def _select_diverse(self, prompts: list[Prompt]) -> list[Prompt]:
        """Select diverse prompts by covering different dimension combinations."""
        selected: list[Prompt] = []
        seen_combos: set[str] = set()

        # Always take the highest scored first
        selected.append(prompts[0])
        seen_combos.add(self._combo_key(prompts[0]))

        for p in prompts[1:]:
            if len(selected) >= self._max_count:
                break
            key = self._combo_key(p)
            if key not in seen_combos:
                selected.append(p)
                seen_combos.add(key)

        # If we still need more, fill with next best regardless of diversity
        if len(selected) < self._max_count:
            for p in prompts:
                if len(selected) >= self._max_count:
                    break
                if p not in selected:
                    selected.append(p)

        return selected

    def _combo_key(self, prompt: Prompt) -> str:
        """Create a diversity key from camera + lighting + composition."""
        return f"{prompt.camera}|{prompt.lighting}|{prompt.composition}"