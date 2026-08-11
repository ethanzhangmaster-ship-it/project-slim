"""E17.3 — Decision Memory（决策记忆，闭环学习）。

复用既有记忆系统（不重造）：
- E16.1 JsonlRevenueExperienceStore：记录「为何决策 + 结果」，计算 reward/success，
  供未来相似决策做置信度加成（这是 E17.3 的「知道什么情况下该做什么」）。
- E13.4 JsonlPatternMemory（Pattern Memory seam）：把决策沉淀为可检索的历史模式，
  供未来相似信号「命中先例」。

存储路径：
- 经验记忆：data/ceo/decision_experience.jsonl
- 模式记忆：data/ceo/decision_patterns.jsonl（可选，传 pattern_memory 时启用）
"""
from __future__ import annotations

from typing import Optional

from src.revenue_intelligence.experience import (
    JsonlRevenueExperienceStore,
    RevenueExperience,
    RevenuePoint,
)
from .simulator import MemoryStats


class DecisionMemory:
    """决策记忆 facade：闭环比 E16 Experience Store + E13 Pattern Memory。"""

    def __init__(
        self,
        experience_path: str = "data/ceo/decision_experience.jsonl",
        pattern_memory=None,  # Optional[JsonlPatternMemory]
    ):
        self.exp = JsonlRevenueExperienceStore(experience_path)
        self.pattern_memory = pattern_memory

    # ------------------------------------------------------------------ #
    # 记录「决策 -> 结果」闭环
    # ------------------------------------------------------------------ #
    def record_outcome(
        self,
        *,
        game_id: str,
        action: str,
        reason: str,
        before_revenue: float,
        after_revenue: float,
        before_roas: float,
        after_roas: float,
        before_spend: float = 0.0,
        after_spend: float = 0.0,
    ) -> None:
        exp = RevenueExperience(
            game_id=game_id,
            action=action,
            reason=reason,
            before=RevenuePoint(
                roas=before_roas, revenue_total=before_revenue, spend=before_spend
            ),
            after=RevenuePoint(
                roas=after_roas, revenue_total=after_revenue, spend=after_spend
            ),
        )
        self.exp.add(exp)

    def record_pattern(
        self,
        *,
        game_id: str,
        action: str,
        description: str,
        confidence: float,
    ) -> None:
        """把一次决策沉淀为 E13 Pattern Memory 可检索模式（可选）。"""
        if self.pattern_memory is None:
            return
        from src.revenue_intelligence.models import PatternMatch

        self.pattern_memory.add(
            PatternMatch(
                pattern_id=f"dec_{game_id}_{action}",
                description=description,
                confidence=confidence,
                similar_case=game_id,
                recommended_strategy=action,
                source="ceo_decision",
            ),
            game_id=game_id,
        )

    # ------------------------------------------------------------------ #
    # 查询：供置信度加成 / 模拟微调
    # ------------------------------------------------------------------ #
    def stats(self, game_id: str, action: str) -> MemoryStats:
        s = self.exp.stats(game_id, action)
        return MemoryStats(
            n=int(s.get("n", 0)),
            success_rate=float(s.get("success_rate", 0.0)),
            avg_reward=float(s.get("avg_reward", 0.0)),
        )

    def confidence_adjust(self, confidence: float, game_id: str, action: str) -> float:
        """历史样本充足且成功率高 → 置信度加成（封顶 0.15）；失败率高 → 降权。"""
        st = self.stats(game_id, action)
        if st.n < 2:
            return confidence
        if st.success_rate >= 0.8:
            return min(0.99, confidence + min(0.15, st.success_rate * 0.1))
        if st.success_rate <= 0.3:
            return max(0.30, confidence - 0.10)
        return confidence
