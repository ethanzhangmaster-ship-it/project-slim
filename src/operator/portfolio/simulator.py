"""P3.4.3 — Allocation Simulator（what-if 资源迁移**模拟器**，只模拟不执行）。

定位：回答「如果把预算从低优先游戏迁到高优先游戏，组合的资源分布会变成什么样、
约束过不过」——**不是**「现在就去迁」。

纪律红线（继承 P3.4 + 用户 P3.4.3 边界）：

- ❌ **不预测收入**（无 ``new_revenue = old_revenue * multiplier``）。
- ❌ 不重算 ROAS / spend / revenue；只读 ``snapshot.spend`` 作 baseline。
- ❌ 不修改 E17.3 Decision；不替代 StrategyMutation；不调 Provider / ``SafeExecutor``。
- ❌ 不产生 ``ExecutionRequest`` / ``ExecutionContract``；不绕过 P2.3 Approval；不自动调预算。
- ✅ ``real_api_called`` 恒 ``False``（由 :data:`REAL_API_CALLED` 锁死）。

算法（确定性、纯资源约束模拟）：

1. ``baseline_i = snapshot.spend``（``None`` → 0，``known=False``）
2. 按排名 ``recommended_action`` 给每游戏一个「方向权重」
3. 负向权重游戏释放资金；正向权重游戏按 ``portfolio_score`` 占池比例吸收
4. 缩放正向 delta 使 ``Σdelta == 0``（**预算守恒**）
5. ``proposed_i = baseline_i + delta_i``
6. 跑约束校验 → ``verdict`` / ``risk`` / ``confidence`` / ``explanation``
"""

from __future__ import annotations

from typing import Dict, List, Optional, Union

from .allocation_models import (
    AllocationDelta,
    AllocationSimulationResult,
    ConstraintCheck,
    ConstraintStatus,
    GameAllocation,
    REAL_API_CALLED,
    RiskLevel,
    SimulationVerdict,
)
from .constraints import AllocationConstraints
from .models import PortfolioSnapshot
from .ranking_models import AllocationCandidate, PortfolioVerdict

# 方向权重：recommended_action → 相对当前 spend 的挪动方向幅度。
# 负值 = 释放资金；正值 = 吸收资金；0 = 不动。
# 设计保证 proposed 永不为负（最极端 SUNSET → -1.0*spend → proposed=0）。
_ACTION_SHIFT_WEIGHT = {
    PortfolioVerdict.SCALE: 1.0,
    PortfolioVerdict.MAINTAIN: 0.2,
    PortfolioVerdict.NO_SCALE: 0.0,
    PortfolioVerdict.REDUCE: -0.5,
    PortfolioVerdict.SUNSET: -1.0,
}

_EPS = 1e-6


