"""E17.3 Growth Decision Engine — 模型层。

把 E17.2 的「机会」转成 E17.3 的「公司级决策」。

约定（与 E17.1 / E17.2 / E16 一致）：
- 纯 dataclass + to_dict / from_dict，无 LLM、无 IO
- 枚举为 str Enum，便于 JSON 序列化与 memory / audit 键
- DecisionType 是公司级三道门的最终出口（区别于 E16.1.1 的 AUTO/HUMAN_QUEUE/RECORD_ONLY）
- ActionDomain 把 OpportunityType 映射到「执行权限域」，Gate 3 据此决定能否自动执行
"""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol


class DecisionType(str, Enum):
    """公司级决策出口（CEO Brain 的最终动作）。"""
    EXECUTE = "execute"        # 自动执行（仍需 E17.6 Execution Router 落地，SIM 下不触发真实 API）
    APPROVE = "approve"        # 需人工审批（进入 JsonlApprovalQueue）
    REJECT = "reject"          # 无正向收益预期，拒绝
    OBSERVE = "observe"        # 置信度不足，仅观察不执行


class ActionDomain(str, Enum):
    """执行权限域：Gate 3 据此决定自动 vs 人工。"""
    RELEASE = "release"        # 发布类：置信足够可自动
    PAYMENT = "payment"        # 付费/经济类：必须人工
    UA = "ua"                  # 买量
    ASO = "aso"                # 商店优化
    CREATIVE = "creative"      # 素材
    PRODUCT = "product"        # 产品/留存/营收修复


# OpportunityType.value -> ActionDomain（Gate 3 映射表）
_ACTION_DOMAIN: Dict[str, ActionDomain] = {
    "release_health": ActionDomain.RELEASE,
    "monetization": ActionDomain.PAYMENT,
    "ua_scale": ActionDomain.UA,
    "ua_stop_loss": ActionDomain.UA,
    "aso_optimization": ActionDomain.ASO,
    "creative_refresh": ActionDomain.CREATIVE,
    "retention": ActionDomain.PRODUCT,
    "revenue_recovery": ActionDomain.PRODUCT,
}


def action_domain(opportunity_type_value: str) -> ActionDomain:
    return _ACTION_DOMAIN.get(opportunity_type_value, ActionDomain.PRODUCT)


# 人类可读的执行动作标签
_ACTION_LABEL: Dict[str, str] = {
    "revenue_recovery": "恢复收入",
    "ua_scale": "扩大买量预算",
    "ua_stop_loss": "止损买量",
    "creative_refresh": "刷新创意素材",
    "aso_optimization": "优化商店页",
    "monetization": "调整变现策略",
    "retention": "改善留存",
    "release_health": "修复发布健康度",
}


def action_label(opportunity_type_value: str, game_id: str) -> str:
    verb = _ACTION_LABEL.get(opportunity_type_value, "执行动作")
    return f"{verb}（{game_id}）"


@dataclass
class SimulationResult:
    """行动前预测（确定性，无 LLM）。"""
    expected_revenue_change: float = 0.0   # 相对收入变化，如 +0.12 = +12%
    expected_roas_change: float = 0.0      # ROAS 绝对变化
    confidence: float = 0.0
    risk: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SimulationResult":
        return cls(
            expected_revenue_change=float(d.get("expected_revenue_change", 0.0)),
            expected_roas_change=float(d.get("expected_roas_change", 0.0)),
            confidence=float(d.get("confidence", 0.0)),
            risk=float(d.get("risk", 0.0)),
        )


