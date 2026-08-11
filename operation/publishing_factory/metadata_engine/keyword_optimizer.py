"""
E15.1.1 — Keyword Optimizer
===========================

Scores, de-duplicates and budgets a keyword list for a game.

Ranking signal (deterministic, no LLM):
  relevance   = 1.0 if keyword in genre seed bank else 0.5
  opportunity = 1.0 - competition_hint  (high competition -> lower)
  score       = 0.6*relevance + 0.4*opportunity

Budget: App Store keyword field is 100 chars. We pack the highest-
scoring unique keywords until the comma-joined length would exceed the
budget, then stop (deterministic greedy).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

_KW_BUDGET = 100  # App Store keyword field char budget


@dataclass
class ScoredKeyword:
    keyword: str
    relevance: float
    opportunity: float
    score: float

    def to_dict(self) -> dict:
        return {"keyword": self.keyword, "relevance": round(self.relevance, 3),
                "opportunity": round(self.opportunity, 3),
                "score": round(self.score, 3)}


@dataclass
class KeywordPlan:
    game_id: str
    ranked: List[ScoredKeyword] = field(default_factory=list)
    selected: List[str] = field(default_factory=list)
    budget_used: int = 0
    dropped: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"game_id": self.game_id,
                "ranked": [k.to_dict() for k in self.ranked],
                "selected": list(self.selected),
                "budget_used": self.budget_used,
                "dropped": list(self.dropped)}


class KeywordOptimizer:
    """Rank + budget keywords for a game."""

    def __init__(self, budget: int = _KW_BUDGET):
        self.budget = budget

    def optimize(self, game_id: str, keywords: List[str],
                 genre_seed: List[str] = None,
                 competition: Dict[str, float] = None) -> KeywordPlan:
        genre_seed = genre_seed or []
        competition = competition or {}
        # dedupe, preserve order, lowercase
        seen, uniq = set(), []
        for k in keywords:
            kl = k.strip().lower()
            if kl and kl not in seen:
                seen.add(kl)
                uniq.append(kl)

        ranked: List[ScoredKeyword] = []
        for k in uniq:
            relevance = 1.0 if k in genre_seed else 0.5
            comp = competition.get(k, 0.5)
            opportunity = 1.0 - comp
            score = round(0.6 * relevance + 0.4 * opportunity, 4)
            ranked.append(ScoredKeyword(k, relevance, opportunity, score))
        ranked.sort(key=lambda x: x.score, reverse=True)

        # greedy budget packing
        selected, dropped, used = [], [], 0
        for sk in ranked:
            add = len(sk.keyword) + (1 if selected else 0)  # +comma
            if used + add <= self.budget:
                selected.append(sk.keyword)
                used += add
            else:
                dropped.append(sk.keyword)
        return KeywordPlan(game_id=game_id, ranked=ranked,
                           selected=selected, budget_used=used,
                           dropped=dropped)


__all__ = ["KeywordOptimizer", "KeywordPlan", "ScoredKeyword", "_KW_BUDGET"]
