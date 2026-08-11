"""
E13.4.2 — Module 2: Variant Allocator
======================================

Splits experiment traffic across arms and, optionally, deterministically maps
individual users to arms so the experiment behaves like a real A/B test
(each arm gets a reproducible, non-overlapping bucket of users).

Allocation only affects *statistical power* (sample size per arm → confidence)
in this simulated engine; the per-user monetisation effect is assumed linear
and independent of volume. The manager scales each arm's simulated impressions
by its allocation, which feeds the E13.2.9 confidence model.

No AI, no DB. Deterministic given a seed (reproducible experiments).
"""

from __future__ import annotations

import hashlib
import random
from typing import Dict, List

from monetization.experiments.models import Variant


def allocate(variants: List[Variant], method: str = "equal") -> List[Variant]:
    """Assign traffic shares to variants.

    method="equal"   -> 1/N each (default, unbiased).
    method="weighted"-> respects a `weight` carried on each variant's
                        `params['_weight']` if present, else falls back to equal.

    Mutates and returns the variants with `allocation` set.
    """
    n = len(variants)
    if n == 0:
        return variants

    if method == "weighted":
        weights = []
        for v in variants:
            w = float((v.params or {}).get("_weight", 1.0))
            weights.append(w if w > 0 else 1.0)
        total = sum(weights)
        for v, w in zip(variants, weights):
            v.allocation = round(w / total, 4)
        return variants

    # equal
    share = round(1.0 / n, 4)
    for v in variants:
        v.allocation = share
    return variants


def bucket(total_users: int, variants: List[Variant],
           seed: int = 1234) -> Dict[str, int]:
    """Deterministically assign `total_users` users to variant buckets.

    Uses a stable hash of (user_index, seed) so the same experiment always
    produces the same split, and the split is proportional to each variant's
    `allocation`. Returns {variant_id: user_count}.

    This is the realism hook: in production an assignment service would do the
    same; here we just need reproducible, allocation-proportional buckets.
    """
    rng = random.Random(seed)
    # Build a cumulative allocation table.
    allocs = [v.allocation for v in variants]
    total_alloc = sum(allocs) or 1.0
    cum: List[float] = []
    running = 0.0
    for a in allocs:
        running += a / total_alloc
        cum.append(running)

    counts: Dict[str, int] = {v.variant_id: 0 for v in variants}
    for i in range(total_users):
        # stable hash of the user index
        h = int(hashlib.md5(f"{seed}:{i}".encode()).hexdigest(), 16) % 100000
        frac = h / 100000.0
        for v, c in zip(variants, cum):
            if frac <= c:
                counts[v.variant_id] += 1
                break
        else:
            # floating-point safety: assign to last
            counts[variants[-1].variant_id] += 1
    return counts


def assign_impressions(baseline_impressions: int,
                       variants: List[Variant]) -> Dict[str, int]:
    """Implied impressions per arm given the segment's total impressions."""
    return {
        v.variant_id: int(round(baseline_impressions * v.allocation))
        for v in variants
    }
