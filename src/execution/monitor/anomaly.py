"""P2.5.5 Anomaly Detector（Rule1~4）。

对一组 ExecutionSummary 做异常检测，输出 AnomalyReport。Monitor 只报警、不拦截、
不修改执行结果、不绕过 Approval。

Rule1 失败率>10%            -> RED      (FAILURE_RATE_HIGH)
Rule2 rollback率>5%         -> WARNING  (ROLLBACK_RATE_HIGH)
Rule3 同日同动作同target>3次 -> WARNING  (ACTION_LOOP)
Rule4 请求动作≠实际动作      -> BLOCK+ALERT (EXECUTION_DRIFT)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.execution.monitor.collector import _parse_iso
from src.execution.monitor.models import (
    SEVERITY_ALERT,
    SEVERITY_BLOCK,
    SEVERITY_RED,
    SEVERITY_WARNING,
    ExecutionMetrics,
    ExecutionSummary,
)

# 阈值常量
FAILURE_RATE_RED = 0.10      # Rule1：失败率 > 10% 触发 RED
ROLLBACK_RATE_WARNING = 0.05  # Rule2：回滚率 > 5% 触发 WARNING
ACTION_LOOP_THRESHOLD = 3     # Rule3：同组出现次数 > 3（即 ≥4）触发

SEVERITY_ORDER = [SEVERITY_WARNING, SEVERITY_RED, SEVERITY_BLOCK, SEVERITY_ALERT]


def _severity_rank(sev: str) -> int:
    try:
        return SEVERITY_ORDER.index(sev)
    except ValueError:
        return 0


def _date_of(timestamp: str) -> str:
    dt = _parse_iso(timestamp)
    return dt.strftime("%Y-%m-%d") if dt else ""


@dataclass
class AnomalyFinding:
    """单条异常发现。"""

    rule: str
    severity: str
    code: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


@dataclass
class AnomalyReport:
    """一组执行的异常检测报告。"""

    scope: str
    findings: List[AnomalyFinding] = field(default_factory=list)
    generated_at: str = ""
    report_id: str = ""

    def __post_init__(self) -> None:
        if not self.report_id:
            self.report_id = f"anr_{uuid.uuid4().hex[:12]}"
        if not self.generated_at:
            self.generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    @property
    def severity(self) -> str:
        if not self.findings:
            return ""
        return max((f.severity for f in self.findings), key=_severity_rank)

    @property
    def empty(self) -> bool:
        return len(self.findings) == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "scope": self.scope,
            "severity": self.severity,
            "generated_at": self.generated_at,
            "findings": [f.to_dict() for f in self.findings],
        }

    def to_markdown(self) -> str:
        lines = [f"# 执行异常报告（Anomaly Report · {self.scope}）", ""]
        if self.empty:
            lines.append("- 状态：**正常**，未发现异常")
            return "\n".join(lines)
        lines.append(f"- 最高严重度：**{self.severity}** ｜ 发现 {len(self.findings)} 条")
        lines.append("")
        for f in self.findings:
            lines.append(f"- [{f.severity}] **{f.code}**（{f.rule}）：{f.message}")
        return "\n".join(lines)


class AnomalyDetector:
    """基于规则的异常检测器（确定性、无 LLM）。"""

    def analyze(
        self,
        summaries: List[ExecutionSummary],
        scope: str = "all",
    ) -> AnomalyReport:
        findings: List[AnomalyFinding] = []

        # Rule1：失败率
        metrics = ExecutionMetrics.from_summaries([s.to_dict() for s in summaries])
        if metrics.total_executions > 0 and metrics.failure_rate > FAILURE_RATE_RED:
            findings.append(
                AnomalyFinding(
                    rule="Rule1",
                    severity=SEVERITY_RED,
                    code="FAILURE_RATE_HIGH",
                    message=(
                        f"失败率 {metrics.failure_rate:.1%} 超过阈值 "
                        f"{FAILURE_RATE_RED:.0%}"
                    ),
                    details={"failure_rate": metrics.failure_rate},
                )
            )

        # Rule2：回滚率
        if metrics.total_executions > 0 and metrics.rollback_rate > ROLLBACK_RATE_WARNING:
            findings.append(
                AnomalyFinding(
                    rule="Rule2",
                    severity=SEVERITY_WARNING,
                    code="ROLLBACK_RATE_HIGH",
                    message=(
                        f"回滚率 {metrics.rollback_rate:.1%} 超过阈值 "
                        f"{ROLLBACK_RATE_WARNING:.0%}"
                    ),
                    details={"rollback_rate": metrics.rollback_rate},
                )
            )

        # Rule3：动作循环（同日同动作同 target > 3 次）
        groups: Dict[tuple, int] = {}
        for s in summaries:
            if not s.target:
                continue
            key = (s.action, s.target, _date_of(s.timestamp))
            groups[key] = groups.get(key, 0) + 1
        for (action, target, day), count in groups.items():
            if count > ACTION_LOOP_THRESHOLD:
                findings.append(
                    AnomalyFinding(
                        rule="Rule3",
                        severity=SEVERITY_WARNING,
                        code="ACTION_LOOP",
                        message=(
                            f"动作 {action} 对 {target} 在 {day} 重复 {count} 次"
                            f"（> {ACTION_LOOP_THRESHOLD}）"
                        ),
                        details={
                            "action": action,
                            "target": target,
                            "date": day,
                            "count": count,
                        },
                    )
                )

        # Rule4：执行漂移（请求动作 ≠ 实际动作）
        for s in summaries:
            if s.drifted:
                findings.append(
                    AnomalyFinding(
                        rule="Rule4",
                        severity=SEVERITY_ALERT,
                        code="EXECUTION_DRIFT",
                        message=(
                            f"执行漂移：请求 {s.intended_action} ≠ 实际 {s.action}"
                            f"（execution_id={s.execution_id}）"
                        ),
                        details={
                            "execution_id": s.execution_id,
                            "intended_action": s.intended_action,
                            "action": s.action,
                        },
                    )
                )

        return AnomalyReport(scope=scope, findings=findings)


__all__ = [
    "AnomalyFinding",
    "AnomalyReport",
    "AnomalyDetector",
    "FAILURE_RATE_RED",
    "ROLLBACK_RATE_WARNING",
    "ACTION_LOOP_THRESHOLD",
]
