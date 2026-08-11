"""E14.2.2 Priority Engine — 多信号优先级决策.

当多个问题/信号同时出现时，Supervisor 需要排序:
  - 哪个问题先解决?
  - 哪个 Agent 先分配资源?
  - 预算如何分配?

评分公式:
  priority_score = impact × urgency × confidence / risk

设计原则:
  - 优先级可量化、可解释
  - 支持多维度评分 (impact, urgency, confidence, risk)
  - 支持动态权重调整
  - 输出可排序的优先级列表
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from ..communication.agent_message import AgentRole


# ═══════════════════════════════════════════════════════════════
# Priority Models
# ═══════════════════════════════════════════════════════════════


class SignalSeverity(str, Enum):
    """信号严重程度."""
    CRITICAL = "critical"    # 立即处理
    HIGH = "high"            # 优先处理
    MEDIUM = "medium"        # 正常处理
    LOW = "low"              # 低优先级
    INFO = "info"            # 通知


class SignalCategory(str, Enum):
    """信号类别."""
    ROAS = "roas"                    # ROAS 相关
    CPI = "cpi"                      # CPI 相关
    CREATIVE = "creative"            # 素材相关
    REVENUE = "revenue"              # 收入相关
    RETENTION = "retention"          # 留存相关
    PAYER = "payer"                  # 付费相关
    BUDGET = "budget"                # 预算相关
    RISK = "risk"                    # 风险相关
    OPPORTUNITY = "opportunity"      # 机会
    SYSTEM = "system"                # 系统


@dataclass
class PrioritySignal:
    """优先级信号 — 需要 Supervisor 关注的事件.

    Attributes:
        signal_id: 信号 ID
        category: 信号类别
        severity: 严重程度
        description: 描述
        source_agent: 来源 Agent
        target_agent: 目标 Agent (谁需要处理)
        impact: 影响程度 (0-1)
        urgency: 紧急程度 (0-1)
        confidence: 置信度 (0-1)
        risk_level: 风险等级 (0-1)
        metrics: 相关指标
        created_at: 创建时间
        metadata: 扩展元数据
    """
    signal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    category: SignalCategory = SignalCategory.SYSTEM
    severity: SignalSeverity = SignalSeverity.MEDIUM
    description: str = ""
    source_agent: AgentRole | None = None
    target_agent: AgentRole | None = None
    impact: float = 0.5
    urgency: float = 0.5
    confidence: float = 0.7
    risk_level: float = 0.3
    metrics: dict[str, float] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def priority_score(self) -> float:
        """优先级评分 = impact × urgency × confidence / risk."""
        if self.risk_level <= 0:
            return self.impact * self.urgency * self.confidence
        return (self.impact * self.urgency * self.confidence) / self.risk_level

    @property
    def weighted_score(self) -> float:
        """加权评分 (severity 加成)."""
        severity_multiplier = {
            SignalSeverity.CRITICAL: 2.0,
            SignalSeverity.HIGH: 1.5,
            SignalSeverity.MEDIUM: 1.0,
            SignalSeverity.LOW: 0.5,
            SignalSeverity.INFO: 0.2,
        }
        return self.priority_score * severity_multiplier.get(self.severity, 1.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "category": self.category.value,
            "severity": self.severity.value,
            "description": self.description,
            "source_agent": self.source_agent.value if self.source_agent else None,
            "target_agent": self.target_agent.value if self.target_agent else None,
            "impact": self.impact,
            "urgency": self.urgency,
            "confidence": self.confidence,
            "risk_level": self.risk_level,
            "priority_score": round(self.priority_score, 4),
            "weighted_score": round(self.weighted_score, 4),
            "metrics": self.metrics,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


@dataclass
class PriorityDecision:
    """优先级决策 — 对多个信号的排序结果.

    Attributes:
        decision_id: 决策 ID
        ranked_signals: 排序后的信号列表
        total_signals: 总信号数
        top_priority: 最高优先级信号
        created_at: 决策时间
        rationale: 决策理由
        metadata: 扩展元数据
    """
    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ranked_signals: list[PrioritySignal] = field(default_factory=list)
    total_signals: int = 0
    top_priority: PrioritySignal | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    rationale: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "ranked_signals": [s.to_dict() for s in self.ranked_signals],
            "total_signals": self.total_signals,
            "top_priority": self.top_priority.to_dict() if self.top_priority else None,
            "created_at": self.created_at,
            "rationale": self.rationale,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# Priority Engine
# ═══════════════════════════════════════════════════════════════


class PriorityEngine:
    """优先级引擎 — 多信号排序和资源分配决策.

    职责:
      1. 接收多个信号
      2. 计算每个信号的优先级评分
      3. 排序输出优先级列表
      4. 识别 top-N 最高优先级信号
    """

    # 默认权重配置
    DEFAULT_WEIGHTS: dict[str, float] = {
        "impact": 0.4,
        "urgency": 0.3,
        "confidence": 0.2,
        "risk": 0.1,
    }

    # 类别基线权重
    CATEGORY_BASE_WEIGHTS: dict[SignalCategory, float] = {
        SignalCategory.ROAS: 1.0,
        SignalCategory.CPI: 0.9,
        SignalCategory.REVENUE: 0.95,
        SignalCategory.PAYER: 0.85,
        SignalCategory.CREATIVE: 0.8,
        SignalCategory.RETENTION: 0.7,
        SignalCategory.BUDGET: 0.75,
        SignalCategory.RISK: 0.9,
        SignalCategory.OPPORTUNITY: 0.6,
        SignalCategory.SYSTEM: 0.5,
    }

    def __init__(self, weights: dict[str, float] | None = None):
        self._weights = weights or self.DEFAULT_WEIGHTS.copy()
        self._signals: list[PrioritySignal] = []
        self._decisions: list[PriorityDecision] = []

    # ── 信号管理 ──────────────────────────────────────────────

    def add_signal(self, signal: PrioritySignal) -> None:
        """添加信号."""
        self._signals.append(signal)

    def add_signals(self, signals: list[PrioritySignal]) -> None:
        """批量添加信号."""
        self._signals.extend(signals)

    def create_signal(
        self,
        category: SignalCategory,
        description: str,
        severity: SignalSeverity = SignalSeverity.MEDIUM,
        impact: float = 0.5,
        urgency: float = 0.5,
        confidence: float = 0.7,
        risk_level: float = 0.3,
        source_agent: AgentRole | None = None,
        target_agent: AgentRole | None = None,
        metrics: dict[str, float] | None = None,
    ) -> PrioritySignal:
        """创建并添加信号."""
        signal = PrioritySignal(
            category=category,
            severity=severity,
            description=description,
            impact=impact,
            urgency=urgency,
            confidence=confidence,
            risk_level=risk_level,
            source_agent=source_agent,
            target_agent=target_agent,
            metrics=metrics or {},
        )
        self.add_signal(signal)
        return signal

    # ── 优先级排序 ────────────────────────────────────────────

    def rank(self, signals: list[PrioritySignal] | None = None) -> PriorityDecision:
        """对信号排序并生成优先级决策.

        Args:
            signals: 待排序信号 (None = 使用所有已添加信号)

        Returns:
            PriorityDecision: 排序结果
        """
        candidates = signals or self._signals

        if not candidates:
            return PriorityDecision(
                ranked_signals=[],
                total_signals=0,
                rationale="no_signals",
            )

        # 按 weighted_score 降序排序
        ranked = sorted(candidates, key=lambda s: s.weighted_score, reverse=True)

        # 生成决策理由
        if ranked:
            top = ranked[0]
            rationale = (
                f"Top priority: {top.category.value} ({top.description[:40]}) "
                f"score={top.weighted_score:.3f}"
            )
        else:
            rationale = "no_signals"

        decision = PriorityDecision(
            ranked_signals=ranked,
            total_signals=len(ranked),
            top_priority=ranked[0] if ranked else None,
            rationale=rationale,
        )
        self._decisions.append(decision)
        return decision

    def rank_current(self) -> PriorityDecision:
        """对当前所有信号排序."""
        decision = self.rank(self._signals)
        # 清除已排序信号
        self._signals.clear()
        return decision

    def get_top_n(self, n: int = 3, signals: list[PrioritySignal] | None = None) -> list[PrioritySignal]:
        """获取 Top-N 最高优先级信号."""
        decision = self.rank(signals)
        return decision.ranked_signals[:n]

    # ── 自定义评分 ────────────────────────────────────────────

    def compute_custom_score(
        self,
        signal: PrioritySignal,
        weights: dict[str, float] | None = None,
    ) -> float:
        """使用自定义权重计算评分."""
        w = weights or self._weights
        score = (
            signal.impact * w.get("impact", 0.4)
            + signal.urgency * w.get("urgency", 0.3)
            + signal.confidence * w.get("confidence", 0.2)
            - signal.risk_level * w.get("risk", 0.1)
        )
        return max(score, 0.0)

    # ── 资源分配 ──────────────────────────────────────────────

    def allocate_attention(
        self,
        signals: list[PrioritySignal] | None = None,
        max_slots: int = 3,
    ) -> list[PrioritySignal]:
        """分配关注资源 (Supervisor 一次只能处理 top-N).

        Args:
            signals: 信号列表
            max_slots: 最大处理槽位

        Returns:
            需要立即处理的信号
        """
        return self.get_top_n(max_slots, signals)

    def allocate_by_role(
        self,
        signals: list[PrioritySignal],
    ) -> dict[AgentRole, list[PrioritySignal]]:
        """按目标 Agent 分配信号.

        Returns:
            {AgentRole: [signals]}
        """
        allocation: dict[AgentRole, list[PrioritySignal]] = {}
        for signal in signals:
            if signal.target_agent:
                allocation.setdefault(signal.target_agent, []).append(signal)
        # 每个角色内按优先级排序
        for role in allocation:
            allocation[role] = sorted(
                allocation[role], key=lambda s: s.weighted_score, reverse=True
            )
        return allocation

    # ── 查询 ──────────────────────────────────────────────────

    def get_signals(self) -> list[PrioritySignal]:
        return list(self._signals)

    def get_signals_by_category(self, category: SignalCategory) -> list[PrioritySignal]:
        return [s for s in self._signals if s.category == category]

    def get_signals_by_severity(self, severity: SignalSeverity) -> list[PrioritySignal]:
        return [s for s in self._signals if s.severity == severity]

    def get_critical_signals(self) -> list[PrioritySignal]:
        return self.get_signals_by_severity(SignalSeverity.CRITICAL)

    def get_last_decision(self) -> PriorityDecision | None:
        return self._decisions[-1] if self._decisions else None

    def get_decisions(self, n: int = 10) -> list[PriorityDecision]:
        return self._decisions[-n:]

    # ── 统计 ──────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """优先级引擎统计."""
        total = len(self._signals)
        n_decisions = len(self._decisions)
        if total == 0:
            return {"total_signals": 0, "total_decisions": n_decisions}

        category_counts = {}
        severity_counts = {}
        for s in self._signals:
            category_counts[s.category.value] = category_counts.get(s.category.value, 0) + 1
            severity_counts[s.severity.value] = severity_counts.get(s.severity.value, 0) + 1

        avg_score = sum(s.weighted_score for s in self._signals) / total if total > 0 else 0

        return {
            "total_signals": total,
            "total_decisions": n_decisions,
            "category_counts": category_counts,
            "severity_counts": severity_counts,
            "avg_weighted_score": round(avg_score, 4),
            "critical_count": severity_counts.get("critical", 0),
            "high_count": severity_counts.get("high", 0),
        }

    def reset(self) -> None:
        self._signals.clear()
        self._decisions.clear()


# ═══════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════


def create_priority_engine() -> PriorityEngine:
    return PriorityEngine()