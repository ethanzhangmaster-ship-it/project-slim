"""E15.2.3 Decision Scoring Engine — 加权评分引擎.

公式:
  ActionScore =
      Expected Reward    × 0.45
    + Confidence         × 0.20
    + Memory Boost       × 0.15
    - Risk Penalty       × 0.15
    - Execution Cost     × 0.05

输出:
  - 综合得分
  - 各维度分解得分
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import ActionCandidate, ScoredCandidate, SelectionStatus

# ═══════════════════════════════════════════════════════════════
# Default Weights
# ═══════════════════════════════════════════════════════════════


@dataclass
class ScoringWeights:
    """评分权重配置."""
    reward: float = 0.45
    confidence: float = 0.20
    memory: float = 0.15
    risk: float = 0.15
    cost: float = 0.05


# ═══════════════════════════════════════════════════════════════
# Blocking Rules
# ═══════════════════════════════════════════════════════════════


class ScoringEngine:
    """E15.2.3 决策评分引擎.

    用法:
        engine = ScoringEngine()
        scored = engine.score(candidate)
    """

    def __init__(self, weights: ScoringWeights | None = None):
        self._weights = weights or ScoringWeights()

    def score(self, candidate: ActionCandidate) -> ScoredCandidate:
        """对单个候选进行评分.

        Args:
            candidate: ActionCandidate

        Returns:
            ScoredCandidate: 评分后的候选
        """
        w = self._weights

        # 1. 检查是否应被阻止
        block_reason = self._check_block(candidate)
        if block_reason:
            return ScoredCandidate(
                candidate=candidate,
                total_score=0.0,
                status=SelectionStatus.BLOCKED,
                block_reason=block_reason,
            )

        # 2. 各维度计算
        reward_component = candidate.expected_reward * w.reward
        confidence_component = candidate.confidence * w.confidence
        memory_component = candidate.memory_boost * w.memory
        risk_penalty = candidate.risk_score * w.risk
        cost_penalty = candidate.execution_cost * w.cost

        # 3. 综合得分
        total_score = (
            reward_component
            + confidence_component
            + memory_component
            - risk_penalty
            - cost_penalty
        )
        total_score = round(max(0.0, min(1.0, total_score)), 4)

        return ScoredCandidate(
            candidate=candidate,
            total_score=total_score,
            reward_component=round(reward_component, 4),
            confidence_component=round(confidence_component, 4),
            memory_component=round(memory_component, 4),
            risk_penalty=round(risk_penalty, 4),
            cost_penalty=round(cost_penalty, 4),
            status=SelectionStatus.PENDING,
        )

    def score_batch(self, candidates: list[ActionCandidate]) -> list[ScoredCandidate]:
        """批量评分.

        Args:
            candidates: 候选列表

        Returns:
            list[ScoredCandidate]: 按得分降序排列
        """
        scored = [self.score(c) for c in candidates]
        scored.sort(key=lambda s: s.total_score, reverse=True)
        return scored

    def get_weights(self) -> dict[str, float]:
        """获取当前权重."""
        return {
            "reward": self._weights.reward,
            "confidence": self._weights.confidence,
            "memory": self._weights.memory,
            "risk": self._weights.risk,
            "cost": self._weights.cost,
        }

    def set_weights(self, weights: ScoringWeights) -> None:
        """设置权重."""
        self._weights = weights

    # ── Blocking Rules ─────────────────────────────────────────

    def _check_block(self, candidate: ActionCandidate) -> str:
        """检查候选是否应被阻止.

        Returns:
            str: 阻止原因 (空字符串 = 不阻止)
        """
        # 风险过高 (> 0.85) 直接阻止
        if candidate.risk_score > 0.85:
            return (
                f"Risk score {candidate.risk_score:.2f} exceeds critical threshold 0.85"
            )

        # 置信度过低 (< 0.2) 直接阻止
        if candidate.confidence < 0.2:
            return (
                f"Confidence {candidate.confidence:.2f} below minimum threshold 0.2"
            )

        return ""


__all__ = ["ScoringWeights", "ScoringEngine"]