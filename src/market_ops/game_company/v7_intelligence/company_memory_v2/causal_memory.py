from dataclasses import dataclass
from typing import List, Dict, Set, Optional
import random


@dataclass
class CausalLink:
    cause: str
    effect: str
    strength: float


class CausalMemory:
    """Store and query cause-effect relationships."""

    def __init__(self):
        self._links: List[CausalLink] = []

    def record_cause_effect(self, cause: str, effect: str, strength: float) -> None:
        """Record a causal link."""
        self._links.append(
            CausalLink(
                cause=cause,
                effect=effect,
                strength=round(max(0.0, min(1.0, strength)), 4),
            )
        )

    def find_causes(self, effect: str) -> List[CausalLink]:
        """Find all recorded causes for a given effect."""
        effect_lower = effect.lower()
        return [link for link in self._links if link.effect.lower() == effect_lower]

    def find_effects(self, cause: str) -> List[CausalLink]:
        """Find all recorded effects for a given cause."""
        cause_lower = cause.lower()
        return [link for link in self._links if link.cause.lower() == cause_lower]

    def get_causal_chain(self, start: str) -> List[str]:
        """Trace a causal chain starting from a node."""
        chain: List[str] = []
        visited: Set[str] = set()
        current = start.lower()
        while current not in visited:
            visited.add(current)
            chain.append(current)
            effects = self.find_effects(current)
            if not effects:
                break
            # pick strongest unseen effect
            effects = [e for e in effects if e.effect.lower() not in visited]
            if not effects:
                break
            current = max(effects, key=lambda x: x.strength).effect.lower()
        return chain
