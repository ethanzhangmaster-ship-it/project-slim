"""E13.7.12 Exploration Policy — 探索/利用平衡策略.

Day 7.12 Step 3:
  ε-greedy + UCB 混合探索策略。
  - ε-greedy: 以概率 ε 随机探索，1-ε 选择最优
  - UCB: Upper Confidence Bound 评分，鼓励探索样本少的 Pattern
  - ε 衰减: 随时间减少探索率
"""

from __future__ import annotations

import math
import random
from typing import Any


class ExplorationPolicy:
    """探索/利用策略 — ε-greedy + UCB.

    Usage:
        policy = ExplorationPolicy(epsilon_init=0.3, seed=42)
        for round_num in range(100):
            action = policy.select_action(patterns, total_rounds=round_num + 1)
            # ... execute action, observe reward ...
            policy.advance_round()
    """

    def __init__(
        self,
        epsilon_init: float = 0.3,
        epsilon_min: float = 0.01,
        decay_factor: float = 0.95,
        seed: int | None = None,
    ) -> None:
        self._epsilon_init = max(0.0, min(1.0, epsilon_init))
        self._epsilon_min = max(0.0, min(1.0, epsilon_min))
        self._decay_factor = max(0.0, min(1.0, decay_factor))
        self._round: int = 0
        self._rng = random.Random(seed)

    # ── Properties ──────────────────────────────────────────

    @property
    def current_round(self) -> int:
        return self._round

    @property
    def epsilon(self) -> float:
        return self.get_current_epsilon()

    # ── Public API ──────────────────────────────────────────

    def should_explore(self) -> bool:
        """ε-greedy: 以概率 ε 返回 True (探索)."""
        return self._rng.random() < self.get_current_epsilon()

    @staticmethod
    def compute_ucb(pattern: Any, total_rounds: int) -> float:
        """计算 UCB 评分.

        ucb = avg_reward + sqrt(2 * ln(total_rounds) / max(pattern_rounds, 1))
        """
        avg_reward = getattr(pattern.performance, "avg_reward", 0.0)
        pattern_rounds = max(getattr(pattern.performance, "samples", 1), 1)
        total = max(total_rounds, 1)
        exploration_bonus = math.sqrt(2.0 * math.log(total) / pattern_rounds)
        return round(avg_reward + exploration_bonus, 4)

    def select_action(
        self,
        patterns: list[Any],
        total_rounds: int,
    ) -> Any | None:
        """基于 UCB + ε-greedy 选择 Pattern.

        Args:
            patterns: PatternMemory 列表
            total_rounds: 总轮次数

        Returns:
            选中的 PatternMemory 或 None
        """
        if not patterns:
            return None

        if self.should_explore():
            # 探索: 随机选择
            return self._rng.choice(patterns)

        # 利用: 选最高 UCB
        best = max(patterns, key=lambda p: self.compute_ucb(p, total_rounds))
        return best

    def get_current_epsilon(self) -> float:
        """返回当前 ε 值.

        ε = max(ε_min, ε_init × decay_factor^round)
        """
        decayed = self._epsilon_init * (self._decay_factor ** self._round)
        return round(max(self._epsilon_min, decayed), 6)

    def advance_round(self) -> None:
        """推进轮次 (ε 衰减)."""
        self._round += 1

    def reset(self) -> None:
        """重置策略状态."""
        self._round = 0

    # ── Serialization ───────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "epsilon_init": self._epsilon_init,
            "epsilon_min": self._epsilon_min,
            "decay_factor": self._decay_factor,
            "current_round": self._round,
            "current_epsilon": self.get_current_epsilon(),
        }

    def __repr__(self) -> str:
        return (
            f"ExplorationPolicy(ε={self.get_current_epsilon():.4f}, "
            f"round={self._round})"
        )


__all__ = [
    "ExplorationPolicy",
]