"""P2.1 Execution Contract Layer — 执行域模型（不触发任何真实 API）。

这一层是 AI CEO 的「手部接口」：把 E17.3 GrowthDecision 的「决策语言」
转成 P2 Execution Layer 可理解的「动作合同（Execution Contract）」。

设计纪律（与 E17.x 一致）：
- 纯 dataclass + to_dict / from_dict，无 LLM、无 IO、无网络
- 枚举为 str Enum，便于 JSON 序列化与 audit / memory 键
- 本层只定义「做什么 / 对谁 / 多重要 / 谁来批准」，绝不调用任何外部系统
- 真实执行推迟到 P2.2 Execution Provider Layer（MAX / Meta / Play 适配器）
"""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


class ExecutionDomain(str, Enum):
    """执行权限域（比 E17.3 ActionDomain 更贴近「系统动作」视角）。"""

    UA = "ua"                          # 买量 / UA 投放
    AD_MONETIZATION = "ad_monetization"  # 广告变现优化（MAX 聚合）
    ASO = "aso"                        # 商店页 / ASO
    REVENUE = "revenue"                # 收入修复 / 收入调查
    RELEASE = "release"                # 发布 / 版本
    ECONOMY = "economy"                # 内购 / 经济系统


class ExecutionAction(str, Enum):
    """P2 可执行的具体动作（P2.2 Provider 据此路由到对应适配器）。"""

    PAUSE_CAMPAIGN = "pause_campaign"          # 暂停广告系列（UA）
    SCALE_BUDGET = "scale_budget"              # 调整买量预算（UA）
    DISABLE_NETWORK = "disable_network"        # 关停某广告网络（MAX）
    UPDATE_WATERFALL = "update_waterfall"      # 更新广告瀑布流（MAX）
    CREATE_ASO_UPDATE = "create_aso_update"    # 生成商店页优化任务（ASO）
    CREATE_INVESTIGATION = "create_investigation"  # 生成收入调查任务（REVENUE）
    CREATE_RELEASE = "create_release"          # 生成发布/版本任务（RELEASE）


class ExecutionMode(str, Enum):
    """执行请求的运行模式。

    - SIMULATION：仅模拟，不落任何写动作（与 E17 全局 SIM 纪律一致）
    - DRY_RUN：生成完整请求但不调用真实 API（默认，供人工复核）
    - PRODUCTION：真实写动作（需人工审批通过后由 P2.2 执行）
    """

    SIMULATION = "simulation"
    DRY_RUN = "dry_run"
    PRODUCTION = "production"


# 人类可读标签
_ACTION_LABEL: Dict[ExecutionAction, str] = {
    ExecutionAction.PAUSE_CAMPAIGN: "暂停广告系列",
    ExecutionAction.SCALE_BUDGET: "调整买量预算",
    ExecutionAction.DISABLE_NETWORK: "关停广告网络",
    ExecutionAction.UPDATE_WATERFALL: "更新广告瀑布流",
    ExecutionAction.CREATE_ASO_UPDATE: "生成商店页优化任务",
    ExecutionAction.CREATE_INVESTIGATION: "生成收入调查任务",
    ExecutionAction.CREATE_RELEASE: "生成发布任务",
}

_DOMAIN_LABEL: Dict[ExecutionDomain, str] = {
    ExecutionDomain.UA: "买量",
    ExecutionDomain.AD_MONETIZATION: "广告变现",
    ExecutionDomain.ASO: "商店优化",
    ExecutionDomain.REVENUE: "收入",
    ExecutionDomain.RELEASE: "发布",
    ExecutionDomain.ECONOMY: "经济系统",
}


def action_label(action: ExecutionAction) -> str:
    return _ACTION_LABEL.get(action, action.value)


def domain_label(domain: ExecutionDomain) -> str:
    return _DOMAIN_LABEL.get(domain, domain.value)


@dataclass
class ExecutionIntent:
    """决策 → 执行意图。

    一个不可变的「手部动作指令」：明确对谁（target_id）、做什么动作（action）、
    属于哪个域（domain）、多重要（confidence / expected_impact）、有多危险（risk_level）、
    是否需要人工审批（requires_approval）。
    """

    intent_id: str
    decision_id: str
    domain: ExecutionDomain
    action: ExecutionAction
    target_id: str
    reason: str
    confidence: float
    expected_impact: Optional[Dict[str, Any]] = None
    risk_level: float = 0.5
    requires_approval: bool = False
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.intent_id:
            self.intent_id = f"int_{uuid.uuid4().hex[:12]}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "decision_id": self.decision_id,
            "domain": self.domain.value,
            "action": self.action.value,
            "target_id": self.target_id,
            "reason": self.reason,
            "confidence": self.confidence,
            "expected_impact": self.expected_impact,
            "risk_level": self.risk_level,
            "requires_approval": self.requires_approval,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ExecutionIntent":
        return cls(
            intent_id=d.get("intent_id", ""),
            decision_id=d.get("decision_id", ""),
            domain=ExecutionDomain(d["domain"]),
            action=ExecutionAction(d["action"]),
            target_id=d.get("target_id", ""),
            reason=d.get("reason", ""),
            confidence=float(d.get("confidence", 0.0)),
            expected_impact=d.get("expected_impact"),
            risk_level=float(d.get("risk_level", 0.5)),
            requires_approval=bool(d.get("requires_approval", False)),
            created_at=d.get("created_at", ""),
        )


@dataclass
class ExecutionRequest:
    """把意图打包成一次可执行请求。

    mode 默认 DRY_RUN：本层永远不触发真实 API；只有 P2.2 在人工审批通过、
    mode=PRODUCTION 时才会调用外部系统。
    """

    intent: ExecutionIntent
    request_id: str = ""
    mode: ExecutionMode = ExecutionMode.DRY_RUN
    created_at: str = ""
    # P2.3.7: ExecutionAuthorization（审批授权令牌）。PRODUCTION 模式下
    # AuthorizationGate 会校验此字段（Rule 1~4）；SIM/DRY_RUN 忽略。
    # 类型用 Any 避免 approval 包的循环依赖。
    authorization: Optional[Any] = None

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.request_id:
            self.request_id = f"req_{uuid.uuid4().hex[:12]}"

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "request_id": self.request_id,
            "mode": self.mode.value,
            "intent": self.intent.to_dict(),
            "created_at": self.created_at,
        }
        if self.authorization is not None and hasattr(self.authorization, "to_dict"):
            payload["authorization"] = self.authorization.to_dict()
        return payload

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ExecutionRequest":
        intent = d.get("intent") or {}
        if isinstance(intent, dict):
            intent = ExecutionIntent.from_dict(intent)
        authorization = d.get("authorization")
        if isinstance(authorization, dict):
            # 延迟导入避免循环依赖（approval 包依赖本模块）
            from src.execution.approval.models import ExecutionAuthorization

            authorization = ExecutionAuthorization.from_dict(authorization)
        return cls(
            request_id=d.get("request_id", ""),
            intent=intent,
            mode=ExecutionMode(d.get("mode", ExecutionMode.DRY_RUN.value)),
            created_at=d.get("created_at", ""),
            authorization=authorization,
        )


__all__ = [
    "ExecutionDomain",
    "ExecutionAction",
    "ExecutionMode",
    "action_label",
    "domain_label",
    "ExecutionIntent",
    "ExecutionRequest",
]
