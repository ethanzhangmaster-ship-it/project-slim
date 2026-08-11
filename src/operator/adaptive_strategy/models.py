"""P3.3.3 — Adaptive Strategy 模型层。

把 P3.3 StrategyProposal 真正闭环成「Proposal → Simulation → Approval →
Execution → Outcome → Memory → Strategy Update」的生产级落地器契约。

定位（与 docs/p3_3_3_contract.md 一致）：
- 这是 Strategy Proposal 的「生产级落地器」，不是新的 Decision Engine；
- 全部复用 E17.3 / E17.8 / P2.1 / P2.2 / P2.3 / P2.4 / P3.3，不重写执行链。

纯 dataclass + to_dict / from_dict，无 LLM、无 IO。str-Enum 一律用 .value 归一化。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from src.ceo_intelligence.decision_engine.models import DecisionType
from src.execution.models import ExecutionAction


def _as_str(v: Any) -> str:
    """py3.11 str-Enum 序列化归一化（与全库一致）。"""
    return str(getattr(v, "value", v))


class AdaptiveAction(str, Enum):
    """首批支持的安全动作（Budget Scale 暂缓）。"""

    NETWORK_CLEANUP = "network_cleanup"
    CAMPAIGN_PAUSE = "campaign_pause"
    BUDGET_SCALE = "budget_scale"   # 暂缓，不在首批 TEMPLATES


class Stage(str, Enum):
    """自适应策略执行状态机。

    成功路径：CREATED → SIMULATION_PENDING → SIMULATION_PASS →
             APPROVAL_PENDING → AUTHORIZED → EXECUTING → COMPLETED
    失败路径：SIMULATION_FAIL / APPROVAL_REJECTED / EXECUTION_FAILED /
             RECOVERY_REQUIRED
    """

    CREATED = "created"
    SIMULATION_PENDING = "simulation_pending"
    SIMULATION_PASS = "simulation_pass"
    APPROVAL_PENDING = "approval_pending"
    AUTHORIZED = "authorized"
    EXECUTING = "executing"
    COMPLETED = "completed"
    # 失败态
    SIMULATION_FAIL = "simulation_fail"
    APPROVAL_REJECTED = "approval_rejected"
    EXECUTION_FAILED = "execution_failed"
    RECOVERY_REQUIRED = "recovery_required"


class FinalStatus(str, Enum):
    """终态（确定性出口）。"""

    PENDING = "pending"
    COMPLETED = "completed"
    SIMULATION_FAIL = "simulation_fail"
    APPROVAL_REJECTED = "approval_rejected"
    EXECUTION_FAILED = "execution_failed"
    RECOVERY_REQUIRED = "recovery_required"
    BLOCKED_UNSUPPORTED = "blocked_unsupported"   # 预算扩量等暂缓项 / 未知策略


@dataclass
class AdaptiveStrategyTemplate:
    """一个自适应策略模板（映射 P3.3 StrategyProposal → E17.3 GrowthDecision）。"""

    strategy_id: str
    display_name: str
    adaptive_action: AdaptiveAction
    decision_action: str           # E17.3 GrowthDecision.action（MAX_OPTIMIZE / UA_STOP ...）
    opportunity_type: str          # 用于 opportunity_id 与先验查找（game_id:type）
    decision_type: DecisionType = DecisionType.EXECUTE
    expected_value: float = 0.0
    confidence: float = 0.7
    risk: float = 0.5
    reason: str = ""
    execution_action: ExecutionAction = ExecutionAction.DISABLE_NETWORK
    dimension: str = ""
    provider_params: Dict[str, Any] = field(default_factory=dict)  # 须注入 expected_impact 的键
    supported: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "display_name": self.display_name,
            "adaptive_action": _as_str(self.adaptive_action),
            "decision_action": self.decision_action,
            "opportunity_type": self.opportunity_type,
            "decision_type": _as_str(self.decision_type),
            "expected_value": self.expected_value,
            "confidence": self.confidence,
            "risk": self.risk,
            "reason": self.reason,
            "execution_action": _as_str(self.execution_action),
            "dimension": self.dimension,
            "provider_params": dict(self.provider_params),
            "supported": self.supported,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AdaptiveStrategyTemplate":
        return cls(
            strategy_id=str(d["strategy_id"]),
            display_name=str(d.get("display_name", d["strategy_id"])),
            adaptive_action=AdaptiveAction(str(d.get("adaptive_action", "network_cleanup"))),
            decision_action=str(d.get("decision_action", "")),
            opportunity_type=str(d.get("opportunity_type", "")),
            decision_type=DecisionType(str(d.get("decision_type", "execute"))),
            expected_value=float(d.get("expected_value", 0.0)),
            confidence=float(d.get("confidence", 0.7)),
            risk=float(d.get("risk", 0.5)),
            reason=str(d.get("reason", "")),
            execution_action=ExecutionAction(str(d.get("execution_action", "disable_network"))),
            dimension=str(d.get("dimension", "")),
            provider_params=dict(d.get("provider_params", {})),
            supported=bool(d.get("supported", True)),
        )


@dataclass
class AdaptiveStrategyRequest:
    """一次自适应策略落地的输入（来自 P3.3 StrategyProposal 适配）。"""

    proposal_id: str
    strategy_id: str               # 模板 key，如 "adaptive.network_cleanup"
    target: str                    # game_id
    expected_change: str = ""      # 人类可读变更描述
    parameters: Dict[str, Any] = field(default_factory=dict)
    requires_simulation: bool = True
    source: str = "strategy_loop"
    mode: str = "dry_run"          # dry_run | simulation | production
    approver: str = ""             # 人工审批人（MANUAL 审批必需）
    approver_role: str = ""        # 审批角色（缺省按最小角色推导）

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "strategy_id": self.strategy_id,
            "target": self.target,
            "expected_change": self.expected_change,
            "parameters": dict(self.parameters),
            "requires_simulation": bool(self.requires_simulation),
            "source": self.source,
            "mode": self.mode,
            "approver": self.approver,
            "approver_role": self.approver_role,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AdaptiveStrategyRequest":
        return cls(
            proposal_id=str(d["proposal_id"]),
            strategy_id=str(d["strategy_id"]),
            target=str(d.get("target", "")),
            expected_change=str(d.get("expected_change", "")),
            parameters=dict(d.get("parameters", {})),
            requires_simulation=bool(d.get("requires_simulation", True)),
            source=str(d.get("source", "strategy_loop")),
            mode=str(d.get("mode", "dry_run")),
            approver=str(d.get("approver", "")),
            approver_role=str(d.get("approver_role", "")),
        )


@dataclass
class AdaptiveStrategyResult:
    """一次自适应策略闭环的结果（确定性交付物）。"""

    proposal_id: str = ""
    strategy_id: str = ""
    target: str = ""
    action: str = ""                       # 实际 P2 执行动作
    stage: str = Stage.CREATED.value
    final_status: str = FinalStatus.PENDING.value
    simulation_flag: str = ""             # PreFlightStatus.value
    simulation_detail: str = ""
    approval_status: str = ""             # SubmitResult.outcome
    execution_verdict: str = ""
    execution_result: Optional[Dict[str, Any]] = None
    real_api_called: bool = False
    feedback: Optional[Dict[str, Any]] = None
    errors: List[str] = field(default_factory=list)
    trace: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "strategy_id": self.strategy_id,
            "target": self.target,
            "action": self.action,
            "stage": _as_str(self.stage),
            "final_status": _as_str(self.final_status),
            "simulation_flag": self.simulation_flag,
            "simulation_detail": self.simulation_detail,
            "approval_status": self.approval_status,
            "execution_verdict": self.execution_verdict,
            "execution_result": self.execution_result,
            "real_api_called": bool(self.real_api_called),
            "feedback": self.feedback,
            "errors": list(self.errors),
            "trace": list(self.trace),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AdaptiveStrategyResult":
        return cls(
            proposal_id=str(d.get("proposal_id", "")),
            strategy_id=str(d.get("strategy_id", "")),
            target=str(d.get("target", "")),
            action=str(d.get("action", "")),
            stage=str(d.get("stage", Stage.CREATED.value)),
            final_status=str(d.get("final_status", FinalStatus.PENDING.value)),
            simulation_flag=str(d.get("simulation_flag", "")),
            simulation_detail=str(d.get("simulation_detail", "")),
            approval_status=str(d.get("approval_status", "")),
            execution_verdict=str(d.get("execution_verdict", "")),
            execution_result=d.get("execution_result"),
            real_api_called=bool(d.get("real_api_called", False)),
            feedback=d.get("feedback"),
            errors=list(d.get("errors", [])),
            trace=list(d.get("trace", [])),
        )


__all__ = [
    "AdaptiveAction",
    "Stage",
    "FinalStatus",
    "AdaptiveStrategyTemplate",
    "AdaptiveStrategyRequest",
    "AdaptiveStrategyResult",
]
