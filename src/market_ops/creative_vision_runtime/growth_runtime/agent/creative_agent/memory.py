"""E14.4.1 Creative Memory — 创意经验记忆系统.

记录 Creative Agent 的决策历史和 DNA 经验，支持经验学习:

  输入: 决策记录 (diagnosis, action, dna, outcome)
  输出: 经验查询 (类似情况 → 过去成功策略)

核心功能:
  - 决策记录: 存储每次分析→DNA 提取→动作→结果的完整链路
  - DNA 记忆: 存储 DNA 画像及其表现
  - 赢家记忆: 追踪历史上的赢家素材 DNA
  - 经验检索: 根据当前 DNA/表现查找历史相似经验

设计原则:
  - 所有决策可追溯
  - DNA 经验循环学习
  - 支持按 DNA 指纹/表现/类型查询
  - 与 UAMemory 和 SupervisorMemory 互补
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .analyzer import CreativeDiagnosisType, CreativeDiagnosisSeverity, CreativeMetrics
from .dna_engine import CreativeDNAProfile, DNAComparisonResult


# ═══════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════


class CreativeDecisionOutcome(str, Enum):
    """创意决策结果."""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"
    PENDING = "pending"
    UNKNOWN = "unknown"


class CreativeActionType(str, Enum):
    """创意动作类型."""
    EXTRACT_DNA = "extract_dna"
    ANALYZE_PERFORMANCE = "analyze_performance"
    GENERATE_VARIANTS = "generate_variants"
    REPLACE_CREATIVE = "replace_creative"
    SCALE_CREATIVE = "scale_creative"
    PAUSE_CREATIVE = "pause_creative"
    MUTATE_DNA = "mutate_dna"
    CLONE_DNA = "clone_dna"
    UNKNOWN = "unknown"


# ═══════════════════════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════════════════════


@dataclass
class CreativeDecisionRecord:
    """创意决策记录 — 完整决策链路.

    Attributes:
        record_id: 记录 ID
        creative_id: 创意 ID
        diagnosis_type: 诊断类型
        diagnosis_severity: 诊断严重度
        action_type: 动作类型
        action_params: 动作参数
        dna_id: 关联 DNA ID
        confidence: 决策置信度
        before_metrics: 执行前指标
        after_metrics: 执行后指标
        outcome: 决策结果
        reward: 奖励值
        learning: 学习总结
        is_resolved: 是否已解析
        created_at: 创建时间
        resolved_at: 解析时间
        metadata: 扩展元数据
    """
    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    creative_id: str = ""
    diagnosis_type: CreativeDiagnosisType = CreativeDiagnosisType.UNKNOWN
    diagnosis_severity: CreativeDiagnosisSeverity = CreativeDiagnosisSeverity.INFO
    action_type: CreativeActionType = CreativeActionType.UNKNOWN
    action_params: dict[str, Any] = field(default_factory=dict)
    dna_id: str = ""
    confidence: float = 0.0
    before_metrics: dict[str, Any] = field(default_factory=dict)
    after_metrics: dict[str, Any] = field(default_factory=dict)
    outcome: CreativeDecisionOutcome = CreativeDecisionOutcome.PENDING
    reward: float = 0.0
    learning: str = ""
    is_resolved: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resolved_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "creative_id": self.creative_id,
            "diagnosis_type": self.diagnosis_type.value,
            "diagnosis_severity": self.diagnosis_severity.value,
            "action_type": self.action_type.value,
            "action_params": self.action_params,
            "dna_id": self.dna_id,
            "confidence": self.confidence,
            "before_metrics": self.before_metrics,
            "after_metrics": self.after_metrics,
            "outcome": self.outcome.value,
            "reward": self.reward,
            "learning": self.learning,
            "is_resolved": self.is_resolved,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
            "metadata": self.metadata,
        }

    @property
    def is_success(self) -> bool:
        return self.outcome == CreativeDecisionOutcome.SUCCESS

    @property
    def is_failure(self) -> bool:
        return self.outcome == CreativeDecisionOutcome.FAILURE


@dataclass
class CreativeExperienceEntry:
    """创意经验条目 — 聚合的经验.

    Attributes:
        experience_id: 经验 ID
        diagnosis_type: 诊断类型
        action_type: 动作类型
        dna_pattern: DNA 模式 (指纹或关键基因)
        total_count: 总次数
        success_count: 成功次数
        avg_reward: 平均奖励
        avg_impact: 平均影响
        confidence_boost: 置信度提升
        last_updated: 最后更新时间
        metadata: 扩展元数据
    """
    experience_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    diagnosis_type: CreativeDiagnosisType = CreativeDiagnosisType.UNKNOWN
    action_type: CreativeActionType = CreativeActionType.UNKNOWN
    dna_pattern: str = ""
    total_count: int = 0
    success_count: int = 0
    avg_reward: float = 0.0
    avg_impact: float = 0.0
    confidence_boost: float = 0.0
    last_updated: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "experience_id": self.experience_id,
            "diagnosis_type": self.diagnosis_type.value,
            "action_type": self.action_type.value,
            "dna_pattern": self.dna_pattern,
            "total_count": self.total_count,
            "success_count": self.success_count,
            "avg_reward": self.avg_reward,
            "avg_impact": self.avg_impact,
            "confidence_boost": self.confidence_boost,
            "last_updated": self.last_updated,
            "metadata": self.metadata,
        }

    @property
    def success_rate(self) -> float:
        if self.total_count == 0:
            return 0.0
        return self.success_count / self.total_count


@dataclass
class CreativeDNAMemoryEntry:
    """DNA 记忆条目 — 存储 DNA 及其表现.

    Attributes:
        entry_id: 条目 ID
        dna: DNA 画像
        performance: 表现指标
        is_winner: 是否为赢家
        created_at: 创建时间
        last_seen_at: 最后出现时间
        metadata: 扩展元数据
    """
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    dna: CreativeDNAProfile | None = None
    performance: dict[str, float] = field(default_factory=dict)
    is_winner: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_seen_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "dna": self.dna.to_dict() if self.dna else None,
            "performance": self.performance,
            "is_winner": self.is_winner,
            "created_at": self.created_at,
            "last_seen_at": self.last_seen_at,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# Creative Memory
# ═══════════════════════════════════════════════════════════════


class CreativeMemory:
    """创意记忆系统 — 记录决策历史与 DNA 经验.

    职责:
      1. 记录创意决策历史
      2. 存储 DNA 画像及其表现
      3. 提取经验用于未来决策
      4. 跟踪赢家 DNA 模式

    用法:
        memory = CreativeMemory()
        record = memory.record_decision(
            creative_id="C102",
            diagnosis_type=CreativeDiagnosisType.CREATIVE_FATIGUE,
            action_type=CreativeActionType.GENERATE_VARIANTS,
            dna_id="dna_001",
        )
        memory.resolve(record.record_id, outcome=CreativeDecisionOutcome.SUCCESS)
    """

    def __init__(self):
        self._records: dict[str, CreativeDecisionRecord] = {}
        self._dna_entries: dict[str, CreativeDNAMemoryEntry] = {}
        self._experiences: dict[str, CreativeExperienceEntry] = {}  # key = f"{diagnosis}:{action}:{dna_pattern}"

    # ── 决策记录 ──────────────────────────────────────────────

    def record_decision(
        self,
        creative_id: str = "",
        diagnosis_type: CreativeDiagnosisType = CreativeDiagnosisType.UNKNOWN,
        diagnosis_severity: CreativeDiagnosisSeverity = CreativeDiagnosisSeverity.INFO,
        action_type: CreativeActionType = CreativeActionType.UNKNOWN,
        action_params: dict[str, Any] | None = None,
        dna_id: str = "",
        confidence: float = 0.0,
        before_metrics: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CreativeDecisionRecord:
        """记录一次创意决策.

        Args:
            creative_id: 创意 ID
            diagnosis_type: 诊断类型
            diagnosis_severity: 诊断严重度
            action_type: 动作类型
            action_params: 动作参数
            dna_id: 关联 DNA ID
            confidence: 决策置信度
            before_metrics: 执行前指标
            metadata: 扩展元数据

        Returns:
            CreativeDecisionRecord: 决策记录
        """
        record = CreativeDecisionRecord(
            creative_id=creative_id,
            diagnosis_type=diagnosis_type,
            diagnosis_severity=diagnosis_severity,
            action_type=action_type,
            action_params=action_params or {},
            dna_id=dna_id,
            confidence=confidence,
            before_metrics=before_metrics or {},
            metadata=metadata or {},
        )
        self._records[record.record_id] = record
        return record

    def resolve(
        self,
        record_id: str,
        outcome: CreativeDecisionOutcome = CreativeDecisionOutcome.UNKNOWN,
        after_metrics: dict[str, Any] | None = None,
        reward: float = 0.0,
        learning: str = "",
    ) -> CreativeDecisionRecord | None:
        """解析决策记录 — 记录执行结果.

        Args:
            record_id: 记录 ID
            outcome: 决策结果
            after_metrics: 执行后指标
            reward: 奖励值
            learning: 学习总结

        Returns:
            CreativeDecisionRecord | None
        """
        record = self._records.get(record_id)
        if not record:
            return None

        record.outcome = outcome
        record.after_metrics = after_metrics or {}
        record.reward = reward
        record.learning = learning
        record.is_resolved = True
        record.resolved_at = datetime.now(timezone.utc).isoformat()

        # 更新经验
        self._update_experience(record)

        return record

    def resolve_batch(
        self,
        resolutions: list[dict[str, Any]],
    ) -> list[CreativeDecisionRecord]:
        """批量解析决策记录."""
        results = []
        for r in resolutions:
            resolved = self.resolve(
                record_id=r.get("record_id", ""),
                outcome=CreativeDecisionOutcome(r.get("outcome", "unknown")),
                after_metrics=r.get("after_metrics"),
                reward=r.get("reward", 0.0),
                learning=r.get("learning", ""),
            )
            if resolved:
                results.append(resolved)
        return results

    # ── DNA 记忆 ──────────────────────────────────────────────

    def store_dna(
        self,
        dna: CreativeDNAProfile,
        is_winner: bool = False,
        performance: dict[str, float] | None = None,
    ) -> CreativeDNAMemoryEntry:
        """存储 DNA 画像.

        Args:
            dna: DNA 画像
            is_winner: 是否为赢家
            performance: 表现指标

        Returns:
            CreativeDNAMemoryEntry
        """
        entry = CreativeDNAMemoryEntry(
            dna=dna,
            is_winner=is_winner,
            performance=performance or dna.fitness,
            last_seen_at=datetime.now(timezone.utc).isoformat(),
        )
        self._dna_entries[entry.entry_id] = entry
        return entry

    def mark_winner(self, dna_id: str) -> bool:
        """标记 DNA 为赢家."""
        for entry in self._dna_entries.values():
            if entry.dna and entry.dna.dna_id == dna_id:
                entry.is_winner = True
                entry.last_seen_at = datetime.now(timezone.utc).isoformat()
                return True
        return False

    # ── 经验 ──────────────────────────────────────────────────

    def _update_experience(self, record: CreativeDecisionRecord) -> None:
        """更新经验条目."""
        key = f"{record.diagnosis_type.value}:{record.action_type.value}"
        exp = self._experiences.get(key)

        if not exp:
            exp = CreativeExperienceEntry(
                diagnosis_type=record.diagnosis_type,
                action_type=record.action_type,
            )
            self._experiences[key] = exp

        exp.total_count += 1
        if record.is_success:
            exp.success_count += 1

        # 更新平均奖励
        old_total = exp.total_count - 1
        exp.avg_reward = (exp.avg_reward * old_total + record.reward) / exp.total_count

        # 置信度提升 (基于成功率)
        if exp.total_count >= 3:
            exp.confidence_boost = min(exp.success_rate * 0.15, 0.15)

        exp.last_updated = datetime.now(timezone.utc).isoformat()

    def get_experience(
        self,
        diagnosis_type: CreativeDiagnosisType,
        action_type: CreativeActionType,
    ) -> CreativeExperienceEntry | None:
        """获取经验条目."""
        key = f"{diagnosis_type.value}:{action_type.value}"
        return self._experiences.get(key)

    def get_experiences(
        self,
        diagnosis_type: CreativeDiagnosisType | None = None,
    ) -> list[CreativeExperienceEntry]:
        """获取经验列表."""
        exps = list(self._experiences.values())
        if diagnosis_type:
            exps = [e for e in exps if e.diagnosis_type == diagnosis_type]
        return exps

    def get_best_experiences(
        self,
        min_success_rate: float = 0.6,
        min_count: int = 3,
    ) -> list[CreativeExperienceEntry]:
        """获取最佳经验."""
        return [
            e for e in self._experiences.values()
            if e.success_rate >= min_success_rate and e.total_count >= min_count
        ]

    # ── 查询 ──────────────────────────────────────────────────

    def get_record(self, record_id: str) -> CreativeDecisionRecord | None:
        return self._records.get(record_id)

    def get_records(
        self,
        creative_id: str | None = None,
        diagnosis_type: CreativeDiagnosisType | None = None,
        is_resolved: bool | None = None,
    ) -> list[CreativeDecisionRecord]:
        """按条件查询记录."""
        results = list(self._records.values())
        if creative_id:
            results = [r for r in results if r.creative_id == creative_id]
        if diagnosis_type:
            results = [r for r in results if r.diagnosis_type == diagnosis_type]
        if is_resolved is not None:
            results = [r for r in results if r.is_resolved == is_resolved]
        return results

    def get_pending(self) -> list[CreativeDecisionRecord]:
        """获取待解析的记录."""
        return [r for r in self._records.values() if not r.is_resolved]

    def get_resolved(self) -> list[CreativeDecisionRecord]:
        """获取已解析的记录."""
        return [r for r in self._records.values() if r.is_resolved]

    def get_dna_entry(self, entry_id: str) -> CreativeDNAMemoryEntry | None:
        return self._dna_entries.get(entry_id)

    def get_dna_by_creative(self, creative_id: str) -> CreativeDNAMemoryEntry | None:
        for entry in self._dna_entries.values():
            if entry.dna and entry.dna.creative_id == creative_id:
                return entry
        return None

    def get_winner_dnas(self) -> list[CreativeDNAMemoryEntry]:
        """获取所有赢家 DNA."""
        return [e for e in self._dna_entries.values() if e.is_winner]

    def get_dna_entries_by_performance(
        self,
        min_roas: float = 1.0,
    ) -> list[CreativeDNAMemoryEntry]:
        """按表现筛选 DNA."""
        return [
            e for e in self._dna_entries.values()
            if e.performance.get("roas", 0) >= min_roas
        ]

    def get_success_rate(
        self,
        diagnosis_type: CreativeDiagnosisType | None = None,
    ) -> float:
        """获取成功率."""
        records = self.get_records(diagnosis_type=diagnosis_type, is_resolved=True)
        if not records:
            return 0.0
        successes = sum(1 for r in records if r.is_success)
        return successes / len(records)

    def get_recent_dna_entries(self, n: int = 20) -> list[CreativeDNAMemoryEntry]:
        """获取最近的 DNA 条目."""
        entries = sorted(
            self._dna_entries.values(),
            key=lambda e: e.created_at,
            reverse=True,
        )
        return entries[:n]

    def stats(self) -> dict[str, Any]:
        """统计信息."""
        total_records = len(self._records)
        resolved = len(self.get_resolved())
        pending = len(self.get_pending())
        winners = len(self.get_winner_dnas())

        return {
            "total_records": total_records,
            "resolved": resolved,
            "pending": pending,
            "total_dna_entries": len(self._dna_entries),
            "winner_dnas": winners,
            "total_experiences": len(self._experiences),
            "success_rate": round(self.get_success_rate(), 4) if resolved > 0 else 0.0,
            "best_experiences": len(self.get_best_experiences()),
        }

    def reset(self) -> None:
        self._records.clear()
        self._dna_entries.clear()
        self._experiences.clear()


# ═══════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════


def create_creative_memory() -> CreativeMemory:
    """创建默认创意记忆."""
    return CreativeMemory()