@dataclass
class GrowthDecision:
    """一个机会经三道门后的公司级决策。"""
    game_id: str
    opportunity_id: str
    action: str
    decision_type: DecisionType
    expected_value: float  # 相对收益预期（与 opportunity.expected_impact 对齐）
    confidence: float
    risk: float
    reason: str
    created_at: str = ""
    urgency: float = 0.5  # 辅助字段：问题紧迫度，供 CEO 打分用
    simulation: Optional[SimulationResult] = None
    audit_id: str = ""
    executed: bool = False
    queued: bool = False

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.audit_id:
            self.audit_id = f"dec_{uuid.uuid4().hex[:12]}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "opportunity_id": self.opportunity_id,
            "action": self.action,
            "decision_type": self.decision_type.value,
            "expected_value": self.expected_value,
            "confidence": self.confidence,
            "risk": self.risk,
            "urgency": self.urgency,
            "reason": self.reason,
            "created_at": self.created_at,
            "simulation": self.simulation.to_dict() if self.simulation else None,
            "audit_id": self.audit_id,
            "executed": self.executed,
            "queued": self.queued,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GrowthDecision":
        sim = d.get("simulation")
        return cls(
            game_id=d["game_id"],
            opportunity_id=d["opportunity_id"],
            action=d["action"],
            decision_type=DecisionType(d["decision_type"]),
            expected_value=float(d.get("expected_value", 0.0)),
            confidence=float(d.get("confidence", 0.0)),
            risk=float(d.get("risk", 0.0)),
            urgency=float(d.get("urgency", 0.5)),
            reason=d.get("reason", ""),
            created_at=d.get("created_at", ""),
            simulation=SimulationResult.from_dict(sim) if sim else None,
            audit_id=d.get("audit_id", ""),
            executed=bool(d.get("executed", False)),
            queued=bool(d.get("queued", False)),
        )


@dataclass
class CeoDecisionItem:
    """CEO 优先级清单的一行。"""
    rank: int
    game_id: str
    action: str
    expected_value: float
    confidence: float
    decision_type: DecisionType

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rank": self.rank,
            "game_id": self.game_id,
            "action": self.action,
            "expected_value": self.expected_value,
            "confidence": self.confidence,
            "decision_type": self.decision_type.value,
        }


@dataclass
class DecisionReport:
    """E17.3 主输出：CEO 决策报告。"""
    total_decisions: int
    ceo_priority_list: List[CeoDecisionItem] = field(default_factory=list)
    decisions: List[GrowthDecision] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_decisions": self.total_decisions,
            "ceo_priority_list": [x.to_dict() for x in self.ceo_priority_list],
            "decisions": [d.to_dict() for d in self.decisions],
            "summary": self.summary,
        }

    def to_markdown(self) -> str:
        lines: List[str] = []
        lines.append("# 增长决策报告（Growth Decision Engine · CEO Brain）")
        lines.append("")
        s = self.summary
        lines.append(f"- 决策总数：**{self.total_decisions}**")
        lines.append(
            f"- 出口分布：自动执行 {s.get('execute',0)} / 待审批 "
            f"{s.get('approve',0)} / 仅观察 {s.get('observe',0)} / 拒绝 {s.get('reject',0)}"
        )
        tot = s.get("total_expected_value", 0.0)
        lines.append(f"- 组合预期收益提升：**{tot:+.1%}**")
        lines.append("")
        if self.ceo_priority_list:
            lines.append("## CEO 优先级清单（Top）")
            lines.append("")
            for it in self.ceo_priority_list:
                lines.append(
                    f"{it.rank}. **{it.game_id}** — {it.action}  "
                    f"| 预期 {it.expected_value:+.1%} | 置信 {it.confidence:.0%} "
                    f"| 出口 {it.decision_type.value}"
                )
        return "\n".join(lines)


class DecisionSink(Protocol):
    """E17.6 Execution Router 的占位契约（SIM 下不触发真实 API）。"""

    def submit(self, decision: GrowthDecision) -> bool:
        ...


__all__ = [
    "DecisionType",
    "ActionDomain",
    "action_domain",
    "action_label",
    "SimulationResult",
    "GrowthDecision",
    "CeoDecisionItem",
    "DecisionReport",
    "DecisionSink",
]
