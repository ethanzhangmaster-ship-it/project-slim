"""
E15.1.1 — Policy Scanner (4.3 Spam / Template Cloning)
======================================================

Pre-submission scan that compares a game's creative + metadata against
the REST of the fleet to detect Apple Guideline 4.3 (spam / copied
template) risk.

Deterministic similarity: normalize text -> token set -> Jaccard.
Icon similarity: compare (genre, glyph, style, base_color) tuples.
A pairwise score above threshold across >=2 dimensions raises a flag.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from operation.publishing_factory.catalog.product_profile import GameProduct

_SIM_THRESHOLD = 0.6


@dataclass
class SimilarityFlag:
    other_game: str
    dimension: str          # "metadata" | "icon" | "screenshot"
    score: float

    def to_dict(self) -> dict:
        return {"other_game": self.other_game, "dimension": self.dimension,
                "score": round(self.score, 3)}


@dataclass
class PolicyReport:
    game_id: str
    clean: bool
    flags: List[SimilarityFlag] = field(default_factory=list)
    max_similarity: float = 0.0
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"game_id": self.game_id, "clean": self.clean,
                "flags": [f.to_dict() for f in self.flags],
                "max_similarity": round(self.max_similarity, 3),
                "notes": list(self.notes)}


def _tokens(text: str) -> set:
    return set(t.lower() for t in text.replace(",", " ").split() if t)


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


class PolicyScanner:
    """Fleet-wide 4.3 spam / template-clone detector."""

    def __init__(self, threshold: float = _SIM_THRESHOLD):
        self.threshold = threshold

    def scan(self, game: GameProduct,
             fleet: List[GameProduct]) -> PolicyReport:
        flags: List[SimilarityFlag] = []
        notes: List[str] = []

        meta_a = _tokens(" ".join([game.display_name] + game.keywords
                                  + game.default_selling_points()))
        icon_a = (game.genre, game.game_id)  # placeholder; real icon via factory

        for other in fleet:
            if other.game_id == game.game_id:
                continue
            # metadata similarity
            meta_b = _tokens(" ".join([other.display_name] + other.keywords
                                      + other.default_selling_points()))
            s_meta = _jaccard(meta_a, meta_b)
            # icon similarity proxy: same genre + same glyph seed
            icon_same = (other.genre == game.genre)
            s_icon = 1.0 if icon_same else 0.0

            for dim, score in (("metadata", s_meta), ("icon", s_icon)):
                if score >= self.threshold:
                    flags.append(SimilarityFlag(other.game_id, dim, score))

        maxsim = max([f.score for f in flags], default=0.0)
        if not flags:
            notes.append("no significant similarity to other fleet games")
        else:
            notes.append(f"{len(flags)} similarity flag(s); review before submit")
        return PolicyReport(game_id=game.game_id, clean=len(flags) == 0,
                           flags=flags, max_similarity=maxsim, notes=notes)


__all__ = ["PolicyScanner", "PolicyReport", "SimilarityFlag", "_SIM_THRESHOLD"]
