"""P2.5.6 Execution Daily Report（执行每日报告）。

把一天（或任意窗口）的执行可观测结果汇总成 Dashboard 可读的 Markdown 报告。
内容（规格）：Date / Executions / Success / Failed / Rollback / Provider /
Warnings / Learning。

Monitor 输出端之一；只呈现观察结论，不做决策。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.execution.monitor.anomaly import AnomalyReport, AnomalyDetector
from src.execution.monitor.collector import ExecutionEventCollector
from src.execution.monitor.models import ExecutionSummary
from src.execution.safe_executor.models import SafeExecutionOutcome


@dataclass
class ExecutionDailyReport:
    """执行每日报告。"""

    date: str
    total_executions: int = 0
    success: int = 0
    failed: int = 0
    rollback: int = 0
    blocked: int = 0
    providers: Dict[str, int] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    learnings: List[str] = field(default_factory=list)
    health_level: str = ""
    report_id: str = ""

    def __post_init__(self) -> None:
        if not self.report_id:
            self.report_id = f"edr_{uuid.uuid4().hex[:12]}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "date": self.date,
            "total_executions": self.total_executions,
            "success": self.success,
            "failed": self.failed,
            "rollback": self.rollback,
            "blocked": self.blocked,
            "providers": dict(self.providers),
            "warnings": list(self.warnings),
            "learnings": list(self.learnings),
            "health_level": self.health_level,
        }

    def to_markdown(self) -> str:
        lines = [f"# 执行每日报告（Execution Daily Report · {self.date}）", ""]
        lines.append(
            f"- 执行 **{self.total_executions}** ｜ 成功 **{self.success}** ｜ "
            f"失败 **{self.failed}** ｜ 回滚 **{self.rollback}** ｜ "
            f"拦截 **{self.blocked}**"
        )
        if self.health_level:
            lines.append(f"- 健康等级：**{self.health_level}**")
        lines.append("")
        if self.providers:
            lines.append("## Provider 分布")
            lines.append("")
            lines.append("| Provider | 执行数 |")
            lines.append("|---|---|")
            for p, c in sorted(self.providers.items(), key=lambda kv: -kv[1]):
                lines.append(f"| {p} | {c} |")
            lines.append("")
        if self.warnings:
            lines.append("## Warnings")
            lines.append("")
            for w in self.warnings:
                lines.append(f"- ⚠️ {w}")
            lines.append("")
        if self.learnings:
            lines.append("## Learning（回流记忆）")
            lines.append("")
            for l in self.learnings:
                lines.append(f"- 🧠 {l}")
            lines.append("")
        return "\n".join(lines)


class ExecutionReporter:
    """从一批执行产出每日报告。"""

    def build(
        self,
        date: str,
        outcomes: List[SafeExecutionOutcome],
        anomalies: Optional[AnomalyReport] = None,
        learnings: Optional[List[str]] = None,
        health_level: str = "",
    ) -> ExecutionDailyReport:
        collector = ExecutionEventCollector()
        summaries: List[ExecutionSummary] = [
            collector.summarize(None, o) for o in outcomes
        ]

        success = failed = rollback = blocked = 0
        providers: Dict[str, int] = {}
        for s in summaries:
            providers[s.provider or "unknown"] = providers.get(s.provider or "unknown", 0) + 1
            if s.verdict in ("EXECUTED", "RETURN_EXISTING"):
                success += 1
            elif s.verdict in ("FAILED", "ESCALATED"):
                failed += 1
            elif s.verdict == "ROLLED_BACK":
                rollback += 1
            elif s.verdict == "BLOCKED":
                blocked += 1

        warnings: List[str] = []
        if anomalies is not None and not anomalies.empty:
            for f in anomalies.findings:
                warnings.append(f"[{f.severity}] {f.code}: {f.message}")

        return ExecutionDailyReport(
            date=date,
            total_executions=len(summaries),
            success=success,
            failed=failed,
            rollback=rollback,
            blocked=blocked,
            providers=providers,
            warnings=warnings,
            learnings=list(learnings or []),
            health_level=health_level,
        )


__all__ = [
    "ExecutionDailyReport",
    "ExecutionReporter",
]
