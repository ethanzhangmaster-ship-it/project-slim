"""P3.4.3 — Allocation Simulation 结果模型。

定位（一句话）：回答「**如果**把资源从 A 游戏迁到 B 游戏，理论组合结果如何」，
而**不是**「现在就把预算迁过去」。

纪律红线（继承 P3.4 契约）：

- ❌ **不预测收入**。本层没有 ``new_revenue = old_revenue * multiplier`` 这类式子——
  一旦出现就悄悄变成预测模型了。只做**资源约束模拟**（钱怎么挪、约束过不过）。
- ❌ 不计算 ROAS（Reality 层职责）；不修改 E17.3 Decision；不替代 StrategyMutation。
- ❌ 不直连 Meta / MAX / Play；不产生 ``ExecutionRequest`` / ``ExecutionContract``；
  不绕过 P2.3 Approval；不自动调预算。
- ✅ ``real_api_called`` 恒为 ``False``（纯分析层，由 :data:`REAL_API_CALLED` 锁死）。

本模块只放**数据结构与序列化**；约束定义见 :mod:`.constraints`，
模拟算法见 :mod:`.simulator`。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .models import _r

# 纯分析层常量：P3.4.3 永不触发真实 API。任何分支都不得改写此值。
REAL_API_CALLED = False


class ConstraintStatus(str, Enum):
    """单条约束的检查结果。"""
    PASS = "pass"           # 通过
    BLOCKED = "blocked"     # 硬阻断（模拟结果不可采纳）
    WARN = "warn"           # 提示（不阻断，仅记录证据）


class SimulationVerdict(str, Enum):
    """模拟整体判定（**不是**执行动作，也不是 E17.3 Decision）。"""
    PASS = "pass"           # 所有约束通过，方案在理论上可提交人工评审
    BLOCKED = "blocked"     # 存在硬阻断约束，方案不成立


class RiskLevel(str, Enum):
    """资源迁移幅度对应的风险等级（**基于挪动比例，非收入预测**）。"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class GameAllocation:
    """单游戏的一笔资源占用（baseline 或 proposed 之一）。"""

    game_id: str
    amount: float            # 绝对额度（与 constraints.total_budget 同币种单位）
    ratio: float = 0.0       # amount / total_budget（0-1，展示用）
    known: bool = True       # baseline 是否来自已知 spend（False = 缺数据按 0 计）

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "amount": _r(self.amount),
            "ratio": _r(self.ratio),
            "known": self.known,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GameAllocation":
        return cls(
            game_id=d["game_id"],
            amount=float(d.get("amount", 0.0)),
            ratio=float(d.get("ratio", 0.0)),
            known=bool(d.get("known", True)),
        )


@dataclass
class AllocationDelta:
    """单游戏的资源变动（proposed - baseline）。"""

    game_id: str
    before: float
    after: float
    delta: float
    delta_ratio: float = 0.0   # delta / total_budget（带符号，占总预算比例）

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "before": _r(self.before),
            "after": _r(self.after),
            "delta": _r(self.delta),
            "delta_ratio": _r(self.delta_ratio),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AllocationDelta":
        return cls(
            game_id=d["game_id"],
            before=float(d.get("before", 0.0)),
            after=float(d.get("after", 0.0)),
            delta=float(d.get("delta", 0.0)),
            delta_ratio=float(d.get("delta_ratio", 0.0)),
        )


@dataclass
class ConstraintCheck:
    """单条约束的检查记录（含证据值，便于 WHY 复盘）。"""

    rule: str                              # 规则名，如 "max_shift_ratio"
    status: ConstraintStatus
    detail: str = ""                       # 人类可读证据
    observed: Optional[float] = None       # 实测值
    limit: Optional[float] = None          # 阈值

    @property
    def ok(self) -> bool:
        """是否未构成硬阻断（WARN 视为通过）。"""
        return self.status is not ConstraintStatus.BLOCKED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule": self.rule,
            "status": self.status.value,
            "detail": self.detail,
            "observed": _r(self.observed),
            "limit": _r(self.limit),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ConstraintCheck":
        return cls(
            rule=d["rule"],
            status=ConstraintStatus(d.get("status", "pass")),
            detail=d.get("detail", ""),
            observed=d.get("observed"),
            limit=d.get("limit"),
        )


