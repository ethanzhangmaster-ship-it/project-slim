"""P3.3.3 — StrategyLoop 集成测试（提案关键词 → 自适应闭环）。"""
from __future__ import annotations

from types import SimpleNamespace

from src.operator.adaptive_strategy import (
    AdaptiveStrategyController,
    FinalStatus,
    build_adaptive_strategy_engine,
)
from src.operator.strategy.loop import StrategyLoop, write_strategy_outputs
from src.operator.strategy.memory import StrategyMemoryAdapter
from src.operator.strategy.models import StrategyProposal
from src.operator.strategy.mutation import StrategyMutationEngine

from .conftest import ok_providers


class KeywordMutator(StrategyMutationEngine):
    """返回含安全动作关键词的提案，确定性触发适配器。"""

    def propose(self, states, insights):
        return [
            StrategyProposal(
                current_strategy="network_cleanup",
                proposed_change="关停低 eCPM 僵尸网络",
                expected_impact="提升 ecpm",
                confidence=0.7,
            ),
            StrategyProposal(
                current_strategy="campaign_pause",
                proposed_change="暂停亏损系列止损",
                expected_impact="改善 roas",
                confidence=0.7,
            ),
            StrategyProposal(
                current_strategy="creative_refresh",
                proposed_change="刷新素材",
                expected_impact="降低疲劳",
                confidence=0.6,
            ),
        ]


def _loop(adapter, target="game_x"):
    engine = build_adaptive_strategy_engine(providers=ok_providers())
    return StrategyLoop(
        memory_adapter=adapter,
        mutation_engine=KeywordMutator(),
        adaptive_controller=engine,
    ), engine


def _daily():
    return SimpleNamespace(actions=[])


def test_loop_adapts_matching_proposals():
    mem = StrategyMemoryAdapter(store_path=None)
    loop, _ = _loop(mem)
    res = loop.run(
        _daily(),
        adaptive_target="game_x",
        adaptive_mode="dry_run",
        adaptive_approver="op1",
        adaptive_approver_role="OPERATOR",
    )
    # 两个安全动作提案被闭环（第三个 creative_refresh 不匹配）
    assert len(res.adaptive) == 2
    for r in res.adaptive:
        assert r.final_status == FinalStatus.COMPLETED.value
        assert r.real_api_called is False


def test_loop_adaptive_results_have_correct_strategy():
    mem = StrategyMemoryAdapter(store_path=None)
    loop, _ = _loop(mem)
    res = loop.run(
        _daily(), adaptive_target="game_x", adaptive_mode="dry_run",
        adaptive_approver="op1", adaptive_approver_role="OPERATOR",
    )
    ids = {r.strategy_id for r in res.adaptive}
    assert "adaptive.network_cleanup" in ids
    assert "adaptive.campaign_pause" in ids


def test_loop_preserves_p3_3_proposals():
    mem = StrategyMemoryAdapter(store_path=None)
    loop, _ = _loop(mem)
    res = loop.run(
        _daily(), adaptive_target="game_x", adaptive_mode="dry_run",
        adaptive_approver="op1", adaptive_approver_role="OPERATOR",
    )
    # P3.3 非变异路径保持完整（3 条提案原样产出）
    assert len(res.proposals) == 3
    # 仅匹配安全模板的才进入 adaptive 闭环
    assert len(res.adaptive) == 2


def test_loop_no_adaptive_when_target_absent():
    mem = StrategyMemoryAdapter(store_path=None)
    loop, _ = _loop(mem)
    res = loop.run(_daily())  # 未传 adaptive_target
    assert res.adaptive == []


def test_loop_adaptive_writes_output(tmp_path):
    mem = StrategyMemoryAdapter(store_path=None)
    loop, _ = _loop(mem)
    res = loop.run(
        _daily(), adaptive_target="game_x", adaptive_mode="dry_run",
        adaptive_approver="op1", adaptive_approver_role="OPERATOR",
    )
    out = tmp_path / "out"
    paths = write_strategy_outputs("2026-07-31", str(out), res)
    import json
    from pathlib import Path
    assert Path(paths["strategy_adaptive"]).exists()
    data = json.loads(Path(paths["strategy_adaptive"]).read_text(encoding="utf-8"))
    assert len(data) == 2
    assert data[0]["final_status"] == "completed"


def test_loop_adaptive_runs_production_when_requested():
    mem = StrategyMemoryAdapter(store_path=None)
    loop, _ = _loop(mem)
    res = loop.run(
        _daily(), adaptive_target="game_x", adaptive_mode="production",
        adaptive_approver="op1", adaptive_approver_role="OPERATOR",
    )
    # PRODUCTION：real_api_called 应为 True
    for r in res.adaptive:
        assert r.real_api_called is True
        assert r.final_status == FinalStatus.COMPLETED.value


def test_loop_adaptive_controller_is_optional():
    """未装配 adaptive_controller 时不应报错，也不产生 adaptive 结果。"""
    mem = StrategyMemoryAdapter(store_path=None)
    loop = StrategyLoop(memory_adapter=mem, mutation_engine=KeywordMutator())
    res = loop.run(
        _daily(), adaptive_target="game_x", adaptive_mode="dry_run",
        adaptive_approver="op1",
    )
    assert res.adaptive == []


def test_loop_manual_no_approver_stays_recovery():
    mem = StrategyMemoryAdapter(store_path=None)
    loop, _ = _loop(mem)
    res = loop.run(
        _daily(), adaptive_target="game_x", adaptive_mode="dry_run",
        adaptive_approver="",  # 无审批人
    )
    # 两条安全提案都停在 RECOVERY_REQUIRED，不执行
    assert len(res.adaptive) == 2
    for r in res.adaptive:
        assert r.final_status == FinalStatus.RECOVERY_REQUIRED.value
