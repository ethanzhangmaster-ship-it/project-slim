"""P3.3.3 — 引擎工厂装配测试（build_adaptive_strategy_engine）。"""
from __future__ import annotations

from src.execution.approval.service import ApprovalService
from src.operator.adaptive_strategy import (
    AdaptiveStrategyController,
    AdaptiveStrategyFeedback,
    AdaptiveStrategyPlanner,
    AdaptiveStrategySimulator,
    FinalStatus,
    build_adaptive_strategy_engine,
)
from src.operator.strategy.memory import StrategyMemoryAdapter

from .conftest import blocking_prior, build_engine, make_request, ok_providers


def test_factory_returns_controller():
    ctrl = build_adaptive_strategy_engine()
    assert isinstance(ctrl, AdaptiveStrategyController)


def test_factory_wires_subcomponents():
    ctrl = build_adaptive_strategy_engine()
    assert isinstance(ctrl.planner, AdaptiveStrategyPlanner)
    assert isinstance(ctrl.simulator, AdaptiveStrategySimulator)
    assert isinstance(ctrl.feedback, AdaptiveStrategyFeedback)
    assert isinstance(ctrl.memory, StrategyMemoryAdapter)
    assert isinstance(ctrl.approval, ApprovalService)


def test_factory_injects_providers_and_runs():
    provs = ok_providers()
    ctrl = build_adaptive_strategy_engine(providers=provs)
    res = ctrl.run(make_request(mode="dry_run", approver="op1"))
    assert res.final_status == FinalStatus.COMPLETED.value
    # 注入的 provider 实际被路由到
    assert provs[0].execute_calls


def test_factory_injected_prior_provider_used():
    ctrl = build_adaptive_strategy_engine(
        providers=ok_providers(), prior_provider=blocking_prior)
    res = ctrl.run(make_request())
    assert res.simulation_flag == "block"
    assert res.final_status == FinalStatus.SIMULATION_FAIL.value


def test_factory_memory_path_persists(tmp_path):
    mem = str(tmp_path / "mem.jsonl")
    ctrl = build_adaptive_strategy_engine(
        providers=ok_providers(), memory_path=mem)
    res = ctrl.run(make_request(approver="op1", mode="dry_run"))
    assert res.final_status == FinalStatus.COMPLETED.value
    import os
    assert os.path.exists(mem)
    # 策略经验已落入文件
    with open(mem, "r", encoding="utf-8") as fh:
        content = fh.read()
    assert "adaptive.network_cleanup" in content


def test_factory_shared_approval_store():
    """Rule 4：ApprovalService 与 Router 必须共享同一个 approval_store。"""
    ctrl = build_adaptive_strategy_engine()
    res = ctrl.run(make_request(mode="dry_run", approver="op1"))
    assert res.final_status == FinalStatus.COMPLETED.value
    # ApprovalService 持有的 store 与内部 router 的 store 为同一实例
    assert ctrl.approval.store is ctrl.approval.router.authorization_gate.store
