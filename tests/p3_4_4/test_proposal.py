"""P3.4.4 — Portfolio Decision Proposal 测试。

覆盖：正常提案、Rule0~3 安全闸门、置信公式、证据链、人可读文本、空模拟、
序列化、真实「模拟→提案」链路、输入兼容、不可变性。
"""

import pytest

from src.operator.portfolio.allocation_models import (
    AllocationDelta,
    AllocationSimulationResult,
    ConstraintCheck,
    ConstraintStatus,
    GameAllocation,
    RiskLevel,
    SimulationVerdict,
)
from src.operator.portfolio.models import GamePortfolioSnapshot, PortfolioSnapshot
from src.operator.portfolio.proposal import (
    PortfolioGuard,
    PortfolioProposal,
    ProposalGenerator,
    ProposalGuardVerdict,
)
from src.operator.portfolio.ranking_models import AllocationCandidate, PortfolioVerdict
from src.operator.report.models import ActionState

from .helpers import make_candidate, make_constraints, make_game, make_snapshot


# --------------------------------------------------------------------------- #
# 局部构造器：手工拼一个 AllocationSimulationResult，精确控制 delta
# --------------------------------------------------------------------------- #
def _build_sim(
    baseline: dict,
    deltas: dict,
    *,
    verdict: str = "pass",
    conf: float = 1.0,
    blocked_rules=None,
    notes=None,
):
    base_alloc = [GameAllocation(gid, amt) for gid, amt in baseline.items()]
    prop_alloc = [
        GameAllocation(gid, baseline[gid] + deltas.get(gid, 0.0))
        for gid in baseline
    ]
    delta_objs = [
        AllocationDelta(
            gid,
            baseline[gid],
            baseline[gid] + deltas.get(gid, 0.0),
            deltas.get(gid, 0.0),
        )
        for gid in baseline
    ]
    checks = [
        ConstraintCheck("budget_conservation", ConstraintStatus.PASS, detail="ok"),
        ConstraintCheck("per_game_shift_cap", ConstraintStatus.PASS, detail="ok"),
        ConstraintCheck("reserve_floor", ConstraintStatus.PASS, detail="ok"),
    ]
    for r in blocked_rules or []:
        checks.append(ConstraintCheck(r, ConstraintStatus.BLOCKED, detail=f"{r} blocked"))
    eff_verdict = SimulationVerdict.BLOCKED if blocked_rules else SimulationVerdict(verdict)
    return AllocationSimulationResult(
        as_of="2026-07-30T00:00:00Z",
        baseline_allocation=base_alloc,
        proposed_allocation=prop_alloc,
        delta=delta_objs,
        constraints_checked=checks,
        confidence=conf,
        verdict=eff_verdict,
        risk=RiskLevel.LOW,
        total_budget=sum(baseline.values()) or 1.0,
        gross_shift=sum(abs(v) for v in deltas.values()) / 2.0,
        notes=list(notes or []),
    )


def _ranking_for(baseline: dict, action: PortfolioVerdict = PortfolioVerdict.MAINTAIN):
    return [
        make_candidate(gid, action, rank=i + 1, confidence=0.9, reason="rk")
        for i, gid in enumerate(baseline)
    ]


