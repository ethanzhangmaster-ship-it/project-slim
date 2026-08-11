"""P3.4.3 — AllocationSimulator 单元测试。

覆盖验收 Case1–6 + 行为（risk / confidence / 序列化 / 无迁移边界）。

纪律断言（贯穿所有用例）：
- 只模拟不执行：``real_api_called`` 恒 ``False``，永不产出 ``ExecutionRequest``。
- 预算守恒：``sum(proposed) == sum(baseline)``。
- 不预测收入（分配只挪钱，不推断 revenue）。
"""

import pytest

from src.operator.portfolio.allocation_models import (
    AllocationSimulationResult,
    REAL_API_CALLED,
    RiskLevel,
    SimulationVerdict,
)
from src.operator.portfolio.constraints import AllocationConstraints
from src.operator.portfolio.models import GamePortfolioSnapshot, PortfolioSnapshot
from src.operator.portfolio.ranking_models import PortfolioVerdict
from src.operator.portfolio.simulator import (
    AllocationSimulator,
    build_allocation_simulator,
)

from tests.p3_4_3.helpers import make_candidate, make_constraints, make_game, make_snapshot

EPS = 1e-6


@pytest.fixture
def sim() -> AllocationSimulator:
    return build_allocation_simulator()


# ====================== Case1 — 正常模拟 ====================== #


class TestCase1NormalSimulation:
    def test_pass_with_correct_deltas(self, sim):
        snap = make_snapshot([
            make_game("a", spend=6000.0, roas=2.0, confidence=0.8,
                      execution_health=0.9, lifecycle_stage="scale"),
            make_game("b", spend=3000.0, roas=0.1, confidence=0.2,
                      execution_health=0.2, lifecycle_stage="prototype"),
        ])
        ranking = [
            make_candidate("a", PortfolioVerdict.SCALE, score=0.7, confidence=0.8),
            make_candidate("b", PortfolioVerdict.REDUCE, score=0.05, confidence=0.2),
        ]
        res = sim.simulate(snap, ranking, make_constraints(total_budget=10000.0))

        assert res.verdict == SimulationVerdict.PASS
        assert res.risk == RiskLevel.MEDIUM
        # 预算守恒
        assert abs(res.baseline_total - res.proposed_total) < EPS
        # B REDUCE: -0.5 * 3000 = -1500; A SCALE 吸收 +1500
        assert abs(res.delta_of("a").delta - 1500.0) < EPS
        assert abs(res.delta_of("b").delta + 1500.0) < EPS
        assert abs(res.delta_of("a").after - 7500.0) < EPS
        assert abs(res.delta_of("b").after - 1500.0) < EPS

    def test_confidence_full_when_all_known_and_ranked(self, sim):
        snap = make_snapshot([
            make_game("a", spend=6000.0, lifecycle_stage="scale"),
            make_game("b", spend=3000.0, lifecycle_stage="prototype"),
        ])
        ranking = [
            make_candidate("a", PortfolioVerdict.SCALE),
            make_candidate("b", PortfolioVerdict.REDUCE),
        ]
        res = sim.simulate(snap, ranking, make_constraints())
        assert abs(res.confidence - 1.0) < EPS

    def test_explanation_notes_reserve_maintained(self, sim):
        snap = make_snapshot([
            make_game("a", spend=6000.0, lifecycle_stage="scale"),
            make_game("b", spend=3000.0, lifecycle_stage="prototype"),
        ])
        ranking = [
            make_candidate("a", PortfolioVerdict.SCALE),
            make_candidate("b", PortfolioVerdict.REDUCE),
        ]
        res = sim.simulate(snap, ranking, make_constraints(total_budget=10000.0))
        assert "reserve_maintained" in res.notes
        assert "simulation only" in res.explanation.lower()


# ====================== Case2 — 超挪动上限 BLOCKED ====================== #


