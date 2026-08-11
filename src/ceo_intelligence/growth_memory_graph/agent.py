"""E17.7 — Growth Memory Graph 主入口（Agent）。

两种建图方式：
1. ingest_pipeline(dec_report, portfolio, reports)：实时吃 E17.3/4/6 产出（在线）
2. build_from_memory(execution_memory)：离线重放 E17.6 ExecutionMemory（重建）

run_pipeline() 串联 E17.1 → E17.2 → E17.3 → E17.4 → E17.6 → E17.7：
公司快照进，记忆图谱报告出。SIM 纪律：全程 real_api_called=False。
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from .ingest import (
    event_from_decision,
    event_from_execution_report,
    event_from_strategy,
)
from .models import ExecutionChain, MemoryGraphReport, NodeType
from .patterns import confidence_boost_for, extract_patterns, record_outcome
from .store import GrowthMemoryGraph


class GrowthMemoryGraphAgent:
    """对外 API：build / query / report。"""

    def __init__(self, graph: Optional[GrowthMemoryGraph] = None):
        self.graph = graph or GrowthMemoryGraph()

    # ------------------------------------------------------------------ #
    # 建图
    # ------------------------------------------------------------------ #
    def ingest_pipeline(self, dec_report, portfolio, reports) -> dict:
        """实时摄入一次全链路运行的产出（幂等）。"""
        total = {"nodes_added": 0, "edges_added": 0}
        events = (
            [event_from_decision(d) for d in dec_report.decisions]
            + [event_from_strategy(p) for p in portfolio.plans]
            + [event_from_execution_report(r) for r in reports]
        )
        for ev in events:
            r = self.graph.ingest_event(ev)
            total["nodes_added"] += r["nodes_added"]
            total["edges_added"] += r["edges_added"]
        return total

    def build_from_memory(self, execution_memory) -> dict:
        """离线重建：直接吃 E17.6 ExecutionMemory，无需重跑上游。"""
        return self.graph.build_from_execution_memory(execution_memory)

    # ------------------------------------------------------------------ #
    # 学习反馈
    # ------------------------------------------------------------------ #
    def record_outcome(self, execution_id: str, revenue_delta: float,
                       detail: str = "") -> bool:
        return record_outcome(self.graph, execution_id, revenue_delta, detail)

    def confidence_boost_for(self, strategy_type: str,
                             domain: Optional[str] = None,
                             action_type: Optional[str] = None) -> float:
        return confidence_boost_for(self.graph, strategy_type,
                                    domain=domain, action_type=action_type)

    # ------------------------------------------------------------------ #
    # 查询 / 报告
    # ------------------------------------------------------------------ #
    def trace(self, execution_id: str) -> Optional[ExecutionChain]:
        return self.graph.trace_execution(execution_id)

    def report(self, top_n: int = 10) -> MemoryGraphReport:
        stats = self.graph.stats()
        games = sorted(
            n.payload.get("game_id", "") for n in self.graph.query(NodeType.GAME)
        )
        chains: List[ExecutionChain] = []
        for n in self.graph.query(NodeType.EXECUTION):
            exec_id = n.id.split(":", 1)[1]
            chain = self.graph.trace_execution(exec_id)
            if chain is not None:
                chains.append(chain)
        chains.sort(key=lambda c: c.execution_id)

        results = self.graph.query(NodeType.RESULT)
        total_results = len(results)
        success_results = sum(1 for n in results if n.payload.get("success"))
        report = MemoryGraphReport(
            total_nodes=stats["nodes"],
            total_edges=stats["edges"],
            games=games,
            chains=chains[:top_n],
            patterns=extract_patterns(self.graph)[:top_n],
            summary={
                "chains": len(chains),
                "action_success_rate": (
                    success_results / total_results if total_results else 0.0
                ),
                "real_api_called": any(
                    n.payload.get("real_api_called") for n in results
                ),
                "nodes_by_type": {
                    k.removeprefix("nodes_"): v
                    for k, v in stats.items() if k.startswith("nodes_")
                },
            },
        )
        return report


# --------------------------------------------------------------------------- #
# 端到端流水线：Reality → Opportunity → Decision → Strategy → Execution → Memory Graph
# --------------------------------------------------------------------------- #
def run_pipeline(
    company,
    *,
    graph: Optional[GrowthMemoryGraph] = None,
    store=None,
    opportunity_memory=None,
    decision_memory=None,
    strategy_memory=None,
    execution_router=None,
    execution_memory=None,
    approval_outbox=None,
    segment: str = "global",
    top_n: int = 10,
    approval_queue_path: str = "data/ceo/approval_queue.jsonl",
    audit_dir: str = "data/ceo/audit",
    graph_path: str = "data/ceo/memory_graph.jsonl",
    created_at: str = "",
) -> Tuple[object, object, list, MemoryGraphReport]:
    """E17.1 → E17.7 全链路（默认全 SIM）。返回 (dec_report, portfolio, reports, graph_report)。"""
    from src.ceo_intelligence.execution_router.agent import (
        run_pipeline as _execution_pipeline,
    )

    dec_report, portfolio, reports = _execution_pipeline(
        company,
        store=store,
        opportunity_memory=opportunity_memory,
        decision_memory=decision_memory,
        strategy_memory=strategy_memory,
        execution_router=execution_router,
        execution_memory=execution_memory,
        approval_outbox=approval_outbox,
        segment=segment,
        top_n=top_n,
        approval_queue_path=approval_queue_path,
        audit_dir=audit_dir,
        created_at=created_at,
    )
    agent = GrowthMemoryGraphAgent(graph=graph or GrowthMemoryGraph(path=graph_path))
    agent.ingest_pipeline(dec_report, portfolio, reports)
    return dec_report, portfolio, reports, agent.report(top_n=top_n)


__all__ = ["GrowthMemoryGraphAgent", "run_pipeline"]
