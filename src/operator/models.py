"""P3.1 Daily Operator Scheduler — 模型层。

把一次「每日增长经营循环」的产出压缩成可序列化的运行结果：
- StageResult：单阶段结论（ok / skipped / failed）
- RunStatus：整轮状态（completed / partial / skipped / failed）
- OperatorRunResult：一轮 Daily Cycle 的完整交付物

纪律（与全库一致）：
- 纯 dataclass + to_dict / from_dict，无 LLM、无 IO
- str Enum 序列化用 .value 归一化（py3.11 str(Enum) 兼容陷阱）
- 确定性：同数据同输出
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List

# 11 个阶段（顺序即执行顺序）
STAGE_REALITY = "reality_refresh"
STAGE_AUDIT = "audit"
STAGE_OPPORTUNITIES = "opportunities"
STAGE_SIMULATIONS = "simulations"
STAGE_DECISIONS = "decisions"
STAGE_APPROVAL = "approval"
STAGE_EXECUTIONS = "executions"
STAGE_MONITOR = "monitor"
STAGE_RECOVERY = "recovery"
STAGE_MEMORY = "memory"
STAGE_LIVEOPS = "liveops"          # 跨 Agent 协同：LiveOps 流失分析 + 回流活动设计
STAGE_STRATEGY = "strategy_loop"
STAGE_PORTFOLIO = "portfolio"
STAGE_CEO_REPORT = "ceo_report"
STAGE_REPORT = "report"

ALL_STAGES = (
    STAGE_REALITY,
    STAGE_AUDIT,
    STAGE_OPPORTUNITIES,
    STAGE_SIMULATIONS,
    STAGE_DECISIONS,
    STAGE_APPROVAL,
    STAGE_EXECUTIONS,
    STAGE_MONITOR,
    STAGE_RECOVERY,
    STAGE_MEMORY,
    STAGE_LIVEOPS,
    STAGE_STRATEGY,
    STAGE_PORTFOLIO,
    STAGE_CEO_REPORT,
    STAGE_REPORT,
)

STAGE_OK = "ok"
STAGE_SKIPPED = "skipped"
STAGE_FAILED = "failed"


def _as_str(v: Any) -> str:
    """py3.11 str-Enum 序列化归一化（与 P2.3 同纪律）。"""
    return str(getattr(v, "value", v))


@dataclass
class StageResult:
    """单阶段结论。payload 只放可 JSON 序列化的摘要，不放原始对象。"""

    stage: str
    status: str = STAGE_OK
    detail: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.stage not in ALL_STAGES:
            raise ValueError(f"unknown stage: {self.stage}")
        if self.status not in (STAGE_OK, STAGE_SKIPPED, STAGE_FAILED):
            raise ValueError(f"invalid stage status: {self.status}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage,
            "status": self.status,
            "detail": self.detail,
            "payload": dict(self.payload),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StageResult":
        return cls(
            stage=str(d["stage"]),
            status=str(d.get("status", STAGE_OK)),
            detail=str(d.get("detail", "")),
            payload=dict(d.get("payload", {})),
        )


class RunStatus(str, Enum):
    COMPLETED = "completed"  # 全阶段 ok / skipped
    PARTIAL = "partial"      # 有阶段 failed，但整轮未中断
    SKIPPED = "skipped"      # 幂等门拦截：当日已跑过（force=True 可重跑）
    FAILED = "failed"        # 不可恢复异常（编排层兜底）


@dataclass
class OperatorRunResult:
    """一轮 Daily Cycle 的完整交付物。"""

    run_id: str
    date: str
    status: RunStatus = RunStatus.COMPLETED
    stages: List[StageResult] = field(default_factory=list)
    decisions: Dict[str, int] = field(default_factory=dict)
    executions: Dict[str, int] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    report_id: str = ""
    real_api_called: bool = False
    summary: Dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status in (RunStatus.COMPLETED, RunStatus.PARTIAL)

    def stage(self, name: str) -> StageResult:
        for s in self.stages:
            if s.stage == name:
                return s
        raise KeyError(name)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "date": self.date,
            "status": _as_str(self.status),
            "stages": [s.to_dict() for s in self.stages],
            "decisions": dict(self.decisions),
            "executions": dict(self.executions),
            "errors": list(self.errors),
            "report_id": self.report_id,
            "real_api_called": bool(self.real_api_called),
            "summary": dict(self.summary),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "OperatorRunResult":
        return cls(
            run_id=str(d["run_id"]),
            date=str(d["date"]),
            status=RunStatus(str(d.get("status", "completed"))),
            stages=[StageResult.from_dict(x) for x in d.get("stages", [])],
            decisions={k: int(v) for k, v in d.get("decisions", {}).items()},
            executions={k: int(v) for k, v in d.get("executions", {}).items()},
            errors=[str(e) for e in d.get("errors", [])],
            report_id=str(d.get("report_id", "")),
            real_api_called=bool(d.get("real_api_called", False)),
            summary=dict(d.get("summary", {})),
        )


__all__ = [
    "StageResult",
    "RunStatus",
    "OperatorRunResult",
    "ALL_STAGES",
    "STAGE_OK",
    "STAGE_SKIPPED",
    "STAGE_FAILED",
    "STAGE_REALITY",
    "STAGE_AUDIT",
    "STAGE_OPPORTUNITIES",
    "STAGE_SIMULATIONS",
    "STAGE_DECISIONS",
    "STAGE_APPROVAL",
    "STAGE_EXECUTIONS",
    "STAGE_MONITOR",
    "STAGE_RECOVERY",
    "STAGE_MEMORY",
    "STAGE_STRATEGY",
    "STAGE_PORTFOLIO",
    "STAGE_CEO_REPORT",
    "STAGE_REPORT",
]