class TestCase2ExceedShiftLimit:
    def test_blocked_by_per_game_shift_cap(self, sim):
        # X 占预算 80% 且 SUNSET → 单游戏挪动 0.8*tb > max_shift_ratio 0.2
        snap = make_snapshot([
            make_game("x", spend=8000.0, lifecycle_stage="kill"),
            make_game("y", spend=1000.0, lifecycle_stage="scale"),
        ])
        ranking = [
            make_candidate("x", PortfolioVerdict.SUNSET),
            make_candidate("y", PortfolioVerdict.SCALE),
        ]
        res = sim.simulate(snap, ranking, make_constraints(total_budget=10000.0))

        assert res.verdict == SimulationVerdict.BLOCKED
        assert "per_game_shift_cap" in res.blocked_rules
        # 大额挪动 → HIGH 风险
        assert res.risk == RiskLevel.HIGH

    def test_no_proposed_change_recommended_when_blocked(self, sim):
        snap = make_snapshot([
            make_game("x", spend=8000.0, lifecycle_stage="kill"),
            make_game("y", spend=1000.0, lifecycle_stage="scale"),
        ])
        ranking = [
            make_candidate("x", PortfolioVerdict.SUNSET),
            make_candidate("y", PortfolioVerdict.SCALE),
        ]
        res = sim.simulate(snap, ranking, make_constraints(total_budget=10000.0))
        assert res.is_blocked
        assert "no allocation change" in res.explanation.lower()


# ====================== Case3 — 预算守恒 ====================== #


class TestCase3BudgetConservation:
    def test_sum_before_equals_sum_after(self, sim):
        snap = make_snapshot([
            make_game("a", spend=5000.0, lifecycle_stage="scale"),
            make_game("b", spend=3000.0, lifecycle_stage="prototype"),
            make_game("c", spend=1000.0, lifecycle_stage="soft_launch"),
        ])
        ranking = [
            make_candidate("a", PortfolioVerdict.SCALE),
            make_candidate("b", PortfolioVerdict.REDUCE),
            make_candidate("c", PortfolioVerdict.MAINTAIN),
        ]
        res = sim.simulate(snap, ranking, make_constraints(total_budget=10000.0))
        assert abs(res.baseline_total - res.proposed_total) < EPS
        # 所有 delta 之和 ≈ 0
        total_delta = sum(d.delta for d in res.delta)
        assert abs(total_delta) < EPS

    def test_each_proposed_is_baseline_plus_delta(self, sim):
        snap = make_snapshot([
            make_game("a", spend=5000.0, lifecycle_stage="scale"),
            make_game("b", spend=5000.0, lifecycle_stage="prototype"),
        ])
        ranking = [
            make_candidate("a", PortfolioVerdict.SCALE),
            make_candidate("b", PortfolioVerdict.REDUCE),
        ]
        res = sim.simulate(snap, ranking, make_constraints(total_budget=10000.0))
        for d in res.delta:
            assert abs(d.after - (d.before + d.delta)) < EPS


# ====================== Case4 — 空组合 BLOCKED ====================== #


class TestCase4EmptyPortfolio:
    def test_empty_snapshot_blocked(self, sim):
        snap = make_snapshot([])
        ranking: list = []
        res = sim.simulate(snap, ranking, make_constraints(total_budget=10000.0))

        assert res.verdict == SimulationVerdict.BLOCKED
        assert "non_empty" in res.blocked_rules
        assert "empty_portfolio_blocked" in res.notes
        assert res.real_api_called is False

    def test_empty_list_of_snapshots_blocked(self, sim):
        res = sim.simulate([], [], make_constraints(total_budget=10000.0))
        assert res.verdict == SimulationVerdict.BLOCKED
        assert "non_empty" in res.blocked_rules


# ====================== Case5 — real_api_called 恒 False ====================== #


class TestCase5NoRealApi:
    def test_real_api_called_false_on_result(self, sim):
        snap = make_snapshot([
            make_game("a", spend=6000.0, lifecycle_stage="scale"),
            make_game("b", spend=3000.0, lifecycle_stage="prototype"),
        ])
        ranking = [
            make_candidate("a", PortfolioVerdict.SCALE),
            make_candidate("b", PortfolioVerdict.REDUCE),
        ]
        res = sim.simulate(snap, ranking, make_constraints(total_budget=10000.0))
        assert res.real_api_called is False
        assert REAL_API_CALLED is False

    def test_constant_locked_false(self):
        # 常量层面锁死
        assert REAL_API_CALLED is False


