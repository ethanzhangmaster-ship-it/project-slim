"""V5.0 Mutation Engine — Deterministic Random Context.

All random operations in the mutation pipeline use this context so that
everything is reproducible given a seed. Never use the global random state.

Usage:
    with RandomContext(seed=42) as rng:
        value = rng.choice(["a", "b", "c"])
        index = rng.randint(0, 10)

Replay: same seed → same sequence → same mutation result.
"""

from __future__ import annotations

import random
from contextlib import contextmanager
from typing import Any, Iterator


class RandomContext:
    """Deterministic random number generator with seed isolation.

    Each mutation operation receives a RandomContext, ensuring:
      - Replay determinism: same seed → same choices
      - Thread safety: no global random state pollution
      - Audit trail: seed is logged in EvolutionEvent.random_seed
    """

    def __init__(self, seed: int | None = None) -> None:
        self.seed = seed if seed is not None else random.randint(0, 2**31 - 1)
        self._rng = random.Random(self.seed)

    def choice(self, seq: list[Any]) -> Any:
        if not seq:
            raise IndexError("Cannot choose from empty sequence")
        return self._rng.choice(seq)

    def choices(self, seq: list[Any], k: int = 1, weights: list[float] | None = None) -> list[Any]:
        return self._rng.choices(seq, weights=weights, k=k)

    def randint(self, a: int, b: int) -> int:
        return self._rng.randint(a, b)

    def randrange(self, start: int, stop: int | None = None, step: int = 1) -> int:
        return self._rng.randrange(start, stop, step)

    def random(self) -> float:
        return self._rng.random()

    def uniform(self, a: float, b: float) -> float:
        return self._rng.uniform(a, b)

    def shuffle(self, seq: list[Any]) -> None:
        self._rng.shuffle(seq)

    def sample(self, seq: list[Any], k: int) -> list[Any]:
        return self._rng.sample(seq, k)

    def gauss(self, mu: float = 0.0, sigma: float = 1.0) -> float:
        return self._rng.gauss(mu, sigma)

    def get_state(self) -> tuple:
        return self._rng.getstate()

    def set_state(self, state: tuple) -> None:
        self._rng.setstate(state)

    def __enter__(self) -> "RandomContext":
        return self

    def __exit__(self, *args: Any) -> None:
        pass


@contextmanager
def with_seed(seed: int | None = None) -> Iterator[RandomContext]:
    """Convenience context manager for a deterministic random context."""
    ctx = RandomContext(seed=seed)
    try:
        yield ctx
    finally:
        pass
