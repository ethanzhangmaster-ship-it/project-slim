"""E13.7.4.4 Decision Report — 决策报告生成器.

决策报告展示 Agent "为什么这么做"：
  - 观测数据 (当前指标，趋势)
  - 推理过程 (发现了什么模式)
  - 决策结论 (具体动作)
  - 置信度 (Agent 有多确定)
  - 证据 (来自哪里，相似案例)

连接:
  - E13.7.2 LLM Reasoning: 推理过程
  - E13.7.3 Knowledge Graph: 模式匹配证据
  - Memory Layer: 历史相似案例
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

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
class ObservedMetric:
    """观测到的单个指标."""

    name: str
    value: float
    previous_value: float | None = None
    unit: str = ""
    threshold: float | None = None
    threshold_breach: bool = False

    @property
    def change(self) -> float:
        if self.previous_value is None or self.previous_value == 0:
            return 0.0
        return self.value - self.previous_value

    @property
    def change_pct(self) -> float:
        if self.previous_value is None or self.previous_value == 0:
            return 0.0
        return (self.value - self.previous_value) / self.previous_value

    @property
    def trend(self) -> str:
        if self.change_pct > 0.1:
            return "up"
        if self.change_pct < -0.1:
            return "down"
        return "stable"

    def to_report_metric(self) -> ReportMetric:
        return ReportMetric(
            name=self.name,
            value=self.value,
            unit=self.unit,
            trend=self.trend,
            change=self.change,
            change_pct=self.change_pct,
            threshold=self.threshold,
            is_alert=self.threshold_breach,
        )


@dataclass
class DecisionEvidence:
    """决策支撑证据."""

    source: str          # "PatternMemory", "KnowledgeGraph", "LLM Reasoning"
    description: str    # "相似案例: 18"
    confidence: float   # 证据可信度
    reference: str = "" # 具体引用

    def to_report_evidence(self) -> ReportEvidence:
        return ReportEvidence(
            source=self.source,
            reference=self.description if not self.reference else self.reference,
            confidence=self.confidence,
        )


@dataclass
class DecisionHypothesis:
    """决策基于的假设."""

    hypothesis: str
    confidence: float
    validation_method: str = ""


@dataclass
class DecisionEntry:
    """单个决策."""

    action: str                  # "CREATE_CREATIVE_VARIANTS", "INCREASE_BUDGET", "PAUSE_CAMPAIGN"
    target: str                  # campaign id / creative id
    reason: str                  # 原因说明
    confidence: float
    evidence: list[DecisionEvidence] = field(default_factory=list)
    expected_outcome: str = ""   # "期望 CTR +15%, ROAS +8%"
    risk_level: str = "low"      # "low", "medium", "high"


# ═══════════════════════════════════════════════════════════════
# DecisionReportBuilder
# ═══════════════════════════════════════════════════════════════


class DecisionReportBuilder:
    """决策报告生成器.

    使用方式:
        builder = DecisionReportBuilder()
        builder.add_observation("ROAS", 0.53, previous=0.75, unit="")
        builder.add_observation("Creative fatigue", 0.82, threshold=0.7)
        builder.add_reasoning("当前素材 CTR 下降 34%，同 DNA 已运行 12 天")
        builder.add_decision(DecisionEntry(
            action="CREATE_CREATIVE_VARIANTS",
            target="Witch Merge",
            reason="素材疲劳触发",
            confidence=0.87,
            evidence=[...],
        ))
        section = builder.build()
    """

    def __init__(self):
        self._observations: list[ObservedMetric] = []
        self._reasoning_points: list[str] = []
        self._hypotheses: list[DecisionHypothesis] = []
        self._decisions: list[DecisionEntry] = []

    def add_observation(
        self,
        name: str,
        value: float,
        previous_value: float | None = None,
        unit: str = "",
        threshold: float | None = None,
    ) -> "DecisionReportBuilder":
        """添加观测指标."""
        threshold_breach = False
        if threshold is not None:
            # 默认超过阈值算 breach，可根据需求调整
            threshold_breach = value > threshold
        self._observations.append(ObservedMetric(
            name=name,
            value=value,
            previous_value=previous_value,
            unit=unit,
            threshold=threshold,
            threshold_breach=threshold_breach,
        ))
        return self

    def add_reasoning(self, reasoning: str) -> "DecisionReportBuilder":
        """添加推理点."""
        self._reasoning_points.append(reasoning)
        return self

    def add_hypothesis(
        self,
        hypothesis: str,
        confidence: float,
        validation_method: str = "",
    ) -> "DecisionReportBuilder":
        """添加假设."""
        self._hypotheses.append(DecisionHypothesis(
            hypothesis=hypothesis,
            confidence=confidence,
            validation_method=validation_method,
        ))
        return self

    def add_decision(self, decision: DecisionEntry) -> "DecisionReportBuilder":
        """添加决策."""
        self._decisions.append(decision)
        return self

    def build(self) -> ReportSection:
        """构建 ReportSection."""
        # 生成 content (Markdown)
        content_lines = []

        # 1. Observation
        if self._observations:
            content_lines.append("### Observation")
            content_lines.append("")
            # content_lines.append("| Metric | Current | Previous | Change | Threshold |")
            # content_lines.append("|--------|---------|----------|--------|-----------|")
            # for obs in self._observations:
            #     prev_str = f"{obs.previous_value}{obs.unit}" if obs.previous_value is not None else "-"
            #     change_str = f"{obs.change_pct:+.0%}" if obs.previous_value is not None else "-"
            #     thresh_str = str(obs.threshold) if obs.threshold is not None else "-"
            #     content_lines.append(f"| {obs.name} | {obs.value}{obs.unit} | {prev_str} | {change_str} | {thresh_str} |")
            # content_lines.append("")
            content_lines.append("")

        # 2. Reasoning
        if self._reasoning_points:
            content_lines.append("### Reasoning")
            content_lines.append("")
            for point in self._reasoning_points:
                content_lines.append(f"- {point}")
            content_lines.append("")

        # 3. Hypotheses
        if self._hypotheses:
            content_lines.append("### Hypothesis")
            content_lines.append("")
            for hypo in self._hypotheses:
                content_lines.append(f"- **{hypo.hypothesis}** (confidence: {hypo.confidence:.0%})")
                if hypo.validation_method:
                    content_lines.append(f"  - Validation: {hypo.validation_method}")
            content_lines.append("")

        # 4. Decision
        content_lines.append("### Decision")
        content_lines.append("")
        for dec in self._decisions:
            risk_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(dec.risk_level, "🟢")
            content_lines.append(f"#### {risk_emoji} {dec.action} → {dec.target}")
            content_lines.append("")
            content_lines.append(f"- **Reason**: {dec.reason}")
            content_lines.append(f"- **Confidence**: {dec.confidence:.0%}")
            content_lines.append(f"- **Risk**: {dec.risk_level}")
            if dec.expected_outcome:
                content_lines.append(f"- **Expected**: {dec.expected_outcome}")
            if dec.evidence:
                content_lines.append("- **Evidence**:")
                for ev in dec.evidence:
                    content_lines.append(f"  - {ev.description} ({ev.confidence:.0%})")
            content_lines.append("")

        content = "\n".join(content_lines)

        # 聚合 metrics
        metrics = [obs.to_report_metric() for obs in self._observations]

        # 聚合 evidence
        evidence: list[ReportEvidence] = []
        for dec in self._decisions:
            for ev in dec.evidence:
                evidence.append(ev.to_report_evidence())

        # 计算整体置信度 (平均)
        if self._decisions:
            overall_confidence = sum(d.confidence for d in self._decisions) / len(self._decisions)
        elif self._hypotheses:
            overall_confidence = sum(h.confidence for h in self._hypotheses) / len(self._hypotheses)
        else:
            overall_confidence = 0.0

        # 一句话摘要
        if self._decisions:
            actions = [d.action for d in self._decisions]
            summary = f"Decision: {', '.join(actions)} (confidence {overall_confidence:.0%})"
        else:
            summary = "Observation and reasoning completed, no decision."

        section = ReportSection(
            type=ReportType.DECISION,
            title="Growth Agent Decision Report",
            content=content,
            summary=summary,
            metrics=metrics,
            evidence=evidence,
            confidence=overall_confidence,
        )

        return section


# ═══════════════════════════════════════════════════════════════
# Helper: Create Decision Report from Raw Data
# ═══════════════════════════════════════════════════════════════


def create_decision_report(
    campaign_name: str,
    observations: dict[str, tuple[float, float | None]],  # name -> (current, previous)
    reasoning_points: list[str],
    decisions: list[dict[str, Any]],
    similar_cases: int = 0,
    success_rate: float = 0.0,
) -> ReportSection:
    """快捷创建决策报告.

    Args:
        campaign_name: 活动名称
        observations: 观测数据字典
        reasoning_points: 推理点列表
        decisions: 决策列表 [{action, target, reason, confidence}]
        similar_cases: 相似案例数
        success_rate: 相似案例成功率

    Returns:
        ReportSection: 决策报告 section
    """
    builder = DecisionReportBuilder()

    # 添加观测
    for name, (value, prev) in observations.items():
        builder.add_observation(name, value, prev)

    # 添加推理
    for point in reasoning_points:
        builder.add_reasoning(point)

    # 添加证据 (相似案例)
    evidence: list[DecisionEvidence] = []
    if similar_cases > 0:
        evidence.append(DecisionEvidence(
            source="PatternMemory",
            description=f"similar cases = {similar_cases}, success rate = {success_rate:.0%}",
            confidence=min(0.5 + success_rate * 0.5, 0.95),
        ))

    # 添加决策
    for d in decisions:
        entry = DecisionEntry(
            action=d["action"],
            target=d.get("target", campaign_name),
            reason=d["reason"],
            confidence=d["confidence"],
            evidence=evidence,
            expected_outcome=d.get("expected", ""),
            risk_level=d.get("risk_level", "low"),
        )
        builder.add_decision(entry)

    return builder.build()