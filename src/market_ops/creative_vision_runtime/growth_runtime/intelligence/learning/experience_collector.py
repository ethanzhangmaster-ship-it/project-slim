"""E15.3.5 Experience Collector — 经验收集器.

从执行结果中收集经验，连接 Memory Feedback Bridge。

来源:
  - Execution Result → Experience
  - OperatorCycleResult → Experience
  - Direct record → Experience

用法:
    collector = ExperienceCollector()
    collector.collect_from_result(action, context, decision, result, reward)
    experiences = collector.get_experiences()
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import (
    ExperienceQuality,
    LearningExperience,
)


# ═══════════════════════════════════════════════════════════════
# Experience Collector
# ═══════════════════════════════════════════════════════════════


class ExperienceCollector:
    """E15.3.5 经验收集器 — 收集执行经验.

    用法:
        collector = ExperienceCollector()
        exp = collector.collect(
            action="creative_refresh",
            context={"country": "US", "campaign": "merge_game"},
            result={"ctr": "+18%", "roas": "+12%"},
            reward=0.74,
        )
    """

    def __init__(self, max_experiences: int = 10000):
        self._experiences: list[LearningExperience] = []
        self._max_experiences = max_experiences
        self._collection_count: int = 0

    @property
    def collection_count(self) -> int:
        return self._collection_count

    # ── Collect ──────────────────────────────────────────────────

    def collect(
        self,
        action: str,
        context: dict[str, Any] | None = None,
        decision: dict[str, Any] | None = None,
        result: dict[str, Any] | None = None,
        reward: float = 0.0,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        timestamp: str | None = None,
    ) -> LearningExperience:
        """收集一条经验.

        Args:
            action:   执行动作
            context:  执行上下文
            decision: 决策信息
            result:   执行结果
            reward:   收益值
            tags:     标签
            metadata: 扩展元数据
            timestamp: 时间戳

        Returns:
            LearningExperience
        """
        self._collection_count += 1

        experience = LearningExperience(
            action=action,
            context=context or {},
            decision=decision or {},
            result=result or {},
            reward=reward,
            tags=tags or [],
            metadata=metadata or {},
            timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
        )

        self._experiences.append(experience)

        # 限制容量
        if len(self._experiences) > self._max_experiences:
            self._experiences = self._experiences[-self._max_experiences:]

        return experience

    def collect_from_result(
        self, result_data: dict[str, Any]
    ) -> LearningExperience:
        """从结果字典收集经验.

        Args:
            result_data: {
                "action": str,
                "context": dict,
                "decision": dict,
                "result": dict,
                "reward": float,
                ...
            }
        """
        return self.collect(
            action=result_data.get("action", ""),
            context=result_data.get("context", {}),
            decision=result_data.get("decision", {}),
            result=result_data.get("result", {}),
            reward=result_data.get("reward", 0.0),
            tags=result_data.get("tags"),
            metadata=result_data.get("metadata"),
        )

    def collect_batch(
        self, results: list[dict[str, Any]]
    ) -> list[LearningExperience]:
        """批量收集经验."""
        return [self.collect_from_result(r) for r in results]

    # ── Query ───────────────────────────────────────────────────

    def get_experiences(self) -> list[LearningExperience]:
        """获取所有经验."""
        return list(self._experiences)

    def get_recent(self, n: int = 100) -> list[LearningExperience]:
        """获取最近 n 条经验."""
        return self._experiences[-n:]

    def get_by_action(self, action: str) -> list[LearningExperience]:
        """按动作筛选经验."""
        return [e for e in self._experiences if e.action == action]

    def get_by_tag(self, tag: str) -> list[LearningExperience]:
        """按标签筛选经验."""
        return [e for e in self._experiences if tag in e.tags]

    def get_valuable(self) -> list[LearningExperience]:
        """获取有价值的经验."""
        return [e for e in self._experiences if e.is_valuable()]

    def get_positive(self) -> list[LearningExperience]:
        """获取正向经验 (reward > 0)."""
        return [e for e in self._experiences if e.reward > 0]

    def get_negative(self) -> list[LearningExperience]:
        """获取负向经验 (reward < 0)."""
        return [e for e in self._experiences if e.reward < 0]

    # ── Stats ───────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息."""
        total = len(self._experiences)
        if total == 0:
            return {"total": 0, "positive_rate": 0.0, "avg_reward": 0.0}

        positive = len(self.get_positive())
        rewards = [e.reward for e in self._experiences]
        avg_reward = sum(rewards) / total

        # 动作分布
        action_counts: dict[str, int] = {}
        for e in self._experiences:
            action_counts[e.action] = action_counts.get(e.action, 0) + 1

        return {
            "total": total,
            "positive": positive,
            "negative": total - positive,
            "positive_rate": positive / total,
            "avg_reward": round(avg_reward, 4),
            "max_reward": max(rewards) if rewards else 0.0,
            "min_reward": min(rewards) if rewards else 0.0,
            "action_distribution": action_counts,
            "collection_count": self._collection_count,
        }

    def get_summary(self) -> dict[str, Any]:
        return {
            "total_experiences": len(self._experiences),
            "collection_count": self._collection_count,
            **self.get_stats(),
        }

    def reset(self) -> None:
        """重置收集器."""
        self._experiences.clear()
        self._collection_count = 0


__all__ = ["ExperienceCollector"]