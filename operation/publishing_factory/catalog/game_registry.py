"""
E15.1.1 — Game Registry
========================

JSONL / JSON-backed persistence for the fleet. Pure-python, no DB.
One GameProduct per record; keyed by game_id.

Default store path is ``data/catalog.json`` (project-local). Override via
``path=`` for tests.
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

from operation.publishing_factory.catalog.product_profile import GameProduct


class GameRegistry:
    """Load / save / query the fleet of GameProducts."""

    def __init__(self, path: str = "data/catalog.json"):
        self.path = path
        self._games: Dict[str, GameProduct] = {}
        self._loaded = False

    # ------------------------------------------------------------------ #
    def load(self, force: bool = False) -> "GameRegistry":
        if self._loaded and not force:
            return self
        self._games = {}
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as fh:
                content = fh.read().strip()
            if not content:
                self._loaded = True
                return self
            # JSON array (preferred) or JSONL (one obj per line)
            if content.startswith("["):
                for obj in json.loads(content):
                    g = GameProduct.from_dict(obj)
                    self._games[g.game_id] = g
            else:
                for raw in content.splitlines():
                    raw = raw.strip().rstrip(",")
                    if not raw:
                        continue
                    g = GameProduct.from_dict(json.loads(raw))
                    self._games[g.game_id] = g
        self._loaded = True
        return self

    def save(self) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        items = list(self._games.values())
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write("[\n")
            for i, g in enumerate(items):
                comma = "," if i < len(items) - 1 else ""
                fh.write("  " + json.dumps(g.to_dict(), ensure_ascii=False) + comma + "\n")
            fh.write("]\n")

    # ------------------------------------------------------------------ #
    def add(self, game: GameProduct) -> GameProduct:
        self._games[game.game_id] = game
        return game

    def get(self, game_id: str) -> Optional[GameProduct]:
        return self._games.get(game_id)

    def update(self, game: GameProduct) -> GameProduct:
        # preserve history if not supplied
        if game.rejection_history is None:
            prev = self._games.get(game.game_id)
            if prev:
                game.rejection_history = prev.rejection_history
        self._games[game.game_id] = game
        return game

    def remove(self, game_id: str) -> bool:
        return self._games.pop(game_id, None) is not None

    def list_all(self) -> List[GameProduct]:
        return list(self._games.values())

    def list_by_status(self, status: str) -> List[GameProduct]:
        return [g for g in self._games.values() if g.status == status]

    def count(self) -> int:
        return len(self._games)

    def ids(self) -> List[str]:
        return list(self._games.keys())


__all__ = ["GameRegistry"]
