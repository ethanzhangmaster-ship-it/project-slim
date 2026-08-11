"""E17.9 Daily Growth Operator — 模型层。

把 E17.1→E17.8 的全链路产物压缩成「CEO 今天早上要看的东西」：
- CompanyStatus：公司状态分层（Healthy / Attention / Critical，确定性规则）
- GamePriority：每游戏优先级（Priority = Impact × Confidence × Urgency × SimScore）
- DailyActionItem：今日行动（AUTO / APPROVAL / BLOCK）
- OperatorDayRecord：运营日记录（跨日记忆，昨天 vs 今天环比）
- DailyRunResult：一次 Daily Run 的完整产出

约定（与 E17.1–E17.8 一致）：
- 纯 dataclass + to_dict / from_dict，无 LLM、无 IO
- 枚举为 str Enum，便于 JSONL 序列化
- 确定性：同数据同输出，可复现到 1e-6
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# --------------------------------------------------------------------------- #
# 公司状态分层（确定性规则，供晨报开头一句话定调）
# --------------------------------------------------------------------------- #
class CompanyStatus(str, Enum):
    HEALTHY = "healthy"      # 🟢 正常运转
    ATTENTION = "attention"  # 🟡 有值得关注的风险
    CRITICAL = "critical"    # 🔴 需要 CEO 立即介入


STATUS_LABEL: Dict[str, str] = {
    "healthy": "🟢 健康",
    "attention": "🟡 需关注",
    "critical": "🔴 危急",
}


def classify_company(company) -> CompanyStatus:
    """从 E17.1 CompanySnapshot 确定性判层。

    - CRITICAL：舰队总收入 <= 0，或 at_risk 占比 >= 50%
    - ATTENTION：at_risk 占比 >= 20%，或平均数据置信度 < 50%
    - 其余 HEALTHY
    """
    total = company.game_count or 1
    risk_ratio = len(company.at_risk) / total
    if company.total_revenue <= 0 or risk_ratio >= 0.5:
        return CompanyStatus.CRITICAL
    if risk_ratio >= 0.2 or company.avg_confidence < 0.5:
        return CompanyStatus.ATTENTION
    return CompanyStatus.HEALTHY


# --------------------------------------------------------------------------- #
# 优先级评分（spec 公式）
# --------------------------------------------------------------------------- #
def priority_score(
    impact: float, confidence: float, urgency: float, sim_score: float
) -> float:
    """Priority = |Impact| × Confidence × Urgency × SimulationScore。

    impact 取绝对值：止损类机会的预期影响可能为负，但其「值得做的程度」
    由幅度决定；方向信息保留在 GamePriority.impact 原值里。
    """
    return round(abs(impact) * confidence * urgency * sim_score, 6)


@dataclass
class GamePriority:
    """每游戏优先级一行（CEO Top10 的元素）。"""
    rank: int
    game_id: str
    action: str
    problem: str
    opportunity_type: str = ""
    decision_type: str = ""
    gate: str = ""               # E17.8 闸门：pass / review / block / ""（未模拟）
    priority_score_value: float = 0.0
    impact: float = 0.0          # 原始预期影响（含符号）
    confidence: float = 0.0
    urgency: float = 0.0
    sim_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GamePriority":
        return cls(
            rank=int(d.get("rank", 0)),
            game_id=str(d["game_id"]),
            action=str(d.get("action", "")),
            problem=str(d.get("problem", "")),
            opportunity_type=str(d.get("opportunity_type", "")),
            decision_type=str(d.get("decision_type", "")),
            gate=str(d.get("gate", "")),
            priority_score_value=float(d.get("priority_score_value", 0.0)),
            impact=float(d.get("impact", 0.0)),
            confidence=float(d.get("confidence", 0.0)),
            urgency=float(d.get("urgency", 0.0)),
            sim_score=float(d.get("sim_score", 0.0)),
        )


# --------------------------------------------------------------------------- #
# 今日行动（安全铁律：只有 EXECUTE + 模拟 PASS 才可能是 AUTO）
# --------------------------------------------------------------------------- #
class ActionKind(str, Enum):
    AUTO = "auto"          # 已自动执行（EXECUTE + Simulation PASS）
    APPROVAL = "approval"  # 等 CEO/人工审批
    BLOCK = "block"        # 被 Simulation 闸门阻断，未进执行层


@dataclass
class DailyActionItem:
    kind: ActionKind
    game_id: str
    action: str
    detail: str = ""
    decision_audit_id: str = ""
    opportunity_type: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind.value
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DailyActionItem":
        return cls(
            kind=ActionKind(d["kind"]),
            game_id=str(d["game_id"]),
            action=str(d.get("action", "")),
            detail=str(d.get("detail", "")),
            decision_audit_id=str(d.get("decision_audit_id", "")),
            opportunity_type=str(d.get("opportunity_type", "")),
        )


# --------------------------------------------------------------------------- #
# 运营日记录（跨日记忆：第二天读昨天）
# --------------------------------------------------------------------------- #
@dataclass
class OperatorDayRecord:
    date: str
    decisions: int = 0
    executed: int = 0          # AUTO 条数
    approved: int = 0          # 待审批条数
    blocked: int = 0           # 闸门阻断条数
    observed: int = 0          # OBSERVE 决策数
    revenue_impact: float = 0.0  # AUTO 决策预期收入影响合计（相对值）
    top_game: str = ""
    company_status: str = ""
    real_api_called: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "OperatorDayRecord":
        return cls(
            date=str(d["date"]),
            decisions=int(d.get("decisions", 0)),
            executed=int(d.get("executed", 0)),
            approved=int(d.get("approved", 0)),
            blocked=int(d.get("blocked", 0)),
            observed=int(d.get("observed", 0)),
            revenue_impact=float(d.get("revenue_impact", 0.0)),
            top_game=str(d.get("top_game", "")),
            company_status=str(d.get("company_status", "")),
            real_api_called=bool(d.get("real_api_called", False)),
        )


# --------------------------------------------------------------------------- #
# Daily Run 主输出
# --------------------------------------------------------------------------- #
@dataclass
class DailyRunResult:
    """一次 Daily Run 的完整产出（晨报 + 行动 + 记录）。

    dec_report / portfolio / sim_report / exec_reports 持有上游原始对象引用，
    仅供进程内使用，不参与序列化。
    """
    date: str
    company_status: CompanyStatus = CompanyStatus.HEALTHY
    priorities: List[GamePriority] = field(default_factory=list)
    actions: List[DailyActionItem] = field(default_factory=list)
    reports: Dict[str, str] = field(default_factory=dict)  # audience -> markdown
    record: Optional[OperatorDayRecord] = None
    notified_paths: List[str] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)

    # 原始产物引用（不序列化）
    dec_report: Any = field(default=None, repr=False, compare=False)
    portfolio: Any = field(default=None, repr=False, compare=False)
    sim_report: Any = field(default=None, repr=False, compare=False)
    exec_reports: Any = field(default=None, repr=False, compare=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "company_status": self.company_status.value,
            "priorities": [p.to_dict() for p in self.priorities],
            "actions": [a.to_dict() for a in self.actions],
            "reports": dict(self.reports),
            "record": self.record.to_dict() if self.record else None,
            "notified_paths": list(self.notified_paths),
            "summary": dict(self.summary),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DailyRunResult":
        rec = d.get("record")
        return cls(
            date=str(d["date"]),
            company_status=CompanyStatus(d.get("company_status", "healthy")),
            priorities=[GamePriority.from_dict(x) for x in d.get("priorities", [])],
            actions=[DailyActionItem.from_dict(x) for x in d.get("actions", [])],
            reports=dict(d.get("reports", {})),
            record=OperatorDayRecord.from_dict(rec) if rec else None,
            notified_paths=list(d.get("notified_paths", [])),
            summary=dict(d.get("summary", {})),
        )


__all__ = [
    "CompanyStatus",
    "STATUS_LABEL",
    "classify_company",
    "priority_score",
    "GamePriority",
    "ActionKind",
    "DailyActionItem",
    "OperatorDayRecord",
    "DailyRunResult",
]
