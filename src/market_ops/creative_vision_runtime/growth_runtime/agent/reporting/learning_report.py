"""E13.7.4.4 Learning Report — 学习报告生成器.

学习报告追踪 Agent 自我进化:
  - 新学习到的模式 (Pattern)
  - 更新的记忆 (Memory Update)
  - 反馈循环 (Execution Result → Memory)
  - 性能变化 (Performance Delta)

连接:
  - Memory Layer: 模式记忆更新
  - Execution Engine: 执行结果反馈
  - Decision Engine: 决策质量追踪
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .report_models import (
    ReportSection,
    ReportEvidence,
    ReportMetric,
    ReportType,
)


# ═══════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════


@dataclass
class LearningEntry:
    """单条学习记录."""

    action: str               # "mutate_creative", "scale_budget"
    condition: str            # "fatigue > 0.8", "ROAS > 2.0"
    reward: float             # 奖励值 (e.g., ROAS change %)
    confidence: float         # 学习置信度
    experience_count: int = 1 # 经验积累次数
    source: str = ""          # 学习来源
    details: dict = field(default_factory=dict)


@dataclass
class PatternUpdate:
    """模式更新."""

    pattern_name: str
    old_value: float | None
    new_value: float
    change: str = "stable"   # "improved", "degraded", "stable"
    description: str = ""


@dataclass
class MemoryFeedback:
    """记忆反馈."""

    memory_type: str          # "pattern", "campaign", "audience", "failure"
    key: str                  # 记忆键
    action: str               # "insert", "update", "delete"
    value: str                # 更新内容描述
    confidence: float = 1.0


# ═══════════════════════════════════════════════════════════════
# LearningReportBuilder
# ═══════════════════════════════════════════════════════════════


class LearningReportBuilder:
    """学习报告生成器.

    使用方式:
        builder = LearningReportBuilder()
        builder.add_learning(LearningEntry(
            action="mutate_creative",
            condition="fatigue > 0.8",
            reward=0.32,
            confidence=0.91,
        ))
        builder.add_pattern_update(PatternUpdate(...))
        builder.add_memory_feedback(MemoryFeedback(...))
        section = builder.build()
    """

    def __init__(self):
        self._learnings: list[LearningEntry] = []
        self._pattern_updates: list[PatternUpdate] = []
        self._memory_feedbacks: list[MemoryFeedback] = []
        self._performance_changes: list[dict] = []

    def add_learning(self, entry: LearningEntry) -> "LearningReportBuilder":
        """添加学习记录."""
        self._learnings.append(entry)
        return self

    def add_pattern_update(self, update: PatternUpdate) -> "LearningReportBuilder":
        """添加模式更新."""
        self._pattern_updates.append(update)
        return self

    def add_memory_feedback(self, feedback: MemoryFeedback) -> "LearningReportBuilder":
        """添加记忆反馈."""
        self._memory_feedbacks.append(feedback)
        return self

    def add_performance_change(
        self, metric: str, old_value: float, new_value: float
    ) -> "LearningReportBuilder":
        """添加性能变化."""
        self._performance_changes.append({
            "metric": metric,
            "old": old_value,
            "new": new_value,
            "delta": new_value - old_value,
        })
        return self

    def build(self) -> ReportSection:
        """构建 ReportSection."""
        content_lines = []

        # 1. 新学习
        if self._learnings:
            content_lines.append("### New Learning")
            content_lines.append("")
            for entry in self._learnings:
                content_lines.append(f"#### {entry.action}")
                content_lines.append("")
                content_lines.append(f"- **Condition**: {entry.condition}")
                content_lines.append(f"- **Reward**: {entry.reward:+.0%}")
                content_lines.append(f"- **Confidence**: {entry.confidence:.0%}")
                content_lines.append(f"- **Experience**: {entry.experience_count} instances")
                if entry.source:
                    content_lines.append(f"- **Source**: {entry.source}")
                content_lines.append("")

        # 2. 模式更新
        if self._pattern_updates:
            content_lines.append("### Pattern Updates")
            content_lines.append("")
            content_lines.append("| Pattern | Old | New | Change |")
            content_lines.append("|---------|-----|-----|--------|")
            for update in self._pattern_updates:
                old_str = f"{update.old_value:.2f}" if update.old_value is not None else "-"
                new_str = f"{update.new_value:.2f}"
                change_emoji = {"improved": "↑", "degraded": "↓", "stable": "→"}.get(update.change, "→")
                content_lines.append(f"| {update.pattern_name} | {old_str} | {new_str} | {change_emoji} {update.change} |")
            content_lines.append("")

        # 3. 记忆反馈
        if self._memory_feedbacks:
            content_lines.append("### Memory Updates")
            content_lines.append("")
            for fb in self._memory_feedbacks:
                content_lines.append(f"- [{fb.memory_type}] {fb.action}: {fb.key} → {fb.value} (confidence: {fb.confidence:.0%})")
            content_lines.append("")

        # 4. 性能变化
        if self._performance_changes:
            content_lines.append("### Performance Delta")
            content_lines.append("")
            content_lines.append("| Metric | Old | New | Delta |")
            content_lines.append("|--------|-----|-----|-------|")
            for pc in self._performance_changes:
                delta_str = f"{pc['delta']:+.2f}"
                content_lines.append(f"| {pc['metric']} | {pc['old']:.2f} | {pc['new']:.2f} | {delta_str} |")
            content_lines.append("")

        content = "\n".join(content_lines)

        # 聚合 metrics
        metrics: list[ReportMetric] = []
        if self._learnings:
            metrics.append(ReportMetric(
                name="learning_count",
                value=float(len(self._learnings)),
                unit="count",
            ))
            avg_confidence = sum(l.confidence for l in self._learnings) / len(self._learnings)
            metrics.append(ReportMetric(
                name="learning_confidence_avg",
                value=avg_confidence,
                unit="%",
            ))
            avg_reward = sum(l.reward for l in self._learnings) / len(self._learnings)
            metrics.append(ReportMetric(
                name="learning_reward_avg",
                value=avg_reward,
                unit="%",
            ))

        if self._pattern_updates:
            metrics.append(ReportMetric(
                name="pattern_updates",
                value=float(len(self._pattern_updates)),
                unit="count",
            ))

        if self._memory_feedbacks:
            metrics.append(ReportMetric(
                name="memory_updates",
                value=float(len(self._memory_feedbacks)),
                unit="count",
            ))

        # 整体置信度
        overall_confidence = 0.0
        if self._learnings:
            overall_confidence = sum(l.confidence for l in self._learnings) / len(self._learnings)

        # 摘要
        parts = []
        if self._learnings:
            parts.append(f"{len(self._learnings)} new learnings")
        if self._pattern_updates:
            parts.append(f"{len(self._pattern_updates)} pattern updates")
        if self._memory_feedbacks:
            parts.append(f"{len(self._memory_feedbacks)} memory updates")
        summary = "Learning: " + (", ".join(parts) if parts else "no updates")

        # 证据
        evidence: list[ReportEvidence] = []
        for entry in self._learnings:
            if entry.experience_count > 1:
                evidence.append(ReportEvidence(
                    source="ExecutionFeedback",
                    reference=f"{entry.action}: {entry.experience_count} experiences, reward {entry.reward:+.0%}",
                    confidence=entry.confidence,
                ))

        section = ReportSection(
            type=ReportType.LEARNING,
            title="Growth Agent Learning Report",
            content=content,
            summary=summary,
            metrics=metrics,
            evidence=evidence,
            confidence=overall_confidence,
        )

        return section


# ═══════════════════════════════════════════════════════════════
# Helper: Quick Learning Report
# ═══════════════════════════════════════════════════════════════


def create_learning_report(
    learnings: list[dict] | None = None,
    pattern_updates: list[dict] | None = None,
    memory_feedbacks: list[dict] | None = None,
) -> ReportSection:
    """快捷创建学习报告.

    Args:
        learnings: 学习记录 [{action, condition, reward, confidence}]
        pattern_updates: 模式更新 [{name, old, new, change}]
        memory_feedbacks: 记忆反馈 [{type, key, action, value, confidence}]

    Returns:
        ReportSection: 学习报告 section
    """
    builder = LearningReportBuilder()

    if learnings:
        for l in learnings:
            builder.add_learning(LearningEntry(
                action=l["action"],
                condition=l.get("condition", ""),
                reward=l.get("reward", 0.0),
                confidence=l.get("confidence", 0.0),
                experience_count=l.get("experience_count", 1),
                source=l.get("source", ""),
            ))

    if pattern_updates:
        for p in pattern_updates:
            builder.add_pattern_update(PatternUpdate(
                pattern_name=p["name"],
                old_value=p.get("old"),
                new_value=p.get("new", 0.0),
                change=p.get("change", "stable"),
                description=p.get("description", ""),
            ))

    if memory_feedbacks:
        for m in memory_feedbacks:
            builder.add_memory_feedback(MemoryFeedback(
                memory_type=m["type"],
                key=m["key"],
                action=m["action"],
                value=m["value"],
                confidence=m.get("confidence", 1.0),
            ))

    return builder.build()