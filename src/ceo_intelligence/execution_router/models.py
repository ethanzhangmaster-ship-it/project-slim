"""E17.6 Growth Execution Router — 模型层。

把 E17.4 的 GrowthStrategyPlan 变成真实执行系统调用（大脑 → 手脚）。

约定（与 E17.1–E17.4 一致）：
- 纯 dataclass + to_dict / from_dict，无 LLM、无 IO
- 枚举为 str Enum，便于 JSON 序列化与 audit / memory 键
- Execution State Machine：
    CREATED → VALIDATING → WAITING_APPROVAL → EXECUTING → SUCCESS → LEARNING
    失败：EXECUTING → FAILED → ROLLBACK
- SIM 纪律：本层与所有默认 Adapter 均不触发真实 API（real_api_called=False）
"""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class ExecutionDomain(str, Enum):
    """执行域 → 路由表键（与 E17.3 ActionDomain 对齐，扩展 ANALYTICS）。"""
    UA = "ua"                # Meta / TikTok 买量
    ASO = "aso"              # Google Play 商店页
    CREATIVE = "creative"    # E11 Creative Evolution
    ECONOMY = "economy"      # Remote Config 定价 / 商品包（PAYMENT 域）
    RELEASE = "release"      # E15 Play Runtime ReleaseAgent
    ANALYTICS = "analytics"  # 只读分析 / 监控（SAFE）


class ExecutionStatus(str, Enum):
    """执行状态机。"""
    CREATED = "created"
    VALIDATING = "validating"
    WAITING_APPROVAL = "waiting_approval"
    EXECUTING = "executing"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLBACK = "rollback"
    LEARNING = "learning"
    SKIPPED = "skipped"      # 前置依赖失败时跳过


@dataclass
class ExecutionAction:
    """统一执行动作模型（Compiler 产出，Router 消费）。"""
    action_id: str
    game_id: str
    domain: str              # ExecutionDomain.value
    action_type: str         # increase_budget / generate_creatives / halt_release ...
    target: str = ""         # campaign_id / package_name / config key ...
    payload: Dict[str, Any] = field(default_factory=dict)
    risk_level: float = 0.0  # 0.0 - 1.0
    approval_required: bool = False
    decision_id: str = ""
    plan_strategy_type: str = ""
    source_task_order: int = 0
    dependency: List[str] = field(default_factory=list)  # 前置 task order（字符串）
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.action_id:
            self.action_id = f"act_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ExecutionAction":
        return cls(
            action_id=d.get("action_id", ""),
            game_id=d["game_id"],
            domain=d["domain"],
            action_type=d["action_type"],
            target=d.get("target", ""),
            payload=dict(d.get("payload", {})),
            risk_level=float(d.get("risk_level", 0.0)),
            approval_required=bool(d.get("approval_required", False)),
            decision_id=d.get("decision_id", ""),
            plan_strategy_type=d.get("plan_strategy_type", ""),
            source_task_order=int(d.get("source_task_order", 0)),
            dependency=list(d.get("dependency", [])),
            created_at=d.get("created_at", ""),
        )


@dataclass
class AdapterOutcome:
    """Adapter 执行的原始结果（Adapter 层统一返回）。"""
    ok: bool
    detail: str = ""
    real_api_called: bool = False
    error: str = ""
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionResult:
    """一个动作经 Router 后的最终结果（含状态机轨迹）。"""
    action_id: str
    system: str                       # 执行系统名（adapter.name 或 approval_queue）
    status: ExecutionStatus
    detail: str = ""
    real_api_called: bool = False
    rolled_back: bool = False
    error: str = ""
    duration_ms: float = 0.0
    permission_tier: str = ""
    state_history: List[str] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ExecutionResult":
        return cls(
            action_id=d["action_id"],
            system=d.get("system", ""),
            status=ExecutionStatus(d["status"]),
            detail=d.get("detail", ""),
            real_api_called=bool(d.get("real_api_called", False)),
            rolled_back=bool(d.get("rolled_back", False)),
            error=d.get("error", ""),
            duration_ms=float(d.get("duration_ms", 0.0)),
            permission_tier=d.get("permission_tier", ""),
            state_history=list(d.get("state_history", [])),
            data=dict(d.get("data", {})),
        )


@dataclass
class ExecutionReport:
    """execute_plan 主输出：{execution_id, status, actions:[{system, result}]}。"""
    execution_id: str
    game_id: str
    decision_id: str = ""
    strategy_type: str = ""
    status: str = ""                  # success / partial / waiting_approval / failed
    actions: List[Dict[str, Any]] = field(default_factory=list)  # {action, result}
    summary: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.execution_id:
            self.execution_id = f"exec_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "game_id": self.game_id,
            "decision_id": self.decision_id,
            "strategy_type": self.strategy_type,
            "status": self.status,
            "actions": self.actions,
            "summary": self.summary,
            "created_at": self.created_at,
        }

    def results(self) -> List[ExecutionResult]:
        return [ExecutionResult.from_dict(a["result"]) for a in self.actions]

    def to_markdown(self) -> str:
        lines = [f"# 执行报告：{self.game_id} — {self.strategy_type}", ""]
        lines.append(f"- 执行 ID：`{self.execution_id}` ｜ 状态：**{self.status}**")
        s = self.summary
        lines.append(
            f"- 成功 {s.get('success', 0)} / 待审批 {s.get('waiting_approval', 0)} "
            f"/ 失败 {s.get('failed', 0)} / 跳过 {s.get('skipped', 0)}"
        )
        lines.append(f"- 真实 API 调用：{'是' if s.get('real_api_called') else '否（SIM）'}")
        lines.append("")
        lines.append("## 动作明细")
        for item in self.actions:
            a, r = item["action"], item["result"]
            lines.append(
                f"- [{r['status']}] {a['domain']}:{a['action_type']} → {r['system']}"
                f"（{r.get('detail', '')}）"
            )
        return "\n".join(lines)


@dataclass
class ExecutionExperience:
    """Decision → Strategy → Execution → Result 闭环记录（供 E17.7 Memory Graph 沉淀）。"""
    execution_id: str
    action_id: str
    decision_id: str
    game_id: str
    strategy_type: str
    domain: str
    action_type: str
    status: str                 # ExecutionStatus.value
    success: bool
    real_api_called: bool = False
    rolled_back: bool = False
    detail: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ExecutionExperience":
        return cls(
            execution_id=d.get("execution_id", ""),
            action_id=d.get("action_id", ""),
            decision_id=d.get("decision_id", ""),
            game_id=d.get("game_id", ""),
            strategy_type=d.get("strategy_type", ""),
            domain=d.get("domain", ""),
            action_type=d.get("action_type", ""),
            status=d.get("status", ""),
            success=bool(d.get("success", False)),
            real_api_called=bool(d.get("real_api_called", False)),
            rolled_back=bool(d.get("rolled_back", False)),
            detail=d.get("detail", ""),
            created_at=d.get("created_at", ""),
        )


__all__ = [
    "ExecutionDomain",
    "ExecutionStatus",
    "ExecutionAction",
    "AdapterOutcome",
    "ExecutionResult",
    "ExecutionReport",
    "ExecutionExperience",
]