# ====================== Case6 — 不产生 ExecutionRequest ====================== #


class TestCase6NoExecutionRequest:
    def test_result_type_is_simulation_not_execution(self, sim):
        snap = make_snapshot([
            make_game("a", spend=6000.0, lifecycle_stage="scale"),
            make_game("b", spend=3000.0, lifecycle_stage="prototype"),
        ])
        ranking = [
            make_candidate("a", PortfolioVerdict.SCALE),
            make_candidate("b", PortfolioVerdict.REDUCE),
        ]
        res = sim.simulate(snap, ranking, make_constraints(total_budget=10000.0))
        assert isinstance(res, AllocationSimulationResult)
        assert not hasattr(res, "execution_request")
        assert not hasattr(res, "execution_contract")

    def test_source_does_not_reference_execution_request(self):
        import src.operator.portfolio.simulator as mod
        from tests.p3_4_3.test_contract_boundary import _code_only
        src = _code_only(open(mod.__file__, encoding="utf-8").read())
        for token in ("ExecutionRequest", "ExecutionContract", "ExecutionIntent"):
            assert token not in src, f"simulator 不应引用 {token}"


# ====================== risk 等级 ====================== #


class TestRiskLevels:
    def test_low_when_tiny_move(self, sim):
        # tb 很大，挪动占比 ≤ 5%
        snap = make_snapshot([
            make_game("a", spend=1000.0, lifecycle_stage="scale"),
            make_game("b", spend=1000.0, lifecycle_stage="kill"),
        ])
        ranking = [
            make_candidate("a", PortfolioVerdict.SCALE),
            make_candidate("b", PortfolioVerdict.SUNSET),
        ]
        res = sim.simulate(snap, ranking, make_constraints(total_budget=100000.0))
        assert res.risk == RiskLevel.LOW

    def test_high_when_exceeds_max_shift_ratio(self, sim):
        # 同 Case2 超上限场景 → risk HIGH
        snap = make_snapshot([
            make_game("x", spend=8000.0, lifecycle_stage="kill"),
            make_game("y", spend=1000.0, lifecycle_stage="scale"),
        ])
        ranking = [
            make_candidate("x", PortfolioVerdict.SUNSET),
            make_candidate("y", PortfolioVerdict.SCALE),
        ]
        res = sim.simulate(snap, ranking, make_constraints(total_budget=10000.0))
        assert res.risk == RiskLevel.HIGH


# ====================== confidence 公式 ====================== #


class TestConfidence:
    def test_partial_known_lowers_confidence(self, sim):
        # b 缺 spend（unknown），但都在 ranking
        snap = make_snapshot([
            make_game("a", spend=6000.0, lifecycle_stage="scale"),
            make_game("b", spend=None, lifecycle_stage="prototype"),
        ])
        ranking = [
            make_candidate("a", PortfolioVerdict.SCALE),
            make_candidate("b", PortfolioVerdict.REDUCE),
        ]
        res = sim.simulate(snap, ranking, make_constraints(total_budget=10000.0))
        # known_ratio=0.5, coverage=1.0 → 0.75
        assert abs(res.confidence - 0.75) < EPS

    def test_partial_ranking_lowers_confidence(self, sim):
        # b 不在 ranking（coverage 降）
        snap = make_snapshot([
            make_game("a", spend=6000.0, lifecycle_stage="scale"),
            make_game("b", spend=3000.0, lifecycle_stage="prototype"),
        ])
        ranking = [make_candidate("a", PortfolioVerdict.SCALE)]
        res = sim.simulate(snap, ranking, make_constraints(total_budget=10000.0))
        # known_ratio=1.0, coverage=0.5 → 0.75
        assert abs(res.confidence - 0.75) < EPS


# ====================== 约束：软告警 WARN ====================== #


