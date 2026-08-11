"""Phase 3.0: Prompt Scorer — evaluates prompt quality across 8 dimensions.

Scores each prompt on:
  - Gameplay: how well gameplay moment is described
  - Composition: spatial arrangement quality
  - Hook: attention-grabbing potential
  - Reward: reward visibility and desirability
  - Brand: game identity clarity
  - Readability: prompt text quality
  - Novelty: how different from other prompts
  - Diversity: dimension coverage

Prompts below 75 are automatically discarded.
"""

from __future__ import annotations

from ..models.prompt import Prompt, PromptScore


class PromptScorer:
    """Scores prompt quality across 8 dimensions. 0-100 each."""

    PASS_THRESHOLD = 75.0

    # ── Dimension-specific keywords for scoring ──

    GAMEPLAY_KEYWORDS = {
        "merge", "drag", "evolve", "transform", "collect", "upgrade",
        "gameplay", "puzzle", "solve", "match", "combo", "chain",
        "interaction", "play", "action", "game",
    }

    COMPOSITION_KEYWORDS = {
        "center", "composition", "layout", "foreground", "background",
        "framing", "focal point", "focus", "balanced", "rule of thirds",
        "diagonal", "triangle", "symmetrical", "negative space",
    }

    HOOK_KEYWORDS = {
        "surprise", "amazing", "wow", "stunning", "shocking",
        "unbelievable", "epic", "incredible", "magical", "mysterious",
        "click", "attention", "stop scrolling", "watch",
    }

    REWARD_KEYWORDS = {
        "reward", "treasure", "dragon", "gold", "gem", "prize",
        "collect", "earn", "win", "unlock", "claim", "free",
        "evolution", "transform", "upgrade", "level up",
    }

    BRAND_KEYWORDS = {
        "merge witches", "witch", "magic", "merge", "mobile game",
        "fantasy", "game", "advertisement", "ad",
    }

    READABILITY_KEYWORDS = {
        "clean", "clear", "high quality", "detail", "sharp",
        "professional", "ultra", "high-converting",
    }

    NOVELTY_KEYWORDS = {
        "unique", "different", "new", "original", "creative",
        "innovative", "fresh", "unexpected", "rare",
    }

    def score(self, prompt: Prompt, all_prompts: list[Prompt] | None = None) -> PromptScore:
        """Score a single prompt."""
        text = prompt.positive_prompt.lower()

        gameplay = self._keyword_score(text, self.GAMEPLAY_KEYWORDS, base=60)
        composition = self._keyword_score(text, self.COMPOSITION_KEYWORDS, base=60)
        hook = self._keyword_score(text, self.HOOK_KEYWORDS, base=50)
        reward = self._keyword_score(text, self.REWARD_KEYWORDS, base=60)
        brand = self._keyword_score(text, self.BRAND_KEYWORDS, base=60)
        readability = self._keyword_score(text, self.READABILITY_KEYWORDS, base=60)

        # Novelty: compare against other prompts
        novelty = 70.0
        if all_prompts and len(all_prompts) > 1:
            novelty = self._novelty_score(prompt, all_prompts)

        # Diversity: check dimension coverage
        diversity = self._diversity_score(prompt)

        return PromptScore(
            gameplay=round(gameplay, 1),
            composition=round(composition, 1),
            hook=round(hook, 1),
            reward=round(reward, 1),
            brand=round(brand, 1),
            readability=round(readability, 1),
            novelty=round(novelty, 1),
            diversity=round(diversity, 1),
        )

    def score_batch(self, prompts: list[Prompt]) -> list[Prompt]:
        """Score all prompts and attach scores. Filters out below threshold."""
        scored = []
        for p in prompts:
            p.score = self.score(p, prompts)
            if p.score.total >= self.PASS_THRESHOLD:
                scored.append(p)
        return scored

    def top_n(self, prompts: list[Prompt], n: int = 20) -> list[Prompt]:
        """Return top N prompts by score."""
        scored = self.score_batch(prompts)
        scored.sort(key=lambda p: p.score.total if p.score else 0, reverse=True)
        return scored[:n]

    # ── Helpers ──

    def _keyword_score(self, text: str, keywords: set[str], base: float = 50) -> float:
        """Score based on keyword presence. Each keyword adds points up to 100."""
        hits = sum(1 for kw in keywords if kw in text)
        bonus = min(hits * 8, 40)  # Max 40 bonus points
        return min(base + bonus, 100.0)

    def _novelty_score(self, prompt: Prompt, all_prompts: list[Prompt]) -> float:
        """Score how different this prompt is from others (simple Jaccard-like)."""
        words = set(prompt.positive_prompt.lower().split())
        if len(words) < 5:
            return 50.0

        overlaps = []
        for other in all_prompts:
            if other.prompt_id == prompt.prompt_id:
                continue
            other_words = set(other.positive_prompt.lower().split())
            if not other_words:
                continue
            overlap = len(words & other_words) / len(words | other_words)
            overlaps.append(overlap)

        if not overlaps:
            return 80.0

        avg_overlap = sum(overlaps) / len(overlaps)
        # Lower overlap = higher novelty
        return round((1.0 - avg_overlap) * 100, 1)

    def _diversity_score(self, prompt: Prompt) -> float:
        """Score based on dimension coverage in the prompt."""
        dims = {
            "camera": prompt.camera,
            "lighting": prompt.lighting,
            "composition": prompt.composition,
        }
        filled = sum(1 for v in dims.values() if v)
        base = 60.0
        bonus = (filled / max(len(dims), 1)) * 40.0
        return min(base + bonus, 100.0)