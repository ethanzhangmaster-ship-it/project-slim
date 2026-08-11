"""E13.5.5 Decision Memory — 决策记录与闭环反馈.

将决策和结果记录为经验，支持:
  1. 决策记录 (DecisionExperience)
  2. 结果反馈 (record_outcome)
  3. 历史查询 (相似场景/策略)
  4. 形成 Autonomous Growth Loop:
     Decision → Outcome → Experience → Pattern → Strategy Upgrade

连接:
  DecisionEngine → DecisionMemory → Growth Memory / Experience Store
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .models import DecisionOutput, DecisionType


# ═══════════════════════════════════════════════════════════════
# Decision Experience
# ═══════════════════════════════════════════════════════════════


@dataclass
class DecisionExperience:
    """决策经验 — 一条完整的决策→结果记录.

    Attributes:
        experience_id: 经验唯一标识
        decision_id: 关联的决策 ID
        opportunity_id: 触发机会 ID
        opportunity_type: 机会类型
        strategy_id: 选中的策略 ID
        strategy_name: 策略名称
        decision_type: 决策类型
        confidence: 决策置信度
        risk_score: 决策风险评分
        final_score: 最终评分
        action_plan: 执行计划 (dict)
        result: 执行结果 (success/failure/partial)
        result_metrics: 结果指标 (ROAS change, etc.)
        result_reason: 结果原因
        lessons_learned: 经验教训
        pattern_contribution: 对 Pattern 的贡献
        created_at: 决策时间
        resolved_at: 结果确认时间
        metadata: 扩展元数据
    """
    experience_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    decision_id: str = ""
    opportunity_id: str = ""
    opportunity_type: str = ""
    strategy_id: str = ""
    strategy_name: str = ""
    decision_type: str = ""
    confidence: float = 0.0
    risk_score: float = 0.0
    final_score: float = 0.0
    action_plan: dict[str, Any] = field(default_factory=dict)
    result: str = "pending"  # pending / success / failure / partial
    result_metrics: dict[str, Any] = field(default_factory=dict)
    result_reason: str = ""
    lessons_learned: list[str] = field(default_factory=list)
    pattern_contribution: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resolved_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "experience_id": self.experience_id,
            "decision_id": self.decision_id,
            "opportunity_id": self.opportunity_id,
            "opportunity_type": self.opportunity_type,
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "decision_type": self.decision_type,
            "confidence": round(self.confidence, 4),
            "risk_score": round(self.risk_score, 4),
            "final_score": round(self.final_score, 4),
            "action_plan": self.action_plan,
            "result": self.result,
            "result_metrics": self.result_metrics,
            "result_reason": self.result_reason,
            "lessons_learned": self.lessons_learned,
            "pattern_contribution": self.pattern_contribution,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
            "metadata": self.metadata,
        }

    @property
    def is_resolved(self) -> bool:
        """是否已有结果."""
        return self.result != "pending"

    @property
    def is_success(self) -> bool:
        """是否成功."""
        return self.result == "success"

    @property
    def is_failure(self) -> bool:
        """是否失败."""
        return self.result == "failure"

    @property
    def is_partial(self) -> bool:
        """是否部分成功."""
        return self.result == "partial"

    def resolve(
        self,
        result: str,
        metrics: dict[str, Any] | None = None,
        reason: str = "",
        lessons: list[str] | None = None,
    ) -> None:
        """记录决策结果.

        Args:
            result: 结果 (success/failure/partial)
            metrics: 结果指标
            reason: 结果原因
            lessons: 经验教训
        """
        self.result = result
        if metrics:
            self.result_metrics = metrics
        self.result_reason = reason
        if lessons:
            self.lessons_learned = lessons
        self.resolved_at = datetime.now(timezone.utc).isoformat()


# ═══════════════════════════════════════════════════════════════
# Decision Memory
# ═══════════════════════════════════════════════════════════════


class DecisionMemory:
    """决策记忆 — 存储和管理决策经验.

    形成闭环:
      Decision → Outcome → Experience → Pattern → Strategy Upgrade

    用法:
        memory = DecisionMemory()
        memory.record_decision(decision_output)
        # ... 执行后 ...
        memory.record_outcome(decision_id, "success", {"roas_change": 0.15})
        similar = memory.find_similar(strategy_id="S1")
    """

    def __init__(self, max_experiences: int = 10000):
        """初始化决策记忆.

        Args:
            max_experiences: 最大经验存储数
        """
        self.max_experiences = max_experiences
        self._experiences: dict[str, DecisionExperience] = {}

    # ═══════════════════════════════════════════════════════════
    # 记录
    # ═══════════════════════════════════════════════════════════

    def record_decision(
        self,
        decision: DecisionOutput,
        opportunity_type: str = "",
    ) -> DecisionExperience:
        """记录决策 (执行前).

        Args:
            decision: 决策输出
            opportunity_type: 机会类型

        Returns:
            DecisionExperience: 创建的经验记录
        """
        experience = DecisionExperience(
            decision_id=decision.decision_id,
            opportunity_id=decision.opportunity_id,
            opportunity_type=opportunity_type,
            strategy_id=decision.strategy_id,
            strategy_name=decision.strategy_name,
            decision_type=decision.decision_type.value,
            confidence=decision.confidence,
            risk_score=decision.risk_score,
            final_score=decision.final_score,
            action_plan=decision.action_plan.to_dict() if decision.action_plan else {},
            metadata=decision.metadata,
        )

        self._add_experience(experience)
        return experience

    def record_outcome(
        self,
        decision_id: str,
        result: str,
        metrics: dict[str, Any] | None = None,
        reason: str = "",
        lessons: list[str] | None = None,
    ) -> DecisionExperience | None:
        """记录决策结果 (执行后).

        Args:
            decision_id: 决策 ID
            result: 结果 (success/failure/partial)
            metrics: 结果指标
            reason: 结果原因
            lessons: 经验教训

        Returns:
            DecisionExperience | None: 更新后的经验，未找到则返回 None
        """
        # 查找匹配的经验
        for exp in self._experiences.values():
            if exp.decision_id == decision_id:
                exp.resolve(result, metrics, reason, lessons)
                return exp
        return None

    # ═══════════════════════════════════════════════════════════
    # 查询
    # ═══════════════════════════════════════════════════════════

    def get_experience(self, experience_id: str) -> DecisionExperience | None:
        """获取指定经验."""
        return self._experiences.get(experience_id)

    def get_by_decision(self, decision_id: str) -> DecisionExperience | None:
        """按决策 ID 查找经验."""
        for exp in self._experiences.values():
            if exp.decision_id == decision_id:
                return exp
        return None

    def get_by_opportunity(self, opportunity_id: str) -> list[DecisionExperience]:
        """按机会 ID 查找经验."""
        return [e for e in self._experiences.values() if e.opportunity_id == opportunity_id]

    def get_by_strategy(self, strategy_id: str) -> list[DecisionExperience]:
        """按策略 ID 查找经验."""
        return [e for e in self._experiences.values() if e.strategy_id == strategy_id]

    def find_similar(
        self,
        opportunity_type: str = "",
        strategy_id: str = "",
        result: str = "",
        min_confidence: float = 0.0,
        limit: int = 20,
    ) -> list[DecisionExperience]:
        """查找相似经验.

        Args:
            opportunity_type: 机会类型 (可选过滤)
            strategy_id: 策略 ID (可选过滤)
            result: 结果类型 (可选过滤)
            min_confidence: 最低置信度
            limit: 返回数量上限

        Returns:
            list[DecisionExperience]: 匹配的经验列表 (按时间降序)
        """
        results: list[DecisionExperience] = []
        for exp in self._experiences.values():
            if opportunity_type and exp.opportunity_type != opportunity_type:
                continue
            if strategy_id and exp.strategy_id != strategy_id:
                continue
            if result and exp.result != result:
                continue
            if exp.confidence < min_confidence:
                continue
            results.append(exp)

        results.sort(key=lambda e: e.created_at, reverse=True)
        return results[:limit]

    def get_recent(self, limit: int = 50) -> list[DecisionExperience]:
        """获取最近的经验."""
        sorted_exps = sorted(
            self._experiences.values(),
            key=lambda e: e.created_at,
            reverse=True,
        )
        return sorted_exps[:limit]

    def get_pending(self) -> list[DecisionExperience]:
        """获取待观察的决策 (尚未有结果)."""
        return [e for e in self._experiences.values() if e.result == "pending"]

    # ═══════════════════════════════════════════════════════════
    # 统计
    # ═══════════════════════════════════════════════════════════

    def get_statistics(
        self,
        opportunity_type: str = "",
        strategy_id: str = "",
    ) -> dict[str, Any]:
        """获取决策统计.

        Args:
            opportunity_type: 机会类型 (可选过滤)
            strategy_id: 策略 ID (可选过滤)

        Returns:
            dict: 统计信息
        """
        exps = self.find_similar(
            opportunity_type=opportunity_type,
            strategy_id=strategy_id,
        )
        resolved = [e for e in exps if e.is_resolved]

        total = len(exps)
        resolved_count = len(resolved)
        success_count = sum(1 for e in resolved if e.is_success)
        failure_count = sum(1 for e in resolved if e.is_failure)
        partial_count = sum(1 for e in resolved if e.is_partial)

        success_rate = success_count / resolved_count if resolved_count > 0 else 0.0

        # 决策类型分布
        decision_types: dict[str, int] = {}
        for e in exps:
            dt = e.decision_type
            decision_types[dt] = decision_types.get(dt, 0) + 1

        return {
            "total_experiences": total,
            "resolved": resolved_count,
            "pending": total - resolved_count,
            "success_count": success_count,
            "failure_count": failure_count,
            "partial_count": partial_count,
            "success_rate": round(success_rate, 4),
            "decision_types": decision_types,
        }

    def get_strategy_success_rate(self, strategy_id: str) -> float:
        """获取指定策略的历史成功率."""
        exps = self.get_by_strategy(strategy_id)
        resolved = [e for e in exps if e.is_resolved]
        if not resolved:
            return 0.0
        success_count = sum(1 for e in resolved if e.is_success)
        return success_count / len(resolved)

    def get_opportunity_success_rate(self, opportunity_type: str) -> float:
        """获取指定机会类型的历史成功率."""
        exps = self.find_similar(opportunity_type=opportunity_type)
        resolved = [e for e in exps if e.is_resolved]
        if not resolved:
            return 0.0
        success_count = sum(1 for e in resolved if e.is_success)
        return success_count / len(resolved)

    # ═══════════════════════════════════════════════════════════
    # 内部
    # ═══════════════════════════════════════════════════════════

    def _add_experience(self, experience: DecisionExperience) -> None:
        """添加经验 (自动淘汰旧记录)."""
        if len(self._experiences) >= self.max_experiences:
            # 淘汰最旧的
            oldest = min(
                self._experiences.values(),
                key=lambda e: e.created_at,
            )
            del self._experiences[oldest.experience_id]
        self._experiences[experience.experience_id] = experience

    @property
    def total_experiences(self) -> int:
        """总经验数."""
        return len(self._experiences)

    @property
    def resolved_count(self) -> int:
        """已解决经验数."""
        return sum(1 for e in self._experiences.values() if e.is_resolved)

    @property
    def pending_count(self) -> int:
        """待观察经验数."""
        return self.total_experiences - self.resolved_count

    def clear(self) -> None:
        """清空所有记忆."""
        self._experiences.clear()