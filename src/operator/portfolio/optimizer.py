"""P3.4.5 — Portfolio Optimizer（组合层 Orchestrator，不是新的 Decision Engine）。

定位：

```
Snapshot
   ↓  (1) validate
Ranker
   ↓  (2) rank portfolios
Simulator
   ↓  (3) run allocation simulator
ProposalGenerator
   ↓  (4) generate proposal
PortfolioOptimizationResult
   ↓  (5) assemble
```

编排顺序严格为：validate → rank → simulate → propose → assemble。

**不负责**：决策批准 / 执行动作 / 调平台 / 创建 ``ExecutionContract``。

纪律红线（用户 P3.4.5 边界）：

- ❌ 不重算 ROAS / spend / revenue / LTV。所有数字只来自
  ``PortfolioSnapshot`` / ``AllocationCandidate`` / ``AllocationSimulationResult``。
- ❌ 不调执行链（``src.execution`` / ``ExecutionContract`` / ``ProviderRouter`` /
  ``SafeExecutor``）；不替代 E17.3 Decision；不产生 ``ExecutionRequest`` / ``Action``。
- ❌ 不修改入参（snapshot / ranking / simulation 保持只读）。
- ✅ ``real_api_called`` 恒为 ``False``（纯分析编排层）。
- ✅ 当模拟/提案被阻断时，**不覆盖**其结果——``status`` 如实标记为 ``BLOCKED``。
"""

from __future__ import annotations

from typing import Any, List, Optional, Union

from .allocation_models import REAL_API_CALLED
from .constraints import AllocationConstraints
from .models import GamePortfolioSnapshot, PortfolioSnapshot, _r
from .optimizer_models import (
    OptimizationStatus,
    PortfolioOptimizationInput,
    PortfolioOptimizationResult,
)
from .proposal import PortfolioProposal, ProposalGenerator, build_proposal_generator
from .ranker import PortfolioRanker, build_portfolio_ranker
from .ranking_models import AllocationCandidate
from .simulator import AllocationSimulator, build_allocation_simulator


def _slug(s: str) -> str:
    """把 as_of 等字符串压成稳定 id 片段。"""
    if not s:
        return "unknown"
    return "".join(ch if (ch.isalnum() or ch in "-_") else "-" for ch in s)


