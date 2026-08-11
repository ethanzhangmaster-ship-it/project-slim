"""
P3.5.1 — GrowthKnowledgeAdvisor 单元测试（Case1~Case4 + 两个决策入口集成）。

覆盖契约：
- Case1 没历史：signal.confidence == 0
- Case2 成功模式：success_rate > 0.8，正向信号（无 risk）
- Case3 失败模式：risk_flags 被填充
- Case4 Graph 不可用：fail-open，不影响主链
- 集成：Portfolio Ranker 经验修正 / Strategy Loop 经验降权
"""
from __future__ import annotations

import pytest

from src.ceo_intelligence.growth_memory_graph.advisor import (
    GrowthKnowledgeAdvisor,
    knowledge_adjusted_confidence,
    knowledge_requires_approval,
)
from src.operator.strategy.models import StrategyProposal

from .helpers import (
    build_advisor,
    build_kg_empty,
    build_kg_failure,
    build_kg_strategy_failure,
    build_kg_success,
)


# --------------------------------------------------------------------------- #
# Case1：没历史 → 空信号
# --------------------------------------------------------------------------- #
def test_case1_no_history_confidence_zero():
    adv = build_advisor(build_kg_empty())
    sig = adv.advise_portfolio("game_a")
    assert sig.confidence == 0.0
    assert sig.historical_success_rate == 0.0
    assert sig.similar_case_count == 0
    assert sig.is_empty()


# --------------------------------------------------------------------------- #
# Case2：成功模式 → 正向信号
# --------------------------------------------------------------------------- #
def test_case2_success_pattern_positive():
    adv = build_advisor(build_kg_success())
    sig = adv.advise_portfolio("game_a")
    assert sig.similar_case_count > 0
    assert sig.historical_success_rate > 0.8
    assert sig.confidence > 0.0
    assert sig.risk_flags == []
    assert not sig.has_risk()
    assert sig.evidence  # 有人可读证据


# --------------------------------------------------------------------------- #
# Case3：失败模式 → risk_flags 被填充
# --------------------------------------------------------------------------- #
def test_case3_failure_pattern_risk_flags():
    adv = build_advisor(build_kg_failure())
    sig = adv.advise_portfolio("game_a")
    assert sig.similar_case_count > 0
    assert sig.historical_success_rate < 0.4
    assert sig.risk_flags
    assert "low_historical_success" in sig.risk_flags
    assert "historical_scale_failure" in sig.risk_flags


# --------------------------------------------------------------------------- #
# Case4：Graph 不可用 → fail-open
# --------------------------------------------------------------------------- #
def test_case4_graph_none_fail_open():
    adv = build_advisor(None)
    sig = adv.advise_portfolio("game_a")
    assert sig.is_empty()


def test_case4_graph_raises_fail_open():
    """图查询抛异常也不应中断主链。"""

    class _Boom:
        def similar_games(self, gid):
            raise RuntimeError("boom")

        def why_game_succeeded(self, gid):
            raise RuntimeError("boom")

        def strategy_results_by_success(self, descending=True):
            raise RuntimeError("boom")

    adv = build_advisor(_Boom())
    assert adv.advise_portfolio("game_a").is_empty()
    prop = StrategyProposal(
        current_strategy="x", proposed_change="y", expected_impact="z", confidence=0.5
    )
    assert adv.advise_strategy(prop).is_empty()


def test_advisor_real_api_called_false():
    adv = build_advisor(build_kg_success())
    assert adv.real_api_called is False


# --------------------------------------------------------------------------- #
# 第二接入点：advise_strategy
# --------------------------------------------------------------------------- #
def test_advise_strategy_failure_pattern():
    adv = build_advisor(build_kg_strategy_failure())
    prop = StrategyProposal(
        current_strategy="aggressive_scale",
        proposed_change="increase budget 30%",
        expected_impact="roas up",
        confidence=0.82,
    )
    sig = adv.advise_strategy(prop)
    assert sig.risk_flags
    assert "historical_failure_pattern" in sig.risk_flags
    assert sig.historical_success_rate < 0.4
    # 降权：0.82 → 更低
    assert knowledge_requires_approval(sig) is True
    assert knowledge_adjusted_confidence(0.82, sig) < 0.82


def test_advise_strategy_no_match_empty():
    adv = build_advisor(build_kg_strategy_failure())
    prop = StrategyProposal(
        current_strategy="creative_refresh",
        proposed_change="new color",
        expected_impact="ctr up",
        confidence=0.9,
    )
    sig = adv.advise_strategy(prop)
    assert sig.is_empty()


