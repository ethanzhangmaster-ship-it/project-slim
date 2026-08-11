"""P3.4.4 测试共用 builder：构造最小 snapshot / candidate / simulation / proposal。"""

from src.operator.portfolio.constraints import AllocationConstraints
from src.operator.portfolio.models import GamePortfolioSnapshot, PortfolioSnapshot
from src.operator.portfolio.ranking_models import AllocationCandidate, PortfolioVerdict
from src.operator.portfolio.simulator import AllocationSimulator


def make_game(
    game_id: str,
    *,
    spend: float = None,
    roas: float = 0.0,
    confidence: float = 0.0,
    execution_health: float = 0.0,
    lifecycle_stage: str = "soft_launch",
    revenue: float = None,
) -> GamePortfolioSnapshot:
    return GamePortfolioSnapshot(
        game_id=game_id,
        spend=spend,
        roas=roas,
        confidence=confidence,
        execution_health=execution_health,
        lifecycle_stage=lifecycle_stage,
        revenue=revenue,
    )


def make_snapshot(games, *, generated_at: str = "2026-07-30T00:00:00Z") -> PortfolioSnapshot:
    return PortfolioSnapshot(generated_at=generated_at, games=list(games))


def make_candidate(
    game_id: str,
    action: PortfolioVerdict,
    *,
    score: float = 0.5,
    rank: int = 1,
    confidence: float = 0.0,
    reason: str = "test",
) -> AllocationCandidate:
    return AllocationCandidate(
        game_id=game_id,
        rank=rank,
        portfolio_score=score,
        recommended_action=action,
        recommended_budget_delta=0.0,
        priority=round(score * 100, 2),
        confidence=confidence,
        action_state="",
        reason=reason,
    )


def make_constraints(
    total_budget: float = 10000.0,
    max_shift_ratio: float = 0.5,
    min_reserve_ratio: float = 0.1,
) -> AllocationConstraints:
    return AllocationConstraints(
        total_budget=total_budget,
        max_shift_ratio=max_shift_ratio,
        min_reserve_ratio=min_reserve_ratio,
    )


def make_simulation(snapshot, ranking, constraints) -> "object":
    """跑一次 P3.4.3 模拟，返回 AllocationSimulationResult（供 proposal 消费）。"""
    return AllocationSimulator().simulate(snapshot, ranking, constraints)