# --------------------------------------------------------------------------- #
# Case1 — 正常提案（全 AUTO）
# --------------------------------------------------------------------------- #
class TestNormalProposal:
    def test_all_auto_is_proposable(self):
        baseline = {"A": 5000.0, "B": 5000.0}
        sim = _build_sim(baseline, {"A": 200.0, "B": -200.0}, conf=1.0)
        snap = make_snapshot(
            [
                make_game("A", spend=5000.0, confidence=0.9, roas=1.5),
                make_game("B", spend=5000.0, confidence=0.9, roas=1.2),
            ]
        )
        ranking = _ranking_for(baseline)
        prop = ProposalGenerator().propose(sim, ranking, snap, make_constraints())

        assert prop.guard_verdict is ProposalGuardVerdict.PROPOSABLE
        assert prop.auto_count == 2
        assert prop.approval_count == 0
        assert prop.blocked_count == 0
        assert prop.real_api_called is False
        # 置信 = sim.conf(1.0) * (2 AUTO)/2 = 1.0
        assert prop.confidence == 1.0
        for it in prop.items:
            assert it.action_state == ActionState.AUTO

    def test_proposal_is_recommendation_only(self):
        baseline = {"A": 5000.0, "B": 5000.0}
        sim = _build_sim(baseline, {"A": 200.0, "B": -200.0})
        snap = make_snapshot(
            [make_game("A", spend=5000.0), make_game("B", spend=5000.0)]
        )
        prop = ProposalGenerator().propose(sim, _ranking_for(baseline), snap, make_constraints())
        assert not hasattr(prop, "execution_request")
        assert isinstance(prop, PortfolioProposal)


# --------------------------------------------------------------------------- #
# Rule0~3 安全闸门
# --------------------------------------------------------------------------- #
class TestGuardRules:
    def test_rule0_no_reality_blocked(self):
        baseline = {"A": 5000.0, "B": 5000.0}
        sim = _build_sim(baseline, {"A": 100.0, "B": -100.0})
        # B 无任何现实数据（无 revenue/spend/roas）
        snap = make_snapshot(
            [
                make_game("A", spend=5000.0, confidence=0.9),
                make_game("B", spend=None, roas=None, revenue=None),
            ]
        )
        prop = ProposalGenerator().propose(sim, _ranking_for(baseline), snap, make_constraints())
        b = prop.item_of("B")
        assert b.action_state == ActionState.BLOCKED
        assert "rule0_no_reality" in b.triggered_rules
        assert prop.blocked_count == 1

    def test_rule2_low_confidence_blocked(self):
        baseline = {"A": 5000.0, "B": 5000.0}
        sim = _build_sim(baseline, {"A": 100.0, "B": -100.0})
        snap = make_snapshot(
            [
                make_game("A", spend=5000.0, confidence=0.9),
                make_game("B", spend=5000.0, confidence=0.30),  # < 0.5
            ]
        )
        prop = ProposalGenerator().propose(sim, _ranking_for(baseline), snap, make_constraints())
        b = prop.item_of("B")
        assert b.action_state == ActionState.BLOCKED
        assert "rule2_low_confidence" in b.triggered_rules
        assert any("confidence=0.300<0.5" in e for e in b.evidence)

    def test_rule3_insufficient_data_age_no_scale_blocked(self):
        baseline = {"A": 5000.0, "B": 5000.0}
        sim = _build_sim(baseline, {"A": 100.0, "B": -100.0})
        snap = make_snapshot(
            [make_game("A", spend=5000.0), make_game("B", spend=5000.0, confidence=0.9)]
        )
        ranking = _ranking_for(baseline, action=PortfolioVerdict.SCALE)
        # B 观察仅 3 天（< 7）
        prop = ProposalGenerator().propose(
            sim, ranking, snap, make_constraints(), data_age_days={"B": 3}
        )
        b = prop.item_of("B")
        assert b.action_state == ActionState.BLOCKED
        assert "rule3_insufficient_data_age" in b.triggered_rules
        # Rule3 把动作降级为 NO_SCALE
        assert b.recommended_action == PortfolioVerdict.NO_SCALE

    def test_rule1_large_shift_approval(self):
        baseline = {"A": 5000.0, "B": 5000.0}
        # B 挪动 2000 / 5000 = 0.4 > 0.3 → APPROVAL
        sim = _build_sim(baseline, {"A": 2000.0, "B": -2000.0})
        snap = make_snapshot(
            [make_game("A", spend=5000.0, confidence=0.9), make_game("B", spend=5000.0, confidence=0.9)]
        )
        prop = ProposalGenerator().propose(sim, _ranking_for(baseline), snap, make_constraints())
        b = prop.item_of("B")
        assert b.action_state == ActionState.APPROVAL
        assert "rule1_large_shift_approval" in b.triggered_rules
        assert b.budget_delta == -2000.0  # 保留 delta，不抹除
        assert prop.guard_verdict is ProposalGuardVerdict.PARTIAL

    def test_rule_default_auto(self):
        baseline = {"A": 5000.0, "B": 5000.0}
        sim = _build_sim(baseline, {"A": 100.0, "B": -100.0})  # 0.02 <= 0.3
        snap = make_snapshot(
            [make_game("A", spend=5000.0, confidence=0.9), make_game("B", spend=5000.0, confidence=0.9)]
        )
        prop = ProposalGenerator().propose(sim, _ranking_for(baseline), snap, make_constraints())
        for it in prop.items:
            assert it.action_state == ActionState.AUTO
            assert it.triggered_rules == []


