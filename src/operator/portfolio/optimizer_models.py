"""P3.4.5 — Portfolio Optimization 结果/输入模型（Orchestrator I/O）。

本文件只承载 ``PortfolioOptimizer`` 的输入与输出数据壳，**不持有任何编排逻辑**。

纪律红线（继承 P3.4 全局 + 用户 P3.4.5 边界）：

- ❌ 不重算 ROAS / spend / revenue / LTV；所有数字来自 ``PortfolioSnapshot`` /
  ``AllocationCandidate`` / ``AllocationSimulationResult``。
- ❌ 不调执行链（``src.execution`` / ``ExecutionContract`` / ``ProviderRouter`` /
  ``SafeExecutor``）；不替代 E17.3 Decision；不产生 ``ExecutionRequest`` / ``Action``。
- ✅ ``real_api_called`` 恒为 ``False``（纯分析编排层）。
- ✅ 三态严格复用 P3.2 ``ActionState``；状态枚举 ``OptimizationStatus`` 仅描述
  *编排结果*（completed / blocked / insufficient_data），不描述执行结果。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from .allocation_models import AllocationSimulationResult, REAL_API_CALLED
from .constraints import AllocationConstraints
from .models import PortfolioSnapshot, _r
from .proposal import PortfolioProposal
from .ranking_models import AllocationCandidate


class OptimizationStatus(str, Enum):
    """优化编排结果状态（**不是**执行/决策状态）。

    - COMPLETED        ：链路跑通，提案可进入人工评审。
    - BLOCKED          ：模拟或提案被闸门/约束阻断。
    - INSUFFICIENT_DATA：输入无可用游戏或排序为空，无法优化。
    """

    COMPLETED = "completed"
    BLOCKED = "blocked"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass
class PortfolioOptimizationInput:
    """P3.4.5 优化器输入。

    字段语义：

    - ``snapshots``        ：组合快照（单份或列表，列表会被合并）。
    - ``rankings``         ：可选预排序候选；非空则编排直接采用，跳过内部重排。
    - ``constraints``      ：``AllocationConstraints``（预算/挪动上限/储备下限）。
    - ``current_allocation``：可选当前预算占用映射（仅作证据/对账，不覆写 baseline）。
    - ``data_age_days``    ：可选观察天数映射（注入 Rule3 闸门）。
    - ``as_of``            ：时间戳（缺省时取快照 ``generated_at``）。
    """

    snapshots: Union[PortfolioSnapshot, List[PortfolioSnapshot], None] = None
    rankings: List[AllocationCandidate] = field(default_factory=list)
    constraints: Optional[AllocationConstraints] = None
    current_allocation: Dict[str, float] = field(default_factory=dict)
    data_age_days: Optional[Dict[str, int]] = None
    as_of: str = ""

    def merged_snapshot(self) -> PortfolioSnapshot:
        """把 ``snapshots``（单份/列表/None）归一为单一 ``PortfolioSnapshot``。

        不修改入参对象——列表分支会构造新 ``PortfolioSnapshot``。
        """
        s = self.snapshots
        if s is None:
            return PortfolioSnapshot(generated_at=self.as_of or "", games=[])
        if isinstance(s, list):
            merged_games = []
            as_of = self.as_of
            for snap in s:
                merged_games.extend(snap.games)
                if snap.generated_at:
                    as_of = snap.generated_at
            return PortfolioSnapshot(generated_at=as_of, games=merged_games)
        # 单份：直接返回（调用方保证不 mutate）
        if not s.generated_at and self.as_of:
            return PortfolioSnapshot(generated_at=self.as_of, games=list(s.games))
        return s

    def to_dict(self) -> Dict[str, Any]:
        snap = self.snapshots
        if isinstance(snap, list):
            snap_d = [x.to_dict() for x in snap]
        elif snap is not None:
            snap_d = snap.to_dict()
        else:
            snap_d = None
        return {
            "snapshots": snap_d,
            "rankings": [c.to_dict() for c in self.rankings],
            "constraints": self.constraints.to_dict() if self.constraints else None,
            "current_allocation": dict(self.current_allocation),
            "data_age_days": dict(self.data_age_days) if self.data_age_days else None,
            "as_of": self.as_of,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PortfolioOptimizationInput":
        snap_d = d.get("snapshots")
        if isinstance(snap_d, list):
            snaps = [PortfolioSnapshot.from_dict(x) for x in snap_d]
        elif isinstance(snap_d, dict):
            snaps = PortfolioSnapshot.from_dict(snap_d)
        else:
            snaps = None
        cons_d = d.get("constraints")
        return cls(
            snapshots=snaps,
            rankings=[AllocationCandidate.from_dict(c) for c in d.get("rankings", [])],
            constraints=AllocationConstraints.from_dict(cons_d) if cons_d else None,
            current_allocation=dict(d.get("current_allocation", {})),
            data_age_days=dict(d["data_age_days"]) if d.get("data_age_days") else None,
            as_of=d.get("as_of", ""),
        )


@dataclass
class PortfolioOptimizationResult:
    """P3.4.5 顶层出参：一次优化编排的完整产物（只建议不执行）。

    ``real_api_called`` 恒 ``False``：编排层不触发任何 Provider / 执行链。
    """

    optimization_id: str = ""
    proposal: Optional[PortfolioProposal] = None
    simulation: Optional[AllocationSimulationResult] = None
    ranked_games: List[AllocationCandidate] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    status: OptimizationStatus = OptimizationStatus.INSUFFICIENT_DATA
    real_api_called: bool = REAL_API_CALLED  # 恒 False

    def to_report_section(self) -> Dict[str, Any]:
        """收敛成 CEO 报告 ``Portfolio Recommendation`` 段（只读、纯搬运）。

        返回可被 ``report/sections.build_portfolio_recommendation_section``
        直接消费的纯 dict。
        """
        prop = self.proposal
        items: List[Dict[str, Any]] = []
        summary = ""
        recommendation = ""
        guard_verdict = ""
        confidence = 0.0
        if prop is not None:
            summary = prop.summary
            recommendation = prop.recommendation
            guard_verdict = prop.guard_verdict.value
            confidence = prop.confidence
            for it in prop.items:
                items.append(
                    {
                        "game_id": it.game_id,
                        "rank": it.rank,
                        "recommended_action": it.recommended_action.value,
                        "budget_delta": _r(it.budget_delta),
                        "action_state": it.action_state.value,
                        "rationale": it.rationale,
                    }
                )
        return {
            "title": "Portfolio Recommendation",
            "status": self.status.value,
            "summary": summary,
            "recommendation": recommendation,
            "guard_verdict": guard_verdict,
            "confidence": _r(confidence),
            "items": items,
            "real_api_called": self.real_api_called,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "optimization_id": self.optimization_id,
            "proposal": self.proposal.to_dict() if self.proposal else None,
            "simulation": self.simulation.to_dict() if self.simulation else None,
            "ranked_games": [c.to_dict() for c in self.ranked_games],
            "evidence": list(self.evidence),
            "status": self.status.value,
            "real_api_called": self.real_api_called,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PortfolioOptimizationResult":
        prop_d = d.get("proposal")
        sim_d = d.get("simulation")
        return cls(
            optimization_id=d.get("optimization_id", ""),
            proposal=PortfolioProposal.from_dict(prop_d) if prop_d else None,
            simulation=AllocationSimulationResult.from_dict(sim_d) if sim_d else None,
            ranked_games=[AllocationCandidate.from_dict(c) for c in d.get("ranked_games", [])],
            evidence=list(d.get("evidence", [])),
            status=OptimizationStatus(d.get("status", "insufficient_data")),
            real_api_called=bool(d.get("real_api_called", REAL_API_CALLED)),
        )
