"""
E16.6.3 — ASO Creative Memory (closed-loop learning).

Persists executed creative changes and their CVR outcome
(``ASOCreativeExperience``) to an append-only JSONL store, then mines them back
into reusable ``ASOCreativePattern`` records — so a winning icon change in one
merge game can inform the next.

This mirrors E13.4 Pattern Memory's store shape (append-only JSONL, bad-line
tolerant) and lives alongside the other ASO stores under ``data/aso``.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.aso_intelligence.creative.models import (
    ASOCreativeExperience,
    ASOCreativePattern,
)


DEFAULT_BASE_DIR = "data/aso"
STORE_FILE = "creative_experiences.jsonl"


@dataclass
class ASOCreativeMemory:
    """Append-only JSONL store of creative optimization experiences."""

    base_dir: str = DEFAULT_BASE_DIR
    store_file: str = STORE_FILE

    # ------------------------------------------------------------------ #
    @property
    def path(self) -> str:
        return os.path.join(self.base_dir, self.store_file)

    def _ensure(self) -> None:
        os.makedirs(self.base_dir, exist_ok=True)
        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8"):
                pass

    def _append(self, record: Dict[str, Any]) -> None:
        self._ensure()
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _read_all(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.path):
            return []
        out: List[Dict[str, Any]] = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return out

    # ------------------------------------------------------------------ #
    def record_experience(self, exp: ASOCreativeExperience) -> None:
        """Persist one closed-loop experience (append-only)."""
        self._append(exp.to_dict())

    def experiences(
        self, game_id: Optional[str] = None
    ) -> List[ASOCreativeExperience]:
        """All recorded experiences, optionally filtered by ``game_id``."""
        rows = self._read_all()
        exps = [ASOCreativeExperience.from_dict(r) for r in rows]
        if game_id is not None:
            exps = [e for e in exps if e.game_id == game_id]
        return exps

    def clear(self) -> None:
        """Wipe the store (test helper)."""
        if os.path.exists(self.path):
            os.remove(self.path)

    # ------------------------------------------------------------------ #
    def pattern_for_category(
        self, category: str
    ) -> List[ASOCreativePattern]:
        """This category's learned patterns.

        Patterns are category-scoped by convention: an experience's ``pattern``
        is namespaced as ``"<category>:<dim>:<value>"`` (e.g.
        ``"merge:composition:centered_focal"``). ``success`` = mean CVR lift of
        the group; ``sample_size`` = number of experiences.
        """
        return [p for p in self.learned_patterns() if p.category == category]

    def learned_patterns(self) -> List[ASOCreativePattern]:
        """All learned patterns across categories."""
        groups: Dict[tuple, List[ASOCreativeExperience]] = {}
        for e in self.experiences():
            if not e.pattern:
                continue
            groups.setdefault((e.asset_type.value, e.pattern), []).append(e)

        patterns: List[ASOCreativePattern] = []
        for (asset, pat), members in groups.items():
            lifts = [m.cvr_lift() for m in members]
            mean_lift = round(sum(lifts) / len(lifts), 4) if lifts else 0.0
            # category is the first token of the pattern, if namespaced
            cat = pat.split(":", 1)[0] if ":" in pat else "global"
            patterns.append(
                ASOCreativePattern(
                    category=cat,
                    asset=asset,
                    pattern=pat,
                    success=mean_lift,
                    sample_size=len(members),
                )
            )
        patterns.sort(key=lambda p: p.success, reverse=True)
        return patterns


__all__ = ["ASOCreativeMemory", "DEFAULT_BASE_DIR", "STORE_FILE"]
