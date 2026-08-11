"""E12.4 — Action Mapper。

将 RealityFeedbackSignal 转换为 E11 Evolution Action。

映射表:
  FATIGUE_WARNING      → CREATE_MUTATION
  ROAS_DECLINE         → ANALYZE_DNA + MUTATION
  SCALE_OPPORTUNITY    → INCREASE_EXPLORATION
  CREATIVE_REPLACEMENT → ARCHIVE + REPLACE
  DATA_COLLECTION      → WAIT

输出格式兼容 E11.9 EvolutionOpportunity。
"""

from __future__ import annotations

from .models import FeedbackSignalType, RealityFeedbackSignal


# ── Action mapping ─────────────────────────────────────────


SIGNAL_TO_ACTION: dict[FeedbackSignalType, str] = {
    FeedbackSignalType.FATIGUE_WARNING: "CREATE_MUTATION",
    FeedbackSignalType.ROAS_DECLINE: "ANALYZE_DNA_AND_MUTATE",
    FeedbackSignalType.SCALE_OPPORTUNITY: "INCREASE_EXPLORATION",
    FeedbackSignalType.CREATIVE_REPLACEMENT: "ARCHIVE_AND_REPLACE",
    FeedbackSignalType.DATA_COLLECTION: "WAIT",
}

# 每种信号类型对应的突变基因建议
SIGNAL_TO_GENES: dict[FeedbackSignalType, list[str]] = {
    FeedbackSignalType.FATIGUE_WARNING: ["hook", "visual_style"],
    FeedbackSignalType.ROAS_DECLINE: ["hook", "gameplay", "monetization"],
    FeedbackSignalType.SCALE_OPPORTUNITY: ["audience", "context"],
    FeedbackSignalType.CREATIVE_REPLACEMENT: ["hook", "visual_style", "gameplay", "monetization", "audience", "context"],
    FeedbackSignalType.DATA_COLLECTION: [],
}

# 行动优先级（用于排序）
ACTION_PRIORITY: dict[str, int] = {
    "CREATE_MUTATION": 4,
    "ANALYZE_DNA_AND_MUTATE": 3,
    "ARCHIVE_AND_REPLACE": 3,
    "INCREASE_EXPLORATION": 2,
    "WAIT": 0,
}


class ActionMapper:
    """反馈信号 → E11 行动映射器。

    将 RealityFeedbackSignal 转换为 E11 EvolutionOrchestrator
    可消费的 Evolution Opportunity 格式。

    Usage:
        >>> mapper = ActionMapper()
        >>> signal = RealityFeedbackSignal(signal_type=FeedbackSignalType.FATIGUE_WARNING, ...)
        >>> action = mapper.map(signal)
        >>> print(action["action"], action["genes"])
    """

    def map(self, signal: RealityFeedbackSignal) -> dict:
        """将单个信号映射为 E11 行动。

        Args:
            signal: 反馈信号

        Returns:
            E11 Evolution Opportunity 格式的 dict
        """
        action = self._get_action(signal.signal_type)
        genes = self._get_genes(signal.signal_type)
        priority = self._get_priority(signal)

        return {
            "action": action,
            "target_id": signal.creative_id,
            "genes": genes,
            "priority": priority,
            "reason": signal.reason,
            "confidence": signal.confidence,
            "signal_id": signal.signal_id,
            "source": "e12.4_feedback",
            "metadata": {
                "signal_type": signal.signal_type.value,
                "severity": signal.severity,
                "recommended_action": signal.recommended_action,
                **signal.metadata,
            },
        }

    def map_batch(
        self,
        signals: list[RealityFeedbackSignal],
    ) -> list[dict]:
        """批量映射信号。

        Args:
            signals: 反馈信号列表

        Returns:
            按优先级排序的 E11 行动列表
        """
        actions = [self.map(s) for s in signals]
        return sorted(
            actions,
            key=lambda a: (
                ACTION_PRIORITY.get(a["action"], 0),
                a["priority"],
            ),
            reverse=True,
        )

    def to_evolution_opportunities(
        self,
        signals: list[RealityFeedbackSignal],
    ) -> list[dict]:
        """转换为 E11.9 EvolutionOpportunity 格式。

        Args:
            signals: 反馈信号列表

        Returns:
            EvolutionOpportunity 格式的 dict 列表
        """
        return [s.to_evolution_opportunity() for s in signals]

    @staticmethod
    def _get_action(signal_type: FeedbackSignalType) -> str:
        """获取对应的 E11 行动。"""
        return SIGNAL_TO_ACTION.get(signal_type, "MONITOR")

    @staticmethod
    def _get_genes(signal_type: FeedbackSignalType) -> list[str]:
        """获取建议的突变基因。"""
        return SIGNAL_TO_GENES.get(signal_type, [])

    @staticmethod
    def _get_priority(signal: RealityFeedbackSignal) -> float:
        """计算综合优先级。"""
        return signal.priority

    def __repr__(self) -> str:
        return "ActionMapper()"