class AllocationSimulator:
    """what-if 资源迁移模拟器（纯分析，不执行）。"""

    def simulate(
        self,
        snapshot: Union[PortfolioSnapshot, List[PortfolioSnapshot]],
        ranking: List[AllocationCandidate],
        constraints: AllocationConstraints,
    ) -> AllocationSimulationResult:
        """执行一次模拟。

        参数
        ----
        snapshot:  单个 ``PortfolioSnapshot``（多游戏集合）或它们的列表；
                    baseline 取每个游戏的 ``spend``。
        ranking:   ranker 产出的 ``AllocationCandidate`` 列表（提供
                   ``recommended_action`` 与 ``portfolio_score``）。
        constraints: 硬约束（total_budget / max_shift_ratio / min_reserve_ratio）。

        返回
        ----
        ``AllocationSimulationResult``：baseline / proposed / delta / 约束检查 /
        verdict / risk / confidence / explanation；``real_api_called`` 恒 ``False``。
        """
        # 兼容「PortfolioSnapshot[]」写法：合并多个快照的游戏
        if isinstance(snapshot, list):
            merged_games: List = []
            as_of = ""
            for s in snapshot:
                merged_games.extend(s.games)
                if s.generated_at:
                    as_of = s.generated_at
            snapshot = PortfolioSnapshot(generated_at=as_of, games=merged_games)

        as_of = snapshot.generated_at
        games = snapshot.games

        # —— Case4: 空组合 → BLOCKED ——
        if not games:
            return AllocationSimulationResult(
                as_of=as_of,
                verdict=SimulationVerdict.BLOCKED,
                constraints_checked=[
                    ConstraintCheck(
                        "non_empty",
                        ConstraintStatus.BLOCKED,
                        detail="portfolio is empty; simulation cannot run",
                    )
                ],
                explanation="Portfolio is empty; no allocation to simulate.",
                total_budget=constraints.total_budget,
                notes=["empty_portfolio_blocked"],
                real_api_called=REAL_API_CALLED,
            )

        ranking_by_id = {c.game_id: c for c in ranking}

        # —— 1. baseline 取 spend（None→0）——
        baseline: Dict[str, float] = {}
        known_map: Dict[str, bool] = {}
        known_count = 0
        for g in games:
            amt = g.spend if g.spend is not None else 0.0
            baseline[g.game_id] = amt
            known = g.spend is not None
            known_map[g.game_id] = known
            if known:
                known_count += 1

        # —— 2. 方向权重 → 原始 delta ——
        raw_deltas: Dict[str, float] = {}
        freed = 0.0
        pos_raw: Dict[str, float] = {}
        pos_total_raw = 0.0
        for g in games:
            cand = ranking_by_id.get(g.game_id)
            if cand is None:
                weight = 0.0  # 无排名 → 不参与迁移
            else:
                weight = _ACTION_SHIFT_WEIGHT.get(cand.recommended_action, 0.0)
            base = baseline[g.game_id]
            raw = weight * base
            raw_deltas[g.game_id] = raw
            if raw < 0:
                freed += -raw
            elif raw > 0:
                pos_raw[g.game_id] = raw
                pos_total_raw += raw

        # —— 3+4. 资金缩放，保证 Σdelta == 0 ——
        final_deltas: Dict[str, float] = {}
        notes: List[str] = []
        if freed <= _EPS:
            # 没有可释放资金 → 不发生迁移
            final_deltas = {gid: 0.0 for gid in baseline}
            notes.append("no_headroom_no_migration")
        elif pos_total_raw <= _EPS:
            # 没人要更多 → 不发生迁移
            final_deltas = {gid: 0.0 for gid in baseline}
            notes.append("no_demand_no_migration")
        else:
            scale = freed / pos_total_raw
            for gid in baseline:
                r = raw_deltas[gid]
                if r < 0:
                    final_deltas[gid] = r  # 负向保持原值（释放资金）
                elif r > 0:
                    final_deltas[gid] = r * scale  # 正向缩放以恰好吸收 freed
                else:
                    final_deltas[gid] = 0.0

        # —— 5. proposed = baseline + delta ——
        proposed: Dict[str, float] = {}
        delta_objs: List[AllocationDelta] = []
        for gid in baseline:
            b = baseline[gid]
            d = final_deltas[gid]
            p = b + d
            proposed[gid] = p
            delta_objs.append(
                AllocationDelta(
                    game_id=gid,
                    before=b,
                    after=p,
                    delta=d,
                    delta_ratio=0.0,  # 在已知 tb 后回填
                )
            )

        gross_shift = freed  # = Σ正向delta = Σ|delta|/2（守恒下）

        # 有效预算池（未显式给定用 baseline 总和兜底）
        effective_budget = (
            constraints.total_budget
            if constraints.total_budget > 0
            else sum(baseline.values())
        )
        tb = effective_budget if effective_budget > 0 else (sum(baseline.values()) or 1.0)

        # 回填 ratio 字段
        for ga in delta_objs:
            ga.delta_ratio = round(ga.delta / tb, 6) if tb else 0.0

        # —— 6. 约束校验（用有效预算下的约束）——
        eval_constraints = AllocationConstraints(
            total_budget=tb,
            max_shift_ratio=constraints.max_shift_ratio,
            min_reserve_ratio=constraints.min_reserve_ratio,
        )
        checks = eval_constraints.validate(baseline, proposed, delta_objs, gross_shift)

        blocked = any(c.status is ConstraintStatus.BLOCKED for c in checks)
        verdict = SimulationVerdict.BLOCKED if blocked else SimulationVerdict.PASS

        # —— risk（基于挪动比例，非收入预测）——
        gross_ratio = (gross_shift / tb) if tb > 0 else 0.0
        if gross_ratio <= 0.05:
            risk = RiskLevel.LOW
        elif gross_ratio <= constraints.max_shift_ratio:
            risk = RiskLevel.MEDIUM
        else:
            risk = RiskLevel.HIGH

        # —— confidence（模拟可信度：输入完整度，非 E17.3 / P1.7 confidence）——
        known_ratio = (known_count / len(games)) if games else 0.0
        ranked_ids = set(ranking_by_id.keys())
        matched = sum(1 for g in games if g.game_id in ranked_ids)
        ranking_coverage = (matched / len(games)) if games else 0.0
        confidence = round((known_ratio + ranking_coverage) / 2.0, 6)

        # —— 装配出参 ——
        baseline_allocation: List[GameAllocation] = []
        proposed_allocation: List[GameAllocation] = []
        for gid in baseline:
            b = baseline[gid]
            p = proposed[gid]
            baseline_allocation.append(
                GameAllocation(
                    game_id=gid,
                    amount=b,
                    ratio=round(b / tb, 6) if tb else 0.0,
                    known=known_map[gid],
                )
            )
            proposed_allocation.append(
                GameAllocation(
                    game_id=gid,
                    amount=p,
                    ratio=round(p / tb, 6) if tb else 0.0,
                    known=True,
                )
            )

        # —— explanation ——
        if blocked:
            blocked_rules = ", ".join(
                c.rule for c in checks if c.status is ConstraintStatus.BLOCKED
            )
            explanation = (
                f"Simulation BLOCKED by constraint(s): {blocked_rules}. "
                f"No allocation change is recommended."
            )
        else:
            explanation = (
                f"What-if reallocation moves {gross_shift:.2f} of {tb:.2f} "
                f"({gross_ratio * 100:.1f}%) across {len(games)} games; "
                f"all constraints PASS. This is a simulation only — no budget is changed."
            )
            if notes:
                explanation += f" (notes: {', '.join(notes)})"

        reserve = tb - sum(proposed.values())
        if reserve >= eval_constraints.min_reserve_ratio * tb - _EPS:
            notes.append("reserve_maintained")

        return AllocationSimulationResult(
            as_of=as_of,
            baseline_allocation=baseline_allocation,
            proposed_allocation=proposed_allocation,
            delta=delta_objs,
            constraints_checked=checks,
            confidence=confidence,
            explanation=explanation,
            verdict=verdict,
            risk=risk,
            total_budget=tb,
            gross_shift=gross_shift,
            notes=notes,
            real_api_called=REAL_API_CALLED,
        )


def build_allocation_simulator() -> AllocationSimulator:
    """构建模拟器（纯函数，无外部依赖）。"""
    return AllocationSimulator()
