"""E13.7.4.4 Report Models — 报告核心数据模型.

定义 Agent 报告系统的核心数据结构:
  - ReportType: 报告类型 (OBSERVATION/REASONING/DECISION/EXECUTION/LEARNING/HEALTH)
  - ReportSection: 统一报告单元
  - AgentReport: 完整 Agent 报告
  - ReportFormat: 输出格式 (JSON/MARKDOWN/TEXT/HTML)
  - ReportSummary: 报告摘要
  - ReportQuery: 报告查询条件
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════
# Report Type Enum
# ═══════════════════════════════════════════════════════════════


class ReportType(str, Enum):
    """报告类型 — 对应 Agent 认知循环的 6 个阶段."""

    OBSERVATION = "observation"       # 环境观察
    REASONING = "reasoning"          # 推理过程
    DECISION = "decision"            # 决策结论
    EXECUTION = "execution"          # 执行追踪
    LEARNING = "learning"            # 学习更新
    HEALTH = "health"                # 健康摘要


class ReportFormat(str, Enum):
    """报告输出格式."""

    JSON = "json"
    MARKDOWN = "markdown"
    TEXT = "text"
    HTML = "html"


class ReportStatus(str, Enum):
    """报告状态."""

    DRAFT = "draft"
    FINAL = "final"
    ARCHIVED = "archived"


# ═══════════════════════════════════════════════════════════════
# Core Data Models
# ═══════════════════════════════════════════════════════════════


@dataclass
class ReportMetric:
    """报告指标 — 单个量化指标.

    Attributes:
        name: 指标名称
        value: 指标值
        unit: 单位 (%, $, s, count, etc.)
        trend: 趋势方向 (up/down/stable)
        change: 变化量
        change_pct: 变化百分比
        threshold: 阈值
        is_alert: 是否触发告警
    """

    name: str
    value: float
    unit: str = ""
    trend: str = "stable"
    change: float = 0.0
    change_pct: float = 0.0
    threshold: float | None = None
    is_alert: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "trend": self.trend,
            "change": self.change,
            "change_pct": round(self.change_pct, 4),
            "threshold": self.threshold,
            "is_alert": self.is_alert,
        }


@dataclass
class ReportEvidence:
    """报告证据 — 支撑结论的引用数据.

    Attributes:
        source: 数据来源
        reference: 引用内容
        confidence: 置信度
        timestamp: 时间戳
    """

    source: str
    reference: str
    confidence: float = 1.0
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "reference": self.reference,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
        }


@dataclass
class ReportSection:
    """报告单元 — Agent 报告的基本组成单元.

    每个 ReportSection 代表 Agent 认知循环中的一个片段:
      - OBSERVATION: 环境状态
      - REASONING: 推理链
      - DECISION: 决策结论
      - EXECUTION: 执行动作
      - LEARNING: 记忆更新
      - HEALTH: 健康状态

    Attributes:
        section_id: 唯一标识
        type: 报告类型
        title: 标题
        content: 正文内容 (Markdown)
        summary: 一句话摘要
        metrics: 量化指标
        evidence: 支撑证据
        confidence: 整体置信度
        timestamp: 时间戳
        parent_id: 父级 section (用于嵌套)
    """

    section_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: ReportType = ReportType.OBSERVATION
    title: str = ""
    content: str = ""
    summary: str = ""
    metrics: list[ReportMetric] = field(default_factory=list)
    evidence: list[ReportEvidence] = field(default_factory=list)
    confidence: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    parent_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "section_id": self.section_id,
            "type": self.type.value,
            "title": self.title,
            "content": self.content,
            "summary": self.summary,
            "metrics": [m.to_dict() for m in self.metrics],
            "evidence": [e.to_dict() for e in self.evidence],
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "parent_id": self.parent_id,
        }

    def to_markdown(self) -> str:
        """渲染为 Markdown 格式."""
        lines = [f"## {self.title}", ""]
        if self.summary:
            lines.append(f"**{self.summary}**")
            lines.append("")
        if self.content:
            lines.append(self.content)
            lines.append("")
        if self.metrics:
            lines.append("### Metrics")
            lines.append("")
            lines.append("| Metric | Value | Trend | Change |")
            lines.append("|--------|-------|-------|--------|")
            for m in self.metrics:
                trend_icon = {"up": "↑", "down": "↓", "stable": "→"}.get(m.trend, "→")
                change_str = f"{m.change_pct:+.1%}" if m.change_pct else "-"
                lines.append(f"| {m.name} | {m.value}{m.unit} | {trend_icon} | {change_str} |")
            lines.append("")
        if self.evidence:
            lines.append("### Evidence")
            lines.append("")
            for e in self.evidence:
                lines.append(f"- **{e.source}**: {e.reference}")
            lines.append("")
        if self.confidence:
            lines.append(f"*Confidence: {self.confidence:.0%}*")
            lines.append("")
        return "\n".join(lines)

    def to_text(self) -> str:
        """渲染为纯文本格式."""
        lines = [f"[{self.type.value.upper()}] {self.title}"]
        if self.summary:
            lines.append(self.summary)
        if self.content:
            lines.append(self.content)
        if self.metrics:
            for m in self.metrics:
                trend_icon = {"up": "↑", "down": "↓", "stable": "→"}.get(m.trend, "→")
                lines.append(f"  {m.name}: {m.value}{m.unit} {trend_icon}")
        if self.confidence:
            lines.append(f"  Confidence: {self.confidence:.0%}")
        return "\n".join(lines)


@dataclass
class ReportSummary:
    """报告摘要 — 快速概览.

    Attributes:
        total_sections: 总 section 数
        decision_count: 决策数
        execution_count: 执行数
        learning_count: 学习更新数
        key_findings: 关键发现
        risk_level: 风险等级
        overall_confidence: 整体置信度
    """

    total_sections: int = 0
    decision_count: int = 0
    execution_count: int = 0
    learning_count: int = 0
    key_findings: list[str] = field(default_factory=list)
    risk_level: str = "low"
    overall_confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_sections": self.total_sections,
            "decision_count": self.decision_count,
            "execution_count": self.execution_count,
            "learning_count": self.learning_count,
            "key_findings": self.key_findings,
            "risk_level": self.risk_level,
            "overall_confidence": self.overall_confidence,
        }


@dataclass
class AgentReport:
    """Agent 完整报告 — 一个周期的完整记录.

    AgentReport 是 Agent 报告系统的核心输出，包含:
      - 报告元信息 (ID, 时间, Agent ID)
      - 报告状态 (draft/final/archived)
      - 报告摘要 (快速概览)
      - 报告 Sections (6 个类型)
      - 整体置信度

    Attributes:
        report_id: 唯一标识
        agent_id: Agent 标识
        cycle_id: 循环 ID
        timestamp: 报告时间
        status: 报告状态
        summary: 报告摘要
        sections: 报告 sections
        overall_confidence: 整体置信度
        tags: 标签
        metadata: 扩展元数据
    """

    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    cycle_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: ReportStatus = ReportStatus.DRAFT
    summary: ReportSummary = field(default_factory=ReportSummary)
    sections: list[ReportSection] = field(default_factory=list)
    overall_confidence: float = 0.0
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── Section Management ──────────────────────────────────────

    def add_section(self, section: ReportSection) -> None:
        """添加一个 report section."""
        self.sections.append(section)
        self._update_summary()

    def get_sections_by_type(self, report_type: ReportType) -> list[ReportSection]:
        """按类型获取 sections."""
        return [s for s in self.sections if s.type == report_type]

    def get_section_by_id(self, section_id: str) -> ReportSection | None:
        """按 ID 获取 section."""
        for s in self.sections:
            if s.section_id == section_id:
                return s
        return None

    def _update_summary(self) -> None:
        """更新报告摘要."""
        summary = ReportSummary(
            total_sections=len(self.sections),
            decision_count=len(self.get_sections_by_type(ReportType.DECISION)),
            execution_count=len(self.get_sections_by_type(ReportType.EXECUTION)),
            learning_count=len(self.get_sections_by_type(ReportType.LEARNING)),
        )
        # 聚合置信度
        confidences = [s.confidence for s in self.sections if s.confidence > 0]
        if confidences:
            summary.overall_confidence = sum(confidences) / len(confidences)
        self.overall_confidence = summary.overall_confidence
        self.summary = summary

    def finalize(self) -> None:
        """标记为最终版本."""
        self.status = ReportStatus.FINAL

    def archive(self) -> None:
        """归档."""
        self.status = ReportStatus.ARCHIVED

    # ── Serialization ───────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "agent_id": self.agent_id,
            "cycle_id": self.cycle_id,
            "timestamp": self.timestamp,
            "status": self.status.value,
            "summary": self.summary.to_dict(),
            "sections": [s.to_dict() for s in self.sections],
            "overall_confidence": self.overall_confidence,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    def to_markdown(self) -> str:
        """渲染为 Markdown 格式."""
        lines = [
            f"# Agent Report: {self.report_id[:8]}",
            "",
            f"**Agent**: {self.agent_id}",
            f"**Cycle**: {self.cycle_id}",
            f"**Time**: {self.timestamp}",
            f"**Status**: {self.status.value}",
            f"**Confidence**: {self.overall_confidence:.0%}",
            "",
            "---",
            "",
        ]
        for section in self.sections:
            lines.append(section.to_markdown())
            lines.append("---")
            lines.append("")
        return "\n".join(lines)

    def to_text(self) -> str:
        """渲染为纯文本格式."""
        lines = [
            f"=== Agent Report: {self.report_id[:8]} ===",
            f"Agent: {self.agent_id}",
            f"Cycle: {self.cycle_id}",
            f"Time: {self.timestamp}",
            f"Confidence: {self.overall_confidence:.0%}",
            "",
        ]
        for section in self.sections:
            lines.append(section.to_text())
            lines.append("")
        return "\n".join(lines)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentReport":
        """从字典还原."""
        report = cls(
            report_id=data.get("report_id", ""),
            agent_id=data.get("agent_id", ""),
            cycle_id=data.get("cycle_id", ""),
            timestamp=data.get("timestamp", ""),
            status=ReportStatus(data.get("status", "draft")),
            overall_confidence=data.get("overall_confidence", 0.0),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )
        for s_data in data.get("sections", []):
            section = ReportSection(
                section_id=s_data.get("section_id", ""),
                type=ReportType(s_data.get("type", "observation")),
                title=s_data.get("title", ""),
                content=s_data.get("content", ""),
                summary=s_data.get("summary", ""),
                confidence=s_data.get("confidence", 0.0),
                timestamp=s_data.get("timestamp", ""),
                parent_id=s_data.get("parent_id", ""),
            )
            for m_data in s_data.get("metrics", []):
                section.metrics.append(ReportMetric(**m_data))
            for e_data in s_data.get("evidence", []):
                section.evidence.append(ReportEvidence(**e_data))
            report.add_section(section)
        return report


@dataclass
class ReportQuery:
    """报告查询条件.

    Attributes:
        agent_id: Agent ID 过滤
        cycle_id: 循环 ID 过滤
        report_type: 报告类型过滤
        start_time: 起始时间
        end_time: 结束时间
        status: 状态过滤
        tags: 标签过滤
        limit: 返回数量限制
        offset: 偏移量
    """

    agent_id: str = ""
    cycle_id: str = ""
    report_type: ReportType | None = None
    start_time: str = ""
    end_time: str = ""
    status: ReportStatus | None = None
    tags: list[str] = field(default_factory=list)
    limit: int = 50
    offset: int = 0

    def match(self, report: AgentReport) -> bool:
        """检查报告是否匹配查询条件."""
        if self.agent_id and report.agent_id != self.agent_id:
            return False
        if self.cycle_id and report.cycle_id != self.cycle_id:
            return False
        if self.report_type and not report.get_sections_by_type(self.report_type):
            return False
        if self.status and report.status != self.status:
            return False
        if self.tags:
            if not any(t in report.tags for t in self.tags):
                return False
        if self.start_time and report.timestamp < self.start_time:
            return False
        if self.end_time and report.timestamp > self.end_time:
            return False
        return True