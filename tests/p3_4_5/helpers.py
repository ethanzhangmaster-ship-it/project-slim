"""P3.4.5 — 测试辅助：构造最小化可复现输入。"""

from src.operator.portfolio.constraints import AllocationConstraints
from src.operator.portfolio.models import GamePortfolioSnapshot, PortfolioSnapshot
from src.operator.portfolio.optimizer_models import (
    PortfolioOptimizationInput,
    PortfolioOptimizationResult,
)
from src.operator.portfolio.ranking_models import AllocationCandidate


def make_game(
    game_id: str,
    *,
    spend: float = 0.0,
    revenue: float = 0.0,
    roas: float = 0.0,
    confidence: float = 0.0,
    execution_health: float = 0.0,
    lifecycle_stage: str = "soft_launch",
    strategy_score: float = 0.0,
) -> GamePortfolioSnapshot:
    return GamePortfolioSnapshot(
        game_id=game_id,
        spend=spend,
        revenue=revenue,
        roas=roas,
        confidence=confidence,
        execution_health=execution_health,
        lifecycle_stage=lifecycle_stage,
        strategy_score=strategy_score,
    )


def make_snapshot(games, *, generated_at: str = "2026-07-30T00:00:00Z") -> PortfolioSnapshot:
    return PortfolioSnapshot(generated_at=generated_at, games=list(games))


def make_constraints(
    total_budget: float = 10000.0,
    max_shift_ratio: float = 0.2,
    min_reserve_ratio: float = 0.1,
) -> AllocationConstraints:
    return AllocationConstraints(
        total_budget=total_budget,
        max_shift_ratio=max_shift_ratio,
        min_reserve_ratio=min_reserve_ratio,
    )


def make_candidate(
    game_id: str,
    action: str = "maintain",
    *,
    rank: int = 1,
    score: float = 0.5,
    confidence: float = 0.9,
) -> AllocationCandidate:
    from src.operator.portfolio.ranking_models import PortfolioVerdict

    return AllocationCandidate(
        game_id=game_id,
        rank=rank,
        portfolio_score=score,
        recommended_action=PortfolioVerdict(action),
        recommended_budget_delta=0.0,
        priority=round(score * 100, 2),
        confidence=confidence,
        action_state="",
        reason=f"test candidate {game_id}",
    )


def make_optimizer_input(
    snapshot: PortfolioSnapshot,
    *,
    constraints: AllocationConstraints = None,
    rankings=None,
    current_allocation=None,
    data_age_days=None,
    as_of: str = None,
) -> PortfolioOptimizationInput:
    return PortfolioOptimizationInput(
        snapshots=snapshot,
        rankings=list(rankings) if rankings else [],
        constraints=constraints or make_constraints(),
        current_allocation=dict(current_allocation) if current_allocation else {},
        data_age_days=dict(data_age_days) if data_age_days else None,
        as_of=as_of or snapshot.generated_at,
    )