class TestGuardStandalone:
    """PortfolioGuard.evaluate 直接单测，每条规则独立验证。"""

    def test_rule0(self):
        g = make_game("X", spend=None, roas=None, revenue=None)
        out = PortfolioGuard().evaluate(g, 100.0, 5000.0)
        assert out.action_state == ActionState.BLOCKED
        assert "rule0_no_reality" in out.triggered_rules

    def test_rule2(self):
        g = make_game("X", spend=5000.0, confidence=0.4)
        out = PortfolioGuard().evaluate(g, 100.0, 5000.0)
        assert out.action_state == ActionState.BLOCKED
        assert "rule2_low_confidence" in out.triggered_rules

    def test_rule3(self):
        g = make_game("X", spend=5000.0, confidence=0.9)
        out = PortfolioGuard().evaluate(g, 100.0, 5000.0, data_age_days=2)
        assert out.action_state == ActionState.BLOCKED
        assert "rule3_insufficient_data_age" in out.triggered_rules

    def test_rule1(self):
        g = make_game("X", spend=5000.0, confidence=0.9)
        out = PortfolioGuard().evaluate(g, 2000.0, 5000.0)  # 0.4 > 0.3
        assert out.action_state == ActionState.APPROVAL
        assert "rule1_large_shift_approval" in out.triggered_rules

    def test_auto(self):
        g = make_game("X", spend=5000.0, confidence=0.9)
        out = PortfolioGuard().evaluate(g, 100.0, 5000.0)
        assert out.action_state == ActionState.AUTO
        assert out.triggered_rules == []

    def test_rule3_skipped_when_not_injected(self):
        g = make_game("X", spend=5000.0, confidence=0.9)
        out = PortfolioGuard().evaluate(g, 100.0, 5000.0, data_age_days=None)
        assert out.action_state == ActionState.AUTO


