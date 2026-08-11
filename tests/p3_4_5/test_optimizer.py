"""P3.4.5 — Portfolio Optimizer 编排测试（Case1~Case6 + 状态/序列化/兼容）。

边界纪律：optimizer 只编排不决策；不重算、不执行、不调 Provider、
不产生 ExecutionRequest；``real_api_called`` 恒 False。
"""

import copy

import pytest

from src.operator.portfolio.optimizer import PortfolioOptimizer, build_portfolio_optimizer
from src.operator.portfolio.optimizer_models import (
    OptimizationStatus,
    PortfolioOptimizationInput,
    PortfolioOptimizationResult,
)
from src.operator.report.sections import build_portfolio_recommendation_section

from .helpers import (
    make_candidate,
    make_constraints,
    make_game,
    make_optimizer_input,
    make_snapshot,
)


# --------------------------------------------------------------------------- #
# Case1 — 完整链路 Snapshot→Rank→Simulation→Proposal→Result PASS
# --------------------------------------------------------------------------- #
class TestCase1FullChain:
    def test_full_chain_completed(self):
        # A 高 ROAS 扩量、B 低 ROAS 缩减；小挪动留储备，使方案可落地
        snap = make_snapshot(
            [
                make_game(
                    "A",
                    spend=9000.0,
                    revenue=16000.0,
                    roas=1.8,
                    confidence=0.9,
                    execution_health=0.8,
                    lifecycle_stage="scale",
                ),
                make_game(
                    "B",
                    spend=1000.0,
                    revenue=300.0,
                    roas=0.3,
                    confidence=0.9,
                    execution_health=0.7,
                    lifecycle_stage="soft_launch",
                ),
            ]
        )
        cons = make_constraints(min_reserve_ratio=0.0, max_shift_ratio=0.6)
        inp = make_optimizer_input(snap, constraints=cons)
        res = PortfolioOptimizer().optimize(inp)

        assert res.status is OptimizationStatus.COMPLETED
        assert res.real_api_called is False
        assert res.proposal is not None
        assert res.proposal.is_blocked is False
        assert res.simulation is not None
        assert res.simulation.verdict.value == "pass"
        assert len(res.ranked_games) == 2
        # 排名确定性：A 分数更高应排第一
        assert res.ranked_games[0].game_id == "A"
        # 含至少一个 AUTO 项（A 挪动比例 < 0.30）
        auto = [i for i in res.proposal.items if i.action_state.value == "auto"]
        assert auto, "expected at least one AUTO item"

    def test_chain_emits_readable_proposal(self):
        snap = make_snapshot(
            [
                make_game("A", spend=9000.0, revenue=16000.0, roas=1.8, confidence=0.9, lifecycle_stage="scale"),
                make_game("B", spend=1000.0, revenue=300.0, roas=0.3, confidence=0.9, lifecycle_stage="soft_launch"),
            ]
        )
        res = PortfolioOptimizer().optimize(make_optimizer_input(snap, constraints=make_constraints(min_reserve_ratio=0.0, max_shift_ratio=0.6)))
        assert res.proposal.summary
        assert "recommend" in res.proposal.recommendation.lower() or "AUTO" in res.proposal.recommendation
        assert res.proposal.recommendation.strip()


# --------------------------------------------------------------------------- #
# Case2 — 空 Portfolio → INSUFFICIENT_DATA
# --------------------------------------------------------------------------- #
class TestCase2EmptyPortfolio:
    def test_empty_snapshot_insufficient(self):
        snap = make_snapshot([])
        res = PortfolioOptimizer().optimize(make_optimizer_input(snap))
        assert res.status is OptimizationStatus.INSUFFICIENT_DATA
        assert res.proposal is None
        assert res.simulation is None
        assert res.ranked_games == []
        assert res.real_api_called is False
        assert any("INSUFFICIENT_DATA" in e for e in res.evidence)

    def test_list_of_empty_snapshots_insufficient(self):
        res = PortfolioOptimizer().optimize(
            PortfolioOptimizationInput(snapshots=[make_snapshot([]), make_snapshot([])])
        )
        assert res.status is OptimizationStatus.INSUFFICIENT_DATA


# --------------------------------------------------------------------------- #
# Case3 — Simulation BLOCKED → Optimizer 不覆盖，Proposal 仍 BLOCKED
# --------------------------------------------------------------------------- #
class TestCase3SimBlockedNotOverridden:
    def test_blocked_simulation_propagates(self):
        # 大挪动 + 保留储备下限 0.1 → reserve_floor 阻断
        snap = make_snapshot(
            [
                make_game("A", spend=5000.0, revenue=9000.0, roas=1.8, confidence=0.9, lifecycle_stage="scale"),
                make_game("B", spend=5000.0, revenue=2000.0, roas=0.5, confidence=0.9, lifecycle_stage="soft_launch"),
            ]
        )
        cons = make_constraints(min_reserve_ratio=0.1, max_shift_ratio=0.6)
        res = PortfolioOptimizer().optimize(make_optimizer_input(snap, constraints=cons))

        # 模拟本身被约束阻断
        assert res.simulation.verdict.value == "blocked"
        assert "reserve_floor" in res.simulation.blocked_rules
        # 编排**不覆盖**下层标记
        assert res.status is OptimizationStatus.BLOCKED
        assert res.proposal is not None
        assert res.proposal.is_blocked is True
        assert res.proposal.guard_verdict.value == "blocked"