class TestTotalShiftWarn:
    def test_warn_when_gross_exceeds_soft_ratio(self, sim):
        # max_shift_ratio=0.5 → 单游戏 0.45 不 BLOCK，但 gross 0.45 > 0.35 → WARN
        snap = make_snapshot([
            make_game("a", spend=4500.0, lifecycle_stage="kill"),
            make_game("b", spend=4500.0, lifecycle_stage="scale"),
        ])
        ranking = [
            make_candidate("a", PortfolioVerdict.SUNSET),
            make_candidate("b", PortfolioVerdict.SCALE),
        ]
        res = sim.simulate(
            snap, ranking,
            make_constraints(total_budget=10000.0, max_shift_ratio=0.5, min_reserve_ratio=0.1),
        )
        assert res.verdict == SimulationVerdict.PASS
        warn = [c for c in res.constraints_checked if c.rule == "total_shift_warn"]
        assert warn and warn[0].status.value == "warn"
        assert "total_shift_warn" not in res.blocked_rules


# ====================== 无迁移边界 ====================== #


class TestNoMigrationBoundaries:
    def test_no_migration_when_nothing_scales(self, sim):
        # 全 REDUCE → 无人吸收 → 不发迁移，proposed == baseline
        snap = make_snapshot([
            make_game("a", spend=4000.0, lifecycle_stage="prototype"),
            make_game("b", spend=4000.0, lifecycle_stage="kill"),
        ])
        ranking = [
            make_candidate("a", PortfolioVerdict.REDUCE),
            make_candidate("b", PortfolioVerdict.SUNSET),
        ]
        res = sim.simulate(snap, ranking, make_constraints(total_budget=10000.0))
        assert res.verdict == SimulationVerdict.PASS
        assert abs(res.baseline_total - res.proposed_total) < EPS
        assert all(abs(d.delta) < EPS for d in res.delta)
        assert "no_demand_no_migration" in res.notes

    def test_games_without_ranking_do_not_move(self, sim):
        snap = make_snapshot([
            make_game("a", spend=5000.0, lifecycle_stage="scale"),
            make_game("b", spend=5000.0, lifecycle_stage="prototype"),
        ])
        ranking = [make_candidate("a", PortfolioVerdict.SCALE)]  # b 无排名
        res = sim.simulate(snap, ranking, make_constraints(total_budget=10000.0))
        # b 无排名 → delta 为 0
        assert abs(res.delta_of("b").delta) < EPS


# ====================== 序列化 ====================== #


class TestSerialization:
    def test_result_roundtrip(self, sim):
        snap = make_snapshot([
            make_game("a", spend=6000.0, lifecycle_stage="scale"),
            make_game("b", spend=3000.0, lifecycle_stage="prototype"),
        ])
        ranking = [
            make_candidate("a", PortfolioVerdict.SCALE),
            make_candidate("b", PortfolioVerdict.REDUCE),
        ]
        res = sim.simulate(snap, ranking, make_constraints(total_budget=10000.0))
        d = res.to_dict()
        res2 = AllocationSimulationResult.from_dict(d)
        assert res2.verdict == res.verdict
        assert abs(res2.baseline_total - res.baseline_total) < EPS
        assert abs(res2.proposed_total - res.proposed_total) < EPS
        assert res2.real_api_called is False
        assert len(res2.delta) == len(res.delta)
        assert res2.blocked_rules == res.blocked_rules

    def test_constraints_roundtrip(self):
        c = make_constraints(total_budget=12345.0, max_shift_ratio=0.33, min_reserve_ratio=0.2)
        c2 = AllocationConstraints.from_dict(c.to_dict())
        assert c2.total_budget == 12345.0
        assert c2.max_shift_ratio == 0.33
        assert c2.min_reserve_ratio == 0.2


# ====================== 输入兼容 ====================== #


class TestInputCompat:
    def test_accepts_list_of_snapshots(self, sim):
        s1 = make_snapshot([make_game("a", spend=6000.0, lifecycle_stage="scale")])
        s2 = make_snapshot([make_game("b", spend=3000.0, lifecycle_stage="prototype")])
        ranking = [
            make_candidate("a", PortfolioVerdict.SCALE),
            make_candidate("b", PortfolioVerdict.REDUCE),
        ]
        res = sim.simulate([s1, s2], ranking, make_constraints(total_budget=10000.0))
        assert res.verdict == SimulationVerdict.PASS
        assert set(g.game_id for g in res.baseline_allocation) == {"a", "b"}