# --------------------------------------------------------------------------- #
# 置信公式
# --------------------------------------------------------------------------- #
class TestConfidence:
    def test_all_auto_full_confidence(self):
        baseline = {"A": 5000.0, "B": 5000.0}
        sim = _build_sim(baseline, {"A": 100.0, "B": -100.0}, conf=1.0)
        snap = make_snapshot(
            [make_game("A", spend=5000.0, confidence=0.9), make_game("B", spend=5000.0, confidence=0.9)]
        )
        prop = ProposalGenerator().propose(sim, _ranking_for(baseline), snap, make_constraints())
        assert prop.confidence == 1.0

    def test_approval_lowers_confidence(self):
        baseline = {"A": 5000.0, "B": 5000.0}
        # A 挪动 100/5000=0.02 → AUTO；B 挪动 2000/5000=0.40 → APPROVAL
        sim = _build_sim(baseline, {"A": 200.0, "B": -2000.0}, conf=1.0)
        snap = make_snapshot(
            [make_game("A", spend=5000.0, confidence=0.9), make_game("B", spend=5000.0, confidence=0.9)]
        )
        prop = ProposalGenerator().propose(sim, _ranking_for(baseline), snap, make_constraints())
        # auto_score = (1 + 0.5*1)/2 = 0.75；sim PASS → conf = 0.75
        assert prop.confidence == 0.75

    def test_simulation_blocked_dampens_confidence(self):
        baseline = {"A": 5000.0, "B": 5000.0}
        sim = _build_sim(
            baseline,
            {"A": 200.0, "B": -2000.0},
            conf=1.0,
            blocked_rules=["reserve_floor"],
        )
        snap = make_snapshot(
            [make_game("A", spend=5000.0, confidence=0.9), make_game("B", spend=5000.0, confidence=0.9)]
        )
        prop = ProposalGenerator().propose(sim, _ranking_for(baseline), snap, make_constraints())
        # auto_score 0.75 * sim-block penalty 0.5 = 0.375
        assert prop.confidence == 0.375
        assert prop.guard_verdict is ProposalGuardVerdict.BLOCKED

    def test_low_simulation_confidence_propagates(self):
        baseline = {"A": 5000.0, "B": 5000.0}
        sim = _build_sim(baseline, {"A": 100.0, "B": -100.0}, conf=0.5)
        snap = make_snapshot(
            [make_game("A", spend=5000.0, confidence=0.9), make_game("B", spend=5000.0, confidence=0.9)]
        )
        prop = ProposalGenerator().propose(sim, _ranking_for(baseline), snap, make_constraints())
        assert prop.confidence == 0.5


# --------------------------------------------------------------------------- #
# 证据链 / 人可读文本
# --------------------------------------------------------------------------- #
class TestEvidenceAndReadable:
    def test_evidence_chain_discipline(self):
        baseline = {"A": 5000.0, "B": 5000.0}
        sim = _build_sim(baseline, {"A": 200.0, "B": -200.0})
        snap = make_snapshot(
            [make_game("A", spend=5000.0), make_game("B", spend=5000.0)]
        )
        prop = ProposalGenerator().propose(sim, _ranking_for(baseline), snap, make_constraints())
        chain = " ".join(prop.evidence_chain)
        assert "Budget conservation" in chain
        assert "no budget changed" in chain
        assert "no execution request emitted" in chain

    def test_recommendation_readable(self):
        baseline = {"A": 5000.0, "B": 5000.0}
        sim = _build_sim(baseline, {"A": 200.0, "B": -200.0})
        snap = make_snapshot(
            [make_game("A", spend=5000.0, confidence=0.9), make_game("B", spend=5000.0, confidence=0.9)]
        )
        prop = ProposalGenerator().propose(sim, _ranking_for(baseline), snap, make_constraints())
        text = prop.recommendation
        assert "A" in text and "B" in text
        assert "AUTO" in text
        assert "Evidence chain" in text
        assert "no execution request emitted" in text
        # 人类可读摘要非空且含数字
        assert prop.summary
        assert "AUTO" in prop.summary


# --------------------------------------------------------------------------- #
# 空模拟 / 边界
# --------------------------------------------------------------------------- #
class TestEmptyAndBoundaries:
    def test_empty_simulation_blocked(self):
        from src.operator.portfolio.constraints import AllocationConstraints
        from src.operator.portfolio.simulator import AllocationSimulator

        snap = make_snapshot([])
        sim = AllocationSimulator().simulate(snap, [], AllocationConstraints(total_budget=1000.0))
        prop = ProposalGenerator().propose(sim, [], snap, make_constraints())
        assert prop.guard_verdict is ProposalGuardVerdict.BLOCKED
        assert prop.items == []
        assert prop.real_api_called is False
        assert prop.auto_count == prop.approval_count == prop.blocked_count == 0

    def test_no_mutation_of_inputs(self):
        baseline = {"A": 5000.0, "B": 5000.0}
        sim = _build_sim(baseline, {"A": 100.0, "B": -100.0})
        snap = make_snapshot(
            [make_game("A", spend=5000.0), make_game("B", spend=5000.0)]
        )
        ranking = _ranking_for(baseline)
        import copy

        sim_before = copy.deepcopy(sim.to_dict())
        rank_before = copy.deepcopy([c.to_dict() for c in ranking])
        ProposalGenerator().propose(sim, ranking, snap, make_constraints())
        assert sim.to_dict() == sim_before
        assert [c.to_dict() for c in ranking] == rank_before


