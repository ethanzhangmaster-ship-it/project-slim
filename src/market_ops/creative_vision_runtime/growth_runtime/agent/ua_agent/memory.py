"""E14.3.6 UA Memory — UA 决策记忆与经验学习.

记录 UA Agent 的决策历史和策略效果，支持经验学习:

  输入: 决策记录 (diagnosis, strategy, action, outcome)
  输出: 经验查询 (类似情况 → 过去成功策略)

核心功能:
  - 决策记录: 存储每次分析→诊断→策略→执行的完整链路
  - 效果追踪: 跟踪策略执行后的实际效果
  - 模式匹配: 根据当前情况查找历史相似经验
  - 经验检索: 提高未来类似情况的置信度

设计原则:
  - 所有决策可追溯
  - 经验循环学习
  - 支持按时间/类型/效果查询
  - 与 SupervisorMemory 互补 (UA 领域专用)
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .diagnosis import DiagnosisType, DiagnosisSeverity
from .strategy import StrategyType


# ═══════════════════════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════════════════════


class DecisionOutcome(str, Enum):
    """决策结果."""
    SUCCESS = "success"            # 成功
    PARTIAL = "partial"            # 部分成功
    FAILURE = "failure"            # 失败
    PENDING = "pending"            # 等待结果
    UNKNOWN = "unknown"            # 未知


@dataclass
class UADecisionRecord:
    """UA 决策记录 — 完整决策链路.

    Attributes:
        record_id: 记录 ID
        product_id: 产品 ID
        campaign_id: 广告系列 ID
        analysis_id: 分析 ID
        diagnosis_type: 诊断类型
        diagnosis_severity: 诊断严重度
        strategy_type: 策略类型
        action_type: 动作类型
        action_target: 动作目标
        confidence: 决策置信度
        outcome: 结果
        before_metrics: 执行前指标
        after_metrics: 执行后指标
        impact: 实际影响
        learning: 学习总结
        created_at: 创建时间
        resolved_at: 结果确认时间
        metadata: 扩展元数据
    """
    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    product_id: str = ""
    campaign_id: str = ""
    analysis_id: str = ""
    diagnosis_type: DiagnosisType = DiagnosisType.HEALTHY
    diagnosis_severity: DiagnosisSeverity = DiagnosisSeverity.LOW
    strategy_type: StrategyType = StrategyType.MONITOR_ONLY
    action_type: str = ""
    action_target: str = ""
    confidence: float = 0.0
    outcome: DecisionOutcome = DecisionOutcome.PENDING
    before_metrics: dict[str, Any] = field(default_factory=dict)
    after_metrics: dict[str, Any] = field(default_factory=dict)
    impact: dict[str, float] = field(default_factory=dict)
    learning: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resolved_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "product_id": self.product_id,
            "campaign_id": self.campaign_id,
            "analysis_id": self.analysis_id,
            "diagnosis_type": self.diagnosis_type.value,
            "diagnosis_severity": self.diagnosis_severity.value,
            "strategy_type": self.strategy_type.value,
            "action_type": self.action_type,
            "action_target": self.action_target,
            "confidence": round(self.confidence, 4),
            "outcome": self.outcome.value,
            "before_metrics": self.before_metrics,
            "after_metrics": self.after_metrics,
            "impact": self.impact,
            "learning": self.learning,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
            "metadata": self.metadata,
        }

    def resolve(
        self,
        outcome: DecisionOutcome,
        after_metrics: dict[str, Any] | None = None,
        learning: str = "",
    ) -> None:
        self.outcome = outcome
        self.resolved_at = datetime.now(timezone.utc).isoformat()
        if after_metrics:
            self.after_metrics = after_metrics
            self._compute_impact()
        if learning:
            self.learning = learning

    def _compute_impact(self) -> None:
        """计算实际影响."""
        if not self.before_metrics or not self.after_metrics:
            return
        for key in self.after_metrics:
            if key in self.before_metrics:
                before = self.before_metrics.get(key, 0)
                after = self.after_metrics.get(key, 0)
                if before != 0:
                    self.impact[key] = (after - before) / before
                else:
                    self.impact[key] = after

    @property
    def is_success(self) -> bool:
        return self.outcome == DecisionOutcome.SUCCESS

    @property
    def is_resolved(self) -> bool:
        return self.outcome not in (DecisionOutcome.PENDING, DecisionOutcome.UNKNOWN)


@dataclass
class ExperienceEntry:
    """经验条目 — 聚合的经验.

    Attributes:
        diagnosis_type: 诊断类型
        strategy_type: 策略类型
        action_type: 动作类型
        success_count: 成功次数
        total_count: 总次数
        avg_impact: 平均影响
        avg_confidence: 平均置信度
        last_used: 最近使用时间
        best_learning: 最佳学习总结
    """
    diagnosis_type: DiagnosisType = DiagnosisType.HEALTHY
    strategy_type: StrategyType = StrategyType.MONITOR_ONLY
    action_type: str = ""
    success_count: int = 0
    total_count: int = 0
    avg_impact: dict[str, float] = field(default_factory=dict)
    avg_confidence: float = 0.0
    last_used: str = ""
    best_learning: str = ""

    @property
    def success_rate(self) -> float:
        if self.total_count == 0:
            return 0.0
        return self.success_count / self.total_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "diagnosis_type": self.diagnosis_type.value,
            "strategy_type": self.strategy_type.value,
            "action_type": self.action_type,
            "success_count": self.success_count,
            "total_count": self.total_count,
            "success_rate": round(self.success_rate, 4),
            "avg_impact": self.avg_impact,
            "avg_confidence": round(self.avg_confidence, 4),
            "last_used": self.last_used,
            "best_learning": self.best_learning,
        }


# ═══════════════════════════════════════════════════════════════
# UA Memory
# ═══════════════════════════════════════════════════════════════


class UAMemory:
    """UA 记忆系统 — 记录决策历史并支持经验检索.

    职责:
      1. 存储完整决策链路
      2. 追踪策略效果
      3. 聚合经验
      4. 匹配历史模式
      5. 提供置信度提升建议

    用法:
        memory = UAMemory()
        record = memory.record_decision(...)
        # 后续
        memory.resolve(record.record_id, DecisionOutcome.SUCCESS, after_metrics)
        # 查询
        experiences = memory.find_similar(DiagnosisType.CREATIVE_FATIGUE)
    """

    def __init__(self, max_records: int = 10000):
        self._records: dict[str, UADecisionRecord] = {}
        self._experiences: list[ExperienceEntry] = []
        self._max_records = max_records

    # ── 记录 ──────────────────────────────────────────────────

    def record_decision(
        self,
        product_id: str = "",
        campaign_id: str = "",
        analysis_id: str = "",
        diagnosis_type: DiagnosisType = DiagnosisType.HEALTHY,
        diagnosis_severity: DiagnosisSeverity = DiagnosisSeverity.LOW,
        strategy_type: StrategyType = StrategyType.MONITOR_ONLY,
        action_type: str = "",
        action_target: str = "",
        confidence: float = 0.0,
        before_metrics: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> UADecisionRecord:
        """记录一次决策.

        Args:
            product_id: 产品 ID
            campaign_id: 广告系列 ID
            analysis_id: 分析 ID
            diagnosis_type: 诊断类型
            diagnosis_severity: 诊断严重度
            strategy_type: 策略类型
            action_type: 动作类型
            action_target: 动作目标
            confidence: 置信度
            before_metrics: 执行前指标
            metadata: 扩展元数据

        Returns:
            UADecisionRecord: 决策记录
        """
        record = UADecisionRecord(
            product_id=product_id,
            campaign_id=campaign_id,
            analysis_id=analysis_id,
            diagnosis_type=diagnosis_type,
            diagnosis_severity=diagnosis_severity,
            strategy_type=strategy_type,
            action_type=action_type,
            action_target=action_target,
            confidence=confidence,
            before_metrics=before_metrics or {},
            metadata=metadata or {},
        )
        self._records[record.record_id] = record
        self._trim_if_needed()
        return record

    def record_from_dict(self, data: dict[str, Any]) -> UADecisionRecord:
        """从字典创建记录."""
        record = UADecisionRecord(
            product_id=data.get("product_id", ""),
            campaign_id=data.get("campaign_id", ""),
            analysis_id=data.get("analysis_id", ""),
            diagnosis_type=DiagnosisType(data.get("diagnosis_type", "healthy")),
            diagnosis_severity=DiagnosisSeverity(data.get("diagnosis_severity", "low")),
            strategy_type=StrategyType(data.get("strategy_type", "monitor_only")),
            action_type=data.get("action_type", ""),
            action_target=data.get("action_target", ""),
            confidence=data.get("confidence", 0.0),
            before_metrics=data.get("before_metrics", {}),
            metadata=data.get("metadata", {}),
        )
        self._records[record.record_id] = record
        return record

    # ── 结果追踪 ──────────────────────────────────────────────

    def resolve(
        self,
        record_id: str,
        outcome: DecisionOutcome,
        after_metrics: dict[str, Any] | None = None,
        learning: str = "",
    ) -> UADecisionRecord | None:
        """记录决策结果.

        Args:
            record_id: 记录 ID
            outcome: 结果
            after_metrics: 执行后指标
            learning: 学习总结

        Returns:
            更新后的记录
        """
        record = self._records.get(record_id)
        if not record:
            return None
        record.resolve(outcome, after_metrics, learning)
        self._update_experience(record)
        return record

    def resolve_batch(
        self,
        resolutions: list[dict[str, Any]],
    ) -> list[UADecisionRecord | None]:
        """批量记录结果."""
        return [
            self.resolve(
                record_id=r["record_id"],
                outcome=DecisionOutcome(r.get("outcome", "unknown")),
                after_metrics=r.get("after_metrics"),
                learning=r.get("learning", ""),
            )
            for r in resolutions
        ]

    # ── 经验聚合 ──────────────────────────────────────────────

    def _update_experience(self, record: UADecisionRecord) -> None:
        """更新经验库."""
        key = (record.diagnosis_type, record.strategy_type, record.action_type)

        # 查找已有经验
        existing = None
        for exp in self._experiences:
            if (exp.diagnosis_type, exp.strategy_type, exp.action_type) == key:
                existing = exp
                break

        if existing:
            existing.total_count += 1
            if record.is_success:
                existing.success_count += 1
            # 更新平均影响
            for k, v in record.impact.items():
                if k in existing.avg_impact:
                    existing.avg_impact[k] = (existing.avg_impact[k] * (existing.total_count - 1) + v) / existing.total_count
                else:
                    existing.avg_impact[k] = v
            existing.avg_confidence = (existing.avg_confidence * (existing.total_count - 1) + record.confidence) / existing.total_count
            existing.last_used = record.created_at
            if record.learning and record.is_success:
                existing.best_learning = record.learning
        else:
            entry = ExperienceEntry(
                diagnosis_type=record.diagnosis_type,
                strategy_type=record.strategy_type,
                action_type=record.action_type,
                success_count=1 if record.is_success else 0,
                total_count=1,
                avg_impact=dict(record.impact),
                avg_confidence=record.confidence,
                last_used=record.created_at,
                best_learning=record.learning if record.is_success else "",
            )
            self._experiences.append(entry)

    def rebuild_experiences(self) -> None:
        """从所有记录重建经验库."""
        self._experiences.clear()
        for record in self._records.values():
            if record.is_resolved:
                self._update_experience(record)

    # ── 经验查询 ──────────────────────────────────────────────

    def find_similar(
        self,
        diagnosis_type: DiagnosisType,
        strategy_type: StrategyType | None = None,
        min_success_rate: float = 0.0,
        top_n: int = 5,
    ) -> list[ExperienceEntry]:
        """查找相似诊断的历史经验.

        Args:
            diagnosis_type: 诊断类型
            strategy_type: 策略类型 (可选)
            min_success_rate: 最低成功率
            top_n: 返回数量

        Returns:
            经验列表 (按成功率排序)
        """
        matches = []
        for exp in self._experiences:
            if exp.diagnosis_type != diagnosis_type:
                continue
            if strategy_type and exp.strategy_type != strategy_type:
                continue
            if exp.success_rate < min_success_rate:
                continue
            matches.append(exp)

        matches.sort(key=lambda e: (e.success_rate, e.total_count), reverse=True)
        return matches[:top_n]

    def find_best_action(
        self,
        diagnosis_type: DiagnosisType,
        min_samples: int = 3,
    ) -> ExperienceEntry | None:
        """查找最佳历史动作.

        Args:
            diagnosis_type: 诊断类型
            min_samples: 最少样本数

        Returns:
            最佳经验
        """
        candidates = self.find_similar(diagnosis_type, min_success_rate=0.5)
        for c in candidates:
            if c.total_count >= min_samples:
                return c
        return None

    def get_confidence_boost(
        self,
        diagnosis_type: DiagnosisType,
        strategy_type: StrategyType,
        action_type: str,
    ) -> float:
        """根据历史经验计算置信度提升.

        Returns:
            置信度提升量 (0-0.3)
        """
        for exp in self._experiences:
            if (exp.diagnosis_type == diagnosis_type
                    and exp.strategy_type == strategy_type
                    and exp.action_type == action_type):
                if exp.total_count >= 5 and exp.success_rate >= 0.7:
                    return 0.15
                elif exp.total_count >= 3 and exp.success_rate >= 0.5:
                    return 0.10
                elif exp.total_count >= 1:
                    return 0.05
        return 0.0

    # ── 查询 ──────────────────────────────────────────────────

    def get_record(self, record_id: str) -> UADecisionRecord | None:
        return self._records.get(record_id)

    def get_records(
        self,
        diagnosis_type: DiagnosisType | None = None,
        outcome: DecisionOutcome | None = None,
        product_id: str = "",
        campaign_id: str = "",
        n: int = 50,
    ) -> list[UADecisionRecord]:
        """按条件查询记录."""
        results = []
        for record in self._records.values():
            if diagnosis_type and record.diagnosis_type != diagnosis_type:
                continue
            if outcome and record.outcome != outcome:
                continue
            if product_id and record.product_id != product_id:
                continue
            if campaign_id and record.campaign_id != campaign_id:
                continue
            results.append(record)
        results.sort(key=lambda r: r.created_at, reverse=True)
        return results[:n]

    def get_pending(self) -> list[UADecisionRecord]:
        """获取待确认结果的记录."""
        return [r for r in self._records.values() if not r.is_resolved]

    def get_success_stories(self, n: int = 10) -> list[UADecisionRecord]:
        """获取成功案例."""
        return self.get_records(outcome=DecisionOutcome.SUCCESS, n=n)

    def get_failures(self, n: int = 10) -> list[UADecisionRecord]:
        """获取失败案例."""
        return self.get_records(outcome=DecisionOutcome.FAILURE, n=n)

    def get_experiences(
        self,
        diagnosis_type: DiagnosisType | None = None,
    ) -> list[ExperienceEntry]:
        """获取经验条目."""
        if diagnosis_type:
            return [e for e in self._experiences if e.diagnosis_type == diagnosis_type]
        return list(self._experiences)

    # ── 统计 ──────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        resolved = [r for r in self._records.values() if r.is_resolved]
        successes = [r for r in resolved if r.is_success]
        return {
            "total_records": len(self._records),
            "resolved": len(resolved),
            "pending": len(self._records) - len(resolved),
            "success_rate": len(successes) / len(resolved) if resolved else 0.0,
            "experiences": len(self._experiences),
            "by_diagnosis": self._count_by_diagnosis(),
            "by_outcome": self._count_by_outcome(),
            "top_experiences": [
                e.to_dict() for e in sorted(
                    self._experiences,
                    key=lambda e: e.success_rate,
                    reverse=True,
                )[:5]
            ],
        }

    def _count_by_diagnosis(self) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for r in self._records.values():
            counts[r.diagnosis_type.value] += 1
        return dict(counts)

    def _count_by_outcome(self) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for r in self._records.values():
            counts[r.outcome.value] += 1
        return dict(counts)

    # ── 维护 ──────────────────────────────────────────────────

    def _trim_if_needed(self) -> None:
        """超出容量时清理旧记录."""
        if len(self._records) > self._max_records:
            # 按时间排序，删除最旧的
            sorted_records = sorted(
                self._records.values(),
                key=lambda r: r.created_at,
            )
            to_remove = len(self._records) - self._max_records
            for record in sorted_records[:to_remove]:
                del self._records[record.record_id]

    def reset(self) -> None:
        self._records.clear()
        self._experiences.clear()