"""V4.1 Similarity utilities."""

import math
from typing import Any


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def l2_distance(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def l2_to_similarity(dist: float) -> float:
    return 1.0 / (1.0 + dist)


def rank_by_similarity(items: list[dict[str, Any]],
                       key: str = "score") -> list[dict[str, Any]]:
    return sorted(items, key=lambda x: x.get(key, 0), reverse=True)