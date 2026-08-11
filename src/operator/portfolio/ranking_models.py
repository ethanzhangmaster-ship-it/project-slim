"""P3.4.2+ — Portfolio 输出模型（评分 / 排序 / 分配 / 推荐）。

**归属说明（P3.4.1 边界）**：

本模块承载的 ``PortfolioVerdict`` / ``PortfolioScore`` / ``AllocationCandidate``
/ ``PortfolioRecommendation`` 属于 **P3.4.2 及之后**的层级，**不属于 P3.4.1 Model Layer**。

P3.4.1 ``models.py`` 是纯快照模型层（只装配、不创造）：不评分、不排序、不产生 Action。
把「会算分的 ``PortfolioScore.compute()``」与「Action 语义的 ``PortfolioRecommendation``」
留在 ``models.py`` 会污染该边界，故独立到本文件，由下游各阶段拥有：

- ``PortfolioScore``          → P3.4.2 ranker.py（评分）
- ``PortfolioVerdict``        → P3.4.2 ranker.py（组合层动作初判）
- ``AllocationCandidate``     → P3.4.2 排序出参 / P3.4.3 allocator 填 delta / P3.4.4 guard 填三态
- ``PortfolioRecommendation`` → P3.4.4 出参，P3.4.5 挂 CEO 报告

纪律不变：全部字段**只读消费** ``GamePortfolioSnapshot`` 既有值，
**绝不**重算 ROAS / spend / revenue / retention，**绝不**触碰 E17.3 Decision 或任何 Provider。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .models import GamePortfolioSnapshot, _r


class PortfolioVerdict(str, Enum):
    """组合层动作（非执行动作），由 ranker 初判 + guard 修正。"""
    SCALE = "scale"             # 扩量（申请增量预算）
    MAINTAIN = "maintain"       # 维持现状
    REDUCE = "reduce"           # 收缩
    SUNSET = "sunset"           # 止损
    NO_SCALE = "no_scale"       # 观察期不扩量（新游戏 <7d）


@dataclass
class PortfolioScore:
    """单游戏组合评分（由 ranker 从 GamePortfolioSnapshot 计算，只读）。"""

    game_id: str
    revenue_quality: float      # clamp(roas / 1.5, 0, 1)
    growth_potential: float     # lifecycle_factor（简化为仅生命周期因子）
    confidence: float            # = snapshot.confidence（None→0）
    execution_health: float     # = snapshot.execution_health（None→0）
    score: float                 # = product of above (0-1)
    strategy_score: float = 0.0  # 支持证据，不进乘积

    @classmethod
    def compute(cls, snapshot: GamePortfolioSnapshot) -> "PortfolioScore":
        """从 snapshot 计算评分。全部字段只读消费 snapshot 既有值，不重算 ROAS。"""
        roas_val = snapshot.roas if snapshot.roas is not None else 0.0
        conf_val = snapshot.confidence if snapshot.confidence is not None else 0.0
        exec_val = snapshot.execution_health if snapshot.execution_health is not None else 0.0
        strat_val = snapshot.strategy_score if snapshot.strategy_score is not None else 0.0

        revenue_quality = max(0.0, min(1.0, roas_val / 1.5))
        lifecycle_factor = _lifecycle_weight(snapshot.lifecycle_stage)
        growth_potential = lifecycle_factor
        score = revenue_quality * growth_potential * conf_val * exec_val

        return cls(
            game_id=snapshot.game_id,
            revenue_quality=revenue_quality,
            growth_potential=growth_potential,
            confidence=conf_val,
            execution_health=exec_val,
            score=score,
            strategy_score=strat_val,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "revenue_quality": _r(self.revenue_quality),
            "growth_potential": _r(self.growth_potential),
            "confidence": _r(self.confidence),
            "execution_health": _r(self.execution_health),
            "score": _r(self.score),
            "strategy_score": _r(self.strategy_score),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PortfolioScore":
        return cls(
            game_id=d["game_id"],
            revenue_quality=float(d.get("revenue_quality", 0.0)),
            growth_potential=float(d.get("growth_potential", 0.0)),
            confidence=float(d.get("confidence", 0.0)),
            execution_health=float(d.get("execution_health", 0.0)),
            score=float(d.get("score", 0.0)),
            strategy_score=float(d.get("strategy_score", 0.0)),
        )


@dataclass
class AllocationCandidate:
    """排序 + 分配结果（含 ranker 初判、allocator delta、guard action_state）。"""

    game_id: str
    rank: int                           # 1-based
    portfolio_score: float              # PortfolioScore.score
    recommended_action: PortfolioVerdict  # ranker 初判 → guard 可修正
    recommended_budget_delta: float     # allocator 模拟增量（第一阶段不执行）
    priority: float                     # round(portfolio_score * 100, 2)，展示用
    confidence: float                   # = snapshot.confidence
    action_state: str                   # ActionState.AUTO/APPROVAL/BLOCKED（guard 填）
    reason: str                         # WHY 证据
    strategy_score: float = 0.0        # 支持证据
    # P3.5.1：经验增强（可选，默认空；不进入乘积，仅证据/排序修正）
    knowledge_signal: Optional[Dict[str, Any]] = None   # KnowledgeSignal.to_dict()
    knowledge_adjustment: float = 0.0                  # augmented - base（排序修正量）

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "rank": self.rank,
            "portfolio_score": _r(self.portfolio_score),
            "recommended_action": self.recommended_action.value,
            "recommended_budget_delta": _r(self.recommended_budget_delta),
            "priority": _r(self.priority),
            "confidence": _r(self.confidence),
            "action_state": self.action_state,
            "reason": self.reason,
            "strategy_score": _r(self.strategy_score),
            "knowledge_signal": self.knowledge_signal,
            "knowledge_adjustment": _r(self.knowledge_adjustment),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AllocationCandidate":
        return cls(
            game_id=d["game_id"],
            rank=int(d.get("rank", 0)),
            portfolio_score=float(d.get("portfolio_score", 0.0)),
            recommended_action=PortfolioVerdict(d.get("recommended_action", "maintain")),
            recommended_budget_delta=float(d.get("recommended_budget_delta", 0.0)),
            priority=float(d.get("priority", 0.0)),
            confidence=float(d.get("confidence", 0.0)),
            action_state=d.get("action_state", "AUTO"),
            reason=d.get("reason", ""),
            strategy_score=float(d.get("strategy_score", 0.0)),
            knowledge_signal=d.get("knowledge_signal"),
            knowledge_adjustment=float(d.get("knowledge_adjustment", 0.0)),
        )


@dataclass
class PortfolioRecommendation:
    """PortfolioOptimizer 顶层出参。

    candidates 为完整候选列表（已过 guard）；
    total_recommended 为正向 delta 总额。
    """

    as_of: str
    candidates: List[AllocationCandidate] = field(default_factory=list)
    total_recommended: float = 0.0
    auto_count: int = 0
    approval_count: int = 0
    blocked_count: int = 0
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "as_of": self.as_of,
            "candidates": [c.to_dict() for c in self.candidates],
            "total_recommended": _r(self.total_recommended),
            "auto_count": self.auto_count,
            "approval_count": self.approval_count,
            "blocked_count": self.blocked_count,
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PortfolioRecommendation":
        return cls(
            as_of=d["as_of"],
            candidates=[AllocationCandidate.from_dict(c) for c in d.get("candidates", [])],
            total_recommended=float(d.get("total_recommended", 0.0)),
            auto_count=int(d.get("auto_count", 0)),
            approval_count=int(d.get("approval_count", 0)),
            blocked_count=int(d.get("blocked_count", 0)),
            notes=list(d.get("notes", [])),
        )


# --------------------------------------------------------------------------- #
# 评分工具（生命周期权重表）
# --------------------------------------------------------------------------- #

LIFECYCLE_WEIGHTS: Dict[str, float] = {
    "scale": 1.0,
    "ua_test": 0.85,
    "soft_launch": 0.70,
    "prototype": 0.45,
    "idea": 0.25,
    "kill": 0.0,
}


def _lifecycle_weight(stage: Optional[str]) -> float:
    """生命周期阶段 → 0-1 权重（确定性，无不识别则 0.0）。"""
    if stage is None:
        return 0.0
    return LIFECYCLE_WEIGHTS.get(stage.lower(), 0.0)