# --------------------------------------------------------------------------- #
# 集成：P3.4 Portfolio Ranker 经验修正
# --------------------------------------------------------------------------- #
def test_ranker_integrates_knowledge_signal():
    from src.operator.portfolio.models import GamePortfolioSnapshot
    from src.operator.portfolio.ranker import PortfolioRanker

    adv = build_advisor(build_kg_failure())
    a = GamePortfolioSnapshot(
        game_id="game_a", roas=1.5, confidence=0.9,
        execution_health=0.9, lifecycle_stage="scale",
    )
    b = GamePortfolioSnapshot(
        game_id="game_b", roas=1.5, confidence=0.9,
        execution_health=0.9, lifecycle_stage="scale",
    )

    # 无 advisor：同分 → game_id 升序，game_a 在前
    base = PortfolioRanker().rank([a, b])
    assert base[0].game_id == "game_a"

    # 有 advisor：game_a 有负面历史 → 被经验下压到 game_b 之后
    signals = {
        "game_a": adv.advise_portfolio(a),
        "game_b": adv.advise_portfolio(b),
    }
    aug = PortfolioRanker().rank([a, b], knowledge_signals=signals)
    assert aug[0].game_id == "game_b"
    assert aug[1].game_id == "game_a"

    a_cand = next(c for c in aug if c.game_id == "game_a")
    assert a_cand.knowledge_signal is not None
    assert a_cand.knowledge_adjustment < 0  # 负向修正


def test_ranker_without_signals_unchanged():
    """不传 knowledge_signals 时，行为与 P3.4.2 完全一致（零回归）。"""
    from src.operator.portfolio.models import GamePortfolioSnapshot
    from src.operator.portfolio.ranker import PortfolioRanker

    a = GamePortfolioSnapshot(game_id="g", roas=1.5, confidence=0.8,
                               execution_health=0.9, lifecycle_stage="scale")
    c1 = PortfolioRanker().rank([a])[0]
    c2 = PortfolioRanker().rank([a], knowledge_signals=None)[0]
    assert c1.portfolio_score == c2.portfolio_score
    assert c1.priority == c2.priority
    assert c1.knowledge_signal is None


# --------------------------------------------------------------------------- #
# 集成：P3.3 Strategy Loop 经验降权
# --------------------------------------------------------------------------- #
def test_strategy_loop_applies_knowledge_signal(tmp_path):
    from src.ceo_intelligence.daily_operator.models import (
        ActionKind,
        DailyActionItem,
        DailyRunResult,
    )
    from src.operator.strategy.guard import StrategyGuard
    from src.operator.strategy.loop import StrategyLoop
    from src.operator.strategy.memory import StrategyMemoryAdapter
    from src.operator.strategy.models import StrategyFeedback, StrategyStatus

    store = str(tmp_path / "sm.jsonl")
    adapter = StrategyMemoryAdapter(store_path=store)
    # 预禁用 aggressive_scale（连续失败；属 SAFER_VARIANT，loop 会产出 gated 提案）
    for _ in range(5):
        adapter.apply_feedback(
            StrategyFeedback(
                action_id="x", strategy_id="aggressive_scale",
                reward=-0.4, outcome="FAILURE", evidence="t",
            )
        )
    adapter.save()
    assert adapter.all_states()["aggressive_scale"].status == StrategyStatus.DISABLED

    adv = build_advisor(build_kg_strategy_failure())
    loop = StrategyLoop(
        memory_adapter=adapter, guard=StrategyGuard(), graph=None, advisor=adv
    )

    daily = DailyRunResult(
        date="2026-07-31",
        actions=[
            DailyActionItem(
                kind=ActionKind.BLOCK, game_id="gx", action="SCALE",
                opportunity_type="aggressive_scale", decision_audit_id="ax",
            )
        ],
    )
    res = loop.run(daily)
    assert len(res.proposals) >= 1
    prop = next(p for p in res.proposals if p.current_strategy == "aggressive_scale")
    assert prop.knowledge_signal is not None
    assert prop.knowledge_signal["risk_flags"]
    assert prop.knowledge_confidence is not None
    assert prop.knowledge_confidence < prop.confidence  # 经验降权
    assert prop.requires_simulation is True             # 强制走审批
    assert any("知识增强" in line for line in res.patterns)
