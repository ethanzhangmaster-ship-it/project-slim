"""
P3.5 — GrowthKnowledgeGraph 功能测试。

覆盖：
- consolidate 从 5 源构建高层图谱（节点/边计数）
- 三大核心查询：why_game_succeeded / similar_games / strategy_for_lifecycle
- 分源查询：portfolio_decisions / recovery_history / patterns
- 纪律：real_api_called 恒 False；不写回源；幂等
"""
from __future__ import annotations

import tempfile

from src.ceo_intelligence.growth_memory_graph.knowledge import GrowthKnowledgeGraph
from src.ceo_intelligence.growth_memory_graph.models import (
    EdgeType,
    NodeType,
    node_id,
)
from src.ceo_intelligence.growth_memory_graph.store import GrowthMemoryGraph

from .helpers import (
    build_e17_graph,
    build_execution_memory,
    build_knowledge_graph,
    build_portfolio_result,
    build_recovery_store,
    build_strategy_memory,
)


class TestConsolidation:
    def test_consolidate_adds_nodes_and_edges(self):
        kg = build_knowledge_graph()
        s = kg.summary()
        # 至少一个高层节点（pattern/strategy/execution/recovery/portfolio）
        assert s["nodes"] > 0
        assert s["edges"] > 0
        # 高层节点类型应出现（8 类里至少 5 类被本 fixture 触发）
        bt = s["by_type"]
        assert bt.get("creative_pattern", 0) >= 1
        assert bt.get("ua_pattern", 0) >= 1
        assert bt.get("strategy_result", 0) >= 1
        assert bt.get("execution_outcome", 0) >= 1
        assert bt.get("recovery_history", 0) >= 1
        assert bt.get("portfolio_decision", 0) >= 1

    def test_real_api_called_locked_false(self):
        kg = build_knowledge_graph()
        assert kg.real_api_called is False
        assert kg.summary()["real_api_called"] is False

    def test_idempotent_reconsolidate(self):
        g = build_e17_graph()
        kg = GrowthKnowledgeGraph(graph=g)
        first = kg.consolidate(
            strategy_memory=build_strategy_memory(),
            execution_memory=build_execution_memory(),
            recovery_store=build_recovery_store(),
            portfolio_results=[build_portfolio_result()],
        )
        second = kg.consolidate(
            strategy_memory=build_strategy_memory(),
            execution_memory=build_execution_memory(),
            recovery_store=build_recovery_store(),
            portfolio_results=[build_portfolio_result()],
        )
        # 第二次不应再新增节点/边（图键幂等）
        assert second["nodes_added"] == 0
        assert second["edges_added"] == 0
        assert first["nodes_added"] > 0


class TestWhyGameSucceeded:
    def test_answers_for_known_game(self):
        kg = build_knowledge_graph()
        result = kg.why_game_succeeded("game_001")
        assert result["game_id"] == "game_001"
        assert result["strategy_results"]
        assert result["patterns"]
        assert result["execution_outcomes"]
        assert result["recovery_history"]   # 来自 exec_1 -> game_001
        assert result["portfolio_decisions"]
        assert isinstance(result["summary"], str) and result["summary"]

    def test_unknown_game_returns_empty_evidence(self):
        kg = build_knowledge_graph()
        result = kg.why_game_succeeded("game_999")
        assert result["strategy_results"] == []
        assert result["patterns"] == []
        assert result["portfolio_decisions"] == []
        assert "暂无" in result["summary"]


class TestSimilarGames:
    def test_finds_similar_by_shared_strategy(self):
        kg = build_knowledge_graph()
        sim = kg.similar_games("game_001")
        ids = [d["game_id"] for d in sim]
        assert "game_002" in ids
        # game_002 与 game_001 共享 creative_refresh 策略与 creative/ua 模式
        assert sim[0]["shared_count"] >= 1
        # 自身不应出现
        assert "game_001" not in ids


class TestStrategyQueries:
    def test_strategy_results_by_success_sorted(self):
        kg = build_knowledge_graph()
        rows = kg.strategy_results_by_success()
        assert rows
        rates = [r.success_rate for r in rows]
        assert rates == sorted(rates, reverse=True)

    def test_strategy_for_lifecycle_filters_dimension(self):
        kg = build_knowledge_graph()
        # growth -> ua 维度；creative_refresh 维度为 ua，应被纳入
        rows = kg.strategy_for_lifecycle("growth")
        assert rows
        for r in rows:
            assert r.dimension == "ua"

    def test_strategy_for_lifecycle_unknown_stage_returns_all(self):
        kg = build_knowledge_graph()
        rows = kg.strategy_for_lifecycle("unknown_stage")
        assert rows  # 回退为全部


class TestPerSourceQueries:
    def test_portfolio_decisions(self):
        kg = build_knowledge_graph()
        all_dec = kg.portfolio_decisions()
        assert len(all_dec) == 1
        assert all_dec[0].game_id == "game_001"
        assert all_dec[0].recommendation == "scale"
        assert all_dec[0].guard == "auto"
        # 按游戏过滤
        assert len(kg.portfolio_decisions("game_001")) == 1
        assert len(kg.portfolio_decisions("game_999")) == 0

    def test_recovery_history(self):
        kg = build_knowledge_graph()
        all_rec = kg.recovery_history()
        assert len(all_rec) == 1
        assert all_rec[0].failure_type == "timeout"
        # 通过 execution_id 解析挂到 game_001
        assert len(kg.recovery_history("game_001")) == 1
        assert len(kg.recovery_history("game_999")) == 0

    def test_patterns_by_kind(self):
        kg = build_knowledge_graph()
        assert kg.creative_patterns()
        assert kg.ua_patterns()
        # 本 fixture 未灌 monetization 域结果
        assert kg.monetization_patterns() == []


class TestNoWriteBack:
    def test_sources_not_mutated(self):
        # 源对象独立构造，consolidate 只读，不应改变其内容
        sm = build_strategy_memory()
        em = build_execution_memory()
        rs = build_recovery_store()
        n_states_before = len(sm.all_states())
        n_exec_before = len(em.all())
        n_rec_before = len(rs.all())

        g = build_e17_graph()
        kg = GrowthKnowledgeGraph(graph=g)
        kg.consolidate(
            strategy_memory=sm,
            execution_memory=em,
            recovery_store=rs,
            portfolio_results=[build_portfolio_result()],
        )

        # 源数据量不变（无写回）
        assert len(sm.all_states()) == n_states_before
        assert len(em.all()) == n_exec_before
        assert len(rs.all()) == n_rec_before
        # 底层 E17.7 图原始节点未被删除
        assert g.get_node(node_id(NodeType.GAME, "game_001")) is not None
        assert g.get_node(node_id(NodeType.RESULT, "act_1a")) is not None


class TestEmptySources:
    def test_consolidate_with_no_sources_still_builds_patterns(self):
        # 仅有 E17.7 图，不传其余源 -> 仍能派生 creative/ua 模式
        g = build_e17_graph()
        kg = GrowthKnowledgeGraph(graph=g)
        counts = kg.consolidate()
        assert counts["nodes_added"] >= 2  # 至少 creative + ua 模式
        assert kg.why_game_succeeded("game_001")["patterns"]