class PortfolioOptimizer:
    """组合优化编排器（纯编排，无外部依赖、无 IO）。

    构造时可注入 ``ranker`` / ``simulator`` / ``proposer``（默认用各 build_* 工厂），
    便于测试与下游替换，但任何注入对象都不得破坏「不执行」纪律。
    """

    def __init__(
        self,
        ranker: Optional[PortfolioRanker] = None,
        simulator: Optional[AllocationSimulator] = None,
        proposer: Optional[ProposalGenerator] = None,
        advisor: Optional[Any] = None,
    ) -> None:
        self.ranker = ranker or build_portfolio_ranker()
        self.simulator = simulator or build_allocation_simulator()
        self.proposer = proposer or build_proposal_generator()
        # P3.5.1（可选）：经验增强顾问；None → 不接经验（零回归）
        self.advisor = advisor
        # 注意：P3.5.2 决策学习写入**不**在本层发生——Optimizer 是业务计算层，
        # 反馈由 Operator Layer（pipeline / src/operator/feedback.py）消费 Result 后写入。

    # ------------------------------------------------------------------ #
    # 主入口
    # ------------------------------------------------------------------ #
    def optimize(
        self,
        input: PortfolioOptimizationInput,
    ) -> PortfolioOptimizationResult:
        """执行完整编排链路。

        参数
        ----
        input: ``PortfolioOptimizationInput``（含 snapshot / rankings / constraints /
               current_allocation / data_age_days / as_of）。

        返回
        ----
        ``PortfolioOptimizationResult``（recommendation-only，``real_api_called`` 恒 ``False``）。
        """
        # —— (1) validate input ——
        snap = input.merged_snapshot()
        games: List[GamePortfolioSnapshot] = list(snap.games)
        if not games:
            return self._insufficient(input, snap, "no games in snapshot")

        # —— (2) rank portfolios ——
        # 若上游已提供 rankings 则直接采用（单源）；否则用 Ranker 重排 snapshot games。
        # P3.5.1：若注入了 advisor，则先对每个游戏查经验信号，喂给 Ranker 做经验修正。
        knowledge_signals = None
        if self.advisor is not None:
            knowledge_signals = {
                snap.game_id: self.advisor.advise_portfolio(snap) for snap in games
            }
        ranked: List[AllocationCandidate] = (
            list(input.rankings)
            if input.rankings
            else self.ranker.rank(games, knowledge_signals=knowledge_signals)
        )
        if not ranked:
            return self._insufficient(input, snap, "ranking produced no candidates")

        # —— (3) run allocation simulator ——
        sim = self.simulator.simulate(snap, ranked, input.constraints)

        # —— (4) generate proposal ——
        prop = self.proposer.propose(
            sim, ranked, snap, input.constraints, input.data_age_days
        )

        # —— (5) assemble result ——
        status = self._status(sim, prop)
        evidence = self._build_evidence(input, snap, games, ranked, sim, prop, status)
        return PortfolioOptimizationResult(
            optimization_id=f"opt-{_slug(snap.generated_at or input.as_of)}",
            proposal=prop,
            simulation=sim,
            ranked_games=ranked,
            evidence=evidence,
            status=status,
            real_api_called=REAL_API_CALLED,
        )

    # ------------------------------------------------------------------ #
    # 状态 / 证据 / 短路
    # ------------------------------------------------------------------ #
    @staticmethod
    def _status(sim, prop: PortfolioProposal) -> OptimizationStatus:
        """编排状态：模拟或提案被阻断 → BLOCKED；否则 COMPLETED。

        注意：**不覆盖** 下层标记——下层说 BLOCKED，编排就如实 BLOCKED。
        """
        if sim.is_blocked or prop.is_blocked:
            return OptimizationStatus.BLOCKED
        return OptimizationStatus.COMPLETED

    def _insufficient(
        self,
        input: PortfolioOptimizationInput,
        snap: PortfolioSnapshot,
        why: str,
    ) -> PortfolioOptimizationResult:
        return PortfolioOptimizationResult(
            optimization_id=f"opt-{_slug(snap.generated_at or input.as_of)}-insufficient",
            proposal=None,
            simulation=None,
            ranked_games=[],
            evidence=[f"INSUFFICIENT_DATA: {why}."],
            status=OptimizationStatus.INSUFFICIENT_DATA,
            real_api_called=REAL_API_CALLED,
        )

    def _build_evidence(
        self,
        input: PortfolioOptimizationInput,
        snap: PortfolioSnapshot,
        games: List[GamePortfolioSnapshot],
        ranked: List[AllocationCandidate],
        sim,
        prop: PortfolioProposal,
        status: OptimizationStatus,
    ) -> List[str]:
        ev: List[str] = []
        ev.append(
            f"Input: {len(games)} game(s) in snapshot; "
            f"rankings supplied={len(input.rankings)} (re-ranked internally="
            f"{'no' if input.rankings else 'yes'})."
        )
        if input.current_allocation:
            base_sum = sum((g.spend or 0.0) for g in games)
            cur_sum = sum(input.current_allocation.values())
            ev.append(
                f"Current allocation provided for {len(input.current_allocation)} game(s); "
                f"Σsnapshot.spend={base_sum:.2f}, Σcurrent_allocation={cur_sum:.2f} "
                f"(current_allocation used for audit only, not overwrite)."
            )
        ev.append(f"Ranked {len(ranked)} game(s) via PortfolioRanker.")
        ev.append(
            f"Simulation verdict: {sim.verdict.value.upper()} "
            f"(confidence={sim.confidence:.3f})."
        )
        if sim.blocked_rules:
            ev.append(
                f"Simulation blocked by constraint(s): {', '.join(sim.blocked_rules)}."
            )
        ev.append(
            f"Proposal guard: {prop.guard_verdict.value} "
            f"({prop.auto_count} AUTO / {prop.approval_count} APPROVAL / "
            f"{prop.blocked_count} BLOCKED)."
        )
        ev.append(f"Status: {status.value}.")
        ev.append(
            "Discipline: optimizer orchestrates only — no re-computation, "
            "no ExecutionRequest, no Provider call, no Decision override; "
            "real_api_called=False. Awaiting E17.3 Decision Review / human approval."
        )
        return ev


def build_portfolio_optimizer(
    ranker: Optional[PortfolioRanker] = None,
    simulator: Optional[AllocationSimulator] = None,
    proposer: Optional[ProposalGenerator] = None,
    advisor: Optional[Any] = None,
) -> PortfolioOptimizer:
    """构建组合优化编排器（纯函数，无外部依赖）。"""
    return PortfolioOptimizer(
        ranker=ranker, simulator=simulator, proposer=proposer, advisor=advisor
    )