# --------------------------------------------------------------------------- #
# Case4 — 输入不可变（snapshot / ranking / simulation 不被 mutate）
# --------------------------------------------------------------------------- #
class TestCase4InputImmutability:
    def test_snapshot_and_rankings_unchanged(self):
        snap = make_snapshot(
            [
                make_game("A", spend=9000.0, revenue=16000.0, roas=1.8, confidence=0.9, lifecycle_stage="scale"),
                make_game("B", spend=1000.0, revenue=300.0, roas=0.3, confidence=0.9, lifecycle_stage="soft_launch"),
            ]
        )
        snap_before = copy.deepcopy(snap)
        rankings = [
            make_candidate("A", "scale", rank=1),
            make_candidate("B", "reduce", rank=2),
        ]
        rankings_before = copy.deepcopy(rankings)

        inp = make_optimizer_input(
            snap, constraints=make_constraints(min_reserve_ratio=0.0, max_shift_ratio=0.6), rankings=rankings
        )
        PortfolioOptimizer().optimize(inp)

        # snapshot 未被改写
        assert snap.games[0].spend == snap_before.games[0].spend
        assert [g.game_id for g in snap.games] == [g.game_id for g in snap_before.games]
        # rankings 未被改写
        assert [(c.game_id, c.rank) for c in rankings] == [
            (c.game_id, c.rank) for c in rankings_before
        ]
        assert all(c.action_state == "" for c in rankings)  # guard 不在 ranking 上填

    def test_optimizer_is_stateless(self):
        snap = make_snapshot(
            [
                make_game("A", spend=9000.0, revenue=16000.0, roas=1.8, confidence=0.9, lifecycle_stage="scale"),
                make_game("B", spend=1000.0, revenue=300.0, roas=0.3, confidence=0.9, lifecycle_stage="soft_launch"),
            ]
        )
        cons = make_constraints(min_reserve_ratio=0.0, max_shift_ratio=0.6)
        opt = PortfolioOptimizer()
        r1 = opt.optimize(make_optimizer_input(snap, constraints=cons))
        r2 = opt.optimize(make_optimizer_input(snap, constraints=cons))
        assert r1.status == r2.status == OptimizationStatus.COMPLETED
        assert r1.optimization_id == r2.optimization_id


# --------------------------------------------------------------------------- #
# Case5 — real_api_called 必须 False
# --------------------------------------------------------------------------- #
class TestCase5NoRealApi:
    def test_real_api_called_false(self):
        snap = make_snapshot(
            [
                make_game("A", spend=9000.0, revenue=16000.0, roas=1.8, confidence=0.9, lifecycle_stage="scale"),
                make_game("B", spend=1000.0, revenue=300.0, roas=0.3, confidence=0.9, lifecycle_stage="soft_launch"),
            ]
        )
        res = PortfolioOptimizer().optimize(make_optimizer_input(snap, constraints=make_constraints(min_reserve_ratio=0.0, max_shift_ratio=0.6)))
        assert res.real_api_called is False
        assert res.proposal.real_api_called is False
        assert res.simulation.real_api_called is False

    def test_result_constant_locked_false(self):
        from src.operator.portfolio.allocation_models import REAL_API_CALLED

        assert REAL_API_CALLED is False


# --------------------------------------------------------------------------- #
# Case6 — CEO Report 集成：PortfolioRecommendation section 可消费 Result
# --------------------------------------------------------------------------- #
class TestCase6ReportSectionConsume:
    def _completed(self) -> PortfolioOptimizationResult:
        snap = make_snapshot(
            [
                make_game("A", spend=9000.0, revenue=16000.0, roas=1.8, confidence=0.9, lifecycle_stage="scale"),
                make_game("B", spend=1000.0, revenue=300.0, roas=0.3, confidence=0.9, lifecycle_stage="soft_launch"),
            ]
        )
        return PortfolioOptimizer().optimize(make_optimizer_input(snap, constraints=make_constraints(min_reserve_ratio=0.0, max_shift_ratio=0.6)))

    def test_section_consumes_result(self):
        res = self._completed()
        sec = build_portfolio_recommendation_section(res)
        assert sec["title"] == "Portfolio Recommendation"
        assert sec["status"] == "completed"
        assert len(sec["items"]) == 2
        assert sec["real_api_called"] is False
        # 段含可读建议
        assert sec["recommendation"]
        # 段不携带任何执行请求字段
        assert "execution_request" not in sec
        assert "execution_contract" not in sec

    def test_section_handles_insufficient_data(self):
        snap = make_snapshot([])
        res = PortfolioOptimizer().optimize(make_optimizer_input(snap))
        sec = build_portfolio_recommendation_section(res)
        assert sec["status"] == "insufficient_data"
        assert sec["items"] == []
        assert sec["real_api_called"] is False

    def test_section_rejects_wrong_type(self):
        with pytest.raises(TypeError):
            build_portfolio_recommendation_section({"foo": "bar"})