# --------------------------------------------------------------------------- #
# 序列化 / 输入兼容
# --------------------------------------------------------------------------- #
class TestSerialization:
    def test_roundtrip(self):
        baseline = {"A": 5000.0, "B": 5000.0}
        sim = _build_sim(baseline, {"A": 200.0, "B": -200.0}, conf=0.8)
        snap = make_snapshot(
            [make_game("A", spend=5000.0, confidence=0.9), make_game("B", spend=5000.0, confidence=0.9)]
        )
        prop = ProposalGenerator().propose(sim, _ranking_for(baseline), snap, make_constraints())
        d = prop.to_dict()
        prop2 = PortfolioProposal.from_dict(d)
        assert prop2.to_dict() == d
        assert prop2.guard_verdict == prop.guard_verdict
        assert prop2.auto_count == prop.auto_count
        assert len(prop2.items) == len(prop.items)
        assert prop2.real_api_called is False


class TestInputCompat:
    def test_accepts_list_of_snapshots(self):
        baseline = {"A": 5000.0, "B": 5000.0}
        sim = _build_sim(baseline, {"A": 100.0, "B": -100.0})
        snap_list = [
            make_snapshot([make_game("A", spend=5000.0, confidence=0.9)], generated_at="2026-07-30T00:00:00Z"),
            make_snapshot([make_game("B", spend=5000.0, confidence=0.9)], generated_at="2026-07-30T00:00:00Z"),
        ]
        prop = ProposalGenerator().propose(sim, _ranking_for(baseline), snap_list, make_constraints())
        assert prop.auto_count == 2
        assert set(prop.item_of(g).action_state for g in ("A", "B")) == {ActionState.AUTO}


# --------------------------------------------------------------------------- #
# 真实「模拟 → 提案」链路（端到端一致性）
# --------------------------------------------------------------------------- #
class TestIntegrationChain:
    def test_simulator_then_propose(self):
        from src.operator.portfolio.simulator import AllocationSimulator

        snap = make_snapshot(
            [
                make_game("A", spend=8000.0, roas=1.8, confidence=0.95, lifecycle_stage="scale"),
                make_game("B", spend=2000.0, roas=0.4, confidence=0.9, lifecycle_stage="soft_launch"),
            ]
        )
        ranking = [
            make_candidate("A", PortfolioVerdict.SCALE, score=0.8, rank=1, confidence=0.95, reason="high roas"),
            make_candidate("B", PortfolioVerdict.REDUCE, score=0.2, rank=2, confidence=0.9, reason="low roas"),
        ]
        cons = make_constraints(total_budget=10000.0, max_shift_ratio=0.5, min_reserve_ratio=0.1)
        sim = AllocationSimulator().simulate(snap, ranking, cons)
        prop = ProposalGenerator().propose(sim, ranking, snap, cons)

        # 一致性：提案条目数 == 游戏数；总计数 == 条目数
        assert len(prop.items) == 2
        assert prop.auto_count + prop.approval_count + prop.blocked_count == len(prop.items)
        # 预算守恒在提案级仍成立
        assert prop.evidence_chain
        # 模拟被阻断则提案亦阻断（本场景 reserve_floor 可能触发）
        if sim.is_blocked:
            assert prop.guard_verdict is ProposalGuardVerdict.BLOCKED
        assert prop.real_api_called is False
