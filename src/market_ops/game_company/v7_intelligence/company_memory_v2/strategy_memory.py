from dataclasses import dataclass, field
from typing import List, Dict, Optional
import random


@dataclass
class StrategyRecord:
    strategy_id: str
    name: str
    context: str
    expected_outcome: str
    success_rate: float = 0.0
    tags: List[str] = field(default_factory=list)


class StrategyMemory:
    """Store and retrieve strategies."""

    def __init__(self):
        self._strategies: List[StrategyRecord] = []
        self._counter = 0

    def record_strategy(self, strategy: StrategyRecord) -> str:
        """Record a strategy and return its ID."""
        self._counter += 1
        strategy.strategy_id = f"strat_{self._counter:04d}"
        if strategy.success_rate == 0.0:
            strategy.success_rate = round(random.uniform(0.3, 0.95), 4)
        self._strategies.append(strategy)
        return strategy.strategy_id

    def get_strategies(self) -> List[StrategyRecord]:
        """Return all recorded strategies."""
        return self._strategies

    def get_best_strategy(self, context: str) -> Optional[StrategyRecord]:
        """Return the best matching strategy for a given context."""
        context_lower = context.lower()
        candidates = [
            s
            for s in self._strategies
            if context_lower in s.context.lower() or any(context_lower in t.lower() for t in s.tags)
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda s: s.success_rate)