@dataclass
class AllocationSimulationResult:
    """P3.4.3 顶层出参：一次 what-if 资源迁移模拟的完整结果。

    ``confidence`` 的语义边界（**重要，勿混淆**）：

    - 这里是 **模拟可信度**（simulation confidence）——衡量「本次模拟的输入数据有多完整」，
      由 baseline 已知比例与排名证据覆盖率决定，是确定性函数。
    - **不是** E17.3 Decision confidence（决策置信）。
    - **不是** P1.7 Reality confidence（现实数据置信，那个在
      ``GamePortfolioSnapshot.confidence``）。

    ``real_api_called`` 恒 ``False``：本层纯分析，绝不触发任何 Provider 调用。
    """

    as_of: str = ""
    baseline_allocation: List[GameAllocation] = field(default_factory=list)
    proposed_allocation: List[GameAllocation] = field(default_factory=list)
    delta: List[AllocationDelta] = field(default_factory=list)
    constraints_checked: List[ConstraintCheck] = field(default_factory=list)
    confidence: float = 0.0                      # 模拟可信度（见类 docstring）
    explanation: str = ""
    verdict: SimulationVerdict = SimulationVerdict.BLOCKED
    risk: RiskLevel = RiskLevel.LOW
    total_budget: float = 0.0
    gross_shift: float = 0.0                     # Σ|delta| / 2，实际挪动总量
    notes: List[str] = field(default_factory=list)
    real_api_called: bool = REAL_API_CALLED      # 恒 False

    # -- 只读派生（不产生新指标）--
    @property
    def is_blocked(self) -> bool:
        return self.verdict is SimulationVerdict.BLOCKED

    @property
    def blocked_rules(self) -> List[str]:
        return [
            c.rule for c in self.constraints_checked
            if c.status is ConstraintStatus.BLOCKED
        ]

    @property
    def baseline_total(self) -> float:
        return sum(a.amount for a in self.baseline_allocation)

    @property
    def proposed_total(self) -> float:
        return sum(a.amount for a in self.proposed_allocation)

    def delta_of(self, game_id: str) -> Optional[AllocationDelta]:
        for d in self.delta:
            if d.game_id == game_id:
                return d
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "as_of": self.as_of,
            "baseline_allocation": [a.to_dict() for a in self.baseline_allocation],
            "proposed_allocation": [a.to_dict() for a in self.proposed_allocation],
            "delta": [d.to_dict() for d in self.delta],
            "constraints_checked": [c.to_dict() for c in self.constraints_checked],
            "confidence": _r(self.confidence),
            "explanation": self.explanation,
            "verdict": self.verdict.value,
            "risk": self.risk.value,
            "total_budget": _r(self.total_budget),
            "gross_shift": _r(self.gross_shift),
            "notes": list(self.notes),
            "real_api_called": self.real_api_called,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AllocationSimulationResult":
        return cls(
            as_of=d.get("as_of", ""),
            baseline_allocation=[
                GameAllocation.from_dict(a) for a in d.get("baseline_allocation", [])
            ],
            proposed_allocation=[
                GameAllocation.from_dict(a) for a in d.get("proposed_allocation", [])
            ],
            delta=[AllocationDelta.from_dict(x) for x in d.get("delta", [])],
            constraints_checked=[
                ConstraintCheck.from_dict(c) for c in d.get("constraints_checked", [])
            ],
            confidence=float(d.get("confidence", 0.0)),
            explanation=d.get("explanation", ""),
            verdict=SimulationVerdict(d.get("verdict", "blocked")),
            risk=RiskLevel(d.get("risk", "low")),
            total_budget=float(d.get("total_budget", 0.0)),
            gross_shift=float(d.get("gross_shift", 0.0)),
            notes=list(d.get("notes", [])),
            real_api_called=bool(d.get("real_api_called", REAL_API_CALLED)),
        )
