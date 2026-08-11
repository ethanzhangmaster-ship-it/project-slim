"""P3.2 — CEO Daily Report 模型层。

把 P3.1 / E17 / P2 的最终产物收敛成「CEO 运营决策单」的可序列化模型。

纪律（与全库一致）：
- 纯 dataclass + to_dict / from_dict，无 LLM、无 IO
- str Enum 序列化用 .value（py3.11 兼容）
- 确定性：同数据同输出，可复现到 1e-6
- 本层只持有「聚合后的展示数据」，不持有任何执行/决策原始对象
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List


# --------------------------------------------------------------------------- #
# 行动三态模型（P3.2 重点）
# --------------------------------------------------------------------------- #
class ActionState(str, Enum):
    """行动执行三态——唯一权威出口，收敛自 E17.9 ActionKind。"""

    AUTO = "auto"          # ✅ 已自动执行（EXECUTE + Simulation PASS，经 P2.4）
    APPROVAL = "approval"  # 🖐 等 CEO / 人工审批
    BLOCKED = "blocked"    # ⛔ 被模拟闸门 / 策略阻断，未进执行层


class CEOActionStatus(str, Enum):
    """行动更细的责任状态（WHY 的可消费形态）。"""

    EXECUTED = "executed"               # AUTO：已落地（经 P2.4）
    AWAITING_APPROVAL = "awaiting"      # APPROVAL：等 CEO 拍板
    PREVENTED = "prevented"             # BLOCKED：被闸门拦下


# 人类可读的三态标题（供 Renderer 直接用）
ACTION_STATE_TITLE: Dict[str, str] = {
    ActionState.AUTO.value: "✅ 已自动执行（AUTO EXECUTE）",
    ActionState.APPROVAL.value: "🖐 待你审批（APPROVAL REQUIRED）",
    ActionState.BLOCKED.value: "⛔ 已被阻断（BLOCKED）",
}


# --------------------------------------------------------------------------- #
# 行动队列元素
# --------------------------------------------------------------------------- #
@dataclass
class CEOAction:
    """决策单里的一行行动（含责任来源与 WHY 解释）。"""

    action_id: str
    game_id: str
    action_type: str
    source: str
    priority: float
    execution_mode: ActionState
    status: CEOActionStatus
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["execution_mode"] = self.execution_mode.value
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CEOAction":
        return cls(
            action_id=str(d["action_id"]),
            game_id=str(d["game_id"]),
            action_type=str(d.get("action_type", "")),
            source=str(d.get("source", "")),
            priority=float(d.get("priority", 0.0)),
            execution_mode=ActionState(d["execution_mode"]),
            status=CEOActionStatus(d["status"]),
            explanation=str(d.get("explanation", "")),
        )


# --------------------------------------------------------------------------- #
# 各 section 模型
# --------------------------------------------------------------------------- #
@dataclass
class HealthSummary:
    company_status: str
    status_label: str
    game_count: int
    total_revenue: float
    total_dau: int
    total_spend: float
    avg_confidence: float
    at_risk: List[str] = field(default_factory=list)
    auto_count: int = 0
    approval_count: int = 0
    blocked_count: int = 0
    observed_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "HealthSummary":
        return cls(
            company_status=str(d.get("company_status", "")),
            status_label=str(d.get("status_label", "")),
            game_count=int(d.get("game_count", 0)),
            total_revenue=float(d.get("total_revenue", 0.0)),
            total_dau=int(d.get("total_dau", 0)),
            total_spend=float(d.get("total_spend", 0.0)),
            avg_confidence=float(d.get("avg_confidence", 0.0)),
            at_risk=list(d.get("at_risk", [])),
            auto_count=int(d.get("auto_count", 0)),
            approval_count=int(d.get("approval_count", 0)),
            blocked_count=int(d.get("blocked_count", 0)),
            observed_count=int(d.get("observed_count", 0)),
        )


@dataclass
class OpportunityItem:
    rank: int
    game_id: str
    action: str
    opportunity_type: str
    priority_score: float
    expected_value: float
    confidence: float
    urgency: float
    sim_gate: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "OpportunityItem":
        return cls(
            rank=int(d.get("rank", 0)),
            game_id=str(d.get("game_id", "")),
            action=str(d.get("action", "")),
            opportunity_type=str(d.get("opportunity_type", "")),
            priority_score=float(d.get("priority_score", 0.0)),
            expected_value=float(d.get("expected_value", 0.0)),
            confidence=float(d.get("confidence", 0.0)),
            urgency=float(d.get("urgency", 0.0)),
            sim_gate=str(d.get("sim_gate", "")),
        )


@dataclass
class RiskItem:
    level: str            # "info" | "warn" | "critical"
    title: str
    detail: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RiskItem":
        return cls(
            level=str(d.get("level", "info")),
            title=str(d.get("title", "")),
            detail=str(d.get("detail", "")),
        )


@dataclass
class ExecutionSummary:
    total_executions: int
    success: int
    failed: int
    rollback: int
    blocked: int
    health_level: str
    warnings: List[str] = field(default_factory=list)
    recovered: int = 0
    escalated: int = 0
    real_api_called: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ExecutionSummary":
        return cls(
            total_executions=int(d.get("total_executions", 0)),
            success=int(d.get("success", 0)),
            failed=int(d.get("failed", 0)),
            rollback=int(d.get("rollback", 0)),
            blocked=int(d.get("blocked", 0)),
            health_level=str(d.get("health_level", "")),
            warnings=list(d.get("warnings", [])),
            recovered=int(d.get("recovered", 0)),
            escalated=int(d.get("escalated", 0)),
            real_api_called=bool(d.get("real_api_called", False)),
        )


# --------------------------------------------------------------------------- #
# 主报告
# --------------------------------------------------------------------------- #
@dataclass
class CEODailyReport:
    """一张 CEO 运营决策单。"""

    report_id: str
    date: str
    health_summary: HealthSummary
    opportunities: List[OpportunityItem]
    actions: List[CEOAction]
    risks: List[RiskItem]
    learning_summary: List[str]
    execution_summary: ExecutionSummary
    portfolio_recommendation: Optional[Dict[str, Any]] = None
    memory_reasoning: Optional[Dict[str, Any]] = None   # P3.6.1 知识推理段
    strategic_memory: Optional[Dict[str, Any]] = None   # P3.6.2 战略规律段
    reflection: Optional[Dict[str, Any]] = None         # P3.6.3 认知复盘段
    governance: Optional[Dict[str, Any]] = None         # P3.6.4 记忆治理段
    real_api_called: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "date": self.date,
            "company_status": self.health_summary.company_status,
            "real_api_called": bool(self.real_api_called),
            "health_summary": self.health_summary.to_dict(),
            "opportunities": [o.to_dict() for o in self.opportunities],
            "actions": [a.to_dict() for a in self.actions],
            "risks": [r.to_dict() for r in self.risks],
            "learning_summary": list(self.learning_summary),
            "execution_summary": self.execution_summary.to_dict(),
            "portfolio_recommendation": (
                dict(self.portfolio_recommendation)
                if self.portfolio_recommendation else None
            ),
            "memory_reasoning": (
                dict(self.memory_reasoning) if self.memory_reasoning else None
            ),
            "strategic_memory": (
                dict(self.strategic_memory) if self.strategic_memory else None
            ),
            "reflection": (
                dict(self.reflection) if self.reflection else None
            ),
            "governance": (
                dict(self.governance) if self.governance else None
            ),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CEODailyReport":
        hs = d.get("health_summary", {})
        return cls(
            report_id=str(d["report_id"]),
            date=str(d["date"]),
            health_summary=HealthSummary.from_dict(hs),
            opportunities=[
                OpportunityItem.from_dict(x) for x in d.get("opportunities", [])
            ],
            actions=[CEOAction.from_dict(x) for x in d.get("actions", [])],
            risks=[RiskItem.from_dict(x) for x in d.get("risks", [])],
            learning_summary=list(d.get("learning_summary", [])),
            execution_summary=ExecutionSummary.from_dict(
                d.get("execution_summary", {})
            ),
            portfolio_recommendation=(
                dict(d["portfolio_recommendation"])
                if d.get("portfolio_recommendation") else None
            ),
            memory_reasoning=(
                dict(d["memory_reasoning"]) if d.get("memory_reasoning") else None
            ),
            strategic_memory=(
                dict(d["strategic_memory"]) if d.get("strategic_memory") else None
            ),
            reflection=(
                dict(d["reflection"]) if d.get("reflection") else None
            ),
            governance=(
                dict(d["governance"]) if d.get("governance") else None
            ),
            real_api_called=bool(d.get("real_api_called", False)),
        )

    # 便捷访问
    @property
    def auto_actions(self) -> List[CEOAction]:
        return [a for a in self.actions if a.execution_mode == ActionState.AUTO]

    @property
    def approval_actions(self) -> List[CEOAction]:
        return [a for a in self.actions if a.execution_mode == ActionState.APPROVAL]

    @property
    def blocked_actions(self) -> List[CEOAction]:
        return [a for a in self.actions if a.execution_mode == ActionState.BLOCKED]


__all__ = [
    "ActionState",
    "CEOActionStatus",
    "ACTION_STATE_TITLE",
    "CEOAction",
    "HealthSummary",
    "OpportunityItem",
    "RiskItem",
    "ExecutionSummary",
    "CEODailyReport",
]
