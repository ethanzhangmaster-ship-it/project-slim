"""P3.4.1 — Portfolio Assembler（装配层）。

职责（**仅此**）：

    多源读取  →  字段映射  →  PortfolioSnapshot

**不做**：

- 不计算新业务指标（ROAS/spend/revenue/retention 一律原样消费）
- 不排序（排序属 P3.4.2 ranker.py）
- 不评分 / 不推荐（评分属 P3.4.2，分配模拟属 P3.4.3，Guard 属 P3.4.4）
- 不触碰 E17.3 Decision，不调任何 Provider

设计要点：

- ``reality`` 直接消费真实 ``GrowthRealitySnapshot``（E17.1）。
- ``strategy`` 可传真实 ``GrowthMemoryGraph``（E17.7）或 ``StrategySource`` 解耦源。
- ``execution`` / ``recovery`` / ``lifecycle`` 接收预计算好的 ``*Source`` 解耦源，
  assembler 不负责从原始 outcomes/incidents 反推——那属于 P3.4.2 的接线工作。
  模块级 ``build_*_source`` 适配器提供「从真实上游填充 *Source」的范例实现。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from src.growth_reality.models import GrowthRealitySnapshot

from .models import (
    ExecutionSource,
    GamePortfolioSnapshot,
    LifecycleSource,
    PortfolioSnapshot,
    RecoverySource,
    StrategySource,
)


class PortfolioAssembler:
    """把多源数据装配成 PortfolioSnapshot。

    单游戏：``assemble(reality, ...)`` → 含 1 个游戏的 PortfolioSnapshot。
    多游戏：``assemble_fleet(realities, sources, ...)`` → 聚合 total/coverage。
    """

    def assemble(
        self,
        reality: GrowthRealitySnapshot,
        strategy: Optional[Union["_GraphLike", StrategySource]] = None,
        execution: Optional[ExecutionSource] = None,
        recovery: Optional[RecoverySource] = None,
        lifecycle: Optional[LifecycleSource] = None,
    ) -> PortfolioSnapshot:
        game_id = reality.game_id

        # —— Reality（原样消费）——
        revenue = reality.revenue.daily_revenue if reality.revenue else None
        spend = reality.acquisition.spend if reality.acquisition else None
        # 注意：roas 直接取既有值；**绝不**用 revenue/spend 反推
        roas = reality.acquisition.roas if reality.acquisition else None
        confidence = reality.confidence if reality.confidence else None
        covered = reality.domain_coverage()
        coverage = (covered / 5.0) if covered else None

        # —— Strategy ——
        s_score: Optional[float]
        s_rate: Optional[float]
        active: int
        if strategy is None:
            s_score = s_rate = None
            active = 0
        elif isinstance(strategy, StrategySource):
            s_score = strategy.strategy_score
            s_rate = strategy.strategy_success_rate
            active = strategy.active_strategy_count
        else:  # GrowthMemoryGraph（真实上游）
            s_rate = strategy.success_rate_by(game_id=game_id)  # 0.0 if 无样本
            s_score = s_rate
            active = _count_strategy_types(strategy, game_id)

        # —— Execution / Recovery / Lifecycle ——（解耦源，原样取用）
        e_health = execution.execution_health if execution else None
        f_rate = execution.failure_rate if execution else None
        recovery_rate = recovery.recovery_rate if recovery else None
        stage = lifecycle.lifecycle_stage if lifecycle else None
        fresh = lifecycle.data_freshness if lifecycle else None

        snap = GamePortfolioSnapshot(
            game_id=game_id,
            revenue=revenue,
            spend=spend,
            roas=roas,
            confidence=confidence,
            coverage=coverage,
            strategy_score=s_score,
            strategy_success_rate=s_rate,
            active_strategy_count=active,
            execution_health=e_health,
            failure_rate=f_rate,
            recovery_rate=recovery_rate,
            lifecycle_stage=stage,
            data_freshness=fresh,
            metadata={
                "real_domains": list(reality.real_domains),
                "sources": list(reality.sources),
            },
        )
        return PortfolioSnapshot(
            generated_at=reality.timestamp,
            games=[snap],
            total_revenue=revenue or 0.0,
            total_spend=spend or 0.0,
            coverage=coverage or 0.0,
        )

    def assemble_fleet(
        self,
        realities: List[GrowthRealitySnapshot],
        sources: Optional[Dict[str, Dict[str, Any]]] = None,
        generated_at: Optional[str] = None,
    ) -> PortfolioSnapshot:
        """批量装配并聚合组合级指标（仅求和/均值，非新指标）。"""
        sources = sources or {}
        games: List[GamePortfolioSnapshot] = []
        for r in realities:
            kw = sources.get(r.game_id, {})
            # 逐游戏 assemble，保持输入顺序（禁止排序）
            single = self.assemble(r, **kw)
            games.append(single.games[0])

        total_revenue = sum(g.revenue or 0.0 for g in games)
        total_spend = sum(g.spend or 0.0 for g in games)
        covs = [g.coverage for g in games if g.coverage is not None]
        avg_cov = (sum(covs) / len(covs)) if covs else 0.0
        return PortfolioSnapshot(
            generated_at=generated_at or (realities[0].timestamp if realities else ""),
            games=games,
            total_revenue=total_revenue,
            total_spend=total_spend,
            coverage=avg_cov,
        )


# 真实上游接入的适配器（范例；P3.4.2 可直接调用，assembler 本身不依赖它们）
_GRAPH_FLAG = object()


def _as_graph(obj: Any) -> Any:
    """若为 GrowthMemoryGraph 则原样返回，否则返回哨兵表示非图。"""
    try:
        from src.ceo_intelligence.growth_memory_graph.store import GrowthMemoryGraph
    except Exception:  # pragma: no cover - 防御性
        return _GRAPH_FLAG
    return obj if isinstance(obj, GrowthMemoryGraph) else _GRAPH_FLAG


# 为类型注解引入「图类」占位（避免顶层硬依赖）；
# assemble 运行时通过 isinstance 判定，不在此 import。
class _GraphLike:  # 仅作 Union 标注占位，运行时不使用
    pass


def _count_strategy_types(graph: Any, game_id: str) -> int:
    """统计该游戏在图谱中出现的不同 strategy_type 数量。"""
    try:
        from src.ceo_intelligence.growth_memory_graph.models import NodeType
    except Exception:  # pragma: no cover
        return 0
    try:
        nodes = [
            n
            for n in graph.query(NodeType.RESULT)
            if n.payload.get("game_id") == game_id
        ]
    except Exception:  # pragma: no cover - 防御性
        return 0
    return len({n.payload.get("strategy_type") for n in nodes if n.payload.get("strategy_type")})


# --------------------------------------------------------------------------- #
# 适配器：从真实上游填充 *Source（保持 P3.4.1 解耦，按需取用）
# --------------------------------------------------------------------------- #
def build_strategy_source(graph: Any, game_id: str) -> StrategySource:
    """从 E17.7 GrowthMemoryGraph 填充 StrategySource。"""
    rate = graph.success_rate_by(game_id=game_id)  # 0.0 if 无样本
    active = _count_strategy_types(graph, game_id)
    return StrategySource(
        strategy_score=rate,
        strategy_success_rate=rate,
        active_strategy_count=active,
    )


def build_execution_source(
    outcomes: List[Any], game_id: str
) -> ExecutionSource:
    """从 P2.5 的 SafeExecutionOutcome 列表（按 target==game_id 过滤）填充 ExecutionSource。"""
    from src.execution.monitor.health import compute_health_score

    per_game = [o for o in outcomes if getattr(o, "target", None) == game_id]
    if not per_game:
        return ExecutionSource()
    health = compute_health_score(per_game)
    failure_rate = (1.0 - health.success_rate) if health.success_rate is not None else None
    return ExecutionSource(
        execution_health=health.score,
        failure_rate=failure_rate,
    )


def build_recovery_source(rate: Optional[float] = None) -> RecoverySource:
    """填充 RecoverySource。

    注：P2.6 经验库按 failure 维度组织、不含 game_id，per-game recovery_rate 由
    P3.4.2 接 RecoveryIncident.target 预计算后注入；此处仅承载结果值。
    """
    return RecoverySource(recovery_rate=rate)


def build_lifecycle_source(manager: Any, game_id: str) -> LifecycleSource:
    """从 E15.1.2 PortfolioManager.stage_of(game_id) 填充 LifecycleSource。"""
    stage = manager.stage_of(game_id)
    return LifecycleSource(lifecycle_stage=stage, data_freshness=None)