# --------------------------------------------------------------------------- #
# 状态枚举 / 序列化 / 输入兼容
# --------------------------------------------------------------------------- #
class TestStatusEnum:
    def test_status_values(self):
        assert OptimizationStatus.COMPLETED.value == "completed"
        assert OptimizationStatus.BLOCKED.value == "blocked"
        assert OptimizationStatus.INSUFFICIENT_DATA.value == "insufficient_data"


class TestSerialization:
    def test_completed_round_trip(self):
        snap = make_snapshot(
            [
                make_game("A", spend=9000.0, revenue=16000.0, roas=1.8, confidence=0.9, lifecycle_stage="scale"),
                make_game("B", spend=1000.0, revenue=300.0, roas=0.3, confidence=0.9, lifecycle_stage="soft_launch"),
            ]
        )
        res = PortfolioOptimizer().optimize(make_optimizer_input(snap, constraints=make_constraints(min_reserve_ratio=0.0, max_shift_ratio=0.6)))
        d = res.to_dict()
        res2 = PortfolioOptimizationResult.from_dict(d)
        assert res2.to_dict() == d
        assert res2.status is res.status
        assert res2.optimization_id == res.optimization_id

    def test_insufficient_round_trip(self):
        res = PortfolioOptimizer().optimize(make_optimizer_input(make_snapshot([])))
        d = res.to_dict()
        res2 = PortfolioOptimizationResult.from_dict(d)
        assert res2.to_dict() == d
        assert res2.proposal is None
        assert res2.simulation is None


class TestInputCompat:
    def test_list_of_snapshots_merged(self):
        s1 = make_snapshot([make_game("A", spend=9000.0, revenue=16000.0, roas=1.8, confidence=0.9, lifecycle_stage="scale")], generated_at="2026-07-30T00:00:00Z")
        s2 = make_snapshot([make_game("B", spend=1000.0, revenue=300.0, roas=0.3, confidence=0.9, lifecycle_stage="soft_launch")], generated_at="2026-07-30T00:00:00Z")
        res = PortfolioOptimizer().optimize(
            PortfolioOptimizationInput(snapshots=[s1, s2], constraints=make_constraints(min_reserve_ratio=0.0, max_shift_ratio=0.6))
        )
        assert res.status is OptimizationStatus.COMPLETED
        assert len(res.ranked_games) == 2

    def test_supplied_rankings_used(self):
        snap = make_snapshot(
            [
                make_game("A", spend=9000.0, revenue=16000.0, roas=1.8, confidence=0.9, lifecycle_stage="scale"),
                make_game("B", spend=1000.0, revenue=300.0, roas=0.3, confidence=0.9, lifecycle_stage="soft_launch"),
            ]
        )
        rankings = [
            make_candidate("B", "reduce", rank=1),
            make_candidate("A", "scale", rank=2),
        ]
        res = PortfolioOptimizer().optimize(
            make_optimizer_input(snap, constraints=make_constraints(min_reserve_ratio=0.0, max_shift_ratio=0.6), rankings=rankings)
        )
        # 采用上游 rankings（不内部重排）
        assert [c.game_id for c in res.ranked_games] == ["B", "A"]
        assert "re-ranked internally=no" in res.evidence[0]

    def test_current_allocation_appears_in_evidence(self):
        snap = make_snapshot(
            [
                make_game("A", spend=9000.0, revenue=16000.0, roas=1.8, confidence=0.9, lifecycle_stage="scale"),
                make_game("B", spend=1000.0, revenue=300.0, roas=0.3, confidence=0.9, lifecycle_stage="soft_launch"),
            ]
        )
        res = PortfolioOptimizer().optimize(
            make_optimizer_input(
                snap,
                constraints=make_constraints(min_reserve_ratio=0.0, max_shift_ratio=0.6),
                current_allocation={"A": 9000.0, "B": 1000.0},
            )
        )
        assert any("Current allocation provided" in e for e in res.evidence)


class TestFactory:
    def test_build_factory(self):
        opt = build_portfolio_optimizer()
        assert isinstance(opt, PortfolioOptimizer)
        assert opt.ranker is not None
        assert opt.simulator is not None
        assert opt.proposer is not None
